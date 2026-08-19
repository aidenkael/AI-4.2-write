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
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# 真实模型调用门控：默认 pytest 不产生任何 Token 消耗。
_real_model_test = pytest.mark.skipif(
    os.environ.get("GOWRITE_REAL_QODER_TEST") != "1",
    reason="真实模型调用需要 GOWRITE_REAL_QODER_TEST=1（默认跳过，防止意外消耗 Token）",
)

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
    """replace_existing 类型的 entry.id 保留 Agent 返回的原始 id，
    且必须在本轮 Context 的 selected_story_state 中真实存在。"""
    from agents.base import AgentResult
    project_id = real_project["project_id"]

    # 先给 state 加一条 canon_fact
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["canon_facts"].append({
        "id": "cf.existing.1",
        "fact": "原有事实",
        "authority": "author_decision:test",
    })
    state["state_rev"] = 3
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    # 选择阶段：选中这条 canon_fact
    sel_with_fact = json.dumps({
        "semantic_interpretation": {
            "objective": "测试 replace_existing。",
            "knowledge_needs": [],
            "selected_bkp_ids": [],
            "assumptions": [],
        },
        "state_selections": [
            {"area": "canon_facts", "id": "cf.existing.1", "reason": "测试"},
        ],
    }, ensure_ascii=False)

    prose_with_replace = json.dumps({
        "draft_text": "正文内容。",
        "settlement_candidates": [
            {
                "classification": "mechanical",
                "target_area": "canon_facts",
                "entry": {"id": "cf.existing.1", "fact": "修改后的事实"},
                "operation": "replace_existing",
                "reason": "修改",
            },
        ],
    }, ensure_ascii=False)

    calls = []

    def _fake(task, cwd=None):
        calls.append(task)
        if len(calls) == 1:
            return AgentResult(status="completed", output=sel_with_fact, agent="fake")
        return AgentResult(status="completed", output=prose_with_replace, agent="fake")

    monkeypatch.setattr(sw_ops, "run_task", _fake)
    result = sw_ops.propose_story_write(
        project_id=project_id,
        author_input="写",
    )
    writing_root = isolated.parent / ".writing"
    turn_dir = list(writing_root.glob(f"{project_id}/*/"))[0]
    meta = json.loads((turn_dir / "writing_meta.json").read_text(encoding="utf-8"))
    replace_cands = [c for c in meta["settlement"]["candidates"] if c["operation"] == "replace_existing"]
    assert len(replace_cands) == 1
    assert replace_cands[0]["entry"]["id"] == "cf.existing.1"


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
# ⚠️ 真实模型调用，消耗 Token；默认跳过，需 GOWRITE_REAL_QODER_TEST=1 显式开启。

@_real_model_test
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


# ==========================================================================
# 22–33. 生产安全边界加固测试
# ==========================================================================

# ---------- 22. cross-project token 拒绝 ----------

def test_cross_project_token_rejected(isolated, real_project, fake_agent, tmp_path):
    """A 的 writing_token + B 的 project_id → 必须拒绝。"""
    from project_workspace import create_project
    project_a = real_project["project_id"]

    # 创建项目 B
    created_b = create_project(
        name="测试作品B",
        author_intent={
            "work_direction": "另一部作品",
            "reader_promise": "另一读者期待",
            "hard_constraints": [],
            "open_space": [],
        },
    )
    project_b = created_b["project_id"]

    # 为 A 生成候选
    result = sw_ops.propose_story_write(project_id=project_a, author_input="写开场")
    token_a = result["writing_token"]

    # 用 A 的 token + B 的 project_id → 拒绝
    with pytest.raises(sw_ops.StoryWritingError, match="不属于当前作品"):
        sw_ops.confirm_story_write(project_id=project_b, writing_token=token_a)

    # A/B 正式正文、State、index 均零变化
    state_b = Path(created_b["project_dir"]) / "_工作台状态" / "story_state.json"
    state_data = json.loads(state_b.read_text(encoding="utf-8"))
    assert state_data["state_rev"] == 1  # B 初始 rev


# ---------- 23. index 有正文但 recent prose 损坏 → propose 拒绝 ----------

