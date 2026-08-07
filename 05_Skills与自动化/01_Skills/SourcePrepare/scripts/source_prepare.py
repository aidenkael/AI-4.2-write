from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional
import xml.etree.ElementTree as ET

SKILL_VERSION = "0.1.0"
SUPPORTED = {".epub", ".txt", ".pdf"}
SOURCE_PRIORITY = {".epub": 0, ".txt": 1, ".pdf": 2}

CHAPTER_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:"
    r"第[\d一二三四五六七八九十百千万零〇两]+[章回节卷部篇集](?:[：:\s　].*)?"
    r"|[卷部篇集][\d一二三四五六七八九十百千万零〇两]+(?:[：:\s　].*)?"
    r"|(?:序章|楔子|引子|前言|序言|尾声|终章|后记|跋|番外(?:篇)?)(?:[：:\s　].*)?"
    r")\s*$"
)
NUMERIC_HEADING_RE = re.compile(r"^\s*#{1,6}\s*(?:Chapter\s+)?(?:\d{1,4}|[IVXLCDM]{1,8})[.、:]?\s*$", re.I)
MD_HEADING_RE = re.compile(r"^\s*#{1,6}\s+\S+")


@dataclass
class Candidate:
    path: str
    ext: str
    sha256: str
    status: str = "FAIL"
    char_count: int = 0
    chapter_count: int = 0
    warnings: list[str] | None = None
    notes: list[str] | None = None
    temp_md: Optional[str] = None

    def __post_init__(self) -> None:
        self.warnings = self.warnings or []
        self.notes = self.notes or []


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_pandoc(root: Path) -> Optional[str]:
    exe = shutil.which("pandoc")
    if exe:
        return exe
    local = root / "05_Skills与自动化" / "pandoc" / ("pandoc.exe" if os.name == "nt" else "pandoc")
    return str(local) if local.exists() else None


def clean_markdown(text: str) -> str:
    text = text.replace("\ufeff", "")
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?m)^\s*!\[[^\]]*\]\([^)]+\)\s*$", "", text)
    text = re.sub(r"(?i)</?(?:div|span|section|article)(?:\s+[^>]*)?>", "", text)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip() + "\n"


def visible_char_count(text: str) -> int:
    plain = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    plain = re.sub(r"\[[^\]]+\]\([^)]+\)", "", plain)
    plain = re.sub(r"[#>*_`~\-\s]", "", plain)
    return len(plain)


def chapter_starts(lines: list[str]) -> list[int]:
    strong = [i for i, line in enumerate(lines) if CHAPTER_RE.match(line)]
    if len(strong) >= 3:
        return strong
    numeric = [i for i, line in enumerate(lines) if NUMERIC_HEADING_RE.match(line)]
    combined = sorted(set(strong + numeric))
    if len(combined) >= 3:
        return combined
    headings = [i for i, line in enumerate(lines) if MD_HEADING_RE.match(line)]
    return headings if len(headings) >= 3 else []


def split_chapters(text: str, out_dir: Path) -> int:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = text.splitlines()
    starts = chapter_starts(lines)
    if not starts:
        return 0
    boundaries = starts + [len(lines)]
    if starts[0] > 0 and any(x.strip() for x in lines[: starts[0]]):
        pre = "\n".join(lines[: starts[0]]).strip()
        if pre:
            (out_dir / "0000_前置内容.md").write_text(pre + "\n", encoding="utf-8")
    count = 0
    for n, (start, end) in enumerate(zip(boundaries[:-1], boundaries[1:]), start=1):
        block = "\n".join(lines[start:end]).strip()
        if block:
            (out_dir / f"{n:04d}.md").write_text(block + "\n", encoding="utf-8")
            count += 1
    return count


