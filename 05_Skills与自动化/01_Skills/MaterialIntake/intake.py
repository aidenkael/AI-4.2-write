#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MaterialIntake intake —— 新素材入库（Phase 2B2）。

薄层职责（不膨胀 catalog.py）：
  scan   扫描 01_原始素材/00_待入库，输出 deterministic 事实
         （path / filename / sha256 / exact_duplicate_matches / possible_existing_candidates）
  apply  校验 explicit intake plan → 安全移动（move journal + rollback）→ ledger mutation
         → catalog.refresh_and_render() →（默认）post_action SAFE_COMMIT_PUSH

架构（对应 SKILL 第 5 节）：
  用户 → Agent → intake scan → Agent 语义判断 → explicit intake plan（系统 TEMP，不 tracked）
  → deterministic runtime apply → catalog refresh → post-action writeback

禁止：
  - runtime 内接 LLM API；不硬编码 书名→分类 字典（旧 CLASSIFY 字典已废止）
  - runtime fuzzy merge（不因标题近似自动合并；同名/同作者是否同一作品由 Agent 判断）
  - 覆盖 destination 已存在文件（SHA 相同 → duplicate；SHA 不同 → <stem>__<sha前8位><suffix>）
  - 分配非 book_XXXX namespace / 补历史 gap / 复用删除 ID

用法：
  python intake.py --root E:/AI-Write scan            # 扫描 inbox，输出 JSON 事实
  python intake.py --root E:/AI-Write apply --plan <plan.json> [--no-git-sync]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog  # noqa: E402
import post_action  # noqa: E402

INBOX_DIR = "00_待入库"
ROLE_DIR = {
    "REFERENCE_WORK": "01_参考作品",
    "RESEARCH": "02_研究资料",
    "LOOSE_MATERIAL": "03_零散素材",
}
VALID_ACTIONS = ("NEW_ASSET", "ATTACH_EXISTING", "REVIEW")
VALID_TYPES = ("REFERENCE_WORK", "RESEARCH", "LOOSE_MATERIAL")
UNSUPPORTED_SUFFIXES = (".doc", ".docx")
ID_RE = re.compile(r"^book_(\d{4})$")

# MaterialIntake 动作允许进 Git 的 tracked 面（01_原始素材 元数据 + 新目录 .gitkeep + README）
INTAKE_ALLOWLIST = [
    "01_原始素材/素材资产.json",
    "01_原始素材/素材清单.csv",
    "01_原始素材/素材总索引.md",
    "01_原始素材/README.md",
    "01_原始素材/00_待入库/.gitkeep",
    "01_原始素材/01_参考作品/.gitkeep",
    "01_原始素材/02_研究资料/.gitkeep",
    "01_原始素材/03_零散素材/.gitkeep",
]


# --------------------------------------------------------------------------- #
# scan
# --------------------------------------------------------------------------- #

def scan_inbox(mat_dir: Path, ledger: dict | None = None) -> list[dict]:
    """扫描 00_待入库：每文件输出 path/filename/sha256 与 deterministic identity hints。

    ledger 为 None 时跳过去重/候选匹配（scan 不要求 ledger 存在）。
    """
    inbox = mat_dir / INBOX_DIR
    results = []
    if not inbox.exists():
        return results
    known_shas = _collect_known_shas(ledger) if ledger else {}
    for p in sorted(inbox.iterdir()):
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        rel = f"{INBOX_DIR}/{p.name}"
        sha = catalog.sha256_file(p)
        entry = {
            "path": rel,
            "filename": p.name,
            "sha256": sha,
            "suffix": p.suffix.lower(),
            "unsupported": p.suffix.lower() in UNSUPPORTED_SUFFIXES,
            "exact_duplicate_matches": _exact_matches(known_shas, sha),
            "possible_existing_candidates": _name_candidates(ledger, p.name) if ledger else [],
        }
        results.append(entry)
    return results


def _collect_known_shas(ledger: dict | None) -> dict[str, str]:
    """已知内容 SHA → 归属描述（asset.files 与 container original）。"""
    known: dict[str, str] = {}
    if not ledger:
        return known
    for a in ledger.get("assets", []):
        for f in a.get("files", []):
            known.setdefault(f["sha256"], f"{a['id']}({Path(f['path']).name})")
    for c in ledger.get("containers", []):
        op = c.get("original") or {}
        if op.get("sha256"):
            known.setdefault(op["sha256"], f"container:{c.get('id')}")
    return known


def _exact_matches(known_shas: dict[str, str], sha: str) -> list[str]:
    return [known_shas[sha]] if sha in known_shas else []


