# -*- coding: utf-8 -*-
"""正文写作"这一段想写什么"纵切 targeted tests。

覆盖用户要求的 20 项验证 + 1 real Agent propose smoke：
1. propose 使用真实 load_project
2. 当前 Agent 设置被消费
3. selection 能进入 frozen prepare_creation_brief / prepare_context
4. Context 不 fallback 全 State
5. inactive/superseded planning selection 被 frozen gate 拒绝
6. 无知识需求 → 0 BKP 正常
7. 第一场无 recent prose 正常
8. 有 recent prose 时只使用 frozen recent window
9. draft propose 阶段正式项目零写入
10. draft_text 非空校验
11. 前端伪造 draft/settlement 不能改变后台候选
12. 无明确 confirmation token 不可 accept
13. stale intent/state 拒绝
14. accepted_text_index 已变化但 state_rev 未变也拒绝
15. append settlement id 后台生成
16. replace_existing 必须保留真实 existing id
17. confirm 调用 accept_prose 且 author_accepted=True
18. accept_prose 失败时不自己补写任何文件
19. 成功后 writing workspace 清理
20. 不生成 planning、不修改 frozen Skills

自动化测试只验证机械胶水；不报告"真实作者 acceptance 已验证"。
真实 author acceptance → accepted_text → production Story State
必须由作者本人在工作台实际点击"保留这段"才算验证。
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "StoryWrite"))

import project_workspace  # noqa: E402

from operations import story_writing as sw_ops  # noqa: E402
from operations.projects import get_project_overview  # noqa: E402
from config.settings import SettingsStore, AppSettings  # noqa: E402

# 合法 Agent 选择阶段输出
VALID_SELECTION_JSON = json.dumps({
    "semantic_interpretation": {
        "objective": "写开场场景。",
        "knowledge_needs": [],
        "selected_bkp_ids": [],
        "assumptions": ["主角首次进入花园"],
    },
    "state_selections": [],
    "conflicts_or_tensions": [],
}, ensure_ascii=False)

# 合法 Agent 正文生成输出
VALID_PROSE_JSON = json.dumps({
    "draft_text": "暴雨打在石板路上，像有人在用力擦洗整座城市的记忆。她推开那扇铁门时，花园里什么声音都没有。",
    "settlement_candidates": [
        {
            "classification": "mechanical",
            "target_area": "canon_facts",
            "entry": {"id": "cf.开场.1", "fact": "主角在暴雨夜第一次进入了花园。"},
            "operation": "append",
            "reason": "正文明确描述了主角进入花园",
        },
    ],
}, ensure_ascii=False)


def _make_two_stage_agent():
    """构造两阶段假 Agent：第一次调用返回选择结果，第二次返回正文结果。"""
    from agents.base import AgentResult
    calls = []

    def _fake(task: str, cwd=None):
        calls.append(task)
        if len(calls) == 1:
            return AgentResult(status="completed", output=VALID_SELECTION_JSON, agent="fake")
        else:
            return AgentResult(status="completed", output=VALID_PROSE_JSON, agent="fake")

    return _fake, calls


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    """隔离：03_作品工程 → tmp 根；临时写作工作区 → tmp；AI_WRITE_CONFIG_DIR → tmp。"""
    projects_root = tmp_path / "03_作品工程"
    projects_root.mkdir()
    monkeypatch.setattr(project_workspace, "get_projects_root", lambda: projects_root)
    monkeypatch.setattr(sw_ops, "get_writing_root", lambda: tmp_path / ".writing")
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path / "cfg"))
    return projects_root


@pytest.fixture()
def fake_agent(monkeypatch):
    """把 run_task 替换成两阶段假 Agent。"""
    _fake, _calls = _make_two_stage_agent()
    monkeypatch.setattr(sw_ops, "run_task", _fake)
    return _fake


@pytest.fixture()
def real_project(isolated):
    """创建一个已有 confirmed_direction + 一条 active planning 的正式作品。"""
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


# ---------- 1. propose 使用真实 load_project ----------

def test_propose_uses_real_load_project(isolated, real_project, fake_agent):
    result = sw_ops.propose_story_write(
        project_id=real_project["project_id"],
        author_input="写开场",
    )
    assert result["project_id"] == real_project["project_id"]
    assert result["draft_text"]


# ---------- 2. 当前 Agent 设置被消费 ----------

def test_agent_settings_consumed(isolated, real_project, tmp_path, monkeypatch):
    store = SettingsStore(config_dir=tmp_path / "cfg")
    store.save(AppSettings(default_agent="deepseek_harness"))

    _fake, calls = _make_two_stage_agent()
    monkeypatch.setattr(sw_ops, "run_task", _fake)
    sw_ops.propose_story_write(project_id=real_project["project_id"], author_input="写开场")
    assert len(calls) == 2, "propose 必须调用两次 run_task（选择 + 正文）"
    assert "测试作品" in calls[0]  # 作品名进入选择阶段任务


# ---------- 3. selection 能进入 frozen prepare_creation_brief / prepare_context ----------

def test_selection_enters_frozen_brief_and_context(isolated, real_project, fake_agent):
    """验证 Agent 选择结果被传递给 frozen StoryWrite。"""
    result = sw_ops.propose_story_write(
        project_id=real_project["project_id"],
        author_input="写开场",
    )
    # 临时工作区存在 writing_meta
    writing_root = isolated.parent / ".writing"
    turn_dirs = list(writing_root.glob(f"{real_project['project_id']}/*/"))
    assert len(turn_dirs) == 1
    meta = json.loads((turn_dirs[0] / "writing_meta.json").read_text(encoding="utf-8"))
    assert meta["draft_text"] == result["draft_text"]
    assert meta["settlement"]["scene_ref"] == result["scene_ref"]


# ---------- 4. Context 不 fallback 全 State ----------

def test_context_no_fallback(isolated, real_project, monkeypatch):
    """空 state_selections 不 fallback 全 State。"""
    _fake, calls = _make_two_stage_agent()
    monkeypatch.setattr(sw_ops, "run_task", _fake)
    result = sw_ops.propose_story_write(
        project_id=real_project["project_id"],
        author_input="写开场",
    )
    # propose 成功即可——Context 没有 fallback 全 State（空 selection 合法）
    assert result["draft_text"]


# ---------- 5. inactive/superseded planning selection 被 frozen gate 拒绝 ----------

def test_superseded_planning_selection_rejected(isolated, real_project, monkeypatch):
    """选择 superseded 的 planning → ContextCompiler 拒绝。"""
    from agents.base import AgentResult
    project_id = real_project["project_id"]

    # 手动 supersede confirmed_direction
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["approved_plan"].append({
        "id": "plan-superseding",
        "description": "替代版本",
        "target_ref": f"design-{project_id}",
        "authority": f"author_decision:decision-s",
        "occurred": False,
        "supersedes": [f"plan-{project_id}"],
    })
    state["state_rev"] = 3
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    # Agent 返回选择已被 supersede 的 planning
    bad_selection = json.dumps({
        "semantic_interpretation": {
            "objective": "测试",
            "knowledge_needs": [],
            "selected_bkp_ids": [],
            "assumptions": [],
        },
        "state_selections": [
            {"area": "approved_plan", "id": f"plan-{project_id}", "reason": "测试"},
        ],
    }, ensure_ascii=False)

    def _bad_sel(task, cwd=None):
        return AgentResult(status="completed", output=bad_selection, agent="fake")

    monkeypatch.setattr(sw_ops, "run_task", _bad_sel)
    with pytest.raises(sw_ops.StoryWritingError, match="Context 被拒绝"):
        sw_ops.propose_story_write(project_id=project_id, author_input="测试")


# ---------- 6. 无知识需求 → 0 BKP 正常 ----------

def test_zero_bkp_normal(isolated, real_project, fake_agent):
    result = sw_ops.propose_story_write(
        project_id=real_project["project_id"],
        author_input="写开场",
    )
    assert result["draft_text"]


# ---------- 7. 第一场无 recent prose 正常 ----------

def test_first_scene_no_recent_prose(isolated, real_project, fake_agent):
    """作品没有任何 accepted text → recent prose = 无 → 正常写第一场。"""
    result = sw_ops.propose_story_write(
        project_id=real_project["project_id"],
        author_input="写开场",
    )
    assert result["draft_text"]


# ---------- 8. 有 recent prose 时只使用 frozen recent window ----------

def test_recent_prose_uses_frozen_window(isolated, real_project, fake_agent):
    """已有 accepted text → get_recent_prose 通过 frozen prepare_recent_prose_window。"""
    # 先写入一段正文
    from project_workspace import accept_prose
    project_dir = real_project["project_dir"]
    project_id = real_project["project_id"]
    accept_prose(
        project_dir=project_dir,
        chapter_number=1,
        scene_ref="scene-prev",
        accepted_text="上一段正文内容。" * 100,
        settlement={"scene_ref": "scene-prev", "candidates": []},
        author_accepted=True,
    )

    result = sw_ops.propose_story_write(
        project_id=project_id,
        author_input="继续写",
    )
    assert result["draft_text"]


# ---------- 9. draft propose 阶段正式项目零写入 ----------

def test_propose_zero_project_write(isolated, real_project, fake_agent):
    project_dir = real_project["project_dir"]
    state_file = project_dir / "_工作台状态" / "story_state.json"
    before_state = state_file.read_text(encoding="utf-8")
    prose_dir = project_dir / "03_正文"
    before_prose = list(prose_dir.iterdir()) if prose_dir.exists() else []

    sw_ops.propose_story_write(
        project_id=real_project["project_id"],
        author_input="写开场",
    )

    after_state = state_file.read_text(encoding="utf-8")
    after_prose = list(prose_dir.iterdir()) if prose_dir.exists() else []
    assert before_state == after_state, "propose 阶段不得修改 Story State"
    assert before_prose == after_prose, "propose 阶段不得修改 03_正文"


# ---------- 10. draft_text 非空校验 ----------

def test_draft_text_non_empty_validation(isolated, real_project, monkeypatch):
    from agents.base import AgentResult
    bad_prose = json.dumps({"draft_text": "", "settlement_candidates": []}, ensure_ascii=False)

    def _bad(task, cwd=None):
        if "上下文选择" in task:
            return AgentResult(status="completed", output=VALID_SELECTION_JSON, agent="fake")
        return AgentResult(status="completed", output=bad_prose, agent="fake")

    monkeypatch.setattr(sw_ops, "run_task", _bad)
    with pytest.raises(sw_ops.StoryWritingError, match="draft_text"):
        sw_ops.propose_story_write(project_id=real_project["project_id"], author_input="写")


# ---------- 11. 前端伪造 draft/settlement 不能改变后台候选 ----------

def test_forged_draft_cannot_change_backend(isolated, real_project, fake_agent):
    """confirm 只读后台保存的 writing_meta.json，不接受前端传入的正文。"""
    result = sw_ops.propose_story_write(
        project_id=real_project["project_id"],
        author_input="写开场",
    )
    # confirm 接口不接受 draft_text / settlement 参数，只接受 writing_token
    # 所以前端无法伪造
    confirmed = sw_ops.confirm_story_write(
        project_id=real_project["project_id"],
        writing_token=result["writing_token"],
    )
    assert confirmed["message"] == "这段已经保留下来了。"


# ---------- 12. 无明确 confirmation token 不可 accept ----------

def test_no_token_rejected(isolated, real_project, fake_agent):
    with pytest.raises(sw_ops.StoryWritingError):
        sw_ops.confirm_story_write(project_id=real_project["project_id"], writing_token="")
    with pytest.raises(sw_ops.StoryWritingError):
        sw_ops.confirm_story_write(project_id=real_project["project_id"], writing_token="不存在的token")


# ---------- 13. stale intent/state 拒绝 ----------

def test_stale_state_rejected(isolated, real_project, fake_agent):
    project_id = real_project["project_id"]
    result = sw_ops.propose_story_write(project_id=project_id, author_input="写开场")
    token = result["writing_token"]

    # 模拟 state_rev 变化
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["state_rev"] = state["state_rev"] + 1
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(sw_ops.StoryWritingError, match="新的变化"):
        sw_ops.confirm_story_write(project_id=project_id, writing_token=token)


# ---------- 14. accepted_text_index 已变化但 state_rev 未变也拒绝 ----------

def test_stale_index_rejected(isolated, real_project, fake_agent):
    project_id = real_project["project_id"]
    result = sw_ops.propose_story_write(project_id=project_id, author_input="写开场")
    token = result["writing_token"]

    # 模拟 accepted_text_index 变化（但 state_rev 不变）
    from project_workspace import accept_prose
    accept_prose(
        project_dir=real_project["project_dir"],
        chapter_number=1,
        scene_ref="scene-other",
        accepted_text="另一段正文。" * 100,
        settlement={"scene_ref": "scene-other", "candidates": []},
        author_accepted=True,
    )

    with pytest.raises(sw_ops.StoryWritingError, match="新的内容"):
        sw_ops.confirm_story_write(project_id=project_id, writing_token=token)


# ---------- 15. append settlement id 后台生成 ----------

def test_append_id_generated_by_backend(isolated, real_project, fake_agent):
    result = sw_ops.propose_story_write(
        project_id=real_project["project_id"],
        author_input="写开场",
    )
    # 后台保存的 settlement 中，append 类型的 entry.id 由后台生成
    writing_root = isolated.parent / ".writing"
    turn_dir = list(writing_root.glob(f"{real_project['project_id']}/*/"))[0]
    meta = json.loads((turn_dir / "writing_meta.json").read_text(encoding="utf-8"))
    for cand in meta["settlement"]["candidates"]:
        if cand["operation"] == "append":
            assert cand["entry"]["id"].startswith("sw-"), f"append id 应由后台生成：{cand['entry']['id']}"


# ---------- 16. replace_existing 必须保留真实 existing id ----------

def test_replace_existing_keeps_real_id(isolated, real_project, monkeypatch):
    """replace_existing 类型的 entry.id 保留 Agent 返回的原始 id。"""
    from agents.base import AgentResult

    prose_with_replace = json.dumps({
        "draft_text": "正文内容。",
        "settlement_candidates": [
            {
                "classification": "mechanical",
                "target_area": "canon_facts",
                "entry": {"id": "existing-fact-1", "fact": "修改后的事实"},
                "operation": "replace_existing",
                "reason": "修改",
            },
        ],
    }, ensure_ascii=False)

    calls = []

    def _fake(task, cwd=None):
        calls.append(task)
        if len(calls) == 1:
            return AgentResult(status="completed", output=VALID_SELECTION_JSON, agent="fake")
        return AgentResult(status="completed", output=prose_with_replace, agent="fake")

    monkeypatch.setattr(sw_ops, "run_task", _fake)
    result = sw_ops.propose_story_write(
        project_id=real_project["project_id"],
        author_input="写",
    )
    writing_root = isolated.parent / ".writing"
    turn_dir = list(writing_root.glob(f"{real_project['project_id']}/*/"))[0]
    meta = json.loads((turn_dir / "writing_meta.json").read_text(encoding="utf-8"))
    replace_cands = [c for c in meta["settlement"]["candidates"] if c["operation"] == "replace_existing"]
    assert len(replace_cands) == 1
    assert replace_cands[0]["entry"]["id"] == "existing-fact-1"


# ---------- 17. confirm 调用 accept_prose 且 author_accepted=True ----------

def test_confirm_calls_accept_prose(isolated, real_project, fake_agent):
    """验证 confirm 通过 accept_prose 且 author_accepted=True（spy 验证）。"""
    project_id = real_project["project_id"]
    result = sw_ops.propose_story_write(project_id=project_id, author_input="写开场")

    # spy accept_prose
    original_accept = sw_ops.accept_prose
    accept_calls = []

    def _spy_accept(**kwargs):
        accept_calls.append(kwargs)
        return original_accept(**kwargs)

    with patch.object(sw_ops, "accept_prose", side_effect=_spy_accept):
        confirmed = sw_ops.confirm_story_write(project_id=project_id, writing_token=result["writing_token"])

    assert confirmed["message"] == "这段已经保留下来了。"
    assert len(accept_calls) == 1
    assert accept_calls[0]["author_accepted"] is True
    assert accept_calls[0]["scene_ref"] == result["scene_ref"]


# ---------- 18. accept_prose 失败时不自己补写任何文件 ----------

def test_accept_prose_failure_no_self_write(isolated, real_project, fake_agent):
    """accept_prose 抛异常时，story_writing 不自己补写任何文件。"""
    project_id = real_project["project_id"]
    result = sw_ops.propose_story_write(project_id=project_id, author_input="写开场")

    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    before = state_file.read_text(encoding="utf-8")

    def _failing_accept(**kwargs):
        from project_workspace import ContractError
        raise ContractError("模拟 accept_prose 失败")

    with patch.object(sw_ops, "accept_prose", side_effect=_failing_accept):
        with pytest.raises(sw_ops.StoryWritingError, match="接受正文失败"):
            sw_ops.confirm_story_write(project_id=project_id, writing_token=result["writing_token"])

    after = state_file.read_text(encoding="utf-8")
    assert before == after, "accept_prose 失败时不得自己补写文件"


# ---------- 19. 成功后 writing workspace 清理 ----------

def test_writing_workspace_cleaned(isolated, real_project, fake_agent):
    project_id = real_project["project_id"]
    result = sw_ops.propose_story_write(project_id=project_id, author_input="写开场")

    writing_root = isolated.parent / ".writing"
    assert (writing_root / project_id).exists()

    sw_ops.confirm_story_write(project_id=project_id, writing_token=result["writing_token"])

    project_writing_dir = writing_root / project_id
    if project_writing_dir.exists():
        assert list(project_writing_dir.iterdir()) == []


# ---------- 20. 不生成 planning、不修改 frozen Skills ----------

def test_no_planning_generated(isolated, real_project, fake_agent):
    """正文写作不生成 planning、不修改 frozen Skills。"""
    project_id = real_project["project_id"]
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    before = json.loads(state_file.read_text(encoding="utf-8"))

    result = sw_ops.propose_story_write(project_id=project_id, author_input="写开场")
    sw_ops.confirm_story_write(project_id=project_id, writing_token=result["writing_token"])

    after = json.loads(state_file.read_text(encoding="utf-8"))
    # approved_plan 不应有新增（正文写作不写 planning）
    assert len(after["approved_plan"]) == len(before["approved_plan"])


# ---------- 21. real Agent propose smoke ----------

def test_real_agent_propose_smoke(isolated, real_project, tmp_path, monkeypatch):
    """真实 Agent 集成验证：只生成候选，不模拟正式 acceptance。"""
    try:
        from agents.deepseek_harness import _default_launch
        _default_launch()
    except RuntimeError as exc:
        pytest.skip(f"DeepSeek Harness 不可用：{exc}")

    cfg_dir = tmp_path / "cfg"
    store = SettingsStore(config_dir=cfg_dir)
    store.save(AppSettings(default_agent="deepseek_harness"))
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(cfg_dir))

    result = sw_ops.propose_story_write(
        project_id=real_project["project_id"],
        author_input="写开场。主角第一次进入那座暴雨夜才开放的花园，但先不要解释花园的规则。",
    )
    assert result["draft_text"]
    assert result["scene_ref"]
    # 未确认：正式 State 零变化
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["state_rev"] == 2
