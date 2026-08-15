"""E3-A Context Compiler: the minimal "task-relevant own-story-state selection" layer.

Given a current Creation Brief, Author Intent and Story State, plus a
model/Skill semantic selection of which pieces of the author's OWN story state
this task needs (and optionally a few BKP hits), produce a Context Package that
is:

    small / traceable / rebuildable / non-authoritative / stale-aware

The runtime never makes literary relevance judgments.  "Is this character fact
worth selecting", "is this foreshadowing important for this chapter" and "is
this BKP card the best literary choice" all belong to the model/Skill.  The
runtime only verifies that what was selected really exists in the current
authoritative state, is active, is fresh, is properly sourced, is deduped and
can be rebuilt:

    AI = semantic brain
    code = deterministic guardrail

E3-A deliberately does NOT redo E1.  It reuses, without modifying:

- the E1 story_runtime authority / revision / BKP retrieval + provenance guard
  (build_context is invoked read-only solely to reuse the frozen BKP gate);
- the E2 StoryPlan resolve_plan_activity projection for current active planning;
- the G4 Context Package authority boundary (BKP != Canon, planning != Canon,
  Context never writes Canon).

Unlike E1 build_context -- which still drops whole Story State blocks into the
Context -- E3-A copies only the authoritative entries that the semantic
selection explicitly names.  An empty selection is legal and never falls back
to "dump the whole State".
"""

from __future__ import annotations

import importlib.util
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

# Reuse StoryPlan in place (which itself loads the E1 runtime); no parallel
# runtime and no E1/E2 refactor.
_SKILLS_ROOT = Path(__file__).resolve().parents[1]
_STORYPLAN_DIR = _SKILLS_ROOT / "StoryPlan"
if str(_STORYPLAN_DIR) not in sys.path:
    sys.path.insert(0, str(_STORYPLAN_DIR))
_sp = sys.modules.get("ai_write_story_plan")
if _sp is None:
    _spec = importlib.util.spec_from_file_location("ai_write_story_plan", _STORYPLAN_DIR / "story_plan.py")
    if _spec is None or _spec.loader is None:
        raise ImportError("无法加载 StoryPlan story_plan")
    _sp = importlib.util.module_from_spec(_spec)
    sys.modules["ai_write_story_plan"] = _sp
    _spec.loader.exec_module(_sp)

ContractError = _sp.ContractError
CANON_AREAS = _sp.CANON_AREAS
validate_author_intent = _sp.validate_author_intent
validate_story_state = _sp.validate_story_state
build_context = _sp.build_context  # E1 gate, reused read-only for the frozen BKP policy
resolve_plan_activity = _sp.resolve_plan_activity
SIMULATION_ONLY_AUTHORITIES = _sp.SIMULATION_ONLY_AUTHORITIES
# Production-trusted future planning authorities, reused verbatim from the
# frozen StoryPlan semantic (E2-A / E2-C): author decisions and manual imports
# are trusted; simulation is not.  No second, parallel whitelist is kept here.
TRUSTED_PLANNING_SOURCE_AUTHORITIES = _sp.TRUSTED_PLANNING_SOURCE_AUTHORITIES
utc_now = _sp.utc_now


CAPABILITY = {
    "capability_id": "context_compiler.v0",
    "solves": "把当前创作任务真正需要的少量自身小说状态与少量 BKP 编译成小而可追溯、可重建、非权威、stale-aware 的 Context Package。",
    "inputs": ["Creation Brief", "Author Intent", "Story State", "semantic state selection",
               "optional selected BKP ids", "optional retrieval callable"],
    "may_read": ["Author Intent", "Story State", "approved_plan active projection",
                 "selected BKP through the frozen E1 KnowledgeRetrieve gate"],
    "writes_state": False,
    "confirmation_required_for_writes": "Context Package 永不写回 Canon / Story State；它是可重建派生工件。",
    "outputs": ["Context Package (small, traceable, rebuildable, non-authoritative, stale-aware)"],
}

# A semantic selection may address any Canon area plus approved_plan.
# approved_plan is handled specially: only a current ACTIVE planning entry may
# be selected (see resolve_plan_activity); superseded history stays out.
SELECTABLE_AREAS = CANON_AREAS + ("approved_plan",)

# E3-A keeps the small, always-present Intent core and copies optional fields
# only when they already exist on the real Author Intent.  The model never
# fabricates Intent values: everything comes straight from the current Intent.
_INTENT_CORE_FIELDS = ("work_direction", "reader_promise", "hard_constraints", "open_space")
_INTENT_OPTIONAL_FIELDS = ("current_priority", "current_focus", "avoidances")


