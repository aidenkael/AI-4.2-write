# -*- coding: utf-8 -*-
"""M3 知识驱动重大基座设计 targeted tests（全假 Agent / 假检索，零真实模型）。

证明：
1. 多轮有界检索（>1 轮；第 _MAX_ROUNDS+1 轮被拒）；
2. 0 命中合法；
3. 选择捕获包外 ref 被拒；
4. 多 source kind 参与；
5. 候选生成零 authority 写；
6. 明确确认经既有 authority 合同写回（author fields + 账本 + settlement）；
7. stale / 跨项目确认被拒；
8. 丢弃后不可确认；
9. 外部知识不覆盖作者 authority（既有对象不变）；
10. StoryPlan/StoryWrite/change_settlement 套件保持原行为（全量回归）。
"""
import json
import sys
import threading
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))

import project_workspace  # noqa: E402

from operations import agent_runner  # noqa: E402
from operations import author_edit  # noqa: E402
from operations import change_settlement  # noqa: E402
from operations import execution_tasks  # noqa: E402
from operations import foundation_design as fd_ops  # noqa: E402
from operations import project_model  # noqa: E402
from operations import qoder_bridge as bridge  # noqa: E402
from operations import story_planning as sp_ops  # noqa: E402
from agents.base import AgentRequest, AgentResult  # noqa: E402
from config.settings import AppSettings, SettingsStore  # noqa: E402


def _hit(kind, anchor, ref=None):
    return types.SimpleNamespace(
        rank=1, selection_ref=ref or f"{kind}/book_x/{anchor}",
        source_kind=kind, source_id="book_x", source_anchor=anchor,
        confidence=0.8, evidence=[f"ev-{anchor}"], relevance_reason="测试",
    )


def _package(hits):
    return types.SimpleNamespace(status="OK", candidate_count=len(hits), hits=hits)


MIXED_PACKAGE = _package([
    _hit("reference_bkp", "a1"),
    _hit("method_source", "m1"),
    _hit("validated_knowledge", "v1"),
])
EMPTY_PACKAGE = _package([])


def _final_result(
    rounds, characters=None, relationships=None, core_conflict=None,
    world_settings=None, locations=None, organizations=None, systems=None,
    story_lines=None, promise_foreshadowing=None, mystery_information=None,
    domain_relations=None,
):
    return json.dumps({
        "objective": "基座设计目标。",
        "topics": [r["topic"] for r in rounds],
        "rounds": rounds,
        "proposal": {
            "characters": characters or [],
            "relationships": relationships or [],
            "world_settings": world_settings or [],
            "locations": locations or [],
            "organizations": organizations or [],
            "systems": systems or [],
            "core_conflict": core_conflict,
            "story_lines": story_lines or [],
            "promise_foreshadowing": promise_foreshadowing or [],
            "mystery_information": mystery_information or [],
            "domain_relations": domain_relations or [],
        },
        "knowledge_notes": "参考了检索包；scope 有限。",
        "assumptions": ["假设一"],
    }, ensure_ascii=False)


class FakeAgent:
    name = "fake_fd_agent"

    def __init__(self, on_run):
        self.on_run = on_run
        self.calls = []
        self.cancel_called = 0

    def run(self, request):
        self.calls.append(request)
        return self.on_run(request)

    def cancel(self):
        self.cancel_called += 1
        return True


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    projects_root = tmp_path / "03_作品工程"
    projects_root.mkdir()
    monkeypatch.setattr(project_workspace, "get_projects_root", lambda: projects_root)
    monkeypatch.setattr(fd_ops, "get_proposals_root", lambda: tmp_path / "foundation_proposals")
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: tmp_path / "qoder_bridge")
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path / "cfg"))
    return projects_root


@pytest.fixture(autouse=True)
def _fresh_exec_task_manager(monkeypatch):
    fresh = execution_tasks.ExecutionTaskManager()
    monkeypatch.setattr(fd_ops, "_exec_task_manager", fresh)
    return fresh


def _direct(adapter, monkeypatch):
    SettingsStore().save(AppSettings(
        default_execution_mode="direct", interactive_agent="qoder",
        direct_agent=adapter.name, direct_model="native-model-1", direct_custom_model=None,
    ))
    monkeypatch.setattr(
        agent_runner, "_build_adapter",
        lambda: (adapter, AgentRequest(task="", model="native-model-1", custom_model=None)),
    )


def _create_project(name="基座作品"):
    return project_workspace.create_project(name=name, author_intent={
        "work_direction": "测试方向",
        "reader_promise": "测试期待",
        "hard_constraints": [],
        "open_space": [],
    })


def _wait(request_id, timeout=5.0):
    fd_ops._exec_task_manager.join(request_id, timeout)


def _run_two_rounds(request_id):
    """模拟 Agent 在执行内按主题运行两次检索命令。"""
    fd_ops.execute_request_scoped_retrieval("人物结构问题", request_id)
    fd_ops.execute_request_scoped_retrieval("核心冲突问题", request_id)
    fp = fd_ops._package_fingerprint(MIXED_PACKAGE)
    return AgentResult(status="completed", output=_final_result([
        {"topic": "人物结构", "query": "人物结构问题", "package_ref": fp,
         "selected_knowledge_refs": ["reference_bkp/book_x/a1", "method_source/book_x/m1"],
         "comparison": "参考作品与方法来源 scope 不同；无反证。"},
        {"topic": "核心冲突", "query": "核心冲突问题", "package_ref": fp,
         "selected_knowledge_refs": ["validated_knowledge/book_x/v1"],
         "comparison": "已验证知识边界清晰。"},
    ], characters=[
        {"title": "程一", "summary": "结构工程师，沉默观察者。", "material_state": "future"},
        {"title": "苏二", "summary": "旧物修复师。", "material_state": "future"},
    ], relationships=[
        {"source_title": "程一", "target_title": "苏二", "label": "缓慢接近", "summary": "日常中的自然接近。"},
    ], core_conflict={"title": "停滞与明天", "summary": "功能正常但内心空白 vs 微小日常责任。"}), agent=FakeAgent.name)


