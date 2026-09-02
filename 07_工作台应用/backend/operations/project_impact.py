# -*- coding: utf-8 -*-
"""Deterministic, read-only direct-impact reports for Go Write project models.

This module exposes explicit project-model history and explicit dependency
edges only.  It deliberately performs no semantic impact judgment, no model
call, and no writeback to Story State, Canon, planning, or the model artifact.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from operations.project_model import (  # existing v1 artifact contract; no writes
    ARTIFACT_NAME,
    ProjectModelError,
    _read_json_text_retry,
    _validate_model,
)
from project_workspace import (  # formal-project resolution/loading only
    ContractError as PWContractError,
    WorkspaceError as PWWorkspaceError,
    load_project,
    resolve_project,
)


SCHEMA_VERSION = "gowrite_direct_impact/v1"


class ProjectImpactError(Exception):
    """A revision-bound direct-impact report cannot be built safely."""


def _load_read_only_project_model(project_id: str) -> dict[str, Any]:
    """Resolve a formal project and validate an existing model without writes."""
    if not isinstance(project_id, str) or not project_id.strip():
        raise ProjectImpactError("缺少 project_id。")
    project_id = project_id.strip()
    try:
        project = resolve_project(project_id)
        loaded = load_project(project["project_dir"])
    except (PWContractError, PWWorkspaceError) as exc:
        raise ProjectImpactError(str(exc)) from exc
    if loaded.get("project_id") != project_id:
        raise ProjectImpactError("项目解析后的 project_id 不一致，已拒绝。")
    project_dir = Path(loaded["project_dir"]).resolve()
    state_dir = (project_dir / "_工作台状态").resolve()
    artifact = (state_dir / ARTIFACT_NAME).resolve()
    if artifact.parent != state_dir or state_dir.parent != project_dir:
        raise ProjectImpactError("项目模型路径 containment 校验失败。")
    if not artifact.is_file():
        raise ProjectImpactError("项目尚未建立 Go Write project-model 工件。")
    try:
        model = json.loads(_read_json_text_retry(artifact))
        return _validate_model(model, project_id)
    except (OSError, json.JSONDecodeError, ProjectModelError) as exc:
        raise ProjectImpactError(f"项目模型读取或校验失败：{exc}") from exc


def _add_ref(refs: set[str], value: Any) -> None:
    if isinstance(value, str) and value:
        refs.add(value)


def _length_plan_refs(
    detail: dict[str, Any], refs: set[str], dependency_refs: set[str], scopes: set[str],
) -> None:
    changed = detail.get("changed")
    if not isinstance(changed, dict):
        return
    if "total_target_words" in changed:
        scopes.add("length_plan.total_target_words")
    for section in ("stages", "chapter_targets"):
        section_change = changed.get(section)
        if not isinstance(section_change, dict):
            continue
        for item in section_change.get("objects") or []:
            if isinstance(item, dict):
                _add_ref(refs, item.get("ref"))
                for edge_ref in item.get("retired_dependency_refs") or []:
                    _add_ref(dependency_refs, edge_ref)
    actuals = changed.get("actual_word_counts")
    if isinstance(actuals, dict):
        before = actuals.get("before") if isinstance(actuals.get("before"), dict) else {}
        after = actuals.get("after") if isinstance(actuals.get("after"), dict) else {}
        for ref in set(before) | set(after):
            if before.get(ref) != after.get(ref):
                _add_ref(refs, ref)


def _extract_changed(change: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    """Extract only refs/scopes proven by a known v1 history contract."""
    kind = change.get("kind")
    detail = change.get("detail")
    if not isinstance(detail, dict):
        return [], [], []
    object_refs: set[str] = set()
    dependency_refs: set[str] = set()
    scopes: set[str] = set()
    if kind in {"foundation.created", "system.created", "object.updated", "object.tombstoned"}:
        _add_ref(object_refs, detail.get("ref"))
        if kind == "object.tombstoned":
            for edge_ref in detail.get("retired_dependency_refs") or []:
                _add_ref(dependency_refs, edge_ref)
    elif kind in {"dependency.created", "relationship.created", "dependency.updated", "dependency.tombstoned"}:
        _add_ref(dependency_refs, detail.get("ref"))
    elif kind == "planning_projection.applied":
        for ref in detail.get("created_object_refs") or []:
            _add_ref(object_refs, ref)
        for ref in detail.get("created_dependency_refs") or []:
            _add_ref(dependency_refs, ref)
    elif kind == "length_plan.set":
        _length_plan_refs(detail, object_refs, dependency_refs, scopes)
    return sorted(object_refs), sorted(dependency_refs), sorted(scopes)


def _dependency_candidates(
    model: dict[str, Any], changed_object_refs: list[str], source_model_rev: int,
) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for changed_ref in changed_object_refs:
        for edge_ref, edge in model.get("dependencies", {}).items():
            if not isinstance(edge, dict):
                continue
            retired_here = bool(edge.get("tombstoned")) and edge.get("tombstoned_at_rev") == source_model_rev
            active = not edge.get("tombstoned")
            if not (active or retired_here):
                continue
            state = "active" if active else "retired_in_source_change"
            if edge.get("source_ref") == changed_ref:
                candidates.append({
                    "edge_ref": edge_ref,
                    "changed_ref": changed_ref,
                    "other_ref": edge.get("target_ref"),
                    "direction": "outgoing",
                    "relation_kind": edge.get("relation_kind"),
                    "edge_state": state,
                })
            if edge.get("target_ref") == changed_ref:
                candidates.append({
                    "edge_ref": edge_ref,
                    "changed_ref": changed_ref,
                    "other_ref": edge.get("source_ref"),
                    "direction": "incoming",
                    "relation_kind": edge.get("relation_kind"),
                    "edge_state": state,
                })
    return sorted(
        candidates,
        key=lambda item: (
            str(item["edge_ref"]), str(item["changed_ref"]), str(item["other_ref"]),
            str(item["direction"]), str(item["relation_kind"]), str(item["edge_state"]),
        ),
    )


def build_direct_impact_report(project_id: str, source_model_rev: int) -> dict[str, Any]:
    """Build a report bound to the latest committed project-model revision.

    It resolves formal projects and reads an existing, validated artifact only.
    This operation makes no writes and rejects any historical/stale revision
    until a future explicit historical-model contract exists.
    """
    if not isinstance(source_model_rev, int) or isinstance(source_model_rev, bool) or source_model_rev <= 0:
        raise ProjectImpactError("source_model_rev 必须是正整数。")
    model = _load_read_only_project_model(project_id)
    if model.get("model_rev") != source_model_rev:
        raise ProjectImpactError("source_model_rev 必须等于当前 model_rev；历史 revision 暂不支持。")
    matches = [
        entry for entry in model.get("change_history", [])
        if isinstance(entry, dict) and entry.get("model_rev") == source_model_rev
    ]
    if len(matches) != 1:
        raise ProjectImpactError("请求 revision 必须恰好对应一条 change_history 记录。")
    change = copy.deepcopy(matches[0])
    changed_object_refs, changed_dependency_refs, changed_scopes = _extract_changed(change)
    candidates = _dependency_candidates(model, changed_object_refs, source_model_rev)
    snapshot_refs = set(changed_object_refs)
    snapshot_refs.update(candidate["other_ref"] for candidate in candidates if isinstance(candidate.get("other_ref"), str))
    if change.get("kind") in {"dependency.created", "relationship.created", "dependency.updated", "dependency.tombstoned"}:
        if len(changed_dependency_refs) != 1:
            raise ProjectImpactError("dependency.created 必须解析到一条现存依赖边。")
        edge = model.get("dependencies", {}).get(changed_dependency_refs[0])
        if not isinstance(edge, dict):
            raise ProjectImpactError("dependency.created 对应依赖边不存在。")
        for endpoint in (edge.get("source_ref"), edge.get("target_ref")):
            if not isinstance(endpoint, str) or endpoint not in model.get("objects", {}):
                raise ProjectImpactError("dependency.created 对应端点对象不存在。")
            snapshot_refs.add(endpoint)
    snapshots = {
        ref: copy.deepcopy(model["objects"][ref])
        for ref in sorted(snapshot_refs)
        if ref in model.get("objects", {})
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": model.get("project_id"),
        "source_model_rev": source_model_rev,
        "change_kind": change.get("kind"),
        "change": change,
        "changed_object_refs": changed_object_refs,
        "changed_dependency_refs": changed_dependency_refs,
        "changed_scopes": changed_scopes,
        "direct_dependency_candidates": candidates,
        "object_snapshots": snapshots,
    }
