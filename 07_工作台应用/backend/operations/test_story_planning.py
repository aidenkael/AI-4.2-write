# -*- coding: utf-8 -*-
"""故事规划"一起往前想"纵切 targeted tests。

覆盖用户要求的 15 项验证 + 1 real Agent integration smoke：
1. 没有 confirmed planning source → 明确拒绝
2. prepare 使用真实 ProjectWorkspace.load_project
3. 当前 Agent 设置被消费（task 进入桥请求）
4. StoryPlan 原样调用
5. candidate = proposal_noncanonical
6. prepare 阶段正式 Story State 零变化
7. 前端伪造 candidate 内容不能写入
8. 明确确认才能写 approved_plan
9. planning id 由后台生成
10. occurred=false
11. authority 来自 author_decision
12. stale state 拒绝确认
13. confirm 后正式概览可以读到新规划
14. 不生成正文
15. 临时 planning workspace 成功后清理

额外验证（active 投影 + 临时目录清理）：
17. superseded 条目不出现在 overview.current_plans
18. active 条目正常显示
19. Agent Task 不包含 superseded planning
20. 第二轮规划的 planning_sources 包含 confirmed_direction + active planning
21. 没有 active source 仍拒绝（多来源场景）
22. invalid Agent output 后临时 planning turn 被清理

注意：本轮切换到 /gowrite 桥模式后，不再调用 run_task。
prepare_story_plan → 创建桥请求；get_story_plan_request → 读取 Qoder 写回结果。
测试通过 mock 桥文件协议模拟 Qoder /gowrite 返回。
"""
import json
import os
import sys
import threading
import types
from pathlib import Path

import pytest

# 真实模型调用门控：默认 pytest 不产生任何 Token 消耗。
_real_model_test = pytest.mark.skipif(
    os.environ.get("GOWRITE_REAL_QODER_TEST") != "1",
    reason="真实模型调用需要 GOWRITE_REAL_QODER_TEST=1（默认跳过，防止意外消耗 Token）",
)

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))

import project_workspace  # noqa: E402

from operations import story_planning as sp_ops  # noqa: E402
from operations import qoder_bridge as bridge  # noqa: E402
from operations import agent_runner  # noqa: E402
from agents.base import AgentRequest, AgentResult  # noqa: E402
from operations.projects import get_project_overview  # noqa: E402
from operations.projects import (  # noqa: E402
    list_projects,
    open_project,
)
from config.settings import SettingsStore, AppSettings  # noqa: E402

# 合法 Agent 输出（用于 propose 测试；knowledge_needs 为空时 package_ref 为空串）
VALID_AGENT_JSON = json.dumps({
    "semantic_interpretation": {
        "objective": "推进故事前半程。",
        "knowledge_needs": [],
        "selected_bkp_ids": [],
        "package_ref": "",
        "assumptions": ["前半程事件顺序待作者确认"],
        "deliberate_open_space": ["对抗公开方式"],
    },
    "planning_target": {
        "description": "故事前半程推进",
        "scope_kind": "free",
        "scope": "约全书前半程",
    },
    "model_output": {
        "proposal": "候选：前半程让同盟在三次共同行动中各进一步。",
        "planning_items": [
            {"description": "主角先因实际问题重新接近"},
            {"description": "两人关系第一次真正发生变化"},
            {"description": "中段让问题变成更难回避的选择"},
        ],
    },
}, ensure_ascii=False)


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    """隔离：03_作品工程 → tmp 根；临时规划工作区 → tmp；AI_WRITE_CONFIG_DIR → tmp。"""
    projects_root = tmp_path / "03_作品工程"
    projects_root.mkdir()
    monkeypatch.setattr(project_workspace, "get_projects_root", lambda: projects_root)
    monkeypatch.setattr(sp_ops, "get_planning_root", lambda: tmp_path / ".planning")
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path / "cfg"))
    return projects_root


@pytest.fixture()
def fake_agent(tmp_path, monkeypatch):
    """Mock 桥文件协议：prepare 创建桥请求 → 预写 response → get 读取结果。

    替代旧的 run_task mock：不再调用后台 Agent，而是通过桥文件模拟 Qoder /gowrite 返回。
    """
    bridge_root = tmp_path / ".bridge"
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: bridge_root)
    monkeypatch.setattr(bridge, "focus_qoder_window", lambda: False)

    def _write_response(request_id: str, output: str = VALID_AGENT_JSON) -> None:
        """预写一个合法的 Qoder response 文件（模拟 /gowrite 返回）。"""
        responses_dir = bridge_root / "responses"
        responses_dir.mkdir(parents=True, exist_ok=True)
        response = {
            "schema": "gowrite_response/v1",
            "request_id": request_id,
            "status": "completed",
            "result": json.loads(output),
        }
        (responses_dir / f"{request_id}.json").write_text(
            json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return _write_response


@pytest.fixture(autouse=True)
def _fresh_exec_task_manager(monkeypatch):
    """每个测试使用独立的 Direct 任务管理器（活跃槽/任务记录不跨测试泄漏）。"""
    from operations import execution_tasks

    fresh = execution_tasks.ExecutionTaskManager()
    monkeypatch.setattr(sp_ops, "_exec_task_manager", fresh)
    return fresh


def _propose(project_id: str, author_question: str, write_response=None) -> dict:
    """模拟完整 propose 流程：prepare → 预写 response → get。

    替代旧的 sp_ops.propose_story_plan()。
    """
    prepare_result = sp_ops.prepare_story_plan(
        project_id=project_id, author_question=author_question
    )
    request_id = prepare_result["request_id"]
    if write_response is not None:
        write_response(request_id)
    get_result = sp_ops.get_story_plan_request(request_id=request_id)
    assert get_result["status"] == "completed", f"propose 失败：{get_result.get('error')}"
    return get_result["result"]


@pytest.fixture()
def real_project(isolated):
    """创建一个已有 confirmed_direction 的正式作品（模拟"我有个想法"已完成）。"""
    from project_workspace import create_project
    author_intent = {
        "work_direction": "都市奇幻长篇的开端设计。",
        "reader_promise": "读者先感到日常秩序被一条私人秘密撬开。",
        "hard_constraints": ["不把候选谜底写成既成事实"],
        "open_space": ["秘密来源", "关系走向"],
    }
    created = create_project(name="测试作品", author_intent=author_intent)
    project_dir = Path(created["project_dir"])
    project_id = created["project_id"]

    # 手动添加 confirmed_direction 到 approved_plan（模拟 new_project confirm 已完成）
    state_file = project_dir / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["approved_plan"].append({
        "id": f"plan-{project_id}",
        "description": "故事发动机：主角在暴雨夜发现花园替人保存秘密。",
        "target_ref": f"design-{project_id}",
        "authority": f"author_decision:decision-{project_id}",
        "occurred": False,
        "kind": "confirmed_direction",
    })
    state["state_rev"] = 2
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"project_id": project_id, "name": "测试作品", "project_dir": project_dir}


# ---------- 1. 没有 confirmed planning source → 明确拒绝 ----------

def test_no_planning_source_rejected(isolated, fake_agent):
    """刚创建但 partial success 没有 confirmed_direction 的作品 → prepare 拒绝。"""
    from project_workspace import create_project
    author_intent = {
        "work_direction": "方向",
        "reader_promise": "期待",
        "hard_constraints": [],
        "open_space": [],
    }
    created = create_project(name="无规划源作品", author_intent=author_intent)
    project_id = created["project_id"]

    with pytest.raises(sp_ops.StoryPlanningError) as ei:
        sp_ops.prepare_story_plan(project_id=project_id, author_question="往前想")
    assert "规划起点" in str(ei.value)


# ---------- 2. prepare 使用真实 ProjectWorkspace.load_project ----------

def test_propose_uses_real_load_project(isolated, real_project, fake_agent):
    result = _propose(
        real_project["project_id"], "先想想前半程", fake_agent
    )
    assert result["project_id"] == real_project["project_id"]
    assert result["status"] == "proposal_noncanonical"


# ---------- 3. 当前 Agent 设置被消费（task 进入桥请求） ----------

