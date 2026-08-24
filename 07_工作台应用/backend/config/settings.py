# -*- coding: utf-8 -*-
"""Persisted Go Write execution choices, never credentials or discovered catalogs."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Optional

VALID_AGENTS = ("deepseek_harness", "qoder")
EXECUTION_MODE_INTERACTIVE = "interactive_bridge"
EXECUTION_MODE_DIRECT = "direct"
VALID_EXECUTION_MODES = (EXECUTION_MODE_INTERACTIVE, EXECUTION_MODE_DIRECT)
SETTINGS_FILENAME = "settings.json"


@dataclass
class AppSettings:
    default_execution_mode: str = EXECUTION_MODE_INTERACTIVE
    interactive_agent: str = "qoder"
    direct_agent: str = "qoder"
    direct_model: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "AppSettings":
        raw = raw or {}
        # Old profile and effort values represented adapter internals, not a
        # durable author choice. Preserve only a selected Qoder model.
        known = {field.name for field in fields(cls)}
        data = {key: value for key, value in raw.items() if key in known}
        legacy_agent = raw.get("default_agent")
        if "interactive_agent" not in data and legacy_agent in VALID_AGENTS:
            data["interactive_agent"] = legacy_agent
        if "direct_agent" not in data and legacy_agent in VALID_AGENTS:
            data["direct_agent"] = legacy_agent
        if "direct_model" not in data and data.get("direct_agent", legacy_agent) == "qoder":
            data["direct_model"] = raw.get("qoder_model")
        return cls(**data)


class SettingsError(Exception):
    pass


class SettingsStore:
    def __init__(self, config_dir: Optional[Path] = None) -> None:
        self._dir = Path(config_dir) if config_dir is not None else Path(os.environ.get("AI_WRITE_CONFIG_DIR") or Path.home() / ".ai-write")
        self._path = self._dir / SETTINGS_FILENAME

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> AppSettings:
        if not self._path.exists(): return AppSettings()
        try: return AppSettings.from_dict(json.loads(self._path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc: raise SettingsError(f"读取设置失败: {exc}") from exc

    def save(self, settings: AppSettings) -> None:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(settings.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc: raise SettingsError(f"保存设置失败: {exc}") from exc
