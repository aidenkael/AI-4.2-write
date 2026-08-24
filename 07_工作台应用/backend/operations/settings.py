# -*- coding: utf-8 -*-
"""Settings feature 的普通设置、Agent discovery 与安全状态检查。

职责：持久化执行选择、协调本机 Agent 发现、安装官方位置的交互命令；不保存密钥。
"""
from __future__ import annotations

from typing import Any, Optional

from agents.registry import discover_all as registry_discover_all
from config.settings import (
    EXECUTION_MODE_DIRECT,
    REASONING_EFFORT_OPTIONS,
    VALID_AGENTS,
    VALID_EXECUTION_MODES,
    AppSettings,
    SettingsStore,
)
from agents.qoder import install_command as install_qoder_command

class SettingsOpError(Exception):
    """设置操作错误（面向 UI 的稳定错误类型，普通用户可读）。"""


# ---------------- 读取 ----------------

def get_agent_settings() -> dict:
    """当前设置 + 规范化本机 discovery + secret presence（无明文）。"""
    store = SettingsStore()
    settings = store.load()
    agents = registry_discover_all()

    return {
        "settings": settings.to_dict(),
        "agents": agents,
        "reasoning_effort_options": list(REASONING_EFFORT_OPTIONS),
    }


# ---------------- 保存 ----------------

def save_agent_settings(payload: dict) -> dict:
    """保存普通设置；动态目录只存选择 id，不存 catalog。"""
    if not isinstance(payload, dict):
        raise SettingsOpError("设置格式错误")

    store = SettingsStore()
    current = store.load()

    execution_mode = str(payload.get("default_execution_mode") or current.default_execution_mode)
    if execution_mode not in VALID_EXECUTION_MODES:
        raise SettingsOpError(f"执行模式无效：{execution_mode}")

    legacy_agent = payload.get("default_agent")
    interactive_agent = str(payload.get("interactive_agent") or legacy_agent or current.interactive_agent)
    direct_agent = str(payload.get("direct_agent") or legacy_agent or current.direct_agent)
    for agent in (interactive_agent, direct_agent):
        if agent not in VALID_AGENTS:
            raise SettingsOpError(f"未知 Agent：{agent}（可选：{'、'.join(VALID_AGENTS)}）")

    direct_profile_id = _str_or_none(payload.get("direct_profile_id", current.direct_profile_id))
    direct_model = _str_or_none(payload.get("direct_model", current.direct_model))

    effort = payload.get("reasoning_effort", current.reasoning_effort)
    if effort is not None and effort not in REASONING_EFFORT_OPTIONS:
        raise SettingsOpError(f"思考强度无效：{effort}（可选：{'、'.join(REASONING_EFFORT_OPTIONS)}）")

    if execution_mode == EXECUTION_MODE_DIRECT:
        _validate_direct_selection(direct_agent, direct_profile_id, direct_model)

    settings = AppSettings(
        default_execution_mode=execution_mode,
        interactive_agent=interactive_agent,
        direct_agent=direct_agent,
        direct_profile_id=direct_profile_id,
        direct_model=direct_model,
        reasoning_effort=effort,
    )
    store.save(settings)
    return settings.to_dict()


def _validate_direct_selection(agent_id: str, profile_id: Optional[str], model_id: Optional[str]) -> None:
    environment = next(
        (item for item in registry_discover_all() if item.get("agent_id") == agent_id),
        None,
    )
    if not environment:
        raise SettingsOpError("所选直接执行 Agent 当前不可用")
    profiles = (environment.get("direct") or {}).get("execution_profiles") or []
    profile = next((item for item in profiles if item.get("id") == profile_id), None)
    if not profile or not profile.get("available"):
        raise SettingsOpError("所选执行配置当前不可用，请刷新后重新选择")
    if profile.get("model_selection") == "selectable":
        available_models = {str(item.get("id")) for item in profile.get("models") or []}
        if not model_id or model_id not in available_models:
            raise SettingsOpError("所选模型当前不可用，请刷新后重新选择")


def install_or_repair_interactive_command(payload: dict) -> dict:
    if not isinstance(payload, dict) or payload.get("agent") != "qoder":
        raise SettingsOpError("当前仅 Qoder CN 支持安装 /gowrite 命令")
    result = install_qoder_command()
    if result["errors"] and not result["command_ready"]:
        raise SettingsOpError("；".join(result["errors"]))
    return result


def _str_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


# ---------------- 测试连接 ----------------

def test_agent_connection(payload: dict) -> dict:
    """只检查本机 discovery/auth/profile；例行测试绝不运行模型。"""
    if not isinstance(payload, dict):
        raise SettingsOpError("测试参数格式错误")
    agent = payload.get("agent") or payload.get("default_agent")
    if agent not in VALID_AGENTS:
        raise SettingsOpError(f"未知 Agent：{agent}")

    environment = next(
        (item for item in registry_discover_all() if item.get("agent_id") == agent),
        None,
    )
    if not environment or not environment.get("installed"):
        return {"agent": agent, "status": "failed", "message": "未检测到本机 Agent"}
    direct = environment.get("direct") or {}
    profile_id = _str_or_none(payload.get("profile_id") or payload.get("direct_profile_id"))
    profiles = direct.get("execution_profiles") or []
    profile = next((item for item in profiles if item.get("id") == profile_id), None)
    if not profile or not profile.get("available"):
        return {
            "agent": agent,
            "status": "not_configured",
            "message": "所选执行配置当前不可用；未发送模型请求。",
        }
    model_id = _str_or_none(payload.get("model") or payload.get("direct_model"))
    if profile.get("model_selection") == "selectable":
        models = {str(item.get("id")) for item in profile.get("models") or []}
        if not model_id or model_id not in models:
            return {
                "agent": agent,
                "status": "not_configured",
                "message": "所选模型当前不可用；未发送模型请求。",
            }
    if direct.get("auth_status") in ("not_authenticated", "not_detected"):
        return {
            "agent": agent,
            "status": "not_configured",
            "message": "本机认证/凭据尚未就绪；未发送模型请求。",
        }
    return {
        "agent": agent,
        "status": "ok",
        "message": "本机执行入口与配置已检测到；未调用模型或验证远端服务。",
    }
