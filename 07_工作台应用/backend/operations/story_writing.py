# -*- coding: utf-8 -*-
"""正文写作 Author Operations：第三条真实作者使用链（"这一段想写什么"）。

链路（统一请求生命周期，执行模式由已保存 Settings 决定）：
  作品概览 → 作者自然语言输入"这一段想写什么"
  → Go Write 读取 Settings 执行配置 → 准备本轮任务
  → Direct：后台 worker 顺序执行两阶段（同一 Agent/模型路由）：
      Stage 1：上下文选择（semantic_interpretation + state_selections +
               conflicts_or_tensions；knowledge_needs 走精确检索包 P0 规则）
      → frozen StoryWrite.prepare_creation_brief / prepare_context（绑定检索包）
      → Stage 2：正文生成（context_ref + draft_text + settlement_candidates）
  → Interactive：两阶段交互桥（真实的两次 /gowrite，绝不回退 Direct）：
      Stage 1：作者在 Qoder 输入 /gowrite 执行上下文选择（任务 = 选择任务）
      → Go Write 验收 Stage 1 输出 → P0 绑定 + 编译精确 Context 快照 →
        请求文件原地换成 Stage 2 正文生成任务（fresh Agent invocation）
      → 作者再次输入 /gowrite 执行 ONLY Stage 2 → context_ref 校验
  → 两种模式都写回同一响应信封 → get_story_write_request 持久化候选 → UI 展示
  → 作者明确"保留这段" → ProjectWorkspace.accept_prose（frozen gate）
  → 正文落盘 + accepted_text_index + Story State → 刷新概览

两阶段隔离（冻结设计要求）：
- Stage 1 可以看到完整 Story State 候选目录，以便选择本场需要的少量条目；
- Stage 2 只看到编译后的选定 Context Package + recent prose，绝不含未选中的
  全量 State 目录。二者是两次独立 Agent 运行（Direct 两次 run；Interactive
  两次 /gowrite 各自 fresh invocation），不合并为一次会话。

知识选择绑定（Knowledge Selection Binding，同 StoryPlan P0）：
- knowledge_needs = []：不调用 KnowledgeRetrieve，不要求快照，selected BKP
  为空，0 张 BKP 是一等合法结果。
- knowledge_needs ≠ []：Agent 在 Stage 1 执行内运行
  `retrieval_snapshot.py --request <request_id> "<query>"` —— 整个流程唯一一次
  确定性 KnowledgeRetrieve 执行；同时把候选返回给模型并把精确序列化包写入
  请求级快照（<writing_dir>/retrieval/package.json）。模型只从该包中选择
  scoped ref 并回显 package_fingerprint。finalize/worker **绝不再次检索**。

交互桥阶段状态机（同一请求生命周期，无第二个前端 API 家族）：
  pending_selection →（Stage 1 验收 + Context 编译）→ pending_prose
  →（Stage 2 验收 + 候选）→ completed / failed / canceled（终态）
- 任一阶段取消都使整个操作失效；晚到/过期阶段响应一律丢弃；
- 项目切换不得把 request/token 带入另一项目（meta.project_id + writing
  token 双重绑定）。

约束（遵守现有冻结合同）：
- 不修改 StoryWrite / ContextCompiler / StoryPlan / ProjectWorkspace。
- 确认前绝不写正式 03_作品工程；候选全部落在可删除的临时工作区。
- 确认必须带后台生成的 writing token；禁止信任前端自行构造正文或 settlement。
- Token 禁止进入 Prompt / UI / 日志 / Bridge 返回值（writing_token 除外，
  它是确认阶段的前后端契约）。
- writing token 必须绑定 project_id；cross-project 使用直接拒绝。
- replace_existing 必须绑定本轮 selected Context 中的真实 id。
- 使用 frozen context_package_is_stale 做 confirm stale 检查。
- accepted_text_index 使用 fingerprint（SHA-256）而非 count。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

from operations import agent_runner
from operations import execution_audit as audit
from operations import execution_tasks
from operations import qoder_bridge as bridge
from operations.agent_runner import AgentRunError
from config.settings import EXECUTION_MODE_DIRECT, SettingsStore
from operations.story_planning import (  # noqa: E402  复用同一 P0 检索包机制
    _DIRECT_BUSY_ERROR,
    _MAX_KNOWLEDGE_HITS,
    _bound_package,
    _package_fingerprint,
    _package_from_snapshot,
    _package_snapshot_dict,
    _retrieve_package,
)

# Direct 执行任务管理器（与 StoryPlan 共用同一单活跃槽；测试可替换）
_exec_task_manager = execution_tasks.manager

# 交互桥阶段状态（同一请求生命周期，无第二个前端 API 家族）
PHASE_PENDING_SELECTION = "pending_selection"
PHASE_PENDING_PROSE = "pending_prose"

# 交互桥两次 /gowrite 的总超时（作者可能 Alt+Tab 后才执行，给足时间）
_INTERACTIVE_TIMEOUT_SECONDS = 60 * 60

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

# 请求级检索快照 CLI（Agent 在 Stage 1 执行内运行；唯一的确定性检索入口）。
_RETRIEVAL_SCRIPT = Path(__file__).resolve().parent / "retrieval_snapshot.py"

# 第一阶段 Agent 任务模板：上下文选择（P0：knowledge_needs 非空时必须先用
# 工具执行检索命令，再输出最终 JSON；绝不回到"先选 BKP 再见包"的旧行为）
_SELECTION_TASK_TEMPLATE = """你是 Go Write 的正文上下文选择执行器。必须严格按下列顺序执行：先完成语义分析；若 knowledge_needs 非空，必须在生成最终 JSON 之前，先调用本地命令/工具执行下面给出的检索命令并读取其结果；完成检索与选择后，才输出最终 JSON。本任务不是纯文本生成任务；中间的工具调用属于执行过程，不属于最终回复。

流程分两个阶段：

第一阶段：语义分析
针对作者本轮写作要求，先完成语义分析（objective / knowledge_needs / assumptions），并从下方 Story State 候选条目中选出本场真正需要的少量条目（state_selections，显式选择，可为空，绝不 fallback 整包），同时给出 conflicts_or_tensions。knowledge_needs 为空列表是合法的。

第二阶段：知识检索与选择（仅当 knowledge_needs 非空；必须执行）
若 knowledge_needs 非空，在生成最终 JSON 之前，你必须先用可用的本地命令/工具执行以下确定性只读检索命令：
  python {retrieval_command} --request {request_id} "<query>"
其中 <query> 是把你第一阶段列出的全部 knowledge_needs 用中文分号（；）连接成的单个字符串（直接替换命令中的 <query> 占位符）。
该命令会把本次检索包（RetrievalPackage，混合参考作品知识/方法知识/已验证知识）写入当前请求的临时快照（不改动任何作品或业务文件），然后向终端输出一个 JSON，其中 package_fingerprint 是本次检索包的身份指纹，package.hits 数组内每个候选项含 selection_ref、source_kind、source_id、source_title、statement、scope、boundary、evidence 等字段；selection_ref 形如 "<source_kind>/<source_id>/<source_anchor>"（例如 reference_bkp/book_a/K001、method_source/book_0138/M0003、validated_knowledge/pkg_opening_hook/V0001）。
你必须读取该命令实际输出的 package：只从中选择 0 到 {max_knowledge_hits} 个 selection_ref，填入 semantic_interpretation.selected_knowledge_refs；并把命令输出的 package_fingerprint 原样填入 semantic_interpretation.package_ref。
严禁编造命令输出中不存在的 selection_ref 或 package_fingerprint；若没有合适的候选，selected_knowledge_refs 保持空列表（0 条知识是合法结果）。
若 knowledge_needs 为空：不要运行检索命令，selected_knowledge_refs 必须为 []，package_ref 必须为空字符串 ""。

