# -*- coding: utf-8 -*-
"""正文写作交互桥（Interactive two-phase /gowrite）targeted tests。

覆盖（全部文件协议 + 假 adapter，无真实模型/API 调用）：
A. prepare 两阶段请求生命周期：phase=pending_selection，无 Direct runner
B. Stage 1 → 精确 Context 编译 → Stage 2（两次 /gowrite 响应）→ 候选
C. Stage 2 任务只含编译 Context + recent prose，绝不含未选中 State 目录
D. 阶段 1 取消
E. 阶段 2 取消
F. 晚到阶段响应丢弃（不推进、不失败、不产生候选）
G. no-needs 检索 = 0；needs 检索 = 恰好 1 次、同包、无重复检索
H. context_ref 不匹配 → 拒绝
I. request_id 不匹配响应 → 丢弃
J. 候选阶段正式项目零写入；confirm 同 Direct 语义
"""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "StoryWrite"))

import project_workspace  # noqa: E402

from agents.base import AgentRequest  # noqa: E402
from operations import agent_runner  # noqa: E402
from operations import qoder_bridge as bridge  # noqa: E402
from operations import story_planning as sp_ops  # noqa: E402
from operations import story_writing as sw_ops  # noqa: E402
from config.settings import SettingsStore, AppSettings  # noqa: E402


def _selection_json(knowledge_needs=None, selected_knowledge_refs=None, package_ref="", state_selections=None):
    return json.dumps({
        "semantic_interpretation": {
            "objective": "写开场。",
            "knowledge_needs": knowledge_needs or [],
            "selected_knowledge_refs": selected_knowledge_refs or [],
            "package_ref": package_ref,
            "assumptions": ["主角首次进入花园"],
        },
        "state_selections": state_selections if state_selections is not None else [],
        "conflicts_or_tensions": [],
    }, ensure_ascii=False)


def _fake_hit(source_id, source_anchor, statement, rank=1, source_kind="reference_bkp"):
    return {
        "selection_ref": f"{source_kind}/{source_id}/{source_anchor}",
        "source_kind": source_kind, "source_id": source_id, "source_title": f"{source_id} 书",
        "maturity": "source_bound",
        "source_anchor": source_anchor,
        "source": f"{source_id}/source", "statement": statement, "scope": "scope",
        "boundary": "boundary", "confidence": 0.9, "evidence": ["证据"], "rank": rank,
        "relevance_reason": "相关",
    }


def _fake_package(hits):
    return type("RetrievalPackage", (), {
        "status": "OK", "gaps": [], "candidate_count": len(hits),
        "hits": [type("Hit", (), dict(h))() for h in hits],
        "to_dict": lambda self, _h=hits: {"status": "OK", "candidate_count": len(_h), "hits": _h, "gaps": []},
    })()


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    projects_root = tmp_path / "03_作品工程"
    projects_root.mkdir()
    monkeypatch.setattr(project_workspace, "get_projects_root", lambda: projects_root)
    monkeypatch.setattr(sw_ops, "get_writing_root", lambda: tmp_path / ".writing")
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path / "cfg"))
    return projects_root


@pytest.fixture()
def fake_bridge(tmp_path, monkeypatch):
    bridge_root = tmp_path / ".bridge"
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: bridge_root)
    return bridge_root


@pytest.fixture(autouse=True)
def _fresh_exec_task_manager(monkeypatch):
    from operations import execution_tasks
    fresh = execution_tasks.ExecutionTaskManager()
    monkeypatch.setattr(sw_ops, "_exec_task_manager", fresh)
    monkeypatch.setattr(sp_ops, "_exec_task_manager", fresh)
    return fresh


@pytest.fixture()
def real_project(isolated):
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
        "id": f"plan-{project_id}", "description": "故事发动机：主角在暴雨夜发现花园替人保存秘密。",
        "target_ref": f"design-{project_id}", "authority": f"author_decision:decision-{project_id}",
        "occurred": False, "kind": "confirmed_direction",
    })
    state["state_rev"] = 2
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"project_id": project_id, "name": "测试作品", "project_dir": project_dir}


