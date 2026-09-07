# -*- coding: utf-8 -*-
"""MethodPrepare 确定性预处理测试（tmp_path fixture；无模型、无真实数据依赖）。

覆盖验收：
  - 来源文件保持字节不变（只读）；
  - 同输入重复运行产物逐字节一致（确定性）；
  - 稳定节 id / 顺序 / 父级（真实已知时）；
  - 标题/列表/编号步骤存在时被保留；
  - 绝不虚构层级：无标题 → 线性保留 + 限制标注 + REVIEW；
  - sections/S####.md 行号稳定、可证据寻址；
  - 坏/不支持/结构不可靠输入 → REVIEW/FAIL，绝不假 PASS。
"""
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import method_prepare as mp  # noqa: E402

_SKILLS_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_SKILLS_ROOT / "MaterialIntake"))
import catalog  # noqa: E402

_REPO = Path(__file__).resolve().parents[4]
_REAL_PANDOC = _REPO / "05_Skills与自动化" / "pandoc" / ("pandoc.exe" if os.name == "nt" else "pandoc")


def _method_epub_bytes(n: int = 3) -> bytes:
    """构造最小合法方法 EPUB：章节标题用 <p class="title"> 而非 <h1>，
    因此 Pandoc 合成 Markdown 无 ATX # 标题（旧逻辑会因 linear_no_heading 误判 REVIEW）。"""
    import io
    import zipfile
    buf = io.BytesIO()
    container = ('<?xml version="1.0"?><container version="1.0" '
                 'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<rootfiles><rootfile full-path="content.opf" '
                 'media-type="application/oebps-package+xml"/></rootfiles></container>')
    items = "".join(f'<item id="s{i}" href="s{i}.xhtml" media-type="application/xhtml+xml"/>'
                    for i in range(1, n + 1))
    refs = "".join(f'<itemref idref="s{i}"/>' for i in range(1, n + 1))
    opf = ('<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" '
           'version="2.0" unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
           '<dc:title>Method</dc:title><dc:creator>Author</dc:creator>'
           '<dc:identifier id="id">mid</dc:identifier><dc:language>en</dc:language></metadata>'
           f'<manifest>{items}<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/></manifest>'
           f'<spine toc="ncx">{refs}</spine></package>')
    navpoints = "".join(
        f'<navPoint id="np{i}" playOrder="{i}"><navLabel><text>Method {i}</text></navLabel>'
        f'<content src="s{i}.xhtml"/></navPoint>' for i in range(1, n + 1))
    ncx = ('<?xml version="1.0" encoding="utf-8"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" '
           'version="2005-1"><head><meta name="dtb:uid" content="mid"/></head>'
           f'<docTitle><text>Method</text></docTitle><navMap>{navpoints}</navMap></ncx>')
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml', container)
        z.writestr('content.opf', opf)
        for i in range(1, n + 1):
            body = (f'<p class="title">Method {i}</p>'
                    + '<p>Method guidance text long enough to count as visible content. </p>' * 20)
            z.writestr(f's{i}.xhtml', (
                '<?xml version="1.0" encoding="utf-8"?><!DOCTYPE html>'
                '<html xmlns="http://www.w3.org/1999/xhtml"><head>'
                f'<title>s{i}</title></head><body>{body}</body></html>').encode('utf-8'))
        z.writestr('toc.ncx', ncx.encode('utf-8'))
    return buf.getvalue()


HEADINGS_TXT = """# 第一章 开场的方法

开场必须先给读者一个可跟随的问题。问题的具体化程度决定了读者愿意投入的耐心，
作者应当把抽象的主题落到一个可以被看见、被听见、被触摸的场景里，
让读者在第一页就获得一个可以跟随的行动线索，而不是获得一段解释。
""" + ("场景要先于解释出现，行动要先于定义出现，具体细节要先于抽象判断出现。" * 4) + """

## 1.1 步骤

1. 找到主角的具体困境
2. 把困境放进第一个场景
- 不要在旁白里解释
- 让行动自己说话
- 每一场都留下一个未完成的动作，让读者带着它进入下一场

> 示例：暴雨夜的来信。信的内容只给一半，另一半留给下一场。

# 第二章 章末钩子

章末钩子应落在行动或决定上，而不是情绪总结上。读者需要的是一个未完成的问题，
而不是一段已经完成的感慨；钩子的强度来自下一场必须发生的理由是否充分。
"""

