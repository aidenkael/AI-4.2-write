# -*- coding: utf-8 -*-
"""Agent registry：业务层只能通过本模块获取 Agent。

当前注册：deepseek_harness、qoder。
以后 Codex 等可新增 Adapter，但业务层不得出现 if deepseek / if qoder / if codex 分支。
"""
from __future__ import annotations

from agents.base import AgentAdapter, AgentRequest, AgentResult  # noqa: F401
from agents.deepseek_harness import DeepSeekHarnessAdapter
from agents.qoder import QoderAdapter

_REGISTRY: dict[str, type[AgentAdapter]] = {
    "deepseek_harness": DeepSeekHarnessAdapter,
    "qoder": QoderAdapter,
}


def available() -> list[str]:
    """已注册 Agent 标识列表。"""
    return sorted(_REGISTRY)


def get_agent(name: str) -> AgentAdapter:
    """按标识返回一个新的 Adapter 实例（每次独立，互不共享运行状态）。"""
    if name not in _REGISTRY:
        raise KeyError(f"未知 Agent: {name}")
    return _REGISTRY[name]()
