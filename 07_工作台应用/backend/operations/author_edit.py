# -*- coding: utf-8 -*-
"""Unified author edit/delta persistence for the Go Write 2.0 workbench.

All explicit Foundation/relationship/planning/prose edits enter this module so
that later semantic settlement and derived views share one traceable path.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import os
import re
import sys
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any, Callable

from operations import project_model
from operations import project_impact
from operations.project_snapshot import ProjectSnapshotError, get_project_snapshot

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PW = _REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"
if str(_PW) not in sys.path:
    sys.path.insert(0, str(_PW))

from project_workspace import (  # noqa: E402
    ContractError as PWContractError,
    WorkspaceError as PWWorkspaceError,
    load_project,
    resolve_project,
    validate_author_intent,
)


SCHEMA_VERSION = "gowrite_author_changes/v1"
ARTIFACT_NAME = "author_changes.json"
_CHAPTER_RE = re.compile(r"^第(\d+)章\.md$")


class AuthorEditError(Exception):
    """Safe, author-readable workbench edit failure."""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


# Per-project serializer for every author_changes.json / project-model mutation.
# Rapid author edits and background Direct AI settlement must never overwrite
# each other's ledger writes (no queue service; one reentrant lock per project).
_PROJECT_WRITE_LOCKS_GUARD = threading.Lock()
_PROJECT_WRITE_LOCKS: dict[str, threading.RLock] = {}


def project_write_lock(project_id: str) -> threading.RLock:
    with _PROJECT_WRITE_LOCKS_GUARD:
        lock = _PROJECT_WRITE_LOCKS.get(project_id)
        if lock is None:
            lock = threading.RLock()
            _PROJECT_WRITE_LOCKS[project_id] = lock
        return lock


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".gowrite-author-edit-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _load(project_id: str) -> tuple[dict[str, Any], Path, Path]:
    project_id = (project_id or "").strip()
    if not project_id:
        raise AuthorEditError("缺少 project_id。")
    try:
        project = resolve_project(project_id)
        loaded = load_project(project["project_dir"])
    except (PWContractError, PWWorkspaceError) as exc:
        raise AuthorEditError(str(exc)) from exc
    if loaded["project_id"] != project_id:
        raise AuthorEditError("作品身份不一致，已拒绝编辑。")
    project_dir = Path(loaded["project_dir"]).resolve()
    artifact = (project_dir / "_工作台状态" / ARTIFACT_NAME).resolve()
    if artifact.parent.parent != project_dir:
        raise AuthorEditError("作者变更记录路径 containment 校验失败。")
    return loaded, project_dir, artifact


def _read_changes(artifact: Path, project_id: str) -> dict[str, Any]:
    if not artifact.exists():
        return {"schema_version": SCHEMA_VERSION, "project_id": project_id, "sequence": 0, "changes": []}
    try:
        value = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthorEditError(f"作者变更记录读取失败：{exc}") from exc
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != SCHEMA_VERSION
        or value.get("project_id") != project_id
        or not isinstance(value.get("sequence"), int)
        or not isinstance(value.get("changes"), list)
    ):
        raise AuthorEditError("作者变更记录结构或 project_id 非法。")
    return value


def _default_state_refresh() -> dict[str, Any]:
    """Read-model lifecycle for the one explicit project-state refresh.

    This stays in the existing author-change ledger: it is not a second story
    state or a queue.  Older ledgers simply receive this deterministic default.
    """
    return {
        "status": "synchronized",
        "refresh_id": None,
        "cutoff_sequence": 0,
        "change_ids": [],
        "summary": None,
        "error": None,
        "awaiting_change_id": None,
        "proposals": [],
        "result": None,
    }


def get_change_ledger(project_id: str) -> dict[str, Any]:
    """Return the existing authoritative ledger for a read-only projection."""
    _loaded, _project_dir, artifact = _load(project_id)
    return copy.deepcopy(_read_changes(artifact, project_id))


def get_state_refresh(project_id: str) -> dict[str, Any]:
    ledger = get_change_ledger(project_id)
    stored = ledger.get("state_refresh")
    state = _default_state_refresh()
    if isinstance(stored, dict):
        state.update(copy.deepcopy(stored))
    return state


def get_state_refresh_read_model(project_id: str, *, worker_active: bool) -> dict[str, Any]:
    """Author-safe projection of the explicit project refresh lifecycle.

    The ledger remains the source of truth.  In particular, a persisted
    ``running`` value cannot masquerade as a live worker after an app restart.
    """
    ledger = get_change_ledger(project_id)
    stored = _default_state_refresh()
    if isinstance(ledger.get("state_refresh"), dict):
        stored.update(copy.deepcopy(ledger["state_refresh"]))
    pending = [
        item for item in ledger["changes"]
        if isinstance(item, dict)
        and item.get("requires_semantic")
        and item.get("status") in {"pending", "failed"}
    ]
    awaiting = [
        item for item in ledger["changes"]
        if isinstance(item, dict) and item.get("status") == "awaiting_author"
    ]
    status = str(stored.get("status") or "synchronized")
    error = stored.get("error")
    if status == "running" and not worker_active:
        status = "failed"
        error = "整理进程已停止；作者修改仍保留，可重试。"
    return {
        "status": status,
        "pending_change_count": len(pending),
        "awaiting_confirmation_count": (
            len(stored.get("proposals") or [])
            if status == "awaiting_confirmation"
            else len(awaiting)
        ),
        "refresh_id": stored.get("refresh_id"),
        "worker_active": bool(worker_active),
        "summary": stored.get("summary"),
        "error": error,
        "cutoff_sequence": stored.get("cutoff_sequence", 0),
        "consequences": [
            {
                "title": item.get("title"), "reason": item.get("reason"),
                "classification": item.get("classification"),
            }
            for item in (stored.get("proposals") or []) if isinstance(item, dict)
        ] if status == "awaiting_confirmation" else [],
    }


def update_changes_and_state_refresh(
    project_id: str,
    *,
    changes: dict[str, dict[str, Any]] | None = None,
    state_refresh: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Atomically update captured change entries and refresh lifecycle metadata."""
    with project_write_lock(project_id):
        _loaded, _project_dir, artifact = _load(project_id)
        ledger = _read_changes(artifact, project_id)
        by_id = {
            str(item.get("change_id")): item
            for item in ledger["changes"]
            if isinstance(item, dict) and isinstance(item.get("change_id"), str)
        }
        for change_id, patch in (changes or {}).items():
            item = by_id.get(change_id)
            if item is None:
                raise AuthorEditError("作者变更不存在或不属于当前作品。")
            item.update(copy.deepcopy(patch))
            item["updated_at"] = _now()
        if state_refresh is not None:
            value = _default_state_refresh()
            value.update(copy.deepcopy(state_refresh))
            ledger["state_refresh"] = value
        _atomic_write(artifact, _json_bytes(ledger))
        return copy.deepcopy(ledger)


