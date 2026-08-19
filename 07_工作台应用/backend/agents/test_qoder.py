# -*- coding: utf-8 -*-
"""Qoder Adapter targeted tests（只测新胶水，不重测 Qoder CLI / SDK 本身）。

覆盖用户要求的验证点：
1. registry 可以取得 QoderAdapter
2. Qoder 自带模型路径：Python → QoderAdapter → qodercli -p → 固定无副作用结果
3. cwd 正确传入
4. model 参数正确传递
5. failed 正确转换
6. cancel 正确工作
7. SDK BYOK 配置能正确进入 resolve_model
8. provider/model 目录能通过官方 SDK取得
9. DeepSeekHarnessAdapter 原有测试继续通过（运行 test_agents.py 覆盖）

所有真实执行使用临时目录；BYOK 不使用真实 API Key、不产生真实第三方费用。
"""
import os
import sys
import threading
import time
from pathlib import Path

import pytest

# 真实模型调用门控：默认 pytest 不产生任何 Token 消耗。
# 只有显式设置 GOWRITE_REAL_QODER_TEST=1 时才允许真实执行。
_real_qoder_test = pytest.mark.skipif(
    os.environ.get("GOWRITE_REAL_QODER_TEST") != "1",
    reason="真实模型调用需要 GOWRITE_REAL_QODER_TEST=1（默认跳过，防止意外消耗 Token）",
)

from agents.base import AgentAdapter, AgentRequest, AgentResult
from agents.qoder import QoderAdapter, QoderBYOKConfig, _default_cli, _resolve_cmd
from agents.registry import available, get_agent


# ---------- 1. registry 可以取得 QoderAdapter ----------

def test_registry_get_qoder():
    assert "qoder" in available()
    agent = get_agent("qoder")
    assert isinstance(agent, QoderAdapter)
    assert isinstance(agent, AgentAdapter)
    assert agent.name == "qoder"
    with pytest.raises(KeyError):
        get_agent("codex")


# ---------- 能力声明（CLI / BYOK 两路径如实区分） ----------

def test_capabilities_cli_path():
    a = QoderAdapter(launch=[sys.executable, "-c", "pass"])
    caps = a.capabilities()
    assert caps["run"] is True
    assert caps["cwd"] is True
    assert caps["final_output"] is True
    assert caps["cancel"] is True
    assert caps["stream"] is False
    assert caps["resume"] is False
    assert caps["session"] is False
    assert caps["model_selection"] == "cli_flag"
    assert caps["reasoning_effort"] is True
    assert caps["byok"] is False


def test_capabilities_byok_path():
    a = QoderAdapter(
        launch=[sys.executable, "-c", "pass"],
        byok=QoderBYOKConfig(provider="bailian", model="qwen-max", api_key="sk-test"),
    )
    caps = a.capabilities()
    assert caps["byok"] is True
    assert caps["model_selection"] == "byok_resolve_model"
    assert caps["cancel"] is False  # SDK query() 无 interrupt，如实声明
    assert caps["reasoning_effort"] is True


# ---------- 3. cwd 正确传入（CLI 路径，假入口） ----------

def test_cli_cwd_used(tmp_path):
    a = QoderAdapter(launch=[sys.executable, "-c", "import os; print(os.getcwd())"])
    result = a.run(AgentRequest(task="x", cwd=str(tmp_path)))
    assert result.status == "completed", result.error
    got = os.path.normcase(os.path.normpath(result.output.strip()))
    want = os.path.normcase(str(tmp_path))
    assert got == want, f"cwd 不匹配: {got} != {want}"


# ---------- 4. model / reasoning_effort 参数正确传递（CLI 路径，假入口） ----------

def test_cli_model_and_effort_passed(tmp_path):
    a = QoderAdapter(
        launch=[sys.executable, "-c", "import sys; print('|'.join(sys.argv[1:]))"]
    )
    result = a.run(AgentRequest(
        task="t", cwd=str(tmp_path),
        model="qwen3.8-max", reasoning_effort="high",
    ))
    assert result.status == "completed", result.error
    parts = result.output.split("|")
    assert "--model" in parts and "qwen3.8-max" in parts
    assert "--reasoning-effort" in parts and "high" in parts