def test_multi_round_retrieval_candidate_no_authority_write_then_confirm(
    isolated, monkeypatch,
):
    monkeypatch.setattr(fd_ops, "_retrieve_package", lambda query: MIXED_PACKAGE)
    project = _create_project()
    pid = project["project_id"]
    rev_before = project_model.read_project_model(pid)["model_rev"]

    # 作者既有 authority（证明 9 的对照物）
    author_char = author_edit.create_foundation_record(
        pid, base_model_rev=project_model.read_project_model(pid)["model_rev"],
        category="character", title="女主", material_state="current", data={"role": "作者设定"},
    )
    rev_before = author_char["model"]["model_rev"]

    captured = {}

    def on_run(request):
        import re
        rid = re.search(r"--request ([0-9a-f]+)", request.task).group(1)
        captured["rid"] = rid
        return _run_two_rounds(rid)

    adapter = FakeAgent(on_run)
    _direct(adapter, monkeypatch)
    prepared = fd_ops.prepare_foundation_design(pid, "设计主角结构与核心冲突", rev_before)
    assert prepared["status"] == "task_prepared"
    _wait(prepared["request_id"])
    polled = fd_ops.get_foundation_design_request(prepared["request_id"])
    assert polled["status"] == "completed", polled.get("error")
    result = polled["result"]

    # 证明 1：>1 轮有界检索；证明 4：多 source kind 参与
    assert len(result["candidate"]["rounds"]) == 2
    assert result["candidate"]["knowledge"]["source_kinds"] == [
        "method_source", "reference_bkp", "validated_knowledge",
    ]
    # 证明 5：候选生成零 authority 写
    assert project_model.read_project_model(pid)["model_rev"] == rev_before

    # 证明 6：明确确认经既有 authority 合同写回
    items = [
        {"kind": "character", "title": "程一", "summary": "编辑后的设定。", "material_state": "future"},
        {"kind": "character", "title": "苏二", "summary": "旧物修复师。", "material_state": "future"},
        {"kind": "relationship", "title": "缓慢接近", "summary": "日常中的自然接近。",
         "material_state": "future", "source_title": "程一", "target_title": "苏二", "label": "缓慢接近"},
        {"kind": "core_conflict", "title": "停滞与明天", "summary": "核心冲突。", "material_state": "future"},
    ]
    confirmed = fd_ops.confirm_foundation_design(
        pid, result["proposal_token"], items, project_model.read_project_model(pid)["model_rev"],
    )
    assert len(confirmed["created"]) == 4 and not confirmed["warnings"]
    model = project_model.read_project_model(pid)
    assert model["model_rev"] > rev_before
    created_titles = {obj["title"] for obj in model["objects"].values() if not obj.get("tombstoned")}
    assert {"程一", "苏二", "停滞与明天"} <= created_titles
    cheng = next(obj for obj in model["objects"].values() if obj["title"] == "程一")
    assert cheng["field_authority"]["design_summary"]["source"] == "author"  # 作者确认 = 作者决定
    edges = [e for e in model["dependencies"].values() if not e.get("tombstoned")]
    assert any(e.get("title") == "缓慢接近" for e in edges)
    # 写回进入既有作者变更账本（语义需要 → settlement 路径）
    ledger = author_edit._read_changes(author_edit._load(pid)[2], pid)["changes"]
    assert any(c.get("source_kind") == "manual_foundation_edit" or c.get("requires_semantic") for c in ledger)

    # 证明 9：外部知识/候选不覆盖作者既有 authority
    nv = next(obj for obj in model["objects"].values() if obj["title"] == "女主")
    assert nv["data"]["role"] == "作者设定"

    # 证明 8 前置：确认后候选失效，重复确认被拒
    with pytest.raises(fd_ops.FoundationDesignError):
        fd_ops.confirm_foundation_design(pid, result["proposal_token"], items, model["model_rev"])


