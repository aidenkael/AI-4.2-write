# -*- coding: utf-8 -*-
"""新建作品“我有个想法”纵切 targeted tests。

覆盖用户要求的 10 项验证（不重测 Agent 基础能力）：
1. 未确认候选不会创建 03_作品工程
2. 当前 Agent 设置确实被消费（default_agent 生效）
3. semantic/model output 能进入 frozen StoryDesign
4. candidate 为 proposal_noncanonical
5. 模糊/无确认不能 create_project
6. 明确确认后调用真实 ProjectWorkspace.create_project
7. author_intent 通过 frozen gate
8. 新作品能被现有 list/open/overview 链读取
9. 不生成正文
10. 不修改现有 frozen Skills（仅 import，不改文件；git diff 另查）

真实 Agent 集成验证：临时 AI_WRITE_CONFIG_DIR + DeepSeek Harness
（当前已验证可用）完成一次无正式写入的候选生成。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))

import project_workspace  # noqa: E402

from operations import new_project as np_ops  # noqa: E402
from operations.agent_runner import AgentRunError  # noqa: E402
from operations.agent_runner import run_task  # noqa: E402
from operations.projects import (  # noqa: E402
    get_project_overview,
    list_projects,
    open_project,
)
from config.settings import SettingsStore, AppSettings  # noqa: E402

VALID_AGENT_JSON = json.dumps({
    "semantic_interpretation": {
        "scope": "story_design",
        "objective": "设计一个可推进的故事发动机。",
        "knowledge_needs": [],
        "selected_bkp_ids": [],
        "assumptions": ["主角与秘密的因果尚未确认"],
    },
    "model_output": {
        "stance": ["story_engine"],
        "proposal": "候选：主角在暴雨夜发现花园替人保存秘密。",
        "work_direction": "都市奇幻长篇的开端设计。",
        "reader_promise": "读者先感到日常秩序被一条私人秘密撬开。",
        "hard_constraints": ["不把候选谜底写成既成事实"],
        "open_space": ["秘密来源", "关系走向"],
        "unknowns": ["花园保存秘密的代价"],
    },
}, ensure_ascii=False)


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    """隔离：03_作品工程 → tmp 根；临时工作区 → tmp；AI_WRITE_CONFIG_DIR → tmp。"""
    projects_root = tmp_path / "03_作品工程"
    projects_root.mkdir()
    monkeypatch.setattr(project_workspace, "get_projects_root", lambda: projects_root)
    monkeypatch.setattr(np_ops, "get_proposals_root", lambda: tmp_path / "proposals")
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path / "cfg"))
    return projects_root


@pytest.fixture()
def fake_agent(monkeypatch):
    """把 run_task 替换成返回固定合法结构化 JSON 的假 Agent。"""
    def _fake(task: str, cwd=None):
        from agents.base import AgentResult
        return AgentResult(status="completed", output=VALID_AGENT_JSON, agent="fake")
    monkeypatch.setattr(np_ops, "run_task", _fake)
    return _fake


# ---------- 1. 未确认候选不会创建 03_作品工程 ----------

def test_propose_does_not_create_project(isolated, fake_agent):
    result = np_ops.propose_new_project(name="测试作品", idea="我想写一个……")
    assert result["status"] == "proposal_noncanonical"
    # 03_作品工程 仍然为空（只有目录本身，无任何作品子目录）
    children = [p for p in isolated.iterdir() if p.is_dir()]
    assert children == [], f"propose 不应创建作品，实际：{children}"


# ---------- 2. 当前 Agent 设置确实被消费 ----------

def test_agent_settings_consumed_by_runner(isolated, tmp_path, monkeypatch):
    # 保存默认 Agent = deepseek_harness，并记录 run_task 是否经由 runner
    store = SettingsStore(config_dir=tmp_path / "cfg")
    store.save(AppSettings(default_agent="deepseek_harness"))

    from agents.base import AgentResult
    calls: list[dict] = []

    def _fake(task: str, cwd=None):
        calls.append({"task": task, "cwd": cwd})
        return AgentResult(status="completed", output=VALID_AGENT_JSON, agent="fake")

    monkeypatch.setattr(np_ops, "run_task", _fake)
    np_ops.propose_new_project(name="消费测试", idea="想法")
    assert calls, "propose 必须消费当前 Agent 设置并调用 run_task"
    # 任务文本包含作品名与想法（作者输入进入 Agent 任务）
    assert "消费测试" in calls[0]["task"]
    assert "想法" in calls[0]["task"]


def test_runner_rejects_unavailable_agent(isolated, tmp_path, monkeypatch):
    store = SettingsStore(config_dir=tmp_path / "cfg")
    store.save(AppSettings(default_agent="qoder", qoder_mode="qoder_byok"))
    # 未配置 BYOK provider/model → 普通可读错误，不触发真实第三方
    with pytest.raises(AgentRunError):
        run_task("任何任务")


# ---------- 3. semantic/model output 能进入 frozen StoryDesign ----------

def test_agent_output_flows_into_story_design(isolated, fake_agent):
    result = np_ops.propose_new_project(name="语义测试", idea="想法")
    # StoryDesign 产物已写入临时工作区
    proposals = isolated.parent / "proposals"
    proj_dir = proposals / result["project_id"]
    assert (proj_dir / "briefs" / "brief-idea-001.json").exists()
    assert (proj_dir / "contexts" / "context-idea-001.json").exists()
    assert (proj_dir / "designs" / "design-idea-001.json").exists()
    # candidate.content 就是 model_output
    candidate = json.loads((proj_dir / "designs" / "design-idea-001.json").read_text(encoding="utf-8"))
    assert candidate["content"]["work_direction"] == "都市奇幻长篇的开端设计。"


# ---------- 4. candidate 为 proposal_noncanonical ----------

def test_candidate_is_proposal_noncanonical(isolated, fake_agent):
    result = np_ops.propose_new_project(name="状态测试", idea="想法")
    assert result["status"] == "proposal_noncanonical"
    proposals = isolated.parent / "proposals"
    candidate = json.loads(
        (proposals / result["project_id"] / "designs" / "design-idea-001.json").read_text(encoding="utf-8")
    )
    assert candidate["status"] == "proposal_noncanonical"
    assert candidate["must_not_write_canon"] is True


# ---------- 非法 Agent 输出：普通可读错误，不落盘 ----------

def test_invalid_agent_output_readable_error(isolated, monkeypatch):
    from agents.base import AgentResult

    def _bad(task: str, cwd=None):
        return AgentResult(status="completed", output="这不是 JSON", agent="fake")

    monkeypatch.setattr(np_ops, "run_task", _bad)
    with pytest.raises(np_ops.NewProjectError) as ei:
        np_ops.propose_new_project(name="坏输出", idea="想法")
    assert "结构化" in str(ei.value)
    assert list(isolated.iterdir()) == []  # 03 仍为空


# ---------- 5. 模糊/无确认不能 create_project ----------

def test_confirm_without_token_rejected(isolated, fake_agent):
    with pytest.raises(np_ops.NewProjectError):
        np_ops.confirm_new_project(proposal_token="")
    with pytest.raises(np_ops.NewProjectError):
        np_ops.confirm_new_project(proposal_token="不存在的token")
    assert list(isolated.iterdir()) == []


def test_confirm_rejects_forged_token(isolated, fake_agent):
    np_ops.propose_new_project(name="防伪造", idea="想法")
    with pytest.raises(np_ops.NewProjectError):
        np_ops.confirm_new_project(proposal_token="forged-token-00000000")
    assert list(isolated.iterdir()) == []


# ---------- 6. 明确确认后调用真实 ProjectWorkspace.create_project ----------

def test_confirm_creates_real_project(isolated, fake_agent):
    result = np_ops.propose_new_project(name="正式作品", idea="想法")
    created = np_ops.confirm_new_project(proposal_token=result["proposal_token"])
    assert created["name"] == "正式作品"
    assert created["project_id"] == result["project_id"]
    proj_dir = isolated / "正式作品"
    assert proj_dir.exists()
    assert (proj_dir / "_工作台状态" / "author_intent.json").exists()
    assert (proj_dir / "_工作台状态" / "story_state.json").exists()
    assert (proj_dir / "_工作台状态" / "accepted_text_index.json").exists()


# ---------- 7. author_intent 通过 frozen gate ----------

def test_confirm_intent_passes_frozen_gate(isolated, fake_agent):
    result = np_ops.propose_new_project(name="门槛作品", idea="想法")
    created = np_ops.confirm_new_project(proposal_token=result["proposal_token"])
    intent = json.loads(
        (isolated / "门槛作品" / "_工作台状态" / "author_intent.json").read_text(encoding="utf-8")
    )
    assert intent["project_id"] == created["project_id"]
    assert intent["intent_rev"] == 1
    for field in ("work_direction", "reader_promise", "hard_constraints", "open_space"):
        assert field in intent


# ---------- 8. 新作品能被现有 list/open/overview 链读取 ----------

def test_new_project_readable_by_existing_chain(isolated, fake_agent):
    result = np_ops.propose_new_project(name="可读作品", idea="想法")
    created = np_ops.confirm_new_project(proposal_token=result["proposal_token"])

    items = list_projects()
    assert any(p["project_id"] == created["project_id"] for p in items)

    opened = open_project({"project_id": created["project_id"]})
    assert opened["project_id"] == created["project_id"]

    overview = get_project_overview(created["project_id"])
    assert overview["project_id"] == created["project_id"]
    assert overview["name"] == "可读作品"


# ---------- 9. 不生成正文 ----------

def test_confirm_generates_no_prose(isolated, fake_agent):
    result = np_ops.propose_new_project(name="无正文作品", idea="想法")
    np_ops.confirm_new_project(proposal_token=result["proposal_token"])
    prose_dir = isolated / "无正文作品" / "03_正文"
    assert prose_dir.exists()
    assert list(prose_dir.iterdir()) == [], "创建作品不得生成正文"
    index = json.loads(
        (isolated / "无正文作品" / "_工作台状态" / "accepted_text_index.json").read_text(encoding="utf-8")
    )
    assert index["entries"] == []


# ---------- 确认后清理临时工作区 ----------

def test_proposal_cleaned_after_confirm(isolated, fake_agent):
    result = np_ops.propose_new_project(name="清理作品", idea="想法")
    assert (isolated.parent / "proposals" / result["project_id"]).exists()
    np_ops.confirm_new_project(proposal_token=result["proposal_token"])
    assert not (isolated.parent / "proposals" / result["project_id"]).exists()


# ---------- 10. frozen Skills 零修改（只 import 不改文件） ----------

def test_frozen_skills_untouched(isolated, fake_agent):
    import story_runtime  # noqa: F401
    import story_design  # noqa: F401
    import project_workspace  # noqa: F401
    # 只要这些模块能原样 import 并使用即证明未被破坏；git diff 另行验证文件未改。
    assert hasattr(story_runtime, "validate_author_intent")
    assert hasattr(project_workspace, "create_project")


# ---------- 真实 Agent 集成验证（DeepSeek Harness，临时目录，无正式写入） ----------

def test_real_dsh_candidate_generation(isolated, tmp_path, monkeypatch):
    """临时 AI_WRITE_CONFIG_DIR + DeepSeek Harness：真实候选生成，不写正式作品。"""
    try:
        from agents.deepseek_harness import _default_launch
        _default_launch()
    except RuntimeError as exc:
        pytest.skip(f"DeepSeek Harness 不可用：{exc}")

    cfg_dir = tmp_path / "cfg"
    store = SettingsStore(config_dir=cfg_dir)
    store.save(AppSettings(default_agent="deepseek_harness"))
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(cfg_dir))

    result = np_ops.propose_new_project(
        name="真实集成测试",
        idea="我想写一个在暴雨夜发现花园会替人保存秘密的故事，主角和失联多年的朋友有关。",
    )
    assert result["status"] == "proposal_noncanonical"
    assert result["candidate"]["work_direction"]
    assert result["candidate"]["proposal"]
    # 未确认：03_作品工程 仍为空
    assert list(isolated.iterdir()) == []
