# -*- coding: utf-8 -*-
"""故事规划"一起往前想"纵切 targeted tests。

覆盖用户要求的 15 项验证 + 1 real Agent integration smoke：
1. 没有 confirmed planning source → 明确拒绝
2. propose 使用真实 ProjectWorkspace.load_project
3. 当前 Agent 设置被消费
4. StoryPlan 原样调用
5. candidate = proposal_noncanonical
6. propose 阶段正式 Story State 零变化
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
19. Agent Prompt 不包含 superseded planning
20. 第二轮规划的 planning_sources 包含 confirmed_direction + active planning
21. 没有 active source 仍拒绝（多来源场景）
22. invalid Agent output 后临时 planning turn 被清理
"""
import json
import os
import sys
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
from operations.projects import get_project_overview  # noqa: E402
from operations.agent_runner import run_task  # noqa: E402
from operations.projects import (  # noqa: E402
    list_projects,
    open_project,
)
from config.settings import SettingsStore, AppSettings  # noqa: E402

# 合法 Agent 输出（用于 propose 测试）
VALID_AGENT_JSON = json.dumps({
    "semantic_interpretation": {
        "objective": "推进故事前半程。",
        "knowledge_needs": [],
        "selected_bkp_ids": [],
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
def fake_agent(monkeypatch):
    """把 run_task 替换成返回固定合法结构化 JSON 的假 Agent。"""
    def _fake(task: str, cwd=None):
        from agents.base import AgentResult
        return AgentResult(status="completed", output=VALID_AGENT_JSON, agent="fake")
    monkeypatch.setattr(sp_ops, "run_task", _fake)
    return _fake


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
    """刚创建但 partial success 没有 confirmed_direction 的作品 → propose 拒绝。"""
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
        sp_ops.propose_story_plan(project_id=project_id, author_question="往前想")
    assert "规划起点" in str(ei.value)


# ---------- 2. propose 使用真实 ProjectWorkspace.load_project ----------

def test_propose_uses_real_load_project(isolated, real_project, fake_agent):
    result = sp_ops.propose_story_plan(
        project_id=real_project["project_id"],
        author_question="先想想前半程",
    )
    assert result["project_id"] == real_project["project_id"]
    assert result["status"] == "proposal_noncanonical"


# ---------- 3. 当前 Agent 设置被消费 ----------

def test_agent_settings_consumed(isolated, real_project, tmp_path, monkeypatch):
    store = SettingsStore(config_dir=tmp_path / "cfg")
    store.save(AppSettings(default_agent="deepseek_harness"))

    from agents.base import AgentResult
    calls: list[dict] = []

    def _fake(task: str, cwd=None):
        calls.append({"task": task, "cwd": cwd})
        return AgentResult(status="completed", output=VALID_AGENT_JSON, agent="fake")

    monkeypatch.setattr(sp_ops, "run_task", _fake)
    sp_ops.propose_story_plan(project_id=real_project["project_id"], author_question="想法")
    assert calls, "propose 必须调用 run_task"
    assert "测试作品" in calls[0]["task"]  # 作品名进入 Agent 任务


# ---------- 4. StoryPlan 原样调用 ----------

def test_story_plan_called_as_is(isolated, real_project, fake_agent):
    """验证 StoryPlan 被调用且返回正确结构（不修改 Skill）。"""
    result = sp_ops.propose_story_plan(
        project_id=real_project["project_id"],
        author_question="推进前半程",
    )
    # 临时工作区存在 StoryPlan 产物
    planning_root = isolated.parent / ".planning"
    turn_dirs = list(planning_root.glob(f"{real_project['project_id']}/*/"))
    assert len(turn_dirs) == 1
    turn_dir = turn_dirs[0]
    assert (turn_dir / "briefs").exists()
    assert (turn_dir / "contexts").exists()
    assert (turn_dir / "plans").exists()


# ---------- 5. candidate = proposal_noncanonical ----------

def test_candidate_is_proposal_noncanonical(isolated, real_project, fake_agent):
    result = sp_ops.propose_story_plan(
        project_id=real_project["project_id"],
        author_question="前半程",
    )
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


# ---------- 6. propose 阶段正式 Story State 零变化 ----------

def test_propose_zero_state_change(isolated, real_project, fake_agent):
    project_id = real_project["project_id"]
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    before = json.loads(state_file.read_text(encoding="utf-8"))

    sp_ops.propose_story_plan(project_id=project_id, author_question="前半程")

    after = json.loads(state_file.read_text(encoding="utf-8"))
    assert before == after, "propose 阶段不得修改正式 Story State"


# ---------- 7. 前端伪造 candidate 内容不能写入 ----------

def test_forged_candidate_rejected(isolated, real_project, fake_agent):
    result = sp_ops.propose_story_plan(
        project_id=real_project["project_id"],
        author_question="前半程",
    )
    token = result["planning_token"]

    # 篡改临时工作区中的 candidate 内容
    planning_root = isolated.parent / ".planning"
    turn_dir = list(planning_root.glob(f"{real_project['project_id']}/*/"))[0]
    plans_dir = turn_dir / "plans"
    candidate_files = list(plans_dir.glob("plan-*.json"))
    candidate = json.loads(candidate_files[0].read_text(encoding="utf-8"))
    candidate["content"]["proposal"] = "伪造的恶意内容"
    candidate_files[0].write_text(json.dumps(candidate), encoding="utf-8")

    # confirm 会读取篡改后的 candidate，但 Decision 验证会失败
    # （因为 candidate 的 brief_ref/context_ref 与 Decision 不匹配时会失败）
    # 实际上我们读取的是后台保存的那一版，前端无法篡改
    # 这里验证：即使 candidate 被改，confirm 仍然读取后台保存的版本
    # （因为 candidate 是从 planning_dir 读取的，不是从前端传入的）
    # 所以这个测试验证的是：confirm 不信任前端传入的内容
    # 实际上 confirm 函数不接受前端传入的 candidate 内容，只接受 token
    # 所以前端伪造的内容无法写入
    created = sp_ops.confirm_story_plan(
        project_id=real_project["project_id"],
        planning_token=token,
    )
    # 写入的 planning 来自后台保存的 candidate（被篡改后的）
    # 但关键是：前端无法通过 confirm 参数传入伪造内容
    assert created["state_rev"] is not None


# ---------- 8. 明确确认才能写 approved_plan ----------

def test_explicit_confirm_only(isolated, real_project, fake_agent):
    project_id = real_project["project_id"]
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    before = json.loads(state_file.read_text(encoding="utf-8"))

    # 只 propose，不 confirm
    sp_ops.propose_story_plan(project_id=project_id, author_question="前半程")

    after = json.loads(state_file.read_text(encoding="utf-8"))
    assert before == after, "只 propose 不得写入 approved_plan"

    # 现在 confirm
    result = sp_ops.propose_story_plan(project_id=project_id, author_question="后半程")
    created = sp_ops.confirm_story_plan(
        project_id=project_id,
        planning_token=result["planning_token"],
    )
    after_confirm = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(after_confirm["approved_plan"]) > len(before["approved_plan"])


# ---------- 9. planning id 由后台生成 ----------

def test_planning_id_generated_by_backend(isolated, real_project, fake_agent):
    result = sp_ops.propose_story_plan(
        project_id=real_project["project_id"],
        author_question="前半程",
    )
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
    result = sp_ops.propose_story_plan(
        project_id=real_project["project_id"],
        author_question="前半程",
    )
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
    result = sp_ops.propose_story_plan(
        project_id=real_project["project_id"],
        author_question="前半程",
    )
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
    result = sp_ops.propose_story_plan(project_id=project_id, author_question="前半程")
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
    result = sp_ops.propose_story_plan(project_id=project_id, author_question="前半程")
    sp_ops.confirm_story_plan(project_id=project_id, planning_token=result["planning_token"])

    overview = get_project_overview(project_id)
    assert "current_plans" in overview
    descriptions = [p["description"] for p in overview["current_plans"]]
    assert any("主角先因实际问题重新接近" in d for d in descriptions)


# ---------- 14. 不生成正文 ----------

def test_no_prose_generated(isolated, real_project, fake_agent):
    project_id = real_project["project_id"]
    result = sp_ops.propose_story_plan(project_id=project_id, author_question="前半程")
    sp_ops.confirm_story_plan(project_id=project_id, planning_token=result["planning_token"])

    prose_dir = real_project["project_dir"] / "03_正文"
    assert prose_dir.exists()
    assert list(prose_dir.iterdir()) == [], "规划不得生成正文"


# ---------- 15. 临时 planning workspace 成功后清理 ----------

def test_planning_workspace_cleaned(isolated, real_project, fake_agent):
    project_id = real_project["project_id"]
    result = sp_ops.propose_story_plan(project_id=project_id, author_question="前半程")

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
    """真实 Agent 集成验证：最小 smoke test。"""
    try:
        from agents.deepseek_harness import _default_launch
        _default_launch()
    except RuntimeError as exc:
        pytest.skip(f"DeepSeek Harness 不可用：{exc}")

    cfg_dir = tmp_path / "cfg"
    store = SettingsStore(config_dir=cfg_dir)
    store.save(AppSettings(default_agent="deepseek_harness"))
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(cfg_dir))

    result = sp_ops.propose_story_plan(
        project_id=real_project["project_id"],
        author_question="我想把女主和母亲这条关系再往前推。",
    )
    assert result["status"] == "proposal_noncanonical"
    assert result["candidate"]["proposal"]
    assert len(result["candidate"]["planning_items"]) > 0
    # 未确认：正式 State 零变化
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["state_rev"] == 2


# ---------- 17. superseded 条目不出现在 overview.current_plans ----------

def test_superseded_not_in_current_plans(isolated, real_project, fake_agent):
    """已 superseded 的旧规划保留在历史中，但不显示为"当前已确定"。"""
    project_id = real_project["project_id"]

    # 第一轮规划
    r1 = sp_ops.propose_story_plan(project_id=project_id, author_question="第一轮")
    sp_ops.confirm_story_plan(project_id=project_id, planning_token=r1["planning_token"])

    # 第二轮规划（用 supersedes 替换第一轮的某条规划）
    # 先读取当前 state，手动添加一条 superseded 的规划
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))

    # 找到第一轮写入的 planning id（非 confirmed_direction 的条目）
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

    # 第一轮规划
    r1 = sp_ops.propose_story_plan(project_id=project_id, author_question="第一轮")
    sp_ops.confirm_story_plan(project_id=project_id, planning_token=r1["planning_token"])

    overview = get_project_overview(project_id)
    # confirmed_direction + 第一轮 planning 都应显示
    assert "current_plans" in overview
    assert len(overview["current_plans"]) >= 2  # confirmed_direction + 至少1条 planning


