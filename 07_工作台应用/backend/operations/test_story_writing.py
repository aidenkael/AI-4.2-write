# -*- coding: utf-8 -*-
"""正文写作"这一段想写什么"Direct 执行纵切 targeted tests。

覆盖（全部使用假 adapter + threading 事件，无真实模型/API 调用）：
A. Direct prepare 非阻塞
B. 精确内置模型路由到达两阶段
C. 精确自定义模型路由到达两阶段（无内置替换）
D. 无效 Direct 配置 → 执行前稳定失败，无回退
E. interactive_bridge → 稳定显式未接入错误，无 Direct 调用
F. 两阶段隔离：Stage1 见 State 目录；Stage2 只见编译 Context + recent prose
G. Stage1 无知识 → 检索 0 次、Context 正常编译
H. Stage1 有知识 → 全程恰好 1 次检索、精确快照绑定、Context 消费同一包
I. 包缺失/伪造 → fail closed，Stage2 不运行
J. 非法 State 选择 → frozen Context gate 拒绝，Stage2 不运行
K. context_ref 不匹配 → 拒绝
L. 重复轮询不重复执行
M. Stage1 中取消 → adapter.cancel 一次、Stage2 不启动、晚结果丢弃
N. Stage2 中取消 → adapter.cancel 一次、无候选、晚结果丢弃
O. Stage1 adapter 失败 → 无 Stage2
P. Stage2 adapter 失败 → 无候选写入
Q. 候选阶段正式项目零写入
R. confirm：后台草稿唯一、stale 拒绝、index 变化拒绝、cross-project 拒绝、
   accept_prose author_accepted=True、工作区清理
S. 忙碌边界：与 StoryPlan 共用单活跃槽
T. StoryPlan 回归（由 test_story_planning.py 全量覆盖）

真实 author acceptance → accepted_text → production Story State
必须由作者本人在工作台实际点击"保留这段"才算验证；自动化测试只验证机械胶水。
"""
import json
import os
import re
import sys
import threading
import copy
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

from agents.base import AgentRequest, AgentResult  # noqa: E402
from operations import agent_runner  # noqa: E402
from operations import author_edit  # noqa: E402
from operations import qoder_bridge as bridge  # noqa: E402
from operations import story_planning as sp_ops  # noqa: E402
from operations import story_writing as sw_ops  # noqa: E402
from config.settings import SettingsStore, AppSettings  # noqa: E402


# 合法 Agent 选择阶段输出（无知识需求：package_ref 空串）
def _selection_json(knowledge_needs=None, selected_knowledge_refs=None, package_ref="",
                    state_selections=None, assumptions=None, objective="写开场。"):
    return json.dumps({
        "semantic_interpretation": {
            "objective": objective,
            "knowledge_needs": knowledge_needs or [],
            "selected_knowledge_refs": selected_knowledge_refs or [],
            "package_ref": package_ref,
            "assumptions": assumptions if assumptions is not None else ["主角首次进入花园"],
        },
        "state_selections": state_selections if state_selections is not None else [],
        "conflicts_or_tensions": [],
    }, ensure_ascii=False)


VALID_SELECTION_JSON = _selection_json()


def _fingerprint_from_task(task: str) -> str:
    m = re.search(r"本次 Context 快照指纹[^\n]*\n([0-9a-f]{64})", task)
    return m.group(1) if m else ""


def _ready_event() -> threading.Event:
    e = threading.Event()
    e.set()
    return e


def _fake_hit(source_id, source_anchor, statement, rank=1, source_kind="reference_bkp"):
    return {
        "selection_ref": f"{source_kind}/{source_id}/{source_anchor}",
        "source_kind": source_kind,
        "source_id": source_id,
        "source_title": f"{source_id} 书",
        "maturity": "source_bound",
        "source_anchor": source_anchor,
        "source": f"{source_id}/source",
        "statement": statement,
        "scope": "scope",
        "boundary": "boundary",
        "confidence": 0.9,
        "evidence": ["证据"],
        "rank": rank,
        "relevance_reason": "相关",
    }


def _fake_package(hits):
    return type("RetrievalPackage", (), {
        "status": "OK",
        "gaps": [],
        "candidate_count": len(hits),
        "hits": [type("Hit", (), dict(h))() for h in hits],
        "to_dict": lambda self, _h=hits: {
            "status": "OK", "candidate_count": len(_h), "hits": _h, "gaps": [],
        },
    })()


class _TwoStageAdapter:
    """两阶段假 adapter：第 1 次 run = 上下文选择，第 2 次 run = 正文生成。

    gate1/gate2 可阻塞对应阶段（取消/非阻塞测试）；on_stage1/on_stage2 可注入
    自定义行为（如模拟 Agent 侧检索快照调用）。done 在 run 返回时置位。
    """

    name = "fake_storywrite_agent"

    def __init__(self, selection_json=None, prose_draft="正文内容。", settlement=None,
                 gate1=None, gate2=None, on_stage1=None, on_stage2=None, on_cancel=None):
        self.calls: list = []
        self.cancel_called = 0
        self.done = threading.Event()
        self.stage1_started = threading.Event()
        self.stage2_started = threading.Event()
        self.selection_json = selection_json if selection_json is not None else VALID_SELECTION_JSON
        self.prose_draft = prose_draft
        self.settlement = settlement
        self.gate1 = gate1 if gate1 is not None else _ready_event()
        self.gate2 = gate2 if gate2 is not None else _ready_event()
        self.on_stage1 = on_stage1
        self.on_stage2 = on_stage2
        self.on_cancel = on_cancel

    def run(self, request):
        try:
            # 记录每次调用的快照副本（同一 AgentRequest 对象会被 worker 复用）
            self.calls.append(copy.copy(request))
            if len(self.calls) == 1:
                self.stage1_started.set()
                if self.on_stage1:
                    return self.on_stage1(request)
                self.gate1.wait(10)
                return AgentResult(status="completed", output=self.selection_json, agent=self.name)
            self.stage2_started.set()
            if self.on_stage2:
                return self.on_stage2(request)
            self.gate2.wait(10)
            fp = _fingerprint_from_task(request.task)
            candidates = self.settlement if self.settlement is not None else [{
                "classification": "mechanical",
                "target_area": "canon_facts",
                "entry": {"id": "placeholder", "fact": "主角在暴雨夜第一次进入了花园。"},
                "operation": "append",
                "reason": "正文明确描述了主角进入花园",
            }]
            output = json.dumps({
                "context_ref": fp,
                "draft_text": self.prose_draft,
                "settlement_candidates": candidates,
            }, ensure_ascii=False)
            return AgentResult(status="completed", output=output, agent=self.name)
        finally:
            self.done.set()

    def cancel(self):
        self.cancel_called += 1
        if self.on_cancel is not None:
            return self.on_cancel()
        return True


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
def fake_bridge(tmp_path, monkeypatch):
    """桥文件协议根目录 → tmp（prepare 创建请求；worker 写回；get 读取）。"""
    bridge_root = tmp_path / ".bridge"
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: bridge_root)
    return bridge_root


