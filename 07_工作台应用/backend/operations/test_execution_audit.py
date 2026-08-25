# -*- coding: utf-8 -*-
"""验证式执行审计 targeted tests。

覆盖：
A. Direct 操作审计：agent.direct_process_started / agent.completed / skill 事件 /
   retrieval 事件 / candidate.created / status=completed / duration_ms；
B. 交互桥审计：bridge.waiting（等待中绝不声称 Agent 已启动）+ bridge.response_received；
C. retrieval 0 次 = 无伪造 retrieval 事件；needs 非空 = candidate/selected/injected 一致；
D. canceled / failed 终态正确记录；
E. 审计写入失败绝不使作者操作失败（best-effort 隔离）；
F. 无 secret 字段（不存 key/token/prompt/输出全文）。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "StoryWrite"))

import project_workspace  # noqa: E402

from agents.base import AgentRequest  # noqa: E402
from operations import execution_audit as audit  # noqa: E402
from operations import qoder_bridge as bridge  # noqa: E402
from operations import story_planning as sp_ops  # noqa: E402
from operations import story_writing as sw_ops  # noqa: E402
from config.settings import SettingsStore, AppSettings  # noqa: E402


def _selection_json():
    return json.dumps({
        "semantic_interpretation": {
            "objective": "写开场。", "knowledge_needs": [], "selected_bkp_ids": [],
            "package_ref": "", "assumptions": ["主角首次进入花园"],
        },
        "state_selections": [], "conflicts_or_tensions": [],
    }, ensure_ascii=False)


def _prose_json(request_id):
    request = bridge.get_request(request_id)
    import re
    m = re.search(r"本次 Context 快照指纹[^\n]*\n([0-9a-f]{64})", request["task"])
    fp = m.group(1) if m else "0" * 64
    return json.dumps({
        "context_ref": fp, "draft_text": "正文内容。",
        "settlement_candidates": [{
            "classification": "mechanical", "target_area": "canon_facts",
            "entry": {"id": "placeholder", "fact": "主角进入花园。"}, "operation": "append", "reason": "正文明确",
        }],
    }, ensure_ascii=False)


def _write_response(request_id, output):
    resp = bridge.response_path(request_id)
    resp.parent.mkdir(parents=True, exist_ok=True)
    resp.write_text(json.dumps({
        "schema": "gowrite_response/v1", "request_id": request_id,
        "status": "completed", "result": None, "output": output, "error": None,
    }, ensure_ascii=False), encoding="utf-8")


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    projects_root = tmp_path / "03_作品工程"
    projects_root.mkdir()
    monkeypatch.setattr(project_workspace, "get_projects_root", lambda: projects_root)
    monkeypatch.setattr(sw_ops, "get_writing_root", lambda: tmp_path / ".writing")
    monkeypatch.setattr(sp_ops, "get_planning_root", lambda: tmp_path / ".planning")
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: tmp_path / ".bridge")
    monkeypatch.setattr(audit, "get_audit_root", lambda: tmp_path / "audit")
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path / "cfg"))
    return projects_root


@pytest.fixture(autouse=True)
def _fresh_manager(monkeypatch):
    from operations import execution_tasks
    fresh = execution_tasks.ExecutionTaskManager()
    monkeypatch.setattr(sw_ops, "_exec_task_manager", fresh)
    monkeypatch.setattr(sp_ops, "_exec_task_manager", fresh)
    return fresh


@pytest.fixture()
def real_project(isolated):
    from project_workspace import create_project
    created = create_project(name="测试作品", author_intent={
        "work_direction": "都市奇幻长篇的开端设计。", "reader_promise": "读者先感到日常秩序被撬开。",
        "hard_constraints": [], "open_space": [],
    })
    project_dir = Path(created["project_dir"])
    state_file = project_dir / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["approved_plan"].append({
        "id": f"plan-{created['project_id']}", "description": "发动机",
        "target_ref": "design-x", "authority": "author_decision:x", "occurred": False, "kind": "confirmed_direction",
    })
    state["state_rev"] = 2
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"project_id": created["project_id"], "name": "测试作品", "project_dir": project_dir}


def _record(request_id):
    record = audit.get_execution_audit(request_id)
    assert record is not None, "审计记录必须存在"
    return record


def _kinds(record):
    return [e["kind"] for e in record["events"]]


# ---------------------------------------------------------------------------
# B. 交互桥审计（两阶段 /gowrite）
# ---------------------------------------------------------------------------

def test_interactive_bridge_audit_waiting_not_started(isolated, real_project, monkeypatch):
    prepared = sw_ops.prepare_story_write(project_id=real_project["project_id"], author_input="写开场")
    rid = prepared["request_id"]
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_selection"

    record = _record(rid)
    kinds = _kinds(record)
    assert "operation.started" in kinds
    assert "bridge.waiting" in kinds
    assert "agent.direct_process_started" not in kinds, "等待 /gowrite 绝不声称 Agent 已启动"
    assert "agent.completed" not in kinds
    assert record["status"] == "running"


def test_interactive_bridge_full_audit_events(isolated, real_project, monkeypatch):
    prepared = sw_ops.prepare_story_write(project_id=real_project["project_id"], author_input="写开场")
    rid = prepared["request_id"]
    _write_response(rid, _selection_json())
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_prose"
    _write_response(rid, _prose_json(rid))
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "completed", got.get("error")

    record = _record(rid)
    kinds = _kinds(record)
    assert "bridge.response_received" in kinds
    assert "skill.started" in kinds and "skill.completed" in kinds
    assert "candidate.created" in kinds
    assert record["status"] == "completed"
    assert record["execution_mode"] == "interactive_bridge"
    assert record["duration_ms"] is not None
    # 无 knowledge_needs → 无任何 retrieval 事件（不伪造）
    assert not any(k.startswith("retrieval.") for k in kinds), "零检索不得伪造 retrieval 事件"
    # 无 secret 字段
    raw = json.dumps(record, ensure_ascii=False)
    for secret in ("api_key", "token", "DEEPSEEK_API_KEY", "QWEN_TOKEN_PLAN_CN_API_KEY", "authorization"):
        assert secret.lower() not in raw.lower()


# ---------------------------------------------------------------------------
# C. retrieval candidate/selected/injected 一致
# ---------------------------------------------------------------------------

def test_retrieval_refs_consistent(isolated, real_project, monkeypatch):
    package = type("RetrievalPackage", (), {
        "status": "OK", "gaps": [], "candidate_count": 1,
        "hits": [type("Hit", (), {
            "book_id": "book_a", "source_anchor": "K001", "statement": "A 卡", "rank": 1,
            "scope": "s", "boundary": "b", "confidence": 0.9, "evidence": [], "relevance_reason": "r",
        })()],
        "to_dict": lambda self: {"status": "OK", "candidate_count": 1, "hits": [{"book_id": "book_a", "source_anchor": "K001", "statement": "A 卡"}], "gaps": []},
    })()
    monkeypatch.setattr(sw_ops, "_retrieve_package", lambda q: package)

    def _stage1(request):
        rid = request["request_id"]
        shown = sw_ops.execute_request_scoped_retrieval("信息层次", rid)
        fp = sw_ops._package_fingerprint(shown)
        return json.dumps({
            "semantic_interpretation": {
                "objective": "写开场。", "knowledge_needs": ["信息层次"],
                "selected_bkp_ids": ["book_a/K001"], "package_ref": fp, "assumptions": [],
            },
            "state_selections": [], "conflicts_or_tensions": [],
        }, ensure_ascii=False)

    prepared = sw_ops.prepare_story_write(project_id=real_project["project_id"], author_input="写开场")
    rid = prepared["request_id"]
    _write_response(rid, _stage1(bridge.get_request(rid)))
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_prose", got.get("error")
    _write_response(rid, _prose_json(rid))
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "completed", got.get("error")

    record = _record(rid)
    built = [e for e in record["events"] if e["kind"] == "retrieval.package_built"]
    selected = [e for e in record["events"] if e["kind"] == "retrieval.selected"]
    bound = [e for e in record["events"] if e["kind"] == "context.bound"]
    assert len(built) == 1 and len(selected) == 1 and len(bound) == 1
    assert "book_a/K001" in built[0]["details"]["refs"]
    assert selected[0]["details"]["refs"] == ["book_a/K001"]
    assert bound[0]["details"]["refs"] == ["book_a/K001"]


# ---------------------------------------------------------------------------
# D. canceled / failed
# ---------------------------------------------------------------------------

def test_audit_canceled(isolated, real_project, monkeypatch):
    prepared = sw_ops.prepare_story_write(project_id=real_project["project_id"], author_input="写开场")
    rid = prepared["request_id"]
    sw_ops.cancel_story_write_request(rid)
    record = _record(rid)
    assert record["status"] == "canceled"
    assert record["finished_at"] is not None


def test_audit_failed_status(isolated, real_project, monkeypatch):
    prepared = sw_ops.prepare_story_write(project_id=real_project["project_id"], author_input="写开场")
    rid = prepared["request_id"]
    _write_response(rid, _selection_json())
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_prose"
    _write_response(rid, json.dumps({
        "context_ref": "0" * 64, "draft_text": "正文。", "settlement_candidates": [],
    }, ensure_ascii=False))
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "failed"
    record = _record(rid)
    assert record["status"] == "failed"
    assert "context_ref" in (record.get("error") or "")


# ---------------------------------------------------------------------------
# E. 审计写入失败不影响作者操作
# ---------------------------------------------------------------------------

def test_audit_write_failure_never_fails_author_task(isolated, real_project, monkeypatch):
    def _boom(*args, **kwargs):
        raise OSError("audit write denied")

    # 只让“审计文件定位”抛错（隔离审计故障；桥/工作区文件照常可写）
    monkeypatch.setattr(audit, "audit_path", _boom)
    # 审计文件系统“写失败”时，prepare/get 必须照常工作
    prepared = sw_ops.prepare_story_write(project_id=real_project["project_id"], author_input="写开场")
    rid = prepared["request_id"]
    assert prepared["status"] == "task_prepared"
    _write_response(rid, _selection_json())
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "pending" and got["phase"] == "pending_prose", "审计失败不得影响阶段推进"
    _write_response(rid, _prose_json(rid))
    got = sw_ops.get_story_write_request(rid)
    assert got["status"] == "completed", "审计失败不得影响候选生成"


# ---------------------------------------------------------------------------
# A. Direct 操作审计（StoryPlan 直连 + 假 adapter）
# ---------------------------------------------------------------------------

def test_direct_operation_audit_events(isolated, real_project, monkeypatch):
    from agents.base import AgentResult
    from operations import agent_runner

    class _FakePlanAdapter:
        name = "fake_plan_agent"
        def run(self, request):
            return AgentResult(status="completed", output=json.dumps({
                "semantic_interpretation": {
                    "objective": "规划", "knowledge_needs": [], "selected_bkp_ids": [],
                    "package_ref": "", "assumptions": [], "deliberate_open_space": [],
                },
                "planning_target": {"description": "继续发展", "scope_kind": "free"},
                "model_output": {"proposal": "建议", "planning_items": [{"description": "第一项"}]},
            }, ensure_ascii=False), agent=self.name)
        def cancel(self):
            return True

    adapter = _FakePlanAdapter()
    SettingsStore().save(AppSettings(
        default_execution_mode="direct", interactive_agent="qoder",
        direct_agent=adapter.name, direct_model="m1", direct_custom_model=None,
    ))
    monkeypatch.setattr(agent_runner, "_build_adapter", lambda: (adapter, AgentRequest(task="", model="m1")))

    prepared = sp_ops.prepare_story_plan(project_id=real_project["project_id"], author_question="再往前想")
    rid = prepared["request_id"]
    assert sp_ops._exec_task_manager.join(rid, 10)
    got = sp_ops.get_story_plan_request(rid)
    assert got["status"] == "completed", got.get("error")

    record = _record(rid)
    kinds = _kinds(record)
    assert "operation.started" in kinds
    assert "agent.direct_process_started" in kinds
    assert "agent.completed" in kinds
    assert "skill.started" in kinds and "skill.completed" in kinds  # StoryPlan 实际 runtime
    assert "candidate.created" in kinds
    assert record["status"] == "completed"
    assert record["execution_mode"] == "direct"
    assert record["agent_id"] == "fake_plan_agent"
    assert record["model"] == "m1"
    # 零检索 → 无 retrieval 事件
    assert not any(k.startswith("retrieval.") for k in kinds)


# ---------------------------------------------------------------------------
# F. 无 secret 字段（direct 记录同样校验）
# ---------------------------------------------------------------------------

def test_audit_no_secret_fields_direct(isolated, real_project, monkeypatch):
    from agents.base import AgentResult
    from operations import agent_runner

    class _FakeAdapter:
        name = "fake_agent"
        def run(self, request):
            return AgentResult(status="completed", output='{"semantic_interpretation":{"objective":"x","knowledge_needs":[],"selected_bkp_ids":[],"package_ref":"","assumptions":[]},"planning_target":{"description":"d","scope_kind":"free"},"model_output":{"proposal":"p","planning_items":[{"description":"i"}]}}', agent=self.name)
        def cancel(self):
            return True

    adapter = _FakeAdapter()
    SettingsStore().save(AppSettings(
        default_execution_mode="direct", interactive_agent="qoder",
        direct_agent=adapter.name, direct_model="m", direct_custom_model=None,
    ))
    monkeypatch.setattr(agent_runner, "_build_adapter", lambda: (adapter, AgentRequest(task="", model="m")))
    prepared = sp_ops.prepare_story_plan(project_id=real_project["project_id"], author_question="继续")
    rid = prepared["request_id"]
    assert sp_ops._exec_task_manager.join(rid, 10)
    got = sp_ops.get_story_plan_request(rid)
    assert got["status"] == "completed"
    record = _record(rid)
    raw = json.dumps(record, ensure_ascii=False)
    assert "planning_token" not in raw, "token 不得进入审计"
    assert "api_key" not in raw.lower()
