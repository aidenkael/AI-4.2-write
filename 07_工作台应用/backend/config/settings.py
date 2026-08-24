# -*- coding: utf-8 -*-
"""普通设置存储（不含任何 Token）。

- 保存交互桥/直接执行的选择标识，以及兼容旧运行入口所需的 Qoder 字段。
- Token 永不写入本文件（见 secrets.py，真正 Token 在 Windows 凭据存储）。
- 配置文件默认放用户主目录 ~/.ai-write/settings.json（可用环境变量
  AI_WRITE_CONFIG_DIR 覆盖，测试用临时目录）。
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Optional

# 当前注册的 Agent（与 registry 一致；Codex 未实现，不出现在候选里）
VALID_AGENTS = ("deepseek_harness", "qoder")

EXECUTION_MODE_INTERACTIVE = "interactive_bridge"
EXECUTION_MODE_DIRECT = "direct"
VALID_EXECUTION_MODES = (EXECUTION_MODE_INTERACTIVE, EXECUTION_MODE_DIRECT)

# Qoder CLI / SDK 当前真实支持的 reasoning effort 档位（来自官方枚举，不硬编码模型名）
REASONING_EFFORT_OPTIONS = ("none", "low", "medium", "high", "xhigh", "max")

SETTINGS_FILENAME = "settings.json"

@dataclass
class AppSettings:
    """AI-write 应用普通设置（可 JSON 序列化，不含 Token）。"""

    default_execution_mode: str = EXECUTION_MODE_INTERACTIVE
    interactive_agent: str = "qoder"
    direct_agent: str = "qoder"
    direct_profile_id: Optional[str] = None
    direct_model: Optional[str] = None

    reasoning_effort: Optional[str] = None
    # Constructor-only migration shims for older callers. They are deliberately
    # excluded from persisted JSON and never form part of the new contract.
    default_agent: Optional[str] = None
    qoder_mode: Optional[str] = None

    def __post_init__(self) -> None:
        if self.default_agent in VALID_AGENTS:
            self.interactive_agent = self.default_agent
            self.direct_agent = self.default_agent

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("default_agent", None)
        data.pop("qoder_mode", None)
        return data

    @classmethod
    def from_dict(cls, raw: dict) -> "AppSettings":
        """只取已知字段，并从旧 settings.json 做最小兼容迁移。"""
        raw = raw or {}
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in raw.items() if k in known}
        settings = cls(**data)
        legacy_agent = str(raw.get("default_agent") or "qoder")
        if "interactive_agent" not in raw:
            settings.interactive_agent = legacy_agent
        if "direct_agent" not in raw:
            settings.direct_agent = legacy_agent
        if "direct_profile_id" not in raw:
            if legacy_agent == "deepseek_harness":
                settings.direct_profile_id = "headless"
            elif raw.get("qoder_model"):
                settings.direct_profile_id = "qoder_cn"
        if "direct_model" not in raw:
            settings.direct_model = raw.get("qoder_model") if legacy_agent == "qoder" else None
        return settings


class SettingsError(Exception):
    """普通设置错误（面向 UI 的稳定错误类型）。"""


class SettingsStore:
    """settings.json 的读写（最小，不做 schema 版本迁移）。"""

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        # 构造时解析（而非 import 时），便于测试用 AI_WRITE_CONFIG_DIR 覆盖
        if config_dir is not None:
            self._dir = Path(config_dir)
        else:
            env_dir = os.environ.get("AI_WRITE_CONFIG_DIR", "")
            self._dir = Path(env_dir) if env_dir else (Path.home() / ".ai-write")
        self._path = self._dir / SETTINGS_FILENAME

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> AppSettings:
        if not self._path.exists():
            return AppSettings()
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SettingsError(f"读取设置失败: {exc}") from exc
        return AppSettings.from_dict(raw)

    def save(self, settings: AppSettings) -> None:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(settings.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise SettingsError(f"保存设置失败: {exc}") from exc
