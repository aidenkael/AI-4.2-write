# -*- coding: utf-8 -*-
"""Focused tests: 日常 AI (Direct AI) settings are independent and secret-safe."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai import runner as semantic_ai  # noqa: E402
from config.secrets import SecretStore  # noqa: E402
from config.settings import AppSettings, SettingsStore  # noqa: E402
import operations.settings as settings_ops  # noqa: E402


@pytest.fixture()
def isolated_config(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(config_dir))
    store: dict = {}
    monkeypatch.setattr(SecretStore, "save_secret", lambda self, sid, token: store.__setitem__(sid, token))
    monkeypatch.setattr(SecretStore, "has_secret", lambda self, sid: sid in store)
    monkeypatch.setattr(SecretStore, "get_secret", lambda self, sid: store.get(sid))
    monkeypatch.setattr(SecretStore, "delete_secret", lambda self, sid: store.pop(sid, None) is not None)
    return config_dir, store


def test_semantic_settings_roundtrip_and_secret_isolation(isolated_config):
    config_dir, store = isolated_config
    assert settings_ops.get_semantic_ai_settings()["configured"] is False

    saved = settings_ops.save_semantic_ai_settings({
        "semantic_ai_base_url": "https://api.example.com/v1",
        "semantic_ai_model": "fake-model",
        "api_key": "sk-test-123",
    })
    assert saved["configured"] is True
    assert saved["has_api_key"] is True
    # The plaintext key never appears in any bridge-facing payload.
    assert "sk-test-123" not in json.dumps(saved, ensure_ascii=False)
    # ...nor in the persisted (trackable) settings file.
    settings_file = config_dir / semantic_ai.SEMANTIC_SETTINGS_FILENAME
    assert settings_file.exists()
    assert "sk-test-123" not in settings_file.read_text(encoding="utf-8")
    # It only lives in the (fake) OS credential store.
    assert store[semantic_ai.SEMANTIC_API_KEY_SECRET_ID] == "sk-test-123"


def test_semantic_settings_rejects_invalid_values(isolated_config):
    with pytest.raises(settings_ops.SettingsOpError):
        settings_ops.save_semantic_ai_settings({
            "semantic_ai_base_url": "ftp://invalid", "semantic_ai_model": "m",
        })
    with pytest.raises(settings_ops.SettingsOpError):
        settings_ops.save_semantic_ai_settings({
            "semantic_ai_base_url": "https://api.example.com/v1", "semantic_ai_model": "",
        })


def test_semantic_settings_independent_from_agent_settings(isolated_config):
    config_dir, _store = isolated_config
    settings_ops.save_semantic_ai_settings({
        "semantic_ai_base_url": "https://api.example.com/v1",
        "semantic_ai_model": "fake-model",
    })
    # Agent execution settings keep their own file and own fields.
    agent = SettingsStore(config_dir).load()
    assert isinstance(agent, AppSettings)
    agent_payload = json.dumps(agent.to_dict(), ensure_ascii=False)
    assert "semantic_ai" not in agent_payload
    assert "fake-model" not in agent_payload
    # And the semantic settings file carries no Agent execution choices.
    semantic_payload = (config_dir / semantic_ai.SEMANTIC_SETTINGS_FILENAME).read_text(encoding="utf-8")
    assert "direct_agent" not in semantic_payload
    assert "interactive_agent" not in semantic_payload


def test_runner_requires_complete_configuration(isolated_config):
    with pytest.raises(semantic_ai.SemanticAiConfigError):
        semantic_ai.require_semantic_ai()
    settings_ops.save_semantic_ai_settings({
        "semantic_ai_base_url": "https://api.example.com/v1",
        "semantic_ai_model": "fake-model",
    })
    # Still incomplete without the API key.
    with pytest.raises(semantic_ai.SemanticAiConfigError):
        semantic_ai.require_semantic_ai()
    settings_ops.save_semantic_ai_settings({
        "semantic_ai_base_url": "https://api.example.com/v1",
        "semantic_ai_model": "fake-model",
        "api_key": "sk-test-456",
    })
    config, key = semantic_ai.require_semantic_ai()
    assert config.model == "fake-model" and key == "sk-test-456"