def _interactive_prepare(real_project, monkeypatch):
    """默认 Settings = interactive_bridge；agent_runner 必须不被调用。"""
    built: list[str] = []

    def _must_not_build():
        built.append("build")
        raise AssertionError("交互模式不得调用 Direct runner")

    monkeypatch.setattr(agent_runner, "_build_adapter", _must_not_build)
    prepared = sw_ops.prepare_story_write(
        project_id=real_project["project_id"], author_input="写开场",
    )
    assert built == []
    return prepared


def _write_qoder_response(request_id, output):
    """模拟 Qoder /gowrite 写回：输出 = 模型原始文本（output 字段）。"""
    resp = bridge.response_path(request_id)
    resp.parent.mkdir(parents=True, exist_ok=True)
    resp.write_text(json.dumps({
        "schema": "gowrite_response/v1", "request_id": request_id,
        "status": "completed", "result": None, "output": output, "error": None,
    }, ensure_ascii=False), encoding="utf-8")


def _write_qoder_structured_response(request_id, result):
    """模拟 Qoder /gowrite 写回：输出 = 结构化 result 对象（新契约）。"""
    resp = bridge.response_path(request_id)
    resp.parent.mkdir(parents=True, exist_ok=True)
    resp.write_text(json.dumps({
        "schema": "gowrite_response/v1", "request_id": request_id,
        "status": "completed", "result": result, "output": None, "error": None,
    }, ensure_ascii=False), encoding="utf-8")


def _write_qoder_dict_output_response(request_id, output_dict):
    """写入旧畸形契约：output 里放对象（必须被桥拒绝，不得出现 dict.strip 异常）。"""
    resp = bridge.response_path(request_id)
    resp.parent.mkdir(parents=True, exist_ok=True)
    resp.write_text(json.dumps({
        "schema": "gowrite_response/v1", "request_id": request_id,
        "status": "completed", "result": None, "output": output_dict, "error": None,
    }, ensure_ascii=False), encoding="utf-8")


def _stage2_fingerprint(request_id) -> str:
    """从请求文件（已换成 Stage 2 任务）提取 Context 指纹。"""
    request = bridge.get_request(request_id)
    m = re.search(r"本次 Context 快照指纹[^\n]*\n([0-9a-f]{64})", request["task"])
    assert m, "Stage 2 任务必须包含编译 Context 指纹"
    return m.group(1)


def _prose_output(request_id, draft="正文内容。", context_ref=None):
    fp = context_ref or _stage2_fingerprint(request_id)
    return json.dumps({
        "context_ref": fp, "draft_text": draft,
        "settlement_candidates": [{
            "classification": "mechanical", "target_area": "canon_facts",
            "entry": {"id": "placeholder", "fact": "主角在暴雨夜第一次进入了花园。"},
            "operation": "append", "reason": "正文明确描述了主角进入花园",
        }],
    }, ensure_ascii=False)


def _writing_meta(real_project, isolated) -> dict:
    root = isolated.parent / ".writing"
    metas = list(root.glob(f"{real_project['project_id']}/*/writing_meta.json"))
    assert len(metas) == 1, f"应恰好一份 writing_meta.json，实际 {len(metas)}"
    return json.loads(metas[0].read_text(encoding="utf-8"))


def _complete_two_phase(real_project, monkeypatch, selection=None):
    """两阶段完整跑通：prepare → Stage1 响应 → pending_prose → Stage2 响应 → completed。"""
    prepared = _interactive_prepare(real_project, monkeypatch)
    rid = prepared["request_id"]

    # 阶段 1：无响应 → pending_selection
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_selection"
    assert "正在选择本次写作上下文" in got["message"]

    _write_qoder_response(rid, selection or _selection_json())
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_prose", got
    assert "再次执行 /gowrite" in got["message"]
    # 请求文件已换成 Stage 2 任务
    request = bridge.get_request(rid)
    assert "当前 Story State 候选条目" not in request["task"]
    assert "Context Package" in request["task"]

    # 阶段 2：无响应 → pending_prose
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_prose"

    _write_qoder_response(rid, _prose_output(rid))
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "completed", got.get("error")
    return got["result"]


# ---------------------------------------------------------------------------
# A. prepare 两阶段请求生命周期
# ---------------------------------------------------------------------------

