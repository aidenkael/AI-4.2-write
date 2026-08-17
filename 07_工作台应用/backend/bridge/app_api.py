# -*- coding: utf-8 -*-
"""AI-write 唯一 Bridge 入口（桌面壳 ↔ React）。

- React 侧唯一调用位置：ui/src/bridge/client.ts（组件禁止直接碰 window.pywebview.api）
- Python 侧唯一暴露入口：本模块 AppApi
- 方法一律返回 JSON 可序列化结构：{ok: true, data: ...} 或 {ok: false, error: str}
- 业务（真实作品浏览）经 operations → views → ProjectWorkspace（只读）；
  本轮不暴露任何修改 authority 的能力。
"""
from __future__ import annotations

from operations.projects import (
    ProjectOpError,
    get_project_overview as op_get_project_overview,
    list_projects as op_list_projects,
    open_project as op_open_project,
)
from views import project as project_views


class AppApi:
    """暴露给 React（window.pywebview.api）的桥接 API。"""

    # ---------------- 骨架验证 ----------------

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

    # ---------------- 真实作品浏览（只读） ----------------

    def list_projects(self) -> dict:
        """真实作品列表（03_作品工程，经 ProjectWorkspace.list_projects）。"""
        try:
            projects = op_list_projects()
            return {"ok": True, "data": {"projects": project_views.list_view(projects)}}
        except Exception as exc:  # noqa: BLE001 — bridge 边界统一兜底
            return {"ok": False, "error": str(exc)}

    def open_project(self, project) -> dict:
        """以 project_id（优先）或作品名打开作品。不持久化“当前项目”。"""
        try:
            opened = op_open_project(project)
            return {"ok": True, "data": project_views.open_view(opened)}
        except ProjectOpError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    def get_project_overview(self, project_id: str) -> dict:
        """最小作品概览（只读正式状态）。"""
        try:
            overview = op_get_project_overview(project_id)
            return {"ok": True, "data": project_views.overview_view(overview)}
        except ProjectOpError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
