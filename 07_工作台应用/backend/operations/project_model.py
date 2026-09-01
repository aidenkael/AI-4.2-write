# -*- coding: utf-8 -*-
"""Go Write 2.0 author-workspace project model.

This is an application-layer author-management artifact, deliberately separate
from production Story State and StoryPlan.  It records explicit author workspace
data, confirmed future projections, and direct dependencies; it neither infers
facts nor writes production Canon, prose, or any frozen runtime artifact.
"""
from __future__ import annotations

import copy
import datetime
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


SCHEMA_VERSION = "gowrite_project_model/v3"
_LEGACY_SCHEMA_VERSIONS = {"gowrite_project_model/v1", "gowrite_project_model/v2"}
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
    "mystery_information",
    "custom",
}
_MATERIAL_STATES = {"current", "future"}
DEFAULT_DOMAIN_MODULES = (
    "core", "characters", "relationships", "world", "locations", "organizations",
    "storylines", "foreshadowing", "events", "time",
)
OPTIONAL_DOMAIN_MODULES = (
    "power_progression", "career_rank", "economy_resources", "politics_factions",
    "technology", "supernatural_rules", "romance_social", "mystery_information", "custom",
)
_DOMAIN_MODULES = set(DEFAULT_DOMAIN_MODULES) | set(OPTIONAL_DOMAIN_MODULES)
_CHAPTER_RESULT_FIELDS = {
    "summary", "important_events", "characters_involved", "character_state_changes",
    "relationship_changes", "time_movement", "location_state_changes", "information_revealed",
    "foreshadowing_planted_paid_off", "unresolved_threads", "final_chapter_state",
    "outline_divergence",
}
_DYNAMIC_SEMANTIC_FIELDS = {
    "one_line_intro", "visible_traits", "background_summary", "position_title",
    "power_rank", "profession_rank", "current_location", "current_state",
    "current_objective", "arc_stage", "relationship_state", "relationship_phase",
    "current_tension", "state", "stage_progress", "reveal_status", "actual_payoff",
}
_INTERNAL_DATA_FIELDS = {
    "source_ref", "source_kind", "material_state", "model_rev", "state_rev",
    "schema_version", "project_id", "request_id", "planning_token", "writing_token",
    "scene_ref", "authority", "provenance", "planning_source_ref", "source_state_ref",
    "supersedes_state_ref", "settlement_provenance", "content_sha256",
}
# 唯一领域关系规格真源：所有校验/写路径都消费它，不建通用 ontology。
# source/target 形状：(kind, category)；kind=="system" 表示体系对象。
# 带 target_categories 的类型允许若干种目标分类（含 "system"）。
_DOMAIN_RELATION_SPECS: dict[str, dict[str, Any]] = {
    "character_affiliated_with_organization": {
        "source": ("foundation", "character"),
        "target": ("foundation", "organization_force"),
        "title": "所属组织",
    },
    "character_uses_system": {
        "source": ("foundation", "character"),
        "target": ("system", None),
        "title": "关联体系",
    },
    "storyline_involves_character": {
        "source": ("foundation", "story_line"),
        "target": ("foundation", "character"),
        "title": "涉及人物",
    },
    "storyline_involves_organization": {
        "source": ("foundation", "story_line"),
        "target": ("foundation", "organization_force"),
        "title": "涉及组织",
    },
    "storyline_involves_location": {
        "source": ("foundation", "story_line"),
        "target": ("foundation", "location"),
        "title": "涉及地点",
    },
    "foreshadowing_related_to": {
        "source": ("foundation", "promise_foreshadowing"),
        "target_categories": {
            "character", "world_setting", "location",
            "organization_force", "system", "story_line",
        },
        "title": "相关对象",
    },
    "mystery_information_related_to": {
        "source": ("foundation", "mystery_information"),
        "target_categories": {
            "character", "world_setting", "location",
            "organization_force", "system", "story_line",
        },
        "title": "相关对象",
    },
}
DOMAIN_RELATION_KINDS = frozenset(_DOMAIN_RELATION_SPECS)
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
        "story_bible_profile": {
            "genre_tags": [],
            "narrative_mode": None,
            "active_modules": list(DEFAULT_DOMAIN_MODULES),
            "field_config": {},
        },
        "length_plan": {
            "total_target_words": None,
            "stage_refs": [],
            "chapter_target_refs": [],
            "actual_word_counts": {},
        },
        "chapter_actual_results": {},
        "planning_impact_candidates": [],
        "change_history": [],
    }


def _is_internal_data_field(field: str) -> bool:
    lowered = field.lower()
    return (
        field in _INTERNAL_DATA_FIELDS
        or lowered.endswith(("_rev", "_hash", "_token"))
        or (lowered.endswith("_ref") and field not in {"system_ref"})
    )


def _field_scope(field: str) -> str:
    return "dynamic" if field in _DYNAMIC_SEMANTIC_FIELDS else "stable"


def _authority_entry(source: str, field: str, model_rev: int) -> dict[str, Any]:
    return {"source": source, "scope": _field_scope(field), "updated_model_rev": model_rev}


def _initial_field_authority(
    data: dict[str, Any], field_authority: str, model_rev: int,
) -> dict[str, dict[str, Any]]:
    return {
        field: _authority_entry(field_authority, field, model_rev)
        for field in data
        if not _is_internal_data_field(field)
    }


