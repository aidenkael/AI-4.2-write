# -*- coding: utf-8 -*-
"""Thin current-direct-settings to adapter routing."""
from __future__ import annotations

from typing import Optional

from agents.base import AgentAdapter, AgentRequest, AgentResult
from agents.registry import get_agent as registry_get_agent
from config.settings import SettingsStore


class AgentRunError(Exception):
    pass


def _build_adapter() -> tuple[AgentAdapter, AgentRequest]:
    settings = SettingsStore().load()
    if settings.default_execution_mode != "direct":
        raise AgentRunError("当前默认方式为交互桥；请在选定 Agent 中运行 /gowrite。")
    if bool(settings.direct_model) == bool(settings.direct_custom_model):
        raise AgentRunError("请在“设置”中选择一个内置模型或自定义模型。")
    adapter = registry_get_agent(settings.direct_agent)
    return adapter, AgentRequest(
        task="", model=settings.direct_model, custom_model=settings.direct_custom_model,
    )


def run_task(task: str, cwd: Optional[str] = None) -> AgentResult:
    try:
        adapter, request = _build_adapter()
    except AgentRunError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AgentRunError(f"当前 Agent 不可用：{exc}") from exc
    request.task, request.cwd = task, cwd
    return adapter.run(request)
