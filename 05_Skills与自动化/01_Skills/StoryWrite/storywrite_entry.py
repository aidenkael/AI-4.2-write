"""THIN_STORYWRITE_CONSUMER_SLICE: the thinnest StoryWrite operation layer.

Scope (approved as THIN_ORCHESTRATION_BUILD_ALLOWED, 2026-08-16):

    Only remove the mechanical cranks that repeated across two real
    vertical slices.  This is NOT a Writer runtime, NOT a Writer platform,
    NOT a prompt framework, and it adds NO new Final Schema.  Every contract
    (Story State shape, authority rules, Brief, Context selection, stale
    semantics) is reused verbatim from the frozen E1 / E2 / E3-A runtimes.

Three automated cranks, in priority order:

    P0  MECHANICAL_SETTLEMENT_ASSIST   apply_settlement()
    P1  Brief / Context preparation    prepare_creation_brief() / prepare_context()
    P2  recent prose window            prepare_recent_prose_window()

Division of labor (same as every frozen subsystem):

    model  = semantic judgment (what was said/done, which classification,
             which State entries this scene needs, which BKP if any)
    code   = deterministic guardrail (three-class gate, author acceptance
             gate, simulation impersonation guard, rev/authority/id
             consistency, explicit selection only, no fallback)

Settlement keeps the three-class semantic discipline proven in the two real
slices: only ``mechanical`` (what the accepted prose literally said/happened)
may ever enter Story State; ``ambiguous`` and ``creative`` are recorded in
the report and NEVER written, by any mode, under any flag.

Production writeback additionally requires explicit author acceptance; the
runtime itself mints the ``accepted_text:<scene_ref>`` authority so no
caller can inject an arbitrary authority.  Shadow / experiment continuity
must use a ``manual_import:`` authority and can never claim acceptance.
Simulation/test sources can never wear a production ``author_decision:`` or
``accepted_text:`` face (the historical ``author_decision:storydesign-simulated``
entries stay untouched as historical evidence; only NEW inputs are rejected).

Recent prose is a simple tail window (target ~1000-2000 Chinese chars):
non-authoritative, no RAG, no embeddings, with a minimal writing hint
(absorb short-term continuity, never copy the previous scene verbatim).
"""

from __future__ import annotations

import importlib.util
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

# Reuse the frozen chain in place: ContextCompiler -> StoryPlan -> E1 runtime.
# No parallel runtime, no copy of any frozen logic.
_SKILLS_ROOT = Path(__file__).resolve().parents[1]
_CONTEXT_COMPILER_DIR = _SKILLS_ROOT / "ContextCompiler"
if str(_CONTEXT_COMPILER_DIR) not in sys.path:
    sys.path.insert(0, str(_CONTEXT_COMPILER_DIR))
_cc = sys.modules.get("ai_write_context_compiler")
if _cc is None:
    _spec = importlib.util.spec_from_file_location(
        "ai_write_context_compiler", _CONTEXT_COMPILER_DIR / "context_compiler.py"
    )
    if _spec is None or _spec.loader is None:
        raise ImportError("无法加载 ContextCompiler context_compiler")
    _cc = importlib.util.module_from_spec(_spec)
    sys.modules["ai_write_context_compiler"] = _cc
    _spec.loader.exec_module(_cc)
_e1 = sys.modules["ai_write_story_runtime"]  # loaded transitively by StoryPlan

ContractError = _cc.ContractError
CANON_AREAS = _cc.CANON_AREAS
validate_author_intent = _cc.validate_author_intent
validate_story_state = _cc.validate_story_state
compile_context = _cc.compile_context
context_package_is_stale = _cc.context_package_is_stale
compile_creation_brief = _e1.compile_creation_brief
utc_now = _e1.utc_now