def test_dynamic_categories_structured_data_candidate_keys_and_core_conflict_fix(isolated, monkeypatch):
    calls = []

    def fake_retrieve(query):
        calls.append(query)
        return EMPTY_PACKAGE

    monkeypatch.setattr(fd_ops, "_retrieve_package", fake_retrieve)
    project = _create_project("动态基座")
    pid = project["project_id"]
    rev = project_model.read_project_model(pid)["model_rev"]

    def on_run(request):
        import re
        rid = re.search(r"--request ([0-9a-f]+)", request.task).group(1)
        fd_ops.execute_request_scoped_retrieval("初始地基", rid)
        fp = fd_ops._package_fingerprint(EMPTY_PACKAGE)
        return AgentResult(status="completed", output=_final_result([
            {"topic": "初始地基", "query": "初始地基", "package_ref": fp,
             "selected_knowledge_refs": [], "comparison": "0 命中，按作者意图。"},
        ], characters=[
            {"candidate_key": "char-a", "title": "程一", "material_state": "future",
             "data": {"one_line_intro": "结构工程师", "goal_desire": "找回明天"}},
            {"candidate_key": "char-b", "title": "苏二", "material_state": "future",
             "data": {"one_line_intro": "旧物修复师"}},
        ], relationships=[
            {"candidate_key": "rel-a", "source_key": "char-a", "target_key": "char-b", "label": "互相试探",
             "material_state": "future", "data": {"description": "因旧物线索相识", "current_tension": "互不完全信任"}},
        ], locations=[
            {"candidate_key": "loc-a", "title": "旧货市场", "material_state": "future",
             "data": {"type": "地点", "story_social_function": "秘密交换场"}},
        ], systems=[
            {"candidate_key": "sys-a", "title": "明日券规则", "material_state": "future",
             "data": {"type": "交易体系", "levels_stages": "一次性券", "limitations_costs": "透支未来记忆"}},
        ], promise_foreshadowing=[
            {"candidate_key": "pf-a", "title": "空白收据", "material_state": "future",
             "data": {"setup_trigger": "第一章收到", "reader_question_promise": "谁支付了代价"}},
        ], mystery_information=[
            {"candidate_key": "myst-a", "title": "付款人", "material_state": "future",
             "data": {"secret_fact": "付款人不是本人", "who_knows": ["苏二"], "reveal_status": "hidden"}},
        ], core_conflict={"candidate_key": "conflict-a", "title": "停滞与明天", "material_state": "future",
                          "data": {"main_conflict": "停滞的人借用未来", "stakes": "未来记忆被抵押"}}), agent=FakeAgent.name)

    adapter = FakeAgent(on_run)
    _direct(adapter, monkeypatch)
    prepared = fd_ops.prepare_foundation_design(pid, "完善新书地基", rev)
    _wait(prepared["request_id"])
    polled = fd_ops.get_foundation_design_request(prepared["request_id"])
    assert polled["status"] == "completed", polled.get("error")
    assert calls == ["初始地基"]

    candidate = polled["result"]["candidate"]["proposal"]
    assert candidate["locations"][0]["data"]["story_social_function"] == "秘密交换场"
    assert candidate["systems"][0]["data"]["limitations_costs"] == "透支未来记忆"
    assert candidate["promise_foreshadowing"][0]["data"]["reader_question_promise"] == "谁支付了代价"
    assert candidate["mystery_information"][0]["data"]["who_knows"] == ["苏二"]

    # 模拟作者 review 阶段编辑了结构化字段，并排除 location。
    items = [
        {**candidate["characters"][0], "kind": "character", "data": {**candidate["characters"][0]["data"], "goal_desire": "查明收据来源"}},
        {**candidate["characters"][1], "kind": "character"},
        {**candidate["relationships"][0], "kind": "relationship", "title": candidate["relationships"][0]["label"]},
        {**candidate["systems"][0], "kind": "system"},
        {**candidate["promise_foreshadowing"][0], "kind": "promise_foreshadowing"},
        {**candidate["mystery_information"][0], "kind": "mystery_information"},
        {**candidate["core_conflict"], "kind": "core_conflict"},
    ]
    confirmed = fd_ops.confirm_foundation_design(
        pid, polled["result"]["proposal_token"], items, project_model.read_project_model(pid)["model_rev"],
    )
    assert not confirmed["warnings"]
    assert calls == ["初始地基"], "finalize/confirm 不得再次检索"
    model = project_model.read_project_model(pid)
    by_title = {obj["title"]: obj for obj in model["objects"].values() if not obj.get("tombstoned")}
    assert by_title["程一"]["data"]["goal_desire"] == "查明收据来源"
    assert by_title["明日券规则"]["kind"] == "system"
    assert by_title["空白收据"]["category"] == "promise_foreshadowing"
    assert by_title["付款人"]["category"] == "mystery_information"
    assert by_title["停滞与明天"]["category"] == "story_line"
    assert by_title["停滞与明天"]["data"]["main_conflict"] == "停滞的人借用未来"
    assert "旧货市场" not in by_title, "未选条目不得写入"
    assert not any(obj.get("category") == "world_setting" and obj.get("title") == "停滞与明天" for obj in model["objects"].values())
    edge = next(edge for edge in model["dependencies"].values() if edge.get("title") == "互相试探")
    assert edge["source_ref"] == by_title["程一"]["ref"]
    assert edge["target_ref"] == by_title["苏二"]["ref"]


def test_ambiguous_relationship_endpoint_is_not_guessed(isolated, monkeypatch):
    monkeypatch.setattr(fd_ops, "_retrieve_package", lambda query: EMPTY_PACKAGE)
    project = _create_project("关系歧义")
    pid = project["project_id"]
    first = author_edit.create_foundation_record(
        pid, base_model_rev=0, category="character", title="同名", material_state="future", data={"note": "一"},
    )
    second = author_edit.create_foundation_record(
        pid, base_model_rev=first["model"]["model_rev"], category="character", title="同名", material_state="future", data={"note": "二"},
    )
    target = author_edit.create_foundation_record(
        pid, base_model_rev=second["model"]["model_rev"], category="character", title="唯一", material_state="future", data={"note": "三"},
    )
    rev = target["model"]["model_rev"]

    def on_run(request):
        import re
        rid = re.search(r"--request ([0-9a-f]+)", request.task).group(1)
        fd_ops.execute_request_scoped_retrieval("关系", rid)
        fp = fd_ops._package_fingerprint(EMPTY_PACKAGE)
        return AgentResult(status="completed", output=_final_result([
            {"topic": "关系", "query": "关系", "package_ref": fp,
             "selected_knowledge_refs": [], "comparison": "无。"},
        ], relationships=[
            {"source_title": "同名", "target_title": "唯一", "label": "不能猜",
             "data": {"description": "端点歧义"}},
        ]), agent=FakeAgent.name)

    adapter = FakeAgent(on_run)
    _direct(adapter, monkeypatch)
    prepared = fd_ops.prepare_foundation_design(pid, "补关系", rev)
    _wait(prepared["request_id"])
    polled = fd_ops.get_foundation_design_request(prepared["request_id"])
    item = {**polled["result"]["candidate"]["proposal"]["relationships"][0], "kind": "relationship", "title": "不能猜"}
    confirmed = fd_ops.confirm_foundation_design(
        pid, polled["result"]["proposal_token"], [item], project_model.read_project_model(pid)["model_rev"],
    )
    assert confirmed["created"] == []
    assert confirmed["warnings"] == ["关系“不能猜”端点不明确，已跳过。"]
    model = project_model.read_project_model(pid)
    assert not any(edge.get("title") == "不能猜" for edge in model["dependencies"].values())


