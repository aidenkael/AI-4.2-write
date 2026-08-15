"""Tests for the thin StoryWrite operation layer (THIN_STORYWRITE_CONSUMER_SLICE).

Coverage required by the experiment contract:

1. mechanical candidate -> safe State-contract-compliant candidate update
2. ambiguous never enters State
3. creative never enters State
4. production writeback without explicit author acceptance -> rejected
5. simulation/test authority cannot impersonate production author_decision
6. State rev / authority / existing-id constraints preserved
7. recent prose window is a non-authoritative derived input
8. Context still selects only explicit entries (no whole-State fallback)
9. frozen subsystem regressions are run separately (ContextCompiler /
   StoryPlan / StoryDesign suites untouched and re-run green).
"""

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from storywrite_entry import (
    ContractError,
    RECENT_PROSE_WRITING_HINT,
    apply_settlement,
    context_package_is_stale,
    prepare_context,
    prepare_creation_brief,
    prepare_recent_prose_window,
    reject_simulation_impersonation,
)


def make_intent():
    return {
        "project_id": "thin-project", "intent_rev": 2,
        "work_direction": "海岛物流站长篇：旧债与姐妹合作",
        "reader_promise": "合作机器运转的同时冲突逐步显形",
        "hard_constraints": ["不揭示父亲旧债真正用途"],
        "open_space": ["宋乔十年前离开的完整原因"],
    }


def make_state():
    return {
        "project_id": "thin-project", "state_rev": 3,
        "canon_facts": [
            {"id": "canon.seed.road", "fact": "岛上一条联运线路。", "authority": "manual_import:seed"},
            {"id": "canon.seed.debt", "fact": "父亲留下一笔旧债。", "authority": "manual_import:seed"},
        ],
        "character_state": [
            {"id": "char.state.songning.belief", "name": "宋宁",
             "status": "相信账要一笔笔算清。", "authority": "manual_import:experiment_shadow_from_W1"},
        ],
        "relationship_state": [
            {"id": "rel.state.sisters", "relation": "姐妹",
             "status": "合作必要，冲突显形。", "authority": "manual_import:experiment_shadow_from_W1"},
        ],
        "occurred_events": [
            {"id": "event.w1.negotiation", "event": "公开谈判完成。",
             "authority": "manual_import:experiment_shadow_from_W1"},
        ],
        "open_threads": [
            {"id": "thread.zheng.month-end", "thread": "郑国栋月底要答复。",
             "authority": "manual_import:experiment_shadow_from_W1"},
        ],
        "approved_plan": [
            {"id": "plan.design.direction.island", "target_ref": "direction",
             "content": "海岛联运方向。", "occurred": False,
             "authority": "manual_import:seed"},
        ],
    }


def mechanical_settlement(entry_id="event.w2.zhou-decision", area="occurred_events"):
    return {
        "scene_ref": "scene2-W1-frozen",
        "candidates": [
            {"classification": "mechanical", "target_area": area,
             "entry": {"id": entry_id, "event": "周昌顺给出货量决定。"},
             "operation": "append", "reason": "正文明确成立的话语动作。"},
        ],
    }