@pytest.fixture(autouse=True)
def _fresh_exec_task_manager(monkeypatch):
    """每个测试使用独立的 Direct 任务管理器，并同时挂到 StoryWrite 与 StoryPlan。"""
    from operations import execution_tasks

    fresh = execution_tasks.ExecutionTaskManager()
    monkeypatch.setattr(sw_ops, "_exec_task_manager", fresh)
    monkeypatch.setattr(sp_ops, "_exec_task_manager", fresh)
    return fresh


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


def _sw_prepare(real_project, adapter, monkeypatch, *,
                model="native-model-1", custom_model=None, author_input="写开场"):
    """保存 Direct Settings + 挂假 adapter → prepare（立即返回）。"""
    SettingsStore().save(AppSettings(
        default_execution_mode="direct",
        interactive_agent="qoder",
        direct_agent=adapter.name,
        direct_model=model,
        direct_custom_model=custom_model,
    ))
    monkeypatch.setattr(
        agent_runner, "_build_adapter",
        lambda: (adapter, AgentRequest(task="", model=model, custom_model=custom_model)),
    )
    return sw_ops.prepare_story_write(project_id=real_project["project_id"], author_input=author_input)


def _wait_worker(request_id, timeout=5.0):
    """等待后台 worker 线程完全退出（响应已写入或已丢弃）。"""
    return sw_ops._exec_task_manager.join(request_id, timeout)


def _writing_meta(real_project, isolated) -> dict:
    root = isolated.parent / ".writing"
    metas = list(root.glob(f"{real_project['project_id']}/*/writing_meta.json"))
    assert len(metas) == 1, f"应恰好一份 writing_meta.json，实际 {len(metas)}"
    return json.loads(metas[0].read_text(encoding="utf-8"))


def test_selected_chapter_fine_outline_enters_writing_context_only(
    isolated, real_project, fake_bridge,
):
    from operations import project_model

    project_model.set_length_plan(
        real_project["project_id"], base_model_rev=0,
        chapter_targets=[
            {"title": "第一章", "chapter_number": 1, "min_words": 2000, "max_words": 3000, "task": "不应注入"},
            {"title": "第二章", "chapter_number": 2, "min_words": 2500, "max_words": 3500, "task": "只写匿名信", "synopsis": "两人第一次合作"},
        ],
    )
    SettingsStore().save(AppSettings(default_execution_mode="interactive_bridge", interactive_agent="qoder"))
    prepared = sw_ops.prepare_story_write(
        project_id=real_project["project_id"], author_input="写第二章", chapter_number=2,
    )
    request = bridge.get_request(prepared["request_id"])
    assert request is not None
    task = request["task"]
    assert '"chapter_number": 2' in task
    assert "只写匿名信" in task
    assert "两人第一次合作" in task
    assert "不应注入" not in task
    sw_ops.cancel_story_write_request(prepared["request_id"])


# ---------------------------------------------------------------------------
# A. Direct prepare 非阻塞
# ---------------------------------------------------------------------------

def test_prepare_is_non_blocking(isolated, real_project, fake_bridge, monkeypatch):
    gate1 = threading.Event()
    adapter = _TwoStageAdapter(gate1=gate1)
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    request_id = prepare_result["request_id"]

    assert prepare_result["status"] == "task_prepared"
    assert prepare_result["execution_mode"] == "direct"
    assert not gate1.is_set(), "prepare 返回时 Stage 1 必须仍在等待（非阻塞）"
    assert sw_ops.get_story_write_request(request_id=request_id)["status"] == "pending"

    gate1.set()
    assert _wait_worker(request_id), "释放后 worker 未完成"
    result = sw_ops.get_story_write_request(request_id=request_id)
    assert result["status"] == "completed", result.get("error")
    assert result["result"]["draft_text"]


# ---------------------------------------------------------------------------
# B/C. 精确内置 / 自定义模型路由到达两阶段
# ---------------------------------------------------------------------------

def test_exact_native_route_reaches_both_stages(isolated, real_project, fake_bridge, monkeypatch):
    adapter = _TwoStageAdapter()
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch, model="native-model-1", custom_model=None)
    assert _wait_worker(prepare_result["request_id"])
    assert sw_ops.get_story_write_request(prepare_result["request_id"])["status"] == "completed"
    assert len(adapter.calls) == 2, "两阶段必须各执行一次"
    for req in adapter.calls:
        assert req.model == "native-model-1"
        assert req.custom_model is None


def test_exact_custom_route_reaches_both_stages(isolated, real_project, fake_bridge, monkeypatch):
    adapter = _TwoStageAdapter()
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch, model=None, custom_model="harness:provider:model-z")
    assert _wait_worker(prepare_result["request_id"])
    assert sw_ops.get_story_write_request(prepare_result["request_id"])["status"] == "completed"
    assert len(adapter.calls) == 2
    for req in adapter.calls:
        assert req.custom_model == "harness:provider:model-z"
        assert req.model is None, "自定义路由时不得替换/同时传入内置模型"


# ---------------------------------------------------------------------------
# D. 无效 Direct 配置：执行前稳定失败，无回退
# ---------------------------------------------------------------------------

def test_invalid_direct_config_fails_before_execution(isolated, real_project, fake_bridge, monkeypatch):
    SettingsStore().save(AppSettings(
        default_execution_mode="direct", interactive_agent="qoder",
        direct_agent="fake_storywrite_agent", direct_model=None, direct_custom_model=None,
    ))
    built: list[str] = []

    def _build():
        built.append("build")
        raise agent_runner.AgentRunError("请在“设置”中选择一个内置模型或自定义模型。")

    monkeypatch.setattr(agent_runner, "_build_adapter", _build)
    with pytest.raises(sw_ops.StoryWritingError) as ei:
        sw_ops.prepare_story_write(project_id=real_project["project_id"], author_input="写开场")
    assert "直连执行配置不可用" in str(ei.value)
    assert "内置模型或自定义模型" in str(ei.value)
    assert built == ["build"], "配置校验只尝试一次即失败"
    assert not sw_ops._exec_task_manager.is_busy()