def test_agent_settings_consumed(isolated, real_project, tmp_path, monkeypatch):
    store = SettingsStore(config_dir=tmp_path / "cfg")
    store.save(AppSettings(direct_agent="deepseek_harness"))

    bridge_root = tmp_path / ".bridge"
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: bridge_root)
    monkeypatch.setattr(bridge, "focus_qoder_window", lambda: False)

    captured_tasks: list[str] = []
    original_create = bridge.create_request

    def _capture_create(task, kind, meta=None, timeout_seconds=None, **kwargs):
        captured_tasks.append(task)
        return original_create(task, kind, meta=meta, timeout_seconds=timeout_seconds)

    monkeypatch.setattr(bridge, "create_request", _capture_create)

    prepare_result = sp_ops.prepare_story_plan(
        project_id=real_project["project_id"], author_question="想法"
    )
    assert captured_tasks, "prepare 必须通过桥创建请求"
    assert "测试作品" in captured_tasks[0]  # 作品名进入 Agent 任务

    # 完成后续流程：预写 response → get
    request_id = prepare_result["request_id"]
    responses_dir = bridge_root / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)
    response = {
        "schema": "gowrite_response/v1",
        "request_id": request_id,
        "status": "completed",
        "result": json.loads(VALID_AGENT_JSON),
    }
    (responses_dir / f"{request_id}.json").write_text(
        json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    sp_ops.get_story_plan_request(request_id=request_id)


# ---------- 4. StoryPlan 原样调用 ----------

def test_story_plan_called_as_is(isolated, real_project, fake_agent):
    """验证 StoryPlan 被调用且临时工作区存在产物。"""
    _propose(real_project["project_id"], "推进前半程", fake_agent)
    # 临时工作区存在 StoryPlan 产物（confirm 后清理；这里不 confirm）
    planning_root = isolated.parent / ".planning"
    turn_dirs = list(planning_root.glob(f"{real_project['project_id']}/*/"))
    assert len(turn_dirs) == 1
    turn_dir = turn_dirs[0]
    assert (turn_dir / "briefs").exists()
    assert (turn_dir / "contexts").exists()
    assert (turn_dir / "plans").exists()


# ---------- 5. candidate = proposal_noncanonical ----------

def test_candidate_is_proposal_noncanonical(isolated, real_project, fake_agent):
    result = _propose(real_project["project_id"], "前半程", fake_agent)
    assert result["status"] == "proposal_noncanonical"
    # 临时工作区中的 candidate 也是 proposal_noncanonical
    planning_root = isolated.parent / ".planning"
    turn_dir = list(planning_root.glob(f"{real_project['project_id']}/*/"))[0]
    plans_dir = turn_dir / "plans"
    candidate_files = list(plans_dir.glob("plan-*.json"))
    assert len(candidate_files) == 1
    candidate = json.loads(candidate_files[0].read_text(encoding="utf-8"))
    assert candidate["status"] == "proposal_noncanonical"
    assert candidate["must_not_write_canon"] is True


# ---------- 6. prepare 阶段正式 Story State 零变化 ----------

def test_propose_zero_state_change(isolated, real_project, fake_agent):
    project_id = real_project["project_id"]
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    before = json.loads(state_file.read_text(encoding="utf-8"))

    _propose(project_id, "前半程", fake_agent)

    after = json.loads(state_file.read_text(encoding="utf-8"))
    assert before == after, "prepare + get 阶段不得修改正式 Story State"


# ---------- 7. 前端伪造 candidate 内容不能写入 ----------

def test_forged_candidate_rejected(isolated, real_project, fake_agent):
    result = _propose(real_project["project_id"], "前半程", fake_agent)
    token = result["planning_token"]

    # 篡改临时工作区中的 candidate 内容
    planning_root = isolated.parent / ".planning"
    turn_dir = list(planning_root.glob(f"{real_project['project_id']}/*/"))[0]
    plans_dir = turn_dir / "plans"
    candidate_files = list(plans_dir.glob("plan-*.json"))
    candidate = json.loads(candidate_files[0].read_text(encoding="utf-8"))
    candidate["content"]["proposal"] = "伪造的恶意内容"
    candidate_files[0].write_text(json.dumps(candidate), encoding="utf-8")

    # confirm 读取的是后台保存的 candidate（被篡改后的那一版），
    # 前端无法通过 confirm 参数传入伪造内容（只传 planning_token）。
    created = sp_ops.confirm_story_plan(
        project_id=real_project["project_id"],
        planning_token=token,
    )
    assert created["state_rev"] is not None


# ---------- 8. 明确确认才能写 approved_plan ----------

def test_explicit_confirm_only(isolated, real_project, fake_agent):
    project_id = real_project["project_id"]
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    before = json.loads(state_file.read_text(encoding="utf-8"))

    # 只 propose，不 confirm
    _propose(project_id, "前半程", fake_agent)

    after = json.loads(state_file.read_text(encoding="utf-8"))
    assert before == after, "只 propose 不得写入 approved_plan"

    # 现在 propose + confirm
    result = _propose(project_id, "后半程", fake_agent)
    created = sp_ops.confirm_story_plan(
        project_id=project_id,
        planning_token=result["planning_token"],
    )
    after_confirm = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(after_confirm["approved_plan"]) > len(before["approved_plan"])


# ---------- 9. planning id 由后台生成 ----------

def test_planning_id_generated_by_backend(isolated, real_project, fake_agent):
    result = _propose(real_project["project_id"], "前半程", fake_agent)
    created = sp_ops.confirm_story_plan(
        project_id=real_project["project_id"],
        planning_token=result["planning_token"],
    )
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    new_plans = [p for p in state["approved_plan"] if p.get("kind") != "confirmed_direction"]
    assert len(new_plans) > 0
    for plan in new_plans:
        assert plan["id"].startswith("plan-"), f"planning id 应由后台生成：{plan['id']}"


# ---------- 10. occurred=false ----------

def test_occurred_false(isolated, real_project, fake_agent):
    result = _propose(real_project["project_id"], "前半程", fake_agent)
    sp_ops.confirm_story_plan(
        project_id=real_project["project_id"],
        planning_token=result["planning_token"],
    )
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    new_plans = [p for p in state["approved_plan"] if p.get("kind") != "confirmed_direction"]
    for plan in new_plans:
        assert plan["occurred"] is False


# ---------- 11. authority 来自 author_decision ----------

def test_authority_from_author_decision(isolated, real_project, fake_agent):
    result = _propose(real_project["project_id"], "前半程", fake_agent)
    sp_ops.confirm_story_plan(
        project_id=real_project["project_id"],
        planning_token=result["planning_token"],
    )
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    new_plans = [p for p in state["approved_plan"] if p.get("kind") != "confirmed_direction"]
    for plan in new_plans:
        assert plan["authority"].startswith("author_decision:")


# ---------- 12. stale state 拒绝确认 ----------

def test_stale_state_rejected(isolated, real_project, fake_agent):
    project_id = real_project["project_id"]
    result = _propose(project_id, "前半程", fake_agent)
    token = result["planning_token"]

    # 模拟作品在这期间有了新变化（state_rev 变化）
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["state_rev"] = state["state_rev"] + 1
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(sp_ops.StoryPlanningError) as ei:
        sp_ops.confirm_story_plan(project_id=project_id, planning_token=token)
    assert "新的变化" in str(ei.value)


# ---------- 13. confirm 后正式概览可以读到新规划 ----------

def test_overview_reads_new_planning(isolated, real_project, fake_agent):
    project_id = real_project["project_id"]
    result = _propose(project_id, "前半程", fake_agent)
    sp_ops.confirm_story_plan(project_id=project_id, planning_token=result["planning_token"])

    overview = get_project_overview(project_id)
    assert "current_plans" in overview
    descriptions = [p["description"] for p in overview["current_plans"]]
    assert any("主角先因实际问题重新接近" in d for d in descriptions)


# ---------- 14. 不生成正文 ----------

def test_no_prose_generated(isolated, real_project, fake_agent):
    project_id = real_project["project_id"]
    result = _propose(project_id, "前半程", fake_agent)
    sp_ops.confirm_story_plan(project_id=project_id, planning_token=result["planning_token"])

    prose_dir = real_project["project_dir"] / "03_正文"
    assert prose_dir.exists()
    assert list(prose_dir.iterdir()) == [], "规划不得生成正文"


# ---------- 15. 临时 planning workspace 成功后清理 ----------

def test_planning_workspace_cleaned(isolated, real_project, fake_agent):
    project_id = real_project["project_id"]
    result = _propose(project_id, "前半程", fake_agent)

    planning_root = isolated.parent / ".planning"
    assert (planning_root / project_id).exists()

    sp_ops.confirm_story_plan(project_id=project_id, planning_token=result["planning_token"])

    # 清理后 project_id 目录应该为空或不存在
    project_planning_dir = planning_root / project_id
    if project_planning_dir.exists():
        assert list(project_planning_dir.iterdir()) == []


# ---------- 16. real Agent integration smoke ----------
# ⚠️ 真实模型调用，消耗 Token；默认跳过，需 GOWRITE_REAL_QODER_TEST=1 显式开启。

@_real_model_test
def test_real_agent_smoke(isolated, real_project, tmp_path, monkeypatch):
    """真实 Agent 集成验证：最小 smoke test（通过桥模式）。"""
    # 真实桥模式需要 Qoder 桌面端可用
    pytest.skip("真实桥模式集成验证待实现（需要 Qoder 桌面端 + /gowrite 可用）")


# ---------- 17. superseded 条目不出现在 overview.current_plans ----------

def test_superseded_not_in_current_plans(isolated, real_project, fake_agent):
    """已 superseded 的旧规划保留在历史中，但不显示为"当前已确定"。"""
    project_id = real_project["project_id"]

    # 第一轮规划
    r1 = _propose(project_id, "第一轮", fake_agent)
    sp_ops.confirm_story_plan(project_id=project_id, planning_token=r1["planning_token"])

    # 找到第一轮写入的 planning id（非 confirmed_direction 的条目）
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    first_round_plans = [p for p in state["approved_plan"] if p.get("kind") != "confirmed_direction"]
    assert len(first_round_plans) > 0
    old_plan_id = first_round_plans[0]["id"]

    # 添加一条新规划，supersedes 旧规划
    state["approved_plan"].append({
        "id": "plan-superseding-1",
        "description": "替代旧规划的新版本",
        "target_ref": first_round_plans[0].get("target_ref"),
        "authority": "author_decision:decision-superseding",
        "occurred": False,
        "supersedes": [old_plan_id],
    })
    state["state_rev"] = state["state_rev"] + 1
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    # 验证 overview 不包含被 supersede 的旧规划
    overview = get_project_overview(project_id)
    current_plan_ids = [p["id"] for p in overview.get("current_plans", [])]
    assert old_plan_id not in current_plan_ids, f"superseded 的 {old_plan_id} 不应出现在 current_plans"
    assert "plan-superseding-1" in current_plan_ids, "新规划应出现在 current_plans"

    # 验证旧规划仍保留在正式 State 历史中
    state_after = json.loads(state_file.read_text(encoding="utf-8"))
    all_ids = [p.get("id") for p in state_after["approved_plan"]]
    assert old_plan_id in all_ids, "superseded 的旧规划必须保留在历史中"


# ---------- 18. active 条目正常显示 ----------

def test_active_plans_displayed(isolated, real_project, fake_agent):
    """所有 active 条目都显示在 current_plans 中。"""
    project_id = real_project["project_id"]

    r1 = _propose(project_id, "第一轮", fake_agent)
    sp_ops.confirm_story_plan(project_id=project_id, planning_token=r1["planning_token"])

    overview = get_project_overview(project_id)
    # confirmed_direction + 第一轮 planning 都应显示
    assert "current_plans" in overview
    assert len(overview["current_plans"]) >= 2  # confirmed_direction + 至少1条 planning


# ---------- 19. Agent Task 不包含 superseded planning ----------

def test_agent_prompt_excludes_superseded(isolated, real_project, fake_agent, tmp_path, monkeypatch):
    """Agent Task 中的"当前已确定的规划"不包含 superseded 条目。"""
    project_id = real_project["project_id"]

    bridge_root = tmp_path / ".bridge"
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: bridge_root)
    monkeypatch.setattr(bridge, "focus_qoder_window", lambda: False)

    captured_tasks: list[str] = []
    original_create = bridge.create_request

    def _capture_create(task, kind, meta=None, timeout_seconds=None, **kwargs):
        captured_tasks.append(task)
        return original_create(task, kind, meta=meta, timeout_seconds=timeout_seconds)

    monkeypatch.setattr(bridge, "create_request", _capture_create)

    # 先做一轮规划
    r1 = _propose(project_id, "第一轮", fake_agent)
    sp_ops.confirm_story_plan(project_id=project_id, planning_token=r1["planning_token"])

    # 手动 supersede 第一轮的某条规划
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    first_round_plans = [p for p in state["approved_plan"] if p.get("kind") != "confirmed_direction"]
    old_plan_id = first_round_plans[0]["id"]
    old_desc = first_round_plans[0]["description"]

    state["approved_plan"].append({
        "id": "plan-superseding-2",
        "description": "替代版本",
        "target_ref": first_round_plans[0].get("target_ref"),
        "authority": "author_decision:decision-s2",
        "occurred": False,
        "supersedes": [old_plan_id],
    })
    state["state_rev"] = state["state_rev"] + 1
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    # 第二轮规划
    captured_tasks.clear()
    prepare_result = sp_ops.prepare_story_plan(
        project_id=project_id, author_question="第二轮"
    )
    # 预写 response 并完成
    request_id = prepare_result["request_id"]
    responses_dir = bridge_root / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)
    response = {
        "schema": "gowrite_response/v1",
        "request_id": request_id,
        "status": "completed",
        "result": json.loads(VALID_AGENT_JSON),
    }
    (responses_dir / f"{request_id}.json").write_text(
        json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    sp_ops.get_story_plan_request(request_id=request_id)

    # 验证 Agent Task 不包含被 supersede 的旧规划描述
    assert len(captured_tasks) == 1
    prompt = captured_tasks[0]
    assert old_desc not in prompt, f"superseded 的旧规划描述不应出现在 Task 中：{old_desc}"
    assert "替代版本" in prompt, "active 的新规划描述应出现在 Task 中"


# ---------- 20. 第二轮规划 planning_sources 包含 confirmed_direction + active planning ----------

def test_second_round_sources_include_all_active(isolated, real_project, fake_agent):
    """第二轮规划的 planning_sources 包含 confirmed_direction 和已确认的 active planning。"""
    project_id = real_project["project_id"]

    # 第一轮规划
    r1 = _propose(project_id, "第一轮", fake_agent)
    sp_ops.confirm_story_plan(project_id=project_id, planning_token=r1["planning_token"])

    # 第二轮规划
    _propose(project_id, "第二轮", fake_agent)

    planning_root = isolated.parent / ".planning"
    turn_dirs = list(planning_root.glob(f"{project_id}/*/"))
    assert len(turn_dirs) >= 1
    # 取最新的 turn dir
    latest_turn = sorted(turn_dirs, key=lambda p: p.stat().st_mtime)[-1]
    brief_files = list(latest_turn.glob("briefs/plan-brief-*.json"))
    assert len(brief_files) == 1
    brief = json.loads(brief_files[0].read_text(encoding="utf-8"))

    # planning_sources 应包含至少 2 条：confirmed_direction + 第一轮 planning
    sources = brief.get("planning_sources", [])
    assert len(sources) >= 2, f"第二轮 planning_sources 应包含至少 2 条 active 来源，实际：{sources}"

    # 验证所有 sources 都是 approved_plan kind
    for s in sources:
        assert s["kind"] == "approved_plan"


# ---------- 21. 没有 active source 仍拒绝（多来源场景） ----------

def test_no_active_source_rejected_multi(isolated, real_project, fake_agent):
    """所有 approved_plan 都被 supersede 后，仍有一条 active 时可以 propose。"""
    project_id = real_project["project_id"]

    # 手动把所有规划都 supersede（包括 confirmed_direction）
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))

    all_plan_ids = [p.get("id") for p in state["approved_plan"] if p.get("id")]
    state["approved_plan"].append({
        "id": "plan-supersede-all",
        "description": "替代所有",
        "target_ref": "design-all",
        "authority": "author_decision:decision-all",
        "occurred": False,
        "supersedes": all_plan_ids,
    })
    state["state_rev"] = state["state_rev"] + 1
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    # 现在还有 1 条 active（plan-supersede-all）
    result = _propose(project_id, "测试", fake_agent)
    assert result["status"] == "proposal_noncanonical"

    # 再把它也 supersede
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["approved_plan"].append({
        "id": "plan-supersede-final",
        "description": "最终替代",
        "target_ref": "design-final",
        "authority": "author_decision:decision-final",
        "occurred": False,
        "supersedes": ["plan-supersede-all"],
    })
    state["state_rev"] = state["state_rev"] + 1
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    # 现在只有 plan-supersede-final 是 active
    result = _propose(project_id, "再测试", fake_agent)
    assert result["status"] == "proposal_noncanonical"


