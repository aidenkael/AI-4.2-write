#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MaterialIntake catalog —— 素材资产 canonical ledger 的 refresh 与 derived view 渲染器。

Phase 2B1（CANONICAL_CATALOG）运行模型（默认）：
  已有素材资产.json
      ↓ load + schema validation
      ↓ 验证磁盘 registered files（MISSING_REGISTERED_FILE → 停止且不写盘）
      ↓ 读取 SourcePrepare / BKP evidence
      ↓ 刷新机器事实（files SHA）与 derived status（purification / knowledge）
      ↓ 保存素材资产.json
      ↓ 生成素材清单.csv（9 列 derived author view）
      ↓ 生成素材总索引.md（derived human/GitHub view）

默认运行不读取 legacy 22 列 CSV。

MIGRATION_ONLY：load_legacy_csv / build_assets / bootstrap_type / parse_author_from_filename
等函数是 legacy 22 列 → ledger 的一次性迁移 / 测试 fixture helper（Phase 2A），
绝不被 production main / refresh 路径调用。Phase 2B2 起由 inbox intake 取代。

设计原则：
  - 素材资产.json = 唯一 canonical material registry；素材清单.csv / 素材总索引.md = derived views。
  - 禁止 CSV / MD 反向生成 ledger；SourcePrepare 不维护第二套 book_id / category registry。
  - refresh 保留 canonical / human semantic 字段（id/name/type/author/tags/notes/
    files[].path/primary/source_container/container membership），不被文件名/旧分类/AI 自动覆盖。
  - files[].sha256 是机器事实快照：registered path 存在则重算；缺失 → MISSING_REGISTERED_FILE。
  - 未登记磁盘文件只报告 UNREGISTERED_FILE，不自动建 asset / 分类 / 分配 ID / 移动。
  - Phase 2B1.1：purification 是长期持久记录。SP metadata 是证据来源、ledger 是已结算事实的
    canonical 存储；06_工作区 删除后，已结算提纯事实仍保留（input_fingerprint 匹配时稳定恢复，
    素材变化时判需更新）。containers[].original.path 也是正式登记事实，缺失必须报 MISSING。

确定性保证：
  - 无时间戳 / 无 volatile 字段
  - JSON sort_keys + assets/files/containers 显式排序
  - 同输入重复执行 byte-for-byte 幂等

用法：
  python catalog.py --root E:/AI-Write           # 默认 refresh + render（写 ledger/CSV/MD）
  python catalog.py --root E:/AI-Write --check   # 只校验，不写盘