# ---------------------------------------------------------------------------
# E. interactive_bridge：两阶段交互桥（真实两次 /gowrite），绝不回退 Direct
# ---------------------------------------------------------------------------

def test_interactive_bridge_no_direct_fallback(isolated, real_project, fake_bridge, monkeypatch):
    built: list[str] = []

    def _must_not_build():
        built.append("build")
        raise AssertionError("交互模式不得调用 Direct runner")

    monkeypatch.setattr(agent_runner, "_build_adapter", _must_not_build)
    # 默认 Settings = interactive_bridge
    prepare_result = sw_ops.prepare_story_write(
        project_id=real_project["project_id"], author_input="写开场",
    )
    assert prepare_result["status"] == "task_prepared"
    assert prepare_result["execution_mode"] == "interactive_bridge"
    assert prepare_result["phase"] == "pending_selection"
    assert "等待 Qoder /gowrite" in prepare_result["message"]
    assert built == []
    assert not sw_ops._exec_task_manager.is_busy()
    # 请求已创建且带阶段标记
    request = bridge.get_request(prepare_result["request_id"])
    assert request is not None
    assert request["phase"] == "pending_selection"


# ---------------------------------------------------------------------------
# F. 两阶段隔离：Stage2 绝不含未选中 State 目录
# ---------------------------------------------------------------------------

def test_two_stage_isolation(isolated, real_project, fake_bridge, monkeypatch):
    adapter = _TwoStageAdapter()
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    assert _wait_worker(prepare_result["request_id"])
    assert len(adapter.calls) == 2
    stage1_task, stage2_task = adapter.calls[0].task, adapter.calls[1].task

    # Stage 1：包含 State 候选目录（选择用）
    assert "当前 Story State 候选条目" in stage1_task
    assert "state_selections" in stage1_task
    # Stage 2：不含未选中 State 目录；只含编译 Context + recent prose 位
    assert "当前 Story State 候选条目" not in stage2_task
    assert "Context Package" in stage2_task
    assert "本次 Context 快照指纹" in stage2_task
    assert "settlement_candidates" not in stage2_task


def test_recent_prose_only_in_stage2_when_index_has_entries(isolated, real_project, fake_bridge, monkeypatch):
    # 第一场：无 recent prose 段落
    adapter = _TwoStageAdapter()
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    assert _wait_worker(prepare_result["request_id"])
    stage2_first = adapter.calls[1].task
    assert "上一段正文" not in stage2_first

    # 已有 accepted scene → Stage 2 只含 short recent window
    from project_workspace import accept_prose
    accept_prose(
        project_dir=real_project["project_dir"],
        chapter_number=1,
        scene_ref="scene-prev",
        accepted_text="上一段正文内容。" * 100,
        settlement={"scene_ref": "scene-prev", "candidates": []},
        author_accepted=True,
    )
    adapter2 = _TwoStageAdapter()
    prepare_result2 = _sw_prepare(real_project, adapter2, monkeypatch, author_input="继续写")
    assert _wait_worker(prepare_result2["request_id"])
    stage2_second = adapter2.calls[1].task
    assert "上一段正文" in stage2_second
    assert "上一段正文内容" in stage2_second


# ---------------------------------------------------------------------------
# G. Stage1 无知识：检索 0 次、Context 正常编译
# ---------------------------------------------------------------------------

def test_stage1_no_knowledge_zero_retrieval(isolated, real_project, fake_bridge, monkeypatch):
    retrieval_calls: list[str] = []
    monkeypatch.setattr(
        sw_ops, "_retrieve_package",
        lambda q: (retrieval_calls.append(q), _fake_package([]))[1],
    )
    adapter = _TwoStageAdapter()
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    assert _wait_worker(prepare_result["request_id"])
    result = sw_ops.get_story_write_request(prepare_result["request_id"])
    assert result["status"] == "completed", result.get("error")
    assert retrieval_calls == [], "knowledge_needs=[] 时检索次数必须为 0"
    assert result["result"]["draft_text"]
    meta = _writing_meta(real_project, isolated)
    assert meta["context_fingerprint"]
    assert meta["context"]["selected_knowledge_hits"] == []


# ---------------------------------------------------------------------------
# H. Stage1 有知识：恰好 1 次检索、精确快照绑定、Context 消费同一包
# ---------------------------------------------------------------------------

def test_stage1_knowledge_exact_package_binding(isolated, real_project, fake_bridge, monkeypatch):
    package = _fake_package([
        _fake_hit("book_a", "K001", "A 卡", rank=1),
        _fake_hit("book_a", "K002", "B 卡", rank=2),
    ])
    retrieval_calls: list[str] = []
    monkeypatch.setattr(
        sw_ops, "_retrieve_package",
        lambda q: (retrieval_calls.append(q), package)[1],
    )

    def _stage1(request):
        rid = re.search(r"--request ([0-9a-f]{32})", request.task).group(1)
        shown = sw_ops.execute_request_scoped_retrieval("信息层次", rid)  # 唯一一次检索
        fp = sw_ops._package_fingerprint(shown)
        return AgentResult(status="completed", output=_selection_json(
            knowledge_needs=["信息层次"], selected_knowledge_refs=["reference_bkp/book_a/K001"], package_ref=fp,
        ), agent="fake_storywrite_agent")

    adapter = _TwoStageAdapter(on_stage1=_stage1)
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    assert _wait_worker(prepare_result["request_id"])
    result = sw_ops.get_story_write_request(prepare_result["request_id"])
    assert result["status"] == "completed", result.get("error")
    assert retrieval_calls == ["信息层次"], "全程必须恰好 1 次检索（worker/finalize 零检索）"

    meta = _writing_meta(real_project, isolated)
    context = meta["context"]
    assert [h["statement"] for h in context["selected_knowledge_hits"]] == ["A 卡"], \
        "Context 必须消费模型从该包中选择的同一批卡"

    turn_dir = list((isolated.parent / ".writing" / real_project["project_id"]).iterdir())[0]
    snapshot = json.loads((turn_dir / "retrieval" / "package.json").read_text(encoding="utf-8"))
    assert snapshot["schema"] == "gowrite_retrieval_snapshot/v2"
    assert snapshot["request_id"] == prepare_result["request_id"]
    assert snapshot["project_id"] == real_project["project_id"]
    assert snapshot["writing_turn_id"] == turn_dir.name
    assert snapshot["query"] == "信息层次"
    assert snapshot["package_fingerprint"] == sw_ops._package_fingerprint(package)