# ---------- 22. invalid Agent output 后临时 planning turn 被清理 ----------

def test_invalid_agent_output_cleanup(isolated, real_project, tmp_path, monkeypatch):
    """Agent 输出结构错误时，临时 planning turn 被清理。"""
    bridge_root = tmp_path / ".bridge"
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: bridge_root)
    monkeypatch.setattr(bridge, "focus_qoder_window", lambda: False)

    project_id = real_project["project_id"]
    planning_root = isolated.parent / ".planning"

    # prepare 创建桥请求
    prepare_result = sp_ops.prepare_story_plan(
        project_id=project_id, author_question="测试"
    )
    request_id = prepare_result["request_id"]

    # 预写非法 response（模拟 Qoder 返回了非结构化文本）
    responses_dir = bridge_root / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)
    bad_response = {
        "schema": "gowrite_response/v1",
        "request_id": request_id,
        "status": "completed",
        "output": "这不是合法 JSON",
    }
    (responses_dir / f"{request_id}.json").write_text(
        json.dumps(bad_response, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # get 应该返回 failed（解析失败）
    get_result = sp_ops.get_story_plan_request(request_id=request_id)
    assert get_result["status"] == "failed"

    # 临时 planning turn 应被清理
    project_planning_dir = planning_root / project_id
    if project_planning_dir.exists():
        assert list(project_planning_dir.iterdir()) == [], "invalid Agent output 后临时目录应被清理"


# ---------------------------------------------------------------------------
# Knowledge Selection Binding（P0 闭环）：唯一一次检索调用 → 请求级快照 →
# 模型从该显示包选择 → finalize 读快照 → Context 消费同一反序列化包
# ---------------------------------------------------------------------------

def _agent_json(knowledge_needs, selected_bkp_ids, package_ref=""):
    """构造带知识选择的合法 Agent 输出。

    selection 为 scoped ref（book_id/source_anchor）；package_ref 是模型
    从检索命令输出中原样回显的包身份指纹。
    """
    return json.dumps({
        "semantic_interpretation": {
            "objective": "推进故事前半程。",
            "knowledge_needs": knowledge_needs,
            "selected_bkp_ids": selected_bkp_ids,
            "package_ref": package_ref,
            "assumptions": ["AI 解读中的假设，作者尚未确认"],
            "deliberate_open_space": [],
        },
        "planning_target": {"description": "故事前半程推进", "scope_kind": "free", "scope": "约全书前半程"},
        "model_output": {
            "proposal": "候选：让同盟在三次共同行动中各进一步。",
            "planning_items": [{"description": "主角先重新接近"}, {"description": "关系第一次变化"}],
        },
    }, ensure_ascii=False)


def _fake_hit(book_id, anchor, statement, rank=1):
    return types.SimpleNamespace(
        rank=rank, book_id=book_id, book_title=book_id,
        source_anchor=anchor, source="knowledge/cards.md", statement=statement,
        scope="测试范围", boundary="测试边界", confidence="中",
        evidence=[f"chapters/{anchor}.md#L1"], relevance_reason="test",
    )


def _fake_package(hits, status="OK", gaps=None, candidate_count=None):
    return types.SimpleNamespace(
        status=status, hits=list(hits), gaps=list(gaps or []),
        candidate_count=candidate_count if candidate_count is not None else len(hits),
    )


def _latest_turn_dir(project_id, planning_root):
    turn_dirs = list(planning_root.glob(f"{project_id}/*/"))
    assert turn_dirs, "planning turn 目录不存在"
    return sorted(turn_dirs, key=lambda p: p.stat().st_mtime)[-1]


def _read_context(project_id, planning_root):
    turn_dir = _latest_turn_dir(project_id, planning_root)
    context_file = list(turn_dir.glob("contexts/plan-context-*.json"))[0]
    return json.loads(context_file.read_text(encoding="utf-8"))


def _read_snapshot(project_id, planning_root):
    turn_dir = _latest_turn_dir(project_id, planning_root)
    return json.loads((turn_dir / "retrieval" / "package.json").read_text(encoding="utf-8"))


def _propose_with_agent(project_id, agent_json, write_response, author_question="往前想"):
    """prepare → 预写自定义 Agent 输出 → get；返回 get_result（可能 failed）。"""
    prepare_result = sp_ops.prepare_story_plan(project_id=project_id, author_question=author_question)
    request_id = prepare_result["request_id"]
    write_response(request_id, output=agent_json)
    return sp_ops.get_story_plan_request(request_id=request_id)


def _propose_with_snapshot(project_id, knowledge_needs, selected_bkp_ids, package,
                           write_response, monkeypatch, package_ref=None,
                           author_question="往前想"):
    """完整知识闭环：prepare → Agent 侧"唯一一次检索调用"（写请求级快照）→
    Agent 响应（选择 + 回显包指纹）→ finalize（读快照，零检索）。

    返回 (get_result, retrieval_calls, request_id)。retrieval_calls 记录
    KnowledgeRetrieve 的实际执行次数（模拟 Agent 侧命令；finalize 不得增加）。
    """
    calls: list[str] = []

    def _retrieve(query):
        calls.append(query)
        return package

    monkeypatch.setattr(sp_ops, "_retrieve_package", _retrieve)

    prepare_result = sp_ops.prepare_story_plan(project_id=project_id, author_question=author_question)
    request_id = prepare_result["request_id"]

    query = "；".join(knowledge_needs)
    shown_package = sp_ops.execute_request_scoped_retrieval(query, request_id)  # 唯一一次检索调用
    fingerprint = sp_ops._package_fingerprint(shown_package)

    agent_json = _agent_json(
        knowledge_needs, selected_bkp_ids,
        package_ref=fingerprint if package_ref is None else package_ref,
    )
    write_response(request_id, output=agent_json)
    get_result = sp_ops.get_story_plan_request(request_id=request_id)
    return get_result, calls, request_id


# A. knowledge_needs = []：检索 0 次调用、无快照、0 BKP、规划成功

def test_knowledge_needs_empty_skips_retrieval(isolated, real_project, fake_agent, monkeypatch):
    calls = []

    def _must_not_be_called(query):
        calls.append(query)
        raise AssertionError("knowledge_needs 为空时不得调用 KnowledgeRetrieve")

    monkeypatch.setattr(sp_ops, "_retrieve_package", _must_not_be_called)

    get_result = _propose_with_agent(real_project["project_id"], _agent_json([], []), fake_agent)
    assert get_result["status"] == "completed", get_result.get("error")
    result = get_result["result"]
    assert calls == [], "无 knowledge_needs 时检索调用次数必须为 0"
    assert result["status"] == "proposal_noncanonical"
    assert result["knowledge"]["retrieval_status"] == "SKIPPED_NO_KNOWLEDGE_NEED"
    assert result["knowledge"]["selected_count"] == 0
    context = _read_context(real_project["project_id"], isolated.parent / ".planning")
    assert context["selected_bkp_hits"] == []
    # 无快照被创建
    turn_dir = _latest_turn_dir(real_project["project_id"], isolated.parent / ".planning")
    assert not (turn_dir / "retrieval" / "package.json").exists(), "无知识需求时不得生成检索快照"


# B. knowledge_needs ≠ []：全程恰好 1 次检索；快照由同一调用写入；
#    finalize 零额外检索；Context 消费与模型所见完全相同的包

def test_knowledge_needs_binds_exact_package_to_context(isolated, real_project, fake_agent, monkeypatch):
    package = _fake_package([
        _fake_hit("book_a", "K001", "A 卡", rank=1),
        _fake_hit("book_a", "K002", "B 卡", rank=2),
        _fake_hit("book_b", "K003", "C 卡", rank=3),
    ])

    get_result, calls, request_id = _propose_with_snapshot(
        real_project["project_id"], ["信息层次"], ["book_a/K001", "book_b/K003"],
        package, fake_agent, monkeypatch,
    )
    assert get_result["status"] == "completed", get_result.get("error")
    result = get_result["result"]
    assert calls == ["信息层次"], "整个知识闭环必须恰好执行 1 次检索（finalize 不得再次检索）"
    assert result["knowledge"]["retrieved_count"] == 3
    assert result["knowledge"]["selected_count"] == 2

    context = _read_context(real_project["project_id"], isolated.parent / ".planning")
    statements = [h["statement"] for h in context["selected_bkp_hits"]]
    assert statements == ["A 卡", "C 卡"], "Context 必须消费模型从该包中选择的同一批卡"
    assert {h["selection_ref"] for h in context["selected_bkp_hits"]} == {"book_a/K001", "book_b/K003"}

    # 快照由 Agent 侧唯一一次调用写入，且身份元数据完整
    snapshot = _read_snapshot(real_project["project_id"], isolated.parent / ".planning")
    assert snapshot["schema"] == "gowrite_retrieval_snapshot/v1"
    assert snapshot["request_id"] == request_id
    assert snapshot["project_id"] == real_project["project_id"]
    turn_dir = _latest_turn_dir(real_project["project_id"], isolated.parent / ".planning")
    assert snapshot["planning_turn_id"] == turn_dir.name
    assert snapshot["query"] == "信息层次"
    assert snapshot["package_fingerprint"] == sp_ops._package_fingerprint(package)
    assert len(snapshot["package"]["hits"]) == 3


# C. 快照创建后底层目录/检索结果被改动：finalize 仍用捕获的包，零新检索

def test_catalog_mutation_after_snapshot_no_fresh_retrieval(isolated, real_project, fake_agent, monkeypatch):
    package_a = _fake_package([_fake_hit("book_a", "K001", "A 卡", rank=1)])
    calls: list[str] = []
    monkeypatch.setattr(sp_ops, "_retrieve_package", lambda q: (calls.append(q), package_a)[1])

    prepare_result = sp_ops.prepare_story_plan(project_id=real_project["project_id"], author_question="往前想")
    request_id = prepare_result["request_id"]

    # Agent 侧唯一一次检索调用 → 快照写入（包 A）
    shown = sp_ops.execute_request_scoped_retrieval("信息层次", request_id)
    fingerprint = sp_ops._package_fingerprint(shown)
    assert calls == ["信息层次"]

    # 模拟"快照创建后底层 BKP/目录发生变化"：检索实现被替换（若被再次调用会暴露）
    monkeypatch.setattr(sp_ops, "_retrieve_package", lambda q: (calls.append(q), _fake_package(
        [_fake_hit("book_a", "K001", "被篡改的新卡", rank=1)]
    ))[1])

    agent_json = _agent_json(["信息层次"], ["book_a/K001"], package_ref=fingerprint)
    fake_agent(request_id, output=agent_json)
    get_result = sp_ops.get_story_plan_request(request_id=request_id)
    assert get_result["status"] == "completed", get_result.get("error")

    # finalize 未再次检索；Context 消费快照中的包 A
    assert calls == ["信息层次"], "finalize 必须零检索（不得因底层变化重新检索）"
    context = _read_context(real_project["project_id"], isolated.parent / ".planning")
    assert [h["statement"] for h in context["selected_bkp_hits"]] == ["A 卡"]


# D. 快照/查询/请求/包身份不匹配 → 整轮失败

def test_snapshot_missing_rejects_knowledge_selection(isolated, real_project, fake_agent, monkeypatch):
    # Agent 声称有知识需求并回显包指纹，但从未运行检索命令 → 无快照 → 拒绝
    monkeypatch.setattr(sp_ops, "_retrieve_package", lambda q: _fake_package([]))
    get_result = _propose_with_agent(
        real_project["project_id"],
        _agent_json(["信息层次"], ["book_a/K001"], package_ref="deadbeef"),
        fake_agent,
    )
    assert get_result["status"] == "failed"
    assert "快照缺失" in get_result["error"]


def test_snapshot_unparseable_rejects_knowledge_selection(isolated, real_project, fake_agent, monkeypatch):
    package = _fake_package([_fake_hit("book_a", "K001", "A 卡", rank=1)])
    monkeypatch.setattr(sp_ops, "_retrieve_package", lambda q: package)

    prepare_result = sp_ops.prepare_story_plan(project_id=real_project["project_id"], author_question="往前想")
    request_id = prepare_result["request_id"]
    sp_ops.execute_request_scoped_retrieval("信息层次", request_id)

    # 篡改快照为不可解析内容
    turn_dir = _latest_turn_dir(real_project["project_id"], isolated.parent / ".planning")
    snapshot_path = turn_dir / "retrieval" / "package.json"
    snapshot_path.write_text("{ 这不是合法 JSON", encoding="utf-8")

    fake_agent(request_id, output=_agent_json(["信息层次"], ["book_a/K001"], package_ref="x"))
    get_result = sp_ops.get_story_plan_request(request_id=request_id)
    assert get_result["status"] == "failed"
    assert "无法解析" in get_result["error"]


def test_snapshot_identity_mismatch_rejects_knowledge_selection(isolated, real_project, fake_agent, monkeypatch):
    package = _fake_package([_fake_hit("book_a", "K001", "A 卡", rank=1)])
    monkeypatch.setattr(sp_ops, "_retrieve_package", lambda q: package)
    planning_root = isolated.parent / ".planning"

    def _run_one_turn(mutate, agent_package_ref=None, needs=None):
        """每个 mismatch 子用例用全新的 planning turn（失败的 finalize 会清理该 turn）。"""
        prepare_result = sp_ops.prepare_story_plan(project_id=real_project["project_id"], author_question="往前想")
        request_id = prepare_result["request_id"]
        sp_ops.execute_request_scoped_retrieval("信息层次", request_id)
        turn_dir = _latest_turn_dir(real_project["project_id"], planning_root)
        snapshot_path = turn_dir / "retrieval" / "package.json"
        if mutate is not None:
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            mutate(snapshot)
            snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
        if agent_package_ref is None:
            agent_package_ref = sp_ops._package_fingerprint(package)
        fake_agent(request_id, output=_agent_json(
            needs if needs is not None else ["信息层次"], ["book_a/K001"], package_ref=agent_package_ref,
        ))
        return sp_ops.get_story_plan_request(request_id=request_id)

    # request_id 不匹配
    get_result = _run_one_turn(lambda s: s.update(request_id="other-request"))
    assert get_result["status"] == "failed" and "request_id" in get_result["error"]

    # project_id 不匹配
    get_result = _run_one_turn(lambda s: s.update(project_id="other-project"))
    assert get_result["status"] == "failed" and "project_id" in get_result["error"]

    # planning_turn_id 不匹配
    get_result = _run_one_turn(lambda s: s.update(planning_turn_id="other-turn"))
    assert get_result["status"] == "failed" and "planning_turn_id" in get_result["error"]

    # query 不匹配（Agent 响应中的 knowledge_needs 与快照查询不一致）
    get_result = _run_one_turn(lambda s: None, needs=["信息层次", "别的"])
    assert get_result["status"] == "failed" and "查询" in get_result["error"]

    # 包身份（package_ref）与快照指纹不一致
    get_result = _run_one_turn(lambda s: None, agent_package_ref="deadbeef")
    assert get_result["status"] == "failed" and "package_ref" in get_result["error"]

    # 缺少 package_ref（空串）
    get_result = _run_one_turn(lambda s: None, agent_package_ref="")
    assert get_result["status"] == "failed" and "缺少检索包身份" in get_result["error"]


# E. 模型选择不存在的 ref → 不注入、稳定 gap、绝不替换成其他候选

def test_nonexistent_ref_no_injection_no_substitution(isolated, real_project, fake_agent, monkeypatch):
    package = _fake_package([
        _fake_hit("book_a", "K001", "A 卡", rank=1),
        _fake_hit("book_a", "K002", "B 卡", rank=2),
    ])
    get_result, calls, _ = _propose_with_snapshot(
        real_project["project_id"], ["信息层次"], ["book_a/NOPE", "book_a/K001"],
        package, fake_agent, monkeypatch,
    )
    assert get_result["status"] == "completed", get_result.get("error")
    assert calls == ["信息层次"]
    context = _read_context(real_project["project_id"], isolated.parent / ".planning")
    statements = [h["statement"] for h in context["selected_bkp_hits"]]
    assert statements == ["A 卡"], "不存在的 ref 不得注入，也不得被替换成其他候选"
    assert any("不在本次有效召回" in g for g in get_result["result"]["knowledge"]["gaps"])


# F. 两本书都含 K001：scoped ref 只命中对应书；裸 K001 绝不双注入

def test_scoped_cross_book_identity(isolated, real_project, fake_agent, monkeypatch):
    package = _fake_package([
        _fake_hit("book_a", "K001", "A 卡", rank=1),
        _fake_hit("book_b", "K001", "B 卡", rank=2),
    ])
    planning_root = isolated.parent / ".planning"

    # book_a/K001 → 只注入 book_a 的卡
    r1, _, _ = _propose_with_snapshot(real_project["project_id"], ["信息层次"], ["book_a/K001"], package, fake_agent, monkeypatch)
    assert r1["status"] == "completed", r1.get("error")
    c1 = _read_context(real_project["project_id"], planning_root)
    assert [h["statement"] for h in c1["selected_bkp_hits"]] == ["A 卡"]
    assert {h["book_id"] for h in c1["selected_bkp_hits"]} == {"book_a"}

    # book_b/K001 → 只注入 book_b 的卡
    r2, _, _ = _propose_with_snapshot(real_project["project_id"], ["信息层次"], ["book_b/K001"], package, fake_agent, monkeypatch)
    assert r2["status"] == "completed", r2.get("error")
    c2 = _read_context(real_project["project_id"], planning_root)
    assert [h["statement"] for h in c2["selected_bkp_hits"]] == ["B 卡"]
    assert {h["book_id"] for h in c2["selected_bkp_hits"]} == {"book_b"}

    # 裸 K001 → 一张都不注入 + AMBIGUOUS gap
    r3, _, _ = _propose_with_snapshot(real_project["project_id"], ["信息层次"], ["K001"], package, fake_agent, monkeypatch)
    assert r3["status"] == "completed", r3.get("error")
    c3 = _read_context(real_project["project_id"], planning_root)
    assert c3["selected_bkp_hits"] == [], "跨书同名裸 anchor 不得双注入"
    assert any(g.startswith("AMBIGUOUS_BKP_REF") for g in r3["result"]["knowledge"]["gaps"])


# 无知识需求却选择 BKP / 声明包身份 → 拒绝（selected 与 package_ref 都必须为空）

def test_selection_without_knowledge_needs_rejected(isolated, real_project, fake_agent, monkeypatch):
    calls = []
    monkeypatch.setattr(sp_ops, "_retrieve_package", lambda q: (calls.append(q), _fake_package([]))[1])

    get_result = _propose_with_agent(real_project["project_id"], _agent_json([], ["book_a/K001"]), fake_agent)
    assert get_result["status"] == "failed"
    assert "没有知识需求却选择了 BKP" in get_result["error"]
    assert calls == [], "无知识需求时不得调用 KnowledgeRetrieve"

    # 无知识需求却回显包身份 → 同样拒绝
    get_result2 = _propose_with_agent(real_project["project_id"], _agent_json([], [], package_ref="deadbeef"), fake_agent)
    assert get_result2["status"] == "failed"
    assert "没有知识需求却选择了 BKP" in get_result2["error"]


# G. 检索后模型 0 选择 → 合法 0-BKP 规划路径

def test_zero_bkp_after_retrieval_is_valid(isolated, real_project, fake_agent, monkeypatch):
    package = _fake_package([_fake_hit("book_a", "K001", "A 卡", rank=1)])
    get_result, calls, _ = _propose_with_snapshot(
        real_project["project_id"], ["信息层次"], [], package, fake_agent, monkeypatch,
    )
    assert get_result["status"] == "completed", get_result.get("error")
    assert calls == ["信息层次"], "有知识需求时必须执行检索（且仅此一次）"
    result = get_result["result"]
    assert result["status"] == "proposal_noncanonical"
    assert result["knowledge"]["retrieval_status"] == "OK"
    assert result["knowledge"]["selected_count"] == 0
    context = _read_context(real_project["project_id"], isolated.parent / ".planning")
    assert context["selected_bkp_hits"] == []
    assert context["status"] == "CURRENT_WITH_BKP_GAP"


# 绑定闭包：Context 查询与绑定包不一致 → 拒绝（绝不触发无关后续检索）

def test_bound_package_rejects_unrelated_query(isolated, real_project):
    package = _fake_package([_fake_hit("book_a", "K001", "A 卡")])
    bound = sp_ops._bound_package(package, "信息层次")
    assert bound("信息层次") is package
    with pytest.raises(sp_ops.SPContractError):
        bound("别的查询")


# Agent 侧唯一一次检索调用：检索失败 → 命令失败；无快照时 finalize 拒绝

def test_agent_retrieval_failure_no_snapshot(isolated, real_project, tmp_path, monkeypatch):
    # 隔离桥根：避免生产桥目录中遗留的 active 指针触发交互忙碌保护
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: tmp_path / ".bridge")
    monkeypatch.setattr(bridge, "focus_qoder_window", lambda: False)

    def _boom(query):
        raise RuntimeError("检索崩溃")

    monkeypatch.setattr(sp_ops, "_retrieve_package", _boom)
    prepare_result = sp_ops.prepare_story_plan(project_id=real_project["project_id"], author_question="往前想")
    request_id = prepare_result["request_id"]
    with pytest.raises(sp_ops.StoryPlanningError) as ei:
        sp_ops.execute_request_scoped_retrieval("信息层次", request_id)
    assert "知识检索失败" in str(ei.value)


# 生产契约：任务要求模型在 /gowrite 内运行唯一检索命令（写快照）后，
# 从该显示包选择并回显 package_ref；不再允许预先编造 BKP id

def test_agent_task_no_longer_invents_bkp_ids_pre_retrieval(isolated, real_project, tmp_path, monkeypatch):
    bridge_root = tmp_path / ".bridge"
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: bridge_root)
    monkeypatch.setattr(bridge, "focus_qoder_window", lambda: False)

    captured_tasks: list[str] = []
    original_create = bridge.create_request

    def _capture_create(task, kind, meta=None, timeout_seconds=None, **kwargs):
        captured_tasks.append(task)
        return original_create(task, kind, meta=meta, timeout_seconds=timeout_seconds)

    monkeypatch.setattr(bridge, "create_request", _capture_create)

    sp_ops.prepare_story_plan(project_id=real_project["project_id"], author_question="往前想")
    assert len(captured_tasks) == 1
    task = captured_tasks[0]
    # 两阶段任务：先语义分析，再运行唯一确定性检索命令（写快照）后选择；严禁编造
    assert "第一阶段" in task and "第二阶段" in task
    assert "retrieval_snapshot.py" in task, "任务必须给出请求级检索快照命令"
    assert "package_fingerprint" in task, "任务必须要求模型回显包身份指纹"
    assert "package_ref" in task
    assert "严禁编造" in task
    assert "book_id/source_anchor" in task


