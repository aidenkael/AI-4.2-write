"""CLI for the disposable E1-A StoryDesign demonstration."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from story_design import run_story_design
from story_runtime import ContractError, initialize_project, write_json


DEMO_INTENT = {
    "project_id": "demo-rain-garden",
    "intent_rev": 1,
    "work_direction": "都市奇幻长篇的开端设计。",
    "reader_promise": "读者先感到日常秩序被一条私人秘密撬开。",
    "current_priority": ["人物选择", "秘密的信息层次"],
    "current_focus": "只设计故事发动机，不写正文。",
    "hard_constraints": ["不把候选谜底写成既成事实", "不开篇解释全部世界规则"],
    "avoidances": ["把参考书经验当模板"],
    "open_space": ["秘密来源", "关系走向", "世界机制细节"],
}

DEMO_STATE = {
    "project_id": "demo-rain-garden",
    "state_rev": 1,
    "sandbox_only": True,
    "canon_facts": [{"id": "canon.garden", "fact": "旧城区有一座只在暴雨夜开放的公共花园。", "authority": "manual_import:demo_seed"}],
    "character_state": [], "relationship_state": [], "occurred_events": [], "open_threads": [], "approved_plan": [],
}


def create_demo(output: Path) -> dict:
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ContractError(f"demo 目录已存在且非空，拒绝覆盖；请换一个空目录：{output}")
    paths = initialize_project(output)
    write_json(paths["intent"], DEMO_INTENT)
    write_json(paths["state"], DEMO_STATE)
    # Frozen E1 policy demo: natural-language seed -> Brief -> first-round
    # noncanonical proposal with 0 BKP.  No knowledge needs means no
    # KnowledgeRetrieve call at all.
    return run_story_design(
        project_dir=output,
        author_input="我想写一个在暴雨夜发现花园会替人保存秘密的故事，主角和失联多年的朋友有关。",
        brief_id="brief-001", context_id="context-001", candidate_id="design-001",
        semantic_interpretation={
            "scope": "story_design",
            "objective": "探索能让主角主动进入花园秘密的故事发动机。",
            "knowledge_needs": [],
            "selected_bkp_ids": [],
            "assumptions": ["失联朋友与花园秘密的具体因果尚未获得作者确认。"],
        },
        model_output={
            "stance": ["story_engine"],
            "proposal": "候选 A：花园只返还一个秘密的后果，主角必须先决定是否交出与朋友有关的记忆。",
            "unknowns": ["朋友是否仍在世", "花园保存秘密的代价"],
            "note": "第一轮 noncanonical 提案；0 张 BKP 是正常路径；不是作者事实或 Canon。",
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
    print(f"selected BKP hits: {len(result['context']['selected_bkp_hits'])}")
    print("candidate status: proposal_noncanonical")


if __name__ == "__main__":
    main()
