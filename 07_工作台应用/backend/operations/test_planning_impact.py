# -*- coding: utf-8 -*-
"""检查点 2 聚焦测试：修改影响 → 作者显式局部重规划。

覆盖任务书 §7–§10 / §13：
- 确定性影响前沿（依赖邻居 / 轨迹 / 故事线 / 伏笔 / 章节目标 / 同阶段后续章）
- 批量「更新作品状态」产出可验证的规划影响候选（refs/章号必须真实）
- 编辑绝不自动启动 StoryPlan；defer 不改规划
- impact_replan：prepare 只用选中候选、确认只替换受影响投影、失败整体回滚、
  成功解决候选
零真实模型调用（全部假 adapter / 假 run_text）。
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))

import project_workspace  # noqa: E402

from operations import author_edit, change_settlement, project_model  # noqa: E402
from operations import execution_audit as audit  # noqa: E402
from operations import story_planning as sp_ops  # noqa: E402
from operations import qoder_bridge as bridge  # noqa: E402
from operations.project_snapshot import build_planning_impact_frontier, get_project_snapshot  # noqa: E402


VALID_AGENT_JSON = json.dumps({
    "semantic_interpretation": {
        "objective": "局部重规划。",
        "knowledge_needs": [],
        "selected_knowledge_refs": [],
        "package_ref": "",
        "assumptions": [],
        "deliberate_open_space": [],
    },
    "planning_target": {"description": "受影响范围", "scope_kind": "free"},
    "model_output": {
        "proposal": "替换受影响规划。",
        "planning_items": [{"description": "调整后的走向"}],
    },
}, ensure_ascii=False)


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    root = tmp_path / "03_作品工程"
    root.mkdir()
    monkeypatch.setattr(project_workspace, "get_projects_root", lambda: root)
    monkeypatch.setattr(sp_ops, "get_planning_root", lambda: tmp_path / ".planning")
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: tmp_path / ".bridge")
    monkeypatch.setattr(bridge, "focus_qoder_window", lambda: False)
    monkeypatch.setattr(audit, "get_audit_root", lambda: tmp_path / ".audit")
    from operations import execution_tasks
    monkeypatch.setattr(sp_ops, "_exec_task_manager", execution_tasks.ExecutionTaskManager())
    return root


@pytest.fixture()
def project(isolated):
    created = project_workspace.create_project(name="影响测试", author_intent={
        "work_direction": "方向", "reader_promise": "期待", "hard_constraints": [], "open_space": [],
    })
    state_file = Path(created["project_dir"]) / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["approved_plan"].append({
        "id": f"plan-{created['project_id']}",
        "description": "故事发动机。",
        "target_ref": f"design-{created['project_id']}",
        "authority": f"author_decision:decision-{created['project_id']}",
        "occurred": False,
        "kind": "confirmed_direction",
    })
    state["state_rev"] = 2
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return created


def _rev(pid):
    return project_model.read_project_model(pid)["model_rev"]


def _create(pid, category, title, material_state="current", data=None):
    created = author_edit.create_foundation_record(
        pid, base_model_rev=_rev(pid), category=category, title=title,
        material_state=material_state, data=data or {},
    )
    return created["model"]["change_history"][-1]["detail"]["ref"]


# ---------- §7 确定性影响前沿 ----------

def test_foundation_edit_produces_deterministic_frontier(project):
    pid = project["project_id"]
    char_ref = _create(pid, "character", "林砚", data={"current_state": "初始"})
    org_ref = _create(pid, "organization_force", "旧城商会")
    line_ref = _create(pid, "story_line", "追查主线")
    foreshadow_ref = _create(pid, "promise_foreshadowing", "暴雨夜伏笔")
    author_edit.create_domain_dependency(
        pid, base_model_rev=_rev(pid), source_ref=char_ref, target_ref=org_ref,
        relation_kind="character_affiliated_with_organization",
    )
    author_edit.create_domain_dependency(
        pid, base_model_rev=_rev(pid), source_ref=line_ref, target_ref=char_ref,
        relation_kind="storyline_involves_character",
    )
    author_edit.create_domain_dependency(
        pid, base_model_rev=_rev(pid), source_ref=foreshadow_ref, target_ref=char_ref,
        relation_kind="foreshadowing_related_to",
    )

    frontier = build_planning_impact_frontier(pid, changed_object_refs=[char_ref])
    assert org_ref in frontier["neighbor_object_refs"]
    assert line_ref in frontier["storyline_refs"]
    assert foreshadow_ref in frontier["foreshadowing_refs"]
    assert char_ref in frontier["changed_object_refs"]
    # 无关记录绝不进入前沿（无全书展开）。
    assert _create(pid, "location", "码头") not in frontier["affected_future_refs"]


def test_relationship_edit_frontier_includes_endpoints_and_trajectories(project):
    pid = project["project_id"]
    a = _create(pid, "character", "甲")
    b = _create(pid, "character", "乙")
    edge = author_edit.create_relationship(
        pid, base_model_rev=_rev(pid), source_ref=a, target_ref=b,
        label="旧识", material_state="current", data={},
    )
    edge_ref = edge["model"]["change_history"][-1]["detail"]["ref"]
    frontier = build_planning_impact_frontier(pid, changed_dependency_refs=[edge_ref])
    assert a in frontier["changed_object_refs"] and b in frontier["changed_object_refs"]

    # 既有实体的未来走向附着在 target_ref：人物变化 → 轨迹进入前沿。
    projection = {
        "characters": [{"key": "future_a", "title": "甲的后期走向", "target_ref": a}],
        "relationships": [], "settings": [], "systems": [], "locations": [],
        "organizations": [], "storylines": [], "events": [], "foreshadowing": [],
        "mystery_information": [], "domain_relations": [], "chapter_changes": [],
    }
    project_model.apply_planning_projection(
        pid, base_model_rev=_rev(pid), projection=projection, source_ref="decision-test",
        plan_ids=["plan-test-1"],
    )
    frontier = build_planning_impact_frontier(pid, changed_object_refs=[a])
    assert frontier["future_trajectory_refs"], "附着在被改人物上的未来走向必须进入前沿"


def test_outline_edit_frontier_scans_only_same_active_stage(project):
    pid = project["project_id"]
    author_edit.set_length_plan(
        pid, base_model_rev=_rev(pid), total_target_words=None,
        stages=[
            {"title": "第一卷", "client_key": "s1"},
            {"title": "第二卷", "client_key": "s2"},
        ],
        chapter_targets=[
            {"title": "第10章", "chapter_number": 10, "min_words": 2000, "max_words": 3000, "stage_key": "s1"},
            {"title": "第11章", "chapter_number": 11, "min_words": 2000, "max_words": 3000, "stage_key": "s1"},
            {"title": "第12章", "chapter_number": 12, "min_words": 2000, "max_words": 3000, "stage_key": "s1"},
            {"title": "第30章", "chapter_number": 30, "min_words": 2000, "max_words": 3000, "stage_key": "s2"},
        ],
    )
    frontier = build_planning_impact_frontier(pid, changed_chapter_numbers=[10])
    assert frontier["later_same_stage_chapter_numbers"] == [11, 12]
    assert 30 not in frontier["later_same_stage_chapter_numbers"], "绝不扫描无关阶段"
    frontier_30 = build_planning_impact_frontier(pid, changed_chapter_numbers=[30])
    assert frontier_30["later_same_stage_chapter_numbers"] == []


def test_chapter_target_explicit_ref_enters_frontier(project):
    pid = project["project_id"]
    char_ref = _create(pid, "character", "林砚")
    author_edit.set_length_plan(
        pid, base_model_rev=_rev(pid), total_target_words=None, stages=None,
        chapter_targets=[{
            "title": "第5章", "chapter_number": 5, "min_words": 2000, "max_words": 3000,
            "participating_characters": [char_ref],
        }],
    )
    frontier = build_planning_impact_frontier(pid, changed_object_refs=[char_ref])
    assert frontier["chapter_target_refs"], "显式引用被改人物的章节目标必须进入前沿"


# ---------- §8 批量整理产出候选 + 真实 ref 强校验 ----------

def _wait_refresh(pid, timeout=5.0):
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = change_settlement.get_project_state_refresh(pid)
        if state["status"] != "running":
            return state
        time.sleep(0.01)
    raise AssertionError("批量整理未在时限内结束")


def test_prose_divergence_produces_validated_impact_candidate(project, monkeypatch):
    pid = project["project_id"]
    future_ref = _create(pid, "character", "未来人物", material_state="future")
    author_edit.create_chapter(pid, chapter_number=1)
    author_edit.save_formal_prose(
        pid, chapter_number=1, base_content_sha256=hashlib.sha256(b"").hexdigest(),
        content="正文与细纲出现了实质偏差。",
    )
    ledger = author_edit.get_change_ledger(pid)
    prose_id = next(
        item["change_id"] for item in ledger["changes"] if item["source_kind"] == "manual_prose_edit"
    )
    payload = {
        "summary": "正文偏差",
        "consequences": [],
        "chapter_actual_results": [
            {"chapter_number": 1, "result": {"summary": "实际结果"}, "planning_impact_candidate": None},
        ],
        "planning_impact_candidates": [{
            "summary": "人物关系调整可能影响后续规划",
            "source_change_ids": [prose_id],
            "affected_refs": [future_ref],
            "affected_chapter_numbers": [1],
            "affected_stage_refs": [],
        }],
    }
    monkeypatch.setattr(change_settlement.semantic_ai, "require_semantic_ai", lambda: (object(), "secret"))
    monkeypatch.setattr(
        change_settlement.semantic_ai, "run_text",
        lambda prompt, **kwargs: json.dumps(payload, ensure_ascii=False),
    )
    change_settlement.prepare_project_state_refresh(pid)
    state = _wait_refresh(pid)
    assert state["status"] == "synchronized", state.get("error")
    model = project_model.read_project_model(pid)
    candidates = model["planning_impact_candidates"]
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["status"] == "pending_author"
    assert candidate["created_from_refresh_id"]
    assert candidate["affected_refs"] == [future_ref]
    assert candidate["source_change_ids"] == [prose_id]
    stored = author_edit.get_state_refresh(pid)
    assert stored["result"]["created_impact_candidates"] == [candidate["candidate_id"]]


def test_impact_refs_must_be_real(project, monkeypatch):
    pid = project["project_id"]
    author_edit.create_chapter(pid, chapter_number=1)
    author_edit.save_formal_prose(
        pid, chapter_number=1, base_content_sha256=hashlib.sha256(b"").hexdigest(),
        content="正文。",
    )
    ledger = author_edit.get_change_ledger(pid)
    prose_id = next(
        item["change_id"] for item in ledger["changes"] if item["source_kind"] == "manual_prose_edit"
    )
    payload = {
        "summary": "虚构影响",
        "consequences": [],
        "chapter_actual_results": [],
        "planning_impact_candidates": [{
            "summary": "AI 虚构了一个不存在的记录",
            "source_change_ids": [prose_id],
            "affected_refs": ["gw2_obj_fake_00000001"],
            "affected_chapter_numbers": [],
            "affected_stage_refs": [],
        }],
    }
    monkeypatch.setattr(change_settlement.semantic_ai, "require_semantic_ai", lambda: (object(), "secret"))
    monkeypatch.setattr(
        change_settlement.semantic_ai, "run_text",
        lambda prompt, **kwargs: json.dumps(payload, ensure_ascii=False),
    )
    change_settlement.prepare_project_state_refresh(pid)
    state = _wait_refresh(pid)
    assert state["status"] == "failed"
    model = project_model.read_project_model(pid)
    assert model["planning_impact_candidates"] == [], "虚构 ref 绝不允许落库"


def test_edits_never_auto_start_story_plan(project):
    source = Path(author_edit.__file__).read_text(encoding="utf-8")
    assert "story_planning" not in source, "作者编辑路径绝不自动调用 StoryPlan"
    settlement_source = Path(change_settlement.__file__).read_text(encoding="utf-8")
    assert "story_planning" not in settlement_source
    assert "prepare_story_plan" not in settlement_source


def test_defer_leaves_active_plan_untouched(project):
    pid = project["project_id"]
    model = project_model.add_planning_impact_candidate(
        pid, base_model_rev=_rev(pid), summary="可能影响",
        source_change_ids=["change-00000001-test"],
        affected_refs=[], affected_chapter_numbers=[],
    )
    candidate_id = model["change_history"][-1]["detail"]["candidate_id"]
    state_file = Path(project["project_dir"]) / "_工作台状态" / "story_state.json"
    state_before = state_file.read_bytes()

    updated = project_model.update_planning_impact_candidate(
        pid, base_model_rev=model["model_rev"], candidate_id=candidate_id, status="deferred",
    )
    candidate = next(
        item for item in updated["planning_impact_candidates"]
        if item["candidate_id"] == candidate_id
    )
    assert candidate["status"] == "deferred"
    assert state_file.read_bytes() == state_before, "暂时保留绝不改规划"
    # 恢复待处理同样不改规划。
    project_model.update_planning_impact_candidate(
        pid, base_model_rev=updated["model_rev"], candidate_id=candidate_id, status="pending_author",
    )
    assert state_file.read_bytes() == state_before


# ---------- §10 impact_replan 真实路径 ----------

def _fake_write(isolated, request_id, output=VALID_AGENT_JSON):
    responses = isolated.parent / ".bridge" / "responses"
    responses.mkdir(parents=True, exist_ok=True)
    (responses / f"{request_id}.json").write_text(json.dumps({
        "schema": "gowrite_response/v1",
        "request_id": request_id,
        "status": "completed",
        "result": json.loads(output),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _propose_with_projection(pid, projection):
    output = json.loads(VALID_AGENT_JSON)
    output["planning_projection"] = projection
    prepare = sp_ops.prepare_story_plan(project_id=pid, author_question="规划")
    _fake_write(Path(sp_ops.get_planning_root()), prepare["request_id"], json.dumps(output, ensure_ascii=False))
    got = sp_ops.get_story_plan_request(request_id=prepare["request_id"])
    assert got["status"] == "completed", got.get("error")
    return got["result"]


def _all_plan_ids(project_dir):
    state = json.loads((Path(project_dir) / "_工作台状态" / "story_state.json").read_text(encoding="utf-8"))
    return {p["id"] for p in state["approved_plan"] if isinstance(p.get("id"), str)}


def test_impact_replan_prepare_uses_selected_candidate_ids_only(project):
    pid = project["project_id"]
    with pytest.raises(sp_ops.StoryPlanningError):
        sp_ops.prepare_story_plan(
            pid, "", planning_mode="impact_replan", impact_candidate_ids=[],
        )
    with pytest.raises(sp_ops.StoryPlanningError):
        sp_ops.prepare_story_plan(
            pid, "", planning_mode="impact_replan", impact_candidate_ids=["planning-impact-missing"],
        )
    model = project_model.add_planning_impact_candidate(
        pid, base_model_rev=_rev(pid), summary="待处理影响",
        source_change_ids=["change-00000001-test"],
    )
    candidate_id = model["change_history"][-1]["detail"]["candidate_id"]
    prepare = sp_ops.prepare_story_plan(
        pid, "", planning_mode="impact_replan", impact_candidate_ids=[candidate_id],
    )
    assert prepare["status"] == "task_prepared"
    updated = project_model.read_project_model(pid)
    candidate = next(
        item for item in updated["planning_impact_candidates"]
        if item["candidate_id"] == candidate_id
    )
    assert candidate["status"] == "in_replan"
    # 取消后恢复原状态。
    sp_ops.cancel_story_plan_request(request_id=prepare["request_id"])
    restored = project_model.read_project_model(pid)
    candidate = next(
        item for item in restored["planning_impact_candidates"]
        if item["candidate_id"] == candidate_id
    )
    assert candidate["status"] == "pending_author"


def test_impact_replan_confirm_replaces_only_affected_projections(project):
    pid = project["project_id"]
    # 第一轮：确认规划 + 投影。
    first = _propose_with_projection(pid, {
        "characters": [{"key": "lead", "title": "第一轮人物"}],
        "relationships": [], "settings": [], "systems": [], "locations": [],
        "organizations": [], "storylines": [], "events": [], "foreshadowing": [],
        "mystery_information": [], "domain_relations": [], "chapter_changes": [],
    })
    sp_ops.confirm_story_plan(project_id=pid, planning_token=first["planning_token"])
    model = project_model.read_project_model(pid)
    first_char_ref = next(
        ref for ref, obj in model["objects"].items()
        if obj.get("title") == "第一轮人物" and obj.get("kind") == "foundation"
    )
    decision_ref = model["objects"][first_char_ref]["data"]["planning_source_ref"]
    # 无关的作者记录（不在影响范围内）。
    author_ref = _create(pid, "character", "作者人物")
    first_plan_ids = {
        plan_id for plan_id in _all_plan_ids(project["project_dir"])
        if plan_id != f"plan-{pid}"
    }
    assert first_plan_ids

    # 影响候选：只指向第一轮决策。
    model = project_model.add_planning_impact_candidate(
        pid, base_model_rev=_rev(pid), summary="第一轮规划需要调整",
        source_change_ids=["change-00000001-test"],
        affected_refs=[first_char_ref],
        affected_planning_source_refs=[decision_ref],
        source_refs=[author_ref],
    )
    candidate_id = model["change_history"][-1]["detail"]["candidate_id"]

    # impact_replan：替换第一轮受影响内容。
    prepare = sp_ops.prepare_story_plan(
        pid, "", planning_mode="impact_replan", impact_candidate_ids=[candidate_id],
    )
    second_output = json.loads(VALID_AGENT_JSON)
    second_output["planning_projection"] = {
        "characters": [{"key": "lead_v2", "title": "调整后人物"}],
        "relationships": [], "settings": [], "systems": [], "locations": [],
        "organizations": [], "storylines": [], "events": [], "foreshadowing": [],
        "mystery_information": [], "domain_relations": [], "chapter_changes": [],
    }
    _fake_write(Path(sp_ops.get_planning_root()), prepare["request_id"], json.dumps(second_output, ensure_ascii=False))
    got = sp_ops.get_story_plan_request(request_id=prepare["request_id"])
    assert got["status"] == "completed", got.get("error")
    confirmed = sp_ops.confirm_story_plan(project_id=pid, planning_token=got["result"]["planning_token"])
    assert confirmed["message"] == "规划已确认并写入"

    model = project_model.read_project_model(pid)
    assert model["objects"][first_char_ref]["tombstoned"] is True, "受影响投影被退役"
    assert any(
        obj.get("title") == "调整后人物" and not obj.get("tombstoned")
        for obj in model["objects"].values()
    )
    assert not model["objects"][author_ref]["tombstoned"], "无关作者记录保持活动"
    candidate = next(
        item for item in model["planning_impact_candidates"]
        if item["candidate_id"] == candidate_id
    )
    assert candidate["status"] == "resolved", "成功确认解决处理过的候选"

    state = json.loads((Path(project["project_dir"]) / "_工作台状态" / "story_state.json").read_text(encoding="utf-8"))
    activity = sp_ops.resolve_plan_activity(state)
    assert first_plan_ids <= set(activity["superseded"])
    snapshot = get_project_snapshot(pid)
    future_titles = [item["title"] for item in snapshot["future"]["characters"]]
    assert "第一轮人物" not in future_titles and "调整后人物" in future_titles


def test_impact_replan_failed_confirm_rolls_back_everything(project):
    pid = project["project_id"]
    first = _propose_with_projection(pid, {
        "characters": [{"key": "lead", "title": "原规划人物"}],
        "relationships": [], "settings": [], "systems": [], "locations": [],
        "organizations": [], "storylines": [], "events": [], "foreshadowing": [],
        "mystery_information": [], "domain_relations": [], "chapter_changes": [],
    })
    sp_ops.confirm_story_plan(project_id=pid, planning_token=first["planning_token"])
    model = project_model.read_project_model(pid)
    first_char_ref = next(
        ref for ref, obj in model["objects"].items()
        if obj.get("title") == "原规划人物" and obj.get("kind") == "foundation"
    )
    decision_ref = model["objects"][first_char_ref]["data"]["planning_source_ref"]
    model = project_model.add_planning_impact_candidate(
        pid, base_model_rev=_rev(pid), summary="需要调整",
        source_change_ids=["change-00000001-test"],
        affected_refs=[first_char_ref],
        affected_planning_source_refs=[decision_ref],
    )
    candidate_id = model["change_history"][-1]["detail"]["candidate_id"]

    prepare = sp_ops.prepare_story_plan(
        pid, "", planning_mode="impact_replan", impact_candidate_ids=[candidate_id],
    )
    bad_output = json.loads(VALID_AGENT_JSON)
    bad_output["planning_projection"] = {
        "characters": [], "relationships": [], "settings": [], "systems": [],
        "locations": [], "organizations": [], "storylines": [], "events": [],
        "foreshadowing": [], "mystery_information": [], "chapter_changes": [],
        # 非法领域关系 → 整个确认失败。
        "domain_relations": [
            {"relation_kind": "character_uses_system", "source_key": "nope", "target_key": "none"},
        ],
    }
    _fake_write(Path(sp_ops.get_planning_root()), prepare["request_id"], json.dumps(bad_output, ensure_ascii=False))
    got = sp_ops.get_story_plan_request(request_id=prepare["request_id"])
    assert got["status"] == "completed", got.get("error")

    state_file = Path(project["project_dir"]) / "_工作台状态" / "story_state.json"
    state_before = state_file.read_bytes()
    model_file = Path(project["project_dir"]) / "_工作台状态" / project_model.ARTIFACT_NAME
    model_before = model_file.read_bytes()

    with pytest.raises(sp_ops.StoryPlanningError, match="写入规划失败"):
        sp_ops.confirm_story_plan(project_id=pid, planning_token=got["result"]["planning_token"])

    assert state_file.read_bytes() == state_before, "Story State 必须完整回滚"
    after = json.loads(model_file.read_text(encoding="utf-8"))
    before = json.loads(model_before.decode("utf-8"))
    for key in ("objects", "dependencies", "length_plan", "chapter_actual_results"):
        assert after[key] == before[key], f"失败确认后 {key} 不得有任何部分替换"
    restored = project_model.read_project_model(pid)
    candidate = next(
        item for item in restored["planning_impact_candidates"]
        if item["candidate_id"] == candidate_id
    )
    assert candidate["status"] == "pending_author", "失败确认后候选状态必须恢复"
    assert not restored["objects"][first_char_ref]["tombstoned"]


def test_author_edit_obsoletes_touching_candidate(project):
    pid = project["project_id"]
    char_ref = _create(pid, "character", "林砚", data={"current_state": "初始"})
    model = project_model.add_planning_impact_candidate(
        pid, base_model_rev=_rev(pid), summary="人物相关影响",
        source_change_ids=["change-00000001-test"],
        affected_refs=[char_ref], source_refs=[char_ref],
    )
    candidate_id = model["change_history"][-1]["detail"]["candidate_id"]
    # 作者再次编辑同一人物 → 候选确定性作废。
    author_edit.update_foundation_record(
        pid, base_model_rev=_rev(pid), ref=char_ref, data={"current_state": "作者已自行处理"},
    )
    updated = project_model.read_project_model(pid)
    candidate = next(
        item for item in updated["planning_impact_candidates"]
        if item["candidate_id"] == candidate_id
    )
    assert candidate["status"] == "obsolete"


def test_prose_edit_obsoletes_chapter_candidate(project):
    pid = project["project_id"]
    author_edit.create_chapter(pid, chapter_number=3)
    author_edit.save_formal_prose(
        pid, chapter_number=3, base_content_sha256=hashlib.sha256(b"").hexdigest(),
        content="初稿。",
    )
    model = project_model.read_project_model(pid)
    model = project_model.add_planning_impact_candidate(
        pid, base_model_rev=model["model_rev"], summary="第3章偏差",
        source_change_ids=["change-00000001-test"],
        affected_chapter_numbers=[3],
    )
    candidate_id = model["change_history"][-1]["detail"]["candidate_id"]
    snapshot = get_project_snapshot(pid)
    author_edit.save_formal_prose(
        pid, chapter_number=3, base_content_sha256=snapshot["chapters"][0]["content_sha256"],
        content="作者改写后的正文。",
    )
    updated = project_model.read_project_model(pid)
    candidate = next(
        item for item in updated["planning_impact_candidates"]
        if item["candidate_id"] == candidate_id
    )
    assert candidate["status"] == "obsolete"