def _name_candidates(ledger: dict | None, filename: str) -> list[str]:
    """文件名与 asset.name 的双向子串匹配（简单可得才给，宁缺毋滥；runtime 不做自动合并）。"""
    if not ledger:
        return []
    stem = Path(filename).stem.lower().replace("_", "").replace(" ", "")
    out = []
    for a in ledger.get("assets", []):
        n = (a.get("name") or "").lower().replace(" ", "")
        if not n:
            continue
        if n in stem or stem in n:
            out.append(f"{a['id']}({a['name']})")
    return out


# --------------------------------------------------------------------------- #
# plan validation
# --------------------------------------------------------------------------- #

def load_plan(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"intake plan 读取失败: {exc}") from exc
    if not isinstance(data.get("items"), list):
        raise ValueError("intake plan 无效：缺少 items 列表")
    return data


def validate_plan(plan: dict, ledger: dict, inbox: Path) -> list[str]:
    """完整校验 plan；返回错误列表（空 = 可执行）。不执行任何移动。"""
    errors = []
    items = plan.get("items", [])
    for i, item in enumerate(items):
        tag = f"items[{i}]"
        action = item.get("action")
        files = item.get("files") or []
        if action not in VALID_ACTIONS:
            errors.append(f"{tag}: 非法 action {action!r}")
            continue
        if not files:
            errors.append(f"{tag}: files 为空")
            continue
        for rel in files:
            src = inbox / Path(rel).name
            if not src.is_file():
                errors.append(f"{tag}: inbox 文件不存在 {rel}")
        if action == "NEW_ASSET":
            if item.get("type") not in VALID_TYPES:
                errors.append(f"{tag}: NEW_ASSET type 非法 {item.get('type')!r}（仅 {VALID_TYPES}）")
            if not (item.get("name") or "").strip():
                errors.append(f"{tag}: NEW_ASSET 缺少 name")
        elif action == "ATTACH_EXISTING":
            aid = item.get("asset_id")
            if aid not in {a["id"] for a in ledger["assets"]}:
                errors.append(f"{tag}: asset_id 不存在 {aid!r}")
        elif action == "REVIEW":
            if not item.get("reason"):
                errors.append(f"{tag}: REVIEW 缺少 reason")
    return errors


# --------------------------------------------------------------------------- #
# apply
# --------------------------------------------------------------------------- #

class _MoveError(Exception):
    pass


def allocate_next_id(ledger: dict) -> str:
    """max(existing numeric book id) + 1；不补 gap、不复用删除 ID。"""
    nums = []
    for a in ledger["assets"]:
        m = ID_RE.match(a["id"])
        if m:
            nums.append(int(m.group(1)))
    nxt = (max(nums) + 1) if nums else 1
    return f"book_{nxt:04d}"


def safe_name(name: str) -> str:
    """目录名安全化：去除非法字符 / 首尾空白与点 / 控制符；截断 80 字符。"""
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", name).strip().strip(".")
    if not s:
        s = "未命名"
    return s[:80]


def route_dir(role: str) -> str:
    return ROLE_DIR[role]


def _dest_for_new(role: str, name: str, mat_dir: Path) -> Path:
    """NEW_ASSET 目标目录：<role_dir>/<safe_name>/（不再建立二级 taxonomy）。"""
    return mat_dir / route_dir(role) / safe_name(name)


def _dest_for_attach(ledger: dict, asset_id: str, mat_dir: Path) -> Path:
    """ATTACH_EXISTING 目标：该 asset 当前 primary source 所在目录（Phase 2C 前同 asset 不拆两套目录）。"""
    a = next(x for x in ledger["assets"] if x["id"] == asset_id)
    primaries = [f for f in a["files"] if f["primary"]]
    src = (primaries[0] if primaries else a["files"][0])["path"]
    return mat_dir / Path(src).parent


def _resolve_dest(src: Path, dest_dir: Path, sha: str) -> Path:
    """目标路径解析：同名文件已存在且 SHA 不同 → <stem>__<sha前8位><suffix>（绝不覆盖）。"""
    cand = dest_dir / src.name
    if not cand.exists():
        return cand
    if catalog.sha256_file(cand) == sha:
        return cand  # 同名同内容 → 调用方按 duplicate 处理
    stem, suffix = src.stem, src.suffix
    return dest_dir / f"{stem}__{sha[:8]}{suffix}"


def _canonical_ref_path(ledger: dict, sha: str, mat_dir: Path) -> Path | None:
    """返回匹配 SHA 的 canonical source 文件路径（asset.files 或 container original），不存在返回 None。"""
    for a in ledger["assets"]:
        for f in a["files"]:
            if f["sha256"] == sha:
                return mat_dir / f["path"]
    for c in ledger["containers"]:
        op = c.get("original") or {}
        if op.get("sha256") == sha and op.get("path"):
            return mat_dir / op["path"]
    return None


