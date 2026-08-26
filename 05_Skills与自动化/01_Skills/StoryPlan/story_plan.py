"""Minimal StoryPlan contract built directly on the E1 StoryDesign runtime.

E2-A deliberately does NOT copy story_runtime.py and does NOT define a
book/volume/arc/chapter/scene hierarchy.  It reuses the E1 deterministic
guardrails (authority, stale, project/ref consistency, approved_plan-only
writeback) and adds only the planning-specific semantics:

- Plan Brief with a free-form planning target/scope and required confirmed
  planning sources (StoryPlan never pretends an author direction exists);
- Plan Candidate as opaque, proposal_noncanonical model content;
- planning items with stable id / target_ref / optional supersedes /
  built_from so future local re-planning stays possible.

E2-C-A adds minimal local re-plan semantics on top (see ADR E2-C):

- approved_plan stays append-only history; superseded plans are never
  deleted, overwritten in place or given a persistent status field;
- which plans are currently active is a derived pure-function projection
  (resolve_plan_activity) and is never stored back into Story State;
- make_plan_diff validates supersedes refs narrowly: existing id, same
  target_ref as the current Brief, still-active base, no self/duplicate
  refs, and the ref must appear in the current Brief's verified
  planning_sources (deterministic source binding).  compile_plan_brief
  additionally rejects planning sources that are already inactive
  (superseded); old plans remain in append-only history but cannot serve
  as the "currently confirmed planning source" for a new Brief.
  built_from stays plain provenance metadata: no dependency graph,
  no stale propagation (deferred).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

# Reuse the E1 runtime in place; no parallel runtime, no E1 refactor.
_SKILLS_ROOT = Path(__file__).resolve().parents[1]
_STORYDESIGN_DIR = _SKILLS_ROOT / "StoryDesign"
if str(_STORYDESIGN_DIR) not in sys.path:
    sys.path.insert(0, str(_STORYDESIGN_DIR))
_module = sys.modules.get("ai_write_story_runtime")
if _module is None:
    _spec = importlib.util.spec_from_file_location("ai_write_story_runtime", _STORYDESIGN_DIR / "story_runtime.py")
    if _spec is None or _spec.loader is None:
        raise ImportError("无法加载 StoryDesign story_runtime")
    _module = importlib.util.module_from_spec(_spec)
    sys.modules["ai_write_story_runtime"] = _module
    _spec.loader.exec_module(_module)

ContractError = _module.ContractError
CANON_AREAS = _module.CANON_AREAS
validate_author_intent = _module.validate_author_intent
validate_story_state = _module.validate_story_state
build_context = _module.build_context
create_decision_record = _module.create_decision_record
make_planning_diff = _module.make_planning_diff
apply_diff = _module.apply_diff
context_is_stale = _module.context_is_stale
mark_stale_if_needed = _module.mark_stale_if_needed
trace_record = _module.trace_record
utc_now = _module.utc_now
write_json = _module.write_json
read_json = _module.read_json
project_paths = _module.project_paths
initialize_project = _module.initialize_project


CAPABILITY = {
    "capability_id": "story_plan.v0",
    "solves": "将已确认的 StoryDesign / approved_plan 展开为可追溯、可修改、可局部失效的长篇 planning material。",
    "inputs": ["author planning question", "Author Intent", "Story State", "confirmed planning sources"],
    "may_read": ["Author Intent", "Story State", "approved_plan", "selected BKP through KnowledgeRetrieve"],
    "writes_state": False,
    "confirmation_required_for_writes": "任何 planning 写入 approved_plan 都需要作者 choose/modify Decision。",
    "outputs": ["Plan Brief", "Context Package", "noncanonical StoryPlan candidate", "trace"],
}

# E2-A v0 唯一正式可验证的 planning source：当前 Story State approved_plan
# 中真实存在的条目。直接 Decision ref 待未来有正式 Decision resolver/store
# 后再开放（见 ADR E2-A）；proposal / context / bkp 永远不算。
SUPPORTED_PLANNING_SOURCE_KINDS = ("approved_plan",)
DEFERRED_PLANNING_SOURCE_KINDS = ("design_decision", "author_decision")
FORBIDDEN_PLANNING_SOURCE_KINDS = ("proposal", "context", "bkp", "ai_candidate")
TRUSTED_PLANNING_SOURCE_AUTHORITIES = ("author_decision:", "manual_import:")
# F2: simulation_author_decision 不是生产可信 planning source；
# 仅显式 allow_simulation_sources=True 的测试/sandbox 路径可以读取。
SIMULATION_ONLY_AUTHORITIES = ("simulation_author_decision:",)


def compile_plan_brief(
    *,
    project_id: str,
    brief_id: str,
    author_planning_question: str,
    planning_target: dict[str, Any],
    planning_sources: list[dict[str, Any]],
    intent: dict[str, Any],
    state: dict[str, Any],
    semantic_interpretation: dict[str, Any] | None = None,
    allow_simulation_sources: bool = False,
) -> dict[str, Any]:
    """Compile the planning task contract.

    ``planning_target`` is intentionally free-form: {target_id, description,
    scope_kind, scope}.  scope_kind is NOT an enum; "女主与母亲关系的中期推进"
    is as legal as "整本书前半程".  No volume/chapter/climax fields are
    required here or anywhere else in E2-A.
    """
    validate_author_intent(intent)
    validate_story_state(state)
    if not author_planning_question.strip():
        raise ContractError("StoryPlan 需要作者当前的规划问题")
    if project_id != intent["project_id"] or project_id != state["project_id"]:
        raise ContractError("Plan Brief、Intent 与 Story State 必须属于同一 project_id")
    if not isinstance(planning_target, dict) or not planning_target.get("target_id") or not planning_target.get("description"):
        raise ContractError("planning_target 必须有 target_id 与 description")
    if not planning_sources:
        raise ContractError("StoryPlan 需要至少一个已确认规划来源；无已确认 StoryDesign/方向时不得假装已有作者方向")
    # 防御性检查：当前 State 的 approved_plan id 必须唯一，否则 ref 解析会歧义。
    plans_by_id: dict[str, dict[str, Any]] = {}
    for plan in state["approved_plan"]:
        pid = plan.get("id")
        if not pid:
            raise ContractError("Story State approved_plan 条目缺少 id")
        if pid in plans_by_id:
            raise ContractError(f"Story State approved_plan 存在重复 id：{pid}")
        plans_by_id[pid] = plan
    verified_sources = []
    for source in planning_sources:
        if not isinstance(source, dict) or not source.get("kind") or not source.get("ref"):
            raise ContractError("planning source 必须有 kind 与 ref")
        kind = source["kind"]
        if kind in FORBIDDEN_PLANNING_SOURCE_KINDS:
            raise ContractError(f"未确认的 {kind} 不能作为规划来源")
        if kind in DEFERRED_PLANNING_SOURCE_KINDS:
            raise ContractError(
                f"E2-A v0 暂不接受直接 Decision ref（{kind}）作为 planning source；"
                "确定性来源是当前 Story State approved_plan 中真实存在的条目"
            )
        if kind not in SUPPORTED_PLANNING_SOURCE_KINDS:
            raise ContractError(f"未知 planning source kind：{kind}")
        entry = plans_by_id.get(source["ref"])
        if entry is None:
            raise ContractError(f"planning source ref 不存在于当前 Story State approved_plan：{source['ref']}")
        activity = resolve_plan_activity(state)
        if source["ref"] not in activity["active"]:
            raise ContractError(
                f"planning source {source['ref']} 当前不是 active（已被 supersede）；"
                "旧 planning 保留在 append-only history 中，但不得作为当前已确认规划来源编译新 Plan Brief"
            )
        if entry.get("occurred") is True:
            raise ContractError(f"planning source {source['ref']} 不得是已发生内容")
        authority = str(entry.get("authority", ""))
        effective_trusted = TRUSTED_PLANNING_SOURCE_AUTHORITIES
        if allow_simulation_sources:
            effective_trusted = effective_trusted + SIMULATION_ONLY_AUTHORITIES
        if not authority.startswith(effective_trusted):
            raise ContractError(f"planning source {source['ref']} 的 authority 不是可信规划来源：{authority}")
        verified_sources.append({"kind": kind, "ref": source["ref"], "verified_authority": authority})
    if not verified_sources:
        raise ContractError("规划来源必须至少包含一个已验证的 approved_plan 条目")

    semantic_interpretation = semantic_interpretation or {}
    model_assumptions = list(semantic_interpretation.get("assumptions", []))
    assumptions = [
        {
            "text": "除作者原话与已确认来源外，系统未把任何规划补全内容写成 Canon 或作者事实。",
            "source": "runtime_guardrail",
        }
    ] + [{"text": text, "source": "ai_interpretation"} for text in model_assumptions]
    return {
        "artifact_type": "plan_brief",
        "brief_id": brief_id,
        "brief_rev": 1,
        "project_id": project_id,
        "status": "CURRENT",
        "author_planning_question": author_planning_question,
        "planning_target": dict(planning_target),
        "planning_sources": verified_sources,
        "inherited_obligations": semantic_interpretation.get("inherited_obligations", []),
        "hard_constraints": list(intent.get("hard_constraints", [])),
        "deliberate_open_space": semantic_interpretation.get("deliberate_open_space", []),
        "knowledge_needs": semantic_interpretation.get("knowledge_needs", []),
        "assumptions": assumptions,
        "source_versions": {"intent_rev": intent["intent_rev"], "state_rev": state["state_rev"]},
        "created_at": utc_now(),
    }


def build_plan_context(
    *,
    context_id: str,
    brief: dict[str, Any],
    intent: dict[str, Any],
    state: dict[str, Any],
    retrieval=None,
    selected_knowledge_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Reuse E1 build_context; E1 already skips retrieval when the brief has
    no knowledge needs and no selected ids (0 BKP is a normal path)."""
    context = build_context(
        context_id=context_id, brief=brief, intent=intent, state=state,
        retrieval=retrieval, selected_knowledge_ids=selected_knowledge_ids,
    )
    context["planning_target"] = dict(brief["planning_target"])
    return context