# ---------------------------------------------------------------------------
# I. 包缺失 / 伪造 → fail closed，Stage2 不运行
# ---------------------------------------------------------------------------

def test_missing_snapshot_fails_closed_no_stage2(isolated, real_project, fake_bridge, monkeypatch):
    monkeypatch.setattr(sw_ops, "_retrieve_package", lambda q: _fake_package([]))
    adapter = _TwoStageAdapter(selection_json=_selection_json(
        knowledge_needs=["信息层次"], selected_knowledge_refs=["reference_bkp/book_a/K001"], package_ref="x",
    ))
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    assert _wait_worker(prepare_result["request_id"])
    result = sw_ops.get_story_write_request(prepare_result["request_id"])
    assert result["status"] == "failed"
    assert "检索包快照缺失" in result["error"]
    assert len(adapter.calls) == 1, "快照缺失时 Stage 2 不得运行"


def test_tampered_package_ref_fails_closed_no_stage2(isolated, real_project, fake_bridge, monkeypatch):
    package = _fake_package([_fake_hit("book_a", "K001", "A 卡", rank=1)])
    monkeypatch.setattr(sw_ops, "_retrieve_package", lambda q: package)

    def _stage1(request):
        rid = re.search(r"--request ([0-9a-f]{32})", request.task).group(1)
        sw_ops.execute_request_scoped_retrieval("信息层次", rid)  # 写快照
        return AgentResult(status="completed", output=_selection_json(
            knowledge_needs=["信息层次"], selected_knowledge_refs=["reference_bkp/book_a/K001"],
            package_ref="deadbeef" * 8,  # 伪造指纹
        ), agent="fake_storywrite_agent")

    adapter = _TwoStageAdapter(on_stage1=_stage1)
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    assert _wait_worker(prepare_result["request_id"])
    result = sw_ops.get_story_write_request(prepare_result["request_id"])
    assert result["status"] == "failed"
    assert "package_ref" in result["error"] or "不一致" in result["error"]
    assert len(adapter.calls) == 1


# ---------------------------------------------------------------------------
# J. 非法 State 选择 → frozen Context gate 拒绝，Stage2 不运行
# ---------------------------------------------------------------------------

def test_invalid_state_selection_no_stage2(isolated, real_project, fake_bridge, monkeypatch):
    project_id = real_project["project_id"]
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

    adapter = _TwoStageAdapter(selection_json=_selection_json(
        state_selections=[{"area": "approved_plan", "id": f"plan-{project_id}", "reason": "测试"}],
    ))
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    assert _wait_worker(prepare_result["request_id"])
    result = sw_ops.get_story_write_request(prepare_result["request_id"])
    assert result["status"] == "failed"
    assert "Context 被拒绝" in result["error"]
    assert len(adapter.calls) == 1


# ---------------------------------------------------------------------------
# K. context_ref 不匹配 → 拒绝
# ---------------------------------------------------------------------------

def test_context_ref_mismatch_rejected(isolated, real_project, fake_bridge, monkeypatch):
    def _stage2(request):
        return AgentResult(status="completed", output=json.dumps({
            "context_ref": "0" * 64,  # 错误指纹
            "draft_text": "正文。",
            "settlement_candidates": [],
        }, ensure_ascii=False), agent="fake_storywrite_agent")

    adapter = _TwoStageAdapter(on_stage2=_stage2)
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    assert _wait_worker(prepare_result["request_id"])
    result = sw_ops.get_story_write_request(prepare_result["request_id"])
    assert result["status"] == "failed"
    assert "context_ref" in result["error"]


# ---------------------------------------------------------------------------
# L. 重复轮询不重复执行
# ---------------------------------------------------------------------------

def test_repeated_poll_no_repeat_execution(isolated, real_project, fake_bridge, monkeypatch):
    gate1 = threading.Event()
    adapter = _TwoStageAdapter(gate1=gate1)
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    for _ in range(5):
        assert sw_ops.get_story_write_request(prepare_result["request_id"])["status"] == "pending"
    assert len(adapter.calls) <= 1, "轮询不得触发额外执行"
    gate1.set()
    assert _wait_worker(prepare_result["request_id"])
    assert len(adapter.calls) == 2, "两阶段各执行一次"


# ---------------------------------------------------------------------------
# M/N. 取消（Stage1 / Stage2）
# ---------------------------------------------------------------------------

def test_cancel_during_stage1(isolated, real_project, fake_bridge, monkeypatch):
    gate1 = threading.Event()
    adapter = _TwoStageAdapter(gate1=gate1, on_cancel=lambda: (gate1.set(), True)[1])
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    assert adapter.stage1_started.wait(5), "Stage 1 未启动"
    assert sw_ops.cancel_story_write_request(prepare_result["request_id"])["status"] == "canceled"
    assert adapter.cancel_called == 1, "adapter.cancel() 必须被调用一次"
    assert adapter.done.wait(5), "worker 应已退出"
    assert len(adapter.calls) == 1, "取消后 Stage 2 不得启动"
    result = sw_ops.get_story_write_request(prepare_result["request_id"])
    assert result["status"] == "canceled"
    assert "result" not in result
    # 取消后临时 writing 工作区（turn 目录）必须清理
    project_writing = isolated.parent / ".writing" / real_project["project_id"]
    assert not project_writing.exists() or list(project_writing.iterdir()) == []


def test_cancel_during_stage2(isolated, real_project, fake_bridge, monkeypatch):
    gate2 = threading.Event()
    adapter = _TwoStageAdapter(gate2=gate2, on_cancel=lambda: (gate2.set(), True)[1])
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    assert adapter.stage2_started.wait(5), "Stage 2 未启动"
    assert sw_ops.cancel_story_write_request(prepare_result["request_id"])["status"] == "canceled"
    assert adapter.cancel_called == 1
    assert adapter.done.wait(5)
    result = sw_ops.get_story_write_request(prepare_result["request_id"])
    assert result["status"] == "canceled"
    project_writing = isolated.parent / ".writing" / real_project["project_id"]
    assert not project_writing.exists() or list(project_writing.iterdir()) == [], \
        "取消后不得残留候选"