# ---------- 5. failed 正确转换（CLI 路径，假入口） ----------

def test_cli_failed_on_nonzero_exit(tmp_path):
    a = QoderAdapter(
        launch=[sys.executable, "-c", "import sys; print('boom', file=sys.stderr); sys.exit(3)"]
    )
    result = a.run(AgentRequest(task="x", cwd=str(tmp_path)))
    assert result.status == "failed"
    assert result.exit_code == 3
    assert "boom" in (result.error or "")


# ---------- 6. cancel 正确工作（CLI 路径，假入口） ----------

def test_cli_cancel_running_process(tmp_path):
    a = QoderAdapter(
        launch=[sys.executable, "-c", "import time; time.sleep(60)"],
        timeout=120,
    )
    holder: dict = {}

    def worker() -> None:
        holder["result"] = a.run(AgentRequest(task="x", cwd=str(tmp_path)))

    t = threading.Thread(target=worker)
    t.start()
    time.sleep(1.5)  # 等子进程真正启动
    assert a.cancel() is True
    t.join(timeout=15)
    assert not t.is_alive(), "cancel 后 run 未返回"
    assert holder["result"].status == "cancelled"


# ---------- 2. 唯一必要验证：真实 Qoder 自带模型路径 ----------
# Python → registry → QoderAdapter → qodercli -p → 固定无副作用结果（临时目录）
# ⚠️ 真实模型调用，消耗 Token；默认跳过，需 GOWRITE_REAL_QODER_TEST=1 显式开启。

@_real_qoder_test
def test_real_qoder_cli_glue(tmp_path):
    try:
        cli = _default_cli()
    except RuntimeError as exc:
        pytest.skip(f"Qoder CLI 不可用：{exc}")

    # 业务层只能通过 registry 拿 Adapter（自带模型 = CLI 路径）
    adapter = get_agent("qoder")
    assert adapter.capabilities()["byok"] is False
    assert adapter.capabilities()["cancel"] is True

    result = adapter.run(AgentRequest(
        task="不要读取或修改任何文件，只返回 QODER_AGENT_OK。",
        cwd=str(tmp_path),
    ))
    assert result.status == "completed", f"status={result.status} error={result.error}"
    assert "QODER_AGENT_OK" in result.output, f"output={result.output!r}"
    assert result.agent == "qoder"


# ---------- 7. SDK BYOK 配置能正确进入 resolve_model（无真实 Key / 费用） ----------

def test_byok_config_enters_resolve_model():
    cfg = QoderBYOKConfig(
        provider="bailian", model="qwen-max", api_key="sk-test-not-real",
        url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        style="openai", reasoning_effort="high",
    )
    a = QoderAdapter(launch=[sys.executable, "-c", "pass"], byok=cfg)
    resolver = a._make_resolver(model="qwen-max", reasoning_effort="high")

    # 官方回调签名：ModelPolicyContext（dict）→ ModelPolicyResult（dict）
    out = resolver({"purpose": "main", "sessionId": "s1", "turnIndex": 0,
                    "availableModels": []})
    cm = out["model"]
    assert cm["provider"] == "bailian"
    assert cm["model"] == "qwen-max"
    assert cm["api_key"] == "sk-test-not-real"
    assert cm["url"] == cfg.url
    assert cm["style"] == "openai"
    assert out["parameters"] == {"reasoningEffort": "high"}


def test_byok_request_overrides_default_model(tmp_path):
    cfg = QoderBYOKConfig(provider="bailian", model="default-model", api_key="sk-test")
    a = QoderAdapter(launch=[sys.executable, "-c", "pass"], byok=cfg)
    resolver = a._make_resolver(model="override-model", reasoning_effort=None)
    out = resolver({"purpose": "main"})
    assert out["model"]["model"] == "override-model"
    assert "parameters" not in out


# ---------- 8. provider/model 目录能通过官方 SDK取得 ----------
# 真实 SDK 读取（复用 qodercli 登录，只读目录，无费用）；CLI 不可用时跳过。

