# -*- coding: utf-8 -*-
"""M3 知识驱动重大基座设计（KNOWLEDGE_GROUNDED_FOUNDATION_DESIGN）垂直切片。

合同（长期开发手册 §15.5 / §16，不重复既有规则）：
  作者初始想法 → Agent 分解重大基座问题 → 按主题多轮 KnowledgeRetrieve
  （每轮只取少量高价值 reference_bkp / method_source / validated_knowledge）
  → Agent 比较来源 / scope / boundary / counterevidence → 综合基座提案
  → 作者选择/编辑 → 明确确认 → Code 校验并写回同一项目 authority。

复用既有合同，绝不新建平行 authority / 检索 / 任务 runtime：
- 请求生命周期：qoder_bridge（kind=foundation_design_propose）+
  execution_tasks 单活跃槽 + agent_runner Direct 路由（与 StoryPlan/
  StoryWrite/NewProject 同一套 Interactive/Direct 双模式）；
- 检索：story_planning 的 P0 精确绑定件（_retrieve_package / 快照 /
  指纹 / 绑定），retrieval_snapshot.py 按 kind 分派到本模块的
  execute_request_scoped_retrieval；每轮一个请求级快照（多轮 = 多个快照），
  finalize 绝不再次检索；
- 候选：06_工作区/应用开发/.foundation_proposals（Local Only，可删除），
  proposal_noncanonical，确认前零 authority 写；
- 写回：author_edit.create_foundation_record / create_relationship
  （author fields、base_model_rev stale 守卫、change_history、项目写锁），
  语义需要时进入既有 change_settlement 路径。

0 个知识命中仍合法；知识仅 advisory，不能压过作者明确意图。
"""
from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Optional

from config.settings import EXECUTION_MODE_DIRECT, SettingsStore
from operations import agent_runner
from operations import author_edit
from operations import change_settlement
from operations import execution_audit as audit
from operations import execution_tasks
from operations import project_model
from operations import qoder_bridge as bridge
from operations.agent_runner import AgentRunError
from operations.project_snapshot import get_project_snapshot
from operations.story_planning import (
    _DIRECT_BUSY_ERROR,
    _MAX_KNOWLEDGE_HITS,
    _package_fingerprint,
    _package_snapshot_dict,
    _retrieve_package,
)

# Direct 执行任务管理器（与 StoryPlan/StoryWrite/Review/NewProject 共用单活跃槽）
_exec_task_manager = execution_tasks.manager

_REPO_ROOT = Path(__file__).resolve().parents[3]

# 临时候选工作区根（06_工作区/应用开发 已 gitignore，Local Only，可删除）
_PROPOSALS_ROOT = _REPO_ROOT / "06_工作区" / "应用开发" / ".foundation_proposals"

# 请求级检索快照 CLI（Agent 在执行内按主题多轮运行；唯一确定性检索入口）
_RETRIEVAL_SCRIPT = Path(__file__).resolve().parent / "retrieval_snapshot.py"

# 单次基座设计的检索轮数上限（有界多轮；每轮仍限 _MAX_KNOWLEDGE_HITS 条）
_MAX_ROUNDS = 4

_ALLOWED_ITEM_KINDS = {
    "character", "relationship", "world_setting", "organization",
    "story_line", "core_conflict",
}
_CATEGORY_BY_KIND = {
    "character": "character",
    "world_setting": "world_setting",
    "organization": "organization_force",
    "story_line": "story_line",
    "core_conflict": "world_setting",
}

