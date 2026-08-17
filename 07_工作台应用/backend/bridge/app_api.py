# -*- coding: utf-8 -*-
"""AI-write 唯一 Bridge 入口（桌面壳 ↔ React）。

- React 侧唯一调用位置：ui/src/bridge/client.ts（组件禁止直接碰 window.pywebview.api）
- Python 侧唯一暴露入口：本模块 AppApi
- 第一轮骨架仅提供 get_app_status() 验证桌面壳 ↔ React 链路；
  不接入任何 Skill / 项目 / 知识数据。
"""
from __future__ import annotations


class AppApi:
    """暴露给 React（window.pywebview.api）的桥接 API。"""

    def get_app_status(self) -> dict:
        """骨架验证：返回应用状态（pywebview 自动把 dict 序列化为 JSON 对象）。"""
        return {
            "ok": True,
            "data": {
                "app_name": "AI-write",
                "status": "ready",
                "message": "工作台连接正常",
            },
        }