def test_list_byok_providers_via_sdk():
    try:
        _default_cli()
    except RuntimeError as exc:
        pytest.skip(f"Qoder CLI 不可用：{exc}")
    a = QoderAdapter()
    providers = a.list_byok_providers()
    assert providers is not None, "CLI 应支持 get_byok_config 或返回 None（较旧版本）"
    # 官方 BYOKProviderInfo 目录：至少包含 provider 的 key 与 display_name
    assert isinstance(providers, list) and providers
    first = providers[0]
    assert isinstance(first, dict)
    assert first.get("key") and first.get("display_name")


def test_list_qoder_models_dynamic():
    """Qoder 自带模型目录动态读取（不硬编码名单）。"""
    try:
        _default_cli()
    except RuntimeError as exc:
        pytest.skip(f"Qoder CLI 不可用：{exc}")
    a = QoderAdapter()
    models = a.list_qoder_models()
    assert isinstance(models, list) and models
    assert all(isinstance(m, str) and m.strip() for m in models)


# ---------- _extract_cli_result：JSON 信封提取 ----------

def test_extract_cli_result_json_envelope():
    """CLI --output-format json 返回 JSON 信封时，应提取 result 字段。"""
    import json
    envelope = json.dumps({
        "type": "result",
        "subtype": "success",
        "result": '{"ok":true}',
        "duration_ms": 1234,
    })
    assert QoderAdapter._extract_cli_result(envelope) == '{"ok":true}'


def test_extract_cli_result_json_envelope_with_chinese():
    """JSON 信封的 result 字段含中文时，应完整提取。"""
    import json
    result_text = '{"semantic_interpretation":{"objective":"测试中文"}}'
    envelope = json.dumps({
        "type": "result",
        "result": result_text,
        "duration_ms": 500,
    }, ensure_ascii=False)
    assert QoderAdapter._extract_cli_result(envelope) == result_text


def test_extract_cli_result_fallback_plain_text():
    """非 JSON 信封时，回退到原始文本。"""
    assert QoderAdapter._extract_cli_result("just plain text") == "just plain text"


def test_extract_cli_result_empty():
    """空输入回退到空文本。"""
    assert QoderAdapter._extract_cli_result("") == ""
    assert QoderAdapter._extract_cli_result(None) == ""


# ---------- _resolve_cmd：CMD 包装器解析 ----------

def test_resolve_cmd_non_windows_returns_original(monkeypatch):
    """非 Windows 系统直接返回原始路径。"""
    monkeypatch.setattr("os.name", "posix")
    result = _resolve_cmd("/usr/local/bin/qodercli")
    assert result == ["/usr/local/bin/qodercli"]


def test_resolve_cmd_non_cmd_returns_original(monkeypatch):
    """非 .CMD/.BAT 文件直接返回原始路径。"""
    monkeypatch.setattr("os.name", "nt")
    result = _resolve_cmd("C:\\path\\to\\qodercli.exe")
    assert result == ["C:\\path\\to\\qodercli.exe"]


# ---------- _extract_cli_error：错误信封检测 ----------

def test_extract_cli_error_detects_error_envelope():
    """CLI 返回 is_error=true 的信封时，应提取错误信息。"""
    import json
    envelope = json.dumps({
        "type": "result",
        "is_error": True,
        "subtype": "error_during_execution",
        "errors": ["You've reached your monthly Lite model limit."],
    })
    error = QoderAdapter._extract_cli_error(envelope)
    assert error is not None
    assert "Lite model limit" in error


def test_extract_cli_error_no_error_returns_none():
    """正常成功信封无错误，应返回 None。"""
    import json
    envelope = json.dumps({
        "type": "result",
        "is_error": False,
        "result": "some output",
    })
    assert QoderAdapter._extract_cli_error(envelope) is None


def test_extract_cli_error_non_json_returns_none():
    """非 JSON 文本应返回 None（不误报）。"""
    assert QoderAdapter._extract_cli_error("plain text") is None
    assert QoderAdapter._extract_cli_error("") is None
    assert QoderAdapter._extract_cli_error(None) is None