def test_zero_hits_valid_and_round_bound(isolated, monkeypatch):
    monkeypatch.setattr(fd_ops, "_retrieve_package", lambda query: EMPTY_PACKAGE)
    project = _create_project("零命中")
    pid = project["project_id"]
    rev = project_model.read_project_model(pid)["model_rev"]

    def on_run(request):
        import re
        rid = re.search(r"--request ([0-9a-f]+)", request.task).group(1)
        # 证明 2：0 命中合法
        fd_ops.execute_request_scoped_retrieval("冷门主题", rid)
        fp = fd_ops._package_fingerprint(EMPTY_PACKAGE)
        return AgentResult(status="completed", output=_final_result([
            {"topic": "冷门主题", "query": "冷门主题", "package_ref": fp,
             "selected_knowledge_refs": [], "comparison": "0 命中，仅凭作者意图。"},
        ], characters=[{"title": "独行人", "summary": "无知识支撑的设定。", "material_state": "future"}]), agent=FakeAgent.name)

    adapter = FakeAgent(on_run)
    _direct(adapter, monkeypatch)
    prepared = fd_ops.prepare_foundation_design(pid, "设计一个冷门设定", rev)
    _wait(prepared["request_id"])
    polled = fd_ops.get_foundation_design_request(prepared["request_id"])
    assert polled["status"] == "completed", polled.get("error")
    assert polled["result"]["candidate"]["knowledge"]["selected_count"] == 0

    # 证明 1（有界）：同一请求第 _MAX_ROUNDS+1 个不同轮被拒
    idle_adapter = FakeAgent(lambda req: AgentResult(status="completed", output="{}", agent=FakeAgent.name))
    _direct(idle_adapter, monkeypatch)
    prepared2 = fd_ops.prepare_foundation_design(pid, "再设计一个冷门设定", rev)
    for i in range(fd_ops._MAX_ROUNDS):
        fd_ops.execute_request_scoped_retrieval(f"轮{i}", prepared2["request_id"])
    with pytest.raises(fd_ops.FoundationDesignError):
        fd_ops.execute_request_scoped_retrieval("超出上限的轮", prepared2["request_id"])
    fd_ops.cancel_foundation_design_request(prepared2["request_id"])


def test_selected_ref_outside_package_rejected(isolated, monkeypatch):
    monkeypatch.setattr(fd_ops, "_retrieve_package", lambda query: MIXED_PACKAGE)
    project = _create_project("伪造ref")
    pid = project["project_id"]
    rev = project_model.read_project_model(pid)["model_rev"]

    def on_run(request):
        import re
        rid = re.search(r"--request ([0-9a-f]+)", request.task).group(1)
        fd_ops.execute_request_scoped_retrieval("人物结构问题", rid)
        fp = fd_ops._package_fingerprint(MIXED_PACKAGE)
        # 证明 3：选择捕获包外 ref
        return AgentResult(status="completed", output=_final_result([
            {"topic": "人物结构", "query": "人物结构问题", "package_ref": fp,
             "selected_knowledge_refs": ["reference_bkp/book_x/不存在的锚点"],
             "comparison": "伪造。"},
        ]), agent=FakeAgent.name)

    adapter = FakeAgent(on_run)
    _direct(adapter, monkeypatch)
    prepared = fd_ops.prepare_foundation_design(pid, "设计", rev)
    _wait(prepared["request_id"])
    polled = fd_ops.get_foundation_design_request(prepared["request_id"])
    assert polled["status"] == "failed"
    assert "不存在" in polled["error"] or "selection_ref" in polled["error"]


def test_stale_and_cross_project_confirm_rejected(isolated, monkeypatch):
    monkeypatch.setattr(fd_ops, "_retrieve_package", lambda query: EMPTY_PACKAGE)
    project = _create_project("隔离")
    pid = project["project_id"]
    other = _create_project("其他作品")
    rev = project_model.read_project_model(pid)["model_rev"]

    def on_run(request):
        import re
        rid = re.search(r"--request ([0-9a-f]+)", request.task).group(1)
        fd_ops.execute_request_scoped_retrieval("主题", rid)
        fp = fd_ops._package_fingerprint(EMPTY_PACKAGE)
        return AgentResult(status="completed", output=_final_result([
            {"topic": "主题", "query": "主题", "package_ref": fp,
             "selected_knowledge_refs": [], "comparison": "无。"},
        ], characters=[{"title": "甲", "summary": "设定。", "material_state": "future"}]), agent=FakeAgent.name)

    adapter = FakeAgent(on_run)
    _direct(adapter, monkeypatch)
    prepared = fd_ops.prepare_foundation_design(pid, "设计", rev)
    _wait(prepared["request_id"])
    polled = fd_ops.get_foundation_design_request(prepared["request_id"])
    assert polled["status"] == "completed"
    token = polled["result"]["proposal_token"]
    items = [{"kind": "character", "title": "甲", "summary": "设定。", "material_state": "future"}]

    # 证明 7：跨项目拒绝
    with pytest.raises(fd_ops.FoundationDesignError):
        fd_ops.confirm_foundation_design(other["project_id"], token, items, rev)
    # 证明 7：stale base_model_rev 拒绝
    author_edit.create_foundation_record(
        pid, base_model_rev=rev, category="character", title="新增", material_state="current", data={},
    )
    with pytest.raises(fd_ops.FoundationDesignError):
        fd_ops.confirm_foundation_design(pid, token, items, rev)