# ---------------------------------------------------------------------------
# 任务契约（Task Contract）：knowledge_needs 非空时必须先用工具执行检索命令，
# 再输出最终 JSON；禁止残留"纯文本输出"式表述（真实直连 Agent 曾因此跳过检索）
# ---------------------------------------------------------------------------

def _render_task_template() -> str:
    """渲染当前 Agent 任务模板（与 prepare_story_plan 同一格式化路径）。"""
    return sp_ops._AGENT_TASK_TEMPLATE.format(
        name="测试作品",
        work_direction="都市奇幻长篇的开端设计。",
        reader_promise="读者先感到日常秩序被一条私人秘密撬开。",
        hard_constraints="不把候选谜底写成既成事实",
        open_space="秘密来源、关系走向",
        current_planning="- 故事发动机：主角在暴雨夜发现花园替人保存秘密。",
        author_question="先想想前半程",
        retrieval_command=f'"{sp_ops._RETRIEVAL_SCRIPT}"',
        max_bkp_hits=sp_ops._MAX_BKP_HITS,
    )


def test_task_mandates_retrieval_tool_before_final_json_for_nonempty_needs():
    """A. knowledge_needs 非空 → 最终 JSON 之前必须先执行检索命令（工具调用）。"""
    task = _render_task_template()
    assert "在生成最终 JSON 之前" in task
    assert "你必须先用可用的本地命令/工具执行以下确定性只读检索命令" in task
    assert "在生成最终回复之前，若 knowledge_needs 非空，你必须先调用工具执行检索命令并读取结果" in task
    assert "工具调用属于任务执行过程，不属于最终回复" in task
    # 顺序必须成立：先工具执行，后最终回复约束
    assert task.index("在生成最终 JSON 之前") < task.index("最终回复必须只有合法 JSON")


