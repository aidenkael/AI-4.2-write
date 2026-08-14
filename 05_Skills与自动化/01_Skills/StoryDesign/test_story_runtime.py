import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from story_design import run_story_design
from story_runtime import (
    ContractError,
    apply_diff,
    build_context,
    compile_creation_brief,
    context_is_stale,
    create_decision_record,
    create_design_candidate,
    make_planning_diff,
    trace_record,
    validate_story_state,
    write_json,
)


INTENT = {
    "project_id": "test-project", "intent_rev": 1,
    "work_direction": "人物驱动的悬疑长篇", "reader_promise": "秘密推动关系变化",
    "hard_constraints": ["不确认失踪者存活"], "open_space": ["秘密的来源"],
}
STATE = {
    "project_id": "test-project", "state_rev": 1,
    "canon_facts": [{"id": "canon.seed", "fact": "一封信已经寄到。", "authority": "manual_import:seed"}],
    "character_state": [], "relationship_state": [], "occurred_events": [], "open_threads": [], "approved_plan": [],
}


class Hit:
    def __init__(self, rank):
        self.rank = rank; self.book_id = "book-test"; self.book_title = "测试书"
        self.source_anchor = f"K{rank:03}"; self.source = "knowledge/cards.md"
        self.statement = "测试知识"; self.scope = "测试范围"; self.boundary = "测试边界"
        self.confidence = "中"; self.evidence = ["chapters/0001.md#L1"]
        self.relevance_reason = "test"


class Package:
    def __init__(self, status="OK", count=5):
        self.status = status; self.hits = [Hit(i) for i in range(1, count + 1)] if status == "OK" else []
        self.gaps = ["无有效命中"] if status != "OK" else []; self.candidate_count = count


def fake_retrieve_ok(query):
    return Package()


def fake_retrieve_gap(query):
    return Package("INSUFFICIENT_BKP", 0)


def fake_retrieve_must_not_be_called(query):
    raise AssertionError("无 knowledge need 时不得调用 KnowledgeRetrieve")


