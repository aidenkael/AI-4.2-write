# -*- coding: utf-8 -*-
"""One incremental semantic-settlement path for every author change source."""
from __future__ import annotations

import copy
import json
import threading
import uuid
from pathlib import Path
from typing import Any

from ai import runner as semantic_ai
from operations import author_edit
from operations import execution_audit as audit
from operations import project_model
from operations import qoder_bridge as bridge
from operations.project_snapshot import (
    ProjectSnapshotError,
    build_planning_impact_frontier,
    focused_task_context,
    get_project_snapshot,
)


NEEDS_CONFIG_PREFIX = "NEEDS_SEMANTIC_AI_CONFIG"
NEEDS_CONFIG_MESSAGE = '需要在“设置”中配置日常 AI 后才能同步语义状态。'
_ALLOWED_KINDS = {
    "character", "relationship", "event", "time", "foreshadowing",
    "setting", "location", "organization", "system", "storyline", "planning",
    "open_thread", "mystery_information",
}
_CATEGORY_FOR_KIND = {
    "character": "character", "event": "event", "time": "event",
    "foreshadowing": "promise_foreshadowing", "setting": "world_setting",
    "location": "location", "organization": "organization_force",
    "storyline": "story_line", "planning": "story_line",
    "open_thread": "promise_foreshadowing",
    "mystery_information": "mystery_information",
}
_ALLOWED_CLASSIFICATIONS = {"mechanically_certain", "ambiguous", "creative_optional"}
_ALLOWED_ACTIONS = {"create", "update", "retire"}
_CHARACTER_SUMMARY_FIELDS = {
    "one_line_intro", "visible_traits", "persona_core", "background_summary",
    "position_title", "power_rank", "current_state", "current_objective",
    "arc_stage", "speech_style", "behavior_anchors",
}

_TASK_TEMPLATE = """你是 Go Write 的增量语义结算执行器。只分析本次明确变更及给出的相关当前快照，不重写正文，不臆造绝对日期，不把未来规划当成已发生事实。

请识别人物状态、关系、已发生事件、时间语义、伏笔/承诺、世界/地点/组织状态、未解决线索和规划有效性后果。代码已经处理哈希、字数、章节、显式字段与引用；不要重复机械计数。

最终回复必须只有合法 JSON 对象，不要 markdown。结构：
{{
  "summary": "本次结算摘要",
  "consequences": [
    {{
      "classification": "mechanically_certain|ambiguous|creative_optional",
      "kind": "character|relationship|event|time|foreshadowing|setting|location|organization|storyline|planning|open_thread",
      "action": "create|update|retire",
      "target_ref": "更新/退役时的显式 ref；新建可为空",
      "title": "作者可读标题",
      "source_ref": "关系起点人物的显式 ref；非关系可为空",
      "target_character_ref": "关系终点人物的显式 ref；非关系可为空",
      "data": {{"只放本次文本明确支持的结构化字段": "值"}},
      "reason": "短理由"
    }}
  ],
  "chapter_actual_result": null,
  "planning_impact_candidate": null
}}

只有文本或作者显式字段直接支持、无需创造性选择的后果才能标 mechanically_certain。相对时间如“过了一年”保留 relative_duration/ordering，不得发明年份；只有同时存在明确 ISO 时间基点时，才可输出 base_story_time_anchor 与结构化 relative_duration={{"value": 数值, "unit": "minutes|hours|days|weeks"}}，最终时间由代码计算。含歧义的解释标 ambiguous；文学选择标 creative_optional。关系端点必须使用快照中的明确人物 ref，绝不按名称猜测。人物摘要更新只允许 one_line_intro / visible_traits / persona_core / background_summary / position_title / power_rank / current_state / current_objective / arc_stage / speech_style / behavior_anchors 中本次证据支持的字段。

若本次是正文变更，chapter_actual_result 必须是对象，包含 summary，并可包含 important_events / characters_involved / character_state_changes / relationship_changes / time_movement / location_state_changes / information_revealed / foreshadowing_planted_paid_off / unresolved_threads / final_chapter_state / outline_divergence；它描述正文现实，不复写细纲。非正文变更填 null。只有正文与细纲存在实质偏差且会影响未来规划时，planning_impact_candidate 才填 {{"summary":"简短影响","affected_refs":[]}}；否则填 null，绝不直接改未来规划。

本次变更：
{change}

相关当前快照：
{snapshot}
"""

_BATCH_TASK_TEMPLATE = """你是 Go Write 的作品状态整理器。作者已经明确保存了下列修改；只读取其中每个目标的最新当前真相，不重放中间编辑，也不重读全书。

作者内容和手工结构化记录优先于旧派生状态。不要臆造事实、日期、人物端点或未来已发生事项；未来规划只能提出候选，绝不直接改写。代码已经处理哈希、字数、章节、结构投影和作者字段保护。

最终回复必须只有一个合法 JSON 对象：
{{
  "summary": "给作者的简短整理摘要",
  "consequences": [
    {{"classification":"mechanically_certain|ambiguous|creative_optional","kind":"character|relationship|event|time|foreshadowing|setting|location|organization|system|storyline|planning|open_thread|mystery_information","action":"create|update|retire","target_ref":"更新或退役的明确 ref；新建可为空","title":"作者可读标题","source_ref":"关系起点 ref；非关系可为空","target_character_ref":"关系终点 ref；非关系可为空","source_change_ids":["支撑本条后果的账本变更 id"],"data":{{}},"reason":"短理由"}}
  ],
  "chapter_actual_results": [{{"chapter_number": 12, "result": {{"summary":"正文实际结果摘要"}}, "planning_impact_candidate": null}}],
  "planning_impact_candidates": [
    {{"summary":"作者可读的影响描述","source_change_ids":["触发该影响的账本变更 id"],"affected_refs":[],"affected_chapter_numbers":[],"affected_stage_refs":[]}}
  ]
}}

只有当前输入直接支持且无需创作选择的后果才是 mechanically_certain。关系端点必须使用输入中已有的明确人物 ref。人物更新只允许 one_line_intro、visible_traits、persona_core、background_summary、position_title、power_rank、current_state、current_objective、arc_stage、speech_style、behavior_anchors。正文实际结果只对应输入中列出的正文章节。

每条 consequence 的 source_change_ids 必须非空，且只能从下方受影响目标列出的账本变更 id 中选择：每条后果必须可追溯到真实支撑它的作者变更；没有真实正文变更支撑时，绝不允许以正文名义推进作者拥有的字段。

planning_impact_candidates：当且仅当本次作者变更实质影响后续规划时才给出；只基于下方给出的确定性影响前沿与当前快照判断，绝不自行遍历全书。每条的 affected_refs / affected_chapter_numbers / affected_stage_refs 只能从输入中真实存在的未来记录、章节号与阶段中选择；不确定的影响不要列出；无影响时给空列表。绝不直接修改任何规划。

本轮合并后的受影响目标（每项列出覆盖的账本变更 id）：
{affected}

确定性规划影响前沿（代码从显式依赖/轨迹/故事线/伏笔/章节目标/同阶段后续章收集；只作候选输入）：
{frontier}

当前作品快照（只为校验和理解，不得以旧派生内容覆盖上述作者真相）：
{snapshot}
"""


class ChangeSettlementError(Exception):
    """Safe semantic-settlement failure exposed to the author workbench."""


