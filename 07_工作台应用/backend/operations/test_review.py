# -*- coding: utf-8 -*-
"""作品检查 targeted tests：确定性只读面、单次 Agent 检查、检索绑定、零写、取消/晚完成。"""
import hashlib
import json
import sys
import threading
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))

import project_workspace  # noqa: E402

from operations import review as rv_ops  # noqa: E402
from operations import qoder_bridge as bridge  # noqa: E402
from operations import agent_runner  # noqa: E402
from operations import execution_tasks  # noqa: E402
from agents.base import AgentRequest, AgentResult  # noqa: E402
from config.settings import SettingsStore, AppSettings  # noqa: E402

REVIEW_JSON = json.dumps({
    "semantic_interpretation": {
        "objective": "检查第 1 章连续性。",
        "knowledge_needs": [],
        "selected_bkp_ids": [],
        "package_ref": "",
        "assumptions": [],
    },
    "review": {
        "summary": "整体连贯，有一处时间线风险。",
        "issues": [
            {"severity": "priority", "title": "时间线不清", "detail": "夜晚到清晨的过渡缺少交代。",
             "evidence": "第 1 章", "suggestion": "补一句时间过渡。"},
            {"severity": "watch", "title": "命名可统一", "detail": "专有名词出现两种写法。",
             "evidence": None, "suggestion": "统一写法。"},
        ],
        "strengths": ["氛围描写克制有力。"],
    },
}, ensure_ascii=False)


class FakeReviewAdapter:
    name = "fake_review_agent"

    def __init__(self, output=REVIEW_JSON, on_run=None, gate=None):
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
                result = self.on_run(request)
                if result is not None:
                    return result
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
    monkeypatch.setattr(rv_ops, "get_review_root", lambda: tmp_path / ".review")
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path / "cfg"))
    return projects_root


@pytest.fixture()
def fake_bridge(tmp_path, monkeypatch):
    bridge_root = tmp_path / ".bridge"
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: bridge_root)
    return bridge_root


@pytest.fixture(autouse=True)
def _fresh_exec_task_manager(monkeypatch):
    fresh = execution_tasks.ExecutionTaskManager()
    monkeypatch.setattr(rv_ops, "_exec_task_manager", fresh)
    return fresh


@pytest.fixture()
def real_project(isolated):
    from project_workspace import create_project
    created = create_project(name="检查作品", author_intent={
        "work_direction": "方向", "reader_promise": "期待",
        "hard_constraints": [], "open_space": [],
    })
    project_dir = Path(created["project_dir"])
    chapter_text = "雨丝敲在车窗上。\n\n林砚靠在窗边，望向雾中的旧城区。"
    (project_dir / "03_正文").mkdir(exist_ok=True)
    (project_dir / "03_正文" / "第001章.md").write_text(chapter_text, encoding="utf-8")
    index_path = project_dir / "_工作台状态" / "accepted_text_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["entries"].append({
        "chapter_number": 1,
        "chapter_path": "03_正文/第001章.md",
        "scene_ref": "scene-1",
        "sequence": 1,
        "start_char": 0,
        "end_char": len(chapter_text),
        "content_sha256": hashlib.sha256(chapter_text.encode("utf-8")).hexdigest(),
    })
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"project_id": created["project_id"], "name": "检查作品", "project_dir": project_dir}


def _direct_settings(adapter, monkeypatch, model="native-model-1"):
    SettingsStore().save(AppSettings(
        default_execution_mode="direct", interactive_agent="qoder",
        direct_agent=adapter.name, direct_model=model, direct_custom_model=None,
    ))
    monkeypatch.setattr(agent_runner, "_build_adapter",
                        lambda: (adapter, AgentRequest(task="", model=model, custom_model=None)))


def _wait(request_id, timeout=5.0):
    rv_ops._exec_task_manager.join(request_id, timeout)


# ---------- 确定性只读面（无模型） ----------

def test_surface_read_only(real_project):
    surface = rv_ops.get_review_surface(real_project["project_id"])
    assert surface["project_id"] == real_project["project_id"]
    assert surface["chapters"] == [{"chapter_number": 1}]
    assert surface["latest_chapter_number"] == 1
    assert surface["has_accepted_prose"] is True


def test_surface_zero_write(real_project):
    index_path = real_project["project_dir"] / "_工作台状态" / "accepted_text_index.json"
    before = index_path.read_bytes()
    rv_ops.get_review_surface(real_project["project_id"])
    assert index_path.read_bytes() == before


def test_prepare_no_accepted_prose_rejected(isolated):
    from project_workspace import create_project
    created = create_project(name="空作品", author_intent={
        "work_direction": "方向", "reader_promise": "期待", "hard_constraints": [], "open_space": [],
    })
    with pytest.raises(rv_ops.ReviewError):
        rv_ops.prepare_review(created["project_id"])


# ---------- 显式检查：单次 Agent 运行、零写、取消 ----------

