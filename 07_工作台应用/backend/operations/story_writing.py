# -*- coding: utf-8 -*-
"""正文写作 Author Operations：第三条真实作者使用链（"这一段想写什么"）。

链路：
  作品概览 → 作者自然语言输入"这一段想写什么"
  → 第一阶段 Agent：上下文选择（semantic_interpretation + state_selections）
  → frozen StoryWrite.prepare_creation_brief / prepare_context
  → 第二阶段 Agent：正文生成（draft_text + settlement_candidates）
  → UI 展示正文候选 → 作者明确"保留这段"
  → ProjectWorkspace.accept_prose（frozen gate）
  → 正文落盘 + accepted_text_index + Story State → 刷新概览

约束（遵守现有冻结合同）：
- 不修改 StoryWrite / ContextCompiler / StoryPlan / ProjectWorkspace。
- 确认前绝不写正式 03_作品工程；候选全部落在可删除的临时工作区。
- 确认必须带后台生成的 writing token；禁止信任前端自行构造正文或 settlement。
- Token 禁止进入 Prompt / UI / 日志 / Bridge 返回值。
- 不修改 planning；不进入 StoryPlan。
- writing token 必须绑定 project_id；cross-project 使用直接拒绝。
- replace_existing 必须绑定本轮 selected Context 中的真实 id。
- 使用 frozen context_package_is_stale 做 confirm stale 检查。
- accepted_text_index 使用 fingerprint（SHA-256）而非 count。
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

from operations.agent_runner import AgentRunError, run_task

# ---------------------------------------------------------------------------
# Frozen runtime imports — NEVER copy their rules; always call them directly.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]

if str(_REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "StoryWrite") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "StoryWrite"))
if str(_REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))
if str(_REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "ContextCompiler") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "ContextCompiler"))

from project_workspace import (  # noqa: E402  ProjectWorkspace frozen runtime
    ContractError as PWContractError,
    WorkspaceError as PWWorkspaceError,
    accept_prose,
    get_recent_prose,
    load_project,
    resolve_project,
)
from storywrite_entry import (  # noqa: E402  StoryWrite frozen runtime
    ContractError as SWContractError,
    prepare_creation_brief,
    prepare_context,
    prepare_recent_prose_window,
)
from context_compiler import context_package_is_stale  # noqa: E402

# 临时 writing 工作区根（06_工作区/应用开发 已 gitignore，Local Only，可删除）
_WRITING_ROOT = (
    Path(__file__).resolve().parents[3] / "06_工作区" / "应用开发" / ".writing"
)

# 第一阶段 Agent 任务模板：上下文选择
_SELECTION_TASK_TEMPLATE = """你是 AI-write 的上下文选择语义助手。只做语义判断，不读取或修改任何文件。

你的任务：根据作者本轮写作要求，从当前 Story State 中选出本场景真正需要的少量条目。
不要选全部，不要 fallback 整包。只选与本场直接相关的条目。

请返回**一个合法的 JSON 对象**（不要任何额外文字、不要 markdown 代码块标记），
结构必须如下：

{{
  "semantic_interpretation": {{
    "objective": "本场写作的目标（一句话）",
    "knowledge_needs": [],
    "selected_bkp_ids": [],
    "assumptions": ["AI 解读中的假设"]
  }},
  "state_selections": [
    {{
      "area": "canon_facts 或 character_state 或 relationship_state 或 occurred_events 或 open_threads 或 approved_plan",
      "id": "条目 id",
      "reason": "为什么这一条与本场有关"
    }}
  ],
  "conflicts_or_tensions": [
    {{"text": "当前叙事中的张力或冲突描述"}}
  ]
}}

作品信息：
- 作品名：{name}
- 已确定的故事方向：{work_direction}
- 读者主要期待：{reader_promise}
- 当前约束：{hard_constraints}
- 自由空间：{open_space}

当前 Story State 候选条目：
{state_entries_summary}

作者本轮要求：{author_input}
"""

# 第二阶段 Agent 任务模板：正文生成
_PROSE_TASK_TEMPLATE = """你是 AI-write 的正文写作助手。根据下面的创作上下文，写一段正文。

请返回**一个合法的 JSON 对象**（不要任何额外文字、不要 markdown 代码块标记），
结构必须如下：

