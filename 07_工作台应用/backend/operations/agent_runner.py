# -*- coding: utf-8 -*-
"""按当前设置取得可运行 Agent 的薄内部入口（agent_runner）。

- Author Operations 只需要表达“使用当前配置的 Agent 执行这个任务”，
  不需要知道 Qoder / DeepSeek Harness 的差异。
- 所有“当前设置 → 具体 Adapter”的差异集中在这里处理（唯一 if 点）：
  - default_agent
  - model / reasoning_effort
  - Qoder native / BYOK（BYOK 时从 keyring 取 Token，只进 Adapter）
- Token 禁止进入 Prompt / UI / 日志 / Bridge 返回值：本层拿到 Token 后
  只构造 QoderBYOKConfig，绝不拼进任务文本或错误信息。
"""
from __future__ import annotations

from typing import Optional

from agents.base import AgentAdapter, AgentRequest, AgentResult
from agents.registry import get_agent as registry_get_agent
from agents.qoder import QoderAdapter, QoderBYOKConfig
from config.secrets import BYOK_SECRET_ID, SecretStore, SecretError
from config.settings import SettingsStore


class AgentRunError(Exception):
    """按当前设置无法取得可运行 Agent 的错误（普通用户可读）。"""


def _build_adapter() -> tuple[AgentAdapter, AgentRequest]:
    """读取已保存设置，构造 (adapter, request)。集中处理 Agent 差异。"""
    settings = SettingsStore().load()
    agent = settings.default_agent

    if agent == "deepseek_harness":
        adapter = registry_get_agent("deepseek_harness")
        # 模型由 Harness profile 管理；request.model 不适用
        return adapter, AgentRequest(task="")  # task 由调用方填充

    if agent == "qoder":
        mode = settings.qoder_mode
        if mode == "qoder_byok":
            provider = settings.byok_provider
            model = settings.byok_model
            if not provider or not model:
                raise AgentRunError("Qoder BYOK 未配置服务商/模型：请先在“设置”中保存。")
            secret = SecretStore()
            try:
                token = secret.get_secret(settings.byok_secret_id or BYOK_SECRET_ID)
            except SecretError as exc:
                raise AgentRunError(str(exc)) from exc
            if not token:
                raise AgentRunError("Qoder BYOK 未配置 Token：请先在“设置”中保存 API Key / Token。")
            adapter = QoderAdapter(byok=QoderBYOKConfig(
                provider=provider,
                model=model,
                api_key=token,  # 只进 Adapter，绝不进 Prompt / 返回值
                reasoning_effort=settings.reasoning_effort,
            ))
            return adapter, AgentRequest(task="")

        # qoder_native
        adapter = QoderAdapter()
        return adapter, AgentRequest(
            task="",
            model=settings.qoder_model,
            reasoning_effort=settings.reasoning_effort,
        )

    raise AgentRunError(f"当前默认 Agent 不可用：{agent}")


def run_task(task: str, cwd: Optional[str] = None) -> AgentResult:
    """使用当前配置的 Agent 执行一次任务（cwd 默认继承调用方）。"""
    try:
        adapter, request = _build_adapter()
    except AgentRunError:
        raise
    except Exception as exc:  # noqa: BLE001 — Adapter 构造失败（如 CLI 缺失）转可读错误
        raise AgentRunError(f"当前 Agent 不可用：{exc}") from exc
    request.task = task
    request.cwd = cwd
    return adapter.run(request)