def test_cancel_idempotent(isolated, real_project, fake_bridge, monkeypatch):
    gate1 = threading.Event()
    adapter = _TwoStageAdapter(gate1=gate1, on_cancel=lambda: (gate1.set(), True)[1])
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    assert adapter.stage1_started.wait(5)
    assert sw_ops.cancel_story_write_request(prepare_result["request_id"])["status"] == "canceled"
    assert sw_ops.cancel_story_write_request(prepare_result["request_id"])["status"] == "canceled"
    assert sw_ops.cancel_story_write_request(prepare_result["request_id"])["status"] == "canceled"
    assert adapter.cancel_called == 1, "重复取消不得重复调用 adapter.cancel()"


# ---------------------------------------------------------------------------
# O/P. 阶段失败
# ---------------------------------------------------------------------------

def test_stage1_failure_no_stage2(isolated, real_project, fake_bridge, monkeypatch):
    def _fail1(request):
        return AgentResult(status="failed", error="选择阶段失败", agent="fake_storywrite_agent")

    adapter = _TwoStageAdapter(on_stage1=_fail1)
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    assert _wait_worker(prepare_result["request_id"])
    result = sw_ops.get_story_write_request(prepare_result["request_id"])
    assert result["status"] == "failed"
    assert "选择阶段失败" in result["error"]
    assert len(adapter.calls) == 1, "Stage 1 失败时不得进入 Stage 2"


def test_stage2_failure_no_candidate(isolated, real_project, fake_bridge, monkeypatch):
    def _fail2(request):
        return AgentResult(status="failed", error="正文生成失败", agent="fake_storywrite_agent")

    adapter = _TwoStageAdapter(on_stage2=_fail2)
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    assert _wait_worker(prepare_result["request_id"])
    result = sw_ops.get_story_write_request(prepare_result["request_id"])
    assert result["status"] == "failed"
    assert "正文生成失败" in result["error"]
    assert not list((isolated.parent / ".writing" / real_project["project_id"]).glob("*/*/writing_meta.json")), \
        "Stage 2 失败不得产生候选"


# ---------------------------------------------------------------------------
# Q. 候选阶段正式项目零写入
# ---------------------------------------------------------------------------

def test_candidate_stage_no_project_write(isolated, real_project, fake_bridge, monkeypatch):
    project_dir = real_project["project_dir"]
    state_file = project_dir / "_工作台状态" / "story_state.json"
    before_state = state_file.read_text(encoding="utf-8")
    prose_dir = project_dir / "03_正文"
    before_prose = list(prose_dir.iterdir()) if prose_dir.exists() else []

    adapter = _TwoStageAdapter()
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    assert _wait_worker(prepare_result["request_id"])
    assert sw_ops.get_story_write_request(prepare_result["request_id"])["status"] == "completed"

    assert state_file.read_text(encoding="utf-8") == before_state, "候选阶段不得修改 Story State"
    after_prose = list(prose_dir.iterdir()) if prose_dir.exists() else []
    assert after_prose == before_prose, "候选阶段不得修改 03_正文"


# ---------------------------------------------------------------------------
# R. confirm：后台草稿唯一 / stale / index / cross-project / frozen gate / 清理
# ---------------------------------------------------------------------------

def _produce_candidate(real_project, isolated, fake_bridge, monkeypatch):
    adapter = _TwoStageAdapter()
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    assert _wait_worker(prepare_result["request_id"])
    result = sw_ops.get_story_write_request(prepare_result["request_id"])
    assert result["status"] == "completed", result.get("error")
    return result["result"]


def test_confirm_uses_backend_draft_only(isolated, real_project, fake_bridge, monkeypatch):
    result = _produce_candidate(real_project, isolated, fake_bridge, monkeypatch)
    confirmed = sw_ops.confirm_story_write(
        project_id=real_project["project_id"], writing_token=result["writing_token"],
    )
    assert confirmed["message"] == "这段已经保留下来了。"
    assert confirmed["scene_ref"] == result["scene_ref"]
    assert confirmed["chapter_number"] == result["chapter_number"]
    from operations import project_model
    model = project_model.load_project_model(real_project["project_id"])
    assert str(result["chapter_number"]) not in model["chapter_actual_results"]
    assert confirmed["settlement_status"] == "pending"


def test_confirm_calls_accept_prose_author_accepted(isolated, real_project, fake_bridge, monkeypatch):
    result = _produce_candidate(real_project, isolated, fake_bridge, monkeypatch)
    # confirm 成功后工作区会被清理，因此在确认前读取后台保存的 meta
    saved_meta = _writing_meta(real_project, isolated)
    original_accept = sw_ops.accept_prose
    accept_calls = []

    def _spy_accept(**kwargs):
        accept_calls.append(kwargs)
        return original_accept(**kwargs)

    with patch.object(sw_ops, "accept_prose", side_effect=_spy_accept):
        sw_ops.confirm_story_write(project_id=real_project["project_id"], writing_token=result["writing_token"])

    assert len(accept_calls) == 1
    assert accept_calls[0]["author_accepted"] is True
    assert accept_calls[0]["scene_ref"] == result["scene_ref"]
    # 后台保存的 draft 才是写入内容（前端无法替换）
    assert accept_calls[0]["accepted_text"] == saved_meta["draft_text"]


def test_confirm_no_token_rejected(isolated, real_project, fake_bridge, monkeypatch):
    with pytest.raises(sw_ops.StoryWritingError):
        sw_ops.confirm_story_write(project_id=real_project["project_id"], writing_token="")
    with pytest.raises(sw_ops.StoryWritingError):
        sw_ops.confirm_story_write(project_id=real_project["project_id"], writing_token="不存在的token")


def test_confirm_stale_state_rejected(isolated, real_project, fake_bridge, monkeypatch):
    result = _produce_candidate(real_project, isolated, fake_bridge, monkeypatch)
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["state_rev"] = state["state_rev"] + 1
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(sw_ops.StoryWritingError, match="新的变化"):
        sw_ops.confirm_story_write(project_id=real_project["project_id"], writing_token=result["writing_token"])


def test_confirm_stale_index_rejected(isolated, real_project, fake_bridge, monkeypatch):
    result = _produce_candidate(real_project, isolated, fake_bridge, monkeypatch)
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
        sw_ops.confirm_story_write(project_id=real_project["project_id"], writing_token=result["writing_token"])


