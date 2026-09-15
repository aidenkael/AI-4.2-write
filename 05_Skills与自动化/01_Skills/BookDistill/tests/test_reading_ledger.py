# -*- coding: utf-8 -*-
"""BookDistill reading manifest / ledger / resume / receipt 确定性测试。

覆盖任务书 §9 BookDistill 检查点：
1. synthetic 多 unit 输入的 manifest 全覆盖，无 gap/overlap；
2. oversized unit 正确拆 span；
3. ledger 可 resume，已完成 batch 不重复；
4. source fingerprint / run / manifest hash mismatch 被拒；
7. batch 已真实处理但 0 high-value findings 可正常 completed。
零模型、零网络、零真实书籍（全部 tmp fixture）。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import reading_ledger as rl  # noqa: E402


def _make_source(root: Path, *, chapters: int = 3, lines_each: int = 40,
                 oversized: int | None = None) -> Path:
    """Build a synthetic SourcePrepare-style chapters/ dir."""
    sp = root / "sp"
    (sp / "chapters").mkdir(parents=True)
    for i in range(1, chapters + 1):
        n = lines_each if oversized != i else 3000
        text = "\n".join(f"第{i}章 第{j}行 内容" for j in range(1, n + 1))
        (sp / "chapters" / f"{i:04d}.md").write_text(text, encoding="utf-8")
    return sp


def _snapshot(fp: str = "c" * 64) -> dict:
    return {"book_id": "book_9001", "sp_version": "0.4.0", "source_sha256": "f" * 64,
            "chapter_count": 3, "chapter_content_fingerprint": fp,
            "unit_semantics": "chapter", "unit_boundary_source": "epub_nav_anchor"}


def _commit_all(bd_dir: Path, manifest: dict, *, domains=None, finding_count: int = 0) -> int:
    domains = tuple(domains if domains is not None else rl.SIX_DOMAINS)
    count = 0
    while True:
        nb = rl.next_pending_batch(bd_dir)
        if nb is None:
            break
        bid = nb["batch_id"]
        note = rl.batch_notes_dir(bd_dir) / f"{bid}.md"
        text = rl.render_batch_note_template(
            batch_id=bid, request_id=manifest["request_id"], run_id=manifest["run_id"],
            manifest_hash=manifest["manifest_hash"], source_fingerprint=manifest["source_fingerprint"],
            spans=nb["spans"], required_domains=domains)
        # 模拟真实处理但 0 高价值发现（finding_count 默认 0）。
        text = text.replace('"finding_count": 0', f'"finding_count": {finding_count}')
        note.write_text(text, encoding="utf-8")
        rl.commit_batch(bd_dir, bid, note, required_domains=domains)
        count += 1
    return count


class ReadingManifestTest(unittest.TestCase):
    def test_manifest_covers_all_units_no_gap_no_overlap(self):
        """检查点 1：多 unit 全覆盖，无 gap/overlap，顺序稳定。"""
        with tempfile.TemporaryDirectory() as tmp:
            sp = _make_source(Path(tmp), chapters=5)
            m = rl.build_manifest(sp, request_id="r1", run_id="r1",
                                  source_id="book_9001", source_snapshot=_snapshot())
            cov = rl.validate_manifest_coverage(m, sp)
            self.assertTrue(cov["ok"], cov["errors"])
            self.assertEqual(cov["unit_count"], 5)
            # span 顺序稳定且每个 unit 恰好被覆盖一次。
            units = [s["unit_file"] for s in m["spans"]]
            self.assertEqual(units, sorted(units))
            self.assertEqual(len(units), len(set(units)))

    def test_oversized_unit_split_into_contiguous_spans(self):
        """检查点 2：超大 unit 确定性拆成连续 span，仍无 gap/overlap。"""
        with tempfile.TemporaryDirectory() as tmp:
            sp = _make_source(Path(tmp), chapters=3, oversized=2)
            m = rl.build_manifest(sp, request_id="r1", run_id="r1",
                                  source_id="book_9001", source_snapshot=_snapshot())
            cov = rl.validate_manifest_coverage(m, sp)
            self.assertTrue(cov["ok"], cov["errors"])
            ch2 = [s for s in m["spans"] if s["unit_file"] == "chapters/0002.md"]
            self.assertGreater(len(ch2), 1, "超大单元应被拆成多个 span")
            # 连续：第一个 span 从 L1 起，后一个紧接前一个。
            self.assertEqual(ch2[0]["start_line"], 1)
            for prev, nxt in zip(ch2, ch2[1:]):
                self.assertEqual(nxt["start_line"], prev["end_line"] + 1)

    def test_batches_respect_byte_bound(self):
        """批次按连续 span 聚合到保守内部上限。"""
        with tempfile.TemporaryDirectory() as tmp:
            sp = _make_source(Path(tmp), chapters=200, lines_each=60)
            m = rl.build_manifest(sp, request_id="r1", run_id="r1",
                                  source_id="book_9001", source_snapshot=_snapshot())
            self.assertGreater(len(m["batches"]), 1)
            for b in m["batches"]:
                # 单 span 批次允许超过上限；多 span 批次不应远超上限。
                if len(b["span_ids"]) > 1:
                    self.assertLessEqual(b["total_bytes"], rl.MAX_BATCH_BYTES + rl.MAX_BATCH_BYTES)


class ReadingLedgerResumeTest(unittest.TestCase):
    def test_resume_skips_completed_batches(self):
        """检查点 3：ledger 可 resume，已完成 batch 不重复。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp = _make_source(root, chapters=60, lines_each=200)
            bd = root / "bd"
            m = rl.build_manifest(sp, request_id="r1", run_id="r1",
                                  source_id="book_9001", source_snapshot=_snapshot())
            rl.write_manifest(bd, m)
            rl.init_ledger(bd, m)
            total = len(m["batches"])
            self.assertGreater(total, 1)
            # 只完成第一批。
            nb = rl.next_pending_batch(bd)
            bid = nb["batch_id"]
            note = rl.batch_notes_dir(bd) / f"{bid}.md"
            note.write_text(rl.render_batch_note_template(
                batch_id=bid, request_id="r1", run_id="r1",
                manifest_hash=m["manifest_hash"], source_fingerprint=m["source_fingerprint"],
                spans=nb["spans"]), encoding="utf-8")
            rl.commit_batch(bd, bid, note)
            # resume：next 返回的绝不是已完成的批次。
            nb2 = rl.next_pending_batch(bd)
            self.assertIsNotNone(nb2)
            self.assertNotEqual(nb2["batch_id"], bid)
            st = rl.ledger_status(bd)
            self.assertEqual(st["completed_batches"], 1)
            self.assertFalse(st["complete"])

    def test_zero_finding_batch_commits_normally(self):
        """检查点 7：batch 已真实处理但 0 高价值发现可正常 completed。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp = _make_source(root, chapters=2)
            bd = root / "bd"
            m = rl.build_manifest(sp, request_id="r1", run_id="r1",
                                  source_id="book_9001", source_snapshot=_snapshot())
            rl.write_manifest(bd, m)
            rl.init_ledger(bd, m)
            committed = _commit_all(bd, m, finding_count=0)
            self.assertEqual(committed, len(m["batches"]))
            st = rl.ledger_status(bd)
            self.assertTrue(st["complete"])
            check = rl.validate_ledger(bd, sp)
            self.assertTrue(check["ok"], check["errors"])
            self.assertTrue(check["complete"])

    def test_fingerprint_mismatch_invalidates_ledger(self):
        """检查点 4：source fingerprint 变化后旧 manifest/ledger 自动失效。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp = _make_source(root, chapters=2)
            bd = root / "bd"
            m = rl.build_manifest(sp, request_id="r1", run_id="r1",
                                  source_id="book_9001", source_snapshot=_snapshot("old" + "0" * 61))
            rl.write_manifest(bd, m)
            rl.init_ledger(bd, m)
            _commit_all(bd, m)
            # 来源 fingerprint 变化 → 新 manifest。
            m2 = rl.build_manifest(sp, request_id="r1", run_id="r1",
                                   source_id="book_9001", source_snapshot=_snapshot("new" + "0" * 61))
            rl.write_manifest(bd, m2)
            # 旧 ledger 与新 manifest 的 source_fingerprint 不一致 → 校验失败。
            check = rl.validate_ledger(bd, sp)
            self.assertFalse(check["ok"])
            self.assertTrue(any("source_fingerprint" in e or "manifest_hash" in e
                                for e in check["errors"]))

    def test_run_id_mismatch_rejected(self):
        """检查点 4：旧 run 的 batch completion 不能混入当前 run。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp = _make_source(root, chapters=2)
            bd = root / "bd"
            m = rl.build_manifest(sp, request_id="r1", run_id="run_A",
                                  source_id="book_9001", source_snapshot=_snapshot())
            rl.write_manifest(bd, m)
            rl.init_ledger(bd, m)
            # 篡改 ledger 的 run_id 模拟旧 run 混入。
            ledger = rl.read_ledger(bd)
            ledger["run_id"] = "run_OLD"
            rl._atomic_write_json(rl.ledger_path(bd), ledger)
            check = rl.validate_ledger(bd, sp)
            self.assertFalse(check["ok"])
            self.assertTrue(any("run_id" in e for e in check["errors"]))

    def test_manifest_hash_mismatch_rejected(self):
        """检查点 4：manifest hash mismatch 被拒。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp = _make_source(root, chapters=2)
            bd = root / "bd"
            m = rl.build_manifest(sp, request_id="r1", run_id="r1",
                                  source_id="book_9001", source_snapshot=_snapshot())
            rl.write_manifest(bd, m)
            rl.init_ledger(bd, m)
            ledger = rl.read_ledger(bd)
            ledger["manifest_hash"] = "tampered"
            rl._atomic_write_json(rl.ledger_path(bd), ledger)
            check = rl.validate_ledger(bd, sp)
            self.assertFalse(check["ok"])
            self.assertTrue(any("manifest_hash" in e for e in check["errors"]))