def create_plan_candidate(
    *,
    candidate_id: str,
    brief: dict[str, Any],
    context: dict[str, Any],
    model_output: dict[str, Any],
) -> dict[str, Any]:
    """Persist the model's planning proposal as opaque noncanonical material.

    The runtime never parses ``model_output`` into Canon facts; literary and
    structural judgment belongs to the model/Skill, not to this module.
    """
    if context.get("status") == "STALE":
        raise ContractError("STALE Context 不得生成 StoryPlan candidate")
    if brief.get("project_id") != context.get("project_id"):
        raise ContractError("Plan Brief 与 Context project_id 不一致")
    built_from = context.get("built_from", {})
    if built_from.get("brief_id") != brief.get("brief_id") or built_from.get("brief_rev") != brief.get("brief_rev"):
        raise ContractError("Context 的 built_from 与 Plan Brief 不一致")
    return {
        "artifact_type": "story_plan_candidate",
        "candidate_id": candidate_id,
        "project_id": brief["project_id"],
        "brief_ref": f"{brief['brief_id']}@{brief['brief_rev']}",
        "context_ref": context["context_id"],
        "planning_target": dict(brief["planning_target"]),
        "source_versions": dict(brief["source_versions"]),
        "status": "proposal_noncanonical",
        "authority": "ai_candidate:noncanonical",
        "content": model_output,
        "must_not_write_canon": True,
        "created_at": utc_now(),
    }