{{
  "draft_text": "正文候选全文（直接可读的小说正文，不要 markdown 标题）",
  "settlement_candidates": [
    {{
      "classification": "mechanical",
      "target_area": "canon_facts",
      "entry": {{"id": "见下方 id 规则", "fact": "本场景中明确成立的事实"}},
      "operation": "append",
      "reason": "正文明确写到了这个事实"
    }}
  ]
}}

settlement 纪律：
- classification 只允许：mechanical / ambiguous / creative
- mechanical：正文中明确已经发生/成立的话语、动作、事实，且适合进入 Story State。
  完成普通 mechanical 判断后，再额外扫描 continuity-critical hard anchors：
  明确数字、日期/时间/deadline、合同条件、明确承诺。
  这些额外项如满足 mechanical 定义也应标 mechanical。
- ambiguous：可能是也可能不是的内容
- creative：纯粹的创意发挥
- 只有 mechanical 才可能被写入 Story State
- operation 只允许：append / replace_existing

entry.id 规则：
- append：id 不由你负责，后台自动生成。你可以省略或写占位值（如 "placeholder"）。
- replace_existing：必须使用 Context Package 中明确提供的真实现有 id
  （见下方 "selected_story_state" 中的 id）。不得使用不存在的 id。

创作 Brief：
{brief_summary}

Context Package：
{context_summary}

{recent_prose_section}