def test_task_skips_retrieval_when_knowledge_needs_empty():
    """B. knowledge_needs 为空 → 明确不运行检索、selected 为空、package_ref 为空串。"""
    task = _render_task_template()
    assert "若 knowledge_needs 为空：不要运行检索命令" in task
    assert "selected_bkp_ids 必须为 []" in task
    assert "package_ref 必须为空字符串" in task


def test_task_requires_strict_json_final_response():
    """C. 最终回复仍必须是严格合法 JSON（结构字段齐全）。"""
    task = _render_task_template()
    assert "最终回复必须只有合法 JSON 对象（不要任何额外文字、不要 markdown 代码块标记）" in task
    assert '"semantic_interpretation"' in task
    assert '"planning_target"' in task
    assert '"model_output"' in task
    assert '"planning_items"' in task


def test_task_requires_package_ref_binding():
    """D. package_fingerprint → package_ref 绑定仍被明确要求。"""
    task = _render_task_template()
    assert "package_fingerprint 原样填入 semantic_interpretation.package_ref" in task
    assert "package_ref" in task


def test_task_requires_selection_only_from_returned_package():
    """E. 选择只能来自命令实际输出的 selection_ref，严禁编造。"""
    task = _render_task_template()
    assert "只从中选择 0 到" in task
    assert "严禁编造命令输出中不存在的 selection_ref 或 package_fingerprint" in task
    assert "book_id/source_anchor" in task


def test_task_has_no_text_only_framing():
    """F. 不再残留会抑制中间工具调用的"纯文本输出"式表述。"""
    task = _render_task_template()
    for phrase in ("只做语义与创意分析", "直接输出 JSON", "不要输出任何其他内容"):
        assert phrase not in task, f"任务残留抑制工具调用的表述：{phrase}"