def normalize_planning_item(plan: dict[str, Any], *, target_ref: str) -> dict[str, Any]:
    """Minimal planning-item contract for approved_plan entries.

    Required: id / description / target_ref.  Allowed future hooks:
    supersedes / built_from ref lists for local re-planning.  occurred is
    always forced false; content shape stays provider-agnostic.
    """
    if not isinstance(plan, dict) or not plan.get("id"):
        raise ContractError("planning 条目必须包含 plan id")
    if not plan.get("description"):
        raise ContractError("planning 条目必须包含 description")
    item = dict(plan)
    item.setdefault("target_ref", target_ref)
    if item["target_ref"] != target_ref:
        raise ContractError("planning 条目 target_ref 与 Plan Brief planning_target 不一致")
    for ref_field in ("supersedes", "built_from"):
        item.setdefault(ref_field, [])
        if not isinstance(item[ref_field], list) or not all(isinstance(ref, str) and ref for ref in item[ref_field]):
            raise ContractError(f"planning 条目 {ref_field} 必须是非空字符串 ref 列表")
    item["occurred"] = False
    return item


def resolve_plan_activity(state: dict[str, Any]) -> dict[str, Any]:
    """Pure, rebuildable projection of which approved_plan entries are
    currently active versus superseded (E2-C-A).

    A plan is superseded iff some later-appended plan's ``supersedes``
    references its id.  Nothing is stored: this never writes derived
    activity back into Story State, never deletes or mutates history, and
    the result is recomputable from ``state["approved_plan"]`` alone.
    """
    superseded_by: dict[str, list[str]] = {}
    for plan in state.get("approved_plan", []):
        pid = plan.get("id")
        if not pid:
            continue
        for ref in plan.get("supersedes", []) or []:
            superseded_by.setdefault(ref, []).append(pid)
    active_ids = [
        plan["id"] for plan in state.get("approved_plan", [])
        if plan.get("id") and plan["id"] not in superseded_by
    ]
    return {
        "active": active_ids,
        "superseded": sorted(superseded_by),
        "superseded_by": superseded_by,
    }


