# -*- coding: utf-8 -*-
"""Agent Adapter targeted tests（只测新胶水，不重测 DeepSeek Harness CLI）。

覆盖：
1. registry：业务层与具体 Agent 解耦（未知 Agent 报错）
2. capabilities：只按当前真实能力声明
3. cwd：子进程工作目录确实生效
4. failed：非 0 退出码 / stderr → failed
5. cancel：运行中进程可终止 → cancelled
6. 唯一必要验证：Python → registry → DeepSeekHarnessAdapter → DSH headless
   → 固定无副作用任务 → completed + 正确 output（临时目录，不碰正式作品）
"""
import os
import sys
import threading
import time
from pathlib import Path

import pytest

from agents.base import AgentAdapter, AgentRequest, AgentResult
from agents.deepseek_harness import DeepSeekHarnessAdapter, _default_launch
from agents.registry import available, get_agent


# ---------- 1. registry 解耦 ----------

def test_registry_decoupled():
    assert "deepseek_harness" in available()
    assert "qoder" in available()
    agent = get_agent("deepseek_harness")
    assert isinstance(agent, DeepSeekHarnessAdapter)
    assert isinstance(agent, AgentAdapter)
    with pytest.raises(KeyError):
        get_agent("codex")


# ---------- 2. capabilities 如实声明 ----------

def test_capabilities_declared():
    a = DeepSeekHarnessAdapter(launch=["node", "unused"])
    caps = a.capabilities()
    assert caps["run"] is True
    assert caps["cwd"] is True
    assert caps["final_output"] is True
    assert caps["cancel"] is True
    assert caps["stream"] is False
    assert caps["resume"] is False
    assert caps["session"] is False
    assert caps["model_selection"] == "profile_managed"


# ---------- 3. cwd 生效 ----------

def test_cwd_used(tmp_path):
    a = DeepSeekHarnessAdapter(launch=[sys.executable, "-c", "import os; print(os.getcwd())"])
    result = a.run(AgentRequest(task="x", cwd=str(tmp_path)))
    assert result.status == "completed", result.error
    got = os.path.normcase(os.path.normpath(result.output.strip()))
    want = os.path.normcase(str(tmp_path))
    assert got == want, f"cwd 不匹配: {got} != {want}"


# ---------- 4. 非 0 退出 → failed ----------

def test_failed_on_nonzero_exit(tmp_path):
    a = DeepSeekHarnessAdapter(
        launch=[sys.executable, "-c", "import sys; print('boom', file=sys.stderr); sys.exit(3)"]
    )
    result = a.run(AgentRequest(task="x", cwd=str(tmp_path)))
    assert result.status == "failed"
    assert result.exit_code == 3
    assert "boom" in (result.error or "")


# ---------- 5. cancel → cancelled ----------

def test_cancel_running_process(tmp_path):
    a = DeepSeekHarnessAdapter(
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


# ---------- 6. 唯一必要验证：真实 DSH headless 胶水通路 ----------

def test_real_dsh_headless_glue(tmp_path):
    try:
        launch = _default_launch()
    except RuntimeError as exc:
        pytest.skip(f"DeepSeek Harness headless 不可用：{exc}")

    # 业务层只能通过 registry 拿 Adapter
    adapter = get_agent("deepseek_harness")
    assert adapter.capabilities()["run"] is True

    result = adapter.run(AgentRequest(
        task="不要读取或修改任何文件，只返回 AI_WRITE_AGENT_OK。",
        cwd=str(tmp_path),
    ))
    assert result.status == "completed", f"status={result.status} error={result.error}"
    assert "AI_WRITE_AGENT_OK" in result.output, f"output={result.output!r}"
    assert result.agent == "deepseek_harness"
