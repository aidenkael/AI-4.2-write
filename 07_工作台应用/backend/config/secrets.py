# -*- coding: utf-8 -*-
"""Token 安全存储（Python keyring → Windows 系统安全凭据存储）。

- 真正 Token 只进 keyring，永不写入 JSON / 源码 / 日志 / Git。
- AI-write 配置文件中只保存 provider / model / secret_id（keyring 引用）。
- 前端永远拿不到明文：Bridge 只暴露 has_secret / save / delete，
  get_secret 仅供后台（如测试连接）使用。
"""
from __future__ import annotations

from typing import Optional

# keyring 服务名 + 当前 BYOK 凭据 id（配置文件中保存此引用，而非 Token）
SERVICE_NAME = "ai-write"
BYOK_SECRET_ID = "qoder_byok"

try:  # keyring 已安装到 .venv；缺失时仍可 import 本模块，调用时再报错
    import keyring as _keyring
except Exception:  # pragma: no cover - 仅环境缺依赖时
    _keyring = None  # type: ignore[assignment]


class SecretError(Exception):
    """Token 存储错误（面向 UI 的稳定错误类型，不含明文）。"""


class SecretStore:
    """keyring 封装：save / has / delete / get（get 仅后台用）。"""

    def __init__(self, service: str = SERVICE_NAME) -> None:
        self._service = service

    def _kr(self):
        if _keyring is None:
            raise SecretError("keyring 未安装，无法安全保存 Token")
        return _keyring

    def save_secret(self, secret_id: str, token: str) -> None:
        if not token:
            raise SecretError("Token 不能为空")
        try:
            self._kr().set_password(self._service, secret_id, token)
        except Exception as exc:  # noqa: BLE001
            raise SecretError(f"保存 Token 失败（系统凭据存储不可用）") from exc

    def has_secret(self, secret_id: str) -> bool:
        try:
            return self.get_secret(secret_id) is not None
        except SecretError:
            return False

    def delete_secret(self, secret_id: str) -> bool:
        try:
            self._kr().delete_password(self._service, secret_id)
            return True
        except Exception:  # noqa: BLE001 - 不存在等同已删除
            return False

    def get_secret(self, secret_id: str) -> Optional[str]:
        """仅供后台使用（测试连接等），禁止返回给前端。"""
        try:
            return self._kr().get_password(self._service, secret_id)
        except Exception as exc:  # noqa: BLE001
            raise SecretError(f"读取 Token 失败（系统凭据存储不可用）") from exc