FLAT_TXT = "这是一段完全没有标题的方法文字。它只按线性顺序排列，没有可靠的结构。" * 10


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _make_repo(tmp_path: Path, name: str, filename: str, content: bytes,
               asset_id="book_9101", asset_type="METHOD_SOURCE") -> tuple[Path, str]:
    root = tmp_path
    mat = root / catalog.MATERIAL_DIR_NAME
    asset_dir = mat / "02_研究资料" / name
    asset_dir.mkdir(parents=True)
    src = asset_dir / filename
    src.write_bytes(content)
    sha = _sha(content)
    ledger = {
        "schema_version": "1.0",
        "assets": [{
            "id": asset_id, "name": name, "type": asset_type, "author": "",
            "tags": [], "notes": "",
            "files": [{"path": f"02_研究资料/{name}/{filename}", "sha256": sha, "primary": True}],
            "purification": {"status": "未处理", "evidence": None},
            "knowledge": {"status": "未开始"},
        }],
        "containers": [],
    }
    catalog.write_ledger(ledger, mat / catalog.LEDGER_FILENAME)
    return root, sha


def _run(root: Path, asset_id="book_9101") -> dict:
    return mp.prepare_asset(root, asset_id)


def _out_dir(root: Path, name="方法书") -> Path:
    return root / "06_工作区" / "MethodPrepare" / f"book_9101_{name}"


def _read_outputs(out: Path) -> dict[str, bytes]:
    files = {}
    for p in sorted(out.rglob("*")):
        if p.is_file():
            files[p.relative_to(out).as_posix()] = p.read_bytes()
    return files


# ---------- PASS：标题结构、列表/步骤保留、行稳定 ----------

def test_txt_with_headings_pass_preserves_structure(tmp_path):
    content = HEADINGS_TXT.encode("utf-8")
    root, sha = _make_repo(tmp_path, "方法书", "方法书.txt", content)
    before = (root / catalog.MATERIAL_DIR_NAME / "02_研究资料" / "方法书" / "方法书.txt").read_bytes()

    result = _run(root)
    assert result["status"] == "PASS", result

    out = _out_dir(root)
    meta = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
    assert meta["asset_id"] == "book_9101"
    assert meta["selected_source"]["sha256"] == sha
    assert meta["parser"].startswith("txt:")
    assert meta["section_count"] >= 3
    assert meta["limitations"] == []

    structure = json.loads((out / "structure.json").read_text(encoding="utf-8"))
    assert structure["heading_structure_known"] is True
    sections = structure["sections"]
    # 稳定节 id 与顺序
    assert [s["id"] for s in sections] == [f"S{i:04d}" for i in range(1, len(sections) + 1)]
    assert [s["order"] for s in sections] == list(range(1, len(sections) + 1))
    # 父级只在真实已知时给出：二级标题挂在一级标题下
    s2 = next(s for s in sections if s["title"] == "1.1 步骤")
    assert s2["level"] == 2
    assert s2["parent"] == "S0001"

    # 标题/列表/编号步骤/引用块原样保留（逐字包含）
    full = (out / "full.md").read_text(encoding="utf-8")
    for fragment in ("# 第一章 开场的方法", "## 1.1 步骤", "1. 找到主角的具体困境",
                     "- 不要在旁白里解释", "> 示例：暴雨夜的来信。", "# 第二章 章末钩子"):
        assert fragment in full

    # 证据寻址：sections 文件行号与 full.md 对应行一致
    for sec in sections:
        sec_lines = (out / sec["file"]).read_text(encoding="utf-8").split("\n")
        full_lines = full.split("\n")
        start = sec["start_line"] - 1
        assert sec_lines[:sec["line_count"]] == full_lines[start:start + sec["line_count"]], sec["id"]

    # 来源文件保持字节不变（只读）
    after = (root / catalog.MATERIAL_DIR_NAME / "02_研究资料" / "方法书" / "方法书.txt").read_bytes()
    assert before == after


def test_deterministic_repeated_output(tmp_path):
    content = HEADINGS_TXT.encode("utf-8")
    root, _ = _make_repo(tmp_path, "方法书", "方法书.txt", content)
    _run(root)
    first = _read_outputs(_out_dir(root))
    _run(root)
    second = _read_outputs(_out_dir(root))
    assert first == second, "同输入重复运行必须逐字节一致"


def test_markdown_source_passthrough_pass(tmp_path):
    content = ("# 方法\n\n" + "方法正文要足够长才能通过可见内容检查，这里反复写一些内容。" * 8 +
               "\n\n- 步骤 A\n- 步骤 B\n").encode("utf-8")
    root, _ = _make_repo(tmp_path, "方法书", "方法书.md", content)
    result = _run(root)
    assert result["status"] == "PASS"
    meta = json.loads((_out_dir(root) / "metadata.json").read_text(encoding="utf-8"))
    assert meta["parser"].startswith("md:")


# ---------- REVIEW：结构不可靠时绝不虚构层级 / 绝不假 PASS ----------

def test_txt_without_headings_review_not_fake_pass(tmp_path):
    root, _ = _make_repo(tmp_path, "方法书", "方法书.txt", FLAT_TXT.encode("utf-8"))
    result = _run(root)
    assert result["status"] == "REVIEW"
    out = _out_dir(root)
    meta = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
    assert "linear_no_heading" in meta["limitations"]
    structure = json.loads((out / "structure.json").read_text(encoding="utf-8"))
    assert structure["heading_structure_known"] is False
    # 线性内容仍完整保留（单个线性节）
    assert structure["section_count"] == 1
    full = (out / "full.md").read_text(encoding="utf-8")
    assert "这是一段完全没有标题的方法文字" in full