def _migrate_model(model: Any) -> tuple[Any, bool]:
    """Additively migrate v1/v2 authority into the field-level v3 contract."""
    if not isinstance(model, dict) or model.get("schema_version") not in _LEGACY_SCHEMA_VERSIONS:
        return model, False
    migrated = copy.deepcopy(model)
    from_v1 = migrated.get("schema_version") == "gowrite_project_model/v1"
    migrated["schema_version"] = SCHEMA_VERSION
    migrated.setdefault("story_bible_profile", {
        "genre_tags": [], "narrative_mode": None,
        "active_modules": list(DEFAULT_DOMAIN_MODULES), "field_config": {},
    })
    migrated.setdefault("chapter_actual_results", {})
    migrated.setdefault("planning_impact_candidates", [])
    for item in [
        *migrated.get("objects", {}).values(),
        *migrated.get("dependencies", {}).values(),
    ]:
        if isinstance(item, dict):
            data = item.get("data") if isinstance(item.get("data"), dict) else {}
            if from_v1:
                item.setdefault("author_fields", sorted(
                    field for field in data if not _is_internal_data_field(field)
                ))
            author_fields = set(item.get("author_fields") or [])
            rev = int(migrated.get("model_rev") or 0)
            item["field_authority"] = {
                field: _authority_entry("author" if field in author_fields else "semantic", field, rev)
                for field in data
                if not _is_internal_data_field(field)
            }
            item["author_fields"] = sorted(
                field for field in author_fields if not _is_internal_data_field(field)
            )
    return migrated, True


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
    if (
        not isinstance(model.get("length_plan"), dict)
        or not isinstance(model.get("change_history"), list)
        or not isinstance(model.get("chapter_actual_results"), dict)
        or not isinstance(model.get("planning_impact_candidates"), list)
    ):
        raise ProjectModelError("项目模型结构不完整。")
    profile = model.get("story_bible_profile")
    if not isinstance(profile, dict):
        raise ProjectModelError("项目领域配置非法。")
    if not isinstance(profile.get("genre_tags"), list) or any(
        not isinstance(tag, str) or not tag.strip() for tag in profile.get("genre_tags", [])
    ):
        raise ProjectModelError("项目领域配置 genre_tags 非法。")
    if profile.get("narrative_mode") is not None and not isinstance(profile.get("narrative_mode"), str):
        raise ProjectModelError("项目领域配置 narrative_mode 非法。")
    modules = profile.get("active_modules")
    if not isinstance(modules, list) or any(module not in _DOMAIN_MODULES for module in modules):
        raise ProjectModelError("项目领域配置 active_modules 非法。")
    if not set(DEFAULT_DOMAIN_MODULES).issubset(modules):
        raise ProjectModelError("项目领域配置不能关闭默认核心模块。")
    if len(modules) != len(set(modules)) or not isinstance(profile.get("field_config"), dict):
        raise ProjectModelError("项目领域配置包含重复模块或非法 field_config。")
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
        if not isinstance(item.get("author_fields", []), list) or any(
            not isinstance(field, str) for field in item.get("author_fields", [])
        ):
            raise ProjectModelError("项目模型对象 author_fields 非法。")
        authority = item.get("field_authority", {})
        if not isinstance(authority, dict) or any(
            not isinstance(field, str)
            or not isinstance(meta, dict)
            or meta.get("source") not in {"author", "semantic", "confirmed_plan"}
            or meta.get("scope") not in {"stable", "dynamic"}
            or not isinstance(meta.get("updated_model_rev"), int)
            for field, meta in authority.items()
        ):
            raise ProjectModelError("项目模型对象 field_authority 非法。")
    for ref, edge in model["dependencies"].items():
        if not isinstance(ref, str) or not ref.startswith(f"gw2_edge_{scope}_"):
            raise ProjectModelError("项目模型包含未知或跨项目依赖 ref。")
        try:
            largest_sequence = max(largest_sequence, int(ref.rsplit("_", 1)[1], 16))
        except (IndexError, ValueError) as exc:
            raise ProjectModelError("项目模型依赖 ref 格式非法。") from exc
        if not isinstance(edge, dict) or edge.get("ref") != ref:
            raise ProjectModelError("项目模型依赖结构非法。")
        if not isinstance(edge.get("author_fields", []), list) or any(
            not isinstance(field, str) for field in edge.get("author_fields", [])
        ):
            raise ProjectModelError("项目模型依赖 author_fields 非法。")
        authority = edge.get("field_authority", {})
        if not isinstance(authority, dict) or any(
            not isinstance(field, str)
            or not isinstance(meta, dict)
            or meta.get("source") not in {"author", "semantic", "confirmed_plan"}
            or meta.get("scope") not in {"stable", "dynamic"}
            or not isinstance(meta.get("updated_model_rev"), int)
            for field, meta in authority.items()
        ):
            raise ProjectModelError("项目模型依赖 field_authority 非法。")
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
        data = model["objects"][ref].get("data") or {}
        stage_ref = data.get("stage_ref")
        if stage_ref is not None and (
            not isinstance(stage_ref, str)
            or stage_ref not in plan["stage_refs"]
            or stage_ref not in model["objects"]
            or model["objects"][stage_ref].get("kind") != "length_stage"
            or model["objects"][stage_ref].get("tombstoned")
        ):
            raise ProjectModelError("章节目标 stage_ref 必须引用同一项目的活动阶段。")
    for ref, count in plan["actual_word_counts"].items():
        if ref not in plan["chapter_target_refs"] or not isinstance(count, int) or count < 0:
            raise ProjectModelError("项目模型实际字数记录非法。")
    for chapter_key, result in model["chapter_actual_results"].items():
        if not isinstance(chapter_key, str) or not chapter_key.isdigit() or int(chapter_key) < 1:
            raise ProjectModelError("章节实际结果 chapter_number 非法。")
        if not isinstance(result, dict) or result.get("chapter_number") != int(chapter_key):
            raise ProjectModelError("章节实际结果结构非法。")
        if set(result) - (_CHAPTER_RESULT_FIELDS | {
            "chapter_number", "content_sha256", "source_change_id", "updated_model_rev",
        }):
            raise ProjectModelError("章节实际结果包含未知字段。")
        if not isinstance(result.get("summary"), str):
            raise ProjectModelError("章节实际结果 summary 非法。")
    for candidate in model["planning_impact_candidates"]:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("summary"), str):
            raise ProjectModelError("规划影响候选结构非法。")
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
    model, migrated = _migrate_model(model)
    validated = _validate_model(model, project_id)
    if migrated:
        _atomic_write_json(artifact, validated)
    return validated, artifact


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
    model, _migrated = _migrate_model(model)
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


def apply_deterministic_time_arithmetic(data: dict[str, Any]) -> dict[str, Any]:
    """Compute an anchor only from an explicit ISO base and structured offset.

    Semantic extraction may identify ``base_story_time_anchor`` and a
    ``relative_duration`` object.  Code owns the arithmetic; prose such as
    "three days later" is never parsed here and therefore cannot invent a date.
    """
    normalized = copy.deepcopy(data)
    base = normalized.get("base_story_time_anchor")
    duration = normalized.get("relative_duration")
    if not isinstance(base, str) or not base.strip() or not isinstance(duration, dict):
        return normalized
    amount = duration.get("value")
    unit = duration.get("unit")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not isinstance(unit, str):
        return normalized
    unit = unit.strip().lower()
    factors = {
        "minute": 60, "minutes": 60,
        "hour": 3600, "hours": 3600,
        "day": 86400, "days": 86400,
        "week": 604800, "weeks": 604800,
    }
    if unit not in factors:
        return normalized
    raw_base = base.strip()
    try:
        if "T" in raw_base or " " in raw_base:
            parsed: datetime.date | datetime.datetime = datetime.datetime.fromisoformat(
                raw_base.replace("Z", "+00:00")
            )
        else:
            parsed = datetime.date.fromisoformat(raw_base)
        delta = datetime.timedelta(seconds=float(amount) * factors[unit])
        if isinstance(parsed, datetime.datetime):
            computed = parsed + delta
            rendered = computed.isoformat()
        elif delta.seconds == 0 and delta.microseconds == 0:
            computed = parsed + delta
            rendered = computed.isoformat()
        else:
            computed = datetime.datetime.combine(parsed, datetime.time()) + delta
            rendered = computed.isoformat()
    except (ValueError, OverflowError):
        return normalized
    normalized["computed_story_time_anchor"] = rendered
    return normalized


def _active_object(model: dict[str, Any], ref: str, *, expected_kind: str | None = None) -> dict[str, Any]:
    item = model["objects"].get(ref)
    if not isinstance(item, dict):
        raise ProjectModelError("未知或跨项目 ref，已拒绝。")
    if item.get("tombstoned"):
        raise ProjectModelError("ref 已 tombstone，不能再作为活动对象使用。")
    if expected_kind and item.get("kind") != expected_kind:
        raise ProjectModelError("ref 类型不符合当前操作。")
    return item