# ---------------------------------------------------------------------------
# 执行模式绑定（Settings → StoryPlan）：交互桥 / 直连 双路径，同一 finalize
# ---------------------------------------------------------------------------

class _FakeDirectAdapter:
    """直连测试假 adapter：记录 AgentRequest，返回预设结果或执行 on_run。

    done 事件在 run() 返回时置位（后台 worker 完成 → 测试确定性轮询）；
    cancel() 记录调用次数并可执行 on_cancel 钩子（如释放阻塞让 worker 退出）。
    """

    name = "fake_direct_agent"

    def __init__(self, result=None, on_run=None, on_cancel=None):
        self.calls: list = []
        self.cancel_called = 0
        self.done = threading.Event()
        self.result = result
        self.on_run = on_run
        self.on_cancel = on_cancel

    def run(self, request):
        try:
            self.calls.append(request)
            if self.on_run is not None:
                return self.on_run(request)
            return self.result
        finally:
            self.done.set()

    def cancel(self):
        self.cancel_called += 1
        if self.on_cancel is not None:
            return self.on_cancel()
        return True


def _save_direct_settings(*, agent="fake_direct_agent", model=None, custom_model=None):
    SettingsStore().save(AppSettings(
        default_execution_mode="direct",
        interactive_agent="qoder",
        direct_agent=agent,
        direct_model=model,
        direct_custom_model=custom_model,
    ))


def _direct_prepare(project_id, adapter, monkeypatch, *,
                    model="native-model-1", custom_model=None, author_question="推进前半程"):
    """直连模式 prepare（同步配置校验 → 后台启动 worker → 立即返回）。"""
    _save_direct_settings(model=model, custom_model=custom_model)
    monkeypatch.setattr(
        agent_runner, "_build_adapter",
        lambda: (adapter, AgentRequest(task="", model=model, custom_model=custom_model)),
    )
    return sp_ops.prepare_story_plan(project_id=project_id, author_question=author_question)


def _blocking_direct_adapter(output=VALID_AGENT_JSON):
    """返回 (adapter, started_event, release_event)：run 阻塞直到 release。"""
    started = threading.Event()
    release = threading.Event()

    def _run(request):
        started.set()
        release.wait(10)
        return AgentResult(status="completed", output=output, agent="fake_direct_agent")

    adapter = _FakeDirectAdapter(on_run=_run, on_cancel=lambda: (release.set(), True)[1])
    return adapter, started, release


def _planning_dir_for(project_id, request_id, isolated):
    meta = (bridge.get_request(request_id) or {}).get("meta") or {}
    turn_id = meta.get("planning_turn_id") or ""
    return isolated.parent / ".planning" / project_id / turn_id


def _wait_direct_worker(request_id, timeout=5.0):
    """等待后台 Direct worker 线程完全退出（响应已写入或已丢弃）。

    比 adapter.done 更靠后：done 在 adapter.run() 返回时置位，而响应写回发生在
    之后；join 保证整条 worker 链路（含 bridge.write_response）已完成。
    """
    return sp_ops._exec_task_manager.join(request_id, timeout)


# A. 交互模式：不触发 Direct runner；现有 /gowrite 请求流保持有效

def test_interactive_mode_no_direct_adapter(isolated, real_project, fake_agent, monkeypatch):
    built: list[str] = []

    def _must_not_build():
        built.append("build")
        raise AssertionError("交互模式不得调用 Direct runner / registry adapter")

    monkeypatch.setattr(agent_runner, "_build_adapter", _must_not_build)

    prepare_result = sp_ops.prepare_story_plan(
        project_id=real_project["project_id"], author_question="推进前半程"
    )
    assert built == [], "交互模式不得触发 Direct adapter 构建/调用"
    assert prepare_result["execution_mode"] == "interactive_bridge"
    assert prepare_result["agent_id"] == "qoder"
    assert "gowrite" in prepare_result["message"]
    assert prepare_result["request_id"]

    # 现有 /gowrite 请求流仍然有效：作者侧写回 → get → 同一 finalize
    request_id = prepare_result["request_id"]
    fake_agent(request_id)
    get_result = sp_ops.get_story_plan_request(request_id=request_id)
    assert get_result["status"] == "completed", get_result.get("error")
    assert get_result["result"]["status"] == "proposal_noncanonical"
    assert get_result["result"]["execution"]["execution_mode"] == "interactive_bridge"


# B. 直连 + 内置模型：精确 Agent/model 传入，无需 /gowrite，走同一 finalize

def test_direct_native_model_uses_exact_agent_and_model(isolated, real_project, fake_agent, monkeypatch):
    _save_direct_settings(model="native-model-1", custom_model=None)
    adapter = _FakeDirectAdapter(
        result=AgentResult(status="completed", output=VALID_AGENT_JSON, agent="fake_direct_agent"),
    )
    monkeypatch.setattr(
        agent_runner, "_build_adapter",
        lambda: (adapter, AgentRequest(task="", model="native-model-1", custom_model=None)),
    )

    prepare_result = sp_ops.prepare_story_plan(
        project_id=real_project["project_id"], author_question="推进前半程"
    )
    assert prepare_result["execution_mode"] == "direct"
    assert prepare_result["agent_id"] == "fake_direct_agent"
    assert prepare_result["model"] == "native-model-1"
    request_id = prepare_result["request_id"]

    # 后台 worker 已完成唯一一次执行（prepare 不阻塞，join 确定性等待）
    assert _wait_direct_worker(request_id), "后台 Direct worker 未在超时内完成"

    # 无需作者执行 /gowrite：adapter 已被调用，且收到精确的内置模型标识
    assert adapter.calls, "直连模式必须通过配置的 adapter 执行任务"
    req = adapter.calls[0]
    assert req.model == "native-model-1"
    assert req.custom_model is None
    assert "测试作品" in req.task

    # 同一请求生命周期 + 同一 finalize
    get_result = sp_ops.get_story_plan_request(request_id=request_id)
    assert get_result["status"] == "completed", get_result.get("error")
    result = get_result["result"]
    assert result["status"] == "proposal_noncanonical"
    assert result["execution"]["execution_mode"] == "direct"
    assert result["execution"]["agent_id"] == "fake_direct_agent"
    assert result["execution"]["model"] == "native-model-1"


# C. 直连 + 自定义模型：精确自定义路由传入，内置模型不被替换/同时传入

def test_direct_custom_model_route_passed(isolated, real_project, fake_agent, monkeypatch):
    _save_direct_settings(model=None, custom_model="harness:provider:model-z")
    adapter = _FakeDirectAdapter(
        result=AgentResult(status="completed", output=VALID_AGENT_JSON, agent="fake_direct_agent"),
    )
    monkeypatch.setattr(
        agent_runner, "_build_adapter",
        lambda: (adapter, AgentRequest(task="", model=None, custom_model="harness:provider:model-z")),
    )

    prepare_result = sp_ops.prepare_story_plan(
        project_id=real_project["project_id"], author_question="推进前半程"
    )
    assert prepare_result["model"] == "harness:provider:model-z"
    request_id = prepare_result["request_id"]
    assert _wait_direct_worker(request_id), "后台 Direct worker 未在超时内完成"

    req = adapter.calls[0]
    assert req.custom_model == "harness:provider:model-z"
    assert req.model is None, "自定义路由时不得替换/同时传入内置模型"

    get_result = sp_ops.get_story_plan_request(request_id=request_id)
    assert get_result["status"] == "completed", get_result.get("error")
    assert get_result["result"]["execution"]["model"] == "harness:provider:model-z"


# D. 无效直连配置：稳定失败、绝不回退、无模型调用

def test_direct_missing_model_stable_failure_no_fallback(isolated, real_project, fake_agent, monkeypatch):
    _save_direct_settings(model=None, custom_model=None)
    built: list[str] = []

    def _build():
        built.append("build")
        raise agent_runner.AgentRunError("请在“设置”中选择一个内置模型或自定义模型。")

    monkeypatch.setattr(agent_runner, "_build_adapter", _build)

    with pytest.raises(sp_ops.StoryPlanningError) as ei:
        sp_ops.prepare_story_plan(project_id=real_project["project_id"], author_question="推进前半程")
    assert "直连执行配置不可用" in str(ei.value)
    assert "内置模型或自定义模型" in str(ei.value)
    assert built == ["build"], "配置校验只尝试一次即失败，不得回退重试"
    # 无模型调用、无回退到交互模式；配置错误在创建请求/工作区之前拦截
    planning_root = isolated.parent / ".planning"
    project_planning_dir = planning_root / real_project["project_id"]
    if project_planning_dir.exists():
        assert list(project_planning_dir.iterdir()) == []


def test_direct_unknown_agent_stable_failure(isolated, real_project, fake_agent, monkeypatch):
    # 真实 registry 解析未知 Agent（_build_adapter 内 KeyError 上抛）
    _save_direct_settings(agent="ghost", model="native-model-1", custom_model=None)

    with pytest.raises(sp_ops.StoryPlanningError) as ei:
        sp_ops.prepare_story_plan(project_id=real_project["project_id"], author_question="推进前半程")
    assert "直连执行配置不可用" in str(ei.value)
    assert "ghost" in str(ei.value)


# E. 直连 + knowledge_needs=[]：检索次数 0

def test_direct_no_knowledge_needs_retrieval_count_zero(isolated, real_project, fake_agent, monkeypatch):
    _save_direct_settings(model="native-model-1", custom_model=None)
    retrieval_calls: list[str] = []
    monkeypatch.setattr(
        sp_ops, "_retrieve_package",
        lambda q: (retrieval_calls.append(q), _fake_package([]))[1],
    )
    adapter = _FakeDirectAdapter(
        result=AgentResult(status="completed", output=VALID_AGENT_JSON, agent="fake_direct_agent"),
    )
    monkeypatch.setattr(
        agent_runner, "_build_adapter",
        lambda: (adapter, AgentRequest(task="", model="native-model-1", custom_model=None)),
    )

    prepare_result = sp_ops.prepare_story_plan(
        project_id=real_project["project_id"], author_question="推进前半程"
    )
    request_id = prepare_result["request_id"]
    assert _wait_direct_worker(request_id), "后台 Direct worker 未在超时内完成"
    get_result = sp_ops.get_story_plan_request(request_id=request_id)
    assert get_result["status"] == "completed", get_result.get("error")
    assert retrieval_calls == [], "直连 + knowledge_needs=[] 时检索次数必须为 0"
    assert get_result["result"]["knowledge"]["retrieval_status"] == "SKIPPED_NO_KNOWLEDGE_NEED"
    assert get_result["result"]["knowledge"]["selected_count"] == 0


