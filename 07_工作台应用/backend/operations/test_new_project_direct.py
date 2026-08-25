# -*- coding: utf-8 -*-
"""新建作品 Direct 执行 targeted tests：非阻塞、精确路由、取消/晚完成、知识绑定。"""
import json
import re
import sys
import threading
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))

import project_workspace  # noqa: E402

from operations import new_project as np_ops  # noqa: E402
from operations import qoder_bridge as bridge  # noqa: E402
from operations import agent_runner  # noqa: E402
from operations import execution_tasks  # noqa: E402
from agents.base import AgentRequest, AgentResult  # noqa: E402
from config.settings import SettingsStore, AppSettings  # noqa: E402

VALID_RESULT = {
    "semantic_interpretation": {
        "scope": "story_design", "objective": "设计方向。",
        "knowledge_needs": [], "selected_bkp_ids": [], "package_ref": "",
        "assumptions": [],
    },
    "model_output": {
        "stance": ["story_engine"],
        "proposal": "候选方向。", "work_direction": "作品方向。", "reader_promise": "读者期待。",
        "hard_constraints": [], "open_space": [], "unknowns": [],
    },
}


class FakeAgent:
    name = "fake_np_agent"

    def __init__(self, output=json.dumps(VALID_RESULT, ensure_ascii=False), on_run=None, gate=None):
        self.output = output
        self.on_run = on_run
        self.gate = gate
        self.calls = []
        self.cancel_called = 0
        self.done = threading.Event()

    def run(self, request):
        self.calls.append(request)
        try:
            if self.gate is not None:
                self.gate.wait(10)
            if self.on_run is not None:
                return self.on_run(request)
            return AgentResult(status="completed", output=self.output, agent=self.name)
        finally:
            self.done.set()

    def cancel(self):
        self.cancel_called += 1
        return True


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    projects_root = tmp_path / "03_作品工程"
    projects_root.mkdir()
    monkeypatch.setattr(project_workspace, "get_projects_root", lambda: projects_root)
    monkeypatch.setattr(np_ops, "get_proposals_root", lambda: tmp_path / "proposals")
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: tmp_path / "qoder_bridge")
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path / "cfg"))
    return projects_root


@pytest.fixture(autouse=True)
def _fresh_exec_task_manager(monkeypatch):
    fresh = execution_tasks.ExecutionTaskManager()
    monkeypatch.setattr(np_ops, "_exec_task_manager", fresh)
    return fresh


def _direct(adapter, monkeypatch, model="native-model-1", custom_model=None):
    SettingsStore().save(AppSettings(
        default_execution_mode="direct", interactive_agent="qoder",
        direct_agent=adapter.name, direct_model=model, direct_custom_model=custom_model,
    ))
    monkeypatch.setattr(agent_runner, "_build_adapter",
                        lambda: (adapter, AgentRequest(task="", model=model, custom_model=custom_model)))


def _wait(request_id, timeout=5.0):
    np_ops._exec_task_manager.join(request_id, timeout)


def test_direct_non_blocking(isolated, monkeypatch):
    adapter = FakeAgent()
    _direct(adapter, monkeypatch)
    prepared = np_ops.prepare_new_project(name="直连作品", idea="想法")
    assert prepared["status"] == "task_prepared"
    assert prepared["execution_mode"] == "direct"
    # 非阻塞：prepare 返回时任务可能仍在运行或已完成，但绝不在 prepare 内阻塞等待
    _wait(prepared["request_id"])
    result = np_ops.get_new_project_request(prepared["request_id"])
    assert result["status"] == "completed"
    assert result["result"]["candidate"]["work_direction"] == "作品方向。"


def test_direct_exact_route(isolated, monkeypatch):
    adapter = FakeAgent()
    _direct(adapter, monkeypatch, model="native-model-1")
    prepared = np_ops.prepare_new_project(name="路由作品", idea="想法")
    request = bridge.get_request(prepared["request_id"])
    meta = request["meta"]
    assert meta["execution"]["execution_mode"] == "direct"
    assert meta["execution"]["agent_id"] == "fake_np_agent"
    assert meta["execution"]["model"] == "native-model-1"
    _wait(prepared["request_id"])


def test_direct_preconfirm_zero_formal_write(isolated, monkeypatch):
    adapter = FakeAgent()
    _direct(adapter, monkeypatch)
    prepared = np_ops.prepare_new_project(name="零写作品", idea="想法")
    _wait(prepared["request_id"])
    np_ops.get_new_project_request(prepared["request_id"])
    children = [p for p in isolated.iterdir() if p.is_dir()]
    assert children == [], "Direct prepare + 候选生成不得创建正式作品"


def test_direct_cancel_late_result_discarded(isolated, monkeypatch):
    gate = threading.Event()
    adapter = FakeAgent(gate=gate)
    _direct(adapter, monkeypatch)
    prepared = np_ops.prepare_new_project(name="取消作品", idea="想法")
    assert np_ops.cancel_new_project_request(prepared["request_id"])["status"] == "canceled"
    gate.set()
    _wait(prepared["request_id"])
    result = np_ops.get_new_project_request(prepared["request_id"])
    assert result["status"] == "canceled"


def test_direct_empty_needs_retrieval_zero(isolated, monkeypatch):
    calls = []
    monkeypatch.setattr(np_ops, "_retrieve_package", lambda q: (calls.append(q), None)[1])
    adapter = FakeAgent()
    _direct(adapter, monkeypatch)
    prepared = np_ops.prepare_new_project(name="零检索作品", idea="想法")
    _wait(prepared["request_id"])
    result = np_ops.get_new_project_request(prepared["request_id"])
    assert result["status"] == "completed"
    assert calls == [], "空 knowledge_needs 不得调用 KnowledgeRetrieve"


def test_direct_needs_retrieval_exact_package(isolated, monkeypatch):
    package = types.SimpleNamespace(
        status="OK",
        hits=[types.SimpleNamespace(
            rank=1, book_id="book_a", book_title="book_a", source_anchor="K001",
            source="knowledge/cards.md", statement="A 卡", scope="范围", boundary="边界",
            confidence="中", evidence=["chapters/x.md#L1"], relevance_reason="test",
        )],
        gaps=[], candidate_count=1,
    )
    monkeypatch.setattr(np_ops, "_retrieve_package", lambda q: package)

    def on_run(request):
        query = "信息层次"
        rid = re.search(r"--request ([0-9a-f]{32})", request.task).group(1)
        shown = np_ops.execute_request_scoped_retrieval(query, rid)
        fp = np_ops._package_fingerprint(shown)
        out = dict(VALID_RESULT)
        out["semantic_interpretation"] = dict(out["semantic_interpretation"])
        out["semantic_interpretation"]["knowledge_needs"] = [query]
        out["semantic_interpretation"]["selected_bkp_ids"] = ["book_a/K001"]
        out["semantic_interpretation"]["package_ref"] = fp
        return AgentResult(status="completed", output=json.dumps(out, ensure_ascii=False), agent="fake")

    adapter = FakeAgent(on_run=on_run)
    _direct(adapter, monkeypatch)
    prepared = np_ops.prepare_new_project(name="检索作品", idea="想法")
    _wait(prepared["request_id"])
    result = np_ops.get_new_project_request(prepared["request_id"])
    assert result["status"] == "completed"
    assert result["result"]["knowledge"]["selected_count"] == 1
