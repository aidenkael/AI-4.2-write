#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MaterialIntake intake —— 新素材入库（Phase 2B2 / 2B2.1 transactional）。

薄层职责（不膨胀 catalog.py）：
  scan   扫描 01_原始素材/00_待入库，输出 deterministic 事实
         （path / filename / sha256 / exact_duplicate_matches / possible_existing_candidates）
  apply  校验 explicit intake plan → 只读 catalog health check（STOP_BEFORE_MOVE）
         → 三份 metadata byte snapshot → 安全移动（move journal + rollback）→ ledger mutation
         → catalog settlement（refresh 三视图）→ 最后删除 inbox duplicate
         →（默认）post_action SAFE_COMMIT_PUSH

Phase 2B2.1 事务边界（INTAKE_TRANSACTIONAL = TRUE）：
  - move 前基于 canonical ledger 做只读 health check；已有 MISSING_REGISTERED_FILE /
    invalid ledger / container original 缺失 → STOP_BEFORE_MOVE，不开始 intake；
  - 修改任何 canonical tracked state 前保存 素材资产.json / 素材清单.csv / 素材总索引.md
    的 byte snapshot（缺失记录为 missing snapshot）；
  - write_ledger / refresh 返回非 0 / refresh 抛异常 / CSV|MD 写入异常 → 完整回滚：
    文件逆序恢复 + 三份 metadata 恢复原始 bytes + 新建空目录清理（INTAKE_CANONICAL_PARTIAL_WRITE = FALSE）；
    只有 rollback 本身失败才 RECOVERY_REQUIRED；
  - exact duplicate 只在 settlement 全部成功后最后删除（失败时 duplicate 仍留 inbox）；
  - Git sync 失败不属于事务范围：settlement 已完成后保留现场，人工处理 Git（不回滚已完成的 intake）。

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
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog  # noqa: E402
import post_action  # noqa: E402

INBOX_DIR = "00_待入库"
# 作者可见的三种正常素材类型 ↔ 物理角色目录（唯一真相：Workbench 类型 == ledger 类型 == 目录含义）。
ROLE_DIR = {
    "REFERENCE_WORK": "01_原著",
    "METHOD_SOURCE": "02_技巧类",
    "LOOSE_MATERIAL": "03_其他",
}
# 反查：物理角色目录名 → canonical type（manual reconcile 用）。
ROLE_DIR_TO_TYPE = {v: k for k, v in ROLE_DIR.items()}
VALID_ACTIONS = ("NEW_ASSET", "ATTACH_EXISTING", "REVIEW")
# RESEARCH 不再是作者可创建的普通类型；历史 RESEARCH 记录由迁移确定性归入 LOOSE_MATERIAL。
VALID_TYPES = ("REFERENCE_WORK", "LOOSE_MATERIAL", "METHOD_SOURCE")
UNSUPPORTED_SUFFIXES = (".doc", ".docx")
ID_RE = re.compile(r"^book_(\d{4})$")

