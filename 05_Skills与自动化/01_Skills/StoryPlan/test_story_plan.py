import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from story_plan import (
    ContractError,
    apply_diff,
    build_plan_context,
    compile_plan_brief,
    context_is_stale,
    create_decision_record,
    create_plan_candidate,
    make_plan_diff,
    mark_stale_if_needed,
    normalize_planning_item,
    run_story_plan,
    validate_story_state,
)


INTENT = {
    "project_id": "plan-project", "intent_rev": 1,
    "work_direction": "都市悬疑长篇", "reader_promise": "读者先相信同盟，后发现目标互斥",
    "hard_constraints": ["不提前确认最终反派"], "open_space": ["关系归宿"],
}
STATE = {
    "project_id": "plan-project", "state_rev": 1,
    "canon_facts": [{"id": "canon.seed", "fact": "两人因旧案结识。", "authority": "manual_import:seed"}],
    "character_state": [], "relationship_state": [], "occurred_events": [], "open_threads": [],
    "approved_plan": [
        {"id": "plan.design.engine", "description": "已确认故事发动机。", "target_ref": "design.engine",
         "authority": "author_decision:sim-design-001", "occurred": False},
    ],
}
CONFIRMED_SOURCES = [{"kind": "approved_plan", "ref": "plan.design.engine"}]
TARGET = {"target_id": "target.front-half", "description": "故事前半程推进", "scope_kind": "free", "scope": "约全书前半程"}


def fake_retrieve_must_not_be_called(query):
    raise AssertionError("无 knowledge need 时不得调用 KnowledgeRetrieve")


