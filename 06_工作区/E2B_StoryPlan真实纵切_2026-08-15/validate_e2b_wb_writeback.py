"""E2-B-WB｜StoryPlan simulated Decision / Writeback 机械验证脚本.

只调用 StoryPlan 正式公开函数（create_plan_candidate / create_decision_record
/ make_plan_diff / apply_diff），在内存副本上验证权限与 Canon 隔离。
不修改任何冻结工件，不写 runtime。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path

E2B_DIR = Path(__file__).resolve().parent
STORY_PLAN_PY = Path(__file__).resolve().parents[2] / "05_Skills与自动化" / "01_Skills" / "StoryPlan" / "story_plan.py"

_spec = importlib.util.spec_from_file_location("e2b_story_plan_skill", STORY_PLAN_PY)
assert _spec and _spec.loader, "无法定位 StoryPlan story_plan.py"
sp = importlib.util.module_from_spec(_spec)
sys.modules["e2b_story_plan_skill"] = sp
_spec.loader.exec_module(sp)

# ---------------------------------------------------------------------------
# 冻结输入（只读，不改写）
# ---------------------------------------------------------------------------
intent = json.loads((E2B_DIR / "author_intent.json").read_text(encoding="utf-8"))
state = json.loads((E2B_DIR / "story_state.json").read_text(encoding="utf-8"))
brief = json.loads((E2B_DIR / "plan_brief.json").read_text(encoding="utf-8"))
context = json.loads((E2B_DIR / "context_package.json").read_text(encoding="utf-8"))
p0_text = (E2B_DIR / "P0_FREE_PLAN.md").read_text(encoding="utf-8")

assert intent["intent_rev"] == 1, "Intent 必须为 rev1"
assert state["state_rev"] == 1, "State 必须为 rev1"
assert f"{brief['brief_id']}@{brief['brief_rev']}" == "plan-brief-001@1", "Brief 必须为 plan-brief-001@1"
assert context["context_id"] == "plan-context-001", "Context 必须为 plan-context-001"

results: dict[str, object] = {}
asserts: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    asserts.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# 三、noncanonical P0 Candidate
# ---------------------------------------------------------------------------
candidate = sp.create_plan_candidate(
    candidate_id="plan-candidate-e2b-p0",
    brief=brief,
    context=context,
    model_output={"format": "markdown", "artifact_ref": "P0_FREE_PLAN.md", "text": p0_text},
)
(E2B_DIR / "p0_candidate.json").write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
check("candidate.artifact_type", candidate["artifact_type"] == "story_plan_candidate", candidate["artifact_type"])
check("candidate.status", candidate["status"] == "proposal_noncanonical", candidate["status"])
check("candidate.authority", candidate["authority"] == "ai_candidate:noncanonical", candidate["authority"])
check("candidate.must_not_write_canon", candidate["must_not_write_canon"] is True, str(candidate["must_not_write_canon"]))
check("candidate.model_output 完整 P0", candidate["content"]["artifact_ref"] == "P0_FREE_PLAN.md"
      and candidate["content"]["text"] == p0_text, f"text {len(candidate['content']['text'])} chars")

# ---------------------------------------------------------------------------
# 四、simulated Decision
# ---------------------------------------------------------------------------
decision = sp.create_decision_record(
    decision_id="decision-e2b-simulated-p0",
    brief=brief,
    context=context,
    candidate=candidate,
    author_action="choose",
    author_confirmation_ref="author:TEST_ONLY/e2b-simulated-p0",
    final_decision={"selected_candidate": "plan-candidate-e2b-p0", "note": "SIMULATED_DECISION_ONLY"},
    simulation=True,
)
(E2B_DIR / "simulated_decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
check("decision.status", decision["status"] == "simulated_confirmed_for_test", decision["status"])
check("decision.authority", decision["authority"] == "simulation_author_decision:decision-e2b-simulated-p0", decision["authority"])
check("decision.simulation_only", decision["simulation_only"] is True, str(decision["simulation_only"]))
check("decision.brief_ref", decision["brief_ref"] == "plan-brief-001@1", decision["brief_ref"])
check("decision 非真实 author_decision", not decision["authority"].startswith("author_decision:"), decision["authority"])

# ---------------------------------------------------------------------------
# 五、Planning Diff
# ---------------------------------------------------------------------------
diff = sp.make_plan_diff(
    diff_id="diff-e2b-simulated-p0",
    state=state,
    intent=intent,
    decision=decision,
    brief=brief,
    plans=[
        {
            "id": "plan.e2b.simulated.first-half",
            "description": "E2-B simulated writeback：P0 前半程规划，仅用于权限与 Canon 隔离验证。",
            "built_from": ["plan-candidate-e2b-p0"],
            "supersedes": [],
        }
    ],
    allow_simulation=True,
)
(E2B_DIR / "simulated_plan_diff.json").write_text(json.dumps(diff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
check("diff.base_state_rev", diff["base_state_rev"] == 1, str(diff["base_state_rev"]))
check("diff.writeback_class", diff["writeback_class"] == "creative_change", diff["writeback_class"])
check("diff.target 只有 approved_plan", all(c["target"] == "approved_plan" for c in diff["changes"]),
      str([c["target"] for c in diff["changes"]]))
check("diff.operation 只有 append", all(c["operation"] == "append" for c in diff["changes"]),
      str([c["operation"] for c in diff["changes"]]))
check("diff 仅 1 条 planning", len(diff["changes"]) == 1, str(len(diff["changes"])))
check("diff.plan_target_ref", diff.get("plan_target_ref") == "pt.first-half.unilateral-harm", diff.get("plan_target_ref"))
check("diff.plan.id 不冲突", diff["changes"][0]["value"]["id"] == "plan.e2b.simulated.first-half"
      and diff["changes"][0]["value"]["id"] not in {p["id"] for p in state["approved_plan"]},
      diff["changes"][0]["value"]["id"])
check("diff.plan.occurred 强制 false", diff["changes"][0]["value"].get("occurred") is False,
      str(diff["changes"][0]["value"].get("occurred")))

# ---------------------------------------------------------------------------
# 六、apply_diff 到内存副本
# ---------------------------------------------------------------------------
new_state = sp.apply_diff(state, diff, decision, allow_simulation=True)
(E2B_DIR / "story_state_after_simulated_writeback.json").write_text(
    json.dumps(new_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# ---------------------------------------------------------------------------
# 七、逐项机械断言
# ---------------------------------------------------------------------------
check("原 state_rev == 1", state["state_rev"] == 1, str(state["state_rev"]))
check("新 state_rev == 2", new_state["state_rev"] == 2, str(new_state["state_rev"]))

for area in ("canon_facts", "character_state", "relationship_state", "occurred_events", "open_threads"):
    check(f"{area} 完全不变", new_state[area] == state[area], f"{len(state[area])} -> {len(new_state[area])} 条")

old_plan_by_id = {p["id"]: p for p in state["approved_plan"]}
new_plan_by_id = {p["id"]: p for p in new_state["approved_plan"]}
check("approved_plan 只新增 1 条", len(new_state["approved_plan"]) == len(state["approved_plan"]) + 1,
      f"{len(state['approved_plan'])} -> {len(new_state['approved_plan'])}")
check("原 approved_plan 条目仍存在且未改变",
      old_plan_by_id["plan.design.direction.island"] == new_plan_by_id["plan.design.direction.island"],
      "plan.design.direction.island")

new_item = new_plan_by_id["plan.e2b.simulated.first-half"]
check("新 planning id 唯一", len(new_plan_by_id) == len(new_state["approved_plan"]), new_item["id"])
check("新 planning occurred == false", new_item["occurred"] is False, str(new_item["occurred"]))
check("新 planning target_ref", new_item["target_ref"] == "pt.first-half.unilateral-harm", new_item["target_ref"])
check("新 planning authority == simulated Decision authority",
      new_item["authority"] == "simulation_author_decision:decision-e2b-simulated-p0", new_item["authority"])
check("last_authority_source 正确", new_state.get("last_authority_source") == diff["source_ref"],
      str(new_state.get("last_authority_source")))
check("Decision.brief_ref == plan-brief-001@1", decision["brief_ref"] == "plan-brief-001@1", decision["brief_ref"])
check("Diff.base_state_rev == 1", diff["base_state_rev"] == 1, str(diff["base_state_rev"]))
check("Intent/State/Brief revision guard 通过", True, "make_plan_diff 未抛 ContractError（intent_rev=1/state_rev=1 匹配）")

# ---------------------------------------------------------------------------
# 八、Canon 零污染检查
#   canon 区域与 State rev1 深度全等是核心证据；关键词扫描只针对"新 state 相对
#   旧 state 新增的 canon 内容"（避免把冻结 seed 本就存在的词误报为污染）。
# ---------------------------------------------------------------------------
canon_areas = ("canon_facts", "character_state", "relationship_state", "occurred_events", "open_threads")
canon_same = all(new_state[a] == state[a] for a in canon_areas)
old_canon_dump = json.dumps({a: state[a] for a in canon_areas}, ensure_ascii=False, sort_keys=True)
new_canon_dump = json.dumps({a: new_state[a] for a in canon_areas}, ensure_ascii=False, sort_keys=True)
future_terms = ["共同保量", "保量", "利益冲突", "联运", "谈判", "竞标", "分拨", "询价"]
polluted_terms = []
if not canon_same:
    # canon 区域发生任何变化：扫描新增文本是否含 P0 未来规划词
    new_serialized = json.dumps(new_state[a] for a in canon_areas)
    polluted_terms = [t for t in future_terms if t in new_serialized]
canon_zero = canon_same and not polluted_terms
check("CANON_POLLUTION == ZERO", canon_zero,
      "canon 区域与 State rev1 完全一致（新增内容为零）" if canon_zero
      else f"canon 区域发生变化，发现污染词: {polluted_terms}")

# 断言汇总
failed = [name for name, ok, _ in asserts if not ok]
results["assert_total"] = len(asserts)
results["assert_failed"] = failed
results["CANON_POLLUTION"] = "ZERO" if canon_zero else "NONZERO"
results["SIMULATED_DECISION_ONLY"] = True

(E2B_DIR / "e2b_wb_assertions.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print("=" * 60)
print(f"ASSERT_TOTAL={len(asserts)} ASSERT_FAILED={len(failed)}")
if failed:
    print("FAILED:", failed)
    sys.exit(1)
print("CANON_POLLUTION=ZERO")
print("SIMULATED_DECISION_ONLY")
sys.exit(0)
