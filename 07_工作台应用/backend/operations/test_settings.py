from operations import settings as ops


def _agents():
    return [{"agent_id": "qoder", "installed": True, "available": True, "direct": {"auth_status": "authenticated", "execution_profiles": [{"id": "qoder_cn", "available": True, "model_selection": "selectable", "models": [{"id": "real", "display_name": "Real", "selectable": True}]}]}}, {"agent_id": "deepseek_harness", "installed": True, "available": True, "direct": {"auth_status": "configured", "execution_profiles": [{"id": "headless", "available": True, "model_selection": "managed", "models": []}]}}]


def test_persists_independent_modes_and_only_identifiers(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path)); monkeypatch.setattr(ops, "registry_discover_all", _agents)
    saved = ops.save_agent_settings({"default_execution_mode": "direct", "interactive_agent": "qoder", "direct_agent": "qoder", "direct_profile_id": "qoder_cn", "direct_model": "real", "reasoning_effort": "high"})
    assert saved["direct_model"] == "real" and "qoder_model" not in saved
    reloaded = ops.get_agent_settings()["settings"]
    assert reloaded["interactive_agent"] == "qoder" and reloaded["direct_profile_id"] == "qoder_cn"


def test_disappeared_model_is_rejected_not_replaced(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path)); monkeypatch.setattr(ops, "registry_discover_all", _agents)
    try: ops.save_agent_settings({"default_execution_mode": "direct", "direct_agent": "qoder", "direct_profile_id": "qoder_cn", "direct_model": "gone"})
    except ops.SettingsOpError: pass
    else: raise AssertionError("missing model must not be silently substituted")


def test_connection_check_is_local_only(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path)); monkeypatch.setattr(ops, "registry_discover_all", _agents)
    assert ops.test_agent_connection({"agent": "qoder", "profile_id": "qoder_cn", "model": "real"})["status"] == "ok"