def _check_supersedes(
    *,
    normalized: list[dict[str, Any]],
    state: dict[str, Any],
    target_ref: str,
    verified_source_refs: set[str] | None = None,
) -> None:
    """E2-C-A narrow writeback guard for explicit supersedes refs.

    Only explicit, same-target local replacement is allowed; there is no
    built_from / dependency propagation and no subtree replacement.  A plan
    that is already superseded (inactive) can never be used as a
    replacement base again -- the next version must supersede the current
    active tip of the chain.  Additionally, every superseded ref must
    appear in the current Brief's verified planning_sources (deterministic
    source binding): a Decision may only supersede planning that its Brief
    explicitly declares it is based on or modifying.
    """
    plans_by_id = {plan.get("id"): plan for plan in state["approved_plan"]}
    activity = resolve_plan_activity(state)
    inactive = set(activity["superseded"])
    for item in normalized:
        supersedes = list(item.get("supersedes", []) or [])
        if not supersedes:
            continue  # 空 supersedes 保持 E2-A 普通 append 语义
        if len(set(supersedes)) != len(supersedes):
            raise ContractError(f"planning {item['id']} 的 supersedes 列表内部不得重复")
        for ref in supersedes:
            if ref == item["id"]:
                raise ContractError(f"planning {item['id']} 不得 supersede 自身")
            entry = plans_by_id.get(ref)
            if entry is None:
                raise ContractError(f"planning {item['id']} 的 supersedes ref 不存在于当前 approved_plan：{ref}")
            if entry.get("target_ref") != target_ref:
                raise ContractError(
                    f"planning {item['id']} 不得跨 target supersede {ref}："
                    f"被替换条目 target_ref={entry.get('target_ref')}，当前 Brief target={target_ref}"
                )
            if ref in inactive:
                raise ContractError(
                    f"planning {item['id']} 不得 supersede 已失效条目 {ref}（当前被 {activity['superseded_by'][ref]} 替换）；"
                    "应 supersede 当前 active 的最新版本"
                )
            if verified_source_refs is not None and ref not in verified_source_refs:
                raise ContractError(
                    f"planning {item['id']} 的 supersedes ref {ref} 不在当前 Plan Brief 声明的 planning_sources 中；"
                    "Decision 只能 supersede 其绑定 Brief 明确引用且当前 active 的 planning source"
                )


