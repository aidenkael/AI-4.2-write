#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BookDistill v0.1 — 最小原著蒸馏纪律工作台。

职责（只做机械纪律，不做语言分析）：
  1. validate  —— 校验 SourcePrepare PASS 输入包完整性与一致性；
  2. prepare   —— 生成章节索引与每章证据模板（evidence-first 底稿）；
  3. assemble  —— 校验证据记录的分类合法性与可追溯引用，汇总清单与报告骨架。

蒸馏分析内容由运行本 Skill 的 Agent / 作者在证据模板中填写：
  FACT（原文事实）/ INFERENCE（推断）/ MECHANISM（可迁移机制）/ BOUNDARY（边界与不确定性）。
本脚本不调用大模型，不修改 SourcePrepare 输出，不读取 01_原始素材。

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
import hashlib
import json
import re
import sys
from pathlib import Path

# ---- 常量 ---------------------------------------------------------------

SP_STATUS_PASS = "PASS"
SP_EXPECTED_VERSION = "0.2.1"
BD_VERSION = "0.1.1"

# 证据记录允许的分类（evidence-first 分层）
EVIDENCE_KINDS = ("FACT", "INFERENCE", "MECHANISM", "BOUNDARY")
# 章节文件前缀（0000_前置内容.md 为卷首非章节内容，不参与正文蒸馏）
CHAPTER_PREFIX = "chapters"
PREAMBLE_GLOB = "0000_*.md"

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
        "分类定义：",
        "- **FACT**：原文可直接支持的事实（引用必须落在原文行范围内）。",
        "- **INFERENCE**：由原文推断的含义，不直接出现在字面。",
        "- **MECHANISM**：可迁移的写作机制/技法（需说明为何可迁移，不能是剧情换皮）。",
        "- **BOUNDARY**：本条的边界/不确定性/反证（如译本影响、样本局限）。",
        "",
        "## FACT（原文事实）",
        "",
        "## INFERENCE（推断）",
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
                f"{evf.name}: 存在非法分类条目（允许 FACT/INFERENCE/MECHANISM/BOUNDARY）: "
                f"{invalid_lines[0][:50]}"
            )
            continue
        if not entries:
            warnings.append(f"{evf.name}: 无证据条目（该章未分析，覆盖缺口）。")
            continue
        per_file[evf.name] = len(entries)
        for kind, line in entries:
            stats[kind] += 1
            ref = extract_ref_from_line(line)
            if not ref:
                errors.append(f"{evf.name}: 条目缺少'证据：'引用 -> {line[:60]}")
                continue
            ok, msg = validate_ref(ref, valid_files, line_bounds)
            if not ok:
                errors.append(f"{evf.name}: {msg} -> {line[:80]}")

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

    # manifest
    manifest = {
        "skill": "BookDistill",
        "version": BD_VERSION,
        "source_snapshot": current_snapshot,
        "evidence_files": [f.name for f in ev_files],
        "entries_per_file": per_file,
        "stats_by_kind": stats,
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="book_distill",
        description="BookDistill v0.1 — 最小原著蒸馏纪律工作台（validate/prepare/assemble）。",
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

    args = parser.parse_args(argv)
    if args.command == "validate":
        return cmd_validate(args)
    if args.command == "prepare":
        return cmd_prepare(args)
    if args.command == "assemble":
        return cmd_assemble(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