_AGENT_TASK_TEMPLATE = """你是 Go Write 的基座设计执行器（重大新书/基座设计，Agent 主导）。必须严格按下列顺序执行；本任务不是纯文本生成任务，中间的工具调用属于任务执行过程，不属于最终回复。

第一阶段：分解基座问题
针对作者请求与当前作品 authority，分解出 2 到 {max_rounds} 个具体的基座问题/主题（例如人物结构、关系动力、世界规则、冲突体系、故事线架构等；不要套用固定分类表，主题必须来自本次请求与作品现状）。

第二阶段：按主题多轮检索（每个主题一轮，必须执行）
对每个主题，在生成最终 JSON 之前，用可用的本地命令/工具执行下列确定性只读检索命令（<query> 为该主题的具体检索问题）：
  python {retrieval_command} --request {request_id} "<query>"
每轮命令输出一个小型混合检索包（reference_bkp / method_source / validated_knowledge）与 package_fingerprint；你必须读取实际输出：
- 只从该轮输出中选择 0 到 {max_knowledge_hits} 个 selection_ref 填入该轮 selected_knowledge_refs；
- 把该轮输出的 package_fingerprint 原样填入该轮 package_ref；
- 在 comparison 中比较本轮（及与前几轮）来源的 scope、boundary 与 counterevidence；
- 没有合适候选时 selected_knowledge_refs 保持 []，0 命中合法；
- 严禁编造输出中不存在的 selection_ref / package_fingerprint；检索轮数不得超过 {max_rounds}。

第三阶段：综合基座提案
结合作者请求、当前作品 authority 与全部检索轮，综合人物/关系/世界规则/组织体系/核心冲突/故事线提案。知识仅 advisory：不得让外部知识压过作者明确意图；来源的 scope/boundary 必须在 knowledge_notes 中向作者交代。

最终回复必须只有合法 JSON 对象（不要任何额外文字、不要 markdown 代码块标记）。结构必须如下：

{{
  "objective": "本次基座设计目标（一句话）",
  "topics": ["主题1", "主题2"],
  "rounds": [
    {{
      "topic": "主题1",
      "query": "与检索命令完全相同的 <query>",
      "package_ref": "该轮命令输出的 package_fingerprint",
      "selected_knowledge_refs": [],
      "comparison": "来源/scope/boundary/counterevidence 比较（作者可读）"
    }}
  ],
  "proposal": {{
    "characters": [{{"title": "人物名", "summary": "作者可读设定", "material_state": "future"}}],
    "relationships": [{{"source_title": "人物名", "target_title": "人物名", "label": "关系", "summary": "作者可读关系设定"}}],
    "world_settings": [{{"title": "规则名", "summary": "作者可读规则", "material_state": "future"}}],
    "organizations": [{{"title": "组织/体系名", "summary": "作者可读设定", "material_state": "future"}}],
    "core_conflict": {{"title": "核心冲突", "summary": "作者可读冲突设定"}},
    "story_lines": [{{"title": "故事线", "summary": "作者可读故事线", "material_state": "future"}}]
  }},
  "knowledge_notes": "参考了哪些知识、scope/boundary、未采用什么（作者可读）",
  "assumptions": ["AI 解读中的假设，作者尚未确认"]
}}

当前作品 authority（只读事实，绝不是可覆盖对象）：
{authority_view}

作者基座设计请求：{author_request}

最终回复必须只有合法 JSON；但在生成最终回复之前，你必须先按主题执行检索命令并读取结果。"""


class FoundationDesignError(Exception):
    """基座设计操作错误（面向 UI 的稳定错误类型，普通用户可读）。"""


def get_proposals_root() -> Path:
    """临时基座设计候选工作区根目录（测试可 monkeypatch 此函数）。"""
    return _PROPOSALS_ROOT


def _proposal_dir(project_id: str) -> Path:
    return get_proposals_root() / project_id


def _cleanup_proposal(project_id: str) -> None:
    shutil.rmtree(_proposal_dir(project_id), ignore_errors=True)


# ---------------------------------------------------------------------------
# 多轮请求级检索快照（P0 精确绑定；每轮一个快照，finalize 绝不再次检索）
# ---------------------------------------------------------------------------

def _round_key(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]


def _round_path(proposal_dir: Path, query: str) -> Path:
    return proposal_dir / "retrieval" / f"round-{_round_key(query)}.json"


def execute_request_scoped_retrieval(query: str, request_id: str) -> Any:
    """Agent 侧（执行内）按主题运行的确定性检索调用（显式绑定 request_id）。

    多轮 = 同一请求下多个 round 快照；轮数有界（_MAX_ROUNDS）。
    """
    query = (query or "").strip()
    if not query:
        raise FoundationDesignError("检索查询不能为空。")
    request = bridge.get_request(request_id)
    if request is None or request.get("kind") != "foundation_design_propose":
        raise FoundationDesignError("任务文件不存在或类型不匹配，无法生成检索快照。")
    meta = request.get("meta") or {}
    project_id = str(meta.get("project_id") or "")
    design_turn_id = str(meta.get("design_turn_id") or "")
    if not project_id or not design_turn_id:
        raise FoundationDesignError("任务缺少 project_id / design_turn_id 元数据。")
    proposal_dir = _proposal_dir(project_id)
    retrieval_dir = proposal_dir / "retrieval"
    existing = list(retrieval_dir.glob("round-*.json")) if retrieval_dir.exists() else []
    if len(existing) >= _MAX_ROUNDS and not _round_path(proposal_dir, query).exists():
        raise FoundationDesignError(f"检索轮数超过上限（{_MAX_ROUNDS}），已拒绝。")
    audit.append_event(
        request_id, audit.EVENT_RETRIEVAL_REQUESTED, "knowledge_retrieve",
        details={"query": query[:200], "round": len(existing) + 1},
    )
    try:
        package = _retrieve_package(query)  # 唯一一次 KnowledgeRetrieve 执行/轮
    except FoundationDesignError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise FoundationDesignError(f"知识检索失败：{exc}") from exc
    snapshot = {
        "schema": "gowrite_retrieval_snapshot/v2",
        "round": True,
        "request_id": request_id,
        "project_id": project_id,
        "design_turn_id": design_turn_id,
        "query": query,
        "package_fingerprint": _package_fingerprint(package),
        "package": _package_snapshot_dict(package),
    }
    path = _round_path(proposal_dir, query)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    audit.append_event(
        request_id, audit.EVENT_RETRIEVAL_PACKAGE_BUILT, "knowledge_retrieve",
        details={
            "query": query[:200],
            "candidate_count": getattr(package, "candidate_count", len(getattr(package, "hits", []))),
            "source_kinds": sorted({
                getattr(hit, "source_kind", "") for hit in getattr(package, "hits", [])
            }),
        },
    )
    return package


