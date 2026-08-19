# -*- coding: utf-8 -*-
"""Qoder 薄桥（operations.qoder_bridge）纯文件机制测试。

覆盖：唯一 request_id、active 指针、response 读写、取消清理、失效 JSON 信封。
不涉及任何模型调用；业务链测试见 test_new_project.py。
"""
import json
from pathlib import Path

import pytest

from operations import qoder_bridge as bridge


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: tmp_path / "qoder_bridge")
    return tmp_path


def test_create_request_writes_files_and_active(isolated):
    rid = bridge.create_request(task="TASK", kind="story_design_propose", meta={"name": "n"})
    assert len(rid) == 32
    req = bridge.get_request(rid)
    assert req["request_id"] == rid
    assert req["task"] == "TASK"
    assert req["kind"] == "story_design_propose"
    assert req["state"] == "pending"
    assert req["meta"]["name"] == "n"
    resp_parts = Path(req["response_path"]).parts
    assert "responses" in resp_parts and resp_parts[-1] == f"{rid}.json"
    assert bridge.get_active_request_id() == rid


def test_latest_request_becomes_active(isolated):
    a = bridge.create_request(task="A", kind="k")
    b = bridge.create_request(task="B", kind="k")
    assert a != b
    assert bridge.get_active_request_id() == b


def test_get_request_missing_returns_none(isolated):
    assert bridge.get_request("no-such-id") is None
    assert bridge.get_active_request_id() is None


def test_read_response_missing_returns_none(isolated):
    rid = bridge.create_request(task="T", kind="k")
    assert bridge.read_response(rid) is None


def test_write_and_read_response(isolated):
    rid = bridge.create_request(task="T", kind="k")
    bridge.write_response(rid, result={"ok": 1})
    resp = bridge.read_response(rid)
    assert resp["request_id"] == rid
    assert resp["status"] == "completed"
    assert resp["result"] == {"ok": 1}


def test_read_response_invalid_json_returns_failed_envelope(isolated):
    rid = bridge.create_request(task="T", kind="k")
    path = bridge.response_path(rid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not-json{", encoding="utf-8")
    resp = bridge.read_response(rid)
    assert resp["request_id"] == rid
    assert resp["status"] == "failed"
    assert resp["error"]


def test_mark_canceled_deletes_response(isolated):
    rid = bridge.create_request(task="T", kind="k")
    bridge.write_response(rid, result={"ok": 1})
    assert bridge.mark_canceled(rid) is True
    assert bridge.get_request(rid)["state"] == "canceled"
    assert not bridge.response_path(rid).exists()
    # 已取消的请求再次取消：幂等（文件仍在时返回 True，被清理后返回 False）
    bridge.cleanup_request(rid)
    assert bridge.mark_canceled(rid) is False


def test_cleanup_request_removes_files_and_active(isolated):
    rid = bridge.create_request(task="T", kind="k")
    bridge.write_response(rid, result={"ok": 1})
    bridge.cleanup_request(rid)
    assert bridge.get_request(rid) is None
    assert not bridge.response_path(rid).exists()
    assert bridge.get_active_request_id() is None


def test_cleanup_request_keeps_other_active(isolated):
    a = bridge.create_request(task="A", kind="k")
    b = bridge.create_request(task="B", kind="k")
    bridge.cleanup_request(a)
    assert bridge.get_active_request_id() == b


def test_is_expired_uses_expires_at(isolated):
    rid = bridge.create_request(task="T", kind="k")
    req = bridge.get_request(rid)
    assert bridge.is_expired(req) is False
    req["expires_at"] = "2000-01-01T00:00:00+00:00"
    assert bridge.is_expired(req) is True
