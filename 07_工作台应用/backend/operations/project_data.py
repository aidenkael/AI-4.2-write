# -*- coding: utf-8 -*-
"""作品资料 / 故事地图的统一只读派生数据面。

职责（对应 UI 1.0 ProjectData / StoryMap 真实消费者）：
- 复用统一 project snapshot 读取 Author Intent、正式 Story State、active planning 与作者工作区；
- 返回作者可读的真实字段投影，绝不推断、绝不编造、绝不写回。

来源 authority：
- Author Intent（work_direction / reader_promise 等）
- Story State（canon_facts / character_state / relationship_state /
  occurred_events / open_threads / approved_plan）
- 每项目作者工作区（当前/未来领域对象、细纲与实际章节结果）

映射到 UI 分类（不改变 Canon，只做形状投影）：
- Characters → character_state
- Relationships → relationship_state
- Confirmed facts/settings → canon_facts
- Important events → occurred_events
- Open threads/questions → open_threads
- Confirmed planning → active approved_plan 投影（frozen resolve_plan_activity）

约束：
- 绝不从正文推断缺失的人物/关系/地点；
- 绝不伪造分类条目；
- 本模块只读；作者编辑由统一 author_edit / settlement 合同处理；
- 零模型 / 零 Skill 调用。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

from operations.project_snapshot import ProjectSnapshotError, get_project_snapshot

_PW = Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"
if str(_PW) not in sys.path:
    sys.path.insert(0, str(_PW))

_SP = Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "StoryPlan"
if str(_SP) not in sys.path:
    sys.path.insert(0, str(_SP))

from project_workspace import (  # noqa: E402
    ContractError as PWContractError,
    WorkspaceError as PWWorkspaceError,
    load_project,
    resolve_project,
)
from story_plan import resolve_plan_activity  # noqa: E402  StoryPlan frozen runtime


class ProjectDataError(Exception):
    """作品资料/故事地图只读面错误（面向 UI 的稳定错误类型）。"""


# 展示标签推断顺序：只从真实字段中取第一个非空字符串，绝不编造
_LABEL_KEYS = (
    "name", "title", "fact", "description", "text", "summary", "content", "label",
)


def _label(entry: Any) -> str:
    """从真实字段中取第一个非空字符串作为展示标签；没有则用 id 或（空）。"""
    if isinstance(entry, str):
        return entry
    if not isinstance(entry, dict):
        return str(entry) if entry is not None else ""
    for key in _LABEL_KEYS:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    eid = entry.get("id")
    if isinstance(eid, str) and eid:
        return eid
    return ""


def _project_entry(entry: Any) -> dict[str, Any]:
    """把一条正式 State 条目投影为 {id, label, record}。record 为原样真实字段。"""
    if not isinstance(entry, dict):
        return {"id": None, "label": _label(entry), "record": entry}
    return {
        "id": entry.get("id"),
        "label": _label(entry),
        "record": entry,
    }


def _section(entries: Any) -> list[dict[str, Any]]:
    """投影一个 State 分区；非 list 视为空（不猜、不报错、不伪造）。"""
    if not isinstance(entries, list):
        return []
    return [_project_entry(e) for e in entries]


def _active_plans(state: dict[str, Any]) -> list[dict[str, Any]]:
    """当前有效规划：只使用 frozen resolve_plan_activity 的 active 投影。"""
    all_plans = state.get("approved_plan") or []
    if not all_plans:
        return []
    try:
        activity = resolve_plan_activity(state)
    except Exception:  # noqa: BLE001 — 活动投影失败时回退为保守空（不伪造）
        return []
    active_ids = set(activity.get("active") or [])
    return [_project_entry(p) for p in all_plans if p.get("id") in active_ids]


def get_project_data(project_id: str) -> dict[str, Any]:
    """只读正式 Story State 投影（ProjectData / StoryMap 共用同一数据面）。

    绝不写回；绝不调用模型；project_id 必须是 FormalProjectShell 的正式身份。
    """
    project_id = (project_id or "").strip()
    if not project_id:
        raise ProjectDataError("缺少作品标识（project_id）。")

    try:
        snapshot = get_project_snapshot(project_id)
    except ProjectSnapshotError as exc:
        raise ProjectDataError(str(exc)) from exc

    def project(item: dict[str, Any], status: str) -> dict[str, Any]:
        record = copy.deepcopy(item.get("record"))
        if isinstance(record, dict):
            record.setdefault("material_state", status)
            record.setdefault("source_ref", item.get("source_ref"))
            record.setdefault("source_kind", item.get("source_kind"))
        return {
            "id": item.get("id") or item.get("ref"),
            "label": item.get("title") or "",
            "record": record,
            "source_ref": item.get("source_ref"),
            "source_kind": item.get("source_kind"),
            "provenance": item.get("provenance"),
            "category": item.get("category"),
            "status": status,
            "editable": bool(item.get("editable")),
        }

    def combined(section: str) -> list[dict[str, Any]]:
        return [
            *[project(item, "current") for item in snapshot["current"].get(section, [])],
            *[project(item, "future") for item in snapshot["future"].get(section, [])],
        ]

    intent = snapshot["author_intent"]
    return {
        "project_id": snapshot["project_id"],
        "name": snapshot["name"],
        "state_rev": snapshot["story_state"].get("state_rev"),
        "model_rev": snapshot["model_rev"],
        "last_authority_source": snapshot["story_state"].get("last_authority_source"),
        "work_direction": intent.get("work_direction") or "",
        "reader_promise": intent.get("reader_promise") or "",
        "settlement": snapshot["settlement"],
        "story_bible_profile": snapshot["story_bible_profile"],
        "length_plan": snapshot["length_plan"],
        "chapters": [{
            "chapter_number": item["chapter_number"],
            "title": item["title"],
            "actual_words": item["actual_words"],
            "fine_outline": copy.deepcopy(item.get("fine_outline") or {}),
            "actual_result": copy.deepcopy(item.get("actual_result")),
        } for item in snapshot["chapters"]],
        "planning_impact_candidates": snapshot.get("planning_impact_candidates", []),
        "sections": {
            "characters": combined("characters"),
            "relationships": combined("relationships"),
            "canon_facts": combined("settings"),
            "locations": combined("locations"),
            "organizations": combined("organizations"),
            "systems": combined("systems"),
            "occurred_events": combined("events"),
            "open_threads": combined("open_threads"),
            "foreshadowing": combined("foreshadowing"),
            "storylines": combined("storylines"),
            "mystery_information": combined("mystery_information"),
            "approved_plan": [project(item, "future") for item in snapshot["future"]["approved_plan"]],
        },
    }
