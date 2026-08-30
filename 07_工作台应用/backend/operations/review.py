# -*- coding: utf-8 -*-
"""作品检查 Author Operations：真实、显式、范围受控的 AI 检查（非模拟）。

职责（对应 UI 1.0 Review 真实消费者）：
- get_review_surface：确定性只读面（无模型）：正式项目身份 / 当前有效规划数 /
  未解决线索数 / 已采用章节目录 / 最新章节选择；
- prepare_review：作者显式按下"开始检查"后，才发起一次 Agent 检查
  （默认检查最新已接受章节），异步后台执行，可轮询/取消；
- 检查结果非权威：零 Canon / 零正文写回，无"标记已处理"持久化。

执行模式：Review 与 StoryWrite 一致，仅支持 Direct 后台执行（交互桥显式
未接入，绝不回退、绝不 UI 选模型）；一次检查 = 一次 Agent 运行。

知识选择绑定（与 StoryPlan/StoryWrite 同一 P0 规则）：
- knowledge_needs == [] → 检索 0 次，selected 为空，正常出报告；
- knowledge_needs != [] → 模型在本次执行内运行唯一一次确定性检索命令
  （retrieval_snapshot.py --request <request_id> "<query>"），从该显示包选择
  scoped ref 并回显 package_fingerprint；finalize 绝不再次检索。

范围纪律：绝不 dump 全本；绝不 dump 未选择的完整 Story State。只给：
  选中章节正文 + Author Intent 摘要 + active 规划摘要 + 未解决线索摘要。
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
from operations.project_snapshot import focused_task_context, get_project_snapshot
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

# Direct 执行任务管理器（与 StoryPlan/StoryWrite 共用同一单活跃槽）
_exec_task_manager = execution_tasks.manager

_REPO_ROOT = Path(__file__).resolve().parents[3]

if str(_REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))
if str(_REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "StoryPlan") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "StoryPlan"))

from project_workspace import (  # noqa: E402
    ContractError as PWContractError,
    WorkspaceError as PWWorkspaceError,
    load_project,
    resolve_project,
)
from story_plan import resolve_plan_activity  # noqa: E402

# 临时 review 工作区根（06_工作区/应用开发 已 gitignore，Local Only，可删除）
_REVIEW_ROOT = _REPO_ROOT / "06_工作区" / "应用开发" / ".review"

# 请求级检索快照 CLI（Agent 在执行内运行；唯一确定性检索入口）
_RETRIEVAL_SCRIPT = Path(__file__).resolve().parent / "retrieval_snapshot.py"

_AGENT_TASK_TEMPLATE = """你是 Go Write 的作品检查执行器。必须严格按下列顺序执行：先完成语义分析；若 knowledge_needs 非空，必须在生成最终 JSON 之前先调用本地命令/工具执行下面给出的检索命令并读取其结果；完成检索与选择后，才输出最终 JSON。本任务不是纯文本生成任务；中间的工具调用属于执行过程，不属于最终回复。

流程分两个阶段：

第一阶段：语义分析
针对本次检查，先完成语义分析（objective / knowledge_needs / assumptions）。knowledge_needs 为空列表是合法的。

第二阶段：知识检索与选择（仅当 knowledge_needs 非空；必须执行）
若 knowledge_needs 非空，在生成最终 JSON 之前，你必须先用可用的本地命令/工具执行以下确定性只读检索命令：
  python {retrieval_command} --request {request_id} "<query>"
其中 <query> 是把你第一阶段列出的全部 knowledge_needs 用中文分号（；）连接成的单个字符串。
该命令会把本次检索包（混合参考作品知识/方法知识/已验证知识）写入当前请求的临时快照，然后输出 JSON；每个候选项的 selection_ref 形如 "<source_kind>/<source_id>/<source_anchor>"。
你必须读取该命令实际输出的 package：只从中选择 0 到 {max_knowledge_hits} 个 selection_ref 填入 semantic_interpretation.selected_knowledge_refs；并把命令输出的 package_fingerprint 原样填入 semantic_interpretation.package_ref。
严禁编造命令输出中不存在的 selection_ref 或 package_fingerprint；没有合适候选时 selected_knowledge_refs 保持空列表。
若 knowledge_needs 为空：不要运行检索命令，selected_knowledge_refs 必须为 []，package_ref 必须为空字符串 ""。

最终回复
最终回复必须只有合法 JSON 对象（不要任何额外文字、不要 markdown 代码块标记）。结构必须如下：