def _parse_output(output: str, *, require_source_change_ids: bool = False) -> dict[str, Any]:
    text = (output or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ChangeSettlementError("语义结算结果不是合法 JSON。") from exc
    if not isinstance(value, dict) or not isinstance(value.get("summary"), str):
        raise ChangeSettlementError("语义结算结果缺少 summary。")
    consequences = value.get("consequences")
    if not isinstance(consequences, list):
        raise ChangeSettlementError("语义结算结果 consequences 必须是列表。")
    normalized = []
    for index, item in enumerate(consequences):
        if not isinstance(item, dict):
            raise ChangeSettlementError(f"consequences[{index}] 必须是对象。")
        classification = item.get("classification")
        kind = item.get("kind")
        action = item.get("action")
        if classification not in _ALLOWED_CLASSIFICATIONS:
            raise ChangeSettlementError(f"consequences[{index}].classification 非法。")
        if kind not in _ALLOWED_KINDS:
            raise ChangeSettlementError(f"consequences[{index}].kind 非法。")
        if action not in _ALLOWED_ACTIONS:
            raise ChangeSettlementError(f"consequences[{index}].action 非法。")
        if not isinstance(item.get("title"), str) or not item["title"].strip():
            raise ChangeSettlementError(f"consequences[{index}].title 不能为空。")
        if not isinstance(item.get("data", {}), dict):
            raise ChangeSettlementError(f"consequences[{index}].data 必须是对象。")
        if action in {"update", "retire"} and (
            not isinstance(item.get("target_ref"), str) or not item["target_ref"].strip()
        ):
            raise ChangeSettlementError(f"consequences[{index}] 更新/退役缺少 target_ref。")
        if kind == "relationship" and (
            not isinstance(item.get("source_ref"), str)
            or not item["source_ref"].strip()
            or not isinstance(item.get("target_character_ref"), str)
            or not item["target_character_ref"].strip()
        ):
            raise ChangeSettlementError(f"consequences[{index}] 关系缺少明确人物端点 ref。")
        if kind == "character" and action == "update":
            unknown_fields = set(item.get("data", {})) - _CHARACTER_SUMMARY_FIELDS
            if unknown_fields:
                raise ChangeSettlementError(
                    f"consequences[{index}] 人物摘要补丁包含不允许字段：{', '.join(sorted(unknown_fields))}。"
                )
        if require_source_change_ids:
            source_ids = item.get("source_change_ids")
            if (
                not isinstance(source_ids, list) or not source_ids
                or any(not isinstance(change_id, str) or not change_id.strip() for change_id in source_ids)
            ):
                raise ChangeSettlementError(
                    f"consequences[{index}] 缺少合法的 source_change_ids；每条后果必须可追溯到已捕获的作者变更。"
                )
            item["source_change_ids"] = list(dict.fromkeys(source_ids))
        normalized.append(copy.deepcopy(item))
    chapter_result = value.get("chapter_actual_result")
    if chapter_result is not None:
        if not isinstance(chapter_result, dict) or not isinstance(chapter_result.get("summary"), str):
            raise ChangeSettlementError("chapter_actual_result 必须包含 summary。")
        unknown = set(chapter_result) - project_model._CHAPTER_RESULT_FIELDS
        if unknown:
            raise ChangeSettlementError("chapter_actual_result 包含未知字段。")
    planning_impact = value.get("planning_impact_candidate")
    if planning_impact is not None:
        if (
            not isinstance(planning_impact, dict)
            or not isinstance(planning_impact.get("summary"), str)
            or not isinstance(planning_impact.get("affected_refs", []), list)
        ):
            raise ChangeSettlementError("planning_impact_candidate 结构非法。")
    return {
        "summary": value["summary"].strip(), "consequences": normalized,
        "chapter_actual_result": copy.deepcopy(chapter_result),
        "planning_impact_candidate": copy.deepcopy(planning_impact),
    }


def _model_artifact(project_id: str) -> Path:
    snapshot = get_project_snapshot(project_id)
    return Path(snapshot["identity"]["project_dir"]) / "_工作台状态" / project_model.ARTIFACT_NAME


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    # Reuse the project model's proven atomic writer through a validated JSON value.
    value = json.loads(payload.decode("utf-8"))
    project_model._atomic_write_json(path, value)


def _restore_model(path: Path, before: bytes | None) -> None:
    if before is None:
        if path.exists():
            path.unlink()
    else:
        _write_bytes_atomic(path, before)


def _find_snapshot_record(snapshot: dict[str, Any], ref: str) -> dict[str, Any] | None:
    for bucket_name in ("current", "future"):
        for records in snapshot[bucket_name].values():
            for record in records:
                if record.get("ref") == ref:
                    return record
    return None


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
        raise ChangeSettlementError("关系端点 ref 不是人物记录。")
    source = _find_snapshot_record(snapshot, ref)
    if not source or source.get("source_kind") != "production_story_state":
        raise ChangeSettlementError("关系端点无法对应到明确人物 ref。")
    data = copy.deepcopy(source.get("record") if isinstance(source.get("record"), dict) else {})
    data["source_state_ref"] = ref
    next_model = project_model.create_foundation_record(
        project_id,
        base_model_rev=model["model_rev"],
        category="character",
        title=source.get("title") or "未命名人物",
        material_state="current",
        data=data,
    )
    created_ref = next_model["change_history"][-1]["detail"]["ref"]
    return next_model, created_ref


def _allowed_semantic_patch(
    record: dict[str, Any],
    patch: dict[str, Any],
    *,
    protect_author_model_revs: set[int] | frozenset[int] | None,
    allow_dynamic_author_override: bool,
    dynamic_override_max_rev: int | None = None,
) -> dict[str, Any]:
    """Mirror the project-model authority gate without creating a no-op revision."""
    current = record.get("data") if isinstance(record.get("data"), dict) else {}
    author_fields = set(record.get("author_fields") or [])
    authority = record.get("field_authority") if isinstance(record.get("field_authority"), dict) else {}
    allowed: dict[str, Any] = {}
    for key, value in patch.items():
        meta = authority.get(key) if isinstance(authority.get(key), dict) else {}
        is_author = key in author_fields or meta.get("source") == "author"
        if project_model._skip_author_patch_field(
            meta, is_author=is_author, key=key,
            protect_author_model_revs=protect_author_model_revs,
            allow_dynamic_author_override=allow_dynamic_author_override,
            dynamic_override_max_rev=dynamic_override_max_rev,
        ):
            continue
        if key not in current or current.get(key) != value:
            allowed[key] = copy.deepcopy(value)
    return allowed


def _author_owned(obj: dict[str, Any]) -> bool:
    authority = obj.get("field_authority") if isinstance(obj.get("field_authority"), dict) else {}
    return any(isinstance(meta, dict) and meta.get("source") == "author" for meta in authority.values())


def _needs_author_gate(model: dict[str, Any], item: dict[str, Any]) -> bool:
    """mechanically_certain 但触及作者主权的后果必须改走作者确认。

    - 退役作者拥有的活动记录：AI 不得机械退役作者主权条目；
    - 在作者拥有的同名活动记录之上创建重复记录：AI 不得机械复制作者条目。
    两者都转入 undecided，由作者经既有 awaiting_author/confirm 合同明确选择。
    """
    action = item.get("action")
    target_ref = item.get("target_ref")
    if action == "retire" and isinstance(target_ref, str):
        obj = model.get("objects", {}).get(target_ref)
        if isinstance(obj, dict) and not obj.get("tombstoned") and _author_owned(obj):
            return True
    if action == "create":
        category = _CATEGORY_FOR_KIND.get(str(item.get("kind") or ""))
        title = str(item.get("title") or "").strip()
        if category and title:
            for obj in model.get("objects", {}).values():
                if (
                    isinstance(obj, dict) and not obj.get("tombstoned")
                    and obj.get("category") == category
                    and str(obj.get("title") or "").strip() == title
                    and _author_owned(obj)
                ):
                    return True
    return False


def _apply_one(
    project_id: str,
    model: dict[str, Any],
    snapshot: dict[str, Any],
    item: dict[str, Any],
    *,
    author_confirmed: bool = False,
    source_model_rev: int | None = None,
    source_model_revs: set[int] | frozenset[int] | None = None,
    source_kind: str | None = None,
    dynamic_override_max_rev: int | None = None,
) -> dict[str, Any]:
    if item["classification"] != "mechanically_certain" and not author_confirmed:
        return model
    protect_revs = source_model_revs
    if protect_revs is None and source_model_rev is not None:
        protect_revs = {source_model_rev}
    data = copy.deepcopy(item.get("data") or {})
    data["settlement_provenance"] = "author_confirmed" if author_confirmed else "semantic_mechanical"
    action = item["action"]
    kind = item["kind"]
    target_ref = item.get("target_ref")
    if kind == "relationship":
        model, source_ref = _ensure_model_character(project_id, model, snapshot, item["source_ref"])
        model, target_character_ref = _ensure_model_character(
            project_id, model, snapshot, item["target_character_ref"],
        )
        if action == "create":
            return project_model.create_relationship(
                project_id, base_model_rev=model["model_rev"], source_ref=source_ref,
                target_ref=target_character_ref, label=item["title"], material_state="current", data=data,
                field_authority="semantic",
            )
        if not isinstance(target_ref, str):
            raise ChangeSettlementError("关系更新/退役 target_ref 不是活动关系。")
        existing_edge = model.get("dependencies", {}).get(target_ref)
        if not isinstance(existing_edge, dict) or existing_edge.get("tombstoned"):
            source_relation = author_edit._snapshot_record(snapshot, target_ref, relationship=True)
            if not source_relation or source_relation.get("source_kind") != "production_story_state":
                raise ChangeSettlementError("关系更新/退役 target_ref 不是活动关系。")
            if action == "retire" and not author_confirmed:
                raise ChangeSettlementError("正式 Story State 关系的退役必须由作者明确确认。")
            overlay_data = author_edit._overlay_data(source_relation, data)
            model = project_model.create_relationship(
                project_id, base_model_rev=model["model_rev"], source_ref=source_ref,
                target_ref=target_character_ref, label=item["title"],
                material_state="current", data=overlay_data, field_authority="semantic",
            )
            if action == "update":
                return model
            marker_ref = model["change_history"][-1]["detail"]["ref"]
            return project_model.tombstone_dependency(
                project_id, base_model_rev=model["model_rev"], ref=marker_ref,
            )
        if action == "update":
            edge = model["dependencies"][target_ref]
            allow_dynamic = source_kind in {"manual_prose_edit", "accepted_ai_prose"}
            allowed = _allowed_semantic_patch(
                edge, data, protect_author_model_revs=protect_revs,
                allow_dynamic_author_override=allow_dynamic,
                dynamic_override_max_rev=dynamic_override_max_rev,
            )
            if not allowed:
                return model
            return project_model.patch_dependency_data(
                project_id, base_model_rev=model["model_rev"], ref=target_ref, patch=allowed,
                protect_author_model_revs=protect_revs,
                allow_dynamic_author_override=allow_dynamic,
                dynamic_override_max_rev=dynamic_override_max_rev,
            )
        return project_model.tombstone_dependency(
            project_id, base_model_rev=model["model_rev"], ref=target_ref,
        )

    category = _CATEGORY_FOR_KIND.get(kind)
    if kind == "time":
        data["time_semantics"] = True
    material_state = "future" if kind == "planning" else "current"
    if action == "create":
        if kind == "system":
            return project_model.create_system(
                project_id, base_model_rev=model["model_rev"], title=item["title"],
                material_state=material_state, definition=data, field_authority="semantic",
            )
        if category is None:
            raise ChangeSettlementError("语义后果 kind 无法映射到领域对象。")
        return project_model.create_foundation_record(
            project_id, base_model_rev=model["model_rev"], category=category,
            title=item["title"], material_state=material_state, data=data,
            field_authority="semantic",
        )
    if isinstance(target_ref, str) and target_ref in model.get("objects", {}):
        target = model["objects"][target_ref]
        # Author edits apply tombstones deterministically before semantic
        # refresh.  The model may faithfully repeat that same retirement;
        # treating it as idempotent keeps a valid refresh from failing while
        # preserving all non-idempotent update/retire guards below.
        if action == "retire" and target.get("tombstoned"):
            return model
        if action == "update":
            allow_dynamic = source_kind in {"manual_prose_edit", "accepted_ai_prose"}
            allowed = _allowed_semantic_patch(
                target, data, protect_author_model_revs=protect_revs,
                allow_dynamic_author_override=allow_dynamic,
                dynamic_override_max_rev=dynamic_override_max_rev,
            )
            if not allowed:
                return model
            return project_model.patch_object_data(
                project_id, base_model_rev=model["model_rev"], ref=target_ref,
                patch=allowed, material_state=material_state,
                protect_author_model_revs=protect_revs,
                allow_dynamic_author_override=allow_dynamic,
                dynamic_override_max_rev=dynamic_override_max_rev,
            )
        return project_model.tombstone_object(
            project_id, base_model_rev=model["model_rev"], ref=target_ref,
        )
    source = _find_snapshot_record(snapshot, str(target_ref or ""))
    if not source or source.get("source_kind") != "production_story_state":
        raise ChangeSettlementError("后果 target_ref 无法对应当前有效记录。")
    if action == "retire":
        if not author_confirmed:
            # A retirement of production Story State is never mechanically
            # safe at the overlay boundary; it needs explicit author choice.
            raise ChangeSettlementError("正式 Story State 条目的退役必须由作者明确确认。")
        marker_data = author_edit._overlay_data(source, data)
        model = project_model.create_foundation_record(
            project_id, base_model_rev=model["model_rev"], category=category,
            title=item["title"], material_state=material_state, data=marker_data,
            field_authority="semantic",
        )
        marker_ref = model["change_history"][-1]["detail"]["ref"]
        return project_model.tombstone_object(
            project_id, base_model_rev=model["model_rev"], ref=marker_ref,
        )
    data["supersedes_state_ref"] = target_ref
    return project_model.create_foundation_record(
        project_id, base_model_rev=model["model_rev"], category=category,
        title=item["title"], material_state="current", data=data,
        field_authority="semantic",
    )


def apply_semantic_result(
    project_id: str,
    change_id: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    parsed = _parse_output(json.dumps(result, ensure_ascii=False)) if "summary" in result else result
    change_before = author_edit.get_change(project_id, change_id)
    if not change_before.get("requires_semantic"):
        raise ChangeSettlementError("这条变更不需要语义同步。")
    if change_before.get("status") not in {"pending", "failed"}:
        raise ChangeSettlementError("这条变更当前不能重复执行语义同步。")
    snapshot = get_project_snapshot(project_id)
    model = project_model.load_project_model(project_id)
    model_path = _model_artifact(project_id)
    before = model_path.read_bytes() if model_path.exists() else None
    mechanical = []
    undecided = [item for item in parsed["consequences"] if item["classification"] != "mechanically_certain"]
    for item in parsed["consequences"]:
        if item["classification"] != "mechanically_certain":
            continue
        if _needs_author_gate(model, item):
            undecided.append(item)
        else:
            mechanical.append(item)
    try:
        for item in mechanical:
            model = _apply_one(
                project_id, model, snapshot, item,
                source_model_rev=change_before.get("source_model_rev"),
                source_kind=change_before.get("source_kind"),
            )
        chapter_result = parsed.get("chapter_actual_result")
        if chapter_result is not None:
            if change_before.get("source_kind") not in {"manual_prose_edit", "accepted_ai_prose"}:
                raise ChangeSettlementError("非正文变更不能写入章节实际结果。")
            delta = change_before.get("delta") if isinstance(change_before.get("delta"), dict) else {}
            chapter_number = delta.get("chapter_number")
            chapter = next(
                (item for item in snapshot["chapters"] if item["chapter_number"] == chapter_number),
                None,
            )
            if not isinstance(chapter_number, int) or chapter is None:
                raise ChangeSettlementError("正文变更缺少有效章节身份。")
            content_sha256 = delta.get("after_sha256") or chapter.get("content_sha256")
            model = project_model.set_chapter_actual_result(
                project_id, base_model_rev=model["model_rev"], chapter_number=chapter_number,
                result=chapter_result, content_sha256=content_sha256,
                source_change_id=change_id, actual_word_count=chapter["actual_words"],
            )
            impact = parsed.get("planning_impact_candidate")
            if impact is not None:
                model = project_model.add_planning_impact_candidate(
                    project_id, base_model_rev=model["model_rev"], chapter_number=chapter_number,
                    summary=impact["summary"], affected_refs=impact.get("affected_refs") or [],
                    source_change_id=change_id,
                )
        elif parsed.get("planning_impact_candidate") is not None:
            raise ChangeSettlementError("规划影响候选必须绑定章节实际结果。")
    except (project_model.ProjectModelError, ChangeSettlementError, OSError) as exc:
        try:
            _restore_model(model_path, before)
        except OSError as rollback_exc:
            raise ChangeSettlementError(f"语义结算失败且项目模型回滚未完成：{rollback_exc}") from exc
        author_edit.update_change(
            project_id, change_id, status="failed", semantic=parsed, error=str(exc),
        )
        raise ChangeSettlementError(str(exc)) from exc
    status = "awaiting_author" if undecided else "synchronized"
    try:
        change = author_edit.update_change(
            project_id, change_id, status=status, semantic=parsed, error=None,
        )
    except (author_edit.AuthorEditError, OSError) as exc:
        try:
            _restore_model(model_path, before)
        except OSError as rollback_exc:
            raise ChangeSettlementError(f"语义结算记账失败且项目模型回滚未完成：{rollback_exc}") from exc
        raise ChangeSettlementError(f"语义结算记账失败，项目模型已回滚：{exc}") from exc
    return {
        "project_id": project_id, "change_id": change_id, "status": status,
        "mechanical_count": len(mechanical), "undecided_count": len(undecided),
        "change": change,
    }


_REFRESH_WORKERS_GUARD = threading.Lock()
_REFRESH_WORKERS: dict[str, threading.Thread] = {}


def _refresh_worker_active(project_id: str) -> bool:
    with _REFRESH_WORKERS_GUARD:
        worker = _REFRESH_WORKERS.get(project_id)
        return bool(worker and worker.is_alive())


def _refresh_key(change: dict[str, Any]) -> str:
    """Stable target key used only to coalesce obsolete intermediate saves."""
    delta = change.get("delta") if isinstance(change.get("delta"), dict) else {}
    chapter = delta.get("chapter_number")
    if change.get("source_kind") in {"manual_prose_edit", "accepted_ai_prose"} and isinstance(chapter, int):
        return f"prose:{chapter}"
    model_change = delta.get("project_model_change") if isinstance(delta.get("project_model_change"), dict) else {}
    detail = model_change.get("detail") if isinstance(model_change.get("detail"), dict) else model_change
    ref = detail.get("ref") if isinstance(detail, dict) else None
    if isinstance(ref, str) and ref:
        return f"record:{ref}"
    return f"{change.get('source_kind') or 'change'}:{chapter if isinstance(chapter, int) else 'project'}"


def _capture_refresh(project_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Capture a cutoff and coalesced latest inputs while holding only the write lock."""
    with author_edit.project_write_lock(project_id):
        ledger = author_edit.get_change_ledger(project_id)
        state = author_edit.get_state_refresh(project_id)
        if state.get("status") == "running" and _refresh_worker_active(project_id):
            return state, []
        cutoff = int(ledger.get("sequence") or 0)
        # 捕获截止点的模型版本：后续正文推进不得触碰截止点之后的作者字段。
        cutoff_model_rev = project_model.read_project_model(project_id)["model_rev"]
        eligible = [
            copy.deepcopy(item) for item in ledger.get("changes", [])
            if isinstance(item, dict)
            and item.get("requires_semantic")
            and item.get("status") in {"pending", "failed"}
            and isinstance(item.get("sequence"), int)
            and item["sequence"] <= cutoff
        ]
        refresh_id = uuid.uuid4().hex
        next_state = {
            "status": "running" if eligible else "synchronized",
            "refresh_id": refresh_id,
            "cutoff_sequence": cutoff,
            "cutoff_model_rev": cutoff_model_rev,
            "change_ids": [str(item["change_id"]) for item in eligible],
            "summary": "正在整理作品状态。" if eligible else "作品状态已是最新。",
            "error": None,
            "proposals": [],
            "result": None,
        }
        author_edit.update_changes_and_state_refresh(project_id, state_refresh=next_state)
    latest: dict[str, dict[str, Any]] = {}
    for item in eligible:
        key = _refresh_key(item)
        existing = latest.get(key)
        if existing is None:
            latest[key] = {"latest": item, "change_ids": [str(item["change_id"])]}
        else:
            existing["latest"] = item
            existing["change_ids"].append(str(item["change_id"]))
    return next_state, list(latest.values())


def _parse_refresh_output(output: str) -> dict[str, Any]:
    """Strictly normalize the bounded refresh envelope into existing patch rules."""
    text = (output or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if len(lines) >= 2 else lines).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ChangeSettlementError("作品状态整理结果不是合法 JSON。") from exc
    if not isinstance(value, dict) or not isinstance(value.get("summary"), str):
        raise ChangeSettlementError("作品状态整理结果缺少 summary。")
    base = _parse_output(json.dumps({
        "summary": value["summary"],
        "consequences": value.get("consequences"),
        "chapter_actual_result": None,
        "planning_impact_candidate": None,
    }, ensure_ascii=False), require_source_change_ids=True)
    outcomes = value.get("chapter_actual_results", [])
    if not isinstance(outcomes, list):
        raise ChangeSettlementError("chapter_actual_results 必须是列表。")
    normalized_outcomes = []
    for index, item in enumerate(outcomes):
        if not isinstance(item, dict) or not isinstance(item.get("chapter_number"), int):
            raise ChangeSettlementError(f"chapter_actual_results[{index}] 缺少合法 chapter_number。")
        result = _parse_output(json.dumps({
            "summary": value["summary"], "consequences": [],
            "chapter_actual_result": item.get("result"),
            "planning_impact_candidate": item.get("planning_impact_candidate"),
        }, ensure_ascii=False))
        normalized_outcomes.append({
            "chapter_number": item["chapter_number"],
            "result": result["chapter_actual_result"],
            "planning_impact_candidate": result["planning_impact_candidate"],
        })
    impacts = value.get("planning_impact_candidates", [])
    if not isinstance(impacts, list):
        raise ChangeSettlementError("planning_impact_candidates 必须是列表。")
    normalized_impacts = []
    for index, item in enumerate(impacts):
        if not isinstance(item, dict):
            raise ChangeSettlementError(f"planning_impact_candidates[{index}] 必须是对象。")
        summary = item.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise ChangeSettlementError(f"planning_impact_candidates[{index}].summary 不能为空。")
        source_ids = item.get("source_change_ids")
        if (
            not isinstance(source_ids, list) or not source_ids
            or any(not isinstance(change_id, str) or not change_id.strip() for change_id in source_ids)
        ):
            raise ChangeSettlementError(
                f"planning_impact_candidates[{index}] 必须绑定非空的 source_change_ids。"
            )
        affected_refs = item.get("affected_refs", [])
        affected_chapters = item.get("affected_chapter_numbers", [])
        affected_stages = item.get("affected_stage_refs", [])
        if not isinstance(affected_refs, list) or any(not isinstance(ref, str) for ref in affected_refs):
            raise ChangeSettlementError(f"planning_impact_candidates[{index}].affected_refs 非法。")
        if not isinstance(affected_chapters, list) or any(
            not isinstance(number, int) or isinstance(number, bool) or number < 1
            for number in affected_chapters
        ):
            raise ChangeSettlementError(f"planning_impact_candidates[{index}].affected_chapter_numbers 非法。")
        if not isinstance(affected_stages, list) or any(not isinstance(ref, str) for ref in affected_stages):
            raise ChangeSettlementError(f"planning_impact_candidates[{index}].affected_stage_refs 非法。")
        normalized_impacts.append({
            "summary": summary.strip(),
            "source_change_ids": list(dict.fromkeys(source_ids)),
            "affected_refs": list(dict.fromkeys(ref.strip() for ref in affected_refs if ref.strip())),
            "affected_chapter_numbers": sorted(set(affected_chapters)),
            "affected_stage_refs": list(dict.fromkeys(ref.strip() for ref in affected_stages if ref.strip())),
        })
    return {
        "summary": base["summary"], "consequences": base["consequences"],
        "chapter_actual_results": normalized_outcomes,
        "planning_impact_candidates": normalized_impacts,
    }


def _apply_refresh_result(
    project_id: str, refresh: dict[str, Any], captured: list[dict[str, Any]], result: dict[str, Any],
    *, frontier: dict[str, Any] | None = None,
) -> None:
    """Apply a fully validated batch atomically, never touching post-cutoff edits."""
    with author_edit.project_write_lock(project_id):
        ledger = author_edit.get_change_ledger(project_id)
        stored = author_edit.get_state_refresh(project_id)
        if stored.get("refresh_id") != refresh.get("refresh_id") or stored.get("status") != "running":
            return
        captured_ids = set(str(item) for item in refresh.get("change_ids") or [])
        entries = {str(item.get("change_id")): item for item in ledger.get("changes", []) if isinstance(item, dict)}
        if any(entries.get(change_id, {}).get("status") not in {"pending", "failed"} for change_id in captured_ids):
            raise ChangeSettlementError("整理期间的账本状态已变化，已拒绝写入过期结果。")
        snapshot = get_project_snapshot(project_id)
        model = project_model.load_project_model(project_id)
        model_path = _model_artifact(project_id)
        before = model_path.read_bytes() if model_path.exists() else None
        cutoff_model_rev = refresh.get("cutoff_model_rev")
        if not isinstance(cutoff_model_rev, int):
            cutoff_model_rev = None

        def _bound_source_context(item: dict[str, Any]) -> tuple[str, set[int]]:
            """把一条后果绑定到已验证的已捕获作者变更：未知/跨批/空源一律拒绝。

            返回（权威 source_kind, protect revs）：只有真实正文变更在源中，
            该后果才可以以正文权威推进作者拥有的 dynamic 字段。
            """
            source_ids = item.get("source_change_ids") or []
            unknown = sorted(set(source_ids) - captured_ids)
            if unknown:
                raise ChangeSettlementError(
                    f"语义后果引用了未知或未被本次捕获的变更 id：{', '.join(unknown)}，已拒绝。"
                )
            sources = [entries[change_id] for change_id in dict.fromkeys(source_ids)]
            prose_supported = any(
                source.get("source_kind") in {"manual_prose_edit", "accepted_ai_prose"}
                for source in sources
            )
            protect_revs = {
                int(source["source_model_rev"]) for source in sources
                if isinstance(source.get("source_model_rev"), int)
            }
            return ("manual_prose_edit" if prose_supported else "semantic_refresh"), protect_revs

        mechanical: list[dict[str, Any]] = []
        proposals: list[dict[str, Any]] = []
        for item in result["consequences"]:
            if item["classification"] == "mechanically_certain" and not _needs_author_gate(model, item):
                mechanical.append(item)
            else:
                proposals.append(item)
        prose_by_chapter: dict[int, dict[str, Any]] = {}
        for group in captured:
            latest = group["latest"]
            delta = latest.get("delta") if isinstance(latest.get("delta"), dict) else {}
            chapter = delta.get("chapter_number")
            if latest.get("source_kind") in {"manual_prose_edit", "accepted_ai_prose"} and isinstance(chapter, int):
                prose_by_chapter[chapter] = latest
        applied_outcomes: list[int] = []
        try:
            for item in mechanical:
                source_kind, protect_revs = _bound_source_context(item)
                model = _apply_one(
                    project_id, model, snapshot, item,
                    source_kind=source_kind,
                    source_model_revs=protect_revs,
                    dynamic_override_max_rev=cutoff_model_rev,
                )
            for outcome in result["chapter_actual_results"]:
                number = outcome["chapter_number"]
                source_change = prose_by_chapter.get(number)
                chapter = next((item for item in snapshot["chapters"] if item["chapter_number"] == number), None)
                expected_hash = ((source_change or {}).get("delta") or {}).get("after_sha256")
                if not source_change or not chapter or not isinstance(expected_hash, str) or chapter.get("content_sha256") != expected_hash:
                    # A later save changed this chapter after the cutoff.  Its
                    # author truth remains pending for a later refresh.
                    continue
                model = project_model.set_chapter_actual_result(
                    project_id, base_model_rev=model["model_rev"], chapter_number=number,
                    result=outcome["result"], content_sha256=expected_hash,
                    source_change_id=str(source_change["change_id"]), actual_word_count=chapter["actual_words"],
                )
                impact = outcome.get("planning_impact_candidate")
                if impact is not None:
                    model = project_model.add_planning_impact_candidate(
                        project_id, base_model_rev=model["model_rev"], chapter_number=number,
                        summary=impact["summary"], affected_refs=impact.get("affected_refs") or [],
                        source_change_id=str(source_change["change_id"]),
                    )
                applied_outcomes.append(number)
            # 规划影响候选：每条必须绑定真实已捕获源变更；全部 ref/章号/阶段必须解析到
            # 当前有效项目事实（AI 不得虚构）；任一非法 → 整批失败回滚。
            created_impact_ids: list[str] = []
            impacts = result.get("planning_impact_candidates") or []
            if impacts:
                valid_refs: set[str] = set()
                for bucket_name in ("current", "future"):
                    for values in snapshot[bucket_name].values():
                        for record in values:
                            if isinstance(record.get("ref"), str):
                                valid_refs.add(record["ref"])
                for edge in snapshot.get("explicit_dependencies", []):
                    valid_refs.add(edge["ref"])
                for chapter in snapshot["chapters"]:
                    if isinstance(chapter.get("fine_outline_ref"), str):
                        valid_refs.add(chapter["fine_outline_ref"])
                stage_refs = {stage["ref"] for stage in snapshot["length_plan"]["stages"]}
                valid_refs |= stage_refs
                valid_chapters = {chapter["chapter_number"] for chapter in snapshot["chapters"]}
                facts_by_change: dict[str, tuple[list[str], list[int]]] = {}
                for group in captured:
                    latest = group["latest"]
                    delta = latest.get("delta") if isinstance(latest.get("delta"), dict) else {}
                    refs: list[str] = []
                    chapters: list[int] = []
                    chapter = delta.get("chapter_number")
                    if latest.get("source_kind") in {"manual_prose_edit", "accepted_ai_prose"} and isinstance(chapter, int):
                        chapters.append(chapter)
                    model_change = delta.get("project_model_change") if isinstance(delta.get("project_model_change"), dict) else {}
                    detail = model_change.get("detail") if isinstance(model_change.get("detail"), dict) else {}
                    ref = detail.get("ref") if isinstance(detail, dict) else None
                    if isinstance(ref, str) and ref:
                        refs.append(ref)
                    facts_by_change[str(latest.get("change_id"))] = (refs, chapters)
                for impact in impacts:
                    unknown = sorted(set(impact["source_change_ids"]) - captured_ids)
                    if unknown:
                        raise ChangeSettlementError(
                            f"影响候选引用了未知或未被本次捕获的变更 id：{', '.join(unknown)}，已拒绝。"
                        )
                    bad_refs = [ref for ref in impact["affected_refs"] if ref not in valid_refs]
                    if bad_refs:
                        raise ChangeSettlementError("影响候选 affected_refs 包含不存在或非有效的记录，已拒绝。")
                    bad_chapters = [n for n in impact["affected_chapter_numbers"] if n not in valid_chapters]
                    if bad_chapters:
                        raise ChangeSettlementError("影响候选 affected_chapter_numbers 包含不存在的章节，已拒绝。")
                    bad_stages = [ref for ref in impact["affected_stage_refs"] if ref not in stage_refs]
                    if bad_stages:
                        raise ChangeSettlementError("影响候选 affected_stage_refs 包含不存在的阶段，已拒绝。")
                    source_refs: set[str] = set()
                    for change_id in impact["source_change_ids"]:
                        refs_for_change, chapters_for_change = facts_by_change.get(change_id, ([], []))
                        source_refs.update(refs_for_change)
                    planning_sources = sorted({
                        (model["objects"][ref].get("data") or {}).get("planning_source_ref")
                        for ref in impact["affected_refs"]
                        if ref in model.get("objects", {})
                        and isinstance((model["objects"][ref].get("data") or {}).get("planning_source_ref"), str)
                    })
                    model = project_model.add_planning_impact_candidate(
                        project_id, base_model_rev=model["model_rev"],
                        summary=impact["summary"],
                        source_change_ids=impact["source_change_ids"],
                        affected_refs=impact["affected_refs"],
                        affected_chapter_numbers=impact["affected_chapter_numbers"],
                        affected_stage_refs=impact["affected_stage_refs"],
                        affected_planning_source_refs=planning_sources,
                        source_refs=sorted(source_refs),
                        created_from_refresh_id=refresh.get("refresh_id"),
                    )
                    created_impact_ids.append(model["change_history"][-1]["detail"]["candidate_id"])
                audit.append_event(
                    str(refresh.get("refresh_id") or ""), audit.EVENT_IMPACT_CANDIDATES, "change_settlement",
                    details={
                        "created": created_impact_ids,
                        "frontier_candidates": len((frontier or {}).get("affected_future_refs") or []),
                        "frontier_refs": (frontier or {}).get("affected_future_refs") or [],
                        "frontier_chapters": (frontier or {}).get("later_same_stage_chapter_numbers") or [],
                    },
                )
        except (project_model.ProjectModelError, ChangeSettlementError, OSError) as exc:
            _restore_model(model_path, before)
            raise ChangeSettlementError(str(exc)) from exc
        change_patches = {
            change_id: {
                "status": "awaiting_author" if proposals else "synchronized",
                "semantic": {"refresh_id": refresh["refresh_id"], "summary": result["summary"]},
                "error": None,
                "settlement_started": False,
            }
            for change_id in captured_ids
        }
        next_state = {
            "status": "awaiting_confirmation" if proposals else "synchronized",
            "refresh_id": refresh["refresh_id"],
            "cutoff_sequence": refresh["cutoff_sequence"],
            "change_ids": sorted(captured_ids),
            "summary": result["summary"],
            "error": None,
            "proposals": copy.deepcopy(proposals),
            "result": {
                "applied_outcome_chapters": applied_outcomes,
                "created_impact_candidates": created_impact_ids,
            },
        }
        try:
            author_edit.update_changes_and_state_refresh(
                project_id, changes=change_patches, state_refresh=next_state,
            )
        except (author_edit.AuthorEditError, OSError) as exc:
            _restore_model(model_path, before)
            raise ChangeSettlementError(f"作品状态整理记账失败，项目模型已回滚：{exc}") from exc


def _refresh_trigger_facts(captured: list[dict[str, Any]]) -> tuple[list[str], list[str], list[int]]:
    """从已捕获变更提取影响前沿触发事实（只认显式 ref / 章节号）。"""
    object_refs: list[str] = []
    dependency_refs: list[str] = []
    chapter_numbers: list[int] = []
    for group in captured:
        latest = group["latest"]
        delta = latest.get("delta") if isinstance(latest.get("delta"), dict) else {}
        chapter = delta.get("chapter_number")
        if latest.get("source_kind") in {"manual_prose_edit", "accepted_ai_prose"} and isinstance(chapter, int):
            chapter_numbers.append(chapter)
        model_change = delta.get("project_model_change") if isinstance(delta.get("project_model_change"), dict) else {}
        detail = model_change.get("detail") if isinstance(model_change.get("detail"), dict) else {}
        ref = detail.get("ref") if isinstance(detail, dict) else None
        if isinstance(ref, str) and ref:
            if "_edge_" in ref:
                dependency_refs.append(ref)
            else:
                object_refs.append(ref)
    return object_refs, dependency_refs, chapter_numbers


def _refresh_worker(project_id: str, refresh: dict[str, Any], captured: list[dict[str, Any]]) -> None:
    try:
        snapshot = get_project_snapshot(project_id)
        affected = []
        for group in captured:
            latest = group["latest"]
            delta = copy.deepcopy(latest.get("delta") or {})
            chapter = delta.get("chapter_number")
            current_chapter = next((item for item in snapshot["chapters"] if item["chapter_number"] == chapter), None)
            affected.append({
                "change_ids": group["change_ids"], "source_kind": latest.get("source_kind"),
                "latest_delta": delta,
                "current_chapter": current_chapter if isinstance(chapter, int) else None,
            })
        object_refs, dependency_refs, chapter_numbers = _refresh_trigger_facts(captured)
        frontier = build_planning_impact_frontier(
            project_id,
            changed_object_refs=object_refs,
            changed_dependency_refs=dependency_refs,
            changed_chapter_numbers=chapter_numbers,
        )
        audit.append_event(
            refresh["refresh_id"], audit.EVENT_OPERATION_STARTED, "change_settlement",
            details={
                "project_id": project_id,
                "change_ids": refresh.get("change_ids") or [],
                "frontier_candidates": len(frontier.get("affected_future_refs") or []),
                "frontier_chapters": frontier.get("later_same_stage_chapter_numbers") or [],
            },
        )
        prompt = _BATCH_TASK_TEMPLATE.format(
            affected=json.dumps(affected, ensure_ascii=False, indent=2),
            frontier=json.dumps(frontier, ensure_ascii=False, indent=2),
            snapshot=json.dumps(focused_task_context(project_id), ensure_ascii=False, indent=2),
        )
        output = semantic_ai.run_text(prompt)
        parsed = _parse_refresh_output(output)
        _apply_refresh_result(project_id, refresh, captured, parsed, frontier=frontier)
        audit.finish_file(refresh["refresh_id"], audit.STATUS_COMPLETED)
    except Exception as exc:  # durable edits remain pending and retryable
        try:
            audit.append_event(
                refresh["refresh_id"], audit.EVENT_AGENT_FAILED, "change_settlement",
                details={"error": str(exc)[:200]},
            )
            audit.finish_file(refresh["refresh_id"], audit.STATUS_FAILED, error=str(exc)[:200])
        except Exception:  # noqa: BLE001 — 审计失败绝不影响作者操作
            pass
        try:
            author_edit.update_changes_and_state_refresh(project_id, state_refresh={
                **refresh, "status": "failed", "error": str(exc), "summary": "整理失败，可重试。", "proposals": [],
            })
        except (author_edit.AuthorEditError, OSError):
            pass


def prepare_project_state_refresh(project_id: str) -> dict[str, Any]:
    """Start the one explicit, bounded Direct-AI project refresh."""
    existing = author_edit.get_state_refresh(project_id)
    if existing.get("status") == "running" and _refresh_worker_active(project_id):
        return get_project_state_refresh(project_id)
    refresh, captured = _capture_refresh(project_id)
    if not captured:
        return get_project_state_refresh(project_id)
    try:
        semantic_ai.require_semantic_ai()
    except semantic_ai.SemanticAiConfigError as exc:
        author_edit.update_changes_and_state_refresh(project_id, state_refresh={
            **refresh, "status": "failed", "error": f"{NEEDS_CONFIG_PREFIX}: {exc}",
            "summary": "需要先配置日常 AI，作者修改仍待整理。",
        })
        return get_project_state_refresh(project_id)
    worker = threading.Thread(
        target=_refresh_worker, args=(project_id, refresh, captured),
        name=f"gowrite-project-state-refresh-{project_id}", daemon=True,
    )
    with _REFRESH_WORKERS_GUARD:
        _REFRESH_WORKERS[project_id] = worker
    worker.start()
    return get_project_state_refresh(project_id)


def get_project_state_refresh(project_id: str) -> dict[str, Any]:
    return author_edit.get_state_refresh_read_model(
        project_id, worker_active=_refresh_worker_active(project_id),
    )


def confirm_project_state_refresh(project_id: str, refresh_id: str, *, accept: bool) -> dict[str, Any]:
    """Resolve only this refresh's author-gated consequences; truth is never reverted."""
    with author_edit.project_write_lock(project_id):
        state = author_edit.get_state_refresh(project_id)
        if state.get("refresh_id") != refresh_id or state.get("status") != "awaiting_confirmation":
            raise ChangeSettlementError("作品状态整理确认已过期或不属于当前作品。")
        proposals = state.get("proposals") if isinstance(state.get("proposals"), list) else []
        model_path = _model_artifact(project_id)
        before = model_path.read_bytes() if model_path.exists() else None
        try:
            if accept:
                snapshot = get_project_snapshot(project_id)
                model = project_model.load_project_model(project_id)
                for item in proposals:
                    model = _apply_one(project_id, model, snapshot, item, author_confirmed=True)
            patches = {str(change_id): {"status": "synchronized", "error": None} for change_id in state.get("change_ids") or []}
            author_edit.update_changes_and_state_refresh(project_id, changes=patches, state_refresh={
                **state, "status": "synchronized", "proposals": [],
                "summary": "作品状态已更新。" if accept else "已忽略这些待确认项；作者内容未回滚。", "error": None,
            })
        except (project_model.ProjectModelError, ChangeSettlementError, author_edit.AuthorEditError, OSError) as exc:
            _restore_model(model_path, before)
            raise ChangeSettlementError(str(exc)) from exc
    return get_project_state_refresh(project_id)


_SETTLEMENT_WORKERS_GUARD = threading.Lock()
_SETTLEMENT_WORKERS: dict[str, threading.Thread] = {}
_PROJECT_SETTLEMENT_LOCKS: dict[str, threading.Lock] = {}


def _project_lock(project_id: str) -> threading.Lock:
    """One in-process settlement serializer per project (no queue service)."""
    with _SETTLEMENT_WORKERS_GUARD:
        lock = _PROJECT_SETTLEMENT_LOCKS.get(project_id)
        if lock is None:
            lock = threading.Lock()
            _PROJECT_SETTLEMENT_LOCKS[project_id] = lock
        return lock


def _active_worker(project_id: str) -> threading.Thread | None:
    with _SETTLEMENT_WORKERS_GUARD:
        worker = _SETTLEMENT_WORKERS.get(project_id)
        if worker is not None and worker.is_alive():
            return worker
        return None


def _register_worker(project_id: str, worker: threading.Thread) -> None:
    with _SETTLEMENT_WORKERS_GUARD:
        _SETTLEMENT_WORKERS[project_id] = worker


def _mark_failed(project_id: str, change_id: str, error: str) -> None:
    try:
        author_edit.update_change(project_id, change_id, status="failed", error=error)
    except (author_edit.AuthorEditError, OSError):
        pass


def _build_prompt(project_id: str, change: dict[str, Any]) -> str:
    delta = copy.deepcopy(change.get("delta") or {})
    chapter_number = delta.get("chapter_number") if isinstance(delta.get("chapter_number"), int) else None
    task_context = focused_task_context(project_id, chapter_number=chapter_number)
    return _TASK_TEMPLATE.format(
        change=json.dumps(delta, ensure_ascii=False, indent=2),
        snapshot=json.dumps(task_context, ensure_ascii=False, indent=2),
    )


def _settle_one_change(project_id: str, change_id: str) -> None:
    """Settle one ledger change via Direct AI through the existing gates."""
    try:
        change = author_edit.get_change(project_id, change_id)
    except author_edit.AuthorEditError:
        return
    if not change.get("requires_semantic") or change.get("status") not in {"pending", "failed"}:
        return
    try:
        config, _api_key = semantic_ai.require_semantic_ai()
    except semantic_ai.SemanticAiConfigError as exc:
        _mark_failed(project_id, change_id, f"{NEEDS_CONFIG_PREFIX}: {exc}")
        return
    request_id = uuid.uuid4().hex
    execution = {"execution_mode": "direct_ai", "agent_id": None, "model": config.model}
    try:
        task = _build_prompt(project_id, change)
        bridge.create_request(
            task=task, kind="change_settlement", request_id=request_id,
            meta={"project_id": project_id, "change_id": change_id, "execution": execution},
            activate_for_gowrite=False,
        )
    except Exception as exc:  # noqa: BLE001 - durable edit must remain retryable
        _mark_failed(project_id, change_id, f"语义同步准备失败：{exc}")
        return
    try:
        author_edit.update_change(
            project_id, change_id, status="pending", error=None,
            settlement_request_id=request_id, settlement_started=True,
        )
    except (author_edit.AuthorEditError, OSError):
        bridge.cleanup_request(request_id)
        return
    try:
        output = semantic_ai.run_text(task)
    except (semantic_ai.SemanticAiConfigError, semantic_ai.SemanticAiRunError) as exc:
        _mark_failed(project_id, change_id, str(exc))
        bridge.write_response(request_id, status="failed", error=str(exc))
        return
    request = bridge.get_request(request_id)
    if not isinstance(request, dict) or request.get("state") == "canceled":
        bridge.cleanup_request(request_id)
        return
    try:
        parsed = _parse_output(output)
    except ChangeSettlementError as exc:
        _mark_failed(project_id, change_id, str(exc))
        bridge.write_response(request_id, status="failed", error=str(exc))
        return
    # Model + ledger mutations happen under the same per-project write lock as
    # durable author edits, so rapid edits and settlement never overwrite
    # each other.
    with author_edit.project_write_lock(project_id):
        try:
            apply_semantic_result(project_id, change_id, parsed)
        except (ChangeSettlementError, author_edit.AuthorEditError, OSError) as exc:
            bridge.write_response(request_id, status="failed", error=str(exc))
            return
    bridge.write_response(request_id, status="completed", output=output)


def _next_pending_change(project_id: str) -> str | None:
    try:
        _loaded, _project_dir, artifact = author_edit._load(project_id)
        ledger = author_edit._read_changes(artifact, project_id)
    except (author_edit.AuthorEditError, OSError):
        return None
    for item in ledger["changes"]:
        if (
            isinstance(item, dict)
            and item.get("requires_semantic")
            and item.get("status") == "pending"
            and item.get("change_id")
        ):
            return str(item["change_id"])
    return None


def _project_settlement_worker(
    project_id: str,
    lock: threading.Lock,
    explicit_change_id: str | None,
) -> None:
    """Drain the durable ledger in order; rapid edits never collide."""
    handled_explicit = explicit_change_id is None
    with lock:
        while True:
            target: str | None = None
            if not handled_explicit:
                handled_explicit = True
                try:
                    explicit = author_edit.get_change(project_id, explicit_change_id)
                except author_edit.AuthorEditError:
                    explicit = None
                if (
                    explicit
                    and explicit.get("requires_semantic")
                    and explicit.get("status") in {"pending", "failed"}
                ):
                    target = str(explicit_change_id)
            if target is None:
                target = _next_pending_change(project_id)
            if not target:
                return
            _settle_one_change(project_id, target)


def prepare_change_settlement(project_id: str, change_id: str) -> dict[str, Any]:
    change = author_edit.get_change(project_id, change_id)
    if not change.get("requires_semantic"):
        raise ChangeSettlementError("这条变更只需要确定性处理，已经同步完成。")
    if change.get("status") not in {"pending", "failed"}:
        raise ChangeSettlementError("这条变更当前不需要重新执行语义同步。")
    if _active_worker(project_id) is not None:
        # Rapid edits: the durable change stays in the author ledger and the
        # running per-project worker drains pending changes in ledger order.
        # No second request, no duplicate failure cards, no Agent slot.
        return {
            "request_id": None, "project_id": project_id, "change_id": change_id,
            "status": "pending", "execution": {"execution_mode": "direct_ai"},
            "request_started": False, "queued": True,
            "message": "已排队：前序变更同步完成后自动继续。",
        }
    # Fail fast on missing configuration before any orchestration.  The durable
    # edit remains visible/retryable; this is configuration state, not story
    # data, and there is no silent Agent fallback.
    try:
        semantic_ai.require_semantic_ai()
    except semantic_ai.SemanticAiConfigError as exc:
        _mark_failed(project_id, change_id, f"{NEEDS_CONFIG_PREFIX}: {exc}")
        raise ChangeSettlementError(NEEDS_CONFIG_MESSAGE) from exc
    lock = _project_lock(project_id)
    worker = threading.Thread(
        target=_project_settlement_worker, args=(project_id, lock, change_id),
        name=f"gowrite-semantic-settlement-{project_id}", daemon=True,
    )
    _register_worker(project_id, worker)
    worker.start()
    return {
        "request_id": None, "project_id": project_id, "change_id": change_id,
        "status": "pending", "execution": {"execution_mode": "direct_ai"},
        "request_started": True, "queued": False,
        "message": "正在后台同步本次修改。",
    }


def get_change_settlement_request(request_id: str) -> dict[str, Any]:
    request = bridge.get_request(request_id)
    if not request or request.get("kind") != "change_settlement":
        raise ChangeSettlementError("语义同步请求不存在或已失效。")
    meta = request.get("meta") or {}
    project_id = str(meta.get("project_id") or "")
    change_id = str(meta.get("change_id") or "")
    if request.get("state") == "canceled":
        bridge.cleanup_request(request_id)
        return {
            "request_id": request_id, "project_id": project_id, "change_id": change_id,
            "status": "canceled",
        }
    response = bridge.read_response(request_id)
    if response is None:
        return {
            "request_id": request_id, "project_id": project_id, "change_id": change_id,
            "status": "pending", "message": "语义同步仍在进行。",
        }
    if response.get("status") != "completed":
        error = response.get("error") or "语义同步失败。"
        try:
            change = author_edit.get_change(project_id, change_id)
            if change.get("status") == "pending":
                author_edit.update_change(project_id, change_id, status="failed", error=error)
        except (author_edit.AuthorEditError, OSError):
            pass
        bridge.cleanup_request(request_id)
        return {
            "request_id": request_id, "project_id": project_id, "change_id": change_id,
            "status": "failed", "error": error,
        }
    # Completed responses are written only after the Direct AI worker applied
    # the result through the existing strict parser and authority gates.
    try:
        change = author_edit.get_change(project_id, change_id)
    except author_edit.AuthorEditError as exc:
        bridge.cleanup_request(request_id)
        return {
            "request_id": request_id, "project_id": project_id, "change_id": change_id,
            "status": "failed", "error": str(exc),
        }
    bridge.cleanup_request(request_id)
    status = change.get("status")
    if status in {"synchronized", "awaiting_author"}:
        return {
            "request_id": request_id, "project_id": project_id, "change_id": change_id,
            "status": "completed",
            "result": {
                "project_id": project_id, "change_id": change_id,
                "status": status, "change": change,
            },
        }
    return {
        "request_id": request_id, "project_id": project_id, "change_id": change_id,
        "status": "failed", "error": change.get("error") or "语义同步失败。",
    }


def has_active_worker(project_id: str) -> bool:
    """True while this process is actively draining the project's ledger.

    Read-only liveness fact for the author surface: stale persisted
    settlement_request_id values (dead workers / old processes) must never be
    presented as a running sync, and the UI must not follow them.
    """
    return _active_worker(project_id) is not None


def cancel_change_settlement(project_id: str, change_id: str) -> dict[str, Any]:
    """Author-visible cancel for one pending/failed sync task.

    The durable author edit stays in the ledger; only the semantic-sync task is
    dismissed (terminal 'canceled'), so stale cards can always be cleared and
    never block or loop. An in-flight Direct AI request is marked canceled so
    the worker aborts before applying anything.
    """
    change = author_edit.get_change(project_id, change_id)
    if change.get("status") not in {"pending", "failed"}:
        raise ChangeSettlementError("这条变更当前没有可取消的同步任务。")
    request_id = change.get("settlement_request_id")
    if change.get("settlement_started") and isinstance(request_id, str) and request_id:
        request = bridge.get_request(request_id)
        if isinstance(request, dict) and request.get("kind") == "change_settlement":
            bridge.mark_canceled(request_id)
    updated = author_edit.update_change(project_id, change_id, status="canceled", error=None)
    return {"project_id": project_id, "change_id": change_id, "status": "canceled", "change": updated}


def cancel_change_settlement_request(request_id: str) -> dict[str, Any]:
    request = bridge.get_request(request_id)
    if not request or request.get("kind") != "change_settlement":
        return {"request_id": request_id, "status": "canceled"}
    meta = request.get("meta") or {}
    project_id = str(meta.get("project_id") or "")
    change_id = str(meta.get("change_id") or "")
    bridge.mark_canceled(request_id)
    if project_id and change_id:
        try:
            author_edit.update_change(project_id, change_id, status="pending", error=None)
        except (author_edit.AuthorEditError, OSError):
            pass
    return {"request_id": request_id, "status": "canceled"}


def confirm_ambiguous_consequences(
    project_id: str,
    change_id: str,
    accepted_indexes: list[int],
) -> dict[str, Any]:
    change = author_edit.get_change(project_id, change_id)
    semantic = change.get("semantic")
    if change.get("status") != "awaiting_author" or not isinstance(semantic, dict):
        raise ChangeSettlementError("这条变更当前没有待确认的语义后果。")
    consequences = semantic.get("consequences") or []
    if not isinstance(accepted_indexes, list) or any(
        not isinstance(index, int) or isinstance(index, bool) or index < 0 or index >= len(consequences)
        for index in accepted_indexes
    ):
        raise ChangeSettlementError("待确认后果索引非法。")
    with author_edit.project_write_lock(project_id):
        return _confirm_ambiguous_locked(project_id, change_id, accepted_indexes, change, semantic)


def _confirm_ambiguous_locked(
    project_id: str,
    change_id: str,
    accepted_indexes: list[int],
    change: dict[str, Any],
    semantic: dict[str, Any],
) -> dict[str, Any]:
    consequences = semantic.get("consequences") or []
    snapshot = get_project_snapshot(project_id)
    model = project_model.load_project_model(project_id)
    model_path = _model_artifact(project_id)
    before = model_path.read_bytes() if model_path.exists() else None
    try:
        for index in accepted_indexes:
            item = consequences[index]
            # 真机械项在首遍已应用；被作者主权门控的机械项在此经作者确认应用。
            if item.get("classification") == "mechanically_certain" and not _needs_author_gate(model, item):
                continue
            model = _apply_one(
                project_id, model, snapshot, item, author_confirmed=True,
                source_model_rev=change.get("source_model_rev"),
                source_kind=change.get("source_kind"),
            )
    except (project_model.ProjectModelError, ChangeSettlementError, OSError) as exc:
        _restore_model(model_path, before)
        raise ChangeSettlementError(str(exc)) from exc
    try:
        updated = author_edit.update_change(
            project_id, change_id, status="synchronized",
            semantic={**semantic, "author_accepted_indexes": sorted(set(accepted_indexes))}, error=None,
        )
    except (author_edit.AuthorEditError, OSError) as exc:
        try:
            _restore_model(model_path, before)
        except OSError as rollback_exc:
            raise ChangeSettlementError(f"确认结果记账失败且项目模型回滚未完成：{rollback_exc}") from exc
        raise ChangeSettlementError(f"确认结果记账失败，项目模型已回滚：{exc}") from exc
    return {"project_id": project_id, "change_id": change_id, "status": "synchronized", "change": updated}
