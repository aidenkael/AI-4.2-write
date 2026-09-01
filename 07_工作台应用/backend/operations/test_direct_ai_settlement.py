# -*- coding: utf-8 -*-
"""Focused regression tests: Direct AI semantic settlement (M2).

Only fake/monkeypatched HTTP layers are used; zero paid/network inference,
zero Agent execution, zero /gowrite activation.
"""
import json
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"),
)

import project_workspace  # noqa: E402
from ai import runner as semantic_ai  # noqa: E402
from operations import (  # noqa: E402
    agent_runner,
    author_edit,
    change_settlement,
    project_model,
    project_snapshot,
    qoder_bridge as bridge,
)


@pytest.fixture()
def projects_root(tmp_path, monkeypatch):
    root = tmp_path / "03_作品工程"
    root.mkdir()
    monkeypatch.setattr(project_workspace, "get_projects_root", lambda: root)
    return root


@pytest.fixture()
def isolated_bridge(tmp_path, monkeypatch):
    root = tmp_path / "bridge"
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: root)
    return root


@pytest.fixture()
def configured_ai(monkeypatch):
    config = semantic_ai.SemanticAiConfig(base_url="http://fake.local/v1", model="fake-model")
    monkeypatch.setattr(
        change_settlement.semantic_ai, "require_semantic_ai", lambda: (config, "fake-key"),
    )
    return config


def _create(name: str):
    return project_workspace.create_project(name=name, author_intent={
        "work_direction": "测试语义结算",
        "reader_promise": "日常同步不占用 Agent",
        "hard_constraints": [],
        "open_space": [],
    })


def _character(project_id: str, title: str) -> tuple[str, int]:
    created = author_edit.create_foundation_record(
        project_id, base_model_rev=project_model.read_project_model(project_id)["model_rev"],
        category="character", title=title, material_state="current", data={},
    )
    ref = created["model"]["change_history"][-1]["detail"]["ref"]
    return ref, created["model"]["model_rev"]


def _edit(project_id: str, base_rev: int, ref: str, note: str):
    return author_edit.update_foundation_record(
        project_id, base_model_rev=base_rev, ref=ref, data={"current_state": note},
    )


