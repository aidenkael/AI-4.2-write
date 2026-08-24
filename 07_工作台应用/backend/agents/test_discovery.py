# -*- coding: utf-8 -*-
"""Agent discovery tests：只使用 fake/local probes，绝不执行模型。"""
from pathlib import Path

from agents.deepseek_harness import DeepSeekHarnessAdapter
from agents.qoder import QoderAdapter, _default_cli, _discover_desktop


class Probe:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_qoder_desktop_discovery_uses_install_path_not_cli(tmp_path, monkeypatch):
    install = tmp_path / "Qoder"
    desktop = install / "Qoder.exe"
    launcher = install / "bin" / "code.cmd"
    launcher.parent.mkdir(parents=True)
    desktop.write_text("desktop", encoding="utf-8")
    launcher.write_text("@echo off", encoding="utf-8")
    monkeypatch.setattr("agents.qoder._desktop_candidates", lambda: [str(desktop)])
    monkeypatch.setattr(
        "agents.qoder.subprocess.run",
        lambda cmd, **_kwargs: Probe("1.24.2\nbuild\nx64\n") if cmd == [str(launcher), "--version"] else Probe(returncode=1),
    )

    result = _discover_desktop()

    assert result == {
        "installed": True,
        "status": "installed",
        "path": str(desktop),
        "launcher_path": str(launcher),
        "version": "1.24.2",
        "error": None,
    }


def test_qoder_discovery_separates_cn_desktop_from_legacy_cli(tmp_path, monkeypatch):
    command_dir = tmp_path / ".qoder" / "commands"
    command_dir.mkdir(parents=True)
    (command_dir / "gowrite.md").write_text("read .qoder_bridge request_id", encoding="utf-8")
    monkeypatch.setattr("agents.qoder.Path.home", classmethod(lambda _cls: tmp_path))
    desktop = tmp_path / "Qoder.exe"
    desktop.write_text("desktop", encoding="utf-8")
    cli = tmp_path / "qodercli.cmd"
    cli.write_text("@echo off", encoding="utf-8")
    monkeypatch.setattr("agents.qoder._discover_desktop", lambda: {
        "installed": True,
        "status": "installed",
        "path": str(desktop),
        "launcher_path": str(tmp_path / "code.cmd"),
        "version": "1.24.2",
        "error": None,
    })
    monkeypatch.setattr("agents.qoder._default_cli", lambda: str(cli))
    monkeypatch.setattr("agents.qoder._resolve_cmd", lambda path: [path])

    def fake_run(cmd, **_kwargs):
        joined = " ".join(cmd)
        if "--help" in joined:
            return Probe("--print --list-models\n")
        if "status -o json" in joined:
            return Probe('{"logged_in":false,"version":"1.1.25","allow_byok":0}')
        if "--version" in joined:
            return Probe("1.1.25\n")
        raise AssertionError(f"unexpected probe: {cmd}")

    monkeypatch.setattr("agents.qoder.subprocess.run", fake_run)
    env = QoderAdapter.discover()
    assert env["installed"] is True
    assert env["available"] is True
    assert env["desktop"]["path"] == str(desktop)
    assert env["desktop"]["version"] == "1.24.2"
    assert env["cli"]["path"] == str(cli)
    assert env["cli"]["version"] == "1.1.25"
    assert env["cli"]["kind"] == "legacy_qodercli"
    assert env["desktop"]["path"] != env["cli"]["path"]
    assert env["interactive"]["available"] is True
    assert env["interactive"]["command_ready"] is True
    assert env["interactive"]["bridge_ready"] is True
    assert env["direct"]["auth_status"] == "not_authenticated"
    assert env["direct"]["available"] is False
    assert env["direct"]["execution_profiles"][0]["models"] == []


def test_qoder_discovery_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr("agents.qoder.Path.home", classmethod(lambda _cls: tmp_path))
    monkeypatch.setattr("agents.qoder._discover_desktop", lambda: {
        "installed": False, "status": "not_detected", "path": None,
        "launcher_path": None, "version": None, "error": None,
    })
    monkeypatch.setattr("agents.qoder._default_cli", lambda: (_ for _ in ()).throw(RuntimeError("missing")))
    env = QoderAdapter.discover()
    assert env["installed"] is False
    assert env["direct"]["available"] is False
    assert env["errors"]


