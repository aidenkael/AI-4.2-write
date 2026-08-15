import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from story_plan import (
    CANON_AREAS,
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
    resolve_plan_activity,
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

    # 1b. planning source 必须在当前 Story State approved_plan 中真实存在
    def test_nonexistent_approved_plan_ref_is_rejected(self):
        with self.assertRaises(ContractError):
            self.brief(sources=[{"kind": "approved_plan", "ref": "fake-plan-id"}])

    def test_real_approved_plan_ref_is_verified(self):
        brief = self.brief()
        self.assertEqual(
            brief["planning_sources"],
            [{"kind": "approved_plan", "ref": "plan.design.engine",
              "verified_authority": "author_decision:sim-design-001"}],
        )

    def test_valid_source_mixed_with_unknown_kind_is_rejected(self):
        with self.assertRaises(ContractError):
            self.brief(sources=CONFIRMED_SOURCES + [{"kind": "random_source", "ref": "r1"}])

    def test_forbidden_source_kinds_stay_rejected(self):
        for kind in ("proposal", "context", "bkp", "ai_candidate"):
            with self.assertRaises(ContractError, msg=kind):
                self.brief(sources=[{"kind": kind, "ref": "plan.design.engine"}])

    def test_direct_decision_ref_kinds_are_deferred_in_v0(self):
        # 锁定 E2-A v0 行为：无 Decision resolver/store 前不直接接受 Decision ref。
        for kind in ("design_decision", "author_decision"):
            with self.assertRaises(ContractError, msg=kind):
                self.brief(sources=[{"kind": kind, "ref": "decision-001"}])

    def test_untrusted_authority_approved_plan_is_rejected(self):
        polluted = dict(STATE, approved_plan=STATE["approved_plan"] + [
            {"id": "plan.bad", "description": "不可信来源", "target_ref": "x",
             "authority": "manual_import:ok", "occurred": False},
        ])
        # manual_import 是可信的；换成一个非可信但能通过 state 校验的前缀验证拒绝路径。
        polluted["approved_plan"][-1]["authority"] = "accepted_text:ch1"
        compile_kwargs = dict(
            project_id="plan-project", brief_id="plan-brief-auth", author_planning_question="规划",
            planning_target=TARGET, planning_sources=[{"kind": "approved_plan", "ref": "plan.bad"}],
            intent=INTENT, state=polluted,
        )
        with self.assertRaises(ContractError):
            compile_plan_brief(**compile_kwargs)

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
                    diff_id=f"plan-diff-{action}", state=STATE, decision=decision, brief=self.brief(), intent=INTENT,
                    plans=[{"id": "plan.p1", "description": "不应写入"}], allow_simulation=True,
                )

    # 6. accepted planning 强制 occurred = false，且只进 approved_plan
    def test_accepted_planning_forces_occurred_false(self):
        decision = self.confirmed_decision()
        diff = make_plan_diff(
            diff_id="plan-diff-1", state=STATE, intent=INTENT, decision=decision, brief=self.brief(),
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
                diff_id="plan-diff-x", state=other_state, intent=INTENT, decision=decision, brief=self.brief(),
                plans=[{"id": "plan.px", "description": "跨 project"}], allow_simulation=True,
            )

    # 8b. planning 条目 target_ref 与 brief planning_target 不一致被拒绝
    def test_mismatched_target_ref_is_rejected(self):
        decision = self.confirmed_decision()
        with self.assertRaises(ContractError):
            make_plan_diff(
                diff_id="plan-diff-m", state=STATE, intent=INTENT, decision=decision, brief=self.brief(),
                plans=[{"id": "plan.pm", "description": "错位", "target_ref": "target.other"}], allow_simulation=True,
            )

    # 8c. Decision 必须绑定当前 Plan Brief：Brief A 的 Decision 不得写 Brief B
    def test_decision_from_other_brief_is_rejected(self):
        other_brief = compile_plan_brief(
            project_id="plan-project", brief_id="plan-brief-2",
            author_planning_question="另一个规划问题。",
            planning_target=TARGET, planning_sources=CONFIRMED_SOURCES,
            intent=INTENT, state=STATE,
        )
        decision = self.confirmed_decision()  # bound to plan-brief-1
        with self.assertRaises(ContractError):
            make_plan_diff(
                diff_id="plan-diff-b", state=STATE, intent=INTENT, decision=decision, brief=other_brief,
                plans=[{"id": "plan.pb", "description": "错位 Brief"}], allow_simulation=True,
            )

    def test_tampered_brief_project_id_is_rejected(self):
        decision = self.confirmed_decision()
        tampered = dict(self.brief(), project_id="other-project")
        with self.assertRaises(ContractError):
            make_plan_diff(
                diff_id="plan-diff-t", state=STATE, intent=INTENT, decision=decision, brief=tampered,
                plans=[{"id": "plan.pt", "description": "篡改 project"}], allow_simulation=True,
            )

    def test_stale_brief_cannot_write_back_on_new_state(self):
        decision = self.confirmed_decision()
        new_state = dict(STATE, state_rev=2)
        with self.assertRaises(ContractError):
            make_plan_diff(
                diff_id="plan-diff-s", state=new_state, intent=INTENT, decision=decision, brief=self.brief(),
                plans=[{"id": "plan.ps", "description": "旧 Brief"}], allow_simulation=True,
            )

    # 8d. intent_rev stale：方向权威变化后旧 Brief 不得写回（即使 state_rev 未变）
    def test_stale_intent_brief_cannot_write_back(self):
        decision = self.confirmed_decision()
        new_intent = dict(INTENT, intent_rev=2)  # state 仍是 rev=1，必须单独拒绝
        with self.assertRaises(ContractError):
            make_plan_diff(
                diff_id="plan-diff-i", state=STATE, intent=new_intent, decision=decision, brief=self.brief(),
                plans=[{"id": "plan.pi", "description": "旧 Intent Brief"}], allow_simulation=True,
            )

    # 8e. cross-project Intent 被拒绝
    def test_cross_project_intent_is_rejected(self):
        decision = self.confirmed_decision()
        other_intent = dict(INTENT, project_id="other-project")
        with self.assertRaises(ContractError):
            make_plan_diff(
                diff_id="plan-diff-ci", state=STATE, intent=other_intent, decision=decision, brief=self.brief(),
                plans=[{"id": "plan.pci", "description": "跨 project intent"}], allow_simulation=True,
            )

    # 8f. planning id 稳定性：批次内唯一、不与现有 approved_plan id 重名
    def test_duplicate_plan_ids_in_batch_rejected(self):
        decision = self.confirmed_decision()
        with self.assertRaises(ContractError):
            make_plan_diff(
                diff_id="plan-diff-d", state=STATE, intent=INTENT, decision=decision, brief=self.brief(),
                plans=[
                    {"id": "plan.dup", "description": "第一条"},
                    {"id": "plan.dup", "description": "第二条"},
                ],
                allow_simulation=True,
            )

    def test_plan_id_colliding_with_existing_approved_plan_rejected(self):
        decision = self.confirmed_decision()
        with self.assertRaises(ContractError):
            make_plan_diff(
                diff_id="plan-diff-c", state=STATE, intent=INTENT, decision=decision, brief=self.brief(),
                plans=[{"id": "plan.design.engine", "description": "重名覆盖"}], allow_simulation=True,
            )

    def test_supersede_requires_new_id_and_keeps_old_entry(self):
        # E2-C-A：supersedes 必须用新 id 且同 target；旧条目原样保留，仅通过 activity 投影标记失效。
        local_state = dict(STATE, approved_plan=STATE["approved_plan"] + [
            {"id": "plan.rel.v1", "description": "关系中段 v1", "target_ref": "target.front-half",
             "authority": "author_decision:sim-rel", "occurred": False},
        ])
        brief = compile_plan_brief(
            project_id="plan-project", brief_id="plan-brief-su",
            author_planning_question="规划前半程。",
            planning_target=TARGET,
            planning_sources=[{"kind": "approved_plan", "ref": "plan.rel.v1"}],
            intent=INTENT, state=local_state,
        )
        context = build_plan_context(
            context_id="plan-context-su", brief=brief, intent=INTENT, state=local_state,
            retrieval=fake_retrieve_must_not_be_called,
        )
        candidate = create_plan_candidate(
            candidate_id="plan-su-001", brief=brief, context=context,
            model_output={"proposal": "候选"},
        )
        decision = create_decision_record(
            decision_id="plan-decision-su", brief=brief, context=context, candidate=candidate,
            author_action="choose", author_confirmation_ref="author:TEST_ONLY/simulated-su",
            final_decision={"selected": "plan-su-001"}, simulation=True,
        )
        diff = make_plan_diff(
            diff_id="plan-diff-su", state=local_state, intent=INTENT, decision=decision, brief=brief,
            plans=[{"id": "plan.p3", "description": "重做前半程", "supersedes": ["plan.rel.v1"]}],
            allow_simulation=True,
        )
        updated = apply_diff(local_state, diff, decision, allow_simulation=True)
        appended = updated["approved_plan"][len(local_state["approved_plan"]):]
        self.assertEqual([plan["id"] for plan in appended], ["plan.p3"])
        self.assertEqual(appended[0]["supersedes"], ["plan.rel.v1"])
        self.assertTrue(any(p["id"] == "plan.rel.v1" for p in updated["approved_plan"]))

    def test_duplicate_approved_plan_ids_in_state_rejected(self):
        polluted = dict(STATE, approved_plan=STATE["approved_plan"] + [
            {"id": "plan.design.engine", "description": "重复条目", "target_ref": "x",
             "authority": "author_decision:sim-design-002", "occurred": False},
        ])
        with self.assertRaises(ContractError):
            compile_plan_brief(
                project_id="plan-project", brief_id="plan-brief-dup", author_planning_question="规划",
                planning_target=TARGET, planning_sources=CONFIRMED_SOURCES, intent=INTENT, state=polluted,
            )

    def test_multiple_distinct_plan_ids_still_pass(self):
        # 正常多条不同 id 路径继续通过（批次唯一 + 不与 state 重名）。
        decision = self.confirmed_decision()
        diff = make_plan_diff(
            diff_id="plan-diff-ok", state=STATE, intent=INTENT, decision=decision, brief=self.brief(),
            plans=[
                {"id": "plan.q1", "description": "第一条"},
                {"id": "plan.q2", "description": "第二条"},
            ],
            allow_simulation=True,
        )
        self.assertEqual([c["value"]["id"] for c in diff["changes"]], ["plan.q1", "plan.q2"])

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


