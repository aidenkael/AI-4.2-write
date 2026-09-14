# -*- coding: utf-8 -*-
"""Bridge completion-receipt 回退与 formal package allowlist 的 focused 回归。

覆盖任务书 §9 Bridge / materials lifecycle 检查点：
13. response 缺失 + 合法 deterministic completion receipt → finalize；
14. response 缺失 + 仅 identity PASS（无 receipt）→ 不 finalize；
15. stale / mismatched / canceled receipt → 不 finalize；
16. finalize 后 formal package 不含 _work / raw discovery / batch / temp script。
零模型、零网络、零真实书籍（全部 tmp fixture）。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from operations import materials  # noqa: E402


def _make_sp(root: Path, asset_id="book_0001", name="样例作品", chapters=2, sha="a" * 64):
    sp = root / "06_工作区" / "SourcePrepare" / f"{asset_id}_{name}"
    (sp / "chapters").mkdir(parents=True)
    for i in range(1, chapters + 1):
        (sp / "chapters" / f"{i:04d}.md").write_text(f"第{i}章正文\n" * 8, encoding="utf-8")
    (sp / "full.md").write_text("# full\n", encoding="utf-8")
    (sp / "conversion_report.md").write_text("# conversion report\n", encoding="utf-8")
    (sp / "metadata.json").write_text(json.dumps({
        "book_id": asset_id, "book": name, "status": "PASS", "skill_version": "0.4.0",
        "unit_semantics": "chapter", "unit_boundary_source": "epub_nav_anchor",
        "chapter_files": chapters, "selected_source": {"format": ".epub", "sha256": sha},
    }, ensure_ascii=False), encoding="utf-8")
    return sp


def _make_complete_stage(root: Path, sp: Path, asset_id="book_0001", name="样例作品",
                         request_id="req1", *, write_receipt=True, receipt_request_id=None):
    """构建 ledger 完整（+ 可选 receipt）的 06 staging。"""
    bd, rl = materials._load_book_distill_runtime()
    stage = root / "06_工作区" / "BookDistill" / f"{request_id}_{asset_id}_{name}"
    stage.mkdir(parents=True)
    snap = bd.validate_input(sp)["info"]["source_snapshot"]
    m = rl.build_manifest(sp, request_id=request_id, run_id=request_id,
                          source_id=asset_id, source_snapshot=snap)
    rl.write_manifest(stage, m)
    rl.init_ledger(stage, m)
    while True:
        nb = rl.next_pending_batch(stage)
        if nb is None:
            break
        bid = nb["batch_id"]
        note = rl.batch_notes_dir(stage) / f"{bid}.md"
        note.write_text(rl.render_batch_note_template(
            batch_id=bid, request_id=request_id, run_id=request_id,
            manifest_hash=m["manifest_hash"], source_fingerprint=m["source_fingerprint"],
            spans=nb["spans"]), encoding="utf-8")
        rl.commit_batch(stage, bid, note)
    if write_receipt:
        rl.write_completion_receipt(
            stage, request_id=receipt_request_id or request_id, run_id=request_id,
            source_id=asset_id, source_snapshot=snap, acceptance_status="PASS",
            canonical_card_count=2, gate_version="test")
    return stage, snap


# ---------------------------------------------------------------------------
# 检查点 16：formal package allowlist
# ---------------------------------------------------------------------------

def test_formal_candidate_excludes_process_artifacts(tmp_path):
    """formal candidate 只含 allowlist 正式文件；_work/discovery/evidence/临时脚本绝不进入。"""
    stage = tmp_path / "stage"
    (stage / "bkp" / "knowledge").mkdir(parents=True)
    (stage / "bkp" / "identity.json").write_text(json.dumps({"book": {"book_id": "b"}}), encoding="utf-8")
    (stage / "bkp" / "knowledge" / "cards.md").write_text("## K001｜卡\n", encoding="utf-8")
    (stage / "bkp" / "author_view.md").write_text("view\n", encoding="utf-8")
    (stage / "model.md").write_text("model\n", encoding="utf-8")
    (stage / "distill_manifest.json").write_text("{}", encoding="utf-8")
    (stage / "BKP_ACCEPTANCE_REPORT.md").write_text("report\n", encoding="utf-8")
    # 过程工件：绝不进入 02。
    (stage / "_work" / "batch_notes").mkdir(parents=True)
    (stage / "_work" / "reading_ledger.json").write_text("{}", encoding="utf-8")
    (stage / "_work" / "batch_notes" / "B0001.md").write_text("note\n", encoding="utf-8")
    (stage / "discovery").mkdir()
    (stage / "discovery" / "raw_observer.md").write_text("raw\n", encoding="utf-8")
    (stage / "evidence").mkdir()
    (stage / "evidence" / "ch_0001.md").write_text("per-chapter\n", encoding="utf-8")
    (stage / "bkp_prototype").mkdir()
    (stage / "bkp_prototype" / "identity.json").write_text("{}", encoding="utf-8")
    (stage / "temp_helper.py").write_text("# temp\n", encoding="utf-8")

    candidate = tmp_path / "candidate"
    result = materials._build_reference_formal_candidate(stage, candidate)
    assert result["ok"], result["missing"]
    # 正式文件已投影。
    assert (candidate / "bkp" / "identity.json").is_file()
    assert (candidate / "bkp" / "knowledge" / "cards.md").is_file()
    assert (candidate / "model.md").is_file()
    # 过程工件绝不进入 candidate。
    assert not (candidate / "_work").exists()
    assert not (candidate / "discovery").exists()
    assert not (candidate / "evidence").exists()
    assert not (candidate / "bkp_prototype").exists()
    assert not (candidate / "temp_helper.py").exists()


def test_formal_candidate_reports_missing_required_files(tmp_path):
    stage = tmp_path / "stage"
    (stage / "bkp").mkdir(parents=True)
    candidate = tmp_path / "candidate"
    result = materials._build_reference_formal_candidate(stage, candidate)
    assert not result["ok"]
    assert "bkp/identity.json" in result["missing"]


# ---------------------------------------------------------------------------
# 检查点 13/14/15：response 缺失回退只认合法 deterministic receipt
# ---------------------------------------------------------------------------

def test_receipt_fallback_finalizes_on_valid_receipt(tmp_path, monkeypatch):
    """检查点 13：response 缺失 + 合法 receipt（匹配当前 request/source）→ 进入 finalize。"""
    root = tmp_path
    sp = _make_sp(root)
    stage, snap = _make_complete_stage(root, sp, request_id="req1")
    called = {}

    def fake_finalize(request_id, asset_id, sp_dir, stage_dir):
        called["args"] = (request_id, asset_id, str(sp_dir), str(stage_dir))
        return {"asset_id": asset_id, "status": "completed", "output_dir": "02/x"}

    monkeypatch.setattr(materials, "_finalize_distill", fake_finalize)
    request = {"state": "pending", "meta": {
        "asset_id": "book_0001", "sp_dir": str(sp), "stage_dir": str(stage)}}
    result = materials._book_distill_receipt_finalize("req1", request, request["meta"])
    assert result is not None
    assert result["status"] == "completed"
    assert called["args"][0] == "req1" and called["args"][1] == "book_0001"


def test_receipt_fallback_rejects_identity_pass_without_receipt(tmp_path, monkeypatch):
    """检查点 14：response 缺失 + 仅 identity PASS（无 receipt）→ 不 finalize，保持 pending。"""
    root = tmp_path
    sp = _make_sp(root)
    # ledger 完整但绝不写 receipt；只伪造一个 identity.json PASS。
    stage, snap = _make_complete_stage(root, sp, request_id="req1", write_receipt=False)
    (stage / "bkp").mkdir(parents=True, exist_ok=True)
    (stage / "bkp" / "identity.json").write_text(json.dumps({
        "book": {"book_id": "book_0001", "title": "样例作品"},
        "acceptance": {"required": True, "status": "PASS"},
    }, ensure_ascii=False), encoding="utf-8")

    def boom(*a, **k):  # finalize 绝不应被调用
        raise AssertionError("must not finalize without a valid receipt")

    monkeypatch.setattr(materials, "_finalize_distill", boom)
    request = {"state": "pending", "meta": {
        "asset_id": "book_0001", "sp_dir": str(sp), "stage_dir": str(stage)}}
    assert materials._book_distill_receipt_finalize("req1", request, request["meta"]) is None


def test_receipt_fallback_rejects_mismatched_request(tmp_path, monkeypatch):
    """检查点 15：receipt 的 request_id 与当前 active request 不一致 → 不 finalize。"""
    root = tmp_path
    sp = _make_sp(root)
    # receipt 绑定 req_OLD，但当前 active request 是 req_NEW。
    stage, snap = _make_complete_stage(root, sp, request_id="req_OLD")

    def boom(*a, **k):
        raise AssertionError("must not finalize on mismatched receipt")

    monkeypatch.setattr(materials, "_finalize_distill", boom)
    request = {"state": "pending", "meta": {
        "asset_id": "book_0001", "sp_dir": str(sp), "stage_dir": str(stage)}}
    assert materials._book_distill_receipt_finalize("req_NEW", request, request["meta"]) is None


def test_receipt_fallback_rejects_canceled_request(tmp_path, monkeypatch):
    """检查点 15：canceled request 的 receipt 一律不触发 finalize。"""
    root = tmp_path
    sp = _make_sp(root)
    stage, snap = _make_complete_stage(root, sp, request_id="req1")

    def boom(*a, **k):
        raise AssertionError("must not finalize a canceled request")

    monkeypatch.setattr(materials, "_finalize_distill", boom)
    request = {"state": "canceled", "meta": {
        "asset_id": "book_0001", "sp_dir": str(sp), "stage_dir": str(stage)}}
    assert materials._book_distill_receipt_finalize("req1", request, request["meta"]) is None


def test_receipt_fallback_rejects_stale_source_fingerprint(tmp_path, monkeypatch):
    """检查点 15：source fingerprint 已变化（当前 SP 与 receipt 不一致）→ 不 finalize。"""
    root = tmp_path
    sp = _make_sp(root, sha="a" * 64)
    stage, snap = _make_complete_stage(root, sp, request_id="req1")
    # 当前来源变化：重写 SP 章节内容 → chapter_content_fingerprint 改变。
    (sp / "chapters" / "0001.md").write_text("完全不同的新内容\n" * 20, encoding="utf-8")

    def boom(*a, **k):
        raise AssertionError("must not finalize on stale source fingerprint")

    monkeypatch.setattr(materials, "_finalize_distill", boom)
    request = {"state": "pending", "meta": {
        "asset_id": "book_0001", "sp_dir": str(sp), "stage_dir": str(stage)}}
    assert materials._book_distill_receipt_finalize("req1", request, request["meta"]) is None