最终回复
最终回复必须只有合法 JSON 对象（不要任何额外文字、不要 markdown 代码块标记）。结构必须如下：

{{
  "semantic_interpretation": {{
    "objective": "本场写作的目标（一句话）",
    "knowledge_needs": [],
    "selected_knowledge_refs": [],
    "package_ref": "",
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

最终回复必须只有合法 JSON；但在生成最终回复之前，若 knowledge_needs 非空，你必须先调用工具执行检索命令并读取结果。工具调用属于任务执行过程，不属于最终回复。"""

# 第二阶段 Agent 任务模板：正文生成（context_ref 必须回显编译 Context 快照指纹）
_PROSE_TASK_TEMPLATE = """根据下面的创作上下文，写一段正文。最终回复必须只有合法 JSON 对象（不要任何额外文字、不要 markdown 代码块标记）。结构必须如下：

{{
  "context_ref": "<下方给出的 Context 快照指纹，原样复制>",
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
- replace_existing：必须使用下方 Context Package 中明确提供的真实现有 id
  （见 "selected_story_state" 中的 id）。不得使用不存在的 id。

本次 Context 快照指纹（必须原样复制到 context_ref，否则结果会被拒绝）：
{context_fingerprint}

创作 Brief：
{brief_summary}

Context Package：
{context_summary}

{recent_prose_section}

作者本轮要求：{author_input}

最终回复必须只有合法 JSON；context_ref 必须与上面给出的指纹完全一致。"""


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
    """确认/失败/取消后删除临时写作工作区。"""
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
    """解析第一阶段 Agent 输出（上下文选择；package_ref 为必填字段）。"""
    data = _parse_json_output(output, "上下文选择阶段")

    si = data.get("semantic_interpretation")
    if not isinstance(si, dict):
        raise StoryWritingError("Agent 输出缺少 semantic_interpretation。")
    if not isinstance(si.get("objective"), str) or not si["objective"].strip():
        raise StoryWritingError("Agent 输出 semantic_interpretation.objective 缺失。")
    if "knowledge_needs" not in si:
        raise StoryWritingError("Agent 输出缺少 semantic_interpretation.knowledge_needs。")
    _validate_str_list(si["knowledge_needs"], "semantic_interpretation.knowledge_needs")
    if "selected_knowledge_refs" not in si:
        raise StoryWritingError("Agent 输出缺少 semantic_interpretation.selected_knowledge_refs。")
    _validate_str_list(si["selected_knowledge_refs"], "semantic_interpretation.selected_knowledge_refs")
    if "package_ref" not in si or not isinstance(si.get("package_ref"), str):
        raise StoryWritingError(
            "Agent 输出缺少 semantic_interpretation.package_ref（应为字符串：本次检索包身份指纹）。"
        )
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


def _parse_prose_result(output: str, *, expected_context_ref: str) -> dict[str, Any]:
    """解析第二阶段 Agent 输出（正文生成；context_ref 必须精确匹配）。

    append 类型：不要求模型给有效唯一 id（后台生成）。
    replace_existing 类型：必须要求非空 id。
    """
    data = _parse_json_output(output, "正文生成阶段")

    context_ref = data.get("context_ref")
    if not isinstance(context_ref, str) or not context_ref.strip():
        raise StoryWritingError("Agent 输出缺少 context_ref（应为编译 Context 快照指纹）。")
    if context_ref.strip() != expected_context_ref:
        raise StoryWritingError("Agent 输出的 context_ref 与编译 Context 快照不一致，已拒绝。")

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

    return {
        "context_ref": context_ref.strip(),
        "draft_text": draft_text.strip(),
        "settlement_candidates": candidates,
    }


# ---------------------------------------------------------------------------
# 辅助：构建 State 条目摘要供 Stage 1 Agent 选择
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
    """把 Context Package 的作者可读内容整理成小型文本块（Stage 2 真正消费）。

    包含：selected_intent / selected_story_state / selected_knowledge_hits /
    conflicts_or_tensions。不包含完整未选择 State。
    """
    parts: list[str] = []

    sel_intent = context.get("selected_intent") or {}
    if sel_intent:
        parts.append("[selected_intent]")
        for k, v in sel_intent.items():
            if v:
                parts.append(f"  {k}: {v}")

    sel_state = context.get("selected_story_state") or {}
    if sel_state:
        parts.append("\n[selected_story_state]")
        for area, items in sel_state.items():
            for item in items:
                eid = item.get("id", "?")
                desc = item.get("fact") or item.get("description") or item.get("text") or ""
                parts.append(f"  [{area}] id={eid}  →  {desc}")

    knowledge_hits = context.get("selected_knowledge_hits") or []
    if knowledge_hits:
        parts.append("\n[selected_knowledge_hits]")
        for hit in knowledge_hits:
            if isinstance(hit, dict):
                parts.append(f"  - {hit.get('selection_ref', '')}: {hit.get('statement', '')[:200]}")

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
# 知识选择绑定（P0，与 StoryPlan 同规则；请求级快照在 writing 工作区）
# ---------------------------------------------------------------------------

def _snapshot_path(writing_dir: Path) -> Path:
    return writing_dir / "retrieval" / "package.json"


def _write_snapshot(
    *,
    request_id: str,
    project_id: str,
    writing_turn_id: str,
    query: str,
    package: Any,
    writing_dir: Path,
) -> Path:
    """把精确序列化 RetrievalPackage 写入请求级快照（非权威、可删除）。"""
    snapshot = {
        "schema": "gowrite_retrieval_snapshot/v2",
        "request_id": request_id,
        "project_id": project_id,
        "writing_turn_id": writing_turn_id,
        "query": query,
        "package_fingerprint": _package_fingerprint(package),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "package": _package_snapshot_dict(package),
    }
    path = _snapshot_path(writing_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _load_snapshot(writing_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    """读取请求级检索快照；返回 (snapshot, error)。error 非空表示缺失或不可解析。"""
    path = _snapshot_path(writing_dir)
    if not path.exists():
        return None, "检索包快照缺失：Agent 未在本轮 Stage 1 执行内生成检索快照。"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "检索包快照无法解析（已被篡改或损坏）。"
    if not isinstance(data, dict) or not isinstance(data.get("package"), dict):
        return None, "检索包快照结构无效（缺少 package 对象）。"
    if data.get("schema") != "gowrite_retrieval_snapshot/v2":
        return None, "检索包快照为不兼容的旧版格式，已拒绝（请重新发起本轮任务）。"
    return data, None


def _validate_snapshot(
    snapshot: dict[str, Any],
    *,
    request_id: str,
    project_id: str,
    writing_turn_id: str,
    query: str,
    package_ref: str,
) -> None:
    """校验快照身份：请求/项目/writing turn/归一化查询/包指纹全部一致。"""
    if snapshot.get("request_id") != request_id:
        raise StoryWritingError("检索包快照 request_id 与当前任务不一致，已拒绝。")
    if snapshot.get("project_id") != project_id:
        raise StoryWritingError("检索包快照 project_id 与当前任务不一致，已拒绝。")
    if snapshot.get("writing_turn_id") != writing_turn_id:
        raise StoryWritingError("检索包快照 writing_turn_id 与当前任务不一致，已拒绝。")
    if snapshot.get("query") != query:
        raise StoryWritingError(
            "检索包快照查询与本次 knowledge_needs 不一致（query mismatch），已拒绝。"
        )
    if not package_ref:
        raise StoryWritingError("Agent 输出缺少检索包身份（package_ref）。")
    if snapshot.get("package_fingerprint") != package_ref:
        raise StoryWritingError(
            "Agent 选择的检索包身份（package_ref）与绑定快照不一致，已拒绝。"
        )


def execute_request_scoped_retrieval(query: str, request_id: str) -> Any:
    """Agent 侧（Stage 1 执行内）的"唯一一次确定性检索调用"。

    显式绑定 request_id（后台 worker 不依赖可变的 active 指针）→ 从请求 meta
    恢复 project_id / writing_turn_id → 运行现有 KnowledgeRetrieve（唯一一次）
    → 把精确序列化包写入请求级快照 → 返回包对象（由 CLI 打印给模型查看）。
    """
    request = bridge.get_request(request_id)
    if request is None:
        raise StoryWritingError("任务文件不存在或不可读，无法生成检索快照。")
    meta = request.get("meta") or {}
    project_id = str(meta.get("project_id") or "")
    writing_turn_id = str(meta.get("writing_turn_id") or "")
    if not project_id or not writing_turn_id:
        raise StoryWritingError("任务缺少 project_id / writing_turn_id 元数据。")
    writing_dir = _writing_dir(project_id, writing_turn_id)
    audit.append_event(
        request_id, audit.EVENT_RETRIEVAL_REQUESTED, "knowledge_retrieve",
        details={"query": query[:200]},
    )
    try:
        package = _retrieve_package(query)  # 唯一一次 KnowledgeRetrieve 执行
    except StoryWritingError:
        raise
    except Exception as exc:  # noqa: BLE001 — 检索失败 → Agent 侧命令失败，无快照可写
        raise StoryWritingError(f"知识检索失败：{exc}") from exc
    _write_snapshot(
        request_id=request_id,
        project_id=project_id,
        writing_turn_id=writing_turn_id,
        query=query,
        package=package,
        writing_dir=writing_dir,
    )
    audit.append_event(
        request_id, audit.EVENT_RETRIEVAL_PACKAGE_BUILT, "knowledge_retrieve",
        details={
            "query": query[:200],
            "candidate_count": getattr(package, "candidate_count", len(getattr(package, "hits", []))),
            "refs": [
                getattr(hit, "selection_ref", "") or (
                    f"{getattr(hit, 'source_kind', '')}/{getattr(hit, 'source_id', '')}/"
                    f"{getattr(hit, 'source_anchor', '')}")
                for hit in getattr(package, "hits", [])
            ],
            "source_kinds": sorted({
                getattr(hit, "source_kind", "") for hit in getattr(package, "hits", [])
            }),
        },
    )
    return package


def _context_fingerprint(context: dict[str, Any]) -> str:
    """编译 Context Package 的确定性快照指纹（Stage 2 必须回显为 context_ref）。"""
    canonical = json.dumps(context, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Direct 后台执行（两阶段 worker；与 StoryPlan 共用任务管理器）
# ---------------------------------------------------------------------------

def _finish_direct(
    request_id: str,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """把 Direct 执行结果写入现有请求响应信封并标记任务终态。

    已取消绝不写响应；桥请求侧 canceled 状态是最终防线（永不 finalize）。
    注意：审计记录不在这里收尾 —— 阶段事件（skill/retrieval/candidate）由
    get_story_write_request 的 finalize 路径追加后再 finish（否则会丢事件）。
    """
    if _exec_task_manager.is_canceled(request_id):
        return
    bridge.write_response(request_id, status=status, result=result, error=error)
    _exec_task_manager.finish(
        request_id,
        execution_tasks.TASK_COMPLETED if status == "completed" else execution_tasks.TASK_FAILED,
    )


def _dispatch_writing_worker(
    adapter: Any, agent_request: Any, ctx: dict[str, Any], request_id: str
) -> None:
    """后台 worker：两阶段顺序执行（选择 → 编译 Context → 正文），写回同一信封。

    绝不调用 finalize —— get_story_write_request 是唯一候选持久化/finalize 路径。
    取消/失败在任何阶段都安全退出，不产生候选。
    验证式审计：只在实际 callsite 记录（adapter.run 前后 / frozen 编译调用点）。
    """
    # ---------- Stage 1：上下文选择 ----------
    if _exec_task_manager.is_canceled(request_id):
        return
    agent_request.task = ctx["selection_task"]
    agent_request.cwd = str(ctx["writing_dir"])
    audit.append_event(
        request_id, audit.EVENT_AGENT_DIRECT_PROCESS_STARTED, "story_write",
        details={"stage": 1, "agent": adapter.name},
    )
    try:
        stage1_result = adapter.run(agent_request)
    except Exception as exc:  # noqa: BLE001 — adapter 异常 → failed 信封
        audit.append_event(request_id, audit.EVENT_AGENT_FAILED, "story_write", details={"error": str(exc)[:200]})
        _finish_direct(request_id, status="failed", error=f"上下文选择执行失败：{exc}")
        return
    if _exec_task_manager.is_canceled(request_id):
        return
    if stage1_result.status != "completed":
        audit.append_event(
            request_id,
            audit.EVENT_AGENT_FAILED if stage1_result.status != "cancelled" else audit.EVENT_AGENT_CANCELED,
            "story_write", details={"error": (stage1_result.error or "")[:200]},
        )
        _finish_direct(
            request_id,
            status="failed",
            error=stage1_result.error or f"上下文选择未完成（status={stage1_result.status}）。",
        )
        return
    audit.append_event(request_id, audit.EVENT_AGENT_COMPLETED, "story_write", details={"stage": 1})
    try:
        selection = _parse_selection_result(stage1_result.output)
    except StoryWritingError as exc:
        _finish_direct(request_id, status="failed", error=str(exc))
        return

    # ---------- Stage 2 任务编译（共享：Direct worker 与交互桥阶段验收） ----------
    try:
        compiled = _compile_context_and_stage2(ctx, selection, request_id)
    except StoryWritingError as exc:
        _finish_direct(request_id, status="failed", error=str(exc))
        return

    if _exec_task_manager.is_canceled(request_id):
        return

    # ---------- Stage 2：正文生成（context_ref 绑定编译 Context 快照） ----------
    agent_request.task = compiled["prose_task"]
    audit.append_event(
        request_id, audit.EVENT_AGENT_DIRECT_PROCESS_STARTED, "story_write",
        details={"stage": 2, "agent": adapter.name},
    )
    try:
        stage2_result = adapter.run(agent_request)
    except Exception as exc:  # noqa: BLE001 — adapter 异常 → failed 信封
        audit.append_event(request_id, audit.EVENT_AGENT_FAILED, "story_write", details={"error": str(exc)[:200]})
        _finish_direct(request_id, status="failed", error=f"正文生成执行失败：{exc}")
        return
    if _exec_task_manager.is_canceled(request_id):
        return
    if stage2_result.status != "completed":
        audit.append_event(
            request_id,
            audit.EVENT_AGENT_FAILED if stage2_result.status != "cancelled" else audit.EVENT_AGENT_CANCELED,
            "story_write", details={"error": (stage2_result.error or "")[:200]},
        )
        _finish_direct(
            request_id,
            status="failed",
            error=stage2_result.error or f"正文生成未完成（status={stage2_result.status}）。",
        )
        return
    audit.append_event(request_id, audit.EVENT_AGENT_COMPLETED, "story_write", details={"stage": 2})
    try:
        prose = _parse_prose_result(stage2_result.output, expected_context_ref=compiled["context_fp"])
    except StoryWritingError as exc:
        _finish_direct(request_id, status="failed", error=str(exc))
        return

    # ---------- 候选组装（后台生成 append id；不写正式项目） ----------
    try:
        candidate = _assemble_candidate(ctx, prose, compiled)
    except StoryWritingError as exc:
        _finish_direct(request_id, status="failed", error=str(exc))
        return
    audit.append_event(request_id, audit.EVENT_CANDIDATE_CREATED, "story_write")
    _finish_direct(request_id, status="completed", result=candidate)


def _compile_context_and_stage2(
    ctx: dict[str, Any],
    selection: dict[str, Any],
    request_id: str,
) -> dict[str, Any]:
    """Stage 1 输出 → 知识绑定 + frozen Brief/Context 编译 → Stage 2 任务。

    共享于：Direct worker（阶段间）与交互桥阶段验收（get_story_write_request）。
    失败抛 StoryWritingError；绝不再次执行 KnowledgeRetrieve。
    """
    # ---------- 知识选择绑定（P0：只从精确捕获包选择，绝不再次检索） ----------
    knowledge_needs = list(selection["semantic_interpretation"].get("knowledge_needs") or [])
    selected_refs = list(selection["semantic_interpretation"].get("selected_knowledge_refs") or [])
    package_ref = str(selection["semantic_interpretation"].get("package_ref") or "")
    retrieval = None
    if knowledge_needs:
        query = "；".join(knowledge_needs)
        snapshot, load_error = _load_snapshot(ctx["writing_dir"])
        if load_error:
            raise StoryWritingError(load_error)
        try:
            _validate_snapshot(
                snapshot,
                request_id=request_id,
                project_id=ctx["project_id"],
                writing_turn_id=ctx["writing_turn_id"],
                query=query,
                package_ref=package_ref,
            )
        except StoryWritingError:
            raise
        package = _package_from_snapshot(snapshot)
        retrieval = _bound_package(package, query)
        audit.append_event(
            request_id, audit.EVENT_RETRIEVAL_SELECTED, "knowledge_retrieve",
            details={"query": query, "refs": selected_refs, "package_ref": package_ref},
        )
    elif selected_refs or package_ref:
        raise StoryWritingError("没有知识需求却选择了知识卡或检索包身份，已拒绝。")

    # ---------- frozen Brief / Context 编译（失败 → 无 Stage 2） ----------
    audit.append_event(request_id, audit.EVENT_SKILL_STARTED, "story_write", details={"skill": "StoryWrite"})
    try:
        brief = prepare_creation_brief(
            project_id=ctx["project_id"],
            brief_id=f"write-brief-{ctx['writing_turn_id']}",
            author_input=ctx["author_input"],
            intent=ctx["intent"],
            state=ctx["state"],
            semantic_interpretation=selection["semantic_interpretation"],
        )
        context = prepare_context(
            context_id=f"write-context-{ctx['writing_turn_id']}",
            brief=brief,
            intent=ctx["intent"],
            state=ctx["state"],
            state_selections=selection["state_selections"],
            conflicts_or_tensions=selection.get("conflicts_or_tensions"),
            retrieval=retrieval,
            selected_knowledge_ids=selected_refs,
        )
    except SWContractError as exc:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "story_write", details={"skill": "StoryWrite"})
        raise StoryWritingError(f"Context 被拒绝：{exc}") from exc
    audit.append_event(request_id, audit.EVENT_SKILL_COMPLETED, "story_write", details={"skill": "StoryWrite"})
    audit.append_event(
        request_id, audit.EVENT_CONTEXT_BOUND, "context_compiler",
        details={"context_id": f"write-context-{ctx['writing_turn_id']}", "refs": selected_refs},
    )

    # ---------- recent prose（只读短窗口；第一场无 recent prose 合法） ----------
    recent_prose_section = ""
    if ctx["index_entries"]:
        try:
            recent_prose_window = get_recent_prose(ctx["project_dir"])
        except (PWContractError, PWWorkspaceError) as exc:
            raise StoryWritingError(f"上一段正文衔接数据异常，请重新生成：{exc}") from exc
        recent_prose_section = (
            f"上一段正文（仅供短时连续性参考，不要逐字复写）：\n{recent_prose_window['text']}"
        )

    # ---------- Stage 2 任务（context_ref 绑定编译 Context 快照） ----------
    context_fp = _context_fingerprint(context)
    brief_summary = f"目标：{brief.get('author_input', '')}\n方向：{ctx['work_direction']}"
    prose_task = _PROSE_TASK_TEMPLATE.format(
        context_fingerprint=context_fp,
        brief_summary=brief_summary,
        context_summary=_build_context_summary(context),
        recent_prose_section=recent_prose_section,
        author_input=ctx["author_input"],
    )
    return {
        "brief": brief,
        "context": context,
        "context_fp": context_fp,
        "prose_task": prose_task,
        "recent_prose_section": recent_prose_section,
    }


def _assemble_candidate(
    ctx: dict[str, Any],
    prose: dict[str, Any],
    compiled: dict[str, Any],
) -> dict[str, Any]:
    """后台候选组装：append id 后台生成；replace_existing 必须绑定本轮 Context。"""
    settlement_candidates = []
    for i, cand in enumerate(prose["settlement_candidates"]):
        entry = dict(cand["entry"])
        if cand.get("operation", "append") == "append":
            entry["id"] = f"sw-{ctx['writing_turn_id']}-{i + 1}"
        settlement_candidates.append({
            "classification": cand["classification"],
            "target_area": cand["target_area"],
            "entry": entry,
            "operation": cand.get("operation", "append"),
            "reason": cand.get("reason") or "",
        })
    _validate_replace_existing_in_context(settlement_candidates, compiled["context"])
    return {
        "writing_token": uuid.uuid4().hex,
        "project_id": ctx["project_id"],
        "name": ctx["name"],
        "writing_turn_id": ctx["writing_turn_id"],
        "scene_ref": ctx["scene_ref"],
        "chapter_number": ctx["chapter_number"],
        "draft_text": prose["draft_text"],
        "settlement": {
            "scene_ref": ctx["scene_ref"],
            "candidates": settlement_candidates,
        },
        "source_versions": {
            "intent_rev": ctx["intent"].get("intent_rev"),
            "state_rev": ctx["state"].get("state_rev"),
        },
        "index_fingerprint": ctx["index_fingerprint"],
        "brief": compiled["brief"],
        "context": compiled["context"],
        "context_fingerprint": compiled["context_fp"],
        "execution": dict(ctx["execution"]),
        "message": "正文候选已生成（未写入正式作品，等待你的确认）",
    }


def _start_direct_execution(
    adapter: Any,
    agent_request: Any,
    ctx: dict[str, Any],
    request_id: str,
) -> None:
    """在后台任务管理器启动两阶段 worker；prepare 立即返回。

    竞态兜底：启动失败（另一个 Direct 任务恰好抢到活跃槽）→ 清理本轮临时
    工作区与请求并抛稳定忙碌错误。
    """
    execution = {
        "execution_mode": "direct",
        "agent_id": adapter.name,
        "model": agent_request.custom_model or agent_request.model,
    }
    ctx["execution"] = execution
    worker = lambda: _dispatch_writing_worker(adapter, agent_request, ctx, request_id)  # noqa: E731
    if not _exec_task_manager.start(
        request_id=request_id, worker=worker, adapter=adapter, execution=execution
    ):
        _cleanup_writing(ctx["project_id"], ctx["writing_turn_id"])
        bridge.cleanup_request(request_id)
        raise StoryWritingError(_DIRECT_BUSY_ERROR)


# ---------------------------------------------------------------------------
# 提出正文候选（prepare → 后台执行 → 立即返回）
# ---------------------------------------------------------------------------

def _build_selection_task(
    *,
    name: str,
    intent: dict[str, Any],
    state: dict[str, Any],
    author_input: str,
    request_id: str,
) -> str:
    """构建 Stage 1 上下文选择任务（含 P0 检索命令：显式 --request <request_id>）。"""
    state_summary = _build_state_entries_summary(state)
    return _SELECTION_TASK_TEMPLATE.format(
        name=name,
        work_direction=intent.get("work_direction") or "",
        reader_promise=intent.get("reader_promise") or "",
        hard_constraints=", ".join(intent.get("hard_constraints") or []) or "（暂无）",
        open_space=", ".join(intent.get("open_space") or []) or "（暂无）",
        state_entries_summary=state_summary,
        author_input=author_input,
        retrieval_command=f'"{_RETRIEVAL_SCRIPT}"',
        request_id=request_id,
        max_knowledge_hits=_MAX_KNOWLEDGE_HITS,
    )


def prepare_story_write(project_id: str, author_input: str) -> dict[str, Any]:
    """"这一段想写什么"：按已保存 Settings 执行模式准备本轮任务。

    - Direct：校验配置 → 创建临时 writing 工作区与桥请求 → 启动两阶段后台
      worker → 立即返回 request_id（不阻塞）。
    - Interactive：两阶段交互桥——创建请求（phase=pending_selection，任务 =
      Stage 1 选择任务），作者在 Qoder 执行 /gowrite；验收 Stage 1 后由
      get_story_write_request 原地换成 Stage 2 任务并进入 pending_prose，
      作者再次 /gowrite。绝不回退 Direct、绝不合并为一次 Agent 会话。
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

    # 2. Settings 执行模式（交互桥 / 直连；绝不静默回退）
    settings = SettingsStore().load()
    execution_mode = settings.default_execution_mode
    interactive = execution_mode != EXECUTION_MODE_DIRECT
    if execution_mode not in (EXECUTION_MODE_DIRECT, "interactive_bridge"):
        raise StoryWritingError("未知执行模式，请在设置中重新选择。")

    # 3. Direct：解析配置（复用现有契约；无有效配置 → 稳定报错，绝不回退）
    adapter = None
    agent_request = None
    execution_agent = settings.interactive_agent
    execution_model = None
    if not interactive:
        try:
            adapter, agent_request = agent_runner._build_adapter()
        except AgentRunError as exc:
            raise StoryWritingError(f"直连执行配置不可用：{exc}") from exc
        except Exception as exc:  # noqa: BLE001 — 未知 Agent / registry 异常
            raise StoryWritingError(f"直连执行配置不可用：{exc}") from exc
        execution_agent = adapter.name
        execution_model = agent_request.custom_model or agent_request.model
        # 忙碌保护（与 StoryPlan 共用同一单活跃槽；避免 active 指针竞态）
        if _exec_task_manager.is_busy():
            raise StoryWritingError(_DIRECT_BUSY_ERROR)

    # 4. 清理同一 project 的旧临时候选；创建本轮 writing 工作区
    _cleanup_all_for_project(project_id)
    writing_turn_id = uuid.uuid4().hex[:12]
    writing_dir = _writing_dir(project_id, writing_turn_id)
    writing_dir.mkdir(parents=True, exist_ok=False)

    # 5. index fingerprint + chapter number（不重设计章节路由）
    index_entries = loaded.get("index", {}).get("entries", [])
    index_fingerprint = _index_fingerprint(index_entries)
    chapter_number = index_entries[-1].get("chapter_number", 1) if index_entries else 1

    # 6. scene_ref（后台生成，不由模型决定）
    scene_ref = f"scene-{writing_turn_id}"

    # 7. 预生成 request_id（选择任务需要内嵌真实 id 供检索命令显式绑定）
    request_id = uuid.uuid4().hex

    # 8. 构建 Stage 1 任务（含 P0 检索命令：显式 --request <request_id>）
    selection_task = _build_selection_task(
        name=name, intent=intent, state=state,
        author_input=author_input, request_id=request_id,
    )

    # 9. 创建桥请求（同一请求生命周期；交互桥带阶段标记与更长超时；
    #    Direct 绝不激活 /gowrite）
    try:
        bridge.create_request(
            task=selection_task,
            kind="story_write_propose",
            meta={
                "project_id": project_id,
                "name": name,
                "writing_turn_id": writing_turn_id,
                "author_input": author_input,
                "intent_rev": intent["intent_rev"],
                "state_rev": state["state_rev"],
                "index_fingerprint": index_fingerprint,
                "execution": {
                    "execution_mode": execution_mode,
                    "agent_id": execution_agent,
                    "model": execution_model,
                },
            },
            request_id=request_id,
            phase=PHASE_PENDING_SELECTION if interactive else None,
            timeout_seconds=_INTERACTIVE_TIMEOUT_SECONDS if interactive else None,
            activate_for_gowrite=interactive,
        )
    except bridge.BridgeBusyError as exc:
        # 已有等待 /gowrite 的交互任务：绝不清除/覆盖它；回滚本轮临时工作区
        _cleanup_writing(project_id, writing_turn_id)
        raise StoryWritingError(str(exc)) from exc

    # 10. 验证式审计（operation.started；交互桥只标 waiting，绝不声称 Agent 已启动）
    execution_facts = {
        "execution_mode": execution_mode,
        "agent_id": execution_agent,
        "model": execution_model,
    }
    recorder = audit.AuditRecorder(
        request_id, "story_write", project_id, execution=execution_facts,
    )
    if interactive:
        recorder.event(audit.EVENT_BRIDGE_WAITING, component="story_write")

    # 11. Direct：后台启动两阶段 worker（prepare 立即返回，不阻塞）
    ctx = {
        "project_id": project_id,
        "name": name,
        "writing_turn_id": writing_turn_id,
        "writing_dir": writing_dir,
        "project_dir": proj["project_dir"],
        "intent": intent,
        "state": state,
        "work_direction": intent.get("work_direction") or "",
        "author_input": author_input,
        "index_entries": index_entries,
        "index_fingerprint": index_fingerprint,
        "chapter_number": chapter_number,
        "scene_ref": scene_ref,
        "selection_task": selection_task,
        "execution": execution_facts,
    }
    if interactive:
        message = "等待 Qoder /gowrite：正在选择本次写作上下文"
        # 交互桥两阶段都由 get_story_write_request 驱动：把 prepare 时刻的
        # 上下文快照（intent/state 等）持久化到临时写作工作区，供阶段验收使用。
        # 与 Direct worker 闭包持有同一份 ctx 语义（prepare 时刻快照）。
        # Path 统一转 str（默认参数覆盖所有不可序列化对象）。
        (writing_dir / "ctx.json").write_text(
            json.dumps(ctx, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
    else:
        message = "任务已通过直连模式后台执行，正在校验结果。"
        _start_direct_execution(adapter, agent_request, ctx, request_id)

    return {
        "request_id": request_id,
        "project_id": project_id,
        "name": name,
        "status": "task_prepared",
        "execution_mode": execution_mode,
        "phase": PHASE_PENDING_SELECTION if interactive else None,
        "agent_id": execution_agent,
        "model": execution_model,
        "message": message,
    }


def get_story_write_request(request_id: str) -> dict[str, Any]:
    """轮询执行结果（UI 每 2-3 秒调用一次）。

    - Direct：读 worker 写回的响应 → 候选；
    - Interactive：两阶段交互桥（同一请求生命周期，无第二个前端 API）：
        phase=pending_selection：等待第一次 /gowrite（Stage 1 选择）；收到后
        验收 → 编译精确 Context → 请求原地换成 Stage 2 任务 → pending_prose；
        phase=pending_prose：等待第二次 /gowrite（正文生成）；收到后校验
        context_ref → 候选。
    返回 status：pending（继续等；含 phase 与作者可读提示）/ completed（含候选）
    / failed / expired / canceled。completed 时持久化 writing_meta.json
    （confirm 只读它，前端不可替换）。
    """
    request_id = (request_id or "").strip()
    if not request_id:
        raise StoryWritingError("缺少任务标识（request_id）。")

    request = bridge.get_request(request_id)
    if request is None:
        audit.finish_file(request_id, audit.STATUS_FAILED, error="任务已失效，请重新发起。")
        return {"request_id": request_id, "status": "failed", "error": "任务已失效，请重新发起。"}

    state = request.get("state")
    meta = request.get("meta") or {}
    project_id = str(meta.get("project_id") or "")
    writing_turn_id = str(meta.get("writing_turn_id") or "")
    phase = request.get("phase")

    if state == "canceled":
        bridge.cleanup_request(request_id)
        _exec_task_manager.remove(request_id)
        audit.finish_file(request_id, audit.STATUS_CANCELED)
        return {"request_id": request_id, "status": "canceled"}
    if state == "completed":
        bridge.cleanup_request(request_id)
        _exec_task_manager.remove(request_id)
        return {"request_id": request_id, "status": "completed", "error": None}
    if state == "failed":
        bridge.cleanup_request(request_id)
        _exec_task_manager.remove(request_id)
        audit.finish_file(
            request_id, audit.STATUS_FAILED, error=request.get("error") or "任务失败，请重新发起。",
        )
        return {
            "request_id": request_id,
            "status": "failed",
            "error": request.get("error") or "任务失败，请重新发起。",
        }

    # pending：先查超时，再查 response
    if bridge.is_expired(request):
        if project_id and writing_turn_id:
            _cleanup_writing(project_id, writing_turn_id)
        _exec_task_manager.cancel(request_id)
        _exec_task_manager.remove(request_id)
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error="任务已超时，请重新发起。")
        return {"request_id": request_id, "status": "expired", "error": "任务已超时，请重新发起。"}

    # 交互桥两阶段：分阶段验收（Direct 无 phase 标记，走下方原路径）
    if phase in (PHASE_PENDING_SELECTION, PHASE_PENDING_PROSE):
        return _get_interactive_story_write_request(request, request_id, phase)

    # ---------------- Direct：读 worker 写回的响应 ----------------
    response = bridge.read_response(request_id)
    if response is None:
        return {"request_id": request_id, "status": "pending"}

    if response.get("request_id") != request_id:
        bridge.cleanup_request(request_id)
        _exec_task_manager.remove(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error="返回结果与任务不匹配，已丢弃。")
        return {"request_id": request_id, "status": "failed", "error": "返回结果与任务不匹配，已丢弃。"}

    resp_status = response.get("status")
    if resp_status != "completed":
        error = response.get("error") or f"执行结果状态异常：{resp_status}"
        if project_id and writing_turn_id:
            _cleanup_writing(project_id, writing_turn_id)
        bridge.cleanup_request(request_id)
        _exec_task_manager.remove(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error=error)
        return {"request_id": request_id, "status": "failed", "error": error}

    payload = response.get("result")
    if not isinstance(payload, dict) or not payload.get("writing_token") or not payload.get("draft_text"):
        if project_id and writing_turn_id:
            _cleanup_writing(project_id, writing_turn_id)
        bridge.cleanup_request(request_id)
        _exec_task_manager.remove(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error="候选数据无效，请重新发起。")
        return {"request_id": request_id, "status": "failed", "error": "候选数据无效，请重新发起。"}

    # 持久化候选元数据（后端保存的唯一权威版本；confirm 只读它，前端不可替换）。
    # request_id 一并写入，使"不用了/换一种"能通过 cancel_story_write_request 定位
    # 已完成但未确认的候选并清理工作区（writing token 随之失效）。
    writing_dir = _writing_dir(project_id, writing_turn_id)
    writing_dir.mkdir(parents=True, exist_ok=True)
    meta_payload = dict(payload)
    meta_payload["request_id"] = request_id
    (writing_dir / "writing_meta.json").write_text(
        json.dumps(meta_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    bridge.cleanup_request(request_id)
    _exec_task_manager.remove(request_id)
    # 候选生成 ≠ 操作完成：记录保持打开（awaiting_confirmation），
    # 等作者 Confirm（authority.confirmed → completed）或 Discard/Cancel（canceled）。
    audit.mark_awaiting_confirmation(request_id)
    return {
        "request_id": request_id,
        "status": "completed",
        "result": {
            "writing_token": payload["writing_token"],
            "project_id": payload["project_id"],
            "name": payload["name"],
            "scene_ref": payload["scene_ref"],
            "chapter_number": payload["chapter_number"],
            "draft_text": payload["draft_text"],
            "execution": payload.get("execution") or {},
            "message": payload.get("message") or "正文候选已生成（未写入正式作品，等待你的确认）",
        },
    }


def _get_interactive_story_write_request(
    request: dict[str, Any], request_id: str, phase: str
) -> dict[str, Any]:
    """交互桥阶段验收（在 get_story_write_request 轮询内执行；同一生命周期）。

    - pending_selection：验收 Stage 1 选择 → P0 绑定 + 编译精确 Context →
      请求文件换成 Stage 2 任务 → 返回 pending_prose 提示再次 /gowrite；
    - pending_prose：验收 Stage 2 正文 → context_ref 校验 → 候选。
    晚到/重复/不匹配响应一律丢弃且不推进阶段；任一阶段取消都使整轮失效。
    """
    meta = request.get("meta") or {}
    project_id = str(meta.get("project_id") or "")
    writing_turn_id = str(meta.get("writing_turn_id") or "")
    writing_dir = _writing_dir(project_id, writing_turn_id)

    response = bridge.read_response(request_id)
    if response is None:
        if phase == PHASE_PENDING_SELECTION:
            return {
                "request_id": request_id, "status": "pending", "phase": phase,
                "message": "等待 Qoder /gowrite：正在选择本次写作上下文",
            }
        return {
            "request_id": request_id, "status": "pending", "phase": phase,
            "message": "上下文已准备好，请再次执行 /gowrite 生成正文",
        }

    if response.get("request_id") != request_id:
        audit.append_event(
            request_id, audit.EVENT_BRIDGE_RESPONSE_DISCARDED, "story_write",
            details={"reason": "request_id mismatch"},
        )
        bridge.clear_response(request_id)
        return {
            "request_id": request_id, "status": "pending", "phase": phase,
            "message": "检测到不匹配的返回结果，已丢弃，请重试 /gowrite。",
        }

    resp_status = response.get("status")
    if resp_status != "completed":
        error = response.get("error") or f"执行结果状态异常：{resp_status}"
        audit.append_event(
            request_id, audit.EVENT_AGENT_FAILED, "story_write",
            details={"error": error[:200]},
        )
        if project_id and writing_turn_id:
            _cleanup_writing(project_id, writing_turn_id)
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error=error)
        return {"request_id": request_id, "status": "failed", "error": error}

    audit.append_event(
        request_id, audit.EVENT_BRIDGE_RESPONSE_RECEIVED, "story_write",
        details={"phase": phase},
    )
    # 结构化 result 优先；纯文本 output 兜底（形状歧义由桥集中消除：
    # output 为对象等畸形信封已被 read_response 转为失败信封）
    try:
        output = bridge.response_result_text(response)
    except bridge.BridgeProtocolError as exc:
        error = f"执行结果状态异常：{exc}"
        audit.append_event(
            request_id, audit.EVENT_AGENT_FAILED, "story_write",
            details={"error": error[:200]},
        )
        if project_id and writing_turn_id:
            _cleanup_writing(project_id, writing_turn_id)
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error=error)
        return {"request_id": request_id, "status": "failed", "error": error}

    # 读取 prepare 时刻的 ctx 快照（缺失 → 整轮失效）
    ctx_path = writing_dir / "ctx.json"
    try:
        ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
        # JSON 往返把 Path 序列化为 str：恢复为 Path（与 Direct worker 闭包一致）
        ctx["writing_dir"] = Path(ctx["writing_dir"])
        ctx["project_dir"] = Path(ctx["project_dir"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        error = "写作工作区数据缺失，请重新发起。"
        _cleanup_writing(project_id, writing_turn_id)
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error=error)
        return {"request_id": request_id, "status": "failed", "error": error}

    if phase == PHASE_PENDING_SELECTION:
        # ---- Stage 1 验收：选择 → 绑定 → 编译精确 Context → 换 Stage 2 任务 ----
        try:
            selection = _parse_selection_result(output)
            compiled = _compile_context_and_stage2(ctx, selection, request_id)
        except StoryWritingError as exc:
            _cleanup_writing(project_id, writing_turn_id)
            bridge.cleanup_request(request_id)
            audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
            return {"request_id": request_id, "status": "failed", "error": str(exc)}

        # 持久化阶段 1 产物（Stage 2 验收使用；request 文件保持小）
        (writing_dir / "stage1.json").write_text(json.dumps({
            "context_fp": compiled["context_fp"],
            "selection": selection,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        (writing_dir / "brief.json").write_text(
            json.dumps(compiled["brief"], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (writing_dir / "context.json").write_text(
            json.dumps(compiled["context"], ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # 请求原地换成 Stage 2 任务（fresh Agent invocation；绝不含未选中 State）
        if not bridge.set_request_task(
            request_id, compiled["prose_task"], phase=PHASE_PENDING_PROSE
        ):
            # 请求已被取消/终态：晚到 Stage 1 响应不得推进
            audit.append_event(
                request_id, audit.EVENT_BRIDGE_RESPONSE_DISCARDED, "story_write",
                details={"reason": "stale phase-1 response after cancel/terminal"},
            )
            audit.finish_file(request_id, audit.STATUS_CANCELED)
            return {"request_id": request_id, "status": "canceled"}
        bridge.clear_response(request_id)
        return {
            "request_id": request_id, "status": "pending", "phase": PHASE_PENDING_PROSE,
            "message": "上下文已准备好，请再次执行 /gowrite 生成正文",
        }

    # ---- Stage 2 验收：正文生成 → 候选 ----
    try:
        stage1 = json.loads((writing_dir / "stage1.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        error = "第一阶段数据缺失，请重新发起。"
        _cleanup_writing(project_id, writing_turn_id)
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error=error)
        return {"request_id": request_id, "status": "failed", "error": error}

    try:
        prose = _parse_prose_result(output, expected_context_ref=stage1["context_fp"])
    except StoryWritingError as exc:
        if '"semantic_interpretation"' in (output or "") and "context_ref" in str(exc):
            # 晚到的第一阶段结果（Qoder 在阶段切换竞态中重跑了旧任务）
            audit.append_event(
                request_id, audit.EVENT_BRIDGE_RESPONSE_DISCARDED, "story_write",
                details={"reason": "stage-1 result arrived during stage-2"},
            )
            bridge.clear_response(request_id)
            return {
                "request_id": request_id, "status": "pending", "phase": phase,
                "message": "收到的是第一阶段的结果，请再次执行 /gowrite 生成正文",
            }
        _cleanup_writing(project_id, writing_turn_id)
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
        return {"request_id": request_id, "status": "failed", "error": str(exc)}

    compiled = {
        "brief": json.loads((writing_dir / "brief.json").read_text(encoding="utf-8")),
        "context": json.loads((writing_dir / "context.json").read_text(encoding="utf-8")),
        "context_fp": stage1["context_fp"],
    }
    try:
        candidate = _assemble_candidate(ctx, prose, compiled)
    except StoryWritingError as exc:
        _cleanup_writing(project_id, writing_turn_id)
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
        return {"request_id": request_id, "status": "failed", "error": str(exc)}

    audit.append_event(request_id, audit.EVENT_CANDIDATE_CREATED, "story_write")
    # 持久化候选元数据（与 Direct 同一权威版本；confirm 只读它）
    writing_dir.mkdir(parents=True, exist_ok=True)
    meta_payload = dict(candidate)
    meta_payload["request_id"] = request_id
    (writing_dir / "writing_meta.json").write_text(
        json.dumps(meta_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    bridge.cleanup_request(request_id)
    _exec_task_manager.remove(request_id)
    # 候选生成 ≠ 操作完成：记录保持打开（awaiting_confirmation），
    # 等作者 Confirm（authority.confirmed → completed）或 Discard/Cancel（canceled）。
    audit.mark_awaiting_confirmation(request_id)
    return {
        "request_id": request_id,
        "status": "completed",
        "result": {
            "writing_token": candidate["writing_token"],
            "project_id": candidate["project_id"],
            "name": candidate["name"],
            "scene_ref": candidate["scene_ref"],
            "chapter_number": candidate["chapter_number"],
            "draft_text": candidate["draft_text"],
            "execution": candidate.get("execution") or {},
            "message": candidate.get("message") or "正文候选已生成（未写入正式作品，等待你的确认）",
        },
    }


def _cleanup_discarded_candidate(request_id: str) -> None:
    """丢弃已完成但未确认的候选：按 writing_meta.json 中持久化的 request_id 定位
    并删除其临时 writing 工作区（writing token 随之失效，confirm 将拒绝）。

    只清理临时工作区（06_工作区/应用开发/.writing），绝不触碰正式 Story State
    或 03_正文。request_id 无匹配时静默（幂等）。
    """
    root = get_writing_root()
    if not root.exists():
        return
    for meta_file in root.glob("*/*/writing_meta.json"):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if meta.get("request_id") != request_id:
            continue
        project_id = str(meta.get("project_id") or "")
        writing_turn_id = str(meta.get("writing_turn_id") or "")
        if project_id and writing_turn_id:
            _cleanup_writing(project_id, writing_turn_id)
        else:
            shutil.rmtree(meta_file.parent, ignore_errors=True)
        return


def cancel_story_write_request(request_id: str) -> dict[str, Any]:
    """取消/丢弃：终止运行中的 Direct adapter（如有）、标记 canceled、
    删除临时 writing 工作区。幂等。

    - 运行中：取消 adapter，晚完成结果丢弃，工作区清理；
    - 已完成但未确认（请求文件已被 get_story_write_request 终态清理）：
      通过 writing_meta.json 定位工作区并删除 → writing token 失效；
    - 绝不触碰正式 Story State 或 accepted prose。
    """
    request_id = (request_id or "").strip()
    if not request_id:
        raise StoryWritingError("缺少任务标识（request_id）。")

    # Direct：先请求任务管理器取消运行中的 adapter（幂等；无任务时 no-op）
    _exec_task_manager.cancel(request_id)

    request = bridge.get_request(request_id)
    if request is not None:
        bridge.mark_canceled(request_id)
        meta = request.get("meta") or {}
        project_id = str(meta.get("project_id") or "")
        writing_turn_id = str(meta.get("writing_turn_id") or "")
        if project_id and writing_turn_id:
            _cleanup_writing(project_id, writing_turn_id)
        bridge.clear_active_if(request_id)
        audit.finish_file(request_id, audit.STATUS_CANCELED)
    else:
        # 请求文件已不存在（已完成并轮询过 / 已取消过）：按持久化 request_id
        # 清理已完成但未确认的候选工作区（幂等；无匹配时静默）。
        _cleanup_discarded_candidate(request_id)
        # 审计记录（awaiting_confirmation）收尾为 canceled
        audit.finish_file(request_id, audit.STATUS_CANCELED)
    _exec_task_manager.remove(request_id)
    return {"request_id": request_id, "status": "canceled"}


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

    # 4. frozen context_package_is_stale 检查（ContextCompiler 实际 runtime 调用点）
    request_id = str(meta.get("request_id") or "")
    audit.append_event(
        request_id, audit.EVENT_SKILL_STARTED, "context_compiler", details={"skill": "ContextCompiler"},
    )
    is_stale = context_package_is_stale(saved_context, saved_brief, current_intent, current_state)
    audit.append_event(
        request_id, audit.EVENT_SKILL_COMPLETED, "context_compiler",
        details={"skill": "ContextCompiler", "stale": bool(is_stale)},
    )
    if is_stale:
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

    # 7. 清理临时写作工作区；审计 authority.confirmed
    _cleanup_writing(project_id, writing_turn_id)
    audit.append_event(
        request_id, audit.EVENT_AUTHORITY_CONFIRMED, "story_write",
        details={"scene_ref": scene_ref, "chapter_number": chapter_number},
    )
    audit.finish_file(request_id, audit.STATUS_COMPLETED)

    return {
        "project_id": project_id,
        "name": loaded["name"],
        "chapter_path": result.get("chapter_path"),
        "chapter_number": chapter_number,
        "scene_ref": scene_ref,
        "message": "这段已经保留下来了。",
    }


# ---------------------------------------------------------------------------
# 只读：正式写作面（WritingPage accepted-prose read model）
# ---------------------------------------------------------------------------
# 数据源：03_作品工程/<project>/03_正文 + accepted_text_index（唯一权威）。
# - 绝不返回临时候选（writing_meta.json / retrieval 快照在 06_工作区，不读）；
# - 只读取 accepted index 引用的章节路径，且每个路径必须落在本项目 03_正文 下；
# - 对每条 entry 做 start/end 边界与 content_sha256 校验（index 漂移 → 显式报错，
#   不静默展示错误正文）；
# - 无任何写副作用。

def _validate_surface_chapter_path(chapter_path_str: Any, project_dir: Path) -> Path:
    """校验 accepted index 中的章节路径必须落在 <project_dir>/03_正文/ 下。

    仅做路径包含校验（frozen ProjectWorkspace._validate_chapter_path 的等价守卫），
    不复制其业务规则；非法路径直接拒绝，绝不返回给前端。
    """
    if not isinstance(chapter_path_str, str) or not chapter_path_str.strip():
        raise StoryWritingError("accepted_text_index 章节路径缺失或非法。")
    chapter_path_str = chapter_path_str.strip()
    if Path(chapter_path_str).is_absolute() or ".." in chapter_path_str:
        raise StoryWritingError(f"accepted_text_index 章节路径非法（绝对路径或含 ..）：{chapter_path_str}")
    prose_root = (project_dir / "03_正文").resolve()
    full = (project_dir / chapter_path_str).resolve()
    try:
        full.relative_to(prose_root)
    except ValueError:
        raise StoryWritingError(f"accepted_text_index 章节路径不在 03_正文/ 下：{chapter_path_str}")
    return full


def get_story_write_surface(project_id: str) -> dict[str, Any]:
    """WritingPage 正式写作面：只读返回已采用正文（按章分组，按 chapter_number 排序）。

    - 无已接受正文 → 返回一个空的第一章视图（chapter 1 / 空内容 / 0 字）；
    - active_chapter_number = 最新已接受章节号，否则 1；
    - words / total_words = 本读模型实际返回正文的长度（len，非估算）；
    - scene_count = 该章 accepted_text_index entry 数。
    """
    project_id = (project_id or "").strip()
    if not project_id:
        raise StoryWritingError("缺少作品标识（project_id）。")

    try:
        proj = resolve_project(project_id)
        loaded = load_project(proj["project_dir"])
    except (PWContractError, PWWorkspaceError) as exc:
        raise StoryWritingError(str(exc)) from exc

    project_dir = Path(loaded["project_dir"])
    index = loaded.get("index") or {}
    entries = index.get("entries") or []

    if not entries:
        return {
            "project_id": loaded["project_id"],
            "name": loaded["name"],
            "chapters": [{
                "chapter_number": 1,
                "title": "第1章",
                "content": "",
                "words": 0,
                "scene_count": 0,
            }],
            "active_chapter_number": 1,
            "total_words": 0,
        }

    # 按章分组（chapter_number 缺失/非法 → 显式报错，不猜测）
    by_chapter: dict[int, list[dict[str, Any]]] = {}
    for entry in entries:
        try:
            chapter_number = int(entry.get("chapter_number") or 0)
        except (TypeError, ValueError):
            raise StoryWritingError("accepted_text_index 存在非法 chapter_number。")
        if chapter_number < 1:
            raise StoryWritingError("accepted_text_index 存在非法 chapter_number。")
        by_chapter.setdefault(chapter_number, []).append(entry)

    chapters: list[dict[str, Any]] = []
    for chapter_number in sorted(by_chapter):
        chapter_entries = by_chapter[chapter_number]
        # 同章所有 entry 必须指向同一合法章节路径
        chapter_paths = {
            _validate_surface_chapter_path(entry.get("chapter_path"), project_dir)
            for entry in chapter_entries
        }
        if len(chapter_paths) != 1:
            raise StoryWritingError(
                f"第{chapter_number}章的 accepted_text_index 章节路径不一致，请检查。"
            )
        chapter_path = chapter_paths.pop()
        if not chapter_path.exists():
            raise StoryWritingError(f"章节文件不存在：{chapter_path}")
        content = chapter_path.read_text(encoding="utf-8")
        # 逐条 entry 校验边界与 SHA（index 漂移 → 显式报错）
        for entry in chapter_entries:
            try:
                start = int(entry.get("start_char") or 0)
                end = int(entry.get("end_char") or 0)
            except (TypeError, ValueError):
                raise StoryWritingError(
                    f"第{chapter_number}章 accepted_text_index 存在非法字符区间。"
                )
            if start < 0 or end < start or end > len(content):
                raise StoryWritingError(
                    f"第{chapter_number}章 accepted_text_index 与正文不一致（越界）。"
                )
            segment = content[start:end]
            if hashlib.sha256(segment.encode("utf-8")).hexdigest() != entry.get("content_sha256"):
                raise StoryWritingError(
                    f"第{chapter_number}章 accepted_text_index 与正文不一致（SHA 不匹配）。"
                )
        chapters.append({
            "chapter_number": chapter_number,
            "title": f"第{chapter_number}章",
            "content": content,
            "words": len(content),
            "scene_count": len(chapter_entries),
        })

    return {
        "project_id": loaded["project_id"],
        "name": loaded["name"],
        "chapters": chapters,
        "active_chapter_number": max(by_chapter),
        "total_words": sum(chapter["words"] for chapter in chapters),
    }
