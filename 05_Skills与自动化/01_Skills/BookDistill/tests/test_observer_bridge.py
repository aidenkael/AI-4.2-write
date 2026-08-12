#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Observer bridge tests (stdlib unittest)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import book_distill as bd
import observer_bridge as ob


def make_fake_pass_pkg(root: Path, chapter_files: int = 2) -> Path:
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
            "sha256": "a" * 64,
        },
        "chapter_files": chapter_files,
    }
    (sp / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )
    (sp / "conversion_report.md").write_text("# PASS\n", encoding="utf-8")
    (sp / "full.md").write_text("全书正文。\n", encoding="utf-8")
    for i in range(1, chapter_files + 1):
        (chapters / f"{i:04d}.md").write_text(
            f"> 第{i}章\n\n第一行正文。\n第二行正文。\n第三行正文。\n",
            encoding="utf-8",
        )
    return sp


class ObserverBridgeTests(unittest.TestCase):
    def test_init_creates_two_observer_workspaces(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sp = make_fake_pass_pkg(root)
            out = root / "out"
            bd.prepare(sp, out)

            result = ob.init_workspace(sp, out)
            self.assertTrue(result["ok"])
            self.assertEqual(result["chapter_count"], 2)
            for observer_id in ob.OBSERVER_IDS:
                self.assertTrue(
                    (out / "discovery" / observer_id / "observer_manifest.json").exists()
                )
                self.assertTrue(
                    (out / "discovery" / observer_id / "chapters" / "ch_0001.md").exists()
                )
                self.assertTrue(
                    (out / "discovery" / observer_id / "synthesis.md").exists()
                )

    def test_validate_requires_observer_tag(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sp = make_fake_pass_pkg(root)
            out = root / "out"
            bd.prepare(sp, out)
            ob.init_workspace(sp, out)

            path = out / "discovery" / "longform_reader_dynamics" / "chapters" / "ch_0001.md"
            text = path.read_text(encoding="utf-8")
            text = text.replace(
                "## OBSERVATION\n",
                "## OBSERVATION\n\n"
                "- [OBSERVATION] dimension:节奏 | 缺少 observer 标签"
                "｜证据：chapters/0001.md#L3-L4｜置信度：高\n",
            )
            path.write_text(text, encoding="utf-8")

            result = ob.validate_observer(sp, out, "longform_reader_dynamics")
            self.assertFalse(result["ok"])
            self.assertTrue(any("缺少 observer" in err for err in result["errors"]))

    def test_inference_and_boundary_tags_are_valid(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sp = make_fake_pass_pkg(root)
            out = root / "out"
            bd.prepare(sp, out)
            ob.init_workspace(sp, out)

            observer_id = "reader_page_craft"
            path = out / "discovery" / observer_id / "chapters" / "ch_0001.md"
            text = path.read_text(encoding="utf-8")
            inference = (
                f"- [INFERENCE] observer:{observer_id} | 这里可能通过省略增强读者参与"
                "｜证据：chapters/0001.md#L3-L4｜置信度：中"
            )
            boundary = (
                f"- [BOUNDARY] observer:{observer_id} | 该判断高度依赖前文语境"
                "｜证据：chapters/0001.md#L3-L4｜置信度：高"
            )
            text = text.replace("## INFERENCE\n", f"## INFERENCE\n\n{inference}\n")
            text = text.replace("## BOUNDARY\n", f"## BOUNDARY\n\n{boundary}\n")
            path.write_text(text, encoding="utf-8")

            result = ob.validate_observer(sp, out, observer_id)
            self.assertTrue(result["ok"], result["errors"])
            self.assertEqual(result["stats"]["INFERENCE"], 1)
            self.assertEqual(result["stats"]["BOUNDARY"], 1)

    def test_merge_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sp = make_fake_pass_pkg(root)
            out = root / "out"
            bd.prepare(sp, out)
            ob.init_workspace(sp, out)

            observer_id = "longform_reader_dynamics"
            path = out / "discovery" / observer_id / "chapters" / "ch_0001.md"
            text = path.read_text(encoding="utf-8")
            line = (
                f"- [OBSERVATION] dimension:信息控制 | observer:{observer_id} | "
                "先制造问题再给局部答案｜证据：chapters/0001.md#L3-L4｜置信度：高"
            )
            text = text.replace("## OBSERVATION\n", f"## OBSERVATION\n\n{line}\n")
            path.write_text(text, encoding="utf-8")

            first = ob.merge_observers(sp, out, [observer_id])
            second = ob.merge_observers(sp, out, [observer_id])
            self.assertTrue(first["ok"])
            self.assertEqual(first["merged"], 1)
            self.assertTrue(second["ok"])
            self.assertEqual(second["merged"], 0)

            canonical = (out / "evidence" / "ch_0001.md").read_text(encoding="utf-8")
            self.assertEqual(canonical.count(line), 1)

    def test_validate_rejects_cross_chapter_ref(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sp = make_fake_pass_pkg(root)
            out = root / "out"
            bd.prepare(sp, out)
            ob.init_workspace(sp, out)

            observer_id = "reader_page_craft"
            path = out / "discovery" / observer_id / "chapters" / "ch_0001.md"
            text = path.read_text(encoding="utf-8")
            line = (
                f"- [OBSERVATION] dimension:Reader Experience | observer:{observer_id} | "
                "跨章错引｜证据：chapters/0002.md#L3-L4｜置信度：中"
            )
            text = text.replace("## OBSERVATION\n", f"## OBSERVATION\n\n{line}\n")
            path.write_text(text, encoding="utf-8")

            result = ob.validate_observer(sp, out, observer_id)
            self.assertFalse(result["ok"])
            self.assertTrue(any("只能引用同章原文" in err for err in result["errors"]))


if __name__ == "__main__":
    unittest.main()
