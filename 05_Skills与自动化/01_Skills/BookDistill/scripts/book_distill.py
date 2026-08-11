#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BookDistill v0.2 — 原著蒸馏纪律工作台（vNext Base Scan 升级）。

职责（机械纪律 + 结构化分析支持）：
  1. validate  —— 校验 SourcePrepare PASS 输入包完整性与一致性；
  2. prepare   —— 生成章节索引、作品地图模板与每章证据模板（含 OBSERVATION）；
  3. assemble  —— 校验证据记录、计算维度覆盖度，汇总清单与报告骨架；
  4. profile   —— 基于 Base Scan 结果生成 BookProfile（维度覆盖、深挖建议）；
  5. deepdive  —— 生成专项深挖模板（复用 assemble 校验逻辑）；
  6. bkp       —— BKP Finalize（校验 bkp_prototype 并封装正式 BKP 到 bkp/）。

蒸馏分析内容由运行本 Skill 的 Agent / 作者在证据模板中填写：
  FACT / INFERENCE / OBSERVATION（v0.2 新增）/ MECHANISM / BOUNDARY。
OBSERVATION 可携带分析维度标签（人物、关系、信息控制等），支持全维度覆盖。
MAP 为独立结构性作品地图，不属于 Evidence kind。
脚本不调用大模型，不修改 SourcePrepare 输出，不读取 01_原始素材。

版本说明（0.2.0）：
  - Base Scan 升级：新增 OBSERVATION 证据分类与可扩展维度框架。
  - 新增 MAP 结构性作品地图节（独立于证据分类）。
  - assemble 增加维度覆盖统计（dimension_stats）。
  - 新增 profile / deepdive / bkp 子命令。
  - bkp 升级为最小 BKP Finalize：校验身份/源指纹、知识类型边界、引用与计数后，
    依据 BKP_v0.1_protocol.md 将人工验证的 bkp_prototype 封装为正式 BKP。
  - 旧四类证据（FACT/INFERENCE/MECHANISM/BOUNDARY）完全兼容。

版本说明（0.1.1）：
  - 章节数校验改为精确相等（0000 前置不计入正文，不再允许“差 1”）。
  - 新增 book_id 与输入目录前缀一致性校验。
  - assemble 增加 --input：校验 source snapshot 与行号越界（end <= 章节实际行数）。
  - distill_manifest.json 固化 source_sha256 / SP version / book_id / chapter_count /
    chapter_content_fingerprint，供后续 assemble 防复用旧产物。

接口契约（继承自旧分支 skill/source-prepare-v1 的接口草案，见 PROVENANCE.md）：
  SourcePrepare PASS -> 06_工作区/SourcePrepare/<作品ID>_<作品>/full.md + chapters/
                     -> 02_原著蒸馏/<作品ID>_<作品>/
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

# ---- 常量 ---------------------------------------------------------------

SP_STATUS_PASS = "PASS"
SP_EXPECTED_VERSION = "0.2.1"
BD_VERSION = "0.2.0"

# 证据记录允许的分类（evidence-first 分层，v0.2 扩展 OBSERVATION）
EVIDENCE_KINDS = ["FACT", "INFERENCE", "OBSERVATION", "MECHANISM", "BOUNDARY"]

# v0.1 基础观察维度框架（可扩展，不设计为永久冻结的封闭枚举）
# OBSERVATION 条目可携带 dimension 标签，使 BookProfile 能区分
# "已扫描但无显著发现" 与 "未扫描"。
BASE_DIMENSIONS = [
    "人物", "关系", "信息控制", "Reader Experience",
    "POV", "情绪", "Scene Turn", "节奏",
    "世界观", "冲突", "主题", "文体",
    "意象", "结构",
]
# 章节文件前缀（0000_前置内容.md 为卷首非章节内容，不参与正文蒸馏）
CHAPTER_PREFIX = "chapters"
PREAMBLE_GLOB = "0000_*.md"

# profile 中 Agent 填写区域的起始标记
AGENT_SECTION_MARKER = "## 深挖建议"
# profile 首次生成时的 Agent 区域模板占位符
PROFILE_TEMPLATE_TAIL = (
    "\n## 深挖建议\n\n"
    "（由运行 Skill 的 Agent 基于以上数据填写："
    "哪些维度值得专项深挖、理由、建议的分析方法来源。）\n"
)

# ---- BKP Finalize 常量 ---------------------------------------------------

# 正式 BKP 输出目录与人工验证的原型目录（位于 BookDistill 输出目录内）
BKP_DIR = "bkp"
BKP_PROTOTYPE_DIR = "bkp_prototype"

# 知识文件角色：用于类型边界与引用校验
BKP_ROLE_FILES = {
    "knowledge/observations.md": "observation",
    "knowledge/inferences.md": "inference",
    "knowledge/patterns.md": "patterns",
    "knowledge/boundaries.md": "boundaries",
}

# 需要保留人工内容的 curated 文件（重跑时若被修改则不覆盖）
BKP_CURATED_FILES = [
    "README.md",
    "work_map.md",
    "profile.md",
    "knowledge/observations.md",
    "knowledge/inferences.md",
    "knowledge/patterns.md",
    "knowledge/boundaries.md",
]
BKP_BASE_WHITELIST = set(BKP_CURATED_FILES) | {"identity.json"}

# 引用与类型边界校验用正则
LINE_REF_RE = re.compile(r"chapters/\d{4}\.md#L\d+(?:-L\d+)?")
CHAPTER_REF_RE = re.compile(r"(?:chapters/\d{4}\.md|ch_\d{4})")
LEADING_KIND_RE = re.compile(
    r"^\s*-\s*\*?\[(FACT|INFERENCE|OBSERVATION|MECHANISM|BOUNDARY)\]"
)
DD_SOURCE_RE = re.compile(r"deep_dive/[^`\s，,）)]+\.md")
UPGRADE_HEADER_RE = re.compile(
    r"^##\s*(Cross-book Pattern|Production Rule)\b", re.MULTILINE
)
OLD_PLACEHOLDER_MARK = "BKP Finalize（占位）"

# ---- 小工具 -------------------------------------------------------------


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def chapter_sort_key(name: str) -> tuple[int, str]:
    """0001.md -> (1, '')；0000_前置内容.md -> (0, '0000_前置内容.md')。"""
    stem = Path(name).stem
    m = re.match(r"^(\d{4})(?:_.*)?$", stem)
    if m:
        return (int(m.group(1)), "")
    return (0, name)


def is_chapter_file(name: str) -> bool:
    """正文章节：NNNN.md（四位数编号），排除 0000 前置与目录。"""
    return bool(re.match(r"^\d{4}\.md$", name)) and not name.startswith("0000_")


def is_preamble_file(name: str) -> bool:
    return name.startswith("0000_")


def compute_chapter_fingerprint(chapters_dir: Path) -> str:
    """按稳定章节顺序（NNNN.md 升序）计算聚合 SHA256。

    每个章节的贡献 = 文件名 + "\\0" + 文件原始字节，按顺序拼接后整体哈希。
    只要任一章节文件名或内容变化，fingerprint 即变化；0000 前置不计入。
    """
    h = hashlib.sha256()
    for name in sorted(
        (p.name for p in chapters_dir.glob("*.md") if is_chapter_file(p.name)),
        key=chapter_sort_key,
    ):
        h.update(name.encode("utf-8"))
        h.update(b"\0")
        h.update((chapters_dir / name).read_bytes())
    return h.hexdigest()


