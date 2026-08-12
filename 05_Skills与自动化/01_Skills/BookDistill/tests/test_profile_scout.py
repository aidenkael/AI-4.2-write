#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BookProfile Scout tests (stdlib unittest)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import profile_scout as ps


def make_fake_pass_pkg(root: Path, chapter_files: int = 20) -> Path:
    sp = root / "book_0001_测试之书"
    chapters = sp / "chapters"
    chapters.mkdir(parents=True, exist_ok=True)
    meta = {
        "skill_version": "0.2.1",
        "book_id": "book_0001",
        "book": "测试之书",
        "status": "PASS",
        "selected_source": {
            "path": "E:/fake/book.epub",
            "format": ".epub",
            "sha256": "b" * 64,
        },
        "chapter_files": chapter_files,
    }
    (sp / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    (sp / "conversion_report.md").write_text("# PASS\n", encoding="utf-8")
    (sp / "full.md").write_text("全书正文。\n", encoding="utf-8")
    for i in range(1, chapter_files + 1):
        (chapters / f"{i:04d}.md").write_text(
            f"> 第{i}章\n\n这是第{i}章正文，足够长以通过校验。\n第二行。\n第三行。\n",
            encoding="utf-8",
        )
    return sp


class ProfileScoutTests(unittest.TestCase):
    def test_short_book_uses_all_chapters(self):
        entries = [{"file": f"{i:04d}.md"} for i in range(1, 7)]
        anchors = ps.select_anchor_chapters(entries)
        self.assertEqual([item["file"] for item in anchors], [item["file"] for item in entries])

    def test_long_book_uses_stratified_anchors(self):
        entries = [{"file": f"{i:04d}.md"} for i in range(1, 21)]
        anchors = [item["file"] for item in ps.select_anchor_chapters(entries)]
        self.assertEqual(anchors[:3], ["0001.md", "0002.md", "0003.md"])
        self.assertEqual(anchors[-3:], ["0018.md", "0019.md", "0020.md"])
        self.assertIn("0011.md", anchors)
        self.assertEqual(len(anchors), len(set(anchors)))

    def test_init_is_non_destructive_and_validate_detects_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sp = make_fake_pass_pkg(root)
            out = root / "out"

            first = ps.init_profile(sp, out)
            self.assertTrue(first["ok"])
            self.assertTrue(first["created"])
            profile = out / ps.PROFILE_FILE
            original = profile.read_text(encoding="utf-8")
            self.assertIn("HYPOTHESIS / NAVIGATION ONLY", original)
            self.assertIn("## Discovery 建议重点", original)

            profile.write_text(original + "\n人工补充。\n", encoding="utf-8")
            second = ps.init_profile(sp, out)
            self.assertTrue(second["ok"])
            self.assertFalse(second["created"])
            self.assertIn("人工补充。", profile.read_text(encoding="utf-8"))

            valid = ps.validate_profile(sp, out)
            self.assertTrue(valid["ok"])

            meta_path = sp / "metadata.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["selected_source"]["sha256"] = "c" * 64
            meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            invalid = ps.validate_profile(sp, out)
            self.assertFalse(invalid["ok"])
            self.assertTrue(any("source_sha256" in err for err in invalid["errors"]))


if __name__ == "__main__":
    unittest.main()
