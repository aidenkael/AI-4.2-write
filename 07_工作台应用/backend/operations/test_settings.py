from operations import settings as ops


def test_interactive_install_refreshes_qoder_discovery(monkeypatch, tmp_path):
    installed = {"installed_paths": [str(tmp_path / ".qoder" / "commands" / "gowrite.md")], "command_ready": True, "status": "installed", "restart_required": False, "errors": []}
    discovery = [{"agent_id": "qoder", "interactive": {"bridge_ready": True, "command_ready": True}}]
    monkeypatch.setattr(ops, "install_qoder_command", lambda: installed)
    monkeypatch.setattr(ops, "registry_discover_all", lambda: discovery)

    result = ops.install_or_repair_interactive_command({"agent": "qoder"})

    assert result["status"] == "installed"
    assert result["discovery"] == discovery


def test_interactive_install_does_not_claim_bridge_when_desktop_not_ready(monkeypatch):
    monkeypatch.setattr(ops, "install_qoder_command", lambda: {"installed_paths": ["C:/Users/test/.qoder/commands/gowrite.md"], "command_ready": True, "status": "installed", "restart_required": False, "errors": []})
    monkeypatch.setattr(ops, "registry_discover_all", lambda: [{"agent_id": "qoder", "interactive": {"bridge_ready": False, "command_ready": True}}])

    try:
        ops.install_or_repair_interactive_command({"agent": "qoder"})
    except ops.SettingsOpError as exc:
        assert "交互桥" in str(exc)
    else:
        raise AssertionError("must not claim bridge readiness without Desktop detection")


def _agents():
    return [{"agent_id": "qoder", "installed": True, "available": True, "direct": {"available": True, "auth_status": "authenticated", "model_selection": "selectable", "models": [{"id": "real", "display_name": "Real", "selectable": True}], "custom_models": [{"id": "route-a", "selectable": True}]}}, {"agent_id": "deepseek_harness", "installed": True, "available": True, "direct": {"available": True, "auth_status": "configured", "model_selection": "selectable", "models": [{"id": "flash", "selectable": True}], "custom_models": [{"id": "harness:plan:flash", "selectable": True}]}}]


def test_persists_independent_modes_and_only_identifiers(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path)); monkeypatch.setattr(ops, "registry_discover_all", _agents)
    saved = ops.save_agent_settings({"default_execution_mode": "direct", "interactive_agent": "qoder", "direct_agent": "qoder", "direct_model": "real"})
    assert saved["direct_model"] == "real" and "qoder_model" not in saved
    reloaded = ops.get_agent_settings()["settings"]
    assert reloaded["interactive_agent"] == "qoder" and reloaded["direct_model"] == "real"


def test_disappeared_model_is_rejected_not_replaced(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path)); monkeypatch.setattr(ops, "registry_discover_all", _agents)
    try: ops.save_agent_settings({"default_execution_mode": "direct", "direct_agent": "qoder", "direct_model": "gone"})
    except ops.SettingsOpError: pass
    else: raise AssertionError("missing model must not be silently substituted")


def test_connection_check_is_local_only(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path)); monkeypatch.setattr(ops, "registry_discover_all", _agents)
    assert ops.test_agent_connection({"agent": "qoder", "profile_id": "qoder_cn", "model": "real"})["status"] == "ok"


def test_native_and_custom_models_are_mutually_exclusive(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path)); monkeypatch.setattr(ops, "registry_discover_all", _agents)
    saved = ops.save_agent_settings({"default_execution_mode": "direct", "direct_agent": "deepseek_harness", "direct_custom_model": "harness:plan:flash"})
    assert saved["direct_model"] is None and saved["direct_custom_model"] == "harness:plan:flash"
    try: ops.save_agent_settings({"default_execution_mode": "direct", "direct_agent": "qoder", "direct_model": "real", "direct_custom_model": "route-a"})
    except ops.SettingsOpError: pass
    else: raise AssertionError("two selections must not persist")


def test_non_selectable_model_is_rejected(tmp_path, monkeypatch):
    def discovered():
        return [{"agent_id": "other", "direct": {"available": True, "model_selection": "selectable", "models": [{"id": "shown", "selectable": False}]}}]
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path)); monkeypatch.setattr(ops, "registry_discover_all", discovered)
    try: ops._validate_direct("other", "shown")
    except ops.SettingsOpError: pass
    else: raise AssertionError("non-selectable model must be rejected")


def test_custom_selection_is_agent_agnostic_and_stale_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path)); monkeypatch.setattr(ops, "registry_discover_all", _agents)
    saved = ops.save_agent_settings({"default_execution_mode": "direct", "direct_agent": "qoder", "direct_custom_model": "route-a"})
    assert saved["direct_custom_model"] == "route-a"
    try: ops.save_agent_settings({"default_execution_mode": "direct", "direct_agent": "qoder", "direct_custom_model": "gone"})
    except ops.SettingsOpError: pass
    else: raise AssertionError("stale custom model must be rejected")


def test_settings_mount_does_not_force_full_discovery(tmp_path, monkeypatch):
    """打开设置页不应每次挂载都重跑昂贵发现：第二次读取复用 last-known 快照。"""
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path))
    calls = {"n": 0}
    def counting_discovery():
        calls["n"] += 1
        return _agents()
    monkeypatch.setattr(ops, "registry_discover_all", counting_discovery)
    ops.reset_discovery_cache()

    first = ops.get_agent_settings()
    second = ops.get_agent_settings()
    assert calls["n"] == 1, "第二次 get_agent_settings 必须复用缓存，不再执行发现"
    assert first["agents"] == second["agents"]
    assert second["discovery"]["source"] == "cache"
    assert second["discovery"]["discovered_at"]


def test_settings_mount_shows_saved_config_without_rediscovery(tmp_path, monkeypatch):
    """保存后重开设置（remount 等价）仍显示已保存配置；未强制重跑发现。"""
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path)); monkeypatch.setattr(ops, "registry_discover_all", _agents)
    ops.reset_discovery_cache()
    ops.save_agent_settings({"default_execution_mode": "direct", "direct_agent": "qoder", "direct_model": "real"})

    calls = {"n": 0}
    def counting_discovery():
        calls["n"] += 1
        return _agents()
    monkeypatch.setattr(ops, "registry_discover_all", counting_discovery)

    reopened = ops.get_agent_settings()
    assert reopened["settings"]["direct_model"] == "real"
    assert reopened["settings"]["default_execution_mode"] == "direct"
    # 已保存模型在未重新检测时不得被当作不可用：原样重存应成功
    saved_again = ops.save_agent_settings({"default_execution_mode": "direct", "direct_agent": "qoder", "direct_model": "real"})
    assert saved_again["direct_model"] == "real"


def test_explicit_discover_forces_refresh(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path))
    calls = {"n": 0}
    def counting_discovery():
        calls["n"] += 1
        return _agents()
    monkeypatch.setattr(ops, "registry_discover_all", counting_discovery)
    ops.reset_discovery_cache()

    ops.get_agent_settings()
    ops.discover_agent_environment()
    assert calls["n"] == 2, "显式“重新检测”必须强制重跑发现并更新快照"
    assert ops.get_agent_settings()["discovery"]["source"] == "cache"
