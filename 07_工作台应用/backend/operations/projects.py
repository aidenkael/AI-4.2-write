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

from project_workspace import (  # noqa: E402
    ContractError,
    WorkspaceError,
    get_recent_prose,
    list_projects as pw_list_projects,
    load_project,
    resolve_project,
)
from operations.project_snapshot import ProjectSnapshotError, get_project_snapshot


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
        snapshot = get_project_snapshot(project_id)
        loaded = load_project(snapshot["identity"]["project_dir"])
    except (ContractError, WorkspaceError, ProjectSnapshotError) as exc:
        raise ProjectOpError(str(exc)) from exc

    intent = snapshot["author_intent"]
    state = loaded["state"]
    index = loaded["index"] or {}

    overview: dict = {
        "project_id": snapshot["project_id"],
        "name": snapshot["name"],
        "state": snapshot["story_state"],
        "settlement": snapshot["settlement"],
        "intent_rev": intent.get("intent_rev"),
        "story_synopsis": intent.get("story_synopsis") or "",
        "progress": {
            "current_chapter": max(item["chapter_number"] for item in snapshot["chapters"]),
            "actual_words": snapshot["length_plan"]["actual_total_words"],
            "target_words": snapshot["length_plan"]["total_target_words"],
        },
    }

    # 作者可读字段：已确定的故事方向 + 读者主要期待
    work_direction = intent.get("work_direction") or ""
    reader_promise = intent.get("reader_promise") or ""
    if work_direction:
        overview["work_direction"] = work_direction
    if reader_promise:
        overview["reader_promise"] = reader_promise

    # 当前已确定的规划：统一快照的 active 投影（snapshot 内部复用 frozen resolve_plan_activity）
    # superseded 的旧规划继续保留在 Story State 历史中，但不显示为"当前已经确定"
    active_plans = snapshot["future"]["approved_plan"]
    current_plans = [
        {"id": item.get("id"), "description": item.get("title") or ""}
        for item in active_plans
        if item.get("id") and item.get("title")
    ]
    if current_plans:
        overview["current_plans"] = current_plans

    open_items = [
        {"id": item.get("ref") or item.get("id"), "title": item.get("title") or "", "kind": "未解决线索", "status": "current"}
        for item in snapshot["current"].get("open_threads", [])
    ] + [
        {"id": item.get("ref") or item.get("id"), "title": item.get("title") or "", "kind": "伏笔与承诺", "status": "future"}
        for item in snapshot["future"].get("foreshadowing", [])
    ] + [
        {"id": item.get("ref") or item.get("id"), "title": item.get("title") or "", "kind": "悬疑信息", "status": item.get("material_state") or "future"}
        for item in [
            *snapshot["current"].get("mystery_information", []),
            *snapshot["future"].get("mystery_information", []),
        ]
    ]
    overview["open_items"] = {
        "total": len([item for item in open_items if item.get("title")]),
        "items": [item for item in open_items if item.get("title")][:5],
    }

    foundation_sections = (
        "characters", "relationships", "settings", "locations", "organizations",
        "systems", "events", "open_threads", "foreshadowing", "storylines", "mystery_information",
    )
    has_structured_foundation = any(
        snapshot[bucket].get(section)
        for bucket in ("current", "future")
        for section in foundation_sections
    )
    overview["primary_next_action"] = "foundation" if not has_structured_foundation else "writing"

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
    if active_plans:
        latest = active_plans[-1]
        overview["planning"] = {
            "entries": len(active_plans),
            "latest": latest.get("title") or None,
            "latest_id": latest.get("id"),
            "latest_occurred": (latest.get("record") or {}).get("occurred")
            if isinstance(latest.get("record"), dict) else None,
        }
    return overview