{{
  "semantic_interpretation": {{
    "objective": "本次检查的目标（一句话）",
    "knowledge_needs": [],
    "selected_knowledge_refs": [],
    "package_ref": "",
    "assumptions": ["AI 解读中的假设"]
  }},
  "review": {{
    "summary": "整体结论（一段话）",
    "issues": [
      {{
        "severity": "priority",
        "title": "问题标题",
        "detail": "具体说明",
        "evidence": "可定位到的章节引用（如有）",
        "suggestion": "改进建议"
      }}
    ],
    "strengths": ["写得好的地方（可选）"]
  }}
}}

severity 只允许：priority（优先处理）/ watch（值得看看）。
只检查本次给出的章节范围内的内容，不要臆测未提供的章节。
可检查人物与关系不一致、世界/系统规则违反、时间矛盾、遗忘伏笔、细纲与正文偏差及连续性问题。报告只提供诊断建议，不得写回或宣称修改任何作品事实；作者接受修正后必须另走正常编辑/结算路径。

作品信息：
- 作品名：{name}
- 已确定的故事方向：{work_direction}
- 读者主要期待：{reader_promise}

当前有效规划：
{current_planning}

未解决线索：
{open_threads}

最新有效作者工作区与本章细纲（显式作者编辑优先；current/future 分开）：
{effective_project_context}

本次检查章节（第 {chapter_number} 章）正文：
{chapter_text}

