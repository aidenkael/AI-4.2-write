#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BookDistill v0.1 单元测试（纯标准库 unittest，不依赖真实输入）。

用临时目录构造最小假 PASS 包，覆盖：
- validate：PASS 通过 / 非 PASS 拒绝 / 缺文件拒绝 / 章节数不一致拒绝 / 差 1 可接受
- prepare：生成章节索引 + 证据模板
- assemble：合法证据通过 / 非法分类拒绝 / 非法引用拒绝 / 缺引用拒绝
"""

import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import book_distill as bd


def make_fake_pass_pkg(root: Path, status="PASS", chapter_files=2, with_preamble=True) -> Path:
    """构造最小假 PASS 包：metadata.json / conversion_report.md / full.md / chapters/。"""
    sp = root / "sp_book"
    chapters = sp / "chapters"
    chapters.mkdir(parents=True, exist_ok=True)

    meta = {
        "skill_version": "0.2.1",
        "book_id": "book_0001",
        "book": "测试之书",
        "category": "外国文学",
        "status": status,
        "selected_source": {
            "path": "E:/fake/book.epub",
            "format": ".epub",
            "sha256": "a" * 64,
            "char_count": 1000,
        },
        "chapter_files": chapter_files,
        "cross_source_warnings": [],
        "candidates": [],
    }
    (sp / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    (sp / "conversion_report.md").write_text("# 报告\n状态: PASS\n", encoding="utf-8")
    (sp / "full.md").write_text("全书正文。\n", encoding="utf-8")

    if with_preamble:
        (chapters / "0000_前置内容.md").write_text("版权页与目录。\n", encoding="utf-8")
    for i in range(1, chapter_files + 1):
        fname = f"{i:04d}.md"
        (chapters / fname).write_text(
            f"> 第{i}章\n\n这是第{i}章的正文内容，足够长以通过空章节检查。\n",
            encoding="utf-8",
        )
    return sp


class ValidateTest(unittest.TestCase):
    def test_pass_pkg_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp))
            r = bd.validate_input(sp)
            self.assertTrue(r["ok"], r["errors"])
            self.assertEqual(r["info"]["status"], "PASS")
            self.assertEqual(r["info"]["chapter_files_on_disk"], 2)

    def test_non_pass_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp), status="REVIEW")
            r = bd.validate_input(sp)
            self.assertFalse(r["ok"])
            self.assertTrue(any("不是 PASS" in e for e in r["errors"]))

    def test_missing_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp))
            (sp / "full.md").unlink()
            r = bd.validate_input(sp)
            self.assertFalse(r["ok"])
            self.assertTrue(any("full.md" in e for e in r["errors"]))

    def test_missing_chapters_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp))
            import shutil
            shutil.rmtree(sp / "chapters")
            r = bd.validate_input(sp)
            self.assertFalse(r["ok"])
            self.assertTrue(any("chapters" in e for e in r["errors"]))

    def test_chapter_count_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp), chapter_files=2)  # 声称 2 章
            # 额外添加 2 个文件，磁盘 4 vs meta 2 = 差 2 → 不一致
            (sp / "chapters" / "0003.md").write_text("第三个文件。\n", encoding="utf-8")
            (sp / "chapters" / "0004.md").write_text("第四个文件。\n", encoding="utf-8")
            r = bd.validate_input(sp)
            self.assertFalse(r["ok"])
            self.assertTrue(any("不一致" in e for e in r["errors"]))

    def test_preamble_diff_one_acceptable(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp), chapter_files=3, with_preamble=True)
            # 磁盘正文章节 2（删掉 0003）+ 0000 前置，meta 声称 3 → 差 1 应产生警告而非错误
            (sp / "chapters" / "0003.md").unlink()
            r = bd.validate_input(sp)
            self.assertTrue(r["ok"], r["errors"])
            self.assertTrue(any("差 1" in w for w in r["warnings"]))

    def test_missing_sha256_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp))
            meta = json.loads((sp / "metadata.json").read_text(encoding="utf-8"))
            del meta["selected_source"]["sha256"]
            (sp / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            r = bd.validate_input(sp)
            self.assertFalse(r["ok"])
            self.assertTrue(any("sha256" in e for e in r["errors"]))


class PrepareTest(unittest.TestCase):
    def test_prepare_creates_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp))
            out = Path(tmp) / "out"
            rc = bd.cmd_prepare(
                type("A", (), {"input": str(sp), "output": str(out)})()
            )
            self.assertEqual(rc, 0)
            self.assertTrue((out / "chapters_index.md").exists())
            self.assertTrue((out / "bd_report.md").exists())
            ev = out / "evidence"
            self.assertTrue((ev / "ch_0001.md").exists())
            self.assertTrue((ev / "ch_0002.md").exists())
            # 前置内容不应生成证据模板
            self.assertFalse(list(ev.glob("ch_0000*.md")))

    def test_prepare_rejects_bad_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp), status="FAIL")
            out = Path(tmp) / "out"
            rc = bd.cmd_prepare(type("A", (), {"input": str(sp), "output": str(out)})())
            self.assertEqual(rc, 1)
            self.assertFalse(out.exists())


class AssembleTest(unittest.TestCase):
    def _prepared(self, tmp: Path):
        sp = make_fake_pass_pkg(Path(tmp))
        out = Path(tmp) / "out"
        bd.cmd_prepare(type("A", (), {"input": str(sp), "output": str(out)})())
        return sp, out

    def _fill(self, ev_path: Path, lines: list[str]):
        text = ev_path.read_text(encoding="utf-8")
        # 在 FACT 节标题后插入条目
        text = text.replace(
            "## FACT（原文事实）\n\n",
            "## FACT（原文事实）\n\n" + "\n".join(lines) + "\n\n",
            1,
        )
        ev_path.write_text(text, encoding="utf-8")

    def test_assemble_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(Path(tmp))
            ev = out / "evidence" / "ch_0001.md"
            self._fill(ev, [
                "- [FACT] 第1章正文存在｜证据：chapters/0001.md#L3｜置信度：高",
                "- [MECHANISM] 章首引用标题｜证据：chapters/0001.md#L1-L1｜置信度：中",
            ])
            m = bd.assemble(out)
            self.assertTrue(m["ok"], m["errors"])
            self.assertEqual(m["stats_by_kind"]["FACT"], 1)
            self.assertEqual(m["stats_by_kind"]["MECHANISM"], 1)

    def test_assemble_invalid_kind_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(Path(tmp))
            ev = out / "evidence" / "ch_0001.md"
            self._fill(ev, [
                "- [OPINION] 这是非法分类｜证据：chapters/0001.md#L3｜置信度：高",
            ])
            m = bd.assemble(out)
            self.assertFalse(m["ok"])
            self.assertTrue(any("非法分类" in e for e in m["errors"]))

    def test_assemble_bad_ref_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(Path(tmp))
            ev = out / "evidence" / "ch_0001.md"
            self._fill(ev, [
                "- [FACT] 引用不存在章节｜证据：chapters/9999.md#L3｜置信度：高",
            ])
            m = bd.assemble(out)
            self.assertFalse(m["ok"])
            self.assertTrue(any("不存在的章节文件" in e for e in m["errors"]))

    def test_assemble_missing_ref_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(Path(tmp))
            ev = out / "evidence" / "ch_0001.md"
            self._fill(ev, [
                "- [FACT] 缺少引用字段",
            ])
            m = bd.assemble(out)
            self.assertFalse(m["ok"])
            self.assertTrue(any("缺少'证据：'引用" in e for e in m["errors"]))


if __name__ == "__main__":
    unittest.main()
