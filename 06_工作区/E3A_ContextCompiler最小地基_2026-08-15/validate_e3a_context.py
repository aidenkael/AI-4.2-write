"""E3-A disposable sandbox validator.

Reuses the sandbox fixtures defined in test_context_compiler.py (the real
minimal sandbox from section 21) and emits a small JSON evidence file showing
that real selection happened: selected_state_items << total_state_items, empty
selection never falls back to the whole State, and the approved_plan activity
projection keeps superseded history out of the Context.

This validator never touches Canon / Story State; it only reads and compiles.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
SKILL_DIR = HERE.parents[2] / "05_Skills与自动化" / "01_Skills" / "ContextCompiler"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from context_compiler import compile_context, resolve_plan_activity  # noqa: E402
import test_context_compiler as T  # noqa: E402


def main() -> None:
    ctx = compile_context(
        context_id="e3a-sandbox-ctx",
        brief=T.make_brief(),
        intent=T.INTENT,
        state=T.STATE,
        state_selections=T.SELECTIONS,
        retrieval=T.fake_retrieve_must_not_be_called,
    )
    activity = resolve_plan_activity(T.STATE)

    empty_ctx = compile_context(
        context_id="e3a-empty-ctx",
        brief=T.make_brief(),
        intent=T.INTENT,
        state=T.STATE,
        state_selections=[],
        retrieval=T.fake_retrieve_must_not_be_called,
    )

    result = {
        "task": T.make_brief()["author_input"],
        "status": ctx["status"],
        "built_from": ctx["built_from"],
        "size_summary": ctx["size_summary"],
        "selected_refs": [r["source_ref"] for r in ctx["selection_reason"]],
        "selected_story_state_areas": {
            area: [item["id"] for item in items]
            for area, items in ctx["selected_story_state"].items()
        },
        "approved_plan_activity": {
            "active": activity["active"],
            "superseded": activity["superseded"],
        },
        "selection_reduced_state": ctx["size_summary"]["selected_state_items"] < ctx["size_summary"]["total_state_items"],
        "empty_selection": {
            "selected_state_items": empty_ctx["size_summary"]["selected_state_items"],
            "selected_story_state": empty_ctx["selected_story_state"],
            "fallback_to_full_state": empty_ctx["selected_story_state"] != {},
        },
        "selected_bkp_hits": len(ctx["selected_bkp_hits"]),
        "note": "SIMULATED/TEST_ONLY fixtures only; nothing here is an author confirmation.",
    }

    out = HERE.parent / "e3a_sandbox_result.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
