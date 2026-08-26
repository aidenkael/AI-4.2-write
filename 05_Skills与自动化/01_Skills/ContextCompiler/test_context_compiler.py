import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from context_compiler import (
    ContractError,
    SELECTABLE_AREAS,
    compile_context,
    context_package_is_stale,
)


# ---------------------------------------------------------------------------
# Disposable sandbox (section 21).  Big enough that real selection must occur:
# 8 canon_facts / 4 character_state / 3 relationship_state / 3 occurred_events
# / 4 open_threads / 4 approved_plan (one broader active, one current-task
# active, one sibling active, one superseded history).
# ---------------------------------------------------------------------------
INTENT = {
    "project_id": "ctx-project", "intent_rev": 3,
    "work_direction": "都市女性长篇：姐妹同盟从共生走向利益互斥",
    "reader_promise": "读者先相信姐妹同盟牢不可破，再亲眼看见利益让承诺失效",
    "current_priority": "写好姐妹第一次公开谈判的张力",
    "current_focus": "姐姐在公开场合第一次承认双方利益已不能同时满足",
    "hard_constraints": ["不提前泄露最终谁离开家族企业"],
    "avoidances": ["不把妹妹写成纯粹反派"],
    "open_space": ["谈判后姐妹是否彻底决裂"],
}
STATE = {
    "project_id": "ctx-project", "state_rev": 7,
    "canon_facts": [
        {"id": "canon.family-business", "fact": "家族企业由姐妹共同继承。", "authority": "accepted_text:ch1"},
        {"id": "canon.sisters", "fact": "姐姐林晚与妹妹林昼是双胞胎。", "authority": "accepted_text:ch1"},
        {"id": "canon.father-debt", "fact": "父亲生前留下一笔未清偿的旧债。", "authority": "accepted_text:ch2"},
        {"id": "canon.board", "fact": "董事会将在季末改选。", "authority": "accepted_text:ch3"},
        {"id": "canon.contract", "fact": "姐妹曾签有内部利益分配协议。", "authority": "accepted_text:ch2"},
        {"id": "canon.city", "fact": "故事发生在临海市。", "authority": "manual_import:seed"},
        {"id": "canon.mother", "fact": "母亲仍健在并持有否决权。", "authority": "accepted_text:ch4"},
        {"id": "canon.rival", "fact": "外部收购方已接触妹妹。", "authority": "accepted_text:ch5"},
    ],
    "character_state": [
        {"id": "chr.sister-elder", "name": "林晚", "status": "守住家族企业主导权，开始动摇。", "authority": "accepted_text:ch5"},
        {"id": "chr.sister-younger", "name": "林昼", "status": "已私下接触外部收购方。", "authority": "accepted_text:ch5"},
        {"id": "chr.mother", "name": "母亲", "status": "观望，尚未表态。", "authority": "accepted_text:ch4"},
        {"id": "chr.lawyer", "name": "周律师", "status": "同时为姐妹服务，立场暧昧。", "authority": "accepted_text:ch3"},
    ],
    "relationship_state": [
        {"id": "rel.sisters", "relation": "姐妹", "status": "表面同盟，利益已开始互斥。", "authority": "accepted_text:ch5"},
        {"id": "rel.mother-daughters", "relation": "母女", "status": "母亲在两人之间保持平衡。", "authority": "accepted_text:ch4"},
        {"id": "rel.sisters-lawyer", "relation": "委托", "status": "周律师掌握双方信息。", "authority": "accepted_text:ch3"},
    ],
    "occurred_events": [
        {"id": "ev.father-funeral", "event": "父亲葬礼上姐妹公开表示共同经营。", "authority": "accepted_text:ch1"},
        {"id": "ev.secret-meeting", "event": "妹妹与收购方秘密会面。", "authority": "accepted_text:ch5"},
        {"id": "ev.board-warning", "event": "董事会私下提醒姐姐注意股权变动。", "authority": "accepted_text:ch4"},
    ],
    "open_threads": [
        {"id": "th.negotiation", "thread": "姐妹第一次公开谈判尚未发生。", "authority": "accepted_text:ch5"},
        {"id": "th.father-debt", "thread": "父亲旧债由谁承担未定。", "authority": "accepted_text:ch2"},
        {"id": "th.acquisition", "thread": "外部收购是否成行未定。", "authority": "accepted_text:ch5"},
        {"id": "th.mother-vote", "thread": "母亲否决权会投向谁未定。", "authority": "accepted_text:ch4"},
    ],
    "approved_plan": [
        {"id": "plan.broader", "description": "前半程围绕姐妹利益从共生滑向互斥。", "target_ref": "book.front-half",
         "authority": "author_decision:d-broader", "occurred": False, "supersedes": [], "built_from": []},
        {"id": "plan.sisters-old", "description": "初版：姐妹始终互相保护。", "target_ref": "rel.sisters.arc",
         "authority": "author_decision:d-old", "occurred": False, "supersedes": [], "built_from": []},
        {"id": "plan.sisters-task", "description": "当前：姐妹第一次公开承认利益不能同时满足。", "target_ref": "rel.sisters.arc",
         "authority": "author_decision:d-task", "occurred": False, "supersedes": ["plan.sisters-old"], "built_from": []},
        {"id": "plan.mother-sibling", "description": "sibling：母亲否决权线中期推进。", "target_ref": "mother.subplot",
         "authority": "author_decision:d-sibling", "occurred": False, "supersedes": [], "built_from": []},
    ],
}

