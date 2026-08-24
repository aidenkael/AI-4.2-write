import json
import sys
import threading
import time

from agents.base import AgentRequest
from agents.qoder import QoderAdapter, _default_cli, _parse_models


def test_cn_cli_is_the_only_candidate(monkeypatch, tmp_path):
    cli = tmp_path / "qoderclicn.exe"; cli.write_text("", encoding="utf-8")
    monkeypatch.setenv("QODER_CN_CLI_PATH", str(cli))
    monkeypatch.setattr("agents.qoder.subprocess.run", lambda cmd, **_: type("R", (), {"returncode": 0, "stdout": "--print --list-models --model --cwd --output-format", "stderr": ""})())
    assert _default_cli() == str(cli)


def test_dynamic_cn_model_parser():
    assert [row["id"] for row in _parse_models("MODEL\nAuto\nReal Model\n")] == ["Auto", "Real Model"]


def test_direct_command_uses_cn_contract(tmp_path):
    adapter = QoderAdapter(launch=[sys.executable, "-c", "import sys; print('|'.join(sys.argv[1:]))"])
    result = adapter.run(AgentRequest(task="task", cwd=str(tmp_path), model="actual-model", reasoning_effort="high"))
    assert result.status == "completed"
    for item in ("-p", "-o", "json", "--cwd", str(tmp_path), "--model", "actual-model", "--reasoning-effort", "high"):
        assert item in result.output.split("|")


def test_json_result_and_error_handling():
    ok = json.dumps({"type": "result", "result": "done"})
    failure = json.dumps({"is_error": True, "errors": ["bad"]})
    assert QoderAdapter._extract_cli_result(ok) == "done"
    assert QoderAdapter._extract_cli_error(failure) == "bad"


def test_cancel(tmp_path):
    adapter = QoderAdapter(launch=[sys.executable, "-c", "import time; time.sleep(60)"], timeout=120)
    holder = {}
    thread = threading.Thread(target=lambda: holder.setdefault("result", adapter.run(AgentRequest(task="x", cwd=str(tmp_path)))))
    thread.start(); time.sleep(0.5)
    assert adapter.cancel() is True
    thread.join(10)
    assert holder["result"].status == "cancelled"