def _validate_round(proposal_dir: Path, round_item: dict[str, Any], *, request_id: str, project_id: str, design_turn_id: str) -> list[str]:
    """校验一轮：快照身份 + 指纹一致 + selected refs 必须来自捕获包。"""
    query = str(round_item.get("query") or "").strip()
    path = _round_path(proposal_dir, query)
    if not path.exists():
        raise FoundationDesignError("该主题未在本轮执行内生成检索快照，已拒绝。")
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise FoundationDesignError("检索包快照无法解析（已被篡改或损坏）。")
    if snapshot.get("request_id") != request_id or snapshot.get("project_id") != project_id:
        raise FoundationDesignError("检索包快照身份与当前任务不一致，已拒绝。")
    if snapshot.get("design_turn_id") != design_turn_id:
        raise FoundationDesignError("检索包快照 design_turn_id 与当前任务不一致，已拒绝。")
    package_ref = str(round_item.get("package_ref") or "")
    if not package_ref or snapshot.get("package_fingerprint") != package_ref:
        raise FoundationDesignError("Agent 选择的检索包身份（package_ref）与绑定快照不一致，已拒绝。")
    captured = {
        str(hit.get("selection_ref") or "") for hit in (snapshot.get("package") or {}).get("hits", [])
    }
    selected = list(round_item.get("selected_knowledge_refs") or [])
    if len(selected) > _MAX_KNOWLEDGE_HITS:
        raise FoundationDesignError(f"单轮知识选择超过上限（{_MAX_KNOWLEDGE_HITS}），已拒绝。")
    for ref in selected:
        if ref not in captured:
            raise FoundationDesignError("Agent 选择了检索包中不存在的 selection_ref，已拒绝。")
    return selected


# ---------------------------------------------------------------------------
# 当前 authority 的紧凑只读视图（嵌入 Agent 任务；绝不包含检索库内容）
# ---------------------------------------------------------------------------

def _authority_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    def titles(bucket: str, key: str, limit: int) -> list[str]:
        return [str(item.get("title") or "") for item in (snapshot[bucket].get(key) or [])][:limit]

    relationships = [
        {"title": str(item.get("title") or ""), "label": str((item.get("record") or {}).get("label") or "")}
        for item in (snapshot["current"].get("relationships") or [])
    ][:12]
    return {
        "name": snapshot.get("name") or "",
        "work_direction": snapshot.get("work_direction") or "",
        "reader_promise": snapshot.get("reader_promise") or "",
        "characters": titles("current", "characters", 12),
        "relationships": relationships,
        "world_settings": titles("current", "settings", 8),
        "organizations": titles("current", "organizations", 8),
        "story_lines": titles("current", "storylines", 8),
        "approved_plan": titles("future", "approved_plan", 6),
    }


# ---------------------------------------------------------------------------
# 准备本轮 Agent 任务（不运行模型；Interactive 提示 /gowrite，Direct 后台执行）
# ---------------------------------------------------------------------------