def test_discarded_proposal_cannot_be_confirmed(isolated, monkeypatch):
    monkeypatch.setattr(fd_ops, "_retrieve_package", lambda query: EMPTY_PACKAGE)
    project = _create_project("丢弃")
    pid = project["project_id"]
    rev = project_model.read_project_model(pid)["model_rev"]

    def on_run(request):
        import re
        rid = re.search(r"--request ([0-9a-f]+)", request.task).group(1)
        fd_ops.execute_request_scoped_retrieval("主题", rid)
        fp = fd_ops._package_fingerprint(EMPTY_PACKAGE)
        return AgentResult(status="completed", output=_final_result([
            {"topic": "主题", "query": "主题", "package_ref": fp,
             "selected_knowledge_refs": [], "comparison": "无。"},
        ], characters=[{"title": "乙", "summary": "设定。", "material_state": "future"}]), agent=FakeAgent.name)

    adapter = FakeAgent(on_run)
    _direct(adapter, monkeypatch)
    prepared = fd_ops.prepare_foundation_design(pid, "设计", rev)
    _wait(prepared["request_id"])
    polled = fd_ops.get_foundation_design_request(prepared["request_id"])
    token = polled["result"]["proposal_token"]

    canceled = fd_ops.cancel_foundation_design_request(prepared["request_id"])
    assert canceled["status"] == "canceled"
    # 证明 8：丢弃后确认被拒
    with pytest.raises(fd_ops.FoundationDesignError):
        fd_ops.confirm_foundation_design(
            pid, token,
            [{"kind": "character", "title": "乙", "summary": "设定。", "material_state": "future"}],
            rev,
        )


def test_no_parallel_retrieval_or_runtime_infra():
    source = Path(fd_ops.__file__).read_text(encoding="utf-8")
    for banned in ("vector", "embedding", "KnowledgeRouter", "langchain", "autogen"):
        assert banned not in source
    # 检索仍走 story_planning 的 P0 绑定件（同一 KnowledgeRetrieve 入口）
    assert "_retrieve_package" in source


# ---------------------------------------------------------------------------
# 显式领域关系：候选合同 + 确认后写回（零 AI；绝不按标题猜）
# ---------------------------------------------------------------------------

def _fd_round_only(request_id, package=EMPTY_PACKAGE):
    fd_ops.execute_request_scoped_retrieval("地基主题", request_id)
    return fd_ops._package_fingerprint(package)


def _fd_prepare_and_complete(pid, monkeypatch, output_builder, request="完善地基"):
    """prepare → 假 Agent 输出 → 轮询完成；返回 polled result。"""
    def on_run(request):
        import re
        rid = re.search(r"--request ([0-9a-f]+)", request.task).group(1)
        fp = _fd_round_only(rid)
        return AgentResult(status="completed", output=output_builder(fp), agent=FakeAgent.name)

    adapter = FakeAgent(on_run)
    _direct(adapter, monkeypatch)
    rev = project_model.read_project_model(pid)["model_rev"]
    prepared = fd_ops.prepare_foundation_design(pid, request, rev)
    _wait(prepared["request_id"])
    polled = fd_ops.get_foundation_design_request(prepared["request_id"])
    assert polled["status"] == "completed", polled.get("error")
    return polled


def test_sparse_proposal_and_confirm_require_only_needed_category_fields(isolated, monkeypatch):
    """FoundationDesign may propose/finalize one needed record without filling a template."""
    monkeypatch.setattr(fd_ops, "_retrieve_package", lambda query: EMPTY_PACKAGE)
    project = _create_project("稀疏候选")
    pid = project["project_id"]

    def build(fp):
        return _final_result([
            {"topic": "必要组织", "query": "地基主题", "package_ref": fp,
             "selected_knowledge_refs": [], "comparison": "0 命中仍合法。"},
        ], organizations=[
            {"candidate_key": "org-only", "title": "巡护队", "material_state": "future",
             "data": {"purpose": "守护旧城"}},
        ])

    polled = _fd_prepare_and_complete(pid, monkeypatch, build, request="只补一个必要组织")
    proposal = polled["result"]["candidate"]["proposal"]
    assert proposal["organizations"][0]["data"] == {"purpose": "守护旧城"}
    for category in (
        "characters", "relationships", "world_settings", "locations", "systems",
        "story_lines", "promise_foreshadowing", "mystery_information", "domain_relations",
    ):
        assert proposal[category] == []
    assert proposal["core_conflict"] is None

    confirmed = fd_ops.confirm_foundation_design(
        pid, polled["result"]["proposal_token"],
        [{**proposal["organizations"][0], "kind": "organization"}],
        project_model.read_project_model(pid)["model_rev"],
    )
    assert len(confirmed["created"]) == 1 and not confirmed["warnings"]
    model = project_model.read_project_model(pid)
    created = next(item for item in model["objects"].values() if item.get("title") == "巡护队")
    assert created["data"] == {"purpose": "守护旧城"}
    assert created["author_fields"] == ["purpose"]


