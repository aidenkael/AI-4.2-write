# -*- coding: utf-8 -*-
"""epub_structure —— SourcePrepare / MethodPrepare 共享的确定性 EPUB 结构 helper。

根因合同（§7 / §8）：EPUB 的**原生结构**（container.xml → OPF → manifest + spine）
恢复阅读顺序；EPUB3 nav / EPUB2 NCX 的 path+fragment target 优先提供真实章节边界。
`spine != chapter`：无可靠 anchor 时由上层检查强章标题，仍无法恢复则显式输出
reading_unit，不虚构 chapter。

设计约束：
  - 纯 stdlib（zipfile + xml.etree.ElementTree + urllib），无 EPUB 框架/依赖、无 AI、无网络；
  - 只读来源 EPUB，绝不修改；
  - 确定性：同一 EPUB 重复解析得到相同的有序单元；
  - spine 只是有序阅读容器；nav/NCX 目标保留 path+fragment，同一 XHTML 的
    多个可靠章标题 anchor 可形成多个章节单元；
  - 每个 spine 文档用 Pandoc `html -> gfm` 单独转换（保留源顺序），空/非内容单元由调用方
    按各自质量口径确定性跳过。

被 SourcePrepare（chapters/）与 MethodPrepare（sections/）共同复用，避免出现两套
不一致的 EPUB 解析器。MethodPrepare 只导入本 helper，绝不调用 SourcePrepare 整个 Skill。
"""
from __future__ import annotations

import subprocess
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urldefrag

_OPF_ITEM = "}item"
_OPF_ITEMREF = "}itemref"
_DC_TITLE = "{http://purl.org/dc/elements/1.1/}title"
_DC_CREATOR = "{http://purl.org/dc/elements/1.1/}creator"
_CONTENT_EXTS = (".xhtml", ".html", ".htm", ".xml")
_PANDOC_TIMEOUT = 30 * 60
_CHAPTER_LABEL_RE = re.compile(
    r"^\s*(?:第[\d一二三四五六七八九十百千万零〇两]+[章回](?:[\s：:].*)?"
    r"|Chapter\s+[\dIVXLCDM]+(?:[\s:.-].*)?|序章|楔子|引子|尾声|终章|番外(?:篇)?)\s*$",
    re.IGNORECASE,
)


@dataclass
class EpubUnit:
    """一个有序 EPUB reading unit = 一个 spine (X)HTML 文档。"""

    order: int
    zip_path: str          # zip 内部路径（已解析相对 OPF 目录、去 URL 编码/锚点）
    label: str | None      # nav/NCX 唯一映射到本文档时的标签，否则 None
    targets: list["EpubTocTarget"] = field(default_factory=list)


@dataclass(frozen=True)
class EpubTocTarget:
    """nav/NCX 目标；fragment 是结构事实，不得在解析时丢弃。"""

    order: int
    zip_path: str
    fragment: str | None
    label: str | None


@dataclass(frozen=True)
class ConvertedEpubUnit:
    """转换后的有序单元；boundary_source 仅表达来源结构事实。"""

    label: str | None
    text: str
    boundary_source: str
    zip_path: str
    fragment: str | None = None


@dataclass
class EpubStructure:
    """EPUB 原生结构解析结果（只读事实，供调用方判定与命名）。"""

    opf_path: str
    title: str | None
    creator: str | None
    manifest_items: int
    spine_items: int
    units: list[EpubUnit]
    nav_label_count: int   # 成功解析到的 nav/NCX 标签总数（结构丰富度事实）
    toc_targets: list[EpubTocTarget] = field(default_factory=list)

    @property
    def has_units(self) -> bool:
        return bool(self.units)


def _join_opf(opf_dir: str, href: str) -> str:
    """把 manifest/NCX 的相对 href 解析为 zip 内部路径（相对 OPF 目录，去编码/锚点）。"""
    href = unquote(urldefrag(href).url).lstrip("/")
    if opf_dir in ("", "."):
        return href
    return f"{opf_dir}/{href}"


def _resolve_href(base_dir: str, href: str) -> tuple[str, str | None]:
    """解析 href 但保留 fragment；path 与旧 _join_opf 合同一致。"""
    decoded = unquote(href)
    split = urldefrag(decoded)
    return _join_opf(base_dir, split.url), (split.fragment or None)


