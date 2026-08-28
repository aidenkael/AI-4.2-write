# -*- coding: utf-8 -*-
"""Qoder 薄桥（operations.qoder_bridge）纯文件机制测试。

覆盖：唯一 request_id、active 指针、response 读写、取消清理、失效 JSON 信封、
严格 JSON 验收（未转义引号拒绝；中文引号 / 正确转义引号接受）。
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
    rid = bridge.create_request(task="TASK", kind="story_design_propose", meta={"name": "n"}, activate_for_gowrite=True)
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


def test_create_request_does_not_activate_by_default(isolated):
    """请求存储与 /gowrite 激活分离：缺省（Direct 一律如此）不触碰 active.json。"""
    rid = bridge.create_request(task="T", kind="k")
    assert bridge.get_request(rid) is not None
    assert bridge.get_active_request_id() is None


def test_activate_request_sets_exact_active(isolated):
    """Interactive 创建 → 显式激活，active.json 精确指向该请求。"""
    rid = bridge.create_request(task="T", kind="k", activate_for_gowrite=True)
    assert bridge.get_active_request_id() == rid


def test_second_interactive_cannot_overwrite(isolated):
    """第二个 Interactive 请求不能覆盖第一个（绝不静默覆盖 active.json）。"""
    a = bridge.create_request(task="A", kind="k", activate_for_gowrite=True)
    with pytest.raises(bridge.BridgeBusyError):
        bridge.create_request(task="B", kind="k", activate_for_gowrite=True)
    assert bridge.get_active_request_id() == a
    # 忙碌时刚创建的请求文件被回滚，不会留下孤儿请求
    reqs = list((isolated / "qoder_bridge" / "requests").glob("*.json"))
    assert len(reqs) == 1


def test_activate_request_refuses_missing_or_terminal(isolated):
    assert bridge.activate_request("no-such-id") is False
    rid = bridge.create_request(task="T", kind="k")
    bridge.mark_canceled(rid)
    assert bridge.activate_request(rid) is False
    # 已取消请求不占用活跃指针（从未激活）
    assert bridge.get_active_request_id() is None


def test_clear_active_if_only_matching_id(isolated):
    """取消/终态只清与自身 id 匹配的 active 指针，绝不清别人的。"""
    a = bridge.create_request(task="A", kind="k", activate_for_gowrite=True)
    assert bridge.get_active_request_id() == a
    bridge.mark_canceled(a)
    bridge.clear_active_if(a)
    assert bridge.get_active_request_id() is None
    b = bridge.create_request(task="B", kind="k", activate_for_gowrite=True)
    assert bridge.get_active_request_id() == b
    # 旧请求的迟到清理绝不能清掉新的活跃指针
    bridge.clear_active_if(a)
    assert bridge.get_active_request_id() == b
    bridge.clear_active_if(b)
    assert bridge.get_active_request_id() is None


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


def test_set_request_task_keeps_active_pointer(isolated):
    """StoryWrite 两阶段：Stage 1 → Stage 2 原地换任务，active 指针保持同一请求。"""
    rid = bridge.create_request(
        task="STAGE1", kind="story_write_propose", activate_for_gowrite=True, phase="pending_selection",
    )
    assert bridge.get_active_request_id() == rid
    assert bridge.set_request_task(rid, "STAGE2", phase="pending_prose") is True
    req = bridge.get_request(rid)
    assert req["task"] == "STAGE2"
    assert req["phase"] == "pending_prose"
    assert req["state"] == "pending"
    assert bridge.get_active_request_id() == rid


def test_read_response_invalid_json_returns_failed_envelope(isolated):
    rid = bridge.create_request(task="T", kind="k")
    path = bridge.response_path(rid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not-json{", encoding="utf-8")
    resp = bridge.read_response(rid)
    assert resp["request_id"] == rid
    assert resp["status"] == "failed"
    assert resp["error"]


def test_read_response_rejects_unescaped_english_quotes(isolated):
    """未转义英文双引号导致的非法 JSON：严格拒绝，Go Write 不做任何猜测修复。"""
    rid = bridge.create_request(task="T", kind="k")
    raw = ('{"schema":"gowrite_response/v1","request_id":"%s","status":"completed",'
           '"result":{"objective":"为一部以"主角被两条狗咬"为核心的故事"}}') % rid
    path = bridge.response_path(rid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw, encoding="utf-8")
    resp = bridge.read_response(rid)
    assert resp["status"] == "failed"
    assert resp["error"]


def test_read_response_accepts_fullwidth_quotes(isolated):
    """中文引号 “ ” / 「 」 是合法 JSON 内容，直接接受，不需要修复。"""
    rid = bridge.create_request(task="T", kind="k")
    raw = ('{"schema":"gowrite_response/v1","request_id":"%s","status":"completed",'
           '"result":{"objective":"围绕「主角被两条狗咬」设计故事方向，读者期待“真实”。"}}') % rid
    path = bridge.response_path(rid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw, encoding="utf-8")
    resp = bridge.read_response(rid)
    assert resp["status"] == "completed"
    assert "「主角被两条狗咬」" in resp["result"]["objective"]
    assert "“真实”" in resp["result"]["objective"]


def test_read_response_accepts_escaped_english_quotes(isolated):
    """JSON 字符串内正确转义的英文双引号（\\"）是合法 JSON，直接接受。"""
    rid = bridge.create_request(task="T", kind="k")
    raw = ('{"schema":"gowrite_response/v1","request_id":"%s","status":"completed",'
           '"result":{"objective":"主角说\\"你好\\"，然后离开。"}}') % rid
    path = bridge.response_path(rid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw, encoding="utf-8")
    resp = bridge.read_response(rid)
    assert resp["status"] == "completed"
    assert resp["result"]["objective"] == "主角说\"你好\"，然后离开。"