def _require_same_project(*artifacts: dict[str, Any]) -> None:
    # Minimal in-place copy of E1's private helper (story_plan does not
    # re-export it).  Kept tiny on purpose; semantics identical to E1.
    ids = {artifact.get("project_id") for artifact in artifacts}
    if len(ids) != 1 or None in ids:
        raise ContractError(f"工件 project_id 不一致: {sorted(str(i) for i in ids)}")


def _select_intent(intent: dict[str, Any]) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for field in _INTENT_CORE_FIELDS + _INTENT_OPTIONAL_FIELDS:
        if field in intent:
            selected[field] = deepcopy(intent[field])
    return selected


def _resolve_state_selections(
    state: dict[str, Any],
    state_selections: list[dict[str, Any]],
    *,
    allow_simulation_sources: bool,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, str]], int]:
    """Deterministically resolve semantic selections against the real State.

    Returns (selected_by_area, selection_reasons, selected_plan_count).  Only
    authoritative entries from the current State are deep-copied through; the
    model's ``reason`` travels alongside but never replaces the original item.
    """
    activity = resolve_plan_activity(state)
    active_ids = set(activity["active"])

    # Deterministic approved_plan index: a selection ref must resolve to exactly
    # one authoritative planning entry.  A missing id or a duplicate id would
    # make the ref ambiguous, so both are ContractErrors -- never silent
    # first/last/dedupe.  This mirrors the same-area duplicate-id ambiguity
    # rejection of the Canon areas and is defensive on top of E1
    # validate_story_state (which already requires plan ids).
    plans_by_id: dict[str, dict[str, Any]] = {}
    for plan in state.get("approved_plan", []):
        pid = plan.get("id")
        if not pid:
            raise ContractError("approved_plan 条目缺少 id，无法确定性解析 selection ref")
        if pid in plans_by_id:
            raise ContractError(
                f"approved_plan 中 id={pid} 重复，selection ref 指向不明确（duplicate-id ambiguity）"
            )
        plans_by_id[pid] = plan

    selected_by_area: dict[str, list[dict[str, Any]]] = {}
    reasons: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    selected_plan_count = 0

    for sel in state_selections:
        if not isinstance(sel, dict):
            raise ContractError("state selection 条目必须是对象")
        area = sel.get("area")
        sel_id = sel.get("id")
        reason = sel.get("reason")
        if not area or not sel_id:
            raise ContractError("state selection 必须同时提供 area 与 id")
        if area not in SELECTABLE_AREAS:
            raise ContractError(f"不支持的 selection area：{area}（允许：{', '.join(SELECTABLE_AREAS)}）")
        if not reason or not str(reason).strip():
            raise ContractError(f"selection {area}:{sel_id} 必须提供非空 reason，保证可追溯")
        key = (area, sel_id)
        if key in seen:
            raise ContractError(f"重复选择同一 state ref：{area}:{sel_id}")
        seen.add(key)

        if area == "approved_plan":
            plan = plans_by_id.get(sel_id)
            if plan is None:
                raise ContractError(f"approved_plan 中找不到 id={sel_id}")
            if sel_id not in active_ids:
                raise ContractError(
                    f"approved_plan {sel_id} 已被 supersede（非 active）；"
                    "历史 planning 保留在 append-only history 中，但不进入当前执行 Context"
                )
            authority = str(plan.get("authority", ""))
            # Production planning authority authenticity, aligned with the
            # frozen StoryPlan semantic: default trust = author_decision: /
            # manual_import:; simulation_author_decision: is allowed ONLY under
            # the explicit test/sandbox gate.  "Not simulation" is NOT enough:
            # accepted_text: is a legal Canon authority but not a legal future
            # planning authority.
            effective_trusted = TRUSTED_PLANNING_SOURCE_AUTHORITIES
            if allow_simulation_sources:
                effective_trusted = effective_trusted + SIMULATION_ONLY_AUTHORITIES
            if not authority.startswith(effective_trusted):
                raise ContractError(
                    f"approved_plan {sel_id} 的 authority 不是可信未来规划来源：{authority}；"
                    "生产 Context 只允许 author_decision: / manual_import:"
                    "（simulation_author_decision: 仅显式 allow_simulation_sources=True 可用）"
                )
            item = deepcopy(plan)
            selected_plan_count += 1
        else:
            matches = [entry for entry in state.get(area, []) if entry.get("id") == sel_id]
            if not matches:
                raise ContractError(f"{area} 中找不到 id={sel_id} 的条目")
            if len(matches) > 1:
                raise ContractError(f"{area} 中 id={sel_id} 存在歧义（{len(matches)} 个条目同名）")
            item = deepcopy(matches[0])

        selected_by_area.setdefault(area, []).append(item)
        reasons.append({"source_ref": f"{area}:{sel_id}", "reason": str(reason)})

    return selected_by_area, reasons, selected_plan_count


