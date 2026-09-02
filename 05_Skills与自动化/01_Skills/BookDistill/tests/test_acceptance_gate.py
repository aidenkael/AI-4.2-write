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
                source_sha256: str = FINGERPRINT, write_report: bool = True):
    asset_dir = root / "02_素材知识库" / "book_9001_测试书"
    bkp = asset_dir / "bkp"
    (bkp / "knowledge").mkdir(parents=True)
    identity = {
        "bkp_version": "0.2",
        "book": {"book_id": "book_9001", "title": "测试书", "author": "作者",
                 "category": "", "language": "zh-CN", "chapter_count": 2},
        "source_snapshot": {"book_id": "book_9001", "source_sha256": source_sha256,
                            "chapter_count": 2},
        "schema_status": "FINALIZED",
    }
    (bkp / "identity.json").write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8")
    (bkp / "knowledge" / "cards.md").write_text(_cards_md(card_count), encoding="utf-8")
    sp_chapters = root / "06_工作区" / "SourcePrepare" / "book_9001_测试书" / "chapters"
    sp_chapters.mkdir(parents=True)
    (sp_chapters / "0001.md").write_text("第一章正文", encoding="utf-8")
    (sp_chapters / "0002.md").write_text("第二章正文", encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