def test_stage1_accepts_structured_result(isolated, real_project, fake_bridge, monkeypatch):
    """Stage 1 验收：结构化 result 对象（新契约）与文本 output 等效。"""
    prepared = _interactive_prepare(real_project, monkeypatch)
    rid = prepared["request_id"]
    _write_qoder_structured_response(rid, json.loads(_selection_json()))
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_prose", got.get("error")
    # 请求文件已换成 Stage 2 任务
    request = bridge.get_request(rid)
    assert "Context Package" in request["task"]


def test_stage2_accepts_structured_result(isolated, real_project, fake_bridge, monkeypatch):
    """Stage 2 验收：正文生成结果以结构化 result 对象返回。"""
    prepared = _interactive_prepare(real_project, monkeypatch)
    rid = prepared["request_id"]
    _write_qoder_response(rid, _selection_json())
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_prose", got.get("error")
    _write_qoder_structured_response(rid, json.loads(_prose_output(rid)))
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "completed", got.get("error")
    assert got["result"]["draft_text"]


def test_stage1_dict_output_rejected_as_bridge_protocol_error(isolated, real_project, fake_bridge, monkeypatch):
    """旧畸形契约（output 为对象）→ 桥失败信封 → 稳定 failed，绝不出现 dict.strip 异常。"""
    prepared = _interactive_prepare(real_project, monkeypatch)
    rid = prepared["request_id"]
    _write_qoder_dict_output_response(rid, {"semantic_interpretation": {"objective": "x"}})
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "failed"
    assert isinstance(got["error"], str) and "output" in got["error"]


def test_interactive_prepare_creates_two_phase_request(isolated, real_project, fake_bridge, monkeypatch):
    prepared = _interactive_prepare(real_project, monkeypatch)
    rid = prepared["request_id"]
    request = bridge.get_request(rid)
    assert request["phase"] == "pending_selection"
    assert request["kind"] == "story_write_propose"
    assert request["state"] == "pending"
    # 阶段 1 任务含 State 候选目录（选择用）
    assert "当前 Story State 候选条目" in request["task"]
    # ctx 快照已持久化（供阶段验收）
    writing_dir = sw_ops._writing_dir(
        real_project["project_id"],
        (request.get("meta") or {}).get("writing_turn_id"),
    )
    assert (writing_dir / "ctx.json").exists()
    # 无 Direct 忙碌占用
    assert not sw_ops._exec_task_manager.is_busy()


# ---------------------------------------------------------------------------
# B/C. 两阶段完整流程 + Stage 2 隔离
# ---------------------------------------------------------------------------

def test_two_phase_full_flow_produces_candidate(isolated, real_project, fake_bridge, monkeypatch):
    result = _complete_two_phase(real_project, monkeypatch)
    assert result["draft_text"] == "正文内容。"
    assert result["writing_token"]
    assert result["project_id"] == real_project["project_id"]
    assert result["execution"]["execution_mode"] == "interactive_bridge"
    # 候选已持久化（confirm 可读取）
    meta = _writing_meta(real_project, isolated)
    assert meta["draft_text"] == "正文内容。"
    assert meta["context_fingerprint"]


def test_stage2_task_contains_only_compiled_context(isolated, real_project, fake_bridge, monkeypatch):
    prepared = _interactive_prepare(real_project, monkeypatch)
    rid = prepared["request_id"]
    _write_qoder_response(rid, _selection_json())
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_prose"
    stage2_task = bridge.get_request(rid)["task"]
    # Stage 2 只含编译 Context + recent prose 位，绝不含未选中 State 目录
    assert "当前 Story State 候选条目" not in stage2_task
    assert "state_selections" not in stage2_task
    assert "Context Package" in stage2_task
    assert "本次 Context 快照指纹" in stage2_task
    assert "settlement_candidates" not in stage2_task


