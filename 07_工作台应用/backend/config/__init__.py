# -*- coding: utf-8 -*-
"""AI-write 应用配置层（backend/config）。

- settings.py：普通设置（默认 Agent / Qoder 模式 / 模型 / 思考强度 / BYOK 引用）存 JSON，
  永不写入 Token。
- secrets.py：Token 经 Python keyring 存 Windows 系统安全凭据存储，仅后台读写。
"""
