# -*- coding: utf-8 -*-
"""普通设置存储（不含任何 Token）。

- 保存内容：default_agent / qoder_mode / qoder_model / reasoning_effort /
  byok_provider / byok_model / byok_secret_id（keyring 引用，非明文）。
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

# Qoder 使用模式
QODER_MODE_NATIVE = "qoder_native"
QODER_MODE_BYOK = "qoder_byok"
VALID_QODER_MODES = (QODER_MODE_NATIVE, QODER_MODE_BYOK)

# 当前注册的 Agent（与 registry 一致；Codex 未实现，不出现在候选里）
VALID_AGENTS = ("deepseek_harness", "qoder")

# Qoder CLI / SDK 当前真实支持的 reasoning effort 档位（来自官方枚举，不硬编码模型名）
REASONING_EFFORT_OPTIONS = ("none", "low", "medium", "high", "xhigh", "max")

SETTINGS_FILENAME = "settings.json"

@dataclass
class AppSettings:
    """AI-write 应用普通设置（可 JSON 序列化，不含 Token）。"""

    default_agent: str = "qoder"
    qoder_mode: str = QODER_MODE_NATIVE  # qoder_native | qoder_byok
    qoder_model: Optional[str] = None      # Qoder 自带模型名（动态列表取值）
    reasoning_effort: Optional[str] = None  # low / medium / high
    byok_provider: Optional[str] = None    # BYOK 服务商 key（动态列表取值）
    byok_model: Optional[str] = None       # BYOK 模型 key（动态列表取值）
    byok_secret_id: Optional[str] = None   # keyring 引用 id（非 Token 明文）

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "AppSettings":
        """只取已知字段；未知字段（如误入的 Token）一律丢弃。"""
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in (raw or {}).items() if k in known}
        return cls(**data)


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