def prepare_foundation_design(project_id: str, author_request: str, base_model_rev: int) -> dict[str, Any]:
    """作者发起一次基座设计：分解/多轮检索/综合全部由 Agent 在执行内完成。"""
    project_id = (project_id or "").strip()
    author_request = (author_request or "").strip()
    if not project_id:
        raise FoundationDesignError("缺少作品标识（project_id）。")
    if not author_request:
        raise FoundationDesignError("请写下你想设计的基座问题。")
    try:
        snapshot = get_project_snapshot(project_id)
    except Exception as exc:  # noqa: BLE001
        raise FoundationDesignError(str(exc)) from exc
    current_rev = int(snapshot.get("model_rev") or 0)
    if int(base_model_rev) != current_rev:
        raise FoundationDesignError("模型版本已变化，请刷新后重新发起基座设计。")

    design_turn_id = uuid.uuid4().hex[:12]
    proposal_dir = _proposal_dir(project_id)
    if proposal_dir.exists():
        shutil.rmtree(proposal_dir, ignore_errors=True)
    proposal_dir.mkdir(parents=True, exist_ok=True)

    settings = SettingsStore().load()
    execution_mode = settings.default_execution_mode

    request_id = uuid.uuid4().hex
    task = _AGENT_TASK_TEMPLATE.format(
        max_rounds=_MAX_ROUNDS,
        max_knowledge_hits=_MAX_KNOWLEDGE_HITS,
        retrieval_command=f'"{_RETRIEVAL_SCRIPT}"',
        request_id=request_id,
        authority_view=json.dumps(_authority_view(snapshot), ensure_ascii=False, indent=2),
        author_request=author_request,
    )

    direct_adapter = None
    direct_agent_request = None
    execution_agent = settings.interactive_agent
    execution_model = None
    if execution_mode == EXECUTION_MODE_DIRECT:
        try:
            direct_adapter, direct_agent_request = agent_runner._build_adapter()
        except Exception as exc:  # noqa: BLE001
            _cleanup_proposal(project_id)
            raise FoundationDesignError(f"直连执行配置不可用：{exc}") from exc
        execution_agent = direct_adapter.name
        execution_model = direct_agent_request.custom_model or direct_agent_request.model
        if _exec_task_manager.is_busy():
            _cleanup_proposal(project_id)
            raise FoundationDesignError(_DIRECT_BUSY_ERROR)

    try:
        bridge.create_request(
            task=task,
            kind="foundation_design_propose",
            meta={
                "project_id": project_id,
                "design_turn_id": design_turn_id,
                "author_request": author_request,
                "base_model_rev": current_rev,
                "execution": {
                    "execution_mode": execution_mode,
                    "agent_id": execution_agent,
                    "model": execution_model,
                },
            },
            request_id=request_id,
            activate_for_gowrite=execution_mode != EXECUTION_MODE_DIRECT,
        )
    except bridge.BridgeBusyError as exc:
        _cleanup_proposal(project_id)
        raise FoundationDesignError(str(exc)) from exc

    proposal_token = uuid.uuid4().hex
    meta = {
        "kind": "foundation_design_proposal",
        "project_id": project_id,
        "design_turn_id": design_turn_id,
        "proposal_token": proposal_token,
        "base_model_rev": current_rev,
        "author_request": author_request,
        "request_id": request_id,
    }
    (proposal_dir / "proposal_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    execution_facts = {
        "execution_mode": execution_mode,
        "agent_id": execution_agent,
        "model": execution_model,
    }
    recorder = audit.AuditRecorder(request_id, "foundation_design", project_id, execution=execution_facts)
    if execution_mode != EXECUTION_MODE_DIRECT:
        recorder.event(audit.EVENT_BRIDGE_WAITING, component="foundation_design")

    message = "任务已准备好，请到 Qoder 输入 /gowrite 并回车。"
    if execution_mode == EXECUTION_MODE_DIRECT:
        message = "基座设计任务已通过直连模式后台执行，正在校验结果。"
        _start_direct_execution(direct_adapter, direct_agent_request, task, request_id, project_id=project_id)

    return {
        "request_id": request_id,
        "project_id": project_id,
        "status": "task_prepared",
        "execution_mode": execution_mode,
        "agent_id": execution_agent,
        "model": execution_model,
        "message": message,
    }


# ---------------------------------------------------------------------------
# Direct 后台执行（与 NewProject 同一 worker 骨架）
# ---------------------------------------------------------------------------

def _start_direct_execution(adapter: Any, agent_request: Any, task: str, request_id: str, *, project_id: str) -> None:
    execution = {
        "execution_mode": "direct",
        "agent_id": adapter.name,
        "model": agent_request.custom_model or agent_request.model,
    }
    worker = lambda: _dispatch_direct_worker(adapter, agent_request, task, request_id)  # noqa: E731
    if not _exec_task_manager.start(request_id=request_id, worker=worker, adapter=adapter, execution=execution):
        _cleanup_proposal(project_id)
        bridge.cleanup_request(request_id)
        raise FoundationDesignError(_DIRECT_BUSY_ERROR)