def _wait_change(project_id: str, change_id: str, statuses, timeout: float = 10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        change = author_edit.get_change(project_id, change_id)
        if change["status"] in statuses:
            return change
        time.sleep(0.05)
    return author_edit.get_change(project_id, change_id)


def _join_worker(worker: threading.Thread | None) -> None:
    if worker is not None:
        worker.join(timeout=10)
        assert not worker.is_alive()


def _settle_explicit(project_id: str, change_id: str):
    """Prepare and wait for a NEW terminal state (stale failures are ignored)."""
    baseline = author_edit.get_change(project_id, change_id)
    change_settlement.prepare_change_settlement(project_id, change_id)
    worker = change_settlement._active_worker(project_id)
    deadline = time.time() + 10.0
    final = baseline
    while time.time() < deadline:
        final = author_edit.get_change(project_id, change_id)
        if final["status"] in {"synchronized", "awaiting_author"}:
            break
        if final["status"] == "failed" and (
            final.get("updated_at") != baseline.get("updated_at")
            or final.get("error") != baseline.get("error")
        ):
            break
        time.sleep(0.05)
    _join_worker(worker)
    ledger = author_edit._read_changes(author_edit._load(project_id)[2], project_id)["changes"]
    diagnostics = (
        final.get("error"),
        [(c["change_id"], c["status"], c.get("error")) for c in ledger],
    )
    assert final["status"] in {"synchronized", "awaiting_author"}, diagnostics
    return final


def test_missing_config_preserves_durable_edit_and_zero_agent(
    projects_root, isolated_bridge, monkeypatch,
):
    def _needs_config():
        raise semantic_ai.SemanticAiConfigError("缺少日常 AI 设置")

    monkeypatch.setattr(change_settlement.semantic_ai, "require_semantic_ai", _needs_config)

    def _agent_forbidden(*args, **kwargs):
        raise AssertionError("日常语义结算绝不调用 Agent")

    monkeypatch.setattr(agent_runner, "_build_adapter", _agent_forbidden)

    project = _create("缺配置")
    ref, rev = _character(project["project_id"], "主角")
    edit = _edit(project["project_id"], rev, ref, "受伤")
    change_id = edit["change"]["change_id"]
    assert edit["change"]["requires_semantic"] is True

    with pytest.raises(change_settlement.ChangeSettlementError) as exc:
        change_settlement.prepare_change_settlement(project["project_id"], change_id)
    assert "日常 AI" in str(exc.value)

    failed = author_edit.get_change(project["project_id"], change_id)
    assert failed["status"] == "failed"
    assert failed["error"].startswith(change_settlement.NEEDS_CONFIG_PREFIX)

    # The durable author edit survives the semantic failure.
    model = project_model.read_project_model(project["project_id"])
    assert model["objects"][ref]["data"]["current_state"] == "受伤"

    # No /gowrite request, no bridge activation, no Agent slot.
    assert bridge.get_active_request_id() is None
    requests_dir = isolated_bridge / "requests"
    assert not requests_dir.exists() or not list(requests_dir.glob("*.json"))

    # One recoverable needs-config state is exposed to the author surface.
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert snapshot["settlement"]["needs_semantic_ai_config"] is True

    # Retry after configuration remains possible through the same change.
    payload = {"summary": "恢复后同步", "consequences": [], "chapter_actual_result": None, "planning_impact_candidate": None}
    config = semantic_ai.SemanticAiConfig(base_url="http://fake.local/v1", model="fake-model")
    monkeypatch.setattr(
        change_settlement.semantic_ai, "require_semantic_ai", lambda: (config, "fake-key"),
    )
    monkeypatch.setattr(
        change_settlement.semantic_ai, "run_text",
        lambda prompt, **kwargs: json.dumps(payload, ensure_ascii=False),
    )
    prepared = change_settlement.prepare_change_settlement(project["project_id"], change_id)
    assert prepared["request_started"] is True
    _settle_explicit(project["project_id"], change_id)


def test_valid_direct_ai_result_passes_existing_gates(
    projects_root, isolated_bridge, configured_ai, monkeypatch,
):
    project = _create("合法结果")
    ref, rev = _character(project["project_id"], "林砚")
    edit = _edit(project["project_id"], rev, ref, "进入封锁区")
    change_id = edit["change"]["change_id"]
    rev_before = edit["model"]["model_rev"]

    payload = {
        "summary": "同步人物状态与新事件",
        "consequences": [
            {
                "classification": "mechanically_certain", "kind": "character", "action": "update",
                "target_ref": ref, "title": "林砚状态更新",
                "data": {"current_objective": "调查封锁区"}, "reason": "本次编辑明确",
            },
            {
                "classification": "mechanically_certain", "kind": "event", "action": "create",
                "title": "进入封锁区",
                "data": {"description": "林砚进入封锁区"}, "reason": "本次编辑明确",
            },
        ],
        "chapter_actual_result": None,
        "planning_impact_candidate": None,
    }
    calls = []

    def fake_run_text(prompt, **kwargs):
        calls.append(prompt)
        return json.dumps(payload, ensure_ascii=False)

    monkeypatch.setattr(change_settlement.semantic_ai, "run_text", fake_run_text)

    prepared = change_settlement.prepare_change_settlement(project["project_id"], change_id)
    assert prepared["status"] == "pending"
    _settle_explicit(project["project_id"], change_id)
    # One call for this edit; the per-project drain also settles the pending
    # semantic change recorded by the character creation itself.
    assert len(calls) == 2

    model = project_model.read_project_model(project["project_id"])
    assert model["model_rev"] > rev_before
    assert model["objects"][ref]["data"]["current_objective"] == "调查封锁区"
    events = [
        item for item in model["objects"].values()
        if item.get("category") == "event" and not item.get("tombstoned")
    ]
    assert any(item["title"] == "进入封锁区" for item in events)


def test_invalid_direct_ai_result_fails_safely(
    projects_root, isolated_bridge, configured_ai, monkeypatch,
):
    project = _create("非法结果")
    ref, rev = _character(project["project_id"], "苏晚")
    edit = _edit(project["project_id"], rev, ref, "离开城市")
    change_id = edit["change"]["change_id"]
    rev_before = edit["model"]["model_rev"]

    monkeypatch.setattr(change_settlement.semantic_ai, "run_text", lambda prompt, **kwargs: "这不是 JSON")
    change_settlement.prepare_change_settlement(project["project_id"], change_id)
    worker = change_settlement._active_worker(project["project_id"])
    assert worker is not None
    final = _wait_change(project["project_id"], change_id, {"failed", "synchronized"})
    assert final["status"] == "failed", repr(final)
    assert "JSON" in (final.get("error") or "")
    # Durable edit preserved; no partial model mutation from invalid output.
    model = project_model.read_project_model(project["project_id"])
    assert model["model_rev"] == rev_before
    assert model["objects"][ref]["data"]["current_state"] == "离开城市"
    # This worker also drains the earlier pending foundation change.  Join the
    # actual worker before pytest restores mocks and removes this temp project.
    _join_worker(worker)


def test_rapid_edits_serialized_without_agent_or_duplicates(
    projects_root, isolated_bridge, configured_ai, monkeypatch,
):
    project = _create("快速编辑")
    ref, rev = _character(project["project_id"], "陈默")

    gate = threading.Event()
    first_call = {"done": False}
    lock = threading.Lock()

    def fake_run_text(prompt, **kwargs):
        with lock:
            is_first = not first_call["done"]
            first_call["done"] = True
        if is_first:
            gate.wait(10)
        return json.dumps(
            {"summary": "同步", "consequences": [], "chapter_actual_result": None, "planning_impact_candidate": None},
            ensure_ascii=False,
        )

    monkeypatch.setattr(change_settlement.semantic_ai, "run_text", fake_run_text)

    edit_a = _edit(project["project_id"], rev, ref, "状态A")
    prepared_a = change_settlement.prepare_change_settlement(project["project_id"], edit_a["change"]["change_id"])
    assert prepared_a["request_started"] is True

    edit_b = _edit(project["project_id"], edit_a["model"]["model_rev"], ref, "状态B")
    prepared_b = change_settlement.prepare_change_settlement(project["project_id"], edit_b["change"]["change_id"])
    # The first settlement is still running: B is drained by the same worker.
    assert prepared_b["queued"] is True and prepared_b["request_started"] is False

    edit_c = _edit(project["project_id"], edit_b["model"]["model_rev"], ref, "状态C")
    prepared_c = change_settlement.prepare_change_settlement(project["project_id"], edit_c["change"]["change_id"])
    assert prepared_c["queued"] is True and prepared_c["request_started"] is False

    gate.set()
    ids = [edit_a["change"]["change_id"], edit_b["change"]["change_id"], edit_c["change"]["change_id"]]
    assert len(set(ids)) == 3
    for edit_change_id in ids:
        final = _wait_change(project["project_id"], edit_change_id, {"synchronized", "awaiting_author", "failed"})
        assert final["status"] == "synchronized", final.get("error")
    _join_worker(change_settlement._active_worker(project["project_id"]))

    # No /gowrite activation, no Agent slot, no duplicate failure cards.
    assert bridge.get_active_request_id() is None
    model = project_model.read_project_model(project["project_id"])
    assert model["objects"][ref]["data"]["current_state"] == "状态C"


def test_cancel_settlement_dismisses_stale_tasks_and_live_request(
    projects_root, isolated_bridge, monkeypatch,
):
    def _needs_config():
        raise semantic_ai.SemanticAiConfigError("缺少日常 AI 设置")

    monkeypatch.setattr(change_settlement.semantic_ai, "require_semantic_ai", _needs_config)

    project = _create("取消同步")
    pid = project["project_id"]
    ref, rev = _character(pid, "主角")
    edit = _edit(pid, rev, ref, "受伤")
    edit_change_id = edit["change"]["change_id"]

    with pytest.raises(change_settlement.ChangeSettlementError):
        change_settlement.prepare_change_settlement(pid, edit_change_id)
    assert author_edit.get_change(pid, edit_change_id)["status"] == "failed"

    # No worker is running: stale/pending tasks must never read as “syncing”.
    assert change_settlement.has_active_worker(pid) is False

    # 1) Cancel the failed task: durable author edit preserved, task terminal.
    change_settlement.cancel_change_settlement(pid, edit_change_id)
    canceled = author_edit.get_change(pid, edit_change_id)
    assert canceled["status"] == "canceled" and canceled.get("error") is None
    model = project_model.read_project_model(pid)
    assert model["objects"][ref]["data"]["current_state"] == "受伤"

    # 2) Cancel a pending task that carries a live Direct AI request.
    ledger = author_edit._read_changes(author_edit._load(pid)[2], pid)["changes"]
    pending = [
        item for item in ledger
        if item.get("requires_semantic") and item.get("status") == "pending"
    ]
    assert pending, "character creation should leave one pending semantic change"
    pending_id = pending[0]["change_id"]
    rid = bridge.create_request(
        task="t", kind="change_settlement",
        meta={"project_id": pid, "change_id": pending_id},
        activate_for_gowrite=False,
    )
    author_edit.update_change(
        pid, pending_id, status="pending", settlement_request_id=rid, settlement_started=True,
    )
    change_settlement.cancel_change_settlement(pid, pending_id)
    assert bridge.get_request(rid)["state"] == "canceled"
    assert author_edit.get_change(pid, pending_id)["status"] == "canceled"

    # 3) All tasks dismissed: author surface returns to synchronized.
    snapshot = project_snapshot.get_project_snapshot(pid)
    assert snapshot["settlement"]["status"] == "synchronized"
    assert snapshot["settlement"]["pending_count"] == 0
    assert snapshot["settlement"]["failed_count"] == 0

    # 4) Terminal state cannot be retried or canceled again.
    with pytest.raises(change_settlement.ChangeSettlementError):
        change_settlement.prepare_change_settlement(pid, edit_change_id)
    with pytest.raises(change_settlement.ChangeSettlementError):
        change_settlement.cancel_change_settlement(pid, edit_change_id)


def test_mechanical_retire_or_duplicate_of_author_record_requires_confirmation(
    projects_root, isolated_bridge, configured_ai, monkeypatch,
):
    project = _create("主权门控")
    pid = project["project_id"]
    ref, rev = _character(pid, "林砚")

    payload = {
        "summary": "试图机械退役作者记录并同名重复创建",
        "consequences": [
            {"classification": "mechanically_certain", "kind": "character", "action": "retire",
             "target_ref": ref, "title": "退役林砚", "source_ref": "", "target_character_ref": "",
             "data": {}, "reason": "模型误判旧记录"},
            {"classification": "mechanically_certain", "kind": "character", "action": "create",
             "title": "林砚", "source_ref": "", "target_character_ref": "",
             "data": {"one_line_intro": "语义重复体"}, "reason": "模型重复创建"},
            {"classification": "mechanically_certain", "kind": "event", "action": "create",
             "title": "进入封锁区", "data": {}, "reason": "正常机械创建"},
        ],
        "chapter_actual_result": None,
        "planning_impact_candidate": None,
    }
    monkeypatch.setattr(
        change_settlement.semantic_ai, "run_text",
        lambda prompt, **kwargs: json.dumps(payload, ensure_ascii=False),
    )
    edit = _edit(pid, rev, ref, "受伤")
    change_id = edit["change"]["change_id"]
    final = _settle_explicit(pid, change_id)
    assert final["status"] == "awaiting_author", final.get("error")

    model = project_model.read_project_model(pid)
    # 作者记录未被机械退役，也未产生同名重复体；正常机械创建仍生效
    assert model["objects"][ref]["tombstoned"] is False
    assert sum(
        1 for o in model["objects"].values()
        if o.get("title") == "林砚" and not o.get("tombstoned")
    ) == 1
    assert any(
        o.get("title") == "进入封锁区" and not o.get("tombstoned")
        for o in model["objects"].values()
    )

    # 作者明确确认后，被门控项经既有合同应用
    change_settlement.confirm_ambiguous_consequences(pid, change_id, [0, 1])
    model = project_model.read_project_model(pid)
    assert model["objects"][ref]["tombstoned"] is True


def test_migrated_settlement_has_no_agent_path():
    source = Path(change_settlement.__file__).read_text(encoding="utf-8")
    assert "agent_runner" not in source
    assert "AgentRunError" not in source
    assert "execution_tasks" not in source
    assert "activate_for_gowrite=True" not in source