def _append_change(
    artifact: Path,
    project_id: str,
    *,
    source_kind: str,
    status: str,
    delta: dict[str, Any],
    requires_semantic: bool,
    source_model_rev: int | None = None,
) -> dict[str, Any]:
    return _append_change_locked(
        artifact, project_id, source_kind=source_kind, status=status,
        delta=delta, requires_semantic=requires_semantic,
        source_model_rev=source_model_rev,
    )


def _append_change_locked(
    artifact: Path,
    project_id: str,
    *,
    source_kind: str,
    status: str,
    delta: dict[str, Any],
    requires_semantic: bool,
    source_model_rev: int | None = None,
) -> dict[str, Any]:
    with project_write_lock(project_id):
        return _append_change_inner(
            artifact, project_id, source_kind=source_kind, status=status,
            delta=delta, requires_semantic=requires_semantic,
            source_model_rev=source_model_rev,
        )


def _append_change_inner(
    artifact: Path,
    project_id: str,
    *,
    source_kind: str,
    status: str,
    delta: dict[str, Any],
    requires_semantic: bool,
    source_model_rev: int | None = None,
) -> dict[str, Any]:
    ledger = _read_changes(artifact, project_id)
    ledger["sequence"] += 1
    change_id = f"change-{ledger['sequence']:08d}-{uuid.uuid4().hex[:8]}"
    entry = {
        "change_id": change_id,
        "sequence": ledger["sequence"],
        "source_kind": source_kind,
        "status": status,
        "requires_semantic": bool(requires_semantic),
        "created_at": _now(),
        "updated_at": _now(),
        "source_model_rev": source_model_rev,
        "delta": copy.deepcopy(delta),
        "semantic": None,
        "error": None,
        "settlement_request_id": None,
        "settlement_started": False,
    }
    ledger["changes"].append(entry)
    _atomic_write(artifact, _json_bytes(ledger))
    return copy.deepcopy(entry)


def _restore(path: Path, snapshot: bytes | None) -> None:
    if snapshot is None:
        if path.exists():
            path.unlink()
    else:
        _atomic_write(path, snapshot)


def _model_artifact(project_dir: Path) -> Path:
    return project_dir / "_工作台状态" / project_model.ARTIFACT_NAME


def _snapshot_record(snapshot: dict[str, Any], ref: str, *, relationship: bool = False) -> dict[str, Any] | None:
    section_names = ("relationships",) if relationship else (
        "characters", "settings", "events", "open_threads", "foreshadowing", "storylines",
    )
    for bucket_name in ("current", "future"):
        for section in section_names:
            for item in snapshot[bucket_name].get(section, []):
                if item.get("ref") == ref:
                    return item
    return None


def _overlay_data(source: dict[str, Any], supplied: dict[str, Any] | None) -> dict[str, Any]:
    value = copy.deepcopy(supplied if supplied is not None else source.get("record") or {})
    if not isinstance(value, dict):
        value = {}
    for key in (
        "id", "authority", "source", "target", "source_name", "target_name", "relationship",
        "source_ref", "source_kind", "material_state", "name",
    ):
        value.pop(key, None)
    value["supersedes_state_ref"] = source["ref"]
    return value


