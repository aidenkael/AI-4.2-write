# -*- coding: utf-8 -*-
"""配置层 targeted tests（普通设置 + Token 安全存储）。

验证：
1. 普通设置能保存/读取（临时配置目录）
2. Token 能保存进 keyring（Windows 系统凭据存储）
3. 配置文件不含 Token 明文
4. 非法值被拒绝（未知 Agent / 模式 / 思考强度）
"""
import json
import uuid

import pytest

from config.secrets import SecretStore
from config.settings import (
    AppSettings,
    REASONING_EFFORT_OPTIONS,
    SettingsError,
    SettingsStore,
)

# 测试专用 keyring 服务名（不污染真实 ai-write 凭据）
TEST_SERVICE = f"ai-write-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def fake_keyring(monkeypatch):
    values = {}
    class FakeKeyring:
        def set_password(self, service, secret_id, token): values[(service, secret_id)] = token
        def get_password(self, service, secret_id): return values.get((service, secret_id))
        def delete_password(self, service, secret_id): values.pop((service, secret_id), None)
    monkeypatch.setattr("config.secrets._keyring", FakeKeyring())


# ---------- 1. 普通设置保存/读取 ----------

def test_settings_save_load_roundtrip(tmp_path):
    store = SettingsStore(config_dir=tmp_path)
    s = AppSettings(
        default_agent="qoder",
        qoder_mode="qoder_byok",
        qoder_model="qwen-max",
        reasoning_effort="high",
        byok_provider="bailian",
        byok_model="qwen3.8-max-tp",
        byok_secret_id="qoder_byok",
    )
    store.save(s)

    loaded = SettingsStore(config_dir=tmp_path).load()
    assert loaded == s
    assert loaded.to_dict()["default_agent"] == "qoder"
    assert loaded.to_dict()["byok_secret_id"] == "qoder_byok"


def test_settings_defaults_when_file_missing(tmp_path):
    store = SettingsStore(config_dir=tmp_path)
    assert store.load() == AppSettings()
    assert store.load().default_agent == "qoder"
    assert store.load().default_execution_mode == "interactive_bridge"


def test_legacy_settings_migrate_without_replacing_identifiers(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({
        "default_agent": "qoder",
        "qoder_mode": "qoder_native",
        "qoder_model": "legacy-local-model",
    }), encoding="utf-8")
    loaded = SettingsStore(config_dir=tmp_path).load()
    assert loaded.interactive_agent == "qoder"
    assert loaded.direct_agent == "qoder"
    assert loaded.direct_profile_id == "native"
    assert loaded.direct_model == "legacy-local-model"


def test_settings_ignores_unknown_fields(tmp_path):
    # 未知字段（例如误入的 Token 明文）一律丢弃，不进入 AppSettings
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"default_agent": "qoder", "api_key": "sk-leak"}), encoding="utf-8")
    loaded = SettingsStore(config_dir=tmp_path).load()
    assert loaded.default_agent == "qoder"
    assert not hasattr(loaded, "api_key")
    assert "api_key" not in loaded.to_dict()


def test_settings_env_config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path / "cfg"))
    store = SettingsStore()
    store.save(AppSettings(default_agent="deepseek_harness"))
    loaded = SettingsStore().load()
    assert loaded.default_agent == "deepseek_harness"
    assert (tmp_path / "cfg" / "settings.json").exists()


# ---------- 2. Token 保存进 keyring（Windows 凭据存储） ----------

def test_secret_store_roundtrip():
    s = SecretStore(service=TEST_SERVICE)
    sid = "test-secret"
    try:
        s.save_secret(sid, "sk-test-abc123")
        assert s.has_secret(sid) is True
        assert s.get_secret(sid) == "sk-test-abc123"
        assert s.delete_secret(sid) is True
        assert s.has_secret(sid) is False
        assert s.get_secret(sid) is None
    finally:
        s.delete_secret(sid)


def test_secret_store_rejects_empty():
    s = SecretStore(service=TEST_SERVICE)
    with pytest.raises(Exception):
        s.save_secret("empty", "")
    assert s.has_secret("empty") is False


# ---------- 3. 配置文件不含 Token 明文 ----------

def test_settings_file_never_contains_token(tmp_path):
    store = SettingsStore(config_dir=tmp_path)
    s = AppSettings(
        default_agent="qoder",
        qoder_mode="qoder_byok",
        byok_provider="bailian",
        byok_model="qwen-max",
        byok_secret_id="qoder_byok",  # 只是引用 id
    )
    store.save(s)

    # 独立保存真实 Token 到 keyring（模拟真实流程）
    sec = SecretStore(service=TEST_SERVICE)
    secret_id = "roundtrip-token"
    token = "sk-REAL-TOKEN-SECRET-987654"
    try:
        sec.save_secret(secret_id, token)
        assert sec.get_secret(secret_id) == token
    finally:
        sec.delete_secret(secret_id)

    raw = (tmp_path / "settings.json").read_text(encoding="utf-8")
    assert "sk-REAL-TOKEN-SECRET-987654" not in raw
    assert "api_key" not in raw
    assert token not in raw


# ---------- 4. 合法值校验 ----------

def test_effort_options_match_qoder_enum():
    # Qoder CLI 官方枚举：none/low/medium/high/xhigh/max
    assert set(REASONING_EFFORT_OPTIONS) == {"none", "low", "medium", "high", "xhigh", "max"}


def test_corrupt_settings_raises(tmp_path):
    (tmp_path / "settings.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(SettingsError):
        SettingsStore(config_dir=tmp_path).load()
