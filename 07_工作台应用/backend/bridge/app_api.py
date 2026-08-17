# -*- coding: utf-8 -*-
"""AI-write 唯一 Bridge 入口（桌面壳 ↔ React）。

- React 侧唯一调用位置：ui/src/bridge/client.ts（组件禁止直接碰 window.pywebview.api）
- Python 侧唯一暴露入口：本模块 AppApi
- **统一返回合同**（所有方法一致，JSON 可序列化）：
  成功：{"ok": true,  "data": ...,                "error": null}
  失败：{"ok": false, "data": null, "error": {"code": str, "message": str}}
- 业务（真实作品浏览）经 operations → views → ProjectWorkspace（只读）
"""
from __future__ import annotations

from operations.projects import (
    ProjectOpError,
    get_project_overview as op_get_project_overview,
    list_projects as op_list_projects,
    open_project as op_open_project,
)
from views import project as project_views

# 稳定错误码（client.ts 依赖 code 字段）
CODE_PROJECT_OP_ERROR = "PROJECT_OP_ERROR"
CODE_BRIDGE_INTERNAL = "BRIDGE_INTERNAL"


def _ok(data) -> dict:
    return {"ok": True, "data": data, "error": None}


def _err(code: str, message: str) -> dict:
    return {"ok": False, "data": None, "error": {"code": code, "message": message}}


class AppApi:
    """暴露给 React（window.pywebview.api）的桥接 API。"""

    # ---------------- 骨架验证 ----------------

    def get_app_status(self) -> dict:
        return _ok({
            "app_name": "AI-write",
            "status": "ready",
            "message": "工作台连接正常",
        })

    # ---------------- 真实作品浏览（只读） ----------------

    def list_projects(self) -> dict:
        try:
            projects = op_list_projects()
            return _ok({"projects": project_views.list_view(projects)})
        except Exception as exc:  # noqa: BLE001 — bridge 边界统一兜底
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def open_project(self, project) -> dict:
        try:
            opened = op_open_project(project)
            return _ok(project_views.open_view(opened))
        except ProjectOpError as exc:
            return _err(CODE_PROJECT_OP_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def get_project_overview(self, project_id: str) -> dict:
        try:
            overview = op_get_project_overview(project_id)
            return _ok(project_views.overview_view(overview))
        except ProjectOpError as exc:
            return _err(CODE_PROJECT_OP_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))