def _dispatch_direct_worker(adapter: Any, agent_request: Any, task: str, request_id: str) -> None:
    agent_request.task = task
    agent_request.cwd = str(_REPO_ROOT)
    audit.append_event(request_id, audit.EVENT_AGENT_DIRECT_PROCESS_STARTED, "foundation_design", details={"agent": adapter.name})
    try:
        result = adapter.run(agent_request)
    except Exception as exc:  # noqa: BLE001
        audit.append_event(request_id, audit.EVENT_AGENT_FAILED, "foundation_design", details={"error": str(exc)[:200]})
        _finish_direct(request_id, status="failed", error=f"直连执行失败：{exc}")
        return
    if _exec_task_manager.is_canceled(request_id):
        return
    if result.status != "completed":
        audit.append_event(
            request_id,
            audit.EVENT_AGENT_FAILED if result.status != "cancelled" else audit.EVENT_AGENT_CANCELED,
            "foundation_design", details={"error": (result.error or "")[:200]},
        )
        _finish_direct(request_id, status="failed", error=result.error or f"直连执行未完成（status={result.status}）。")
        return
    audit.append_event(request_id, audit.EVENT_AGENT_COMPLETED, "foundation_design")
    _finish_direct(request_id, status="completed", output=result.output or "")


def _finish_direct(request_id: str, *, status: str, output: str = "", error: Optional[str] = None) -> None:
    if _exec_task_manager.is_canceled(request_id):
        return
    bridge.write_response(request_id, status=status, output=output or None, error=error)
    _exec_task_manager.finish(
        request_id,
        execution_tasks.TASK_COMPLETED if status == "completed" else execution_tasks.TASK_FAILED,
    )


# ---------------------------------------------------------------------------
# 严格解析与 finalize（候选落临时工作区；零 authority 写）
# ---------------------------------------------------------------------------

def _validate_str_list(value: Any, field_name: str) -> None:
    if not isinstance(value, list):
        raise FoundationDesignError(f"Agent 输出字段 {field_name} 类型错误（应为列表）。")
    for i, item in enumerate(value):
        if not isinstance(item, str):
            raise FoundationDesignError(f"Agent 输出字段 {field_name}[{i}] 类型错误（应为字符串）。")


def _validate_proposal_items(value: Any, field_name: str, *, require_state: bool) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise FoundationDesignError(f"Agent 输出字段 {field_name} 类型错误（应为列表）。")
    items = []
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            raise FoundationDesignError(f"{field_name}[{i}] 必须是对象。")
        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()
        if not title or not summary:
            raise FoundationDesignError(f"{field_name}[{i}] 缺少 title/summary。")
        state = str(item.get("material_state") or "future")
        if state not in {"current", "future"}:
            raise FoundationDesignError(f"{field_name}[{i}].material_state 非法。")
        items.append({"title": title, "summary": summary, "material_state": state if require_state else "future"})
    return items