def _rollback(journal: list[dict], mat_dir: Path, report: dict) -> None:
    """按逆序回滚已移动文件（journal 每项含 from/to；含移动后校验失败项）。回滚失败 → RECOVERY_REQUIRED。"""
    for j in reversed(journal):
        dst = mat_dir / j["to"]
        src = mat_dir / j["from"]
        try:
            if dst.exists():
                dst.replace(src)
                report["rolled_back"].append(j["from"])
                # 清理本次新建的空目录（ATTACH 目标在既有 asset 目录 → rmdir 非空失败，天然安全）
                try:
                    dst.parent.rmdir()
                except OSError:
                    pass
        except OSError as exc:
            report["errors"].append(f"RECOVERY_REQUIRED rollback 失败 {j['to']}: {exc}")
            break


def apply_plan(plan: dict, ledger: dict, root: Path) -> dict:
    """执行 intake plan：validate → 移动（journal + SHA 校验）→ ledger mutation → refresh。

    返回 report：
      {"ok", "new_ids", "attached", "duplicates_removed", "reviews", "moves",
       "errors", "rolled_back"}
    任何移动失败 → 逆序回滚已移动文件；ledger 不写半份。
    """
    mat_dir = root / catalog.MATERIAL_DIR_NAME
    inbox = mat_dir / INBOX_DIR
    report = {"ok": False, "new_ids": [], "attached": [], "duplicates_removed": [],
              "reviews": [], "moves": [], "errors": [], "rolled_back": []}

    errors = validate_plan(plan, ledger, inbox)
    if errors:
        report["errors"] = errors
        return report

    # 逐文件：inbox 源 + 当前 SHA + 所属 plan item
    planned: list[tuple[Path, str, dict]] = []
    for item in plan["items"]:
        for rel in item["files"]:
            src = inbox / Path(rel).name
            if src.is_file():
                planned.append((src, catalog.sha256_file(src), item))

    # EXACT_DUPLICATE 自动处理（deterministic）：三条件全满足才删 inbox 副本，否则 STOP
    known_shas = _collect_known_shas(ledger)
    remaining: list[tuple[Path, str, dict]] = []
    for src, sha, item in planned:
        if sha not in known_shas:
            remaining.append((src, sha, item))
            continue
        ref_path = _canonical_ref_path(ledger, sha, mat_dir)
        if ref_path is not None and ref_path.exists():
            src.unlink()
            report["duplicates_removed"].append({"file": f"{INBOX_DIR}/{src.name}",
                                                 "sha": sha, "match": known_shas[sha]})
        else:
            report["errors"].append(
                f"EXACT_DUPLICATE 删除条件不满足（canonical source 缺失）: "
                f"{INBOX_DIR}/{src.name} match={known_shas[sha]} → 保留文件，STOP")
            return report

    # 执行移动（REVIEW 不动；NEW_ASSET/ATTACH_EXISTING 移动并记录 journal）
    journal: list[dict] = []
    try:
        for src, sha, item in remaining:
            action = item["action"]
            if action == "REVIEW":
                report["reviews"].append(f"{INBOX_DIR}/{src.name}")
                continue
            if action == "NEW_ASSET":
                dest_dir = _dest_for_new(item["type"], item["name"], mat_dir)
            else:
                dest_dir = _dest_for_attach(ledger, item["asset_id"], mat_dir)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = _resolve_dest(src, dest_dir, sha)
            if dest.exists():
                # 同名同 SHA → duplicate（上轮已删）；同名不同 SHA → collision 文件名；到这里仍存在 → 防御
                raise _MoveError(f"destination 已存在且无法安全命名: {dest}")
            # 先入 journal 再移动：若移动后 SHA 校验失败，rollback 能连同本项一起回滚
            journal.append({"from": f"{INBOX_DIR}/{src.name}",
                            "to": dest.relative_to(mat_dir).as_posix(),
                            "sha": sha, "item": item})
            src.replace(dest)
            after = catalog.sha256_file(dest)
            if sha != after:
                raise _MoveError(
                    f"move SHA 不匹配: {src.name} before={sha} after={after}")
            report["moves"].append({"from": f"{INBOX_DIR}/{src.name}",
                                    "to": dest.relative_to(mat_dir).as_posix(),
                                    "sha": sha, "before": sha, "after": after})
    except _MoveError as exc:
        if exc.args:
            report["errors"].append(str(exc.args[0]))
        _rollback(journal, mat_dir, report)
        return report

    # 全部移动成功 → 内存 mutation → 落盘 ledger → refresh 三视图
    old_ids = {a["id"] for a in ledger["assets"]}
    new_ledger = _mutate_ledger(ledger, journal)
    try:
        catalog.write_ledger(new_ledger, mat_dir / catalog.LEDGER_FILENAME)
    except OSError as exc:
        report["errors"].append(f"写 ledger 失败: {exc}")
        _rollback(journal, mat_dir, report)
        return report
    rc = catalog.refresh_and_render(root)
    if rc != 0:
        report["errors"].append(f"catalog refresh 失败 rc={rc}（ledger 已写，需人工检查）")
        return report

    report["new_ids"] = sorted(a["id"] for a in new_ledger["assets"]
                               if a["id"] not in old_ids)
    report["attached"] = [j["to"] for j in journal if j["item"]["action"] == "ATTACH_EXISTING"]
    report["ok"] = True
    return report