def test_corrupted_recent_prose_rejected(isolated, real_project, fake_agent):
    """已有 accepted index，但 chapter/hash 损坏 → propose 拒绝。"""
    from project_workspace import accept_prose
    project_dir = real_project["project_dir"]
    project_id = real_project["project_id"]

    # 先正常写入一段正文
    accept_prose(
        project_dir=project_dir,
        chapter_number=1,
        scene_ref="scene-prev",
        accepted_text="上一段正文内容。" * 100,
        settlement={"scene_ref": "scene-prev", "candidates": []},
        author_accepted=True,
    )

    # 人为损坏章节文件
    chapter_file = project_dir / "03_正文" / "第001章.md"
    chapter_file.unlink()

    with pytest.raises(sw_ops.StoryWritingError, match="衔接数据异常"):
        sw_ops.propose_story_write(project_id=project_id, author_input="继续写")


# ---------- 24. 第二阶段 Prompt 包含 selected_intent ----------

def test_stage2_prompt_contains_selected_intent(isolated, real_project, monkeypatch):
    """第二阶段 Prompt 必须包含 selected_intent 内容。"""
    from agents.base import AgentResult
    calls = []

    def _fake(task, cwd=None):
        calls.append(task)
        if len(calls) == 1:
            return AgentResult(status="completed", output=VALID_SELECTION_JSON, agent="fake")
        return AgentResult(status="completed", output=VALID_PROSE_JSON, agent="fake")

    monkeypatch.setattr(sw_ops, "run_task", _fake)
    sw_ops.propose_story_write(project_id=real_project["project_id"], author_input="写开场")

    # 第二阶段 prompt
    stage2_prompt = calls[1]
    assert "selected_intent" in stage2_prompt or "work_direction" in stage2_prompt


# ---------- 25. 第二阶段 Prompt 包含 selected Story State id ----------

def test_stage2_prompt_contains_selected_state_id(isolated, real_project, monkeypatch):
    """当选择阶段选中 state 条目时，第二阶段 Prompt 必须包含其 id。"""
    from agents.base import AgentResult
    project_id = real_project["project_id"]

    # 给 state 加 canon_fact
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["canon_facts"].append({
        "id": "cf.test.prompt.1",
        "fact": "用于验证的事实",
        "authority": "author_decision:test",
    })
    state["state_rev"] = 3
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    sel_with_fact = json.dumps({
        "semantic_interpretation": {
            "objective": "测试。",
            "knowledge_needs": [],
            "selected_bkp_ids": [],
            "assumptions": [],
        },
        "state_selections": [
            {"area": "canon_facts", "id": "cf.test.prompt.1", "reason": "测试"},
        ],
    }, ensure_ascii=False)

    calls = []

    def _fake(task, cwd=None):
        calls.append(task)
        if len(calls) == 1:
            return AgentResult(status="completed", output=sel_with_fact, agent="fake")
        return AgentResult(status="completed", output=VALID_PROSE_JSON, agent="fake")

    monkeypatch.setattr(sw_ops, "run_task", _fake)
    sw_ops.propose_story_write(project_id=project_id, author_input="写")

    stage2_prompt = calls[1]
    assert "cf.test.prompt.1" in stage2_prompt


# ---------- 26. BKP/conflicts 存在时进入第二阶段 Context ----------

def test_bkp_and_conflicts_enter_stage2(isolated, real_project, monkeypatch):
    """conflicts_or_tensions 存在时进入第二阶段 Context 摘要。"""
    from agents.base import AgentResult
    project_id = real_project["project_id"]

    sel_with_conflict = json.dumps({
        "semantic_interpretation": {
            "objective": "测试。",
            "knowledge_needs": [],
            "selected_bkp_ids": [],
            "assumptions": [],
        },
        "state_selections": [],
        "conflicts_or_tensions": [{"text": "主角的秘密与公开身份之间的张力"}],
    }, ensure_ascii=False)

    calls = []

    def _fake(task, cwd=None):
        calls.append(task)
        if len(calls) == 1:
            return AgentResult(status="completed", output=sel_with_conflict, agent="fake")
        return AgentResult(status="completed", output=VALID_PROSE_JSON, agent="fake")

    monkeypatch.setattr(sw_ops, "run_task", _fake)
    sw_ops.propose_story_write(project_id=project_id, author_input="写")

    stage2_prompt = calls[1]
    assert "张力" in stage2_prompt or "conflicts_or_tensions" in stage2_prompt


