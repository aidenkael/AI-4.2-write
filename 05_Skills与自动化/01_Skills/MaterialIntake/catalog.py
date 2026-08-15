#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MaterialIntake catalog builder —— 素材资产 canonical ledger 构建器（CATALOG_FOUNDATION_ONLY）。

输入（全部只读，绝不修改）：
  - 01_原始素材/ 磁盘全量扫描（SHA256，by-file）
  - 01_原始素材/素材清单.csv（legacy 22 列，仅作 migration/bootstrap 输入）
  - 02_原著蒸馏/book_xxxx_*/bkp/identity.json（knowledge evidence，FINALIZED 状态）
  - 01_原始素材/**/collection_manifest.json（container evidence，Local Only）
  - 06_工作区/SourcePrepare/<book_id>_<书名>/metadata.json（A 级提纯证据，SP 正式合同路径）

输出：
  - 01_原始素材/素材资产.json        machine canonical ledger（tracked）
  - 01_原始素材/素材总索引.md        人类/GitHub 总览（tracked）
  - %TEMP%/素材清单_v1_preview.csv   9 列作者视图 preview（不 tracked）

确定性保证：
  - 无时间戳 / 无 volatile 字段
  - JSON sort_keys + assets/files/containers 显式排序
  - 同输入重复执行 byte-for-byte 幂等

用法：
  python catalog.py --root E:/AI-Write [--preview-dir DIR]
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from pathlib import Path

MATERIAL_DIR_NAME = "01_原始素材"
DISTILL_DIR_NAME = "02_原著蒸馏"
LEGACY_CSV_FILENAME = "素材清单.csv"
LEDGER_FILENAME = "素材资产.json"
INDEX_FILENAME = "素材总索引.md"
PREVIEW_FILENAME = "素材清单_v1_preview.csv"
MANIFEST_FILENAME = "collection_manifest.json"
SCHEMA_VERSION = "1.0"

# 边界案例（中文文学中需要人工确认角色的作品 → NEEDS_REVIEW）
BOUNDARY_REVIEW_NAMES = {
    "明朝那些事儿",
    "我读书少你可别骗我",
    "马伯庸笑翻中国简史",
    "她死在QQ上",
    "殷商玛雅征服史",
    "事实证明，人民永远是最可爱的",
    "事实证明人民永远是最可爱的",  # 无逗号变体（防御）
}

# 文件名作者解析时的噪声词（z-library 痕迹 / 版本 / 系列标注等）
NOISE_KW = (
    "z-library", "1lib", "z-lib", "译文", "译", "经典", "出版", "版", "全集", "精排",
    "校对", "全本", "纪念", "作者", "原著", "合集", "丛书", "共", "册", "著",
)

# 单字候选（册标记 / 方位标记），几乎不可能是作者名
SINGLE_CHAR_REJECT = ("上", "下", "中", "全")

# legacy CSV SourcePrepare 状态 → 提纯状态（仅 migration bootstrap 用）
SP_STATUS_MAP = {"PASS": "可用", "REVIEW": "需复核", "FAIL": "失败"}

# 提纯状态（含 Phase 2B 预留：不适用）
PURIFICATION_STATUS = ("未处理", "可用", "需复核", "需更新", "失败", "不适用")
# 知识状态（含 Phase 2B 预留：失败 / 不适用）
KNOWLEDGE_STATUS = ("未开始", "可用", "需更新", "失败", "不适用")

# 合法类型（LOOSE_MATERIAL 为 Phase 2B 预留，当前 ledger 不产出）
VALID_TYPES = ("REFERENCE_WORK", "RESEARCH", "LOOSE_MATERIAL", "NEEDS_REVIEW")


