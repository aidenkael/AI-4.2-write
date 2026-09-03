# -*- coding: utf-8 -*-
"""Materials 作者面 BKP 全书验收状态可见性（检查点 4 §25）。

确定性读 bkp/identity.json 的 acceptance 块：
- 新协议包：BKP 可检索 / 需要复核 / 未完成全书验收；
- 旧版包（无 acceptance 块）：保持原有“可用”语义，不追溯。
零模型、零写副作用。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from operations import materials  # noqa: E402


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    root = tmp_path / "root"
    (root / "02_素材知识库").mkdir(parents=True)
    monkeypatch.setattr(materials, "get_repo_root", lambda: root)
    return root


def _asset():
    return {
        "id": "book_0001",
        "name": "样例作品",
        "type": "REFERENCE_WORK",
        "purification": {"status": "可用"},
        "knowledge": {"status": "可用"},
    }


def _write_bkp(root: Path, acceptance: dict | None):
    bkp = root / "02_素材知识库" / "book_0001_样例作品" / "bkp"
    bkp.mkdir(parents=True)
    identity = {
        "bkp_version": "0.2",
        "book": {"book_id": "book_0001", "title": "样例作品", "author": "作者"},
        "schema_status": "FINALIZED",
    }
    if acceptance is not None:
        identity["acceptance"] = acceptance
    (bkp / "identity.json").write_text(json.dumps(identity, ensure_ascii=False), encoding="utf-8")


def test_acceptance_pass_shows_bkp_searchable(isolated):
    _write_bkp(isolated, {"schema": "gowrite_bkp_acceptance/v1", "required": True, "status": "PASS"})
    classified = materials._classify_author_group(_asset())
    assert classified["writing_callable"] is True
    assert classified["state"] == "ready"


def test_acceptance_review_blocks_retrieval_with_honest_label(isolated):
    _write_bkp(isolated, {"schema": "gowrite_bkp_acceptance/v1", "required": True, "status": "REVIEW"})
    classified = materials._classify_author_group(_asset())
    assert classified["writing_callable"] is False
    assert classified["state"] == "needs_attention"


def test_acceptance_pending_shows_not_completed(isolated):
    _write_bkp(isolated, {"schema": "gowrite_bkp_acceptance/v1", "required": True, "status": "PENDING"})
    classified = materials._classify_author_group(_asset())
    assert classified["writing_callable"] is False
    assert classified["state"] == "needs_attention"


def test_legacy_package_without_acceptance_keeps_old_semantics(isolated):
    _write_bkp(isolated, None)
    classified = materials._classify_author_group(_asset())
    assert classified["writing_callable"] is True
    assert classified["state"] == "ready"


def test_no_bkp_directory_requires_real_loader_discovery(isolated):
    classified = materials._classify_author_group(_asset())
    assert classified["writing_callable"] is False
    assert classified["state"] == "needs_attention"
