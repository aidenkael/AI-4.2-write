# -*- coding: utf-8 -*-
"""Settings feature 的普通设置、Agent discovery 与安全状态检查。

职责：
- 普通设置（default_agent / qoder 模式 / 模型 / 思考强度 / BYOK 引用）读写
- Token 走 keyring（save / has / delete / get，get 仅后台测试连接用）
- Agent 状态 / 能力查询（经 registry，真实数据，无假数据）
- Qoder 自带模型 / BYOK provider-model 动态读取（不硬编码名单）
- 测试连接（无副作用任务 + 临时目录，绝不修改作品）

安全：本层返回给 Bridge 的任何数据都不得包含 Token 明文。
"""
from __future__ import annotations

from typing import Any, Optional

from agents.registry import discover_all as registry_discover_all
from config.secrets import BYOK_SECRET_ID, SecretStore
from config.settings import (
    EXECUTION_MODE_DIRECT,
    REASONING_EFFORT_OPTIONS,
    VALID_AGENTS,
    VALID_EXECUTION_MODES,
    VALID_QODER_MODES,
    AppSettings,
    SettingsStore,
)

class SettingsOpError(Exception):
    """设置操作错误（面向 UI 的稳定错误类型，普通用户可读）。"""


# ---------------- 读取 ----------------

def get_agent_settings() -> dict:
    """当前设置 + 规范化本机 discovery + secret presence（无明文）。"""
    store = SettingsStore()
    settings = store.load()
    secret = SecretStore()

    agents = registry_discover_all()

    has_secret = False
    if settings.byok_secret_id:
        try:
            has_secret = secret.has_secret(settings.byok_secret_id)
        except Exception:  # noqa: BLE001
            has_secret = False

    return {
        "settings": settings.to_dict(),
        "agents": agents,
        "byok": {
            "secret_id": settings.byok_secret_id,
            "has_secret": has_secret,
        },
        "reasoning_effort_options": list(REASONING_EFFORT_OPTIONS),
    }


def get_agent_options() -> dict:
    """旧 Bridge 方法兼容：选项仍从 normalized discovery 派生。"""
    qoder = next((item for item in registry_discover_all() if item["agent_id"] == "qoder"), None)
    profiles = ((qoder or {}).get("direct") or {}).get("execution_profiles") or []
    native = next((profile for profile in profiles if profile.get("id") == "native"), None)
    provider_map: dict[str, dict] = {}
    for profile in profiles:
        if profile.get("type") != "byok" or not profile.get("provider_id"):
            continue
        provider_id = str(profile["provider_id"])
        provider = provider_map.setdefault(provider_id, {
            "key": provider_id, "display_name": provider_id, "types": [],
        })
        provider["types"].append({
            "key": str(profile.get("id") or "").split(":")[-1],
            "display_name": profile.get("display_name"),
            "models": [
                {
                    "key": model.get("id"), "display_name": model.get("display_name"),
                    "is_reasoning": bool(model.get("reasoning_efforts")),
                    "efforts": model.get("reasoning_efforts") or [],
                }
                for model in profile.get("models") or []
            ],
        })
    return {
        "qoder_models": [model["id"] for model in (native or {}).get("models") or []],
        "qoder_models_error": (native or {}).get("error"),
        "byok_providers": list(provider_map.values()),
        "byok_error": None,
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

    mode = payload.get("qoder_mode", current.qoder_mode)
    if mode not in VALID_QODER_MODES:
        raise SettingsOpError(f"Qoder 使用模式无效：{mode}")

    effort = payload.get("reasoning_effort", current.reasoning_effort)
    if effort is not None and effort not in REASONING_EFFORT_OPTIONS:
        raise SettingsOpError(f"思考强度无效：{effort}（可选：{'、'.join(REASONING_EFFORT_OPTIONS)}）")

    if execution_mode == EXECUTION_MODE_DIRECT:
        _validate_direct_selection(direct_agent, direct_profile_id, direct_model)

    qoder_mode = mode
    qoder_model = _str_or_none(payload.get("qoder_model", current.qoder_model))
    byok_provider = _str_or_none(payload.get("byok_provider", current.byok_provider))
    byok_model = _str_or_none(payload.get("byok_model", current.byok_model))
    if direct_agent == "qoder" and direct_profile_id:
        if direct_profile_id == "native":
            qoder_mode = "qoder_native"
            qoder_model = direct_model
        elif direct_profile_id.startswith("byok:"):
            qoder_mode = "qoder_byok"
            parts = direct_profile_id.split(":")
            byok_provider = parts[1] if len(parts) > 1 else byok_provider
            byok_model = direct_model

    settings = AppSettings(
        default_execution_mode=execution_mode,
        interactive_agent=interactive_agent,
        direct_agent=direct_agent,
        direct_profile_id=direct_profile_id,
        direct_model=direct_model,
        default_agent=direct_agent,
        qoder_mode=qoder_mode,
        qoder_model=qoder_model,
        reasoning_effort=effort,
        byok_provider=byok_provider,
        byok_model=byok_model,
        byok_secret_id=current.byok_secret_id,  # Token 引用保持原样，不接受前端改动
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


def save_byok_secret(token: str) -> dict:
    """保存 BYOK Token 到 keyring；配置只写 secret_id 引用。"""
    if not isinstance(token, str) or not token.strip():
        raise SettingsOpError("Token 不能为空")
    secret = SecretStore()
    secret.save_secret(BYOK_SECRET_ID, token.strip())

    store = SettingsStore()
    settings = store.load()
    settings.byok_secret_id = BYOK_SECRET_ID
    store.save(settings)
    return {"secret_id": BYOK_SECRET_ID, "has_secret": True}


def delete_byok_secret() -> dict:
    """删除 keyring 中的 Token，并清空配置里的引用；状态立即变为未配置。"""
    secret = SecretStore()
    secret.delete_secret(BYOK_SECRET_ID)

    store = SettingsStore()
    settings = store.load()
    settings.byok_secret_id = None
    store.save(settings)
    return {"secret_id": None, "has_secret": False}


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
