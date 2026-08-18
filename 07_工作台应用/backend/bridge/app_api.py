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
from operations.settings import SettingsOpError
from operations import settings as settings_ops
from operations.new_project import NewProjectError
from operations import new_project as new_project_ops
from operations.story_planning import StoryPlanningError
from operations import story_planning as story_planning_ops
from operations.story_writing import StoryWritingError
from operations import story_writing as story_writing_ops
from views import project as project_views

# 稳定错误码（client.ts 依赖 code 字段）
CODE_PROJECT_OP_ERROR = "PROJECT_OP_ERROR"
CODE_SETTINGS_ERROR = "SETTINGS_ERROR"
CODE_NEW_PROJECT_ERROR = "NEW_PROJECT_ERROR"
CODE_STORY_PLANNING_ERROR = "STORY_PLANNING_ERROR"
CODE_STORY_WRITING_ERROR = "STORY_WRITING_ERROR"
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

    # ---------------- Agent / 模型 / Token 设置（最小配置层） ----------------
    # 安全：任何 Bridge 返回值都不得包含 Token 明文（save 只存 keyring，
    # 读取只回 has_secret；get_secret 仅后台测试连接使用）。

    def get_agent_settings(self) -> dict:
        """当前设置 + 各 Agent 真实状态/能力 + BYOK Token 是否已配置（无明文）。"""
        try:
            return _ok(settings_ops.get_agent_settings())
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def get_agent_options(self) -> dict:
        """动态选项：Qoder 自带模型 / BYOK provider-model / 思考强度档位。"""
        try:
            return _ok(settings_ops.get_agent_options())
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def save_agent_settings(self, settings: dict) -> dict:
        """保存普通设置（不含 Token）；非法 Agent / 模式 / 思考强度会被拒绝。"""
        try:
            saved = settings_ops.save_agent_settings(settings)
            return _ok({"settings": saved})
        except SettingsOpError as exc:
            return _err(CODE_SETTINGS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def save_byok_secret(self, token: str) -> dict:
        """保存 BYOK Token 到 keyring；配置只写 secret_id 引用。"""
        try:
            return _ok(settings_ops.save_byok_secret(token))
        except SettingsOpError as exc:
            return _err(CODE_SETTINGS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def delete_byok_secret(self) -> dict:
        """删除 keyring 中的 BYOK Token，状态立即变为未配置。"""
        try:
            return _ok(settings_ops.delete_byok_secret())
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def test_agent_connection(self, payload: dict) -> dict:
        """测试连接：无副作用任务 + 临时目录；BYOK 未配置 Token 时不真实调用。"""
        try:
            return _ok(settings_ops.test_agent_connection(payload))
        except SettingsOpError as exc:
            return _err(CODE_SETTINGS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    # ---------------- 新建作品（"我有个想法"纵切） ----------------
    # 确认前只写临时 pre-project 工作区；只有作者明确确认（带后台 proposal token）
    # 才调用真实 ProjectWorkspace.create_project。

    def propose_new_project(self, payload: dict) -> dict:
        """我有个想法 → 当前 Agent 设置 → StoryDesign 候选（proposal_noncanonical）。"""
        try:
            data = new_project_ops.propose_new_project(
                name=str(payload.get("name") or ""),
                idea=str(payload.get("idea") or ""),
            )
            return _ok(data)
        except NewProjectError as exc:
            return _err(CODE_NEW_PROJECT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def confirm_new_project(self, payload: dict) -> dict:
        """作者明确确认 → 用后台保存的候选创建正式作品。"""
        try:
            data = new_project_ops.confirm_new_project(
                proposal_token=str(payload.get("proposal_token") or ""),
            )
            return _ok(data)
        except NewProjectError as exc:
            return _err(CODE_NEW_PROJECT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    # ---------------- 故事规划（"一起往前想"纵切） ----------------
    # 确认前只写临时 planning 工作区；只有作者明确确认（带后台 planning token）
    # 才写入正式 Story State 的 approved_plan。

    def propose_story_plan(self, payload: dict) -> dict:
        """一起往前想 → 当前 Agent 设置 → StoryPlan 候选（proposal_noncanonical）。"""
        try:
            data = story_planning_ops.propose_story_plan(
                project_id=str(payload.get("project_id") or ""),
                author_question=str(payload.get("author_question") or ""),
            )
            return _ok(data)
        except StoryPlanningError as exc:
            return _err(CODE_STORY_PLANNING_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def confirm_story_plan(self, payload: dict) -> dict:
        """作者明确确认 → 用后台保存的候选写入正式 approved_plan。"""
        try:
            data = story_planning_ops.confirm_story_plan(
                project_id=str(payload.get("project_id") or ""),
                planning_token=str(payload.get("planning_token") or ""),
            )
            return _ok(data)
        except StoryPlanningError as exc:
            return _err(CODE_STORY_PLANNING_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    # ---------------- 正文写作（"这一段想写什么"纵切） ----------------
    # 确认前只写临时 writing 工作区；只有作者明确确认（带后台 writing token）
    # 才通过 ProjectWorkspace.accept_prose 写入正式 03_正文。

    def propose_story_write(self, payload: dict) -> dict:
        """这一段想写什么 → 两阶段 Agent → 正文候选（不写正式作品）。"""
        try:
            data = story_writing_ops.propose_story_write(
                project_id=str(payload.get("project_id") or ""),
                author_input=str(payload.get("author_input") or ""),
            )
            return _ok(data)
        except StoryWritingError as exc:
            return _err(CODE_STORY_WRITING_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def confirm_story_write(self, payload: dict) -> dict:
        """作者明确"保留这段" → accept_prose 写入正式 03_正文。"""
        try:
            data = story_writing_ops.confirm_story_write(
                project_id=str(payload.get("project_id") or ""),
                writing_token=str(payload.get("writing_token") or ""),
            )
            return _ok(data)
        except StoryWritingError as exc:
            return _err(CODE_STORY_WRITING_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))
