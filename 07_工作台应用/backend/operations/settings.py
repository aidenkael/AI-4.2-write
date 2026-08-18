# -*- coding: utf-8 -*-
"""Agent / 模型 / Token 设置操作层（operations.settings）。

职责：
- 普通设置（default_agent / qoder 模式 / 模型 / 思考强度 / BYOK 引用）读写
- Token 走 keyring（save / has / delete / get，get 仅后台测试连接用）
- Agent 状态 / 能力查询（经 registry，真实数据，无假数据）
- Qoder 自带模型 / BYOK provider-model 动态读取（不硬编码名单）
- 测试连接（无副作用任务 + 临时目录，绝不修改作品）

安全：本层返回给 Bridge 的任何数据都不得包含 Token 明文。
"""
from __future__ import annotations

import tempfile
from typing import Any, Optional

from agents.base import AgentRequest
from agents.registry import available as registry_available
from agents.registry import get_agent as registry_get_agent
from agents.qoder import QoderAdapter, QoderBYOKConfig
from config.secrets import BYOK_SECRET_ID, SecretStore
from config.settings import (
    REASONING_EFFORT_OPTIONS,
    VALID_AGENTS,
    VALID_QODER_MODES,
    AppSettings,
    SettingsError,
    SettingsStore,
)

# 测试连接统一无副作用任务（临时目录内执行，不碰作品 / Skills）
CONNECTION_PROBE_TASK = "不要读取或修改任何文件，只返回 AI_WRITE_CONNECTION_OK。"


class SettingsOpError(Exception):
    """设置操作错误（面向 UI 的稳定错误类型，普通用户可读）。"""


def _friendly(exc: Exception) -> str:
    """把底层异常转成普通用户能看懂的一句话（不泄露 Token）。"""
    msg = str(exc).strip()
    if not msg:
        msg = type(exc).__name__
    return msg


# ---------------- 读取 ----------------

def get_agent_settings() -> dict:
    """当前设置 + 各 Agent 真实状态/能力 + BYOK Token 是否已配置（无明文）。"""
    store = SettingsStore()
    settings = store.load()
    secret = SecretStore()

    agents = []
    for name in registry_available():
        info: dict[str, Any] = {"id": name, "available": False, "capabilities": None, "error": None}
        try:
            adapter = registry_get_agent(name)
            info["available"] = True
            info["capabilities"] = adapter.capabilities()
        except Exception as exc:  # noqa: BLE001
            info["error"] = _friendly(exc)
        agents.append(info)

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
    }


def get_agent_options() -> dict:
    """动态选项：Qoder 自带模型 / BYOK provider-model / 思考强度档位。"""
    qoder_models: list[str] = []
    qoder_models_error: Optional[str] = None
    byok_providers: list[dict] = []
    byok_error: Optional[str] = None

    try:
        qoder_models = QoderAdapter().list_qoder_models()
    except Exception as exc:  # noqa: BLE001
        qoder_models_error = _friendly(exc)

    try:
        raw_providers = QoderAdapter().list_byok_providers()
        byok_providers = _shape_byok_providers(raw_providers)
    except Exception as exc:  # noqa: BLE001
        byok_error = _friendly(exc)

    return {
        "qoder_models": qoder_models,
        "qoder_models_error": qoder_models_error,
        "byok_providers": byok_providers,
        "byok_error": byok_error,
        "reasoning_effort_options": list(REASONING_EFFORT_OPTIONS),
    }


def _shape_byok_providers(raw: Optional[list[dict]]) -> list[dict]:
    """把官方 BYOKProviderInfo 目录压成前端需要的最小声（不含任何凭据）。"""
    out: list[dict] = []
    for p in raw or []:
        types = []
        for t in p.get("types") or []:
            models = []
            for m in t.get("models") or []:
                models.append({
                    "key": m.get("key"),
                    "display_name": m.get("display_name"),
                    "is_reasoning": m.get("is_reasoning"),
                    "efforts": m.get("efforts") or [],
                })
            types.append({
                "key": t.get("key"),
                "display_name": t.get("display_name"),
                "models": models,
            })
        out.append({
            "key": p.get("key"),
            "display_name": p.get("display_name"),
            "types": types,
        })
    return out


