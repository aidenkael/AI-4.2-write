from bridge.app_api import AppApi
from operations import settings as ops


def test_settings_bridge_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(ops, "registry_discover_all", lambda: [{"agent_id": "qoder", "installed": True, "direct": {"available": True, "auth_status": "authenticated", "model_selection": "selectable", "models": [{"id": "real", "selectable": True}]}}])
    api = AppApi()
    assert api.get_agent_settings()["ok"] is True
    response = api.save_agent_settings({"default_execution_mode": "direct", "direct_agent": "qoder", "direct_model": "real"})
    assert response["ok"] is True and response["data"]["settings"]["direct_model"] == "real"


def test_install_command_bridge(tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "install_qoder_command", lambda: {"installed_paths": [str(tmp_path / "gowrite.md")], "command_ready": True, "status": "installed", "restart_required": False, "errors": []})
    monkeypatch.setattr(ops, "registry_discover_all", lambda: [{"agent_id": "qoder", "interactive": {"bridge_ready": True, "command_ready": True}}])
    response = AppApi().install_or_repair_interactive_command({"agent": "qoder"})
    assert response["ok"] is True and response["data"]["command_ready"] is True
    assert response["data"]["status"] == "installed"