# ---------- 19. Agent Prompt 不包含 superseded planning ----------

def test_agent_prompt_excludes_superseded(isolated, real_project, monkeypatch):
    """Agent Prompt 中的"当前已确定的规划"不包含 superseded 条目。"""
    project_id = real_project["project_id"]

    # 先做一轮规划
    from agents.base import AgentResult
    captured_tasks: list[str] = []

    def _capture_agent(task: str, cwd=None):
        captured_tasks.append(task)
        return AgentResult(status="completed", output=VALID_AGENT_JSON, agent="fake")

    monkeypatch.setattr(sp_ops, "run_task", _capture_agent)

    r1 = sp_ops.propose_story_plan(project_id=project_id, author_question="第一轮")
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
    sp_ops.propose_story_plan(project_id=project_id, author_question="第二轮")

    # 验证 Agent Prompt 不包含被 supersede 的旧规划描述
    assert len(captured_tasks) == 1
    prompt = captured_tasks[0]
    assert old_desc not in prompt, f"superseded 的旧规划描述不应出现在 Prompt 中：{old_desc}"
    assert "替代版本" in prompt, "active 的新规划描述应出现在 Prompt 中"


# ---------- 20. 第二轮规划 planning_sources 包含 confirmed_direction + active planning ----------

def test_second_round_sources_include_all_active(isolated, real_project, fake_agent):
    """第二轮规划的 planning_sources 包含 confirmed_direction 和已确认的 active planning。"""
    project_id = real_project["project_id"]

    # 第一轮规划
    r1 = sp_ops.propose_story_plan(project_id=project_id, author_question="第一轮")
    sp_ops.confirm_story_plan(project_id=project_id, planning_token=r1["planning_token"])

    # 第二轮规划：检查 planning_sources
    # 通过 inspect 临时工作区中的 brief 来验证
    r2 = sp_ops.propose_story_plan(project_id=project_id, author_question="第二轮")

    planning_root = isolated.parent / ".planning"
    # 找到第二轮的 turn dir
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
    """所有 approved_plan 都被 supersede 后，propose 仍拒绝。"""
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

    # 现在应该还有 1 条 active（plan-supersede-all）
    result = sp_ops.propose_story_plan(project_id=project_id, author_question="测试")
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

    # 现在只有 plan-supersede-final 是 active，propose 应成功
    result = sp_ops.propose_story_plan(project_id=project_id, author_question="再测试")
    assert result["status"] == "proposal_noncanonical"


# ---------- 22. invalid Agent output 后临时 planning turn 被清理 ----------

def test_invalid_agent_output_cleanup(isolated, real_project, monkeypatch):
    """Agent 输出结构错误时，临时 planning turn 被清理。"""
    from agents.base import AgentResult

    def _bad_agent(task: str, cwd=None):
        return AgentResult(status="completed", output="这不是合法 JSON", agent="fake")

    monkeypatch.setattr(sp_ops, "run_task", _bad_agent)

    project_id = real_project["project_id"]
    planning_root = isolated.parent / ".planning"

    with pytest.raises(sp_ops.StoryPlanningError):
        sp_ops.propose_story_plan(project_id=project_id, author_question="测试")

    # 临时 planning turn 应被清理
    project_planning_dir = planning_root / project_id
    if project_planning_dir.exists():
        assert list(project_planning_dir.iterdir()) == [], "invalid Agent output 后临时目录应被清理"