def test_read_response_rejects_dict_output_with_failed_envelope(isolated):
    """output 中放对象（旧 /gowrite 畸形契约）→ 稳定失败信封，绝不产生 Python 类型异常。"""
    rid = bridge.create_request(task="T", kind="k")
    path = bridge.response_path(rid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema": "gowrite_response/v1", "request_id": rid,
        "status": "completed", "result": None,
        "output": {"items": [{"action": "NEW_ASSET", "type": "METHOD_SOURCE"}]},
        "error": None,
    }, ensure_ascii=False), encoding="utf-8")
    resp = bridge.read_response(rid)
    assert resp["request_id"] == rid
    assert resp["status"] == "failed"
    assert resp["result"] is None and resp["output"] is None
    assert "output" in resp["error"]
    assert isinstance(resp["error"], str) and resp["error"].strip()


def test_read_response_rejects_array_output(isolated):
    """output 中放数组同样无效（对象/数组必须放 result）。"""
    rid = bridge.create_request(task="T", kind="k")
    path = bridge.response_path(rid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema": "gowrite_response/v1", "request_id": rid,
        "status": "completed", "result": None,
        "output": [1, 2], "error": None,
    }, ensure_ascii=False), encoding="utf-8")
    resp = bridge.read_response(rid)
    assert resp["status"] == "failed"
    assert "output" in resp["error"]


def test_read_response_survives_structured_result(isolated):
    """规范化信封：结构化 result 对象原样通过桥。"""
    rid = bridge.create_request(task="T", kind="k")
    payload = {"items": [{"action": "NEW_ASSET", "name": "方法书", "type": "METHOD_SOURCE"}]}
    bridge.write_response(rid, result=payload)
    resp = bridge.read_response(rid)
    assert resp["status"] == "completed"
    assert resp["result"] == payload
    assert resp["output"] is None


def test_read_response_survives_textual_output(isolated):
    """规范化信封：纯文本 output 原样通过桥。"""
    rid = bridge.create_request(task="T", kind="k")
    bridge.write_response(rid, output="普通文本结果")
    resp = bridge.read_response(rid)
    assert resp["status"] == "completed"
    assert resp["output"] == "普通文本结果"
    assert resp["result"] is None


