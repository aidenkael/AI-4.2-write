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
from operations.foundation_design import FoundationDesignError
from operations import foundation_design as foundation_design_ops
from operations import qoder_bridge as bridge_ops
from operations.story_planning import StoryPlanningError
from operations import story_planning as story_planning_ops
from operations.story_writing import StoryWritingError
from operations import story_writing as story_writing_ops
from operations.ideas import IdeasError
from operations import ideas as ideas_ops
from operations.materials import MaterialsError
from operations import materials as materials_ops
from operations.project_data import ProjectDataError
from operations import project_data as project_data_ops
from operations.author_edit import AuthorEditError
from operations import author_edit as author_edit_ops
from operations.project_model import ProjectModelError
from operations import project_model as project_model_ops
from operations.change_settlement import ChangeSettlementError
from operations import change_settlement as change_settlement_ops
from operations.review import ReviewError
from operations import review as review_ops
from operations import author_operation as author_operation_ops
from operations import execution_audit as audit_ops
from views import project as project_views

# 稳定错误码（client.ts 依赖 code 字段）
CODE_PROJECT_OP_ERROR = "PROJECT_OP_ERROR"
CODE_SETTINGS_ERROR = "SETTINGS_ERROR"
CODE_NEW_PROJECT_ERROR = "NEW_PROJECT_ERROR"
CODE_FOUNDATION_DESIGN_ERROR = "FOUNDATION_DESIGN_ERROR"
CODE_STORY_PLANNING_ERROR = "STORY_PLANNING_ERROR"
CODE_STORY_WRITING_ERROR = "STORY_WRITING_ERROR"
CODE_IDEAS_ERROR = "IDEAS_ERROR"
CODE_MATERIALS_ERROR = "MATERIALS_ERROR"
CODE_PROJECT_DATA_ERROR = "PROJECT_DATA_ERROR"
CODE_AUTHOR_EDIT_ERROR = "AUTHOR_EDIT_ERROR"
CODE_PLANNING_IMPACT_ERROR = "PLANNING_IMPACT_ERROR"
CODE_CHANGE_SETTLEMENT_ERROR = "CHANGE_SETTLEMENT_ERROR"
CODE_REVIEW_ERROR = "REVIEW_ERROR"
CODE_BRIDGE_INTERNAL = "BRIDGE_INTERNAL"


def _ok(data) -> dict:
    return {"ok": True, "data": data, "error": None}


def _err(code: str, message: str) -> dict:
    return {"ok": False, "data": None, "error": {"code": code, "message": message}}


def _annotate_settlement_liveness(data: dict, project_id: str) -> dict:
    """Attach the author-triggered refresh read model to every project view."""
    refresh = change_settlement_ops.get_project_state_refresh(project_id)
    data["state_refresh"] = refresh
    settlement = data.get("settlement") if isinstance(data, dict) else None
    if isinstance(settlement, dict):
        settlement["worker_active"] = bool(refresh.get("worker_active"))
    return data