def test_stage1_knowledge_exact_package_single_retrieval(isolated, real_project, fake_bridge, monkeypatch):
    package = _fake_package([_fake_hit("book_a", "K001", "A 卡", rank=1)])
    retrieval_calls: list[str] = []
    monkeypatch.setattr(sw_ops, "_retrieve_package", lambda q: (retrieval_calls.append(q), package)[1])

    def _stage1_with_retrieval(request):
        # 模拟 Agent 在 /gowrite 执行内运行唯一一次确定性检索（写快照 + 返回包）
        rid = request["request_id"]
        shown = sw_ops.execute_request_scoped_retrieval("信息层次", rid)
        fp = sw_ops._package_fingerprint(shown)
        return _selection_json(
            knowledge_needs=["信息层次"], selected_knowledge_refs=["reference_bkp/book_a/K001"], package_ref=fp,
        )

    prepared = _interactive_prepare(real_project, monkeypatch)
    rid = prepared["request_id"]
    _write_qoder_response(rid, _stage1_with_retrieval(bridge.get_request(rid)))
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_prose", got.get("error")
    assert retrieval_calls == ["信息层次"], "全程必须恰好 1 次检索（finalize 零检索）"

    _write_qoder_response(rid, _prose_output(rid))
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "completed", got.get("error")
    assert retrieval_calls == ["信息层次"], "Stage 2 / finalize 绝不再次检索"
    meta = _writing_meta(real_project, isolated)
    assert [h["statement"] for h in meta["context"]["selected_knowledge_hits"]] == ["A 卡"]


def test_stage1_no_knowledge_zero_retrieval(isolated, real_project, fake_bridge, monkeypatch):
    retrieval_calls: list[str] = []
    monkeypatch.setattr(sw_ops, "_retrieve_package", lambda q: (retrieval_calls.append(q), _fake_package([]))[1])
    prepared = _interactive_prepare(real_project, monkeypatch)
    rid = prepared["request_id"]
    _write_qoder_response(rid, _selection_json())
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_prose", got.get("error")
    _write_qoder_response(rid, _prose_output(rid))
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "completed", got.get("error")
    assert retrieval_calls == [], "knowledge_needs=[] 时检索次数必须为 0"
    meta = _writing_meta(real_project, isolated)
    assert meta["context"]["selected_knowledge_hits"] == []


# ---------------------------------------------------------------------------
# D/E. 取消（阶段 1 / 阶段 2）
# ---------------------------------------------------------------------------

def test_cancel_in_phase1(isolated, real_project, fake_bridge, monkeypatch):
    prepared = _interactive_prepare(real_project, monkeypatch)
    rid = prepared["request_id"]
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_selection"

    canceled = sw_ops.cancel_story_write_request(rid)
    assert canceled["status"] == "canceled"
    # 晚到阶段 1 响应不得推进
    _write_qoder_response(rid, _selection_json())
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "canceled"
    # 临时工作区已清理
    project_writing = isolated.parent / ".writing" / real_project["project_id"]
    assert not project_writing.exists() or list(project_writing.iterdir()) == []


def test_cancel_in_phase2(isolated, real_project, fake_bridge, monkeypatch):
    prepared = _interactive_prepare(real_project, monkeypatch)
    rid = prepared["request_id"]
    _write_qoder_response(rid, _selection_json())
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_prose"

    canceled = sw_ops.cancel_story_write_request(rid)
    assert canceled["status"] == "canceled"
    _write_qoder_response(rid, _prose_output(rid))
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "canceled"
    assert "writing_meta.json" not in [p.name for p in (isolated.parent / ".writing" / real_project["project_id"]).rglob("*") if p.is_file()] if (isolated.parent / ".writing" / real_project["project_id"]).exists() else True


# ---------------------------------------------------------------------------
# F. 晚到/重复响应丢弃
# ---------------------------------------------------------------------------

def test_late_stage1_response_discarded_after_transition(isolated, real_project, fake_bridge, monkeypatch):
    prepared = _interactive_prepare(real_project, monkeypatch)
    rid = prepared["request_id"]
    _write_qoder_response(rid, _selection_json())
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_prose"

    # 阶段切换后再次出现第一阶段形状的响应 → 丢弃，仍停留在 pending_prose
    _write_qoder_response(rid, _selection_json())
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_prose"
    assert "再次执行 /gowrite" in got["message"]

    # 正确的 Stage 2 响应仍可完成
    _write_qoder_response(rid, _prose_output(rid))
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "completed", got.get("error")