# Semantic selection for: "规划/准备写姐妹第一次公开承认利益已经不能同时满足的谈判场景。"
# Only the directly relevant items are named: 2 canon facts, the elder sister,
# the sister relationship, 1 open thread and the current active relationship
# plan.  Unrelated siblings / most canon / the superseded plan are NOT selected.
SELECTIONS = [
    {"area": "canon_facts", "id": "canon.family-business", "reason": "谈判围绕家族企业控制权展开"},
    {"area": "canon_facts", "id": "canon.contract", "reason": "内部利益分配协议是谈判的直接依据"},
    {"area": "character_state", "id": "chr.sister-elder", "reason": "当前场景以姐姐公开承认为核心"},
    {"area": "relationship_state", "id": "rel.sisters", "reason": "姐妹关系状态直接约束谈判行为"},
    {"area": "open_threads", "id": "th.negotiation", "reason": "本任务正是兑现这条尚未发生的谈判"},
    {"area": "approved_plan", "id": "plan.sisters-task", "reason": "当前 active 的姐妹线规划约束本场景走向"},
]

TOTAL_STATE_ITEMS = 8 + 4 + 3 + 3 + 4 + 4  # = 26


def make_brief(intent=None, state=None, knowledge_needs=None, brief_id="ctx-brief-1", brief_rev=1):
    intent = intent or INTENT
    state = state or STATE
    return {
        "artifact_type": "creation_brief",
        "brief_id": brief_id,
        "brief_rev": brief_rev,
        "project_id": intent["project_id"],
        "status": "CURRENT",
        "author_input": "规划/准备写姐妹第一次公开承认利益已经不能同时满足的谈判场景。",
        "knowledge_needs": list(knowledge_needs or []),
        "source_versions": {"intent_rev": intent["intent_rev"], "state_rev": state["state_rev"]},
    }


def fake_retrieve_must_not_be_called(query):
    raise AssertionError("无 knowledge need 时不得调用 KnowledgeRetrieve")


class _FakeHit:
    def __init__(self, source_anchor, statement="示例知识观察"):
        self.source_kind = "reference_bkp"
        self.source_id = "book_0035"
        self.source_title = "长安十二时辰"
        self.maturity = "source_bound"
        self.source_anchor = source_anchor
        self.source = "knowledge/cards.md#x"
        self.statement = statement
        self.scope = "关系冲突"
        self.boundary = "仅限参考作品，不是原创 Canon"
        self.confidence = "medium"
        self.evidence = ["evidence-1"]
        self.rank = 1
        self.relevance_reason = "测试相关性"


class _FakePackage:
    def __init__(self, hits, status="OK", gaps=None):
        self.hits = hits
        self.status = status
        self.gaps = list(gaps or [])
        self.candidate_count = len(hits)


def fake_retrieve_ok(query):
    return _FakePackage([_FakeHit("bkp.negotiation.1"), _FakeHit("bkp.negotiation.2")])


NEG_REF = "reference_bkp/book_0035/bkp.negotiation.1"