def build_source_snapshot(meta: dict, chapters_dir: Path) -> dict | None:
    """从 metadata.json + chapters/ 构建不可篡改的输入快照。

    metadata 属于 Local Only，不进入 Git；snapshot 字段会固化进
    distill_manifest.json / bd_report.md，供 assemble 校验复用。
    """
    selected = meta.get("selected_source") or {}
    sha256 = str(selected.get("sha256", ""))
    if not sha256 or not chapters_dir.is_dir():
        return None
    return {
        "book_id": str(meta.get("book_id", "")),
        "sp_version": str(meta.get("skill_version", "")),
        "source_sha256": sha256,
        "chapter_count": int(meta.get("chapter_files", -1)),
        "chapter_content_fingerprint": compute_chapter_fingerprint(chapters_dir),
    }


def check_book_id_dir_prefix(sp_dir: Path, book_id: str) -> str | None:
    """输入目录名必须形如 <book_id>_<书名>，前缀与 metadata.book_id 精确一致。"""
    dirname = sp_dir.name
    if not book_id:
        return "metadata.json 缺少 book_id，无法核对目录前缀。"
    if not dirname.startswith(book_id + "_") and dirname != book_id:
        return (
            f"输入目录名 '{dirname}' 与 metadata.book_id '{book_id}' 不一致"
            "（目录名必须为 <book_id>_<书名>）。"
        )
    return None

# ---- 输入校验 -----------------------------------------------------------


def validate_input(sp_dir: Path) -> dict:
    """校验 SourcePrepare PASS 包。返回校验结果 dict，含 errors 列表。"""
    errors: list[str] = []
    warnings: list[str] = []
    info: dict = {}

    if not sp_dir.is_dir():
        return {"ok": False, "errors": [f"输入目录不存在: {sp_dir}"], "warnings": [], "info": {}}

    meta_path = sp_dir / "metadata.json"
    if not meta_path.exists():
        return {"ok": False, "errors": [f"缺少 metadata.json: {meta_path}"], "warnings": [], "info": {}}

    meta = json.loads(read_text(meta_path))

    # 1. 状态必须 PASS
    status = str(meta.get("status", "")).upper()
    if status != SP_STATUS_PASS:
        errors.append(f"SourcePrepare 状态不是 PASS（当前: {status}），BookDistill 禁止读取。")
    info["status"] = status

    # 2. SP 版本
    version = str(meta.get("skill_version", ""))
    if version != SP_EXPECTED_VERSION:
        warnings.append(f"SP 版本 {version} 与期望 {SP_EXPECTED_VERSION} 不一致，仅记录，不阻塞。")
    info["skill_version"] = version

    # 3. book_id 与书名
    book_id = str(meta.get("book_id", ""))
    book = str(meta.get("book", ""))
    if not book_id:
        errors.append("metadata.json 缺少 book_id。")
    else:
        prefix_err = check_book_id_dir_prefix(sp_dir, book_id)
        if prefix_err:
            errors.append(prefix_err)
    info["book_id"] = book_id
    info["book"] = book

    # 4. 必需文件
    required = ["full.md", "metadata.json", "conversion_report.md"]
    chapters_dir = sp_dir / CHAPTER_PREFIX
    if not chapters_dir.is_dir():
        errors.append(f"缺少 chapters/ 目录: {chapters_dir}")
    for f in required:
        if not (sp_dir / f).exists():
            errors.append(f"缺少必需文件: {f}")

    # 5. 章节文件与 metadata 一致性
    chapter_files = sorted(
        [p.name for p in chapters_dir.glob("*.md") if is_chapter_file(p.name)],
        key=chapter_sort_key,
    ) if chapters_dir.is_dir() else []
    meta_chapters = int(meta.get("chapter_files", -1))
    info["chapter_files_on_disk"] = len(chapter_files)
    info["chapter_files_in_meta"] = meta_chapters
    if meta_chapters == -1:
        errors.append("metadata.json 缺少 chapter_files。")
    elif len(chapter_files) != meta_chapters:
        # 精确相等：0000_前置内容.md 不参与正文计数，metadata.chapter_files
        # 只统计 NNNN.md；任何 ±1 都意味着实际缺章或多章，必须 FAIL。
        errors.append(
            f"章节文件数 {len(chapter_files)} 与 metadata.chapter_files "
            f"{meta_chapters} 不一致（必须精确相等；0000 前置不影响正文计数）。"
        )

    # 6. 源指纹 / SHA256 存在性
    selected = meta.get("selected_source") or {}
    if not selected.get("sha256"):
        errors.append("metadata.json 缺少 selected_source.sha256（源指纹）。")
    else:
        info["source_sha256"] = str(selected["sha256"])
        info["source_path"] = str(selected.get("path", ""))

    # 6.5 source snapshot（book_id / SP version / source_sha256 / chapter_count /
    #     chapter_content_fingerprint）——固化到最终 tracked 产物，不保存原始路径。
    chapters_dir = sp_dir / CHAPTER_PREFIX
    snapshot = build_source_snapshot(meta, chapters_dir)
    if snapshot is None:
        errors.append("无法构建 source snapshot（缺少 chapters/ 或 selected_source.sha256）。")
    else:
        info["source_snapshot"] = snapshot
        info["chapter_content_fingerprint"] = snapshot["chapter_content_fingerprint"]

    # 7. 空章节检查
    empty_chapters = []
    for name in chapter_files:
        p = chapters_dir / name
        if len(p.read_text(encoding="utf-8", errors="replace").strip()) < 20:
            empty_chapters.append(name)
    if empty_chapters:
        warnings.append(f"疑似空/极短章节: {', '.join(empty_chapters)}")
    info["empty_chapters"] = empty_chapters

    ok = len(errors) == 0
    return {"ok": ok, "errors": errors, "warnings": warnings, "info": info}


# ---- prepare：章节索引 + 证据模板 ---------------------------------------


def build_chapter_index(sp_dir: Path) -> list[dict]:
    """返回按阅读顺序排列的正文章节元数据列表。"""
    chapters_dir = sp_dir / CHAPTER_PREFIX
    entries = []
    for name in sorted(
        [p.name for p in chapters_dir.glob("*.md") if is_chapter_file(p.name)],
        key=chapter_sort_key,
    ):
        p = chapters_dir / name
        text = read_text(p)
        lines = text.splitlines()
        # 章节标题：首行形如 "> 一" 的引用行
        title = ""
        for line in lines[:5]:
            s = line.strip()
            if s.startswith(">") and len(s) > 1:
                title = s.lstrip(">").strip()
                break
        entries.append(
            {
                "file": name,
                "title": title,
                "chars": len(text),
                "lines": len(lines),
                "ref_prefix": Path(CHAPTER_PREFIX) / name,
            }
        )
    return entries