def make_plan_diff(
    *,
    diff_id: str,
    state: dict[str, Any],
    intent: dict[str, Any],
    decision: dict[str, Any],
    brief: dict[str, Any],
    plans: list[dict[str, Any]],
    allow_simulation: bool = False,
) -> dict[str, Any]:
    """StoryPlan writeback gate: reuse E1 make_planning_diff (author_action
    choose/modify only, same project) after normalizing planning items.

    Extra deterministic guards: the Decision must really target the current
    Plan Brief (brief_ref); Brief, Intent and State must belong to the same
    project; a Brief compiled against an older intent_rev OR state_rev may
    not write back on current authoritative sources (stale Brief rejection);
    planning ids must be non-empty, unique within the batch and unique
    within the existing approved_plan namespace.  E2-C-A additionally
    validates supersedes refs (existing, same target, still active, and
    explicitly declared in the Brief's planning_sources); the
    writeback itself stays a pure approved_plan append -- old plans remain
    stored and are only marked superseded through the derived activity
    projection.
    """
    if not plans:
        raise ContractError("StoryPlan Diff 需要至少一条 planning 条目")
    validate_author_intent(intent)
    projects = {brief.get("project_id"), state.get("project_id"), intent.get("project_id")}
    if len(projects) != 1 or None in projects:
        raise ContractError("Plan Brief、Story State 与 Author Intent 必须属于同一 project_id")
    source_versions = brief.get("source_versions", {})
    if source_versions.get("intent_rev") != intent.get("intent_rev"):
        raise ContractError("旧 intent_rev 的 Plan Brief 不得在当前 Intent 上生成 Planning Diff")
    if source_versions.get("state_rev") != state.get("state_rev"):
        raise ContractError("旧 state_rev 的 Plan Brief 不得在当前 State 上生成 Planning Diff")
    if decision.get("brief_ref") != f"{brief['brief_id']}@{brief['brief_rev']}":
        raise ContractError("Decision 不是针对当前 Plan Brief 做出的，不得写回该 Brief 的 planning")
    plan_ids = [plan.get("id") for plan in plans]
    if any(not pid for pid in plan_ids):
        raise ContractError("planning 条目必须包含非空 plan id")
    if len(set(plan_ids)) != len(plan_ids):
        raise ContractError("本批 planning 条目 id 不得重复")
    existing_ids = {plan.get("id") for plan in state["approved_plan"]}
    collisions = sorted(set(plan_ids) & existing_ids)
    if collisions:
        raise ContractError(f"planning id 与现有 approved_plan id 重名：{collisions}；supersedes 也必须使用新 id")
    target_ref = brief["planning_target"]["target_id"]
    normalized = [normalize_planning_item(plan, target_ref=target_ref) for plan in plans]
    verified_source_refs = {
        s["ref"] for s in brief.get("planning_sources", [])
        if s.get("kind") == "approved_plan"
    }
    _check_supersedes(normalized=normalized, state=state, target_ref=target_ref,
                      verified_source_refs=verified_source_refs)
    diff = make_planning_diff(
        diff_id=diff_id, state=state, decision=decision,
        plan=normalized[0],
        allow_simulation=allow_simulation,
    )
    # Replace the single-item change with the normalized batch; the E1 gate
    # above already enforced confirmation, author_action and project checks.
    diff["changes"] = [{"target": "approved_plan", "operation": "append", "value": item} for item in normalized]
    diff["plan_target_ref"] = target_ref
    return diff


def story_plan_trace(*, trace_id: str, brief: dict[str, Any], context: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    trace = trace_record(trace_id=trace_id, brief=brief, context=context, candidate=candidate)
    trace["artifact_type"] = "story_plan_trace"
    trace["plan_target"] = dict(brief["planning_target"])
    return trace


def run_story_plan(
    *,
    project_dir: Path,
    author_planning_question: str,
    planning_target: dict[str, Any],
    planning_sources: list[dict[str, Any]],
    brief_id: str,
    context_id: str,
    candidate_id: str,
    semantic_interpretation: dict[str, Any],
    model_output: dict[str, Any],
    retrieval=None,
) -> dict[str, Any]:
    """Deterministic shell around model/skill-provided planning work.

    First round follows BKP_POSTHOC_SPARSE_PROBLEM_DRIVEN: pass empty
    knowledge_needs and no selected ids; retrieval is then never called.
    Nothing here confirms anything: author Decision is required before any
    planning may enter approved_plan.
    """
    paths = initialize_project(project_dir)
    intent = read_json(paths["intent"])
    state = read_json(paths["state"])
    brief = compile_plan_brief(
        project_id=intent["project_id"], brief_id=brief_id,
        author_planning_question=author_planning_question,
        planning_target=planning_target, planning_sources=planning_sources,
        intent=intent, state=state, semantic_interpretation=semantic_interpretation,
    )
    context = build_plan_context(
        context_id=context_id, brief=brief, intent=intent, state=state,
        retrieval=retrieval, selected_knowledge_ids=semantic_interpretation.get("selected_knowledge_refs", []),
    )
    candidate = create_plan_candidate(candidate_id=candidate_id, brief=brief, context=context, model_output=model_output)
    trace = story_plan_trace(trace_id=f"trace-{candidate_id}", brief=brief, context=context, candidate=candidate)
    plans_dir = Path(project_dir) / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    write_json(paths["briefs"] / f"{brief_id}.json", brief)
    write_json(paths["contexts"] / f"{context_id}.json", context)
    write_json(plans_dir / f"{candidate_id}.json", candidate)
    write_json(paths["traces"] / f"trace-{candidate_id}.json", trace)
    return {"brief": brief, "context": context, "candidate": candidate, "trace": trace}