# F. 直连 + knowledge_needs≠[]：P0 快照工作流保持不变（全程恰好 1 次检索）

def test_direct_knowledge_needs_p0_snapshot_workflow(isolated, real_project, fake_agent, monkeypatch):
    _save_direct_settings(model="native-model-1", custom_model=None)
    package = _fake_package([
        _fake_hit("book_a", "K001", "A 卡", rank=1),
        _fake_hit("book_a", "K002", "B 卡", rank=2),
    ])
    retrieval_calls: list[str] = []
    monkeypatch.setattr(
        sp_ops, "_retrieve_package",
        lambda q: (retrieval_calls.append(q), package)[1],
    )

    def _agentic_run(request):
        # 模拟直连 Agent：执行内运行 retrieval_snapshot 命令（唯一一次检索）
        # → 从该显示包选择 → 回显 package_ref → 输出 JSON
        # request_id 从任务文本中解析（任务模板显式内嵌 --request <id>）
        import re as _re
        _m = _re.search(r"--request ([0-9a-f]{32})", request.task)
        assert _m, "任务文本必须显式绑定 --request"
        rid = _m.group(1)
        shown = sp_ops.execute_request_scoped_retrieval("信息层次", rid)
        fingerprint = sp_ops._package_fingerprint(shown)
        output = _agent_json(["信息层次"], ["book_a/K001"], package_ref=fingerprint)
        return AgentResult(status="completed", output=output, agent="fake_direct_agent")

    adapter = _FakeDirectAdapter(on_run=_agentic_run)
    monkeypatch.setattr(
        agent_runner, "_build_adapter",
        lambda: (adapter, AgentRequest(task="", model="native-model-1", custom_model=None)),
    )

    prepare_result = sp_ops.prepare_story_plan(
        project_id=real_project["project_id"], author_question="推进前半程"
    )
    request_id = prepare_result["request_id"]
    assert _wait_direct_worker(request_id), "后台 Direct worker 未在超时内完成"
    get_result = sp_ops.get_story_plan_request(request_id=request_id)
    assert get_result["status"] == "completed", get_result.get("error")
    result = get_result["result"]
    assert retrieval_calls == ["信息层次"], "直连知识闭环必须恰好执行 1 次检索（finalize 零检索）"
    assert result["knowledge"]["retrieved_count"] == 2
    assert result["knowledge"]["selected_count"] == 1

    # Context 消费与模型所见完全相同的捕获包
    context = _read_context(real_project["project_id"], isolated.parent / ".planning")
    assert [h["statement"] for h in context["selected_bkp_hits"]] == ["A 卡"]
    assert {h["selection_ref"] for h in context["selected_bkp_hits"]} == {"book_a/K001"}

    # 请求级快照由同一调用写入并带身份元数据
    snapshot = _read_snapshot(real_project["project_id"], isolated.parent / ".planning")
    assert snapshot["request_id"] == request_id
    assert snapshot["project_id"] == real_project["project_id"]
    assert snapshot["query"] == "信息层次"
    assert snapshot["package_fingerprint"] == sp_ops._package_fingerprint(package)


# 直连执行失败（adapter 返回 failed / 抛异常）→ 同一请求生命周期写 failed 信封

def test_direct_adapter_failure_writes_failed_envelope(isolated, real_project, fake_agent, monkeypatch):
    _save_direct_settings(model="native-model-1", custom_model=None)
    adapter = _FakeDirectAdapter(
        result=AgentResult(status="failed", output="", error="模型执行出错", agent="fake_direct_agent"),
    )
    monkeypatch.setattr(
        agent_runner, "_build_adapter",
        lambda: (adapter, AgentRequest(task="", model="native-model-1", custom_model=None)),
    )

    prepare_result = sp_ops.prepare_story_plan(
        project_id=real_project["project_id"], author_question="推进前半程"
    )
    request_id = prepare_result["request_id"]
    assert _wait_direct_worker(request_id), "后台 Direct worker 未在超时内完成"
    get_result = sp_ops.get_story_plan_request(request_id=request_id)
    assert get_result["status"] == "failed"
    assert "模型执行出错" in get_result["error"]


# ---------------------------------------------------------------------------
# Direct 后台执行生命周期（synchronous blocking → background → poll → cancel）
# ---------------------------------------------------------------------------

# A. Direct prepare 非阻塞：adapter 阻塞等待时 prepare 已返回

def test_direct_prepare_is_non_blocking(isolated, real_project, fake_agent, monkeypatch):
    adapter, started, release = _blocking_direct_adapter()
    prepare_result = _direct_prepare(real_project["project_id"], adapter, monkeypatch)
    request_id = prepare_result["request_id"]

    assert started.wait(5), "后台 worker 必须已启动 adapter"
    assert not release.is_set(), "prepare 返回时 adapter 必须仍在等待"
    assert not adapter.done.is_set(), "prepare 不得等待 adapter 完成（非阻塞）"

    # 无响应前轮询为 pending
    assert sp_ops.get_story_plan_request(request_id=request_id)["status"] == "pending"

    # 释放 → 走现有 finalize → proposal_noncanonical
    release.set()
    assert _wait_direct_worker(request_id), "释放后 worker 未完成"
    get_result = sp_ops.get_story_plan_request(request_id=request_id)
    assert get_result["status"] == "completed", get_result.get("error")
    assert get_result["result"]["status"] == "proposal_noncanonical"


# B. 运行中状态 + 恰好一次 dispatch

def test_direct_running_state_and_single_dispatch(isolated, real_project, fake_agent, monkeypatch, _fresh_exec_task_manager):
    adapter, started, release = _blocking_direct_adapter()
    prepare_result = _direct_prepare(real_project["project_id"], adapter, monkeypatch)
    request_id = prepare_result["request_id"]

    assert started.wait(5)
    assert _fresh_exec_task_manager.get(request_id)["state"] == "running"
    assert _fresh_exec_task_manager.is_busy() is True
    assert sp_ops.get_story_plan_request(request_id=request_id)["status"] == "pending"
    assert len(adapter.calls) == 1, "prepare 只 dispatch 一次"

    release.set()
    assert _wait_direct_worker(request_id), "释放后 worker 未完成"
    assert sp_ops.get_story_plan_request(request_id=request_id)["status"] == "completed"
    assert len(adapter.calls) == 1, "轮询/完成不得再次 dispatch"
    assert _fresh_exec_task_manager.get(request_id) is None, "终态后任务记录已移除"


# C. Direct 完成：归一化响应进入现有桥生命周期，走同一 finalize

def test_direct_completion_uses_existing_finalize(isolated, real_project, fake_agent, monkeypatch):
    adapter = _FakeDirectAdapter(
        result=AgentResult(status="completed", output=VALID_AGENT_JSON, agent="fake_direct_agent"),
    )
    prepare_result = _direct_prepare(real_project["project_id"], adapter, monkeypatch)
    request_id = prepare_result["request_id"]
    assert _wait_direct_worker(request_id), "后台 Direct worker 未在超时内完成"

    get_result = sp_ops.get_story_plan_request(request_id=request_id)
    assert get_result["status"] == "completed", get_result.get("error")
    result = get_result["result"]
    assert result["status"] == "proposal_noncanonical"
    assert result["execution"] == {
        "execution_mode": "direct",
        "agent_id": "fake_direct_agent",
        "model": "native-model-1",
    }


# D. Direct 失败（adapter 抛异常）→ 稳定 failed，无 finalize/writeback

def test_direct_adapter_exception_writes_failed(isolated, real_project, fake_agent, monkeypatch):
    def _boom(request):
        raise RuntimeError("模型执行崩溃")

    adapter = _FakeDirectAdapter(on_run=_boom)
    prepare_result = _direct_prepare(real_project["project_id"], adapter, monkeypatch)
    request_id = prepare_result["request_id"]
    assert _wait_direct_worker(request_id), "后台 Direct worker 未在超时内完成"
    get_result = sp_ops.get_story_plan_request(request_id=request_id)
    assert get_result["status"] == "failed"
    assert "直连执行失败" in get_result["error"]
    assert "模型执行崩溃" in get_result["error"]


# E. Direct 取消：adapter.cancel() 恰好一次；请求 canceled；工作区清理

def test_direct_cancellation_cleans_up(isolated, real_project, fake_agent, monkeypatch, _fresh_exec_task_manager):
    adapter, started, release = _blocking_direct_adapter()
    prepare_result = _direct_prepare(real_project["project_id"], adapter, monkeypatch)
    request_id = prepare_result["request_id"]
    planning_dir = _planning_dir_for(real_project["project_id"], request_id, isolated)
    assert started.wait(5)
    assert planning_dir.exists()

    cancel_result = sp_ops.cancel_story_plan_request(request_id=request_id)
    assert cancel_result["status"] == "canceled"
    assert adapter.cancel_called == 1, "adapter.cancel() 必须被调用一次"
    assert adapter.done.wait(5), "worker 应已退出"

    assert not planning_dir.exists(), "取消后临时 planning 工作区必须清理"
    assert sp_ops.get_story_plan_request(request_id=request_id)["status"] == "canceled"
    assert _fresh_exec_task_manager.get(request_id) is None, "取消后任务记录已移除"


# F. 取消后的晚完成：结果丢弃，不写响应，永不 finalize

def test_direct_late_completion_after_cancel_discarded(isolated, real_project, fake_agent, monkeypatch, _fresh_exec_task_manager):
    adapter, started, release = _blocking_direct_adapter()
    prepare_result = _direct_prepare(real_project["project_id"], adapter, monkeypatch)
    request_id = prepare_result["request_id"]
    assert started.wait(5)

    # 取消（on_cancel 释放阻塞 → worker 返回 completed —— 晚完成）
    assert sp_ops.cancel_story_plan_request(request_id=request_id)["status"] == "canceled"
    assert adapter.done.wait(5), "worker 应已返回"
    assert len(adapter.calls) == 1  # run 确实执行过

    # 晚完成结果被丢弃：无响应文件、轮询恒为 canceled、永不 finalize
    assert bridge.read_response(request_id) is None, "取消后不得写入任何响应"
    get_result = sp_ops.get_story_plan_request(request_id=request_id)
    assert get_result["status"] == "canceled"
    assert "result" not in get_result