class StoryPlanContractTest(unittest.TestCase):
    def brief(self, interpretation=None, sources=None, target=None):
        return compile_plan_brief(
            project_id="plan-project", brief_id="plan-brief-1",
            author_planning_question="先规划前半程，我主要担心男女主太晚才真正站到对立面。",
            planning_target=target or TARGET, planning_sources=sources if sources is not None else CONFIRMED_SOURCES,
            intent=INTENT, state=STATE, semantic_interpretation=interpretation or {},
        )

    def context(self):
        return build_plan_context(
            context_id="plan-context-1", brief=self.brief(), intent=INTENT, state=STATE,
            retrieval=fake_retrieve_must_not_be_called,
        )

    def candidate(self):
        return create_plan_candidate(
            candidate_id="plan-001", brief=self.brief(), context=self.context(),
            model_output={"proposal": "候选规划"},
        )

    def confirmed_decision(self, action="choose"):
        return create_decision_record(
            decision_id="plan-decision-1", brief=self.brief(), context=self.context(), candidate=self.candidate(),
            author_action=action, author_confirmation_ref="author:TEST_ONLY/simulated-plan",
            final_decision={"selected": "plan-001"}, simulation=True,
        )

    # 1. 无已确认规划来源时不假装已有作者方向
    def test_no_confirmed_source_is_rejected(self):
        with self.assertRaises(ContractError):
            self.brief(sources=[])
        with self.assertRaises(ContractError):
            self.brief(sources=[{"kind": "proposal", "ref": "candidate-x"}])
        with self.assertRaises(ContractError):
            self.brief(sources=[{"kind": "model_idea", "ref": "guess-1"}])

    # 2. Plan Candidate 是 noncanonical
    def test_plan_candidate_is_noncanonical(self):
        candidate = self.candidate()
        self.assertEqual(candidate["status"], "proposal_noncanonical")
        self.assertEqual(candidate["authority"], "ai_candidate:noncanonical")
        self.assertTrue(candidate["must_not_write_canon"])
        self.assertEqual(candidate["planning_target"]["target_id"], "target.front-half")

    # 3. Plan Candidate 不能直接修改 Canon
    def test_plan_candidate_cannot_become_canon(self):
        polluted = dict(STATE, canon_facts=STATE["canon_facts"] + [
            {"id": "bad", "fact": "偷渡未来事实", "authority": "proposal:plan-001"},
        ])
        with self.assertRaises(ContractError):
            validate_story_state(polluted)

    # 4. 未确认 Candidate 不能进入 approved_plan
    def test_unconfirmed_candidate_cannot_enter_approved_plan(self):
        with self.assertRaises(ContractError):
            create_decision_record(
                decision_id="plan-decision-2", brief=self.brief(), context=self.context(), candidate=self.candidate(),
                author_action="choose", author_confirmation_ref=None,
            )

    # 5. reject_all / defer 不能产生 planning writeback
    def test_reject_all_and_defer_cannot_write_plan(self):
        for action in ("reject_all", "defer"):
            decision = create_decision_record(
                decision_id=f"plan-decision-{action}", brief=self.brief(), context=self.context(), candidate=self.candidate(),
                author_action=action, author_confirmation_ref="author:real-confirmation",
            )
            with self.assertRaises(ContractError, msg=action):
                make_plan_diff(
                    diff_id=f"plan-diff-{action}", state=STATE, decision=decision, brief=self.brief(),
                    plans=[{"id": "plan.p1", "description": "不应写入"}], allow_simulation=True,
                )

    # 6. accepted planning 强制 occurred = false，且只进 approved_plan
    def test_accepted_planning_forces_occurred_false(self):
        decision = self.confirmed_decision()
        diff = make_plan_diff(
            diff_id="plan-diff-1", state=STATE, decision=decision, brief=self.brief(),
            plans=[
                {"id": "plan.p1", "description": "前半程三次共同行动", "occurred": True},
                {"id": "plan.p2", "description": "第三次行动后信息互相咬合", "supersedes": [], "built_from": ["plan.design.engine"]},
            ],
            allow_simulation=True,
        )
        updated = apply_diff(STATE, diff, decision, allow_simulation=True)
        self.assertEqual(updated["state_rev"], 2)
        self.assertEqual(updated["canon_facts"], STATE["canon_facts"])
        appended = updated["approved_plan"][len(STATE["approved_plan"]):]
        self.assertEqual([plan["id"] for plan in appended], ["plan.p1", "plan.p2"])
        self.assertTrue(all(plan["occurred"] is False for plan in appended))
        self.assertTrue(all(plan["target_ref"] == "target.front-half" for plan in appended))

    # 7. stale Context 被拒绝
    def test_stale_context_rejected(self):
        context = self.context()
        new_state = dict(STATE, state_rev=2)
        self.assertTrue(context_is_stale(context, INTENT, new_state))
        stale = mark_stale_if_needed(context, INTENT, new_state)
        with self.assertRaises(ContractError):
            create_plan_candidate(candidate_id="plan-stale", brief=self.brief(), context=stale, model_output={"proposal": "候选"})

    # 8. cross-project 被拒绝
    def test_cross_project_is_rejected(self):
        other_state = dict(STATE, project_id="other-project")
        with self.assertRaises(ContractError):
            compile_plan_brief(
                project_id="plan-project", brief_id="plan-brief-x", author_planning_question="规划",
                planning_target=TARGET, planning_sources=CONFIRMED_SOURCES, intent=INTENT, state=other_state,
            )
        decision = self.confirmed_decision()
        with self.assertRaises(ContractError):
            make_plan_diff(
                diff_id="plan-diff-x", state=other_state, decision=decision, brief=self.brief(),
                plans=[{"id": "plan.px", "description": "跨 project"}], allow_simulation=True,
            )

    # 8b. planning 条目 target_ref 与 brief planning_target 不一致被拒绝
    def test_mismatched_target_ref_is_rejected(self):
        decision = self.confirmed_decision()
        with self.assertRaises(ContractError):
            make_plan_diff(
                diff_id="plan-diff-m", state=STATE, decision=decision, brief=self.brief(),
                plans=[{"id": "plan.pm", "description": "错位", "target_ref": "target.other"}], allow_simulation=True,
            )

    # 9 + 10. knowledge_needs 空时 Retrieval 0 调用；0 BKP 正常
    def test_no_knowledge_need_skips_retrieval_and_zero_bkp_is_legal(self):
        context = self.context()  # retrieval raises if called
        self.assertEqual(context["status"], "CURRENT")
        self.assertEqual(context["retrieval"]["status"], "SKIPPED_NO_KNOWLEDGE_NEED")
        self.assertEqual(context["selected_bkp_hits"], [])
        self.assertEqual(context["planning_target"]["target_id"], "target.front-half")

    # 11 + 12. 非固定层级 scope 合法；runtime 不要求五层树
    def test_free_scope_is_legal_without_fixed_hierarchy(self):
        brief = self.brief(target={
            "target_id": "target.mother-daughter-mid",
            "description": "女主与母亲关系的中期推进",
            "scope_kind": "relationship",
            "scope": "中段关系变化，不涉及卷/章结构",
        })
        self.assertEqual(brief["planning_target"]["scope_kind"], "relationship")
        item = normalize_planning_item(
            {"id": "plan.rel1", "description": "母亲知情权与女主隐瞒的第一次正面碰撞"},
            target_ref="target.mother-daughter-mid",
        )
        self.assertFalse(item["occurred"])
        self.assertNotIn("volume", item)
        self.assertNotIn("chapter", item)

    # 13. 模型规划内容不被 runtime 解析成 Canon facts
    def test_model_content_stays_opaque_and_canon_unchanged(self):
        model_output = {
            "proposal": "第三阶段让男主发现女主的真实目的（这不是事实，只是规划候选）。",
            "events_that_look_like_facts": ["男主在仓库摊牌", "女主离开城市"],
        }
        candidate = create_plan_candidate(
            candidate_id="plan-opaque", brief=self.brief(), context=self.context(), model_output=model_output,
        )
        self.assertEqual(candidate["content"], model_output)
        self.assertEqual(STATE["canon_facts"], [{"id": "canon.seed", "fact": "两人因旧案结识。", "authority": "manual_import:seed"}])
        self.assertEqual(STATE["occurred_events"], [])

    # 端到端 disposable 链：0 BKP、noncanonical、无确认
    def test_run_story_plan_end_to_end_zero_bkp(self):
        import tempfile
        from story_plan import write_json
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "author_intent.json", INTENT)
            write_json(root / "story_state.json", STATE)
            result = run_story_plan(
                project_dir=root,
                author_planning_question="先规划前半程。",
                planning_target=TARGET, planning_sources=CONFIRMED_SOURCES,
                brief_id="pb", context_id="pc", candidate_id="pp",
                semantic_interpretation={"knowledge_needs": [], "selected_bkp_ids": []},
                model_output={"proposal": "候选"},
                retrieval=fake_retrieve_must_not_be_called,
            )
            self.assertEqual(result["context"]["retrieval"]["status"], "SKIPPED_NO_KNOWLEDGE_NEED")
            self.assertEqual(result["candidate"]["status"], "proposal_noncanonical")
            self.assertTrue((root / "plans" / "pp.json").exists())
            self.assertTrue((root / "traces" / "trace-pp.json").exists())


if __name__ == "__main__":
    unittest.main()