def test_unsupported_format_review_not_fake_pass(tmp_path):
    root, _ = _make_repo(tmp_path, "方法书", "方法书.zip", b"PK\x03\x04 not a real zip")
    result = _run(root)
    assert result["status"] == "REVIEW"
    meta = json.loads((_out_dir(root) / "metadata.json").read_text(encoding="utf-8"))
    assert any(lim.startswith("no_supported_source") for lim in meta["limitations"])


def test_undecodable_txt_review_not_fake_pass(tmp_path):
    root, _ = _make_repo(tmp_path, "方法书", "方法书.txt", b"\x00\x01\x02\x03" * 100)
    result = _run(root)
    assert result["status"] == "REVIEW"


def test_empty_content_review_not_fake_pass(tmp_path):
    root, _ = _make_repo(tmp_path, "方法书", "方法书.txt", b"")
    result = _run(root)
    assert result["status"] == "REVIEW"
    meta = json.loads((_out_dir(root) / "metadata.json").read_text(encoding="utf-8"))
    assert any("too_few_visible_chars" in lim for lim in meta["limitations"])


def test_sha_mismatch_rejected(tmp_path):
    root, _ = _make_repo(tmp_path, "方法书", "方法书.txt", HEADINGS_TXT.encode("utf-8"))
    # 台账之外篡改来源文件 → SHA 不一致 → 拒绝（不产出任何假结果）
    src = root / catalog.MATERIAL_DIR_NAME / "02_研究资料" / "方法书" / "方法书.txt"
    src.write_bytes(b"tampered")
    with pytest.raises(mp.MethodPrepareError):
        _run(root)


def test_non_method_source_rejected(tmp_path):
    root, _ = _make_repo(tmp_path, "参考小说", "参考小说.txt", HEADINGS_TXT.encode("utf-8"),
                         asset_type="REFERENCE_WORK")
    with pytest.raises(mp.MethodPrepareError):
        _run(root)


def test_missing_asset_rejected(tmp_path):
    root, _ = _make_repo(tmp_path, "方法书", "方法书.txt", b"x")
    with pytest.raises(mp.MethodPrepareError):
        _run(root, asset_id="book_9999")


# ---------- §8：EPUB 原生结构（OPF spine + nav/NCX）优先，ATX 标题只是兜底 ----------

def test_epub_native_structure_produces_sections_and_pass(tmp_path, monkeypatch):
    """§8/§15：有效 EPUB 原生结构但合成 MD 无 ATX 标题 → 产出分节并可 PASS（不再误判 REVIEW）。"""
    if not _REAL_PANDOC.exists():
        pytest.skip("pandoc not available")
    monkeypatch.setattr(mp, "find_pandoc", lambda root: str(_REAL_PANDOC))
    root, sha = _make_repo(tmp_path, "方法书", "方法书.epub", _method_epub_bytes(n=3))
    result = _run(root)
    assert result["status"] == "PASS", result
    assert result["section_count"] >= 3
    out = _out_dir(root)
    meta = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
    assert meta["parser"] == "epub:native-spine+nav"
    assert meta["selected_source"]["sha256"] == sha
    assert meta["section_count"] >= 3
    assert "linear_no_heading" not in meta["limitations"]
    structure = json.loads((out / "structure.json").read_text(encoding="utf-8"))
    assert structure["heading_structure_known"] is True
    secs = list((out / "sections").glob("S*.md"))
    assert len(secs) == meta["section_count"], "sections/ 非空且与 metadata 一致"
    # 行稳定：sections 文件行与 full.md 对应行一致
    full = (out / "full.md").read_text(encoding="utf-8")
    assert full.strip()
    full_lines = full.split("\n")
    for sec in structure["sections"]:
        sec_lines = (out / sec["file"]).read_text(encoding="utf-8").split("\n")
        start = sec["start_line"] - 1
        assert sec_lines[:sec["line_count"]] == full_lines[start:start + sec["line_count"]], sec["id"]


def test_epub_native_deterministic_repeated_output(tmp_path, monkeypatch):
    """§8：EPUB 原生结构分节同输入重复运行逐字节一致（确定性）。"""
    if not _REAL_PANDOC.exists():
        pytest.skip("pandoc not available")
    monkeypatch.setattr(mp, "find_pandoc", lambda root: str(_REAL_PANDOC))
    root, _ = _make_repo(tmp_path, "方法书", "方法书.epub", _method_epub_bytes(n=3))
    _run(root)
    first = _read_outputs(_out_dir(root))
    _run(root)
    second = _read_outputs(_out_dir(root))
    assert first == second, "同输入重复运行必须逐字节一致"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