def render_index_md(book: str, book_id: str, entries: list[dict]) -> str:
    lines = [
        f"# 章节索引：{book}（{book_id}）",
        "",
        f"> 由 BookDistill v{BD_VERSION} 生成。每条证据必须引用 `chapters/NNNN.md` 章节文件；",
        "> 引用格式：`chapters/NNNN.md#L<起始行>-L<结束行>` 或 `chapters/NNNN.md#L<行>`。",
        "",
        "| 章节 | 标题 | 字符数 | 行数 |",
        "|------|------|-------:|-----:|",
    ]
    for e in entries:
        lines.append(
            f"| chapters/{e['file']} | {e['title']} | {e['chars']} | {e['lines']} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_evidence_template(e: dict, book: str, book_id: str) -> str:
    lines = [
        f"# 章节证据：{e['file']}",
        "",
        f"- 作品：{book}（{book_id}）",
        f"- 来源文件：`{e['ref_prefix']}`（{e['chars']} 字符，{e['lines']} 行）",
        f"- 标题：{e['title'] or '（未识别）'}",
        "",
        "## 填写说明",
        "",
        "在对应分类下追加条目，每条格式：",
        "`- [kind] 一句话结论｜证据：chapters/NNNN.md#L<行范围>｜置信度：高/中/低`",
        "",
        "OBSERVATION 条目须携带维度标签：",
        "`- [OBSERVATION] dimension:维度名 | 一句话观察｜证据：chapters/NNNN.md#L<行范围>｜置信度：高/中/低`",
        "",
        "分类定义：",
        "- **FACT**：原文可直接支持的事实（引用必须落在原文行范围内）。",
        "- **INFERENCE**：由原文推断的含义，不直接出现在字面。",
        "- **OBSERVATION**：作品内观察（按维度标记），不强制收口为可迁移机制。",
        "- **MECHANISM**：可迁移的写作机制/技法（需说明为何可迁移，不能是剧情换皮）。",
        "- **BOUNDARY**：本条的边界/不确定性/反证（如译本影响、样本局限）。",
        "",
        "## MAP（章节作品地图）",
        "",
        "> 结构性地图，不属于 Evidence kind。填写本章的场景切换、人物功能、",
        "> 时间线位置、信息状态变化、冲突/stakes 级别等结构性信息。",
        "",
        "## FACT（原文事实）",
        "",
        "## INFERENCE（推断）",
        "",
        "## OBSERVATION（作品内观察）",
        "",
        "## MECHANISM（可迁移机制）",
        "",
        "## BOUNDARY（边界与不确定性）",
        "",
    ]
    return "\n".join(lines)


# ---- assemble：校验证据 + 汇总 ------------------------------------------


def extract_evidence_entries(ev_text: str) -> tuple[list[tuple[str, str]], list[str]]:
    """从证据模板文本提取 (kind, line) 条目与非法分类行。

    合法 kind 条目进入 entries；行首形如 `- [X]` 但 X 不在允许列表的记入 invalid。
    """
    entries: list[tuple[str, str]] = []
    invalid: list[str] = []
    for line in ev_text.splitlines():
        m = re.match(r"^\s*-\s*\[(\w+)\]\s*(.+)$", line)
        if m:
            kind = m.group(1).upper()
            if kind in EVIDENCE_KINDS:
                entries.append((kind, line.strip()))
            else:
                invalid.append(line.strip())
    return entries, invalid


def extract_ref_from_line(line: str) -> str | None:
    """提取 '证据：chapters/NNNN.md#L..' 引用；容忍全角｜与半角| 分隔。"""
    m = re.search(r"证据：\s*(chapters/\d{4}\.md#L\d+(?:-L\d+)?)", line)
    return m.group(1) if m else None


def parse_observation_dimension(entry_line: str) -> str | None:
    """从 OBSERVATION 条目提取 dimension 标签。

    格式：- [OBSERVATION] dimension:人物 | 观察内容｜证据：...
    返回维度字符串或 None（未标记时）。
    """
    m = re.match(r"^\s*-\s*\[OBSERVATION\]\s*dimension\s*[:：]\s*(.+?)(?:\s*\|\s*|\s*$)", entry_line)
    if m:
        dim = m.group(1).rstrip("| ").strip()
        return dim if dim else None
    return None


def compute_dimension_coverage(
    evidence_dir: Path, valid_files: list[str]
) -> dict:
    """统计 OBSERVATION 条目的维度覆盖度。

    返回 {dimension: {count, chapters}} 结构。
    无 OBSERVATION 条目时返回空 dict（兼容旧产物）。
    """
    coverage: dict[str, dict] = {}
    ev_files = sorted(evidence_dir.glob("ch_*.md")) if evidence_dir.is_dir() else []
    for evf in ev_files:
        text = read_text(evf)
        entries, _ = extract_evidence_entries(text)
        ch_name = evf.name  # ch_NNNN.md
        for kind, line in entries:
            if kind == "OBSERVATION":
                dim = parse_observation_dimension(line)
                if dim:
                    if dim not in coverage:
                        coverage[dim] = {"count": 0, "chapters": set()}
                    coverage[dim]["count"] += 1
                    coverage[dim]["chapters"].add(ch_name)
    # sets 不能 JSON 序列化，转为 sorted list
    return {
        dim: {"count": data["count"], "chapters": sorted(data["chapters"])}
        for dim, data in sorted(coverage.items())
    }


def validate_evidence_entries(
    entries: list[tuple[str, str]],
    valid_files: list[str],
    line_bounds: dict[str, int],
    file_label: str = "",
) -> tuple[bool, list[str]]:
    """校验证据条目的引用格式、章节存在性与行号范围。

    返回 (ok, errors)。可复用于 evidence/ 与 deepdive/ 文件。
    """
    errors: list[str] = []
    prefix = f"{file_label}: " if file_label else ""
    for kind, line in entries:
        ref = extract_ref_from_line(line)
        if not ref:
            errors.append(f"{prefix}条目缺少'证据：'引用 -> {line[:60]}")
            continue
        ok, msg = validate_ref(ref, valid_files, line_bounds)
        if not ok:
            errors.append(f"{prefix}{msg} -> {line[:80]}")
    return (len(errors) == 0, errors)


def validate_ref(
    ref: str, valid_files: list[str], line_bounds: dict[str, int]
) -> tuple[bool, str]:
    """校验证据引用指向存在的章节文件，且行号不超出章节实际总行数。"""
    m = re.match(r"^(chapters/\d{4}\.md)#L(\d+)(?:-L(\d+))?$", ref)
    if not m:
        return False, f"引用格式不合法: {ref}"
    if m.group(1) not in valid_files:
        return False, f"引用指向不存在的章节文件: {ref}"
    start, end = int(m.group(2)), int(m.group(3) or m.group(2))
    if start < 1 or end < start:
        return False, f"行范围非法: {ref}"
    max_lines = line_bounds.get(m.group(1))
    if max_lines is None:
        return False, f"无法取得章节行数: {ref}"
    if end > max_lines:
        return (
            False,
            f"引用行号超出章节实际行数: {ref}（章节 {m.group(1)} 共 {max_lines} 行）",
        )
    return True, ""


def read_manifest(output_dir: Path) -> dict | None:
    manifest_path = output_dir / "distill_manifest.json"
    if manifest_path.exists():
        try:
            return json.loads(read_text(manifest_path))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def check_input_snapshot(
    sp_dir: Path | None, output_dir: Path
) -> tuple[str, dict | None]:
    """assemble 时重算输入 snapshot 并与 prepare 记录比对。

    返回 (状态, snapshot)：'ok' 一致可继续；'mismatch' 输入已变化必须 FAIL；
    'missing' 为旧版产物首次升级，自动记录并继续（带警告）。
    """
    if sp_dir is None:
        return "missing", None
    meta_path = sp_dir / "metadata.json"
    chapters_dir = sp_dir / CHAPTER_PREFIX
    if not meta_path.exists() or not chapters_dir.is_dir():
        return "missing", None
    meta = json.loads(read_text(meta_path))
    current = build_source_snapshot(meta, chapters_dir)
    if current is None:
        return "missing", None

    manifest = read_manifest(output_dir)
    recorded = (manifest or {}).get("source_snapshot")
    if recorded is None:
        return "missing", current
    if recorded != current:
        return "mismatch", current
    return "ok", current


def assemble(output_dir: Path, sp_dir: Path | None = None) -> dict:
    """校验 evidence/*.md 记录，生成 distill_manifest.json 与报告骨架。

    空模板（无任何条目）记为警告（未覆盖），不阻塞；
    条目格式/引用错误记为错误（格式坏），阻塞。
    sp_dir 提供时额外校验：source snapshot 一致性 + 行号不越界。
    """
    errors: list[str] = []
    warnings: list[str] = []
    stats = {k: 0 for k in EVIDENCE_KINDS}
    per_file: dict[str, int] = {}

    evidence_dir = output_dir / "evidence"
    ev_files = sorted(evidence_dir.glob("ch_*.md")) if evidence_dir.is_dir() else []

    # 有效章节文件清单（来自章节索引）
    index_path = output_dir / "chapters_index.md"
    valid_files: list[str] = []
    if index_path.exists():
        for m in re.finditer(r"\| (chapters/\d{4}\.md) \|", read_text(index_path)):
            valid_files.append(m.group(1))

    # 章节实际行数（来自输入 chapters/，用于行号越界校验；缺输入时用索引行数）
    line_bounds: dict[str, int] = {}
    if sp_dir is not None and (sp_dir / CHAPTER_PREFIX).is_dir():
        for name in sorted(
            (p.name for p in (sp_dir / CHAPTER_PREFIX).glob("*.md") if is_chapter_file(p.name)),
            key=chapter_sort_key,
        ):
            text = read_text(sp_dir / CHAPTER_PREFIX / name)
            line_bounds[f"{CHAPTER_PREFIX}/{name}"] = len(text.splitlines())
    else:
        for m in re.finditer(r"\| (chapters/\d{4}\.md) \| (\d+) \|", read_text(index_path)):
            line_bounds[m.group(1)] = int(m.group(2))

    for evf in ev_files:
        text = read_text(evf)
        entries, invalid_lines = extract_evidence_entries(text)
        if invalid_lines:
            errors.append(
                f"{evf.name}: 存在非法分类条目"
                f"（允许 {'/'.join(EVIDENCE_KINDS)}）: "
                f"{invalid_lines[0][:50]}"
            )
            continue
        if not entries:
            warnings.append(f"{evf.name}: 无证据条目（该章未分析，覆盖缺口）。")
            continue
        per_file[evf.name] = len(entries)
        for kind, line in entries:
            stats[kind] += 1
        _, ref_errors = validate_evidence_entries(entries, valid_files, line_bounds, evf.name)
        errors.extend(ref_errors)

    # source snapshot 一致性（防 assemble 复用旧产物）
    snapshot_status, current_snapshot = check_input_snapshot(sp_dir, output_dir)
    if snapshot_status == "mismatch":
        errors.append(
            "输入 SourcePrepare 包与 distill_manifest.json 中记录的 source snapshot "
            "不一致（章节内容或源指纹已变化），禁止复用旧 evidence，请重新 prepare。"
        )
    elif snapshot_status == "missing":
        warnings.append(
            "distill_manifest.json 缺少 source_snapshot（旧版产物），本次已自动记录当前 "
            "输入 snapshot；下次 assemble 将严格比对。"
        )

    # 维度覆盖统计（v0.2 Base Scan 升级）
    dimension_stats = compute_dimension_coverage(evidence_dir, valid_files)

    # manifest
    manifest = {
        "skill": "BookDistill",
        "version": BD_VERSION,
        "source_snapshot": current_snapshot,
        "evidence_files": [f.name for f in ev_files],
        "entries_per_file": per_file,
        "stats_by_kind": stats,
        "dimension_stats": dimension_stats,
        "total_entries": sum(stats.values()),
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
    write_text(
        output_dir / "distill_manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2),
    )
    return manifest


def extract_agent_sections(content: str) -> str | None:
    """从现有 book_profile.md 提取 Agent 填写区域（## 深挖建议 及之后）。

    返回 Agent 内容字符串；未找到标记或仅有模板占位符时返回 None。
    """
    idx = content.find(AGENT_SECTION_MARKER)
    if idx == -1:
        return None
    agent_text = content[idx:].strip()
    # 检测是否仍为模板占位符（Agent 未实际填写）
    after_header = agent_text[len(AGENT_SECTION_MARKER):].strip()
    if after_header.startswith("（由运行 Skill 的 Agent"):
        return None
    return agent_text


def merge_profile(machine_text: str, existing_path: Path) -> str:
    """合并：机器统计部分用新生成内容，Agent 填写区域保留现有文件内容。"""
    if not existing_path.exists():
        return machine_text
    existing = read_text(existing_path)
    agent_content = extract_agent_sections(existing)
    if agent_content:
        return machine_text.rstrip() + "\n\n" + agent_content + "\n"
    return machine_text


def render_report_skeleton(book: str, book_id: str, manifest: dict) -> str:
    return (
        f"# 蒸馏报告：{book}（{book_id}）\n\n"
        f"- BookDistill 版本：{BD_VERSION}\n"
        f"- source snapshot：{json.dumps(manifest.get('source_snapshot'), ensure_ascii=False)}\n"
        f"- 证据条目总数：{manifest['total_entries']}\n"
        f"- 分类统计：{json.dumps(manifest['stats_by_kind'], ensure_ascii=False)}\n"
        f"- 覆盖章节：{len(manifest['entries_per_file'])} 个证据文件\n\n"
        "## 方法\n\n（填写：阅读范围、分析方式、译本说明）\n\n"
        "## 覆盖范围与置信度\n\n（填写：哪些部分覆盖充分、哪些局部、哪些未覆盖）\n\n"
        "## 边界与不确定性\n\n（填写：译本影响、样本局限、不随意外推声明）\n\n"
    )


# ---- BKP Finalize：校验 + 封装 -------------------------------------------


def load_json_text(path: Path) -> dict | None:
    """读取 JSON 文件；不存在或解析失败返回 None。"""
    if not path.exists():
        return None
    try:
        return json.loads(read_text(path))
    except (OSError, json.JSONDecodeError):
        return None


def bullet_lines(text: str) -> list[str]:
    """Markdown 无序列表条目（`- ` 开头且非空）。"""
    return [ln for ln in text.splitlines() if re.match(r"^\s*-\s+\S", ln)]


def parse_chapter_lines(out_dir: Path) -> dict[str, int]:
    """从 chapters_index.md 读取 {chapters/NNNN.md: 行数}。"""
    index_path = out_dir / "chapters_index.md"
    if not index_path.exists():
        return {}
    result: dict[str, int] = {}
    for line in read_text(index_path).splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 5 and parts[1].startswith("chapters/") and parts[4].isdigit():
            result[parts[1]] = int(parts[4])
    return result


def validate_line_refs_in_text(
    text: str, chapter_lines: dict[str, int], label: str
) -> list[str]:
    """校验文本中所有 chapters/NNNN.md#L.. 引用（章节存在 + 行号不越界）。"""
    errors: list[str] = []
    valid_files = list(chapter_lines.keys())
    for ref in sorted(set(LINE_REF_RE.findall(text))):
        ok, msg = validate_ref(ref, valid_files, chapter_lines)
        if not ok:
            errors.append(f"{label}: {msg}")
    return errors


def validate_observation_file(path: Path, chapter_lines: dict[str, int]) -> list[str]:
    """Observation 层：必须带章节+行号引用，不得混入证据分类标记。"""
    text = read_text(path)
    errors: list[str] = []
    for i, line in enumerate(bullet_lines(text), 1):
        if LEADING_KIND_RE.match(line):
            errors.append(
                f"{path.name}:L{i} Observation 条目混入证据分类标记 -> {line[:60]}"
            )
        if not LINE_REF_RE.search(line):
            errors.append(
                f"{path.name}:L{i} Observation 缺少章节+行号引用 -> {line[:60]}"
            )
    errors += validate_line_refs_in_text(text, chapter_lines, path.name)
    return errors


def validate_inference_file(path: Path, chapter_lines: dict[str, int]) -> list[str]:
    """Inference 层：必须明确标记 [INFERENCE] 且带章节+行号引用。"""
    text = read_text(path)
    errors: list[str] = []
    for i, line in enumerate(bullet_lines(text), 1):
        if "[INFERENCE]" not in line.upper():
            errors.append(f"{path.name}:L{i} 条目缺少 [INFERENCE] 标记 -> {line[:60]}")
            continue
        m = LEADING_KIND_RE.match(line)
        if m and m.group(1) != "INFERENCE":
            errors.append(
                f"{path.name}:L{i} Inference 条目被标记为 {m.group(1)} -> {line[:60]}"
            )
        if not LINE_REF_RE.search(line):
            errors.append(
                f"{path.name}:L{i} Inference 缺少章节+行号引用 -> {line[:60]}"
            )
    errors += validate_line_refs_in_text(text, chapter_lines, path.name)
    return errors


def _pattern_entries(text: str) -> list[tuple[str, int]]:
    """提取 Pattern 条目：(行内容, 行号)。编号条目或 - **P.. 深挖 Pattern。"""
    result: list[tuple[str, int]] = []
    for i, line in enumerate(text.splitlines(), 1):
        if re.match(r"^\s*\d+\.\s+\*\*", line) or re.match(r"^\s*-\s*\*\*P\d+", line):
            result.append((line, i))
    return result


def validate_patterns_file(
    path: Path, chapter_lines: dict[str, int], proto_dir: Path
) -> list[str]:
    """Pattern 层：默认 Work-specific Pattern；禁止升级章节标题；

    每条需有章节级引用（ch_NNNN / chapters/NNNN.md），或属于显式声明
    来源 Deep Dive 文件（该文件必须存在且含行级证据）的深挖 Pattern 节。
    """
    text = read_text(path)
    errors: list[str] = []
    lines = text.splitlines()

    for m in UPGRADE_HEADER_RE.finditer(text):
        errors.append(f"{path.name}: 出现知识升级章节标题 -> {m.group(0)}")

    for line, i in _pattern_entries(text):
        if CHAPTER_REF_RE.search(line):
            continue
        # 无内联引用：检查所属节内是否有 Deep Dive 来源声明
        section_start = i
        while section_start > 1 and not lines[section_start - 1].startswith("##"):
            section_start -= 1
        section_text = (
            "\n".join(lines[section_start - 1 : i - 1]) if section_start > 1 else ""
        )
        dd_sources = DD_SOURCE_RE.findall(section_text) + DD_SOURCE_RE.findall(line)
        if not dd_sources:
            errors.append(
                f"{path.name}:L{i} Pattern 条目缺少章节引用且无 Deep Dive 来源"
                f" -> {line[:60]}"
            )
            continue
        for ref in dd_sources:
            if not (proto_dir / ref).exists():
                errors.append(
                    f"{path.name}:L{i} Pattern 引用的 Deep Dive 文件不存在 -> {ref}"
                )

    if _pattern_entries(text) and CHAPTER_REF_RE.search(text) is None and not any(
        DD_SOURCE_RE.search(line) for line in lines
    ):
        errors.append(f"{path.name}: 全文件无任何章节级引用，无法回溯原文。")

    errors += validate_line_refs_in_text(text, chapter_lines, path.name)
    return errors


def validate_deep_dive_file(path: Path, chapter_lines: dict[str, int]) -> list[str]:
    """Deep Dive 最终知识：证据条目带行级引用 + 知识等级声明。"""
    text = read_text(path)
    errors: list[str] = []
    if "Pattern Hypothesis" not in text and "单书" not in text:
        errors.append(f"{path.name}: 缺少知识等级声明（Pattern Hypothesis / 单书）。")
    entries, invalid = extract_evidence_entries(text)
    if invalid:
        errors.append(
            f"{path.name}: 存在非法分类条目"
            f"（允许 {'/'.join(EVIDENCE_KINDS)}）: {invalid[0][:50]}"
        )
    for kind, line in entries:
        if not LINE_REF_RE.search(line):
            errors.append(
                f"{path.name}: {kind} 条目缺少章节+行号引用 -> {line[:60]}"
            )
    errors += validate_line_refs_in_text(text, chapter_lines, path.name)
    return errors


def validate_boundaries_file(path: Path, chapter_lines: dict[str, int]) -> list[str]:
    """边界层：章节级边界须指向存在的章节；全局边界属元信息，不强制行号。"""
    text = read_text(path)
    errors: list[str] = []
    for i, line in enumerate(bullet_lines(text), 1):
        for m in re.finditer(r"ch_(\d{4})", line):
            ref = f"chapters/{m.group(1)}.md"
            if ref not in chapter_lines:
                errors.append(f"{path.name}:L{i} 章节引用不存在 -> {ref}")
    errors += validate_line_refs_in_text(text, chapter_lines, path.name)
    return errors


def validate_work_map(path: Path, chapter_lines: dict[str, int]) -> list[str]:
    """作品地图：章节标题必须对应实际章节。"""
    text = read_text(path)
    errors: list[str] = []
    for m in re.finditer(r"^###\s*ch_(\d{4})", text, re.MULTILINE):
        ref = f"chapters/{m.group(1)}.md"
        if ref not in chapter_lines:
            errors.append(f"{path.name}: 作品地图章节不存在 -> {ref}")
    return errors


def validate_bkp_counts(identity: dict, proto_dir: Path) -> list[str]:
    """校验 identity.json 声明的知识条数与实际文件一致（manifest 完整性）。"""
    errors: list[str] = []
    bc = identity.get("bkp_contents") or {}

    def declared(key: str, field: str):
        item = bc.get(key)
        return item.get(field) if isinstance(item, dict) else None

    obs_path = proto_dir / "knowledge" / "observations.md"
    inf_path = proto_dir / "knowledge" / "inferences.md"
    pat_path = proto_dir / "knowledge" / "patterns.md"

    if obs_path.exists():
        n_obs = len(bullet_lines(read_text(obs_path)))
        d_obs = declared("observations", "count")
        if d_obs is not None and d_obs != n_obs:
            errors.append(f"identity 声明 observations={d_obs}，实际文件 {n_obs}。")
    if inf_path.exists():
        n_inf = len(
            [l for l in bullet_lines(read_text(inf_path)) if "[INFERENCE]" in l.upper()]
        )
        d_inf = declared("inferences", "count")
        if d_inf is not None and d_inf != n_inf:
            errors.append(f"identity 声明 inferences={d_inf}，实际文件 {n_inf}。")
    if pat_path.exists():
        pat_text = read_text(pat_path)
        n_mech = len(re.findall(r"^\s*\d+\.\s+\*\*", pat_text, re.MULTILINE))
        n_p = len(re.findall(r"^\s*-\s*\*\*P\d+", pat_text, re.MULTILINE))
        d_mech = declared("patterns", "mechanism_count")
        d_p = declared("patterns", "deep_dive_pattern_count")
        if d_mech is not None and d_mech != n_mech:
            errors.append(f"identity 声明 mechanism_count={d_mech}，实际文件 {n_mech}。")
        if d_p is not None and d_p != n_p:
            errors.append(
                f"identity 声明 deep_dive_pattern_count={d_p}，实际文件 {n_p}。"
            )
    return errors


def validate_bkp_identity(identity, manifest_snapshot) -> list[str]:
    """校验 identity.json 必需字段与源指纹格式。"""
    errors: list[str] = []
    if not isinstance(identity, dict):
        return ["identity.json 不是合法 JSON 对象。"]
    book = identity.get("book") or {}
    snap = identity.get("source_snapshot") or {}
    if not identity.get("bkp_version"):
        errors.append("identity.json 缺少 bkp_version。")
    for field in ("book_id", "title", "author"):
        if not book.get(field):
            errors.append(f"identity.json book 缺少 {field}。")
    for field in ("source_sha256", "chapter_count", "chapter_content_fingerprint"):
        if field not in snap:
            errors.append(f"identity.json source_snapshot 缺少 {field}。")
    sha = str(snap.get("source_sha256", ""))
    if sha and not re.fullmatch(r"[0-9a-f]{64}", sha):
        errors.append("identity.json source_sha256 不是 64 位十六进制。")
    fp = str(snap.get("chapter_content_fingerprint", ""))
    if fp and not re.fullmatch(r"[0-9a-f]{64}", fp):
        errors.append("identity.json chapter_content_fingerprint 不是 64 位十六进制。")
    try:
        if int(book.get("chapter_count", -1)) != int(snap.get("chapter_count", -1)):
            errors.append("identity.json book.chapter_count 与 source_snapshot 不一致。")
    except (TypeError, ValueError):
        errors.append("identity.json chapter_count 不是整数。")
    if manifest_snapshot and snap != manifest_snapshot:
        errors.append(
            "identity.json source_snapshot 与 distill_manifest.json 不一致"
            "（源指纹或章节内容已变化）。"
        )
    if not identity.get("provenance"):
        errors.append("identity.json 缺少 provenance。")
    bc = identity.get("bkp_contents")
    if not isinstance(bc, dict):
        errors.append("identity.json 缺少 bkp_contents。")
    else:
        dd_count = int((identity.get("provenance") or {}).get("deep_dive_count", 0) or 0)
        if dd_count > 0 and not bc.get("deep_dives"):
            errors.append("identity.json 声明 deep_dive_count>0 但 deep_dives 为空。")
    return errors


def build_bkp_whitelist(identity: dict) -> set[str]:
    """原型允许进入正式 BKP 的文件白名单（标准文件 + identity 声明的文件）。"""
    whitelist = set(BKP_BASE_WHITELIST)

    def add_file(value) -> None:
        if isinstance(value, dict) and value.get("file"):
            whitelist.add(value["file"])
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and item.get("file"):
                    whitelist.add(item["file"])

    for value in (identity.get("bkp_contents") or {}).values():
        add_file(value)
    return whitelist


def normalize_readme_status(text: str) -> str:
    """将原型 README 的 PROTOTYPE 横幅替换为 FINALIZED 状态（其余内容原样保留）。"""
    banner = re.compile(r"^>\s*\*\*PROTOTYPE\*\*.*$", re.MULTILINE)
    new_banner = (
        "> **FINALIZED** — 依据 `BKP_v0.1_protocol.md` 封装；"
        "协议第 8 节未冻结项保持开放。本文件是作者打开 BKP 后的第一阅读入口。"
    )
    return banner.sub(new_banner, text, count=1) if banner.search(text) else text


def _copy_curated(
    src: Path, dst: Path, rel: str, report: dict, content: str | None = None
) -> None:
    """复制 curated 文件；目标已存在且内容不同时保留人工修改并告警。"""
    if content is None:
        content = read_text(src)
    if dst.exists():
        if read_text(dst) == content:
            # 内容一致时字节级复制，保持原型行尾/字节不变
            shutil.copyfile(src, dst)
            report["copied"].append(rel)
        else:
            report["skipped_curated"].append(rel)
            report["warnings"].append(
                f"已保留 BKP 中的人工修改，未覆盖 {rel}（如需更新请手动合并）。"
            )
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        report["copied"].append(rel)


def finalize_bkp(out_dir: Path, proto_dir: Path | None = None) -> dict:
    """BKP Finalize：校验 bkp_prototype，封装正式 BKP 到 <out>/bkp/。

    返回报告 dict：
      ok / errors / warnings / copied / skipped_curated / excluded / generated
    原则：
      - 不复制 Evidence 工作底稿、草稿、Prompt、日志等过程文件；
      - identity.json 为机器生成；curated 文件被人工修改时不覆盖；
      - 源指纹必须与 distill_manifest.json 一致。
    """
    report: dict = {
        "ok": False,
        "errors": [],
        "warnings": [],
        "copied": [],
        "skipped_curated": [],
        "excluded": [],
        "generated": [],
        "bkp_dir": str(out_dir / BKP_DIR),
    }
    if proto_dir is None:
        proto_dir = out_dir / BKP_PROTOTYPE_DIR
    else:
        proto_dir = Path(proto_dir)

    if not proto_dir.is_dir():
        report["errors"].append(
            f"未找到 BKP 原型目录: {proto_dir}"
            "（先完成 Base Scan / BookProfile / Deep Dive 并整理 bkp_prototype/）。"
        )
        return report

    manifest = read_manifest(out_dir)
    if manifest is None:
        report["errors"].append("缺少 distill_manifest.json：请先运行 prepare + assemble。")
        return report
    manifest_snapshot = manifest.get("source_snapshot")
    if not manifest_snapshot:
        report["errors"].append("distill_manifest.json 缺少 source_snapshot。")
        return report

    chapter_lines = parse_chapter_lines(out_dir)
    if not chapter_lines:
        report["errors"].append("缺少 chapters_index.md 或无法解析章节行数。")
        return report

    identity = load_json_text(proto_dir / "identity.json")
    report["errors"] += validate_bkp_identity(identity, manifest_snapshot)
    if not isinstance(identity, dict):
        return report

    whitelist = build_bkp_whitelist(identity)

    for rel, role in BKP_ROLE_FILES.items():
        path = proto_dir / rel
        if not path.exists():
            report["errors"].append(f"原型缺少必需知识文件: {rel}")
            continue
        if role == "observation":
            report["errors"] += validate_observation_file(path, chapter_lines)
        elif role == "inference":
            report["errors"] += validate_inference_file(path, chapter_lines)
        elif role == "patterns":
            report["errors"] += validate_patterns_file(path, chapter_lines, proto_dir)
        elif role == "boundaries":
            report["errors"] += validate_boundaries_file(path, chapter_lines)

    work_map_path = proto_dir / "work_map.md"
    if not work_map_path.exists():
        report["errors"].append("原型缺少必需文件: work_map.md")
    else:
        report["errors"] += validate_work_map(work_map_path, chapter_lines)

    dd_files: list[str] = []
    for item in (identity.get("bkp_contents") or {}).get("deep_dives") or []:
        rel = item.get("file") if isinstance(item, dict) else None
        if not rel:
            continue
        path = proto_dir / rel
        dd_files.append(rel)
        if not path.exists():
            report["errors"].append(f"原型缺少 Deep Dive 文件: {rel}")
        else:
            report["errors"] += validate_deep_dive_file(path, chapter_lines)

    report["errors"] += validate_bkp_counts(identity, proto_dir)
    if report["errors"]:
        return report

    # ---- 封装 ----
    bkp_dir = out_dir / BKP_DIR
    bkp_dir.mkdir(parents=True, exist_ok=True)

    new_identity = json.loads(json.dumps(identity))
    new_identity["bkp_version"] = "0.2"
    new_identity["schema_status"] = (
        "FINALIZED（依据 BKP_v0.1_protocol.md 封装；"
        "协议第 8 节未冻结项保持开放，不冻结最终 schema）"
    )
    new_identity["source_snapshot"] = manifest_snapshot
    provenance = dict(identity.get("provenance") or {})
    provenance["nature"] = (
        "正式 BKP（源自人工验证的 bkp_prototype，经 BookDistill bkp finalize 封装）"
    )
    new_identity["provenance"] = provenance
    new_identity["finalize"] = {
        "tool": "BookDistill bkp finalize",
        "version": BD_VERSION,
        "date": datetime.date.today().isoformat(),
        "input": "bkp_prototype/（人工验证的 curated 知识层）",
        "protocol": "BKP_v0.1_protocol.md",
        "knowledge_level": (
            "单书 BKP 最高为 Work-specific Pattern；"
            "不得升级 Cross-book Pattern / Production Rule"
        ),
        "rerun_policy": (
            "curated 文件若被人工修改则保留并告警；identity.json 由工具重生成"
        ),
    }
    write_text(
        bkp_dir / "identity.json",
        json.dumps(new_identity, ensure_ascii=False, indent=2),
    )
    report["generated"].append("identity.json")

    # README：横幅状态归一化；旧占位 README 视为机器产物可替换
    readme_content = normalize_readme_status(read_text(proto_dir / "README.md"))
    readme_dst = bkp_dir / "README.md"
    if (
        readme_dst.exists()
        and OLD_PLACEHOLDER_MARK not in read_text(readme_dst)
        and read_text(readme_dst) != readme_content
    ):
        report["skipped_curated"].append("README.md")
        report["warnings"].append(
            "已保留 BKP 中的人工修改，未覆盖 README.md（如需更新请手动合并）。"
        )
    else:
        readme_dst.parent.mkdir(parents=True, exist_ok=True)
        readme_dst.write_text(readme_content, encoding="utf-8", newline="\n")
        report["copied"].append("README.md")

    for rel in BKP_CURATED_FILES:
        if rel == "README.md":
            continue
        src = proto_dir / rel
        if not src.exists():
            continue
        _copy_curated(src, bkp_dir / rel, rel, report)

    for rel in dd_files:
        src = proto_dir / rel
        if not src.exists():
            continue
        _copy_curated(src, bkp_dir / rel, rel, report)

    # 过程文件排除：白名单之外的文件一律不进入正式 BKP
    for p in sorted(proto_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(proto_dir).as_posix()
        if rel not in whitelist:
            report["excluded"].append(rel)

    report["ok"] = True
    return report


# ---- CLI ----------------------------------------------------------------


def cmd_validate(args) -> int:
    result = validate_input(Path(args.input))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def cmd_prepare(args) -> int:
    sp_dir = Path(args.input)
    out_dir = Path(args.output)

    check = validate_input(sp_dir)
    if not check["ok"]:
        print("输入校验失败，中止 prepare：")
        for e in check["errors"]:
            print(f"  - {e}")
        return 1

    info = check["info"]
    entries = build_chapter_index(sp_dir)

    # 章节索引
    write_text(out_dir / "chapters_index.md", render_index_md(info["book"], info["book_id"], entries))

    # 每章证据模板
    for e in entries:
        write_text(
            out_dir / "evidence" / f"ch_{Path(e['file']).stem}.md",
            render_evidence_template(e, info["book"], info["book_id"]),
        )

    # 初始 manifest（固化 source snapshot，供 assemble 比对；条目由 assemble 填充）
    initial_manifest = {
        "skill": "BookDistill",
        "version": BD_VERSION,
        "source_snapshot": info.get("source_snapshot"),
        "evidence_files": [],
        "entries_per_file": {},
        "stats_by_kind": {k: 0 for k in EVIDENCE_KINDS},
        "dimension_stats": {},
        "total_entries": 0,
        "ok": False,
        "errors": [],
        "warnings": [],
    }
    write_text(
        out_dir / "distill_manifest.json",
        json.dumps(initial_manifest, ensure_ascii=False, indent=2),
    )

    # 报告骨架
    empty_manifest = {
        "total_entries": 0,
        "stats_by_kind": {k: 0 for k in EVIDENCE_KINDS},
        "entries_per_file": {},
        "source_snapshot": info.get("source_snapshot"),
    }
    write_text(out_dir / "bd_report.md", render_report_skeleton(info["book"], info["book_id"], empty_manifest))

    print(
        f"prepare 完成: {info['book']}（{info['book_id']}），"
        f"{len(entries)} 章，输出 -> {out_dir}"
    )
    if check["warnings"]:
        print("警告：")
        for w in check["warnings"]:
            print(f"  - {w}")
    return 0


def cmd_assemble(args) -> int:
    manifest = assemble(Path(args.output), Path(args.input) if args.input else None)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["ok"] else 1


def cmd_profile(args) -> int:
    """基于 Base Scan 结果生成 BookProfile。"""
    out_dir = Path(args.output)
    manifest = read_manifest(out_dir)
    if manifest is None:
        print("错误：未找到 distill_manifest.json，请先运行 prepare + assemble。")
        return 1

    if not manifest.get("source_snapshot"):
        print("警告：manifest 缺少 source_snapshot（旧版产物），Profile 数据可能不完整。")

    stats = manifest.get("stats_by_kind", {})
    dim_stats = manifest.get("dimension_stats", {})
    ev_files = manifest.get("evidence_files", [])
    uncovered = [f for f in ev_files if manifest.get("entries_per_file", {}).get(f, 0) == 0]

    machine_lines = [
        f"# BookProfile",
        "",
        f"- 生成工具：BookDistill v{BD_VERSION}",
        f"- 基于：distill_manifest.json",
        "",
        "## 扫描状态",
        "",
        f"- 证据文件数：{len(ev_files)}",
        f"- 证据条目总数：{manifest.get('total_entries', 0)}",
        f"- 未覆盖章节：{len(uncovered)}",
        "",
        "## 证据分类统计",
        "",
        "| 分类 | 数量 |",
        "|------|-----:|",
    ]
    for kind in EVIDENCE_KINDS:
        machine_lines.append(f"| {kind} | {stats.get(kind, 0)} |")

    machine_lines.extend([
        "",
        "## 维度覆盖",
        "",
        "| 维度 | Observation 数 | 覆盖章节数 |",
        "|------|---------------:|----------:|",
    ])
    scanned_dims = set(dim_stats.keys())
    for dim in BASE_DIMENSIONS:
        if dim in dim_stats:
            d = dim_stats[dim]
            machine_lines.append(f"| {dim} | {d['count']} | {len(d['chapters'])} |")
        else:
            machine_lines.append(f"| {dim} | 0 | 0 |")
    for dim in sorted(scanned_dims - set(BASE_DIMENSIONS)):
        d = dim_stats[dim]
        machine_lines.append(f"| {dim} | {d['count']} | {len(d['chapters'])} |")

    machine_lines.extend([
        "",
        "## Uncertainty / Counterevidence",
        "",
        f"BOUNDARY 条目数：{stats.get('BOUNDARY', 0)}",
        "",
    ])

    machine_text = "\n".join(machine_lines)
    profile_path = out_dir / "book_profile.md"

    # 合并：机器统计用新生成内容，Agent 填写区域保留现有文件
    merged = merge_profile(machine_text, profile_path)
    if not profile_path.exists() or extract_agent_sections(
        read_text(profile_path) if profile_path.exists() else ""
    ) is None:
        # 首次生成或无 Agent 内容：追加模板占位符
        merged = machine_text + PROFILE_TEMPLATE_TAIL

    write_text(profile_path, merged)
    print(f"profile 生成完成 -> {profile_path}")
    return 0


def cmd_deepdive(args) -> int:
    """生成专项深挖模板。"""
    out_dir = Path(args.output)
    if not out_dir.is_dir():
        print(f"错误：输出目录不存在: {out_dir}")
        return 1

    manifest = read_manifest(out_dir)
    if manifest is None:
        print("警告：未找到 distill_manifest.json，deep dive 将不包含扫描状态。")

    dimension = args.dimension
    topic = args.topic or dimension

    template_lines = [
        f"# 专项深挖：{topic}",
        "",
        f"- 维度/主题：{dimension}",
        f"- 生成工具：BookDistill v{BD_VERSION}",
        "",
        "## 深挖说明",
        "",
        "（填写：为何选择此维度深挖、分析方法来源（如 Apodictic/ani-book/oh-story））",
        "",
        "## Evidence（深挖证据）",
        "",
        "格式：`- [FACT/INFERENCE/OBSERVATION] 结论｜证据：chapters/NNNN.md#L<行范围>｜置信度：高/中/低`",
        "",
        "## Observation（深挖观察）",
        "",
        "## Pattern / Interpretation（可迁移模式或解释）",
        "",
        "## Counterevidence / Boundary（反证与边界）",
        "",
        "## Confidence（整体置信度与依据）",
        "",
        "## Scope（适用范围与外推边界）",
        "",
    ]

    dive_file = out_dir / "deepdive" / f"dd_{dimension.replace(' ', '_').replace('/', '_')}.md"
    if not dive_file.exists():
        write_text(dive_file, "\n".join(template_lines))
        print(f"deepdive 模板生成 -> {dive_file}")
    else:
        print(f"deepdive 文件已存在，跳过模板生成: {dive_file}")

    # 校验已填写的深挖内容（复用 assemble 校验逻辑）
    sp_input = getattr(args, 'input', None)
    if sp_input:
        sp_dir = Path(sp_input)
        manifest_data = read_manifest(out_dir)
        valid_files: list[str] = []
        index_path = out_dir / "chapters_index.md"
        if index_path.exists():
            for m_idx in re.finditer(r"\| (chapters/\d{4}\.md) \|", read_text(index_path)):
                valid_files.append(m_idx.group(1))
        line_bounds: dict[str, int] = {}
        if sp_dir.is_dir() and (sp_dir / CHAPTER_PREFIX).is_dir():
            for name in sorted(
                (p.name for p in (sp_dir / CHAPTER_PREFIX).glob("*.md") if is_chapter_file(p.name)),
                key=chapter_sort_key,
            ):
                text = read_text(sp_dir / CHAPTER_PREFIX / name)
                line_bounds[f"{CHAPTER_PREFIX}/{name}"] = len(text.splitlines())

        dd_text = read_text(dive_file)
        dd_entries, dd_invalid = extract_evidence_entries(dd_text)
        dd_errors: list[str] = []
        if dd_invalid:
            dd_errors.append(
                f"{dive_file.name}: 存在非法分类条目"
                f"（允许 {'/'.join(EVIDENCE_KINDS)}）: {dd_invalid[0][:50]}"
            )
        if dd_entries:
            _, ref_errs = validate_evidence_entries(
                dd_entries, valid_files, line_bounds, dive_file.name
            )
            dd_errors.extend(ref_errs)
        if dd_errors:
            print("deepdive 校验失败：")
            for e in dd_errors:
                print(f"  - {e}")
            return 1
        if dd_entries:
            print(f"deepdive 校验通过：{len(dd_entries)} 条证据条目")

    return 0


def cmd_bkp(args) -> int:
    """BKP Finalize：校验 bkp_prototype 并封装正式 BKP 到 bkp/。"""
    out_dir = Path(args.output)
    proto_dir = Path(args.prototype) if getattr(args, "prototype", None) else None
    report = finalize_bkp(out_dir, proto_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="book_distill",
        description="BookDistill v0.2 — 原著蒸馏纪律工作台（validate/prepare/assemble/profile/deepdive/bkp）。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_v = sub.add_parser("validate", help="校验 SourcePrepare PASS 输入包")
    p_v.add_argument("--input", required=True, help="SourcePrepare 输出目录，如 06_工作区/SourcePrepare/book_0038_一九八四")

    p_p = sub.add_parser("prepare", help="生成章节索引与证据模板")
    p_p.add_argument("--input", required=True, help="SourcePrepare 输出目录")
    p_p.add_argument("--output", required=True, help="BookDistill 输出目录，如 02_原著蒸馏/book_0038_一九八四")

    p_a = sub.add_parser("assemble", help="校验证据并生成清单与报告骨架")
    p_a.add_argument("--input", required=True, help="SourcePrepare 输出目录（用于校验 source snapshot 与行号越界）")
    p_a.add_argument("--output", required=True, help="BookDistill 输出目录")

    p_pr = sub.add_parser("profile", help="基于 Base Scan 生成 BookProfile")
    p_pr.add_argument("--output", required=True, help="BookDistill 输出目录")

    p_d = sub.add_parser("deepdive", help="生成专项深挖模板")
    p_d.add_argument("--output", required=True, help="BookDistill 输出目录")
    p_d.add_argument("--dimension", required=True, help="深挖维度名")
    p_d.add_argument("--topic", default=None, help="深挖主题描述（可选，默认同 dimension）")
    p_d.add_argument("--input", default=None, help="SourcePrepare 输出目录（可选，用于校验引用与行号）")

    p_b = sub.add_parser("bkp", help="BKP Finalize（校验原型并封装正式 BKP）")
    p_b.add_argument("--output", required=True, help="BookDistill 输出目录")
    p_b.add_argument(
        "--prototype",
        default=None,
        help="BKP 原型目录（可选；默认 <output>/bkp_prototype）",
    )

    args = parser.parse_args(argv)
    if args.command == "validate":
        return cmd_validate(args)
    if args.command == "prepare":
        return cmd_prepare(args)
    if args.command == "assemble":
        return cmd_assemble(args)
    if args.command == "profile":
        return cmd_profile(args)
    if args.command == "deepdive":
        return cmd_deepdive(args)
    if args.command == "bkp":
        return cmd_bkp(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