def _ensure_model_character(
    project_id: str,
    model: dict[str, Any],
    snapshot: dict[str, Any],
    ref: str,
) -> tuple[dict[str, Any], str]:
    item = model.get("objects", {}).get(ref)
    if isinstance(item, dict) and not item.get("tombstoned"):
        if item.get("kind") == "foundation" and item.get("category") == "character":
            return model, ref
        raise AuthorEditError("关系端点必须是人物记录。")
    source = _snapshot_record(snapshot, ref)
    if not source or source.get("category") != "character":
        raise AuthorEditError("关系端点无法对应到明确人物记录。")
    data = _overlay_data(source, source.get("record") if isinstance(source.get("record"), dict) else {})
    data["source_state_ref"] = ref
    next_model = project_model.create_foundation_record(
        project_id, base_model_rev=model["model_rev"], category="character",
        title=source.get("title") or "未命名人物",
        material_state=source.get("material_state") or "current", data=data,
    )
    created_ref = next_model["change_history"][-1]["detail"]["ref"]
    return next_model, created_ref


def _legacy_relationship_endpoints(snapshot: dict[str, Any], relation: dict[str, Any]) -> tuple[str, str]:
    aliases: dict[str, set[str]] = {}
    for bucket_name in ("current", "future"):
        for character in snapshot[bucket_name].get("characters", []):
            ref = character.get("ref")
            if not isinstance(ref, str) or not ref:
                continue
            record = character.get("record") if isinstance(character.get("record"), dict) else {}
            for value in (ref, character.get("id"), character.get("title"), record.get("id"), record.get("name"), record.get("label")):
                if isinstance(value, str) and value.strip():
                    aliases.setdefault(value.strip(), set()).add(ref)

    record = relation.get("record") if isinstance(relation.get("record"), dict) else {}
    raw: list[Any] | None = None
    for key in ("targets", "characters", "between", "participants"):
        if isinstance(record.get(key), list):
            raw = record[key]
            break
    if raw is None:
        for left, right in (("source", "target"), ("from", "to")):
            if left in record or right in record:
                raw = [record.get(left), record.get(right)]
                break
    if raw is None or len(raw) != 2:
        raise AuthorEditError("旧关系没有可精确解析的两个端点，不能安全编辑。")

    resolved: list[str] = []
    for value in raw:
        if isinstance(value, dict):
            value = next((value.get(key) for key in ("id", "name", "label") if isinstance(value.get(key), str)), None)
        if not isinstance(value, str) or len(aliases.get(value.strip(), set())) != 1:
            raise AuthorEditError("旧关系端点无法唯一对应人物，不能安全编辑。")
        resolved.append(next(iter(aliases[value.strip()])))
    if resolved[0] == resolved[1]:
        raise AuthorEditError("关系两端不能指向同一人物。")
    return resolved[0], resolved[1]


