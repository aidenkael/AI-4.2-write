# -*- coding: utf-8 -*-
"""
source_prepare.py — AI-Write 原著源文件标准化（SourcePrepare / SP）

设计目标：
- 把 01_原始素材 中的第三方原著，**只读**标准化为可供后续 BookDistill 使用的
  纯净 Markdown 工作副本。SP 只做“输入标准化”，不分析、不蒸馏、不改写正文。
- 直接扫描作品目录根层（不再依赖 00_原始文件 嵌套子目录）。
- 支持 6 大分类；05_现代专业资料 为非书籍类专业资料，标记 NOT_APPLICABLE，不转换。
- 来源选择优先级：完整性 > 准确性 > 章节 > 格式（不再“EPUB 永远最好”；
  单 EPUB 只要通过质检即可 PASS）。
- EPUB 跑 14 项质量检测（结构 + 转换 + 正文质量）。
- 每跑完一部作品，自动回写中央索引（素材清单.csv / 素材总索引.md）。

输出位置：
  06_工作区/SourcePrepare/<作品ID>_<作品>/
      ├─ full.md
      ├─ chapters/
      ├─ metadata.json
      └─ conversion_report.md

注意：01_原始素材 与 06_工作区 均 Local Only（不上 GitHub）。
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
import unicodedata
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional
import xml.etree.ElementTree as ET

# 同目录下的索引工具：SP 跑完一本书后回写中央索引
sys.path.insert(0, str(Path(__file__).resolve().parent))
import index_builder  # noqa: E402

SKILL_VERSION = "0.2.1"
RAW = "01_原始素材"
SUPPORTED = {".epub", ".txt", ".pdf", ".zip", ".azw3", ".mobi"}
SOURCE_PRIORITY = {".epub": 0, ".txt": 1, ".pdf": 2}

# 6 大分类（目录名），与 index_builder.CATEGORY_LABEL 对应
CATEGORY_DIRS = [
    "01_网络小说", "02_中文文学", "03_外国文学",
    "04_历史与古代资料", "05_现代专业资料", "06_其他参考资料",
]
CAT_DIR_TO_LABEL = {d: index_builder.CATEGORY_LABEL[d] for d in CATEGORY_DIRS}
# 非书籍类专业资料：SP 不适用，标记 NOT_APPLICABLE，不转换、不进 06_工作区
NOT_APPLICABLE_CATEGORIES = {"05_现代专业资料"}
# 待人工核验目录：SP 不自动处理
SKIP_DIRS = {"00_待核验"}
# 合集容器目录内标记文件（Local Only，不上传 GitHub）
COLLECTION_MANIFEST = "collection_manifest.json"

MIN_VISIBLE_CHARS = 5000
CHAPTER_MIN = 3
GARBLE_WARN = 10

CHAPTER_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:"
    r"第[\d一二三四五六七八九十百千万零〇两]+[章回节卷部篇集](?:[：:\s　].*)?"
    r"|[卷部篇集][\d一二三四五六七八九十百千万零〇两]+(?:[：:\s　].*)?"
    r"|(?:序章|楔子|引子|前言|序言|尾声|终章|后记|跋|番外(?:篇)?)(?:[：:\s　].*)?"
    r")\s*$"
)
NUMERIC_HEADING_RE = re.compile(r"^\s*#{1,6}\s*(?:Chapter\s+)?(?:\d{1,4}|[IVXLCDM]{1,8})[.、:]?\s*$", re.I)
MD_HEADING_RE = re.compile(r"^\s*#{1,6}\s+\S+")
# 出版物 EPUB 常把章号渲染成独立 blockquote 行，如 “> 五”“> 第一部”“> 一”
BQ_CHAPTER_RE = re.compile(
    r"^\s*>\s*(?:"
    r"[第卷部篇集]?[\d一二三四五六七八九十百千零〇两]{1,4}[章回节卷部篇集]?"
    r"|序章|楔子|引子|尾声|终章|后记|跋|番外"
    r")\s*$"
)


@dataclass
class Candidate:
    path: str
    ext: str
    sha256: str
    status: str = "FAIL"
    char_count: int = 0
    garbled: int = 0
    chapter_count: int = 0
    warnings: list[str] | None = None
    notes: list[str] | None = None
    temp_md: Optional[str] = None
    epub_checks: list[dict] | None = None

    def __post_init__(self) -> None:
        self.warnings = self.warnings or []
        self.notes = self.notes or []


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
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
    if len(strong) >= CHAPTER_MIN:
        return strong
    # 独立 blockquote 章号（出版物 EPUB 常见）
    bq = [i for i, line in enumerate(lines) if BQ_CHAPTER_RE.match(line)]
    if len(bq) >= CHAPTER_MIN:
        return bq
    numeric = [i for i, line in enumerate(lines) if NUMERIC_HEADING_RE.match(line)]
    combined = sorted(set(strong + numeric))
    if len(combined) >= CHAPTER_MIN:
        return combined
    headings = [i for i, line in enumerate(lines) if MD_HEADING_RE.match(line)]
    return headings if len(headings) >= CHAPTER_MIN else []


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


def safe_name(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", s).strip() or "unnamed"


# --------------------------------------------------------------------------- #
# EPUB 14 项质量检测
# --------------------------------------------------------------------------- #
def check_epub(path: Path) -> tuple[list[dict], bool]:
    """返回 (14项检测清单, 是否通过关键结构)。"""
    name = path.name
    checks: list[dict] = []
    notes: list[str] = []
    try:
        if not zipfile.is_zipfile(path):
            checks.append(_c(1, "有效 ZIP/EPUB 容器", "fail", "不是有效的 ZIP/EPUB 容器"))
            # 后面无需继续
            checks += [_c(i, t, "skip", "前序关键项失败") for i, t in [
                (2, "mimetype 声明 application/epub+zip"),
                (3, "含 META-INF/container.xml"),
                (4, "container.xml 指向有效 OPF"),
                (5, "OPF 文件可解析"),
                (6, "OPF 含 dc:title"),
                (7, "OPF 含 dc:creator"),
                (8, "manifest 清单非空"),
                (9, "spine 阅读顺序非空"),
                (10, "spine 可定位率 ≥ 80%"),
                (11, "可定位正文文档 ≥ 1"),
                (12, "含 NCX / EPUB3 nav 导航"),
            ]]
            return checks, False

        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())

            # 2. mimetype
            mt_ok = False
            if "mimetype" in names:
                data = z.read("mimetype").decode("utf-8", "replace").strip()
                mt_ok = data == "application/epub+zip"
                checks.append(_c(2, "mimetype 声明 application/epub+zip",
                                 "pass" if mt_ok else "warn",
                                 data if data else "缺失 mimetype 内容"))
            else:
                checks.append(_c(2, "mimetype 声明 application/epub+zip", "warn", "未找到 mimetype 文件"))

            # 3. container.xml
            if "META-INF/container.xml" not in names:
                checks.append(_c(3, "含 META-INF/container.xml", "fail", "缺失"))
            else:
                checks.append(_c(3, "含 META-INF/container.xml", "pass", "存在"))

            # 4. 定位 OPF
            opf_path: Optional[str] = None
            if "META-INF/container.xml" in names:
                try:
                    container = ET.fromstring(z.read("META-INF/container.xml"))
                    for elem in container.iter():
                        if elem.tag.endswith("rootfile"):
                            rf = elem.attrib.get("full-path")
                            if rf and rf in names:
                                opf_path = rf
                                break
                    checks.append(_c(4, "container.xml 指向有效 OPF",
                                     "pass" if opf_path else "fail",
                                     opf_path or "未指向包内有效 OPF"))
                except ET.ParseError as e:
                    checks.append(_c(4, "container.xml 指向有效 OPF", "fail", f"解析失败：{e}"))
            else:
                checks.append(_c(4, "container.xml 指向有效 OPF", "skip", "前序关键项失败"))

            # 5-12 OPF 解析与清单
            opf = None
            if opf_path:
                try:
                    opf = ET.fromstring(z.read(opf_path))
                    checks.append(_c(5, "OPF 文件可解析", "pass", opf_path))
                except ET.ParseError as e:
                    checks.append(_c(5, "OPF 文件可解析", "fail", f"XML 解析失败：{e}"))
            else:
                checks.append(_c(5, "OPF 文件可解析", "skip", "无可用 OPF"))

            title = creator = None
            manifest: dict[str, str] = {}
            spine_ids: list[str] = []
            nav_ids: set[str] = set()
            if opf is not None:
                DC = "{http://purl.org/dc/elements/1.1/}"
                for elem in opf.iter():
                    tag = elem.tag
                    if tag == DC + "title" and elem.text:
                        title = elem.text.strip()
                    elif tag == DC + "creator" and elem.text:
                        creator = elem.text.strip()
                    elif tag.endswith("}item"):
                        iid = elem.attrib.get("id")
                        href = elem.attrib.get("href")
                        mtype = (elem.attrib.get("media-type") or "").lower()
                        if iid and href:
                            manifest[iid] = href
                        if "nav" in mtype or elem.attrib.get("properties", "").lower() == "nav":
                            if iid:
                                nav_ids.add(iid)
                    elif tag.endswith("}itemref"):
                        rid = elem.attrib.get("idref")
                        if rid:
                            spine_ids.append(rid)

                # 6. dc:title
                checks.append(_c(6, "OPF 含 dc:title",
                                 "pass" if title else "warn", title or "缺失标题元数据"))
                # 7. dc:creator
                checks.append(_c(7, "OPF 含 dc:creator",
                                 "pass" if creator else "warn", creator or "缺失作者元数据（仅警告）"))
                # 8. manifest
                checks.append(_c(8, "manifest 清单非空",
                                 "pass" if manifest else "fail", f"条目数 {len(manifest)}"))
                # 9. spine
                checks.append(_c(9, "spine 阅读顺序非空",
                                 "pass" if spine_ids else "fail", f"条目数 {len(spine_ids)}"))
                # 10. spine 可定位率
                if spine_ids:
                    base = Path(opf_path).parent
                    existing = sum(1 for rid in spine_ids
                                   if manifest.get(rid) and (base / manifest[rid]).as_posix() in names)
                    ratio = existing / len(spine_ids)
                    checks.append(_c(10, "spine 可定位率 ≥ 80%",
                                     "pass" if ratio >= 0.8 else "fail",
                                     f"{existing}/{len(spine_ids)} = {ratio:.0%}"))
                    # 11. 可定位正文文档
                    checks.append(_c(11, "可定位正文文档 ≥ 1",
                                     "pass" if existing >= 1 else "fail", f"{existing} 个"))
                    # 12. 导航
                    has_nav = bool(nav_ids) or any(n.endswith((".ncx",)) for n in names)
                    checks.append(_c(12, "含 NCX / EPUB3 nav 导航",
                                     "pass" if has_nav else "warn",
                                     "存在" if has_nav else "未检测到导航文档（仅警告）"))
                else:
                    for i, t in [(10, "spine 可定位率 ≥ 80%"), (11, "可定位正文文档 ≥ 1"),
                                (12, "含 NCX / EPUB3 nav 导航")]:
                        checks.append(_c(i, t, "skip", "spine 为空"))

            notes.append(f"title={title or '?'}, creator={creator or '?'}, "
                         f"manifest={len(manifest)}, spine={len(spine_ids)}")

    except Exception as e:
        checks.append(_c(0, "EPUB 检测异常", "fail", str(e)))
        return checks, False

    critical = {1, 3, 4, 5, 8, 9, 10, 11}
    passed = all(c["status"] != "fail" for c in checks if c["idx"] in critical)
    return checks, passed


def _c(idx: int, title: str, status: str, detail: str) -> dict:
    return {"idx": idx, "title": title, "status": status, "detail": detail}


# --------------------------------------------------------------------------- #
# 单文件转换
# --------------------------------------------------------------------------- #
def assess_candidate(cand: Candidate, text: str) -> None:
    fatal = False
    if cand.char_count < MIN_VISIBLE_CHARS:
        cand.warnings.append(f"正文字符数过少：{cand.char_count}（阈值 {MIN_VISIBLE_CHARS}）")
        fatal = True
    if cand.garbled > GARBLE_WARN:
        cand.warnings.append(f"出现 {cand.garbled} 个替换字符 �，疑似乱码")
    if cand.chapter_count == 0:
        cand.warnings.append(f"未可靠识别章节边界（需 ≥ {CHAPTER_MIN} 个）")
    if fatal:
        cand.status = "FAIL"
    elif cand.garbled > GARBLE_WARN or cand.chapter_count == 0:
        cand.status = "REVIEW"
    else:
        cand.status = "PASS"


def convert_epub(path: Path, pandoc: str, work_dir: Path) -> Candidate:
    cand = Candidate(str(path), ".epub", sha256_file(path))
    checks, ok = check_epub(path)
    cand.epub_checks = checks
    cand.notes.append("EPUB 14 项检测：" + ", ".join(
        f"{c['idx']}:{c['status']}" for c in checks if c["idx"]))
    if not ok:
        cand.warnings.append("EPUB 关键结构检测未通过（见 conversion_report 明细）")
        return cand
    out = work_dir / f"{cand.sha256[:12]}.epub.md"
    proc = subprocess.run(
        [pandoc, str(path), "-f", "epub", "-t", "gfm", "--wrap=none", "-o", str(out)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0 or not out.exists():
        cand.warnings.append("Pandoc EPUB→Markdown 失败")
        if proc.stderr:
            cand.notes.append(proc.stderr[-2000:])
        # 把第 13/14 项标记为 fail
        cand.epub_checks = (cand.epub_checks or []) + [
            _c(13, "Pandoc 转换执行", "fail", "转换失败"),
            _c(14, "转换后正文质量", "skip", "转换失败未产出"),
        ]
        return cand
    text = clean_markdown(out.read_text(encoding="utf-8", errors="replace"))
    out.write_text(text, encoding="utf-8")
    cand.temp_md = str(out)
    cand.char_count = visible_char_count(text)
    cand.garbled = text.count("\ufffd")
    cand.chapter_count = len(chapter_starts(text.splitlines()))
    # 补 13/14 项
    cand.epub_checks = (cand.epub_checks or []) + [
        _c(13, "Pandoc 转换执行", "pass", "成功"),
        _c(14, "转换后正文质量",
           "pass" if (cand.char_count >= MIN_VISIBLE_CHARS and cand.garbled <= GARBLE_WARN)
           else "warn",
           f"可见字符 {cand.char_count}，替换字符 {cand.garbled}"),
    ]
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
    cand.garbled = text.count("\ufffd")
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
            proc = subprocess.run([exe, "-layout", str(path), str(out)],
                                  capture_output=True, text=True)
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
    cand.garbled = text.count("\ufffd")
    cand.chapter_count = len(chapter_starts(text.splitlines()))
    assess_candidate(cand, text)
    return cand


def convert_other(path: Path) -> Candidate:
    cand = Candidate(str(path), path.suffix.lower(), sha256_file(path))
    cand.warnings.append(f"{path.suffix} 暂不支持自动转换；需人工解压/确认内部格式后再处理")
    return cand


# --------------------------------------------------------------------------- #
# 来源选择：完整性 > 准确性 > 章节 > 格式
# --------------------------------------------------------------------------- #
def choose_candidate(cands: list[Candidate]) -> tuple[Optional[Candidate], list[str]]:
    warnings: list[str] = []
    usable = [c for c in cands if c.temp_md and c.status != "FAIL"]
    if not usable:
        return None, warnings
    max_char = max(c.char_count for c in usable)
    for c in usable:
        if max_char > 0 and c.char_count < 0.7 * max_char:
            c.warnings.append(f"正文长度仅为最长来源的 {c.char_count / max_char:.0%}，可能不完整")
            if c.status == "PASS":
                c.status = "REVIEW"
    # 近邻选源修正（P1）：两个候选正文长度差 ≤ 2% 时，
    # 若“较长来源”为 REVIEW 且 0 章节，而“另一来源”为 PASS 且有章节，
    # 则优先选择 PASS + 有章节的来源（避免丢失分章、整体降级）。
    preferred: Optional[Candidate] = None
    longest = max(usable, key=lambda c: c.char_count)
    for other in usable:
        if other is longest:
            continue
        if longest.char_count and other.char_count:
            ratio = other.char_count / longest.char_count
            if ratio >= 0.98:  # 长度差 ≤ 2%
                if (longest.status == "REVIEW" and longest.chapter_count == 0
                        and other.status == "PASS" and other.chapter_count >= 1):
                    preferred = other
                    break

    # 排序键：近邻修正优先 > 完整性(字符数降) > 准确性(替换字符升) >
    #         章节数降 > 格式优先级升
    usable.sort(key=lambda c: (
        c is not preferred,           # 被修正选中的来源排最前
        -c.char_count,
        c.garbled,
        -c.chapter_count,
        SOURCE_PRIORITY.get(c.ext, 9),
    ))
    selected = usable[0]
    if preferred is not None:
        # 修正说明写入选中候选 notes（出现在报告“单文件备注”，
        # 且不进入 cross_warnings，因此不会触发整体 REVIEW 升级）。
        selected.notes.append(
            f"近邻选源修正（长度差≤2%）：较长来源 `{Path(longest.path).name}` 为 REVIEW/0章，"
            f"改用更可信的 PASS+有章节来源 `{Path(selected.path).name}`")
    for peer in usable[1:]:
        if selected.char_count and peer.char_count:
            ratio = min(selected.char_count, peer.char_count) / max(selected.char_count, peer.char_count)
            if ratio < 0.65:
                warnings.append(
                    f"来源长度差异较大：{Path(selected.path).name}({selected.char_count}) "
                    f"vs {Path(peer.path).name}({peer.char_count})，较短/较长={ratio:.0%}")
    return selected, warnings


# --------------------------------------------------------------------------- #
# 作品扫描（直接扫根层，无 00_原始文件 依赖）
# --------------------------------------------------------------------------- #
def load_collection_manifests(root: Path) -> dict:
    """扫描 01_原始素材 下所有含 collection_manifest.json 的“合集容器”目录。

    返回 {容器目录Path: manifest字典}。合集目录只登记 manifest 中列出的拆分单书，
    不入原始合集本身，也不把它当成“一个作品”。
    """
    raw = root / RAW
    result: dict = {}
    for cat in CATEGORY_DIRS:
        cdir = raw / cat
        if not cdir.exists():
            continue
        for entry in sorted(cdir.iterdir()):
            if entry.is_dir():
                mpath = entry / COLLECTION_MANIFEST
                if mpath.exists():
                    try:
                        result[entry] = json.loads(mpath.read_text(encoding="utf-8"))
                    except Exception:
                        pass
    return result


@dataclass
class CandidateRec:
    cat_dir: str
    work_name: str
    source_container: str
    path: Path
    manifest_book_id: Optional[str] = None


def collect_candidates(root: Path) -> list[CandidateRec]:
    """收集所有候选源文件，且“合集容器”感知。

    - 普通作品目录：目录内每个支持文件 = 一个候选（来源容器为空）。
    - 合集容器目录（含 collection_manifest.json）：只登记 manifest 中列出的拆分单书，
      来源容器 = 容器名；原始合集 EPUB 等其余文件跳过。
    - 作品身份不直接由“文件夹名”决定；book ID 由索引 / manifest 解析（见 group_works）。
    """
    raw = root / RAW
    collections = load_collection_manifests(root)
    collection_dirs = set(collections.keys())
    out: list[CandidateRec] = []
    for cat in CATEGORY_DIRS:
        cdir = raw / cat
        if not cdir.exists():
            continue
        for entry in sorted(cdir.iterdir()):
            if entry in collection_dirs:
                man = collections[entry]
                cname = man.get("container", entry.name)
                cat_for_splits = man.get("category", cat)
                for s in man.get("splits", []):
                    fn = s.get("filename")
                    p = entry / fn if fn else None
                    if p and p.exists():
                        out.append(CandidateRec(
                            cat_dir=cat_for_splits,
                            work_name=s.get("work_name", p.stem),
                            source_container=cname,
                            path=p,
                            manifest_book_id=s.get("book_id")))
                # 原始合集及其他文件不入索引
                continue
            if entry.is_dir():
                if entry.name in SKIP_DIRS:
                    continue
                for f in entry.iterdir():
                    if f.is_file() and f.suffix.lower() in SUPPORTED:
                        out.append(CandidateRec(cat_dir=cat, work_name=entry.name,
                                                source_container="", path=f))
            elif entry.is_file() and entry.suffix.lower() in SUPPORTED:
                out.append(CandidateRec(cat_dir=cat, work_name=entry.stem,
                                        source_container="", path=entry))
    return out


def build_book_map(root: Path) -> tuple[dict[tuple[str, str], str], dict[str, str]]:
    """CSV 索引：返回 ((分类label, 作品名)->作品ID, 仅作品名->作品ID)。

    - 主键 (分类label, 作品名) 用于正常单本。
    - 仅作品名 映射作为兜底：当作品因“分类平移 / 合集拆分”导致物理分类与
      索引分类不一致时（如 长安十二时辰 旧 txt 在 网络小说、索引归类为 中文文学），
      仍能靠作品名归并到同一 book_id。
    作品身份最终以 book_id + 中央索引为准。
    """
    rows = index_builder.load_csv(root)
    by_key: dict[tuple[str, str], str] = {}
    by_name: dict[str, str] = {}
    for r in rows:
        by_key.setdefault((r["资料大类"], r["作品名"]), r["作品ID"])
        by_name.setdefault(r["作品名"], r["作品ID"])
    return by_key, by_name


def group_candidates(cands: list[CandidateRec], book_map: dict, name_map: dict) -> list[dict]:
    """把候选源按作品身份聚类：manifest book_id > (分类label, 作品名) > 作品名。

    合集拆分单书的 book_id 来自 manifest；普通作品来自 CSV 索引（优先按
    分类+作品名，再按作品名兜底，兼容分类平移）。这样同一作品的不同物理来源
    （例如 01_网络小说/长安十二时辰/ 与 02_中文文学/马伯庸作品合集/长安十二时辰.epub）
    会归到同一 book_id，SourcePrepare 处理该作品时能看见并交叉校验全部候选来源。
    """
    groups: dict = {}
    for c in cands:
        cat_label = CAT_DIR_TO_LABEL.get(c.cat_dir, c.cat_dir)
        bid = (c.manifest_book_id
               or book_map.get((cat_label, c.work_name))
               or name_map.get(c.work_name))
        key = bid if bid else (cat_label, c.work_name)
        g = groups.get(key)
        if g is None:
            g = {"cat_dir": c.cat_dir, "work_name": c.work_name,
                 "book_id": bid, "files": [], "containers": set()}
            groups[key] = g
        g["files"].append(c.path)
        g["containers"].add(c.source_container)
    return list(groups.values())


# --------------------------------------------------------------------------- #
# 报告
# --------------------------------------------------------------------------- #
def report_markdown(book: str, category: str, book_id: str, cands: list[Candidate],
                    selected: Optional[Candidate], overall: str,
                    warnings: list[str], pandoc: Optional[str]) -> str:
    lines = [
        f"# SourcePrepare 转换报告：{book}",
        "",
        f"- Skill 版本：{SKILL_VERSION}",
        f"- 作品ID：{book_id}",
        f"- 分类：{category}",
        f"- Pandoc：{pandoc or '未找到'}",
        f"- 最终状态：**{overall}**",
        f"- 选中来源：`{Path(selected.path).name}`" if selected else "- 选中来源：无",
        "",
        "## 来源评估", "",
        "| 文件 | 格式 | 状态 | 可见字符 | 替换字符 | 章节边界 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for c in cands:
        lines.append(
            f"| `{Path(c.path).name}` | {c.ext} | {c.status} | "
            f"{c.char_count} | {c.garbled} | {c.chapter_count} |")

    # EPUB 14 项检测明细
    for c in cands:
        if c.ext == ".epub" and c.epub_checks:
            lines += ["", f"## EPUB 质量检测（14 项）：`{Path(c.path).name}`", "",
                      "| # | 检测项 | 结果 | 说明 |", "|---:|---|---|---|"]
            for ck in c.epub_checks:
                if ck["idx"] == 0:
                    continue
                lines.append(f"| {ck['idx']} | {ck['title']} | {ck['status']} | {ck['detail']} |")

    if warnings:
        lines += ["", "## 需要注意", ""] + [f"- {w}" for w in warnings]
    lines += ["", "## 单文件备注", ""]
    for c in cands:
        lines.append(f"### {Path(c.path).name}")
        items = (c.notes or []) + [f"⚠ {w}" for w in (c.warnings or [])]
        lines.extend(f"- {x}" for x in items) if items else lines.append("- 无")
        lines.append("")
    lines += [
        "## 使用规则", "",
        "- `PASS`：可进入后续 BookDistill。",
        "- `REVIEW`：需要人工检查后再进入 BookDistill。",
        "- `FAIL`：不得进入 BookDistill，应使用备用来源或人工处理。",
        "- `NOT_APPLICABLE`：非书籍类专业资料，SourcePrepare 不适用。",
        "- 本流程不修改、不覆盖 `01_原始素材` 中任何文件。",
        "- PDF 无文本层时不自动 OCR。", "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 处理单部作品
# --------------------------------------------------------------------------- #
def process_book(root: Path, cat_dir: str, work_name: str, is_loose: bool,
                 files: list[Path], book_id: Optional[str],
                 pandoc: Optional[str], force: bool) -> str:
    category = CAT_DIR_TO_LABEL[cat_dir]

    # 非书籍类专业资料：直接标记 NOT_APPLICABLE，不进 06_工作区
    if cat_dir in NOT_APPLICABLE_CATEGORIES:
        if book_id:
            index_builder.update_book(
                root, book_id, sp_status="NOT_APPLICABLE", sp_version=SKILL_VERSION,
                note="非书籍类专业资料，SourcePrepare 不适用")
        return f"NOT_APPLICABLE {work_name}（{category}）"

    if not book_id:
        return f"SKIP {work_name}: 未在中央索引找到作品ID（请先运行 index_builder.py）"

    out_dir = root / "06_工作区" / "SourcePrepare" / f"{book_id}_{safe_name(work_name)}"
    full_md = out_dir / "full.md"
    chapters_dir = out_dir / "chapters"
    report = out_dir / "conversion_report.md"
    meta = out_dir / "metadata.json"

    if full_md.exists() and not force:
        return f"SKIP {work_name}: 已存在 full.md（使用 --force 重跑）"

    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        cands: list[Candidate] = []
        for p in sorted(files):
            ext = p.suffix.lower()
            if ext == ".epub":
                cands.append(convert_epub(p, pandoc, work) if pandoc
                             else _no_pandoc_epub(p))
            elif ext == ".txt":
                cands.append(convert_txt(p, work))
            elif ext == ".pdf":
                cands.append(convert_pdf(p, work))
            else:
                cands.append(convert_other(p))

        selected, cross_warnings = choose_candidate(cands)
        if not selected:
            overall = "FAIL"
            report.write_text(report_markdown(work_name, category, book_id, cands,
                                              None, overall, cross_warnings, pandoc),
                              encoding="utf-8")
            meta.write_text(json.dumps({
                "skill_version": SKILL_VERSION, "book_id": book_id, "book": work_name,
                "category": category, "status": overall, "selected_source": None,
                "candidates": [_cand_json(c) for c in cands],
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            index_builder.update_book(root, book_id, sp_status=overall,
                                      sp_version=SKILL_VERSION, note="无可用来源")
            return f"FAIL {work_name}"

        text = Path(selected.temp_md).read_text(encoding="utf-8")
        out_dir.mkdir(parents=True, exist_ok=True)
        full_md.write_text(text, encoding="utf-8")
        split_count = split_chapters(text, chapters_dir)
        overall = selected.status
        if cross_warnings or split_count == 0:
            overall = "REVIEW"
        if split_count == 0:
            cross_warnings.append("未生成 chapters/ 分章文件；full.md 已保留")

        report.write_text(report_markdown(work_name, category, book_id, cands,
                                          selected, overall, cross_warnings, pandoc),
                          encoding="utf-8")
        meta.write_text(json.dumps({
            "skill_version": SKILL_VERSION, "book_id": book_id, "book": work_name,
            "category": category, "status": overall,
            "selected_source": {
                "path": selected.path, "format": selected.ext,
                "sha256": selected.sha256, "char_count": selected.char_count,
            },
            "chapter_files": split_count,
            "cross_source_warnings": cross_warnings,
            "candidates": [_cand_json(c) for c in cands],
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        index_builder.update_book(
            root, book_id, sp_status=overall, sp_version=SKILL_VERSION,
            char_count=selected.char_count, chapter_count=split_count,
            note=f"选中来源：{Path(selected.path).name}（{selected.ext}）")
        return f"{overall} {work_name}: {Path(selected.path).name}, chapters={split_count}"


def _no_pandoc_epub(p: Path) -> Candidate:
    c = Candidate(str(p), ".epub", sha256_file(p))
    c.warnings.append("未找到 Pandoc，无法转换 EPUB（已做结构检测）")
    checks, ok = check_epub(p)
    c.epub_checks = checks
    if not ok:
        c.warnings.append("EPUB 关键结构检测未通过")
    return c


def _cand_json(c: Candidate) -> dict:
    d = asdict(c)
    d["temp_md"] = None
    return d


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def locate(root: Path, name: Optional[str], all_books: bool, book_map: dict, name_map: dict) -> list[dict]:
    """定位要处理的作品分组。支持按作品名 或 作品ID（如 book_0035）匹配。

    不再假定“文件夹=作品”：候选来源来自 collect_candidates（合集感知），
    再按 book_id/作品名 聚类（group_candidates）。因此同一作品即使来源
    分散在多个物理目录，也能被一起选中。
    """
    cands = collect_candidates(root)
    groups = group_candidates(cands, book_map, name_map)
    if all_books:
        return groups
    if not name:
        raise SystemExit("必须指定 --book <作品名 或 作品ID> 或 --all")
    # 精确匹配：作品名 或 作品ID
    exact = [g for g in groups
             if g["work_name"] == name or (g["book_id"] and g["book_id"] == name)]
    if exact:
        return exact
    # 部分匹配（不区分大小写）
    lname = name.lower()
    partial = [g for g in groups
               if lname in g["work_name"].lower()
               or (g["book_id"] and lname in g["book_id"].lower())]
    if len(partial) == 1:
        return partial
    if not partial:
        raise SystemExit(f"未找到作品：{name}")
    raise SystemExit("作品名匹配多个：" + "、".join(
        f"{g['work_name']}({g['book_id']})" for g in partial))


def main() -> int:
    ap = argparse.ArgumentParser(description="AI-Write SourcePrepare：原著源文件标准化为纯净 Markdown")
    ap.add_argument("--root", required=True, help=r"项目根目录，例如 E:\AI-Write")
    ap.add_argument("--book", help="处理单部作品；支持唯一部分匹配")
    ap.add_argument("--all", action="store_true", help="处理全部作品（建议先单书试跑）")
    ap.add_argument("--force", action="store_true", help="覆盖工作区已有转换结果；绝不覆盖原始素材")
    ap.add_argument("--dry-run", action="store_true", help="仅输出处理计划，不转换、不写索引")
    args = ap.parse_args()

    if not args.book and not args.all:
        raise SystemExit("必须指定 --book <作品名> 或 --all")
    root = Path(args.root).resolve()
    if not (root / "01_原始素材").exists():
        raise SystemExit("项目根目录不正确：缺少 01_原始素材")
    pandoc = find_pandoc(root)
    book_map, name_map = build_book_map(root)
    targets = locate(root, args.book, args.all, book_map, name_map)

    if args.dry_run:
        print(f"[DRY-RUN] Pandoc: {pandoc or '未找到'}  目标作品数：{len(targets)}")
        for g in targets:
            label = CAT_DIR_TO_LABEL.get(g["cat_dir"], g["cat_dir"])
            na = " [NOT_APPLICABLE]" if g["cat_dir"] in NOT_APPLICABLE_CATEGORIES else ""
            fmts = ", ".join(sorted({f.suffix.lower() for f in g["files"]}))
            conts = "、".join(sorted(("独立来源" if not c else c) for c in g["containers"])) or "独立来源"
            print(f"  - {label}/{g['work_name']}  id={g['book_id']}  "
                  f"formats=[{fmts}]  来源容器=[{conts}]{na}")
        return 0

    results = []
    for g in targets:
        is_loose = "" in g["containers"]  # 含独立（非合集）来源
        try:
            results.append(process_book(root, g["cat_dir"], g["work_name"], is_loose,
                                        g["files"], g["book_id"], pandoc, args.force))
        except Exception as exc:  # 单书异常不应中断整个批次
            msg = f"ERROR {g['work_name']}({g['book_id']}): {type(exc).__name__}: {exc}"
            results.append(msg)
            print(msg, file=sys.stderr)
    for r in results:
        print(r)
    # FAIL / ERROR 均视为批次中存在失败项，退出码非 0
    failed = any(r.startswith(("FAIL", "ERROR")) for r in results)
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