class AppApi:
    """暴露给 React（window.pywebview.api）的桥接 API。"""

    # ---------------- 骨架验证 ----------------

    def get_app_status(self) -> dict:
        return _ok({
            "app_name": "Go Write",
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
        """当前设置 + last-known 本机 Agent 状态/能力 + BYOK Token 是否已配置（无明文）。

        打开设置页默认**不重跑**昂贵发现：复用进程内上次发现快照；首次无快照
        时才执行一次真实发现。
        """
        try:
            return _ok(settings_ops.get_agent_settings())
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def discover_agent_environment(self) -> dict:
        """显式“重新检测”：强制刷新本机 Agent / 模型目录并更新 last-known 快照。"""
        try:
            return _ok(settings_ops.discover_agent_environment())
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

    def install_or_repair_interactive_command(self, payload: dict) -> dict:
        """安装或修复当前 Agent 官方位置的 /gowrite 命令。"""
        try:
            return _ok(settings_ops.install_or_repair_interactive_command(payload))
        except SettingsOpError as exc:
            return _err(CODE_SETTINGS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def test_agent_connection(self, payload: dict) -> dict:
        """测试连接：只检查本机 discovery/profile/auth，不执行模型。"""
        try:
            return _ok(settings_ops.test_agent_connection(payload))
        except SettingsOpError as exc:
            return _err(CODE_SETTINGS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    # ---------------- 日常 AI（Direct AI 语义结算）独立设置 ----------------
    # 与 Agent 执行设置完全分离；API Key 只进 OS keyring，绝不明文返回。

    def get_semantic_ai_settings(self) -> dict:
        """日常 AI 设置（API 地址 / 模型 / 是否已配置 Key；无明文）。"""
        try:
            return _ok(settings_ops.get_semantic_ai_settings())
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def save_semantic_ai_settings(self, payload: dict) -> dict:
        """保存日常 AI 设置；API Key 只写 keyring，不回传明文。"""
        try:
            return _ok({"settings": settings_ops.save_semantic_ai_settings(payload)})
        except SettingsOpError as exc:
            return _err(CODE_SETTINGS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    # ---------------- 新建作品（"我有个想法"纵切） ----------------
    # 确认前只写临时 pre-project 工作区 + 桥文件（06_工作区/应用开发/.qoder_bridge）；
    # 模型执行由作者在 Qoder 桌面端输入 /gowrite 完成（Go Write 不直接调模型）。
    # 只有作者明确确认（带后台 proposal token）才调用真实 ProjectWorkspace.create_project。

    def prepare_new_project(self, payload: dict) -> dict:
        """我有个想法 → 准备本轮 Agent 任务（pending request），不运行模型。

        准备完成后非侵入尽力把 Qoder 桌面端切到前台（只做窗口切换，绝不
        模拟键盘/回车/提交；失败静默，作者 Alt+Tab 即可）。
        """
        try:
            data = new_project_ops.prepare_new_project(
                name=str(payload.get("name") or ""),
                idea=str(payload.get("idea") or ""),
            )
            bridge_ops.focus_qoder_window()
            return _ok(data)
        except NewProjectError as exc:
            return _err(CODE_NEW_PROJECT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def get_new_project_request(self, payload: dict) -> dict:
        """轮询 Qoder 写回结果：pending / completed / failed / expired / canceled。"""
        try:
            data = new_project_ops.get_new_project_request(
                request_id=str(payload.get("request_id") or ""),
            )
            return _ok(data)
        except NewProjectError as exc:
            return _err(CODE_NEW_PROJECT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def cancel_new_project_request(self, payload: dict) -> dict:
        """取消等待：旧结果不可能再被接受；下一次请求用全新 request_id。"""
        try:
            data = new_project_ops.cancel_new_project_request(
                request_id=str(payload.get("request_id") or ""),
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

    # ---------------- M3 知识驱动重大基座设计（Agent 主导，作者确认后写回） ----------------

    def prepare_foundation_design(self, payload: dict) -> dict:
        """作者发起基座设计：Agent 分解问题/多轮检索/综合提案（不运行模型）。"""
        try:
            return _ok(foundation_design_ops.prepare_foundation_design(
                project_id=str(payload.get("project_id") or ""),
                author_request=str(payload.get("author_request") or ""),
                base_model_rev=int(payload.get("base_model_rev") or 0),
            ))
        except (FoundationDesignError, TypeError, ValueError) as exc:
            return _err(CODE_FOUNDATION_DESIGN_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def get_foundation_design_request(self, payload: dict) -> dict:
        """轮询基座设计结果：pending / completed / failed / expired / canceled。"""
        try:
            return _ok(foundation_design_ops.get_foundation_design_request(
                request_id=str(payload.get("request_id") or ""),
            ))
        except FoundationDesignError as exc:
            return _err(CODE_FOUNDATION_DESIGN_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def cancel_foundation_design_request(self, payload: dict) -> dict:
        """取消/丢弃基座设计任务与临时候选；幂等。"""
        try:
            return _ok(foundation_design_ops.cancel_foundation_design_request(
                request_id=str(payload.get("request_id") or ""),
            ))
        except FoundationDesignError as exc:
            return _err(CODE_FOUNDATION_DESIGN_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def confirm_foundation_design(self, payload: dict) -> dict:
        """作者明确确认 → 选择/编辑后的提案经既有 authority 合同写回。"""
        try:
            return _ok(foundation_design_ops.confirm_foundation_design(
                project_id=str(payload.get("project_id") or ""),
                proposal_token=str(payload.get("proposal_token") or ""),
                items=payload.get("items") if isinstance(payload.get("items"), list) else [],
                base_model_rev=int(payload.get("base_model_rev") or 0),
                relations=payload.get("relations") if isinstance(payload.get("relations"), list) else None,
            ))
        except (FoundationDesignError, AuthorEditError) as exc:
            return _err(CODE_FOUNDATION_DESIGN_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    # ---------------- 故事规划（"一起往前想"纵切） ----------------
    # 统一 /gowrite 桥模式：Go Write 准备任务 → Qoder /gowrite → 结果返回
    # 确认前只写临时 planning 工作区；只有作者明确确认（带后台 planning token）
    # 才写入正式 Story State 的 approved_plan。

    def prepare_story_plan(self, payload: dict) -> dict:
        """一起往前想 → 按已保存 Settings 执行模式准备本轮任务。

        Interactive：创建 pending request，提示作者到 Qoder 执行 /gowrite；
        Direct：Go Write 通过配置的 Agent/模型直接执行并写回同一响应信封。
        """
        try:
            replaces = payload.get("replaces_plan_ids")
            impact_ids = payload.get("impact_candidate_ids")
            data = story_planning_ops.prepare_story_plan(
                project_id=str(payload.get("project_id") or ""),
                author_question=str(payload.get("author_question") or ""),
                replaces_plan_ids=(
                    [str(pid) for pid in replaces]
                    if isinstance(replaces, list) and replaces
                    else None
                ),
                planning_mode=str(payload.get("planning_mode") or "free"),
                impact_candidate_ids=(
                    [str(cid) for cid in impact_ids]
                    if isinstance(impact_ids, list) and impact_ids
                    else None
                ),
            )
            # 只有交互模式需要把 Qoder 桌面端切到前台；直连模式由后台执行
            if data.get("execution_mode") != "direct":
                bridge_ops.focus_qoder_window()
            return _ok(data)
        except StoryPlanningError as exc:
            return _err(CODE_STORY_PLANNING_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def get_story_plan_request(self, payload: dict) -> dict:
        """轮询 Qoder 写回结果：pending / completed / failed / expired / canceled。"""
        try:
            data = story_planning_ops.get_story_plan_request(
                request_id=str(payload.get("request_id") or ""),
            )
            return _ok(data)
        except StoryPlanningError as exc:
            return _err(CODE_STORY_PLANNING_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def cancel_story_plan_request(self, payload: dict) -> dict:
        """取消等待：旧结果不可能再被接受。"""
        try:
            data = story_planning_ops.cancel_story_plan_request(
                request_id=str(payload.get("request_id") or ""),
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

    # ---------------- 规划影响候选（作者显式处置；绝不自动重规划） ----------------

    def set_planning_impact_candidate_status(self, payload: dict) -> dict:
        """作者显式处置一条影响候选：暂时保留（deferred）或重新待处理（pending_author）。

        绝不标记旧规划为“正确”，绝不重写任何规划；重规划只走 prepare_story_plan
        的 impact_replan 显式路径。
        """
        try:
            model = project_model_ops.read_project_model(str(payload.get("project_id") or ""))
            updated = project_model_ops.update_planning_impact_candidate(
                str(payload.get("project_id") or ""),
                base_model_rev=model["model_rev"],
                candidate_id=str(payload.get("candidate_id") or ""),
                status=str(payload.get("status") or ""),
            )
            return _ok({
                "model_rev": updated["model_rev"],
                "planning_impact_candidates": updated["planning_impact_candidates"],
            })
        except (ProjectModelError, TypeError, ValueError) as exc:
            return _err(CODE_PLANNING_IMPACT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    # ---------------- 正文写作（"这一段想写什么"纵切） ----------------
    # 确认前只写临时 writing 工作区；只有作者明确确认（带后台 writing token）
    # 才通过 ProjectWorkspace.accept_prose 写入正式 03_正文。
    # StoryWrite 仅支持 Direct 后台执行（交互桥显式未接入，绝不回退）。

    def prepare_story_write(self, payload: dict) -> dict:
        """这一段想写什么 → 按已保存 Settings 执行模式准备本轮任务。"""
        try:
            data = story_writing_ops.prepare_story_write(
                project_id=str(payload.get("project_id") or ""),
                author_input=str(payload.get("author_input") or ""),
                chapter_number=(int(payload["chapter_number"]) if payload.get("chapter_number") is not None else None),
            )
            # 只有交互模式需要把 Qoder 桌面端切到前台（阶段 1 等待第一次 /gowrite）
            if data.get("execution_mode") != "direct":
                bridge_ops.focus_qoder_window()
            return _ok(data)
        except StoryWritingError as exc:
            return _err(CODE_STORY_WRITING_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def get_story_write_request(self, payload: dict) -> dict:
        """轮询 Direct 执行结果：pending / completed / failed / expired / canceled。"""
        try:
            data = story_writing_ops.get_story_write_request(
                request_id=str(payload.get("request_id") or ""),
            )
            return _ok(data)
        except StoryWritingError as exc:
            return _err(CODE_STORY_WRITING_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def cancel_story_write_request(self, payload: dict) -> dict:
        """取消等待：终止运行中的 Direct adapter；旧结果不可能再被接受。"""
        try:
            data = story_writing_ops.cancel_story_write_request(
                request_id=str(payload.get("request_id") or ""),
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

    def get_story_write_surface(self, payload: dict) -> dict:
        """WritingPage 正式写作面（只读）：正式已采用正文 + accepted index 派生。

        绝不返回临时候选；绝无写副作用；path containment + SHA 校验失败显式报错。
        """
        try:
            data = story_writing_ops.get_story_write_surface(
                project_id=str(payload.get("project_id") or ""),
            )
            return _ok(_annotate_settlement_liveness(data, str(payload.get("project_id") or "")))
        except StoryWritingError as exc:
            return _err(CODE_STORY_WRITING_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    # ---------------- 灵感箱（真实本地收件箱，非权威、无模型） ----------------

    def list_ideas(self) -> dict:
        """列出全部灵感（created_at 倒序）；无任何模型调用。"""
        try:
            return _ok(ideas_ops.list_ideas())
        except IdeasError as exc:
            return _err(CODE_IDEAS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def create_idea(self, payload: dict) -> dict:
        """新增一条灵感（原子写入；kind: text|link）。"""
        try:
            return _ok(ideas_ops.create_idea(
                content=str(payload.get("content") or ""),
                kind=str(payload.get("kind") or "text"),
            ))
        except IdeasError as exc:
            return _err(CODE_IDEAS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def delete_idea(self, payload: dict) -> dict:
        """删除一条灵感（幂等）。"""
        try:
            return _ok(ideas_ops.delete_idea(
                idea_id=str(payload.get("idea_id") or ""),
            ))
        except IdeasError as exc:
            return _err(CODE_IDEAS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def mark_idea_used(self, payload: dict) -> dict:
        """可选：把一条灵感标记为已用于某作品（非权威）。"""
        try:
            return _ok(ideas_ops.mark_idea_used(
                idea_id=str(payload.get("idea_id") or ""),
                project_id=str(payload.get("project_id") or ""),
            ))
        except IdeasError as exc:
            return _err(CODE_IDEAS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    # ---------------- 素材目录（真实 canonical catalog；仅显式动作） ----------------

    def list_materials(self) -> dict:
        """只读读取 canonical 素材 ledger 投影；零模型 / 零写副作用。"""
        try:
            return _ok(materials_ops.list_materials())
        except MaterialsError as exc:
            return _err(CODE_MATERIALS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def refresh_materials(self) -> dict:
        """显式触发 MaterialIntake catalog refresh（确定性、无模型）。"""
        try:
            return _ok(materials_ops.refresh_materials())
        except MaterialsError as exc:
            return _err(CODE_MATERIALS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def scan_material_inbox(self) -> dict:
        """只读扫描 00_待入库（MaterialIntake inbox scan）。"""
        try:
            return _ok(materials_ops.scan_material_inbox())
        except MaterialsError as exc:
            return _err(CODE_MATERIALS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def apply_material_intake(self, payload: dict) -> dict:
        """作者显式选择的入库决策：走 MaterialIntake 确定性 intake 事务。"""
        try:
            plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else None
            if plan is None:
                return _err(CODE_MATERIALS_ERROR, "入库计划格式错误。")
            return _ok(materials_ops.apply_material_intake(plan))
        except MaterialsError as exc:
            return _err(CODE_MATERIALS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def pick_material_files(self, payload: dict) -> dict:
        """本地文件选择（pywebview 原生对话框；Python 侧控制路径来源）。"""
        try:
            return _ok(materials_ops.pick_material_files())
        except MaterialsError as exc:
            return _err(CODE_MATERIALS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def import_material_files(self, payload: dict) -> dict:
        """把本地文件字节 stage 到 MaterialIntake 收件箱（00_待入库）。"""
        try:
            files = payload.get("files") if isinstance(payload.get("files"), list) else None
            if files is None:
                return _err(CODE_MATERIALS_ERROR, "导入文件列表格式错误。")
            return _ok(materials_ops.import_material_files(files))
        except MaterialsError as exc:
            return _err(CODE_MATERIALS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def classify_material_inbox(self, payload: dict) -> dict:
        """Agent 辅助入库：scan → 确定性事实 → 仅对无法定论文件调一次 Agent。"""
        try:
            return _ok(materials_ops.classify_material_inbox())
        except MaterialsError as exc:
            return _err(CODE_MATERIALS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def get_material_classify_request(self, payload: dict) -> dict:
        """轮询交互式分类：pending / completed（含 plan）/ failed / canceled。"""
        try:
            return _ok(materials_ops.get_material_classify_request(
                request_id=str(payload.get("request_id") or ""),
            ))
        except MaterialsError as exc:
            return _err(CODE_MATERIALS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def cancel_material_classify_request(self, payload: dict) -> dict:
        try:
            return _ok(materials_ops.cancel_material_classify_request(
                request_id=str(payload.get("request_id") or ""),
            ))
        except MaterialsError as exc:
            return _err(CODE_MATERIALS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def run_source_prepare(self, payload: dict) -> dict:
        """对指定素材显式运行真实 SourcePrepare（确定性，无模型）。"""
        try:
            return _ok(materials_ops.run_source_prepare(
                asset_id=str(payload.get("asset_id") or ""),
            ))
        except MaterialsError as exc:
            return _err(CODE_MATERIALS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def run_book_distill(self, payload: dict) -> dict:
        """对 SourcePrepare PASS 素材显式运行真实 BookDistill（含 Agent 阅读阶段）。"""
        try:
            return _ok(materials_ops.run_book_distill(
                asset_id=str(payload.get("asset_id") or ""),
            ))
        except MaterialsError as exc:
            return _err(CODE_MATERIALS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def get_book_distill_request(self, payload: dict) -> dict:
        """轮询 Interactive 蒸馏：pending / completed / failed / canceled。"""
        try:
            return _ok(materials_ops.get_book_distill_request(
                request_id=str(payload.get("request_id") or ""),
            ))
        except MaterialsError as exc:
            return _err(CODE_MATERIALS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def cancel_book_distill_request(self, payload: dict) -> dict:
        try:
            return _ok(materials_ops.cancel_book_distill_request(
                request_id=str(payload.get("request_id") or ""),
            ))
        except MaterialsError as exc:
            return _err(CODE_MATERIALS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def get_material_detail(self, payload: dict) -> dict:
        """单素材作者面详情（写作时能否调用 / 阶段 / 下一步；零模型）。"""
        try:
            return _ok(materials_ops.get_material_detail(
                asset_id=str(payload.get("asset_id") or ""),
            ))
        except MaterialsError as exc:
            return _err(CODE_MATERIALS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def prepare_material(self, payload: dict) -> dict:
        """作者面通用「提纯」：UI 只传素材 id，后端按类型分派
        （REFERENCE_WORK/RESEARCH → SourcePrepare；METHOD_SOURCE → MethodPrepare）。"""
        try:
            return _ok(materials_ops.prepare_material(
                asset_id=str(payload.get("asset_id") or ""),
            ))
        except MaterialsError as exc:
            return _err(CODE_MATERIALS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def distill_material(self, payload: dict) -> dict:
        """作者面通用「蒸馏」：UI 只传素材 id，后端按类型分派
        （REFERENCE_WORK → BookDistill；METHOD_SOURCE → MethodDistill）。"""
        try:
            return _ok(materials_ops.distill_material(
                asset_id=str(payload.get("asset_id") or ""),
            ))
        except MaterialsError as exc:
            return _err(CODE_MATERIALS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def get_material_distill_request(self, payload: dict) -> dict:
        """通用蒸馏轮询：按桥请求 kind 分派到 BookDistill / MethodDistill。"""
        try:
            return _ok(materials_ops.get_material_distill_request(
                request_id=str(payload.get("request_id") or ""),
            ))
        except MaterialsError as exc:
            return _err(CODE_MATERIALS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def cancel_material_distill_request(self, payload: dict) -> dict:
        """通用蒸馏取消：按桥请求 kind 分派。"""
        try:
            return _ok(materials_ops.cancel_material_distill_request(
                request_id=str(payload.get("request_id") or ""),
            ))
        except MaterialsError as exc:
            return _err(CODE_MATERIALS_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    # ---------------- 作品资料 / 故事地图（只读正式 Story State 投影） ----------------

    def get_project_data(self, payload: dict) -> dict:
        """只读正式 Story State 投影（ProjectData / StoryMap 共用；零写回、零模型）。"""
        try:
            return _ok(_annotate_settlement_liveness(
                project_data_ops.get_project_data(
                    project_id=str(payload.get("project_id") or ""),
                ),
                str(payload.get("project_id") or ""),
            ))
        except ProjectDataError as exc:
            return _err(CODE_PROJECT_DATA_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    # ---------------- 统一作者编辑 / 增量语义结算 ----------------

    def get_project_snapshot(self, payload: dict) -> dict:
        try:
            return _ok(author_edit_ops.get_author_edit_surface(str(payload.get("project_id") or "")))
        except AuthorEditError as exc:
            return _err(CODE_AUTHOR_EDIT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def create_foundation_record(self, payload: dict) -> dict:
        try:
            return _ok(author_edit_ops.create_foundation_record(
                str(payload.get("project_id") or ""),
                base_model_rev=int(payload.get("base_model_rev")),
                category=str(payload.get("category") or ""),
                title=str(payload.get("title") or ""),
                material_state=str(payload.get("material_state") or "current"),
                data=payload.get("data") if isinstance(payload.get("data"), dict) else {},
                category_name=(str(payload.get("category_name")) if payload.get("category_name") is not None else None),
                relations=payload.get("relations") if isinstance(payload.get("relations"), list) else None,
            ))
        except (AuthorEditError, TypeError, ValueError) as exc:
            return _err(CODE_AUTHOR_EDIT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def set_story_bible_profile(self, payload: dict) -> dict:
        try:
            return _ok(author_edit_ops.set_story_bible_profile(
                str(payload.get("project_id") or ""),
                base_model_rev=int(payload.get("base_model_rev")),
                genre_tags=payload.get("genre_tags") if isinstance(payload.get("genre_tags"), list) else [],
                narrative_mode=(str(payload.get("narrative_mode")) if payload.get("narrative_mode") is not None else None),
                active_modules=payload.get("active_modules") if isinstance(payload.get("active_modules"), list) else [],
                field_config=payload.get("field_config") if isinstance(payload.get("field_config"), dict) else {},
            ))
        except (AuthorEditError, TypeError, ValueError) as exc:
            return _err(CODE_AUTHOR_EDIT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def update_foundation_record(self, payload: dict) -> dict:
        try:
            return _ok(author_edit_ops.update_foundation_record(
                str(payload.get("project_id") or ""),
                base_model_rev=int(payload.get("base_model_rev")),
                ref=str(payload.get("ref") or ""),
                title=(str(payload.get("title")) if payload.get("title") is not None else None),
                material_state=(str(payload.get("material_state")) if payload.get("material_state") is not None else None),
                data=payload.get("data") if isinstance(payload.get("data"), dict) else None,
                relations=payload.get("relations") if isinstance(payload.get("relations"), list) else None,
            ))
        except (AuthorEditError, TypeError, ValueError) as exc:
            return _err(CODE_AUTHOR_EDIT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def retire_foundation_record(self, payload: dict) -> dict:
        try:
            return _ok(author_edit_ops.retire_foundation_record(
                str(payload.get("project_id") or ""),
                base_model_rev=int(payload.get("base_model_rev")), ref=str(payload.get("ref") or ""),
            ))
        except (AuthorEditError, TypeError, ValueError) as exc:
            return _err(CODE_AUTHOR_EDIT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def create_relationship(self, payload: dict) -> dict:
        try:
            return _ok(author_edit_ops.create_relationship(
                str(payload.get("project_id") or ""),
                base_model_rev=int(payload.get("base_model_rev")),
                source_ref=str(payload.get("source_ref") or ""),
                target_ref=str(payload.get("target_ref") or ""),
                label=str(payload.get("label") or ""),
                material_state=str(payload.get("material_state") or "current"),
                data=payload.get("data") if isinstance(payload.get("data"), dict) else {},
            ))
        except (AuthorEditError, TypeError, ValueError) as exc:
            return _err(CODE_AUTHOR_EDIT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def update_relationship(self, payload: dict) -> dict:
        try:
            return _ok(author_edit_ops.update_relationship(
                str(payload.get("project_id") or ""),
                base_model_rev=int(payload.get("base_model_rev")), ref=str(payload.get("ref") or ""),
                source_ref=(str(payload.get("source_ref")) if payload.get("source_ref") is not None else None),
                target_ref=(str(payload.get("target_ref")) if payload.get("target_ref") is not None else None),
                label=(str(payload.get("label")) if payload.get("label") is not None else None),
                material_state=(str(payload.get("material_state")) if payload.get("material_state") is not None else None),
                data=payload.get("data") if isinstance(payload.get("data"), dict) else None,
            ))
        except (AuthorEditError, TypeError, ValueError) as exc:
            return _err(CODE_AUTHOR_EDIT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def retire_relationship(self, payload: dict) -> dict:
        try:
            return _ok(author_edit_ops.retire_relationship(
                str(payload.get("project_id") or ""),
                base_model_rev=int(payload.get("base_model_rev")), ref=str(payload.get("ref") or ""),
            ))
        except (AuthorEditError, TypeError, ValueError) as exc:
            return _err(CODE_AUTHOR_EDIT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def restore_foundation_record(self, payload: dict) -> dict:
        """确定性恢复同一退役记录（同一 ref；零 AI/Agent）。"""
        try:
            return _ok(author_edit_ops.restore_foundation_record(
                str(payload.get("project_id") or ""),
                base_model_rev=int(payload.get("base_model_rev")), ref=str(payload.get("ref") or ""),
            ))
        except (AuthorEditError, TypeError, ValueError) as exc:
            return _err(CODE_AUTHOR_EDIT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def restore_relationship(self, payload: dict) -> dict:
        """确定性恢复同一退役关系（同一 ref；零 AI/Agent）。"""
        try:
            return _ok(author_edit_ops.restore_relationship(
                str(payload.get("project_id") or ""),
                base_model_rev=int(payload.get("base_model_rev")), ref=str(payload.get("ref") or ""),
            ))
        except (AuthorEditError, TypeError, ValueError) as exc:
            return _err(CODE_AUTHOR_EDIT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def set_length_plan(self, payload: dict) -> dict:
        try:
            total = payload.get("total_target_words")
            return _ok(author_edit_ops.set_length_plan(
                str(payload.get("project_id") or ""),
                base_model_rev=int(payload.get("base_model_rev")),
                total_target_words=(int(total) if total is not None else None),
                stages=payload.get("stages") if isinstance(payload.get("stages"), list) else None,
                chapter_targets=(payload.get("chapter_targets") if isinstance(payload.get("chapter_targets"), list) else None),
            ))
        except (AuthorEditError, TypeError, ValueError) as exc:
            return _err(CODE_AUTHOR_EDIT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def update_story_synopsis(self, payload: dict) -> dict:
        try:
            return _ok(author_edit_ops.update_story_synopsis(
                str(payload.get("project_id") or ""),
                base_intent_rev=int(payload.get("base_intent_rev")),
                story_synopsis=str(payload.get("story_synopsis") or ""),
            ))
        except (AuthorEditError, TypeError, ValueError) as exc:
            return _err(CODE_AUTHOR_EDIT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def create_chapter(self, payload: dict) -> dict:
        try:
            return _ok(author_edit_ops.create_chapter(
                str(payload.get("project_id") or ""), chapter_number=int(payload.get("chapter_number")),
            ))
        except (AuthorEditError, TypeError, ValueError) as exc:
            return _err(CODE_AUTHOR_EDIT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def save_formal_prose(self, payload: dict) -> dict:
        try:
            return _ok(author_edit_ops.save_formal_prose(
                str(payload.get("project_id") or ""), chapter_number=int(payload.get("chapter_number")),
                base_content_sha256=str(payload.get("base_content_sha256") or ""),
                content=str(payload.get("content") or ""),
            ))
        except (AuthorEditError, TypeError, ValueError) as exc:
            return _err(CODE_AUTHOR_EDIT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def prepare_project_state_refresh(self, payload: dict) -> dict:
        try:
            return _ok(change_settlement_ops.prepare_project_state_refresh(
                str(payload.get("project_id") or ""),
            ))
        except (ChangeSettlementError, AuthorEditError) as exc:
            return _err(CODE_CHANGE_SETTLEMENT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def get_project_state_refresh(self, payload: dict) -> dict:
        try:
            return _ok(change_settlement_ops.get_project_state_refresh(
                str(payload.get("project_id") or ""),
            ))
        except (ChangeSettlementError, AuthorEditError) as exc:
            return _err(CODE_CHANGE_SETTLEMENT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def confirm_project_state_refresh(self, payload: dict) -> dict:
        try:
            return _ok(change_settlement_ops.confirm_project_state_refresh(
                str(payload.get("project_id") or ""), str(payload.get("refresh_id") or ""),
                accept=bool(payload.get("accept")),
            ))
        except (ChangeSettlementError, AuthorEditError) as exc:
            return _err(CODE_CHANGE_SETTLEMENT_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    # ---------------- 作品检查（真实、显式、范围受控的 AI 检查） ----------------

    def get_review_surface(self, payload: dict) -> dict:
        """确定性只读检查面（无模型）：正式身份 / 规划数 / 线索数 / 章节目录。"""
        try:
            return _ok(review_ops.get_review_surface(
                project_id=str(payload.get("project_id") or ""),
            ))
        except ReviewError as exc:
            return _err(CODE_REVIEW_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def prepare_review(self, payload: dict) -> dict:
        """作者显式"开始检查"→ 后台发起一次 Agent 检查（Direct；异步轮询/取消）。"""
        try:
            chapter_number = payload.get("chapter_number")
            if chapter_number is not None:
                chapter_number = int(chapter_number)
            data = review_ops.prepare_review(
                project_id=str(payload.get("project_id") or ""),
                chapter_number=chapter_number,
            )
            return _ok(data)
        except ReviewError as exc:
            return _err(CODE_REVIEW_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def get_review_request(self, payload: dict) -> dict:
        """轮询检查结果：pending / completed（含报告）/ failed / expired / canceled。"""
        try:
            return _ok(review_ops.get_review_request(
                request_id=str(payload.get("request_id") or ""),
            ))
        except ReviewError as exc:
            return _err(CODE_REVIEW_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def cancel_review_request(self, payload: dict) -> dict:
        """取消/丢弃检查：终止运行中的 Direct adapter（如有）。"""
        try:
            return _ok(review_ops.cancel_review_request(
                request_id=str(payload.get("request_id") or ""),
            ))
        except ReviewError as exc:
            return _err(CODE_REVIEW_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    # ---------------- 执行记录（验证式审计；只读，显式清理） ----------------

    def focus_qoder(self, payload: dict | None = None) -> dict:
        """尽力把已运行的 Qoder 桌面端切到前台（非侵入；失败静默）。

        只做窗口切换，绝不模拟键盘/回车/提交；供全局任务条"前往 Qoder
        执行 /gowrite"按钮使用。
        """
        try:
            focused = bridge_ops.focus_qoder_window()
            return _ok({"focused": focused})
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def get_active_author_operation(self, payload: dict | None = None) -> dict:
        """恢复当前待办作者操作（App 协调器 remount/reload 用；仅非机密事实）。

        返回 data：操作事实 dict，或 None（当前无待办操作）。
        Interactive pending 可恢复；Direct 仅当 in-process worker 仍在；
        进程重启后的孤儿 Direct 请求 fail closed（state=orphaned）。
        """
        try:
            return _ok(author_operation_ops.get_active_author_operation())
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def list_execution_audits(self, payload: dict) -> dict:
        """最近执行记录列表（摘要字段；按时间倒序）。"""
        try:
            return _ok(audit_ops.list_execution_audits(
                limit=int(payload.get("limit") or 50),
                operation=str(payload.get("operation") or "") or None,
                status=str(payload.get("status") or "") or None,
                project_id=str(payload.get("project_id") or "") or None,
            ))
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def get_execution_audit(self, payload: dict) -> dict:
        """单条执行记录（完整事件时间线）；不存在返回 data=None。"""
        try:
            record = audit_ops.get_execution_audit(
                request_id=str(payload.get("request_id") or ""),
            )
            return _ok({"record": record})
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))

    def clear_execution_audits(self, payload: dict) -> dict:
        """显式清理：只删除 06_工作区/运行审计。"""
        try:
            return _ok(audit_ops.clear_execution_audits())
        except Exception as exc:  # noqa: BLE001
            return _err(CODE_BRIDGE_INTERNAL, str(exc))