class SettlementGateTests(unittest.TestCase):
    def test_mechanical_candidate_applies_as_valid_state_update(self):
        """1: mechanical -> compliant candidate update, rev bumped, valid State."""
        state = make_state()
        report = apply_settlement(
            state=state, settlement=mechanical_settlement(), mode="shadow",
            shadow_authority="manual_import:experiment_shadow_from_W2",
        )
        self.assertEqual(report["status"], "APPLIED")
        self.assertEqual(report["base_state_rev"], 3)
        self.assertEqual(report["new_state_rev"], 4)
        new_state = report["new_state"]
        ids = [item["id"] for item in new_state["occurred_events"]]
        self.assertIn("event.w2.zhou-decision", ids)
        written = [i for i in new_state["occurred_events"] if i["id"] == "event.w2.zhou-decision"][0]
        self.assertEqual(written["authority"], "manual_import:experiment_shadow_from_W2")
        # base state untouched (pure function)
        self.assertNotIn("event.w2.zhou-decision", [i["id"] for i in state["occurred_events"]])

    def test_ambiguous_never_enters_state(self):
        """2: ambiguous candidates are reported, never written."""
        settlement = mechanical_settlement()
        settlement["candidates"].append({
            "classification": "ambiguous", "target_area": "relationship_state",
            "entry": {"id": "rel.sisters.broken", "status": "姐妹彻底决裂。"},
            "operation": "append", "reason": "需要解释，正文未明说。",
        })
        report = apply_settlement(
            state=make_state(), settlement=settlement, mode="shadow",
            shadow_authority="manual_import:experiment_shadow_from_W2",
        )
        areas = ("canon_facts", "character_state", "relationship_state",
                 "occurred_events", "open_threads")
        for area in areas:
            self.assertNotIn("rel.sisters.broken", [i["id"] for i in report["new_state"].get(area, [])])
        self.assertEqual([n["classification"] for n in report["not_writable"]], ["ambiguous"])

    def test_creative_never_enters_state(self):
        """3: creative candidates are reported, never written, even shadow."""
        settlement = {
            "scene_ref": "scene2-W1-frozen",
            "candidates": [{
                "classification": "creative", "target_area": "canon_facts",
                "entry": {"id": "canon.debt.used-for-hospital",
                          "fact": "旧债用于父亲治病。"},
                "operation": "append", "reason": "重大方向，属作者决定。",
            }],
        }
        report = apply_settlement(
            state=make_state(), settlement=settlement, mode="shadow",
            shadow_authority="manual_import:experiment_shadow_from_W2",
        )
        self.assertEqual(report["status"], "APPLIED_NO_MECHANICAL")
        self.assertEqual(report["new_state"]["state_rev"], 4)
        self.assertNotIn("canon.debt.used-for-hospital",
                         [i["id"] for i in report["new_state"]["canon_facts"]])
        self.assertEqual(report["not_writable"][0]["classification"], "creative")

    def test_production_writeback_requires_explicit_author_acceptance(self):
        """4: no acceptance -> production writeback refused; with acceptance it
        mints accepted_text: authority."""
        state = make_state()
        with self.assertRaises(ContractError):
            apply_settlement(
                state=state, settlement=mechanical_settlement(),
                mode="production", author_accepted=False,
                accepted_scene_ref="scene2",
            )
        with self.assertRaises(ContractError):
            apply_settlement(
                state=state, settlement=mechanical_settlement(),
                mode="production", author_accepted=True, accepted_scene_ref="",
            )
        report = apply_settlement(
            state=state, settlement=mechanical_settlement(),
            mode="production", author_accepted=True, accepted_scene_ref="scene2",
        )
        self.assertEqual(report["authority"], "accepted_text:scene2")

    def test_simulation_authority_cannot_impersonate_production(self):
        """5: simulation/test sources may not wear author_decision:/accepted_text:."""
        # Guard is available for any new input...
        with self.assertRaises(ContractError):
            reject_simulation_impersonation("author_decision:storydesign-simulated")
        with self.assertRaises(ContractError):
            reject_simulation_impersonation("accepted_text:scene-TEST_ONLY")
        # ...and the two entry paths enforce it structurally:
        # shadow cannot claim author_decision:/accepted_text: at all...
        with self.assertRaises(ContractError):
            apply_settlement(
                state=make_state(), settlement=mechanical_settlement(),
                mode="shadow", shadow_authority="author_decision:storydesign-simulated",
            )
        with self.assertRaises(ContractError):
            apply_settlement(
                state=make_state(), settlement=mechanical_settlement(),
                mode="shadow", shadow_authority="accepted_text:scene2",
            )
        # ...and production scene refs carrying simulation markers are refused.
        with self.assertRaises(ContractError):
            apply_settlement(
                state=make_state(), settlement=mechanical_settlement(),
                mode="production", author_accepted=True,
                accepted_scene_ref="scene2-simulated-experiment",
            )
        # shadow also cannot claim acceptance
        with self.assertRaises(ContractError):
            apply_settlement(
                state=make_state(), settlement=mechanical_settlement(),
                mode="shadow", author_accepted=True,
                shadow_authority="manual_import:experiment_shadow_from_W2",
            )

    def test_rev_authority_and_existing_id_constraints_preserved(self):
        """6: existing contracts stay intact."""
        state = make_state()
        # append with an existing id -> refused
        with self.assertRaises(ContractError):
            apply_settlement(
                state=state, settlement=mechanical_settlement(entry_id="event.w1.negotiation"),
                mode="shadow", shadow_authority="manual_import:experiment_shadow_from_W2",
            )
        # replace_existing must target an existing id
        settlement = {
            "scene_ref": "scene2-W1-frozen",
            "candidates": [{
                "classification": "mechanical", "target_area": "open_threads",
                "entry": {"id": "thread.zheng.month-end", "thread": "郑国栋月底要答复，已提出价格疑问。"},
                "operation": "replace_existing", "reason": "同一线程的状态更新。",
            }],
        }
        report = apply_settlement(
            state=state, settlement=settlement, mode="shadow",
            shadow_authority="manual_import:experiment_shadow_from_W2",
        )
        threads = report["new_state"]["open_threads"]
        self.assertEqual(len(threads), 1)
        self.assertIn("价格疑问", threads[0]["thread"])
        # replace on missing id -> refused
        with self.assertRaises(ContractError):
            apply_settlement(
                state=state,
                settlement={"scene_ref": "s", "candidates": [{
                    "classification": "mechanical", "target_area": "open_threads",
                    "entry": {"id": "thread.missing", "thread": "x"},
                    "operation": "replace_existing", "reason": "r"}]},
                mode="shadow", shadow_authority="manual_import:experiment_shadow_from_W2",
            )
        # the model can never choose its own authority: an injected authority
        # is overwritten by the runtime-minted one.
        settlement = mechanical_settlement(entry_id="event.w2.zhou-decision")
        settlement["candidates"][0]["entry"]["authority"] = "ai_candidate:injected"
        report = apply_settlement(
            state=state, settlement=settlement, mode="shadow",
            shadow_authority="manual_import:experiment_shadow_from_W2",
        )
        written = [i for i in report["new_state"]["occurred_events"]
                   if i["id"] == "event.w2.zhou-decision"][0]
        self.assertEqual(written["authority"], "manual_import:experiment_shadow_from_W2")
        # illegal classification / area are contract errors, not silent skips
        bad = mechanical_settlement(entry_id="event.w2.x")
        bad["candidates"][0]["classification"] = "guess"
        with self.assertRaises(ContractError):
            apply_settlement(state=state, settlement=bad, mode="shadow",
                             shadow_authority="manual_import:x")
        bad = mechanical_settlement(entry_id="event.w2.x", area="style_notes")
        with self.assertRaises(ContractError):
            apply_settlement(state=state, settlement=bad, mode="shadow",
                             shadow_authority="manual_import:x")