def sha256_file(path: Path) -> str:
    """计算单文件 SHA256（1MiB 分块）。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_material_files(mat_dir: Path) -> dict:
    """全量扫描 01_原始素材 下所有文件（排除 collection_manifest.json），返回 {相对posix路径: sha256}。"""
    scanned = {}
    for p in sorted(mat_dir.rglob("*")):
        if not p.is_file():
            continue
        if p.name == MANIFEST_FILENAME:
            continue
        rel = p.relative_to(mat_dir).as_posix()
        scanned[rel] = sha256_file(p)
    return scanned


def load_legacy_csv(mat_dir: Path) -> list:
    """读取 legacy 22 列素材清单.csv（UTF-8-sig），返回 DictReader 行列表。"""
    csv_path = mat_dir / LEGACY_CSV_FILENAME
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def strip_material_prefix(path_value: str) -> str:
    """去掉 CSV 本地相对路径中的 '01_原始素材/' 前缀，得到相对 01_原始素材 的 posix 路径。"""
    p = path_value.replace("\\", "/").strip()
    prefix = MATERIAL_DIR_NAME + "/"
    if p.startswith(prefix):
        return p[len(prefix):]
    return p


def bootstrap_type(category: str, name: str) -> str:
    """类型初始化：现代专业资料 → RESEARCH；边界案例 → NEEDS_REVIEW；其余 → REFERENCE_WORK。"""
    if category == "现代专业资料":
        return "RESEARCH"
    if name in BOUNDARY_REVIEW_NAMES:
        return "NEEDS_REVIEW"
    return "REFERENCE_WORK"


def parse_author_from_filename(filename: str) -> str:
    """
    从文件名保守解析作者：取括号（半角/全角）内候选，过滤噪声词；
    仅当恰好剩下一个可信候选（无空格、长度 ≤ 12）才返回，否则空串。
    """
    stem = Path(filename).stem
    pairs = re.findall(r"\(([^()]*)\)|（([^（）]*)）", stem)
    cleaned = []
    for half, full in pairs:
        c = (half or full).strip()
        if not c:
            continue
        low = c.lower()
        if any(k in low for k in NOISE_KW):
            continue
        if c in SINGLE_CHAR_REJECT:
            continue
        if " " in c or "\u3000" in c:
            continue
        if len(c) > 12:
            continue
        cleaned.append(c)
    if len(cleaned) == 1:
        return cleaned[0]
    return ""


def find_bkp(distill_dir: Path, book_id: str) -> dict | None:
    """查找 book_id 对应的正式 BKP（identity.json），返回证据摘要或 None。"""
    if distill_dir is None or not distill_dir.exists():
        return None
    for d in sorted(distill_dir.iterdir()):
        if not d.is_dir() or not d.name.startswith(book_id + "_"):
            continue
        identity = d / "bkp" / "identity.json"
        if not identity.exists():
            return None
        try:
            data = json.loads(identity.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        schema_status = str(data.get("schema_status", ""))
        ss = data.get("source_snapshot", {}) or {}
        return {
            "finalized": schema_status.startswith("FINALIZED"),
            "source_sha256": ss.get("source_sha256") or "",
            "dir_rel": f"{DISTILL_DIR_NAME}/{d.name}",
            "author": (data.get("book", {}) or {}).get("author") or "",
        }
    return None


def find_sp_metadata(sp_dir: Path, book_id: str) -> dict | None:
    """按 SourcePrepare 正式合同查找 A 级提纯证据。

    合同路径：06_工作区/SourcePrepare/<book_id>_<书名>/metadata.json。
    规则：
      - 目录名前缀 <book_id>_ 恰好匹配 1 个 → 读取该目录 metadata.json；
      - 0 个 → None（无 A 级证据）；
      - >1 个 → RuntimeError（目录歧义，不静默选第一个）；
      - metadata.book_id 与 book_id 不一致 → RuntimeError（拒绝脏数据）。
    """
    if sp_dir is None or not sp_dir.exists():
        return None
    matches = [d for d in sorted(sp_dir.iterdir())
               if d.is_dir() and d.name.startswith(book_id + "_")]
    if not matches:
        return None
    if len(matches) > 1:
        raise RuntimeError(
            f"SourcePrepare 目录歧义: {book_id} 匹配多个目录 {[d.name for d in matches]}")
    m = matches[0] / "metadata.json"
    if not m.exists():
        return None
    try:
        data = json.loads(m.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    meta_book_id = data.get("book_id")
    if meta_book_id and meta_book_id != book_id:
        raise RuntimeError(
            f"SourcePrepare metadata book_id 不一致: {matches[0].name} 内 "
            f"book_id={meta_book_id!r} != {book_id!r}")
    return data


def derive_purification(sp_meta: dict | None, bkp: dict | None,
                        legacy_status: str, file_shas: set) -> dict:
    """
    提纯状态推导（优先级 A > B > C > D > E）：
      A. SourcePrepare metadata.json（A 级证据，合同路径 <book_id>_<书名>/metadata.json）
         schema: status / book_id / selected_source.sha256
         - selected_source.sha256 匹配 files：
             status=PASS → 可用；REVIEW → 需复核；FAIL → 失败
         - SHA 已不属于当前 asset → 需更新（即使 status=PASS 也不标记可用）
         - 缺关键字段 / 未知 status → 需复核（明确异常，不静默判可用）
      B. BKP FINALIZED 且 source_sha256 在 files 中 → 可用（bkp_source_snapshot）
      C. legacy CSV SP 状态（一次性 migration bootstrap，legacy_catalog）
      D. SHA 不匹配 → 需更新
      E. 无任何证据 → 未处理
    """
    if sp_meta is not None:
        sp_status = sp_meta.get("status")
        sel = sp_meta.get("selected_source")
        sha = sel.get("sha256") if isinstance(sel, dict) else None
        if not sp_status or not sha:
            return {"status": "需复核", "evidence": "sourceprepare_metadata_incomplete"}
        if sha not in file_shas:
            return {"status": "需更新", "evidence": "sourceprepare_metadata_sha_mismatch"}
        if sp_status == "PASS":
            return {"status": "可用", "evidence": "sourceprepare_metadata"}
        if sp_status == "REVIEW":
            return {"status": "需复核", "evidence": "sourceprepare_metadata"}
        if sp_status == "FAIL":
            return {"status": "失败", "evidence": "sourceprepare_metadata"}
        return {"status": "需复核", "evidence": "sourceprepare_metadata_unknown_status"}
    if bkp is not None and bkp["finalized"]:
        if bkp["source_sha256"] and bkp["source_sha256"] in file_shas:
            return {"status": "可用", "evidence": "bkp_source_snapshot"}
        return {"status": "需更新", "evidence": "bkp_source_sha_mismatch"}
    if legacy_status in SP_STATUS_MAP:
        return {"status": SP_STATUS_MAP[legacy_status], "evidence": "legacy_catalog"}
    return {"status": "未处理", "evidence": None}


def derive_knowledge(bkp: dict | None, file_shas: set) -> dict:
    """知识状态推导：无 FINALIZED BKP → 未开始；FINALIZED 且 SHA 匹配 → 可用；否则 → 需更新。"""
    if bkp is None or not bkp["finalized"]:
        return {"status": "未开始"}
    base = {"status": "可用" if bkp["source_sha256"] in file_shas else "需更新",
            "path": bkp["dir_rel"], "source_sha256": bkp["source_sha256"]}
    return base


def split_tags(raw: str) -> list:
    """标签列非空时按常见分隔符拆分；空 → []。"""
    raw = (raw or "").strip()
    if not raw:
        return []
    return [t.strip() for t in re.split(r"[;；,，、/|]", raw) if t.strip()]


def build_assets(rows: list, scanned: dict, distill_dir: Path, sp_dir: Path) -> list:
    """按作品ID 分组构建 assets：id/name/type/author/tags/notes/files/purification/knowledge。"""
    by_id = {}
    for r in rows:
        by_id.setdefault(r["作品ID"], []).append(r)

    assets = []
    for book_id in sorted(by_id):
        group = by_id[book_id]
        primary = next((r for r in group if r["是否主来源"] == "是"), group[0])
        name = (primary["作品名"] or "").strip()
        category = (primary["资料大类"] or "").strip()

        files = []
        for r in sorted(group, key=lambda x: strip_material_prefix(x["本地相对路径"])):
            rel = strip_material_prefix(r["本地相对路径"])
            if rel not in scanned:
                raise RuntimeError(f"磁盘缺失（CSV 已注册但文件不存在）: {rel}")
            fe = {"path": rel, "sha256": scanned[rel], "primary": r["是否主来源"] == "是"}
            cont = (r["来源容器"] or "").strip()
            if cont:
                fe["source_container"] = cont
            files.append(fe)

        file_shas = {f["sha256"] for f in files}
        bkp = find_bkp(distill_dir, book_id)
        sp_meta = find_sp_metadata(sp_dir, book_id)

        # 作者：CSV > BKP identity > 主来源文件名保守解析 > 空
        author = (primary["作者"] or "").strip()
        if not author and bkp is not None and bkp["author"]:
            author = bkp["author"]
        if not author:
            author = parse_author_from_filename(primary["文件名"] or "")

        notes = (primary["备注"] or "").strip()

        assets.append({
            "id": book_id,
            "name": name,
            "type": bootstrap_type(category, name),
            "author": author,
            "tags": split_tags(primary["标签"]),
            "notes": notes,
            "files": files,
            "purification": derive_purification(
                sp_meta, bkp, (primary["SourcePrepare状态"] or "").strip(), file_shas),
            "knowledge": derive_knowledge(bkp, file_shas),
        })
    return assets


def load_manifests(mat_dir: Path) -> list:
    """读取 01_原始素材 下所有 collection_manifest.json（Local Only 证据）。"""
    manifests = []
    for mf in sorted(mat_dir.rglob(MANIFEST_FILENAME)):
        try:
            data = json.loads(mf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        manifests.append(data)
    return manifests


def build_containers(manifests: list, scanned: dict) -> list:
    """由 manifest 构建 containers（original 为容器原始文件，SHA 以磁盘扫描为准）。"""
    containers = []
    for mf in manifests:
        rel_dir = (mf.get("container_dir") or "").replace("\\", "/").strip("/")
        original = mf.get("original") or {}
        filename = original.get("filename") or ""
        orig_path = f"{rel_dir}/{filename}" if filename else ""
        splits = mf.get("splits") or []
        containers.append({
            "id": mf.get("container") or rel_dir,
            "container_dir": rel_dir,
            "category": mf.get("category") or "",
            "source_format": mf.get("source_format") or "",
            "manifest_path": f"{rel_dir}/{MANIFEST_FILENAME}" if rel_dir else MANIFEST_FILENAME,
            "original": {
                "path": orig_path,
                "filename": filename,
                "sha256": scanned.get(orig_path) or original.get("sha256") or "",
            },
            "split_count": len(splits),
            "split_book_ids": [s.get("book_id") for s in splits if s.get("book_id")],
        })
    containers.sort(key=lambda c: c["id"])
    return containers


def build_ledger(assets: list, containers: list) -> dict:
    """组装 ledger（schema_version / assets / containers）。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "assets": assets,
        "containers": containers,
    }