def _find_opf(z: zipfile.ZipFile, names: set[str]) -> str | None:
    if "META-INF/container.xml" not in names:
        return None
    try:
        container = ET.fromstring(z.read("META-INF/container.xml"))
    except ET.ParseError:
        return None
    for elem in container.iter():
        if elem.tag.endswith("rootfile"):
            full = elem.attrib.get("full-path")
            if full and full in names:
                return full
    return None


def _parse_opf(z: zipfile.ZipFile, opf_path: str):
    """返回 (title, creator, manifest{id:href}, media{id:type}, props{id:properties}, spine[idref])。"""
    opf = ET.fromstring(z.read(opf_path))
    title = creator = None
    manifest: dict[str, str] = {}
    media: dict[str, str] = {}
    props: dict[str, str] = {}
    spine: list[str] = []
    for elem in opf.iter():
        tag = elem.tag
        if tag == _DC_TITLE and elem.text and title is None:
            title = elem.text.strip()
        elif tag == _DC_CREATOR and elem.text and creator is None:
            creator = elem.text.strip()
        elif tag.endswith(_OPF_ITEM):
            iid = elem.attrib.get("id")
            href = elem.attrib.get("href")
            if iid and href:
                manifest[iid] = href
                media[iid] = (elem.attrib.get("media-type") or "").lower()
                props[iid] = (elem.attrib.get("properties") or "").lower()
        elif tag.endswith(_OPF_ITEMREF):
            rid = elem.attrib.get("idref")
            if rid:
                spine.append(rid)
    return title, creator, manifest, media, props, spine


def _parse_toc_labels(z: zipfile.ZipFile, names: set[str], opf_dir: str,
                      manifest: dict[str, str], media: dict[str, str],
                      props: dict[str, str]) -> tuple[list[EpubTocTarget], int]:
    """解析 EPUB3 nav / EPUB2 NCX，保留 path + fragment + label + 阅读顺序。"""
    targets: list[EpubTocTarget] = []

    # EPUB3 nav document（properties 含 "nav"）
    nav_href = None
    for iid, pr in props.items():
        if "nav" in pr and iid in manifest:
            nav_href = manifest[iid]
            break
    if nav_href:
        nav_path = _join_opf(opf_dir, nav_href)
        if nav_path in names:
            targets.extend(_collect_nav_labels(z.read(nav_path), opf_dir, nav_path))

    # EPUB2 NCX（media-type application/x-dtbncx+xml，或包内任意 .ncx）
    ncx_paths: list[str] = []
    for iid, mt in media.items():
        if "dtbncx" in mt and iid in manifest:
            ncx_paths.append(_join_opf(opf_dir, manifest[iid]))
    if not ncx_paths:
        ncx_paths = [n for n in sorted(names) if n.lower().endswith(".ncx")]
    for ncx in ncx_paths[:1]:
        if ncx in names:
            targets.extend(_collect_ncx_labels(z.read(ncx), ncx))

    # 有 nav 时不再把同一内容的 NCX 重复追加；按第一次出现去重。
    deduped: list[EpubTocTarget] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    for target in targets:
        key = (target.zip_path, target.fragment, target.label)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(EpubTocTarget(len(deduped) + 1, *key))
    return deduped, len(deduped)


def _collect_nav_labels(data: bytes, opf_dir: str, nav_path: str) -> list[EpubTocTarget]:
    """EPUB3 nav XHTML：<nav epub:type="toc"> 下的 <a href="...">label</a>。"""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    nav_dir = str(Path(nav_path).parent)
    if nav_dir in ("", "."):
        nav_dir = opf_dir
    targets: list[EpubTocTarget] = []
    for a in root.iter():
        if not a.tag.endswith("}a"):
            continue
        href = a.attrib.get("href")
        if not href:
            continue
        label = "".join(a.itertext()).strip()
        target, fragment = _resolve_href(nav_dir, href)
        targets.append(EpubTocTarget(len(targets) + 1, target, fragment, label or None))
    return targets


