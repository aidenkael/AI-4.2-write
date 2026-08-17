# -*- coding: utf-8 -*-
"""EPUB-first 选源回归测试（SourcePrepare Phase 2B2 选源规则冻结）。

覆盖：
  A. EPUB PASS + TXT 字符明显更多 → 必须选择 EPUB
  B. 上述场景中 TXT converter 根本没有被调用
  C. EPUB FAIL → 自动 fallback TXT，TXT PASS 时成功选 TXT
  D. 单 EPUB PASS 行为不回归
  E. 没有 EPUB 时现有 TXT/PDF 行为不回归

全部用 monkeypatch 假转换器在 tmp_path 上运行，不碰真实素材 / 真实 git。
"""
import json
from pathlib import Path

import pytest

import source_prepare as sp


def _mk_cand(root: Path, ext: str, status: str, char_count: int,
             chapter_count: int, sha: str = "0" * 64) -> sp.Candidate:
    md = root / f"fake_{ext.lstrip('.')}.md"
    md.write_text("# 第一章\n正文内容\n# 第二章\n正文内容\n", encoding="utf-8")
    c = sp.Candidate(str(root / f"src{ext}"), ext, sha)
    c.status = status
    c.char_count = char_count
    c.chapter_count = chapter_count
    c.garbled = 0
    c.temp_md = str(md)
    return c


def _meta(tmp_path: Path, book_id: str = "book_0001") -> dict:
    p = tmp_path / "06_工作区" / "SourcePrepare" / f"{book_id}_Alpha" / "metadata.json"
    return json.loads(p.read_text(encoding="utf-8"))


# ---------- A. EPUB PASS + TXT 明显更长 → 必须选 EPUB ----------

def test_epub_pass_wins_over_longer_txt(tmp_path, monkeypatch):
    epub = _mk_cand(tmp_path, ".epub", "PASS", 5000, 5)
    txt = _mk_cand(tmp_path, ".txt", "PASS", 50000, 5)

    monkeypatch.setattr(sp, "convert_epub", lambda p, pandoc, work: epub)
    monkeypatch.setattr(sp, "convert_txt", lambda p, work: txt)
    monkeypatch.setattr(sp, "split_chapters", lambda text, out_dir: 5)

    files = [tmp_path / "src.epub", tmp_path / "src.txt"]
    out = sp.process_book(tmp_path, "Alpha", "REFERENCE_WORK", files,
                          "book_0001", "pandoc", False)
    assert out.startswith("PASS Alpha")
    meta = _meta(tmp_path)
    assert meta["selected_source"]["format"] == ".epub"
    assert meta["selected_source"]["char_count"] == 5000


# ---------- B. EPUB PASS 时 TXT converter 根本没有被调用 ----------

def test_txt_converter_not_called_when_epub_pass(tmp_path, monkeypatch):
    epub = _mk_cand(tmp_path, ".epub", "PASS", 5000, 5)
    txt = _mk_cand(tmp_path, ".txt", "PASS", 50000, 5)
    calls = {"txt": 0}

    def fake_epub(p, pandoc, work):
        return epub

    def fake_txt(p, work):
        calls["txt"] += 1
        return txt

    monkeypatch.setattr(sp, "convert_epub", fake_epub)
    monkeypatch.setattr(sp, "convert_txt", fake_txt)
    monkeypatch.setattr(sp, "split_chapters", lambda text, out_dir: 5)

    files = [tmp_path / "src.epub", tmp_path / "src.txt"]
    sp.process_book(tmp_path, "Alpha", "REFERENCE_WORK", files,
                    "book_0001", "pandoc", False)
    assert calls["txt"] == 0  # TXT 从未被读取/转换


# ---------- C. EPUB FAIL → fallback TXT，TXT PASS → 选 TXT ----------

def test_epub_fail_falls_back_to_txt(tmp_path, monkeypatch):
    epub = _mk_cand(tmp_path, ".epub", "FAIL", 0, 0)
    epub.temp_md = None  # FAIL：无 temp_md
    txt = _mk_cand(tmp_path, ".txt", "PASS", 20000, 5)

    monkeypatch.setattr(sp, "convert_epub", lambda p, pandoc, work: epub)
    monkeypatch.setattr(sp, "convert_txt", lambda p, work: txt)
    monkeypatch.setattr(sp, "split_chapters", lambda text, out_dir: 5)

    files = [tmp_path / "src.epub", tmp_path / "src.txt"]
    out = sp.process_book(tmp_path, "Alpha", "REFERENCE_WORK", files,
                          "book_0001", "pandoc", False)
    assert out.startswith("PASS Alpha")
    meta = _meta(tmp_path)
    assert meta["selected_source"]["format"] == ".txt"
    assert meta["selected_source"]["char_count"] == 20000


# ---------- D. 单 EPUB PASS 行为不回归 ----------

def test_single_epub_pass_no_regression(tmp_path, monkeypatch):
    epub = _mk_cand(tmp_path, ".epub", "PASS", 8000, 5)

    monkeypatch.setattr(sp, "convert_epub", lambda p, pandoc, work: epub)
    monkeypatch.setattr(sp, "split_chapters", lambda text, out_dir: 5)

    files = [tmp_path / "src.epub"]
    out = sp.process_book(tmp_path, "Alpha", "REFERENCE_WORK", files,
                          "book_0001", "pandoc", False)
    assert out.startswith("PASS Alpha")
    meta = _meta(tmp_path)
    assert meta["selected_source"]["format"] == ".epub"
    assert meta["selected_source"]["char_count"] == 8000


# ---------- E. 没有 EPUB 时现有 TXT/PDF 行为不回归 ----------