CAPABILITY = {
    "capability_id": "storywrite_entry.v0",
    "solves": "消除跨场景真实写作中已两轮重复的机械摇柄：结算三分类落盘、Brief/Context 准备、recent prose 窗口。",
    "inputs": ["accepted or frozen-draft scene prose", "model settlement candidates", "Author Intent", "Story State",
               "model state selection", "previous scene tail prose"],
    "may_read": ["Story State", "Author Intent", "frozen E1/E2/E3-A contracts"],
    "writes_state": True,
    "confirmation_required_for_writes": "production writeback 必须显式 author acceptance；shadow 只允许 manual_import: authority。",
    "outputs": ["settlement report + new Story State (mechanical only)", "Creation Brief", "Context Package", "recent prose window"],
}

# ---------------------------------------------------------------------------
# P0  MECHANICAL_SETTLEMENT_ASSIST
# ---------------------------------------------------------------------------

SETTLEMENT_CLASSIFICATIONS = ("mechanical", "ambiguous", "creative")
SETTLEMENT_OPERATIONS = ("append", "replace_existing")

# New inputs wearing a production authority prefix while carrying a
# simulation/test marker are impersonation and are rejected.  Existing
# historical artifacts are never re-validated retroactively.
_PRODUCTION_AUTHORITY_PREFIXES = ("author_decision:", "accepted_text:")
_SIMULATION_IMPERSONATION_MARKERS = (
    "simulat", "test_only", "test-only", "sandbox", "shadow", "experiment",
)


def reject_simulation_impersonation(authority: str) -> None:
    """Guard D: simulation/test sources may not wear production authority."""
    if not isinstance(authority, str) or not authority:
        raise ContractError("authority 必须是非空字符串")
    if authority.startswith(_PRODUCTION_AUTHORITY_PREFIXES):
        lowered = authority.lower()
        if any(marker in lowered for marker in _SIMULATION_IMPERSONATION_MARKERS):
            raise ContractError(
                f"simulation/test source 不得伪装 production authority：{authority}"
            )


def _resolve_write_authority(
    *,
    mode: str,
    author_accepted: bool,
    accepted_scene_ref: str | None,
    shadow_authority: str | None,
) -> str:
    if mode == "production":
        if not author_accepted:
            raise ContractError(
                "production writeback 必须获得明确 author acceptance；"
                "FROZEN EXPERIMENT DRAFT 不得因本工具存在而升级为 accepted_text"
            )
        if not accepted_scene_ref or not str(accepted_scene_ref).strip():
            raise ContractError("production writeback 需要 accepted_scene_ref")
        authority = f"accepted_text:{str(accepted_scene_ref).strip()}"
        reject_simulation_impersonation(authority)
        return authority
    if mode == "shadow":
        if author_accepted:
            raise ContractError("shadow 结算不得声称已获得 author acceptance")
        if not shadow_authority or not str(shadow_authority).startswith("manual_import:"):
            raise ContractError(
                "shadow 结算 authority 必须以 manual_import: 开头；"
                "shadow/test-only 来源不得使用 accepted_text: 或 author_decision:"
            )
        return str(shadow_authority)
    raise ContractError(f"未知 settlement mode：{mode}（允许 production / shadow）")


