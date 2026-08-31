# -*- coding: utf-8 -*-
import hashlib
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))

import project_workspace  # noqa: E402
from operations import author_edit, change_settlement, project_snapshot  # noqa: E402
from bridge import app_api  # noqa: E402


@pytest.fixture()
def project(tmp_path, monkeypatch):
    root = tmp_path / "03_作品工程"
    root.mkdir()
    monkeypatch.setattr(project_workspace, "get_projects_root", lambda: root)
    return project_workspace.create_project(name="正文编辑", author_intent={
        "work_direction": "方向", "reader_promise": "期待", "hard_constraints": [], "open_space": [],
    })


def _empty_hash() -> str:
    return hashlib.sha256(b"").hexdigest()


def test_manual_prose_save_is_atomic_indexed_pending_and_stale_guarded(project):
    author_edit.create_chapter(project["project_id"], chapter_number=1)
    saved = author_edit.save_formal_prose(
        project["project_id"], chapter_number=1, base_content_sha256=_empty_hash(), content="第一版正文",
    )
    assert saved["change"]["status"] == "pending"
    loaded = project_workspace.load_project(project["project_dir"])
    entry = loaded["index"]["entries"][0]
    assert entry["revision_kind"] == "author_edited_chapter"
    assert entry["start_char"] == 0 and entry["end_char"] == len("第一版正文")
    assert project_workspace.get_recent_prose(project["project_dir"])["text"] == "第一版正文"
    with pytest.raises(author_edit.AuthorEditError, match="stale"):
        author_edit.save_formal_prose(
            project["project_id"], chapter_number=1, base_content_sha256=_empty_hash(), content="覆盖",
        )


def test_second_manual_edit_supersedes_old_ranges_without_losing_history(project):
    author_edit.create_chapter(project["project_id"], chapter_number=1)
    first = author_edit.save_formal_prose(
        project["project_id"], chapter_number=1, base_content_sha256=_empty_hash(), content="第一版",
    )
    second = author_edit.save_formal_prose(
        project["project_id"], chapter_number=1, base_content_sha256=first["content_sha256"], content="完整第二版",
    )
    index = json.loads((Path(project["project_dir"]) / "_工作台状态" / "accepted_text_index.json").read_text(encoding="utf-8"))
    assert len(index["entries"]) == 1
    assert len(index["superseded_entries"]) == 1
    assert index["entries"][0]["content_sha256"] == second["content_sha256"]
    assert project_workspace.get_recent_prose(project["project_dir"])["text"] == "完整第二版"


def test_save_rolls_back_chapter_and_index_when_ledger_write_fails(project, monkeypatch):
    author_edit.create_chapter(project["project_id"], chapter_number=1)
    project_dir = Path(project["project_dir"])
    chapter = project_dir / "03_正文" / "第001章.md"
    index = project_dir / "_工作台状态" / "accepted_text_index.json"
    chapter_before = chapter.read_bytes()
    index_before = index.read_bytes()
    real_append = author_edit._append_change
    monkeypatch.setattr(author_edit, "_append_change", lambda *args, **kwargs: (_ for _ in ()).throw(author_edit.AuthorEditError("ledger failed")))
    with pytest.raises(author_edit.AuthorEditError, match="已回滚"):
        author_edit.save_formal_prose(
            project["project_id"], chapter_number=1, base_content_sha256=_empty_hash(), content="不能丢失",
        )
    assert chapter.read_bytes() == chapter_before
    assert index.read_bytes() == index_before
    monkeypatch.setattr(author_edit, "_append_change", real_append)


def test_semantic_mechanical_writeback_and_ambiguous_confirmation(project):
    author_edit.create_chapter(project["project_id"], chapter_number=1)
    saved = author_edit.save_formal_prose(
        project["project_id"], chapter_number=1, base_content_sha256=_empty_hash(), content="一年后，他回到城门。",
    )
    change_id = saved["change"]["change_id"]
    result = change_settlement.apply_semantic_result(project["project_id"], change_id, {
        "summary": "识别相对时间与可选人物情绪",
        "consequences": [
            {"classification": "mechanically_certain", "kind": "time", "action": "create",
             "target_ref": "", "title": "一年后回城", "source_ref": "", "target_character_ref": "",
             "data": {"relative_duration": "1 year", "ordering": "after previous chapter"}, "reason": "正文明确"},
            {"classification": "ambiguous", "kind": "character", "action": "create",
             "target_ref": "", "title": "他", "source_ref": "", "target_character_ref": "",
             "data": {"emotion": "释然"}, "reason": "情绪未明说"},
        ],
    })
    assert result["status"] == "awaiting_author"
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert any(item["title"] == "一年后回城" for item in snapshot["current"]["events"])
    assert not any(item["title"] == "他" for item in snapshot["current"]["characters"])
    confirmed = change_settlement.confirm_ambiguous_consequences(project["project_id"], change_id, [1])
    assert confirmed["status"] == "synchronized"
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert any(item["title"] == "他" for item in snapshot["current"]["characters"])