class ContextCompilerSandboxTest(unittest.TestCase):
    """Positive sandbox: real selection actually happens, not whole-State dump."""

    def context(self, selections=None, **kwargs):
        return compile_context(
            context_id="ctx-1",
            brief=kwargs.pop("brief", make_brief()),
            intent=kwargs.pop("intent", INTENT),
            state=kwargs.pop("state", STATE),
            state_selections=selections if selections is not None else SELECTIONS,
            retrieval=kwargs.pop("retrieval", fake_retrieve_must_not_be_called),
            **kwargs,
        )

    def test_selection_actually_reduces_state(self):
        ctx = self.context()
        ss = ctx["size_summary"]
        self.assertEqual(ss["total_state_items"], TOTAL_STATE_ITEMS)
        self.assertEqual(ss["selected_state_items"], len(SELECTIONS))
        self.assertLess(ss["selected_state_items"], ss["total_state_items"])
        self.assertEqual(ss["total_active_plans"], 3)
        self.assertEqual(ss["selected_active_plans"], 1)
        self.assertEqual(ss["selected_knowledge_hits"], 0)

    def test_only_selected_items_copied(self):
        ctx = self.context()
        sstate = ctx["selected_story_state"]
        self.assertEqual([i["id"] for i in sstate["canon_facts"]], ["canon.family-business", "canon.contract"])
        self.assertEqual([i["id"] for i in sstate["character_state"]], ["chr.sister-elder"])
        self.assertEqual([i["id"] for i in sstate["relationship_state"]], ["rel.sisters"])
        self.assertEqual([i["id"] for i in sstate["open_threads"]], ["th.negotiation"])
        self.assertEqual([i["id"] for i in sstate["approved_plan"]], ["plan.sisters-task"])
        # Unselected areas are not dumped into the package.
        self.assertNotIn("occurred_events", sstate)

    def test_copied_items_match_authoritative_content(self):
        ctx = self.context()
        elder = ctx["selected_story_state"]["character_state"][0]
        original = next(c for c in STATE["character_state"] if c["id"] == "chr.sister-elder")
        self.assertEqual(elder, original)
        self.assertIsNot(elder, original)  # deep copy, not the same object

    def test_intent_selected_from_real_intent_only(self):
        ctx = self.context()
        si = ctx["selected_intent"]
        for field in ("work_direction", "reader_promise", "hard_constraints", "open_space",
                      "current_priority", "current_focus", "avoidances"):
            self.assertEqual(si[field], INTENT[field])

    def test_selection_reason_traceable_per_item(self):
        ctx = self.context()
        refs = {r["source_ref"]: r["reason"] for r in ctx["selection_reason"]}
        self.assertEqual(len(refs), len(SELECTIONS))
        self.assertIn("relationship_state:rel.sisters", refs)
        self.assertTrue(all(r.strip() for r in refs.values()))

    def test_built_from_records_all_versions(self):
        ctx = self.context()
        self.assertEqual(ctx["built_from"], {
            "brief_id": "ctx-brief-1", "brief_rev": 1,
            "intent_rev": INTENT["intent_rev"], "state_rev": STATE["state_rev"],
        })

    def test_missing_reason_rejected_for_traceability(self):
        with self.assertRaises(ContractError):
            self.context(selections=[{"area": "canon_facts", "id": "canon.city", "reason": "   "}])


