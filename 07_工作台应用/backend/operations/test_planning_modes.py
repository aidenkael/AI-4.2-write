# -*- coding: utf-8 -*-
"""检查点 3 聚焦测试：分层长篇规划模式 + 知识策略上限 + 有效规划消费。

覆盖任务书 §14–§20：
- 全部规划模式校验（free/book/stage/near_term/impact_replan）
- book/stage/near_term 的 mode/scope 溯源进入请求元数据与 planning_meta
- stage 绑定真实 stage_ref；near_term 范围显式且有界
- 粗纲被细化后同一章号仅一个有效目标；被取代细纲不进入快照/任务上下文
- 多需求检索上限（需求数/选择数）与既有单请求选择上限保持
- StoryWrite 消费链看到有效细纲而非旧细纲或全书规划
零真实模型调用（全部假桥响应）。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))

import project_workspace  # noqa: E402

from operations import author_edit, project_model  # noqa: E402
from operations import story_planning as sp_ops  # noqa: E402
from operations import qoder_bridge as bridge  # noqa: E402
from operations.project_snapshot import focused_task_context, get_project_snapshot  # noqa: E402


def _valid_agent_json(projection=None):
    return json.dumps({
        "semantic_interpretation": {
            "objective": "分层规划测试。",
            "knowledge_needs": [],
            "knowledge_rounds": [],
            "selected_knowledge_refs": [],
            "package_ref": "",
            "assumptions": [],
            "deliberate_open_space": [],
        },
        "planning_target": {"description": "测试范围"},
        "model_output": {
            "proposal": "候选。",
            "planning_items": [{"description": "条目一"}],
        },
        **({"planning_projection": projection} if projection is not None else {}),
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
    from operations import execution_tasks
    monkeypatch.setattr(sp_ops, "_exec_task_manager", execution_tasks.ExecutionTaskManager())
    return root


@pytest.fixture()
def project(isolated):
    created = project_workspace.create_project(name="分层规划", author_intent={
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


def _fake_write(isolated, request_id, output):
    responses = isolated.parent / ".bridge" / "responses"
    responses.mkdir(parents=True, exist_ok=True)
    (responses / f"{request_id}.json").write_text(json.dumps({
        "schema": "gowrite_response/v1",
        "request_id": request_id,
        "status": "completed",
        "result": json.loads(output),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _finalize(isolated, prepare, output):
    _fake_write(isolated, prepare["request_id"], output)
    got = sp_ops.get_story_plan_request(request_id=prepare["request_id"])
    assert got["status"] == "completed", got.get("error")
    return got["result"]


def _planning_meta(isolated, pid):
    metas = list((isolated.parent / ".planning").glob(f"{pid}/*/planning_meta.json"))
    assert metas, "planning_meta 不存在"
    return json.loads(sorted(metas, key=lambda p: p.stat().st_mtime)[-1].read_text(encoding="utf-8"))


# ---------- §14 模式校验 ----------

def test_all_planning_modes_validate(project):
    pid = project["project_id"]
    with pytest.raises(sp_ops.StoryPlanningError):
        sp_ops.prepare_story_plan(pid, "任意问题", planning_mode="novel")
    for mode, question in (("free", "自由想一下"), ("book", "")):
        prepared = sp_ops.prepare_story_plan(pid, question, planning_mode=mode)
        assert prepared["status"] == "task_prepared"
        sp_ops.cancel_story_plan_request(request_id=prepared["request_id"])
    with pytest.raises(sp_ops.StoryPlanningError):
        sp_ops.prepare_story_plan(pid, "", planning_mode="stage")
    with pytest.raises(sp_ops.StoryPlanningError):
        sp_ops.prepare_story_plan(pid, "", planning_mode="near_term")
    with pytest.raises(sp_ops.StoryPlanningError):
        sp_ops.prepare_story_plan(pid, "", planning_mode="impact_replan")


def test_book_plan_stores_mode_scope_provenance(isolated, project):
    pid = project["project_id"]
    prepared = sp_ops.prepare_story_plan(pid, "", planning_mode="book")
    _finalize(isolated, prepared, _valid_agent_json())
    meta = _planning_meta(isolated, pid)
    assert meta["planning_mode"] == "book"
    assert meta["stage_binding"] is None and meta["near_term_range"] is None
    assert meta["planning_turn_id"]
    sp_ops.cancel_story_plan_request(request_id=meta["request_id"])


def test_stage_plan_binds_real_stage_ref(isolated, project):
    pid = project["project_id"]
    author_edit.set_length_plan(
        pid, base_model_rev=_rev(pid), total_target_words=None,
        stages=[{"title": "第一卷", "client_key": "s1"}],
        chapter_targets=[
            {"title": "第10章", "chapter_number": 10, "min_words": 2000, "max_words": 3000, "stage_key": "s1"},
        ],
    )
    model = project_model.read_project_model(pid)
    stage_ref = model["length_plan"]["stage_refs"][0]

    with pytest.raises(sp_ops.StoryPlanningError):
        sp_ops.prepare_story_plan(pid, "", planning_mode="stage", stage_ref="gw2_obj_missing")

    prepared = sp_ops.prepare_story_plan(pid, "", planning_mode="stage", stage_ref=stage_ref)
    # 任务文本绑定真实阶段而非标题推断（请求在 finalize 后会被清理，先读取）。
    request_task = bridge.get_request(prepared["request_id"]) or {}
    assert stage_ref in json.dumps(request_task, ensure_ascii=False)
    _finalize(isolated, prepared, _valid_agent_json())
    meta = _planning_meta(isolated, pid)
    assert meta["planning_mode"] == "stage"
    assert meta["stage_binding"]["stage_ref"] == stage_ref
    assert meta["stage_binding"]["stage_title"] == "第一卷"
    assert meta["stage_binding"]["chapter_numbers"] == [10]
    sp_ops.cancel_story_plan_request(request_id=meta["request_id"])


def test_near_term_range_explicit_and_bounded(isolated, project):
    pid = project["project_id"]
    with pytest.raises(sp_ops.StoryPlanningError):
        sp_ops.prepare_story_plan(pid, "", planning_mode="near_term", chapter_range=[14, 10])
    with pytest.raises(sp_ops.StoryPlanningError):
        sp_ops.prepare_story_plan(pid, "", planning_mode="near_term", chapter_range=[1, 13])
    with pytest.raises(sp_ops.StoryPlanningError):
        sp_ops.prepare_story_plan(pid, "", planning_mode="near_term", chapter_range=[0, 5])

    prepared = sp_ops.prepare_story_plan(pid, "", planning_mode="near_term", chapter_range=[10, 14])
    assert prepared["status"] == "task_prepared"
    request_task = bridge.get_request(prepared["request_id"]) or {}
    task_text = json.dumps(request_task, ensure_ascii=False)
    assert "第 10–14 章" in task_text and "绝不静默改写范围之外的远期骨架" in task_text
    _finalize(isolated, prepared, _valid_agent_json())
    meta = _planning_meta(isolated, pid)
    assert meta["planning_mode"] == "near_term"
    assert meta["near_term_range"] == [10, 14]
    sp_ops.cancel_story_plan_request(request_id=meta["request_id"])


def test_book_task_covers_dimensions_and_coarse_remote(isolated, project):
    pid = project["project_id"]
    prepared = sp_ops.prepare_story_plan(pid, "", planning_mode="book")
    task_text = json.dumps(bridge.get_request(prepared["request_id"]) or {}, ensure_ascii=False)
    for dimension in ("情节推进", "人物弧光", "次要人物", "伏笔", "读者期待", "冲突升级"):
        assert dimension in task_text
    assert "远期章节保持粗粒度" in task_text
    assert "2–4 个具体知识需求" in task_text
    sp_ops.cancel_story_plan_request(request_id=prepared["request_id"])


# ---------- §16/§19 分层有效规划与 StoryWrite 消费 ----------

def test_coarse_target_refined_by_detail_leaves_one_effective(isolated, project):
    pid = project["project_id"]
    coarse = _valid_agent_json({
        "characters": [], "relationships": [], "settings": [], "systems": [],
        "locations": [], "organizations": [], "storylines": [], "events": [],
        "foreshadowing": [], "mystery_information": [], "domain_relations": [],
        "chapter_changes": [{
            "title": "第20章", "chapter_number": 20, "min_words": 2000, "max_words": 3000,
            "task": "粗纲任务", "synopsis": "粗纲",
        }],
    })
    first = _finalize(isolated, sp_ops.prepare_story_plan(pid, "", planning_mode="book"), coarse)
    sp_ops.confirm_story_plan(project_id=pid, planning_token=first["planning_token"])

    detail = _valid_agent_json({
        "characters": [], "relationships": [], "settings": [], "systems": [],
        "locations": [], "organizations": [], "storylines": [], "events": [],
        "foreshadowing": [], "mystery_information": [], "domain_relations": [],
        "chapter_changes": [{
            "title": "第20章", "chapter_number": 20, "min_words": 2200, "max_words": 3200,
            "task": "细化任务", "synopsis": "细纲", "pov": "主角",
            "key_beats": ["开场冲突", "反转"], "end_state_hook": "钩子",
        }],
    })
    second = _finalize(
        isolated, sp_ops.prepare_story_plan(pid, "", planning_mode="near_term", chapter_range=[20, 20]),
        detail,
    )
    sp_ops.confirm_story_plan(project_id=pid, planning_token=second["planning_token"])

    model = project_model.read_project_model(pid)
    active_targets = [
        ref for ref in model["length_plan"]["chapter_target_refs"]
        if not model["objects"][ref].get("tombstoned")
        and (model["objects"][ref]["data"] or {}).get("chapter_number") == 20
    ]
    assert len(active_targets) == 1, "细化后同一章号只允许一个有效章节目标"
    snapshot = get_project_snapshot(pid)
    chapter20 = next(item for item in snapshot["chapters"] if item["chapter_number"] == 20)
    assert chapter20["fine_outline"]["task"] == "细化任务"

    # StoryWrite 消费：有效细纲是最新版；被取代的粗纲不进入任务上下文。
    context = focused_task_context(pid, chapter_number=20)
    assert context["chapter"]["fine_outline"]["task"] == "细化任务"
    assert "粗纲任务" not in json.dumps(context, ensure_ascii=False)


# ---------- §17 知识策略上限 ----------

def test_mode_knowledge_caps_fail_closed():
    def _semantic(needs, selected=None):
        selected = list(selected or [])
        rounds = [
            {"need": need, "query": need, "package_ref": f"pkg-{index}", "selected_knowledge_refs": []}
            for index, need in enumerate(needs)
        ]
        return {
            "knowledge_needs": needs,
            "knowledge_rounds": rounds,
            "selected_knowledge_refs": selected,
            "package_ref": "",
        }
    with pytest.raises(sp_ops.StoryPlanningError):
        sp_ops._validate_knowledge_rounds(_semantic([f"需求{index}" for index in range(5)]))
    sp_ops._validate_knowledge_rounds(_semantic([f"需求{index}" for index in range(4)]))
    sp_ops._validate_knowledge_rounds(_semantic([f"阶段需求{index}" for index in range(4)]))
    with pytest.raises(sp_ops.StoryPlanningError):
        sp_ops._validate_knowledge_rounds(_semantic([], ["ref"] * 9))
    sp_ops._validate_knowledge_rounds(_semantic([], []))
    # 0 检索/0 选择始终合法。
    sp_ops._validate_knowledge_rounds(_semantic([], []))
    # 既有单请求选择上限（提示词与 E1 消费合同）保持 3。
    assert sp_ops._MAX_KNOWLEDGE_HITS == 3
    assert "0 到 3" in sp_ops._AGENT_TASK_TEMPLATE or "{max_knowledge_hits}" in sp_ops._AGENT_TASK_TEMPLATE


def test_near_term_range_validation_bounds():
    assert sp_ops.validate_near_term_range([1, 12]) == (1, 12)
    with pytest.raises(sp_ops.StoryPlanningError):
        sp_ops.validate_near_term_range([1, 13])
    with pytest.raises(sp_ops.StoryPlanningError):
        sp_ops.validate_near_term_range("1-5")
    with pytest.raises(sp_ops.StoryPlanningError):
        sp_ops.validate_near_term_range([True, 5])
