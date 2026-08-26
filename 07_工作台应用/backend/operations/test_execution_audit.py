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
            "objective": "写开场。", "knowledge_needs": [], "selected_knowledge_refs": [],
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
    # 候选生成 ≠ 操作完成：记录保持打开（awaiting_confirmation，非终态）
    assert record["status"] == "awaiting_confirmation"
    assert record["finished_at"] is None
    assert record["execution_mode"] == "interactive_bridge"
    assert record["duration_ms"] is None
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
            "selection_ref": "reference_bkp/book_a/K001",
            "source_kind": "reference_bkp", "source_id": "book_a", "source_title": "book_a",
            "maturity": "source_bound", "source_anchor": "K001",
            "statement": "A 卡", "rank": 1,
            "scope": "s", "boundary": "b", "confidence": 0.9, "evidence": [], "relevance_reason": "r",
        })()],
        "to_dict": lambda self: {"status": "OK", "candidate_count": 1, "hits": [{"selection_ref": "reference_bkp/book_a/K001", "source_kind": "reference_bkp", "source_id": "book_a", "source_anchor": "K001", "statement": "A 卡"}], "gaps": []},
    })()
    monkeypatch.setattr(sw_ops, "_retrieve_package", lambda q: package)

    def _stage1(request):
        rid = request["request_id"]
        shown = sw_ops.execute_request_scoped_retrieval("信息层次", rid)
        fp = sw_ops._package_fingerprint(shown)
        return json.dumps({
            "semantic_interpretation": {
                "objective": "写开场。", "knowledge_needs": ["信息层次"],
                "selected_knowledge_refs": ["reference_bkp/book_a/K001"], "package_ref": fp, "assumptions": [],
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
    # 审计证明：混合多源检索事件同时记录 selection_ref 与 source_kind（不记录知识正文）
    assert "reference_bkp/book_a/K001" in built[0]["details"]["refs"]
    assert built[0]["details"]["source_kinds"] == ["reference_bkp"]
    assert selected[0]["details"]["refs"] == ["reference_bkp/book_a/K001"]
    assert bound[0]["details"]["refs"] == ["reference_bkp/book_a/K001"]


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
                    "objective": "规划", "knowledge_needs": [], "selected_knowledge_refs": [],
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
    # 候选生成 ≠ 操作完成：Direct 同样进入 awaiting_confirmation（等作者确认）
    assert record["status"] == "awaiting_confirmation"
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
            return AgentResult(status="completed", output='{"semantic_interpretation":{"objective":"x","knowledge_needs":[],"selected_knowledge_refs":[],"package_ref":"","assumptions":[]},"planning_target":{"description":"d","scope_kind":"free"},"model_output":{"proposal":"p","planning_items":[{"description":"i"}]}}', agent=self.name)
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


# ---------------------------------------------------------------------------
# G2. 跨进程事件合并（event_id 身份；seq 只作顺序元数据）
# ---------------------------------------------------------------------------

def _simulate_child_append(request_id: str, kind: str, component: str, **kw):
    """模拟 retrieval_snapshot.py 子进程：进程内 registry 为空 → 走文件路径。"""
    audit._ACTIVE_RECORDERS.clear()
    audit.append_event(request_id, kind, component, **kw)


def test_cross_process_events_all_preserved(isolated):
    """A. 主进程 seq=1,2 → 子进程追加 → 主进程再追加 → 全部事件恰好一次。

    旧实现按 seq 合并会把子进程事件（与主进程本地 seq 撞号）静默覆盖；
    新实现以 event_id 合并，全部保留。
    """
    rid = "req-cross-a"
    recorder = audit.AuditRecorder(rid, "story_write")
    recorder.event(audit.EVENT_BRIDGE_WAITING, "story_write")
    recorder.event(audit.EVENT_SKILL_STARTED, "story_write", details={"skill": "StoryWrite"})

    # 模拟子进程：磁盘当前 seq=1,2 → 子进程写 seq=3（与主进程本地 seq 撞号）
    _simulate_child_append(rid, audit.EVENT_RETRIEVAL_REQUESTED, "knowledge_retrieve")
    _simulate_child_append(rid, audit.EVENT_RETRIEVAL_PACKAGE_BUILT, "knowledge_retrieve", details={"candidate_count": 1})

    # 主进程继续写（本地 seq=3 撞子进程 seq=3）
    recorder.event(audit.EVENT_RETRIEVAL_SELECTED, "knowledge_retrieve")
    recorder.event(audit.EVENT_CONTEXT_BOUND, "context_compiler")
    recorder.finish(audit.STATUS_COMPLETED)

    record = _record(rid)
    kinds = [e["kind"] for e in record["events"]]
    assert kinds.count("operation.started") == 1
    assert kinds.count("bridge.waiting") == 1
    assert kinds.count("skill.started") == 1
    assert kinds.count("retrieval.requested") == 1
    assert kinds.count("retrieval.package_built") == 1
    assert kinds.count("retrieval.selected") == 1
    assert kinds.count("context.bound") == 1
    assert len(record["events"]) == 7, "所有事件必须恰好一次"


def test_duplicate_original_seq_both_survive(isolated):
    """B. 两个不同事件携带相同原始 seq 时，合并后都必须保留。"""
    rid = "req-cross-b"
    recorder = audit.AuditRecorder(rid, "story_write")
    recorder.event(audit.EVENT_BRIDGE_WAITING, "story_write")  # 本地 seq=1

    # 手工构造磁盘记录：两个不同事件都写 seq=1（模拟跨写入方 seq 撞号）
    path = audit.audit_path(rid)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema": audit.SCHEMA,
        "request_id": rid,
        "operation": "story_write",
        "project_id": None,
        "execution_mode": "interactive_bridge",
        "agent_id": "qoder",
        "model": None,
        "status": "running",
        "started_at": audit._now_iso(),
        "finished_at": None,
        "duration_ms": None,
        "events": [
            {"event_id": "child-1", "seq": 1, "at": audit._now_iso(), "kind": "retrieval.requested", "component": "knowledge_retrieve", "verified": True},
            {"event_id": "child-2", "seq": 1, "at": audit._now_iso(), "kind": "retrieval.package_built", "component": "knowledge_retrieve", "verified": True},
        ],
    }
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    recorder.event(audit.EVENT_RETRIEVAL_SELECTED, "knowledge_retrieve")
    recorder.finish(audit.STATUS_COMPLETED)

    record = _record(rid)
    kinds = [e["kind"] for e in record["events"]]
    assert kinds.count("retrieval.requested") == 1
    assert kinds.count("retrieval.package_built") == 1
    assert kinds.count("retrieval.selected") == 1
    # op.started + bridge.waiting（recorder 自身）+ 两个同 seq 子事件 + selected
    assert kinds.count("operation.started") == 1
    assert kinds.count("bridge.waiting") == 1
    assert len(record["events"]) == 5


def test_retrieval_child_events_not_lost_after_main_events(isolated):
    """C. KnowledgeRetrieve 子进程事件（requested/package_built）在主进程随后
    追加事件后绝不丢失（对应真实 Stage 1：CLI 子进程写检索事件 → finalize 追写）。"""
    rid = "req-cross-c"
    recorder = audit.AuditRecorder(rid, "story_write")
    recorder.event(audit.EVENT_BRIDGE_WAITING, "story_write")

    _simulate_child_append(rid, audit.EVENT_RETRIEVAL_REQUESTED, "knowledge_retrieve", details={"query": "信息层次"})
    _simulate_child_append(rid, audit.EVENT_RETRIEVAL_PACKAGE_BUILT, "knowledge_retrieve", details={"candidate_count": 2})

    # 主进程 finalize 追写（多次 flush 后仍须保留子进程事件）
    recorder.event(audit.EVENT_RETRIEVAL_SELECTED, "knowledge_retrieve", details={"refs": ["reference_bkp/book_a/K001"]})
    recorder.event(audit.EVENT_CONTEXT_BOUND, "context_compiler", details={"refs": ["reference_bkp/book_a/K001"]})
    recorder.event(audit.EVENT_CANDIDATE_CREATED, "story_write")
    recorder.finish(audit.STATUS_COMPLETED)

    record = _record(rid)
    kinds = [e["kind"] for e in record["events"]]
    assert kinds.count("retrieval.requested") == 1
    assert kinds.count("retrieval.package_built") == 1
    assert kinds.count("retrieval.selected") == 1
    assert kinds.count("context.bound") == 1
    assert kinds.count("candidate.created") == 1
    requested = next(e for e in record["events"] if e["kind"] == "retrieval.requested")
    assert requested["details"]["query"] == "信息层次"
    built = next(e for e in record["events"] if e["kind"] == "retrieval.package_built")
    assert built["details"]["candidate_count"] == 2


def test_final_seq_contiguous_and_ids_unique(isolated):
    """D+E. 合并后 seq 连续 1..N（仅展示顺序）；event_id 全部唯一。"""
    rid = "req-cross-de"
    recorder = audit.AuditRecorder(rid, "story_write")
    recorder.event(audit.EVENT_BRIDGE_WAITING, "story_write")
    recorder.event(audit.EVENT_SKILL_STARTED, "story_write", details={"skill": "StoryWrite"})
    _simulate_child_append(rid, audit.EVENT_RETRIEVAL_REQUESTED, "knowledge_retrieve")
    recorder.event(audit.EVENT_SKILL_COMPLETED, "story_write", details={"skill": "StoryWrite"})
    recorder.finish(audit.STATUS_COMPLETED)

    record = _record(rid)
    events = record["events"]
    seqs = [e["seq"] for e in events]
    assert seqs == list(range(1, len(events) + 1)), f"seq 必须连续 1..N：{seqs}"
    ids = [e["event_id"] for e in events]
    assert len(ids) == len(set(ids)), "event_id 必须全局唯一"
    assert all(isinstance(eid, str) and eid for eid in ids)


def test_legacy_events_without_event_id_preserved(isolated):
    """F. 旧版事件（无 event_id）仍可读、不被丢弃（append/finish 容忍旧记录）。"""
    rid = "req-legacy"
    path = audit.audit_path(rid)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema": audit.SCHEMA,
        "request_id": rid,
        "operation": "story_plan",
        "project_id": None,
        "execution_mode": "direct",
        "agent_id": "fake",
        "model": "m",
        "status": "running",
        "started_at": audit._now_iso(),
        "finished_at": None,
        "duration_ms": None,
        "events": [
            {"seq": 1, "at": audit._now_iso(), "kind": "operation.started", "component": "operation", "verified": True, "details": {"operation": "story_plan"}},
            {"seq": 2, "at": audit._now_iso(), "kind": "agent.completed", "component": "story_plan", "verified": True},
        ],
    }
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    # 新版子进程向旧版记录追加（legacy 事件必须原样保留）
    audit.append_event(rid, "candidate.created", "story_plan")
    audit.finish_file(rid, audit.STATUS_COMPLETED)

    record = audit.get_execution_audit(rid)
    assert record is not None
    kinds = [e["kind"] for e in record["events"]]
    assert kinds.count("operation.started") == 1, "legacy 事件不得被丢弃"
    assert kinds.count("agent.completed") == 1
    assert kinds.count("candidate.created") == 1
    assert len(record["events"]) == 3
    assert [e["seq"] for e in record["events"]] == [1, 2, 3]
    # 新事件带 event_id；legacy 事件保持原字段可读
    new_event = next(e for e in record["events"] if e["kind"] == "candidate.created")
    assert new_event["event_id"]
    assert any(e.get("event_id") is None for e in record["events"]), "legacy 事件不强制补写 event_id"


def test_merge_corrupt_disk_never_breaks_author_op(isolated, monkeypatch):
    """G. 磁盘合并失败（损坏 JSON）不能破坏作者操作：回退到进程内事件。"""
    rid = "req-corrupt"
    recorder = audit.AuditRecorder(rid, "story_write")
    recorder.event(audit.EVENT_BRIDGE_WAITING, "story_write")
    # 磁盘文件被写坏（不可解析）
    path = audit.audit_path(rid)
    path.write_text("{not valid json", encoding="utf-8")
    recorder.event(audit.EVENT_SKILL_STARTED, "story_write", details={"skill": "StoryWrite"})
    recorder.finish(audit.STATUS_COMPLETED)

    record = audit.get_execution_audit(rid)
    assert record is not None, "损坏磁盘不能使记录消失"
    kinds = [e["kind"] for e in record["events"]]
    assert kinds.count("operation.started") == 1
    assert kinds.count("bridge.waiting") == 1
    assert kinds.count("skill.started") == 1