def test_confirm_cross_project_token_rejected(isolated, real_project, fake_bridge, monkeypatch):
    from project_workspace import create_project
    created = create_project(name="另一作品", author_intent={
        "work_direction": "方向",
        "reader_promise": "期待",
        "hard_constraints": [],
        "open_space": [],
    })
    other_id = created["project_id"]
    result = _produce_candidate(real_project, isolated, fake_bridge, monkeypatch)
    with pytest.raises(sw_ops.StoryWritingError, match="不属于当前作品"):
        sw_ops.confirm_story_write(project_id=other_id, writing_token=result["writing_token"])


def test_confirm_workspace_cleaned(isolated, real_project, fake_bridge, monkeypatch):
    result = _produce_candidate(real_project, isolated, fake_bridge, monkeypatch)
    writing_root = isolated.parent / ".writing"
    assert (writing_root / real_project["project_id"]).exists()
    sw_ops.confirm_story_write(project_id=real_project["project_id"], writing_token=result["writing_token"])
    project_writing_dir = writing_root / real_project["project_id"]
    if project_writing_dir.exists():
        assert list(project_writing_dir.iterdir()) == []


def test_storywrite_candidate_does_not_precompute_semantic_settlement(isolated, real_project, fake_bridge, monkeypatch):
    result = _produce_candidate(real_project, isolated, fake_bridge, monkeypatch)
    meta = _writing_meta(real_project, isolated)
    assert "settlement" not in meta
    assert "semantic_result" not in meta


def test_storywrite_acceptance_enters_pending_ledger_without_semantic_apply(isolated, real_project, fake_bridge, monkeypatch):
    project_id = real_project["project_id"]
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["canon_facts"].append({
        "id": "cf.existing.1",
        "fact": "原有事实",
        "authority": "author_decision:test",
    })
    state["state_rev"] = 3
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    result = _produce_candidate(real_project, isolated, fake_bridge, monkeypatch)
    confirmed = sw_ops.confirm_story_write(project_id=project_id, writing_token=result["writing_token"])
    assert confirmed["settlement_status"] == "pending"
    ledger = author_edit.get_change_ledger(project_id)
    assert ledger["changes"][-1]["source_kind"] == "accepted_ai_prose"
    assert ledger["changes"][-1]["status"] == "pending"


def test_confirm_no_planning_generated(isolated, real_project, fake_bridge, monkeypatch):
    project_id = real_project["project_id"]
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    before = json.loads(state_file.read_text(encoding="utf-8"))
    result = _produce_candidate(real_project, isolated, fake_bridge, monkeypatch)
    sw_ops.confirm_story_write(project_id=project_id, writing_token=result["writing_token"])
    after = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(after["approved_plan"]) == len(before["approved_plan"]), "正文写作不写 planning"


# ---------------------------------------------------------------------------
# S. 忙碌边界：与 StoryPlan 共用单活跃槽
# ---------------------------------------------------------------------------

def test_busy_boundary_shared_with_storyplan(isolated, real_project, fake_bridge, monkeypatch, _fresh_exec_task_manager):
    gate1 = threading.Event()
    adapter = _TwoStageAdapter(gate1=gate1)
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    assert adapter.stage1_started.wait(5)
    assert _fresh_exec_task_manager.is_busy() is True

    # StoryPlan Direct prepare 也被拒绝（同一活跃槽）
    with pytest.raises(sp_ops.StoryPlanningError) as ei:
        sp_ops.prepare_story_plan(project_id=real_project["project_id"], author_question="再往前想")
    assert "直连规划任务正在执行" in str(ei.value)

    # StoryWrite 再次 prepare 也被拒绝
    with pytest.raises(sw_ops.StoryWritingError) as ei2:
        sw_ops.prepare_story_write(project_id=real_project["project_id"], author_input="再写一段")
    assert "直连规划任务正在执行" in str(ei2.value)

    # 第一个任务保持完好
    gate1.set()
    assert _wait_worker(prepare_result["request_id"]), "释放后 worker 未完成"
    result = sw_ops.get_story_write_request(prepare_result["request_id"])
    assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# T. StoryPlan 回归（由 test_story_planning.py 全量覆盖；此处只验证共享契约）
# ---------------------------------------------------------------------------

def test_storyplan_async_lifecycle_contract_preserved(isolated, real_project, fake_bridge, monkeypatch, _fresh_exec_task_manager):
    """StoryPlan 与 StoryWrite 共用同一任务管理器契约（单活跃槽 + join 等待）。"""
    from operations import execution_tasks
    assert isinstance(_fresh_exec_task_manager, execution_tasks.ExecutionTaskManager)
    assert sw_ops._exec_task_manager is sp_ops._exec_task_manager, "两者必须共用同一管理器实例（测试内）"


# ---------------------------------------------------------------------------
# 检索快照 CLI：StoryWrite 显式 --request 分发
# ---------------------------------------------------------------------------

def test_retrieval_cli_story_write_explicit_request(isolated, real_project, fake_bridge, monkeypatch):
    """retrieval_snapshot.py --request <id> 按 kind 分发到 StoryWrite 请求级检索。"""
    import contextlib
    import io
    import sys as _sys

    import operations.retrieval_snapshot as rs

    package = _fake_package([_fake_hit("book_a", "K001", "A 卡", rank=1)])
    monkeypatch.setattr(sw_ops, "_retrieve_package", lambda q: package)

    project_id = real_project["project_id"]
    writing_turn_id = "w-turn-1"
    request_id = bridge.create_request(
        task="task",
        kind="story_write_propose",
        meta={"project_id": project_id, "writing_turn_id": writing_turn_id},
    )
    writing_dir = sw_ops._writing_dir(project_id, writing_turn_id)
    writing_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(_sys, "argv", ["retrieval_snapshot.py", "--request", request_id, "信息层次"])
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = rs.main()
    assert rc == 0

    snapshot = json.loads((writing_dir / "retrieval" / "package.json").read_text(encoding="utf-8"))
    assert snapshot["request_id"] == request_id
    assert snapshot["project_id"] == project_id
    assert snapshot["writing_turn_id"] == writing_turn_id
    assert snapshot["query"] == "信息层次"
    assert snapshot["package_fingerprint"] in out.getvalue()


# ---------------------------------------------------------------------------
# U. 正式写作面只读模型（get_story_write_surface）
# ---------------------------------------------------------------------------