class ContextCompilerNegativeTest(unittest.TestCase):
    """Negative boundaries from section 22."""

    def compile(self, selections, **kwargs):
        return compile_context(
            context_id="ctx-neg",
            brief=kwargs.pop("brief", make_brief()),
            intent=kwargs.pop("intent", INTENT),
            state=kwargs.pop("state", STATE),
            state_selections=selections,
            retrieval=kwargs.pop("retrieval", fake_retrieve_must_not_be_called),
            **kwargs,
        )

    # 1. missing state ref -> reject
    def test_missing_state_ref_rejected(self):
        with self.assertRaises(ContractError):
            self.compile([{"area": "canon_facts", "id": "canon.does-not-exist", "reason": "x"}])
        with self.assertRaises(ContractError):
            self.compile([{"area": "approved_plan", "id": "plan.no-such", "reason": "x"}])

    # 2. duplicate selection ref -> reject
    def test_duplicate_selection_ref_rejected(self):
        dup = [
            {"area": "relationship_state", "id": "rel.sisters", "reason": "a"},
            {"area": "relationship_state", "id": "rel.sisters", "reason": "b"},
        ]
        with self.assertRaises(ContractError):
            self.compile(dup)

    # 3. ambiguous duplicate id in same area -> reject
    def test_ambiguous_duplicate_id_rejected(self):
        polluted = copy.deepcopy(STATE)
        polluted["open_threads"].append(
            {"id": "th.negotiation", "thread": "重名条目", "authority": "accepted_text:ch9"},
        )
        with self.assertRaises(ContractError):
            self.compile([{"area": "open_threads", "id": "th.negotiation", "reason": "x"}], state=polluted)

    # 3b. duplicate approved_plan id -> reject.  Must be the duplicate-id
    # ambiguity guard, not superseded / simulation / missing.
    def test_approved_plan_duplicate_id_rejected(self):
        polluted = copy.deepcopy(STATE)
        polluted["approved_plan"].append(
            {"id": "plan.sisters-task", "description": "同 id 的重复条目（内容不同）",
             "target_ref": "rel.sisters.arc", "authority": "author_decision:d-dup",
             "occurred": False, "supersedes": [], "built_from": []},
        )
        with self.assertRaises(ContractError) as cm:
            self.compile([{"area": "approved_plan", "id": "plan.sisters-task", "reason": "x"}], state=polluted)
        self.assertIn("duplicate-id ambiguity", str(cm.exception))

    # 4. unsupported area -> reject
    def test_unsupported_area_rejected(self):
        with self.assertRaises(ContractError):
            self.compile([{"area": "secret_area", "id": "x", "reason": "x"}])
        with self.assertRaises(ContractError):
            self.compile([{"area": "canon_facts.subpath", "id": "canon.city", "reason": "x"}])

    # 5. superseded plan -> reject
    def test_superseded_plan_rejected(self):
        with self.assertRaises(ContractError):
            self.compile([{"area": "approved_plan", "id": "plan.sisters-old", "reason": "x"}])

    def _state_with_simulation_plan(self):
        polluted = copy.deepcopy(STATE)
        polluted["approved_plan"].append(
            {"id": "plan.sim", "description": "simulation-only plan", "target_ref": "t",
             "authority": "simulation_author_decision:d-sim", "occurred": False,
             "supersedes": [], "built_from": []},
        )
        return polluted

    # 6. simulation plan default -> reject
    def test_simulation_plan_default_rejected(self):
        polluted = self._state_with_simulation_plan()
        with self.assertRaises(ContractError):
            self.compile([{"area": "approved_plan", "id": "plan.sim", "reason": "x"}], state=polluted)

    # 7. simulation plan explicit test gate -> pass
    def test_simulation_plan_explicit_gate_passes(self):
        polluted = self._state_with_simulation_plan()
        ctx = self.compile(
            [{"area": "approved_plan", "id": "plan.sim", "reason": "x"}],
            state=polluted, allow_simulation_sources=True,
        )
        self.assertEqual([p["id"] for p in ctx["selected_story_state"]["approved_plan"]], ["plan.sim"])

    # 8. 知识选择 without knowledge_need -> reject
    def test_bkp_without_knowledge_need_rejected(self):
        brief = make_brief(knowledge_needs=[])
        with self.assertRaises(ContractError):
            self.compile([], brief=brief, selected_knowledge_ids=[NEG_REF],
                         retrieval=fake_retrieve_ok)

    # 9. selected knowledge not in retrieval -> gap / not injected
    def test_selected_bkp_not_in_retrieval_not_injected(self):
        brief = make_brief(knowledge_needs=["姐妹公开谈判如何处理利益冲突"])
        ctx = self.compile([], brief=brief, selected_knowledge_ids=["reference_bkp/book_0035/bkp.not-in-recall"],
                           retrieval=fake_retrieve_ok)
        self.assertEqual(ctx["selected_knowledge_hits"], [])
        self.assertEqual(ctx["status"], "CURRENT_WITH_KNOWLEDGE_GAP")
        self.assertTrue(ctx["retrieval"]["gaps"])

    def test_selected_bkp_in_retrieval_injected(self):
        brief = make_brief(knowledge_needs=["姐妹公开谈判如何处理利益冲突"])
        ctx = self.compile([], brief=brief, selected_knowledge_ids=[NEG_REF],
                           retrieval=fake_retrieve_ok)
        self.assertEqual(len(ctx["selected_knowledge_hits"]), 1)
        hit = ctx["selected_knowledge_hits"][0]
        self.assertEqual(hit["selection_ref"], NEG_REF)
        self.assertEqual(hit["source_kind"], "reference_bkp")
        self.assertEqual(hit["source_id"], "book_0035")
        self.assertEqual(hit["source_anchor"], "bkp.negotiation.1")
        self.assertEqual(ctx["status"], "CURRENT")


