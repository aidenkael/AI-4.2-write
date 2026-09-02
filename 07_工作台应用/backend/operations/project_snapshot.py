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

from operations.project_model import (
    DOMAIN_RELATION_KINDS,
    ProjectModelError,
    inactive_planning_source_refs,
    read_project_model,
)

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


SCHEMA_VERSION = "gowrite_project_snapshot/v3"
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


def _character_state_records(state: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Separate explicit identities from free-form state observations."""
    entries = state.get("character_state")
    if not isinstance(entries, list):
        return [], []
    identities: list[dict[str, Any]] = []
    observations: list[tuple[int, Any]] = []
    aliases: dict[str, set[str]] = {}
    by_ref: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            observations.append((index, entry))
            continue
        explicit_id = entry.get("id") if isinstance(entry.get("id"), str) and entry["id"].strip() else None
        explicit_name = entry.get("name") if isinstance(entry.get("name"), str) and entry["name"].strip() else None
        if not explicit_id and not explicit_name:
            observations.append((index, entry))
            continue
        ref = _state_ref("character_state", entry, index)
        record = copy.deepcopy(entry)
        projected = {
            "ref": ref, "source_ref": ref, "id": explicit_id,
            "title": (explicit_name or explicit_id or "").strip(), "record": record,
            "material_state": "current", "source_kind": "production_story_state",
            "provenance": entry.get("authority"), "editable": True, "superseded": False,
            "category": "character", "kind": "production_story_state",
        }
        identities.append(projected)
        by_ref[ref] = projected
        alias_values = [explicit_id, explicit_name]
        if isinstance(entry.get("aliases"), list):
            alias_values.extend(entry["aliases"])
        for value in alias_values:
            if isinstance(value, str) and value.strip():
                aliases.setdefault(value.strip(), set()).add(ref)

    unresolved: list[dict[str, Any]] = []
    for index, entry in observations:
        target = None
        if isinstance(entry, dict):
            for key in ("character_ref", "character_id", "character_name", "subject_ref", "subject_name", "character"):
                if isinstance(entry.get(key), str) and entry[key].strip():
                    target = entry[key].strip()
                    break
        matches = aliases.get(target or "", set())
        if len(matches) == 1:
            record = by_ref[next(iter(matches))]["record"]
            record.setdefault("state_observations", []).append(copy.deepcopy(entry))
        else:
            unresolved.append({
                "source_ref": _state_ref("character_state", entry, index),
                "observation": copy.deepcopy(entry),
                "reason": "missing_explicit_identity" if not target else "identity_not_uniquely_resolved",
            })
    return identities, unresolved


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


def _dependency_category(item: dict[str, Any]) -> str | None:
    """作者可读分类：体系对象统一显示为 system。"""
    if not isinstance(item, dict):
        return None
    return "system" if item.get("kind") == "system" else item.get("category")


# 快照可见的显式关系类型：人物关系 + 批准的领域关系类型。
_VISIBLE_RELATION_KINDS = {"character_relationship", *DOMAIN_RELATION_KINDS}


def _explicit_dependencies(
    model: dict[str, Any],
    inactive_planning_sources: frozenset[str] | set[str] = frozenset(),
) -> list[dict[str, Any]]:
    """活动显式依赖的只读投影；不含 tombstoned 边，不改写任何源记录。

    血缘已失效（规划被取代）的规划派生边不作为有效未来事实暴露。
    """
    objects = model.get("objects", {})
    result: list[dict[str, Any]] = []
    for edge in model.get("dependencies", {}).values():
        if not isinstance(edge, dict) or edge.get("tombstoned"):
            continue
        if edge.get("relation_kind") not in _VISIBLE_RELATION_KINDS:
            continue
        edge_data = edge.get("data") if isinstance(edge.get("data"), dict) else {}
        if edge_data.get("planning_source_ref") in inactive_planning_sources:
            continue
        source = objects.get(edge["source_ref"])
        target = objects.get(edge["target_ref"])
        if not isinstance(source, dict) or not isinstance(target, dict):
            continue
        result.append({
            "ref": edge["ref"],
            "relation_kind": edge.get("relation_kind"),
            "title": edge.get("title") or edge.get("relation_kind") or "",
            "material_state": edge.get("material_state", "current"),
            "source_ref": edge["source_ref"],
            "source_title": source.get("title") or "",
            "source_category": _dependency_category(source),
            "target_ref": edge["target_ref"],
            "target_title": target.get("title") or "",
            "target_category": _dependency_category(target),
            "data": copy.deepcopy(edge.get("data") or {}),
        })
    result.sort(key=lambda item: item["ref"])
    return result


def _chapter_number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _validated_chapters(
    loaded: dict[str, Any],
    model: dict[str, Any],
    inactive_planning_sources: frozenset[str] | set[str] = frozenset(),
) -> list[dict[str, Any]]:
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

    stage_titles: dict[str, str] = {}
    stage_refs_by_title: dict[str, list[str]] = {}
    for ref in model.get("length_plan", {}).get("stage_refs", []):
        item = model.get("objects", {}).get(ref)
        if not isinstance(item, dict) or item.get("tombstoned") or item.get("kind") != "length_stage":
            continue
        title = str(item.get("title") or "")
        stage_titles[ref] = title
        if title:
            stage_refs_by_title.setdefault(title, []).append(ref)

    target_by_number: dict[int, dict[str, Any]] = {}
    for ref in model.get("length_plan", {}).get("chapter_target_refs", []):
        item = model.get("objects", {}).get(ref)
        if not isinstance(item, dict) or item.get("tombstoned"):
            continue
        data = item.get("data") or {}
        if data.get("planning_source_ref") in inactive_planning_sources:
            continue
        number = _chapter_number(data.get("chapter_number"))
        if number is None:
            continue
        existing = target_by_number.get(number)
        if existing is None:
            target_by_number[number] = item
            continue
        # 防御性确定性平手（写入侧已强制唯一）：非规划派生优先，其余取最小 ref，
        # 结果与 dict 插入顺序无关。
        existing_derived = bool((existing.get("data") or {}).get("planning_source_ref"))
        new_derived = bool(data.get("planning_source_ref"))
        if (existing_derived and not new_derived) or (
            existing_derived == new_derived and ref < existing["ref"]
        ):
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
        stage_ref = target_data.get("stage_ref")
        legacy_stage = target_data.get("stage")
        stage_unresolved = None
        if isinstance(stage_ref, str) and stage_ref in stage_titles:
            target_data["stage_ref"] = stage_ref
            target_data["stage_title"] = stage_titles[stage_ref]
        elif stage_ref is not None:
            target_data.pop("stage_ref", None)
            stage_unresolved = "invalid_stage_ref"
        elif isinstance(legacy_stage, str) and legacy_stage.strip():
            matches = stage_refs_by_title.get(legacy_stage.strip(), [])
            if len(matches) == 1:
                target_data["stage_ref"] = matches[0]
                target_data["stage_title"] = stage_titles[matches[0]]
                target_data["legacy_stage"] = legacy_stage.strip()
            else:
                stage_unresolved = "ambiguous_or_unmatched_legacy_stage"
        else:
            target_data.pop("stage_ref", None)
        target_data.pop("stage", None)
        if stage_unresolved:
            target_data["stage_unresolved"] = stage_unresolved
        title = target_data.get("chapter_title") or (target or {}).get("title") or f"第{number}章"
        formal_prose_exists = path.exists()
        chapters.append({
            "chapter_number": number,
            "title": title,
            "path": str(path),
            "content": content,
            "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "formal_prose_exists": formal_prose_exists,
            "actual_words": len(content),
            "accepted_scene_count": len(chapter_entries),
            "accepted": bool(chapter_entries),
            "fine_outline_ref": (target or {}).get("ref"),
            "fine_outline": target_data,
            "actual_result": copy.deepcopy(model.get("chapter_actual_results", {}).get(str(number))),
        })
    if not chapters:
        chapters.append({
            "chapter_number": 1, "title": "第1章", "path": str(prose_root / "第001章.md"),
            "content": "", "content_sha256": hashlib.sha256(b"").hexdigest(),
            "formal_prose_exists": False,
            "actual_words": 0, "accepted_scene_count": 0, "accepted": False,
            "fine_outline_ref": None, "fine_outline": {},
            "actual_result": copy.deepcopy(model.get("chapter_actual_results", {}).get("1")),
        })
    return chapters


def _settlement_summary(project_dir: Path) -> dict[str, Any]:
    path = project_dir / "_工作台状态" / "author_changes.json"
    if not path.exists():
        return {
            "status": "synchronized", "pending_count": 0, "failed_count": 0,
            "changes": [], "state_refresh": {},
        }
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
    needs_semantic_ai_config = any(
        isinstance(item, dict)
        and item.get("status") in {"pending", "failed"}
        and isinstance(item.get("error"), str)
        and item["error"].startswith("NEEDS_SEMANTIC_AI_CONFIG")
        for item in changes
    )
    stored_refresh = artifact.get("state_refresh") if isinstance(artifact.get("state_refresh"), dict) else {}
    return {
        "status": "pending" if pending else ("failed" if failed else "synchronized"),
        "pending_count": pending, "failed_count": failed,
        "needs_semantic_ai_config": needs_semantic_ai_config,
        "changes": copy.deepcopy(changes[-20:]),
        "state_refresh": copy.deepcopy(stored_refresh),
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
    # 血缘读不变量：被取代规划（resolve_plan_activity 非 active）的投影不再是有效未来，
    # 历史记录仍物理存储可审计；作者已提升为 current 的记录不受血缘过滤影响。
    try:
        active_plan_ids = set(resolve_plan_activity(state).get("active") or [])
    except Exception:  # noqa: BLE001 - fail closed：血缘异常不误伤有效投影
        active_plan_ids = {
            entry.get("id") for entry in (state.get("approved_plan") or [])
            if isinstance(entry, dict) and entry.get("id")
        }
    inactive_planning_sources = frozenset(inactive_planning_source_refs(model, active_plan_ids))

    def _effective_future(item_data: dict[str, Any], material_state: str | None) -> bool:
        if material_state != "future":
            return True
        return item_data.get("planning_source_ref") not in inactive_planning_sources

    character_records, unresolved_character_observations = _character_state_records(state)
    current: dict[str, list[dict[str, Any]]] = {
        "characters": character_records,
        "relationships": _state_records(state, "relationship_state"),
        "settings": _state_records(state, "canon_facts"),
        "locations": [],
        "organizations": [],
        "systems": [],
        "events": _state_records(state, "occurred_events"),
        "open_threads": _state_records(state, "open_threads"),
        "foreshadowing": [],
        "storylines": [],
        "mystery_information": [],
    }
    future: dict[str, list[dict[str, Any]]] = {
        "characters": [], "relationships": [], "settings": [], "locations": [],
        "organizations": [], "systems": [], "events": [], "open_threads": [],
        "foreshadowing": [], "storylines": [], "mystery_information": [],
        "approved_plan": _active_plans(state),
    }
    category_section = {
        "character": "characters", "relationship": "relationships", "world_setting": "settings",
        "location": "locations", "organization_force": "organizations", "custom": "settings",
        "event": "events", "promise_foreshadowing": "foreshadowing", "story_line": "storylines",
        "mystery_information": "mystery_information",
    }
    for item in model.get("objects", {}).values():
        if not isinstance(item, dict) or item.get("tombstoned") or item.get("kind") != "foundation":
            continue
        section = category_section.get(item.get("category"))
        if not section:
            continue
        if not _effective_future(item.get("data") or {}, item.get("material_state")):
            continue
        bucket = current if item.get("material_state") == "current" else future
        bucket[section].append(_model_record(item))
    for item in model.get("objects", {}).values():
        if not isinstance(item, dict) or item.get("tombstoned") or item.get("kind") != "system":
            continue
        if not _effective_future(item.get("data") or {}, item.get("material_state")):
            continue
        bucket = current if item.get("material_state") == "current" else future
        bucket["systems"].append(_model_record(item))
    for edge in model.get("dependencies", {}).values():
        if not isinstance(edge, dict) or edge.get("tombstoned") or edge.get("relation_kind") != "character_relationship":
            continue
        if not _effective_future(edge.get("data") or {}, edge.get("material_state", "current")):
            continue
        bucket = current if edge.get("material_state", "current") == "current" else future
        bucket["relationships"].append(_relationship_record(edge, model["objects"]))

    # 既有实体的未来走向（规划派生）：不新建第二身份，只附在 target_ref 上；
    # 血缘失效或目标已退役的轨迹不作为有效未来暴露。
    future_trajectories: list[dict[str, Any]] = []
    for ref, item in model.get("objects", {}).items():
        if not isinstance(item, dict) or item.get("tombstoned") or item.get("kind") != "future_trajectory":
            continue
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        if data.get("planning_source_ref") in inactive_planning_sources:
            continue
        target = model.get("objects", {}).get(data.get("target_ref") or "")
        if not isinstance(target, dict) or target.get("tombstoned"):
            continue
        future_trajectories.append({
            "ref": ref,
            "target_ref": data.get("target_ref"),
            "target_title": target.get("title") or "",
            "category": item.get("category"),
            "title": item.get("title") or "",
            "planning_source_ref": data.get("planning_source_ref"),
            "record": copy.deepcopy(data),
        })
    future_trajectories.sort(key=lambda entry: entry["ref"])

    # Soft-retired records stay stored and retrievable, but never mix into
    # current/future projections (Story Map must not render them as active).
    retired: dict[str, list[dict[str, Any]]] = {"foundation": [], "relationships": []}
    for item in model.get("objects", {}).values():
        if (
            not isinstance(item, dict)
            or not item.get("tombstoned")
            or item.get("kind") not in {"foundation", "system"}
        ):
            continue
        record = _model_record(item)
        record["retired_at_rev"] = item.get("tombstoned_at_rev")
        retired["foundation"].append(record)
    for edge in model.get("dependencies", {}).values():
        if (
            not isinstance(edge, dict)
            or not edge.get("tombstoned")
            or edge.get("relation_kind") != "character_relationship"
        ):
            continue
        record = _relationship_record(edge, model["objects"])
        record["retired_at_rev"] = edge.get("tombstoned_at_rev")
        retired["relationships"].append(record)

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

    chapters = _validated_chapters(loaded, model, inactive_planning_sources)
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
            "formal_prose_exists": chapter["formal_prose_exists"],
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
        "story_bible_profile": copy.deepcopy(model["story_bible_profile"]),
        "current": current,
        "future": future,
        "retired": retired,
        "length_plan": length_plan,
        "chapters": chapters,
        "explicit_dependencies": _explicit_dependencies(model, inactive_planning_sources),
        "future_trajectories": future_trajectories,
        "planning_impact_candidates": copy.deepcopy(model.get("planning_impact_candidates", [])),
        "legacy_diagnostics": {
            "unresolved_character_observations": unresolved_character_observations,
        },
        "settlement": _settlement_summary(project_dir),
    }


# 任务近端上下文硬上限：一跳关系边 / 新增关联对象 / 每分区记录。
_MAX_TASK_RELATION_EDGES = 16
_MAX_TASK_RELATED_OBJECTS = 12
_MAX_TASK_RECORDS_PER_SECTION = 12

_OUTLINE_SEED_FIELDS = (
    "participating_characters", "new_characters", "character_refs", "relationship_refs",
    "location_ref", "location", "organization_refs", "system_refs", "storyline_ref",
    "storyline", "foreshadowing_refs", "open_thread_refs", "related_refs",
)


def _outline_seed_tokens(chapter: dict[str, Any] | None) -> list[str]:
    """章节细纲中的显式种子文本（ref 或名称）；不做任何推断。"""
    tokens: list[str] = []
    outline = (chapter or {}).get("fine_outline") if isinstance((chapter or {}).get("fine_outline"), dict) else {}
    for key in _OUTLINE_SEED_FIELDS:
        value = outline.get(key)
        if isinstance(value, str) and value.strip():
            tokens.append(value.strip())
        elif isinstance(value, list):
            tokens.extend(item.strip() for item in value if isinstance(item, str) and item.strip())
    return tokens


def _active_record_index(
    snapshot: dict[str, Any],
) -> tuple[dict[str, tuple[str, str, dict[str, Any]]], dict[str, list[str]]]:
    """活动 current/future 记录的 ref 索引与标题 → refs 索引。"""
    by_ref: dict[str, tuple[str, str, dict[str, Any]]] = {}
    by_title: dict[str, list[str]] = {}
    for bucket_name in ("current", "future"):
        for section, values in snapshot[bucket_name].items():
            for item in values:
                ref = item.get("ref")
                if not isinstance(ref, str) or not ref:
                    continue
                by_ref[ref] = (bucket_name, section, item)
                title = item.get("title")
                if isinstance(title, str) and title.strip():
                    by_title.setdefault(title.strip(), []).append(ref)
    return by_ref, by_title


def _is_global_rule_record(section: str, item: dict[str, Any]) -> bool:
    record = item.get("record") if isinstance(item.get("record"), dict) else {}
    return section in {"settings", "systems"} and (
        record.get("context_scope") == "global" or bool(record.get("hard_rule"))
    )


def _resolve_direct_seeds(
    tokens: list[str],
    by_ref: dict[str, tuple[str, str, dict[str, Any]]],
    by_title: dict[str, list[str]],
) -> list[str]:
    """直接种子解析：精确 ref 直接命中；精确标题只有唯一活动记录时才是种子。

    歧义/重复标题绝不选择多条；无模糊匹配；无语义推断。
    """
    seeds: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in by_ref:
            ref = token
        else:
            matches = by_title.get(token, [])
            if len(matches) != 1:
                continue
            ref = matches[0]
        if ref not in seen:
            seen.add(ref)
            seeds.append(ref)
    return seeds


def _focus_text_seeds(focus_text: str, by_title: dict[str, list[str]]) -> list[str]:
    """规划 focus_text 只按“字面出现且唯一精确匹配”的存储标题产生种子。"""
    seeds: list[str] = []
    for title, refs in by_title.items():
        if len(refs) == 1 and title in focus_text:
            seeds.append(refs[0])
    return seeds


def _task_relevant_context(
    snapshot: dict[str, Any],
    chapter: dict[str, Any] | None,
    focus_text: str | None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """选择任务近端记录 + 有界一跳显式关系；绝不 fallback 全书。

    一跳只在原始直接种子上展开；新加入的关联记录绝不继续递归。
    """
    by_ref, by_title = _active_record_index(snapshot)
    seed_refs = _resolve_direct_seeds(_outline_seed_tokens(chapter), by_ref, by_title)
    if chapter is None:
        focus = (focus_text or "").strip()
        if focus:
            existing = set(seed_refs)
            seed_refs.extend(ref for ref in _focus_text_seeds(focus, by_title) if ref not in existing)
        if not seed_refs:
            # 无种子时保留既有有界规划摘要行为（不是全书 fallback）。
            return (
                {key: values[:_MAX_TASK_RECORDS_PER_SECTION] for key, values in snapshot["current"].items()},
                {key: values[:_MAX_TASK_RECORDS_PER_SECTION] for key, values in snapshot["future"].items()},
                [],
            )
    seed_set = set(seed_refs)

    # 一跳边选择：只取与原始种子直接相连的活动边；确定性排序后封顶。
    candidates: list[tuple[int, int, str, dict[str, Any]]] = []
    for edge in snapshot.get("explicit_dependencies", []):
        src_seed = edge["source_ref"] in seed_set
        tgt_seed = edge["target_ref"] in seed_set
        if not src_seed and not tgt_seed:
            continue
        candidates.append((
            0 if src_seed and tgt_seed else 1,
            0 if edge.get("material_state", "current") == "current" else 1,
            edge["ref"],
            edge,
        ))
    candidates.sort(key=lambda entry: (entry[0], entry[1], entry[2]))
    selected_edges = [entry[3] for entry in candidates[:_MAX_TASK_RELATION_EDGES]]

    selected: dict[str, tuple[str, str, dict[str, Any]]] = {}
    order: list[str] = []

    def add_record(ref: str) -> bool:
        if ref in selected or ref not in by_ref:
            return False
        selected[ref] = by_ref[ref]
        order.append(ref)
        return True

    for ref in seed_refs:
        add_record(ref)
    added_related = 0
    for edge in selected_edges:
        for endpoint in (edge["source_ref"], edge["target_ref"]):
            if endpoint in seed_set or endpoint in selected:
                continue
            if added_related >= _MAX_TASK_RELATED_OBJECTS:
                continue
            if add_record(endpoint):
                added_related += 1

    relevant_current: dict[str, list[dict[str, Any]]] = {section: [] for section in snapshot["current"]}
    relevant_future: dict[str, list[dict[str, Any]]] = {section: [] for section in snapshot["future"]}
    for ref in order:
        bucket_name, section, item = selected[ref]
        target = relevant_current if bucket_name == "current" else relevant_future
        if len(target[section]) < _MAX_TASK_RECORDS_PER_SECTION:
            target[section].append(item)
    # 全局设定/硬规则保留既有确定性包含行为。
    for source, target in ((snapshot["current"], relevant_current), (snapshot["future"], relevant_future)):
        for section, values in source.items():
            for item in values:
                if item.get("ref") in selected:
                    continue
                if not _is_global_rule_record(section, item):
                    continue
                if len(target[section]) < _MAX_TASK_RECORDS_PER_SECTION:
                    target[section].append(item)
    # 选中的 character_relationship 边进入既有 relationships 分区。
    for edge in selected_edges:
        if edge.get("relation_kind") != "character_relationship":
            continue
        for bucket_name, target in (("current", relevant_current), ("future", relevant_future)):
            for item in snapshot[bucket_name].get("relationships", []):
                if item.get("ref") != edge["ref"]:
                    continue
                if (
                    len(target["relationships"]) < _MAX_TASK_RECORDS_PER_SECTION
                    and all(existing.get("ref") != edge["ref"] for existing in target["relationships"])
                ):
                    target["relationships"].append(item)
    explicit_relations = [
        {
            "relation_kind": edge.get("relation_kind"),
            "title": edge.get("title") or "",
            "material_state": edge.get("material_state", "current"),
            "source_ref": edge["source_ref"],
            "source_title": edge.get("source_title") or "",
            "source_category": edge.get("source_category"),
            "target_ref": edge["target_ref"],
            "target_title": edge.get("target_title") or "",
            "target_category": edge.get("target_category"),
        }
        for edge in selected_edges
    ]
    return relevant_current, relevant_future, explicit_relations


def build_planning_impact_frontier(
    project_id: str,
    *,
    changed_object_refs: list[str] | None = None,
    changed_dependency_refs: list[str] | None = None,
    changed_chapter_numbers: list[int] | None = None,
) -> dict[str, Any]:
    """有界确定性规划影响前沿：只从显式事实收集机械相关的未来候选。

    规则：不递归、不模糊语义图遍历、不全书展开；只读零写回。
    输出只是候选输入，不代表每一项都真的受影响。
    """
    model = read_project_model(project_id)
    changed_refs = {
        ref for ref in (changed_object_refs or []) if isinstance(ref, str) and ref
    }
    for dep_ref in (changed_dependency_refs or []):
        if not isinstance(dep_ref, str) or not dep_ref:
            continue
        edge = model.get("dependencies", {}).get(dep_ref)
        if isinstance(edge, dict):
            changed_refs.add(edge.get("source_ref") or "")
            changed_refs.add(edge.get("target_ref") or "")
    changed_refs.discard("")
    changed_chapters = {
        number for number in (changed_chapter_numbers or [])
        if isinstance(number, int) and not isinstance(number, bool) and number > 0
    }
    objects = model.get("objects", {})
    changed_titles = {
        objects[ref].get("title") for ref in changed_refs
        if ref in objects and isinstance(objects[ref], dict) and objects[ref].get("title")
    }

    neighbor_refs: set[str] = set()
    storyline_refs: set[str] = set()
    foreshadowing_refs: set[str] = set()
    if changed_refs:
        for edge in model.get("dependencies", {}).values():
            if not isinstance(edge, dict) or edge.get("tombstoned"):
                continue
            src, tgt = edge.get("source_ref"), edge.get("target_ref")
            if src not in changed_refs and tgt not in changed_refs:
                continue
            other = tgt if src in changed_refs else src
            kind = edge.get("relation_kind")
            if kind in {
                "storyline_involves_character", "storyline_involves_organization",
                "storyline_involves_location",
            }:
                line = objects.get(src) if isinstance(src, str) else None
                if isinstance(line, dict) and line.get("category") == "story_line":
                    storyline_refs.add(src)
            if kind in {"foreshadowing_related_to", "mystery_information_related_to"}:
                head = objects.get(src) if isinstance(src, str) else None
                if isinstance(head, dict) and head.get("category") in {
                    "promise_foreshadowing", "mystery_information",
                }:
                    foreshadowing_refs.add(src)
            if isinstance(other, str) and other:
                neighbor_refs.add(other)

    trajectory_refs = {
        ref for ref, item in objects.items()
        if isinstance(item, dict) and not item.get("tombstoned")
        and item.get("kind") == "future_trajectory"
        and (item.get("data") or {}).get("target_ref") in changed_refs
    }

    # 章节目标：只认显式引用（精确 ref 或精确标题出现在细纲字段中）。
    chapter_target_refs: set[str] = set()
    target_stage_by_number: dict[int, str | None] = {}
    for ref in model.get("length_plan", {}).get("chapter_target_refs", []):
        item = objects.get(ref)
        if not isinstance(item, dict) or item.get("tombstoned"):
            continue
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        number = _chapter_number(data.get("chapter_number"))
        if number is not None:
            target_stage_by_number[number] = data.get("stage_ref")
        explicit = False
        for value in data.values():
            values = value if isinstance(value, list) else [value]
            for entry in values:
                if isinstance(entry, str) and entry.strip() and (
                    entry.strip() in changed_refs or entry.strip() in changed_titles
                ):
                    explicit = True
                    break
            if explicit:
                break
        if explicit:
            chapter_target_refs.add(ref)

    # 同阶段后续章节骨架：编辑的章本身变化时，只扫同一活动阶段的后续章。
    later_same_stage: set[int] = set()
    for number in changed_chapters:
        stage_ref = target_stage_by_number.get(number)
        if not isinstance(stage_ref, str) or not stage_ref:
            continue
        for other_number, other_stage in target_stage_by_number.items():
            if other_stage == stage_ref and other_number > number:
                later_same_stage.add(other_number)

    affected_future_refs = sorted(
        neighbor_refs | trajectory_refs | storyline_refs | foreshadowing_refs | chapter_target_refs
    )
    planning_source_refs = sorted({
        (objects[ref].get("data") or {}).get("planning_source_ref")
        for ref in affected_future_refs
        if ref in objects and isinstance(objects[ref], dict)
        and isinstance((objects[ref].get("data") or {}).get("planning_source_ref"), str)
    })
    return {
        "changed_object_refs": sorted(changed_refs),
        "changed_chapter_numbers": sorted(changed_chapters),
        "neighbor_object_refs": sorted(neighbor_refs),
        "future_trajectory_refs": sorted(trajectory_refs),
        "storyline_refs": sorted(storyline_refs),
        "foreshadowing_refs": sorted(foreshadowing_refs),
        "chapter_target_refs": sorted(chapter_target_refs),
        "later_same_stage_chapter_numbers": sorted(later_same_stage),
        "affected_future_refs": affected_future_refs,
        "affected_planning_source_refs": planning_source_refs,
    }


def focused_task_context(
    project_id: str,
    *,
    chapter_number: int | None = None,
    focus_text: str | None = None,
) -> dict[str, Any]:
    """Small effective view for Planning/Writing/Review task preparation.

    Planning 可传入 ``focus_text``（如作者本轮问题）：只有字面出现且唯一精确匹配
    的存储标题才会成为直接种子；无匹配时保留既有有界规划摘要行为。
    """
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
    relevant_current, relevant_future, explicit_relations = _task_relevant_context(
        snapshot, chapter, focus_text,
    )
    pending_manifest = []
    pending_chapter_numbers: set[int] = set()
    for item in snapshot["settlement"].get("changes", []):
        if not isinstance(item, dict) or item.get("status") not in {"pending", "failed", "awaiting_author"}:
            continue
        delta = item.get("delta") if isinstance(item.get("delta"), dict) else {}
        chapter_no = delta.get("chapter_number")
        if isinstance(chapter_no, int):
            pending_chapter_numbers.add(chapter_no)
        pending_manifest.append({
            "change_id": item.get("change_id"), "sequence": item.get("sequence"),
            "source_kind": item.get("source_kind"), "chapter_number": chapter_no,
            "target": (delta.get("project_model_change") or {}).get("detail", {}).get("ref")
            if isinstance(delta.get("project_model_change"), dict) else None,
        })
    pending_manifest = pending_manifest[-12:]
    # 任务近端未来走向：只注入与本次任务选中实体直接相关的规划轨迹，
    # 不注入全书规划；未来轨迹绝不覆盖当前状态。
    involved_refs = {
        item.get("ref")
        for values in (*relevant_current.values(), *relevant_future.values())
        for item in values
        if isinstance(item.get("ref"), str)
    }
    task_trajectories = [
        {
            "ref": entry["ref"], "target_ref": entry["target_ref"],
            "target_title": entry["target_title"], "category": entry["category"],
            "title": entry["title"], "record": entry["record"],
        }
        for entry in snapshot.get("future_trajectories", [])
        if entry.get("target_ref") in involved_refs
    ][:_MAX_TASK_RELATED_OBJECTS]
    previous_result = None
    previous_content = None
    if chapter_number is not None and chapter_number > 1:
        previous = next(
            (item for item in snapshot["chapters"] if item["chapter_number"] == chapter_number - 1),
            None,
        )
        previous_result = copy.deepcopy((previous or {}).get("actual_result"))
        previous_content = str((previous or {}).get("content") or "")[-2000:]
    changed_chapters = []
    for item in snapshot["chapters"]:
        if item["chapter_number"] in pending_chapter_numbers:
            changed_chapters.append({
                "chapter_number": item["chapter_number"], "content_sha256": item.get("content_sha256"),
                "content_excerpt": str(item.get("content") or "")[-2000:],
            })
        if len(changed_chapters) >= 4:
            break
    return {
        "project_id": project_id,
        "model_rev": snapshot["model_rev"],
        "state_rev": snapshot["story_state"]["state_rev"],
        "story_bible_profile": copy.deepcopy(snapshot["story_bible_profile"]),
        "settlement": settlement_gate,
        "unconsolidated_changes": {
            "present": bool(pending_manifest), "manifest": pending_manifest,
            "changed_chapters": changed_chapters,
        },
        "current": {
            key: [{"ref": item["ref"], "title": item["title"], "record": item["record"]} for item in values]
            for key, values in relevant_current.items()
        },
        "future": {
            key: [{"ref": item["ref"], "title": item["title"], "record": item["record"]} for item in values]
            for key, values in relevant_future.items()
        },
        # 派生任务上下文：选中种子一跳内的显式关系事实（非 authority）。
        "explicit_relations": explicit_relations,
        # 任务近端实体的未来走向（规划派生，非 Canon；绝不覆盖 current）。
        "future_trajectories": task_trajectories,
        "chapter": None if chapter is None else {
            "chapter_number": chapter["chapter_number"],
            "title": chapter["title"],
            "actual_words": chapter["actual_words"],
            "fine_outline": copy.deepcopy(chapter.get("fine_outline") or {}),
            "actual_result": copy.deepcopy(chapter.get("actual_result")),
            "previous_actual_result": previous_result,
            "content": str(chapter.get("content") or "")[-2000:],
            "previous_content": previous_content,
        },
        "planning_impact_candidates": [
            item for item in snapshot.get("planning_impact_candidates", [])
            if item.get("status") == "pending_author"
        ][:10],
    }