def _perform_model_change(
    project_id: str,
    source_kind: str,
    action: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    with project_write_lock(project_id):
        return _perform_model_change_locked(project_id, source_kind, action)


def _perform_model_change_locked(
    project_id: str,
    source_kind: str,
    action: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    _loaded, project_dir, changes_path = _load(project_id)
    model_path = _model_artifact(project_dir)
    model_before = model_path.read_bytes() if model_path.exists() else None
    changes_before = changes_path.read_bytes() if changes_path.exists() else None
    try:
        model = action()
        history = model.get("change_history") or []
        detail = copy.deepcopy(history[-1]) if history else {}
        direct_impact = project_impact.build_direct_impact_report(
            project_id, int(model.get("model_rev") or 0),
        )
        requires_semantic = _model_change_requires_semantic(source_kind, model, detail)
        change = _append_change(
            changes_path, project_id, source_kind=source_kind,
            status="pending" if requires_semantic else "synchronized",
            delta={"project_model_change": detail, "direct_impact": direct_impact},
            requires_semantic=requires_semantic,
            source_model_rev=model.get("model_rev"),
        )
        return {"model": model, "change": change}
    except (
        project_model.ProjectModelError,
        project_impact.ProjectImpactError,
        OSError,
        AuthorEditError,
    ) as exc:
        try:
            _restore(model_path, model_before)
            _restore(changes_path, changes_before)
        except OSError as rollback_exc:
            raise AuthorEditError(f"编辑失败且回滚未完成，需要人工检查：{rollback_exc}") from exc
        raise AuthorEditError(str(exc)) from exc


_DISPLAY_ONLY_DATA_FIELDS = {"display_order", "display_group", "collapsed", "color", "avatar_seed"}
_MECHANICAL_OUTLINE_FIELDS = {
    "chapter_number", "chapter_title", "min_words", "max_words", "actual_words",
}


def _changed_data_keys(change: dict[str, Any]) -> set[str]:
    data_change = (change.get("changes") or {}).get("data")
    if not isinstance(data_change, dict):
        return set()
    before = data_change.get("before") if isinstance(data_change.get("before"), dict) else {}
    after = data_change.get("after") if isinstance(data_change.get("after"), dict) else {}
    return {key for key in set(before) | set(after) if before.get(key) != after.get(key)}


def _model_change_requires_semantic(
    source_kind: str,
    model: dict[str, Any],
    detail: dict[str, Any],
) -> bool:
    """Conservative boundary: only proven display/mechanical edits skip AI."""
    if source_kind in {"profile_edit", "foundation_restore", "relationship_restore"}:
        return False
    if source_kind == "domain_relation_edit":
        # 显式领域关系是作者维护的结构化记录；写入立即持久并进入 pending，
        # 但绝不在这里自动运行语义 AI。
        return True
    history_detail = detail.get("detail") if isinstance(detail.get("detail"), dict) else {}
    if source_kind in {"relationship_edit", "system_edit"}:
        changes = history_detail.get("changes") if isinstance(history_detail.get("changes"), dict) else {}
        if changes and set(changes) == {"data"} and _changed_data_keys(history_detail) <= _DISPLAY_ONLY_DATA_FIELDS:
            return False
        return True
    if source_kind == "foundation_edit":
        ref = history_detail.get("ref")
        item = model.get("objects", {}).get(ref) if isinstance(ref, str) else None
        category = item.get("category") if isinstance(item, dict) else None
        if category not in {
            "character", "world_setting", "location", "organization_force", "story_line",
            "promise_foreshadowing", "event", "mystery_information",
        }:
            return False
        changes = history_detail.get("changes") if isinstance(history_detail.get("changes"), dict) else {}
        if changes and set(changes) == {"data"} and _changed_data_keys(history_detail) <= _DISPLAY_ONLY_DATA_FIELDS:
            return False
        return True
    if source_kind == "planning_edit":
        changed = history_detail.get("changed") if isinstance(history_detail.get("changed"), dict) else {}
        for group, mechanical_fields in (
            ("stages", {"target_words", "display_order"}),
            ("chapter_targets", _MECHANICAL_OUTLINE_FIELDS),
        ):
            object_changes = (changed.get(group) or {}).get("objects", [])
            for item in object_changes if isinstance(object_changes, list) else []:
                if item.get("action") in {"created", "tombstoned"}:
                    return True
                if "title" in (item.get("changes") or {}):
                    return True
                if _changed_data_keys(item) - mechanical_fields:
                    return True
        return False
    return False


def create_foundation_record(
    project_id: str,
    *,
    base_model_rev: int,
    category: str,
    title: str,
    material_state: str,
    data: dict[str, Any] | None = None,
    category_name: str | None = None,
    relations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if category == "system":
        if relations is not None:
            raise AuthorEditError("体系记录不是领域关系起点，无法携带关联选择。")
        return _perform_model_change(
            project_id,
            "system_edit",
            lambda: project_model.create_system(
                project_id, base_model_rev=base_model_rev, title=title,
                material_state=material_state, definition=data or {},
            ),
        )
    return _perform_model_change(
        project_id,
        "foundation_edit",
        lambda: project_model.create_foundation_record(
            project_id, base_model_rev=base_model_rev, category=category, title=title,
            material_state=material_state, data=data, category_name=category_name,
            relations=relations,
        ),
    )


def set_story_bible_profile(
    project_id: str,
    *,
    base_model_rev: int,
    genre_tags: list[str],
    narrative_mode: str | None,
    active_modules: list[str],
    field_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _perform_model_change(
        project_id,
        "profile_edit",
        lambda: project_model.set_story_bible_profile(
            project_id, base_model_rev=base_model_rev, genre_tags=genre_tags,
            narrative_mode=narrative_mode, active_modules=active_modules,
            field_config=field_config,
        ),
    )


def update_foundation_record(
    project_id: str,
    *,
    base_model_rev: int,
    ref: str,
    title: str | None = None,
    material_state: str | None = None,
    data: dict[str, Any] | None = None,
    relations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    try:
        initial = project_model.load_project_model(project_id)
    except project_model.ProjectModelError as exc:
        raise AuthorEditError(str(exc)) from exc
    initial_item = initial.get("objects", {}).get(ref)
    source_kind = "system_edit" if isinstance(initial_item, dict) and initial_item.get("kind") == "system" else "foundation_edit"
    if relations is not None and source_kind == "system_edit":
        raise AuthorEditError("体系记录不是领域关系起点，无法携带关联选择。")

    def action() -> dict[str, Any]:
        model = project_model.load_project_model(project_id)
        if model["model_rev"] != base_model_rev:
            raise AuthorEditError("模型版本已变化，已拒绝 stale 写入。")
        item = model.get("objects", {}).get(ref)
        if isinstance(item, dict) and not item.get("tombstoned"):
            return project_model.update_object(
                project_id, base_model_rev=model["model_rev"], ref=ref, title=title,
                material_state=material_state, data=data, relations=relations,
            )
        snapshot = get_project_snapshot(project_id)
        source = _snapshot_record(snapshot, ref)
        if not source or source.get("source_kind") != "production_story_state":
            raise AuthorEditError("未知或跨项目记录 ref，已拒绝。")
        category = source.get("category")
        if not isinstance(category, str) or category == "relationship":
            raise AuthorEditError("这条记录必须使用关系编辑入口。")
        return project_model.create_foundation_record(
            project_id, base_model_rev=model["model_rev"], category=category,
            title=(title or source.get("title") or "未命名记录"),
            material_state=(material_state or source.get("material_state") or "current"),
            data=_overlay_data(source, data),
            relations=relations,
        )

    return _perform_model_change(
        project_id,
        source_kind,
        action,
    )


def retire_foundation_record(project_id: str, *, base_model_rev: int, ref: str) -> dict[str, Any]:
    try:
        initial = project_model.load_project_model(project_id)
    except project_model.ProjectModelError as exc:
        raise AuthorEditError(str(exc)) from exc
    initial_item = initial.get("objects", {}).get(ref)
    source_kind = "system_edit" if isinstance(initial_item, dict) and initial_item.get("kind") == "system" else "foundation_edit"

    def action() -> dict[str, Any]:
        model = project_model.load_project_model(project_id)
        if model["model_rev"] != base_model_rev:
            raise AuthorEditError("模型版本已变化，已拒绝 stale 写入。")
        item = model.get("objects", {}).get(ref)
        if isinstance(item, dict) and not item.get("tombstoned"):
            return project_model.tombstone_object(
                project_id, base_model_rev=model["model_rev"], ref=ref,
            )
        snapshot = get_project_snapshot(project_id)
        source = _snapshot_record(snapshot, ref)
        if not source or source.get("source_kind") != "production_story_state":
            raise AuthorEditError("未知或跨项目记录 ref，已拒绝。")
        category = source.get("category")
        if not isinstance(category, str) or category == "relationship":
            raise AuthorEditError("这条记录必须使用关系编辑入口。")
        model = project_model.create_foundation_record(
            project_id, base_model_rev=model["model_rev"], category=category,
            title=source.get("title") or "已退役记录",
            material_state=source.get("material_state") or "current",
            data=_overlay_data(source, source.get("record") if isinstance(source.get("record"), dict) else {}),
        )
        marker_ref = model["change_history"][-1]["detail"]["ref"]
        return project_model.tombstone_object(
            project_id, base_model_rev=model["model_rev"], ref=marker_ref,
        )

    return _perform_model_change(
        project_id,
        source_kind,
        action,
    )


def create_relationship(
    project_id: str,
    *,
    base_model_rev: int,
    source_ref: str,
    target_ref: str,
    label: str,
    material_state: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def action() -> dict[str, Any]:
        model = project_model.load_project_model(project_id)
        snapshot = get_project_snapshot(project_id)
        model, explicit_source = _ensure_model_character(project_id, model, snapshot, source_ref)
        model, explicit_target = _ensure_model_character(project_id, model, snapshot, target_ref)
        return project_model.create_relationship(
            project_id, base_model_rev=model["model_rev"], source_ref=explicit_source,
            target_ref=explicit_target, label=label, material_state=material_state, data=data,
        )

    return _perform_model_change(
        project_id,
        "relationship_edit",
        lambda: action() if project_model.read_project_model(project_id)["model_rev"] == base_model_rev
        else (_ for _ in ()).throw(AuthorEditError("模型版本已变化，已拒绝 stale 写入。")),
    )


def update_relationship(
    project_id: str,
    *,
    base_model_rev: int,
    ref: str,
    source_ref: str | None = None,
    target_ref: str | None = None,
    label: str | None = None,
    material_state: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def action() -> dict[str, Any]:
        model = project_model.load_project_model(project_id)
        if model["model_rev"] != base_model_rev:
            raise AuthorEditError("模型版本已变化，已拒绝 stale 写入。")
        snapshot = get_project_snapshot(project_id)
        existing = model.get("dependencies", {}).get(ref)
        legacy = None
        next_source_ref = source_ref
        next_target_ref = target_ref
        if not isinstance(existing, dict) or existing.get("tombstoned"):
            legacy = _snapshot_record(snapshot, ref, relationship=True)
            if not legacy or legacy.get("source_kind") != "production_story_state":
                raise AuthorEditError("未知或跨项目关系 ref，已拒绝。")
            legacy_source, legacy_target = _legacy_relationship_endpoints(snapshot, legacy)
            next_source_ref = next_source_ref or legacy_source
            next_target_ref = next_target_ref or legacy_target

        explicit_source = None
        explicit_target = None
        if next_source_ref is not None:
            model, explicit_source = _ensure_model_character(project_id, model, snapshot, next_source_ref)
        if next_target_ref is not None:
            model, explicit_target = _ensure_model_character(project_id, model, snapshot, next_target_ref)
        if legacy is not None:
            relation_data = _overlay_data(legacy, data)
            return project_model.create_relationship(
                project_id, base_model_rev=model["model_rev"],
                source_ref=explicit_source or "", target_ref=explicit_target or "",
                label=label or legacy.get("title") or "未命名关系",
                material_state=material_state or legacy.get("material_state") or "current",
                data=relation_data,
            )
        return project_model.update_dependency(
            project_id, base_model_rev=model["model_rev"], ref=ref, source_ref=explicit_source,
            target_ref=explicit_target, title=label, material_state=material_state, data=data,
        )

    return _perform_model_change(
        project_id,
        "relationship_edit",
        action,
    )


def retire_relationship(project_id: str, *, base_model_rev: int, ref: str) -> dict[str, Any]:
    def action() -> dict[str, Any]:
        model = project_model.load_project_model(project_id)
        if model["model_rev"] != base_model_rev:
            raise AuthorEditError("模型版本已变化，已拒绝 stale 写入。")
        edge = model.get("dependencies", {}).get(ref)
        if isinstance(edge, dict) and not edge.get("tombstoned"):
            return project_model.tombstone_dependency(
                project_id, base_model_rev=model["model_rev"], ref=ref,
            )
        snapshot = get_project_snapshot(project_id)
        legacy = _snapshot_record(snapshot, ref, relationship=True)
        if not legacy or legacy.get("source_kind") != "production_story_state":
            raise AuthorEditError("未知或跨项目关系 ref，已拒绝。")
        source_ref, target_ref = _legacy_relationship_endpoints(snapshot, legacy)
        model, source_ref = _ensure_model_character(project_id, model, snapshot, source_ref)
        model, target_ref = _ensure_model_character(project_id, model, snapshot, target_ref)
        model = project_model.create_relationship(
            project_id, base_model_rev=model["model_rev"], source_ref=source_ref,
            target_ref=target_ref, label=legacy.get("title") or "已退役关系",
            material_state=legacy.get("material_state") or "current",
            data=_overlay_data(legacy, legacy.get("record") if isinstance(legacy.get("record"), dict) else {}),
        )
        marker_ref = model["change_history"][-1]["detail"]["ref"]
        return project_model.tombstone_dependency(
            project_id, base_model_rev=model["model_rev"], ref=marker_ref,
        )

    return _perform_model_change(
        project_id,
        "relationship_edit",
        action,
    )


def create_domain_dependency(
    project_id: str,
    *,
    base_model_rev: int,
    source_ref: str,
    target_ref: str,
    relation_kind: str,
    material_state: str = "current",
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """窄口径作者变更：新增一条经中央规格校验的领域关系。

    仅供 FoundationDesign 等已确认的高层操作使用；写后立即 durable 并进入
    pending 语义刷新，绝不自动运行 AI/Agent；不新增第二本作者账本。
    """
    def action() -> dict[str, Any]:
        model = project_model.load_project_model(project_id)
        if model["model_rev"] != base_model_rev:
            raise AuthorEditError("模型版本已变化，已拒绝 stale 写入。")
        return project_model.add_domain_dependency(
            project_id, base_model_rev=model["model_rev"], source_ref=source_ref,
            target_ref=target_ref, relation_kind=relation_kind,
            material_state=material_state, data=data,
        )

    return _perform_model_change(project_id, "domain_relation_edit", action)


def restore_foundation_record(project_id: str, *, base_model_rev: int, ref: str) -> dict[str, Any]:
    """Deterministically restore the same retired foundation/system ref."""
    def action() -> dict[str, Any]:
        model = project_model.load_project_model(project_id)
        if model["model_rev"] != base_model_rev:
            raise AuthorEditError("模型版本已变化，已拒绝 stale 写入。")
        item = model.get("objects", {}).get(ref)
        if not isinstance(item, dict):
            raise AuthorEditError("未知或跨项目记录 ref，已拒绝。")
        if item.get("kind") not in {"foundation", "system"}:
            raise AuthorEditError("该 ref 不是可恢复的地基记录。")
        if not item.get("tombstoned"):
            raise AuthorEditError("该记录已处于活动状态，无需恢复。")
        return project_model.restore_object(
            project_id, base_model_rev=model["model_rev"], ref=ref,
        )

    return _perform_model_change(project_id, "foundation_restore", action)


def restore_relationship(project_id: str, *, base_model_rev: int, ref: str) -> dict[str, Any]:
    """Deterministically restore the same retired relationship ref."""
    def action() -> dict[str, Any]:
        model = project_model.load_project_model(project_id)
        if model["model_rev"] != base_model_rev:
            raise AuthorEditError("模型版本已变化，已拒绝 stale 写入。")
        edge = model.get("dependencies", {}).get(ref)
        if not isinstance(edge, dict):
            raise AuthorEditError("未知或跨项目关系 ref，已拒绝。")
        if not edge.get("tombstoned"):
            raise AuthorEditError("该关系已处于活动状态，无需恢复。")
        return project_model.restore_dependency(
            project_id, base_model_rev=model["model_rev"], ref=ref,
        )

    return _perform_model_change(project_id, "relationship_restore", action)


def set_length_plan(
    project_id: str,
    *,
    base_model_rev: int,
    total_target_words: int | None,
    stages: list[dict[str, Any]] | None,
    chapter_targets: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    return _perform_model_change(
        project_id,
        "planning_edit",
        lambda: project_model.set_length_plan(
            project_id, base_model_rev=base_model_rev, total_target_words=total_target_words,
            stages=stages, chapter_targets=chapter_targets,
        ),
    )


def update_story_synopsis(
    project_id: str,
    *,
    base_intent_rev: int,
    story_synopsis: str,
) -> dict[str, Any]:
    """Edit the optional durable work synopsis in Author Intent only.

    This is a narrow Author Intent operation, not a schema editor.  It records a
    deterministic author-change ledger entry and never starts semantic work.
    """
    if not isinstance(base_intent_rev, int) or isinstance(base_intent_rev, bool) or base_intent_rev < 1:
        raise AuthorEditError("base_intent_rev 必须是正整数。")
    if not isinstance(story_synopsis, str):
        raise AuthorEditError("story_synopsis 必须是字符串。")
    with project_write_lock(project_id):
        loaded, project_dir, changes_path = _load(project_id)
        intent_path = (project_dir / "_工作台状态" / "author_intent.json").resolve()
        if intent_path.parent.parent != project_dir:
            raise AuthorEditError("Author Intent 路径 containment 校验失败。")
        intent_before = intent_path.read_bytes()
        changes_before = changes_path.read_bytes() if changes_path.exists() else None
        intent = copy.deepcopy(loaded["intent"])
        if int(intent.get("intent_rev") or 0) != base_intent_rev:
            raise AuthorEditError(
                f"作者意图版本已变化（当前 {intent.get('intent_rev')}，提交基线 {base_intent_rev}），已拒绝 stale 写入。"
            )
        before_synopsis = intent.get("story_synopsis") or ""
        intent["story_synopsis"] = story_synopsis
        intent["intent_rev"] = base_intent_rev + 1
        try:
            validate_author_intent(intent)
            _atomic_write(intent_path, _json_bytes(intent))
            change = _append_change(
                changes_path, project_id, source_kind="author_intent_edit",
                status="synchronized",
                delta={
                    "author_intent_change": {
                        "field": "story_synopsis",
                        "before": before_synopsis,
                        "after": story_synopsis,
                        "base_intent_rev": base_intent_rev,
                        "intent_rev": intent["intent_rev"],
                    }
                },
                requires_semantic=False,
                source_model_rev=None,
            )
        except Exception as exc:  # noqa: BLE001
            try:
                _restore(intent_path, intent_before)
                _restore(changes_path, changes_before)
            except OSError as rollback_exc:
                raise AuthorEditError(f"简介保存失败且回滚未完成，需要人工检查：{rollback_exc}") from exc
            raise AuthorEditError(str(exc)) from exc
        return {
            "project_id": project_id,
            "intent_rev": intent["intent_rev"],
            "story_synopsis": story_synopsis,
            "change": change,
        }


def _chapter_path(project_dir: Path, chapter_number: int) -> Path:
    if not isinstance(chapter_number, int) or isinstance(chapter_number, bool) or chapter_number < 1:
        raise AuthorEditError("chapter_number 必须是正整数。")
    prose_root = (project_dir / "03_正文").resolve()
    path = (prose_root / f"第{chapter_number:03d}章.md").resolve()
    if path.parent != prose_root:
        raise AuthorEditError("章节路径 containment 校验失败。")
    return path


def create_chapter(project_id: str, *, chapter_number: int) -> dict[str, Any]:
    with project_write_lock(project_id):
        return _create_chapter_locked(project_id, chapter_number=chapter_number)


def _create_chapter_locked(project_id: str, *, chapter_number: int) -> dict[str, Any]:
    _loaded, project_dir, changes_path = _load(project_id)
    chapter = _chapter_path(project_dir, chapter_number)
    if chapter.exists():
        raise AuthorEditError(f"第{chapter_number}章已经存在。")
    changes_before = changes_path.read_bytes() if changes_path.exists() else None
    try:
        _atomic_write(chapter, b"")
        change = _append_change(
            changes_path, project_id, source_kind="chapter_created", status="synchronized",
            delta={"chapter_number": chapter_number, "chapter_path": f"03_正文/{chapter.name}"},
            requires_semantic=False,
        )
    except (OSError, AuthorEditError) as exc:
        try:
            _restore(chapter, None)
            _restore(changes_path, changes_before)
        except OSError as rollback_exc:
            raise AuthorEditError(f"新建章节失败且回滚未完成：{rollback_exc}") from exc
        raise AuthorEditError(f"新建章节失败：{exc}") from exc
    return {"project_id": project_id, "chapter_number": chapter_number, "change": change}


def save_formal_prose(
    project_id: str,
    *,
    chapter_number: int,
    base_content_sha256: str,
    content: str,
) -> dict[str, Any]:
    """Explicit save with stale guard, atomic chapter/index/change ledger update."""
    with project_write_lock(project_id):
        return _save_formal_prose_locked(
            project_id, chapter_number=chapter_number,
            base_content_sha256=base_content_sha256, content=content,
        )


def _save_formal_prose_locked(
    project_id: str,
    *,
    chapter_number: int,
    base_content_sha256: str,
    content: str,
) -> dict[str, Any]:
    if not isinstance(content, str):
        raise AuthorEditError("正文 content 必须是字符串。")
    if not isinstance(base_content_sha256, str) or len(base_content_sha256) != 64:
        raise AuthorEditError("缺少合法的正文基线哈希。")
    loaded, project_dir, changes_path = _load(project_id)
    chapter = _chapter_path(project_dir, chapter_number)
    if not chapter.exists():
        raise AuthorEditError("章节不存在，请先新建章节。")
    before_text = chapter.read_text(encoding="utf-8")
    before_hash = hashlib.sha256(before_text.encode("utf-8")).hexdigest()
    if before_hash != base_content_sha256:
        raise AuthorEditError("正文已被其他操作修改，已拒绝 stale 保存；请刷新后重试。")
    if content == before_text:
        raise AuthorEditError("正文没有实际变化。")

    state_dir = project_dir / "_工作台状态"
    index_path = state_dir / "accepted_text_index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthorEditError(f"accepted_text_index 读取失败：{exc}") from exc
    if index.get("project_id") != project_id or not isinstance(index.get("entries"), list):
        raise AuthorEditError("accepted_text_index 结构或 project_id 非法。")

    chapter_before = chapter.read_bytes()
    index_before = index_path.read_bytes()
    changes_before = changes_path.read_bytes() if changes_path.exists() else None
    revision_ref = f"author-edit-{uuid.uuid4().hex[:16]}"
    active_entries = copy.deepcopy(index["entries"])
    retired = [item for item in active_entries if item.get("chapter_number") == chapter_number]
    retained = [item for item in active_entries if item.get("chapter_number") != chapter_number]
    historical = index.get("superseded_entries")
    if historical is None:
        historical = []
    if not isinstance(historical, list):
        raise AuthorEditError("accepted_text_index.superseded_entries 结构非法。")
    for item in retired:
        item["superseded_by"] = revision_ref
        item["superseded_at"] = _now()
        historical.append(item)
    all_sequences = [
        item.get("sequence", 0) for item in [*active_entries, *historical]
        if isinstance(item, dict) and isinstance(item.get("sequence", 0), int)
    ]
    if content:
        retained.append({
            "sequence": max(all_sequences or [0]) + 1,
            "scene_ref": revision_ref,
            "chapter_number": chapter_number,
            "chapter_path": f"03_正文/{chapter.name}",
            "start_char": 0,
            "end_char": len(content),
            "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "state_rev_after": loaded["state"].get("state_rev"),
            "revision_kind": "author_edited_chapter",
            "supersedes_scene_refs": [item.get("scene_ref") for item in retired if item.get("scene_ref")],
        })
    retained.sort(key=lambda item: int(item.get("sequence") or 0))
    new_index = copy.deepcopy(index)
    new_index["entries"] = retained
    new_index["superseded_entries"] = historical
    delta = {
        "chapter_number": chapter_number,
        "chapter_path": f"03_正文/{chapter.name}",
        "before_sha256": before_hash,
        "after_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "before_words": len(before_text),
        "after_words": len(content),
        "changed_text": content,
        "superseded_scene_refs": [item.get("scene_ref") for item in retired if item.get("scene_ref")],
        "revision_ref": revision_ref,
    }
    try:
        _atomic_write(chapter, content.encode("utf-8"))
        _atomic_write(index_path, _json_bytes(new_index))
        change = _append_change(
            changes_path, project_id, source_kind="manual_prose_edit", status="pending",
            delta=delta, requires_semantic=True,
        )
    except (OSError, AuthorEditError) as exc:
        try:
            _restore(chapter, chapter_before)
            _restore(index_path, index_before)
            _restore(changes_path, changes_before)
        except OSError as rollback_exc:
            raise AuthorEditError(f"正文保存失败且回滚未完成，需要人工检查：{rollback_exc}") from exc
        raise AuthorEditError(f"正文保存失败，已回滚：{exc}") from exc
    return {
        "project_id": project_id,
        "chapter_number": chapter_number,
        "content_sha256": delta["after_sha256"],
        "actual_words": len(content),
        "change": change,
        "message": "正文已安全保存；语义同步待执行。",
    }


def record_accepted_ai_prose(
    project_id: str,
    *,
    chapter_number: int,
    scene_ref: str,
    settlement: dict[str, Any],
    content_sha256: str | None = None,
) -> dict[str, Any]:
    """Record durable StoryWrite acceptance as pending author-triggered work."""
    with project_write_lock(project_id):
        _loaded, _project_dir, changes_path = _load(project_id)
        return _append_change(
            changes_path, project_id, source_kind="accepted_ai_prose",
            status="pending",
            delta={
                "chapter_number": chapter_number, "scene_ref": scene_ref,
                "after_sha256": content_sha256,
            },
            requires_semantic=True,
        )


def get_change(project_id: str, change_id: str) -> dict[str, Any]:
    _loaded, _project_dir, artifact = _load(project_id)
    ledger = _read_changes(artifact, project_id)
    for item in ledger["changes"]:
        if isinstance(item, dict) and item.get("change_id") == change_id:
            return copy.deepcopy(item)
    raise AuthorEditError("作者变更不存在或不属于当前作品。")


def update_change(
    project_id: str,
    change_id: str,
    *,
    status: str,
    semantic: dict[str, Any] | None = None,
    error: str | None = None,
    settlement_request_id: str | None = None,
    settlement_started: bool | None = None,
) -> dict[str, Any]:
    if status not in {"pending", "failed", "awaiting_author", "synchronized", "canceled"}:
        raise AuthorEditError("作者变更状态非法。")
    with project_write_lock(project_id):
        return _update_change_locked(
            project_id, change_id, status=status, semantic=semantic, error=error,
            settlement_request_id=settlement_request_id, settlement_started=settlement_started,
        )


def _update_change_locked(
    project_id: str,
    change_id: str,
    *,
    status: str,
    semantic: dict[str, Any] | None = None,
    error: str | None = None,
    settlement_request_id: str | None = None,
    settlement_started: bool | None = None,
) -> dict[str, Any]:
    _loaded, _project_dir, artifact = _load(project_id)
    ledger = _read_changes(artifact, project_id)
    matched = None
    for item in ledger["changes"]:
        if isinstance(item, dict) and item.get("change_id") == change_id:
            matched = item
            break
    if matched is None:
        raise AuthorEditError("作者变更不存在或不属于当前作品。")
    matched["status"] = status
    matched["semantic"] = copy.deepcopy(semantic)
    matched["error"] = error
    if settlement_request_id is not None:
        matched["settlement_request_id"] = settlement_request_id
    if settlement_started is not None:
        matched["settlement_started"] = bool(settlement_started)
    matched["updated_at"] = _now()
    _atomic_write(artifact, _json_bytes(ledger))
    return copy.deepcopy(matched)


def get_author_edit_surface(project_id: str) -> dict[str, Any]:
    try:
        snapshot = get_project_snapshot(project_id)
    except ProjectSnapshotError as exc:
        raise AuthorEditError(str(exc)) from exc
    return snapshot
