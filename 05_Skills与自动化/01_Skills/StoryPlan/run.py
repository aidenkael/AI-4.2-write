"""CLI for the disposable E2-A StoryPlan demonstration.

Demo only proves the contract runs: confirmed StoryDesign -> Plan Brief ->
first-round noncanonical plan candidate with 0 BKP.  No author confirmation,
no Canon write, no full-book outline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from story_plan import ContractError, initialize_project, run_story_plan, write_json


DEMO_INTENT = {
    "project_id": "demo-crossroad-lovers",
    "intent_rev": 1,
    "work_direction": "都市悬疑长篇：两位主角从各自隐瞒走向正面对抗。",
    "reader_promise": "读者先相信两人同盟，再逐步发现他们目标互斥。",
    "hard_constraints": ["不把候选谜底写成既成事实", "不提前确认最终反派"],
    "open_space": ["对抗的公开方式", "关系归宿"],
}

# StoryDesign 已确认方向（disposable 模拟）：一条 approved_plan 条目，
# authority 来自作者 Decision，occurred=False。
DEMO_STATE = {
    "project_id": "demo-crossroad-lovers",
    "state_rev": 1,
    "sandbox_only": True,
    "canon_facts": [{"id": "canon.seed", "fact": "两人在同一桩旧案中分别失去过重要的人。", "authority": "manual_import:demo_seed"}],
    "character_state": [], "relationship_state": [], "occurred_events": [], "open_threads": [],
    "approved_plan": [
        {
            "id": "plan.design.engine",
            "description": "故事发动机：男女主因旧案结成临时同盟，各自隐瞒关键信息。",
            "target_ref": "design.engine",
            "authority": "author_decision:simulated-storydesign-demo",
            "occurred": False,
        }
    ],
}


def create_demo(output: Path) -> dict:
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ContractError(f"demo 目录已存在且非空，拒绝覆盖；请换一个空目录：{output}")
    paths = initialize_project(output)
    write_json(paths["intent"], DEMO_INTENT)
    write_json(paths["state"], DEMO_STATE)
    return run_story_plan(
        project_dir=output,
        author_planning_question="先规划这个故事前半程，我主要担心男女主太晚才真正站到对立面。",
        planning_target={
            "target_id": "target.front-half",
            "description": "故事前半程推进",
            "scope_kind": "free",
            "scope": "约全书前半程（不固定章数）",
        },
        planning_sources=[{"kind": "approved_plan", "ref": "plan.design.engine"}],
        brief_id="plan-brief-001", context_id="plan-context-001", candidate_id="plan-001",
        semantic_interpretation={
            "knowledge_needs": [],
            "selected_knowledge_refs": [],
            "deliberate_open_space": ["对抗公开的具体方式", "谁先掌握对方秘密", "关系归宿"],
            "assumptions": ["前半程的具体事件顺序尚未获得作者确认。"],
        },
        model_output={
            "stance": ["structure"],
            "proposal": "候选：前半程让同盟在三次共同行动中各进一步，同时让两人隐瞒的信息在第三次行动后互相咬合，使对立成为不可避免而非外部强加。",
            "open_choices": ["对立公开于私下还是公开场合", "是否有一方先坦白"],
            "note": "第一轮 noncanonical 规划候选；0 张 BKP 是正常路径；不是 Canon，不自动确认。",
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo-dir", type=Path, required=True, help="disposable sandbox output directory")
    args = parser.parse_args()
    try:
        result = create_demo(args.demo_dir)
    except ContractError as exc:
        print(f"demo 拒绝运行：{exc}", file=sys.stderr)
        raise SystemExit(2)
    print(f"demo created: {args.demo_dir}")
    print(f"retrieval status: {result['context']['retrieval']['status']}")
    print(f"selected knowledge hits: {len(result['context']['selected_knowledge_hits'])}")
    print(f"plan candidate status: {result['candidate']['status']}")
    print("author decision required before any planning enters approved_plan")


if __name__ == "__main__":
    main()
