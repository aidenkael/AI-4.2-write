# -*- coding: utf-8 -*-
"""统一 Agent 合同（最小）。

只定义 AI-write 真正需要的最小面：请求、结果、能力声明与 Adapter 基类。
不为未来 Agent 预造 session framework、事件总线、插件系统或大型抽象层。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class AgentRequest:
    """一次 Agent 调用请求。

    只放多个 Agent 都可能真正需要的通用字段；Agent 特有配置（如 Qoder
    BYOK 的 provider / api_key）由各 Adapter 的配置对象负责，不进本类。
    """

    task: str
    cwd: Optional[str] = None  # 子进程工作目录（None = 继承调用方）
    model: Optional[str] = None  # 可选：通用模型选择（多个 Agent 都可能需要）
    reasoning_effort: Optional[str] = None  # 可选：通用推理强度（多个 Agent 都可能需要）


@dataclass
class AgentResult:
    """一次 Agent 调用的统一结果。"""

    status: str  # completed / failed / cancelled
    output: str = ""
    error: Optional[str] = None
    agent: str = ""  # provider/agent 标识（最小即可，如 "deepseek_harness"）
    exit_code: Optional[int] = None


class AgentAdapter:
    """Adapter 基类：业务层只依赖本类 + AgentRequest/AgentResult。"""

    name: str = ""

    @classmethod
    def discover(cls) -> dict[str, Any]:
        """返回供设置页使用的规范化本机环境描述；不得执行模型请求。"""
        raise NotImplementedError

    def capabilities(self) -> dict[str, Any]:
        raise NotImplementedError

    def run(self, request: AgentRequest) -> AgentResult:
        raise NotImplementedError

    def cancel(self) -> bool:
        """终止当前运行中的子进程；成功终止返回 True。默认不支持。"""
        return False