# ---------------------------------------------------------------------------
# E2-C-A：最小局部重规划语义（append-only history + derived activity projection）
# ---------------------------------------------------------------------------

SANDBOX_STATE = {
    "project_id": "plan-project", "state_rev": 1,
    "canon_facts": [{"id": "canon.seed", "fact": "两人因旧案结识。", "authority": "manual_import:seed"}],
    "character_state": [{"id": "char.lead", "name": "女主", "authority": "manual_import:seed"}],
    "relationship_state": [{"id": "rel.seed", "description": "同盟假象", "authority": "manual_import:seed"}],
    "occurred_events": [], "open_threads": [],
    "approved_plan": [
        {"id": "plan.book.direction", "description": "全书方向：先相信同盟，后发现目标互斥。",
         "target_ref": "target.book.direction", "authority": "author_decision:sim-book", "occurred": False},
        {"id": "plan.rel.mid.v1", "description": "关系中段 v1：隐瞒与试探。",
         "target_ref": "target.rel.mid", "authority": "author_decision:sim-rel-1", "occurred": False},
        {"id": "plan.suspense.mid", "description": "悬念链：旧案卷宗的去向。",
         "target_ref": "target.suspense.mid", "authority": "author_decision:sim-suspense", "occurred": False},
    ],
}
REL_TARGET = {"target_id": "target.rel.mid", "description": "关系中段局部重规划",
              "scope_kind": "relationship", "scope": "只动关系中段，不重算全书"}