def test_request_id_mismatch_response_discarded(isolated, real_project, fake_bridge, monkeypatch):
    prepared = _interactive_prepare(real_project, monkeypatch)
    rid = prepared["request_id"]
    resp = bridge.response_path(rid)
    resp.parent.mkdir(parents=True, exist_ok=True)
    resp.write_text(json.dumps({
        "schema": "gowrite_response/v1", "request_id": "other-id",
        "status": "completed", "result": None, "output": _selection_json(), "error": None,
    }, ensure_ascii=False), encoding="utf-8")
    got = sw_ops.get_story_write_request(rid)
    # 请求 id 不匹配响应由桥边界直接转成稳定失败信封（request_id 恢复为请求 id），
    # 绝不把其它请求内容当作本任务的有效载荷解析。
    assert got["status"] == "failed"
    assert "request_id" in got.get("error", "")
    assert bridge.get_request(rid) is None  # 终态清理


# ---------------------------------------------------------------------------
# H. context_ref 不匹配拒绝
# ---------------------------------------------------------------------------

def test_context_ref_mismatch_rejected(isolated, real_project, fake_bridge, monkeypatch):
    prepared = _interactive_prepare(real_project, monkeypatch)
    rid = prepared["request_id"]
    _write_qoder_response(rid, _selection_json())
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_prose"

    _write_qoder_response(rid, _prose_output(rid, context_ref="0" * 64))
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "failed"
    assert "context_ref" in got["error"]
    assert not list((isolated.parent / ".writing" / real_project["project_id"]).glob("*/*/writing_meta.json")), \
        "失败不得产生候选"


# ---------------------------------------------------------------------------
# I/J. 候选阶段零写入 + confirm 语义
# ---------------------------------------------------------------------------

def test_candidate_stage_no_project_write(isolated, real_project, fake_bridge, monkeypatch):
    project_dir = real_project["project_dir"]
    state_file = project_dir / "_工作台状态" / "story_state.json"
    before_state = state_file.read_text(encoding="utf-8")
    prose_dir = project_dir / "03_正文"
    before_prose = list(prose_dir.iterdir()) if prose_dir.exists() else []

    result = _complete_two_phase(real_project, monkeypatch)
    assert result["draft_text"]

    assert state_file.read_text(encoding="utf-8") == before_state, "候选阶段不得修改 Story State"
    after_prose = list(prose_dir.iterdir()) if prose_dir.exists() else []
    assert after_prose == before_prose, "候选阶段不得修改 03_正文"


def test_confirm_uses_backend_draft_only(isolated, real_project, fake_bridge, monkeypatch):
    result = _complete_two_phase(real_project, monkeypatch)
    confirmed = sw_ops.confirm_story_write(
        project_id=real_project["project_id"], writing_token=result["writing_token"],
    )
    assert confirmed["message"] == "这段已经保留下来了。"
    assert confirmed["scene_ref"] == result["scene_ref"]


def test_confirm_cross_project_rejected(isolated, real_project, fake_bridge, monkeypatch):
    from project_workspace import create_project
    created = create_project(name="另一作品", author_intent={
        "work_direction": "方向", "reader_promise": "期待", "hard_constraints": [], "open_space": [],
    })
    result = _complete_two_phase(real_project, monkeypatch)
    with pytest.raises(sw_ops.StoryWritingError, match="不属于当前作品"):
        sw_ops.confirm_story_write(project_id=created["project_id"], writing_token=result["writing_token"])


# ---------------------------------------------------------------------------
# K. 两阶段 active 指针保持（/gowrite 激活与请求存储分离后的关键不变量）
# ---------------------------------------------------------------------------

def test_two_phase_keeps_same_active_request(isolated, real_project, fake_bridge, monkeypatch):
    """交互桥两阶段：active.json 全程指向同一请求，绝不因阶段切换改变/丢失。"""
    prepared = _interactive_prepare(real_project, monkeypatch)
    rid = prepared["request_id"]
    assert bridge.get_active_request_id() == rid, "prepare 后 active 精确指向该请求"

    _write_qoder_response(rid, _selection_json())
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_prose"
    assert bridge.get_active_request_id() == rid, "Stage 1 → Stage 2 必须保持同一 active 请求"

    _write_qoder_response(rid, _prose_output(rid))
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "completed", got.get("error")
    # 候选完成 = 请求终态清理：active 指针不再指向已完成任务
    assert bridge.get_active_request_id() is None


