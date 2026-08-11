#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BookDistill v0.1 单元测试（纯标准库 unittest，不依赖真实输入）。

用临时目录构造最小假 PASS 包，覆盖：
- validate：PASS 通过 / 非 PASS 拒绝 / 缺文件拒绝 / 章节数不一致（含差 1）拒绝
- validate：book_id 与目录前缀一致 / 不一致拒绝 / 章节内容 fingerprint 记录
- prepare：生成章节索引 + 证据模板
- assemble：合法证据通过 / 非法分类拒绝 / 非法引用拒绝 / 缺引用拒绝
- assemble --input：source snapshot 一致通过 / fingerprint 变更拒绝 / 行号越界拒绝
"""

import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import book_distill as bd


def make_fake_pass_pkg(
    root: Path,
    status="PASS",
    chapter_files=2,
    with_preamble=True,
    dirname="book_0001_测试之书",
    book_id="book_0001",
) -> Path:
    """构造最小假 PASS 包：metadata.json / conversion_report.md / full.md / chapters/。"""
    sp = root / dirname
    chapters = sp / "chapters"
    chapters.mkdir(parents=True, exist_ok=True)

    meta = {
        "skill_version": "0.2.1",
        "book_id": book_id,
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


def make_fake_prototype(out: Path) -> Path:
    """构造最小 bkp_prototype（知识条目与 out/distill_manifest.json 快照一致）。"""
    manifest = json.loads((out / "distill_manifest.json").read_text(encoding="utf-8"))
    snap = manifest["source_snapshot"]
    proto = out / "bkp_prototype"
    (proto / "knowledge").mkdir(parents=True, exist_ok=True)
    (proto / "deep_dive").mkdir(parents=True, exist_ok=True)

    identity = {
        "bkp_version": "0.1-prototype",
        "schema_status": "PROTOTYPE — 不冻结 schema，不视为最终协议",
        "book": {
            "book_id": snap["book_id"],
            "title": "测试之书",
            "author": "测试作者",
            "category": "外国文学",
            "language": "zh-CN",
            "chapter_count": snap["chapter_count"],
            "parts": {},
        },
        "source_snapshot": snap,
        "provenance": {
            "distill_tool": "BookDistill v0.2.0",
            "distill_method": "Base Scan",
            "scan_date": "2026-08-11",
            "scan_scope": "全部章节",
            "deep_dive_count": 1,
            "deep_dive_dimensions": ["信息控制"],
            "nature": "prototype",
        },
        "stats": {
            "total_entries": 5,
            "by_kind": {"FACT": 1, "INFERENCE": 2, "OBSERVATION": 2, "MECHANISM": 1, "BOUNDARY": 1},
        },
        "bkp_contents": {
            "identity": "identity.json",
            "work_map": "work_map.md",
            "book_profile": "profile.md",
            "observations": {"file": "knowledge/observations.md", "count": 2},
            "inferences": {"file": "knowledge/inferences.md", "count": 2},
            "patterns": {"file": "knowledge/patterns.md", "mechanism_count": 1, "deep_dive_pattern_count": 1},
            "boundaries": {"file": "knowledge/boundaries.md"},
            "deep_dives": [{"dimension": "信息控制", "file": "deep_dive/dd_信息控制.md"}],
        },
        "protocol_alignment": "BKP v0.1 候选协议",
    }
    (proto / "identity.json").write_text(
        json.dumps(identity, ensure_ascii=False), encoding="utf-8"
    )
    (proto / "README.md").write_text(
        "# BKP：测试之书\n\n> **PROTOTYPE** — 原型，schema 未冻结。\n\n## 文件结构\n\n| 文件 | 用途 |\n",
        encoding="utf-8",
    )
    (proto / "work_map.md").write_text(
        "# 作品地图\n\n## 第一部\n\n### ch_0001（开场）\n- 场景说明\n\n### ch_0002\n- 场景说明\n",
        encoding="utf-8",
    )
    (proto / "profile.md").write_text(
        "# BookProfile\n\n## 扫描状态\n\n- 证据条目总数：5\n\n## 深挖建议\n\n（由 Agent 填写）\n",
        encoding="utf-8",
    )
    (proto / "knowledge" / "observations.md").write_text(
        "# 观察索引\n\n> 2 条 OBSERVATION，均为单书观察。\n\n## 人物（2 条）\n\n"
        "- 观察一（chapters/0001.md#L3，高）\n"
        "- 观察二（chapters/0002.md#L3，中）[scope: 测试]\n",
        encoding="utf-8",
    )
    (proto / "knowledge" / "inferences.md").write_text(
        "# 重要推断索引\n\n## 第一部（2 条）\n\n"
        "- **[INFERENCE]** 推断一（chapters/0001.md#L3，高）\n"
        "- **[INFERENCE]** 推断二（chapters/0002.md#L3，中）\n",
        encoding="utf-8",
    )
    (proto / "knowledge" / "patterns.md").write_text(
        "# 写作机制与 Pattern Hypothesis\n\n> 全部为单书 Pattern Hypothesis。\n\n"
        "## Deep Dive Pattern（1 条）\n\n来自 `deep_dive/dd_信息控制.md`，基于观察归纳。\n\n"
        "- **P1 测试模式**：描述。\n\n## 逐章 MECHANISM（1 条）\n\n"
        "1. **测试机制**（ch_0001）：描述。\n",
        encoding="utf-8",
    )
    (proto / "knowledge" / "boundaries.md").write_text(
        "# 边界、反例与不确定性\n\n## 全局性边界\n\n- 译本限制说明。\n\n## 章节级边界\n\n- ch_0001：细节说明。\n",
        encoding="utf-8",
    )
    (proto / "deep_dive" / "dd_信息控制.md").write_text(
        "# 专项深挖：信息控制\n\n## 深挖说明\n\n- 知识等级：单书 Pattern Hypothesis。\n\n"
        "## Evidence（深挖证据）\n\n- [FACT] 测试事实｜证据：chapters/0001.md#L3｜置信度：高\n\n"
        "## Pattern / Interpretation\n\n- **P1 测试模式**：描述。\n\n## Confidence\n\n- 整体置信度：高。\n",
        encoding="utf-8",
    )
    return proto


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

    def test_chapter_count_short_by_one_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp), chapter_files=2, with_preamble=True)
            # 磁盘正文章节 1（删掉 0002）+ 0000 前置，meta 声称 2 → 差 1 必须 FAIL
            (sp / "chapters" / "0002.md").unlink()
            r = bd.validate_input(sp)
            self.assertFalse(r["ok"])
            self.assertTrue(any("不一致" in e for e in r["errors"]))

    def test_chapter_count_long_by_one_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp), chapter_files=2, with_preamble=True)
            # 磁盘正文章节 3（多出 0003）+ 0000 前置，meta 声称 2 → 多 1 必须 FAIL
            (sp / "chapters" / "0003.md").write_text(
                "> 第3章\n\n这是多出来的第3章正文，足够长以通过空章节检查。\n",
                encoding="utf-8",
            )
            r = bd.validate_input(sp)
            self.assertFalse(r["ok"])
            self.assertTrue(any("不一致" in e for e in r["errors"]))

    def test_preamble_not_counted_when_meta_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            # meta 声称 2 章，磁盘 0001/0002 + 0000 前置：精确相等，PASS
            sp = make_fake_pass_pkg(Path(tmp), chapter_files=2, with_preamble=True)
            r = bd.validate_input(sp)
            self.assertTrue(r["ok"], r["errors"])
            self.assertEqual(r["info"]["chapter_files_on_disk"], 2)
            self.assertEqual(r["info"]["chapter_files_in_meta"], 2)

    def test_book_id_dir_prefix_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp), dirname="book_9999_别书")
            r = bd.validate_input(sp)
            self.assertFalse(r["ok"])
            self.assertTrue(any("目录名" in e and "book_id" in e for e in r["errors"]))

    def test_fingerprint_recorded_on_validate(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp))
            r = bd.validate_input(sp)
            self.assertTrue(r["ok"], r["errors"])
            snap = r["info"]["source_snapshot"]
            self.assertEqual(snap["book_id"], "book_0001")
            self.assertEqual(snap["chapter_count"], 2)
            self.assertEqual(len(snap["source_sha256"]), 64)
            self.assertRegex(snap["chapter_content_fingerprint"], r"^[0-9a-f]{64}$")

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

    def test_prepare_writes_manifest_with_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp))
            out = Path(tmp) / "out"
            rc = bd.cmd_prepare(type("A", (), {"input": str(sp), "output": str(out)})())
            self.assertEqual(rc, 0)
            manifest = json.loads((out / "distill_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], bd.BD_VERSION)
            self.assertEqual(manifest["source_snapshot"]["book_id"], "book_0001")
            self.assertEqual(manifest["source_snapshot"]["chapter_count"], 2)


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
            sp, out = self._prepared(Path(tmp))
            ev = out / "evidence" / "ch_0001.md"
            self._fill(ev, [
                "- [FACT] 第1章正文存在｜证据：chapters/0001.md#L3｜置信度：高",
                "- [MECHANISM] 章首引用标题｜证据：chapters/0001.md#L1-L1｜置信度：中",
            ])
            m = bd.assemble(out, sp)
            self.assertTrue(m["ok"], m["errors"])
            self.assertEqual(m["stats_by_kind"]["FACT"], 1)
            self.assertEqual(m["stats_by_kind"]["MECHANISM"], 1)
            self.assertEqual(m["source_snapshot"]["book_id"], "book_0001")
            self.assertEqual(m["source_snapshot"]["chapter_count"], 2)

    def test_assemble_invalid_kind_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp, out = self._prepared(Path(tmp))
            ev = out / "evidence" / "ch_0001.md"
            self._fill(ev, [
                "- [OPINION] 这是非法分类｜证据：chapters/0001.md#L3｜置信度：高",
            ])
            m = bd.assemble(out, sp)
            self.assertFalse(m["ok"])
            self.assertTrue(any("非法分类" in e for e in m["errors"]))

    def test_assemble_bad_ref_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp, out = self._prepared(Path(tmp))
            ev = out / "evidence" / "ch_0001.md"
            self._fill(ev, [
                "- [FACT] 引用不存在章节｜证据：chapters/9999.md#L3｜置信度：高",
            ])
            m = bd.assemble(out, sp)
            self.assertFalse(m["ok"])
            self.assertTrue(any("不存在的章节文件" in e for e in m["errors"]))

    def test_assemble_missing_ref_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp, out = self._prepared(Path(tmp))
            ev = out / "evidence" / "ch_0001.md"
            self._fill(ev, [
                "- [FACT] 缺少引用字段",
            ])
            m = bd.assemble(out, sp)
            self.assertFalse(m["ok"])
            self.assertTrue(any("缺少'证据：'引用" in e for e in m["errors"]))

    def test_assemble_ref_beyond_line_count_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp, out = self._prepared(Path(tmp))
            ev = out / "evidence" / "ch_0001.md"
            # 假章节 0001.md 只有 4 行（含空行），引用 L5 必须 FAIL
            self._fill(ev, [
                "- [FACT] 行号越界条目｜证据：chapters/0001.md#L5-L5｜置信度：高",
            ])
            m = bd.assemble(out, sp)
            self.assertFalse(m["ok"])
            self.assertTrue(any("超出章节实际行数" in e for e in m["errors"]))

    def test_assemble_snapshot_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp, out = self._prepared(Path(tmp))
            ev = out / "evidence" / "ch_0001.md"
            self._fill(ev, [
                "- [FACT] 合法条目｜证据：chapters/0001.md#L3｜置信度：高",
            ])
            # 先通过一次 assemble（记录 snapshot）
            m = bd.assemble(out, sp)
            self.assertTrue(m["ok"], m["errors"])
            # 修改输入章节内容 → fingerprint 变化 → 必须拒绝复用旧产物
            (sp / "chapters" / "0001.md").write_text(
                "> 第1章\n\n内容被改动，不再与 prepare 快照一致。\n",
                encoding="utf-8",
            )
            m2 = bd.assemble(out, sp)
            self.assertFalse(m2["ok"])
            self.assertTrue(any("source snapshot" in e for e in m2["errors"]))

    def test_assemble_legacy_manifest_records_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp, out = self._prepared(Path(tmp))
            ev = out / "evidence" / "ch_0001.md"
            self._fill(ev, [
                "- [FACT] 合法条目｜证据：chapters/0001.md#L3｜置信度：高",
            ])
            # 模拟旧版产物：manifest 无 source_snapshot
            manifest = json.loads((out / "distill_manifest.json").read_text(encoding="utf-8"))
            del manifest["source_snapshot"]
            (out / "distill_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
            )
            m = bd.assemble(out, sp)
            self.assertTrue(m["ok"], m["errors"])
            self.assertTrue(any("自动记录" in w for w in m["warnings"]))
            self.assertIsNotNone(m["source_snapshot"])


class BaseScanUpgradeTest(unittest.TestCase):
    """v0.2 Base Scan 升级测试：OBSERVATION / MAP / 维度 / 覆盖度。"""

    def _prepared(self, tmp: Path):
        sp = make_fake_pass_pkg(Path(tmp))
        out = Path(tmp) / "out"
        bd.cmd_prepare(type("A", (), {"input": str(sp), "output": str(out)})())
        return sp, out

    def _fill(self, ev_path: Path, section: str, lines: list[str]):
        text = ev_path.read_text(encoding="utf-8")
        # 中间节：## section\n\n（后接其他内容）
        target = f"## {section}\n\n"
        if target in text:
            text = text.replace(
                target,
                target + "\n".join(lines) + "\n\n",
                1,
            )
        else:
            # 末尾节：## section\n（文件结尾只有一个 \n）
            target_end = f"## {section}\n"
            text = text.replace(
                target_end,
                target_end + "\n".join(lines) + "\n",
                1,
            )
        ev_path.write_text(text, encoding="utf-8")

    # ---- OBSERVATION 分类兼容性 ----

    def test_assemble_observation_kind_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp, out = self._prepared(Path(tmp))
            ev = out / "evidence" / "ch_0001.md"
            self._fill(ev, "OBSERVATION（作品内观察）", [
                "- [OBSERVATION] dimension:人物 | 角色功能观察"
                "｜证据：chapters/0001.md#L3｜置信度：高",
            ])
            m = bd.assemble(out, sp)
            self.assertTrue(m["ok"], m["errors"])
            self.assertEqual(m["stats_by_kind"]["OBSERVATION"], 1)

    def test_assemble_old_four_kinds_still_valid(self):
        """旧四类证据在 v0.2 下仍然完全兼容。"""
        with tempfile.TemporaryDirectory() as tmp:
            sp, out = self._prepared(Path(tmp))
            ev = out / "evidence" / "ch_0001.md"
            self._fill(ev, "FACT（原文事实）", [
                "- [FACT] 事实条目｜证据：chapters/0001.md#L3｜置信度：高",
            ])
            self._fill(ev, "INFERENCE（推断）", [
                "- [INFERENCE] 推断条目｜证据：chapters/0001.md#L3｜置信度：中",
            ])
            self._fill(ev, "MECHANISM（可迁移机制）", [
                "- [MECHANISM] 机制条目｜证据：chapters/0001.md#L3｜置信度：高",
            ])
            self._fill(ev, "BOUNDARY（边界与不确定性）", [
                "- [BOUNDARY] 边界条目｜证据：chapters/0001.md#L3｜置信度：低",
            ])
            m = bd.assemble(out, sp)
            self.assertTrue(m["ok"], m["errors"])
            self.assertEqual(m["stats_by_kind"]["FACT"], 1)
            self.assertEqual(m["stats_by_kind"]["INFERENCE"], 1)
            self.assertEqual(m["stats_by_kind"]["MECHANISM"], 1)
            self.assertEqual(m["stats_by_kind"]["BOUNDARY"], 1)
            self.assertEqual(m["stats_by_kind"]["OBSERVATION"], 0)

    # ---- 模板结构 ----

    def test_template_has_map_and_observation_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp, out = self._prepared(Path(tmp))
            ev = out / "evidence" / "ch_0001.md"
            text = ev.read_text(encoding="utf-8")
            self.assertIn("## MAP（章节作品地图）", text)
            self.assertIn("## OBSERVATION（作品内观察）", text)
            self.assertIn("dimension:", text)

    # ---- 维度解析 ----

    def test_parse_observation_dimension(self):
        line = "- [OBSERVATION] dimension:人物 | 观察内容｜证据：chapters/0001.md#L3"
        self.assertEqual(bd.parse_observation_dimension(line), "人物")

    def test_parse_observation_dimension_with_punctuation(self):
        line = "- [OBSERVATION] dimension：信息控制 | 观察内容｜证据：chapters/0001.md#L3"
        self.assertEqual(bd.parse_observation_dimension(line), "信息控制")

    def test_parse_observation_dimension_none_for_non_observation(self):
        line = "- [FACT] 事实条目｜证据：chapters/0001.md#L3"
        self.assertIsNone(bd.parse_observation_dimension(line))

    def test_parse_observation_dimension_none_for_missing_tag(self):
        line = "- [OBSERVATION] 无维度标签的观察｜证据：chapters/0001.md#L3"
        self.assertIsNone(bd.parse_observation_dimension(line))

    def test_parse_observation_dimension_reader_experience(self):
        """带空格维度名 Reader Experience 不被截断为 Reader。"""
        line = "- [OBSERVATION] dimension:Reader Experience | 读者体验观察｜证据：chapters/0001.md#L3"
        self.assertEqual(bd.parse_observation_dimension(line), "Reader Experience")

    def test_parse_observation_dimension_scene_turn(self):
        """带空格维度名 Scene Turn 不被截断为 Scene。"""
        line = "- [OBSERVATION] dimension:Scene Turn | 场景转换观察｜证据：chapters/0001.md#L3"
        self.assertEqual(bd.parse_observation_dimension(line), "Scene Turn")

    def test_parse_observation_dimension_custom_spaced_dimension(self):
        """自定义带空格维度名也能正确解析。"""
        line = "- [OBSERVATION] dimension:My Custom Dim | 自定义维度观察｜证据：chapters/0001.md#L3"
        self.assertEqual(bd.parse_observation_dimension(line), "My Custom Dim")

    # ---- 维度覆盖统计 ----

    def test_dimension_coverage_computed_in_assemble(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp, out = self._prepared(Path(tmp))
            ev1 = out / "evidence" / "ch_0001.md"
            ev2 = out / "evidence" / "ch_0002.md"
            self._fill(ev1, "OBSERVATION（作品内观察）", [
                "- [OBSERVATION] dimension:人物 | 观察A"
                "｜证据：chapters/0001.md#L3｜置信度：高",
                "- [OBSERVATION] dimension:关系 | 观察B"
                "｜证据：chapters/0001.md#L3｜置信度：中",
            ])
            self._fill(ev2, "OBSERVATION（作品内观察）", [
                "- [OBSERVATION] dimension:人物 | 观察C"
                "｜证据：chapters/0002.md#L3｜置信度：高",
            ])
            m = bd.assemble(out, sp)
            self.assertTrue(m["ok"], m["errors"])
            self.assertIn("dimension_stats", m)
            ds = m["dimension_stats"]
            self.assertIn("人物", ds)
            self.assertEqual(ds["人物"]["count"], 2)
            self.assertEqual(len(ds["人物"]["chapters"]), 2)
            self.assertIn("关系", ds)
            self.assertEqual(ds["关系"]["count"], 1)

    def test_dimension_coverage_empty_for_old_products(self):
        """旧产物无 OBSERVATION 时 dimension_stats 为空 dict。"""
        with tempfile.TemporaryDirectory() as tmp:
            sp, out = self._prepared(Path(tmp))
            ev = out / "evidence" / "ch_0001.md"
            self._fill(ev, "FACT（原文事实）", [
                "- [FACT] 纯旧条目｜证据：chapters/0001.md#L3｜置信度：高",
            ])
            m = bd.assemble(out, sp)
            self.assertTrue(m["ok"], m["errors"])
            self.assertEqual(m["dimension_stats"], {})

    def test_dimension_coverage_with_spaced_dimension_names(self):
        """带空格维度名在 assemble 统计中被正确归组，不截断。"""
        with tempfile.TemporaryDirectory() as tmp:
            sp, out = self._prepared(Path(tmp))
            ev1 = out / "evidence" / "ch_0001.md"
            ev2 = out / "evidence" / "ch_0002.md"
            self._fill(ev1, "OBSERVATION（作品内观察）", [
                "- [OBSERVATION] dimension:Reader Experience | 阅读体验观察"
                "｜证据：chapters/0001.md#L3｜置信度：高",
                "- [OBSERVATION] dimension:Scene Turn | 场景转换观察"
                "｜证据：chapters/0001.md#L3｜置信度：中",
            ])
            self._fill(ev2, "OBSERVATION（作品内观察）", [
                "- [OBSERVATION] dimension:Reader Experience | 第二章阅读体验"
                "｜证据：chapters/0002.md#L3｜置信度：高",
            ])
            m = bd.assemble(out, sp)
            self.assertTrue(m["ok"], m["errors"])
            ds = m["dimension_stats"]
            self.assertIn("Reader Experience", ds)
            self.assertEqual(ds["Reader Experience"]["count"], 2)
            self.assertEqual(len(ds["Reader Experience"]["chapters"]), 2)
            self.assertIn("Scene Turn", ds)
            self.assertEqual(ds["Scene Turn"]["count"], 1)


class ProfileTest(unittest.TestCase):
    """BookProfile 子命令测试。"""

    def test_profile_generates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp))
            out = Path(tmp) / "out"
            bd.cmd_prepare(type("A", (), {"input": str(sp), "output": str(out)})())
            ev = out / "evidence" / "ch_0001.md"
            text = ev.read_text(encoding="utf-8")
            text = text.replace(
                "## OBSERVATION（作品内观察）\n\n",
                "## OBSERVATION（作品内观察）\n\n"
                "- [OBSERVATION] dimension:人物 | 测试观察"
                "｜证据：chapters/0001.md#L3｜置信度：高\n\n",
                1,
            )
            ev.write_text(text, encoding="utf-8")
            bd.assemble(out, sp)
            rc = bd.cmd_profile(type("A", (), {"output": str(out)})())
            self.assertEqual(rc, 0)
            pf = out / "book_profile.md"
            self.assertTrue(pf.exists())
            content = pf.read_text(encoding="utf-8")
            self.assertIn("BookProfile", content)
            self.assertIn("扫描状态", content)
            self.assertIn("维度覆盖", content)
            self.assertIn("深挖建议", content)
            self.assertIn("人物", content)

    def test_profile_fails_without_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            out.mkdir()
            rc = bd.cmd_profile(type("A", (), {"output": str(out)})())
            self.assertEqual(rc, 1)

    def test_profile_preserves_agent_deep_dive_suggestions(self):
        """profile 重跑保留 Agent 已填写的深挖建议。"""
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp))
            out = Path(tmp) / "out"
            bd.cmd_prepare(type("A", (), {"input": str(sp), "output": str(out)})())
            bd.assemble(out, sp)
            # 首次生成 profile
            rc = bd.cmd_profile(type("A", (), {"output": str(out)})())
            self.assertEqual(rc, 0)
            pf = out / "book_profile.md"
            # 模拟 Agent 填写深挖建议
            content = pf.read_text(encoding="utf-8")
            content = content.replace(
                "## 深挖建议\n\n"
                "（由运行 Skill 的 Agent 基于以上数据填写："
                "哪些维度值得专项深挖、理由、建议的分析方法来源。）",
                "## 深挖建议\n\n推荐信息控制维度深挖。\n"
                "理由：签名维度，21条/21章。\n"
                "分析方法来源：Apodictic 框架。",
            )
            pf.write_text(content, encoding="utf-8")
            # 再次运行 profile
            rc = bd.cmd_profile(type("A", (), {"output": str(out)})())
            self.assertEqual(rc, 0)
            result = pf.read_text(encoding="utf-8")
            self.assertIn("推荐信息控制维度深挖", result)
            self.assertIn("理由：签名维度", result)
            self.assertIn("分析方法来源：Apodictic 框架", result)
            # 机器统计仍然正确
            self.assertIn("扫描状态", result)
            self.assertIn("维度覆盖", result)

    def test_profile_first_run_generates_template(self):
        """首次 profile 生成包含模板占位符。"""
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp))
            out = Path(tmp) / "out"
            bd.cmd_prepare(type("A", (), {"input": str(sp), "output": str(out)})())
            bd.assemble(out, sp)
            rc = bd.cmd_profile(type("A", (), {"output": str(out)})())
            self.assertEqual(rc, 0)
            content = (out / "book_profile.md").read_text(encoding="utf-8")
            self.assertIn("由运行 Skill 的 Agent 基于以上数据填写", content)

    def test_profile_rerun_updates_machine_stats(self):
        """profile 重跑时机器统计数据更新，模板占位符仍显示（无 Agent 填写时）。"""
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp))
            out = Path(tmp) / "out"
            bd.cmd_prepare(type("A", (), {"input": str(sp), "output": str(out)})())
            bd.assemble(out, sp)
            rc = bd.cmd_profile(type("A", (), {"output": str(out)})())
            self.assertEqual(rc, 0)
            first = (out / "book_profile.md").read_text(encoding="utf-8")
            self.assertIn("证据条目总数：0", first)
            # 添加证据后重新 assemble + profile
            ev = out / "evidence" / "ch_0001.md"
            text = ev.read_text(encoding="utf-8")
            text = text.replace(
                "## FACT（原文事实）\n\n",
                "## FACT（原文事实）\n\n"
                "- [FACT] 新增条目｜证据：chapters/0001.md#L3｜置信度：高\n\n",
                1,
            )
            ev.write_text(text, encoding="utf-8")
            bd.assemble(out, sp)
            rc = bd.cmd_profile(type("A", (), {"output": str(out)})())
            self.assertEqual(rc, 0)
            second = (out / "book_profile.md").read_text(encoding="utf-8")
            self.assertIn("证据条目总数：1", second)

    def test_extract_agent_sections_none_for_template(self):
        """模板占位符不被识别为 Agent 内容。"""
        content = "# BookProfile\n\n## 深挖建议\n\n（由运行 Skill 的 Agent 基于以上数据填写：哪些维度值得专项深挖、理由、建议的分析方法来源。）\n"
        self.assertIsNone(bd.extract_agent_sections(content))

    def test_extract_agent_sections_preserves_filled(self):
        """Agent 已填写内容被正确提取。"""
        content = "# BookProfile\n\n## 深挖建议\n\n推荐深挖信息控制。\n"
        result = bd.extract_agent_sections(content)
        self.assertIsNotNone(result)
        self.assertIn("推荐深挖信息控制", result)


class DeepDiveTest(unittest.TestCase):
    """Deep Dive 子命令测试。"""

    def _prepared(self, tmp: Path):
        sp = make_fake_pass_pkg(Path(tmp))
        out = Path(tmp) / "out"
        bd.cmd_prepare(type("A", (), {"input": str(sp), "output": str(out)})())
        return sp, out

    def _inject(self, dd_path: Path, section: str, lines: list[str]):
        text = dd_path.read_text(encoding="utf-8")
        target = f"## {section}\n\n"
        if target in text:
            text = text.replace(target, target + "\n".join(lines) + "\n\n", 1)
        else:
            target_end = f"## {section}\n"
            text = text.replace(target_end, target_end + "\n".join(lines) + "\n", 1)
        dd_path.write_text(text, encoding="utf-8")

    def test_deepdive_generates_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp))
            out = Path(tmp) / "out"
            bd.cmd_prepare(type("A", (), {"input": str(sp), "output": str(out)})())
            rc = bd.cmd_deepdive(
                type("A", (), {
                    "output": str(out),
                    "dimension": "人物",
                    "topic": "人物功能分析",
                })()
            )
            self.assertEqual(rc, 0)
            dd = out / "deepdive" / "dd_人物.md"
            self.assertTrue(dd.exists())
            content = dd.read_text(encoding="utf-8")
            self.assertIn("专项深挖：人物功能分析", content)
            self.assertIn("维度/主题：人物", content)
            self.assertIn("Evidence", content)
            self.assertIn("Counterevidence", content)
            self.assertIn("Scope", content)

    def test_deepdive_topic_defaults_to_dimension(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp = make_fake_pass_pkg(Path(tmp))
            out = Path(tmp) / "out"
            bd.cmd_prepare(type("A", (), {"input": str(sp), "output": str(out)})())
            rc = bd.cmd_deepdive(
                type("A", (), {
                    "output": str(out),
                    "dimension": "信息控制",
                    "topic": None,
                })()
            )
            self.assertEqual(rc, 0)
            dd = out / "deepdive" / "dd_信息控制.md"
            self.assertTrue(dd.exists())
            content = dd.read_text(encoding="utf-8")
            self.assertIn("专项深挖：信息控制", content)

    def test_deepdive_validate_passes_valid_entries(self):
        """合法 Deep Dive 条目通过校验。"""
        with tempfile.TemporaryDirectory() as tmp:
            sp, out = self._prepared(Path(tmp))
            bd.cmd_deepdive(
                type("A", (), {
                    "output": str(out),
                    "dimension": "信息控制",
                    "topic": None,
                    "input": str(sp),
                })()
            )
            dd = out / "deepdive" / "dd_信息控制.md"
            self._inject(dd, "Evidence（深挖证据）", [
                "- [FACT] 深挖事实｜证据：chapters/0001.md#L3｜置信度：高",
                "- [OBSERVATION] dimension:信息控制 | 深挖观察"
                "｜证据：chapters/0001.md#L3｜置信度：中",
            ])
            rc = bd.cmd_deepdive(
                type("A", (), {
                    "output": str(out),
                    "dimension": "信息控制",
                    "topic": None,
                    "input": str(sp),
                })()
            )
            self.assertEqual(rc, 0)

    def test_deepdive_validate_rejects_bad_ref(self):
        """Deep Dive 中引用不存在章节被拦截。"""
        with tempfile.TemporaryDirectory() as tmp:
            sp, out = self._prepared(Path(tmp))
            bd.cmd_deepdive(
                type("A", (), {
                    "output": str(out),
                    "dimension": "信息控制",
                    "topic": None,
                    "input": str(sp),
                })()
            )
            dd = out / "deepdive" / "dd_信息控制.md"
            self._inject(dd, "Evidence（深挖证据）", [
                "- [FACT] 非法引用｜证据：chapters/9999.md#L3｜置信度：高",
            ])
            rc = bd.cmd_deepdive(
                type("A", (), {
                    "output": str(out),
                    "dimension": "信息控制",
                    "topic": None,
                    "input": str(sp),
                })()
            )
            self.assertEqual(rc, 1)

    def test_deepdive_validate_rejects_line_beyond_bounds(self):
        """Deep Dive 中行号越界被拦截。"""
        with tempfile.TemporaryDirectory() as tmp:
            sp, out = self._prepared(Path(tmp))
            bd.cmd_deepdive(
                type("A", (), {
                    "output": str(out),
                    "dimension": "信息控制",
                    "topic": None,
                    "input": str(sp),
                })()
            )
            dd = out / "deepdive" / "dd_信息控制.md"
            self._inject(dd, "Evidence（深挖证据）", [
                "- [FACT] 行号越界｜证据：chapters/0001.md#L99｜置信度：高",
            ])
            rc = bd.cmd_deepdive(
                type("A", (), {
                    "output": str(out),
                    "dimension": "信息控制",
                    "topic": None,
                    "input": str(sp),
                })()
            )
            self.assertEqual(rc, 1)

    def test_deepdive_validate_rejects_missing_ref(self):
        """Deep Dive 中缺少证据引用被拦截。"""
        with tempfile.TemporaryDirectory() as tmp:
            sp, out = self._prepared(Path(tmp))
            bd.cmd_deepdive(
                type("A", (), {
                    "output": str(out),
                    "dimension": "信息控制",
                    "topic": None,
                    "input": str(sp),
                })()
            )
            dd = out / "deepdive" / "dd_信息控制.md"
            self._inject(dd, "Evidence（深挖证据）", [
                "- [FACT] 缺少证据引用条目",
            ])
            rc = bd.cmd_deepdive(
                type("A", (), {
                    "output": str(out),
                    "dimension": "信息控制",
                    "topic": None,
                    "input": str(sp),
                })()
            )
            self.assertEqual(rc, 1)


class BKPFinalizeTest(unittest.TestCase):
    """BKP Finalize 测试：结构、快照、类型边界、引用、过程文件排除、重跑安全。"""

    def _prepared(self, tmp: Path):
        sp = make_fake_pass_pkg(Path(tmp))
        out = Path(tmp) / "out"
        bd.cmd_prepare(type("A", (), {"input": str(sp), "output": str(out)})())
        bd.assemble(out, sp)
        return sp, out

    def test_finalize_creates_formal_bkp(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(Path(tmp))
            make_fake_prototype(out)
            r = bd.finalize_bkp(out)
            self.assertTrue(r["ok"], r["errors"])
            bkp = out / "bkp"
            for rel in [
                "identity.json",
                "README.md",
                "work_map.md",
                "profile.md",
                "knowledge/observations.md",
                "knowledge/inferences.md",
                "knowledge/patterns.md",
                "knowledge/boundaries.md",
                "deep_dive/dd_信息控制.md",
            ]:
                self.assertTrue((bkp / rel).exists(), f"缺少 {rel}")
            readme = (bkp / "README.md").read_text(encoding="utf-8")
            self.assertIn("FINALIZED", readme)
            identity = json.loads((bkp / "identity.json").read_text(encoding="utf-8"))
            manifest = json.loads((out / "distill_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(identity["source_snapshot"], manifest["source_snapshot"])
            self.assertEqual(identity["source_snapshot"]["source_sha256"], "a" * 64)
            self.assertEqual(identity["bkp_version"], "0.2")

    def test_cmd_bkp_success_with_prototype(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(Path(tmp))
            make_fake_prototype(out)
            rc = bd.cmd_bkp(type("A", (), {"output": str(out), "prototype": None})())
            self.assertEqual(rc, 0)
            self.assertTrue((out / "bkp" / "identity.json").exists())

    def test_finalize_missing_prototype_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(Path(tmp))
            r = bd.finalize_bkp(out)
            self.assertFalse(r["ok"])
            self.assertTrue(any("原型目录" in e for e in r["errors"]))

    def test_cmd_bkp_fails_without_prototype(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(Path(tmp))
            rc = bd.cmd_bkp(type("A", (), {"output": str(out), "prototype": None})())
            self.assertEqual(rc, 1)

    def test_finalize_snapshot_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(Path(tmp))
            proto = make_fake_prototype(out)
            ident = json.loads((proto / "identity.json").read_text(encoding="utf-8"))
            ident["source_snapshot"]["source_sha256"] = "b" * 64
            (proto / "identity.json").write_text(
                json.dumps(ident, ensure_ascii=False), encoding="utf-8"
            )
            r = bd.finalize_bkp(out)
            self.assertFalse(r["ok"])
            self.assertTrue(
                any("source_snapshot" in e and "distill_manifest" in e for e in r["errors"])
            )

    def test_finalize_rejects_inference_mixed_as_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(Path(tmp))
            proto = make_fake_prototype(out)
            inf = (proto / "knowledge" / "inferences.md").read_text(encoding="utf-8")
            inf += "- [OBSERVATION] 混入观察｜证据：chapters/0001.md#L3｜置信度：中\n"
            (proto / "knowledge" / "inferences.md").write_text(inf, encoding="utf-8")
            r = bd.finalize_bkp(out)
            self.assertFalse(r["ok"])
            self.assertTrue(any("OBSERVATION" in e for e in r["errors"]))

    def test_finalize_rejects_observation_missing_citation(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(Path(tmp))
            proto = make_fake_prototype(out)
            obs = (proto / "knowledge" / "observations.md").read_text(encoding="utf-8")
            obs += "- 无引用的观察\n"
            (proto / "knowledge" / "observations.md").write_text(obs, encoding="utf-8")
            r = bd.finalize_bkp(out)
            self.assertFalse(r["ok"])
            self.assertTrue(any("引用" in e for e in r["errors"]))

    def test_finalize_rejects_line_beyond_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(Path(tmp))
            proto = make_fake_prototype(out)
            obs = (proto / "knowledge" / "observations.md").read_text(encoding="utf-8")
            obs += "- 越界观察（chapters/0001.md#L99，高）\n"
            (proto / "knowledge" / "observations.md").write_text(obs, encoding="utf-8")
            r = bd.finalize_bkp(out)
            self.assertFalse(r["ok"])
            self.assertTrue(any("超出章节实际行数" in e for e in r["errors"]))

    def test_finalize_rejects_pattern_upgrade_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(Path(tmp))
            proto = make_fake_prototype(out)
            pat = (proto / "knowledge" / "patterns.md").read_text(encoding="utf-8")
            pat += "\n## Production Rule\n\n- 不应出现的升级规则。\n"
            (proto / "knowledge" / "patterns.md").write_text(pat, encoding="utf-8")
            r = bd.finalize_bkp(out)
            self.assertFalse(r["ok"])
            self.assertTrue(any("升级" in e for e in r["errors"]))

    def test_finalize_excludes_process_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(Path(tmp))
            proto = make_fake_prototype(out)
            (proto / "prompts").mkdir()
            (proto / "prompts" / "prompt.txt").write_text("中间 Prompt\n", encoding="utf-8")
            (proto / "drafts").mkdir()
            (proto / "drafts" / "过程草稿.md").write_text("分析草稿\n", encoding="utf-8")
            (proto / "logs").mkdir()
            (proto / "logs" / "run.log").write_text("日志\n", encoding="utf-8")
            r = bd.finalize_bkp(out)
            self.assertTrue(r["ok"], r["errors"])
            bkp = out / "bkp"
            self.assertFalse((bkp / "prompts" / "prompt.txt").exists())
            self.assertFalse((bkp / "drafts" / "过程草稿.md").exists())
            self.assertFalse((bkp / "logs" / "run.log").exists())
            self.assertIn("prompts/prompt.txt", r["excluded"])
            self.assertIn("drafts/过程草稿.md", r["excluded"])
            self.assertIn("logs/run.log", r["excluded"])

    def test_finalize_rerun_preserves_human_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(Path(tmp))
            make_fake_prototype(out)
            r1 = bd.finalize_bkp(out)
            self.assertTrue(r1["ok"], r1["errors"])
            obs_dst = out / "bkp" / "knowledge" / "observations.md"
            obs_dst.write_text(
                obs_dst.read_text(encoding="utf-8") + "- 人工补充的知识\n",
                encoding="utf-8",
            )
            r2 = bd.finalize_bkp(out)
            self.assertTrue(r2["ok"], r2["errors"])
            self.assertIn("knowledge/observations.md", r2["skipped_curated"])
            content = obs_dst.read_text(encoding="utf-8")
            self.assertIn("人工补充的知识", content)

    def test_finalize_rerun_idempotent_when_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(Path(tmp))
            make_fake_prototype(out)
            r1 = bd.finalize_bkp(out)
            self.assertTrue(r1["ok"], r1["errors"])
            first = (out / "bkp" / "knowledge" / "observations.md").read_text(encoding="utf-8")
            r2 = bd.finalize_bkp(out)
            self.assertTrue(r2["ok"], r2["errors"])
            self.assertEqual(r2["skipped_curated"], [])
            second = (out / "bkp" / "knowledge" / "observations.md").read_text(encoding="utf-8")
            self.assertEqual(first, second)

    def test_finalize_count_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(Path(tmp))
            proto = make_fake_prototype(out)
            ident = json.loads((proto / "identity.json").read_text(encoding="utf-8"))
            ident["bkp_contents"]["observations"]["count"] = 3
            (proto / "identity.json").write_text(
                json.dumps(ident, ensure_ascii=False), encoding="utf-8"
            )
            r = bd.finalize_bkp(out)
            self.assertFalse(r["ok"])
            self.assertTrue(any("observations" in e for e in r["errors"]))

    def test_finalize_deep_dive_pattern_requires_source_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(Path(tmp))
            proto = make_fake_prototype(out)
            pat = (proto / "knowledge" / "patterns.md").read_text(encoding="utf-8")
            pat = pat.replace(
                "deep_dive/dd_信息控制.md",
                "deep_dive/dd_不存在.md",
            )
            (proto / "knowledge" / "patterns.md").write_text(pat, encoding="utf-8")
            r = bd.finalize_bkp(out)
            self.assertFalse(r["ok"])
            self.assertTrue(any("Deep Dive 文件不存在" in e for e in r["errors"]))

    def test_finalize_missing_knowledge_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(Path(tmp))
            proto = make_fake_prototype(out)
            (proto / "knowledge" / "observations.md").unlink()
            r = bd.finalize_bkp(out)
            self.assertFalse(r["ok"])
            self.assertTrue(any("observations.md" in e for e in r["errors"]))


if __name__ == "__main__":
    unittest.main()