def _endpoint_matches(item: dict[str, Any], endpoint: tuple[str, str | None]) -> bool:
    kind, category = endpoint
    if kind == "system":
        return item.get("kind") == "system"
    return item.get("kind") == kind and item.get("category") == category


def _relation_target_matches(item: dict[str, Any], spec: dict[str, Any]) -> bool:
    if "target" in spec:
        return _endpoint_matches(item, spec["target"])
    categories = spec.get("target_categories") or set()
    if item.get("kind") == "system":
        return "system" in categories
    return item.get("kind") == "foundation" and item.get("category") in categories


def _validate_domain_relation(
    model: dict[str, Any], *, relation_kind: str, source_ref: str, target_ref: str,
) -> None:
    """机械校验一条领域关系；不推断、不模糊匹配端点。"""
    spec = _DOMAIN_RELATION_SPECS.get(relation_kind)
    if spec is None:
        raise ProjectModelError(f"不支持的领域关系类型：{relation_kind}。")
    if source_ref == target_ref:
        raise ProjectModelError("关系两端不能指向同一对象。")
    source = _active_object(model, source_ref)
    target = _active_object(model, target_ref)
    if not _endpoint_matches(source, spec["source"]):
        raise ProjectModelError("领域关系起点类型不符合该关系类型。")
    if not _relation_target_matches(target, spec):
        raise ProjectModelError("领域关系终点类型不符合该关系类型。")


def _find_active_duplicate_edge(
    model: dict[str, Any], *, relation_kind: str, source_ref: str, target_ref: str,
) -> dict[str, Any] | None:
    for edge in model["dependencies"].values():
        if (
            not edge.get("tombstoned")
            and edge.get("relation_kind") == relation_kind
            and edge["source_ref"] == source_ref
            and edge["target_ref"] == target_ref
        ):
            return edge
    return None


def _managed_relation_kinds(item: dict[str, Any]) -> set[str]:
    """该对象作为起点可管理的领域关系类型集合。"""
    return {
        kind for kind, spec in _DOMAIN_RELATION_SPECS.items()
        if _endpoint_matches(item, spec["source"])
    }


def _reconcile_domain_relations(
    model: dict[str, Any],
    source_ref: str,
    requested: list[dict[str, Any]],
    next_rev: int,
) -> dict[str, list[str]]:
    """把作者提交的完整领域关系集合原子地对账到同一 mutation。

    - 只管理 source == source_ref 且 relation_kind 属于该对象可管理类型的边；
    - 绝不触碰 character_relationship / 未知类型 / 其他对象为起点的依赖；
    - 先整体校验再动模型；匹配的活动边保留稳定 ref；缺失边创建；
      移除的受管边 tombstone；未显式提供 data 时保留既有 data。
    """
    item = model["objects"][source_ref]
    managed = _managed_relation_kinds(item)
    seen: set[tuple[str, str]] = set()
    normalized: list[tuple[str, str, dict[str, Any] | None]] = []
    for index, entry in enumerate(requested):
        if not isinstance(entry, dict):
            raise ProjectModelError(f"领域关系请求[{index}] 必须是对象。")
        relation_kind = entry.get("relation_kind")
        target_ref = entry.get("target_ref")
        if relation_kind not in managed:
            raise ProjectModelError("领域关系类型不属于该记录可管理的关联。")
        if not isinstance(target_ref, str) or not target_ref.strip():
            raise ProjectModelError("领域关系必须提供明确的 target_ref。")
        _validate_domain_relation(
            model, relation_kind=relation_kind, source_ref=source_ref, target_ref=target_ref,
        )
        identity = (relation_kind, target_ref)
        if identity in seen:
            raise ProjectModelError("领域关系请求包含重复的关系。")
        seen.add(identity)
        data = entry.get("data")
        normalized.append((relation_kind, target_ref, data if data is not None else None))
    existing = {
        (edge["relation_kind"], edge["target_ref"]): edge_ref
        for edge_ref, edge in model["dependencies"].items()
        if not edge.get("tombstoned")
        and edge["source_ref"] == source_ref
        and edge.get("relation_kind") in managed
    }
    created: list[str] = []
    kept: list[str] = []
    updated: list[str] = []
    tombstoned: list[str] = []
    for relation_kind, target_ref, supplied_data in normalized:
        edge_ref = existing.get((relation_kind, target_ref))
        if edge_ref is not None:
            kept.append(edge_ref)
            if supplied_data is not None:
                edge = model["dependencies"][edge_ref]
                next_data = _validate_data(supplied_data)
                if edge.get("data") != next_data:
                    edge["data"] = next_data
                    edge["field_authority"] = _initial_field_authority(next_data, "author", next_rev)
                    edge["author_fields"] = sorted(
                        field for field in next_data if not _is_internal_data_field(field)
                    )
                    updated.append(edge_ref)
            continue
        edge_ref = _next_ref(model, "edge")
        edge_data = _validate_data(supplied_data)
        target_item = model["objects"][target_ref]
        # 任一端点是未来记录 → 关系也是未来；两端都当前才是当前。
        edge_state = (
            "future"
            if "future" in {item.get("material_state", "current"), target_item.get("material_state", "current")}
            else "current"
        )
        model["dependencies"][edge_ref] = {
            "ref": edge_ref,
            "source_ref": source_ref,
            "target_ref": target_ref,
            "relation_kind": relation_kind,
            "title": _DOMAIN_RELATION_SPECS[relation_kind]["title"],
            "material_state": edge_state,
            "data": edge_data,
            "field_authority": _initial_field_authority(edge_data, "author", next_rev),
            "author_fields": sorted(
                field for field in edge_data if not _is_internal_data_field(field)
            ),
            "tombstoned": False,
        }
        created.append(edge_ref)
    for identity, edge_ref in existing.items():
        if identity not in seen:
            edge = model["dependencies"][edge_ref]
            edge["tombstoned"] = True
            edge["tombstoned_at_rev"] = next_rev
            tombstoned.append(edge_ref)
    return {"created": created, "kept": kept, "updated": updated, "tombstoned": tombstoned}


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
    field_authority: str = "author",
    relations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create an explicit author workspace record without creating Canon.

    ``relations=None`` 保留既有领域关系；``relations=[...]`` 是作者提交的完整
    受管领域关系集合，与对象创建在同一次 _commit / 同一 model_rev 内对账。
    """
    if category not in _FOUNDATION_CATEGORIES:
        raise ProjectModelError("不支持的基础记录分类；自定义分类请使用 custom。")
    if not isinstance(title, str) or not title.strip():
        raise ProjectModelError("基础记录 title 不能为空。")
    if category == "custom" and (not isinstance(category_name, str) or not category_name.strip()):
        raise ProjectModelError("custom 基础记录必须提供 category_name。")
    if relations is not None and not isinstance(relations, list):
        raise ProjectModelError("relations 必须是列表或省略。")
    material_state = _validate_material_state(material_state)
    record_data = _validate_data(data)
    if category == "event":
        record_data = apply_deterministic_time_arithmetic(record_data)
    if field_authority not in {"author", "semantic", "confirmed_plan"}:
        raise ProjectModelError("field_authority 非法。")

    def mutate(model: dict[str, Any], next_rev: int) -> dict[str, Any]:
        ref = _next_ref(model, "obj")
        model["objects"][ref] = {
            "ref": ref,
            "kind": "foundation",
            "category": category,
            "category_name": category_name.strip() if isinstance(category_name, str) else None,
            "title": title.strip(),
            "material_state": material_state,
            "data": record_data,
            "field_authority": _initial_field_authority(record_data, field_authority, next_rev),
            "author_fields": sorted(
                field for field in record_data
                if field_authority == "author" and not _is_internal_data_field(field)
            ),
            "tombstoned": False,
        }
        detail: dict[str, Any] = {"ref": ref, "action": "created", "kind": "foundation"}
        if relations is not None:
            reconciled = _reconcile_domain_relations(model, ref, relations, next_rev)
            detail["relations"] = reconciled
        return detail

    return _commit(project_id, base_model_rev, "foundation.created", mutate)


def update_object(
    project_id: str,
    *,
    base_model_rev: int,
    ref: str,
    title: str | None = None,
    material_state: str | None = None,
    data: dict[str, Any] | None = None,
    field_authority: str = "author",
    relations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Edit an object in place; its opaque ref remains stable.

    ``relations=None`` 表示调用方未编辑关系集合 → 保留全部既有领域关系；
    ``relations=[...]`` 表示作者提交的完整受管关系集合，与字段编辑在同一次
    _commit / 同一 model_rev 内对账。
    """
    if title is not None and (not isinstance(title, str) or not title.strip()):
        raise ProjectModelError("title 不能为空。")
    if material_state is not None:
        _validate_material_state(material_state)
    if data is not None:
        data = _validate_data(data)
    if relations is not None and not isinstance(relations, list):
        raise ProjectModelError("relations 必须是列表或省略。")
    if field_authority not in {"author", "semantic", "confirmed_plan"}:
        raise ProjectModelError("field_authority 非法。")

    def mutate(model: dict[str, Any], next_rev: int) -> dict[str, Any]:
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
        next_data = data
        if data is not None and item.get("category") == "event":
            next_data = apply_deterministic_time_arithmetic(data)
        if next_data is not None and item.get("data") != next_data:
            before = copy.deepcopy(item.get("data"))
            item["data"] = next_data
            changes["data"] = {"before": before, "after": copy.deepcopy(next_data)}
            changed_fields = {
                field for field in set(before or {}) | set(next_data)
                if (before or {}).get(field, _UNSET) != next_data.get(field, _UNSET)
                and not _is_internal_data_field(field)
            }
            authority = item.setdefault("field_authority", {})
            for field in changed_fields:
                authority[field] = _authority_entry(field_authority, field, next_rev)
            item["author_fields"] = sorted(
                field for field, meta in authority.items()
                if isinstance(meta, dict) and meta.get("source") == "author"
            )
            changes["data"]["changed_fields"] = sorted(changed_fields)
        if relations is not None:
            reconciled = _reconcile_domain_relations(model, ref, relations, next_rev)
            if reconciled["created"] or reconciled["tombstoned"] or reconciled["updated"]:
                changes["relations"] = reconciled
        if not changes:
            raise ProjectModelError("编辑未产生任何实际变化。")
        return {"ref": ref, "action": "updated", "changes": changes}

    return _commit(project_id, base_model_rev, "object.updated", mutate)


