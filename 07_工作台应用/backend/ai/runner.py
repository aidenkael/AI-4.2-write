# -*- coding: utf-8 -*-
"""Direct AI 薄通道：备好上下文 → 一次 OpenAI 兼容请求 → 返回 assistant 文本。

边界（与 长期开发手册 §15.6 一致）：
- 无工具循环、无 provider 插件、无 memory / workflow / session；
- 不重复 settlement schema 校验（既有 settlement 解析器继续是语义合同）；
- 绝不直接写项目文件；输出只是文本，写回由调用方既有校验门负责；
- API Key 只进 OS keyring；持久化配置只有非机密的 base_url / model；
- 配置缺失时抛作者可读的 SemanticAiConfigError（配置状态，不是故事数据）。
"""
from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from config.secrets import SecretStore

SEMANTIC_SETTINGS_FILENAME = "semantic_ai_settings.json"
SEMANTIC_API_KEY_SECRET_ID = "semantic_ai_api_key"
DEFAULT_TIMEOUT_SECONDS = 180.0


class SemanticAiConfigError(Exception):
    """日常 AI 配置缺失/非法：作者需在设置中配置后才能同步语义状态。"""


class SemanticAiRunError(Exception):
    """日常 AI 请求失败：可恢复、可重试，绝不回退 Agent。"""


@dataclass(frozen=True)
class SemanticAiConfig:
    base_url: str
    model: str

    @property
    def complete(self) -> bool:
        return bool(self.base_url and self.model)


def _settings_path() -> Path:
    root = os.environ.get("AI_WRITE_CONFIG_DIR")
    base = Path(root) if root else Path.home() / ".ai-write"
    return base / SEMANTIC_SETTINGS_FILENAME


def load_semantic_ai_config() -> SemanticAiConfig:
    """只读非机密配置；文件缺失/损坏时返回空配置（视为未配置）。"""
    path = _settings_path()
    raw: dict[str, Any] = {}
    if path.exists():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            raw = value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            raw = {}
    return SemanticAiConfig(
        base_url=str(raw.get("semantic_ai_base_url") or "").strip(),
        model=str(raw.get("semantic_ai_model") or "").strip(),
    )


def save_semantic_ai_config(base_url: str, model: str) -> SemanticAiConfig:
    """原子保存非机密配置；绝不把 API Key 写进该文件。"""
    normalized_url = str(base_url or "").strip()
    normalized_model = str(model or "").strip()
    if not normalized_url.startswith(("http://", "https://")):
        raise SemanticAiConfigError("API 地址必须以 http:// 或 https:// 开头。")
    if not normalized_model:
        raise SemanticAiConfigError("模型不能为空。")
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"semantic_ai_base_url": normalized_url, "semantic_ai_model": normalized_model}
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".gowrite-semantic-ai-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return SemanticAiConfig(base_url=normalized_url, model=normalized_model)


def has_semantic_api_key() -> bool:
    return SecretStore().has_secret(SEMANTIC_API_KEY_SECRET_ID)


def save_semantic_api_key(token: str) -> None:
    SecretStore().save_secret(SEMANTIC_API_KEY_SECRET_ID, token)


def require_semantic_ai() -> tuple[SemanticAiConfig, str]:
    """完整配置（base_url / model / keyring API Key）；缺失抛作者可读错误。"""
    config = load_semantic_ai_config()
    if not config.complete:
        raise SemanticAiConfigError('缺少日常 AI 设置，请在「设置 - 日常 AI」中配置 API 地址与模型。')
    try:
        api_key = SecretStore().get_secret(SEMANTIC_API_KEY_SECRET_ID)
    except Exception as exc:  # noqa: BLE001 - keyring 不可用同样属于“未配置”
        raise SemanticAiConfigError('系统凭据存储不可用，无法读取日常 AI API Key。') from exc
    if not api_key:
        raise SemanticAiConfigError('缺少日常 AI API Key，请在「设置 - 日常 AI」中保存。')
    return config, api_key


def run_text(prompt: str, *, timeout: Optional[float] = None) -> str:
    """一次 OpenAI 兼容 chat completion；返回 assistant 文本。

    任何失败（配置缺失、网络、HTTP 错误、空响应）都抛稳定错误类型；
    绝不静默回退其它执行路径。
    """
    config, api_key = require_semantic_ai()
    url = config.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout or DEFAULT_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:300]
        except OSError:
            pass
        message = f"日常 AI 请求失败（HTTP {exc.code}）。"
        if detail:
            message += f"响应：{detail}"
        raise SemanticAiRunError(message) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SemanticAiRunError(f"日常 AI 请求失败：{exc}") from exc
    try:
        parsed = json.loads(body)
        choices = parsed.get("choices") or []
        content = (choices[0].get("message") or {}).get("content") if choices else None
    except (json.JSONDecodeError, IndexError, AttributeError, TypeError) as exc:
        raise SemanticAiRunError("日常 AI 响应格式非法。") from exc
    if not isinstance(content, str) or not content.strip():
        raise SemanticAiRunError("日常 AI 响应内容为空。")
    return content