def test_no_epub_txt_pdf_unchanged(tmp_path, monkeypatch):
    txt = _mk_cand(tmp_path, ".txt", "PASS", 10000, 5)
    pdf = _mk_cand(tmp_path, ".pdf", "PASS", 8000, 5)  # 长度接近，避免触发跨来源 REVIEW

    monkeypatch.setattr(sp, "convert_txt", lambda p, work: txt)
    monkeypatch.setattr(sp, "convert_pdf", lambda p, work: pdf)
    monkeypatch.setattr(sp, "split_chapters", lambda text, out_dir: 5)

    files = [tmp_path / "src.txt", tmp_path / "src.pdf"]
    out = sp.process_book(tmp_path, "Alpha", "REFERENCE_WORK", files,
                          "book_0001", "pandoc", False)
    assert out.startswith("PASS Alpha")
    meta = _meta(tmp_path)
    # 无 EPUB：仍按现有“完整性(字符数降)”选优 → 更长的 TXT 胜出
    assert meta["selected_source"]["format"] == ".txt"
    assert meta["selected_source"]["char_count"] == 10000


# ---------- F. 单 EPUB 正文正常 + 0 章 → REVIEW（不是 FAIL），full.md 必须存在 ----------

def test_single_epub_review_zero_chapters_is_review_not_fail(tmp_path, monkeypatch):
    epub = _mk_cand(tmp_path, ".epub", "REVIEW", 50000, 0)  # 正文可用，仅章节未识别

    monkeypatch.setattr(sp, "convert_epub", lambda p, pandoc, work: epub)
    monkeypatch.setattr(sp, "split_chapters", lambda text, out_dir: 0)

    files = [tmp_path / "src.epub"]
    out = sp.process_book(tmp_path, "Alpha", "REFERENCE_WORK", files,
                          "book_0001", "pandoc", False)
    assert out.startswith("REVIEW Alpha")
    meta = _meta(tmp_path)
    assert meta["status"] == "REVIEW"
    assert meta["selected_source"]["format"] == ".epub"
    # 正文可用 → full.md 必须保留
    full = tmp_path / "06_工作区" / "SourcePrepare" / "book_0001_Alpha" / "full.md"
    assert full.exists()


# ---------- G. EPUB 关键结构失败 → 仍 FAIL ----------

def test_single_epub_critical_structure_fail_still_fail(tmp_path, monkeypatch):
    epub = _mk_cand(tmp_path, ".epub", "FAIL", 0, 0)
    epub.temp_md = None  # 关键结构失败：无可用转换输出

    monkeypatch.setattr(sp, "convert_epub", lambda p, pandoc, work: epub)
    monkeypatch.setattr(sp, "split_chapters", lambda text, out_dir: 0)

    files = [tmp_path / "src.epub"]
    out = sp.process_book(tmp_path, "Alpha", "REFERENCE_WORK", files,
                          "book_0001", "pandoc", False)
    assert out.startswith("FAIL Alpha")
    meta = _meta(tmp_path)
    assert meta["status"] == "FAIL"
    full = tmp_path / "06_工作区" / "SourcePrepare" / "book_0001_Alpha" / "full.md"
    assert not full.exists()


# ---------- H. Pandoc 转换失败（无输出）→ 仍 FAIL ----------

def test_single_epub_pandoc_failure_still_fail(tmp_path, monkeypatch):
    epub = _mk_cand(tmp_path, ".epub", "FAIL", 0, 0)
    epub.temp_md = None  # Pandoc 失败：无 temp_md

    monkeypatch.setattr(sp, "convert_epub", lambda p, pandoc, work: epub)
    monkeypatch.setattr(sp, "split_chapters", lambda text, out_dir: 0)

    files = [tmp_path / "src.epub"]
    out = sp.process_book(tmp_path, "Alpha", "REFERENCE_WORK", files,
                          "book_0001", "pandoc", False)
    assert out.startswith("FAIL Alpha")


# ---------- I. 正文低于质量阈值 → 仍 FAIL（即使有 temp_md） ----------

def test_single_epub_low_chars_still_fail(tmp_path, monkeypatch):
    epub = _mk_cand(tmp_path, ".epub", "FAIL", 1000, 3)  # 正文过少 → 判定 FAIL

    monkeypatch.setattr(sp, "convert_epub", lambda p, pandoc, work: epub)
    monkeypatch.setattr(sp, "split_chapters", lambda text, out_dir: 0)

    files = [tmp_path / "src.epub"]
    out = sp.process_book(tmp_path, "Alpha", "REFERENCE_WORK", files,
                          "book_0001", "pandoc", False)
    assert out.startswith("FAIL Alpha")
    meta = _meta(tmp_path)
    assert meta["status"] == "FAIL"


# ---------- J. EPUB-first / fallback 不回归：EPUB REVIEW + TXT PASS → 仍 fallback 选 TXT ----------

def test_epub_review_falls_back_to_txt_not_regressed(tmp_path, monkeypatch):
    epub = _mk_cand(tmp_path, ".epub", "REVIEW", 50000, 0)
    txt = _mk_cand(tmp_path, ".txt", "PASS", 20000, 5)

    monkeypatch.setattr(sp, "convert_epub", lambda p, pandoc, work: epub)
    monkeypatch.setattr(sp, "convert_txt", lambda p, work: txt)
    monkeypatch.setattr(sp, "split_chapters", lambda text, out_dir: 5)

    files = [tmp_path / "src.epub", tmp_path / "src.txt"]
    out = sp.process_book(tmp_path, "Alpha", "REFERENCE_WORK", files,
                          "book_0001", "pandoc", False)
    assert out.startswith("PASS Alpha")
    meta = _meta(tmp_path)
    assert meta["selected_source"]["format"] == ".txt"