def patch_object_data(
    project_id: str,
    *,
    base_model_rev: int,
    ref: str,
    patch: dict[str, Any],
    title: str | None = None,
    material_state: str | None = None,
    protect_author_model_rev: int | None = None,
    allow_dynamic_author_override: bool = False,
) -> dict[str, Any]:
    """Apply an evidence-backed semantic patch without overwriting author fields."""
    patch = _validate_data(patch)
    if not patch:
        raise ProjectModelError("语义补丁不能为空。")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        raise ProjectModelError("title 不能为空。")
    if material_state is not None:
        _validate_material_state(material_state)

    def mutate(model: dict[str, Any], next_rev: int) -> dict[str, Any]:
        item = _active_object(model, ref)
        current = copy.deepcopy(item.get("data") or {})
        author_fields = set(item.get("author_fields") or [])
        authority = item.setdefault("field_authority", {})
        applied: dict[str, Any] = {}
        skipped: list[str] = []
        for key, value in patch.items():
            meta = authority.get(key) if isinstance(authority.get(key), dict) else {}
            is_author = key in author_fields or meta.get("source") == "author"
            if is_author:
                same_change = (
                    protect_author_model_rev is not None
                    and meta.get("updated_model_rev") == protect_author_model_rev
                )
                dynamic = meta.get("scope", _field_scope(key)) == "dynamic"
                if same_change or not (allow_dynamic_author_override and dynamic):
                    skipped.append(key)
                    continue
            if current.get(key) != value:
                current[key] = copy.deepcopy(value)
                applied[key] = copy.deepcopy(value)
                if not _is_internal_data_field(key):
                    authority[key] = _authority_entry("semantic", key, next_rev)
                    author_fields.discard(key)
        title_changed = False
        if title is not None and item.get("title") != title.strip():
            item["title"] = title.strip()
            title_changed = True
        state_changed = False
        if material_state is not None and item.get("material_state") != material_state:
            item["material_state"] = material_state
            state_changed = True
        if not applied and not title_changed and not state_changed:
            raise ProjectModelError("语义补丁未产生变化；显式作者字段保持优先。")
        if item.get("category") == "event":
            current = apply_deterministic_time_arithmetic(current)
        item["data"] = current
        item["author_fields"] = sorted(author_fields)
        return {
            "ref": ref, "action": "semantic_patch", "applied_fields": sorted(applied),
            "skipped_author_fields": sorted(skipped),
        }

    return _commit(project_id, base_model_rev, "object.semantic_patch", mutate)


def tombstone_object(project_id: str, *, base_model_rev: int, ref: str) -> dict[str, Any]:
    """Retire an identity without removing it or permitting reuse."""
    def mutate(model: dict[str, Any], next_rev: int) -> dict[str, Any]:
        retired_edges = _tombstone_object_with_incident_edges(model, ref, next_rev)
        return {"ref": ref, "action": "tombstoned", "retired_dependency_refs": retired_edges}

    return _commit(project_id, base_model_rev, "object.tombstoned", mutate)


def restore_object(project_id: str, *, base_model_rev: int, ref: str) -> dict[str, Any]:
    """Restore the SAME tombstoned identity; never create a replacement.

    Deterministic: no AI/Agent involved.  Incident explicit edges retired by the
    same tombstone revision are restored together when both endpoints are active
    again, so relationships remain bound to the same stable refs.
    """
    def mutate(model: dict[str, Any], next_rev: int) -> dict[str, Any]:
        item = model["objects"].get(ref)
        if not isinstance(item, dict):
            raise ProjectModelError("未知或跨项目 ref，已拒绝。")
        if not item.get("tombstoned"):
            raise ProjectModelError("该记录处于活动状态，无需恢复。")
        item["tombstoned"] = False
        item.pop("tombstoned_at_rev", None)
        item["restored_at_rev"] = next_rev
        restored_edges: list[str] = []
        for entry in reversed(model["change_history"]):
            if entry.get("kind") != "object.tombstoned":
                continue
            detail = entry.get("detail") if isinstance(entry.get("detail"), dict) else {}
            if detail.get("ref") != ref:
                continue
            for edge_ref in detail.get("retired_dependency_refs") or []:
                edge = model["dependencies"].get(edge_ref)
                if (
                    isinstance(edge, dict)
                    and edge.get("tombstoned")
                    and edge.get("tombstoned_at_rev") == entry.get("model_rev")
                    and not model["objects"][edge["source_ref"]].get("tombstoned")
                    and not model["objects"][edge["target_ref"]].get("tombstoned")
                ):
                    edge["tombstoned"] = False
                    edge.pop("tombstoned_at_rev", None)
                    edge["restored_at_rev"] = next_rev
                    restored_edges.append(edge_ref)
            break
        return {"ref": ref, "action": "restored", "restored_dependency_refs": restored_edges}

    return _commit(project_id, base_model_rev, "object.restored", mutate)