# ---------------- 保存 ----------------

def save_agent_settings(payload: dict) -> dict:
    """保存普通设置（不含 Token）。校验 Agent / 模式 / 思考强度合法值。"""
    if not isinstance(payload, dict):
        raise SettingsOpError("设置格式错误")

    agent = payload.get("default_agent")
    if agent not in VALID_AGENTS:
        raise SettingsOpError(f"未知 Agent：{agent}（可选：{'、'.join(VALID_AGENTS)}）")

    mode = payload.get("qoder_mode", "qoder_native")
    if mode not in VALID_QODER_MODES:
        raise SettingsOpError(f"Qoder 使用模式无效：{mode}")

    effort = payload.get("reasoning_effort")
    if effort is not None and effort not in REASONING_EFFORT_OPTIONS:
        raise SettingsOpError(f"思考强度无效：{effort}（可选：{'、'.join(REASONING_EFFORT_OPTIONS)}）")

    store = SettingsStore()
    current = store.load()

    settings = AppSettings(
        default_agent=agent,
        qoder_mode=mode,
        qoder_model=_str_or_none(payload.get("qoder_model")),
        reasoning_effort=effort,
        byok_provider=_str_or_none(payload.get("byok_provider")),
        byok_model=_str_or_none(payload.get("byok_model")),
        byok_secret_id=current.byok_secret_id,  # Token 引用保持原样，不接受前端改动
    )
    store.save(settings)
    return settings.to_dict()


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
    """测试连接：无副作用任务 + 临时目录，绝不修改作品。

    - deepseek_harness：走现有 Adapter（真实执行 headless 任务）
    - qoder + qoder_native：走 QoderAdapter CLI 路径
    - qoder + qoder_byok：仅当 keyring 已保存真实 Token 时才真实调用；
      未配置时明确返回“未配置”，不做第三方调用、不产生费用。
    """
    if not isinstance(payload, dict):
        raise SettingsOpError("测试参数格式错误")
    agent = payload.get("agent") or payload.get("default_agent")
    if agent not in VALID_AGENTS:
        raise SettingsOpError(f"未知 Agent：{agent}")

    tmp_dir = tempfile.mkdtemp(prefix="ai-write-conn-")
    request = AgentRequest(task=CONNECTION_PROBE_TASK, cwd=tmp_dir)

    try:
        if agent == "deepseek_harness":
            adapter = registry_get_agent("deepseek_harness")
            result = adapter.run(request)
        elif agent == "qoder":
            mode = payload.get("qoder_mode", "qoder_native")
            effort = payload.get("reasoning_effort")
            if mode == "qoder_byok":
                secret = SecretStore()
                token = secret.get_secret(BYOK_SECRET_ID)
                if not token:
                    return {
                        "agent": agent,
                        "status": "not_configured",
                        "message": "Qoder BYOK 未配置 Token：请先保存 API Key / Token 后再测试。",
                    }
                byok = QoderBYOKConfig(
                    provider=str(payload.get("byok_provider") or ""),
                    model=str(payload.get("byok_model") or ""),
                    api_key=token,
                    reasoning_effort=effort,
                )
                adapter = QoderAdapter(byok=byok)
                result = adapter.run(request)
            else:
                adapter = QoderAdapter()
                result = adapter.run(AgentRequest(
                    task=CONNECTION_PROBE_TASK,
                    cwd=tmp_dir,
                    model=_str_or_none(payload.get("qoder_model")),
                    reasoning_effort=effort,
                ))
        else:  # pragma: no cover - 上面已校验
            raise SettingsOpError(f"未知 Agent：{agent}")
    except SettingsOpError:
        raise
    except Exception as exc:  # noqa: BLE001
        return {"agent": agent, "status": "failed", "message": _friendly(exc)}

    if result.status == "completed":
        return {
            "agent": agent,
            "status": "ok",
            "message": "连接正常",
            "output": _clip_output(result.output),
        }
    return {
        "agent": agent,
        "status": "failed",
        "message": result.error or f"连接失败（{result.status}）",
        "output": _clip_output(result.output),
    }


def _clip_output(output: str) -> Optional[str]:
    """只给前端一个简短片段，避免回传大段内容。"""
    if not output:
        return None
    return output[:300]
