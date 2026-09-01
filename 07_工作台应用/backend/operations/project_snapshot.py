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


def _explicit_dependencies(model: dict[str, Any]) -> list[dict[str, Any]]:
    """活动显式依赖的只读投影；不含 tombstoned 边，不改写任何源记录。"""
    objects = model.get("objects", {})
    result: list[dict[str, Any]] = []
    for edge in model.get("dependencies", {}).values():
        if not isinstance(edge, dict) or edge.get("tombstoned"):
            continue
        if edge.get("relation_kind") not in _VISIBLE_RELATION_KINDS:
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
        bucket = current if item.get("material_state") == "current" else future
        bucket[section].append(_model_record(item))
    for item in model.get("objects", {}).values():
        if not isinstance(item, dict) or item.get("tombstoned") or item.get("kind") != "system":
            continue
        bucket = current if item.get("material_state") == "current" else future
        bucket["systems"].append(_model_record(item))
    for edge in model.get("dependencies", {}).values():
        if not isinstance(edge, dict) or edge.get("tombstoned") or edge.get("relation_kind") != "character_relationship":
            continue
        bucket = current if edge.get("material_state", "current") == "current" else future
        bucket["relationships"].append(_relationship_record(edge, model["objects"]))

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
        "explicit_dependencies": _explicit_dependencies(model),
        "planning_impact_candidates": copy.deepcopy(model.get("planning_impact_candidates", [])),
        "legacy_diagnostics": {
            "unresolved_character_observations": unresolved_character_observations,
        },
        "settlement": _settlement_summary(project_dir),
    }


def _task_relevant_records(
    snapshot: dict[str, Any],
    chapter: dict[str, Any] | None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """Select only explicit task-near refs/names; never fallback to full state."""
    tokens: set[str] = set()
    outline = (chapter or {}).get("fine_outline") if isinstance((chapter or {}).get("fine_outline"), dict) else {}
    for key in (
        "participating_characters", "new_characters", "character_refs", "relationship_refs",
        "location_ref", "location", "organization_refs", "system_refs", "storyline_ref",
        "storyline", "foreshadowing_refs", "open_thread_refs", "related_refs",
    ):
        value = outline.get(key)
        if isinstance(value, str) and value.strip():
            tokens.add(value.strip())
        elif isinstance(value, list):
            tokens.update(item.strip() for item in value if isinstance(item, str) and item.strip())

    def selected(bucket: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = {}
        for section, values in bucket.items():
            chosen = []
            for item in values:
                record = item.get("record") if isinstance(item.get("record"), dict) else {}
                global_rule = section in {"settings", "systems"} and (
                    record.get("context_scope") == "global" or bool(record.get("hard_rule"))
                )
                if item.get("ref") in tokens or item.get("title") in tokens or global_rule:
                    chosen.append(item)
                if len(chosen) >= 12:
                    break
            result[section] = chosen
        return result

    if chapter is None:
        # Planning sees bounded structured summaries, never an unbounded full dump.
        return (
            {key: values[:12] for key, values in snapshot["current"].items()},
            {key: values[:12] for key, values in snapshot["future"].items()},
        )
    return selected(snapshot["current"]), selected(snapshot["future"])


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
    relevant_current, relevant_future = _task_relevant_records(snapshot, chapter)
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
