# -*- coding: utf-8 -*-
"""设置操作层 targeted tests。

验证：
- get_agent_settings：设置 + Agent 真实状态/能力 + BYOK has_secret（无明文）
- get_agent_options：Qoder 自带模型 / BYOK provider-model 动态读取
- save_agent_settings：合法保存 + 非法值拒绝
- save/delete_byok_secret：keyring 存取 + 状态立即变化
- test_agent_connection：deepseek_harness / qoder 自带走真实 Adapter；
  qoder BYOK 未配置 Token 时不真实调用（返回 not_configured）
"""
import uuid

import pytest

from config.secrets import SecretStore
from operations import settings as ops

TEST_SERVICE = f"ai-write-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def config_dir(tmp_path, monkeypatch):
    """把普通设置目录指到临时目录；keyring 用测试服务名。"""
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(ops, "SecretStore", lambda: SecretStore(service=TEST_SERVICE))
    return tmp_path


# ---------- get_agent_settings ----------

def test_get_agent_settings_shape(config_dir):
    data = ops.get_agent_settings()
    assert set(data.keys()) == {"settings", "agents", "byok"}
    # 两个真实 Agent 都出现，无假数据
    ids = {a["id"] for a in data["agents"]}
    assert ids == {"deepseek_harness", "qoder"}
    for a in data["agents"]:
        assert "available" in a and "capabilities" in a and "error" in a
    # 默认 byok 未配置
    assert data["byok"]["has_secret"] is False


def test_get_agent_settings_no_token_plaintext(config_dir):
    ops.save_byok_secret("sk-SECRET-PLAINTEXT-111")
    data = ops.get_agent_settings()
    blob = str(data)
    assert "sk-SECRET-PLAINTEXT-111" not in blob
    assert data["byok"]["has_secret"] is True


# ---------- get_agent_options（动态读取，不硬编码） ----------

def test_get_agent_options_dynamic(config_dir):
    data = ops.get_agent_options()
    assert "reasoning_effort_options" in data
    assert set(data["reasoning_effort_options"]) == {"none", "low", "medium", "high", "xhigh", "max"}
    # 动态读取失败时不抛异常，只带 error 字段（CLI/SDK 可用时为真实列表）
    assert "qoder_models_error" in data
    assert "byok_error" in data


# ---------- save_agent_settings ----------

def test_save_agent_settings_valid(config_dir):
    saved = ops.save_agent_settings({
        "default_agent": "qoder",
        "qoder_mode": "qoder_native",
        "qoder_model": "Qwen3.8-Max",
        "reasoning_effort": "high",
    })
    assert saved["default_agent"] == "qoder"
    assert saved["qoder_model"] == "Qwen3.8-Max"
    assert saved["reasoning_effort"] == "high"

    # 读回一致
    data = ops.get_agent_settings()
    assert data["settings"]["default_agent"] == "qoder"
    assert data["settings"]["qoder_model"] == "Qwen3.8-Max"


def test_save_agent_settings_invalid_agent(config_dir):
    with pytest.raises(ops.SettingsOpError):
        ops.save_agent_settings({"default_agent": "codex"})


def test_save_agent_settings_invalid_mode(config_dir):
    with pytest.raises(ops.SettingsOpError):
        ops.save_agent_settings({"default_agent": "qoder", "qoder_mode": "qoder_evil"})


def test_save_agent_settings_invalid_effort(config_dir):
    with pytest.raises(ops.SettingsOpError):
        ops.save_agent_settings({"default_agent": "qoder", "reasoning_effort": "insane"})


def test_save_agent_settings_preserves_secret_ref(config_dir):
    ops.save_byok_secret("sk-keep-ref")
    ops.save_agent_settings({"default_agent": "deepseek_harness"})
    data = ops.get_agent_settings()
    assert data["settings"]["byok_secret_id"] is not None
    assert data["byok"]["has_secret"] is True


# ---------- save / delete_byok_secret ----------

def test_save_delete_byok_secret(config_dir):
    r = ops.save_byok_secret("sk-b-y-o-k-123")
    assert r["has_secret"] is True
    assert r["secret_id"] is not None

    data = ops.get_agent_settings()
    assert data["byok"]["has_secret"] is True
    assert data["settings"]["byok_secret_id"] is not None

    r2 = ops.delete_byok_secret()
    assert r2["has_secret"] is False
    data2 = ops.get_agent_settings()
    assert data2["byok"]["has_secret"] is False
    assert data2["settings"]["byok_secret_id"] is None


def test_save_byok_secret_empty(config_dir):
    with pytest.raises(ops.SettingsOpError):
        ops.save_byok_secret("   ")


# ---------- test_agent_connection ----------

def test_connection_qoder_byok_not_configured(config_dir):
    """未配置 Token：不真实调用，明确返回 not_configured。"""
    r = ops.test_agent_connection({
        "agent": "qoder",
        "qoder_mode": "qoder_byok",
        "byok_provider": "bailian",
        "byok_model": "qwen-max",
    })
    assert r["status"] == "not_configured"
    assert "Token" in r["message"]


def test_connection_unknown_agent(config_dir):
    with pytest.raises(ops.SettingsOpError):
        ops.test_agent_connection({"agent": "codex"})


def test_connection_deepseek_real(config_dir):
    """走现有 Adapter 真实执行（无副作用任务 + 临时目录）。"""
    try:
        from agents.deepseek_harness import _default_launch
        _default_launch()
    except RuntimeError as exc:
        pytest.skip(f"DeepSeek Harness 不可用：{exc}")
    r = ops.test_agent_connection({"agent": "deepseek_harness"})
    assert r["status"] in ("ok", "failed")
    assert r["agent"] == "deepseek_harness"


def test_connection_qoder_native_real(config_dir):
    """Qoder 自带：走现有 QoderAdapter CLI 路径真实执行。"""
    try:
        from agents.qoder import _default_cli
        _default_cli()
    except RuntimeError as exc:
        pytest.skip(f"Qoder CLI 不可用：{exc}")
    r = ops.test_agent_connection({
        "agent": "qoder",
        "qoder_mode": "qoder_native",
        "qoder_model": None,
    })
    assert r["status"] in ("ok", "failed")
    assert r["agent"] == "qoder"