class RecentProseWindowTests(unittest.TestCase):
    def test_window_is_non_authoritative_derived_input(self):
        """7: recent prose is a hint, not authority; tail window behavior."""
        long_text = "甲" * 1500 + "乙" * 1500  # 3000 chars
        window = prepare_recent_prose_window(prose_text=long_text, scene_ref="scene2-W1-frozen")
        self.assertFalse(window["is_authority"])
        self.assertTrue(window["must_not_write_state"])
        self.assertEqual(window["window_chars"], 2000)
        self.assertTrue(window["truncated_from_tail"])
        self.assertEqual(window["text"], "甲" * 500 + "乙" * 1500)  # tail kept
        self.assertIn("不得逐字复写", window["writing_hint"])
        self.assertEqual(window["writing_hint"], RECENT_PROSE_WRITING_HINT)
        # short prose stays whole, flagged below target
        short = prepare_recent_prose_window(prose_text="只有三百字的短场景。", scene_ref="s1")
        self.assertTrue(short["below_target"])
        self.assertFalse(short["truncated_from_tail"])
        # empty text / missing ref refused
        with self.assertRaises(ContractError):
            prepare_recent_prose_window(prose_text="   ", scene_ref="s1")
        with self.assertRaises(ContractError):
            prepare_recent_prose_window(prose_text="正文", scene_ref="")