def test_explicit_review_one_agent_turn(real_project, fake_bridge, monkeypatch):
    adapter = FakeReviewAdapter()
    _direct_settings(adapter, monkeypatch)
    prepared = rv_ops.prepare_review(real_project["project_id"])
    _wait(prepared["request_id"])
    result = rv_ops.get_review_request(prepared["request_id"])
    assert result["status"] == "completed"
    report = result["result"]
    assert report["summary"] == "整体连贯，有一处时间线风险。"
    assert len(report["issues"]) == 2
    assert report["chapter_number"] == 1
    # 单次 Agent 运行
    assert len(adapter.calls) == 1


def test_review_zero_canon_write(real_project, fake_bridge, monkeypatch):
    index_path = real_project["project_dir"] / "_工作台状态" / "accepted_text_index.json"
    state_path = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    before_index = index_path.read_bytes()
    before_state = state_path.read_bytes()
    adapter = FakeReviewAdapter()
    _direct_settings(adapter, monkeypatch)
    prepared = rv_ops.prepare_review(real_project["project_id"])
    _wait(prepared["request_id"])
    rv_ops.get_review_request(prepared["request_id"])
    assert index_path.read_bytes() == before_index
    assert state_path.read_bytes() == before_state


def test_review_empty_needs_retrieval_zero(real_project, fake_bridge, monkeypatch):
    calls = []
    monkeypatch.setattr(rv_ops, "_retrieve_package", lambda q: (calls.append(q), None)[1])
    adapter = FakeReviewAdapter()
    _direct_settings(adapter, monkeypatch)
    prepared = rv_ops.prepare_review(real_project["project_id"])
    _wait(prepared["request_id"])
    result = rv_ops.get_review_request(prepared["request_id"])
    assert result["status"] == "completed"
    assert calls == [], "空 knowledge_needs 不得调用 KnowledgeRetrieve"


def test_review_cancel_late_result_discarded(real_project, fake_bridge, monkeypatch):
    gate = threading.Event()
    adapter = FakeReviewAdapter(gate=gate)
    _direct_settings(adapter, monkeypatch)
    prepared = rv_ops.prepare_review(real_project["project_id"])
    # 取消（worker 仍阻塞在 gate）
    canceled = rv_ops.cancel_review_request(prepared["request_id"])
    assert canceled["status"] == "canceled"
    # 放行 worker 完成（晚完成）
    gate.set()
    _wait(prepared["request_id"])
    # 晚完成结果已被丢弃：请求保持 canceled，绝不产生可接受报告
    result = rv_ops.get_review_request(prepared["request_id"])
    assert result["status"] == "canceled"


def test_review_interactive_mode_rejected(real_project, fake_bridge, monkeypatch):
    SettingsStore().save(AppSettings(default_execution_mode="interactive_bridge", interactive_agent="qoder"))
    with pytest.raises(rv_ops.ReviewError):
        rv_ops.prepare_review(real_project["project_id"])


# ---------- 知识选择绑定（P0） ----------

def _fake_hit(book_id, anchor, statement):
    return types.SimpleNamespace(
        rank=1, book_id=book_id, book_title=book_id, source_anchor=anchor,
        source="knowledge/cards.md", statement=statement, scope="范围", boundary="边界",
        confidence="中", evidence=["chapters/x.md#L1"], relevance_reason="test",
    )


def _fake_package(hits):
    return types.SimpleNamespace(status="OK", hits=list(hits), gaps=[], candidate_count=len(hits))


def test_review_needs_retrieval_exact_package(real_project, fake_bridge, monkeypatch):
    import re
    package = _fake_package([_fake_hit("book_a", "K001", "A 卡")])
    monkeypatch.setattr(rv_ops, "_retrieve_package", lambda q: package)

    def on_run(request):
        query = "写作连续性"
        # request_id 内嵌在任务文本的检索命令中（--request <hex>）
        rid = re.search(r"--request ([0-9a-f]{32})", request.task).group(1)
        shown = rv_ops.execute_request_scoped_retrieval(query, rid)
        fp = rv_ops._package_fingerprint(shown)
        out = json.dumps({
            "semantic_interpretation": {
                "objective": "检查", "knowledge_needs": [query],
                "selected_bkp_ids": ["book_a/K001"], "package_ref": fp, "assumptions": [],
            },
            "review": {"summary": "用到了写作知识", "issues": [], "strengths": []},
        }, ensure_ascii=False)
        return AgentResult(status="completed", output=out, agent="fake")

    adapter = FakeReviewAdapter(on_run=on_run)
    _direct_settings(adapter, monkeypatch)
    prepared = rv_ops.prepare_review(real_project["project_id"])
    _wait(prepared["request_id"])
    result = rv_ops.get_review_request(prepared["request_id"])
    assert result["status"] == "completed"
    assert result["result"]["knowledge"]["selected_count"] == 1