def compile_context(
    *,
    context_id: str,
    brief: dict[str, Any],
    intent: dict[str, Any],
    state: dict[str, Any],
    state_selections: list[dict[str, Any]] | None = None,
    conflicts_or_tensions: list[dict[str, Any]] | None = None,
    retrieval: Callable[[str], Any] | None = None,
    selected_knowledge_ids: list[str] | None = None,
    max_bkp_hits: int = 3,
    allow_simulation_sources: bool = False,
) -> dict[str, Any]:
    """Compile a task-relevant Context Package.

    The model/Skill supplies ``state_selections`` (semantic brain); this runtime
    proves each selection is real, active, fresh and safely copyable, then copies
    ONLY those authoritative entries into ``selected_story_state``.  BKP handling
    is delegated to the frozen E1 gate and kept in a structurally separate area.
    Nothing here writes Canon / Story State: the package is a rebuildable,
    non-authoritative derived artifact.
    """
    validate_author_intent(intent)
    validate_story_state(state)
    _require_same_project(brief, intent, state)
    if not context_id:
        raise ContractError("Context 需要 context_id")
    # Build-time stale guard mirrors E1: a Brief compiled against an older
    # intent_rev / state_rev may not build a Context on current sources.
    if brief.get("source_versions") != {"intent_rev": intent["intent_rev"], "state_rev": state["state_rev"]}:
        raise ContractError("不能用过期 Brief 构建 Context（intent_rev/state_rev 不匹配）")

    state_selections = list(state_selections or [])
    selected_story_state, selection_reasons, selected_plan_count = _resolve_state_selections(
        state, state_selections, allow_simulation_sources=allow_simulation_sources,
    )

    # Reuse the frozen E1 BKP gate read-only: only take its selected hits,
    # retrieval info and BKP selection reason.  E3-A never re-implements
    # KnowledgeRetrieve and never modifies build_context.
    e1_context = build_context(
        context_id=context_id, brief=brief, intent=intent, state=state,
        retrieval=retrieval, max_bkp_hits=max_bkp_hits,
        selected_knowledge_ids=selected_knowledge_ids,
    )
    selected_bkp_hits = e1_context["selected_bkp_hits"]
    retrieval_info = e1_context["retrieval"]
    status = "CURRENT_WITH_BKP_GAP" if e1_context["status"] == "CURRENT_WITH_BKP_GAP" else "CURRENT"

    activity = resolve_plan_activity(state)
    total_state_items = sum(len(state.get(area, [])) for area in SELECTABLE_AREAS)
    selected_state_items = sum(len(items) for items in selected_story_state.values())

    conflicts: list[dict[str, Any]] = []
    for entry in (conflicts_or_tensions or []):
        item = dict(entry) if isinstance(entry, dict) else {"text": str(entry)}
        item["authority"] = "analysis_noncanonical"
        item["must_not_write_canon"] = True
        conflicts.append(item)

    return {
        "artifact_type": "context_package",
        "context_id": context_id,
        "project_id": brief["project_id"],
        "status": status,
        "built_from": {
            "brief_id": brief["brief_id"],
            "brief_rev": brief["brief_rev"],
            "intent_rev": intent["intent_rev"],
            "state_rev": state["state_rev"],
        },
        "selected_intent": _select_intent(intent),
        "selected_story_state": selected_story_state,
        "selected_bkp_hits": selected_bkp_hits,
        "selection_reason": selection_reasons,
        "conflicts_or_tensions": conflicts,
        "size_summary": {
            "total_state_items": total_state_items,
            "selected_state_items": selected_state_items,
            "total_active_plans": len(activity["active"]),
            "selected_active_plans": selected_plan_count,
            "selected_bkp_hits": len(selected_bkp_hits),
            "by_area": {area: len(items) for area, items in selected_story_state.items()},
        },
        "retrieval": retrieval_info,
        "created_at": utc_now(),
    }


def context_package_is_stale(
    context: dict[str, Any],
    brief: dict[str, Any],
    intent: dict[str, Any],
    state: dict[str, Any],
) -> bool:
    """E3-A stale check; more complete than E1 context_is_stale.

    Any change to brief_id / brief_rev / intent_rev / state_rev makes a built
    Context stale.  E1's context_is_stale is intentionally left untouched.
    """
    built = context.get("built_from", {})
    return (
        built.get("brief_id") != brief.get("brief_id")
        or built.get("brief_rev") != brief.get("brief_rev")
        or built.get("intent_rev") != intent.get("intent_rev")
        or built.get("state_rev") != state.get("state_rev")
    )
