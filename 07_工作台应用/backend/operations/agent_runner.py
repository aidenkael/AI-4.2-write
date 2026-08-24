# -*- coding: utf-8 -*-
"""Thin current-direct-settings to adapter routing."""
from __future__ import annotations

from typing import Optional

from agents.base import AgentAdapter, AgentRequest, AgentResult
from agents.qoder import QoderAdapter
from agents.registry import get_agent as registry_get_agent
from config.settings import SettingsStore


class AgentRunError(Exception):
    pass


def _build_adapter() -> tuple[AgentAdapter, AgentRequest]:
    settings = SettingsStore().load()
    if settings.default_execution_mode != "direct":
        raise AgentRunError("当前默认方式为交互桥；请在选定 Agent 中运行 /gowrite。")
    if settings.direct_agent == "deepseek_harness":
        if settings.direct_profile_id != "headless":
            raise AgentRunError("Harness Headless 配置不可用，请在“设置”中刷新后重新选择。")
        return registry_get_agent("deepseek_harness"), AgentRequest(task="")
    if settings.direct_agent == "qoder":
        if settings.direct_profile_id != "qoder_cn" or not settings.direct_model:
            raise AgentRunError("Qoder CN 模型未配置，请在“设置”中选择已发现的模型。")
        return QoderAdapter(), AgentRequest(task="", model=settings.direct_model, reasoning_effort=settings.reasoning_effort)
    raise AgentRunError(f"当前直接执行 Agent 不可用：{settings.direct_agent}")


def run_task(task: str, cwd: Optional[str] = None) -> AgentResult:
    try:
        adapter, request = _build_adapter()
    except AgentRunError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AgentRunError(f"当前 Agent 不可用：{exc}") from exc
    request.task, request.cwd = task, cwd
    return adapter.run(request)