def test_qoder_command_dispatcher_is_not_reported_as_cli(tmp_path, monkeypatch):
    dispatcher = tmp_path / "qoder.cmd"
    dispatcher.write_text("set BRIDGE_DISPATCHER=%USERPROFILE%\\.qoder\\entry\\qoder.cmd", encoding="utf-8")
    legacy = tmp_path / "qodercli.cmd"
    legacy.write_text("@echo off", encoding="utf-8")
    monkeypatch.delenv("QODER_CLI_BIN", raising=False)
    monkeypatch.delenv("QODERCLI_PATH", raising=False)
    monkeypatch.setattr("agents.qoder.Path.home", classmethod(lambda _cls: tmp_path))
    monkeypatch.setattr(
        "agents.qoder.shutil.which",
        lambda name: str(dispatcher) if name == "qoder" else str(legacy) if name == "qodercli" else None,
    )
    monkeypatch.setattr("agents.qoder._resolve_cmd", lambda path: [path])
    monkeypatch.setattr(
        "agents.qoder.subprocess.run",
        lambda cmd, **_kwargs: Probe("--print --list-models\n") if "--help" in cmd else Probe(),
    )

    assert _default_cli() == str(legacy)


def test_qoder_command_without_desktop_does_not_enable_bridge(tmp_path, monkeypatch):
    command_dir = tmp_path / ".qoder" / "commands"
    command_dir.mkdir(parents=True)
    (command_dir / "gowrite.md").write_text("read .qoder_bridge request_id", encoding="utf-8")
    monkeypatch.setattr("agents.qoder.Path.home", classmethod(lambda _cls: tmp_path))
    monkeypatch.setattr("agents.qoder._discover_desktop", lambda: {
        "installed": False, "status": "not_detected", "path": None,
        "launcher_path": None, "version": None, "error": None,
    })
    monkeypatch.setattr("agents.qoder._default_cli", lambda: (_ for _ in ()).throw(RuntimeError("missing")))

    env = QoderAdapter.discover()

    assert env["interactive"]["command_ready"] is True
    assert env["interactive"]["available"] is False
    assert env["interactive"]["bridge_ready"] is False


def test_harness_discovery_profiles_and_truthful_bridge(tmp_path, monkeypatch):
    home = tmp_path / ".dsh"
    home.mkdir()
    (home / ".credentials.yaml").write_text("configured: true", encoding="utf-8")
    monkeypatch.setenv("DSH_HOME", str(home))
    monkeypatch.setattr("agents.deepseek_harness._default_launch", lambda: ["node", "dsh.js"])

    def fake_run(cmd, **_kwargs):
        joined = " ".join(cmd)
        if "--version" in joined:
            return Probe("0.1.0-test\n")
        if "--profile headless --dump-config" in joined:
            return Probe("- id: agent-default-model\n  name: adapter\n  config:\n    provider: local-provider\n    model: local-model\n- id: next\n")
        if "--profile web --dump-config" in joined:
            return Probe("- id: commands\n  name: '@deepseek-ai/dsh-commands'\n")
        raise AssertionError(f"unexpected probe: {cmd}")

    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_args): return None

    monkeypatch.setattr("agents.deepseek_harness.subprocess.run", fake_run)
    monkeypatch.setattr("agents.deepseek_harness.urllib.request.urlopen", lambda *_args, **_kwargs: Response())
    env = DeepSeekHarnessAdapter.discover()
    assert env["version"] == "0.1.0-test"
    assert env["direct"]["available"] is True
    profile = env["direct"]["execution_profiles"][0]
    assert profile["provider_id"] == "local-provider"
    assert profile["models"][0]["id"] == "local-model"
    assert profile["model_selection"] == "managed"
    assert env["interactive"]["available"] is True
    assert env["interactive"]["command_ready"] is False
    assert env["interactive"]["bridge_ready"] is False


def test_harness_discovery_unavailable(monkeypatch):
    monkeypatch.setattr("agents.deepseek_harness._default_launch", lambda: (_ for _ in ()).throw(RuntimeError("missing")))
    env = DeepSeekHarnessAdapter.discover()
    assert env["installed"] is False
    assert env["direct"]["execution_profiles"] == []
