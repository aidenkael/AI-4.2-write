"""E2-C-A｜StoryPlan 最小局部重规划 sandbox 验证脚本（disposable）。

只调用 StoryPlan 正式公开函数（compile_plan_brief / build_plan_context /
create_plan_candidate / create_decision_record / make_plan_diff / apply_diff /
resolve_plan_activity），在内存副本上验证：

- 局部 supersede：旧 planning 原样保留，activity 为纯函数投影；
- sibling / ancestor / Canon 不受影响；
- cross-target、missing ref、inactive base 的 supersede 被拒绝；
- stale local Brief 拒绝写回；重编译 Brief 后同一意图通过。

SIMULATED_DECISION_ONLY：全部 Decision 为 TEST_ONLY simulation，
不得表述为"作者已接受任何规划"。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
STORY_PLAN_PY = HERE.parents[1] / "05_Skills与自动化" / "01_Skills" / "StoryPlan" / "story_plan.py"

_spec = importlib.util.spec_from_file_location("e2c_story_plan_skill", STORY_PLAN_PY)
assert _spec and _spec.loader, "无法定位 StoryPlan story_plan.py"
sp = importlib.util.module_from_spec(_spec)
sys.modules["e2c_story_plan_skill"] = sp
_spec.loader.exec_module(sp)

ContractError = sp.ContractError
CANON_AREAS = sp.CANON_AREAS

RESULTS: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append({"check": name, "pass": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + ((" | " + detail) if detail else ""))
    assert ok, name


def expect_contract_error(name: str, fn) -> str:
    try:
        fn()
    except ContractError as exc:
        check(name, True, f"ContractError: {exc}")
        return str(exc)
    check(name, False, "expected ContractError but none raised")
    raise AssertionError(name)


# ---------------------------------------------------------------------------
# 七、sandbox 初始状态：ancestor + 待局部修改 planning + unrelated sibling
# ---------------------------------------------------------------------------
INTENT = {
    "project_id": "e2c-sandbox", "intent_rev": 1,
    "work_direction": "都市悬疑长篇", "reader_promise": "读者先相信同盟，后发现目标互斥",
    "hard_constraints": ["不提前确认最终反派"], "open_space": ["关系归宿"],
}
STATE = {
    "project_id": "e2c-sandbox", "state_rev": 1,
    "canon_facts": [
        {"id": "canon.seed.city", "fact": "故事发生在港口城市。", "authority": "manual_import:seed"},
        {"id": "canon.seed.case", "fact": "两人因旧案结识。", "authority": "manual_import:seed"},
    ],
    "character_state": [{"id": "char.lead", "name": "女主", "authority": "manual_import:seed"}],
    "relationship_state": [{"id": "rel.seed", "description": "表面同盟", "authority": "manual_import:seed"}],
    "occurred_events": [],
    "open_threads": [],
    "approved_plan": [
        # A. ancestor / broader plan
        {"id": "plan.book.direction", "description": "全书方向：同盟假象到目标互斥。",
         "target_ref": "target.book.direction", "authority": "author_decision:sim-book", "occurred": False},
        # B. 待局部修改的 relationship planning
        {"id": "plan.rel.mid.v1", "description": "关系中段 v1：隐瞒与试探循环。",
         "target_ref": "target.rel.mid", "authority": "author_decision:sim-rel-1", "occurred": False},
        # C. unrelated sibling
        {"id": "plan.suspense.mid", "description": "悬念链：旧案卷宗去向。",
         "target_ref": "target.suspense.mid", "authority": "author_decision:sim-suspense", "occurred": False},
    ],
}
sp.validate_story_state(STATE)
REL_TARGET = {"target_id": "target.rel.mid", "description": "关系中段局部重规划",
              "scope_kind": "relationship", "scope": "只动关系中段，不重算全书"}
REL_SOURCES = [{"kind": "approved_plan", "ref": "plan.rel.mid.v1"}]


def compile_rel_brief(state, brief_id: str):
    return sp.compile_plan_brief(
        project_id="e2c-sandbox", brief_id=brief_id,
        author_planning_question="把关系中段改成责任分配与关系判断持续变化的推进。",
        planning_target=REL_TARGET, planning_sources=REL_SOURCES,
        intent=INTENT, state=state, semantic_interpretation={"knowledge_needs": []},
    )


def build_rel_chain(state, brief_id: str, context_id: str, decision_id: str, candidate_id: str):
    brief = compile_rel_brief(state, brief_id)
    context = sp.build_plan_context(
        context_id=context_id, brief=brief, intent=INTENT, state=state, retrieval=None,
    )
    check(f"{brief_id}: 0 BKP 路径", context["retrieval"]["status"] == "SKIPPED_NO_KNOWLEDGE_NEED",
          context["retrieval"]["status"])
    candidate = sp.create_plan_candidate(
        candidate_id=candidate_id, brief=brief, context=context,
        model_output={"format": "markdown", "proposal": "关系中段 v2：未解决旧债通过当前选择成本持续产生后果。"},
    )
    check(f"{candidate_id}: noncanonical", candidate["status"] == "proposal_noncanonical"
          and candidate["authority"] == "ai_candidate:noncanonical" and candidate["must_not_write_canon"])
    decision = sp.create_decision_record(
        decision_id=decision_id, brief=brief, context=context, candidate=candidate,
        author_action="modify", author_confirmation_ref="author:TEST_ONLY/e2c-simulated-modify",
        final_decision={"note": "SIMULATED_DECISION_ONLY"}, simulation=True,
    )
    check(f"{decision_id}: simulated modify", decision["author_action"] == "modify"
          and decision["status"] == "simulated_confirmed_for_test"
          and decision["authority"].startswith("simulation_author_decision:"))
    return brief, decision


# ---------------------------------------------------------------------------
# 八、真实 local replan 链：plan.rel.mid.v2 supersedes plan.rel.mid.v1
# ---------------------------------------------------------------------------
brief_a, decision_a = build_rel_chain(STATE, "plan-brief-rel-a", "plan-context-rel-a",
                                      "decision-rel-v2", "cand-rel-v2")
canon_before = {area: deepcopy(STATE[area]) for area in CANON_AREAS}
diff_v2 = sp.make_plan_diff(
    diff_id="diff-rel-v2", state=STATE, intent=INTENT, decision=decision_a, brief=brief_a,
    plans=[{"id": "plan.rel.mid.v2", "description": "关系中段 v2：责任分配持续变化。",
            "supersedes": ["plan.rel.mid.v1"], "built_from": ["cand-rel-v2"]}],
    allow_simulation=True,
)
check("diff base_state_rev==1", diff_v2["base_state_rev"] == 1)
check("diff writeback append-only", all(c["target"] == "approved_plan" and c["operation"] == "append"
                                         for c in diff_v2["changes"]))
state_rev2 = sp.apply_diff(STATE, diff_v2, decision_a, allow_simulation=True)

# ---------------------------------------------------------------------------
# 九、Activity Projection 验证
# ---------------------------------------------------------------------------
ids_rev2 = [p["id"] for p in state_rev2["approved_plan"]]
check("v1 仍原样保留（append-only history）", "plan.rel.mid.v1" in ids_rev2)
check("v1 条目未被改写", [p for p in state_rev2["approved_plan"] if p["id"] == "plan.rel.mid.v1"]
      == [p for p in STATE["approved_plan"] if p["id"] == "plan.rel.mid.v1"])
check("v2 已新增", "plan.rel.mid.v2" in ids_rev2)
check("无持久 status/active 字段", all("status" not in p and "active" not in p
                                        for p in state_rev2["approved_plan"]))
act2 = sp.resolve_plan_activity(state_rev2)
check("v1 = superseded/inactive", "plan.rel.mid.v1" in act2["superseded"]
      and "plan.rel.mid.v1" not in act2["active"])
check("v1.superseded_by == [v2]", act2["superseded_by"].get("plan.rel.mid.v1") == ["plan.rel.mid.v2"])
check("v2 = active", "plan.rel.mid.v2" in act2["active"])
check("ancestor 保持 active", "plan.book.direction" in act2["active"])
check("sibling 保持 active", "plan.suspense.mid" in act2["active"])
check("LOCAL_REPLAN_ONLY_TARGET_CHANGED", sorted(act2["superseded"]) == ["plan.rel.mid.v1"])

# ---------------------------------------------------------------------------
# 十、Canon 零污染
# ---------------------------------------------------------------------------
check("state_rev 1->2", STATE["state_rev"] == 1 and state_rev2["state_rev"] == 2)
canon_same = all(state_rev2[area] == canon_before[area] for area in CANON_AREAS)
check("CANON_POLLUTION = ZERO", canon_same,
      "canon_facts/character/relationship/occurred/open_threads deep-equal")
check("last_authority_source = simulated decision", state_rev2["last_authority_source"] == decision_a["authority"])

# ---------------------------------------------------------------------------
# 十一、cross-target supersede 必须拒绝（Brief/Decision 基于当前 state_rev2，
#     确保触发的是 supersede guard 而非 stale guard）
# ---------------------------------------------------------------------------
brief_reject, decision_reject = build_rel_chain(state_rev2, "plan-brief-reject", "plan-context-reject",
                                                "decision-reject", "cand-reject")
expect_contract_error("cross-target supersede 拒绝", lambda: sp.make_plan_diff(
    diff_id="diff-cross", state=state_rev2, intent=INTENT, decision=decision_reject, brief=brief_reject,
    plans=[{"id": "plan.rel.mid.v3x", "description": "x", "supersedes": ["plan.suspense.mid"]}],
    allow_simulation=True,
))

# ---------------------------------------------------------------------------
# 十二、missing / dead supersede ref
# ---------------------------------------------------------------------------
expect_contract_error("missing supersede ref 拒绝", lambda: sp.make_plan_diff(
    diff_id="diff-missing", state=state_rev2, intent=INTENT, decision=decision_reject, brief=brief_reject,
    plans=[{"id": "plan.rel.mid.v3y", "description": "x", "supersedes": ["plan.not.exists"]}],
    allow_simulation=True,
))
expect_contract_error("dead base: v3 supersedes v1 拒绝（v1 已 inactive）", lambda: sp.make_plan_diff(
    diff_id="diff-dead", state=state_rev2, intent=INTENT, decision=decision_reject, brief=brief_reject,
    plans=[{"id": "plan.rel.mid.v3z", "description": "x", "supersedes": ["plan.rel.mid.v1"]}],
    allow_simulation=True,
))

# 链式合法路径：v3 supersedes v2
brief_c, decision_c = build_rel_chain(state_rev2, "plan-brief-rel-c", "plan-context-rel-c",
                                      "decision-rel-v3", "cand-rel-v3")
diff_v3 = sp.make_plan_diff(
    diff_id="diff-rel-v3", state=state_rev2, intent=INTENT, decision=decision_c, brief=brief_c,
    plans=[{"id": "plan.rel.mid.v3", "description": "关系中段 v3：链式局部替换。",
            "supersedes": ["plan.rel.mid.v2"]}],
    allow_simulation=True,
)
state_rev3 = sp.apply_diff(state_rev2, diff_v3, decision_c, allow_simulation=True)
act3 = sp.resolve_plan_activity(state_rev3)
check("链 v1→v2→v3：v1/v2 inactive、v3 active",
      sorted(act3["superseded"]) == ["plan.rel.mid.v1", "plan.rel.mid.v2"]
      and "plan.rel.mid.v3" in act3["active"]
      and "plan.rel.mid.v2" not in act3["active"])

# 1→N replacement：两条新 item 同时 supersede v3（基于当前 state_rev3 重编译 Brief）
brief_split, decision_split = build_rel_chain(state_rev3, "plan-brief-split", "plan-context-split",
                                              "decision-split", "cand-split")
diff_split = sp.make_plan_diff(
    diff_id="diff-rel-split", state=state_rev3, intent=INTENT, decision=decision_split, brief=brief_split,
    plans=[
        {"id": "plan.rel.mid.v4a", "description": "拆分上半段。", "supersedes": ["plan.rel.mid.v3"]},
        {"id": "plan.rel.mid.v4b", "description": "拆分下半段。", "supersedes": ["plan.rel.mid.v3"]},
    ],
    allow_simulation=True,
)
state_rev4 = sp.apply_diff(state_rev3, diff_split, decision_split, allow_simulation=True)
act4 = sp.resolve_plan_activity(state_rev4)
check("1→N replacement 成立", act4["superseded_by"].get("plan.rel.mid.v3") == ["plan.rel.mid.v4a", "plan.rel.mid.v4b"]
      and "plan.rel.mid.v4a" in act4["active"] and "plan.rel.mid.v4b" in act4["active"])

# ---------------------------------------------------------------------------
# 十三、stale local Brief 真实场景
# ---------------------------------------------------------------------------
# 1) 在 state_rev=4 编译关系局部 Brief A，并在其尚未写回时建立绑定的 Decision
brief_stale, decision_stale = build_rel_chain(state_rev4, "plan-brief-stale-a", "plan-context-stale-a",
                                              "decision-stale-a", "cand-stale-a")
check("Brief A source_versions.state_rev==4", brief_stale["source_versions"]["state_rev"] == 4)
# 2) 另一条合法 planning append 让 Story State 进入 5（无关 sibling target）
sus_target = {"target_id": "target.suspense.mid", "description": "悬念链补充",
              "scope_kind": "suspense", "scope": "只动悬念链"}
brief_sus = sp.compile_plan_brief(
    project_id="e2c-sandbox", brief_id="plan-brief-suspense-extra",
    author_planning_question="给悬念链补一条推进。",
    planning_target=sus_target, planning_sources=[{"kind": "approved_plan", "ref": "plan.suspense.mid"}],
    intent=INTENT, state=state_rev4,
)
ctx_sus = sp.build_plan_context(context_id="ctx-suspense-extra", brief=brief_sus, intent=INTENT, state=state_rev4)
cand_sus = sp.create_plan_candidate(candidate_id="cand-suspense-extra", brief=brief_sus, context=ctx_sus,
                                    model_output={"proposal": "卷宗流向档案馆。"})
dec_sus = sp.create_decision_record(
    decision_id="decision-suspense-extra", brief=brief_sus, context=ctx_sus, candidate=cand_sus,
    author_action="choose", author_confirmation_ref="author:TEST_ONLY/e2c-simulated-choose",
    final_decision={"note": "SIMULATED_DECISION_ONLY"}, simulation=True,
)
diff_sus = sp.make_plan_diff(
    diff_id="diff-suspense-extra", state=state_rev4, intent=INTENT, decision=dec_sus, brief=brief_sus,
    plans=[{"id": "plan.suspense.mid.extra", "description": "悬念链无关补充。"}],
    allow_simulation=True,
)
state_rev5 = sp.apply_diff(state_rev4, diff_sus, dec_sus, allow_simulation=True)
check("无关 append 推进 state_rev 4->5", state_rev5["state_rev"] == 5)
# 3) 旧 Brief A 写回必须被拒绝（brief.source_versions.state_rev != current state_rev）
expect_contract_error("STALE_REPLAN_BRIEF_REJECTED", lambda: sp.make_plan_diff(
    diff_id="diff-stale-rejected", state=state_rev5, intent=INTENT, decision=decision_stale, brief=brief_stale,
    plans=[{"id": "plan.rel.mid.v5", "description": "x", "supersedes": ["plan.rel.mid.v4a"]}],
    allow_simulation=True,
))
# 4) + 5) 基于 N+1 重编译 Brief B，同一 local replan 意图正常通过
brief_b, decision_b = build_rel_chain(state_rev5, "plan-brief-rel-b", "plan-context-rel-b",
                                      "decision-rel-v5", "cand-rel-v5")
check("Brief B source_versions.state_rev==5", brief_b["source_versions"]["state_rev"] == 5)
diff_v5 = sp.make_plan_diff(
    diff_id="diff-rel-v5", state=state_rev5, intent=INTENT, decision=decision_b, brief=brief_b,
    plans=[{"id": "plan.rel.mid.v5", "description": "重编译后的同一意图。",
            "supersedes": ["plan.rel.mid.v4a", "plan.rel.mid.v4b"]}],
    allow_simulation=True,
)
state_rev6 = sp.apply_diff(state_rev5, diff_v5, decision_b, allow_simulation=True)
act6 = sp.resolve_plan_activity(state_rev6)
check("RECOMPILED_CURRENT_BRIEF_PASS", state_rev6["state_rev"] == 6
      and "plan.rel.mid.v5" in act6["active"]
      and sorted(act6["superseded"]) == ["plan.rel.mid.v1", "plan.rel.mid.v2", "plan.rel.mid.v3",
                                         "plan.rel.mid.v4a", "plan.rel.mid.v4b"])
check("全程 Canon 保持 ZERO pollution", all(state_rev6[area] == canon_before[area] for area in CANON_AREAS))

# ---------------------------------------------------------------------------
# 证据输出
# ---------------------------------------------------------------------------
failed = [r for r in RESULTS if not r["pass"]]
summary = {
    "task": "E2-C-A local replan sandbox",
    "SIMULATED_DECISION_ONLY": True,
    "CANON_POLLUTION": "ZERO" if all(state_rev6[a] == canon_before[a] for a in CANON_AREAS) else "NONZERO",
    "LOCAL_REPLAN_ONLY_TARGET_CHANGED": True,
    "STALE_REPLAN_BRIEF_REJECTED": True,
    "RECOMPILED_CURRENT_BRIEF_PASS": True,
    "checks_total": len(RESULTS),
    "checks_failed": len(failed),
    "final_activity": act6,
    "approved_plan_ids_final": [p["id"] for p in state_rev6["approved_plan"]],
}
(HERE / "e2c_sandbox_result.json").write_text(
    json.dumps({"summary": summary, "checks": RESULTS}, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
if failed:
    print("SANDBOX FAILED:", [r["check"] for r in failed])
    sys.exit(1)
print("E2C_SANDBOX_OK")
