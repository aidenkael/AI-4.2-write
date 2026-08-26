"""Deterministic guardrails for the five G4 creative-runtime artifacts.

This module deliberately does not judge literary merit.  Models/skills provide
semantic interpretation and proposals; this module owns artifact shape,
versions, provenance, stale checks and writeback permissions.
"""

from __future__ import annotations

import json
import importlib.util
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


class ContractError(ValueError):
    """Raised when a deterministic G4/E1 contract boundary is violated."""


CANON_AREAS = ("canon_facts", "character_state", "relationship_state", "occurred_events", "open_threads")
LEGAL_CANON_AUTHORITIES = ("accepted_text:", "author_decision:", "manual_import:")
FORBIDDEN_CANON_AUTHORITIES = ("bkp:", "proposal:", "ai_candidate:", "context:", "derived_context:")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def project_paths(project_dir: Path) -> dict[str, Path]:
    """Return the small, file-based project layout used by E1-A."""
    root = Path(project_dir)
    return {
        "root": root,
        "intent": root / "author_intent.json",
        "state": root / "story_state.json",
        "briefs": root / "briefs",
        "contexts": root / "contexts",
        "designs": root / "designs",
        "decisions": root / "decisions",
        "diffs": root / "diffs",
        "traces": root / "traces",
    }


def initialize_project(project_dir: Path) -> dict[str, Path]:
    paths = project_paths(project_dir)
    for path in paths.values():
        if path.suffix:
            continue
        path.mkdir(parents=True, exist_ok=True)
    return paths


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _require(payload: dict[str, Any], *fields: str) -> None:
    missing = [field for field in fields if field not in payload]
    if missing:
        raise ContractError(f"缺少必填字段: {', '.join(missing)}")


def _validate_authority(authority: str) -> None:
    if not isinstance(authority, str) or not authority:
        raise ContractError("Canon 条目必须有 authority source")
    if authority.startswith(FORBIDDEN_CANON_AUTHORITIES):
        raise ContractError(f"禁止由 {authority} 写入 Canon")
    if not authority.startswith(LEGAL_CANON_AUTHORITIES):
        raise ContractError(f"不合规 Canon authority: {authority}")


def _require_same_project(*artifacts: dict[str, Any]) -> None:
    ids = {artifact.get("project_id") for artifact in artifacts}
    if len(ids) != 1 or None in ids:
        raise ContractError(f"工件 project_id 不一致: {sorted(str(i) for i in ids)}")


def validate_author_intent(intent: dict[str, Any]) -> None:
    _require(intent, "project_id", "intent_rev", "work_direction", "reader_promise", "hard_constraints", "open_space")
    if not isinstance(intent["intent_rev"], int) or intent["intent_rev"] < 1:
        raise ContractError("intent_rev 必须是正整数")


def validate_story_state(state: dict[str, Any]) -> None:
    _require(state, "project_id", "state_rev", "canon_facts", "approved_plan")
    if not isinstance(state["state_rev"], int) or state["state_rev"] < 1:
        raise ContractError("state_rev 必须是正整数")
    for area in CANON_AREAS:
        for item in state.get(area, []):
            if not isinstance(item, dict):
                raise ContractError(f"{area} 的条目必须为对象")
            _validate_authority(item.get("authority", ""))
            if item.get("source_kind") in {"bkp", "proposal", "context"}:
                raise ContractError(f"{area} 不能把派生内容伪装成 Canon")
    for plan in state["approved_plan"]:
        if not isinstance(plan, dict) or not plan.get("id"):
            raise ContractError("approved_plan 必须是有 id 的 planning 条目")
        if plan.get("occurred") is True:
            raise ContractError("approved_plan 不得声明为已发生 Canon")
        authority = plan.get("authority", "")
        if authority.startswith(FORBIDDEN_CANON_AUTHORITIES):
            raise ContractError("BKP、proposal 或 Context 不得直接成为 approved_plan authority")


def context_is_stale(context: dict[str, Any], intent: dict[str, Any], state: dict[str, Any]) -> bool:
    built = context.get("built_from", {})
    return built.get("intent_rev") != intent.get("intent_rev") or built.get("state_rev") != state.get("state_rev")


