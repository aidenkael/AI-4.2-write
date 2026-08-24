from bridge.app_api import AppApi
from operations import settings as ops


def test_settings_bridge_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(ops, "registry_discover_all", lambda: [{"agent_id": "qoder", "installed": True, "direct": {"auth_status": "authenticated", "execution_profiles": [{"id": "qoder_cn", "available": True, "model_selection": "selectable", "models": [{"id": "real"}]}]}}])
    api = AppApi()
    assert api.get_agent_settings()["ok"] is True
    response = api.save_agent_settings({"default_execution_mode": "direct", "direct_agent": "qoder", "direct_profile_id": "qoder_cn", "direct_model": "real"})
    assert response["ok"] is True and response["data"]["settings"]["direct_model"] == "real"


def test_install_command_bridge(tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "install_qoder_command", lambda: {"installed_paths": [str(tmp_path / "gowrite.md")], "command_ready": True, "errors": []})
    response = AppApi().install_or_repair_interactive_command({"agent": "qoder"})
    assert response["ok"] is True and response["data"]["command_ready"] is True