最终回复必须只有合法 JSON；但在生成最终回复之前，若 knowledge_needs 非空，你必须先调用工具执行检索命令并读取结果。工具调用属于任务执行过程，不属于最终回复。"""


class ReviewError(Exception):
    """作品检查操作错误（面向 UI 的稳定错误类型，普通用户可读）。"""


# ---------------------------------------------------------------------------
# 临时 review 工作区
# ---------------------------------------------------------------------------

def get_review_root() -> Path:
    """临时 review 工作区根（测试可 monkeypatch 本函数）。"""
    return _REVIEW_ROOT


def _review_dir(project_id: str, review_turn_id: str) -> Path:
    return get_review_root() / project_id / review_turn_id


def _cleanup_review(project_id: str, review_turn_id: str) -> None:
    shutil.rmtree(_review_dir(project_id, review_turn_id), ignore_errors=True)


# ---------------------------------------------------------------------------
# 知识选择绑定（P0，与 StoryPlan/StoryWrite 同规则；快照在 review 工作区）
# ---------------------------------------------------------------------------

def _snapshot_path(review_dir: Path) -> Path:
    return review_dir / "retrieval" / "package.json"


def _write_snapshot(
    *,
    request_id: str,
    project_id: str,
    review_turn_id: str,
    query: str,
    package: Any,
    review_dir: Path,
) -> Path:
    snapshot = {
        "schema": "gowrite_retrieval_snapshot/v2",
        "request_id": request_id,
        "project_id": project_id,
        "review_turn_id": review_turn_id,
        "query": query,
        "package_fingerprint": _package_fingerprint(package),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "package": _package_snapshot_dict(package),
    }
    path = _snapshot_path(review_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _load_snapshot(review_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    path = _snapshot_path(review_dir)
    if not path.exists():
        return None, "检索包快照缺失：Agent 未在本轮检查执行内生成检索快照。"
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
    review_turn_id: str,
    query: str,
    package_ref: str,
) -> None:
    if snapshot.get("request_id") != request_id:
        raise ReviewError("检索包快照 request_id 与当前任务不一致，已拒绝。")
    if snapshot.get("project_id") != project_id:
        raise ReviewError("检索包快照 project_id 与当前任务不一致，已拒绝。")
    if snapshot.get("review_turn_id") != review_turn_id:
        raise ReviewError("检索包快照 review_turn_id 与当前任务不一致，已拒绝。")
    if snapshot.get("query") != query:
        raise ReviewError("检索包快照查询与本次 knowledge_needs 不一致（query mismatch），已拒绝。")
    if not package_ref:
        raise ReviewError("Agent 输出缺少检索包身份（package_ref）。")
    if snapshot.get("package_fingerprint") != package_ref:
        raise ReviewError("Agent 选择的检索包身份（package_ref）与绑定快照不一致，已拒绝。")


def execute_request_scoped_retrieval(query: str, request_id: str) -> Any:
    """Agent 侧（检查执行内）的唯一一次确定性检索调用（显式绑定 request_id）。"""
    request = bridge.get_request(request_id)
    if request is None:
        raise ReviewError("任务文件不存在或不可读，无法生成检索快照。")
    meta = request.get("meta") or {}
    project_id = str(meta.get("project_id") or "")
    review_turn_id = str(meta.get("review_turn_id") or "")
    if not project_id or not review_turn_id:
        raise ReviewError("任务缺少 project_id / review_turn_id 元数据。")
    review_dir = _review_dir(project_id, review_turn_id)
    audit.append_event(
        request_id, audit.EVENT_RETRIEVAL_REQUESTED, "knowledge_retrieve",
        details={"query": query[:200]},
    )
    try:
        package = _retrieve_package(query)  # 唯一一次 KnowledgeRetrieve 执行
    except ReviewError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ReviewError(f"知识检索失败：{exc}") from exc
    _write_snapshot(
        request_id=request_id,
        project_id=project_id,
        review_turn_id=review_turn_id,
        query=query,
        package=package,
        review_dir=review_dir,
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


# ---------------------------------------------------------------------------
# 确定性只读面（无模型）
# ---------------------------------------------------------------------------

def _active_plan_descriptions(state: dict[str, Any]) -> list[str]:
    all_plans = state.get("approved_plan") or []
    if not all_plans:
        return []
    try:
        activity = resolve_plan_activity(state)
    except Exception:  # noqa: BLE001
        return []
    active_ids = set(activity.get("active") or [])
    out = []
    for p in all_plans:
        if p.get("id") in active_ids:
            desc = p.get("description") or p.get("text") or ""
            if desc:
                out.append(desc)
    return out


def _open_thread_labels(state: dict[str, Any]) -> list[str]:
    threads = state.get("open_threads") or []
    out = []
    if isinstance(threads, list):
        for t in threads:
            if isinstance(t, dict):
                label = t.get("description") or t.get("text") or t.get("fact") or t.get("title") or ""
                if isinstance(label, str) and label.strip():
                    out.append(label.strip())
    return out


def _read_chapter_text(loaded: dict[str, Any], chapter_number: int) -> str:
    """只读选中章节正文（accepted_text_index → 03_正文），仅做路径包含校验。"""
    index = loaded.get("index") or {}
    entries = index.get("entries") or []
    project_dir = Path(loaded["project_dir"])
    chapter_entries = [e for e in entries if e.get("chapter_number") == chapter_number]
    if not chapter_entries:
        return ""
    chapter_paths = {e.get("chapter_path") for e in chapter_entries}
    if len(chapter_paths) != 1:
        raise ReviewError("该章节的 accepted_text_index 章节路径不一致，请检查。")
    rel = (chapter_paths.pop() or "").strip()
    if not rel or Path(rel).is_absolute() or ".." in rel:
        raise ReviewError("accepted_text_index 章节路径非法。")
    prose_root = (project_dir / "03_正文").resolve()
    full = (project_dir / rel).resolve()
    try:
        full.relative_to(prose_root)
    except ValueError:
        raise ReviewError("accepted_text_index 章节路径不在 03_正文/ 下。")
    if not full.exists():
        raise ReviewError("章节文件不存在，请先有已接受的正文。")
    return full.read_text(encoding="utf-8")


def get_review_surface(project_id: str) -> dict[str, Any]:
    """确定性只读面：正式身份 / 有效规划数 / 未解决线索数 / 章节目录 / 最新章节。"""
    project_id = (project_id or "").strip()
    if not project_id:
        raise ReviewError("缺少作品标识（project_id）。")
    try:
        snapshot = get_project_snapshot(project_id)
    except Exception as exc:  # noqa: BLE001
        raise ReviewError(str(exc)) from exc
    accepted = [item for item in snapshot["chapters"] if item.get("accepted")]
    chapters = [item["chapter_number"] for item in accepted]
    return {
        "project_id": snapshot["project_id"],
        "name": snapshot["name"],
        "active_plan_count": len(snapshot["future"]["approved_plan"]),
        "open_thread_count": len(snapshot["current"]["open_threads"]),
        "chapters": [{"chapter_number": number} for number in chapters],
        "latest_chapter_number": chapters[-1] if chapters else None,
        "has_accepted_prose": bool(accepted),
        "settlement": snapshot["settlement"],
    }


# ---------------------------------------------------------------------------
# Agent 输出解析
# ---------------------------------------------------------------------------

def _validate_str_list(value: Any, field_name: str) -> None:
    if not isinstance(value, list):
        raise ReviewError(f"Agent 输出字段 {field_name} 类型错误（应为列表）。")
    for i, item in enumerate(value):
        if not isinstance(item, str):
            raise ReviewError(f"Agent 输出字段 {field_name}[{i}] 类型错误（应为字符串）。")


def _parse_json_output(output: str) -> dict[str, Any]:
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
        raise ReviewError("Agent 输出不是合法结构化结果，请重试。") from exc
    if not isinstance(data, dict):
        raise ReviewError("Agent 输出不是合法结构化结果（应为 JSON 对象）。")
    return data


def _parse_review_result(output: str) -> dict[str, Any]:
    """解析检查阶段 Agent 输出（semantic_interpretation + review）。"""
    data = _parse_json_output(output)

    si = data.get("semantic_interpretation")
    if not isinstance(si, dict):
        raise ReviewError("Agent 输出缺少 semantic_interpretation。")
    if not isinstance(si.get("objective"), str) or not si["objective"].strip():
        raise ReviewError("Agent 输出 semantic_interpretation.objective 缺失。")
    if "knowledge_needs" not in si:
        raise ReviewError("Agent 输出缺少 semantic_interpretation.knowledge_needs。")
    _validate_str_list(si["knowledge_needs"], "semantic_interpretation.knowledge_needs")
    if "selected_knowledge_refs" not in si:
        raise ReviewError("Agent 输出缺少 semantic_interpretation.selected_knowledge_refs。")
    _validate_str_list(si["selected_knowledge_refs"], "semantic_interpretation.selected_knowledge_refs")
    if "package_ref" not in si or not isinstance(si.get("package_ref"), str):
        raise ReviewError("Agent 输出缺少 semantic_interpretation.package_ref。")
    if "assumptions" in si:
        _validate_str_list(si["assumptions"], "semantic_interpretation.assumptions")

    review = data.get("review")
    if not isinstance(review, dict):
        raise ReviewError("Agent 输出缺少 review（应为对象）。")
    if not isinstance(review.get("summary"), str) or not review["summary"].strip():
        raise ReviewError("Agent 输出 review.summary 缺失或不是非空字符串。")
    issues = review.get("issues")
    if not isinstance(issues, list):
        raise ReviewError("Agent 输出 review.issues 缺失（应为列表）。")
    for i, issue in enumerate(issues):
        if not isinstance(issue, dict):
            raise ReviewError(f"review.issues[{i}] 不是对象。")
        if issue.get("severity") not in ("priority", "watch"):
            raise ReviewError(f"review.issues[{i}].severity 非法。")
        if not isinstance(issue.get("title"), str) or not issue["title"].strip():
            raise ReviewError(f"review.issues[{i}].title 缺失。")
        if not isinstance(issue.get("detail"), str) or not issue["detail"].strip():
            raise ReviewError(f"review.issues[{i}].detail 缺失。")
        if not isinstance(issue.get("suggestion", ""), str):
            raise ReviewError(f"review.issues[{i}].suggestion 类型错误。")
    strengths = review.get("strengths")
    if strengths is not None:
        if not isinstance(strengths, list) or any(not isinstance(s, str) for s in strengths):
            raise ReviewError("Agent 输出 review.strengths 类型错误（应为字符串列表）。")

    return {"semantic_interpretation": si, "review": review}


# ---------------------------------------------------------------------------
# Direct 后台执行（单 Agent 运行）
# ---------------------------------------------------------------------------

def _finish_direct(request_id: str, *, status: str, result: dict[str, Any] | None = None, error: str | None = None) -> None:
    # 审计记录不在这里收尾（finalize 事件由 get_review_request 追加后 finish）
    if _exec_task_manager.is_canceled(request_id):
        return
    bridge.write_response(request_id, status=status, result=result, error=error)
    _exec_task_manager.finish(
        request_id,
        execution_tasks.TASK_COMPLETED if status == "completed" else execution_tasks.TASK_FAILED,
    )


def _dispatch_review_worker(adapter: Any, agent_request: Any, ctx: dict[str, Any], request_id: str) -> None:
    """后台 worker：唯一一次 Agent 检查 → 解析 → 组装报告 → 写回信封。"""
    agent_request.task = ctx["task"]
    agent_request.cwd = str(ctx["review_dir"])
    audit.append_event(
        request_id, audit.EVENT_AGENT_DIRECT_PROCESS_STARTED, "review",
        details={"agent": adapter.name},
    )
    try:
        result = adapter.run(agent_request)
    except Exception as exc:  # noqa: BLE001
        audit.append_event(request_id, audit.EVENT_AGENT_FAILED, "review", details={"error": str(exc)[:200]})
        _finish_direct(request_id, status="failed", error=f"检查执行失败：{exc}")
        return
    if _exec_task_manager.is_canceled(request_id):
        return
    if result.status != "completed":
        audit.append_event(
            request_id,
            audit.EVENT_AGENT_FAILED if result.status != "cancelled" else audit.EVENT_AGENT_CANCELED,
            "review", details={"error": (result.error or "")[:200]},
        )
        _finish_direct(
            request_id, status="failed",
            error=result.error or f"检查执行未完成（status={result.status}）。",
        )
        return
    audit.append_event(request_id, audit.EVENT_AGENT_COMPLETED, "review")
    try:
        parsed = _parse_review_result(result.output)
    except ReviewError as exc:
        _finish_direct(request_id, status="failed", error=str(exc))
        return

    # 知识选择绑定（P0：只从精确捕获包选择，绝不再次检索）
    knowledge_needs = list(parsed["semantic_interpretation"].get("knowledge_needs") or [])
    selected_refs = list(parsed["semantic_interpretation"].get("selected_knowledge_refs") or [])
    package_ref = str(parsed["semantic_interpretation"].get("package_ref") or "")
    if knowledge_needs:
        query = "；".join(knowledge_needs)
        snapshot, load_error = _load_snapshot(ctx["review_dir"])
        if load_error:
            _finish_direct(request_id, status="failed", error=load_error)
            return
        try:
            _validate_snapshot(
                snapshot,
                request_id=request_id,
                project_id=ctx["project_id"],
                review_turn_id=ctx["review_turn_id"],
                query=query,
                package_ref=package_ref,
            )
        except ReviewError as exc:
            _finish_direct(request_id, status="failed", error=str(exc))
            return
        audit.append_event(
            request_id, audit.EVENT_RETRIEVAL_SELECTED, "knowledge_retrieve",
            details={"query": query, "refs": selected_refs, "package_ref": package_ref},
        )
    elif selected_refs or package_ref:
        _finish_direct(request_id, status="failed", error="没有知识需求却选择了知识卡或检索包身份，已拒绝。")
        return

    review = parsed["review"]
    report = {
        "review_token": uuid.uuid4().hex,
        "project_id": ctx["project_id"],
        "name": ctx["name"],
        "chapter_number": ctx["chapter_number"],
        "summary": review["summary"],
        "issues": review.get("issues") or [],
        "strengths": review.get("strengths") or [],
        "knowledge": {
            "retrieved_count": 0,
            "selected_count": len(selected_refs),
        },
        "execution": dict(ctx["execution"]),
        "message": "检查已完成（结果仅供参考，不写入正式作品）",
    }
    audit.append_event(request_id, audit.EVENT_CANDIDATE_CREATED, "review")
    _finish_direct(request_id, status="completed", result=report)


def _start_direct_execution(adapter: Any, agent_request: Any, ctx: dict[str, Any], request_id: str) -> None:
    execution = {
        "execution_mode": "direct",
        "agent_id": adapter.name,
        "model": agent_request.custom_model or agent_request.model,
    }
    ctx["execution"] = execution
    worker = lambda: _dispatch_review_worker(adapter, agent_request, ctx, request_id)  # noqa: E731
    if not _exec_task_manager.start(request_id=request_id, worker=worker, adapter=adapter, execution=execution):
        _cleanup_review(ctx["project_id"], ctx["review_turn_id"])
        bridge.cleanup_request(request_id)
        raise ReviewError(_DIRECT_BUSY_ERROR)


# ---------------------------------------------------------------------------
# prepare / get / cancel
# ---------------------------------------------------------------------------

def prepare_review(project_id: str, chapter_number: int | None = None) -> dict[str, Any]:
    """作者显式"开始检查"：读取正式项目 → 构造检查任务 → 后台执行（Direct only）。"""
    project_id = (project_id or "").strip()
    if not project_id:
        raise ReviewError("缺少作品标识（project_id）。")

    try:
        proj = resolve_project(project_id)
        loaded = load_project(proj["project_dir"])
    except (PWContractError, PWWorkspaceError) as exc:
        raise ReviewError(str(exc)) from exc

    intent = loaded["intent"]
    state = loaded["state"]
    name = loaded["name"]

    # 章节选择：作者未显式指定 → 最新已接受章节
    index = loaded.get("index") or {}
    entries = index.get("entries") or []
    chapters = sorted({int(e.get("chapter_number") or 1) for e in entries}) if entries else []
    if chapter_number is None:
        if not chapters:
            raise ReviewError("还没有已接受的正文，无法检查。请先写一段并保留。")
        chapter_number = chapters[-1]
    if chapter_number not in chapters:
        raise ReviewError(f"第 {chapter_number} 章还没有已接受的正文，无法检查。")

    chapter_text = _read_chapter_text(loaded, chapter_number)

    # Settings 执行模式：Review 仅支持 Direct（交互桥显式未接入）
    settings = SettingsStore().load()
    if settings.default_execution_mode != EXECUTION_MODE_DIRECT:
        raise ReviewError("作品检查的交互桥执行尚未接入；请在设置中选择“直连”执行模式后重试。")

    try:
        adapter, agent_request = agent_runner._build_adapter()
    except AgentRunError as exc:
        raise ReviewError(f"直连执行配置不可用：{exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise ReviewError(f"直连执行配置不可用：{exc}") from exc
    execution_agent = adapter.name
    execution_model = agent_request.custom_model or agent_request.model

    if _exec_task_manager.is_busy():
        raise ReviewError(_DIRECT_BUSY_ERROR)

    review_turn_id = uuid.uuid4().hex[:12]
    review_dir = _review_dir(project_id, review_turn_id)
    if review_dir.exists():
        shutil.rmtree(review_dir, ignore_errors=True)
    review_dir.mkdir(parents=True, exist_ok=False)

    # 只给摘要，不 dump 全本 / 全 State
    current_planning = "\n".join(f"- {d}" for d in _active_plan_descriptions(state)) or "（暂无）"
    open_threads = "\n".join(f"- {t}" for t in _open_thread_labels(state)) or "（暂无）"

    # 预生成 request_id（检索命令需要内嵌真实 id）
    request_id = uuid.uuid4().hex

    task = _AGENT_TASK_TEMPLATE.format(
        name=name,
        work_direction=intent.get("work_direction") or "",
        reader_promise=intent.get("reader_promise") or "",
        current_planning=current_planning,
        open_threads=open_threads,
        effective_project_context=json.dumps(
            focused_task_context(project_id, chapter_number=chapter_number),
            ensure_ascii=False,
            indent=2,
        ),
        chapter_number=chapter_number,
        chapter_text=chapter_text,
        retrieval_command=f'"{_RETRIEVAL_SCRIPT}"',
        request_id=request_id,
        max_knowledge_hits=_MAX_KNOWLEDGE_HITS,
    )

    bridge.create_request(
        task=task,
        kind="review_propose",
        meta={
            "project_id": project_id,
            "name": name,
            "review_turn_id": review_turn_id,
            "chapter_number": chapter_number,
            "intent_rev": intent["intent_rev"],
            "state_rev": state["state_rev"],
            "execution": {
                "execution_mode": "direct",
                "agent_id": execution_agent,
                "model": execution_model,
            },
        },
        request_id=request_id,
        activate_for_gowrite=False,  # Review 仅 Direct：请求永不进入 Qoder /gowrite
    )

    ctx = {
        "project_id": project_id,
        "name": name,
        "review_turn_id": review_turn_id,
        "review_dir": review_dir,
        "chapter_number": chapter_number,
        "task": task,
        "execution": {
            "execution_mode": "direct",
            "agent_id": execution_agent,
            "model": execution_model,
        },
    }
    # 验证式审计（operation.started）——必须先于 worker 创建（worker 内事件依赖 recorder）
    audit.AuditRecorder(
        request_id, "review", project_id,
        execution={
            "execution_mode": "direct",
            "agent_id": execution_agent,
            "model": execution_model,
        },
    )
    _start_direct_execution(adapter, agent_request, ctx, request_id)

    return {
        "request_id": request_id,
        "project_id": project_id,
        "name": name,
        "chapter_number": chapter_number,
        "status": "task_prepared",
        "execution_mode": "direct",
        "agent_id": execution_agent,
        "model": execution_model,
        "message": "检查已通过直连模式后台执行，正在生成结果。",
    }


def _cleanup_discarded_review(request_id: str) -> None:
    """丢弃已完成但未确认的检查报告：按 review_meta.json 中持久化的 request_id 定位并清理。"""
    root = get_review_root()
    if not root.exists():
        return
    for meta_file in root.glob("*/*/review_meta.json"):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if meta.get("request_id") != request_id:
            continue
        project_id = str(meta.get("project_id") or "")
        review_turn_id = str(meta.get("review_turn_id") or "")
        if project_id and review_turn_id:
            _cleanup_review(project_id, review_turn_id)
        else:
            shutil.rmtree(meta_file.parent, ignore_errors=True)
        return


def get_review_request(request_id: str) -> dict[str, Any]:
    """轮询 Direct 检查结果：pending / completed（含报告）/ failed / expired / canceled。"""
    request_id = (request_id or "").strip()
    if not request_id:
        raise ReviewError("缺少任务标识（request_id）。")

    request = bridge.get_request(request_id)
    if request is None:
        return {"request_id": request_id, "status": "failed", "error": "任务已失效，请重新发起。"}

    state = request.get("state")
    meta = request.get("meta") or {}
    project_id = str(meta.get("project_id") or "")
    review_turn_id = str(meta.get("review_turn_id") or "")

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
        return {"request_id": request_id, "status": "failed", "error": request.get("error") or "任务失败，请重新发起。"}

    if bridge.is_expired(request):
        if project_id and review_turn_id:
            _cleanup_review(project_id, review_turn_id)
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
        return {"request_id": request_id, "status": "failed", "error": "返回结果与任务不匹配，已丢弃。"}

    audit.append_event(request_id, audit.EVENT_BRIDGE_RESPONSE_RECEIVED, "review")

    resp_status = response.get("status")
    if resp_status != "completed":
        error = response.get("error") or f"执行结果状态异常：{resp_status}"
        if project_id and review_turn_id:
            _cleanup_review(project_id, review_turn_id)
        bridge.cleanup_request(request_id)
        _exec_task_manager.remove(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error=error)
        return {"request_id": request_id, "status": "failed", "error": error}

    payload = response.get("result")
    if not isinstance(payload, dict) or not payload.get("summary"):
        if project_id and review_turn_id:
            _cleanup_review(project_id, review_turn_id)
        bridge.cleanup_request(request_id)
        _exec_task_manager.remove(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error="检查结果无效，请重新发起。")
        return {"request_id": request_id, "status": "failed", "error": "检查结果无效，请重新发起。"}

    # 持久化报告元数据（供"丢弃已完成但未确认报告"时按 request_id 定位清理）
    review_dir = _review_dir(project_id, review_turn_id)
    review_dir.mkdir(parents=True, exist_ok=True)
    meta_payload = dict(payload)
    meta_payload["request_id"] = request_id
    (review_dir / "review_meta.json").write_text(
        json.dumps(meta_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    bridge.cleanup_request(request_id)
    _exec_task_manager.remove(request_id)
    audit.finish_file(request_id, audit.STATUS_COMPLETED)
    return {
        "request_id": request_id,
        "status": "completed",
        "result": payload,
    }


def cancel_review_request(request_id: str) -> dict[str, Any]:
    """取消/丢弃检查：终止运行中的 Direct adapter（如有）、标记 canceled、清理工作区。幂等。"""
    request_id = (request_id or "").strip()
    if not request_id:
        raise ReviewError("缺少任务标识（request_id）。")

    _exec_task_manager.cancel(request_id)

    request = bridge.get_request(request_id)
    if request is not None:
        bridge.mark_canceled(request_id)
        meta = request.get("meta") or {}
        project_id = str(meta.get("project_id") or "")
        review_turn_id = str(meta.get("review_turn_id") or "")
        if project_id and review_turn_id:
            _cleanup_review(project_id, review_turn_id)
        bridge.clear_active_if(request_id)
        audit.finish_file(request_id, audit.STATUS_CANCELED)
    else:
        _cleanup_discarded_review(request_id)
        # 已完成报告的记录已是 completed 终态：finish_file 幂等 no-op；
        # awaiting_confirmation 状态（如有）收尾为 canceled
        audit.finish_file(request_id, audit.STATUS_CANCELED)
    _exec_task_manager.remove(request_id)
    return {"request_id": request_id, "status": "canceled"}