def _accept(real_project, *, chapter_number=1, scene_ref, text):
    """直接写入正式已接受正文（frozen accept_prose）。"""
    from project_workspace import accept_prose
    return accept_prose(
        project_dir=real_project["project_dir"],
        chapter_number=chapter_number,
        scene_ref=scene_ref,
        accepted_text=text,
        settlement={"scene_ref": scene_ref, "candidates": []},
        author_accepted=True,
    )


def test_surface_empty_project(isolated, real_project, fake_bridge, monkeypatch):
    """A. 空项目：chapter 1 空、total_words 0。"""
    surface = sw_ops.get_story_write_surface(project_id=real_project["project_id"])
    assert surface["project_id"] == real_project["project_id"]
    assert surface["name"] == "测试作品"
    assert surface["chapters"] == [{
        "chapter_number": 1,
        "title": "第1章",
        "content": "",
        "words": 0,
        "scene_count": 0,
        "formal_prose_exists": False,
        "stage_ref": None,
        "stage_title": None,
    }]
    assert surface["active_chapter_number"] == 1
    assert surface["total_words"] == 0


def test_surface_includes_planned_chapter_without_formal_file(isolated, real_project, fake_bridge, monkeypatch):
    from operations import project_model

    planned = project_model.set_length_plan(
        real_project["project_id"], base_model_rev=0,
        stages=[{"client_key": "vol-1", "title": "第一卷", "target_words": 50000}],
        chapter_targets=[
            {"title": "第一章", "chapter_number": 1, "min_words": 2000, "max_words": 3000, "stage_key": "vol-1"},
            {"title": "第二章", "chapter_number": 2, "min_words": 2500, "max_words": 3500, "task": "调查匿名信", "stage_key": "vol-1"},
        ],
    )
    stage_ref = planned["length_plan"]["stage_refs"][0]

    surface = sw_ops.get_story_write_surface(project_id=real_project["project_id"])
    assert [item["chapter_number"] for item in surface["chapters"]] == [1, 2]
    second = surface["chapters"][1]
    assert second["title"] == "第二章"
    assert second["formal_prose_exists"] is False
    assert "content_sha256" not in second
    assert second["fine_outline"]["task"] == "调查匿名信"
    assert second["stage_ref"] == stage_ref
    assert second["stage_title"] == "第一卷"
    assert surface["active_chapter_number"] == 1


def test_surface_active_chapter_uses_latest_formal_prose_not_future_plan(isolated, real_project, fake_bridge, monkeypatch):
    from operations import project_model

    _accept(real_project, chapter_number=1, scene_ref="scene-1", text="第一章正文。")
    project_model.set_length_plan(
        real_project["project_id"], base_model_rev=0,
        chapter_targets=[
            {"title": "第一章", "chapter_number": 1, "min_words": 2000, "max_words": 3000},
            {"title": "第二章", "chapter_number": 2, "min_words": 2500, "max_words": 3500},
        ],
    )
    surface = sw_ops.get_story_write_surface(project_id=real_project["project_id"])
    assert [item["chapter_number"] for item in surface["chapters"]] == [1, 2]
    assert surface["chapters"][1]["formal_prose_exists"] is False
    assert surface["active_chapter_number"] == 1


def test_surface_reads_formal_accepted_prose(isolated, real_project, fake_bridge, monkeypatch):
    """B. 已接受正文：正确读取正式 03_正文；chapter_number/content/words/scene_count 正确。"""
    text = "第一章正文内容。" * 20
    _accept(real_project, scene_ref="scene-a", text=text)
    surface = sw_ops.get_story_write_surface(project_id=real_project["project_id"])
    assert len(surface["chapters"]) == 1
    ch = surface["chapters"][0]
    assert ch["chapter_number"] == 1
    assert ch["title"] == "第1章"
    assert ch["content"] == text
    assert ch["words"] == len(text)
    assert ch["scene_count"] == 1
    assert surface["active_chapter_number"] == 1
    assert surface["total_words"] == len(text)


def test_surface_excludes_temp_candidate(isolated, real_project, fake_bridge, monkeypatch):
    """B2. 临时候选绝不进入正式写作面。"""
    adapter = _TwoStageAdapter(prose_draft="临时候选正文，绝不能出现在已采用面。")
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    assert _wait_worker(prepare_result["request_id"])
    result = sw_ops.get_story_write_request(prepare_result["request_id"])
    assert result["status"] == "completed", result.get("error")

    surface = sw_ops.get_story_write_surface(project_id=real_project["project_id"])
    assert surface["chapters"][0]["content"] == ""
    assert "临时候选" not in surface["chapters"][0]["content"]
    assert surface["total_words"] == 0


def test_surface_multiple_chapters_grouped_sorted(isolated, real_project, fake_bridge, monkeypatch):
    """C. 多章：按 chapter_number 分组排序；active = 最新已接受章。"""
    _accept(real_project, scene_ref="scene-1", text="第一章第一段。")
    _accept(real_project, scene_ref="scene-2", text="第一章第二段。")
    _accept(real_project, chapter_number=2, scene_ref="scene-3", text="第二章内容。")
    surface = sw_ops.get_story_write_surface(project_id=real_project["project_id"])
    assert [c["chapter_number"] for c in surface["chapters"]] == [1, 2]
    ch1, ch2 = surface["chapters"]
    assert ch1["scene_count"] == 2
    assert ch1["content"] == "第一章第一段。\n\n第一章第二段。"
    assert ch2["scene_count"] == 1
    assert ch2["content"] == "第二章内容。"
    assert surface["active_chapter_number"] == 2
    assert surface["total_words"] == ch1["words"] + ch2["words"]


def test_surface_rejects_out_of_root_chapter_path(isolated, real_project, fake_bridge, monkeypatch):
    """D. 路径安全：越界/伪造章节路径被拒绝。"""
    _accept(real_project, scene_ref="scene-1", text="正文。")
    index_file = real_project["project_dir"] / "_工作台状态" / "accepted_text_index.json"

    # 相对越界（..）
    index = json.loads(index_file.read_text(encoding="utf-8"))
    index["entries"][0]["chapter_path"] = "../../outside.md"
    index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    with pytest.raises(sw_ops.StoryWritingError):
        sw_ops.get_story_write_surface(project_id=real_project["project_id"])

    # 绝对路径
    index = json.loads(index_file.read_text(encoding="utf-8"))
    index["entries"][0]["chapter_path"] = str(real_project["project_dir"] / "outside.md")
    index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    with pytest.raises(sw_ops.StoryWritingError):
        sw_ops.get_story_write_surface(project_id=real_project["project_id"])

    # 本项目 03_正文 之外但相对合法的路径
    index = json.loads(index_file.read_text(encoding="utf-8"))
    index["entries"][0]["chapter_path"] = "01_设定与人物/人物.md"
    index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    with pytest.raises(sw_ops.StoryWritingError):
        sw_ops.get_story_write_surface(project_id=real_project["project_id"])


