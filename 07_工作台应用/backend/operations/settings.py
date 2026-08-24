# -*- coding: utf-8 -*-
"""Settings persistence and local-only capability checks."""
from __future__ import annotations

from typing import Any, Optional

from agents.qoder import install_command as install_qoder_command
from agents.registry import discover_all as registry_discover_all
from config.settings import EXECUTION_MODE_DIRECT, VALID_AGENTS, VALID_EXECUTION_MODES, AppSettings, SettingsStore


class SettingsOpError(Exception): pass


def get_agent_settings() -> dict:
    return {"settings": SettingsStore().load().to_dict(), "agents": registry_discover_all()}


def _agent(agent_id: str) -> Optional[dict]:
    return next((item for item in registry_discover_all() if item.get("agent_id") == agent_id), None)


def _validate_direct(agent_id: str, model_id: Optional[str]) -> None:
    agent = _agent(agent_id); direct = (agent or {}).get("direct") or {}
    if not agent or direct.get("available") is False: raise SettingsOpError("所选直接执行 Agent 当前不可用，请刷新后重试")
    if direct.get("model_selection") == "selectable":
        models = {str(model.get("id")) for model in direct.get("models") or []}
        if not model_id or model_id not in models: raise SettingsOpError("所选模型当前不可用，请刷新后重新选择")


def save_agent_settings(payload: dict) -> dict:
    if not isinstance(payload, dict): raise SettingsOpError("设置格式错误")
    current = SettingsStore().load()
    mode = str(payload.get("default_execution_mode") or current.default_execution_mode)
    interactive = str(payload.get("interactive_agent") or current.interactive_agent)
    direct = str(payload.get("direct_agent") or current.direct_agent)
    model = _str_or_none(payload.get("direct_model", current.direct_model))
    if mode not in VALID_EXECUTION_MODES: raise SettingsOpError(f"执行模式无效：{mode}")
    if interactive not in VALID_AGENTS or direct not in VALID_AGENTS: raise SettingsOpError("未知 Agent")
    if mode == EXECUTION_MODE_DIRECT: _validate_direct(direct, model)
    # A bridge can only be selected after its command is actually ready.
    if mode != EXECUTION_MODE_DIRECT:
        bridge = ((_agent(interactive) or {}).get("interactive") or {})
        if not bridge.get("bridge_ready"): raise SettingsOpError("所选 Agent 的 /gowrite 交互桥尚未就绪")
    settings = AppSettings(default_execution_mode=mode, interactive_agent=interactive, direct_agent=direct, direct_model=model if direct == "qoder" else None)
    SettingsStore().save(settings)
    return settings.to_dict()


def install_or_repair_interactive_command(payload: dict) -> dict:
    if not isinstance(payload, dict) or payload.get("agent") != "qoder": raise SettingsOpError("当前仅 Qoder CN 支持安装 /gowrite 命令")
    result = install_qoder_command()
    if result["errors"] and not result["command_ready"]: raise SettingsOpError("；".join(result["errors"]))
    return result


def _str_or_none(value: Any) -> Optional[str]:
    return str(value).strip() or None if value is not None else None


def test_agent_connection(payload: dict) -> dict:
    if not isinstance(payload, dict): raise SettingsOpError("测试参数格式错误")
    agent_id = payload.get("agent")
    if agent_id not in VALID_AGENTS: raise SettingsOpError("未知 Agent")
    try: _validate_direct(str(agent_id), _str_or_none(payload.get("model")))
    except SettingsOpError as exc: return {"agent": agent_id, "status": "not_configured", "message": f"{exc}；未发送模型请求。"}
    return {"agent": agent_id, "status": "ok", "message": "本机执行入口与当前配置已检测到；未调用模型或远端服务。"}
