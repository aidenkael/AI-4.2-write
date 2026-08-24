# -*- coding: utf-8 -*-
"""Agent discovery tests：只使用 fake/local probes，绝不执行模型。"""
from pathlib import Path

from agents.deepseek_harness import DeepSeekHarnessAdapter
from agents.qoder import QoderAdapter


class Probe:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_qoder_discovery_normalizes_cn_and_unavailable_login(tmp_path, monkeypatch):
    command_dir = tmp_path / ".qoder" / "commands"
    command_dir.mkdir(parents=True)
    (command_dir / "gowrite.md").write_text("read .qoder_bridge request_id", encoding="utf-8")
    monkeypatch.setattr("agents.qoder.Path.home", classmethod(lambda _cls: tmp_path))
    cli = tmp_path / "qoder.cmd"
    cli.write_text("@echo off", encoding="utf-8")
    monkeypatch.setattr("agents.qoder._default_cli", lambda: str(cli))
    monkeypatch.setattr("agents.qoder._resolve_cmd", lambda path: [path])
    monkeypatch.setattr("agents.qoder.shutil.which", lambda name: str(cli) if name == "qoder" else None)

    def fake_run(cmd, **_kwargs):
        joined = " ".join(cmd)
        if "ide --version" in joined:
            return Probe("1.24.2\n")
        if "status -o json" in joined:
            return Probe('{"logged_in":false,"version":"1.1.25","allow_byok":0}')
        if "--version" in joined:
            return Probe("1.1.25\n")
        raise AssertionError(f"unexpected probe: {cmd}")

    monkeypatch.setattr("agents.qoder.subprocess.run", fake_run)
    env = QoderAdapter.discover()
    assert env["installed"] is True
    assert env["interactive"]["available"] is True
    assert env["interactive"]["command_ready"] is True
    assert env["interactive"]["bridge_ready"] is True
    assert env["direct"]["auth_status"] == "not_authenticated"
    assert env["direct"]["available"] is False
    assert env["direct"]["execution_profiles"][0]["models"] == []


def test_qoder_discovery_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr("agents.qoder.Path.home", classmethod(lambda _cls: tmp_path))
    monkeypatch.setattr("agents.qoder._default_cli", lambda: (_ for _ in ()).throw(RuntimeError("missing")))
    monkeypatch.setattr("agents.qoder.shutil.which", lambda _name: None)
    env = QoderAdapter.discover()
    assert env["installed"] is False
    assert env["direct"]["available"] is False
    assert env["errors"]


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
