# -*- coding: utf-8 -*-
"""get_active_author_operation() 恢复 API 测试（App 协调器 remount/reload 真相源）。

覆盖：
- Interactive pending（已激活 /gowrite）可恢复，且只暴露非机密事实；
- Direct pending 且 in-process worker 仍在 → running 可恢复；
- Direct 请求存在但 worker 已不存在（进程重启）→ fail closed（orphaned），
  绝不显示假 running，且请求被清理；
- 无待办操作 → None；
- 活跃指针指向已不存在的请求 → 清掉陈旧指针。
不调用任何模型。
"""
import json
import threading
import time
from pathlib import Path

import pytest

from operations import author_operation as ao
from operations import execution_tasks
from operations import qoder_bridge as bridge


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: tmp_path / "qoder_bridge")
    fresh = execution_tasks.ExecutionTaskManager()
    monkeypatch.setattr(execution_tasks, "manager", fresh)
    return tmp_path


def _interactive_request(project_id="proj-a", kind="story_write_propose", phase="pending_selection"):
    return bridge.create_request(
        task="SECRET_TASK_TEXT", kind=kind,
        meta={
            "project_id": project_id,
            "execution": {"execution_mode": "interactive_bridge", "agent_id": "qoder", "model": None},
        },
        phase=phase,
        activate_for_gowrite=True,
    )


def _direct_request(project_id="proj-b", kind="story_plan_propose"):
    return bridge.create_request(
        task="SECRET_TASK_TEXT", kind=kind,
        meta={
            "project_id": project_id,
            "execution": {"execution_mode": "direct", "agent_id": "deepseek_harness", "model": "m1"},
        },
        activate_for_gowrite=False,
    )


def test_interactive_pending_resumable(isolated):
    rid = _interactive_request()
    facts = ao.get_active_author_operation()
    assert facts is not None
    assert facts["request_id"] == rid
    assert facts["kind"] == "story_write"
    assert facts["project_id"] == "proj-a"
    assert facts["execution_mode"] == "interactive_bridge"
    assert facts["agent_id"] == "qoder"
    assert facts["model"] is None  # 交互模式未经执行验证：不编造模型
    assert facts["phase"] == "pending_selection"
    assert facts["state"] == "pending"
    assert "再次执行 /gowrite" in facts["message"] or "正在选择" in facts["message"]
    # 绝不暴露任务文本 / token / 凭据 / 输出
    assert facts.get("task") is None
    assert "SECRET_TASK_TEXT" not in json.dumps(facts, ensure_ascii=False)


def test_story_write_pending_prose_message(isolated):
    rid = _interactive_request(phase="pending_prose")
    facts = ao.get_active_author_operation()
    assert facts["phase"] == "pending_prose"
    assert "再次执行 /gowrite" in facts["message"]


def test_no_active_returns_none(isolated):
    assert ao.get_active_author_operation() is None


def test_direct_running_resumable(isolated):
    rid = _direct_request()
    gate = threading.Event()

    def _worker():
        gate.wait(5)

    assert execution_tasks.manager.start(rid, _worker, execution={"execution_mode": "direct"})
    facts = ao.get_active_author_operation()
    assert facts is not None
    assert facts["request_id"] == rid
    assert facts["kind"] == "story_plan"
    assert facts["execution_mode"] == "direct"
    assert facts["agent_id"] == "deepseek_harness"
    assert facts["model"] == "m1"  # Direct 模型机械已知
    assert facts["state"] == "running"
    assert "后台 AI 正在执行" in facts["message"]
    gate.set()
    execution_tasks.manager.join(rid, 5)


def test_direct_orphaned_fails_closed(isolated):
    """进程重启后 worker 不存在：fail closed（orphaned），绝不显示假 running。"""
    rid = _direct_request()
    facts = ao.get_active_author_operation()
    assert facts is not None
    assert facts["request_id"] == rid
    assert facts["state"] == "orphaned"
    assert "失效" in facts["message"]
    # 孤儿请求被清理，不会残留
    assert bridge.get_request(rid) is None
    # 清理后无待办
    assert ao.get_active_author_operation() is None


def test_stale_active_pointer_cleared(isolated):
    """active 指针指向已不存在/已终态的请求：清掉陈旧指针，不返回假任务。"""
    rid = _interactive_request()
    bridge.cleanup_request(rid)
    assert ao.get_active_author_operation() is None
    assert bridge.get_active_request_id() is None


def test_material_kind_normalization(isolated):
    rid = bridge.create_request(
        task="t", kind="material_classify_propose",
        meta={"execution": {"execution_mode": "interactive_bridge", "agent_id": "qoder", "model": None}},
        activate_for_gowrite=True,
    )
    facts = ao.get_active_author_operation()
    assert facts["kind"] == "material_classify"
    assert facts["state"] == "pending"


def test_canceled_interactive_cleared(isolated):
    rid = _interactive_request()
    bridge.mark_canceled(rid)
    bridge.clear_active_if(rid)
    assert ao.get_active_author_operation() is None