class StoryRuntimeTest(unittest.TestCase):
    def brief(self, interpretation=None):
        return compile_creation_brief(
            project_id="test-project", brief_id="brief-1",
            author_input="我想写一个收到亡友来信的故事。", intent=INTENT, state=STATE,
            semantic_interpretation=interpretation or {"knowledge_needs": ["信息层次"]},
        )

    def context(self, retrieval=fake_retrieve_ok):
        return build_context(
            context_id="context-1", brief=self.brief(), intent=INTENT, state=STATE, retrieval=retrieval,
            selected_knowledge_ids=["K001", "K002", "K003"],
        )

    def candidate(self):
        return create_design_candidate(candidate_id="candidate-1", brief=self.brief(), context=self.context(), model_output={"proposal": "候选"})

    def test_natural_language_input_compiles_brief(self):
        brief = self.brief()
        self.assertEqual(brief["objective"], "我想写一个收到亡友来信的故事。")
        self.assertEqual(brief["source_versions"], {"intent_rev": 1, "state_rev": 1})

    def test_ai_assumptions_are_explicit_not_author_facts(self):
        brief = self.brief({"assumptions": ["来信可能是伪造的"], "knowledge_needs": []})
        self.assertIn({"text": "来信可能是伪造的", "source": "ai_interpretation"}, brief["assumptions"])
        self.assertNotIn("来信可能是伪造的", str(STATE["canon_facts"]))

    def test_bkp_cannot_become_canon(self):
        polluted = dict(STATE, canon_facts=[{"id": "bad", "fact": "坏", "authority": "bkp:book/K001"}])
        with self.assertRaises(ContractError):
            validate_story_state(polluted)

    def test_candidate_is_noncanonical(self):
        self.assertEqual(self.candidate()["status"], "proposal_noncanonical")
        self.assertTrue(self.candidate()["must_not_write_canon"])

    def test_unconfirmed_design_cannot_become_approved_plan(self):
        with self.assertRaises(ContractError):
            create_decision_record(
                decision_id="d1", brief=self.brief(), context=self.context(), candidate=self.candidate(),
                author_action="choose", author_confirmation_ref=None,
            )

    def test_simulated_author_decision_can_write_plan_but_not_canon(self):
        # TEST_ONLY is in-memory verification, never a persisted author authority.
        decision = create_decision_record(
            decision_id="d1", brief=self.brief(), context=self.context(), candidate=self.candidate(),
            author_action="choose", author_confirmation_ref="author:TEST_ONLY/simulated-choice",
            final_decision={"selected": "candidate-1"}, simulation=True,
        )
        diff = make_planning_diff(diff_id="diff-1", state=STATE, decision=decision, plan={"id": "plan-1", "text": "探索候选方向"}, allow_simulation=True)
        updated = apply_diff(STATE, diff, decision, allow_simulation=True)
        self.assertEqual(updated["state_rev"], 2)
        self.assertEqual(updated["canon_facts"], STATE["canon_facts"])
        self.assertFalse(updated["approved_plan"][0]["occurred"])

    def test_approved_plan_is_not_occurred_canon(self):
        bad = dict(STATE, approved_plan=[{"id": "plan", "occurred": True}])
        with self.assertRaises(ContractError):
            validate_story_state(bad)

    def test_context_becomes_stale_after_revision_change(self):
        context = self.context()
        new_state = dict(STATE, state_rev=2)
        self.assertTrue(context_is_stale(context, INTENT, new_state))

    def test_old_diff_cannot_override_new_state(self):
        diff = {"base_state_rev": 1, "writeback_class": "ambiguous_inference"}
        with self.assertRaises(ContractError):
            apply_diff(dict(STATE, state_rev=2), diff)

    def test_creative_change_needs_author_decision(self):
        diff = {"base_state_rev": 1, "writeback_class": "creative_change", "source_ref": "author_decision:d", "changes": []}
        with self.assertRaises(ContractError):
            apply_diff(STATE, diff)

    def test_ambiguous_inference_never_auto_applies(self):
        diff = {"base_state_rev": 1, "writeback_class": "ambiguous_inference", "changes": []}
        with self.assertRaises(ContractError):
            apply_diff(STATE, diff)

    def test_insufficient_bkp_falls_back_without_failure(self):
        context = self.context(fake_retrieve_gap)
        self.assertEqual(context["status"], "CURRENT_WITH_BKP_GAP")
        self.assertEqual(context["selected_bkp_hits"], [])

    def test_zero_bkp_with_all_candidates_rejected_is_legal(self):
        # Frozen E1 policy: retrieval OK ≠ must use; 0 selected / NO_USEFUL_BKP is a normal result.
        context = build_context(
            context_id="context-zero", brief=self.brief(), intent=INTENT, state=STATE,
            retrieval=fake_retrieve_ok, selected_knowledge_ids=[],
        )
        self.assertEqual(context["status"], "CURRENT_WITH_BKP_GAP")
        self.assertEqual(context["selected_bkp_hits"], [])
        self.assertTrue(context["retrieval"]["gaps"])
        candidate = create_design_candidate(
            candidate_id="candidate-zero", brief=self.brief(), context=context, model_output={"proposal": "候选"},
        )
        self.assertEqual(candidate["status"], "proposal_noncanonical")

    def test_empty_knowledge_needs_is_legal(self):
        brief = self.brief({"knowledge_needs": [], "selected_bkp_ids": []})
        self.assertEqual(brief["knowledge_needs"], [])

    def test_no_knowledge_need_skips_retrieval_entirely(self):
        brief = self.brief({"knowledge_needs": []})
        context = build_context(
            context_id="context-skip", brief=brief, intent=INTENT, state=STATE,
            retrieval=fake_retrieve_must_not_be_called, selected_knowledge_ids=[],
        )
        self.assertEqual(context["status"], "CURRENT")
        self.assertEqual(context["retrieval"]["status"], "SKIPPED_NO_KNOWLEDGE_NEED")
        self.assertEqual(context["selected_bkp_hits"], [])
        candidate = create_design_candidate(
            candidate_id="candidate-skip", brief=brief, context=context, model_output={"proposal": "候选"},
        )
        self.assertEqual(candidate["status"], "proposal_noncanonical")

    def test_selected_ids_without_knowledge_needs_are_rejected(self):
        brief = self.brief({"knowledge_needs": []})
        with self.assertRaises(ContractError):
            build_context(
                context_id="context-bad", brief=brief, intent=INTENT, state=STATE,
                retrieval=fake_retrieve_must_not_be_called, selected_knowledge_ids=["K001"],
            )

    def test_reject_all_and_defer_cannot_write_plan_even_with_confirmation(self):
        for action in ("reject_all", "defer"):
            decision = create_decision_record(
                decision_id=f"decision-{action}", brief=self.brief(), context=self.context(), candidate=self.candidate(),
                author_action=action, author_confirmation_ref="author:real-confirmation-001",
            )
            self.assertIsNone(decision["authority"], action)
            self.assertNotIn(decision["status"], {"confirmed_for_plan_only", "simulated_confirmed_for_test"}, action)
            with self.assertRaises(ContractError, msg=action):
                make_planning_diff(
                    diff_id=f"diff-{action}", state=STATE, decision=decision,
                    plan={"id": f"plan-{action}", "text": "不应写入"}, allow_simulation=True,
                )

    def test_cross_project_artifacts_are_rejected(self):
        other_state = dict(STATE, project_id="other-project")
        with self.assertRaises(ContractError):
            compile_creation_brief(
                project_id="test-project", brief_id="brief-x", author_input="种子",
                intent=INTENT, state=other_state,
            )
        with self.assertRaises(ContractError):
            build_context(
                context_id="context-x", brief=self.brief(), intent=INTENT, state=other_state,
                retrieval=fake_retrieve_ok, selected_knowledge_ids=["K001"],
            )
        decision = create_decision_record(
            decision_id="decision-x", brief=self.brief(), context=self.context(), candidate=self.candidate(),
            author_action="choose", author_confirmation_ref="author:TEST_ONLY/simulated", simulation=True,
        )
        with self.assertRaises(ContractError):
            make_planning_diff(
                diff_id="diff-x", state=other_state, decision=decision,
                plan={"id": "plan-x", "text": "跨 project"}, allow_simulation=True,
            )

    def test_apply_diff_rejects_cross_project(self):
        decision = create_decision_record(
            decision_id="decision-ap", brief=self.brief(), context=self.context(), candidate=self.candidate(),
            author_action="choose", author_confirmation_ref="author:TEST_ONLY/simulated", simulation=True,
        )
        diff = make_planning_diff(
            diff_id="diff-ap", state=STATE, decision=decision,
            plan={"id": "plan-ap", "text": "探索候选方向"}, allow_simulation=True,
        )
        other_state = dict(STATE, project_id="other-project")
        with self.assertRaises(ContractError):
            apply_diff(other_state, diff, decision, allow_simulation=True)

    def test_decision_rejects_mismatched_refs(self):
        brief, context, candidate = self.brief(), self.context(), self.candidate()
        bad_candidate = dict(candidate, brief_ref="brief-other@9")
        with self.assertRaises(ContractError):
            create_decision_record(
                decision_id="decision-m1", brief=brief, context=context, candidate=bad_candidate,
                author_action="reject_all", author_confirmation_ref=None,
            )
        bad_context = dict(context, built_from=dict(context["built_from"], brief_rev=99))
        with self.assertRaises(ContractError):
            create_decision_record(
                decision_id="decision-m2", brief=brief, context=bad_context, candidate=candidate,
                author_action="reject_all", author_confirmation_ref=None,
            )

    def test_context_built_from_records_brief_rev(self):
        context = self.context()
        self.assertEqual(context["built_from"]["brief_id"], "brief-1")
        self.assertEqual(context["built_from"]["brief_rev"], 1)

    def test_demo_cli_refuses_existing_nonempty_dir(self):
        import run as story_run
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "demo"
            result = story_run.create_demo(target)
            self.assertEqual(result["context"]["retrieval"]["status"], "SKIPPED_NO_KNOWLEDGE_NEED")
            with self.assertRaises(ContractError):
                story_run.create_demo(target)

    def test_proposal_cannot_pollute_canon(self):
        polluted = dict(STATE, canon_facts=[{"id": "bad", "fact": "坏", "authority": "proposal:design-001"}])
        with self.assertRaises(ContractError):
            validate_story_state(polluted)

    def test_retrieval_rank_is_not_a_semantic_selection(self):
        context = build_context(context_id="context-rank-only", brief=self.brief(), intent=INTENT, state=STATE, retrieval=fake_retrieve_ok)
        self.assertEqual(context["selected_bkp_hits"], [])
        self.assertIn("未选择", context["retrieval"]["gaps"][0])

    def test_context_limits_bkp_and_preserves_provenance(self):
        context = self.context()
        self.assertEqual(len(context["selected_bkp_hits"]), 3)
        self.assertEqual(context["selected_bkp_hits"][0]["knowledge_id"], "K001")
        self.assertIn("evidence", context["selected_bkp_hits"][0]["provenance"])

    def test_trace_is_provenance_linked(self):
        brief, context, candidate = self.brief(), self.context(), self.candidate()
        trace = trace_record(trace_id="t1", brief=brief, context=context, candidate=candidate)
        self.assertEqual(trace["candidate_ref"], "candidate-1")
        self.assertEqual(len(trace["bkp_provenance"]), 3)

    def test_provider_agnostic_run_writes_inspectable_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); write_json(root / "author_intent.json", INTENT); write_json(root / "story_state.json", STATE)
            result = run_story_design(
                project_dir=root, author_input="我现在只有一个设想：亡友来信。", brief_id="b", context_id="c", candidate_id="d",
                semantic_interpretation={"knowledge_needs": ["信息层次"], "selected_bkp_ids": []}, model_output={"proposal": "候选"}, retrieval=fake_retrieve_gap,
            )
            self.assertTrue((root / "briefs" / "b.json").exists())
            self.assertEqual(result["candidate"]["status"], "proposal_noncanonical")


if __name__ == "__main__":
    unittest.main()