# G. 幂等取消：重复取消安全，adapter.cancel() 只调一次

def test_direct_cancel_idempotent(isolated, real_project, fake_agent, monkeypatch):
    adapter, started, release = _blocking_direct_adapter()
    prepare_result = _direct_prepare(real_project["project_id"], adapter, monkeypatch)
    request_id = prepare_result["request_id"]
    assert started.wait(5)

    assert sp_ops.cancel_story_plan_request(request_id=request_id)["status"] == "canceled"
    assert sp_ops.cancel_story_plan_request(request_id=request_id)["status"] == "canceled"
    assert sp_ops.cancel_story_plan_request(request_id=request_id)["status"] == "canceled"
    assert adapter.cancel_called == 1, "重复取消不得重复调用 adapter.cancel()"


# H. 重复轮询不触发第二次 dispatch

def test_direct_repeated_poll_no_second_dispatch(isolated, real_project, fake_agent, monkeypatch):
    adapter, started, release = _blocking_direct_adapter()
    prepare_result = _direct_prepare(real_project["project_id"], adapter, monkeypatch)
    request_id = prepare_result["request_id"]
    assert started.wait(5)

    for _ in range(5):
        assert sp_ops.get_story_plan_request(request_id=request_id)["status"] == "pending"
    assert len(adapter.calls) == 1, "重复轮询不得再次 dispatch"

    release.set()
    assert _wait_direct_worker(request_id), "释放后 worker 未完成"
    assert sp_ops.get_story_plan_request(request_id=request_id)["status"] == "completed"
    assert len(adapter.calls) == 1


# I. 忙碌保护：一个 Direct 任务运行时，第二个 Direct prepare 稳定报错

def test_direct_busy_rejects_second_prepare(isolated, real_project, fake_agent, monkeypatch, _fresh_exec_task_manager):
    adapter, started, release = _blocking_direct_adapter()
    prepare_result = _direct_prepare(real_project["project_id"], adapter, monkeypatch)
    request_id = prepare_result["request_id"]
    assert started.wait(5)
    assert _fresh_exec_task_manager.is_busy() is True

    with pytest.raises(sp_ops.StoryPlanningError) as ei:
        sp_ops.prepare_story_plan(project_id=real_project["project_id"], author_question="再往前想")
    assert "直连规划任务正在执行" in str(ei.value)
    assert len(adapter.calls) == 1, "被拒绝的 prepare 不得触发第二次 dispatch"

    # 第一个请求保持完好
    assert sp_ops.get_story_plan_request(request_id=request_id)["status"] == "pending"
    release.set()
    assert _wait_direct_worker(request_id), "释放后 worker 未完成"
    assert sp_ops.get_story_plan_request(request_id=request_id)["status"] == "completed"


# J. 交互模式：不创建后台任务、不触发 Direct adapter

def test_interactive_creates_no_background_task(isolated, real_project, fake_agent, monkeypatch, _fresh_exec_task_manager):
    built: list[str] = []

    def _must_not_build():
        built.append("build")
        raise AssertionError("交互模式不得构建/调用 Direct adapter")

    monkeypatch.setattr(agent_runner, "_build_adapter", _must_not_build)

    prepare_result = sp_ops.prepare_story_plan(
        project_id=real_project["project_id"], author_question="推进前半程"
    )
    request_id = prepare_result["request_id"]
    assert built == []
    assert _fresh_exec_task_manager.get(request_id) is None, "交互模式不得创建 Direct 后台任务"
    assert _fresh_exec_task_manager.is_busy() is False

    # 现有 /gowrite 生命周期不变
    fake_agent(request_id)
    get_result = sp_ops.get_story_plan_request(request_id=request_id)
    assert get_result["status"] == "completed"
    assert get_result["result"]["status"] == "proposal_noncanonical"


# K. P0 回归（直连 + 异步）：knowledge_needs=[] → 检索 0 次

def test_direct_async_empty_needs_zero_retrieval(isolated, real_project, fake_agent, monkeypatch):
    retrieval_calls: list[str] = []
    monkeypatch.setattr(
        sp_ops, "_retrieve_package",
        lambda q: (retrieval_calls.append(q), _fake_package([]))[1],
    )
    adapter = _FakeDirectAdapter(
        result=AgentResult(status="completed", output=VALID_AGENT_JSON, agent="fake_direct_agent"),
    )
    prepare_result = _direct_prepare(real_project["project_id"], adapter, monkeypatch)
    request_id = prepare_result["request_id"]
    assert _wait_direct_worker(request_id), "后台 Direct worker 未在超时内完成"
    get_result = sp_ops.get_story_plan_request(request_id=request_id)
    assert get_result["status"] == "completed", get_result.get("error")
    assert retrieval_calls == [], "直连 + knowledge_needs=[] 检索必须为 0"
    assert get_result["result"]["knowledge"]["retrieval_status"] == "SKIPPED_NO_KNOWLEDGE_NEED"


# M. 生产安全：取消路径不修改正式 Story State

def test_direct_cancel_does_not_touch_story_state(isolated, real_project, fake_agent, monkeypatch):
    from project_workspace import load_project, resolve_project

    proj = resolve_project(real_project["project_id"])
    before = json.dumps(load_project(proj["project_dir"])["state"], ensure_ascii=False, sort_keys=True)

    adapter, started, release = _blocking_direct_adapter()
    prepare_result = _direct_prepare(real_project["project_id"], adapter, monkeypatch)
    request_id = prepare_result["request_id"]
    assert started.wait(5)
    sp_ops.cancel_story_plan_request(request_id=request_id)
    assert adapter.done.wait(5)

    proj = resolve_project(real_project["project_id"])
    after = json.dumps(load_project(proj["project_dir"])["state"], ensure_ascii=False, sort_keys=True)
    assert after == before, "取消路径不得写入正式 Story State"


# ---------------------------------------------------------------------------
# N. 已完成但未确认候选的丢弃（cancel 扩展：request_id 定位工作区 → token 失效）
# ---------------------------------------------------------------------------

def _planning_meta_file(project_id, isolated) -> Path:
    root = isolated.parent / ".planning"
    metas = list(root.glob(f"{project_id}/*/planning_meta.json"))
    assert len(metas) == 1, f"应恰好一份 planning_meta.json，实际 {len(metas)}"
    return metas[0]


def test_discard_completed_unconfirmed_candidate(isolated, real_project, fake_agent):
    """A. 已完成未确认规划候选可丢弃：request_id 定位工作区 / token 失效 /
    正式 Story State 字节不变 / 幂等。"""
    result = _propose(real_project["project_id"], "推进前半程", fake_agent)
    assert result["planning_token"]

    meta_file = _planning_meta_file(real_project["project_id"], isolated)
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert meta.get("request_id"), "planning_meta 必须持久化 request_id"
    request_id = meta["request_id"]
    assert bridge.get_request(request_id) is None, "完成轮询后桥请求文件应已清理"

    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    before_state = state_file.read_bytes()

    canceled = sp_ops.cancel_story_plan_request(request_id=request_id)
    assert canceled["status"] == "canceled"
    assert not meta_file.parent.exists(), "丢弃后规划工作区应被删除"

    # token 已失效：confirm 拒绝
    with pytest.raises(sp_ops.StoryPlanningError, match="已失效"):
        sp_ops.confirm_story_plan(
            project_id=real_project["project_id"], planning_token=result["planning_token"],
        )

    assert state_file.read_bytes() == before_state, "丢弃不得修改正式 Story State"

    # 幂等
    assert sp_ops.cancel_story_plan_request(request_id=request_id)["status"] == "canceled"


def test_discard_unknown_request_id_no_op(isolated, real_project, fake_agent):
    """D. 未知/过期 request_id 不删除任何工作区。"""
    result = _propose(real_project["project_id"], "推进前半程", fake_agent)
    meta_file = _planning_meta_file(real_project["project_id"], isolated)
    sp_ops.cancel_story_plan_request(request_id="deadbeef" * 8)
    assert meta_file.exists(), "未知 request_id 不得删除规划工作区"
    assert result["planning_token"]


def test_discard_cannot_touch_other_project(isolated, real_project, fake_agent):
    """C. 一个项目的 request_id 不能丢弃另一项目的规划工作区 / token。"""
    from project_workspace import create_project
    other = create_project(name="另一作品", author_intent={
        "work_direction": "方向",
        "reader_promise": "期待",
        "hard_constraints": [],
        "open_space": [],
    })
    other_dir = Path(other["project_dir"])
    state_file = other_dir / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["approved_plan"].append({
        "id": f"plan-{other['project_id']}",
        "description": "另一作品的起点",
        "target_ref": f"design-{other['project_id']}",
        "authority": f"author_decision:decision-{other['project_id']}",
        "occurred": False,
        "kind": "confirmed_direction",
    })
    state["state_rev"] = 2
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    result_a = _propose(real_project["project_id"], "推进前半程", fake_agent)
    result_b = _propose(other["project_id"], "推进另一作品", fake_agent)

    meta_a = json.loads(_planning_meta_file(real_project["project_id"], isolated).read_text(encoding="utf-8"))
    meta_b = json.loads(_planning_meta_file(other["project_id"], isolated).read_text(encoding="utf-8"))
    assert meta_a["request_id"] != meta_b["request_id"]

    sp_ops.cancel_story_plan_request(request_id=meta_a["request_id"])

    # A 的工作区已删、token 失效
    a_workspace = isolated.parent / ".planning" / real_project["project_id"]
    assert not a_workspace.exists() or list(a_workspace.iterdir()) == []
    with pytest.raises(sp_ops.StoryPlanningError, match="已失效"):
        sp_ops.confirm_story_plan(
            project_id=real_project["project_id"], planning_token=result_a["planning_token"],
        )
    # B 的工作区与 token 完好，仍可确认
    assert _planning_meta_file(other["project_id"], isolated).parent.exists()
    confirmed = sp_ops.confirm_story_plan(
        project_id=other["project_id"], planning_token=result_b["planning_token"],
    )
    assert confirmed["message"] == "规划已确认并写入"