class BriefAndContextPreparationTests(unittest.TestCase):
    def _brief(self, state=None):
        return prepare_creation_brief(
            project_id="thin-project",
            brief_id="thin-brief-003",
            author_input="写第三场：宋宁在三天内算完末梢账并答复。",
            intent=make_intent(),
            state=state or make_state(),
            semantic_interpretation={
                "scope": "scene_writing",
                "objective": "宋宁三天期限内给出末梢条件答复",
                "knowledge_needs": [],
            },
        )

    def test_brief_reuses_frozen_e1_contract(self):
        brief = self._brief()
        self.assertEqual(brief["artifact_type"], "creation_brief")
        self.assertEqual(brief["source_versions"], {"intent_rev": 2, "state_rev": 3})
        # stale brief cannot build a context on a moved state
        moved = make_state()
        moved["state_rev"] = 4
        with self.assertRaises(ContractError):
            prepare_context(
                context_id="thin-ctx-003", brief=brief, intent=make_intent(),
                state=moved, state_selections=[],
            )

    def test_context_selects_only_explicit_entries_no_fallback(self):
        """8: explicit selection only; empty selection stays empty."""
        state = make_state()
        brief = self._brief(state)
        # empty selection: legal, and never falls back to whole State
        empty = prepare_context(
            context_id="thin-ctx-003-empty", brief=brief, intent=make_intent(),
            state=state, state_selections=[],
        )
        self.assertEqual(empty["selected_story_state"], {})
        self.assertEqual(empty["size_summary"]["selected_state_items"], 0)
        self.assertEqual(empty["size_summary"]["total_state_items"], 7)
        # explicit selection copies only named entries
        ctx = prepare_context(
            context_id="thin-ctx-003", brief=brief, intent=make_intent(),
            state=state,
            state_selections=[
                {"area": "canon_facts", "id": "canon.seed.debt", "reason": "旧债后果在场"},
                {"area": "open_threads", "id": "thread.zheng.month-end", "reason": "月底期限"},
                {"area": "approved_plan", "id": "plan.design.direction.island", "reason": "方向义务"},
            ],
        )
        self.assertEqual(ctx["size_summary"]["selected_state_items"], 3)
        self.assertEqual(
            [i["id"] for i in ctx["selected_story_state"]["canon_facts"]],
            ["canon.seed.debt"],
        )
        self.assertEqual(ctx["retrieval"]["status"], "SKIPPED_NO_KNOWLEDGE_NEED")
        # unknown id / missing reason stay ContractErrors from the frozen compiler
        with self.assertRaises(ContractError):
            prepare_context(
                context_id="thin-ctx-bad", brief=brief, intent=make_intent(),
                state=state,
                state_selections=[{"area": "canon_facts", "id": "nope", "reason": "r"}],
            )
        with self.assertRaises(ContractError):
            prepare_context(
                context_id="thin-ctx-bad2", brief=brief, intent=make_intent(),
                state=state,
                state_selections=[{"area": "canon_facts", "id": "canon.seed.debt", "reason": "  "}],
            )
        # stale detection still works through the thin layer
        moved_intent = make_intent()
        moved_intent["intent_rev"] = 3
        self.assertTrue(context_package_is_stale(ctx, brief, moved_intent, state))


if __name__ == "__main__":
    unittest.main()