def validate_epub_structure(path: Path) -> tuple[bool, list[str], list[str]]:
    warnings: list[str] = []
    notes: list[str] = []
    try:
        if not zipfile.is_zipfile(path):
            return False, ["不是有效 ZIP/EPUB 容器"], notes
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            if "META-INF/container.xml" not in names:
                return False, ["缺少 META-INF/container.xml"], notes
            try:
                container = ET.fromstring(z.read("META-INF/container.xml"))
                rootfile = None
                for elem in container.iter():
                    if elem.tag.endswith("rootfile"):
                        rootfile = elem.attrib.get("full-path")
                        if rootfile:
                            break
                if not rootfile or rootfile not in names:
                    return False, ["container.xml 未指向有效 OPF"], notes
                opf = ET.fromstring(z.read(rootfile))
                manifest: dict[str, str] = {}
                spine_ids: list[str] = []
                for elem in opf.iter():
                    if elem.tag.endswith("item"):
                        item_id, href = elem.attrib.get("id"), elem.attrib.get("href")
                        if item_id and href:
                            manifest[item_id] = href
                    elif elem.tag.endswith("itemref"):
                        rid = elem.attrib.get("idref")
                        if rid:
                            spine_ids.append(rid)
                if not spine_ids:
                    return False, ["OPF spine 为空"], notes
                base = Path(rootfile).parent
                existing = 0
                for rid in spine_ids:
                    href = manifest.get(rid)
                    if href and (base / href).as_posix() in names:
                        existing += 1
                ratio = existing / max(1, len(spine_ids))
                notes.append(f"spine 条目 {len(spine_ids)}，可定位正文 {existing}")
                if ratio < 0.8:
                    warnings.append(f"仅 {ratio:.0%} 的 spine 项可定位，结构可疑")
                return True, warnings, notes
            except ET.ParseError as e:
                return False, [f"EPUB XML 解析失败：{e}"], notes
    except Exception as e:
        return False, [f"EPUB 结构检查异常：{e}"], notes


def assess_candidate(cand: Candidate, text: str) -> None:
    fatal = False
    if cand.char_count < 5000:
        cand.warnings.append(f"正文字符数过少：{cand.char_count}")
        fatal = True
    bad = text.count("\ufffd")
    if bad > 10:
        cand.warnings.append(f"出现 {bad} 个替换字符 �，疑似乱码")
    if cand.chapter_count == 0:
        cand.warnings.append("未可靠识别章节边界")
    if fatal:
        cand.status = "FAIL"
    elif bad > 10 or cand.chapter_count == 0:
        cand.status = "REVIEW"
    else:
        cand.status = "PASS"