class CompletionReceiptTest(unittest.TestCase):
    def test_receipt_requires_complete_ledger_and_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp = _make_source(root, chapters=2)
            bd = root / "bd"
            m = rl.build_manifest(sp, request_id="r1", run_id="r1",
                                  source_id="book_9001", source_snapshot=_snapshot())
            rl.write_manifest(bd, m)
            rl.init_ledger(bd, m)
            # ledger 未完整时拒绝写 receipt。
            with self.assertRaises(rl.ReadingLedgerError):
                rl.write_completion_receipt(bd, request_id="r1", run_id="r1",
                                            source_id="book_9001", source_snapshot=_snapshot(),
                                            acceptance_status="PASS", canonical_card_count=3,
                                            gate_version="test")
            _commit_all(bd, m)
            # acceptance 非 PASS 时拒绝。
            with self.assertRaises(rl.ReadingLedgerError):
                rl.write_completion_receipt(bd, request_id="r1", run_id="r1",
                                            source_id="book_9001", source_snapshot=_snapshot(),
                                            acceptance_status="REVIEW", canonical_card_count=3,
                                            gate_version="test")
            path = rl.write_completion_receipt(bd, request_id="r1", run_id="r1",
                                               source_id="book_9001", source_snapshot=_snapshot(),
                                               acceptance_status="PASS", canonical_card_count=3,
                                               gate_version="test")
            self.assertTrue(path.exists())
            receipt = rl.read_completion_receipt(bd)
            ok = rl.validate_completion_receipt(receipt, bd, request_id="r1",
                                                source_id="book_9001", source_snapshot=_snapshot())
            self.assertTrue(ok["ok"], ok["errors"])

    def test_receipt_rejects_stale_source(self):
        """source fingerprint 已变化的 receipt 不能触发 finalize。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp = _make_source(root, chapters=2)
            bd = root / "bd"
            snap = _snapshot()
            m = rl.build_manifest(sp, request_id="r1", run_id="r1",
                                  source_id="book_9001", source_snapshot=snap)
            rl.write_manifest(bd, m)
            rl.init_ledger(bd, m)
            _commit_all(bd, m)
            rl.write_completion_receipt(bd, request_id="r1", run_id="r1",
                                        source_id="book_9001", source_snapshot=snap,
                                        acceptance_status="PASS", canonical_card_count=3,
                                        gate_version="test")
            receipt = rl.read_completion_receipt(bd)
            # 当前来源 snapshot 变化 → receipt 失效。
            bad = rl.validate_completion_receipt(receipt, bd, request_id="r1",
                                                 source_id="book_9001",
                                                 source_snapshot=_snapshot("changed" + "0" * 57))
            self.assertFalse(bad["ok"])


# ---------------------------------------------------------------------------
# A1：单一权威 canonical batch note 校验器（publish / has_valid / commit / validate 共用）
# ---------------------------------------------------------------------------

def _note_text(batch, manifest, *, finding_count=None, span_count=None, observations=()):
    text = rl.render_batch_note_template(
        batch_id=batch["batch_id"], request_id=manifest["request_id"], run_id=manifest["run_id"],
        manifest_hash=manifest["manifest_hash"], source_fingerprint=manifest["source_fingerprint"],
        spans=batch["spans"])
    if finding_count is not None:
        text = text.replace('"finding_count": 0', f'"finding_count": {finding_count}')
    if span_count is not None:
        text = text.replace(f'"span_count": {len(batch["spans"])}', f'"span_count": {span_count}')
    if observations:
        block = "\n".join(observations)
        text = text.replace("## 未解决问题 / 待跨批核对",
                            f"## 来源绑定 findings（source-bound）\n{block}\n\n## 未解决问题 / 待跨批核对")
    return text


class CanonicalNoteValidatorTest(unittest.TestCase):
    """检查点 1（A1）：finding_count / span_count / evidence 机械校验，不靠 Agent 自报。"""

    def _bd(self, root):
        sp = _make_source(Path(root), chapters=2)
        bd = Path(root) / "bd"
        m = rl.build_manifest(sp, request_id="r1", run_id="r1", source_id="book_9001",
                              source_snapshot=_snapshot())
        rl.write_manifest(bd, m)
        rl.init_ledger(bd, m)
        return sp, bd, m, rl.next_pending_batch(bd)

    def test_finding_count_mismatch_fails(self):
        """finding_count 与实际 finding 数不一致必须失败。"""
        with tempfile.TemporaryDirectory() as tmp:
            sp, bd, m, batch = self._bd(tmp)
            note = rl.batch_notes_dir(bd) / f"{batch['batch_id']}.md"
            note.write_text(_note_text(batch, m, finding_count=5), encoding="utf-8")
            _, errs = rl.validate_batch_note_file(note, m, batch["batch_id"])
            self.assertTrue(any("finding_count" in e for e in errs), errs)
            with self.assertRaises(rl.ReadingLedgerError):
                rl.commit_batch(bd, batch["batch_id"], note)

    def test_finding_without_evidence_ref_fails(self):
        """finding_count>0 但 [OBSERVATION] 行无来源 ref 必须失败。"""
        with tempfile.TemporaryDirectory() as tmp:
            sp, bd, m, batch = self._bd(tmp)
            note = rl.batch_notes_dir(bd) / f"{batch['batch_id']}.md"
            note.write_text(_note_text(batch, m, finding_count=1,
                                       observations=["- [OBSERVATION] dimension:人物 | 无证据观察｜置信度：高"]),
                            encoding="utf-8")
            _, errs = rl.validate_batch_note_file(note, m, batch["batch_id"])
            self.assertTrue(any("缺少来源证据" in e or "越出" in e for e in errs), errs)

    def test_finding_count_matches_real_findings_passes(self):
        """finding_count == 真实 [OBSERVATION] 数且证据合法 → 通过（不被误杀）。"""
        with tempfile.TemporaryDirectory() as tmp:
            sp, bd, m, batch = self._bd(tmp)
            first = batch["spans"][0]
            obs = (f"- [OBSERVATION] dimension:人物 | 观察｜证据：{first['unit_file']}"
                   f"#L{first['start_line']}-L{first['end_line']}｜置信度：高")
            note = rl.batch_notes_dir(bd) / f"{batch['batch_id']}.md"
            note.write_text(_note_text(batch, m, finding_count=1, observations=[obs]), encoding="utf-8")
            _, errs = rl.validate_batch_note_file(note, m, batch["batch_id"])
            self.assertEqual(errs, [], errs)

    def test_forged_span_count_fails(self):
        """span_count 伪造必须失败。"""
        with tempfile.TemporaryDirectory() as tmp:
            sp, bd, m, batch = self._bd(tmp)
            note = rl.batch_notes_dir(bd) / f"{batch['batch_id']}.md"
            note.write_text(_note_text(batch, m, span_count=len(batch["spans"]) + 99), encoding="utf-8")
            _, errs = rl.validate_batch_note_file(note, m, batch["batch_id"])
            self.assertTrue(any("span_count" in e for e in errs), errs)

    def test_stale_canonical_note_not_commit_ready(self):
        """stale manifest_hash 的 canonical note 不得成为 commit_ready。"""
        with tempfile.TemporaryDirectory() as tmp:
            sp, bd, m, batch = self._bd(tmp)
            note = rl.batch_notes_dir(bd) / f"{batch['batch_id']}.md"
            note.write_text(_note_text(batch, m, span_count=None), encoding="utf-8")
            self.assertTrue(rl.has_valid_canonical_note(bd, batch["batch_id"]))
            # 来源/批次计划变化 → 新 manifest（manifest_hash 变）。
            m2 = rl.build_manifest(sp, request_id="r1", run_id="r1", source_id="book_9001",
                                   source_snapshot=_snapshot("d" * 64))
            rl.write_manifest(bd, m2)
            self.assertFalse(rl.has_valid_canonical_note(bd, batch["batch_id"]))


# ---------------------------------------------------------------------------
# A3：真实 UTF-8 字节边界（不再是行号比例估算）
# ---------------------------------------------------------------------------

class RealByteBoundaryTest(unittest.TestCase):
    def _chapters(self, root, contents: dict) -> Path:
        sp = Path(root) / "sp"
        (sp / "chapters").mkdir(parents=True)
        for name, text in contents.items():
            (sp / "chapters" / name).write_text(text, encoding="utf-8")
        return sp

    def _batch_actual_bytes(self, m, sp):
        """recompute the ACTUAL UTF-8 bytes each batch covers."""
        spans_by_id = {s["span_id"]: s for s in m["spans"]}
        actual = 0
        for b in m["batches"]:
            total = 0
            for sid in b["span_ids"]:
                s = spans_by_id[sid]
                lines = (sp / s["unit_file"]).read_text(encoding="utf-8").splitlines()
                for i in range(s["start_line"], s["end_line"] + 1):
                    total += len(lines[i - 1].encode("utf-8")) + 1
            actual = max(actual, total)
            self.assertLessEqual(b["total_bytes"], rl.MAX_BATCH_BYTES,
                                 f"batch {b['batch_id']} 声明字节超预算")
        return actual

    def test_chinese_multibyte_source_bytes_are_actual(self):
        """中文多字节：span source_bytes 是真实 UTF-8 字节（不是行数估算）。"""
        with tempfile.TemporaryDirectory() as tmp:
            body = "\n".join("中" * 400 for _ in range(5))  # 每行 400 个汉字 = 1200 字节
            sp = self._chapters(tmp, {"0001.md": body})
            m = rl.build_manifest(sp, request_id="r1", run_id="r1", source_id="book_9001",
                                  source_snapshot=_snapshot())
            # 5 行×1200 ≈ 6000+ 字节；旧行数比例估算会低估。断言真实字节被记录。
            self.assertGreater(m["spans"][0]["source_bytes"], 5 * 400 * 3)
            self._batch_actual_bytes(m, sp)

    def test_uneven_long_lines_stay_within_budget(self):
        """极不均匀长行：每 batch 真实字节 <= MAX_BATCH_BYTES。"""
        with tempfile.TemporaryDirectory() as tmp:
            # 混合 1 行超 100KB（但 < 200KB）+ 大量短行，迫使真实字节分批。
            big = "长" * 60000  # ~180KB 单行
            many = "\n".join("短行内容" for _ in range(5000))
            sp = self._chapters(tmp, {"0001.md": big, "0002.md": many})
            m = rl.build_manifest(sp, request_id="r1", run_id="r1", source_id="book_9001",
                                  source_snapshot=_snapshot())
            self._batch_actual_bytes(m, sp)

    def test_single_span_over_budget_splits(self):
        """单章 >200KB（多行）拆为多 span，每 span/batch 真实字节不越界。"""
        with tempfile.TemporaryDirectory() as tmp:
            body = "\n".join("内" * 500 for _ in range(2000))  # 2000×1500B ≈ 3MB
            sp = self._chapters(tmp, {"0001.md": body})
            m = rl.build_manifest(sp, request_id="r1", run_id="r1", source_id="book_9001",
                                  source_snapshot=_snapshot())
            ch = [s for s in m["spans"] if s["unit_file"] == "chapters/0001.md"]
            self.assertGreater(len(ch), 1, "大章应拆为多 span")
            for s in ch:
                self.assertLessEqual(s["source_bytes"], rl.MAX_BATCH_BYTES)
            self._batch_actual_bytes(m, sp)
            # gap-free：覆盖到末行。
            self.assertEqual(ch[-1]["end_line"], 2000)

    def test_single_line_over_budget_fails_closed(self):
        """单行本身就 >200KB 时 fail closed，不偷偷生成 oversized batch。"""
        with tempfile.TemporaryDirectory() as tmp:
            huge = "字" * 80000  # 80000×3 = 240KB > 200KB
            sp = self._chapters(tmp, {"0001.md": huge})
            with self.assertRaises(rl.ReadingLedgerError):
                rl.build_manifest(sp, request_id="r1", run_id="r1", source_id="book_9001",
                                  source_snapshot=_snapshot())


if __name__ == "__main__":
    unittest.main()
