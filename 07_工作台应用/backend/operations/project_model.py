# -*- coding: utf-8 -*-
"""Go Write 2.0 author-workspace project model.

This is an application-layer author-management artifact, deliberately separate
from production Story State and StoryPlan.  It records only explicit author
workspace data and direct dependencies; it neither infers facts nor writes
Canon, planning, prose, or any frozen runtime artifact.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

_PW = Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"
if str(_PW) not in sys.path:
    sys.path.insert(0, str(_PW))

from project_workspace import (  # noqa: E402 - frozen project resolution only
    ContractError as PWContractError,
    WorkspaceError as PWWorkspaceError,
    load_project,
    resolve_project,
)


SCHEMA_VERSION = "gowrite_project_model/v1"
ARTIFACT_NAME = "go_write_project_model.json"
_FOUNDATION_CATEGORIES = {
    "character",
    "relationship",
    "world_setting",
    "location",
    "organization_force",
    "story_line",
    "promise_foreshadowing",
    "event",
    "custom",
}
_MATERIAL_STATES = {"current", "future"}
_UNSET = object()


class ProjectModelError(Exception):
    """Safe failure for Go Write 2.0 project-model operations."""


def _require_project(project_id: str) -> dict[str, Any]:
    project_id = (project_id or "").strip()
    if not project_id:
        raise ProjectModelError("缺少 project_id。")
    try:
        project = resolve_project(project_id)
        loaded = load_project(project["project_dir"])
    except (PWContractError, PWWorkspaceError) as exc:
        raise ProjectModelError(str(exc)) from exc
    if loaded["project_id"] != project_id:
        raise ProjectModelError("项目解析后的 project_id 不一致，已拒绝。")
    return loaded


def _artifact_path(loaded: dict[str, Any]) -> Path:
    project_dir = Path(loaded["project_dir"]).resolve()
    state_dir = (project_dir / "_工作台状态").resolve()
    artifact = (state_dir / ARTIFACT_NAME).resolve()
    if artifact.parent != state_dir or state_dir.parent != project_dir:
        raise ProjectModelError("项目模型路径 containment 校验失败。")
    return artifact


def _initial_model(project_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": project_id,
        "model_rev": 0,
        "ref_sequence": 0,
        "objects": {},
        "dependencies": {},
        "length_plan": {
            "total_target_words": None,
            "stage_refs": [],
            "chapter_target_refs": [],
            "actual_word_counts": {},
        },
        "change_history": [],
    }


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".gowrite-project-model-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _validate_model(model: Any, project_id: str) -> dict[str, Any]:
    if not isinstance(model, dict):
        raise ProjectModelError("项目模型必须是 JSON 对象。")
    if model.get("schema_version") != SCHEMA_VERSION:
        raise ProjectModelError("项目模型 schema_version 不兼容。")
    if model.get("project_id") != project_id:
        raise ProjectModelError("项目模型 project_id 与当前项目不一致，已拒绝。")
    if not isinstance(model.get("model_rev"), int) or model["model_rev"] < 0:
        raise ProjectModelError("项目模型 model_rev 非法。")
    if not isinstance(model.get("ref_sequence"), int) or model["ref_sequence"] < 0:
        raise ProjectModelError("项目模型 ref_sequence 非法。")
    for key in ("objects", "dependencies"):
        if not isinstance(model.get(key), dict):
            raise ProjectModelError(f"项目模型 {key} 非法。")
    if not isinstance(model.get("length_plan"), dict) or not isinstance(model.get("change_history"), list):
        raise ProjectModelError("项目模型结构不完整。")
    scope = hashlib.sha256(project_id.encode("utf-8")).hexdigest()[:12]
    largest_sequence = 0
    for ref, item in model["objects"].items():
        if not isinstance(ref, str) or not ref.startswith(f"gw2_obj_{scope}_"):
            raise ProjectModelError("项目模型包含未知或跨项目对象 ref。")
        try:
            largest_sequence = max(largest_sequence, int(ref.rsplit("_", 1)[1], 16))
        except (IndexError, ValueError) as exc:
            raise ProjectModelError("项目模型对象 ref 格式非法。") from exc
        if not isinstance(item, dict) or item.get("ref") != ref or not isinstance(item.get("kind"), str):
            raise ProjectModelError("项目模型对象结构非法。")
        if item.get("material_state") not in _MATERIAL_STATES:
            raise ProjectModelError("项目模型对象 material_state 非法。")
    for ref, edge in model["dependencies"].items():
        if not isinstance(ref, str) or not ref.startswith(f"gw2_edge_{scope}_"):
            raise ProjectModelError("项目模型包含未知或跨项目依赖 ref。")
        try:
            largest_sequence = max(largest_sequence, int(ref.rsplit("_", 1)[1], 16))
        except (IndexError, ValueError) as exc:
            raise ProjectModelError("项目模型依赖 ref 格式非法。") from exc
        if not isinstance(edge, dict) or edge.get("ref") != ref:
            raise ProjectModelError("项目模型依赖结构非法。")
        if edge.get("source_ref") not in model["objects"] or edge.get("target_ref") not in model["objects"]:
            raise ProjectModelError("项目模型依赖指向未知或跨项目 ref。")
        if not edge.get("tombstoned") and (
            model["objects"][edge["source_ref"]].get("tombstoned")
            or model["objects"][edge["target_ref"]].get("tombstoned")
        ):
            raise ProjectModelError("活动依赖不能指向 tombstoned 对象。")
    plan = model["length_plan"]
    if not isinstance(plan.get("stage_refs"), list) or not isinstance(plan.get("chapter_target_refs"), list):
        raise ProjectModelError("项目模型长度规划 ref 列表非法。")
    if not isinstance(plan.get("actual_word_counts"), dict):
        raise ProjectModelError("项目模型 actual_word_counts 非法。")
    for ref in plan["stage_refs"]:
        if (
            ref not in model["objects"]
            or model["objects"][ref].get("kind") != "length_stage"
            or model["objects"][ref].get("tombstoned")
        ):
            raise ProjectModelError("项目模型阶段 ref 非法。")
    for ref in plan["chapter_target_refs"]:
        if (
            ref not in model["objects"]
            or model["objects"][ref].get("kind") != "chapter_target"
            or model["objects"][ref].get("tombstoned")
        ):
            raise ProjectModelError("项目模型章节目标 ref 非法。")
    for ref, count in plan["actual_word_counts"].items():
        if ref not in plan["chapter_target_refs"] or not isinstance(count, int) or count < 0:
            raise ProjectModelError("项目模型实际字数记录非法。")
    if model["ref_sequence"] < largest_sequence:
        raise ProjectModelError("项目模型 ref_sequence 落后于已有 ref，已拒绝潜在 ref 重用。")
    return model


def _load_or_initialize(project_id: str) -> tuple[dict[str, Any], Path]:
    loaded = _require_project(project_id)
    artifact = _artifact_path(loaded)
    if not artifact.exists():
        model = _initial_model(project_id)
        _atomic_write_json(artifact, model)
        return model, artifact
    try:
        model = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectModelError(f"项目模型读取失败：{exc}") from exc
    return _validate_model(model, project_id), artifact


def load_project_model(project_id: str) -> dict[str, Any]:
    """Load the isolated model, lazily creating a revision-0 artifact if absent."""
    model, _ = _load_or_initialize(project_id)
    return copy.deepcopy(model)


def read_project_model(project_id: str) -> dict[str, Any]:
    """Read the author model without creating an artifact.

    Snapshot/read-model consumers must stay read-only.  A project that has not
    received author-workspace edits therefore gets an in-memory revision-0
    model; the first real mutation still creates the artifact atomically.
    """
    loaded = _require_project(project_id)
    artifact = _artifact_path(loaded)
    if not artifact.exists():
        return _initial_model(project_id)
    try:
        model = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectModelError(f"项目模型读取失败：{exc}") from exc
    return copy.deepcopy(_validate_model(model, project_id))


def _next_ref(model: dict[str, Any], prefix: str) -> str:
    model["ref_sequence"] += 1
    # Project-scoped opaque identity prevents an independently allocated ref in
    # another project from ever resolving as a local object.
    scope = hashlib.sha256(model["project_id"].encode("utf-8")).hexdigest()[:12]
    return f"gw2_{prefix}_{scope}_{model['ref_sequence']:08x}"


def _require_base_rev(model: dict[str, Any], base_model_rev: int) -> None:
    if not isinstance(base_model_rev, int) or isinstance(base_model_rev, bool):
        raise ProjectModelError("base_model_rev 必须是整数。")
    if model["model_rev"] != base_model_rev:
        raise ProjectModelError(
            f"模型版本已变化（当前 {model['model_rev']}，提交基线 {base_model_rev}），已拒绝 stale 写入。"
        )


def _commit(
    project_id: str,
    base_model_rev: int,
    change_kind: str,
    mutate: Callable[[dict[str, Any], int], dict[str, Any]],
) -> dict[str, Any]:
    model, artifact = _load_or_initialize(project_id)
    _require_base_rev(model, base_model_rev)
    next_rev = model["model_rev"] + 1
    detail = mutate(model, next_rev)
    model["model_rev"] = next_rev
    model["change_history"].append({"model_rev": next_rev, "kind": change_kind, "detail": detail})
    _validate_model(model, project_id)
    _atomic_write_json(artifact, model)
    return copy.deepcopy(model)


def _validate_material_state(material_state: str) -> str:
    if material_state not in _MATERIAL_STATES:
        raise ProjectModelError("material_state 只能是 current 或 future。")
    return material_state


def _validate_data(data: dict[str, Any] | None) -> dict[str, Any]:
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ProjectModelError("data 必须是对象。")
    return copy.deepcopy(data)


def _active_object(model: dict[str, Any], ref: str, *, expected_kind: str | None = None) -> dict[str, Any]:
    item = model["objects"].get(ref)
    if not isinstance(item, dict):
        raise ProjectModelError("未知或跨项目 ref，已拒绝。")
    if item.get("tombstoned"):
        raise ProjectModelError("ref 已 tombstone，不能再作为活动对象使用。")
    if expected_kind and item.get("kind") != expected_kind:
        raise ProjectModelError("ref 类型不符合当前操作。")
    return item


def _tombstone_object_with_incident_edges(model: dict[str, Any], ref: str, next_rev: int) -> list[str]:
    """Retire one object and every active explicit edge incident to it."""
    item = _active_object(model, ref)
    item["tombstoned"] = True
    item["tombstoned_at_rev"] = next_rev
    retired_edges: list[str] = []
    for edge_ref, edge in model["dependencies"].items():
        if not edge.get("tombstoned") and (edge["source_ref"] == ref or edge["target_ref"] == ref):
            edge["tombstoned"] = True
            edge["tombstoned_at_rev"] = next_rev
            retired_edges.append(edge_ref)
    return retired_edges


def create_foundation_record(
    project_id: str,
    *,
    base_model_rev: int,
    category: str,
    title: str,
    material_state: str = "current",
    data: dict[str, Any] | None = None,
    category_name: str | None = None,
) -> dict[str, Any]:
    """Create an explicit author workspace record without creating Canon."""
    if category not in _FOUNDATION_CATEGORIES:
        raise ProjectModelError("不支持的基础记录分类；自定义分类请使用 custom。")
    if not isinstance(title, str) or not title.strip():
        raise ProjectModelError("基础记录 title 不能为空。")
    if category == "custom" and (not isinstance(category_name, str) or not category_name.strip()):
        raise ProjectModelError("custom 基础记录必须提供 category_name。")
    material_state = _validate_material_state(material_state)
    record_data = _validate_data(data)

    def mutate(model: dict[str, Any], _next_rev: int) -> dict[str, Any]:
        ref = _next_ref(model, "obj")
        model["objects"][ref] = {
            "ref": ref,
            "kind": "foundation",
            "category": category,
            "category_name": category_name.strip() if isinstance(category_name, str) else None,
            "title": title.strip(),
            "material_state": material_state,
            "data": record_data,
            "tombstoned": False,
        }
        return {"ref": ref, "action": "created", "kind": "foundation"}

    return _commit(project_id, base_model_rev, "foundation.created", mutate)


def update_object(
    project_id: str,
    *,
    base_model_rev: int,
    ref: str,
    title: str | None = None,
    material_state: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Edit an object in place; its opaque ref remains stable."""
    if title is not None and (not isinstance(title, str) or not title.strip()):
        raise ProjectModelError("title 不能为空。")
    if material_state is not None:
        _validate_material_state(material_state)
    if data is not None:
        data = _validate_data(data)

    def mutate(model: dict[str, Any], _next_rev: int) -> dict[str, Any]:
        item = _active_object(model, ref)
        changes: dict[str, dict[str, Any]] = {}
        if title is not None and item.get("title") != title.strip():
            before = item.get("title")
            item["title"] = title.strip()
            changes["title"] = {"before": before, "after": item["title"]}
        if material_state is not None and item.get("material_state") != material_state:
            before = item.get("material_state")
            item["material_state"] = material_state
            changes["material_state"] = {"before": before, "after": material_state}
        if data is not None and item.get("data") != data:
            before = copy.deepcopy(item.get("data"))
            item["data"] = data
            changes["data"] = {"before": before, "after": copy.deepcopy(data)}
        if not changes:
            raise ProjectModelError("编辑未产生任何实际变化。")
        return {"ref": ref, "action": "updated", "changes": changes}

    return _commit(project_id, base_model_rev, "object.updated", mutate)


