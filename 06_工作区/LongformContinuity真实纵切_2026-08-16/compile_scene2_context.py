"""LONGFORM_CONTINUITY disposable context compilation (2026-08-16).

Compiles the second-round Context for scene 2 ("周昌顺礼拜四的账") from:

- the frozen E2-B Author Intent (intent_rev=1);
- shadow_story_state.json (state_rev=3, simulation_only continuity sandbox,
  mechanical settlement from the FROZEN EXPERIMENT DRAFT W1);
- the model's semantic selection (see context_selection.md).

This script never touches production Canon / Story State; it only reads and
compiles.  allow_simulation_sources=True is the explicit TEST_ONLY gate
required because the shadow state still carries E2-B's simulated P0 planning
entry; it does not loosen production planning authority.
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
     "reason": "四个月后旧路关闭，是周昌顺必须此刻算账的时间压力源"},
    {"area": "canon_facts", "id": "canon.seed.debt",
     "reason": "旧债以融资/押金后果进入本场：周昌顺的账会算到宋宁的信用"},
    {"area": "canon_facts", "id": "canon.w1.thirdparties",
     "reason": "周昌顺、郑国栋的身份与利益是本场的直接素材"},
    {"area": "relationship_state", "id": "rel.state.sisters",
     "reason": "本场要继续推动的关系轴：合作更必要与冲突更明显必须同时兑现"},
    {"area": "character_state", "id": "char.state.songning.belief",
     "reason": "宋宁面对姐姐方案赢的结果时，旧判断会作为潜台词在场"},
    {"area": "occurred_events", "id": "event.w1.public-admission",
     "reason": "冲突已公开化的既定事实：本场不得退回'大家还没说开'，联运照旧是合作机器存量"},
    {"area": "occurred_events", "id": "event.w1.recalc-commitment",
     "reason": "宋乔的重算承诺以本场结果为触发条件，是她本场动作的依据"},
    {"area": "occurred_events", "id": "event.w1.zhou-takeaway",
     "reason": "本场直接前情：两份方案都被周昌顺带走，他欠岛上所有人一个账"},
    {"area": "occurred_events", "id": "event.w1.zheng-deadline",
     "reason": "郑国栋月底期限与'礼拜四来听账'都在本场兑现"},
    {"area": "open_threads", "id": "thread.zhou.thursday-decision",
     "reason": "本场必须兑现的线：周昌顺的货量决定"},
    {"area": "open_threads", "id": "thread.zheng.month-end",
     "reason": "未收线的外部时钟，决定本场结尾把压力交给谁"},
    {"area": "approved_plan", "id": "plan.design.direction.island",
     "reason": "作者确认方向：每解决一个现实问题，合作更必要、冲突更明显；旧债进现实但不揭真相"},
    {"area": "approved_plan", "id": "plan.e2b.simulated.first-half",
     "reason": "P0 前半程规划义务来源（TEST_ONLY simulation gate）"},
]


def main() -> None:
    intent = json.loads((E2B_DIR / "author_intent.json").read_text(encoding="utf-8"))
    state = json.loads((HERE.parent / "shadow_story_state.json").read_text(encoding="utf-8"))
    brief = json.loads((HERE.parent / "creation_brief.json").read_text(encoding="utf-8"))

    ctx = compile_context(
        context_id="longform-ctx-002",
        brief=brief,
        intent=intent,
        state=state,
        state_selections=SELECTIONS,
        retrieval=retrieval_must_not_be_called,
        allow_simulation_sources=True,  # TEST_ONLY gate: shadow state carries E2-B simulated P0 planning
    )
    activity = resolve_plan_activity(state)

    ctx["experiment_note"] = (
        "一次性实验 Context：基于 simulation_only shadow state（W1 为 FROZEN EXPERIMENT DRAFT，"
        "未获作者 acceptance）；allow_simulation_sources=True 仅 TEST_ONLY；"
        "Context Package 非权威，永不写回 Canon / Story State。"
    )
    ctx["approved_plan_activity_snapshot"] = activity

    out = HERE.parent / "context_package.json"
    out.write_text(json.dumps(ctx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    size = ctx["size_summary"]
    print(json.dumps(
        {
            "status": ctx["status"],
            "size_summary": size,
            "selection_ratio": f"{size['selected_state_items']}/{size['total_state_items']}",
            "selected_refs": [r["source_ref"] for r in ctx["selection_reason"]],
            "active_planning": activity["active"],
            "selected_bkp_hits": len(ctx["selected_bkp_hits"]),
            "retrieval_status": ctx["retrieval"]["status"],
        },
        ensure_ascii=False, indent=2,
    ))


if __name__ == "__main__":
    main()