def _collect_ncx_labels(data: bytes, ncx_path: str) -> list[EpubTocTarget]:
    """EPUB2 NCX：<navPoint><navLabel><text>label</text></navLabel><content src="..."/>。"""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    ncx_dir = str(Path(ncx_path).parent)
    targets: list[EpubTocTarget] = []
    for np in root.iter():
        if not np.tag.endswith("navPoint"):
            continue
        label = ""
        src = ""
        for child in np.iter():
            if child.tag.endswith("}text") and not label:
                label = (child.text or "").strip()
            elif child.tag.endswith("}content"):
                src = child.attrib.get("src") or src
        if not src:
            continue
        base = ncx_dir if ncx_dir not in ("", ".") else ""
        target, fragment = _resolve_href(base, src)
        targets.append(EpubTocTarget(len(targets) + 1, target, fragment, label or None))
    return targets


def parse_epub_structure(epub_path: Path) -> EpubStructure | None:
    """解析 EPUB 原生结构；不是有效 zip/EPUB 或无 OPF → None。

    单元 = OPF spine 顺序下的独立 (X)HTML 内容文档（“最小可靠 spine 文档边界”）。
    nav/NCX 标签在唯一映射到某文档时命名该单元。spine 无 HTML 文档 → units 为空
    （调用方据此回退到 Markdown 标题兜底，而不是伪造章节）。
    """
    if not epub_path.is_file() or not zipfile.is_zipfile(epub_path):
        return None
    try:
        with zipfile.ZipFile(epub_path) as z:
            names = set(z.namelist())
            opf_path = _find_opf(z, names)
            if not opf_path:
                return None
            try:
                title, creator, manifest, media, props, spine = _parse_opf(z, opf_path)
            except ET.ParseError:
                return None
            opf_dir = str(Path(opf_path).parent)
            toc_targets, nav_label_count = _parse_toc_labels(
                z, names, opf_dir, manifest, media, props)
            targets_by_path: dict[str, list[EpubTocTarget]] = {}
            for target in toc_targets:
                targets_by_path.setdefault(target.zip_path, []).append(target)

            units: list[EpubUnit] = []
            order = 0
            for rid in spine:
                href = manifest.get(rid)
                mt = media.get(rid, "")
                if not href:
                    continue
                is_html = ("html" in mt or "xml" in mt)
                zip_path = _join_opf(opf_dir, href)
                if not is_html or zip_path not in names:
                    continue
                if not zip_path.lower().endswith(_CONTENT_EXTS):
                    continue
                order += 1
                targets = targets_by_path.get(zip_path, [])
                label = targets[0].label if len(targets) == 1 else None
                units.append(EpubUnit(order=order, zip_path=zip_path,
                                      label=label, targets=targets))
            return EpubStructure(
                opf_path=opf_path, title=title, creator=creator,
                manifest_items=len(manifest), spine_items=len(spine),
                units=units, nav_label_count=nav_label_count, toc_targets=toc_targets)
    except (OSError, zipfile.BadZipFile, ET.ParseError):
        return None


def render_unit_markdown(label: str | None, text: str) -> str:
    """把一个 EPUB 原生单元渲染为章节/分节 Markdown（SP chapters / MP sections 共用）。

    nav/NCX 标签只在“不会与正文首行重复”时作为 `# 标签` 标题前置（命名单元，
    绝不虚构内容/层级）；无标签时原样返回。确定性：同输入同输出。
    """
    body = (text or "").strip()
    lab = (label or "").strip()
    if lab and body:
        first = ""
        for line in body.splitlines():
            if line.strip():
                first = line.strip().lstrip("#").strip()
                break
        if lab != first:
            return f"# {lab}\n\n{body}"
    return body


def is_chapter_label(label: str | None) -> bool:
    """nav/NCX 标签是否足以作为保守的文学章节边界。"""
    return bool(_CHAPTER_LABEL_RE.match((label or "").strip()))


def _body_child_for_fragment(root: ET.Element, fragment: str) -> int | None:
    body = next((node for node in root.iter() if node.tag.lower().endswith("}body") or node.tag.lower() == "body"), None)
    if body is None:
        return None
    for index, child in enumerate(list(body)):
        for node in child.iter():
            if node.attrib.get("id") == fragment or node.attrib.get("name") == fragment:
                return index
    return None