def test_story_state_record_can_be_safely_overlaid_and_retired(project):
    state_path = Path(project["project_dir"]) / "_工作台状态" / "story_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["character_state"] = [{"id": "c1", "name": "旧名", "authority": "accepted_text:s1"}]
    state["state_rev"] = 2
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    raw_ref = "story_state:character_state:c1"
    edited = author_edit.update_foundation_record(
        project["project_id"], base_model_rev=0, ref=raw_ref, title="作者新名",
        material_state="current", data={"role": "主角"},
    )
    assert edited["change"]["delta"]["direct_impact"]["source_model_rev"] == edited["model"]["model_rev"]
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert [item["title"] for item in snapshot["current"]["characters"]] == ["作者新名"]
    assert json.loads(state_path.read_text(encoding="utf-8"))["character_state"][0]["name"] == "旧名"

    author_edit.retire_foundation_record(
        project["project_id"], base_model_rev=edited["model"]["model_rev"],
        ref=snapshot["current"]["characters"][0]["ref"],
    )
    assert project_snapshot.get_project_snapshot(project["project_id"])["current"]["characters"] == []


def test_legacy_relationship_exact_endpoints_promote_to_editable_contract(project):
    state_path = Path(project["project_dir"]) / "_工作台状态" / "story_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["character_state"] = [
        {"id": "c1", "name": "甲", "authority": "accepted_text:s1"},
        {"id": "c2", "name": "乙", "authority": "accepted_text:s1"},
    ]
    state["relationship_state"] = [
        {"id": "r1", "description": "旧识", "targets": ["c1", "c2"], "authority": "accepted_text:s1"},
    ]
    state["state_rev"] = 2
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    refs = {item["title"]: item["ref"] for item in snapshot["current"]["characters"]}
    relation_ref = snapshot["current"]["relationships"][0]["ref"]

    edited = author_edit.update_relationship(
        project["project_id"], base_model_rev=0, ref=relation_ref,
        source_ref=refs["甲"], target_ref=refs["乙"], label="盟友",
        material_state="current", data={"description": "共同调查"},
    )
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert [item["title"] for item in snapshot["current"]["relationships"]] == ["盟友"]
    assert snapshot["current"]["relationships"][0]["editable"] is True
    assert edited["change"]["status"] == "pending"
    assert edited["change"]["requires_semantic"] is True


def test_failed_semantic_writeback_keeps_edit_and_can_retry(project):
    author_edit.create_chapter(project["project_id"], chapter_number=1)
    saved = author_edit.save_formal_prose(
        project["project_id"], chapter_number=1, base_content_sha256=_empty_hash(), content="一年后回城。",
    )
    change_id = saved["change"]["change_id"]
    with pytest.raises(change_settlement.ChangeSettlementError):
        change_settlement.apply_semantic_result(project["project_id"], change_id, {
            "summary": "失败样例",
            "consequences": [{
                "classification": "mechanically_certain", "kind": "character", "action": "update",
                "target_ref": "missing", "title": "不存在", "data": {}, "reason": "测试",
            }],
        })
    assert author_edit.get_change(project["project_id"], change_id)["status"] == "failed"
    assert (Path(project["project_dir"]) / "03_正文" / "第001章.md").read_text(encoding="utf-8") == "一年后回城。"

    retried = change_settlement.apply_semantic_result(project["project_id"], change_id, {
        "summary": "重试成功",
        "consequences": [{
            "classification": "mechanically_certain", "kind": "time", "action": "create",
            "target_ref": "", "title": "一年后", "data": {"relative_duration": "一年"}, "reason": "正文明确",
        }],
    })
    assert retried["status"] == "synchronized"
    assert project_snapshot.get_project_snapshot(project["project_id"])["settlement"]["status"] == "synchronized"


