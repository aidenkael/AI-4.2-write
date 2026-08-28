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
    "custom",
}
_MATERIAL_STATES = {"current", "future"}


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
    plan = model["length_plan"]
    if not isinstance(plan.get("stage_refs"), list) or not isinstance(plan.get("chapter_target_refs"), list):
        raise ProjectModelError("项目模型长度规划 ref 列表非法。")
    if not isinstance(plan.get("actual_word_counts"), dict):
        raise ProjectModelError("项目模型 actual_word_counts 非法。")
    for ref in plan["stage_refs"]:
        if ref not in model["objects"] or model["objects"][ref].get("kind") != "length_stage":
            raise ProjectModelError("项目模型阶段 ref 非法。")
    for ref in plan["chapter_target_refs"]:
        if ref not in model["objects"] or model["objects"][ref].get("kind") != "chapter_target":
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
        changed: list[str] = []
        if title is not None:
            item["title"] = title.strip()
            changed.append("title")
        if material_state is not None:
            item["material_state"] = material_state
            changed.append("material_state")
        if data is not None:
            item["data"] = data
            changed.append("data")
        return {"ref": ref, "action": "updated", "fields": changed}

    return _commit(project_id, base_model_rev, "object.updated", mutate)


def tombstone_object(project_id: str, *, base_model_rev: int, ref: str) -> dict[str, Any]:
    """Retire an identity without removing it or permitting reuse."""
    def mutate(model: dict[str, Any], next_rev: int) -> dict[str, Any]:
        item = _active_object(model, ref)
        item["tombstoned"] = True
        item["tombstoned_at_rev"] = next_rev
        return {"ref": ref, "action": "tombstoned"}

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
    total_target_words: int | None = None,
    stages: list[dict[str, Any]] | None = None,
    chapter_targets: list[dict[str, Any]] | None = None,
    actual_word_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Set only explicit soft planning values; never derives actual word counts."""
    if total_target_words is not None and (not isinstance(total_target_words, int) or total_target_words < 0):
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

    def replace_items(model: dict[str, Any], plan: dict[str, Any], key: str, kind: str, entries: list[dict[str, Any]]) -> list[str]:
        old_refs = list(plan[key])
        for old_ref in old_refs:
            old = _active_object(model, old_ref, expected_kind=kind)
            old["tombstoned"] = True
        new_refs: list[str] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ProjectModelError("长度规划条目必须是对象。")
            title = entry.get("title") or entry.get("name") or entry.get("label")
            if not isinstance(title, str) or not title.strip():
                raise ProjectModelError("长度规划条目必须有 title/name/label。")
            data = {k: copy.deepcopy(v) for k, v in entry.items() if k not in {"title", "name", "label"}}
            if kind == "length_stage":
                target = data.get("target_words")
                if target is not None and (not isinstance(target, int) or target < 0):
                    raise ProjectModelError("阶段 target_words 必须是非负整数。")
            else:
                minimum, maximum = data.get("min_words"), data.get("max_words")
                if not isinstance(minimum, int) or not isinstance(maximum, int) or minimum < 0 or maximum < minimum:
                    raise ProjectModelError("章节目标必须提供合法 min_words/max_words。")
            ref = _next_ref(model, "obj")
            model["objects"][ref] = {
                "ref": ref, "kind": kind, "title": title.strip(), "material_state": "future",
                "data": data, "tombstoned": False,
            }
            new_refs.append(ref)
        plan[key] = new_refs
        return new_refs

    def mutate(model: dict[str, Any], _next_rev: int) -> dict[str, Any]:
        plan = model["length_plan"]
        changed: dict[str, Any] = {}
        if total_target_words is not None:
            plan["total_target_words"] = total_target_words
            changed["total_target_words"] = total_target_words
        if stages is not None:
            changed["stage_refs"] = replace_items(model, plan, "stage_refs", "length_stage", stages)
        if chapter_targets is not None:
            changed["chapter_target_refs"] = replace_items(model, plan, "chapter_target_refs", "chapter_target", chapter_targets)
        if actual_word_counts is not None:
            for ref in actual_word_counts:
                _active_object(model, ref, expected_kind="chapter_target")
            plan["actual_word_counts"] = copy.deepcopy(actual_word_counts)
            changed["actual_word_counts"] = sorted(actual_word_counts)
        return {"action": "length_plan.set", "changed": changed}

    return _commit(project_id, base_model_rev, "length_plan.set", mutate)


def add_dependency(
    project_id: str,
    *,
    base_model_rev: int,
    source_ref: str,
    target_ref: str,
    relation_kind: str,
) -> dict[str, Any]:
    """Record one explicit direct dependency; no semantic inference is performed."""
    if not isinstance(relation_kind, str) or not relation_kind.strip():
        raise ProjectModelError("relation_kind 不能为空。")

    def mutate(model: dict[str, Any], _next_rev: int) -> dict[str, Any]:
        _active_object(model, source_ref)
        _active_object(model, target_ref)
        edge_ref = _next_ref(model, "edge")
        model["dependencies"][edge_ref] = {
            "ref": edge_ref,
            "source_ref": source_ref,
            "target_ref": target_ref,
            "relation_kind": relation_kind.strip(),
            "tombstoned": False,
        }
        return {"ref": edge_ref, "action": "created", "source_ref": source_ref, "target_ref": target_ref}

    return _commit(project_id, base_model_rev, "dependency.created", mutate)


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
