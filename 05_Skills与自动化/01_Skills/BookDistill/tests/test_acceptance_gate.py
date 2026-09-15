# -*- coding: utf-8 -*-
"""BookDistill 全书验收门（acceptance_gate）确定性测试。

覆盖任务书检查点 4 §26：
- 新协议 PASS 验证通过
- 缺失卡 id / 身份指纹不一致 / blocking 缺口 + PASS / REVIEW 不可检索
- evidence 溯源格式校验
- --write-identity 只在通过后写入
零模型、零网络、零真实书籍（全部 tmp fixture）。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from acceptance_gate import (  # noqa: E402
    ACCEPTANCE_SCHEMA,
    REPORT_NAME,
    validate_acceptance,
    write_identity_acceptance,
)
import reading_ledger as rl  # noqa: E402
import reader_continuity as rc  # noqa: E402


FINGERPRINT = "f" * 64


def _cards_md(count: int = 2) -> str:
    lines = ["# Cards", ""]
    for i in range(1, count + 1):
        lines += [
            f"## K{i:03d}｜测试卡 {i}",
            "",
            "- statement: 测试结论。",
            "- evidence:",
            "  - chapters/0001.md#L3",
            "",
        ]
    return "\n".join(lines)


def _acceptance_data(**overrides):
    data = {
        "schema": ACCEPTANCE_SCHEMA,
        "book_id": "book_9001",
        "title": "测试书",
        "source_sha256": FINGERPRINT,
        "protocol": ACCEPTANCE_SCHEMA,
        "status": "PASS",
        "canonical_card_count": 2,
        "findings": [
            {
                "finding": "全书级机制：三层时钟接力",
                "accepted": True,
                "card_ids": ["K001", "K002"],
            },
        ],
        "unresolved_gaps": [],
        "retrieval_ready": True,
    }
    data.update(overrides)
    return data


def _report_md(data: dict) -> str:
    return (
        "# BKP 验收报告：《测试书》（book_9001）\n\n"
        "## 结论\n\n测试结论。\n\n"
        "```json\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n```\n"
    )


def _make_asset(root: Path, *, data: dict | None = None, card_count: int = 2,
                source_sha256: str = FINGERPRINT, write_report: bool = True,
                ledger_complete: bool = True, all_six_domains: bool = True,
                write_manifest_ledger: bool = True, continuity_complete: bool = True):
    asset_dir = root / "02_素材知识库" / "book_9001_测试书"
    bkp = asset_dir / "bkp"
    (bkp / "knowledge").mkdir(parents=True)
    snapshot = {"book_id": "book_9001", "sp_version": "0.4.0",
                "source_sha256": source_sha256, "chapter_count": 2,
                "chapter_content_fingerprint": "c" * 64,
                "unit_semantics": "chapter", "unit_boundary_source": "epub_heading"}
    identity = {
        "bkp_version": "0.2",
        "book": {"book_id": "book_9001", "title": "测试书", "author": "作者",
                 "category": "", "language": "zh-CN", "chapter_count": 2},
        "source_snapshot": snapshot,
        "schema_status": "FINALIZED",
    }
    (bkp / "identity.json").write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8")
    (bkp / "knowledge" / "cards.md").write_text(_cards_md(card_count), encoding="utf-8")
    stats = {"FACT": 1, "INFERENCE": 0, "OBSERVATION": 0, "MECHANISM": 0, "BOUNDARY": 0}
    manifest = {
        "source_snapshot": snapshot, "unit_semantics": "chapter",
        "unit_boundary_source": "epub_heading", "total_entries": 1,
        "stats_by_kind": stats, "scan_coverage": {"ok": True, "blocking": []},
    }
    (asset_dir / "distill_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (asset_dir / "bd_report.md").write_text(
        "\n".join(["# 蒸馏报告", "", "- 输入单元语义：chapter",
                    "- 证据条目总数：1", f"- 分类统计：{json.dumps(stats, ensure_ascii=False)}",
                    ""]), encoding="utf-8")
    # SourcePrepare 快照（2 章）——reading manifest 覆盖验证的权威来源。
    sp_dir = root / "06_工作区" / "SourcePrepare" / "book_9001_测试书"
    sp_chapters = sp_dir / "chapters"
    sp_chapters.mkdir(parents=True)
    (sp_chapters / "0001.md").write_text("第一章正文", encoding="utf-8")
    (sp_chapters / "0002.md").write_text("第二章正文", encoding="utf-8")
    # Reading manifest + ledger（绑定同一 snapshot；全书阅读完成度权威）。
    if write_manifest_ledger:
        rmanifest = rl.build_manifest(sp_dir, request_id="req1", run_id="req1",
                                      source_id="book_9001", source_snapshot=snapshot)
        rl.write_manifest(asset_dir, rmanifest)
        rl.init_ledger(asset_dir, rmanifest)
        rc.initialize_state(asset_dir, rmanifest)
        if ledger_complete:
            domains = list(rl.SIX_DOMAINS) if all_six_domains else list(rl.SIX_DOMAINS)[:-1]
            while True:
                nb = rl.next_pending_batch(asset_dir)
                if nb is None:
                    break
                bid = nb["batch_id"]
                note = rl.batch_notes_dir(asset_dir) / f"{bid}.md"
                text = rl.render_batch_note_template(
                    batch_id=bid, request_id="req1", run_id="req1",
                    manifest_hash=rmanifest["manifest_hash"],
                    source_fingerprint=rmanifest["source_fingerprint"],
                    spans=nb["spans"], required_domains=tuple(domains))
                note.write_text(text, encoding="utf-8")
                rl.commit_batch(asset_dir, bid, note, required_domains=tuple(domains))
        if continuity_complete:
            while True:
                nxt = rc.next_batch_payload(asset_dir, rmanifest)
                if nxt.get("complete"):
                    break
                token = "acceptance-fixture"
                candidate = rc.render_candidate_template(rmanifest, nxt)
                candidate["experience_update"] = f"{nxt['batch_id']} 的阅读体验变化。"
                candidate["rolling_state"] = f"已顺序读到 {nxt['batch_id']}，保留当前疑问。"
                path = rc.unique_temp_candidate_path(asset_dir, nxt["batch_id"], token)
                path.write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")
                rc.commit_candidate(asset_dir, nxt["batch_id"], path,
                                    lease_token=token, manifest=rmanifest)
    if write_report:
        (asset_dir / REPORT_NAME).write_text(_report_md(data or _acceptance_data()), encoding="utf-8")
    return asset_dir


class AcceptanceGateTest(unittest.TestCase):
    def test_new_protocol_pass_validates_and_writes_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset_dir = _make_asset(root)
            result = validate_acceptance(asset_dir, root)
            self.assertTrue(result["ok"], result["errors"])
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["retrieval_ready"])
            self.assertEqual(result["card_count"], 2)

            write_identity_acceptance(asset_dir, result)
            identity = json.loads((asset_dir / "bkp" / "identity.json").read_text(encoding="utf-8"))
            self.assertEqual(identity["acceptance"]["status"], "PASS")
            self.assertTrue(identity["acceptance"]["required"])
            self.assertEqual(identity["bkp_protocol_version"], "0.3")

    def test_missing_card_id_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = _acceptance_data(findings=[
                {"finding": "发现", "accepted": True, "card_ids": ["K003"]},
            ])
            asset_dir = _make_asset(root, data=data)
            result = validate_acceptance(asset_dir, root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("K003" in e for e in result["errors"]))

    def test_identity_fingerprint_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = _acceptance_data(source_sha256="0" * 64)
            asset_dir = _make_asset(root, data=data)
            result = validate_acceptance(asset_dir, root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("指纹" in e for e in result["errors"]))

    def test_identity_book_id_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = _acceptance_data(book_id="book_8888")
            asset_dir = _make_asset(root, data=data)
            result = validate_acceptance(asset_dir, root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("book_id" in e for e in result["errors"]))

    def test_blocking_gap_with_pass_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = _acceptance_data(unresolved_gaps=[
                {"description": "覆盖缺口", "blocking": True},
            ])
            asset_dir = _make_asset(root, data=data)
            result = validate_acceptance(asset_dir, root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("blocking" in e for e in result["errors"]))

    def test_review_is_not_retrieval_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = _acceptance_data(status="REVIEW", retrieval_ready=False)
            asset_dir = _make_asset(root, data=data)
            result = validate_acceptance(asset_dir, root)
            self.assertTrue(result["ok"], result["errors"])
            self.assertEqual(result["status"], "REVIEW")
            self.assertFalse(result["retrieval_ready"])
            with self.assertRaises(RuntimeError):
                write_identity_acceptance(asset_dir, result)

    def test_retrieval_ready_must_match_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = _acceptance_data(status="REVIEW", retrieval_ready=True)
            asset_dir = _make_asset(root, data=data)
            result = validate_acceptance(asset_dir, root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("retrieval_ready" in e for e in result["errors"]))

    def test_card_count_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = _acceptance_data(canonical_card_count=5)
            asset_dir = _make_asset(root, data=data)
            result = validate_acceptance(asset_dir, root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("canonical_card_count" in e for e in result["errors"]))

    def test_excluded_finding_requires_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = _acceptance_data(findings=[
                {"finding": "重要但太局部", "accepted": False},
            ])
            asset_dir = _make_asset(root, data=data)
            result = validate_acceptance(asset_dir, root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("exclusion_reason" in e for e in result["errors"]))

    def test_bad_evidence_format_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset_dir = _make_asset(root)
            cards = (asset_dir / "bkp" / "knowledge" / "cards.md")
            cards.write_text(
                cards.read_text(encoding="utf-8").replace("chapters/0001.md#L3", "p123"),
                encoding="utf-8",
            )
            result = validate_acceptance(asset_dir, root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("evidence" in e for e in result["errors"]))

    def test_missing_report_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset_dir = _make_asset(root, write_report=False)
            result = validate_acceptance(asset_dir, root)
            self.assertFalse(result["ok"])
            self.assertTrue(any(REPORT_NAME in e for e in result["errors"]))

    def test_incomplete_ledger_rejects_pass(self):
        """ledger 未全部 completed 时必须失败（全书阅读未结算）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset_dir = _make_asset(root, ledger_complete=False)
            result = validate_acceptance(asset_dir, root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("ledger" in e or "completed" in e for e in result["errors"]))

    def test_incomplete_continuity_rejects_pass(self):
        """local ledger 完整也不能绕过 ordered continuity completion。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset_dir = _make_asset(root, continuity_complete=False)
            result = validate_acceptance(asset_dir, root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("continuity" in e for e in result["errors"]))

    def test_missing_manifest_ledger_rejects_pass(self):
        """仅有旧产物、无 reading manifest/ledger 时必须失败（scan_refs 不是权威）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset_dir = _make_asset(root, write_manifest_ledger=False)
            result = validate_acceptance(asset_dir, root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("reading_manifest" in e for e in result["errors"]))
            self.assertTrue(any("reading_ledger" in e for e in result["errors"]))

    def test_missing_six_domain_check_rejects_pass(self):
        """某个 completed batch 未检查全部六域时必须失败（0 findings 合法，unchecked 不合法）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset_dir = _make_asset(root, all_six_domains=False)
            result = validate_acceptance(asset_dir, root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("六域" in e for e in result["errors"]))

    def test_pass_writes_completion_receipt(self):
        """PASS + ledger 完整时 write_identity_acceptance 写出确定性 completion receipt。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset_dir = _make_asset(root)
            result = validate_acceptance(asset_dir, root)
            self.assertTrue(result["ok"], result["errors"])
            write_identity_acceptance(asset_dir, result)
            receipt = rl.read_completion_receipt(asset_dir)
            self.assertIsNotNone(receipt)
            self.assertEqual(receipt["request_id"], "req1")
            self.assertEqual(receipt["source_id"], "book_9001")
            self.assertEqual(receipt["acceptance_status"], "PASS")
            self.assertTrue(receipt["ledger_complete"])
            self.assertEqual(receipt["continuity_state_sha256"], rc.state_fingerprint(asset_dir))
            # receipt 严格匹配当前 active request/source 才有效。
            manifest = rl.read_manifest(asset_dir)
            ok = rl.validate_completion_receipt(
                receipt, asset_dir, request_id="req1", source_id="book_9001",
                source_snapshot=manifest["source_snapshot"])
            self.assertTrue(ok["ok"], ok["errors"])
            # request_id 不匹配的 receipt 一律无效。
            bad = rl.validate_completion_receipt(
                receipt, asset_dir, request_id="other", source_id="book_9001",
                source_snapshot=manifest["source_snapshot"])
            self.assertFalse(bad["ok"])

            # receipt 不能在其绑定的 continuity state 丢失后继续触发恢复。
            rc.state_path(asset_dir).unlink()
            missing_continuity = rl.validate_completion_receipt(
                receipt, asset_dir, request_id="req1", source_id="book_9001",
                source_snapshot=manifest["source_snapshot"])
            self.assertFalse(missing_continuity["ok"])
            self.assertTrue(any("continuity" in e for e in missing_continuity["errors"]))

    def test_bd_report_manifest_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset_dir = _make_asset(root)
            report = asset_dir / "bd_report.md"
            report.write_text(report.read_text(encoding="utf-8").replace("证据条目总数：1", "证据条目总数：0"), encoding="utf-8")
            result = validate_acceptance(asset_dir, root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("bd_report" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