def apply_settlement(
    *,
    state: dict[str, Any],
    settlement: dict[str, Any],
    mode: str,
    author_accepted: bool = False,
    accepted_scene_ref: str | None = None,
    shadow_authority: str | None = None,
) -> dict[str, Any]:
    """Apply ONLY the mechanical part of a model settlement candidate.

    ``settlement`` is model output:
        {"scene_ref": str,
         "candidates": [{"classification": "mechanical|ambiguous|creative",
                          "target_area": <CANON area>,
                          "entry": {"id": ..., ...},
                          "operation": "append" | "replace_existing",
                          "reason": str}]}

    The model judges classification and content (semantic brain); this runtime
    enforces the three-class gate, the acceptance gate, authority minting,
    area/id/rev consistency and final validate_story_state (deterministic
    guardrail).  Returns a report; the new state is inside it, never written
    to disk by this function.
    """
    validate_story_state(state)
    if not isinstance(settlement, dict):
        raise ContractError("settlement 必须是对象")
    scene_ref = settlement.get("scene_ref")
    candidates = settlement.get("candidates")
    if not scene_ref or not isinstance(candidates, list):
        raise ContractError("settlement 需要 scene_ref 与 candidates 列表")

    authority = _resolve_write_authority(
        mode=mode,
        author_accepted=author_accepted,
        accepted_scene_ref=accepted_scene_ref,
        shadow_authority=shadow_authority,
    )

    result = deepcopy(state)
    applied: list[dict[str, Any]] = []
    not_writable: list[dict[str, Any]] = []

    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ContractError("settlement candidate 必须是对象")
        classification = candidate.get("classification")
        reason = str(candidate.get("reason") or "")
        if classification not in SETTLEMENT_CLASSIFICATIONS:
            raise ContractError(
                f"非法 settlement classification：{classification}"
                f"（允许 {', '.join(SETTLEMENT_CLASSIFICATIONS)}）"
            )
        if classification != "mechanical":
            # ambiguous / creative never enter Story State, in any mode.
            not_writable.append({
                "classification": classification,
                "target_area": candidate.get("target_area"),
                "entry_id": (candidate.get("entry") or {}).get("id") if isinstance(candidate.get("entry"), dict) else None,
                "reason": reason or f"{classification} 类永远不得自动写入 Story State",
            })
            continue

        target_area = candidate.get("target_area")
        entry = candidate.get("entry")
        operation = candidate.get("operation", "append")
        if target_area not in CANON_AREAS:
            raise ContractError(f"mechanical settlement target_area 非法：{target_area}")
        if operation not in SETTLEMENT_OPERATIONS:
            raise ContractError(f"mechanical settlement operation 非法：{operation}")
        if not isinstance(entry, dict) or not entry.get("id"):
            raise ContractError("mechanical settlement entry 必须是带 id 的对象")
        if candidate.get("project_id") not in (None, state["project_id"]):
            raise ContractError("settlement candidate project_id 与 Story State 不一致")

        # Authority is minted by the runtime; the model can never choose it.
        clean_entry = deepcopy(entry)
        clean_entry["authority"] = authority

        existing_ids = [item.get("id") for item in result.get(target_area, [])]
        if operation == "append":
            if clean_entry["id"] in existing_ids:
                raise ContractError(
                    f"{target_area} 中 id={clean_entry['id']} 已存在；append 不得使用既有 id"
                )
            result.setdefault(target_area, []).append(clean_entry)
        else:  # replace_existing
            if clean_entry["id"] not in existing_ids:
                raise ContractError(
                    f"{target_area} 中找不到 id={clean_entry['id']}；replace_existing 必须指向既有 id"
                )
            result[target_area] = [
                clean_entry if item.get("id") == clean_entry["id"] else item
                for item in result[target_area]
            ]
        applied.append({
            "classification": "mechanical",
            "target_area": target_area,
            "entry_id": clean_entry["id"],
            "operation": operation,
            "authority": authority,
            "reason": reason,
        })

    # F0-1: only bump state_rev / authority when at least one mechanical
    # candidate was actually written.  A pure-ambiguous / pure-creative
    # settlement must not produce a phantom revision change, because
    # state_rev participates in Brief / Context stale detection.
    if applied:
        result["state_rev"] = state["state_rev"] + 1
        result["last_authority_source"] = authority
    validate_story_state(result)
    return {
        "artifact_type": "settlement_report",
        "scene_ref": scene_ref,
        "mode": mode,
        "status": "APPLIED" if applied else "APPLIED_NO_MECHANICAL",
        "authority": authority if applied else None,
        "base_state_rev": state["state_rev"],
        "new_state_rev": result["state_rev"],
        "applied": applied,
        "not_writable": not_writable,
        "new_state": result,
        "created_at": utc_now(),
    }