def test_fd_domain_relations_written_after_explicit_confirm_only(isolated, monkeypatch):
    monkeypatch.setattr(fd_ops, "_retrieve_package", lambda query: EMPTY_PACKAGE)
    project = _create_project("关系写回")
    pid = project["project_id"]

    def build(fp):
        return _final_result([
            {"topic": "地基主题", "query": "地基主题", "package_ref": fp,
             "selected_knowledge_refs": [], "comparison": "0 命中。"},
        ], characters=[
            {"candidate_key": "char-a", "title": "林渊", "material_state": "future",
             "data": {"one_line_intro": "主角"}},
        ], organizations=[
            {"candidate_key": "org-a", "title": "玄天宗", "material_state": "future",
             "data": {"type": "宗门"}},
        ], systems=[
            {"candidate_key": "sys-a", "title": "玄灵境界", "material_state": "future",
             "data": {"type": "修炼体系"}},
        ], story_lines=[
            {"candidate_key": "line-a", "title": "主线一", "material_state": "future",
             "data": {"goal_purpose": "入门"}},
        ], locations=[
            {"candidate_key": "loc-a", "title": "北境", "material_state": "future",
             "data": {"type": "地域"}},
        ], promise_foreshadowing=[
            {"candidate_key": "pf-a", "title": "旧玉佩", "material_state": "future",
             "data": {"setup_trigger": "开局"}},
        ], mystery_information=[
            {"candidate_key": "myst-a", "title": "失踪真相", "material_state": "future",
             "data": {"secret_fact": "秘密"}},
        ], domain_relations=[
            {"relation_kind": "character_affiliated_with_organization", "source_key": "char-a", "target_key": "org-a"},
            {"relation_kind": "character_uses_system", "source_key": "char-a", "target_key": "sys-a"},
            {"relation_kind": "storyline_involves_character", "source_key": "line-a", "target_key": "char-a"},
            {"relation_kind": "storyline_involves_organization", "source_key": "line-a", "target_key": "org-a"},
            {"relation_kind": "storyline_involves_location", "source_key": "line-a", "target_key": "loc-a"},
            {"relation_kind": "foreshadowing_related_to", "source_key": "pf-a", "target_key": "char-a"},
            {"relation_kind": "mystery_information_related_to", "source_key": "myst-a", "target_key": "org-a"},
        ])

    polled = _fd_prepare_and_complete(pid, monkeypatch, build)
    candidate = polled["result"]["candidate"]
    assert len(candidate["proposal"]["domain_relations"]) == 7
    # 候选阶段零 authority 写：没有任何边被创建
    assert project_model.read_project_model(pid)["dependencies"] == {}

    items = []
    for kind, entry in (
        ("character", candidate["proposal"]["characters"][0]),
        ("organization", candidate["proposal"]["organizations"][0]),
        ("system", candidate["proposal"]["systems"][0]),
        ("story_line", candidate["proposal"]["story_lines"][0]),
        ("location", candidate["proposal"]["locations"][0]),
        ("promise_foreshadowing", candidate["proposal"]["promise_foreshadowing"][0]),
        ("mystery_information", candidate["proposal"]["mystery_information"][0]),
    ):
        items.append({**entry, "kind": kind})

    # 未选关系不写：仅采用条目、不带关系 → 零边
    confirmed = fd_ops.confirm_foundation_design(
        pid, polled["result"]["proposal_token"], items,
        project_model.read_project_model(pid)["model_rev"],
    )
    assert not confirmed["warnings"]
    assert project_model.read_project_model(pid)["dependencies"] == {}


def test_fd_selected_domain_relations_write_via_author_edit(isolated, monkeypatch):
    monkeypatch.setattr(fd_ops, "_retrieve_package", lambda query: EMPTY_PACKAGE)
    project = _create_project("关系选中")
    pid = project["project_id"]

    def build(fp):
        return _final_result([
            {"topic": "地基主题", "query": "地基主题", "package_ref": fp,
             "selected_knowledge_refs": [], "comparison": "0 命中。"},
        ], characters=[
            {"candidate_key": "char-a", "title": "林渊", "material_state": "future",
             "data": {"one_line_intro": "主角"}},
        ], organizations=[
            {"candidate_key": "org-a", "title": "玄天宗", "material_state": "future",
             "data": {"type": "宗门"}},
        ], domain_relations=[
            {"relation_kind": "character_affiliated_with_organization", "source_key": "char-a", "target_key": "org-a"},
        ])

    polled = _fd_prepare_and_complete(pid, monkeypatch, build)
    proposal = polled["result"]["candidate"]["proposal"]
    items = [
        {**proposal["characters"][0], "kind": "character"},
        {**proposal["organizations"][0], "kind": "organization"},
    ]
    confirmed = fd_ops.confirm_foundation_design(
        pid, polled["result"]["proposal_token"], items,
        project_model.read_project_model(pid)["model_rev"],
        relations=[{"relation_kind": "character_affiliated_with_organization",
                    "source_key": "char-a", "target_key": "org-a"}],
    )
    assert not confirmed["warnings"]
    model = project_model.read_project_model(pid)
    edges = [edge for edge in model["dependencies"].values() if not edge.get("tombstoned")]
    assert len(edges) == 1
    edge = edges[0]
    assert edge["relation_kind"] == "character_affiliated_with_organization"
    assert model["objects"][edge["source_ref"]]["title"] == "林渊"
    assert model["objects"][edge["target_ref"]]["title"] == "玄天宗"
    assert edge["title"] == "所属组织"
    # 写回经统一作者账本（domain_relation_edit）；零 AI 自动启动
    ledger = author_edit._read_changes(author_edit._load(pid)[2], pid)["changes"]
    assert any(item.get("source_kind") == "domain_relation_edit" for item in ledger)
    assert all(not item.get("settlement_started") for item in ledger)