作者本轮要求：{author_input}
"""


class StoryWritingError(Exception):
    """正文写作操作错误（面向 UI 的稳定错误类型，普通用户可读）。"""


# ---------------------------------------------------------------------------
# 临时 writing 工作区
# ---------------------------------------------------------------------------

def get_writing_root() -> Path:
    """临时写作工作区根目录（测试可 monkeypatch 此函数）。"""
    return _WRITING_ROOT


def _writing_dir(project_id: str, writing_turn_id: str) -> Path:
    return get_writing_root() / project_id / writing_turn_id


def _cleanup_writing(project_id: str, writing_turn_id: str) -> None:
    """确认/失败后删除临时写作工作区。"""
    shutil.rmtree(_writing_dir(project_id, writing_turn_id), ignore_errors=True)


def _cleanup_all_for_project(project_id: str) -> None:
    """清理同一 project 下所有旧临时候选（"我想改一改 → 再生成"不留残留）。"""
    root = get_writing_root()
    project_writing = root / project_id
    if project_writing.exists():
        shutil.rmtree(project_writing, ignore_errors=True)


# ---------------------------------------------------------------------------
# accepted_text_index fingerprint
# ---------------------------------------------------------------------------

def _index_fingerprint(entries: list[dict]) -> str:
    """对 index entries 做稳定 SHA-256（空 entries → "empty"）。"""
    if not entries:
        return "empty"
    raw = json.dumps(entries, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------------------
# Agent 输出解析
# ---------------------------------------------------------------------------

def _validate_str_list(value: Any, field_name: str) -> None:
    if not isinstance(value, list):
        raise StoryWritingError(f"Agent 输出字段 {field_name} 类型错误（应为列表）。")
    for i, item in enumerate(value):
        if not isinstance(item, str):
            raise StoryWritingError(f"Agent 输出字段 {field_name}[{i}] 类型错误（应为字符串）。")


def _parse_json_output(output: str, error_prefix: str = "Agent 输出") -> dict[str, Any]:
    """解析 Agent JSON 输出（容错 markdown 代码块标记）。"""
    text = (output or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StoryWritingError(f"{error_prefix}不是合法结构化结果，请重试。") from exc
    if not isinstance(data, dict):
        raise StoryWritingError(f"{error_prefix}不是合法结构化结果（应为 JSON 对象）。")
    return data


def _parse_selection_result(output: str) -> dict[str, Any]:
    """解析第一阶段 Agent 输出（上下文选择）。"""
    data = _parse_json_output(output, "上下文选择阶段")

    si = data.get("semantic_interpretation")
    if not isinstance(si, dict):
        raise StoryWritingError("Agent 输出缺少 semantic_interpretation。")
    if not isinstance(si.get("objective"), str) or not si["objective"].strip():
        raise StoryWritingError("Agent 输出 semantic_interpretation.objective 缺失。")
    if "knowledge_needs" not in si:
        raise StoryWritingError("Agent 输出缺少 semantic_interpretation.knowledge_needs。")
    _validate_str_list(si["knowledge_needs"], "semantic_interpretation.knowledge_needs")
    if "selected_bkp_ids" not in si:
        raise StoryWritingError("Agent 输出缺少 semantic_interpretation.selected_bkp_ids。")
    _validate_str_list(si["selected_bkp_ids"], "semantic_interpretation.selected_bkp_ids")
    if "assumptions" not in si:
        raise StoryWritingError("Agent 输出缺少 semantic_interpretation.assumptions。")
    _validate_str_list(si["assumptions"], "semantic_interpretation.assumptions")

    sels = data.get("state_selections")
    if not isinstance(sels, list):
        raise StoryWritingError("Agent 输出缺少 state_selections（应为列表）。")
    for i, sel in enumerate(sels):
        if not isinstance(sel, dict):
            raise StoryWritingError(f"Agent 输出 state_selections[{i}] 不是对象。")
        if not sel.get("area") or not sel.get("id") or not (sel.get("reason") or "").strip():
            raise StoryWritingError(f"Agent 输出 state_selections[{i}] 缺少 area/id/reason。")

    return {
        "semantic_interpretation": si,
        "state_selections": sels,
        "conflicts_or_tensions": data.get("conflicts_or_tensions") or [],
    }


def _parse_prose_result(output: str) -> dict[str, Any]:
    """解析第二阶段 Agent 输出（正文生成）。

    append 类型：不要求模型给有效唯一 id（后台生成）。
    replace_existing 类型：必须要求非空 id。
    """
    data = _parse_json_output(output, "正文生成阶段")

    draft_text = data.get("draft_text")
    if not isinstance(draft_text, str) or not draft_text.strip():
        raise StoryWritingError("Agent 输出缺少正文（draft_text 应为非空字符串）。")

    candidates = data.get("settlement_candidates")
    if not isinstance(candidates, list):
        raise StoryWritingError("Agent 输出缺少 settlement_candidates（应为列表）。")
    valid_classifications = ("mechanical", "ambiguous", "creative")
    valid_operations = ("append", "replace_existing")
    for i, cand in enumerate(candidates):
        if not isinstance(cand, dict):
            raise StoryWritingError(f"settlement_candidates[{i}] 不是对象。")
        if cand.get("classification") not in valid_classifications:
            raise StoryWritingError(f"settlement_candidates[{i}].classification 非法。")
        if not isinstance(cand.get("target_area"), str) or not cand["target_area"]:
            raise StoryWritingError(f"settlement_candidates[{i}].target_area 缺失。")
        entry = cand.get("entry")
        if not isinstance(entry, dict):
            raise StoryWritingError(f"settlement_candidates[{i}].entry 不是对象。")
        op = cand.get("operation", "append")
        if op not in valid_operations:
            raise StoryWritingError(f"settlement_candidates[{i}].operation 非法。")
        # replace_existing 必须要求非空 id；append 不要求
        if op == "replace_existing" and not entry.get("id"):
            raise StoryWritingError(
                f"settlement_candidates[{i}]: replace_existing 必须提供非空 entry.id。"
            )

    return {"draft_text": draft_text.strip(), "settlement_candidates": candidates}


# ---------------------------------------------------------------------------
# 辅助：构建 State 条目摘要供 Agent 选择
# ---------------------------------------------------------------------------

def _build_state_entries_summary(state: dict[str, Any]) -> str:
    """把当前 State 的可选择条目整理成可读摘要（供选择阶段 Agent）。"""
    lines = []
    selectable = ("canon_facts", "character_state", "relationship_state",
                  "occurred_events", "open_threads", "approved_plan")
    for area in selectable:
        entries = state.get(area) or []
        if not entries:
            continue
        lines.append(f"\n[{area}]")
        for entry in entries:
            eid = entry.get("id", "?")
            desc = entry.get("fact") or entry.get("description") or entry.get("text") or json.dumps(entry, ensure_ascii=False)[:120]
            lines.append(f"  - id: {eid}  →  {desc}")
    if not lines:
        return "（当前 State 无可选择条目）"
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 辅助：构建第二阶段 Context 摘要（真正消费 Context Package）
# ---------------------------------------------------------------------------

def _build_context_summary(context: dict[str, Any]) -> str:
    """把 Context Package 的作者可读内容整理成小型文本块（第二阶段 Agent 真正消费）。

    包含：selected_intent / selected_story_state / selected_bkp_hits /
    conflicts_or_tensions。不包含完整未选择 State。
    """
    parts: list[str] = []

    # selected_intent
    sel_intent = context.get("selected_intent") or {}
    if sel_intent:
        parts.append("[selected_intent]")
        for k, v in sel_intent.items():
            if v:
                parts.append(f"  {k}: {v}")

    # selected_story_state（保留 area + id + 实际内容，replace_existing 需要）
    sel_state = context.get("selected_story_state") or {}
    if sel_state:
        parts.append("\n[selected_story_state]")
        for area, items in sel_state.items():
            for item in items:
                eid = item.get("id", "?")
                desc = item.get("fact") or item.get("description") or item.get("text") or ""
                parts.append(f"  [{area}] id={eid}  →  {desc}")

    # selected_bkp_hits
    bkp_hits = context.get("selected_bkp_hits") or []
    if bkp_hits:
        parts.append("\n[selected_bkp_hits]")
        for hit in bkp_hits:
            if isinstance(hit, dict):
                parts.append(f"  - {hit.get('title', '')}: {hit.get('text', '')[:200]}")

    # conflicts_or_tensions
    conflicts = context.get("conflicts_or_tensions") or []
    if conflicts:
        parts.append("\n[conflicts_or_tensions]")
        for c in conflicts:
            if isinstance(c, dict) and c.get("text"):
                parts.append(f"  - {c['text']}")

    return "\n".join(parts) if parts else "（Context 中无选定条目）"


# ---------------------------------------------------------------------------
# 辅助：验证 replace_existing 绑定本轮 selected Context
# ---------------------------------------------------------------------------

def _validate_replace_existing_in_context(
    settlement_candidates: list[dict],
    context: dict[str, Any],
) -> None:
    """replace_existing 的 target_area + entry.id 必须出现在 selected_story_state 中。"""
    sel_state = context.get("selected_story_state") or {}
    # 构建 (area, id) 集合
    valid_refs: set[tuple[str, str]] = set()
    for area, items in sel_state.items():
        for item in items:
            eid = item.get("id")
            if eid:
                valid_refs.add((area, eid))

    for i, cand in enumerate(settlement_candidates):
        if cand.get("operation") == "replace_existing":
            area = cand.get("target_area", "")
            eid = cand.get("entry", {}).get("id", "")
            if (area, eid) not in valid_refs:
                raise StoryWritingError(
                    f"settlement_candidates[{i}]: replace_existing 目标 "
                    f"({area}/{eid}) 不在本轮 Context 的选定条目中，拒绝候选。"
                )


# ---------------------------------------------------------------------------
# 提出正文候选
# ---------------------------------------------------------------------------

def propose_story_write(project_id: str, author_input: str) -> dict[str, Any]:
    """"这一段想写什么"：两阶段 Agent → StoryWrite → 正文候选。

    返回给 UI 的最小展示形状（正文候选 + writing_token）。
    """
    author_input = (author_input or "").strip()
    if not author_input:
        raise StoryWritingError("请写下这一段想写什么。")

    # 1. 读取正式作品
    try:
        proj = resolve_project(project_id)
        loaded = load_project(proj["project_dir"])
    except (PWContractError, PWWorkspaceError) as exc:
        raise StoryWritingError(str(exc)) from exc

    intent = loaded["intent"]
    state = loaded["state"]
    name = loaded["name"]

    # 清理同一 project 的旧临时候选（"我想改一改 → 再生成"不留残留）
    _cleanup_all_for_project(project_id)

    # 2. 创建临时写作工作区
    writing_turn_id = uuid.uuid4().hex[:12]
    writing_dir = _writing_dir(project_id, writing_turn_id)
    writing_dir.mkdir(parents=True, exist_ok=False)

    # 3. 第一阶段 Agent：上下文选择
    state_summary = _build_state_entries_summary(state)
    work_direction = intent.get("work_direction") or ""
    reader_promise = intent.get("reader_promise") or ""
    hard_constraints = ", ".join(intent.get("hard_constraints") or []) or "（暂无）"
    open_space = ", ".join(intent.get("open_space") or []) or "（暂无）"

    selection_task = _SELECTION_TASK_TEMPLATE.format(
        name=name,
        work_direction=work_direction,
        reader_promise=reader_promise,
        hard_constraints=hard_constraints,
        open_space=open_space,
        state_entries_summary=state_summary,
        author_input=author_input,
    )

    try:
        sel_result = run_task(selection_task, cwd=str(writing_dir))
    except AgentRunError as exc:
        _cleanup_writing(project_id, writing_turn_id)
        raise StoryWritingError(str(exc)) from exc

    if sel_result.status != "completed":
        _cleanup_writing(project_id, writing_turn_id)
        raise StoryWritingError(sel_result.error or f"Agent 未能完成选择阶段（{sel_result.status}）。")

    try:
        selection = _parse_selection_result(sel_result.output)
    except StoryWritingError:
        _cleanup_writing(project_id, writing_turn_id)
        raise

    # 4. 调用 frozen StoryWrite.prepare_creation_brief
    brief_id = f"write-brief-{writing_turn_id}"
    try:
        brief = prepare_creation_brief(
            project_id=project_id,
            brief_id=brief_id,
            author_input=author_input,
            intent=intent,
            state=state,
            semantic_interpretation=selection["semantic_interpretation"],
        )
    except SWContractError as exc:
        _cleanup_writing(project_id, writing_turn_id)
        raise StoryWritingError(f"Creation Brief 被拒绝：{exc}") from exc

    # 5. 调用 frozen StoryWrite.prepare_context
    context_id = f"write-context-{writing_turn_id}"
    try:
        context = prepare_context(
            context_id=context_id,
            brief=brief,
            intent=intent,
            state=state,
            state_selections=selection["state_selections"],
            conflicts_or_tensions=selection.get("conflicts_or_tensions"),
            selected_knowledge_ids=selection["semantic_interpretation"].get("selected_bkp_ids", []),
        )
    except SWContractError as exc:
        _cleanup_writing(project_id, writing_turn_id)
        raise StoryWritingError(f"Context 被拒绝：{exc}") from exc

    # 6. 获取 recent prose
    #    区分"第一场（index 为空）"和"index 有正文但 recent prose 损坏"
    index_entries = loaded.get("index", {}).get("entries", [])
    recent_prose_window = None
    if index_entries:
        # index 已有 accepted entry → 必须有 recent prose；失败则停止
        try:
            recent_prose_window = get_recent_prose(proj["project_dir"])
        except (PWContractError, PWWorkspaceError) as exc:
            _cleanup_writing(project_id, writing_turn_id)
            raise StoryWritingError(
                f"上一段正文衔接数据异常，请重新生成：{exc}"
            ) from exc
    # else: index 为空 → 第一场，recent_prose_window = None

    # 7. 生成 scene_ref（后台生成，不由模型决定）
    scene_ref = f"scene-{writing_turn_id}"

    # 8. 第二阶段 Agent：正文生成（真正消费 Context Package）
    brief_summary = f"目标：{brief.get('author_input', '')}\n方向：{work_direction}"
    context_summary = _build_context_summary(context)

    recent_prose_section = ""
    if recent_prose_window:
        recent_prose_section = f"上一段正文（仅供短时连续性参考，不要逐字复写）：\n{recent_prose_window['text']}"

    prose_task = _PROSE_TASK_TEMPLATE.format(
        brief_summary=brief_summary,
        context_summary=context_summary,
        recent_prose_section=recent_prose_section,
        author_input=author_input,
    )

    try:
        prose_result = run_task(prose_task, cwd=str(writing_dir))
    except AgentRunError as exc:
        _cleanup_writing(project_id, writing_turn_id)
        raise StoryWritingError(str(exc)) from exc

    if prose_result.status != "completed":
        _cleanup_writing(project_id, writing_turn_id)
        raise StoryWritingError(prose_result.error or f"Agent 未能完成正文生成（{prose_result.status}）。")

    try:
        prose = _parse_prose_result(prose_result.output)
    except StoryWritingError:
        _cleanup_writing(project_id, writing_turn_id)
        raise

    # 9. 后台为 append 类型的 settlement entry 生成稳定 id
    settlement_candidates = []
    for i, cand in enumerate(prose["settlement_candidates"]):
        entry = dict(cand["entry"])
        if cand.get("operation", "append") == "append":
            # 后台生成稳定 id（不让模型管理唯一 id）
            entry["id"] = f"sw-{writing_turn_id}-{i+1}"
        settlement_candidates.append({
            "classification": cand["classification"],
            "target_area": cand["target_area"],
            "entry": entry,
            "operation": cand.get("operation", "append"),
            "reason": cand.get("reason") or "",
        })

    # 10. replace_existing 必须绑定本轮 selected Context
    _validate_replace_existing_in_context(settlement_candidates, context)

    # 11. 保存元信息（writing_token 用于确认时校验）
    meta = {
        "kind": "story_writing_proposal",
        "project_id": project_id,
        "name": name,
        "writing_turn_id": writing_turn_id,
        "writing_token": uuid.uuid4().hex,
        "scene_ref": scene_ref,
        "author_input": author_input,
        "draft_text": prose["draft_text"],
        "settlement": {
            "scene_ref": scene_ref,
            "candidates": settlement_candidates,
        },
        "source_versions": {
            "intent_rev": intent["intent_rev"],
            "state_rev": state["state_rev"],
        },
        "index_fingerprint": _index_fingerprint(index_entries),
        # 保存 brief + context 供 confirm 时 frozen stale 检查
        "brief": brief,
        "context": context,
    }

    # 12. 确定 chapter_number
    if index_entries:
        chapter_number = index_entries[-1].get("chapter_number", 1)
    else:
        chapter_number = 1
    meta["chapter_number"] = chapter_number

    (writing_dir / "writing_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "writing_token": meta["writing_token"],
        "project_id": project_id,
        "name": name,
        "scene_ref": scene_ref,
        "chapter_number": chapter_number,
        "draft_text": prose["draft_text"],
        "message": "正文候选已生成（未写入正式作品，等待你的确认）",
    }


# ---------------------------------------------------------------------------
# 作者明确接受正文
# ---------------------------------------------------------------------------

def confirm_story_write(project_id: str, writing_token: str) -> dict[str, Any]:
    """作者明确"保留这段"：用后台保存的 draft + settlement 调用 accept_prose。

    确认必须带后台生成的 writing token；前端不能重新上传正文或 settlement。
    """
    writing_token = (writing_token or "").strip()
    if not writing_token:
        raise StoryWritingError("缺少正文确认标识（writing token）。")

    # 1. 用 token 反查写作工作区
    root = get_writing_root()
    matched: Path | None = None
    if root.exists():
        for meta_file in root.glob("*/*/writing_meta.json"):
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if meta.get("writing_token") == writing_token:
                matched = meta_file.parent
                break
    if matched is None:
        raise StoryWritingError("正文候选已失效或不存在，请重新生成。")

    meta = json.loads((matched / "writing_meta.json").read_text(encoding="utf-8"))

    # 2. cross-project token 检查：writing token 必须绑定当前 project_id
    if meta.get("project_id") != project_id:
        raise StoryWritingError("这份正文候选不属于当前作品，请重新生成。")

    writing_turn_id = meta["writing_turn_id"]
    scene_ref = meta["scene_ref"]
    draft_text = meta["draft_text"]
    settlement = meta["settlement"]
    chapter_number = meta["chapter_number"]
    saved_brief = meta.get("brief", {})
    saved_context = meta.get("context", {})

    # 3. 重新读取正式作品（用于 stale 检查）
    try:
        proj = resolve_project(project_id)
        loaded = load_project(proj["project_dir"])
    except (PWContractError, PWWorkspaceError) as exc:
        raise StoryWritingError(str(exc)) from exc

    current_intent = loaded["intent"]
    current_state = loaded["state"]
    current_index = loaded.get("index", {})
    project_dir = Path(loaded["project_dir"])

    # 4. frozen context_package_is_stale 检查
    if context_package_is_stale(saved_context, saved_brief, current_intent, current_state):
        _cleanup_writing(project_id, writing_turn_id)
        raise StoryWritingError("作品在这期间已经有了新的变化，请重新生成这一段。")

    # 5. accepted_text_index fingerprint 检查（覆盖正文索引变化）
    current_entries = current_index.get("entries", [])
    current_fp = _index_fingerprint(current_entries)
    if current_fp != meta.get("index_fingerprint"):
        _cleanup_writing(project_id, writing_turn_id)
        raise StoryWritingError("作品在这期间已经有了新的内容，请重新生成这一段。")

    # 6. 调用 ProjectWorkspace.accept_prose（frozen gate）
    try:
        result = accept_prose(
            project_dir=project_dir,
            chapter_number=chapter_number,
            scene_ref=scene_ref,
            accepted_text=draft_text,
            settlement=settlement,
            author_accepted=True,
        )
    except (PWContractError, PWWorkspaceError) as exc:
        _cleanup_writing(project_id, writing_turn_id)
        raise StoryWritingError(f"接受正文失败：{exc}") from exc

    # 7. 清理临时写作工作区
    _cleanup_writing(project_id, writing_turn_id)

    return {
        "project_id": project_id,
        "name": loaded["name"],
        "chapter_path": result.get("chapter_path"),
        "chapter_number": chapter_number,
        "scene_ref": scene_ref,
        "message": "这段已经保留下来了。",
    }