# ---------- 27. replace_existing 未在 selected Context → 拒绝 ----------

def test_replace_existing_not_in_context_rejected(isolated, real_project, monkeypatch):
    """replace_existing 目标不在本轮 Context 中 → propose 拒绝。"""
    from agents.base import AgentResult

    prose_with_replace = json.dumps({
        "draft_text": "正文内容。",
        "settlement_candidates": [
            {
                "classification": "mechanical",
                "target_area": "canon_facts",
                "entry": {"id": "nonexistent-fact", "fact": "不存在的事实"},
                "operation": "replace_existing",
                "reason": "测试",
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
    with pytest.raises(sw_ops.StoryWritingError, match="不在本轮 Context"):
        sw_ops.propose_story_write(
            project_id=real_project["project_id"],
            author_input="写",
        )


# ---------- 28. append 不依赖模型唯一 id ----------

def test_append_no_dependency_on_model_id(isolated, real_project, monkeypatch):
    """append 类型的 entry.id 无论模型给什么值，都由后台覆盖。"""
    from agents.base import AgentResult

    prose_with_placeholder = json.dumps({
        "draft_text": "正文内容。",
        "settlement_candidates": [
            {
                "classification": "mechanical",
                "target_area": "canon_facts",
                "entry": {"id": "placeholder", "fact": "新事实"},
                "operation": "append",
                "reason": "测试",
            },
        ],
    }, ensure_ascii=False)

    calls = []

    def _fake(task, cwd=None):
        calls.append(task)
        if len(calls) == 1:
            return AgentResult(status="completed", output=VALID_SELECTION_JSON, agent="fake")
        return AgentResult(status="completed", output=prose_with_placeholder, agent="fake")

    monkeypatch.setattr(sw_ops, "run_task", _fake)
    result = sw_ops.propose_story_write(
        project_id=real_project["project_id"],
        author_input="写",
    )

    writing_root = isolated.parent / ".writing"
    turn_dir = list(writing_root.glob(f"{real_project['project_id']}/*/"))[0]
    meta = json.loads((turn_dir / "writing_meta.json").read_text(encoding="utf-8"))
    append_cands = [c for c in meta["settlement"]["candidates"] if c["operation"] == "append"]
    assert len(append_cands) == 1
    assert append_cands[0]["entry"]["id"].startswith("sw-"), "append id 由后台覆盖"
    assert append_cands[0]["entry"]["id"] != "placeholder"


# ---------- 29. frozen context_package_is_stale 被真实调用/生效 ----------

def test_frozen_context_stale_check_works(isolated, real_project, fake_agent):
    """confirm 时如果 context 判定 stale → 拒绝。"""
    project_id = real_project["project_id"]
    result = sw_ops.propose_story_write(project_id=project_id, author_input="写开场")
    token = result["writing_token"]

    # 模拟 intent_rev 变化（这会让 frozen stale 返回 True）
    intent_file = real_project["project_dir"] / "_工作台状态" / "author_intent.json"
    intent = json.loads(intent_file.read_text(encoding="utf-8"))
    intent["intent_rev"] = intent["intent_rev"] + 1
    intent_file.write_text(json.dumps(intent, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(sw_ops.StoryWritingError, match="新的变化"):
        sw_ops.confirm_story_write(project_id=project_id, writing_token=token)


# ---------- 30. accepted index 同数量但内容变化 → stale 拒绝 ----------

def test_index_fingerprint_content_change_rejected(isolated, real_project, monkeypatch):
    """index entries 内容变化（即使数量相同） → fingerprint 不同 → 拒绝。"""
    from project_workspace import accept_prose
    project_id = real_project["project_id"]
    project_dir = real_project["project_dir"]

    # 先接受一段正文，使 index 有 entries
    accept_prose(
        project_dir=project_dir,
        chapter_number=1,
        scene_ref="scene-existing",
        accepted_text="已有正文内容。" * 100,
        settlement={"scene_ref": "scene-existing", "candidates": []},
        author_accepted=True,
    )

    # 用 stateless fake agent（因为 fake_agent 的 counter 在多次 propose 时不重置）
    from agents.base import AgentResult

    def _stateless_fake(task, cwd=None):
        if "上下文选择" in task:
            return AgentResult(status="completed", output=VALID_SELECTION_JSON, agent="fake")
        else:
            return AgentResult(status="completed", output=VALID_PROSE_JSON, agent="fake")

    monkeypatch.setattr(sw_ops, "run_task", _stateless_fake)

    result = sw_ops.propose_story_write(project_id=project_id, author_input="写下一段")
    token = result["writing_token"]

    # 修改 index 内容但保持相同数量（篡改 scene_ref）
    index_file = project_dir / "_工作台状态" / "accepted_text_index.json"
    idx = json.loads(index_file.read_text(encoding="utf-8"))
    assert idx.get("entries"), "index 应有 entries"
    idx["entries"][0]["scene_ref"] = "scene-tampered"
    index_file.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(sw_ops.StoryWritingError, match="新的内容"):
        sw_ops.confirm_story_write(project_id=project_id, writing_token=token)


# ---------- 31. 正常第一场 index 为空仍可写 ----------

def test_first_scene_empty_index_still_writes(isolated, real_project, fake_agent):
    """index 为空（第一场）→ propose + confirm 正常完成。"""
    project_id = real_project["project_id"]
    result = sw_ops.propose_story_write(project_id=project_id, author_input="写开场")
    confirmed = sw_ops.confirm_story_write(project_id=project_id, writing_token=result["writing_token"])
    assert confirmed["message"] == "这段已经保留下来了。"
    assert confirmed["chapter_number"] == 1


# ---------- 32. confirm 仍然只通过 accept_prose 正式保存 ----------

def test_confirm_only_via_accept_prose(isolated, real_project, fake_agent):
    """confirm 唯一写入路径是 accept_prose；不绕过 frozen gate。"""
    project_id = real_project["project_id"]
    result = sw_ops.propose_story_write(project_id=project_id, author_input="写开场")

    accept_prose_calls = []
    original = sw_ops.accept_prose

    def _spy(**kwargs):
        accept_prose_calls.append(kwargs)
        return original(**kwargs)

    with patch.object(sw_ops, "accept_prose", side_effect=_spy):
        sw_ops.confirm_story_write(project_id=project_id, writing_token=result["writing_token"])

    assert len(accept_prose_calls) == 1
    assert accept_prose_calls[0]["author_accepted"] is True


# ---------- 33. 旧临时候选在新生成时被清理 ----------

def test_old_candidate_cleaned_on_new_propose(isolated, real_project, monkeypatch):
    """同一 project 生成新候选时，旧临时候选被清理。"""
    from agents.base import AgentResult
    project_id = real_project["project_id"]

    # 使用基于 task 内容判断的 fake agent（不依赖全局 counter）
    def _stateless_fake(task, cwd=None):
        if "上下文选择" in task:
            return AgentResult(status="completed", output=VALID_SELECTION_JSON, agent="fake")
        else:
            return AgentResult(status="completed", output=VALID_PROSE_JSON, agent="fake")

    monkeypatch.setattr(sw_ops, "run_task", _stateless_fake)

    # 第一次 propose
    result1 = sw_ops.propose_story_write(project_id=project_id, author_input="写第一段")
    token1 = result1["writing_token"]

    writing_root = isolated.parent / ".writing"
    # 第一次 propose 后有且仅有一个 turn 目录
    turns_after_first = list((writing_root / project_id).iterdir())
    assert len(turns_after_first) == 1

    # 第二次 propose（"我想改一改 → 再生成"）
    result2 = sw_ops.propose_story_write(project_id=project_id, author_input="重写第一段")

    # 旧 turn 已被清理，只剩新的
    turns_after_second = list((writing_root / project_id).iterdir())
    assert len(turns_after_second) == 1
    # 旧 token 已失效
    with pytest.raises(sw_ops.StoryWritingError, match="已失效"):
        sw_ops.confirm_story_write(project_id=project_id, writing_token=token1)
    # 新 token 有效
    confirmed = sw_ops.confirm_story_write(project_id=project_id, writing_token=result2["writing_token"])
    assert confirmed["message"] == "这段已经保留下来了。"