def _parse_agent_result(output: str) -> dict[str, Any]:
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
        raise FoundationDesignError(f"Agent 输出不是合法 JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise FoundationDesignError("Agent 输出应为 JSON 对象。")
    if not isinstance(data.get("objective"), str) or not data["objective"].strip():
        raise FoundationDesignError("Agent 输出缺少 objective。")
    topics = data.get("topics")
    _validate_str_list(topics, "topics")
    if not topics or len(topics) > _MAX_ROUNDS:
        raise FoundationDesignError(f"主题数量必须在 1 到 {_MAX_ROUNDS} 之间。")
    rounds = data.get("rounds")
    if not isinstance(rounds, list) or not rounds or len(rounds) > _MAX_ROUNDS:
        raise FoundationDesignError(f"检索轮数必须在 1 到 {_MAX_ROUNDS} 之间。")
    for i, rnd in enumerate(rounds):
        if not isinstance(rnd, dict):
            raise FoundationDesignError(f"rounds[{i}] 必须是对象。")
        for key in ("topic", "query", "comparison"):
            if not isinstance(rnd.get(key), str) or not str(rnd[key]).strip():
                raise FoundationDesignError(f"rounds[{i}].{key} 缺失或不是非空字符串。")
        if not isinstance(rnd.get("package_ref"), str):
            raise FoundationDesignError(f"rounds[{i}].package_ref 必须是字符串。")
        _validate_str_list(rnd.get("selected_knowledge_refs") or [], f"rounds[{i}].selected_knowledge_refs")
    proposal = data.get("proposal")
    if not isinstance(proposal, dict):
        raise FoundationDesignError("Agent 输出缺少 proposal。")
    parsed_proposal: dict[str, Any] = {
        "characters": _validate_proposal_items(proposal.get("characters") or [], "proposal.characters", require_state=True),
        "relationships": [],
        "world_settings": _validate_proposal_items(proposal.get("world_settings") or [], "proposal.world_settings", require_state=True),
        "organizations": _validate_proposal_items(proposal.get("organizations") or [], "proposal.organizations", require_state=True),
        "story_lines": _validate_proposal_items(proposal.get("story_lines") or [], "proposal.story_lines", require_state=True),
        "core_conflict": None,
    }
    rels = proposal.get("relationships") or []
    if not isinstance(rels, list):
        raise FoundationDesignError("proposal.relationships 类型错误（应为列表）。")
    for i, rel in enumerate(rels):
        if not isinstance(rel, dict):
            raise FoundationDesignError(f"proposal.relationships[{i}] 必须是对象。")
        source_title = str(rel.get("source_title") or "").strip()
        target_title = str(rel.get("target_title") or "").strip()
        label = str(rel.get("label") or "").strip()
        summary = str(rel.get("summary") or "").strip()
        if not source_title or not target_title or not label or not summary:
            raise FoundationDesignError(f"proposal.relationships[{i}] 缺少 source_title/target_title/label/summary。")
        parsed_proposal["relationships"].append({
            "source_title": source_title, "target_title": target_title,
            "label": label, "summary": summary, "material_state": "future",
        })
    core = proposal.get("core_conflict")
    if core is not None:
        if not isinstance(core, dict) or not str(core.get("title") or "").strip() or not str(core.get("summary") or "").strip():
            raise FoundationDesignError("proposal.core_conflict 缺少 title/summary。")
        parsed_proposal["core_conflict"] = {
            "title": str(core["title"]).strip(), "summary": str(core["summary"]).strip(), "material_state": "future",
        }
    assumptions = data.get("assumptions") or []
    _validate_str_list(assumptions, "assumptions")
    knowledge_notes = str(data.get("knowledge_notes") or "")
    return {
        "objective": data["objective"].strip(),
        "topics": topics,
        "rounds": rounds,
        "proposal": parsed_proposal,
        "assumptions": assumptions,
        "knowledge_notes": knowledge_notes,
    }


def _finalize_request(request: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    if response.get("request_id") != request["request_id"]:
        raise FoundationDesignError("返回结果与任务不匹配（request_id 不一致），已丢弃。")
    resp_status = response.get("status")
    if resp_status not in (None, "completed"):
        raise FoundationDesignError(response.get("error") or f"执行器返回状态异常：{resp_status}")
    try:
        raw = bridge.response_result_text(response)
    except bridge.BridgeProtocolError as exc:
        raise FoundationDesignError(str(exc)) from exc
    parsed = _parse_agent_result(raw)

    meta = request.get("meta") or {}
    project_id = str(meta.get("project_id") or "")
    design_turn_id = str(meta.get("design_turn_id") or "")
    proposal_dir = _proposal_dir(project_id)

    all_selected: list[str] = []
    source_kinds: set[str] = set()
    for rnd in parsed["rounds"]:
        selected = _validate_round(
            proposal_dir, rnd,
            request_id=request["request_id"], project_id=project_id, design_turn_id=design_turn_id,
        )
        all_selected.extend(selected)
        path = _round_path(proposal_dir, str(rnd.get("query") or "").strip())
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        captured = {
            str(hit.get("selection_ref") or ""): hit
            for hit in (snapshot.get("package") or {}).get("hits", [])
        }
        for ref in selected:
            source_kinds.add(str((captured.get(ref) or {}).get("source_kind") or ""))
    audit.append_event(
        request["request_id"], audit.EVENT_RETRIEVAL_SELECTED, "knowledge_retrieve",
        details={"rounds": len(parsed["rounds"]), "refs": all_selected, "source_kinds": sorted(source_kinds)},
    )

    proposal_meta = json.loads((proposal_dir / "proposal_meta.json").read_text(encoding="utf-8"))
    candidate = {
        "status": "proposal_noncanonical",
        "objective": parsed["objective"],
        "topics": parsed["topics"],
        "rounds": [
            {
                "topic": rnd["topic"], "query": rnd["query"],
                "comparison": rnd["comparison"],
                "selected_count": len(rnd.get("selected_knowledge_refs") or []),
            }
            for rnd in parsed["rounds"]
        ],
        "proposal": parsed["proposal"],
        "assumptions": parsed["assumptions"],
        "knowledge_notes": parsed["knowledge_notes"],
        "knowledge": {
            "rounds": len(parsed["rounds"]),
            "selected_count": len(all_selected),
            "source_kinds": sorted(source_kinds),
        },
    }
    (proposal_dir / "proposal.json").write_text(
        json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    audit.append_event(request["request_id"], audit.EVENT_CANDIDATE_CREATED, "foundation_design")
    return {
        "proposal_token": proposal_meta["proposal_token"],
        "project_id": project_id,
        "status": "proposal_noncanonical",
        "candidate": candidate,
        "execution": dict(meta.get("execution") or {}),
        "message": "基座设计候选已生成（未写入作品，等待你的确认）",
    }


def get_foundation_design_request(request_id: str) -> dict[str, Any]:
    """轮询写回结果：pending / completed / failed / expired / canceled。"""
    request_id = (request_id or "").strip()
    if not request_id:
        raise FoundationDesignError("缺少任务标识（request_id）。")
    request = bridge.get_request(request_id)
    if request is None:
        return {"request_id": request_id, "status": "failed", "error": "任务已失效，请重新发起。"}
    state = request.get("state")
    project_id = str((request.get("meta") or {}).get("project_id") or "")

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
        audit.finish_file(request_id, audit.STATUS_FAILED, error=request.get("error") or "任务失败，请重新发起。")
        return {"request_id": request_id, "status": "failed", "error": request.get("error") or "任务失败，请重新发起。"}

    if bridge.is_expired(request):
        if project_id:
            _cleanup_proposal(project_id)
        _exec_task_manager.cancel(request_id)
        _exec_task_manager.remove(request_id)
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error="任务已超时，请重新发起。")
        return {"request_id": request_id, "status": "expired", "error": "任务已超时，请重新发起。"}

    response = bridge.read_response(request_id)
    if response is None:
        return {"request_id": request_id, "status": "pending"}
    if response.get("request_id") != request_id:
        bridge.cleanup_request(request_id)
        _exec_task_manager.remove(request_id)
        return {"request_id": request_id, "status": "failed", "error": "返回结果与任务不匹配（request_id 不一致），已丢弃。"}

    audit.append_event(request_id, audit.EVENT_BRIDGE_RESPONSE_RECEIVED, "foundation_design")
    try:
        result = _finalize_request(request, response)
    except FoundationDesignError as exc:
        if project_id:
            _cleanup_proposal(project_id)
        bridge.cleanup_request(request_id)
        _exec_task_manager.remove(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
        return {"request_id": request_id, "status": "failed", "error": str(exc)}

    bridge.cleanup_request(request_id)
    _exec_task_manager.remove(request_id)
    audit.mark_awaiting_confirmation(request_id)
    return {"request_id": request_id, "status": "completed", "result": result}


def cancel_foundation_design_request(request_id: str) -> dict[str, Any]:
    """取消/丢弃：终止运行中 Direct adapter（如有）、删除临时候选；幂等。"""
    request_id = (request_id or "").strip()
    if not request_id:
        raise FoundationDesignError("缺少任务标识（request_id）。")
    _exec_task_manager.cancel(request_id)
    request = bridge.get_request(request_id)
    if request is not None:
        bridge.mark_canceled(request_id)
        project_id = str((request.get("meta") or {}).get("project_id") or "")
        if project_id:
            _cleanup_proposal(project_id)
        bridge.clear_active_if(request_id)
        audit.finish_file(request_id, audit.STATUS_CANCELED)
    else:
        root = get_proposals_root()
        if root.exists():
            for meta_file in root.glob("*/proposal_meta.json"):
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if meta.get("request_id") == request_id:
                    _cleanup_proposal(str(meta.get("project_id") or ""))
                    break
        audit.finish_file(request_id, audit.STATUS_CANCELED)
    _exec_task_manager.remove(request_id)
    return {"request_id": request_id, "status": "canceled"}


# ---------------------------------------------------------------------------
# 作者明确确认 → 通过既有 authority 合同写回（唯一写入口）
# ---------------------------------------------------------------------------

def _validate_confirm_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list) or not items:
        raise FoundationDesignError("没有可写入的基座条目。")
    validated = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise FoundationDesignError(f"items[{i}] 必须是对象。")
        kind = str(item.get("kind") or "")
        if kind not in _ALLOWED_ITEM_KINDS:
            raise FoundationDesignError(f"items[{i}].kind 非法。")
        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()
        if not title or not summary:
            raise FoundationDesignError(f"items[{i}] 缺少 title/summary。")
        state = str(item.get("material_state") or "future")
        if state not in {"current", "future"}:
            raise FoundationDesignError(f"items[{i}].material_state 非法。")
        entry = {
            "kind": kind, "title": title, "summary": summary, "material_state": state,
            "source_title": str(item.get("source_title") or "").strip(),
            "target_title": str(item.get("target_title") or "").strip(),
            "label": str(item.get("label") or "").strip(),
        }
        if kind == "relationship" and (not entry["source_title"] or not entry["target_title"] or not entry["label"]):
            raise FoundationDesignError(f"items[{i}] 关系缺少 source_title/target_title/label。")
        validated.append(entry)
    return validated


def confirm_foundation_design(
    project_id: str,
    proposal_token: str,
    items: Any,
    base_model_rev: int,
) -> dict[str, Any]:
    """作者明确确认：把选择/编辑后的提案条目写回同一项目 authority。

    - token 绑定 project_id（跨项目拒绝）；丢弃/失效的候选不可确认；
    - base_model_rev stale 守卫；项目写锁内顺序创建；
    - 作者确认即作者决定：field_authority=author；
    - 语义需要时进入既有 change_settlement 路径（不新建第二条）。
    """
    project_id = (project_id or "").strip()
    proposal_token = (proposal_token or "").strip()
    if not project_id or not proposal_token:
        raise FoundationDesignError("缺少作品标识或候选确认标识。")
    confirmed_items = _validate_confirm_items(items)

    root = get_proposals_root()
    matched: Optional[Path] = None
    if root.exists():
        for meta_file in root.glob("*/proposal_meta.json"):
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if meta.get("proposal_token") == proposal_token:
                matched = meta_file.parent
                break
    if matched is None:
        raise FoundationDesignError("候选已失效或不存在（可能已丢弃/确认），请重新发起。")
    meta = json.loads((matched / "proposal_meta.json").read_text(encoding="utf-8"))
    if str(meta.get("project_id") or "") != project_id:
        raise FoundationDesignError("候选不属于当前作品，已拒绝（项目隔离）。")

    with author_edit.project_write_lock(project_id):
        model = project_model.load_project_model(project_id)
        if int(base_model_rev) != int(model["model_rev"]):
            raise FoundationDesignError("模型版本已变化，请刷新后重新确认。")
        created: list[dict[str, Any]] = []
        warnings: list[str] = []
        title_to_ref: dict[str, str] = {}
        for obj in model.get("objects", {}).values():
            if isinstance(obj, dict) and not obj.get("tombstoned") and obj.get("category") == "character":
                title_to_ref.setdefault(str(obj.get("title") or ""), str(obj.get("ref") or ""))
        rev = int(model["model_rev"])
        first_semantic_change: Optional[str] = None
        for item in confirmed_items:
            if item["kind"] == "relationship":
                source_ref = title_to_ref.get(item["source_title"])
                target_ref = title_to_ref.get(item["target_title"])
                if not source_ref or not target_ref:
                    warnings.append(f"关系“{item['source_title']} ↔ {item['target_title']}”端点不明确，已跳过。")
                    continue
                result = author_edit.create_relationship(
                    project_id, base_model_rev=rev, source_ref=source_ref, target_ref=target_ref,
                    label=item["label"], material_state=item["material_state"],
                    data={"design_summary": item["summary"]},
                )
            else:
                category = _CATEGORY_BY_KIND[item["kind"]]
                data: dict[str, Any] = {"design_summary": item["summary"]}
                if item["kind"] == "core_conflict":
                    data["design_kind"] = "core_conflict"
                result = author_edit.create_foundation_record(
                    project_id, base_model_rev=rev, category=category, title=item["title"],
                    material_state=item["material_state"], data=data,
                )
                if item["kind"] == "character":
                    title_to_ref[item["title"]] = result["model"]["change_history"][-1]["detail"]["ref"]
            rev = int(result["model"]["model_rev"])
            change = result.get("change") or {}
            if change.get("requires_semantic") and first_semantic_change is None:
                first_semantic_change = str(change.get("change_id") or "")
            created.append({"kind": item["kind"], "title": item["title"], "ref": (
                result["model"]["change_history"][-1]["detail"]["ref"]
            )})
        settlement_started = False
        if first_semantic_change:
            try:
                change_settlement.prepare_change_settlement(project_id, first_semantic_change)
                settlement_started = True
            except Exception:  # noqa: BLE001 — durable 写入保留，可稍后重试同步
                settlement_started = False
    _cleanup_proposal(project_id)
    audit.append_event(
        str(meta.get("request_id") or ""), audit.EVENT_AUTHORITY_CONFIRMED, "foundation_design",
        details={"project_id": project_id, "created": len(created), "warnings": warnings},
    )
    audit.finish_file(str(meta.get("request_id") or ""), audit.STATUS_COMPLETED)
    return {
        "project_id": project_id,
        "model_rev": rev,
        "created": created,
        "warnings": warnings,
        "settlement_started": settlement_started,
        "message": "基座设计已写入作品地基。",
    }