def _mutate_ledger(ledger: dict, journal: list[dict]) -> dict:
    """对内存 ledger 应用移动结果：NEW_ASSET 建 asset（按 deterministic inbox path 排序分配 ID）；
    ATTACH_EXISTING 追加 file（primary 默认 False；make_primary=true 时旧 primary 降级）。"""
    new_ledger = json.loads(json.dumps(ledger, ensure_ascii=False))  # deep copy

    # NEW_ASSET：按 deterministic inbox path 排序后分配 ID（同一 item 多文件 → 一个 asset）
    new_items = sorted([j for j in journal if j["item"]["action"] == "NEW_ASSET"],
                       key=lambda j: j["from"])
    seen: list[dict] = []
    for j in new_items:
        if j["item"] not in seen:
            seen.append(j["item"])
    for item in seen:
        files = [m for m in journal if m["item"] is item and m["item"]["action"] == "NEW_ASSET"]
        file_recs = []
        for m in sorted(files, key=lambda x: x["from"]):
            file_recs.append({"path": m["to"], "sha256": m["sha"],
                              "primary": not file_recs})
        if not file_recs:
            continue
        new_id = allocate_next_id(new_ledger)
        role = item["type"]
        new_ledger["assets"].append({
            "id": new_id,
            "name": item["name"],
            "type": role,
            "author": item.get("author") or "",
            "tags": list(item.get("tags") or [])[:5],
            "notes": item.get("notes") or "",
            "files": file_recs,
            "purification": {"status": "不适用" if role == "LOOSE_MATERIAL" else "未处理",
                             "evidence": None},
            "knowledge": {"status": "未开始"},
        })

    # ATTACH_EXISTING：追加 file 到现有 asset（ID 不变）
    attach_items = [j for j in journal if j["item"]["action"] == "ATTACH_EXISTING"]
    for j in attach_items:
        item = j["item"]
        asset = next(a for a in new_ledger["assets"] if a["id"] == item["asset_id"])
        make_primary = bool(item.get("make_primary"))
        if make_primary:
            for f in asset["files"]:
                f["primary"] = False
        asset["files"].append({"path": j["to"], "sha256": j["sha"],
                               "primary": make_primary})
        asset["files"].sort(key=lambda f: f["path"])

    new_ledger["assets"].sort(key=lambda a: a["id"])
    return new_ledger


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="MaterialIntake 新素材入库（scan / apply）")
    ap.add_argument("--root", default=os.getcwd(), help="仓库根目录（默认当前目录）")
    ap.add_argument("--no-git-sync", action="store_true",
                    help="apply 后不自动 commit/push（仅供测试/调试/明确本地操作）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("scan", help="扫描 00_待入库，输出 JSON 事实到 stdout")

    p2 = sub.add_parser("apply", help="校验并执行 intake plan")
    p2.add_argument("--plan", required=True, help="intake plan JSON 路径（建议系统 TEMP，不 tracked）")

    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    mat_dir = root / catalog.MATERIAL_DIR_NAME
    if not mat_dir.exists():
        print(f"[intake] ERROR: 缺少 {mat_dir}")
        return 2

    if args.cmd == "scan":
        ledger_path = mat_dir / catalog.LEDGER_FILENAME
        ledger = catalog.load_ledger(ledger_path) if ledger_path.exists() else None
        facts = scan_inbox(mat_dir, ledger)
        print(json.dumps({"inbox": INBOX_DIR, "files": facts}, ensure_ascii=False, indent=2))
        return 0

    # apply
    try:
        plan = load_plan(Path(args.plan))
        ledger = catalog.load_ledger(mat_dir / catalog.LEDGER_FILENAME)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"[intake] ERROR: {exc}")
        return 2

    if not args.no_git_sync:
        ok, reason = post_action.precheck(root)
        if not ok:
            print(f"[intake] PRECHECK FAILED: {reason} → STOP（不执行 intake）")
            return 1

    report = apply_plan(plan, ledger, root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        return 1

    if not args.no_git_sync:
        outcome = post_action.safe_commit_push(root, INTAKE_ALLOWLIST,
                                               "chore: intake new materials")
        print(f"[intake] POST_ACTION={outcome}")
        if outcome.startswith("STOP_"):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
