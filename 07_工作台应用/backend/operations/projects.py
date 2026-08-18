# -*- coding: utf-8 -*-
"""真实作品操作层（operations）——只复用 ProjectWorkspace，不复制其逻辑。

本轮只暴露只读能力：
- list_projects(): 真实 03_作品工程 作品列表
- open_project(project): 以 project_id（优先）或作品名解析并加载作品
- get_project_overview(project_id): 最小作品概览（正式状态 → 展示数据）

约束：
- 不修改 03_作品工程；不建立全局 current_project 文件；
  当前打开项目只存在于前端/运行时会话状态（本模块无持久状态）。
- 不暴露任何修改 authority 的能力（accept / persist / create 均不暴露）。
"""
from __future__ import annotations

import sys
from pathlib import Path

_PW = Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"
if str(_PW) not in sys.path:
    sys.path.insert(0, str(_PW))

_SP = Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "StoryPlan"
if str(_SP) not in sys.path:
    sys.path.insert(0, str(_SP))

from project_workspace import (  # noqa: E402
    ContractError,
    WorkspaceError,
    get_recent_prose,
    list_projects as pw_list_projects,
    load_project,
    resolve_project,
)
from story_plan import resolve_plan_activity  # noqa: E402  StoryPlan frozen runtime


class ProjectOpError(Exception):
    """操作层错误（面向 UI 的稳定错误类型）。"""


def list_projects() -> list[dict]:
    """真实作品列表（来自 03_作品工程，经 ProjectWorkspace.list_projects）。"""
    return pw_list_projects()


def open_project(project: dict | str) -> dict:
    """以 project_id（优先）或作品名解析并加载作品。返回只读 {project_id, name, project_dir}。"""
    if isinstance(project, dict):
        selector = project.get("project_id") or project.get("name")
    else:
        selector = project
    try:
        proj = resolve_project(selector)
        loaded = load_project(proj["project_dir"])
    except (ContractError, WorkspaceError) as exc:
        raise ProjectOpError(str(exc)) from exc
    return {
        "project_id": loaded["project_id"],
        "name": loaded["name"],
        "project_dir": loaded["project_dir"],
    }


def get_project_overview(project_id: str) -> dict:
    """最小作品概览：只读正式状态 → 展示数据（保持最小，字段只在真实存在时出现）。"""
    try:
        proj = resolve_project(project_id)
        loaded = load_project(proj["project_dir"])
    except (ContractError, WorkspaceError) as exc:
        raise ProjectOpError(str(exc)) from exc

    intent = loaded["intent"]
    state = loaded["state"]
    index = loaded["index"] or {}

    overview: dict = {
        "project_id": loaded["project_id"],
        "name": loaded["name"],
        "state": {
            "state_rev": state.get("state_rev"),
            "last_authority_source": state.get("last_authority_source"),
        },
    }

    # 作者可读字段：已确定的故事方向 + 读者主要期待
    work_direction = intent.get("work_direction") or ""
    reader_promise = intent.get("reader_promise") or ""
    if work_direction:
        overview["work_direction"] = work_direction
    if reader_promise:
        overview["reader_promise"] = reader_promise

    # 当前已确定的规划：只使用 frozen resolve_plan_activity 的 active 投影
    # superseded 的旧规划继续保留在 Story State 历史中，但不显示为"当前已经确定"
    all_plans = state.get("approved_plan") or []
    activity = resolve_plan_activity(state)
    active_ids = set(activity["active"])

    if all_plans:
        current_plans = []
        for plan in all_plans:
            pid = plan.get("id")
            if pid and pid in active_ids:
                desc = plan.get("description") or plan.get("text") or ""
                if desc:
                    current_plans.append({"id": pid, "description": desc})
        if current_plans:
            overview["current_plans"] = current_plans

    # 最近写作位置：accepted_text_index 最后一条（可靠）
    entries = index.get("entries") or []
    if entries:
        last = entries[-1]
        overview["last_accepted"] = {
            "chapter_path": last.get("chapter_path"),
            "scene_ref": last.get("scene_ref"),
            "sequence": last.get("sequence"),
        }
        # 最近正文窗口：仅当 index 与章节一致时可靠返回，否则不显示
        try:
            window = get_recent_prose(loaded["project_dir"])
            overview["recent_prose"] = {
                "scene_ref": window.get("scene_ref"),
                "window_chars": window.get("window_chars"),
                "below_target": window.get("below_target"),
            }
        except (ContractError, WorkspaceError):
            pass

    # 当前有效规划摘要：只取 active 条目的最新一条（用于向后兼容旧 UI 字段）
    if all_plans:
        active_plans = [p for p in all_plans if p.get("id") and p["id"] in active_ids]
        if active_plans:
            latest = active_plans[-1]
            text = None
            for key in ("description", "text", "title", "summary", "content"):
                if isinstance(latest.get(key), str) and latest[key].strip():
                    text = latest[key].strip()
                    break
            overview["planning"] = {
                "entries": len(active_plans),
                "latest": text,
                "latest_id": latest.get("id"),
                "latest_occurred": latest.get("occurred"),
            }
    return overview