def mark_stale_if_needed(context: dict[str, Any], intent: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(context)
    if context_is_stale(result, intent, state):
        result["status"] = "STALE"
        result["stale_reason"] = "intent_rev 或 state_rev 已变化；必须重建 Context"
    else:
        result.setdefault("status", "CURRENT")
    return result


def compile_creation_brief(
    *,
    project_id: str,
    brief_id: str,
    author_input: str,
    intent: dict[str, Any],
    state: dict[str, Any],
    semantic_interpretation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile a task contract without converting model interpretation into fact.

    ``semantic_interpretation`` is provider/agent supplied.  It may suggest
    objectives or knowledge needs, but every unquoted item stays under
    ``assumptions`` until an author later confirms a decision.
    """
    validate_author_intent(intent)
    validate_story_state(state)
    if not author_input.strip():
        raise ContractError("StoryDesign 需要作者自然语言输入")
    if project_id != intent["project_id"] or project_id != state["project_id"]:
        raise ContractError("Brief、Intent 与 Story State 必须属于同一 project_id")

    semantic_interpretation = semantic_interpretation or {}
    model_assumptions = list(semantic_interpretation.get("assumptions", []))
    assumptions = [
        {
            "text": "除作者原话外，系统未把任何补全内容写成 Canon 或作者事实。",
            "source": "runtime_guardrail",
        }
    ] + [{"text": text, "source": "ai_interpretation"} for text in model_assumptions]
    return {
        "artifact_type": "creation_brief",
        "brief_id": brief_id,
        "brief_rev": 1,
        "project_id": project_id,
        "status": "CURRENT",
        "author_input": author_input,
        "scope": semantic_interpretation.get("scope", "story_design"),
        "objective": semantic_interpretation.get("objective", author_input),
        "focal_entities": semantic_interpretation.get("focal_entities", []),
        "desired_reader_experience": semantic_interpretation.get("desired_reader_experience", []),
        "inherited_obligations": semantic_interpretation.get("inherited_obligations", []),
        "hard_constraints": list(intent.get("hard_constraints", [])),
        "freedom_zone": list(intent.get("open_space", [])),
        "knowledge_needs": semantic_interpretation.get("knowledge_needs", []),
        "assumptions": assumptions,
        "source_versions": {"intent_rev": intent["intent_rev"], "state_rev": state["state_rev"]},
        "created_at": utc_now(),
    }


def _default_retrieve(query: str):
    root = Path(__file__).resolve().parents[3]
    retrieve_dir = root / "05_Skills与自动化" / "01_Skills" / "KnowledgeRetrieve"
    if str(retrieve_dir) not in sys.path:
        sys.path.insert(0, str(retrieve_dir))
    module_name = "ai_write_knowledge_retrieve_runtime"
    module = sys.modules.get(module_name)
    if module is None:
        spec = importlib.util.spec_from_file_location(module_name, retrieve_dir / "run.py")
        if spec is None or spec.loader is None:
            raise ContractError("无法加载 KnowledgeRetrieve")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    return module.retrieve(query, top_k=8)


def build_context(
    *,
    context_id: str,
    brief: dict[str, Any],
    intent: dict[str, Any],
    state: dict[str, Any],
    retrieval: Callable[[str], Any] | None = None,
    max_knowledge_hits: int = 3,
    selected_knowledge_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Build a small, reconstructible Context Package from a retrieval call.

    知识选择是通用的：选择身份是 canonical selection_ref
    "<source_kind>/<source_id>/<source_anchor>"，runtime 不关心知识来自哪个存储。
    """
    validate_author_intent(intent)
    validate_story_state(state)
    _require_same_project(brief, intent, state)
    if brief["source_versions"] != {"intent_rev": intent["intent_rev"], "state_rev": state["state_rev"]}:
        raise ContractError("不能用过期 Brief 构建 Context")
    knowledge_needs = list(brief.get("knowledge_needs") or [])
    selected_knowledge_ids = list(selected_knowledge_ids or [])
    if selected_knowledge_ids and not knowledge_needs:
        raise ContractError("选择知识必须先有明确 knowledge_needs；不允许无知识需求直接选卡")
    selected: list[dict[str, Any]] = []
    gaps: list[str] = []
    if not knowledge_needs:
        # Frozen E1 policy: without an explicit knowledge need there is no
        # retrieval call at all.  0 knowledge is a normal path; never fall back
        # to objective-based auto retrieval.
        retrieval_info = {"query": None, "status": "SKIPPED_NO_KNOWLEDGE_NEED", "gaps": gaps, "candidate_count": 0}
        selection_reason = ("Brief 没有明确 knowledge_needs；按冻结策略跳过 KnowledgeRetrieve，"
                            "0 条知识是正常路径。")
    else:
        retrieval = retrieval or _default_retrieve
        query = "；".join(knowledge_needs)
        package = retrieval(query)
        selected_id_set = set(selected_knowledge_ids)
        gaps = list(getattr(package, "gaps", []))
        if getattr(package, "status", "INSUFFICIENT_KNOWLEDGE") == "OK":
            # Retrieval only recalls candidates.  A model/Skill must explicitly
            # select refs after considering scope and boundary; rank is not a
            # substitute for literary/semantic judgment.
            hits = list(getattr(package, "hits", []))
            # Generic selection identity (Knowledge Selection Binding): a
            # selected ref is the canonical selection_ref
            # "<source_kind>/<source_id>/<source_anchor>".  A ref is usable
            # only when it resolves to EXACTLY ONE candidate inside this exact
            # package; unknown refs, ambiguous refs and over-limit selections
            # never inject anything and never substitute another candidate.
            def _hit_ref(hit: Any) -> str:
                ref_attr = getattr(hit, "selection_ref", None)
                if isinstance(ref_attr, str) and ref_attr:
                    return ref_attr
                return f"{getattr(hit, 'source_kind', '')}/{getattr(hit, 'source_id', '')}/{getattr(hit, 'source_anchor', '')}"

            resolved: dict[str, list[Any]] = {
                ref: [h for h in hits if _hit_ref(h) == ref] for ref in selected_id_set
            }
            ambiguous_ids = {ref for ref, matches in resolved.items() if len(matches) > 1}
            unknown_ids = {ref for ref, matches in resolved.items() if not matches}
            used_refs: set[str] = set()
            for hit in hits:
                if len(selected) >= max_knowledge_hits:
                    break
                ref = _hit_ref(hit)
                if ref not in selected_id_set or ref in ambiguous_ids or ref in used_refs:
                    continue
                selected.append({
                    "selection_ref": ref,
                    "source_kind": getattr(hit, "source_kind", ""),
                    "source_id": getattr(hit, "source_id", ""),
                    "source_title": getattr(hit, "source_title", ""),
                    "source_anchor": hit.source_anchor,
                    "source": hit.source,
                    "statement": hit.statement,
                    "scope": hit.scope,
                    "boundary": hit.boundary,
                    "confidence": hit.confidence,
                    "provenance": {"evidence": hit.evidence, "rank": hit.rank, "relevance_reason": hit.relevance_reason},
                })
                used_refs.add(ref)
            for ref in sorted(ambiguous_ids):
                gaps.append(f"AMBIGUOUS_KNOWLEDGE_REF: 选择 ref {ref} 在本次召回中命中多条知识，未注入任何碰撞候选。")
            if unknown_ids:
                gaps.append("部分模型/Skill 选择的知识 ref 不在本次有效召回中。")
            for ref in sorted(selected_id_set - unknown_ids - ambiguous_ids - used_refs):
                gaps.append(f"KNOWLEDGE_LIMIT: 选择 ref {ref} 超过上限 {max_knowledge_hits} 条，未注入。")
        if getattr(package, "status", "INSUFFICIENT_KNOWLEDGE") == "OK" and not selected:
            gaps.append("模型/Skill 未选择可用知识；Context 不注入未审查候选。")
        retrieval_info = {
            "query": query,
            "status": getattr(package, "status", "INSUFFICIENT_KNOWLEDGE"),
            "gaps": gaps,
            "candidate_count": getattr(package, "candidate_count", 0),
        }
        selection_reason = ("模型/Skill 明示选择的少量知识；runtime 只校验 provenance 和数量上限。"
                             if selected else "没有可注入的模型/Skill 选择；保留检索 gap 而非按排名硬凑。")
    status = "CURRENT" if selected or not knowledge_needs else "CURRENT_WITH_KNOWLEDGE_GAP"
    return {
        "artifact_type": "context_package",
        "context_id": context_id,
        "project_id": brief["project_id"],
        "status": status,
        "built_from": {"brief_id": brief["brief_id"], "brief_rev": brief["brief_rev"], **brief["source_versions"]},
        "selected_intent": {"work_direction": intent["work_direction"], "reader_promise": intent["reader_promise"]},
        "selected_story_state": {
            "canon_facts": state.get("canon_facts", []),
            "open_threads": state.get("open_threads", []),
            "approved_plan": state.get("approved_plan", []),
        },
        "selected_knowledge_hits": selected,
        "selection_reason": selection_reason,
        "retrieval": retrieval_info,
        "size_summary": {"selected_knowledge_hits": len(selected), "catalog_not_injected": True},
        "created_at": utc_now(),
    }


def create_design_candidate(
    *,
    candidate_id: str,
    brief: dict[str, Any],
    context: dict[str, Any],
    model_output: dict[str, Any],
) -> dict[str, Any]:
    """Persist a model proposal as noncanonical material only."""
    if context.get("status") == "STALE":
        raise ContractError("STALE Context 不得生成 StoryDesign candidate")
    _require_same_project(brief, context)
    if context.get("built_from", {}).get("brief_id") != brief["brief_id"] \
            or context.get("built_from", {}).get("brief_rev") != brief["brief_rev"]:
        raise ContractError("Context 的 built_from 与 Brief 不一致")
    return {
        "artifact_type": "story_design_candidate",
        "candidate_id": candidate_id,
        "project_id": brief["project_id"],
        "brief_ref": f"{brief['brief_id']}@{brief['brief_rev']}",
        "context_ref": context["context_id"],
        "status": "proposal_noncanonical",
        "authority": "ai_candidate:noncanonical",
        "content": model_output,
        "must_not_write_canon": True,
        "created_at": utc_now(),
    }


def create_decision_record(
    *,
    decision_id: str,
    brief: dict[str, Any],
    context: dict[str, Any],
    candidate: dict[str, Any],
    author_action: str,
    author_confirmation_ref: str | None,
    final_decision: dict[str, Any] | None = None,
    simulation: bool = False,
) -> dict[str, Any]:
    if author_action not in {"choose", "modify", "reject_all", "defer"}:
        raise ContractError("author_action 不合法")
    test_only = bool(author_confirmation_ref and "TEST_ONLY" in author_confirmation_ref)
    if test_only and not simulation:
        raise ContractError("TEST_ONLY confirmation 只能用于显式 simulation 分支")
    confirmed = bool(author_confirmation_ref and author_confirmation_ref.startswith(("author:", "chat:")))
    if author_action in {"choose", "modify"} and not confirmed:
        raise ContractError("创作性选择必须有真实作者 confirmation_ref")
    _require_same_project(brief, context, candidate)
    if candidate.get("brief_ref") != f"{brief['brief_id']}@{brief['brief_rev']}":
        raise ContractError("Candidate 的 brief_ref 与 Brief 不一致")
    if candidate.get("context_ref") != context["context_id"]:
        raise ContractError("Candidate 的 context_ref 与 Context 不一致")
    if context.get("built_from", {}).get("brief_id") != brief["brief_id"] \
            or context.get("built_from", {}).get("brief_rev") != brief["brief_rev"]:
        raise ContractError("Context 的 built_from 与 Brief 不一致")
    if author_action in {"choose", "modify"}:
        authority = (f"simulation_author_decision:{decision_id}" if simulation and confirmed
                     else f"author_decision:{decision_id}")
        status = ("simulated_confirmed_for_test" if simulation and confirmed
                  else "confirmed_for_plan_only")
    else:
        # reject_all / defer never gain planning writeback authority, even
        # with a real author confirmation.
        authority = None
        status = "unconfirmed" if not confirmed else f"{author_action}_no_writeback"
    return {
        "artifact_type": "decision_record",
        "decision_id": decision_id,
        "project_id": brief["project_id"],
        "brief_ref": f"{brief['brief_id']}@{brief['brief_rev']}",
        "context_ref": context["context_id"],
        "candidate_ref": candidate["candidate_id"],
        "author_action": author_action,
        "confirmation_ref": author_confirmation_ref,
        "authority": authority,
        "final_decision": final_decision or {},
        "status": status,
        "simulation_only": simulation,
        "created_at": utc_now(),
    }


def make_planning_diff(*, diff_id: str, state: dict[str, Any], decision: dict[str, Any], plan: dict[str, Any], allow_simulation: bool = False) -> dict[str, Any]:
    validate_story_state(state)
    _require_same_project(decision, state)
    if decision.get("author_action") not in {"choose", "modify"}:
        raise ContractError("只有 choose/modify 的确认 Decision 才能生成 planning Diff")
    simulated = decision.get("status") == "simulated_confirmed_for_test"
    if simulated and not allow_simulation:
        raise ContractError("simulation Decision 不得在生产路径生成 Diff")
    if decision.get("status") not in {"confirmed_for_plan_only", "simulated_confirmed_for_test"} or not decision.get("authority"):
        raise ContractError("未确认的 StoryDesign 不能生成 planning writeback")
    return {
        "artifact_type": "state_diff",
        "diff_id": diff_id,
        "project_id": state["project_id"],
        "base_state_rev": state["state_rev"],
        "writeback_class": "creative_change",
        "source_ref": decision["authority"],
        "changes": [{"target": "approved_plan", "operation": "append", "value": plan}],
        "apply_status": "pending",
        "canon_changed": False,
        "simulation_only": simulated,
        "created_at": utc_now(),
    }


def apply_diff(state: dict[str, Any], diff: dict[str, Any], decision: dict[str, Any] | None = None, *, allow_simulation: bool = False) -> dict[str, Any]:
    """Apply only permitted deterministic mutations, returning a new state."""
    validate_story_state(state)
    if diff.get("project_id") != state["project_id"]:
        raise ContractError("Diff 与 Story State project_id 不一致")
    if decision is not None and decision.get("project_id") != state["project_id"]:
        raise ContractError("Decision 与 Story State project_id 不一致")
    if diff.get("base_state_rev") != state["state_rev"]:
        raise ContractError("旧 base_state_rev Diff 不得覆盖当前 Story State")
    writeback_class = diff.get("writeback_class")
    if writeback_class == "ambiguous_inference":
        raise ContractError("ambiguous_inference 永远不得自动 apply")
    if writeback_class == "creative_change":
        simulated = bool(decision and decision.get("status") == "simulated_confirmed_for_test")
        if simulated and not allow_simulation:
            raise ContractError("simulation Decision 不得在生产路径 apply")
        if not decision or decision.get("status") not in {"confirmed_for_plan_only", "simulated_confirmed_for_test"}:
            raise ContractError("creative_change 缺少作者确认")
        if diff.get("source_ref") != decision.get("authority"):
            raise ContractError("creative_change source_ref 与 Decision 不一致")
    elif writeback_class == "mechanical_settlement":
        if not str(diff.get("source_ref", "")).startswith("accepted_text:"):
            raise ContractError("mechanical_settlement 必须来自 accepted_text")
    else:
        raise ContractError("未知 writeback_class")

    result = deepcopy(state)
    for change in diff.get("changes", []):
        if change.get("target") != "approved_plan" or change.get("operation") != "append":
            raise ContractError("E1-A 只允许 StoryDesign 写入 approved_plan，不能修改 Canon")
        plan = deepcopy(change.get("value"))
        if not isinstance(plan, dict) or not plan.get("id"):
            raise ContractError("planning 写入必须包含 plan id")
        plan["authority"] = diff["source_ref"]
        plan["occurred"] = False
        result["approved_plan"].append(plan)
    result["state_rev"] += 1
    result["last_authority_source"] = diff["source_ref"]
    validate_story_state(result)
    return result


def trace_record(*, trace_id: str, brief: dict[str, Any], context: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "story_design_trace",
        "trace_id": trace_id,
        "project_id": brief["project_id"],
        "brief_ref": f"{brief['brief_id']}@{brief['brief_rev']}",
        "context_ref": context["context_id"],
        "candidate_ref": candidate["candidate_id"],
        "source_versions": brief["source_versions"],
        "retrieval": context["retrieval"],
        "knowledge_provenance": [
            hit["provenance"]
            | {
                "selection_ref": hit["selection_ref"],
                "source_kind": hit["source_kind"],
                "source_id": hit["source_id"],
                "source_anchor": hit["source_anchor"],
            }
            for hit in context["selected_knowledge_hits"]
        ],
        "created_at": utc_now(),
    }