class ContextCompilerIsolationTest(unittest.TestCase):
    """Zero-mutation, BKP/State isolation and empty-selection boundaries."""

    def test_context_does_not_mutate_state_or_intent(self):  # 13
        before_state = copy.deepcopy(STATE)
        before_intent = copy.deepcopy(INTENT)
        compile_context(
            context_id="ctx-mut", brief=make_brief(), intent=INTENT, state=STATE,
            state_selections=SELECTIONS, retrieval=fake_retrieve_must_not_be_called,
        )
        self.assertEqual(STATE, before_state)
        self.assertEqual(INTENT, before_intent)

    def test_bkp_structurally_isolated_from_story_state(self):  # 14
        brief = make_brief(knowledge_needs=["姐妹公开谈判利益冲突"])
        ctx = compile_context(
            context_id="ctx-iso", brief=brief, intent=INTENT, state=STATE,
            state_selections=[{"area": "relationship_state", "id": "rel.sisters", "reason": "谈判核心"}],
            selected_knowledge_ids=[NEG_REF], retrieval=fake_retrieve_ok,
        )
        self.assertEqual(len(ctx["selected_knowledge_hits"]), 1)
        for area in ctx["selected_story_state"]:
            self.assertIn(area, SELECTABLE_AREAS)
        state_item_keys = set()
        for items in ctx["selected_story_state"].values():
            for item in items:
                state_item_keys.update(item.keys())
        self.assertNotIn("selection_ref", state_item_keys)
        self.assertNotIn("source_kind", state_item_keys)

    def test_empty_selection_does_not_fallback_to_full_state(self):  # 15
        ctx = compile_context(
            context_id="ctx-empty", brief=make_brief(), intent=INTENT, state=STATE,
            state_selections=[], retrieval=fake_retrieve_must_not_be_called,
        )
        self.assertEqual(ctx["selected_story_state"], {})
        self.assertEqual(ctx["size_summary"]["selected_state_items"], 0)
        self.assertEqual(ctx["status"], "CURRENT")

    def test_conflicts_or_tensions_are_noncanonical(self):
        ctx = compile_context(
            context_id="ctx-conflict", brief=make_brief(), intent=INTENT, state=STATE,
            state_selections=SELECTIONS, retrieval=fake_retrieve_must_not_be_called,
            conflicts_or_tensions=[
                {"text": "当前 approved plan 要求两人继续合作，但 relationship_state 已进入公开利益冲突。"},
            ],
        )
        self.assertEqual(len(ctx["conflicts_or_tensions"]), 1)
        entry = ctx["conflicts_or_tensions"][0]
        self.assertEqual(entry["authority"], "analysis_noncanonical")
        self.assertTrue(entry["must_not_write_canon"])


class ContextCompilerStaleTest(unittest.TestCase):
    """E3-A stale helper: brief_id/brief_rev/intent_rev/state_rev all checked."""

    def build(self):
        return compile_context(
            context_id="ctx-stale", brief=make_brief(), intent=INTENT, state=STATE,
            state_selections=SELECTIONS, retrieval=fake_retrieve_must_not_be_called,
        )

    # 10. stale state_rev -> stale
    def test_state_rev_change_is_stale(self):
        ctx = self.build()
        new_state = dict(STATE, state_rev=STATE["state_rev"] + 1)
        self.assertTrue(context_package_is_stale(ctx, make_brief(), INTENT, new_state))

    # 11. stale intent_rev -> stale
    def test_intent_rev_change_is_stale(self):
        ctx = self.build()
        new_intent = dict(INTENT, intent_rev=INTENT["intent_rev"] + 1)
        self.assertTrue(context_package_is_stale(ctx, make_brief(), new_intent, STATE))

    # 12. changed brief_rev -> stale
    def test_brief_rev_change_is_stale(self):
        ctx = self.build()
        self.assertTrue(context_package_is_stale(ctx, make_brief(brief_rev=2), INTENT, STATE))

    def test_brief_id_change_is_stale(self):
        ctx = self.build()
        self.assertTrue(context_package_is_stale(ctx, make_brief(brief_id="other-brief"), INTENT, STATE))

    def test_no_change_is_not_stale(self):
        ctx = self.build()
        self.assertFalse(context_package_is_stale(ctx, make_brief(), INTENT, STATE))

    def test_stale_brief_rejected_at_build_time(self):
        old_brief = make_brief()
        old_brief["source_versions"] = {"intent_rev": INTENT["intent_rev"], "state_rev": STATE["state_rev"] - 1}
        with self.assertRaises(ContractError):
            compile_context(
                context_id="ctx-old-brief", brief=old_brief, intent=INTENT, state=STATE,
                state_selections=SELECTIONS, retrieval=fake_retrieve_must_not_be_called,
            )

    def test_cross_project_rejected(self):
        other_state = dict(STATE, project_id="other-project")
        with self.assertRaises(ContractError):
            compile_context(
                context_id="ctx-xproj", brief=make_brief(), intent=INTENT, state=other_state,
                state_selections=[], retrieval=fake_retrieve_must_not_be_called,
            )


