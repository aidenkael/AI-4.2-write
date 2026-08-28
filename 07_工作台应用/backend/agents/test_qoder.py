import json
import sys
import threading
import time

from agents import qoder
from agents.base import AgentRequest
from agents.qoder import QoderAdapter, _default_cli, _parse_models


def test_cn_cli_is_the_only_candidate(monkeypatch, tmp_path):
    cli = tmp_path / "qoderclicn.exe"; cli.write_text("", encoding="utf-8")
    monkeypatch.setenv("QODER_CN_CLI_PATH", str(cli))
    monkeypatch.setattr("agents.qoder.subprocess.run", lambda cmd, **_: type("R", (), {"returncode": 0, "stdout": "--print --list-models --model --cwd --output-format", "stderr": ""})())
    assert _default_cli() == str(cli)


def test_dynamic_cn_model_parser():
    assert [row["id"] for row in _parse_models("MODEL\nAuto\nReal Model\n")] == ["Auto", "Real Model"]


def test_parser_v1129_catalog_splits_native_and_custom():
    """已安装 Qoder CN v1.1.29 的真实 --list-models 输出形状（fixture）。

    最后一行是自定义路由：`名称 (Provider) (provider/model)`，其 modelID 是
    尾部 `provider/model`（与 ~/.qoder-cn/settings.json 的 model.name 一致）；
    其余为内置模型。每个可选项的 id 就是 CLI --model 接受的精确标识。
    """
    fixture = """MODEL
Auto
Qwen3.8-Max
DeepSeek-V4-Pro
DeepSeek-V4-Flash
Qwen-3.8-Max (QwenCloud-China) (qwencloud-cn/qwen3.8-max-tp)
"""
    rows = _parse_models(fixture)
    natives = [r for r in rows if r["kind"] == "native"]
    customs = [r for r in rows if r["kind"] == "custom"]
    assert [r["id"] for r in natives] == ["Auto", "Qwen3.8-Max", "DeepSeek-V4-Pro", "DeepSeek-V4-Flash"]
    assert len(customs) == 1
    assert customs[0]["id"] == "qwencloud-cn/qwen3.8-max-tp"
    assert customs[0]["display_name"] == "Qwen-3.8-Max（QwenCloud-China）"
    # 去重：同一 id 只保留一次
    rows2 = _parse_models("MODEL\nA\nA\nB (P) (p/m)\nB (P) (p/m)\n")
    ids = [r["id"] for r in rows2]
    assert ids == ["A", "p/m"]


def test_parser_does_not_split_plain_parens_names():
    """没有 `(provider/model)` 尾缀的普通名字不得被误判为自定义路由。"""
    rows = _parse_models("MODEL\nSome Model (v2)\nPlain\n")
    assert all(r["kind"] == "native" for r in rows)
    assert [r["id"] for r in rows] == ["Some Model (v2)", "Plain"]


def test_direct_command_passes_custom_model_id(tmp_path):
    """CLI 合同：Custom 路由用 modelID（provider/model），经 --model 原样传入。"""
    adapter = QoderAdapter(launch=[sys.executable, "-c", "import sys; print('|'.join(sys.argv[1:]))"])
    result = adapter.run(AgentRequest(task="task", cwd=str(tmp_path), custom_model="qwencloud-cn/qwen3.8-max-tp"))
    assert result.status == "completed"
    parts = result.output.split("|")
    assert "--model" in parts
    assert "qwencloud-cn/qwen3.8-max-tp" in parts


def test_direct_command_uses_cn_contract(tmp_path):
    adapter = QoderAdapter(launch=[sys.executable, "-c", "import sys; print('|'.join(sys.argv[1:]))"])
    result = adapter.run(AgentRequest(task="task", cwd=str(tmp_path), model="actual-model", reasoning_effort="high"))
    assert result.status == "completed"
    for item in ("-p", "-o", "json", "--cwd", str(tmp_path), "--model", "actual-model"):
        assert item in result.output.split("|")
    assert "--reasoning-effort" not in result.output


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


def test_command_ready_requires_every_managed_location(monkeypatch, tmp_path):
    """就绪 = 每个受支持命令位置都与当前定义精确一致（任一 stale/缺失 → 不就绪）。"""
    a = tmp_path / "a" / "commands" / "gowrite.md"
    b = tmp_path / "b" / "commands" / "gowrite.md"
    monkeypatch.setattr(qoder, "_command_paths", lambda: [a, b])
    assert qoder.command_ready() is False  # 两个位置都缺失
    a.parent.mkdir(parents=True)
    a.write_text(qoder.command_definition(), encoding="utf-8")
    assert qoder.command_ready() is False  # 一个正确 + 一个缺失
    b.parent.mkdir(parents=True)
    b.write_text("stale command", encoding="utf-8")
    assert qoder.command_ready() is False  # 一个正确 + 一个 stale
    b.write_text(qoder.command_definition(), encoding="utf-8")
    assert qoder.command_ready() is True  # 两个都精确一致


def test_install_command_writes_exact_definition_to_all_locations(monkeypatch, tmp_path):
    """install_command 必须把同一份当前定义写入全部位置并逐位置校验。"""
    a = tmp_path / "a" / "commands" / "gowrite.md"
    b = tmp_path / "b" / "commands" / "gowrite.md"
    monkeypatch.setattr(qoder, "_command_paths", lambda: [a, b])
    result = qoder.install_command()
    assert result["status"] == "installed"
    assert result["command_ready"] is True
    assert sorted(result["installed_paths"]) == sorted([str(a), str(b)])
    assert a.read_text(encoding="utf-8") == qoder.command_definition()
    assert b.read_text(encoding="utf-8") == qoder.command_definition()
    assert all(loc["ready"] for loc in result["locations"])
    assert len(result["locations"]) == 2


def test_command_locations_reports_stale_content(monkeypatch, tmp_path):
    a = tmp_path / "a" / "commands" / "gowrite.md"
    b = tmp_path / "b" / "commands" / "gowrite.md"
    monkeypatch.setattr(qoder, "_command_paths", lambda: [a, b])
    a.parent.mkdir(parents=True)
    a.write_text(qoder.command_definition(), encoding="utf-8")
    b.parent.mkdir(parents=True)
    b.write_text("stale", encoding="utf-8")
    facts = {loc["path"]: loc for loc in qoder.command_locations()}
    assert facts[str(a)]["ready"] is True
    assert facts[str(b)]["ready"] is False
    assert facts[str(b)]["matches"] is False
