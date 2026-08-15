"""STORYWRITE disposable context compilation (2026-08-15).

Reads the frozen E2-B experiment artifacts, applies the model's semantic state
selection (see context_selection.md) and emits the Context Package used to
write the sisters' first public negotiation scene.

This validator never touches Canon / Story State; it only reads and compiles.
allow_simulation_sources=True is the explicit TEST_ONLY gate required because
this experiment reuses E2-B's simulated P0 planning entry; it does not loosen
production planning authority.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
SKILL_DIR = HERE.parents[2] / "05_Skills与自动化" / "01_Skills" / "ContextCompiler"
E2B_DIR = HERE.parents[1] / "E2B_StoryPlan真实纵切_2026-08-15"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from context_compiler import compile_context, resolve_plan_activity  # noqa: E402


def retrieval_must_not_be_called(query):
    raise AssertionError("无 knowledge need 时不得调用 KnowledgeRetrieve")


SELECTIONS = [
    {"area": "canon_facts", "id": "canon.seed.road",
     "reason": "旧路关闭倒计时是本场谈判的直接压力源"},
    {"area": "canon_facts", "id": "canon.seed.songning",
     "reason": "物流站是宋宁要保住的谈判标的，也是宋乔方案要重新定位的对象"},
    {"area": "canon_facts", "id": "canon.seed.songqiao",
     "reason": "宋乔代表区域公司竞标大宗配送合同，是对立方方案的事实基础"},
    {"area": "canon_facts", "id": "canon.seed.debt",
     "reason": "旧债以融资难/现金紧的后果进入本场景，是责任观分歧的载体"},
    {"area": "character_state", "id": "char.state.songning.belief",
     "reason": "宋宁认定姐姐离开与债有关，支配她的防御与潜台词"},
    {"area": "character_state", "id": "char.state.songqiao.stance",
     "reason": "宋乔坚持物流站没有继续存在的价值，是宋宁公开反驳的直接对象"},
    {"area": "relationship_state", "id": "rel.state.sisters",
     "reason": "不得不合作又利益互斥的关系轴正是本场景要完成性质变化的对象"},
    {"area": "approved_plan", "id": "plan.design.direction.island",
     "reason": "作者确认方向：合作更必要与利益冲突更明显必须同时兑现，旧债进入现实选择但真相不揭"},
    {"area": "approved_plan", "id": "plan.e2b.simulated.first-half",
     "reason": "本场景是 P0 前半程终点场景，planning obligation 直接来自它（TEST_ONLY simulation gate）"},
]


def main() -> None:
    intent = json.loads((E2B_DIR / "author_intent.json").read_text(encoding="utf-8"))
    state = json.loads((E2B_DIR / "story_state_after_simulated_writeback.json").read_text(encoding="utf-8"))
    brief = json.loads((HERE.parent / "creation_brief.json").read_text(encoding="utf-8"))

    ctx = compile_context(
        context_id="storywrite-ctx-001",
        brief=brief,
        intent=intent,
        state=state,
        state_selections=SELECTIONS,
        retrieval=retrieval_must_not_be_called,
        allow_simulation_sources=True,  # TEST_ONLY gate: reuse of E2-B simulated P0 planning
    )
    activity = resolve_plan_activity(state)

    ctx["experiment_note"] = (
        "一次性实验 Context：复用 E2-B 模拟工件，allow_simulation_sources=True 仅 TEST_ONLY；"
        "Context Package 非权威，永不写回 Canon / Story State。"
    )
    ctx["approved_plan_activity_snapshot"] = activity

    out = HERE.parent / "context_package.json"
    out.write_text(json.dumps(ctx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(
        {
            "status": ctx["status"],
            "size_summary": ctx["size_summary"],
            "selected_refs": [r["source_ref"] for r in ctx["selection_reason"]],
            "active_planning": activity["active"],
            "selected_bkp_hits": len(ctx["selected_bkp_hits"]),
            "retrieval_status": ctx["retrieval"]["status"],
        },
        ensure_ascii=False, indent=2,
    ))


if __name__ == "__main__":
    main()