def write_ledger(ledger: dict, out_path: Path) -> None:
    """写素材资产.json（sort_keys + ensure_ascii=False + indent=2 + 末尾换行 → byte-for-byte 幂等）。"""
    text = json.dumps(ledger, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    out_path.write_text(text, encoding="utf-8", newline="\n")


def generate_index(ledger: dict) -> str:
    """生成素材总索引.md（总览 + 参考作品表 + 研究资料表 + 待确认表；不含 SHA/大小/文件名/来源网站等）。"""
    assets = ledger["assets"]
    n = len(assets)
    by_type = {}
    type_counter = {}
    for a in assets:
        by_type.setdefault(a["type"], []).append(a)
        type_counter[a["type"]] = type_counter.get(a["type"], 0) + 1
    purif_counter = {}
    know_counter = {}
    for a in assets:
        purif_counter[a["purification"]["status"]] = purif_counter.get(a["purification"]["status"], 0) + 1
        know_counter[a["knowledge"]["status"]] = know_counter.get(a["knowledge"]["status"], 0) + 1

    def fmt_counter(counter):
        return " / ".join(f"{k} {v}" for k, v in sorted(counter.items())) or "无"

    lines = [
        "# 素材总索引",
        "",
        "> 由 `MaterialIntake/catalog.py` 自动生成（ledger schema v1.0），反映 `01_原始素材` 的真实情况。",
        "> 第三方原著全文 **Local Only，不上传 GitHub**；本索引仅含元数据与处理状态。",
        "",
        "## 总览",
        "",
        f"- 素材总数：{n}",
        f"- 类型分布：{fmt_counter(type_counter)}",
        f"- 提纯状态：{fmt_counter(purif_counter)}",
        f"- 知识状态：{fmt_counter(know_counter)}",
        "",
    ]

    def table(header, items):
        rows = [f"| {header} |", "|---|---|---|---|---|---|"]
        for a in items:
            tags = "、".join(a["tags"]) if a["tags"] else "—"
            rows.append(
                f"| {a['id']} | {a['name']} | {a['author'] or '—'} | {tags} | "
                f"{a['purification']['status']} | {a['knowledge']['status']} |")
        return rows

    sections = [
        ("## 参考作品（REFERENCE_WORK）", by_type.get("REFERENCE_WORK", [])),
        ("## 研究资料（RESEARCH）", by_type.get("RESEARCH", [])),
        ("## 待确认（NEEDS_REVIEW）", by_type.get("NEEDS_REVIEW", [])),
    ]
    for title, items in sections:
        lines.append(title)
        lines.append("")
        lines.extend(table("ID | 名称 | 作者 | 标签 | 提纯 | 知识", items))
        lines.append("")
    return "\n".join(lines)


def generate_preview_rows(ledger: dict) -> list:
    """生成 9 列 preview 行（含表头）：素材ID/名称/类型/作者/标签/位置/提纯/知识/备注。"""
    header = ["素材ID", "名称", "类型", "作者", "标签", "位置", "提纯", "知识", "备注"]
    rows = [header]
    for a in ledger["assets"]:
        primary_files = [f for f in a["files"] if f["primary"]]
        loc_src = primary_files[0] if primary_files else a["files"][0]
        location = str(Path(loc_src["path"]).parent.as_posix())
        if location == ".":
            location = ""
        rows.append([
            a["id"],
            a["name"],
            a["type"],
            a["author"],
            "、".join(a["tags"]),
            location,
            a["purification"]["status"],
            a["knowledge"]["status"],
            a["notes"],
        ])
    return rows


def write_preview(rows: list, out_path: Path) -> None:
    """写 preview CSV（utf-8-sig，Excel 友好）。"""
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="素材资产 ledger 构建器（CATALOG_FOUNDATION_ONLY）")
    parser.add_argument("--root", default=os.getcwd(), help="仓库根目录（默认当前目录）")
    parser.add_argument("--preview-dir", default=None, help="preview CSV 输出目录（默认 %TEMP%）")
    args = parser.parse_args(argv)

    root = Path(args.root)
    mat_dir = root / MATERIAL_DIR_NAME
    distill_dir = root / DISTILL_DIR_NAME
    sp_dir = root / "06_工作区" / "SourcePrepare"

    print("[catalog] scanning material files (SHA256) ...")
    scanned = scan_material_files(mat_dir)
    print(f"[catalog] scanned {len(scanned)} files")

    rows = load_legacy_csv(mat_dir)
    print(f"[catalog] legacy CSV rows: {len(rows)}")

    assets = build_assets(rows, scanned, distill_dir, sp_dir)
    manifests = load_manifests(mat_dir)
    containers = build_containers(manifests, scanned)
    ledger = build_ledger(assets, containers)

    ledger_path = mat_dir / LEDGER_FILENAME
    index_path = mat_dir / INDEX_FILENAME
    write_ledger(ledger, ledger_path)
    index_path.write_text(generate_index(ledger), encoding="utf-8", newline="\n")

    preview_dir = Path(args.preview_dir) if args.preview_dir else Path(os.environ.get("TEMP", "."))
    preview_path = preview_dir / PREVIEW_FILENAME
    write_preview(generate_preview_rows(ledger), preview_path)

    print(f"[catalog] assets: {len(assets)} | containers: {len(containers)}")
    print(f"[catalog] wrote {ledger_path}")
    print(f"[catalog] wrote {index_path}")
    print(f"[catalog] wrote {preview_path}")

    # 自检：schema 级不变式（类型/状态合法性；数量级由调用方/测试断言）
    for a in assets:
        assert a["type"] in VALID_TYPES, a["id"]
        assert a["purification"]["status"] in PURIFICATION_STATUS, a["id"]
        assert a["knowledge"]["status"] in KNOWLEDGE_STATUS, a["id"]
        assert len({f["path"] for f in a["files"]}) == len(a["files"]), f"{a['id']} 重复文件路径"
    print(f"[catalog] self-checks passed ({len(assets)} assets / "
          f"{sum(len(a['files']) for a in assets)} files / valid statuses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