class StoryPlanLocalReplanTest(unittest.TestCase):
    def brief(self, state, *, brief_id="plan-brief-rel", target=None, sources=None,
              allow_simulation_sources=False):
        return compile_plan_brief(
            project_id="plan-project", brief_id=brief_id,
            author_planning_question="把关系中段改成责任分配持续变化的推进。",
            planning_target=target or REL_TARGET,
            planning_sources=sources if sources is not None else [{"kind": "approved_plan", "ref": "plan.rel.mid.v1"}],
            intent=INTENT, state=state, semantic_interpretation={},
            allow_simulation_sources=allow_simulation_sources,
        )

    def context(self, state, brief, *, context_id="plan-context-rel"):
        return build_plan_context(
            context_id=context_id, brief=brief, intent=INTENT, state=state,
            retrieval=fake_retrieve_must_not_be_called,
        )

    def modify_decision(self, *, state, brief, context, decision_id="plan-decision-modify", action="modify"):
        candidate = create_plan_candidate(
            candidate_id="plan-cand-rel-v2", brief=brief, context=context,
            model_output={"proposal": "关系中段 v2：把未解决旧债改造成当前选择成本与关系判断。"},
        )
        return create_decision_record(
            decision_id=decision_id, brief=brief, context=context, candidate=candidate,
            author_action=action, author_confirmation_ref="author:TEST_ONLY/e2c-simulated-modify",
            final_decision={"action": action, "note": "SIMULATED_DECISION_ONLY"}, simulation=True,
        )

    def chain(self, state, *, new_id, old_id, diff_id="plan-diff-rel", brief_id="plan-brief-rel",
              allow_simulation_sources=False):
        """一次同 target 局部替换：brief -> 0-BKP context -> modify Decision -> diff -> apply。

        Brief 明确引用 old_id 作为当前 active planning source，确保
        supersede binding 与 Brief declared sources 一致。
        """
        brief = self.brief(state, brief_id=brief_id,
                           sources=[{"kind": "approved_plan", "ref": old_id}],
                           allow_simulation_sources=allow_simulation_sources)
        context = self.context(state, brief, context_id=f"ctx-{brief_id}")
        decision = self.modify_decision(state=state, brief=brief, context=context, decision_id=f"decision-{brief_id}")
        diff = make_plan_diff(
            diff_id=diff_id, state=state, intent=INTENT, decision=decision, brief=brief,
            plans=[{"id": new_id, "description": f"关系中段新版本 {new_id}", "supersedes": [old_id]}],
            allow_simulation=True,
        )
        return apply_diff(state, diff, decision, allow_simulation=True)

    def unrelated_append(self, state, *, plan_id="plan.suspense.mid.extra", brief_id="plan-brief-suspense"):
        """一条合法但完全无关的 sibling append，用于推进 state_rev。"""
        suspense_target = {"target_id": "target.suspense.mid", "description": "悬念链补充",
                           "scope_kind": "suspense", "scope": "只动悬念链"}
        brief = compile_plan_brief(
            project_id="plan-project", brief_id=brief_id,
            author_planning_question="给悬念链补一条推进。",
            planning_target=suspense_target,
            planning_sources=[{"kind": "approved_plan", "ref": "plan.suspense.mid"}],
            intent=INTENT, state=state,
        )
        context = build_plan_context(
            context_id=f"ctx-{brief_id}", brief=brief, intent=INTENT, state=state,
            retrieval=fake_retrieve_must_not_be_called,
        )
        decision = self.modify_decision(state=state, brief=brief, context=context, decision_id=f"decision-{brief_id}", action="choose")
        diff = make_plan_diff(
            diff_id=f"diff-{brief_id}", state=state, intent=INTENT, decision=decision, brief=brief,
            plans=[{"id": plan_id, "description": "悬念链的无关补充条目。"}],
            allow_simulation=True,
        )
        return apply_diff(state, diff, decision, allow_simulation=True)

    # 1. 基本 activity projection
    def test_basic_activity_projection(self):
        state = dict(SANDBOX_STATE, approved_plan=SANDBOX_STATE["approved_plan"] + [
            {"id": "plan.rel.mid.v2", "description": "v2", "target_ref": "target.rel.mid",
             "authority": "author_decision:sim-rel-2", "occurred": False, "supersedes": ["plan.rel.mid.v1"]},
        ])
        activity = resolve_plan_activity(state)
        self.assertNotIn("plan.rel.mid.v1", activity["active"])
        self.assertIn("plan.rel.mid.v2", activity["active"])
        self.assertEqual(activity["superseded"], ["plan.rel.mid.v1"])
        self.assertEqual(activity["superseded_by"], {"plan.rel.mid.v1": ["plan.rel.mid.v2"]})

    # 2 + 3 + 15. 真实 local replan 链：旧条目保留、superseded_by 正确、Canon ZERO pollution
    def test_local_replan_chain_keeps_history_and_canon_clean(self):
        before = {area: SANDBOX_STATE[area] for area in CANON_AREAS}
        updated = self.chain(SANDBOX_STATE, new_id="plan.rel.mid.v2", old_id="plan.rel.mid.v1")
        self.assertEqual(updated["state_rev"], 2)
        ids = [plan["id"] for plan in updated["approved_plan"]]
        self.assertIn("plan.rel.mid.v1", ids)  # 旧条目不删除、不改写
        self.assertIn("plan.rel.mid.v2", ids)
        self.assertEqual(
            [plan for plan in updated["approved_plan"] if plan["id"] == "plan.rel.mid.v1"],
            [plan for plan in SANDBOX_STATE["approved_plan"] if plan["id"] == "plan.rel.mid.v1"],
        )
        activity = resolve_plan_activity(updated)
        self.assertEqual(activity["superseded_by"]["plan.rel.mid.v1"], ["plan.rel.mid.v2"])
        self.assertIn("plan.rel.mid.v2", activity["active"])
        self.assertTrue(all("status" not in plan and "active" not in plan for plan in updated["approved_plan"]))
        for area in CANON_AREAS:  # CANON_POLLUTION = ZERO
            self.assertEqual(updated[area], before[area], area)

    # 4 + 5. sibling / ancestor 保持 active，不重算全书
    def test_sibling_and_ancestor_stay_active(self):
        updated = self.chain(SANDBOX_STATE, new_id="plan.rel.mid.v2", old_id="plan.rel.mid.v1")
        activity = resolve_plan_activity(updated)
        self.assertIn("plan.suspense.mid", activity["active"])
        self.assertIn("plan.book.direction", activity["active"])
        self.assertEqual(activity["superseded"], ["plan.rel.mid.v1"])

    # 6. missing supersede ref 拒绝
    def test_missing_supersede_ref_rejected(self):
        brief = self.brief(SANDBOX_STATE)
        context = self.context(SANDBOX_STATE, brief)
        decision = self.modify_decision(state=SANDBOX_STATE, brief=brief, context=context)
        with self.assertRaises(ContractError):
            make_plan_diff(
                diff_id="plan-diff-missing", state=SANDBOX_STATE, intent=INTENT, decision=decision, brief=brief,
                plans=[{"id": "plan.rel.mid.v2", "description": "x", "supersedes": ["plan.not.exists"]}],
                allow_simulation=True,
            )

    # 6b. self-supersede 与列表内重复也拒绝
    def test_self_and_duplicate_supersede_refs_rejected(self):
        brief = self.brief(SANDBOX_STATE)
        context = self.context(SANDBOX_STATE, brief)
        decision = self.modify_decision(state=SANDBOX_STATE, brief=brief, context=context)
        for supersedes in (["plan.rel.mid.v2"], ["plan.rel.mid.v1", "plan.rel.mid.v1"]):
            with self.assertRaises(ContractError):
                make_plan_diff(
                    diff_id="plan-diff-badref", state=SANDBOX_STATE, intent=INTENT, decision=decision, brief=brief,
                    plans=[{"id": "plan.rel.mid.v2", "description": "x", "supersedes": supersedes}],
                    allow_simulation=True,
                )

    # 7. cross-target supersede 拒绝（局部重规划不得影响无关区域）
    def test_cross_target_supersede_rejected(self):
        brief = self.brief(SANDBOX_STATE)
        context = self.context(SANDBOX_STATE, brief)
        decision = self.modify_decision(state=SANDBOX_STATE, brief=brief, context=context)
        with self.assertRaises(ContractError):
            make_plan_diff(
                diff_id="plan-diff-cross", state=SANDBOX_STATE, intent=INTENT, decision=decision, brief=brief,
                plans=[{"id": "plan.rel.mid.v2", "description": "x", "supersedes": ["plan.suspense.mid"]}],
                allow_simulation=True,
            )

    # 8. 已 inactive 的旧 base 不得再作为 replacement base（v1→v2 后 v3 不得 supersede v1）
    def test_inactive_base_rejected_and_chain_tip_accepted(self):
        s2 = self.chain(SANDBOX_STATE, new_id="plan.rel.mid.v2", old_id="plan.rel.mid.v1")
        # Brief 明确引用当前 active source v2（simulation authority，需显式 gate）
        brief = self.brief(s2, brief_id="plan-brief-rel-v3",
                           sources=[{"kind": "approved_plan", "ref": "plan.rel.mid.v2"}],
                           allow_simulation_sources=True)
        context = self.context(s2, brief, context_id="ctx-rel-v3")
        decision = self.modify_decision(state=s2, brief=brief, context=context, decision_id="plan-decision-v3")
        with self.assertRaises(ContractError):
            make_plan_diff(
                diff_id="plan-diff-v3-dead", state=s2, intent=INTENT, decision=decision, brief=brief,
                plans=[{"id": "plan.rel.mid.v3", "description": "分叉旧版", "supersedes": ["plan.rel.mid.v1"]}],
                allow_simulation=True,
            )
        # 9. 合法下一版：v3 supersedes v2 → v1→v2→v3 链成立
        diff = make_plan_diff(
            diff_id="plan-diff-v3", state=s2, intent=INTENT, decision=decision, brief=brief,
            plans=[{"id": "plan.rel.mid.v3", "description": "链式新版", "supersedes": ["plan.rel.mid.v2"]}],
            allow_simulation=True,
        )
        s3 = apply_diff(s2, diff, decision, allow_simulation=True)
        activity = resolve_plan_activity(s3)
        self.assertEqual(sorted(activity["superseded"]), ["plan.rel.mid.v1", "plan.rel.mid.v2"])
        self.assertIn("plan.rel.mid.v3", activity["active"])
        self.assertNotIn("plan.rel.mid.v2", activity["active"])

    # 10. 1→N replacement：两条新 item 同时 supersede 同一旧条目
    def test_one_to_many_replacement(self):
        brief = self.brief(SANDBOX_STATE)
        context = self.context(SANDBOX_STATE, brief)
        decision = self.modify_decision(state=SANDBOX_STATE, brief=brief, context=context)
        diff = make_plan_diff(
            diff_id="plan-diff-split", state=SANDBOX_STATE, intent=INTENT, decision=decision, brief=brief,
            plans=[
                {"id": "plan.rel.mid.v2a", "description": "拆分上半段", "supersedes": ["plan.rel.mid.v1"]},
                {"id": "plan.rel.mid.v2b", "description": "拆分下半段", "supersedes": ["plan.rel.mid.v1"]},
            ],
            allow_simulation=True,
        )
        updated = apply_diff(SANDBOX_STATE, diff, decision, allow_simulation=True)
        activity = resolve_plan_activity(updated)
        self.assertEqual(activity["superseded_by"]["plan.rel.mid.v1"], ["plan.rel.mid.v2a", "plan.rel.mid.v2b"])
        self.assertIn("plan.rel.mid.v2a", activity["active"])
        self.assertIn("plan.rel.mid.v2b", activity["active"])

    # 11. 空 supersedes 保持 E2-A 普通 append
    def test_empty_supersedes_keeps_plain_append(self):
        brief = self.brief(SANDBOX_STATE)
        context = self.context(SANDBOX_STATE, brief)
        decision = self.modify_decision(state=SANDBOX_STATE, brief=brief, context=context)
        diff = make_plan_diff(
            diff_id="plan-diff-append", state=SANDBOX_STATE, intent=INTENT, decision=decision, brief=brief,
            plans=[{"id": "plan.rel.mid.extra", "description": "普通新增", "supersedes": []}],
            allow_simulation=True,
        )
        updated = apply_diff(SANDBOX_STATE, diff, decision, allow_simulation=True)
        activity = resolve_plan_activity(updated)
        self.assertEqual(activity["superseded"], [])
        self.assertIn("plan.rel.mid.extra", activity["active"])
        self.assertIn("plan.rel.mid.v1", activity["active"])

    # 12. author_action=modify 写回路径：simulated authority，绝不记录“作者已接受”
    def test_modify_decision_path_is_simulated_only(self):
        brief = self.brief(SANDBOX_STATE)
        context = self.context(SANDBOX_STATE, brief)
        decision = self.modify_decision(state=SANDBOX_STATE, brief=brief, context=context)
        self.assertEqual(decision["author_action"], "modify")
        self.assertEqual(decision["status"], "simulated_confirmed_for_test")
        self.assertTrue(decision["authority"].startswith("simulation_author_decision:"))
        diff = make_plan_diff(
            diff_id="plan-diff-modify", state=SANDBOX_STATE, intent=INTENT, decision=decision, brief=brief,
            plans=[{"id": "plan.rel.mid.v2", "description": "modify 路径", "supersedes": ["plan.rel.mid.v1"]}],
            allow_simulation=True,
        )
        self.assertTrue(diff["simulation_only"])
        updated = apply_diff(SANDBOX_STATE, diff, decision, allow_simulation=True)
        new_item = [plan for plan in updated["approved_plan"] if plan["id"] == "plan.rel.mid.v2"][0]
        self.assertEqual(new_item["authority"], decision["authority"])
        self.assertEqual(updated["last_authority_source"], decision["authority"])
        # simulation Decision 在无 allow_simulation 的生产路径必须被拒绝
        with self.assertRaises(ContractError):
            make_plan_diff(
                diff_id="plan-diff-nosim", state=SANDBOX_STATE, intent=INTENT, decision=decision, brief=brief,
                plans=[{"id": "plan.rel.mid.v2b", "description": "生产路径", "supersedes": ["plan.rel.mid.v1"]}],
                allow_simulation=False,
            )

    # 13 + 14. stale 真实场景：无关 append 推进 state_rev 后旧 Brief 拒绝；重编译 Brief 通过
    def test_stale_replan_brief_rejected_then_recompiled_passes(self):
        brief_a = self.brief(SANDBOX_STATE, brief_id="plan-brief-stale-a")
        context_a = self.context(SANDBOX_STATE, brief_a, context_id="ctx-stale-a")
        decision_a = self.modify_decision(state=SANDBOX_STATE, brief=brief_a, context=context_a,
                                          decision_id="decision-stale-a")
        self.assertEqual(brief_a["source_versions"]["state_rev"], 1)
        # 另一条合法但无关的 sibling append 让 Story State 进入 N+1
        state_n1 = self.unrelated_append(SANDBOX_STATE)
        self.assertEqual(state_n1["state_rev"], 2)
        self.assertIn("plan.suspense.mid.extra", [plan["id"] for plan in state_n1["approved_plan"]])
        # STALE_REPLAN_BRIEF_REJECTED：旧 Brief A 不得在 N+1 上写回
        with self.assertRaises(ContractError):
            make_plan_diff(
                diff_id="plan-diff-stale", state=state_n1, intent=INTENT, decision=decision_a, brief=brief_a,
                plans=[{"id": "plan.rel.mid.v2", "description": "旧 Brief 写回", "supersedes": ["plan.rel.mid.v1"]}],
                allow_simulation=True,
            )
        # RECOMPILED_CURRENT_BRIEF_PASS：同一 local replan 意图在 N+1 重编译后正常通过
        brief_b = self.brief(state_n1, brief_id="plan-brief-stale-b")
        context_b = self.context(state_n1, brief_b, context_id="ctx-stale-b")
        decision_b = self.modify_decision(state=state_n1, brief=brief_b, context=context_b,
                                          decision_id="decision-stale-b")
        self.assertEqual(brief_b["source_versions"]["state_rev"], 2)
        diff = make_plan_diff(
            diff_id="plan-diff-recompiled", state=state_n1, intent=INTENT, decision=decision_b, brief=brief_b,
            plans=[{"id": "plan.rel.mid.v2", "description": "重编译后的同一意图", "supersedes": ["plan.rel.mid.v1"]}],
            allow_simulation=True,
        )
        updated = apply_diff(state_n1, diff, decision_b, allow_simulation=True)
        self.assertEqual(updated["state_rev"], 3)
        activity = resolve_plan_activity(updated)
        self.assertEqual(activity["superseded"], ["plan.rel.mid.v1"])
        self.assertIn("plan.suspense.mid.extra", activity["active"])

    # --- E2-C-A F1: inactive source / source binding tests ---

    # F1-1. inactive planning source rejected in compile_plan_brief
    def test_inactive_planning_source_rejected_in_brief(self):
        s2 = self.chain(SANDBOX_STATE, new_id="plan.rel.mid.v2", old_id="plan.rel.mid.v1")
        # v1 已被 v2 supersede，不再是 active；用它编译 Brief 应被拒绝
        with self.assertRaises(ContractError):
            compile_plan_brief(
                project_id="plan-project", brief_id="plan-brief-inactive",
                author_planning_question="规划",
                planning_target=REL_TARGET,
                planning_sources=[{"kind": "approved_plan", "ref": "plan.rel.mid.v1"}],
                intent=INTENT, state=s2,
            )

    # F1-2. current active source accepted after supersede chain
    def test_current_active_source_accepted_after_supersede(self):
        s2 = self.chain(SANDBOX_STATE, new_id="plan.rel.mid.v2", old_id="plan.rel.mid.v1")
        # v2 是当前 active source，应正常编译（simulation authority 需显式 gate）
        brief = compile_plan_brief(
            project_id="plan-project", brief_id="plan-brief-active",
            author_planning_question="规划",
            planning_target=REL_TARGET,
            planning_sources=[{"kind": "approved_plan", "ref": "plan.rel.mid.v2"}],
            intent=INTENT, state=s2,
            allow_simulation_sources=True,
        )
        self.assertEqual(brief["planning_sources"][0]["ref"], "plan.rel.mid.v2")

    # F1-3. v1→v2→v3 链：每轮 Brief 明确使用当前 active source
    def test_v1_v2_v3_chain_each_step_uses_active_source(self):
        s2 = self.chain(SANDBOX_STATE, new_id="plan.rel.mid.v2", old_id="plan.rel.mid.v1")
        # 第二轮 chain：v2 是 simulation authority，需显式 gate
        s3 = self.chain(s2, new_id="plan.rel.mid.v3", old_id="plan.rel.mid.v2",
                        diff_id="plan-diff-v3", brief_id="plan-brief-v3",
                        allow_simulation_sources=True)
        activity = resolve_plan_activity(s3)
        self.assertEqual(sorted(activity["superseded"]),
                         ["plan.rel.mid.v1", "plan.rel.mid.v2"])
        self.assertIn("plan.rel.mid.v3", activity["active"])
        self.assertNotIn("plan.rel.mid.v2", activity["active"])
        self.assertNotIn("plan.rel.mid.v1", activity["active"])

    # F1-4. same-target 但 Brief 未声明的 active source 不得 supersede
    def test_same_target_wrong_source_rejected(self):
        # 1→N split 产生 v2a、v2b 同 target 且都 active
        brief = self.brief(SANDBOX_STATE)
        context = self.context(SANDBOX_STATE, brief)
        decision = self.modify_decision(state=SANDBOX_STATE, brief=brief, context=context)
        diff = make_plan_diff(
            diff_id="plan-diff-split", state=SANDBOX_STATE, intent=INTENT, decision=decision, brief=brief,
            plans=[
                {"id": "plan.rel.mid.v2a", "description": "拆分上", "supersedes": ["plan.rel.mid.v1"]},
                {"id": "plan.rel.mid.v2b", "description": "拆分下", "supersedes": ["plan.rel.mid.v1"]},
            ],
            allow_simulation=True,
        )
        s2 = apply_diff(SANDBOX_STATE, diff, decision, allow_simulation=True)
        # Brief 只引用 v2a（simulation authority，需显式 gate），尝试 supersede v2b
        brief_v2a = self.brief(s2, brief_id="plan-brief-v2a-only",
                               sources=[{"kind": "approved_plan", "ref": "plan.rel.mid.v2a"}],
                               allow_simulation_sources=True)
        context_v2a = self.context(s2, brief_v2a, context_id="ctx-v2a-only")
        decision_v2a = self.modify_decision(
            state=s2, brief=brief_v2a, context=context_v2a, decision_id="decision-v2a-only",
        )
        with self.assertRaises(ContractError):
            make_plan_diff(
                diff_id="plan-diff-wrong-source", state=s2, intent=INTENT,
                decision=decision_v2a, brief=brief_v2a,
                plans=[{"id": "plan.rel.mid.v3", "description": "应拒绝",
                        "supersedes": ["plan.rel.mid.v2b"]}],
                allow_simulation=True,
            )

    # F1-5. 多 source Brief 显式 N→1 consolidation
    def test_multi_source_n_to_one_replacement_accepted(self):
        # 1→N split 产生 v2a、v2b
        brief = self.brief(SANDBOX_STATE)
        context = self.context(SANDBOX_STATE, brief)
        decision = self.modify_decision(state=SANDBOX_STATE, brief=brief, context=context)
        diff = make_plan_diff(
            diff_id="plan-diff-split", state=SANDBOX_STATE, intent=INTENT, decision=decision, brief=brief,
            plans=[
                {"id": "plan.rel.mid.v2a", "description": "拆分上", "supersedes": ["plan.rel.mid.v1"]},
                {"id": "plan.rel.mid.v2b", "description": "拆分下", "supersedes": ["plan.rel.mid.v1"]},
            ],
            allow_simulation=True,
        )
        s2 = apply_diff(SANDBOX_STATE, diff, decision, allow_simulation=True)
        # Brief 同时引用 v2a 和 v2b
        multi_sources = [
            {"kind": "approved_plan", "ref": "plan.rel.mid.v2a"},
            {"kind": "approved_plan", "ref": "plan.rel.mid.v2b"},
        ]
        brief_multi = self.brief(s2, brief_id="plan-brief-multi",
                                 sources=multi_sources,
                                 allow_simulation_sources=True)
        context_multi = self.context(s2, brief_multi, context_id="ctx-multi")
        decision_multi = self.modify_decision(
            state=s2, brief=brief_multi, context=context_multi, decision_id="decision-multi",
        )
        diff_consolid = make_plan_diff(
            diff_id="plan-diff-consolid", state=s2, intent=INTENT,
            decision=decision_multi, brief=brief_multi,
            plans=[{"id": "plan.rel.mid.v3", "description": "N→1 合并",
                    "supersedes": ["plan.rel.mid.v2a", "plan.rel.mid.v2b"]}],
            allow_simulation=True,
        )
        s3 = apply_diff(s2, diff_consolid, decision_multi, allow_simulation=True)
        activity = resolve_plan_activity(s3)
        self.assertIn("plan.rel.mid.v3", activity["active"])
        self.assertNotIn("plan.rel.mid.v2a", activity["active"])
        self.assertNotIn("plan.rel.mid.v2b", activity["active"])

    # --- E2-C-A F2: simulation authority isolation ---

    # F2-1. 默认生产 Brief 拒绝 simulation planning source
    def test_production_brief_rejects_simulation_source(self):
        s2 = self.chain(SANDBOX_STATE, new_id="plan.rel.mid.v2", old_id="plan.rel.mid.v1")
        # v2 的 authority 是 simulation_author_decision:*，默认生产路径必须拒绝
        with self.assertRaises(ContractError):
            compile_plan_brief(
                project_id="plan-project", brief_id="plan-brief-prod",
                author_planning_question="规划",
                planning_target=REL_TARGET,
                planning_sources=[{"kind": "approved_plan", "ref": "plan.rel.mid.v2"}],
                intent=INTENT, state=s2,
            )

    # F2-2. 显式 simulation gate 接受 simulation source
    def test_explicit_simulation_gate_accepts_simulation_source(self):
        s2 = self.chain(SANDBOX_STATE, new_id="plan.rel.mid.v2", old_id="plan.rel.mid.v1")
        brief = compile_plan_brief(
            project_id="plan-project", brief_id="plan-brief-sim",
            author_planning_question="规划",
            planning_target=REL_TARGET,
            planning_sources=[{"kind": "approved_plan", "ref": "plan.rel.mid.v2"}],
            intent=INTENT, state=s2,
            allow_simulation_sources=True,
        )
        self.assertEqual(brief["planning_sources"][0]["ref"], "plan.rel.mid.v2")

    # F2-3. author_decision 默认生产路径继续 PASS
    def test_author_decision_source_passes_production_default(self):
        brief = self.brief(SANDBOX_STATE)  # default allow_simulation_sources=False
        self.assertEqual(brief["planning_sources"][0]["ref"], "plan.rel.mid.v1")
        self.assertTrue(brief["planning_sources"][0]["verified_authority"].startswith("author_decision:"))

    # F2-4. manual_import 默认生产路径继续 PASS
    def test_manual_import_source_passes_production_default(self):
        manual_state = dict(STATE, approved_plan=STATE["approved_plan"] + [
            {"id": "plan.manual", "description": "手动导入", "target_ref": "target.front-half",
             "authority": "manual_import:seed", "occurred": False},
        ])
        brief = compile_plan_brief(
            project_id="plan-project", brief_id="plan-brief-manual",
            author_planning_question="规划",
            planning_target=TARGET,
            planning_sources=[{"kind": "approved_plan", "ref": "plan.manual"}],
            intent=INTENT, state=manual_state,
        )
        self.assertEqual(brief["planning_sources"][0]["verified_authority"], "manual_import:seed")

    # F2-5. inactive simulation source 即使 allow_simulation_sources=True 仍拒绝
    def test_inactive_simulation_source_rejected_even_with_gate(self):
        s2 = self.chain(SANDBOX_STATE, new_id="plan.rel.mid.v2", old_id="plan.rel.mid.v1")
        s3 = self.chain(s2, new_id="plan.rel.mid.v3", old_id="plan.rel.mid.v2",
                        diff_id="plan-diff-v3", brief_id="plan-brief-v3",
                        allow_simulation_sources=True)
        # v2 已被 v3 supersede，现在是 inactive；即使开 simulation gate 也必须拒绝
        with self.assertRaises(ContractError):
            compile_plan_brief(
                project_id="plan-project", brief_id="plan-brief-dead-sim",
                author_planning_question="规划",
                planning_target=REL_TARGET,
                planning_sources=[{"kind": "approved_plan", "ref": "plan.rel.mid.v2"}],
                intent=INTENT, state=s3,
                allow_simulation_sources=True,
            )


if __name__ == "__main__":
    unittest.main()
