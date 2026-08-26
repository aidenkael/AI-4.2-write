#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MethodPrepare —— METHOD_SOURCE 素材的确定性预处理（无模型、无重写、无 OCR）。

与 SourcePrepare 平行的独立 Skill：不把 SourcePrepare 改造成多用途分支解析器，
也不改变 SourcePrepare 的生产行为与输出合同。

输入（只读）：
  素材资产.json（canonical ledger）中 type == METHOD_SOURCE 的资产；
  来源文件保持只读，绝不修改。

输出：
  06_工作区/MethodPrepare/<asset_id>_<名称>/
  ├─ full.md                 归一化全文（保持原文档顺序）
  ├─ sections/               行稳定、可证据寻址的分节文件
  │  ├─ S0001.md ...
  ├─ structure.json          稳定节 id / 顺序 / 父级（仅在真实已知时）
  ├─ metadata.json           资产身份 / SHA / 指纹 / 解析器身份 / 状态 / 限制
  └─ conversion_report.md    人类可读报告

合同：
  - 只做确定性准备：无 LLM、无语义摘要、无改写、无 OCR；
  - 保留文档顺序；在可靠可得时保留标题层级、列表、编号步骤、表格、引用、示例；
  - 绝不虚构标题层级：无法可靠恢复结构时保留线性内容并在
    metadata/报告中标注限制；限制重大时用 REVIEW，不用假 PASS；
  - sections/S####.md 行号稳定，下游证据可用 sections/S0001.md#Lx-Ly；
  - 确定性：同输入重复执行产物逐字节一致（无时间戳、排序确定）。

解析器隔离：convert_to_markdown / extract_structure 是独立函数，
未来可加 Docling 适配器而不改本 Skill 的输出合同。

用法：
  python method_prepare.py --root E:/AI-Write --asset book_0138
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "MaterialIntake"))
import catalog  # noqa: E402  MaterialIntake canonical ledger（只读消费）

SKILL_VERSION = "method_prepare/v1"
OUTPUT_ROOT_REL = Path("06_工作区") / "MethodPrepare"
MIN_VISIBLE_CHARS = 200
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")

# 可直接确定性转换的扩展名（其余 → REVIEW，绝不假 PASS）
SUPPORTED_EXTS = {".md", ".markdown", ".txt", ".epub", ".pdf"}


class MethodPrepareError(Exception):
    pass


# --------------------------------------------------------------------------- #
# 确定性工具
# --------------------------------------------------------------------------- #

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_name(name: str) -> str:
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", name).strip().strip(".")
    return (s or "未命名")[:80]


def visible_char_count(text: str) -> int:
    return len(re.sub(r"\s", "", text))


def find_pandoc(root: Path) -> str | None:
    exe = shutil.which("pandoc")
    if exe:
        return exe
    local = root / "05_Skills与自动化" / "pandoc" / ("pandoc.exe" if os.name == "nt" else "pandoc")
    return str(local) if local.is_file() else None


def decode_text(path: Path) -> tuple[str | None, str | None]:
    """确定性多编码尝试（与仓库现有文本层解码习惯一致）；无法解码 → (None, None)。"""
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030", "big5"):
        try:
            text = raw.decode(enc)
            if "\x00" not in text[:5000]:
                return text, enc
        except UnicodeDecodeError:
            continue
    return None, None