class ContextCompilerAuthorityTest(unittest.TestCase):
    """approved_plan production authority authenticity (E3-A-R1).

    Default trusted future planning authorities come from the frozen StoryPlan
    semantic: author_decision: / manual_import:; simulation_author_decision:
    only under the explicit test/sandbox gate.  accepted_text: is a legal
    Canon authority but NOT a legal future planning authority.
    """

    def compile(self, selections, **kwargs):
        return compile_context(
            context_id="ctx-auth",
            brief=kwargs.pop("brief", make_brief()),
            intent=kwargs.pop("intent", INTENT),
            state=kwargs.pop("state", STATE),
            state_selections=selections,
            retrieval=kwargs.pop("retrieval", fake_retrieve_must_not_be_called),
            **kwargs,
        )

    def _state_with_plan(self, plan):
        polluted = copy.deepcopy(STATE)
        polluted["approved_plan"].append(plan)
        return polluted

    # 1. author_decision planning -> production PASS
    def test_author_decision_planning_production_pass(self):
        ctx = self.compile([{"area": "approved_plan", "id": "plan.sisters-task", "reason": "x"}])
        self.assertEqual([p["id"] for p in ctx["selected_story_state"]["approved_plan"]], ["plan.sisters-task"])

    # 2. manual_import planning -> production PASS
    def test_manual_import_planning_production_pass(self):
        polluted = self._state_with_plan(
            {"id": "plan.imported", "description": "manual-imported 的规划线", "target_ref": "book.imported",
             "authority": "manual_import:seed-arc", "occurred": False, "supersedes": [], "built_from": []},
        )
        ctx = self.compile([{"area": "approved_plan", "id": "plan.imported", "reason": "x"}], state=polluted)
        self.assertEqual([p["id"] for p in ctx["selected_story_state"]["approved_plan"]], ["plan.imported"])

    # 3/4. simulation default reject + explicit gate pass are kept in
    # ContextCompilerNegativeTest (#6 / #7).

    # 5. accepted_text planning -> reject: legal Canon authority, but not a
    #    legal future planning authority.
    def test_accepted_text_planning_rejected(self):
        polluted = self._state_with_plan(
            {"id": "plan.accepted", "description": "以正文为 authority 的规划", "target_ref": "t",
             "authority": "accepted_text:ch10", "occurred": False, "supersedes": [], "built_from": []},
        )
        with self.assertRaises(ContractError) as cm:
            self.compile([{"area": "approved_plan", "id": "plan.accepted", "reason": "x"}], state=polluted)
        self.assertIn("authority", str(cm.exception))

    # 6. arbitrary / untrusted planning authority -> reject
    def test_arbitrary_planning_authority_rejected(self):
        polluted = self._state_with_plan(
            {"id": "plan.guess", "description": "不可信来源的规划", "target_ref": "t",
             "authority": "external_guess:x", "occurred": False, "supersedes": [], "built_from": []},
        )
        with self.assertRaises(ContractError) as cm:
            self.compile([{"area": "approved_plan", "id": "plan.guess", "reason": "x"}], state=polluted)
        self.assertIn("authority", str(cm.exception))

    # The planning whitelist never applies to Canon areas: accepted_text stays
    # a legal Canon source.
    def test_canon_accepted_text_still_legal(self):
        ctx = self.compile([{"area": "canon_facts", "id": "canon.family-business", "reason": "x"}])
        self.assertEqual(ctx["selected_story_state"]["canon_facts"][0]["authority"], "accepted_text:ch1")


if __name__ == "__main__":
    unittest.main()
