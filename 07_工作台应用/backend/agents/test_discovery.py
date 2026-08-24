from agents.deepseek_harness import DeepSeekHarnessAdapter
from agents.qoder import QoderAdapter


def test_qoder_discovery_keeps_desktop_and_cli_separate(monkeypatch):
    monkeypatch.setattr("agents.qoder._discover_desktop", lambda: {"installed": True, "status": "installed", "path": "desktop", "launcher_path": "desktop", "version": "1.24.2", "error": None})
    monkeypatch.setattr("agents.qoder._default_cli", lambda: "qoderclicn")
    def run(cmd, **_):
        if "--version" in cmd: return type("R", (), {"returncode": 0, "stdout": "1.1.28\n", "stderr": ""})()
        return type("R", (), {"returncode": 0, "stdout": "MODEL\nactual\n", "stderr": ""})()
    monkeypatch.setattr("agents.qoder.subprocess.run", run)
    env = QoderAdapter.discover()
    assert env["desktop"]["version"] == "1.24.2"
    assert env["cli"]["kind"] == "qoder_cn"
    assert env["direct"]["execution_profiles"][0]["models"][0]["id"] == "actual"


def test_harness_discovery_unavailable(monkeypatch):
    monkeypatch.setattr("agents.deepseek_harness._default_launch", lambda: (_ for _ in ()).throw(RuntimeError("missing")))
    assert DeepSeekHarnessAdapter.discover()["installed"] is False