def convert_epub(path: Path, pandoc: str, work_dir: Path) -> Candidate:
    cand = Candidate(str(path), ".epub", sha256_file(path))
    ok, warns, notes = validate_epub_structure(path)
    cand.warnings.extend(warns)
    cand.notes.extend(notes)
    if not ok:
        return cand
    out = work_dir / f"{cand.sha256[:12]}.epub.md"
    proc = subprocess.run(
        [pandoc, str(path), "-f", "epub", "-t", "gfm", "--wrap=none", "-o", str(out)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0 or not out.exists():
        cand.warnings.append("Pandoc EPUB→Markdown 失败")
        if proc.stderr:
            cand.notes.append(proc.stderr[-2000:])
        return cand
    text = clean_markdown(out.read_text(encoding="utf-8", errors="replace"))
    out.write_text(text, encoding="utf-8")
    cand.temp_md = str(out)
    cand.char_count = visible_char_count(text)
    cand.chapter_count = len(chapter_starts(text.splitlines()))
    assess_candidate(cand, text)
    return cand


def decode_txt(path: Path) -> tuple[Optional[str], Optional[str]]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030", "big5"):
        try:
            text = raw.decode(enc)
            if "\x00" not in text[:5000]:
                return text, enc
        except UnicodeDecodeError:
            pass
    return None, None


def convert_txt(path: Path, work_dir: Path) -> Candidate:
    cand = Candidate(str(path), ".txt", sha256_file(path))
    text, enc = decode_txt(path)
    if text is None:
        cand.warnings.append("TXT 编码无法可靠识别")
        return cand
    cand.notes.append(f"TXT 解码：{enc}")
    text = clean_markdown(text)
    out = work_dir / f"{cand.sha256[:12]}.txt.md"
    out.write_text(text, encoding="utf-8")
    cand.temp_md = str(out)
    cand.char_count = visible_char_count(text)
    cand.chapter_count = len(chapter_starts(text.splitlines()))
    assess_candidate(cand, text)
    return cand


def pdf_to_text(path: Path) -> tuple[Optional[str], str]:
    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(str(path))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages), "pypdf"
    except Exception:
        pass
    exe = shutil.which("pdftotext")
    if exe:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.txt"
            proc = subprocess.run([exe, "-layout", str(path), str(out)], capture_output=True, text=True)
            if proc.returncode == 0 and out.exists():
                return out.read_text(encoding="utf-8", errors="replace"), "pdftotext"
    return None, ""


def convert_pdf(path: Path, work_dir: Path) -> Candidate:
    cand = Candidate(str(path), ".pdf", sha256_file(path))
    text, engine = pdf_to_text(path)
    if not text:
        cand.warnings.append("PDF 无可用文本层，或缺少 pypdf/pdftotext；不自动 OCR")
        return cand
    cand.notes.append(f"PDF 文本提取：{engine}")
    text = clean_markdown(text)
    out = work_dir / f"{cand.sha256[:12]}.pdf.md"
    out.write_text(text, encoding="utf-8")
    cand.temp_md = str(out)
    cand.char_count = visible_char_count(text)
    cand.chapter_count = len(chapter_starts(text.splitlines()))
    assess_candidate(cand, text)
    return cand


def choose_candidate(cands: list[Candidate]) -> tuple[Optional[Candidate], list[str]]:
    warnings: list[str] = []
    usable = [c for c in cands if c.status in {"PASS", "REVIEW"} and c.temp_md]
    if not usable:
        return None, warnings
    usable.sort(key=lambda c: (0 if c.status == "PASS" else 1, SOURCE_PRIORITY.get(c.ext, 9), -c.char_count))
    selected = usable[0]
    for peer in [c for c in usable if c is not selected and c.char_count > 0]:
        ratio = min(selected.char_count, peer.char_count) / max(selected.char_count, peer.char_count)
        if ratio < 0.65:
            warnings.append(
                f"来源长度差异较大：{Path(selected.path).name}={selected.char_count}，"
                f"{Path(peer.path).name}={peer.char_count}，较短/较长={ratio:.0%}"
            )
    return selected, warnings


def book_dirs(root: Path) -> Iterable[tuple[str, Path]]:
    for rel in ("01_原始素材/01_网络小说", "01_原始素材/02_世界文学"):
        base = root / rel
        if base.exists():
            for p in sorted(base.iterdir()):
                if p.is_dir():
                    yield Path(rel).name, p


def locate_books(root: Path, name: Optional[str], all_books: bool) -> list[tuple[str, Path]]:
    items = list(book_dirs(root))
    if all_books:
        return items
    if not name:
        raise SystemExit("必须指定 --book <作品名> 或 --all")
    exact = [(cat, p) for cat, p in items if p.name == name]
    if exact:
        return exact
    partial = [(cat, p) for cat, p in items if name.lower() in p.name.lower()]
    if len(partial) == 1:
        return partial
    if not partial:
        raise SystemExit(f"未找到作品：{name}")
    raise SystemExit("作品名匹配多个目录：" + ", ".join(p.name for _, p in partial))


def report_markdown(book: str, category: str, cands: list[Candidate], selected: Optional[Candidate], overall: str, warnings: list[str], pandoc: Optional[str]) -> str:
    lines = [
        f"# SourcePrepare 转换报告：{book}", "",
        f"- Skill 版本：{SKILL_VERSION}",
        f"- 分类：{category}",
        f"- Pandoc：{pandoc or '未找到'}",
        f"- 最终状态：**{overall}**",
        f"- 选中来源：`{Path(selected.path).name}`" if selected else "- 选中来源：无",
        "", "## 来源评估", "",
        "| 文件 | 格式 | 状态 | 正文字符 | 章节边界 |",
        "|---|---:|---:|---:|---:|",
    ]
    for c in cands:
        lines.append(f"| `{Path(c.path).name}` | {c.ext} | {c.status} | {c.char_count} | {c.chapter_count} |")
    if warnings:
        lines += ["", "## 需要注意", ""] + [f"- {w}" for w in warnings]
    lines += ["", "## 单文件备注", ""]
    for c in cands:
        lines.append(f"### {Path(c.path).name}")
        items = (c.notes or []) + [f"⚠ {w}" for w in (c.warnings or [])]
        if items:
            lines.extend(f"- {x}" for x in items)
        else:
            lines.append("- 无")
        lines.append("")
    lines += [
        "## 使用规则", "",
        "- `PASS`：可进入后续 BookDistill。",
        "- `REVIEW`：需要人工检查后再进入 BookDistill。",
        "- `FAIL`：不得进入 BookDistill，应使用备用来源或人工处理。",
        "- 本流程不修改、不覆盖 `01_原始素材` 中任何文件。",
        "- PDF 无文本层时不自动 OCR。", "",
    ]
    return "\n".join(lines)


def process_book(root: Path, category: str, book_dir: Path, pandoc: Optional[str], force: bool) -> str:
    source_dir = book_dir / "00_原始文件"
    if not source_dir.exists():
        source_dir = book_dir
    paths = [p for p in source_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED]
    out_dir = root / "06_工作区" / "02_格式转换" / category / book_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)
    full_md = out_dir / "full.md"
    chapters_dir = out_dir / "chapters"
    report = out_dir / "conversion_report.md"
    meta = out_dir / "metadata.json"
    if full_md.exists() and not force:
        return f"SKIP {book_dir.name}: 已存在 full.md（使用 --force 重跑）"

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        cands: list[Candidate] = []
        for p in sorted(paths):
            ext = p.suffix.lower()
            if ext == ".epub":
                if pandoc:
                    cands.append(convert_epub(p, pandoc, work))
                else:
                    c = Candidate(str(p), ext, sha256_file(p))
                    c.warnings.append("未找到 Pandoc，无法转换 EPUB")
                    cands.append(c)
            elif ext == ".txt":
                cands.append(convert_txt(p, work))
            elif ext == ".pdf":
                cands.append(convert_pdf(p, work))

        selected, cross_warnings = choose_candidate(cands)
        if not selected:
            overall = "FAIL"
            report.write_text(report_markdown(book_dir.name, category, cands, None, overall, cross_warnings, pandoc), encoding="utf-8")
            meta.write_text(json.dumps({
                "skill_version": SKILL_VERSION,
                "book": book_dir.name,
                "category": category,
                "status": overall,
                "selected_source": None,
                "candidates": [{**asdict(c), "temp_md": None} for c in cands],
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            return f"FAIL {book_dir.name}"

        text = Path(selected.temp_md).read_text(encoding="utf-8")
        full_md.write_text(text, encoding="utf-8")
        split_count = split_chapters(text, chapters_dir)
        overall = selected.status
        if cross_warnings or split_count == 0:
            overall = "REVIEW"
        if split_count == 0:
            cross_warnings.append("未生成 chapters/ 分章文件；full.md 已保留")

        report.write_text(report_markdown(book_dir.name, category, cands, selected, overall, cross_warnings, pandoc), encoding="utf-8")
        meta.write_text(json.dumps({
            "skill_version": SKILL_VERSION,
            "book": book_dir.name,
            "category": category,
            "status": overall,
            "selected_source": {
                "path": selected.path,
                "format": selected.ext,
                "sha256": selected.sha256,
                "char_count": selected.char_count,
            },
            "chapter_files": split_count,
            "cross_source_warnings": cross_warnings,
            "candidates": [{**asdict(c), "temp_md": None} for c in cands],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return f"{overall} {book_dir.name}: {Path(selected.path).name}, chapters={split_count}"


def main() -> int:
    ap = argparse.ArgumentParser(description="AI-Wirte SourcePrepare: 原著源文件标准化为纯净 Markdown")
    ap.add_argument("--root", required=True, help=r"项目根目录，例如 D:\BaiduSyncdisk\AI-Wirte")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--book", help="处理单部作品；支持唯一部分匹配")
    group.add_argument("--all", action="store_true", help="处理全部作品（建议先单书试跑）")
    ap.add_argument("--force", action="store_true", help="覆盖工作区已有转换结果；绝不覆盖原始素材")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not (root / "01_原始素材").exists():
        raise SystemExit("项目根目录不正确：缺少 01_原始素材")
    pandoc = find_pandoc(root)
    results = [process_book(root, category, book, pandoc, args.force) for category, book in locate_books(root, args.book, args.all)]
    for result in results:
        print(result)
    return 0 if all(not r.startswith("FAIL") for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