def _anchored_xhtml_parts(raw: bytes, targets: list[EpubTocTarget]) -> list[tuple[EpubTocTarget | None, bytes]]:
    """将同一 XHTML 中可靠的章节 fragment 映射到 body 顶层块并切分。

    只在至少两个强章节标签都能映射、且边界严格递增时使用；
    否则 fail closed 回退整个 spine unit。
    """
    chapter_targets = [t for t in targets if t.fragment and is_chapter_label(t.label)]
    if len(chapter_targets) < 2:
        return []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    body = next((node for node in root.iter() if node.tag.lower().endswith("}body") or node.tag.lower() == "body"), None)
    if body is None:
        return []
    mapped = [(t, _body_child_for_fragment(root, t.fragment or "")) for t in chapter_targets]
    if any(index is None for _, index in mapped):
        return []
    indexes = [int(index) for _, index in mapped]
    if indexes != sorted(set(indexes)):
        return []

    children = list(body)
    parts: list[tuple[EpubTocTarget | None, bytes]] = []
    if indexes[0] > 0:
        prefix = b"<html><body>" + b"".join(ET.tostring(c, encoding="utf-8") for c in children[:indexes[0]]) + b"</body></html>"
        parts.append((None, prefix))
    for pos, (target, start) in enumerate(mapped):
        end = indexes[pos + 1] if pos + 1 < len(indexes) else len(children)
        payload = b"<html><body>" + b"".join(
            ET.tostring(c, encoding="utf-8") for c in children[int(start):end]
        ) + b"</body></html>"
        parts.append((target, payload))
    return parts


def convert_units_with_boundaries(epub_path: Path, units: list[EpubUnit], pandoc: str,
                                  work_dir: Path) -> list[ConvertedEpubUnit]:
    """按 spine 顺序转换，并在可靠时保留同 XHTML 的 nav/NCX fragment 边界。"""
    out: list[ConvertedEpubUnit] = []
    if not units or not pandoc:
        return out
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        archive = zipfile.ZipFile(epub_path)
    except (OSError, zipfile.BadZipFile):
        return out
    with archive:
        serial = 0
        for unit in units:
            try:
                raw = archive.read(unit.zip_path)
            except KeyError:
                continue
            parts = _anchored_xhtml_parts(raw, unit.targets)
            if not parts:
                chapter_target = next((t for t in unit.targets if is_chapter_label(t.label)), None)
                parts = [(chapter_target, raw)]
            for target, payload in parts:
                serial += 1
                src = work_dir / f"_epub_unit_{serial:05d}.xhtml"
                dst = work_dir / f"_epub_unit_{serial:05d}.md"
                try:
                    src.write_bytes(payload)
                    proc = subprocess.run(
                        [pandoc, str(src), "-f", "html", "-t", "gfm", "--wrap=none", "-o", str(dst)],
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                        timeout=_PANDOC_TIMEOUT,
                    )
                except (OSError, subprocess.SubprocessError):
                    continue
                if proc.returncode != 0 or not dst.exists():
                    continue
                try:
                    text = dst.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                label = target.label if target is not None else unit.label
                boundary = "epub_nav_anchor" if target is not None and is_chapter_label(target.label) else "epub_spine_fallback"
                out.append(ConvertedEpubUnit(label, text, boundary, unit.zip_path,
                                             target.fragment if target is not None else None))
                src.unlink(missing_ok=True)
                dst.unlink(missing_ok=True)
    return out


def convert_units_to_markdown(epub_path: Path, units: list[EpubUnit], pandoc: str,
                              work_dir: Path) -> list[tuple[str | None, str]]:
    """按 spine 顺序，把每个 spine 文档单独用 Pandoc `html -> gfm` 转换。

    返回有序 [(label, raw_markdown)]；单个文档缺失/转换失败按确定性跳过（不中断整体）。
    空/非内容单元的过滤由调用方按各自质量口径处理（本 helper 不虚构内容判断）。
    """
    return [(unit.label, unit.text) for unit in
            convert_units_with_boundaries(epub_path, units, pandoc, work_dir)]