# ---------------------------------------------------------------------------
# P1  Brief / Context preparation (thin pass-through, zero new contract)
# ---------------------------------------------------------------------------

def prepare_creation_brief(
    *,
    project_id: str,
    brief_id: str,
    author_input: str,
    intent: dict[str, Any],
    state: dict[str, Any],
    semantic_interpretation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reuse the frozen E1 Creation Brief contract; no parallel brief schema."""
    return compile_creation_brief(
        project_id=project_id,
        brief_id=brief_id,
        author_input=author_input,
        intent=intent,
        state=state,
        semantic_interpretation=semantic_interpretation,
    )


def prepare_context(
    *,
    context_id: str,
    brief: dict[str, Any],
    intent: dict[str, Any],
    state: dict[str, Any],
    state_selections: list[dict[str, Any]],
    conflicts_or_tensions: list[dict[str, Any]] | None = None,
    retrieval: Any = None,
    selected_knowledge_ids: list[str] | None = None,
    max_bkp_hits: int = 3,
    allow_simulation_sources: bool = False,
) -> dict[str, Any]:
    """Reuse the frozen E3-A Context Compiler; explicit selection only.

    ``state_selections`` is the model's semantic choice.  An empty selection
    stays empty: this layer never falls back to dumping the whole State, and
    BKP stays BKP_POSTHOC_SPARSE_PROBLEM_DRIVEN via the frozen E1 gate.
    """
    if not isinstance(state_selections, list):
        raise ContractError("state_selections 必须是显式列表（可为空，但不 fallback 全 State）")
    return compile_context(
        context_id=context_id,
        brief=brief,
        intent=intent,
        state=state,
        state_selections=state_selections,
        conflicts_or_tensions=conflicts_or_tensions,
        retrieval=retrieval,
        selected_knowledge_ids=selected_knowledge_ids,
        max_bkp_hits=max_bkp_hits,
        allow_simulation_sources=allow_simulation_sources,
    )


# ---------------------------------------------------------------------------
# P2  recent prose window (simple tail window; NOT authority; no RAG)
# ---------------------------------------------------------------------------

RECENT_PROSE_MIN_CHARS = 1000
RECENT_PROSE_MAX_CHARS = 2000
RECENT_PROSE_WRITING_HINT = (
    "recent prose 只是短时连续性输入（语气、意象、即时余波），不是 Canon、不是 authority；"
    "吸收它，但不得逐字复写上一场的表达，重复出现的母题必须改写成属于本场的变奏。"
)


def prepare_recent_prose_window(
    *,
    prose_text: str,
    scene_ref: str,
    min_chars: int = RECENT_PROSE_MIN_CHARS,
    max_chars: int = RECENT_PROSE_MAX_CHARS,
) -> dict[str, Any]:
    """Cut the previous scene's tail into a small, non-authoritative window.

    Prioritizes the END of the most recent scene (where continuity residue is
    strongest).  No embeddings, no vector DB, no full-text RAG: a plain tail.
    """
    if not isinstance(prose_text, str) or not prose_text.strip():
        raise ContractError("recent prose 需要非空正文文本")
    if not scene_ref or not str(scene_ref).strip():
        raise ContractError("recent prose 需要 scene_ref 以保留可追溯来源")
    if min_chars < 1 or max_chars < min_chars:
        raise ContractError("recent prose 窗口参数非法（需 1 <= min <= max）")

    text = prose_text.strip()
    truncated_from_tail = len(text) > max_chars
    window = text[-max_chars:] if truncated_from_tail else text
    return {
        "artifact_type": "recent_prose_window",
        "scene_ref": str(scene_ref).strip(),
        "is_authority": False,
        "must_not_write_state": True,
        "target_range_chars": [min_chars, max_chars],
        "window_chars": len(window),
        "truncated_from_tail": truncated_from_tail,
        "below_target": len(window) < min_chars,
        "writing_hint": RECENT_PROSE_WRITING_HINT,
        "text": window,
        "created_at": utc_now(),
    }