def test_fd_excluded_endpoint_skips_relation_with_warning(isolated, monkeypatch):
    monkeypatch.setattr(fd_ops, "_retrieve_package", lambda query: EMPTY_PACKAGE)
    project = _create_project("端点排除")
    pid = project["project_id"]

    def build(fp):
        return _final_result([
            {"topic": "地基主题", "query": "地基主题", "package_ref": fp,
             "selected_knowledge_refs": [], "comparison": "0 命中。"},
        ], characters=[
            {"candidate_key": "char-a", "title": "林渊", "material_state": "future",
             "data": {"one_line_intro": "主角"}},
        ], organizations=[
            {"candidate_key": "org-a", "title": "玄天宗", "material_state": "future",
             "data": {"type": "宗门"}},
        ], domain_relations=[
            {"relation_kind": "character_affiliated_with_organization", "source_key": "char-a", "target_key": "org-a"},
        ])

    polled = _fd_prepare_and_complete(pid, monkeypatch, build)
    proposal = polled["result"]["candidate"]["proposal"]
    # 作者只采用人物，排除组织候选 → 关系跳过 + 警告；绝不按同名既有对象猜。
    confirmed = fd_ops.confirm_foundation_design(
        pid, polled["result"]["proposal_token"],
        [{**proposal["characters"][0], "kind": "character"}],
        project_model.read_project_model(pid)["model_rev"],
        relations=[{"relation_kind": "character_affiliated_with_organization",
                    "source_key": "char-a", "target_key": "org-a"}],
    )
    assert confirmed["warnings"] == ["领域关系“所属组织”的端点未在本次确认中采用，已跳过。"]
    assert project_model.read_project_model(pid)["dependencies"] == {}


def test_fd_same_title_existing_object_never_silently_bound(isolated, monkeypatch):
    monkeypatch.setattr(fd_ops, "_retrieve_package", lambda query: EMPTY_PACKAGE)
    project = _create_project("同名不猜")
    pid = project["project_id"]
    # 既有同名组织（作者记录）
    author_edit.create_foundation_record(
        pid, base_model_rev=project_model.read_project_model(pid)["model_rev"],
        category="organization_force", title="玄天宗", material_state="current", data={},
    )

    def build(fp):
        return _final_result([
            {"topic": "地基主题", "query": "地基主题", "package_ref": fp,
             "selected_knowledge_refs": [], "comparison": "0 命中。"},
        ], characters=[
            {"candidate_key": "char-a", "title": "林渊", "material_state": "future",
             "data": {"one_line_intro": "主角"}},
        ], organizations=[
            {"candidate_key": "org-a", "title": "玄天宗", "material_state": "future",
             "data": {"type": "宗门"}},
        ], domain_relations=[
            {"relation_kind": "character_affiliated_with_organization", "source_key": "char-a", "target_key": "org-a"},
        ])

    polled = _fd_prepare_and_complete(pid, monkeypatch, build)
    proposal = polled["result"]["candidate"]["proposal"]
    # 排除候选组织 → 关系跳过；绝不静默绑定到既有同名“玄天宗”。
    confirmed = fd_ops.confirm_foundation_design(
        pid, polled["result"]["proposal_token"],
        [{**proposal["characters"][0], "kind": "character"}],
        project_model.read_project_model(pid)["model_rev"],
        relations=[{"relation_kind": "character_affiliated_with_organization",
                    "source_key": "char-a", "target_key": "org-a"}],
    )
    assert confirmed["warnings"]
    model = project_model.read_project_model(pid)
    assert model["dependencies"] == {}


def test_fd_invalid_domain_relation_candidate_rejected(isolated, monkeypatch):
    monkeypatch.setattr(fd_ops, "_retrieve_package", lambda query: EMPTY_PACKAGE)
    project = _create_project("非法关系")
    pid = project["project_id"]

    def build_bad_kind(fp):
        return _final_result([
            {"topic": "地基主题", "query": "地基主题", "package_ref": fp,
             "selected_knowledge_refs": [], "comparison": "0 命中。"},
        ], characters=[{"candidate_key": "char-a", "title": "林渊", "data": {"one_line_intro": "x"}}],
        domain_relations=[{"relation_kind": "freeform_link", "source_key": "char-a", "target_key": "char-a"}])

    def build_missing_endpoint(fp):
        return _final_result([
            {"topic": "地基主题", "query": "地基主题", "package_ref": fp,
             "selected_knowledge_refs": [], "comparison": "0 命中。"},
        ], characters=[{"candidate_key": "char-a", "title": "林渊", "data": {"one_line_intro": "x"}}],
        domain_relations=[{"relation_kind": "character_uses_system", "source_key": "char-a"}])

    for builder in (build_bad_kind, build_missing_endpoint):
        # 直接运行完整流程并断言 failed
        def on_run(request):
            import re
            rid = re.search(r"--request ([0-9a-f]+)", request.task).group(1)
            fp = _fd_round_only(rid)
            return AgentResult(status="completed", output=builder(fp), agent=FakeAgent.name)

        adapter = FakeAgent(on_run)
        _direct(adapter, monkeypatch)
        rev = project_model.read_project_model(pid)["model_rev"]
        prep = fd_ops.prepare_foundation_design(pid, "非法关系设计", rev)
        _wait(prep["request_id"])
        polled = fd_ops.get_foundation_design_request(prep["request_id"])
        assert polled["status"] == "failed"
        assert project_model.read_project_model(pid)["dependencies"] == {}