def tombstone_object(project_id: str, *, base_model_rev: int, ref: str) -> dict[str, Any]:
    """Retire an identity without removing it or permitting reuse."""
    def mutate(model: dict[str, Any], next_rev: int) -> dict[str, Any]:
        retired_edges = _tombstone_object_with_incident_edges(model, ref, next_rev)
        return {"ref": ref, "action": "tombstoned", "retired_dependency_refs": retired_edges}

    return _commit(project_id, base_model_rev, "object.tombstoned", mutate)


def create_system(
    project_id: str,
    *,
    base_model_rev: int,
    title: str,
    definition: dict[str, Any],
    material_state: str = "current",
) -> dict[str, Any]:
    """Create a data-driven, author-defined system without a genre enum."""
    if not isinstance(title, str) or not title.strip():
        raise ProjectModelError("系统 title 不能为空。")
    definition = _validate_data(definition)
    material_state = _validate_material_state(material_state)

    def mutate(model: dict[str, Any], _next_rev: int) -> dict[str, Any]:
        ref = _next_ref(model, "obj")
        model["objects"][ref] = {
            "ref": ref,
            "kind": "system",
            "title": title.strip(),
            "material_state": material_state,
            "data": definition,
            "tombstoned": False,
        }
        return {"ref": ref, "action": "created", "kind": "system"}

    return _commit(project_id, base_model_rev, "system.created", mutate)


