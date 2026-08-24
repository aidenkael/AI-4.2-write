# -*- coding: utf-8 -*-
"""Agent registry：业务层只能通过本模块获取 Agent。

当前注册：deepseek_harness、qoder。
以后 Codex 等可新增 Adapter，但业务层不得出现 if deepseek / if qoder / if codex 分支。
"""
from __future__ import annotations

from typing import Any

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


def discover_all() -> list[dict[str, Any]]:
    """读取所有注册 Agent 的本机能力；单个 Agent 失败不阻断其余发现。"""
    environments: list[dict[str, Any]] = []
    for name in available():
        adapter_type = _REGISTRY[name]
        try:
            environments.append(adapter_type.discover())
        except Exception as exc:  # noqa: BLE001 — discovery 边界必须稳定
            environments.append({
                "agent_id": name,
                "display_name": name,
                "installed": False,
                "available": False,
                "version": None,
                "errors": [str(exc) or type(exc).__name__],
                "interactive": {
                    "available": False,
                    "bridge_ready": False,
                    "command_name": "/gowrite",
                    "command_ready": False,
                },
                "direct": {
                    "available": False,
                    "auth_status": "not_detected",
                    "model_selection": "none",
                    "models": [],
                    "managed_model": None,
                    "capabilities": {},
                },
            })
    return environments