# MaterialIntake 动作允许进 Git 的 tracked 面（Phase 2B2.1 收窄为最小必要面：
# 仅三份 material state files。README / .gitkeep 属 Phase 2B2 安装时一次性 commit，
# 动作期间意外修改 → STOP_UNEXPECTED_DIFF，避免被顺手提交）
INTAKE_ALLOWLIST = [
    "01_原始素材/素材资产.json",
    "01_原始素材/素材清单.csv",
    "01_原始素材/素材总索引.md",
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


class _SettlementError(Exception):
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


def _rmdir_chain(d: Path) -> None:
    """从 d 向上逐级删除空目录；非空或到达 01_原始素材 即停。"""
    while d.name != catalog.MATERIAL_DIR_NAME:
        try:
            d.rmdir()
        except OSError:
            break
        d = d.parent


def _rollback(journal: list[dict], mat_dir: Path, report: dict) -> None:
    """按逆序回滚已移动文件（journal 每项含 from/to；含移动后校验失败项），并清理新建空目录。
    回滚失败 → RECOVERY_REQUIRED。"""
    for j in reversed(journal):
        dst = mat_dir / j["to"]
        src = mat_dir / j["from"]
        try:
            if dst.exists():
                dst.replace(src)
                report["rolled_back"].append(j["from"])
                _rmdir_chain(dst.parent)
        except OSError as exc:
            report["errors"].append(f"RECOVERY_REQUIRED rollback 失败 {j['to']}: {exc}")
            break


def _catalog_health_errors(root: Path, ledger: dict) -> list[str]:
    """move 前只读 catalog health check（不写盘、不重算 SHA）。

    基于当前 canonical ledger 验证：
      - schema 合法（validate_ledger）
      - 磁盘 registered files 全部存在（MISSING_REGISTERED_FILE）
      - container original 存在
    发现任何问题 → 调用方 STOP_BEFORE_MOVE，不开始 intake。
    """
    mat_dir = root / catalog.MATERIAL_DIR_NAME
    errors = []
    errors.extend(catalog.validate_ledger(ledger))
    for a in ledger["assets"]:
        for f in a["files"]:
            if not (mat_dir / f["path"]).is_file():
                errors.append(f"MISSING_REGISTERED_FILE: {a['id']}: {f['path']}")
    for c in ledger["containers"]:
        op = c.get("original") or {}
        if op.get("path") and not (mat_dir / op["path"]).is_file():
            errors.append(f"MISSING_REGISTERED_FILE: container:{c.get('id')}: {op['path']}")
    return errors


def _snapshot_metadata(mat_dir: Path) -> dict[str, bytes | None]:
    """三份 canonical metadata（ledger / CSV / MD）的 byte snapshot；缺失 → None（missing snapshot）。"""
    out = {}
    for rel in (catalog.LEDGER_FILENAME, catalog.LEGACY_CSV_FILENAME,
                catalog.INDEX_FILENAME):
        p = mat_dir / rel
        out[rel] = p.read_bytes() if p.exists() else None
    return out


def _rollback_all(journal: list[dict], mat_dir: Path, report: dict,
                  snapshots: dict[str, bytes | None]) -> None:
    """完整事务回滚（catalog settlement 失败路径）：
      A. 按 journal 逆序恢复所有已移动文件（含新建空目录清理）
      B. 恢复 ledger / CSV / MD 原始 bytes（原本缺失 → 删除本次新建）
    只有 rollback 本身失败才记 RECOVERY_REQUIRED。report.ok 由调用方置 false。
    """
    _rollback(journal, mat_dir, report)
    for rel, data in snapshots.items():
        p = mat_dir / rel
        try:
            if data is None:
                if p.exists():
                    p.unlink()
            else:
                p.write_bytes(data)
        except OSError as exc:
            report["errors"].append(f"RECOVERY_REQUIRED 恢复 {rel} 失败: {exc}")


def apply_plan(plan: dict, ledger: dict, root: Path) -> dict:
    """执行 intake plan：validate → health check → snapshot → 移动（journal + SHA 校验）
    → ledger mutation → catalog settlement → 最后删除 inbox duplicate。

    Phase 2B2.1（INTAKE_TRANSACTIONAL = TRUE）：
      - move 前基于 canonical ledger 做只读 health check（失败 → STOP_BEFORE_MOVE）；
      - 修改任何 canonical tracked state 前保存三份 metadata byte snapshot；
      - write_ledger / refresh 非 0 / refresh 异常 / CSV|MD 写入异常 → 完整回滚
        （文件 + 三份 metadata + 新建空目录），不留下“ledger 已写需人工检查”的正常失败路径；
      - exact duplicate 只在 settlement 全部成功后最后删除（失败时 inbox 不变）；
      - Git sync 失败不在本函数范围内（settlement 已完成 → 保留现场人工处理 Git）。

    返回 report：
      {"ok", "new_ids", "attached", "duplicates_removed", "reviews", "moves",
       "errors", "rolled_back"}
    """
    mat_dir = root / catalog.MATERIAL_DIR_NAME
    inbox = mat_dir / INBOX_DIR
    report = {"ok": False, "new_ids": [], "attached": [], "duplicates_removed": [],
              "reviews": [], "moves": [], "errors": [], "rolled_back": []}

    errors = validate_plan(plan, ledger, inbox)
    if errors:
        report["errors"] = errors
        return report

    # 0) move 前 catalog health check（只读）：现有仓已损坏 → STOP_BEFORE_MOVE，不开始 intake
    health_errors = _catalog_health_errors(root, ledger)
    if health_errors:
        report["errors"] = [f"STOP_BEFORE_MOVE: {e}" for e in health_errors]
        return report

    # 1) 事务开始：三份 canonical metadata byte snapshot（缺失 → missing snapshot）
    snapshots = _snapshot_metadata(mat_dir)

    # 逐文件：inbox 源 + 当前 SHA + 所属 plan item
    planned: list[tuple[Path, str, dict]] = []
    for item in plan["items"]:
        for rel in item["files"]:
            src = inbox / Path(rel).name
            if src.is_file():
                planned.append((src, catalog.sha256_file(src), item))

    # EXACT_DUPLICATE 确认（deterministic）：三条件全满足才记录待删，暂不 unlink；
    # 全部 settlement 成功后最后删除（失败时 duplicate 仍留 inbox，不造成部分状态改变）
    known_shas = _collect_known_shas(ledger)
    remaining: list[tuple[Path, str, dict]] = []
    pending_duplicates: list[dict] = []
    for src, sha, item in planned:
        if sha not in known_shas:
            remaining.append((src, sha, item))
            continue
        ref_path = _canonical_ref_path(ledger, sha, mat_dir)
        if ref_path is not None and ref_path.exists():
            pending_duplicates.append({"file": f"{INBOX_DIR}/{src.name}",
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

    # 全部移动成功 → 内存 mutation → 落盘 ledger → catalog settlement（refresh 三视图）
    old_ids = {a["id"] for a in ledger["assets"]}
    new_ledger = _mutate_ledger(ledger, journal)
    try:
        catalog.write_ledger(new_ledger, mat_dir / catalog.LEDGER_FILENAME)
        rc = catalog.refresh_and_render(root)
        if rc != 0:
            raise _SettlementError(f"catalog refresh 失败 rc={rc}")
    except Exception as exc:
        report["errors"].append(f"catalog settlement 失败: {exc}")
        _rollback_all(journal, mat_dir, report, snapshots)
        return report

    # 5) settlement 完整成功 → 最后删除 inbox duplicate（事务收尾）
    for d in pending_duplicates:
        try:
            (mat_dir / d["file"]).unlink()
            report["duplicates_removed"].append(d)
        except OSError as exc:
            report["errors"].append(f"删除 inbox duplicate 失败（settlement 已完成，不回滚）: "
                                    f"{d['file']}: {exc}")
            report["ok"] = False
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
# Manual Explorer reconcile（作者手动文件夹编辑在「刷新状态」时确定性并入 ledger）
# --------------------------------------------------------------------------- #

SUPPORTED_SOURCE_SUFFIXES = (".epub", ".pdf", ".txt")


def _folder_units(mat_dir: Path) -> list[dict]:
    """扫描三个角色目录；每个直接子文件夹 = 一个素材文件夹单元（manual sync unit）。

    只计入受支持来源文件（EPUB/PDF/TXT）；排除 .gitkeep / collection_manifest.json。
    无受支持文件的空文件夹忽略。files 按相对路径排序，第一个为 primary。
    """
    units: list[dict] = []
    for mtype, role_dir in sorted(ROLE_DIR.items(), key=lambda kv: kv[1]):
        base = mat_dir / role_dir
        if not base.is_dir():
            continue
        for folder in sorted(base.iterdir()):
            if not folder.is_dir():
                continue
            files: list[dict] = []
            for p in sorted(folder.rglob("*")):
                if not p.is_file():
                    continue
                if p.name == ".gitkeep" or p.name == catalog.MANIFEST_FILENAME:
                    continue
                if p.suffix.lower() not in SUPPORTED_SOURCE_SUFFIXES:
                    continue
                files.append({"path": p.relative_to(mat_dir).as_posix(),
                              "sha256": catalog.sha256_file(p), "primary": False})
            if not files:
                continue
            files[0]["primary"] = True
            units.append({
                "role_dir": role_dir, "type": mtype, "folder_name": folder.name,
                "rel_dir": folder.relative_to(mat_dir).as_posix(), "files": files,
                "fingerprint": catalog.content_fingerprint(files),
            })
    return units


def _structural_edit_detected(mat_dir: Path, ledger: dict) -> bool:
    """廉价结构快检（零 SHA）：登记来源是否都在磁盘 + 角色目录子文件夹集合是否与登记一致。

    无结构变化（未移动/改名/新建/删除文件夹）→ False，跳过昂贵的指纹匹配；
    任何结构差异 → True，进入完整内容指纹 reconcile。
    """
    recorded_dirs: set[str] = set()
    all_present = True
    for a in ledger["assets"]:
        for f in a.get("files", []):
            recorded_dirs.add(str(Path(f["path"]).parent.as_posix()))
            if not (mat_dir / f["path"]).is_file():
                all_present = False
    actual_dirs: set[str] = set()
    for role_dir in ROLE_DIR.values():
        base = mat_dir / role_dir
        if not base.is_dir():
            continue
        for folder in base.iterdir():
            if folder.is_dir():
                actual_dirs.add(folder.relative_to(mat_dir).as_posix())
    return (not all_present) or (recorded_dirs != actual_dirs)


def _finalized_package_kind(distill_dir: Path, asset_id: str) -> tuple[str | None, Path | None]:
    """返回 asset 在 02 的已定稿知识包类型（"bkp"/"method"/None）与其目录，用于类型变更时判定不兼容。"""
    if not distill_dir.exists():
        return None, None
    for d in sorted(distill_dir.iterdir()):
        if not d.is_dir() or not d.name.startswith(asset_id + "_"):
            continue
        if (d / "bkp" / "identity.json").is_file():
            return "bkp", d
        if (d / "method" / "identity.json").is_file():
            return "method", d
    return None, None


def reconcile_manual_edits(root: Path) -> dict:
    """把作者手动 Explorer 编辑（移动/改名/新建素材文件夹）确定性并入 canonical ledger。

    manual sync unit = 一个素材文件夹；身份 = 精确内容指纹（SHA multiset），绝不模糊标题合并。
      - 文件夹指纹唯一匹配一个既有 asset → 保留 id，更新 files[].path + canonical type
        （按所在角色目录）+ 名字（文件夹改名且唯一时）；
      - 文件夹指纹不匹配任何 asset → 注册为新 asset（类型按角色目录，名字按文件夹名）；
      - 指纹匹配多个 asset / 同一指纹出现在多个文件夹 / 映射歧义 → fail closed（不写盘）；
      - 既有 asset 登记来源在磁盘缺失 → 保留记录（绝不静默删除），记入 missing_sources；
      - asset 类型变更导致 02 已定稿包不兼容 → 把该包移入 06 recovery（不再可检索，不删除）。

    事务性：歧义/失败 → 不写任何文件；成功且有变化 → snapshot 三份 metadata → 写
    reconciled ledger → catalog.refresh_and_render(tolerate_missing) → 失败回滚三份 metadata。
    """
    mat_dir = root / catalog.MATERIAL_DIR_NAME
    distill_dir = root / catalog.DISTILL_DIR_NAME
    report: dict = {"ok": False, "changed": False, "moved": [], "renamed": [], "registered": [],
                    "type_changed": [], "missing_sources": [], "relocated_packages": [], "errors": []}

    ledger_path = mat_dir / catalog.LEDGER_FILENAME
    if not ledger_path.exists():
        report["ok"] = True  # 无 ledger 时不报错（由上层 refresh 统一处理）
        return report
    try:
        ledger = catalog.load_ledger(ledger_path)
    except (FileNotFoundError, RuntimeError) as exc:
        report["errors"].append(f"ledger 不可用：{exc}")
        return report

    # 廉价结构快检：无任何手动文件夹编辑 → 无需昂贵指纹匹配（后续 refresh 仍重算 SHA/派生状态）。
    if not _structural_edit_detected(mat_dir, ledger):
        report["ok"] = True
        return report

    units = _folder_units(mat_dir)

    # asset 内容指纹索引
    fp_index: dict[str, list[str]] = {}
    for a in ledger["assets"]:
        if not a.get("files"):
            continue
        fp_index.setdefault(catalog.content_fingerprint(a["files"]), []).append(a["id"])

    # fail closed：同一指纹出现在多个文件夹 / 匹配多个已登记 asset → 归属歧义
    errors: list[str] = []
    unit_fp_count: dict[str, int] = {}
    for u in units:
        unit_fp_count[u["fingerprint"]] = unit_fp_count.get(u["fingerprint"], 0) + 1
    for fp, cnt in unit_fp_count.items():
        if cnt > 1:
            errors.append("同一内容出现在多个素材文件夹，无法确定归属，请检查后重试。")
            break
    if not errors:
        for u in units:
            if len(fp_index.get(u["fingerprint"], [])) > 1:
                errors.append("同一内容匹配多个已登记素材，无法确定归属，请检查后重试。")
                break
    if errors:
        report["errors"] = errors
        return report  # fail closed：不写盘

    new_assets = json.loads(json.dumps(ledger["assets"], ensure_ascii=False))
    new_by_id = {a["id"]: a for a in new_assets}
    matched_ids: set[str] = set()
    changed = False

    for u in units:
        ids = fp_index.get(u["fingerprint"], [])
        if ids:
            asset_id = ids[0]
            matched_ids.add(asset_id)
            target = new_by_id[asset_id]
            if {f["path"] for f in target["files"]} != {f["path"] for f in u["files"]}:
                target["files"] = json.loads(json.dumps(u["files"], ensure_ascii=False))
                report["moved"].append({"id": asset_id, "to": u["rel_dir"]})
                changed = True
            if target["type"] != u["type"]:
                report["type_changed"].append({"id": asset_id, "from": target["type"], "to": u["type"]})
                target["type"] = u["type"]
                changed = True
            folder_name = safe_name(u["folder_name"])
            if folder_name and folder_name != target["name"]:
                report["renamed"].append({"id": asset_id, "from": target["name"], "to": folder_name})
                target["name"] = folder_name
                changed = True
        else:
            new_id = allocate_next_id({"assets": new_assets})
            new_asset = {
                "id": new_id, "name": safe_name(u["folder_name"]), "type": u["type"],
                "author": "", "tags": [], "notes": "",
                "files": json.loads(json.dumps(u["files"], ensure_ascii=False)),
                "purification": {"status": "不适用" if u["type"] == "LOOSE_MATERIAL" else "未处理",
                                 "evidence": None},
                "knowledge": {"status": "未开始"},
            }
            new_assets.append(new_asset)
            new_by_id[new_id] = new_asset
            fp_index.setdefault(u["fingerprint"], []).append(new_id)
            report["registered"].append({"id": new_id, "name": new_asset["name"], "type": u["type"]})
            changed = True

    for a in ledger["assets"]:
        if a["id"] in matched_ids or not a.get("files"):
            continue
        if not any((mat_dir / f["path"]).is_file() for f in a["files"]):
            report["missing_sources"].append(a["id"])

    # 类型变更 → 不兼容的 02 已定稿包移入 06 recovery（不再可检索；不删除）
    for tc in report["type_changed"]:
        kind, pkg_dir = _finalized_package_kind(distill_dir, tc["id"])
        if kind is None or pkg_dir is None:
            continue
        expected = "method" if tc["to"] == "METHOD_SOURCE" else "bkp"
        if kind == expected:
            continue
        recovery = root / "06_工作区" / "BookDistill" / "_incompatible_recovery"
        try:
            recovery.mkdir(parents=True, exist_ok=True)
            dest = recovery / pkg_dir.name
            shutil.move(str(pkg_dir), str(dest))
        except OSError as exc:
            report["errors"].append(f"迁移不兼容知识包失败，已停止：{exc}")
            return report  # fail closed
        report["relocated_packages"].append({"id": tc["id"], "to": str(dest)})
        changed = True

    if not changed:
        report["ok"] = True
        return report

    snapshots = _snapshot_metadata(mat_dir)
    new_assets.sort(key=lambda a: a["id"])
    new_ledger = {"schema_version": ledger["schema_version"], "assets": new_assets,
                  "containers": ledger["containers"]}
    try:
        catalog.write_ledger(new_ledger, mat_dir / catalog.LEDGER_FILENAME)
        rc = catalog.refresh_and_render(root, tolerate_missing=True)
        if rc != 0:
            raise RuntimeError(f"catalog refresh rc={rc}")
    except Exception as exc:  # noqa: BLE001
        for rel, data in snapshots.items():
            p = mat_dir / rel
            try:
                if data is None:
                    if p.exists():
                        p.unlink()
                else:
                    p.write_bytes(data)
            except OSError:
                pass
        report["errors"].append("刷新素材状态失败，已回滚，未改动素材登记。")
        return report

    report["ok"] = True
    report["changed"] = True
    return report


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
