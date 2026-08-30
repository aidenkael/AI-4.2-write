# -*- coding: utf-8 -*-
"""Settings persistence and local-only capability checks.

职责分离（对应真实作者使用修复）：
- 持久化设置（`SettingsStore`）与"本机能力发现"（`registry_discover_all`）
  是两个独立关注点；
- 打开设置页默认只读**已保存配置** + 复用**上次发现快照**（in-process
  last-known cache），绝不每次挂载都重跑昂贵 CLI/profile 发现；
- “重新检测”显式强制刷新发现并更新缓存；
- 保存只校验结构合法性；已保存的模型在未重新检测时不会被当作不可用拒绝
  （不因本页会话未重跑发现而作废已保存配置）。
"""
from __future__ import annotations

import datetime
from typing import Any, Optional

from agents.qoder import install_command as install_qoder_command
from agents.registry import discover_all as registry_discover_all
from config.settings import EXECUTION_MODE_DIRECT, VALID_AGENTS, VALID_EXECUTION_MODES, AppSettings, SettingsStore
from ai import runner as semantic_ai


class SettingsOpError(Exception): pass


# ---------------------------------------------------------------------------
# last-known discovery cache（in-process，非权威；只为避免每次挂载重跑发现）
# ---------------------------------------------------------------------------

_DISCOVERY_CACHE: dict[str, Any] = {"agents": None, "discovered_at": None, "source_fn": None}


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _discover(force: bool = False) -> tuple[list[dict], str, bool]:
    """返回 (agents, discovered_at, was_cached)。

    默认复用缓存；force=True（“重新检测”/安装修复后）强制重跑并更新缓存。
    缓存记录构建它的发现函数身份：一旦发现函数被替换（测试 monkeypatch /
    热重载），立即视为过期重跑，避免跨测试/跨实现串用旧快照。
    """
    current_fn = registry_discover_all
    cached = _DISCOVERY_CACHE.get("agents")
    if (
        not force
        and cached is not None
        and _DISCOVERY_CACHE.get("source_fn") is current_fn
    ):
        return cached, _DISCOVERY_CACHE.get("discovered_at") or "", True
    agents = current_fn()
    now = _now_iso()
    _DISCOVERY_CACHE["agents"] = agents
    _DISCOVERY_CACHE["discovered_at"] = now
    _DISCOVERY_CACHE["source_fn"] = current_fn
    return agents, now, False


def _refresh_cache(agents: list[dict]) -> None:
    _DISCOVERY_CACHE["agents"] = agents
    _DISCOVERY_CACHE["discovered_at"] = _now_iso()
    _DISCOVERY_CACHE["source_fn"] = registry_discover_all


def reset_discovery_cache() -> None:
    """测试钩子：清空缓存（强制下一次调用重跑发现）。"""
    _DISCOVERY_CACHE["agents"] = None
    _DISCOVERY_CACHE["discovered_at"] = None
    _DISCOVERY_CACHE["source_fn"] = None


def get_agent_settings() -> dict:
    """已保存设置 + 本机发现（复用 last-known 快照；首次无快照时才跑一次）。"""
    agents, discovered_at, cached = _discover()
    return {
        "settings": SettingsStore().load().to_dict(),
        "agents": agents,
        "discovery": {"source": "cache" if cached else "fresh", "discovered_at": discovered_at},
    }


def discover_agent_environment() -> dict:
    """显式“重新检测”：强制重跑本机 Agent/模型目录发现并更新 last-known 快照。"""
    agents, discovered_at, _ = _discover(force=True)
    return {"agents": agents, "discovery": {"source": "fresh", "discovered_at": discovered_at}}


def _agent(agent_id: str) -> Optional[dict]:
    return next((item for item in _discover()[0] if item.get("agent_id") == agent_id), None)


def _validate_direct(
    agent_id: str,
    model_id: Optional[str],
    custom_model_id: Optional[str] = None,
    allow_saved_model: Optional[str] = None,
    allow_saved_custom_model: Optional[str] = None,
) -> None:
    """直连配置校验。

    - Agent 必须是当前发现中 direct 可用的；
    - 恰好选择一个内置或自定义模型；
    - 新选模型必须出现在当前发现的可选项里；
    - **已保存模型**即使当前发现未包含（本页会话未重跑发现/环境变更）也允许
      原样重新保存，绝不因为"未重新检测"就作废已保存配置。
    """
    agent = _agent(agent_id)
    direct = (agent or {}).get("direct") or {}
    if not agent or direct.get("available") is False:
        raise SettingsOpError("所选直接执行 Agent 当前不可用，请重新检测后重试")
    if bool(model_id) == bool(custom_model_id):
        raise SettingsOpError("请选择一个内置模型或自定义模型")
    models = {str(model.get("id")) for model in direct.get("models") or [] if model.get("selectable") is True}
    custom_models = {str(model.get("id")) for model in direct.get("custom_models") or [] if model.get("selectable") is True}
    if model_id:
        if model_id in models:
            return
        if allow_saved_model is not None and model_id == allow_saved_model:
            return  # 原样重存已保存配置：不因未重跑发现而拒绝
        raise SettingsOpError("所选内置模型当前不可用，请重新检测后重新选择")
    if custom_model_id:
        if custom_model_id in custom_models:
            return
        if allow_saved_custom_model is not None and custom_model_id == allow_saved_custom_model:
            return
        raise SettingsOpError("所选自定义模型当前不可用，请重新检测后重新选择")