def set_length_plan(
    project_id: str,
    *,
    base_model_rev: int,
    total_target_words: int | None | object = _UNSET,
    stages: list[dict[str, Any]] | None = None,
    chapter_targets: list[dict[str, Any]] | None = None,
    actual_word_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Set only explicit soft planning values; never derives actual word counts."""
    if total_target_words is not _UNSET and total_target_words is not None and (
        not isinstance(total_target_words, int)
        or isinstance(total_target_words, bool)
        or total_target_words < 0
    ):
        raise ProjectModelError("total_target_words 必须是非负整数。")
    if stages is not None and not isinstance(stages, list):
        raise ProjectModelError("stages 必须是列表或省略。")
    if chapter_targets is not None and not isinstance(chapter_targets, list):
        raise ProjectModelError("chapter_targets 必须是列表或省略。")
    if actual_word_counts is not None:
        if not isinstance(actual_word_counts, dict) or any(
            not isinstance(k, str) or not isinstance(v, int) or v < 0 for k, v in actual_word_counts.items()
        ):
            raise ProjectModelError("actual_word_counts 必须是 ref 到非负整数的映射。")

    def normalize_entry(kind: str, entry: dict[str, Any], current: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
        if not isinstance(entry, dict):
            raise ProjectModelError("长度规划条目必须是对象。")
        supplied_title = entry.get("title") or entry.get("name") or entry.get("label")
        title = supplied_title if supplied_title is not None else (current or {}).get("title")
        if not isinstance(title, str) or not title.strip():
            raise ProjectModelError("长度规划条目必须有 title/name/label。")
        data = copy.deepcopy((current or {}).get("data") or {})
        if "data" in entry:
            data = _validate_data(entry["data"])
        for field, value in entry.items():
            if field not in {"ref", "title", "name", "label", "data"}:
                data[field] = copy.deepcopy(value)
        if kind == "length_stage":
            target = data.get("target_words")
            if target is not None and (not isinstance(target, int) or target < 0):
                raise ProjectModelError("阶段 target_words 必须是非负整数。")
        else:
            minimum, maximum = data.get("min_words"), data.get("max_words")
            if not isinstance(minimum, int) or not isinstance(maximum, int) or minimum < 0 or maximum < minimum:
                raise ProjectModelError("章节目标必须提供合法 min_words/max_words。")
        return title.strip(), data

    def reconcile_items(
        model: dict[str, Any], plan: dict[str, Any], key: str, kind: str,
        entries: list[dict[str, Any]], next_rev: int,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        old_refs = list(plan[key])
        submitted_refs: set[str] = set()
        new_refs: list[str] = []
        object_changes: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ProjectModelError("长度规划条目必须是对象。")
            ref = entry.get("ref")
            if ref is None:
                title, data = normalize_entry(kind, entry, None)
                ref = _next_ref(model, "obj")
                model["objects"][ref] = {
                    "ref": ref, "kind": kind, "title": title, "material_state": "future",
                    "data": data, "tombstoned": False,
                }
                object_changes.append({"ref": ref, "action": "created"})
            else:
                if not isinstance(ref, str) or ref in submitted_refs:
                    raise ProjectModelError("长度规划 ref 必须唯一且为字符串。")
                item = _active_object(model, ref, expected_kind=kind)
                if ref not in old_refs:
                    raise ProjectModelError("长度规划 ref 不属于当前项目的活动规划集合。")
                title, data = normalize_entry(kind, entry, item)
                changes: dict[str, dict[str, Any]] = {}
                if item.get("title") != title:
                    changes["title"] = {"before": item.get("title"), "after": title}
                    item["title"] = title
                if item.get("data") != data:
                    changes["data"] = {"before": copy.deepcopy(item.get("data")), "after": copy.deepcopy(data)}
                    item["data"] = data
                if changes:
                    object_changes.append({"ref": ref, "action": "updated", "changes": changes})
            submitted_refs.add(ref)
            new_refs.append(ref)
        for ref in old_refs:
            if ref not in submitted_refs:
                _active_object(model, ref, expected_kind=kind)
                retired_edges = _tombstone_object_with_incident_edges(model, ref, next_rev)
                object_changes.append({
                    "ref": ref, "action": "tombstoned", "retired_dependency_refs": retired_edges,
                })
        plan[key] = new_refs
        return new_refs, object_changes

    def mutate(model: dict[str, Any], next_rev: int) -> dict[str, Any]:
        plan = model["length_plan"]
        changed: dict[str, Any] = {}
        if total_target_words is not _UNSET and plan.get("total_target_words") != total_target_words:
            changed["total_target_words"] = {
                "before": plan.get("total_target_words"), "after": total_target_words,
            }
            plan["total_target_words"] = total_target_words
        if stages is not None:
            before = list(plan["stage_refs"])
            refs, object_changes = reconcile_items(model, plan, "stage_refs", "length_stage", stages, next_rev)
            if before != refs or object_changes:
                changed["stages"] = {"before_refs": before, "after_refs": refs, "objects": object_changes}
        if chapter_targets is not None:
            before = list(plan["chapter_target_refs"])
            refs, object_changes = reconcile_items(model, plan, "chapter_target_refs", "chapter_target", chapter_targets, next_rev)
            if before != refs or object_changes:
                changed["chapter_targets"] = {"before_refs": before, "after_refs": refs, "objects": object_changes}
        active_chapter_refs = set(plan["chapter_target_refs"])
        retained_actuals = {
            ref: count for ref, count in plan["actual_word_counts"].items() if ref in active_chapter_refs
        }
        if actual_word_counts is not None:
            for ref in actual_word_counts:
                if ref not in active_chapter_refs:
                    raise ProjectModelError("actual_word_counts 只能引用最终活动章节目标。")
                _active_object(model, ref, expected_kind="chapter_target")
            final_actuals = copy.deepcopy(actual_word_counts)
        else:
            final_actuals = retained_actuals
        if plan["actual_word_counts"] != final_actuals:
            changed["actual_word_counts"] = {
                "before": copy.deepcopy(plan["actual_word_counts"]), "after": copy.deepcopy(final_actuals),
            }
            plan["actual_word_counts"] = final_actuals
        if not changed:
            raise ProjectModelError("长度规划编辑未产生任何实际变化。")
        return {"action": "length_plan.set", "changed": changed}

    return _commit(project_id, base_model_rev, "length_plan.set", mutate)


def add_dependency(
    project_id: str,
    *,
    base_model_rev: int,
    source_ref: str,
    target_ref: str,
    relation_kind: str,
    title: str | None = None,
    material_state: str = "current",
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record one explicit direct dependency; no semantic inference is performed."""
    if not isinstance(relation_kind, str) or not relation_kind.strip():
        raise ProjectModelError("relation_kind 不能为空。")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        raise ProjectModelError("依赖 title 不能为空。")
    material_state = _validate_material_state(material_state)
    edge_data = _validate_data(data)

    def mutate(model: dict[str, Any], _next_rev: int) -> dict[str, Any]:
        _active_object(model, source_ref)
        _active_object(model, target_ref)
        edge_ref = _next_ref(model, "edge")
        model["dependencies"][edge_ref] = {
            "ref": edge_ref,
            "source_ref": source_ref,
            "target_ref": target_ref,
            "relation_kind": relation_kind.strip(),
            "title": title.strip() if isinstance(title, str) else relation_kind.strip(),
            "material_state": material_state,
            "data": edge_data,
            "tombstoned": False,
        }
        return {"ref": edge_ref, "action": "created", "source_ref": source_ref, "target_ref": target_ref}

    return _commit(project_id, base_model_rev, "dependency.created", mutate)


def update_dependency(
    project_id: str,
    *,
    base_model_rev: int,
    ref: str,
    source_ref: str | None = None,
    target_ref: str | None = None,
    relation_kind: str | None = None,
    title: str | None = None,
    material_state: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update one explicit dependency while preserving its stable identity."""
    if relation_kind is not None and (not isinstance(relation_kind, str) or not relation_kind.strip()):
        raise ProjectModelError("relation_kind 不能为空。")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        raise ProjectModelError("依赖 title 不能为空。")
    if material_state is not None:
        _validate_material_state(material_state)
    if data is not None:
        data = _validate_data(data)

    def mutate(model: dict[str, Any], _next_rev: int) -> dict[str, Any]:
        edge = model["dependencies"].get(ref)
        if not isinstance(edge, dict):
            raise ProjectModelError("未知或跨项目依赖 ref，已拒绝。")
        if edge.get("tombstoned"):
            raise ProjectModelError("依赖 ref 已 tombstone，不能再编辑。")
        next_source = source_ref if source_ref is not None else edge["source_ref"]
        next_target = target_ref if target_ref is not None else edge["target_ref"]
        _active_object(model, next_source)
        _active_object(model, next_target)
        if next_source == next_target:
            raise ProjectModelError("关系两端不能指向同一对象。")
        changes: dict[str, dict[str, Any]] = {}
        replacements = {
            "source_ref": next_source,
            "target_ref": next_target,
            "relation_kind": relation_kind.strip() if isinstance(relation_kind, str) else edge.get("relation_kind"),
            "title": title.strip() if isinstance(title, str) else edge.get("title", edge.get("relation_kind")),
            "material_state": material_state if material_state is not None else edge.get("material_state", "current"),
            "data": data if data is not None else copy.deepcopy(edge.get("data") or {}),
        }
        for key, value in replacements.items():
            if edge.get(key) != value:
                changes[key] = {"before": copy.deepcopy(edge.get(key)), "after": copy.deepcopy(value)}
                edge[key] = value
        if not changes:
            raise ProjectModelError("关系编辑未产生任何实际变化。")
        return {"ref": ref, "action": "updated", "changes": changes}

    return _commit(project_id, base_model_rev, "dependency.updated", mutate)


def tombstone_dependency(project_id: str, *, base_model_rev: int, ref: str) -> dict[str, Any]:
    """Retire one explicit dependency without deleting its history."""
    def mutate(model: dict[str, Any], next_rev: int) -> dict[str, Any]:
        edge = model["dependencies"].get(ref)
        if not isinstance(edge, dict):
            raise ProjectModelError("未知或跨项目依赖 ref，已拒绝。")
        if edge.get("tombstoned"):
            raise ProjectModelError("依赖 ref 已 tombstone。")
        edge["tombstoned"] = True
        edge["tombstoned_at_rev"] = next_rev
        return {"ref": ref, "action": "tombstoned"}

    return _commit(project_id, base_model_rev, "dependency.tombstoned", mutate)


def create_relationship(
    project_id: str,
    *,
    base_model_rev: int,
    source_ref: str,
    target_ref: str,
    label: str,
    material_state: str = "current",
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create the single editable author-managed character relationship contract."""
    if not isinstance(label, str) or not label.strip():
        raise ProjectModelError("关系名称不能为空。")

    def ensure_character(model: dict[str, Any], ref: str) -> None:
        item = _active_object(model, ref)
        if item.get("kind") != "foundation" or item.get("category") != "character":
            raise ProjectModelError("人物关系端点必须是活动人物记录。")

    material_state = _validate_material_state(material_state)
    relation_data = _validate_data(data)

    def mutate(model: dict[str, Any], _next_rev: int) -> dict[str, Any]:
        ensure_character(model, source_ref)
        ensure_character(model, target_ref)
        if source_ref == target_ref:
            raise ProjectModelError("关系两端不能指向同一人物。")
        edge_ref = _next_ref(model, "edge")
        model["dependencies"][edge_ref] = {
            "ref": edge_ref,
            "source_ref": source_ref,
            "target_ref": target_ref,
            "relation_kind": "character_relationship",
            "title": label.strip(),
            "material_state": material_state,
            "data": relation_data,
            "tombstoned": False,
        }
        return {"ref": edge_ref, "action": "created", "source_ref": source_ref, "target_ref": target_ref}

    return _commit(project_id, base_model_rev, "relationship.created", mutate)


def validate_planning_projection(value: Any) -> dict[str, list[dict[str, Any]]]:
    """Strict, side-effect-free validation for the optional StoryPlan projection."""
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ProjectModelError("planning_projection 必须是对象。")
    allowed = {
        "characters", "relationships", "settings", "storylines", "events",
        "foreshadowing", "chapter_changes",
    }
    unknown = set(value) - allowed
    if unknown:
        raise ProjectModelError(f"planning_projection 包含未知字段：{', '.join(sorted(unknown))}。")
    normalized: dict[str, list[dict[str, Any]]] = {}
    for key in sorted(allowed):
        entries = value.get(key, [])
        if not isinstance(entries, list):
            raise ProjectModelError(f"planning_projection.{key} 必须是列表。")
        normalized[key] = []
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise ProjectModelError(f"planning_projection.{key}[{index}] 必须是对象。")
            item = copy.deepcopy(entry)
            if key == "relationships":
                required = ("source_key", "target_key", "label")
                if any(not isinstance(item.get(field), str) or not item[field].strip() for field in required):
                    raise ProjectModelError("规划关系必须提供 source_key、target_key、label。")
            else:
                title = item.get("title") or item.get("name")
                if not isinstance(title, str) or not title.strip():
                    raise ProjectModelError(f"planning_projection.{key}[{index}] 缺少 title/name。")
                item["title"] = title.strip()
                if key != "chapter_changes":
                    entity_key = item.get("key") or item["title"]
                    if not isinstance(entity_key, str) or not entity_key.strip():
                        raise ProjectModelError("规划实体 key 必须是非空字符串。")
                    item["key"] = entity_key.strip()
            normalized[key].append(item)
    return normalized


def apply_planning_projection(
    project_id: str,
    *,
    base_model_rev: int,
    projection: dict[str, Any],
    source_ref: str,
) -> dict[str, Any]:
    """Commit one confirmed candidate's explicit fields as future workspace data."""
    normalized = validate_planning_projection(projection)
    if not any(normalized.values()):
        return load_project_model(project_id)
    if not isinstance(source_ref, str) or not source_ref.strip():
        raise ProjectModelError("规划投影 source_ref 不能为空。")

    category_for = {
        "characters": "character",
        "settings": "world_setting",
        "storylines": "story_line",
        "events": "event",
        "foreshadowing": "promise_foreshadowing",
    }

    def mutate(model: dict[str, Any], _next_rev: int) -> dict[str, Any]:
        key_to_ref: dict[str, str] = {}
        created_objects: list[str] = []
        created_edges: list[str] = []
        for collection, category in category_for.items():
            for item in normalized[collection]:
                key = item["key"]
                if key in key_to_ref:
                    raise ProjectModelError(f"规划投影实体 key 重复：{key}。")
                ref = _next_ref(model, "obj")
                payload = {k: copy.deepcopy(v) for k, v in item.items() if k not in {"key", "title", "name"}}
                payload["planning_source_ref"] = source_ref.strip()
                model["objects"][ref] = {
                    "ref": ref, "kind": "foundation", "category": category,
                    "category_name": None, "title": item["title"], "material_state": "future",
                    "data": payload, "tombstoned": False,
                }
                key_to_ref[key] = ref
                created_objects.append(ref)
        for rel in normalized["relationships"]:
            source = key_to_ref.get(rel["source_key"])
            target = key_to_ref.get(rel["target_key"])
            if not source or not target:
                raise ProjectModelError("规划关系端点必须引用同一投影中的明确人物 key。")
            if model["objects"][source].get("category") != "character" or model["objects"][target].get("category") != "character":
                raise ProjectModelError("规划关系端点必须引用规划人物。")
            edge_ref = _next_ref(model, "edge")
            payload = {k: copy.deepcopy(v) for k, v in rel.items() if k not in {"source_key", "target_key", "label"}}
            payload["planning_source_ref"] = source_ref.strip()
            model["dependencies"][edge_ref] = {
                "ref": edge_ref, "source_ref": source, "target_ref": target,
                "relation_kind": "character_relationship", "title": rel["label"].strip(),
                "material_state": "future", "data": payload, "tombstoned": False,
            }
            created_edges.append(edge_ref)
        for item in normalized["chapter_changes"]:
            minimum = item.get("min_words")
            maximum = item.get("max_words")
            if not isinstance(minimum, int) or not isinstance(maximum, int) or minimum < 0 or maximum < minimum:
                raise ProjectModelError("规划章节变化必须提供合法 min_words/max_words。")
            ref = _next_ref(model, "obj")
            payload = {k: copy.deepcopy(v) for k, v in item.items() if k not in {"title", "name"}}
            payload["planning_source_ref"] = source_ref.strip()
            model["objects"][ref] = {
                "ref": ref, "kind": "chapter_target", "title": item["title"],
                "material_state": "future", "data": payload, "tombstoned": False,
            }
            model["length_plan"]["chapter_target_refs"].append(ref)
            created_objects.append(ref)
        return {
            "action": "planning_projection.applied", "source_ref": source_ref.strip(),
            "created_object_refs": created_objects, "created_dependency_refs": created_edges,
        }

    return _commit(project_id, base_model_rev, "planning_projection.applied", mutate)


def list_direct_dependencies(project_id: str, ref: str | None = None) -> list[dict[str, Any]]:
    """Return only explicitly stored, non-tombstoned direct dependency edges."""
    model = load_project_model(project_id)
    if ref is not None:
        _active_object(model, ref)
    return [
        copy.deepcopy(edge)
        for edge in model["dependencies"].values()
        if not edge.get("tombstoned")
        and (ref is None or edge["source_ref"] == ref or edge["target_ref"] == ref)
    ]