def test_application_boundary_never_auto_starts_settlement(project, monkeypatch):
    created = author_edit.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character", title="林澈",
        material_state="current", data={"one_line_intro": "调查者"},
    )
    called = []
    monkeypatch.setattr(app_api.change_settlement_ops, "prepare_project_state_refresh", lambda *_args: called.append(True))
    assert created["change"]["status"] == "pending"
    assert called == []


def test_deterministic_change_stays_synchronized_without_ai(project, monkeypatch):
    author_edit.create_chapter(project["project_id"], chapter_number=1)
    change = author_edit.get_author_edit_surface(project["project_id"])["settlement"]["changes"][-1]
    called = []
    monkeypatch.setattr(app_api.change_settlement_ops, "prepare_project_state_refresh", lambda *_args: called.append(True))
    assert called == []
    assert change["status"] == "synchronized"


def test_application_boundary_keeps_durable_edit_pending_without_config(project, monkeypatch):
    created = author_edit.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character", title="林澈",
        material_state="current", data={"one_line_intro": "调查者"},
    )
    assert created["change"]["status"] == "pending"
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert [item["title"] for item in snapshot["current"]["characters"]] == ["林澈"]


def _wait_refresh(project_id: str, timeout: float = 3.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = change_settlement.get_project_state_refresh(project_id)
        if state["status"] != "running":
            return state
        time.sleep(0.01)
    raise AssertionError("project refresh did not finish")


def test_project_refresh_batches_and_coalesces_latest_prose(project, monkeypatch):
    author_edit.create_chapter(project["project_id"], chapter_number=1)
    first = author_edit.save_formal_prose(
        project["project_id"], chapter_number=1, base_content_sha256=_empty_hash(), content="旧稿内容",
    )
    author_edit.save_formal_prose(
        project["project_id"], chapter_number=1, base_content_sha256=first["content_sha256"], content="最新正文",
    )
    calls: list[str] = []
    monkeypatch.setattr(change_settlement.semantic_ai, "require_semantic_ai", lambda: (object(), "secret"))
    monkeypatch.setattr(change_settlement.semantic_ai, "run_text", lambda prompt: calls.append(prompt) or json.dumps({
        "summary": "已整理", "consequences": [],
        "chapter_actual_results": [{"chapter_number": 1, "result": {"summary": "最新正文结果"}}],
    }, ensure_ascii=False))
    started = change_settlement.prepare_project_state_refresh(project["project_id"])
    assert started["status"] == "running"
    state = _wait_refresh(project["project_id"])
    assert state["status"] == "synchronized"
    assert len(calls) == 1
    assert "最新正文" in calls[0] and "旧稿内容" not in calls[0]
    ledger = author_edit.get_change_ledger(project["project_id"])
    assert all(item["status"] == "synchronized" for item in ledger["changes"] if item["requires_semantic"])
    change_settlement.prepare_project_state_refresh(project["project_id"])
    assert len(calls) == 1, "zero pending changes must not call Direct AI"


def test_project_refresh_cutoff_leaves_concurrent_save_pending(project, monkeypatch):
    import threading
    author_edit.create_chapter(project["project_id"], chapter_number=1)
    first = author_edit.save_formal_prose(
        project["project_id"], chapter_number=1, base_content_sha256=_empty_hash(), content="刷新前正文",
    )
    entered, release = threading.Event(), threading.Event()
    monkeypatch.setattr(change_settlement.semantic_ai, "require_semantic_ai", lambda: (object(), "secret"))
    def run_text(_prompt):
        entered.set()
        assert release.wait(2)
        return json.dumps({"summary": "已整理", "consequences": [], "chapter_actual_results": []}, ensure_ascii=False)
    monkeypatch.setattr(change_settlement.semantic_ai, "run_text", run_text)
    change_settlement.prepare_project_state_refresh(project["project_id"])
    assert entered.wait(1)
    author_edit.save_formal_prose(
        project["project_id"], chapter_number=1, base_content_sha256=first["content_sha256"], content="刷新后正文",
    )
    release.set()
    assert _wait_refresh(project["project_id"])["status"] == "synchronized"
    ledger = author_edit.get_change_ledger(project["project_id"])
    assert ledger["changes"][-1]["status"] == "pending"
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert snapshot["chapters"][0]["content"] == "刷新后正文"