def save_agent_settings(payload: dict) -> dict:
    if not isinstance(payload, dict): raise SettingsOpError("设置格式错误")
    current = SettingsStore().load()
    mode = str(payload.get("default_execution_mode") or current.default_execution_mode)
    interactive = str(payload.get("interactive_agent") or current.interactive_agent)
    direct = str(payload.get("direct_agent") or current.direct_agent)
    model = _str_or_none(payload.get("direct_model", current.direct_model))
    custom_model = _str_or_none(payload.get("direct_custom_model", current.direct_custom_model))
    if mode not in VALID_EXECUTION_MODES: raise SettingsOpError(f"执行模式无效：{mode}")
    if interactive not in VALID_AGENTS or direct not in VALID_AGENTS: raise SettingsOpError("未知 Agent")
    if mode == EXECUTION_MODE_DIRECT:
        _validate_direct(direct, model, custom_model,
                         allow_saved_model=current.direct_model,
                         allow_saved_custom_model=current.direct_custom_model)
    # A bridge can only be selected after its command is actually ready.
    if mode != EXECUTION_MODE_DIRECT:
        bridge = ((_agent(interactive) or {}).get("interactive") or {})
        if not bridge.get("bridge_ready"): raise SettingsOpError("所选 Agent 的 /gowrite 交互桥尚未就绪")
    settings = AppSettings(default_execution_mode=mode, interactive_agent=interactive, direct_agent=direct, direct_model=model, direct_custom_model=custom_model)
    SettingsStore().save(settings)
    return settings.to_dict()


def install_or_repair_interactive_command(payload: dict) -> dict:
    if not isinstance(payload, dict) or payload.get("agent") != "qoder": raise SettingsOpError("当前仅 Qoder CN 支持安装 /gowrite 命令")
    result = install_qoder_command()
    if result.get("status") == "error" or not result.get("command_ready"):
        raise SettingsOpError("；".join(result.get("errors") or ["Qoder Desktop 未识别已安装的 /gowrite 命令"]))
    discovery = registry_discover_all()
    _refresh_cache(discovery)
    agent = next((item for item in discovery if item.get("agent_id") == "qoder"), None) or {}
    interactive = agent.get("interactive") or {}
    if not interactive.get("bridge_ready"):
        result.update({"status": "error", "errors": ["命令已写入，但 Qoder Desktop 尚未检测到可用交互桥"], "discovery": discovery})
        raise SettingsOpError(result["errors"][0])
    result["discovery"] = discovery
    return result


def _str_or_none(value: Any) -> Optional[str]:
    return str(value).strip() or None if value is not None else None


# ---------------------------------------------------------------------------
# 日常 AI（Direct AI 语义结算）独立设置：与 Agent 执行设置完全分离。
# 只持久化非机密配置（API 地址 / 模型）；API Key 只进 OS keyring。
# ---------------------------------------------------------------------------


def get_semantic_ai_settings() -> dict:
    config = semantic_ai.load_semantic_ai_config()
    return {
        "semantic_ai_base_url": config.base_url,
        "semantic_ai_model": config.model,
        "has_api_key": semantic_ai.has_semantic_api_key(),
        "configured": config.complete and semantic_ai.has_semantic_api_key(),
    }


def save_semantic_ai_settings(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise SettingsOpError("设置格式错误")
    base_url = str(payload.get("semantic_ai_base_url") or "").strip()
    model = str(payload.get("semantic_ai_model") or "").strip()
    api_key = payload.get("api_key")
    try:
        config = semantic_ai.save_semantic_ai_config(base_url, model)
        if isinstance(api_key, str) and api_key.strip():
            semantic_ai.save_semantic_api_key(api_key.strip())
    except semantic_ai.SemanticAiConfigError as exc:
        raise SettingsOpError(str(exc)) from exc
    return get_semantic_ai_settings()


def test_agent_connection(payload: dict) -> dict:
    if not isinstance(payload, dict): raise SettingsOpError("测试参数格式错误")
    agent_id = payload.get("agent")
    if agent_id not in VALID_AGENTS: raise SettingsOpError("未知 Agent")
    try: _validate_direct(str(agent_id), _str_or_none(payload.get("model")), _str_or_none(payload.get("custom_model")))
    except SettingsOpError as exc: return {"agent": agent_id, "status": "not_configured", "message": f"{exc}；未发送模型请求。"}
    return {"agent": agent_id, "status": "ok", "message": "本机执行入口与当前配置已检测到；未调用模型或远端服务。"}
