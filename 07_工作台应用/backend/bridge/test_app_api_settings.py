# -*- coding: utf-8 -*-
"""Bridge 设置接口 targeted tests（统一 {ok, data, error} 合同 + 无 Token 明文）。"""
import json
import uuid

import pytest

from bridge.app_api import AppApi
from config.secrets import SecretStore
from operations import settings as ops

TEST_SERVICE = f"ai-write-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def bridge(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(ops, "SecretStore", lambda: SecretStore(service=TEST_SERVICE))
    return AppApi()


def _json_str(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def test_get_agent_settings_contract(bridge):
    resp = bridge.get_agent_settings()
    assert resp["ok"] is True
    assert resp["error"] is None
    data = resp["data"]
    assert "settings" in data and "agents" in data and "byok" in data
    ids = {a["id"] for a in data["agents"]}
    assert ids == {"deepseek_harness", "qoder"}


def test_get_agent_options_contract(bridge):
    resp = bridge.get_agent_options()
    assert resp["ok"] is True
    assert "reasoning_effort_options" in resp["data"]


def test_save_agent_settings_contract(bridge):
    resp = bridge.save_agent_settings({
        "default_agent": "qoder",
        "qoder_mode": "qoder_native",
        "qoder_model": "Qwen3.8-Max",
        "reasoning_effort": "medium",
    })
    assert resp["ok"] is True
    assert resp["data"]["settings"]["default_agent"] == "qoder"

    bad = bridge.save_agent_settings({"default_agent": "codex"})
    assert bad["ok"] is False
    assert bad["error"]["code"] == "SETTINGS_ERROR"


def test_byok_secret_never_returns_plaintext(bridge):
    token = "sk-BRIDGE-SECRET-98765"
    resp = bridge.save_byok_secret(token)
    assert resp["ok"] is True
    assert resp["data"]["has_secret"] is True
    assert token not in _json_str(resp)  # 保存返回值无明文

    # 保存后读取任何设置接口都不含明文
    for method in (bridge.get_agent_settings, bridge.get_agent_options):
        out = _json_str(method())
        assert token not in out, f"{method.__name__} 泄漏 Token 明文"

    # 测试连接（BYOK 未配置 provider/model 时不真实调用）也不含明文
    conn = bridge.test_agent_connection({
        "agent": "qoder", "qoder_mode": "qoder_byok",
    })
    assert conn["ok"] is True
    assert token not in _json_str(conn)

    # 删除后状态立即未配置
    resp2 = bridge.delete_byok_secret()
    assert resp2["ok"] is True
    assert resp2["data"]["has_secret"] is False
    assert bridge.get_agent_settings()["data"]["byok"]["has_secret"] is False


def test_test_agent_connection_contract(bridge):
    resp = bridge.test_agent_connection({"agent": "qoder", "qoder_mode": "qoder_byok"})
    assert resp["ok"] is True
    assert resp["data"]["status"] == "not_configured"
    assert resp["data"]["agent"] == "qoder"