"""

import argparse
import copy
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
MANIFEST_FILENAME = "collection_manifest.json"
SCHEMA_VERSION = "1.0"

# 已知系统文件：不算未登记新素材
SYSTEM_FILES = {
    "README.md", LEDGER_FILENAME, LEGACY_CSV_FILENAME, INDEX_FILENAME, ".gitkeep",
}

# 边界案例（中文文学中需要人工确认角色的作品 → NEEDS_REVIEW）【migration bootstrap 用】
BOUNDARY_REVIEW_NAMES = {
    "明朝那些事儿",
    "我读书少你可别骗我",
    "马伯庸笑翻中国简史",
    "她死在QQ上",
    "殷商玛雅征服史",
    "事实证明，人民永远是最可爱的",
    "事实证明人民永远是最可爱的",  # 无逗号变体（防御）
}

# 文件名作者解析时的噪声词（z-library 痕迹 / 版本 / 系列标注等）【migration bootstrap 用】
NOISE_KW = (
    "z-library", "1lib", "z-lib", "译文", "译", "经典", "出版", "版", "全集", "精排",
    "校对", "全本", "纪念", "作者", "原著", "合集", "丛书", "共", "册", "著",
)

# 单字候选（册标记 / 方位标记），几乎不可能是作者名 【migration bootstrap 用】
SINGLE_CHAR_REJECT = ("上", "下", "中", "全")

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


def load_ledger(path: Path) -> dict:
    """读取素材资产.json（canonical ledger），校验 schema_version 与顶层结构。"""
    if not path.exists():
        raise FileNotFoundError(f"canonical ledger 不存在: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"ledger 解析失败: {exc}") from exc
    if data.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError(
            f"ledger schema_version 不兼容: {data.get('schema_version')!r} != {SCHEMA_VERSION!r}")
    if not isinstance(data.get("assets"), list) or not isinstance(data.get("containers"), list):
        raise RuntimeError("ledger 结构无效：缺少 assets / containers 列表")
    return data


def validate_ledger(ledger: dict) -> list[str]:
    """schema 级校验，返回错误信息列表（空 = 合法）。"""
    errors = []
    seen_ids = set()
    for a in ledger["assets"]:
        if a["id"] in seen_ids:
            errors.append(f"重复 asset id: {a['id']}")
        seen_ids.add(a["id"])
        if a["type"] not in VALID_TYPES:
            errors.append(f"{a['id']}: 非法 type {a['type']!r}")
        if a["purification"]["status"] not in PURIFICATION_STATUS:
            errors.append(f"{a['id']}: 非法 purification {a['purification']['status']!r}")
        if a["knowledge"]["status"] not in KNOWLEDGE_STATUS:
            errors.append(f"{a['id']}: 非法 knowledge {a['knowledge']['status']!r}")
        paths = [f["path"] for f in a["files"]]
        if len(paths) != len(set(paths)):
            errors.append(f"{a['id']}: files 路径重复")
        for f in a["files"]:
            if not re.fullmatch(r"[0-9a-f]{64}", f.get("sha256") or ""):
                errors.append(f"{a['id']}: {f['path']} SHA256 非法")
    return errors


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


def content_fingerprint(files: list) -> str:
    """对 asset 全部 registered source files 计算 content fingerprint（Phase 2B1.2）。

    只基于内容 SHA256 集合计算：sorted(f["sha256"] for f in files) 保留重复，
    整体取 SHA256 = SHA256 multiset fingerprint。与物理路径 / 文件名无关，
    因此目录迁移、文件改名不导致 stale；内容变化、来源文件增删才导致 stale。
    """
    hashes = sorted(f["sha256"] for f in files)
    return hashlib.sha256("\n".join(hashes).encode("utf-8")).hexdigest()


def legacy_path_fingerprint(files: list) -> str:
    """Phase 2B1.1 旧算法：排序后的 'path:sha256' 行整体 SHA256。

    仅用于一次性兼容迁移：识别旧算法写入的 input_fingerprint record，
    在内容未变时把 input_fingerprint 迁移为 content_fingerprint。不进入长期使用。
    """
    parts = sorted(f"{f['path']}:{f['sha256']}" for f in files)
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def derive_purification(sp_meta: dict | None, bkp: dict | None, file_shas: set,
                        input_fp: str | None = None, prev: dict | None = None,
                        legacy_fp: str | None = None) -> dict:
    """提纯状态推导（Phase 2B1.1 持久化版；Phase 2B1.2 指纹与路径解耦）。

    优先级：
      1. 当前 SourcePrepare metadata（存在时）= 最新处理事实
      2. 已持久化 ledger purification record（content fingerprint 匹配）= 上一次已结算事实
      3. FINALIZED BKP = 历史恢复证据
      4. 无证据 = 未处理
    任何层级发现当前 content fingerprint 已变化 → 需更新。

    Phase 2B1.2 一次性兼容迁移：prev 的 input_fingerprint 若等于 legacy_fp
    （旧 path:sha256 算法，且当前内容与之仍一致）→ 保持状态与 source_sha256，
    仅把 input_fingerprint 迁移为 content_fingerprint，不标记需更新。
    迁移完成后新 record 只使用 content fingerprint，不再产生 legacy record。

    持久化字段（canonical schema enrichment，schema_version 保持 1.0）：
      - source_sha256：有 selected_source 时保存其 SHA
      - input_fingerprint：本次评估时 asset 全部 registered source files 的
        SHA256 multiset fingerprint（与路径无关）
    不保存时间戳 / SourcePrepare 正文。

    evidence 语义：
      - sourceprepare_metadata / sourceprepare_metadata_*：由当前 SP metadata 直接推导
      - sourceprepare_record / sourceprepare_record_input_changed：ledger 持久 record 结算/判定
      - bkp_source_snapshot / bkp_source_sha_mismatch：BKP 历史恢复证据
    """
    # 1. 当前 SourcePrepare metadata = 最新处理事实
    if sp_meta is not None:
        sp_status = sp_meta.get("status")
        sel = sp_meta.get("selected_source")
        sha = sel.get("sha256") if isinstance(sel, dict) else None
        if not sp_status:
            return {"status": "需复核", "evidence": "sourceprepare_metadata_incomplete"}
        if sp_status not in ("PASS", "REVIEW", "FAIL"):
            return {"status": "需复核", "evidence": "sourceprepare_metadata_unknown_status"}
        if not sha:
            if sp_status == "FAIL":
                rec = {"status": "失败", "evidence": "sourceprepare_metadata"}
                if input_fp is not None:
                    rec["input_fingerprint"] = input_fp
                return rec
            return {"status": "需复核", "evidence": "sourceprepare_metadata_incomplete"}
        if sha not in file_shas:
            # SP 结果不属于当前素材 → 需更新；保留上次已结算 record（如有）
            if isinstance(prev, dict) and prev.get("input_fingerprint"):
                return {"status": "需更新", "evidence": "sourceprepare_metadata_sha_mismatch",
                        "source_sha256": prev.get("source_sha256"),
                        "input_fingerprint": prev["input_fingerprint"]}
            return {"status": "需更新", "evidence": "sourceprepare_metadata_sha_mismatch"}
        status = {"PASS": "可用", "REVIEW": "需复核", "FAIL": "失败"}[sp_status]
        rec = {"status": status, "evidence": "sourceprepare_metadata", "source_sha256": sha}
        if input_fp is not None:
            rec["input_fingerprint"] = input_fp
        return rec

    # 2. 已持久化 ledger record = 上一次已结算处理事实
    prev_fp = prev.get("input_fingerprint") if isinstance(prev, dict) else None
    if prev_fp:
        if input_fp is not None and input_fp != prev_fp:
            # Phase 2B1.2 一次性兼容迁移：prev 为旧 path-based 算法 record 且当前内容
            # 与其一致 → 保持状态/source_sha256，仅迁移 input_fingerprint，不判需更新。
            if legacy_fp is not None and prev_fp == legacy_fp \
                    and prev.get("status") in ("可用", "需复核", "失败"):
                return {"status": prev["status"],
                        "evidence": prev.get("evidence") or "sourceprepare_record",
                        "source_sha256": prev.get("source_sha256"),
                        "input_fingerprint": input_fp}
            rec = {"status": "需更新", "evidence": "sourceprepare_record_input_changed",
                   "input_fingerprint": prev_fp}
            if prev.get("source_sha256"):
                rec["source_sha256"] = prev["source_sha256"]
            return rec
        if prev.get("status") in ("可用", "需复核", "失败"):
            rec = {"status": prev["status"],
                   "evidence": prev.get("evidence") or "sourceprepare_record",
                   "input_fingerprint": prev_fp}
            if prev.get("source_sha256"):
                rec["source_sha256"] = prev["source_sha256"]
            return rec
        # prev 是非正式状态（需更新/未处理/不适用）→ 保持原状
        return dict(prev)

    # 3. FINALIZED BKP = 历史恢复证据（可补写长期 record）
    if bkp is not None and bkp["finalized"]:
        if bkp["source_sha256"] and bkp["source_sha256"] in file_shas:
            rec = {"status": "可用", "evidence": "bkp_source_snapshot",
                   "source_sha256": bkp["source_sha256"]}
            if input_fp is not None:
                rec["input_fingerprint"] = input_fp
            return rec
        return {"status": "需更新", "evidence": "bkp_source_sha_mismatch"}

    # 4. 无证据
    return {"status": "未处理", "evidence": None}


def derive_knowledge(bkp: dict | None, file_shas: set) -> dict:
    """知识状态推导：无 FINALIZED BKP → 未开始；FINALIZED 且 SHA 匹配 → 可用；否则 → 需更新。"""
    if bkp is None or not bkp["finalized"]:
        return {"status": "未开始"}
    base = {"status": "可用" if bkp["source_sha256"] in file_shas else "需更新",
            "path": bkp["dir_rel"], "source_sha256": bkp["source_sha256"]}
    return base


def refresh_ledger(ledger: dict, mat_dir: Path, distill_dir: Path, sp_dir: Path) -> tuple[dict, dict]:
    """基于磁盘事实与证据刷新 ledger；返回 (new_ledger, report)。

    report = {"missing": [...], "unregistered": [...]}
    - canonical / human semantic 字段全部保留（id/name/type/author/tags/notes/
      files[].path/primary/source_container/container membership）。
    - files[].sha256 重新计算（机器事实快照）。
    - registered path 缺失 → 记入 missing（调用方应停止写盘，保持原 ledger 不被半写）。
    - 未登记新文件 → 记入 unregistered（不自动建 asset / 分类 / 分配 ID）。
    """
    scanned = scan_material_files(mat_dir)
    report = {"missing": [], "unregistered": []}

    new_assets = []
    for a in ledger["assets"]:
        new_files = []
        for f in a["files"]:
            rel = f["path"]
            if rel not in scanned:
                report["missing"].append(rel)
                continue
            nf = dict(f)
            nf["sha256"] = scanned[rel]
            new_files.append(nf)
        file_shas = {f["sha256"] for f in new_files}
        input_fp = content_fingerprint(new_files)
        legacy_fp = legacy_path_fingerprint(new_files)
        bkp = find_bkp(distill_dir, a["id"])
        sp_meta = find_sp_metadata(sp_dir, a["id"])
        new_assets.append({
            "id": a["id"],
            "name": a["name"],
            "type": a["type"],
            "author": a["author"],
            "tags": list(a.get("tags") or []),
            "notes": a.get("notes") or "",
            "files": new_files,
            "purification": derive_purification(sp_meta, bkp, file_shas, input_fp,
                                                a.get("purification"), legacy_fp),
            "knowledge": derive_knowledge(bkp, file_shas),
        })

    # containers：结构保留；original.sha256 以磁盘扫描为准重算（机器事实）。
    # original.path 非空但磁盘缺失 → 必须报 MISSING（不得静默保留旧 SHA 并返回成功）。
    # collection_manifest.json 是 Local Only 证据，不是 tracked canonical source，缺失不判坏。
    new_containers = []
    for c in ledger["containers"]:
        nc = copy.deepcopy(c)
        op = nc.get("original") or {}
        if op.get("path"):
            if op["path"] in scanned:
                op["sha256"] = scanned[op["path"]]
            else:
                report["missing"].append(f"container:{c.get('id')}:{op['path']}")
        new_containers.append(nc)

    # unregistered 检测：排除系统文件 / 已登记 container original
    registered = {f["path"] for a in new_assets for f in a["files"]}
    container_originals = {
        c["original"]["path"] for c in new_containers if c.get("original", {}).get("path")
    }
    for rel in sorted(set(scanned) - registered - container_originals):
        if Path(rel).name in SYSTEM_FILES:
            continue
        report["unregistered"].append(rel)

    new_ledger = {
        "schema_version": ledger["schema_version"],
        "assets": new_assets,
        "containers": new_containers,
    }
    return new_ledger, report


def render_catalog_csv(ledger: dict) -> list:
    """渲染 9 列作者视图（含表头）：素材ID/名称/类型/作者/标签/位置/提纯/知识/备注。

    完全由 ledger 派生；一项逻辑素材 = 一行；位置 = primary file 所在目录（相对 01_原始素材）。
    禁止任何 CSV → ledger 反向同步入口。
    """
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


def write_csv(rows: list, out_path: Path) -> None:
    """写 derived CSV（utf-8-sig，Excel 友好）。"""
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)


def write_ledger(ledger: dict, out_path: Path) -> None:
    """写素材资产.json（sort_keys + ensure_ascii=False + indent=2 + 末尾换行 → byte-for-byte 幂等）。"""
    text = json.dumps(ledger, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    out_path.write_text(text, encoding="utf-8", newline="\n")


def render_index_md(ledger: dict) -> str:
    """渲染素材总索引.md（总览 + 参考作品表 + 研究资料表 + 待确认表；不含 SHA/大小/文件名/来源网站等）。"""
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


def refresh_and_render(root: Path, check_only: bool = False) -> int:
    """canonical 默认流程：load ledger → refresh → validate →（check_only 停止）→ 写三视图。

    供 CLI 与 SourcePrepare local writeback 复用；任何 MISSING 都停止且不写盘。
    """
    mat_dir = root / MATERIAL_DIR_NAME
    distill_dir = root / DISTILL_DIR_NAME
    sp_dir = root / "06_工作区" / "SourcePrepare"
    ledger_path = mat_dir / LEDGER_FILENAME

    if not ledger_path.exists():
        print(f"[catalog] ERROR: canonical ledger 不存在: {ledger_path}")
        print("[catalog] 默认流程从 ledger 加载；legacy CSV bootstrap 仅限迁移 helper / 测试使用")
        return 2

    ledger = load_ledger(ledger_path)
    new_ledger, report = refresh_ledger(ledger, mat_dir, distill_dir, sp_dir)

    if report["missing"]:
        print(f"[catalog] MISSING_REGISTERED_FILE × {len(report['missing'])}：")
        for rel in report["missing"]:
            print(f"  - {rel}")
        print("[catalog] refresh 已停止，未写入任何文件（原 ledger 保持原样）")
        return 1

    errors = validate_ledger(new_ledger)
    if errors:
        print(f"[catalog] 校验失败 × {len(errors)}：")
        for e in errors:
            print(f"  - {e}")
        return 1

    n_assets = len(new_ledger["assets"])
    n_files = sum(len(a["files"]) for a in new_ledger["assets"])
    if check_only:
        print(f"[catalog] CHECK OK: {n_assets} assets / {n_files} files "
              f"/ {len(new_ledger['containers'])} containers（未写入）")
        return 0

    write_ledger(new_ledger, ledger_path)
    write_csv(render_catalog_csv(new_ledger), mat_dir / LEGACY_CSV_FILENAME)
    (mat_dir / INDEX_FILENAME).write_text(render_index_md(new_ledger), encoding="utf-8", newline="\n")

    if report["unregistered"]:
        print(f"[catalog] UNREGISTERED_FILE × {len(report['unregistered'])}（仅报告，不自动登记）：")
        for rel in report["unregistered"]:
            print(f"  - {rel}")

    print(f"[catalog] assets: {n_assets} | files: {n_files} | containers: {len(new_ledger['containers'])}")
    print(f"[catalog] wrote {ledger_path}")
    print(f"[catalog] wrote {mat_dir / LEGACY_CSV_FILENAME}（9 列 derived view）")
    print(f"[catalog] wrote {mat_dir / INDEX_FILENAME}")
    return 0


# =========================================================================== #
# MIGRATION_ONLY：legacy 22 列 CSV → ledger 的一次性迁移 / 测试 fixture helper。
# 以下函数不被 production main / refresh 路径调用；Phase 2B2 起由 inbox intake 取代。
# =========================================================================== #

def load_legacy_csv(mat_dir: Path) -> list:
    """[MIGRATION_ONLY] 读取 legacy 22 列素材清单.csv（UTF-8-sig），返回 DictReader 行列表。"""
    csv_path = mat_dir / LEGACY_CSV_FILENAME
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def strip_material_prefix(path_value: str) -> str:
    """[MIGRATION_ONLY] 去掉 CSV 本地相对路径中的 '01_原始素材/' 前缀，得到相对 01_原始素材 的 posix 路径。"""
    p = path_value.replace("\\", "/").strip()
    prefix = MATERIAL_DIR_NAME + "/"
    if p.startswith(prefix):
        return p[len(prefix):]
    return p


def bootstrap_type(category: str, name: str) -> str:
    """[MIGRATION_ONLY] 类型初始化：现代专业资料 → RESEARCH；边界案例 → NEEDS_REVIEW；其余 → REFERENCE_WORK。"""
    if category == "现代专业资料":
        return "RESEARCH"
    if name in BOUNDARY_REVIEW_NAMES:
        return "NEEDS_REVIEW"
    return "REFERENCE_WORK"


def parse_author_from_filename(filename: str) -> str:
    """[MIGRATION_ONLY] 从文件名保守解析作者：取括号（半角/全角）内候选，过滤噪声词；
    仅当恰好剩下一个可信候选（无空格、长度 ≤ 12）才返回，否则空串。"""
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


def split_tags(raw: str) -> list:
    """[MIGRATION_ONLY] 标签列非空时按常见分隔符拆分；空 → []。"""
    raw = (raw or "").strip()
    if not raw:
        return []
    return [t.strip() for t in re.split(r"[;；,，、/|]", raw) if t.strip()]


def build_assets(rows: list, scanned: dict, distill_dir: Path, sp_dir: Path) -> list:
    """[MIGRATION_ONLY] 按作品ID 分组构建 assets：id/name/type/author/tags/notes/files/purification/knowledge。

    一次性迁移 / 测试 fixture 用；不进入 production main。作者优先级 CSV > BKP > 文件名解析。
    """
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
        input_fp = content_fingerprint(files)
        bkp = find_bkp(distill_dir, book_id)
        sp_meta = find_sp_metadata(sp_dir, book_id)

        author = (primary["作者"] or "").strip()
        if not author and bkp is not None and bkp["author"]:
            author = bkp["author"]
        if not author:
            author = parse_author_from_filename(primary["文件名"] or "")

        assets.append({
            "id": book_id,
            "name": name,
            "type": bootstrap_type(category, name),
            "author": author,
            "tags": split_tags(primary["标签"]),
            "notes": (primary["备注"] or "").strip(),
            "files": files,
            "purification": derive_purification(sp_meta, bkp, file_shas, input_fp),
            "knowledge": derive_knowledge(bkp, file_shas),
        })
    return assets


def load_manifests(mat_dir: Path) -> list:
    """[MIGRATION_ONLY] 读取 01_原始素材 下所有 collection_manifest.json（Local Only 证据）。"""
    manifests = []
    for mf in sorted(mat_dir.rglob(MANIFEST_FILENAME)):
        try:
            data = json.loads(mf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        manifests.append(data)
    return manifests


def build_containers(manifests: list, scanned: dict) -> list:
    """[MIGRATION_ONLY] 由 manifest 构建 containers（original 为容器原始文件，SHA 以磁盘扫描为准）。"""
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
    """[MIGRATION_ONLY] 组装 ledger（schema_version / assets / containers）。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "assets": assets,
        "containers": containers,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="素材资产 canonical ledger refresh + derived views")
    parser.add_argument("--root", default=os.getcwd(), help="仓库根目录（默认当前目录）")
    parser.add_argument("--check", action="store_true", help="仅校验 ledger/磁盘/视图，不写盘")
    args = parser.parse_args(argv)
    return refresh_and_render(Path(args.root), check_only=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