def create_system(
    project_id: str,
    *,
    base_model_rev: int,
    title: str,
    definition: dict[str, Any],
    material_state: str = "current",
    field_authority: str = "author",
) -> dict[str, Any]:
    """Create a data-driven, author-defined system without a genre enum."""
    if not isinstance(title, str) or not title.strip():
        raise ProjectModelError("系统 title 不能为空。")
    definition = _validate_data(definition)
    material_state = _validate_material_state(material_state)
    if field_authority not in {"author", "semantic", "confirmed_plan"}:
        raise ProjectModelError("field_authority 非法。")

    def mutate(model: dict[str, Any], next_rev: int) -> dict[str, Any]:
        ref = _next_ref(model, "obj")
        model["objects"][ref] = {
            "ref": ref,
            "kind": "system",
            "title": title.strip(),
            "material_state": material_state,
            "data": definition,
            "field_authority": _initial_field_authority(definition, field_authority, next_rev),
            "author_fields": sorted(
                field for field in definition
                if field_authority == "author" and not _is_internal_data_field(field)
            ),
            "tombstoned": False,
        }
        return {"ref": ref, "action": "created", "kind": "system"}

    return _commit(project_id, base_model_rev, "system.created", mutate)


def set_story_bible_profile(
    project_id: str,
    *,
    base_model_rev: int,
    genre_tags: list[str],
    narrative_mode: str | None,
    active_modules: list[str],
    field_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Replace only project configuration; hidden modules never delete records."""
    if not isinstance(genre_tags, list) or any(
        not isinstance(tag, str) or not tag.strip() for tag in genre_tags
    ):
        raise ProjectModelError("genre_tags 必须是非空字符串列表。")
    if narrative_mode is not None and not isinstance(narrative_mode, str):
        raise ProjectModelError("narrative_mode 必须是字符串或 null。")
    if not isinstance(active_modules, list) or any(module not in _DOMAIN_MODULES for module in active_modules):
        raise ProjectModelError("active_modules 包含未知模块。")
    modules = list(dict.fromkeys([*DEFAULT_DOMAIN_MODULES, *active_modules]))
    config = _validate_data(field_config)
    profile = {
        "genre_tags": list(dict.fromkeys(tag.strip() for tag in genre_tags)),
        "narrative_mode": narrative_mode.strip() if isinstance(narrative_mode, str) and narrative_mode.strip() else None,
        "active_modules": modules,
        "field_config": config,
    }

    def mutate(model: dict[str, Any], _next_rev: int) -> dict[str, Any]:
        before = copy.deepcopy(model["story_bible_profile"])
        if before == profile:
            raise ProjectModelError("项目领域配置没有实际变化。")
        model["story_bible_profile"] = copy.deepcopy(profile)
        return {"action": "story_bible_profile.set", "before": before, "after": copy.deepcopy(profile)}

    return _commit(project_id, base_model_rev, "story_bible_profile.set", mutate)


def set_chapter_actual_result(
    project_id: str,
    *,
    base_model_rev: int,
    chapter_number: int,
    result: dict[str, Any],
    content_sha256: str,
    source_change_id: str,
    actual_word_count: int,
) -> dict[str, Any]:
    """Persist accepted-prose reality separately from the chapter fine outline."""
    if not isinstance(chapter_number, int) or isinstance(chapter_number, bool) or chapter_number < 1:
        raise ProjectModelError("chapter_number 必须是正整数。")
    result = _validate_data(result)
    unknown = set(result) - _CHAPTER_RESULT_FIELDS
    if unknown:
        raise ProjectModelError(f"章节实际结果包含未知字段：{', '.join(sorted(unknown))}。")
    if not isinstance(result.get("summary"), str) or not result["summary"].strip():
        raise ProjectModelError("章节实际结果 summary 不能为空。")
    if not isinstance(content_sha256, str) or len(content_sha256) != 64:
        raise ProjectModelError("章节实际结果 content_sha256 非法。")
    if not isinstance(source_change_id, str) or not source_change_id.strip():
        raise ProjectModelError("章节实际结果 source_change_id 不能为空。")
    if not isinstance(actual_word_count, int) or isinstance(actual_word_count, bool) or actual_word_count < 0:
        raise ProjectModelError("章节实际字数必须是非负整数。")

    def mutate(model: dict[str, Any], next_rev: int) -> dict[str, Any]:
        payload = copy.deepcopy(result)
        payload.update({
            "chapter_number": chapter_number,
            "content_sha256": content_sha256,
            "source_change_id": source_change_id.strip(),
            "updated_model_rev": next_rev,
        })
        before = copy.deepcopy(model["chapter_actual_results"].get(str(chapter_number)))
        model["chapter_actual_results"][str(chapter_number)] = payload
        for ref in model["length_plan"]["chapter_target_refs"]:
            item = model["objects"].get(ref)
            if isinstance(item, dict) and (item.get("data") or {}).get("chapter_number") == chapter_number:
                model["length_plan"]["actual_word_counts"][ref] = actual_word_count
                break
        return {"action": "chapter_actual_result.set", "chapter_number": chapter_number, "before": before}

    return _commit(project_id, base_model_rev, "chapter_actual_result.set", mutate)


def add_planning_impact_candidate(
    project_id: str,
    *,
    base_model_rev: int,
    chapter_number: int,
    summary: str,
    affected_refs: list[str] | None = None,
    source_change_id: str,
) -> dict[str, Any]:
    """Record a non-authoritative impact candidate without rewriting planning."""
    if not isinstance(summary, str) or not summary.strip():
        raise ProjectModelError("规划影响候选 summary 不能为空。")
    if not isinstance(chapter_number, int) or chapter_number < 1:
        raise ProjectModelError("规划影响候选 chapter_number 非法。")
    refs = affected_refs or []
    if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
        raise ProjectModelError("规划影响候选 affected_refs 非法。")

    def mutate(model: dict[str, Any], next_rev: int) -> dict[str, Any]:
        candidate = {
            "candidate_id": f"planning-impact-{next_rev:08d}",
            "chapter_number": chapter_number,
            "summary": summary.strip(),
            "affected_refs": list(dict.fromkeys(refs)),
            "source_change_id": source_change_id,
            "status": "pending_author",
        }
        model["planning_impact_candidates"].append(candidate)
        return {"action": "planning_impact_candidate.added", "candidate_id": candidate["candidate_id"]}

    return _commit(project_id, base_model_rev, "planning_impact_candidate.added", mutate)


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

    def normalize_entry(
        kind: str,
        entry: dict[str, Any],
        current: dict[str, Any] | None,
        stage_key_map: dict[str, str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
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
            if field not in {"ref", "title", "name", "label", "data", "client_key", "stage_key", "stage_ref"}:
                data[field] = copy.deepcopy(value)
        if kind == "length_stage":
            data.pop("client_key", None)
            target = data.get("target_words")
            if target is not None and (not isinstance(target, int) or target < 0):
                raise ProjectModelError("阶段 target_words 必须是非负整数。")
        else:
            minimum, maximum = data.get("min_words"), data.get("max_words")
            if not isinstance(minimum, int) or not isinstance(maximum, int) or minimum < 0 or maximum < minimum:
                raise ProjectModelError("章节目标必须提供合法 min_words/max_words。")
            raw_stage_key = entry.get("stage_key", entry.get("stage_ref", data.get("stage_ref")))
            data.pop("stage", None)
            data.pop("stage_key", None)
            if raw_stage_key in (None, ""):
                data.pop("stage_ref", None)
            else:
                if stage_key_map is None:
                    raise ProjectModelError("章节阶段关联无法解析。")
                if not isinstance(raw_stage_key, str) or raw_stage_key not in stage_key_map:
                    raise ProjectModelError("章节阶段关联引用了未知或非活动阶段。")
                data["stage_ref"] = stage_key_map[raw_stage_key]
        return title.strip(), data

    def reconcile_items(
        model: dict[str, Any], plan: dict[str, Any], key: str, kind: str,
        entries: list[dict[str, Any]], next_rev: int, stage_key_map: dict[str, str] | None = None,
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
                title, data = normalize_entry(kind, entry, None, stage_key_map)
                ref = _next_ref(model, "obj")
                model["objects"][ref] = {
                    "ref": ref, "kind": kind, "title": title, "material_state": "future",
                    "data": data,
                    "field_authority": _initial_field_authority(data, "author", next_rev),
                    "author_fields": sorted(
                        field for field in data if not _is_internal_data_field(field)
                    ),
                    "tombstoned": False,
                }
                object_changes.append({"ref": ref, "action": "created"})
            else:
                if not isinstance(ref, str) or ref in submitted_refs:
                    raise ProjectModelError("长度规划 ref 必须唯一且为字符串。")
                item = _active_object(model, ref, expected_kind=kind)
                if ref not in old_refs:
                    raise ProjectModelError("长度规划 ref 不属于当前项目的活动规划集合。")
                title, data = normalize_entry(kind, entry, item, stage_key_map)
                changes: dict[str, dict[str, Any]] = {}
                if item.get("title") != title:
                    changes["title"] = {"before": item.get("title"), "after": title}
                    item["title"] = title
                if item.get("data") != data:
                    before_data = copy.deepcopy(item.get("data") or {})
                    changed_fields = {
                        field for field in set(before_data) | set(data)
                        if before_data.get(field, _UNSET) != data.get(field, _UNSET)
                        and not _is_internal_data_field(field)
                    }
                    changes["data"] = {
                        "before": before_data, "after": copy.deepcopy(data),
                        "changed_fields": sorted(changed_fields),
                    }
                    item["data"] = data
                    authority = item.setdefault("field_authority", {})
                    for field in changed_fields:
                        authority[field] = _authority_entry("author", field, next_rev)
                    item["author_fields"] = sorted(
                        field for field, meta in authority.items()
                        if isinstance(meta, dict) and meta.get("source") == "author"
                    )
                if changes:
                    object_changes.append({"ref": ref, "action": "updated", "changes": changes})
            submitted_refs.add(ref)
            new_refs.append(ref)
            if kind == "length_stage":
                stage_key_map = stage_key_map if stage_key_map is not None else {}
                stage_key_map[ref] = ref
                client_key = entry.get("client_key")
                if client_key is not None:
                    if not isinstance(client_key, str) or not client_key.strip():
                        raise ProjectModelError("阶段 client_key 必须是非空字符串。")
                    if client_key in stage_key_map and stage_key_map[client_key] != ref:
                        raise ProjectModelError("阶段 client_key 重复。")
                    stage_key_map[client_key] = ref
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
        stage_key_map: dict[str, str] = {
            ref: ref
            for ref in plan.get("stage_refs", [])
            if ref in model.get("objects", {}) and not model["objects"][ref].get("tombstoned")
        }
        if total_target_words is not _UNSET and plan.get("total_target_words") != total_target_words:
            changed["total_target_words"] = {
                "before": plan.get("total_target_words"), "after": total_target_words,
            }
            plan["total_target_words"] = total_target_words
        if stages is not None:
            before = list(plan["stage_refs"])
            stage_key_map.clear()
            refs, object_changes = reconcile_items(model, plan, "stage_refs", "length_stage", stages, next_rev, stage_key_map)
            if before != refs or object_changes:
                changed["stages"] = {"before_refs": before, "after_refs": refs, "objects": object_changes}
        else:
            stage_key_map = {
                ref: ref
                for ref in plan.get("stage_refs", [])
                if ref in model.get("objects", {}) and not model["objects"][ref].get("tombstoned")
            }
        if chapter_targets is not None:
            before = list(plan["chapter_target_refs"])
            refs, object_changes = reconcile_items(model, plan, "chapter_target_refs", "chapter_target", chapter_targets, next_rev, stage_key_map)
            if before != refs or object_changes:
                changed["chapter_targets"] = {"before_refs": before, "after_refs": refs, "objects": object_changes}
        active_stage_refs = set(plan["stage_refs"])
        for ref in plan["chapter_target_refs"]:
            item = _active_object(model, ref, expected_kind="chapter_target")
            data = item.get("data") or {}
            stage_ref = data.get("stage_ref")
            if stage_ref is not None and stage_ref not in active_stage_refs:
                raise ProjectModelError("不能删除仍被章节规划引用的阶段；请先重新分配或设为未分卷。")
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
    field_authority: str = "author",
) -> dict[str, Any]:
    """Record one explicit direct dependency; no semantic inference is performed."""
    if not isinstance(relation_kind, str) or not relation_kind.strip():
        raise ProjectModelError("relation_kind 不能为空。")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        raise ProjectModelError("依赖 title 不能为空。")
    material_state = _validate_material_state(material_state)
    edge_data = _validate_data(data)
    if field_authority not in {"author", "semantic", "confirmed_plan"}:
        raise ProjectModelError("field_authority 非法。")

    def mutate(model: dict[str, Any], next_rev: int) -> dict[str, Any]:
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
            "field_authority": _initial_field_authority(edge_data, field_authority, next_rev),
            "author_fields": sorted(
                field for field in edge_data
                if field_authority == "author" and not _is_internal_data_field(field)
            ),
            "tombstoned": False,
        }
        return {"ref": edge_ref, "action": "created", "source_ref": source_ref, "target_ref": target_ref}

    return _commit(project_id, base_model_rev, "dependency.created", mutate)


def add_domain_dependency(
    project_id: str,
    *,
    base_model_rev: int,
    source_ref: str,
    target_ref: str,
    relation_kind: str,
    material_state: str = "current",
    data: dict[str, Any] | None = None,
    field_authority: str = "author",
) -> dict[str, Any]:
    """新增一条经中央领域关系规格校验的显式依赖（窄口径确认写入口）。

    复用既有 dependency ref 格式 / _commit / 重复检测 / field_authority 语义；
    不支持任意 relation_kind 的作者直写。
    """
    if relation_kind not in _DOMAIN_RELATION_SPECS:
        raise ProjectModelError(f"不支持的领域关系类型：{relation_kind}。")
    material_state = _validate_material_state(material_state)
    edge_data = _validate_data(data)
    if field_authority not in {"author", "semantic", "confirmed_plan"}:
        raise ProjectModelError("field_authority 非法。")

    def mutate(model: dict[str, Any], next_rev: int) -> dict[str, Any]:
        _validate_domain_relation(
            model, relation_kind=relation_kind, source_ref=source_ref, target_ref=target_ref,
        )
        duplicate = _find_active_duplicate_edge(
            model, relation_kind=relation_kind, source_ref=source_ref, target_ref=target_ref,
        )
        if duplicate is not None:
            raise ProjectModelError("相同的领域关系已存在，未重复创建。")
        edge_ref = _next_ref(model, "edge")
        model["dependencies"][edge_ref] = {
            "ref": edge_ref,
            "source_ref": source_ref,
            "target_ref": target_ref,
            "relation_kind": relation_kind,
            "title": _DOMAIN_RELATION_SPECS[relation_kind]["title"],
            "material_state": material_state,
            "data": edge_data,
            "field_authority": _initial_field_authority(edge_data, field_authority, next_rev),
            "author_fields": sorted(
                field for field in edge_data
                if field_authority == "author" and not _is_internal_data_field(field)
            ),
            "tombstoned": False,
        }
        return {
            "ref": edge_ref, "action": "created", "relation_kind": relation_kind,
            "source_ref": source_ref, "target_ref": target_ref,
        }

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
    field_authority: str = "author",
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
    if field_authority not in {"author", "semantic", "confirmed_plan"}:
        raise ProjectModelError("field_authority 非法。")

    def mutate(model: dict[str, Any], next_rev: int) -> dict[str, Any]:
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
        if data is not None and "data" in changes:
            before_data = changes["data"].get("before") or {}
            changed_fields = {
                field for field in set(before_data) | set(data)
                if before_data.get(field, _UNSET) != data.get(field, _UNSET)
                and not _is_internal_data_field(field)
            }
            authority = edge.setdefault("field_authority", {})
            for field in changed_fields:
                authority[field] = _authority_entry(field_authority, field, next_rev)
            edge["author_fields"] = sorted(
                field for field, meta in authority.items()
                if isinstance(meta, dict) and meta.get("source") == "author"
            )
            changes["data"]["changed_fields"] = sorted(changed_fields)
        if not changes:
            raise ProjectModelError("关系编辑未产生任何实际变化。")
        return {"ref": ref, "action": "updated", "changes": changes}

    return _commit(project_id, base_model_rev, "dependency.updated", mutate)


def patch_dependency_data(
    project_id: str,
    *,
    base_model_rev: int,
    ref: str,
    patch: dict[str, Any],
    title: str | None = None,
    protect_author_model_rev: int | None = None,
    allow_dynamic_author_override: bool = False,
) -> dict[str, Any]:
    patch = _validate_data(patch)
    if not patch:
        raise ProjectModelError("关系语义补丁不能为空。")

    def mutate(model: dict[str, Any], next_rev: int) -> dict[str, Any]:
        edge = model["dependencies"].get(ref)
        if not isinstance(edge, dict) or edge.get("tombstoned"):
            raise ProjectModelError("未知或已退役关系 ref。")
        current = copy.deepcopy(edge.get("data") or {})
        author_fields = set(edge.get("author_fields") or [])
        authority = edge.setdefault("field_authority", {})
        applied: dict[str, Any] = {}
        skipped: list[str] = []
        for key, value in patch.items():
            meta = authority.get(key) if isinstance(authority.get(key), dict) else {}
            is_author = key in author_fields or meta.get("source") == "author"
            if is_author:
                same_change = (
                    protect_author_model_rev is not None
                    and meta.get("updated_model_rev") == protect_author_model_rev
                )
                dynamic = meta.get("scope", _field_scope(key)) == "dynamic"
                if same_change or not (allow_dynamic_author_override and dynamic):
                    skipped.append(key)
                    continue
            if current.get(key) != value:
                current[key] = copy.deepcopy(value)
                applied[key] = copy.deepcopy(value)
                if not _is_internal_data_field(key):
                    authority[key] = _authority_entry("semantic", key, next_rev)
                    author_fields.discard(key)
        title_changed = isinstance(title, str) and title.strip() and edge.get("title") != title.strip()
        if not applied and not title_changed:
            raise ProjectModelError("关系语义补丁未产生变化；显式作者字段保持优先。")
        edge["data"] = current
        edge["author_fields"] = sorted(author_fields)
        if title_changed:
            edge["title"] = title.strip()
        return {
            "ref": ref, "action": "semantic_patch", "applied_fields": sorted(applied),
            "skipped_author_fields": sorted(skipped),
        }

    return _commit(project_id, base_model_rev, "dependency.semantic_patch", mutate)


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


def restore_dependency(project_id: str, *, base_model_rev: int, ref: str) -> dict[str, Any]:
    """Restore the SAME tombstoned dependency; endpoints must be active."""
    def mutate(model: dict[str, Any], next_rev: int) -> dict[str, Any]:
        edge = model["dependencies"].get(ref)
        if not isinstance(edge, dict):
            raise ProjectModelError("未知或跨项目依赖 ref，已拒绝。")
        if not edge.get("tombstoned"):
            raise ProjectModelError("该关系处于活动状态，无需恢复。")
        for endpoint in (edge["source_ref"], edge["target_ref"]):
            item = model["objects"].get(endpoint)
            if not isinstance(item, dict) or item.get("tombstoned"):
                raise ProjectModelError("关系两端人物仍处于退役状态，请先恢复人物。")
        edge["tombstoned"] = False
        edge.pop("tombstoned_at_rev", None)
        edge["restored_at_rev"] = next_rev
        return {"ref": ref, "action": "restored"}

    return _commit(project_id, base_model_rev, "dependency.restored", mutate)


def create_relationship(
    project_id: str,
    *,
    base_model_rev: int,
    source_ref: str,
    target_ref: str,
    label: str,
    material_state: str = "current",
    data: dict[str, Any] | None = None,
    field_authority: str = "author",
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
    if field_authority not in {"author", "semantic", "confirmed_plan"}:
        raise ProjectModelError("field_authority 非法。")

    def mutate(model: dict[str, Any], next_rev: int) -> dict[str, Any]:
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
            "field_authority": _initial_field_authority(relation_data, field_authority, next_rev),
            "author_fields": sorted(
                field for field in relation_data
                if field_authority == "author" and not _is_internal_data_field(field)
            ),
            "tombstoned": False,
        }
        return {"ref": edge_ref, "action": "created", "source_ref": source_ref, "target_ref": target_ref}

    return _commit(project_id, base_model_rev, "relationship.created", mutate)


def validate_planning_projection(value: Any) -> dict[str, Any]:
    """Strict, side-effect-free validation for the optional StoryPlan projection."""
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ProjectModelError("planning_projection 必须是对象。")
    collections = {
        "characters", "relationships", "settings", "systems", "locations", "organizations",
        "storylines", "events", "foreshadowing", "mystery_information", "chapter_changes",
    }
    allowed = collections | {"domain_profile"}
    unknown = set(value) - allowed
    if unknown:
        raise ProjectModelError(f"planning_projection 包含未知字段：{', '.join(sorted(unknown))}。")
    normalized: dict[str, Any] = {"domain_profile": None}
    profile = value.get("domain_profile")
    if profile is not None:
        if not isinstance(profile, dict):
            raise ProjectModelError("planning_projection.domain_profile 必须是对象。")
        unknown_profile = set(profile) - {"genre_tags", "narrative_mode", "active_modules", "field_config"}
        if unknown_profile:
            raise ProjectModelError("planning_projection.domain_profile 包含未知字段。")
        normalized["domain_profile"] = copy.deepcopy(profile)
    for key in sorted(collections):
        entries = value.get(key, [])
        if not isinstance(entries, list):
            raise ProjectModelError(f"planning_projection.{key} 必须是列表。")
        normalized[key] = []
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise ProjectModelError(f"planning_projection.{key}[{index}] 必须是对象。")
            item = copy.deepcopy(entry)
            if key == "relationships":
                if not isinstance(item.get("label"), str) or not item["label"].strip():
                    raise ProjectModelError("规划关系必须提供 label。")
                source_explicit = any(
                    isinstance(item.get(field), str) and item[field].strip()
                    for field in ("source_key", "source_ref")
                )
                target_explicit = any(
                    isinstance(item.get(field), str) and item[field].strip()
                    for field in ("target_key", "target_ref")
                )
                if not source_explicit or not target_explicit:
                    raise ProjectModelError("规划关系必须为 source/target 分别提供明确的 key 或 ref。")
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
    if not any(value for value in normalized.values()):
        return load_project_model(project_id)
    if not isinstance(source_ref, str) or not source_ref.strip():
        raise ProjectModelError("规划投影 source_ref 不能为空。")

    category_for = {
        "characters": "character",
        "settings": "world_setting",
        "locations": "location",
        "organizations": "organization_force",
        "storylines": "story_line",
        "events": "event",
        "foreshadowing": "promise_foreshadowing",
        "mystery_information": "mystery_information",
    }

    def mutate(model: dict[str, Any], next_rev: int) -> dict[str, Any]:
        key_to_ref: dict[str, str] = {}
        created_objects: list[str] = []
        created_edges: list[str] = []
        profile_change = None
        profile = normalized.get("domain_profile")
        if profile is not None:
            current = copy.deepcopy(model["story_bible_profile"])
            genre_tags = profile.get("genre_tags", current["genre_tags"])
            narrative_mode = profile.get("narrative_mode", current["narrative_mode"])
            modules = profile.get("active_modules", current["active_modules"])
            field_config = profile.get("field_config", current["field_config"])
            if (
                not isinstance(genre_tags, list)
                or any(not isinstance(tag, str) or not tag.strip() for tag in genre_tags)
                or narrative_mode is not None and not isinstance(narrative_mode, str)
                or not isinstance(modules, list)
                or any(module not in _DOMAIN_MODULES for module in modules)
                or not isinstance(field_config, dict)
            ):
                raise ProjectModelError("规划投影 domain_profile 非法。")
            next_profile = {
                "genre_tags": list(dict.fromkeys(tag.strip() for tag in genre_tags)),
                "narrative_mode": narrative_mode.strip() if isinstance(narrative_mode, str) and narrative_mode.strip() else None,
                "active_modules": list(dict.fromkeys([*DEFAULT_DOMAIN_MODULES, *modules])),
                "field_config": copy.deepcopy(field_config),
            }
            if next_profile != current:
                model["story_bible_profile"] = next_profile
                profile_change = {"before": current, "after": copy.deepcopy(next_profile)}
        for collection, category in category_for.items():
            for item in normalized[collection]:
                key = item["key"]
                if key in key_to_ref:
                    raise ProjectModelError(f"规划投影实体 key 重复：{key}。")
                ref = _next_ref(model, "obj")
                payload = {k: copy.deepcopy(v) for k, v in item.items() if k not in {"key", "title", "name"}}
                payload["planning_source_ref"] = source_ref.strip()
                if category == "event":
                    payload = apply_deterministic_time_arithmetic(payload)
                model["objects"][ref] = {
                    "ref": ref, "kind": "foundation", "category": category,
                    "category_name": None, "title": item["title"], "material_state": "future",
                    "data": payload,
                    "field_authority": _initial_field_authority(payload, "confirmed_plan", next_rev),
                    "author_fields": [], "tombstoned": False,
                }
                key_to_ref[key] = ref
                created_objects.append(ref)
        for item in normalized["systems"]:
            key = item["key"]
            if key in key_to_ref:
                raise ProjectModelError(f"规划投影实体 key 重复：{key}。")
            ref = _next_ref(model, "obj")
            payload = {k: copy.deepcopy(v) for k, v in item.items() if k not in {"key", "title", "name"}}
            payload["planning_source_ref"] = source_ref.strip()
            model["objects"][ref] = {
                "ref": ref, "kind": "system", "title": item["title"], "material_state": "future",
                "data": payload,
                "field_authority": _initial_field_authority(payload, "confirmed_plan", next_rev),
                "author_fields": [], "tombstoned": False,
            }
            key_to_ref[key] = ref
            created_objects.append(ref)
        for rel in normalized["relationships"]:
            source = key_to_ref.get(rel.get("source_key")) or rel.get("source_ref")
            target = key_to_ref.get(rel.get("target_key")) or rel.get("target_ref")
            if not source or not target:
                raise ProjectModelError("规划关系端点必须引用明确人物。")
            source_item = _active_object(model, source)
            target_item = _active_object(model, target)
            if source_item.get("category") != "character" or target_item.get("category") != "character":
                raise ProjectModelError("规划关系端点必须引用规划人物。")
            edge_ref = _next_ref(model, "edge")
            payload = {k: copy.deepcopy(v) for k, v in rel.items() if k not in {
                "source_key", "target_key", "source_ref", "target_ref", "label",
            }}
            payload["planning_source_ref"] = source_ref.strip()
            model["dependencies"][edge_ref] = {
                "ref": edge_ref, "source_ref": source, "target_ref": target,
                "relation_kind": "character_relationship", "title": rel["label"].strip(),
                "material_state": "future", "data": payload,
                "field_authority": _initial_field_authority(payload, "confirmed_plan", next_rev),
                "author_fields": [], "tombstoned": False,
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
                "material_state": "future", "data": payload,
                "field_authority": _initial_field_authority(payload, "confirmed_plan", next_rev),
                "author_fields": [], "tombstoned": False,
            }
            model["length_plan"]["chapter_target_refs"].append(ref)
            created_objects.append(ref)
        return {
            "action": "planning_projection.applied", "source_ref": source_ref.strip(),
            "created_object_refs": created_objects, "created_dependency_refs": created_edges,
            "profile_change": profile_change,
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