def test_read_response_rejects_invalid_field_types(isolated):
    """result/output/error/status 类型非法或被拒绝的状态 → 稳定失败信封。"""
    cases = [
        {"status": "completed", "result": []},       # result 是数组
        {"status": "completed", "result": "text"},   # result 是字符串
        {"status": "completed", "output": 123},       # output 是数字
        {"status": "completed", "error": 123},        # error 是数字
        {"status": "maybe"},                          # 生产流程未使用的状态
    ]
    for extra in cases:
        rid = bridge.create_request(task="T", kind="k")
        path = bridge.response_path(rid)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema": "gowrite_response/v1", "request_id": rid,
            "status": "completed", "result": None, "output": None, "error": None,
            **extra,
        }
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        resp = bridge.read_response(rid)
        assert resp["status"] == "failed", extra
        assert isinstance(resp["error"], str) and resp["error"]


def test_read_response_wrong_schema_or_request_id_rejected(isolated):
    rid = bridge.create_request(task="T", kind="k")
    path = bridge.response_path(rid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema": "other/v1", "request_id": rid, "status": "completed", "result": {"a": 1},
    }, ensure_ascii=False), encoding="utf-8")
    assert bridge.read_response(rid)["status"] == "failed"
    path.write_text(json.dumps({
        "schema": "gowrite_response/v1", "request_id": "other-id", "status": "completed", "result": {"a": 1},
    }, ensure_ascii=False), encoding="utf-8")
    resp = bridge.read_response(rid)
    assert resp["status"] == "failed"
    assert resp["request_id"] == rid


def test_read_response_completed_without_payload_rejected(isolated):
    """completed 必须携带有效载荷（result 对象或非空 output 文本）。"""
    rid = bridge.create_request(task="T", kind="k")
    path = bridge.response_path(rid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema": "gowrite_response/v1", "request_id": rid,
        "status": "completed", "result": None, "output": "", "error": None,
    }, ensure_ascii=False), encoding="utf-8")
    resp = bridge.read_response(rid)
    assert resp["status"] == "failed"
    assert "有效载荷" in resp["error"]


def test_read_response_failed_without_error_rejected(isolated):
    """failed 必须携带可用的 error。"""
    rid = bridge.create_request(task="T", kind="k")
    path = bridge.response_path(rid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema": "gowrite_response/v1", "request_id": rid,
        "status": "failed", "result": None, "output": None, "error": None,
    }, ensure_ascii=False), encoding="utf-8")
    resp = bridge.read_response(rid)
    assert resp["status"] == "failed"
    assert "error" in resp["error"]


def test_response_result_text_shared_helper(isolated):
    """共享 helper：result 对象 → JSON 文本；output 纯文本 → 原样；两者皆无 → BridgeProtocolError。"""
    rid = bridge.create_request(task="T", kind="k")
    payload = {"items": [{"action": "NEW_ASSET"}]}
    bridge.write_response(rid, result=payload)
    text = bridge.response_result_text(bridge.read_response(rid))
    assert json.loads(text) == payload

    bridge.write_response(rid, output="  纯文本  ")
    assert bridge.response_result_text(bridge.read_response(rid)) == "  纯文本  "

    bridge.write_response(rid, result={})
    with pytest.raises(bridge.BridgeProtocolError):
        bridge.response_result_text(bridge.read_response(rid))


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
    rid = bridge.create_request(task="T", kind="k", activate_for_gowrite=True)
    bridge.write_response(rid, result={"ok": 1})
    bridge.cleanup_request(rid)
    assert bridge.get_request(rid) is None
    assert not bridge.response_path(rid).exists()
    assert bridge.get_active_request_id() is None


def test_cleanup_request_keeps_other_active(isolated):
    a = bridge.create_request(task="A", kind="k", activate_for_gowrite=True)
    bridge.mark_canceled(a)
    bridge.clear_active_if(a)
    b = bridge.create_request(task="B", kind="k", activate_for_gowrite=True)
    # 旧请求文件/指针的终态清理（幂等重放）不得影响新的活跃请求
    bridge.cleanup_request(a)
    assert bridge.get_active_request_id() == b


def test_is_expired_uses_expires_at(isolated):
    rid = bridge.create_request(task="T", kind="k")
    req = bridge.get_request(rid)
    assert bridge.is_expired(req) is False
    req["expires_at"] = "2000-01-01T00:00:00+00:00"
    assert bridge.is_expired(req) is True