def normalize_text(text: str) -> str:
    """归一化换行与行尾空白；保留原文档顺序，不做任何内容改写。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n" if lines else ""


# --------------------------------------------------------------------------- #
# 转换器（隔离层：未来可加 Docling 适配器而不改输出合同）
# --------------------------------------------------------------------------- #

def convert_markdown_like(path: Path, converter_note: str) -> tuple[str, str, list[str]]:
    """md/txt：解码 + 归一化。返回 (text, converter_id, limitations)。"""
    text, enc = decode_text(path)
    if text is None:
        raise MethodPrepareError(f"文本编码无法可靠识别：{path.name}")
    return normalize_text(text), f"{converter_note}:encoding={enc}", []


def convert_epub(path: Path, pandoc: str | None) -> tuple[str, str, list[str]]:
    if not pandoc:
        raise MethodPrepareError("未找到 Pandoc，无法转换 EPUB")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "full.md"
        proc = subprocess.run(
            [pandoc, str(path), "-f", "epub", "-t", "gfm", "--wrap=none", "-o", str(out)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30 * 60,
        )
        if proc.returncode != 0 or not out.exists():
            raise MethodPrepareError(f"Pandoc EPUB→Markdown 失败：{(proc.stderr or '')[:300]}")
        text = out.read_text(encoding="utf-8", errors="replace")
    return normalize_text(text), "epub:pandoc-gfm", []


def convert_pdf(path: Path) -> tuple[str, str, list[str]]:
    """只取文本层；无文本层 → 抛错（由调用方转 REVIEW，绝不 OCR）。"""
    text, engine = None, ""
    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(str(path))
        text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
        engine = "pdf:pypdf"
    except Exception:  # noqa: BLE001 — pypdf 不可用/损坏 → 尝试 pdftotext
        text = None
    if not text:
        exe = shutil.which("pdftotext")
        if exe:
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / "out.txt"
                proc = subprocess.run([exe, "-layout", str(path), str(out)],
                                      capture_output=True, text=True)
                if proc.returncode == 0 and out.exists():
                    text = out.read_text(encoding="utf-8", errors="replace")
                    engine = "pdf:pdftotext"
    if not (text or "").strip():
        raise MethodPrepareError("PDF 无可用文本层（不做 OCR），需人工确认")
    return normalize_text(text or ""), engine, [
        "PDF 文本层提取不保留原文档视觉结构；标题层级仅按转换后 Markdown 判定"
    ]


def convert_to_markdown(path: Path, root: Path) -> tuple[str, str, list[str]]:
    """分派层。返回 (归一化全文, 解析器身份, 限制列表)；不可转换抛 MethodPrepareError。"""
    ext = path.suffix.lower()
    if ext in (".md", ".markdown"):
        return convert_markdown_like(path, "md:passthrough")
    if ext == ".txt":
        return convert_markdown_like(path, "txt")
    if ext == ".epub":
        return convert_epub(path, find_pandoc(root))
    if ext == ".pdf":
        return convert_pdf(path)
    raise MethodPrepareError(f"{ext or '无后缀'} 暂不支持确定性转换，需人工确认")


# --------------------------------------------------------------------------- #
# 结构提取（绝不虚构层级：只记录真实可见的 ATX 标题）
# --------------------------------------------------------------------------- #

def extract_structure(text: str) -> tuple[dict, list[str]]:
    """按 ATX 标题切分节。

    无标题 → 单个线性节（heading_structure_known=false，限制 linear_no_heading）。
    返回 (structure, limitations)；structure 内 parent 仅在真实层级关系成立时给出。
    """
    lines = text.split("\n")
    sections: list[dict] = []
    limitations: list[str] = []
    headings: list[tuple[int, int, int, str]] = []  # (line_no, level, sec_index, title)

    current_title = "（卷首）"
    current_level = 0
    current_lines: list[str] = []
    current_start = 1

    def flush(sec_index: int) -> None:
        if not current_lines and sec_index == 0:
            return
        sections.append({
            "id": f"S{sec_index + 1:04d}",
            "file": f"sections/S{sec_index + 1:04d}.md",
            "title": current_title,
            "level": current_level,
            "order": sec_index + 1,
            "start_line": current_start,
            "line_count": len(current_lines),
            "_lines": list(current_lines),
        })

    for i, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if m:
            flush(len(sections))
            current_title = m.group(2).strip()
            current_level = len(m.group(1))
            current_lines = [line]
            current_start = i + 1
            headings.append((i + 1, current_level, len(sections), current_title))
        else:
            current_lines.append(line)
    flush(len(sections))

    if not headings:
        limitations.append("linear_no_heading")

    # parent：最近的前置更低级别标题（仅在真实已知时）
    stack: list[tuple[int, str]] = []
    for sec in sections:
        lvl = sec["level"]
        while stack and stack[-1][0] >= lvl:
            stack.pop()
        sec["parent"] = stack[-1][1] if (stack and lvl > 0) else None
        if lvl > 0:
            stack.append((lvl, sec["id"]))
        del sec["_lines"]

    structure = {
        "heading_structure_known": bool(headings),
        "section_count": len(sections),
        "sections": sections,
    }
    return structure, limitations


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #

def _select_source(asset: dict) -> dict | None:
    """选源：优先 primary 且受支持；否则按确定性排序取第一个受支持文件。"""
    files = list(asset.get("files") or [])
    supported = [f for f in files if Path(f["path"]).suffix.lower() in SUPPORTED_EXTS]
    if not supported:
        return None
    supported.sort(key=lambda f: (not f.get("primary"), f["path"]))
    return supported[0]


def prepare_asset(root: Path, asset_id: str) -> dict:
    """对单个 METHOD_SOURCE 资产运行确定性预处理。返回 result dict。"""
    mat_dir = root / catalog.MATERIAL_DIR_NAME
    ledger = catalog.load_ledger(mat_dir / catalog.LEDGER_FILENAME)
    asset = next((a for a in ledger["assets"] if a["id"] == asset_id), None)
    if asset is None:
        raise MethodPrepareError(f"素材不存在：{asset_id}")
    if asset["type"] != "METHOD_SOURCE":
        raise MethodPrepareError(
            f"素材 {asset_id} 类型 {asset['type']} 不适用 MethodPrepare"
            "（仅 METHOD_SOURCE 走方法提纯；参考作品请用 SourcePrepare）")

    out_dir = root / OUTPUT_ROOT_REL / f"{asset_id}_{safe_name(asset.get('name') or '')}"
    limitations: list[str] = []
    status = "PASS"
    parser_id = ""
    section_count = 0
    full_text = ""
    selected = _select_source(asset)
    file_shas = {f["sha256"] for f in asset.get("files") or []}

    if selected is None:
        status = "REVIEW"
        limitations.append("no_supported_source: 无 .md/.txt/.epub/.pdf 来源，需人工确认格式")
    else:
        src_path = root / catalog.MATERIAL_DIR_NAME / selected["path"]
        if not src_path.is_file():
            raise MethodPrepareError(f"登记来源文件缺失：{selected['path']}")
        sha = sha256_file(src_path)
        if sha != selected.get("sha256"):
            raise MethodPrepareError(
                f"来源文件 SHA256 与台账不一致（{selected['path']}），请先刷新素材状态")
        try:
            full_text, parser_id, conv_limits = convert_to_markdown(src_path, root)
            limitations.extend(conv_limits)
        except MethodPrepareError as exc:
            status = "REVIEW"
            limitations.append(f"conversion_unavailable: {exc}")
        except Exception as exc:  # noqa: BLE001 — 转换异常一律不假 PASS
            status = "REVIEW"
            limitations.append(f"conversion_error: {exc}")

    structure = {"heading_structure_known": False, "section_count": 0, "sections": []}
    if status == "PASS":
        if visible_char_count(full_text) < MIN_VISIBLE_CHARS:
            status = "REVIEW"
            limitations.append("too_few_visible_chars: 可见内容过少，无法可靠蒸馏")
        if full_text.count("\ufffd") > 50:
            status = "REVIEW"
            limitations.append("garbled_content: 大量替换字符，疑似编码损坏")
    if status == "PASS":
        structure, struct_limits = extract_structure(full_text)
        limitations.extend(struct_limits)
        if "linear_no_heading" in struct_limits:
            # 无法可靠恢复结构：保留线性内容、标注限制、用 REVIEW（绝不虚构层级）
            status = "REVIEW"
        section_count = structure["section_count"]

    # --- 写产物（确定性：覆盖式写入，无时间戳） ---
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sections").mkdir(exist_ok=True)
    # 清理旧 sections，保证重复运行逐字节一致
    for old in (out_dir / "sections").glob("S*.md"):
        old.unlink()

    (out_dir / "full.md").write_text(full_text, encoding="utf-8", newline="\n")
    for sec in structure["sections"]:
        sec_lines = _section_lines(full_text, sec)
        (out_dir / sec["file"]).write_text(
            "\n".join(sec_lines) + ("\n" if sec_lines else ""), encoding="utf-8", newline="\n")

    clean_sections = [
        {k: v for k, v in sec.items()} for sec in structure["sections"]
    ]
    structure_out = {
        "heading_structure_known": structure["heading_structure_known"],
        "section_count": structure["section_count"],
        "sections": clean_sections,
    }
    structure_json = json.dumps(structure_out, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    (out_dir / "structure.json").write_text(structure_json, encoding="utf-8", newline="\n")

    input_fingerprint = catalog.content_fingerprint(asset.get("files") or [])
    metadata = {
        "skill_version": SKILL_VERSION,
        "asset_id": asset_id,
        "asset_name": asset.get("name") or "",
        "type": "METHOD_SOURCE",
        "status": status,
        "selected_source": (
            {
                "path": selected["path"],
                "format": Path(selected["path"]).suffix.lower(),
                "sha256": selected["sha256"],
                "char_count": visible_char_count(full_text),
            } if selected is not None else None
        ),
        "input_fingerprint": input_fingerprint,
        "content_fingerprint": sha256_text(full_text),
        "structure_fingerprint": sha256_text(structure_json),
        "parser": parser_id or "none",
        "section_count": section_count,
        "limitations": sorted(set(limitations)),
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8", newline="\n")

    (out_dir / "conversion_report.md").write_text(_render_report(metadata, structure_out),
                                                   encoding="utf-8", newline="\n")
    return {"asset_id": asset_id, "status": status, "output_dir": str(out_dir),
            "section_count": section_count, "limitations": metadata["limitations"]}


def _section_lines(full_text: str, sec: dict) -> list[str]:
    lines = full_text.split("\n")
    start = sec["start_line"] - 1
    return lines[start:start + sec["line_count"]]


def _render_report(metadata: dict, structure: dict) -> str:
    m = metadata
    sel = m.get("selected_source") or {}
    lines = [
        f"# MethodPrepare 转换报告：{m['asset_name']}",
        "",
        f"- 素材：`{m['asset_id']}`（METHOD_SOURCE）",
        f"- 状态：**{m['status']}**",
        f"- 选中来源：{sel.get('path') or '（无受支持来源）'}（sha256={(sel.get('sha256') or '')[:16]}…）",
        f"- 解析器：{m['parser']}",
        f"- 分节数：{m['section_count']}（标题结构可靠：{'是' if structure['heading_structure_known'] else '否'}）",
        f"- 内容指纹：{m['content_fingerprint'][:16]}…",
        "",
        "## 限制与不确定性",
        "",
    ]
    if m["limitations"]:
        lines.extend(f"- {lim}" for lim in m["limitations"])
    else:
        lines.append("- 无")
    lines += [
        "",
        "## 产物",
        "",
        "- `full.md`：归一化全文（保持原文档顺序）",
        "- `sections/`：行稳定分节（证据寻址 `sections/S0001.md#Lx-Ly`）",
        "- `structure.json`：稳定节 id / 顺序 / 父级（仅真实已知）",
        "- `metadata.json`：身份 / 指纹 / 状态",
    ]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="MethodPrepare 方法素材确定性预处理")
    ap.add_argument("--root", default=os.getcwd(), help="仓库根目录")
    ap.add_argument("--asset", required=True, help="canonical 素材资产 id（book_XXXX）")
    args = ap.parse_args(argv)
    try:
        result = prepare_asset(Path(args.root).resolve(), args.asset)
    except (MethodPrepareError, FileNotFoundError, RuntimeError) as exc:
        print(f"[method_prepare] ERROR: {exc}")
        return 2
    print(f"[method_prepare] {result['status']} {result['asset_id']}: "
          f"sections={result['section_count']} → {result['output_dir']}")
    for lim in result["limitations"]:
        print(f"[method_prepare] limitation: {lim}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
