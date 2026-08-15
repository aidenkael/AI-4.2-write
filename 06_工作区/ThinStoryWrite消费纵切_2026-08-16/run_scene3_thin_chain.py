"""THIN_STORYWRITE_CONSUMER_SLICE disposable chain runner (2026-08-16).

Runs the FULL scene-3 preparation chain through the thin StoryWrite entry
(storywrite_entry.py) instead of hand-assembling files:

    P0  apply_settlement(scene2 W1 settlement, mode="shadow")
        -> shadow_story_state_rev4.json  (+ settlement_report.json)
    P1  prepare_creation_brief(...)       -> creation_brief.json
    P2  prepare_recent_prose_window(...)  -> recent_prose_window.json
    P1  prepare_context(..., SELECTIONS)  -> context_package.json

Everything stays shadow / test-only: no production writeback, no
accepted_text:, no author acceptance claimed.  The previous scene's W1 is a
FROZEN EXPERIMENT DRAFT; this script only derives non-authoritative artifacts
from it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
SKILL_DIR = HERE.parents[2] / "05_Skills与自动化" / "01_Skills" / "StoryWrite"
PREV_DIR = HERE.parents[1] / "LongformContinuity真实纵切_2026-08-16"
E2B_DIR = HERE.parents[1] / "E2B_StoryPlan真实纵切_2026-08-15"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from storywrite_entry import (  # noqa: E402
    apply_settlement,
    prepare_context,
    prepare_creation_brief,
    prepare_recent_prose_window,
)


def retrieval_must_not_be_called(query):
    raise AssertionError("无 knowledge need 时不得调用 KnowledgeRetrieve")


# Model semantic judgment, recorded in settlement_candidate.md.
SETTLEMENT = {
    "scene_ref": "scene2-W1-frozen",
    "candidates": [
        {"classification": "mechanical", "target_area": "occurred_events", "operation": "append",
         "entry": {"id": "event.w2.zhou-decision",
                   "description": "周昌顺当众决定：他的大宗下个月起走海路拼线；宋乔的重算可以算，模型里有他这一份。"},
         "reason": "正文明确成立的话语动作：'我的大宗，下个月起走海路，拼线'。"},
        {"classification": "mechanical", "target_area": "occurred_events", "operation": "append",
         "entry": {"id": "event.w2.three-party-condition",
                   "description": "周昌顺为走海路开出条件：岛上末梢、进岛的货由宋宁的站接，价格按明价写进合同，三方都签、缺一不行。"},
         "reason": "正文明确开出的条件原话，本场第三场答复的直接对象。"},
        {"classification": "mechanical", "target_area": "occurred_events", "operation": "append",
         "entry": {"id": "event.w2.songning-three-day",
                   "description": "宋宁当众承诺：末梢的价格她要算，三天以内给周昌顺话。"},
         "reason": "正文明确承诺：'三天以内给你话'。"},
        {"classification": "mechanical", "target_area": "occurred_events", "operation": "append",
         "entry": {"id": "event.w2.songqiao-framework",
                   "description": "宋乔承诺：末梢计价和账期的框架明天中午以前送到站里，并陪宋宁对数字。"},
         "reason": "正文明确承诺：'末梢计价和账期，我明天中午以前给框架'。"},
        {"classification": "mechanical", "target_area": "occurred_events", "operation": "append",
         "entry": {"id": "event.w2.zheng-month-end",
                   "description": "郑国栋接受'大宗跟着拼、末梢给宋宁'的安排，月底等价格与准话，并表示两人的准话他都记着。"},
         "reason": "正文明确表态：'行。我月底等你们的价'。"},
        {"classification": "mechanical", "target_area": "occurred_events", "operation": "append",
         "entry": {"id": "event.w2.xiulan-stocktake",
                   "description": "秀兰来消息：下礼拜店里盘点，两天的货都交宋宁；宋宁答复排得开。"},
         "reason": "正文结尾明确往来消息，合作机器日常运转的存量事实。"},
        {"classification": "mechanical", "target_area": "open_threads", "operation": "replace_existing",
         "entry": {"id": "thread.zhou.thursday-decision",
                   "description": "已兑现：周昌顺礼拜四已当众给出决定（见 event.w2.zhou-decision 与 event.w2.three-party-condition），该线不再悬置。"},
         "reason": "该线程在第二场正文中已明确兑现，更新为已兑现状态。"},
        {"classification": "mechanical", "target_area": "open_threads", "operation": "append",
         "entry": {"id": "thread.songning.three-day-answer",
                   "description": "宋宁须在三日内算完末梢账并给周昌顺与宋乔准话（接或不接）。"},
         "reason": "第三场必须兑现的线，来自两处明确期限原话。"},
        {"classification": "mechanical", "target_area": "open_threads", "operation": "append",
         "entry": {"id": "thread.contract.three-party",
                   "description": "三方末梢合同待成立：明价条款、三方签署缺一不行；未签前末梢安排不生效。"},
         "reason": "周昌顺条件原话产生的待成立合同线。"},
        {"classification": "mechanical", "target_area": "open_threads", "operation": "replace_existing",
         "entry": {"id": "thread.zheng.month-end",
                   "description": "月底前郑国栋等的是末梢价格与双方准话（指向 thread.songning.three-day-answer 与 thread.contract.three-party）。"},
         "reason": "第二场把月底期限的对象更新为'你们的价'。"},
        # --- ambiguous / creative: recorded here so the thin layer's gate
        # --- visibly rejects them; they never enter State.
        {"classification": "ambiguous", "target_area": "character_state",
         "entry": {"id": "char.zhou.stance-leans-songning"},
         "reason": "B1：'欠情分'的立场含义是解释，正文未定性。"},
        {"classification": "ambiguous", "target_area": "character_state",
         "entry": {"id": "char.songqiao.money-view"},
         "reason": "B2：'钱没有名字'的动机推断归属 open space（隐藏私人目的）。"},
        {"classification": "ambiguous", "target_area": "character_state",
         "entry": {"id": "char.songning.belief-reinforced"},
         "reason": "B3：belief 条目早已在 State；本场仅再触碰，无新事实。"},
        {"classification": "ambiguous", "target_area": "occurred_events",
         "entry": {"id": "event.w2.signing-conflict-prophecy"},
         "reason": "B4：格言式台词的预言性含义不得预写。"},
        {"classification": "ambiguous", "target_area": "canon_facts",
         "entry": {"id": "canon.w2.framework-favors-songning"},
         "reason": "B5：数字优劣的动机解释直接触碰 open space 3，拒收。"},
        {"classification": "creative", "target_area": "occurred_events",
         "entry": {"id": "event.w3.songning-answer"},
         "reason": "C1：宋宁接或不接是第三场的创作内容，提前结算即偷写未来场景。"},
        {"classification": "creative", "target_area": "canon_facts",
         "entry": {"id": "canon.debt-linked-to-songqiao"},
         "reason": "C2：旧债与宋乔的因果关联属作者重大方向决定。"},
    ],
}

# Model semantic selection for scene 3 (see context_selection.md): only what
# this scene truly needs.  State has grown to 28 items; selection must still
# really reduce.
SELECTIONS = [
    {"area": "canon_facts", "id": "canon.seed.road",
     "reason": "四个月倒计时是末梢账所有数字的时间边界"},
    {"area": "canon_facts", "id": "canon.seed.debt",
     "reason": "旧债只以信用/融资后果在场：宋宁垫资能力受限是本场的真实成本项"},
    {"area": "canon_facts", "id": "canon.w1.thirdparties",
     "reason": "秀兰盘点单与郑国栋月底都在本场运转"},
    {"area": "canon_facts", "id": "canon.w1.hailu",
     "reason": "宋乔框架（统一定价/账期/急单计价）是末梢对价的直接输入"},
    {"area": "relationship_state", "id": "rel.state.sisters",
     "reason": "本场必须继续兑现：合作更必要与冲突更明显同时发生"},
    {"area": "character_state", "id": "char.state.songning.belief",
     "reason": "连续两次第一稿缺席的条目，本场创作约束要求正面触碰"},
    {"area": "occurred_events", "id": "event.w2.three-party-condition",
     "reason": "本场答复的直接对象：三方末梢条件的原文"},
    {"area": "occurred_events", "id": "event.w2.songning-three-day",
     "reason": "三天期限的出处，本场必须兑现"},
    {"area": "occurred_events", "id": "event.w2.songqiao-framework",
     "reason": "宋乔框架中午送达是本场的第一个动作"},
    {"area": "occurred_events", "id": "event.w2.zheng-month-end",
     "reason": "月底外部时钟：宋宁的答复必须给郑国栋一个取向"},
    {"area": "open_threads", "id": "thread.songning.three-day-answer",
     "reason": "本场必须收口的线"},
    {"area": "open_threads", "id": "thread.contract.three-party",
     "reason": "答复之后合同的成立条件仍在前面，结尾必须保持开放"},
    {"area": "open_threads", "id": "thread.zheng.month-end",
     "reason": "月底期限本场不收，只被答复推进"},
    {"area": "approved_plan", "id": "plan.design.direction.island",
     "reason": "作者确认方向：每解决一个现实问题，合作更必要、冲突更明显；旧债进现实但不揭真相"},
]


def _dump(name: str, payload) -> Path:
    out = HERE.parent / name
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def main() -> None:
    # ---- inputs (read-only) -------------------------------------------------
    intent = json.loads((E2B_DIR / "author_intent.json").read_text(encoding="utf-8"))
    state_rev3 = json.loads((PREV_DIR / "shadow_story_state.json").read_text(encoding="utf-8"))
    scene2_w1 = (PREV_DIR / "scene2_W1.md").read_text(encoding="utf-8")
    # recent prose source: only the W1 full prose section, cut at its tail.
    prose = scene2_w1.split("## W1 全文", 1)[1].split("\n---", 1)[0]

    # ---- P0 settlement assist (shadow mode; no acceptance possible) --------
    report = apply_settlement(
        state=state_rev3,
        settlement=SETTLEMENT,
        mode="shadow",
        shadow_authority="manual_import:experiment_shadow_from_W2",
    )
    state_rev4 = report["new_state"]
    # Carry the sandbox metadata forward; the thin layer never invents it.
    state_rev4["shadow_metadata"] = dict(state_rev3["shadow_metadata"])
    state_rev4["shadow_metadata"]["source_scene"] = (
        "06_工作区/LongformContinuity真实纵切_2026-08-16/scene2_W1.md (FROZEN EXPERIMENT DRAFT)"
    )
    _dump("shadow_story_state_rev4.json", state_rev4)
    _dump("settlement_report.json", report)

    # ---- P1 brief preparation (frozen E1 contract, no parallel schema) -----
    brief = prepare_creation_brief(
        project_id=state_rev4["project_id"],
        brief_id="longform-brief-003",
        author_input="写第三场：宋宁在三天期限内算完末梢账，并给出是否接受三方末梢条件的答复。",
        intent=intent,
        state=state_rev4,
        semantic_interpretation={
            "scope": "scene_writing",
            "objective": "宋宁算完末梢账并给出答复；她第一次成为把条件摆上桌面的人",
            "focal_entities": ["宋宁", "宋乔", "周昌顺", "郑国栋"],
            "inherited_obligations": [
                "五项 open space 保持开放",
                "三天期限内给出答复",
                "月底期限被推进但不收口",
            ],
            "knowledge_needs": [],  # BKP_POSTHOC_SPARSE_PROBLEM_DRIVEN
        },
    )
    _dump("creation_brief.json", brief)

    # ---- P2 recent prose window (simple tail window, non-authoritative) ----
    window = prepare_recent_prose_window(prose_text=prose, scene_ref="scene2-W1-frozen")
    _dump("recent_prose_window.json", window)

    # ---- P1 context preparation (frozen E3-A compiler, explicit selection) -
    ctx = prepare_context(
        context_id="longform-ctx-003",
        brief=brief,
        intent=intent,
        state=state_rev4,
        state_selections=SELECTIONS,
        retrieval=retrieval_must_not_be_called,
        allow_simulation_sources=True,  # TEST_ONLY: shadow state carries E2-B simulated P0 planning
    )
    ctx["experiment_note"] = (
        "THIN_STORYWRITE_CONSUMER_SLICE 一次性实验 Context：基于 simulation_only shadow state rev4"
        "（scene2 W1 为 FROZEN EXPERIMENT DRAFT，未获作者 acceptance）；本 Context 由薄层"
        "prepare_context 编译（复用冻结 E3-A，零新 Schema）；Context Package 非权威，"
        "永不写回 Canon / Story State。"
    )
    _dump("context_package.json", ctx)

    size = ctx["size_summary"]
    print(json.dumps(
        {
            "settlement": {
                "mode": report["mode"],
                "authority": report["authority"],
                "base_state_rev": report["base_state_rev"],
                "new_state_rev": report["new_state_rev"],
                "applied": len(report["applied"]),
                "not_writable": len(report["not_writable"]),
                "not_writable_classifications": sorted({n["classification"] for n in report["not_writable"]}),
            },
            "brief": {"brief_id": brief["brief_id"], "source_versions": brief["source_versions"]},
            "recent_prose": {
                "window_chars": window["window_chars"],
                "truncated_from_tail": window["truncated_from_tail"],
                "below_target": window["below_target"],
                "is_authority": window["is_authority"],
            },
            "context": {
                "status": ctx["status"],
                "total_state_items": size["total_state_items"],
                "selected_state_items": size["selected_state_items"],
                "selection_ratio": round(size["selected_state_items"] / size["total_state_items"], 3),
                "selected_bkp_hits": size["selected_bkp_hits"],
                "retrieval_status": ctx["retrieval"]["status"],
            },
        },
        ensure_ascii=False, indent=2,
    ))


if __name__ == "__main__":
    main()