def test_fd_confirm_relation_key_never_in_proposal_rejected(isolated, monkeypatch):
    monkeypatch.setattr(fd_ops, "_retrieve_package", lambda query: EMPTY_PACKAGE)
    project = _create_project("幽灵键")
    pid = project["project_id"]

    def build(fp):
        return _final_result([
            {"topic": "地基主题", "query": "地基主题", "package_ref": fp,
             "selected_knowledge_refs": [], "comparison": "0 命中。"},
        ], characters=[
            {"candidate_key": "char-a", "title": "林渊", "material_state": "future",
             "data": {"one_line_intro": "主角"}},
        ], organizations=[
            {"candidate_key": "org-a", "title": "玄天宗", "material_state": "future",
             "data": {"type": "宗门"}},
        ], domain_relations=[
            {"relation_kind": "character_affiliated_with_organization", "source_key": "char-a", "target_key": "org-a"},
        ])

    polled = _fd_prepare_and_complete(pid, monkeypatch, build)
    proposal = polled["result"]["candidate"]["proposal"]
    items = [
        {**proposal["characters"][0], "kind": "character"},
        {**proposal["organizations"][0], "kind": "organization"},
    ]
    # 端点键从未在候选中出现 → 拒绝（不是跳过）
    with pytest.raises(fd_ops.FoundationDesignError):
        fd_ops.confirm_foundation_design(
            pid, polled["result"]["proposal_token"], items,
            project_model.read_project_model(pid)["model_rev"],
            relations=[{"relation_kind": "character_affiliated_with_organization",
                        "source_key": "ghost-key", "target_key": "org-a"}],
        )
    # 确认载荷中的关系不属于本轮候选 → 拒绝
    with pytest.raises(fd_ops.FoundationDesignError):
        fd_ops.confirm_foundation_design(
            pid, polled["result"]["proposal_token"], items,
            project_model.read_project_model(pid)["model_rev"],
            relations=[{"relation_kind": "character_uses_system",
                        "source_key": "char-a", "target_key": "org-a"}],
        )
    # 未知/跨项目显式 ref → 拒绝
    other = _create_project("外部作品")
    foreign = author_edit.create_foundation_record(
        other["project_id"], base_model_rev=0, category="character", title="外部人物",
        material_state="current", data={},
    )
    foreign_ref = foreign["model"]["change_history"][-1]["detail"]["ref"]
    with pytest.raises(fd_ops.FoundationDesignError):
        fd_ops.confirm_foundation_design(
            pid, polled["result"]["proposal_token"], items,
            project_model.read_project_model(pid)["model_rev"],
            relations=[{"relation_kind": "character_affiliated_with_organization",
                        "source_ref": foreign_ref, "target_key": "org-a"}],
        )
    assert project_model.read_project_model(pid)["dependencies"] == {}


def test_fd_duplicate_active_relation_warns_not_duplicated(isolated, monkeypatch):
    monkeypatch.setattr(fd_ops, "_retrieve_package", lambda query: EMPTY_PACKAGE)
    project = _create_project("重复防护")
    pid = project["project_id"]
    char = author_edit.create_foundation_record(
        pid, base_model_rev=0, category="character", title="林渊",
        material_state="current", data={},
    )
    char_ref = char["model"]["change_history"][-1]["detail"]["ref"]
    org = author_edit.create_foundation_record(
        pid, base_model_rev=char["model"]["model_rev"], category="organization_force",
        title="玄天宗", material_state="current", data={},
    )
    org_ref = org["model"]["change_history"][-1]["detail"]["ref"]
    author_edit.update_foundation_record(
        pid, base_model_rev=org["model"]["model_rev"], ref=char_ref,
        relations=[{"relation_kind": "character_affiliated_with_organization", "target_ref": org_ref}],
    )

    def build(fp):
        return _final_result([
            {"topic": "地基主题", "query": "地基主题", "package_ref": fp,
             "selected_knowledge_refs": [], "comparison": "0 命中。"},
        ], characters=[
            {"candidate_key": "char-a", "title": "新人物", "material_state": "future",
             "data": {"one_line_intro": "新"}},
        ], domain_relations=[
            {"relation_kind": "character_affiliated_with_organization",
             "source_ref": char_ref, "target_ref": org_ref},
        ])

    polled = _fd_prepare_and_complete(pid, monkeypatch, build)
    proposal = polled["result"]["candidate"]["proposal"]
    confirmed = fd_ops.confirm_foundation_design(
        pid, polled["result"]["proposal_token"],
        [{**proposal["characters"][0], "kind": "character"}],
        project_model.read_project_model(pid)["model_rev"],
        relations=[{"relation_kind": "character_affiliated_with_organization",
                    "source_ref": char_ref, "target_ref": org_ref}],
    )
    assert any("已存在" in warning for warning in confirmed["warnings"])
    edges = [e for e in project_model.read_project_model(pid)["dependencies"].values() if not e.get("tombstoned")]
    assert len(edges) == 1


def test_fd_authority_view_includes_bounded_existing_relations(isolated, monkeypatch):
    monkeypatch.setattr(fd_ops, "_retrieve_package", lambda query: EMPTY_PACKAGE)
    project = _create_project("视图关系")
    pid = project["project_id"]
    char = author_edit.create_foundation_record(
        pid, base_model_rev=0, category="character", title="林渊",
        material_state="current", data={},
    )
    char_ref = char["model"]["change_history"][-1]["detail"]["ref"]
    org = author_edit.create_foundation_record(
        pid, base_model_rev=char["model"]["model_rev"], category="organization_force",
        title="玄天宗", material_state="current", data={},
    )
    org_ref = org["model"]["change_history"][-1]["detail"]["ref"]
    author_edit.update_foundation_record(
        pid, base_model_rev=org["model"]["model_rev"], ref=char_ref,
        relations=[{"relation_kind": "character_affiliated_with_organization", "target_ref": org_ref}],
    )
    from operations.project_snapshot import get_project_snapshot
    view = fd_ops._authority_view(get_project_snapshot(pid))
    assert view["existing_relations"] == ["林渊 — 所属组织 → 玄天宗"]
    # 绝不暴露 ref / relation_kind 内部身份给作者面视图行文本（只有标题）
    assert all("gw2_" not in row for row in view["existing_relations"])