def test_surface_zero_write_side_effects(isolated, real_project, fake_bridge, monkeypatch):
    """E. surface 读模型零写副作用。"""
    _accept(real_project, scene_ref="scene-1", text="正文内容。")
    project_dir = real_project["project_dir"]
    tracked = [
        project_dir / "_工作台状态" / "story_state.json",
        project_dir / "_工作台状态" / "accepted_text_index.json",
        project_dir / "03_正文" / "第001章.md",
    ]
    before = {p: p.read_bytes() for p in tracked}
    before_tree = sorted(str(p.relative_to(project_dir)) for p in project_dir.rglob("*") if p.is_file())

    sw_ops.get_story_write_surface(project_id=real_project["project_id"])
    sw_ops.get_story_write_surface(project_id=real_project["project_id"])

    for p, data in before.items():
        assert p.read_bytes() == data, f"{p} 被 surface 读模型修改"
    after_tree = sorted(str(p.relative_to(project_dir)) for p in project_dir.rglob("*") if p.is_file())
    assert after_tree == before_tree, "surface 读模型不得新建/删除任何正式文件"


def test_app_api_get_story_write_surface_contract(isolated, real_project, fake_bridge, monkeypatch):
    """E2. Bridge 层 get_story_write_surface 返回合同（成功 + 稳定错误码）。"""
    from bridge.app_api import AppApi
    _accept(real_project, scene_ref="scene-api", text="桥接层正文。")
    response = AppApi().get_story_write_surface({"project_id": real_project["project_id"]})
    assert response["ok"] is True
    surface = response["data"]
    assert surface["chapters"][0]["content"] == "桥接层正文。"
    assert surface["total_words"] == len("桥接层正文。")

    bad = AppApi().get_story_write_surface({"project_id": "no-such-project"})
    assert bad["ok"] is False
    assert bad["error"]["code"] == "STORY_WRITING_ERROR"
    assert bad["data"] is None


# ---------------------------------------------------------------------------
# V. 已完成但未确认候选的丢弃（cancel 扩展）
# ---------------------------------------------------------------------------

def test_discard_completed_unconfirmed_candidate(isolated, real_project, fake_bridge, monkeypatch):
    """F. 已完成未确认候选可丢弃：工作区删除 / token 失效 / 正式 State 与正文不变 / 幂等。"""
    result = _produce_candidate(real_project, isolated, fake_bridge, monkeypatch)
    writing_root = isolated.parent / ".writing"
    project_writing = writing_root / real_project["project_id"]
    turn_dir = list(project_writing.iterdir())[0]
    assert (turn_dir / "writing_meta.json").exists()

    # 正式文件快照
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    before_state = state_file.read_text(encoding="utf-8")
    prose_dir = real_project["project_dir"] / "03_正文"
    before_prose = sorted(str(p.name) for p in prose_dir.iterdir()) if prose_dir.exists() else []

    # request_id 已持久化（get_story_write_request 完成轮询后请求文件已被清理）
    meta = json.loads((turn_dir / "writing_meta.json").read_text(encoding="utf-8"))
    assert meta.get("request_id")
    assert bridge.get_request(meta["request_id"]) is None, "完成轮询后请求文件应已清理"

    canceled = sw_ops.cancel_story_write_request(meta["request_id"])
    assert canceled["status"] == "canceled"

    # 工作区删除 → writing token 失效（confirm 拒绝）
    assert not project_writing.exists() or list(project_writing.iterdir()) == []
    with pytest.raises(sw_ops.StoryWritingError, match="已失效"):
        sw_ops.confirm_story_write(
            project_id=real_project["project_id"], writing_token=result["writing_token"],
        )

    # 正式 State / 正文不变
    assert state_file.read_text(encoding="utf-8") == before_state
    after_prose = sorted(str(p.name) for p in prose_dir.iterdir()) if prose_dir.exists() else []
    assert after_prose == before_prose

    # 幂等
    assert sw_ops.cancel_story_write_request(meta["request_id"])["status"] == "canceled"


def test_discard_unknown_request_id_idempotent(isolated, real_project, fake_bridge, monkeypatch):
    """F2. 丢弃未知 request_id：静默幂等，不影响任何正式文件。"""
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    before_state = state_file.read_text(encoding="utf-8")
    result = sw_ops.cancel_story_write_request("deadbeef" * 8)
    assert result["status"] == "canceled"
    assert state_file.read_text(encoding="utf-8") == before_state


def test_regenerate_discards_old_token_before_new_prepare(isolated, real_project, fake_bridge, monkeypatch):
    """F3. "换一种"：旧候选先丢弃（token 失效），再发起新 prepare，绝不同时存在两个有效 token。"""
    first = _produce_candidate(real_project, isolated, fake_bridge, monkeypatch)
    writing_root = isolated.parent / ".writing"
    meta_file = list((writing_root / real_project["project_id"]).rglob("writing_meta.json"))[0]
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    old_request_id = meta["request_id"]

    # 丢弃旧候选
    assert sw_ops.cancel_story_write_request(old_request_id)["status"] == "canceled"
    with pytest.raises(sw_ops.StoryWritingError, match="已失效"):
        sw_ops.confirm_story_write(
            project_id=real_project["project_id"], writing_token=first["writing_token"],
        )

    # 新 prepare 正常完成
    adapter = _TwoStageAdapter(prose_draft="换一种后的正文。")
    prepare_result = _sw_prepare(real_project, adapter, monkeypatch)
    assert _wait_worker(prepare_result["request_id"])
    second = sw_ops.get_story_write_request(prepare_result["request_id"])
    assert second["status"] == "completed", second.get("error")
    assert second["result"]["writing_token"] != first["writing_token"]

    # 旧 token 仍不可确认，新 token 可确认
    with pytest.raises(sw_ops.StoryWritingError, match="已失效"):
        sw_ops.confirm_story_write(
            project_id=real_project["project_id"], writing_token=first["writing_token"],
        )
    confirmed = sw_ops.confirm_story_write(
        project_id=real_project["project_id"], writing_token=second["result"]["writing_token"],
    )
    assert confirmed["message"] == "这段已经保留下来了。"
