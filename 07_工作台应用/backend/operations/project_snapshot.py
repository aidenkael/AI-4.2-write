# -*- coding: utf-8 -*-
"""One read-only, composed current-project snapshot for Go Write 2.0.

The snapshot is a view.  It never persists a new truth store and never mutates
Story State, Author Intent, accepted prose, planning, or the project model.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from operations.project_model import ProjectModelError, read_project_model

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PW = _REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"
_SP = _REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "StoryPlan"
for path in (_PW, _SP):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from project_workspace import (  # noqa: E402
    ContractError as PWContractError,
    WorkspaceError as PWWorkspaceError,
    load_project,
    resolve_project,
)
from story_plan import resolve_plan_activity  # noqa: E402


SCHEMA_VERSION = "gowrite_project_snapshot/v1"
_CHAPTER_RE = re.compile(r"^第(\d+)章\.md$")
_STATE_SECTIONS = (
    "canon_facts", "character_state", "relationship_state", "occurred_events", "open_threads",
)


class ProjectSnapshotError(Exception):
    """A logical current-project snapshot cannot be composed safely."""


def _label(entry: Any) -> str:
    if isinstance(entry, str):
        return entry
    if not isinstance(entry, dict):
        return str(entry) if entry is not None else ""
    for key in ("name", "title", "fact", "description", "text", "summary", "content", "label"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    value = entry.get("id")
    return value if isinstance(value, str) else ""


def _state_ref(area: str, entry: Any, index: int) -> str:
    if isinstance(entry, dict) and isinstance(entry.get("id"), str) and entry["id"]:
        return f"story_state:{area}:{entry['id']}"
    digest = hashlib.sha256(
        json.dumps(entry, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:12]
    return f"story_state:{area}:{index}:{digest}"


def _state_records(state: dict[str, Any], area: str) -> list[dict[str, Any]]:
    entries = state.get(area)
    if not isinstance(entries, list):
        return []
    category_for_area = {
        "character_state": "character",
        "relationship_state": "relationship",
        "canon_facts": "world_setting",
        "occurred_events": "event",
        "open_threads": "promise_foreshadowing",
    }
    result: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        record = copy.deepcopy(entry)
        result.append({
            "ref": _state_ref(area, entry, index),
            "source_ref": _state_ref(area, entry, index),
            "id": entry.get("id") if isinstance(entry, dict) else None,
            "title": _label(entry),
            "record": record,
            "material_state": "current",
            "source_kind": "production_story_state",
            "provenance": (entry or {}).get("authority") if isinstance(entry, dict) else None,
            # Editing is implemented as an author-workspace overlay.  The
            # production Story State entry remains preserved as provenance.
            "editable": True,
            "superseded": False,
            "category": category_for_area.get(area),
            "kind": "production_story_state",
        })
    return result


def _active_plans(state: dict[str, Any]) -> list[dict[str, Any]]:
    plans = state.get("approved_plan")
    if not isinstance(plans, list) or not plans:
        return []
    try:
        active = set(resolve_plan_activity(state).get("active") or [])
    except Exception:  # noqa: BLE001 - fail closed to no effective future plan
        return []
    result = []
    for index, entry in enumerate(plans):
        if not isinstance(entry, dict) or entry.get("id") not in active:
            continue
        result.append({
            "ref": _state_ref("approved_plan", entry, index),
            "source_ref": _state_ref("approved_plan", entry, index),
            "id": entry.get("id"),
            "title": _label(entry),
            "record": copy.deepcopy(entry),
            "material_state": "future",
            "source_kind": "approved_plan",
            "provenance": entry.get("authority"),
            "editable": False,
            "superseded": False,
        })
    return result


def _model_record(item: dict[str, Any]) -> dict[str, Any]:
    record = copy.deepcopy(item.get("data") or {})
    record.setdefault("name", item.get("title") or "")
    return {
        "ref": item["ref"],
        "source_ref": item["ref"],
        "id": item["ref"],
        "title": item.get("title") or "",
        "record": record,
        "material_state": item.get("material_state"),
        "source_kind": "author_workspace",
        "provenance": (item.get("data") or {}).get("planning_source_ref") or "author_explicit",
        "editable": True,
        "superseded": False,
        "category": item.get("category"),
        "kind": item.get("kind"),
    }


def _relationship_record(edge: dict[str, Any], objects: dict[str, Any]) -> dict[str, Any]:
    source = objects[edge["source_ref"]]
    target = objects[edge["target_ref"]]
    record = copy.deepcopy(edge.get("data") or {})
    record.update({
        "source": edge["source_ref"],
        "target": edge["target_ref"],
        "source_name": source.get("title") or "",
        "target_name": target.get("title") or "",
        "relationship": edge.get("title") or edge.get("relation_kind") or "",
    })
    return {
        "ref": edge["ref"],
        "source_ref": edge["ref"],
        "id": edge["ref"],
        "title": edge.get("title") or edge.get("relation_kind") or "",
        "record": record,
        "material_state": edge.get("material_state", "current"),
        "source_kind": "author_workspace_relationship",
        "provenance": record.get("planning_source_ref") or "author_explicit",
        "editable": True,
        "superseded": False,
        "category": "relationship",
        "kind": "dependency",
    }


def _chapter_number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _validated_chapters(loaded: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    project_dir = Path(loaded["project_dir"]).resolve()
    prose_root = (project_dir / "03_正文").resolve()
    entries = (loaded.get("index") or {}).get("entries") or []
    by_chapter: dict[int, list[dict[str, Any]]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ProjectSnapshotError("accepted_text_index 包含非法条目。")
        number = _chapter_number(entry.get("chapter_number"))
        if number is None:
            raise ProjectSnapshotError("accepted_text_index 包含非法 chapter_number。")
        by_chapter.setdefault(number, []).append(entry)

    paths: dict[int, Path] = {}
    if prose_root.exists():
        for path in prose_root.iterdir():
            if not path.is_file():
                continue
            match = _CHAPTER_RE.match(path.name)
            if match:
                paths[int(match.group(1))] = path.resolve()
    for number, chapter_entries in by_chapter.items():
        for entry in chapter_entries:
            rel = entry.get("chapter_path")
            if not isinstance(rel, str) or Path(rel).is_absolute() or ".." in rel:
                raise ProjectSnapshotError("accepted_text_index 章节路径非法。")
            path = (project_dir / rel).resolve()
            try:
                path.relative_to(prose_root)
            except ValueError as exc:
                raise ProjectSnapshotError("accepted_text_index 章节路径越界。") from exc
            if number in paths and paths[number] != path:
                raise ProjectSnapshotError(f"第{number}章路径与标准章节文件冲突。")
            paths[number] = path

    target_by_number: dict[int, dict[str, Any]] = {}
    for ref in model.get("length_plan", {}).get("chapter_target_refs", []):
        item = model.get("objects", {}).get(ref)
        if not isinstance(item, dict) or item.get("tombstoned"):
            continue
        data = item.get("data") or {}
        number = _chapter_number(data.get("chapter_number"))
        if number is not None and number not in target_by_number:
            target_by_number[number] = item

    chapters: list[dict[str, Any]] = []
    for number in sorted(set(paths) | set(target_by_number)):
        path = paths.get(number)
        if path is None:
            path = (prose_root / f"第{number:03d}章.md").resolve()
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        chapter_entries = by_chapter.get(number, [])
        for entry in chapter_entries:
            try:
                start = int(entry.get("start_char"))
                end = int(entry.get("end_char"))
            except (TypeError, ValueError) as exc:
                raise ProjectSnapshotError(f"第{number}章 accepted range 非法。") from exc
            if start < 0 or end < start or end > len(content):
                raise ProjectSnapshotError(f"第{number}章 accepted range 越界。")
            actual = hashlib.sha256(content[start:end].encode("utf-8")).hexdigest()
            if actual != entry.get("content_sha256"):
                raise ProjectSnapshotError(f"第{number}章 accepted index SHA 不匹配。")
        target = target_by_number.get(number)
        target_data = copy.deepcopy((target or {}).get("data") or {})
        title = target_data.get("chapter_title") or (target or {}).get("title") or f"第{number}章"
        chapters.append({
            "chapter_number": number,
            "title": title,
            "path": str(path),
            "content": content,
            "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "actual_words": len(content),
            "accepted_scene_count": len(chapter_entries),
            "accepted": bool(chapter_entries),
            "fine_outline_ref": (target or {}).get("ref"),
            "fine_outline": target_data,
        })
    if not chapters:
        chapters.append({
            "chapter_number": 1, "title": "第1章", "path": str(prose_root / "第001章.md"),
            "content": "", "content_sha256": hashlib.sha256(b"").hexdigest(),
            "actual_words": 0, "accepted_scene_count": 0, "accepted": False,
            "fine_outline_ref": None, "fine_outline": {},
        })
    return chapters


def _settlement_summary(project_dir: Path) -> dict[str, Any]:
    path = project_dir / "_工作台状态" / "author_changes.json"
    if not path.exists():
        return {"status": "synchronized", "pending_count": 0, "failed_count": 0, "changes": []}
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectSnapshotError(f"作者变更记录读取失败：{exc}") from exc
    changes = artifact.get("changes") if isinstance(artifact, dict) else None
    if not isinstance(changes, list):
        raise ProjectSnapshotError("作者变更记录结构非法。")
    pending = sum(
        1 for item in changes
        if isinstance(item, dict) and item.get("status") in {"pending", "awaiting_author"}
    )
    failed = sum(1 for item in changes if isinstance(item, dict) and item.get("status") == "failed")
    return {
        "status": "pending" if pending else ("failed" if failed else "synchronized"),
        "pending_count": pending, "failed_count": failed,
        "changes": copy.deepcopy(changes[-20:]),
    }


def get_project_snapshot(project_id: str) -> dict[str, Any]:
    project_id = (project_id or "").strip()
    if not project_id:
        raise ProjectSnapshotError("缺少 project_id。")
    try:
        project = resolve_project(project_id)
        loaded = load_project(project["project_dir"])
        model = read_project_model(project_id)
    except (PWContractError, PWWorkspaceError, ProjectModelError) as exc:
        raise ProjectSnapshotError(str(exc)) from exc
    if loaded["project_id"] != project_id or model["project_id"] != project_id:
        raise ProjectSnapshotError("项目身份不一致，已拒绝快照。")

    state = loaded["state"]
    current: dict[str, list[dict[str, Any]]] = {
        "characters": _state_records(state, "character_state"),
        "relationships": _state_records(state, "relationship_state"),
        "settings": _state_records(state, "canon_facts"),
        "events": _state_records(state, "occurred_events"),
        "open_threads": _state_records(state, "open_threads"),
        "foreshadowing": [],
        "storylines": [],
    }
    future: dict[str, list[dict[str, Any]]] = {
        "characters": [], "relationships": [], "settings": [], "events": [],
        "open_threads": [], "foreshadowing": [], "storylines": [],
        "approved_plan": _active_plans(state),
    }
    category_section = {
        "character": "characters", "relationship": "relationships", "world_setting": "settings",
        "location": "settings", "organization_force": "settings", "custom": "settings",
        "event": "events", "promise_foreshadowing": "foreshadowing", "story_line": "storylines",
    }
    for item in model.get("objects", {}).values():
        if not isinstance(item, dict) or item.get("tombstoned") or item.get("kind") != "foundation":
            continue
        section = category_section.get(item.get("category"))
        if not section:
            continue
        bucket = current if item.get("material_state") == "current" else future
        bucket[section].append(_model_record(item))
    for edge in model.get("dependencies", {}).values():
        if not isinstance(edge, dict) or edge.get("tombstoned") or edge.get("relation_kind") != "character_relationship":
            continue
        bucket = current if edge.get("material_state", "current") == "current" else future
        bucket["relationships"].append(_relationship_record(edge, model["objects"]))

    # An explicit author-workspace overlay can supersede a raw Story State
    # projection without deleting the historical production entry.
    superseded_state_refs = {
        str((item.get("data") or {}).get("supersedes_state_ref") or (item.get("data") or {}).get("source_state_ref"))
        for item in [
            *model.get("objects", {}).values(),
            *model.get("dependencies", {}).values(),
        ]
        if isinstance(item, dict)
        and isinstance(item.get("data"), dict)
        and ((item.get("data") or {}).get("supersedes_state_ref") or (item.get("data") or {}).get("source_state_ref"))
    }
    if superseded_state_refs:
        for section in current:
            current[section] = [item for item in current[section] if item.get("ref") not in superseded_state_refs]

    chapters = _validated_chapters(loaded, model)
    stages = [
        _model_record(model["objects"][ref])
        for ref in model.get("length_plan", {}).get("stage_refs", [])
        if ref in model.get("objects", {}) and not model["objects"][ref].get("tombstoned")
    ]
    length_plan = {
        "total_target_words": model.get("length_plan", {}).get("total_target_words"),
        "stages": stages,
        "chapters": [{
            "ref": chapter.get("fine_outline_ref"), "chapter_number": chapter["chapter_number"],
            "title": chapter["title"], "actual_words": chapter["actual_words"],
            **copy.deepcopy(chapter.get("fine_outline") or {}),
        } for chapter in chapters],
        "actual_total_words": sum(chapter["actual_words"] for chapter in chapters),
    }
    project_dir = Path(loaded["project_dir"]).resolve()
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": project_id,
        "name": loaded["name"],
        "identity": {"project_id": project_id, "name": loaded["name"], "project_dir": str(project_dir)},
        "author_intent": copy.deepcopy(loaded["intent"]),
        "story_state": {
            "state_rev": state.get("state_rev"),
            "last_authority_source": state.get("last_authority_source"),
        },
        "model_rev": model.get("model_rev", 0),
        "current": current,
        "future": future,
        "length_plan": length_plan,
        "chapters": chapters,
        "settlement": _settlement_summary(project_dir),
    }


def focused_task_context(
    project_id: str,
    *,
    chapter_number: int | None = None,
) -> dict[str, Any]:
    """Small effective view for Planning/Writing/Review task preparation."""
    snapshot = get_project_snapshot(project_id)
    chapter = next(
        (item for item in snapshot["chapters"] if item["chapter_number"] == chapter_number), None,
    ) if chapter_number is not None else None
    if snapshot["settlement"]["status"] in {"pending", "failed"}:
        settlement_gate = {
            "status": snapshot["settlement"]["status"],
            "message": "存在尚未完成的语义同步；以下显式作者编辑仍优先，但派生状态可能不完整。",
        }
    else:
        settlement_gate = {"status": "synchronized", "message": ""}
    return {
        "project_id": project_id,
        "model_rev": snapshot["model_rev"],
        "state_rev": snapshot["story_state"]["state_rev"],
        "settlement": settlement_gate,
        "current": {
            key: [{"ref": item["ref"], "title": item["title"], "record": item["record"]} for item in values]
            for key, values in snapshot["current"].items()
        },
        "future": {
            key: [{"ref": item["ref"], "title": item["title"], "record": item["record"]} for item in values]
            for key, values in snapshot["future"].items()
        },
        "chapter": None if chapter is None else {
            "chapter_number": chapter["chapter_number"],
            "title": chapter["title"],
            "actual_words": chapter["actual_words"],
            "fine_outline": copy.deepcopy(chapter.get("fine_outline") or {}),
        },
    }
