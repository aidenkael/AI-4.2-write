"""Provider-agnostic orchestration for one StoryDesign turn."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from story_runtime import (
    build_context,
    compile_creation_brief,
    create_design_candidate,
    initialize_project,
    project_paths,
    read_json,
    trace_record,
    write_json,
)


CAPABILITY = {
    "capability_id": "story_design.v0",
    "solves": "将作者自然语言设想编译为可审查的 StoryDesign proposal。",
    "inputs": ["author natural-language seed", "Author Intent", "Story State"],
    "may_read": ["Author Intent", "Story State", "selected BKP through KnowledgeRetrieve"],
    "writes_state": False,
    "confirmation_required_for_writes": "任何 proposal 或 future plan 写入都需要 Author Decision。",
    "outputs": ["Creation Brief", "Context Package", "noncanonical StoryDesign candidate", "trace"],
}


def run_story_design(
    *,
    project_dir: Path,
    author_input: str,
    brief_id: str,
    context_id: str,
    candidate_id: str,
    semantic_interpretation: dict[str, Any],
    model_output: dict[str, Any],
    retrieval: Callable | None = None,
) -> dict[str, Any]:
    """Run the deterministic shell around model/skill-provided semantic work."""
    paths = initialize_project(project_dir)
    intent = read_json(paths["intent"])
    state = read_json(paths["state"])
    brief = compile_creation_brief(
        project_id=intent["project_id"], brief_id=brief_id, author_input=author_input,
        intent=intent, state=state, semantic_interpretation=semantic_interpretation,
    )
    context = build_context(
        context_id=context_id, brief=brief, intent=intent, state=state, retrieval=retrieval,
        selected_knowledge_ids=semantic_interpretation.get("selected_bkp_ids", []),
    )
    candidate = create_design_candidate(candidate_id=candidate_id, brief=brief, context=context, model_output=model_output)
    trace = trace_record(trace_id=f"trace-{candidate_id}", brief=brief, context=context, candidate=candidate)
    write_json(paths["briefs"] / f"{brief_id}.json", brief)
    write_json(paths["contexts"] / f"{context_id}.json", context)
    write_json(paths["designs"] / f"{candidate_id}.json", candidate)
    write_json(paths["traces"] / f"trace-{candidate_id}.json", trace)
    return {"brief": brief, "context": context, "candidate": candidate, "trace": trace}