def test_second_interactive_write_busy_until_cancel(isolated, real_project, fake_bridge, monkeypatch):
    """第二个 Interactive StoryWrite 在第一个 pending 时被拒绝（绝不覆盖 active）。"""
    prepared = _interactive_prepare(real_project, monkeypatch)
    rid = prepared["request_id"]
    with pytest.raises(sw_ops.StoryWritingError) as ei:
        _interactive_prepare(real_project, monkeypatch)
    assert "Qoder /gowrite" in str(ei.value)
    assert bridge.get_active_request_id() == rid

    # 取消第一个后，新一轮 Interactive 可以正常开始
    sw_ops.cancel_story_write_request(rid)
    assert bridge.get_active_request_id() is None
    prepared2 = _interactive_prepare(real_project, monkeypatch)
    assert prepared2["request_id"] != rid
    assert bridge.get_active_request_id() == prepared2["request_id"]


# ---------------------------------------------------------------------------
# L. 审计生命周期：candidate → awaiting_confirmation → authority.confirmed
# ---------------------------------------------------------------------------

def _isolated_audit(tmp_path, monkeypatch):
    from operations import execution_audit as audit
    monkeypatch.setattr(audit, "get_audit_root", lambda: tmp_path / "audit")
    return audit


def test_audit_awaiting_confirmation_then_authority_confirmed(isolated, real_project, fake_bridge, monkeypatch, tmp_path):
    """候选生成 → 审计 awaiting_confirmation（非终态）→ Confirm →
    authority.confirmed 物理存在于最终审计 JSON + completed。"""
    audit = _isolated_audit(tmp_path, monkeypatch)

    prepared = _interactive_prepare(real_project, monkeypatch)
    rid = prepared["request_id"]
    _write_qoder_response(rid, _selection_json())
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_prose"
    _write_qoder_response(rid, _prose_output(rid))
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "completed", got.get("error")

    # 候选生成后：记录保持打开（awaiting_confirmation，非终态）
    record = audit.get_execution_audit(rid)
    assert record["status"] == "awaiting_confirmation"
    assert record["finished_at"] is None
    kinds = [e["kind"] for e in record["events"]]
    assert "candidate.created" in kinds
    assert "authority.confirmed" not in kinds

    # 作者明确确认 → authority.confirmed 物理存在 + completed
    confirmed = sw_ops.confirm_story_write(
        project_id=real_project["project_id"], writing_token=got["result"]["writing_token"],
    )
    assert confirmed["message"] == "这段已经保留下来了。"

    final = audit.get_execution_audit(rid)
    assert final["status"] == "completed"
    assert final["finished_at"] is not None
    final_kinds = [e["kind"] for e in final["events"]]
    assert "authority.confirmed" in final_kinds, "authority.confirmed 必须出现在最终审计事件中"
    raw = json.dumps(final, ensure_ascii=False)
    assert '"authority.confirmed"' in raw, "authority.confirmed 必须物理存在于最终审计 JSON"


def test_audit_discard_after_candidate_cancels(isolated, real_project, fake_bridge, monkeypatch, tmp_path):
    """候选生成后 Discard/Cancel：审计收尾为 canceled（不再停留在 awaiting）。"""
    audit = _isolated_audit(tmp_path, monkeypatch)

    prepared = _interactive_prepare(real_project, monkeypatch)
    rid = prepared["request_id"]
    _write_qoder_response(rid, _selection_json())
    sw_ops.get_story_write_request(rid)
    _write_qoder_response(rid, _prose_output(rid))
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "completed", got.get("error")
    assert audit.get_execution_audit(rid)["status"] == "awaiting_confirmation"

    sw_ops.cancel_story_write_request(rid)
    final = audit.get_execution_audit(rid)
    assert final["status"] == "canceled"
    assert final["finished_at"] is not None
