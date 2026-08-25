# -*- coding: utf-8 -*-
"""新建作品 Author Operations：第一条真实作者使用链（“我有个想法”）。

架构（已确认）：Go Write 管长期记忆；执行器按已保存 Settings 决定：
- Interactive（交互桥，默认）：Go Write 准备任务 → 作者在 Qoder 桌面端执行
  /gowrite（桌面端已配置好的模型）→ 写回 response；
- Direct（直连）：仅当 Settings 显式配置 Direct + 有效 Agent/模型时，通过现有
  Agent registry/adapter 后台执行同一任务（prepare 立即返回，可轮询/取消）。

链路（统一请求生命周期，两种模式共用同一任务文本与同一 finalize）：
  作者想法 → Go Write 准备本轮 Agent 任务（唯一 request_id + 完整 task +
  结果写回位置）→ Interactive 提示作者 /gowrite；Direct 后台执行
  → 写回同一响应信封 → request_id 校验 → 严格 JSON/字段验证
  → 现有 StoryDesign 生成 proposal_noncanonical 候选（临时 pre-project 工作区）
  → UI 展示 → 作者明确确认 → ProjectWorkspace.create_project 创建正式作品

知识选择绑定（与 StoryPlan/StoryWrite 同一 P0 规则）：
- knowledge_needs = []：不调用 KnowledgeRetrieve、不要求快照，0 BKP 合法；
- knowledge_needs 非空：模型在本次执行内运行唯一一次确定性检索命令
  （retrieval_snapshot.py --request <request_id> "<query>"），从该显示包选择
  scoped ref 并回显 package_fingerprint；finalize 绝不再次检索；
  同一捕获包绑定给 run_story_design(retrieval=bound_package)。

约束（遵守现有冻结合同）：
- 不修改 StoryDesign / ProjectWorkspace；不创建空壳项目。
- 确认前绝不写 03_作品工程；候选全部落在可删除的临时工作区。
- 确认必须带后台生成的 proposal token；禁止信任前端自行构造隐藏内容。
- Token 禁止进入 Prompt / UI / 日志 / Bridge 返回值。
- 新增作品只写 Author Intent + 空 Story State + 空索引；不生成正文。
- 桥文件全部在 06_工作区/应用开发/.qoder_bridge（Local Only，可删除）。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

from operations import agent_runner
from operations import execution_audit as audit
from operations import execution_tasks
from operations import qoder_bridge as bridge
from operations.agent_runner import AgentRunError
from config.settings import EXECUTION_MODE_DIRECT, SettingsStore
from operations.story_planning import (  # noqa: E402  复用同一 P0 检索包机制
    _DIRECT_BUSY_ERROR,
    _MAX_BKP_HITS,
    _bound_package,
    _package_fingerprint,
    _package_from_snapshot,
    _package_snapshot_dict,
    _retrieve_package,
)

# Direct 执行任务管理器（与 StoryPlan/StoryWrite/Review 共用同一单活跃槽）
_exec_task_manager = execution_tasks.manager

# ---------------------------------------------------------------------------
# Frozen runtime imports — NEVER copy their rules; always call them directly.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]

if str(_REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "StoryDesign") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "StoryDesign"))
if str(_REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))

from project_workspace import (  # noqa: E402  ProjectWorkspace frozen runtime
    ContractError as PWContractError,
    WorkspaceError as PWWorkspaceError,
    create_project,
    generate_project_id,
    load_project,
    persist_state_transition,
    validate_project_name,
)
from story_runtime import (  # noqa: E402  StoryDesign frozen runtime
    ContractError as SDContractError,
    apply_diff,
    create_decision_record,
    initialize_project,
    make_planning_diff,
    project_paths,
    write_json,
)
from story_design import run_story_design  # noqa: E402  StoryDesign orchestration

# 临时 pre-project 工作区根（06_工作区/应用开发 已 gitignore，Local Only，可删除）
_PROPOSALS_ROOT = (
    Path(__file__).resolve().parents[3] / "06_工作区" / "应用开发" / ".proposals"
)

# 请求级检索快照 CLI（Agent 在执行内运行；唯一确定性检索入口）
_RETRIEVAL_SCRIPT = Path(__file__).resolve().parent / "retrieval_snapshot.py"

# Agent 任务模板：两阶段。第一阶段语义分析；第二阶段（仅 knowledge_needs 非空）
# 运行确定性检索命令查看真实候选，然后从该候选中选择 scoped ref。模型不得在
# 见到检索结果前编造/选择 BKP id。作者想法放在最后，避免模型先回应角色设定。
_AGENT_TASK_TEMPLATE = """你是 Go Write 的故事设计执行器。必须严格按下列顺序执行：先完成语义分析；若 knowledge_needs 非空，必须在生成最终 JSON 之前先用本地命令/工具执行下面给出的检索命令并读取其结果；完成检索与选择后，才输出最终 JSON。本任务不是纯文本生成任务；中间的工具调用属于任务执行过程，不属于最终回复。

流程分两个阶段：

第一阶段：语义分析
针对作者想法，先完成语义分析（objective / knowledge_needs / assumptions）。knowledge_needs 为空列表是合法的。

第二阶段：知识检索与选择（仅当 knowledge_needs 非空；必须执行）
若 knowledge_needs 非空，在生成最终 JSON 之前，你必须先用可用的本地命令/工具执行以下确定性只读检索命令：
  python {retrieval_command} --request {request_id} "<query>"
其中 <query> 是把你第一阶段列出的全部 knowledge_needs 用中文分号（；）连接成的单个字符串。
该命令会把本次检索包写入当前请求的临时快照，然后输出 JSON；每个候选项的 selection_ref 为 "book_id/source_anchor"。
你必须读取该命令实际输出的 package：只从中选择 0 到 {max_bkp_hits} 个 selection_ref 填入 semantic_interpretation.selected_bkp_ids；并把命令输出的 package_fingerprint 原样填入 semantic_interpretation.package_ref。
严禁编造命令输出中不存在的 selection_ref 或 package_fingerprint；没有合适候选时 selected_bkp_ids 保持空列表。
若 knowledge_needs 为空：不要运行检索命令，selected_bkp_ids 必须为 []，package_ref 必须为空字符串 ""。

最终回复
最终回复必须只有合法 JSON 对象（不要任何额外文字、不要 markdown 代码块标记）。结构必须如下：

{{
  "semantic_interpretation": {{
    "scope": "story_design",
    "objective": "本次设计的目标（一句话）",
    "knowledge_needs": [],
    "selected_bkp_ids": [],
    "package_ref": "",
    "assumptions": ["AI 解读中的假设，作者尚未确认"]
  }},
  "model_output": {{
    "stance": ["story_engine"],
    "proposal": "作者可读的故事方向候选（一段话）",
    "work_direction": "作品方向（一两句话）",
    "reader_promise": "读者最主要的期待（一两句话）",
    "hard_constraints": ["最好守住的约束，作者确认前只是候选"],
    "open_space": ["可以自由变化的部分"],
    "unknowns": ["尚不确定、留待作者决定的部分"]
  }}
}}

作者作品名：{name}
作者想法：{idea}

最终回复必须只有合法 JSON；但在生成最终回复之前，若 knowledge_needs 非空，你必须先调用工具执行检索命令并读取结果。工具调用属于任务执行过程，不属于最终回复。"""

# StoryDesign 候选/工件 id（临时工作区内）
_BRIEF_ID = "brief-idea-001"
_CONTEXT_ID = "context-idea-001"
_CANDIDATE_ID = "design-idea-001"


class NewProjectError(Exception):
    """新建作品操作错误（面向 UI 的稳定错误类型，普通用户可读）。"""


# ---------------------------------------------------------------------------
# 临时 pre-project 工作区（可删除，绝不写 03_作品工程）
# ---------------------------------------------------------------------------

def get_proposals_root() -> Path:
    """临时候选工作区根目录（测试可 monkeypatch 此函数）。"""
    return _PROPOSALS_ROOT


def _proposal_dir(project_id: str) -> Path:
    return get_proposals_root() / project_id


def _write_temp_pre_project(proposal_dir: Path, project_id: str, name: str, idea: str, proposal_turn_id: str) -> None:
    """构造 StoryDesign 所需的临时 Author Intent + 空 Story State。

    内容明确属于 proposal / pre-project：project_id 用 generate_project_id(name)
    得到的未来 project_id；临时 intent 只做合同占位，不视为正式 authority。
    """
    paths = initialize_project(proposal_dir)
    temp_intent: dict[str, Any] = {
        "project_id": project_id,
        "intent_rev": 1,
        "work_direction": f"（临时候选前导，待作者确认）围绕作者想法展开：{idea[:120]}",
        "reader_promise": "（临时候选前导，待作者确认）",
        "hard_constraints": ["AI 候选在作者确认前不是作者决定"],
        "open_space": ["故事方向", "读者期待", "约束与自由空间"],
        "_pre_project": True,  # 标记：临时占位，非正式 authority
    }
    temp_state: dict[str, Any] = {
        "project_id": project_id,
        "state_rev": 1,
        "canon_facts": [],
        "character_state": [],
        "relationship_state": [],
        "occurred_events": [],
        "open_threads": [],
        "approved_plan": [],
        "last_authority_source": "pre_project:temp",
    }
    write_json(paths["intent"], temp_intent)
    write_json(paths["state"], temp_state)
    # 记录 pre-project 元信息（proposal token 用于确认时校验）
    meta = {
        "kind": "pre_project_proposal",
        "project_id": project_id,
        "name": name,
        "idea": idea,
        "proposal_token": uuid.uuid4().hex,
        "proposal_turn_id": proposal_turn_id,
    }
    write_json(proposal_dir / "proposal_meta.json", meta)


def _load_proposal_meta(project_id: str) -> dict[str, Any]:
    meta_path = _proposal_dir(project_id) / "proposal_meta.json"
    if not meta_path.exists():
        raise NewProjectError("候选已失效或不存在，请重新生成。")
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _cleanup_proposal(project_id: str) -> None:
    """删除临时候选工作区（可删除原则）。"""
    shutil.rmtree(_proposal_dir(project_id), ignore_errors=True)


# ---------------------------------------------------------------------------
# 知识选择绑定（P0，与 StoryPlan/StoryWrite 同规则；快照在 proposal 工作区）
# ---------------------------------------------------------------------------

def _snapshot_path(proposal_dir: Path) -> Path:
    return proposal_dir / "retrieval" / "package.json"


def _write_snapshot(
    *,
    request_id: str,
    project_id: str,
    proposal_turn_id: str,
    query: str,
    package: Any,
    proposal_dir: Path,
) -> Path:
    snapshot = {
        "schema": "gowrite_retrieval_snapshot/v1",
        "request_id": request_id,
        "project_id": project_id,
        "proposal_turn_id": proposal_turn_id,
        "query": query,
        "package_fingerprint": _package_fingerprint(package),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "package": _package_snapshot_dict(package),
    }
    path = _snapshot_path(proposal_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _load_snapshot(proposal_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    path = _snapshot_path(proposal_dir)
    if not path.exists():
        return None, "检索包快照缺失：Agent 未在本轮执行内生成检索快照。"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "检索包快照无法解析（已被篡改或损坏）。"
    if not isinstance(data, dict) or not isinstance(data.get("package"), dict):
        return None, "检索包快照结构无效（缺少 package 对象）。"
    return data, None


def _validate_snapshot(
    snapshot: dict[str, Any],
    *,
    request_id: str,
    project_id: str,
    proposal_turn_id: str,
    query: str,
    package_ref: str,
) -> None:
    if snapshot.get("request_id") != request_id:
        raise NewProjectError("检索包快照 request_id 与当前任务不一致，已拒绝。")
    if snapshot.get("project_id") != project_id:
        raise NewProjectError("检索包快照 project_id 与当前任务不一致，已拒绝。")
    if snapshot.get("proposal_turn_id") != proposal_turn_id:
        raise NewProjectError("检索包快照 proposal_turn_id 与当前任务不一致，已拒绝。")
    if snapshot.get("query") != query:
        raise NewProjectError("检索包快照查询与本次 knowledge_needs 不一致（query mismatch），已拒绝。")
    if not package_ref:
        raise NewProjectError("Agent 输出缺少检索包身份（package_ref）。")
    if snapshot.get("package_fingerprint") != package_ref:
        raise NewProjectError("Agent 选择的检索包身份（package_ref）与绑定快照不一致，已拒绝。")


def execute_request_scoped_retrieval(query: str, request_id: str) -> Any:
    """Agent 侧（执行内）的唯一一次确定性检索调用（显式绑定 request_id）。"""
    request = bridge.get_request(request_id)
    if request is None:
        raise NewProjectError("任务文件不存在或不可读，无法生成检索快照。")
    meta = request.get("meta") or {}
    project_id = str(meta.get("project_id") or "")
    proposal_turn_id = str(meta.get("proposal_turn_id") or "")
    if not project_id or not proposal_turn_id:
        raise NewProjectError("任务缺少 project_id / proposal_turn_id 元数据。")
    proposal_dir = _proposal_dir(project_id)
    audit.append_event(
        request_id, audit.EVENT_RETRIEVAL_REQUESTED, "knowledge_retrieve",
        details={"query": query[:200]},
    )
    try:
        package = _retrieve_package(query)  # 唯一一次 KnowledgeRetrieve 执行
    except NewProjectError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise NewProjectError(f"知识检索失败：{exc}") from exc
    _write_snapshot(
        request_id=request_id,
        project_id=project_id,
        proposal_turn_id=proposal_turn_id,
        query=query,
        package=package,
        proposal_dir=proposal_dir,
    )
    audit.append_event(
        request_id, audit.EVENT_RETRIEVAL_PACKAGE_BUILT, "knowledge_retrieve",
        details={
            "query": query[:200],
            "candidate_count": getattr(package, "candidate_count", len(getattr(package, "hits", []))),
            "refs": [
                f"{getattr(hit, 'book_id', '')}/{getattr(hit, 'source_anchor', '')}"
                for hit in getattr(package, "hits", [])
            ],
        },
    )
    return package


# ---------------------------------------------------------------------------
# 候选解析（Agent 输出必须是合法结构化结果）
# ---------------------------------------------------------------------------

def _validate_str_list(value: Any, field_name: str) -> None:
    """校验字段必须是 list[str]；类型错误抛 NewProjectError。"""
    if not isinstance(value, list):
        raise NewProjectError(f"Agent 输出字段 {field_name} 类型错误（应为列表）。")
    for i, item in enumerate(value):
        if not isinstance(item, str):
            raise NewProjectError(
                f"Agent 输出字段 {field_name}[{i}] 类型错误（应为字符串）。"
            )


def _extract_json_from_output(text: str) -> str:
    """从 Agent 输出中提取 JSON 对象字符串。

    策略链（按顺序尝试，第一个成功即返回）：
    1. 直接 json.loads（最快路径）
    2. 去掉 markdown 代码块包裹（含 ```json 等带语言标记的变体）
    3. 找文本中第一个 ``` 代码块围栏，提取其中内容
    4. 找最外层 { ... } 匹配
    """
    stripped = text.strip()
    if not stripped:
        return stripped

    try:
        json.loads(stripped)
        return stripped
    except (json.JSONDecodeError, ValueError):
        pass

    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2 and lines[-1].strip() == "```":
            inner = "\n".join(lines[1:-1]).strip()
            try:
                json.loads(inner)
                return inner
            except (json.JSONDecodeError, ValueError):
                pass

    lines = stripped.splitlines()
    fence_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            fence_start = i
            break
    if fence_start is not None:
        fence_end = None
        for i in range(len(lines) - 1, fence_start, -1):
            if lines[i].strip() == "```":
                fence_end = i
                break
        if fence_end is not None and fence_end > fence_start:
            inner = "\n".join(lines[fence_start + 1:fence_end]).strip()
            if inner:
                try:
                    json.loads(inner)
                    return inner
                except (json.JSONDecodeError, ValueError):
                    pass

    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidate = stripped[first_brace:last_brace + 1]
        try:
            json.loads(candidate)
            return candidate
        except (json.JSONDecodeError, ValueError):
            pass

    if stripped.startswith("```"):
        inner_lines = lines[1:]
        if inner_lines and inner_lines[-1].strip() == "```":
            inner_lines = inner_lines[:-1]
        return "\n".join(inner_lines).strip()
    return stripped


def _output_preview(output: str, max_len: int = 300) -> str:
    """截取 Agent 输出前 max_len 字符用于错误诊断（不打印密钥）。"""
    text = (output or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


def _parse_agent_result(output: str) -> dict[str, Any]:
    """把 Agent 输出解析成 {semantic_interpretation, model_output}。

    非法结构化结果：抛 NewProjectError（普通可读错误），不猜数据补齐、不落盘。
    严格类型检查：字段缺失或类型错误一律拒绝，不自动修复。
    """
    text = _extract_json_from_output(output)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        preview = _output_preview(output)
        raise NewProjectError(
            f"Agent 输出不是合法 JSON，请重试或更换想法表述。"
            f"\n\n--- Agent 输出预览 ---\n{preview}"
        ) from exc
    if not isinstance(data, dict):
        raise NewProjectError("Agent 输出不是合法结构化结果（应为 JSON 对象）。")

    si = data.get("semantic_interpretation")
    if not isinstance(si, dict):
        raise NewProjectError("Agent 输出缺少 semantic_interpretation（应为对象）。")
    if "scope" in si and not isinstance(si["scope"], str):
        raise NewProjectError("Agent 输出 semantic_interpretation.scope 类型错误（应为字符串）。")
    if not isinstance(si.get("objective"), str) or not si["objective"].strip():
        raise NewProjectError("Agent 输出 semantic_interpretation.objective 缺失或不是非空字符串。")
    if "knowledge_needs" not in si:
        raise NewProjectError("Agent 输出缺少 semantic_interpretation.knowledge_needs（应为列表）。")
    _validate_str_list(si["knowledge_needs"], "semantic_interpretation.knowledge_needs")
    if "selected_bkp_ids" not in si:
        raise NewProjectError("Agent 输出缺少 semantic_interpretation.selected_bkp_ids（应为列表）。")
    _validate_str_list(si["selected_bkp_ids"], "semantic_interpretation.selected_bkp_ids")
    if "package_ref" not in si or not isinstance(si.get("package_ref"), str):
        raise NewProjectError("Agent 输出缺少 semantic_interpretation.package_ref（应为字符串）。")
    if "assumptions" not in si:
        raise NewProjectError("Agent 输出缺少 semantic_interpretation.assumptions（应为列表）。")
    _validate_str_list(si["assumptions"], "semantic_interpretation.assumptions")

    mo = data.get("model_output")
    if not isinstance(mo, dict):
        raise NewProjectError("Agent 输出缺少 model_output（应为对象）。")
    if not isinstance(mo.get("proposal"), str) or not mo["proposal"].strip():
        raise NewProjectError("Agent 输出缺少作者可读的故事方向（model_output.proposal）。")
    if not isinstance(mo.get("work_direction"), str) or not mo["work_direction"].strip():
        raise NewProjectError("Agent 输出缺少作品方向（model_output.work_direction 应为非空字符串）。")
    if not isinstance(mo.get("reader_promise"), str) or not mo["reader_promise"].strip():
        raise NewProjectError("Agent 输出缺少读者期待（model_output.reader_promise 应为非空字符串）。")
    if "hard_constraints" not in mo:
        raise NewProjectError("Agent 输出缺少 model_output.hard_constraints（应为列表）。")
    _validate_str_list(mo["hard_constraints"], "model_output.hard_constraints")
    if "open_space" not in mo:
        raise NewProjectError("Agent 输出缺少 model_output.open_space（应为列表）。")
    _validate_str_list(mo["open_space"], "model_output.open_space")
    if "unknowns" in mo:
        _validate_str_list(mo["unknowns"], "model_output.unknowns")
    if "stance" in mo:
        _validate_str_list(mo["stance"], "model_output.stance")

    return {"semantic_interpretation": si, "model_output": mo}


# ---------------------------------------------------------------------------
# 准备本轮 Agent 任务（不运行模型；Interactive 提示 /gowrite，Direct 后台执行）
# ---------------------------------------------------------------------------

def prepare_new_project(name: str, idea: str) -> dict[str, Any]:
    """“我有个想法”：按已保存 Settings 执行模式准备本轮 Agent 任务。

    Interactive：创建 pending request，提示作者到 Qoder 执行 /gowrite；
    Direct：通过配置的 Agent/模型后台执行（prepare 立即返回，可轮询/取消）。
    """
    name = (name or "").strip()
    idea = (idea or "").strip()
    if not name:
        raise NewProjectError("请填写作品名。")
    if not idea:
        raise NewProjectError("请写下你的想法。")
    try:
        validate_project_name(name)
    except PWContractError as exc:
        raise NewProjectError(str(exc)) from exc

    project_id = generate_project_id(name)
    proposal_turn_id = uuid.uuid4().hex[:12]
    proposal_dir = _proposal_dir(project_id)
    if proposal_dir.exists():
        shutil.rmtree(proposal_dir, ignore_errors=True)
    _write_temp_pre_project(proposal_dir, project_id, name, idea, proposal_turn_id)

    # 解析执行配置（Settings 契约；agent_runner._build_adapter 负责直连解析）
    settings = SettingsStore().load()
    execution_mode = settings.default_execution_mode

    # 预生成 request_id（检索命令需要内嵌真实 id；Interactive/Direct 共用）
    request_id = uuid.uuid4().hex
    task = _AGENT_TASK_TEMPLATE.format(
        name=name,
        idea=idea,
        retrieval_command=f'"{_RETRIEVAL_SCRIPT}"',
        request_id=request_id,
        max_bkp_hits=_MAX_BKP_HITS,
    )

    direct_adapter = None
    direct_agent_request = None
    execution_agent = settings.interactive_agent
    execution_model = None
    if execution_mode == EXECUTION_MODE_DIRECT:
        try:
            direct_adapter, direct_agent_request = agent_runner._build_adapter()
        except AgentRunError as exc:
            _cleanup_proposal(project_id)
            raise NewProjectError(f"直连执行配置不可用：{exc}") from exc
        except Exception as exc:  # noqa: BLE001
            _cleanup_proposal(project_id)
            raise NewProjectError(f"直连执行配置不可用：{exc}") from exc
        execution_agent = direct_adapter.name
        execution_model = direct_agent_request.custom_model or direct_agent_request.model
        if _exec_task_manager.is_busy():
            _cleanup_proposal(project_id)
            raise NewProjectError(_DIRECT_BUSY_ERROR)

    bridge.create_request(
        task=task,
        kind="story_design_propose",
        meta={
            "name": name,
            "idea": idea,
            "project_id": project_id,
            "proposal_turn_id": proposal_turn_id,
            "execution": {
                "execution_mode": execution_mode,
                "agent_id": execution_agent,
                "model": execution_model,
            },
        },
        request_id=request_id,
    )

    # 把 request_id 持久化到 proposal_meta.json，使"丢弃已完成但未确认候选"
    # 能按 request_id 定位并清理工作区（proposal token 随之失效）。
    meta_path = proposal_dir / "proposal_meta.json"
    if meta_path.exists():
        _meta = json.loads(meta_path.read_text(encoding="utf-8"))
        _meta["request_id"] = request_id
        write_json(meta_path, _meta)

    # 验证式审计（operation.started；交互桥只标 waiting，绝不声称 Agent 已启动）
    # 必须先于 Direct worker 创建（worker 内 append_event 依赖进程内 recorder）。
    execution_facts = {
        "execution_mode": execution_mode,
        "agent_id": execution_agent,
        "model": execution_model,
    }
    recorder = audit.AuditRecorder(
        request_id, "new_project", project_id, execution=execution_facts,
    )
    if execution_mode != EXECUTION_MODE_DIRECT:
        recorder.event(audit.EVENT_BRIDGE_WAITING, component="new_project")

    message = "任务已准备好，请到 Qoder 输入 /gowrite 并回车。"
    if execution_mode == EXECUTION_MODE_DIRECT:
        message = "任务已通过直连模式后台执行，正在校验结果。"
        _start_direct_execution(
            direct_adapter, direct_agent_request, task, request_id,
            project_id=project_id,
        )

    return {
        "request_id": request_id,
        "name": name,
        "status": "task_prepared",
        "execution_mode": execution_mode,
        "agent_id": execution_agent,
        "model": execution_model,
        "message": message,
    }


# ---------------------------------------------------------------------------
# Direct 后台执行
# ---------------------------------------------------------------------------

def _start_direct_execution(
    adapter: Any,
    agent_request: Any,
    task: str,
    request_id: str,
    *,
    project_id: str,
) -> None:
    execution = {
        "execution_mode": "direct",
        "agent_id": adapter.name,
        "model": agent_request.custom_model or agent_request.model,
    }
    worker = lambda: _dispatch_direct_worker(adapter, agent_request, task, request_id)  # noqa: E731
    if not _exec_task_manager.start(request_id=request_id, worker=worker, adapter=adapter, execution=execution):
        _cleanup_proposal(project_id)
        bridge.cleanup_request(request_id)
        raise NewProjectError(_DIRECT_BUSY_ERROR)


def _dispatch_direct_worker(adapter: Any, agent_request: Any, task: str, request_id: str) -> None:
    """后台 worker：执行唯一一次 Direct Agent 调用并写回现有响应信封。"""
    agent_request.task = task
    agent_request.cwd = str(_REPO_ROOT)
    audit.append_event(
        request_id, audit.EVENT_AGENT_DIRECT_PROCESS_STARTED, "new_project",
        details={"agent": adapter.name},
    )
    try:
        result = adapter.run(agent_request)
    except Exception as exc:  # noqa: BLE001
        audit.append_event(request_id, audit.EVENT_AGENT_FAILED, "new_project", details={"error": str(exc)[:200]})
        _finish_direct(request_id, status="failed", error=f"直连执行失败：{exc}")
        return
    if _exec_task_manager.is_canceled(request_id):
        return
    if result.status != "completed":
        audit.append_event(
            request_id,
            audit.EVENT_AGENT_FAILED if result.status != "cancelled" else audit.EVENT_AGENT_CANCELED,
            "new_project", details={"error": (result.error or "")[:200]},
        )
        _finish_direct(
            request_id,
            status="failed",
            error=result.error or f"直连执行未完成（status={result.status}）。",
        )
        return
    audit.append_event(request_id, audit.EVENT_AGENT_COMPLETED, "new_project")
    _finish_direct(request_id, status="completed", output=result.output or "")


def _finish_direct(request_id: str, *, status: str, output: str = "", error: str | None = None) -> None:
    # 审计记录不在这里收尾（finalize 事件由 get_new_project_request 追加后 finish）
    if _exec_task_manager.is_canceled(request_id):
        return
    bridge.write_response(request_id, status=status, output=output or None, error=error)
    _exec_task_manager.finish(
        request_id,
        execution_tasks.TASK_COMPLETED if status == "completed" else execution_tasks.TASK_FAILED,
    )


# ---------------------------------------------------------------------------
# 等待/检测写回结果（request_id 校验 → 严格解析 → StoryDesign 候选）
# ---------------------------------------------------------------------------

def _response_output_text(response: dict[str, Any]) -> str:
    result = response.get("result")
    if isinstance(result, dict) and result:
        return json.dumps(result, ensure_ascii=False)
    output = response.get("output")
    if isinstance(output, str) and output.strip():
        return output
    raise NewProjectError("Qoder 返回结果缺少模型输出。")


def _finalize_request(request: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    """response → request_id 校验 → 现有严格业务解析 → StoryDesign 候选。"""
    if response.get("request_id") != request["request_id"]:
        raise NewProjectError("返回结果与任务不匹配（request_id 不一致），已丢弃。")

    resp_status = response.get("status")
    if resp_status not in (None, "completed"):
        err = response.get("error") or f"Qoder 返回状态异常：{resp_status}"
        raise NewProjectError(err)

    raw = _response_output_text(response)
    parsed = _parse_agent_result(raw)

    meta = request.get("meta") or {}
    project_id = str(meta.get("project_id") or "")
    proposal_turn_id = str(meta.get("proposal_turn_id") or "")
    proposal_dir = _proposal_dir(project_id)

    # 知识选择绑定（P0：只从精确捕获包选择，绝不再次检索）
    knowledge_needs = list(parsed["semantic_interpretation"].get("knowledge_needs") or [])
    selected_refs = list(parsed["semantic_interpretation"].get("selected_bkp_ids") or [])
    package_ref = str(parsed["semantic_interpretation"].get("package_ref") or "")
    retrieval = None
    if knowledge_needs:
        query = "；".join(knowledge_needs)
        snapshot, load_error = _load_snapshot(proposal_dir)
        if load_error:
            _cleanup_proposal(project_id)
            raise NewProjectError(load_error)
        try:
            _validate_snapshot(
                snapshot,
                request_id=request["request_id"],
                project_id=project_id,
                proposal_turn_id=proposal_turn_id,
                query=query,
                package_ref=package_ref,
            )
        except NewProjectError:
            _cleanup_proposal(project_id)
            raise
        package = _package_from_snapshot(snapshot)
        retrieval = _bound_package(package, query)
        audit.append_event(
            request["request_id"], audit.EVENT_RETRIEVAL_SELECTED, "knowledge_retrieve",
            details={"query": query, "refs": selected_refs, "package_ref": package_ref},
        )
    elif selected_refs or package_ref:
        _cleanup_proposal(project_id)
        raise NewProjectError("没有知识需求却选择了 BKP 卡或检索包身份，已拒绝。")

    audit.append_event(
        request["request_id"], audit.EVENT_SKILL_STARTED, "new_project", details={"skill": "StoryDesign"},
    )
    try:
        sd_result = run_story_design(
            project_dir=proposal_dir,
            author_input=meta.get("idea") or "",
            brief_id=_BRIEF_ID,
            context_id=_CONTEXT_ID,
            candidate_id=_CANDIDATE_ID,
            semantic_interpretation=parsed["semantic_interpretation"],
            model_output=parsed["model_output"],
            retrieval=retrieval,
        )
    except SDContractError as exc:
        audit.append_event(
            request["request_id"], audit.EVENT_SKILL_FAILED, "new_project", details={"skill": "StoryDesign"},
        )
        raise NewProjectError(f"StoryDesign 拒绝生成候选：{exc}") from exc
    audit.append_event(
        request["request_id"], audit.EVENT_SKILL_COMPLETED, "new_project", details={"skill": "StoryDesign"},
    )
    audit.append_event(
        request["request_id"], audit.EVENT_CONTEXT_BOUND, "context_compiler",
        details={"context_id": _CONTEXT_ID, "refs": selected_refs},
    )
    audit.append_event(
        request["request_id"], audit.EVENT_CANDIDATE_CREATED, "new_project",
        details={"candidate_id": _CANDIDATE_ID},
    )

    candidate = sd_result["candidate"]
    if candidate.get("status") != "proposal_noncanonical":
        raise NewProjectError("候选状态异常（非 proposal_noncanonical），已中止。")

    proposal_meta = _load_proposal_meta(project_id)
    content = candidate.get("content") or {}
    retrieval_info = (sd_result.get("context") or {}).get("retrieval") or {}
    return {
        "proposal_token": proposal_meta["proposal_token"],
        "project_id": project_id,
        "name": meta.get("name") or "",
        "status": "proposal_noncanonical",
        "candidate": {
            "work_direction": content.get("work_direction") or "",
            "proposal": content.get("proposal") or "",
            "reader_promise": content.get("reader_promise") or "",
            "hard_constraints": content.get("hard_constraints") or [],
            "open_space": content.get("open_space") or [],
            "unknowns": content.get("unknowns") or [],
        },
        "knowledge": {
            "retrieval_status": retrieval_info.get("status"),
            "retrieved_count": retrieval_info.get("candidate_count", 0),
            "selected_count": len(selected_refs),
            "gaps": retrieval_info.get("gaps", []),
        },
        "execution": dict(meta.get("execution") or {}),
        "message": "候选已生成（未写入正式作品，等待你的确认）",
    }


def get_new_project_request(request_id: str) -> dict[str, Any]:
    """轮询写回结果（UI 每 2-3 秒调用一次）。

    返回 status：pending（继续等）/ completed（含候选）/ failed / expired / canceled。
    """
    request_id = (request_id or "").strip()
    if not request_id:
        raise NewProjectError("缺少任务标识（request_id）。")

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
        audit.finish_file(
            request_id, audit.STATUS_FAILED, error=request.get("error") or "任务失败，请重新发起。",
        )
        return {
            "request_id": request_id,
            "status": "failed",
            "error": request.get("error") or "任务失败，请重新发起。",
        }

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

    audit.append_event(
        request_id, audit.EVENT_BRIDGE_RESPONSE_RECEIVED, "new_project",
        details={"execution_mode": (request.get("meta") or {}).get("execution", {}).get("execution_mode")},
    )
    try:
        result = _finalize_request(request, response)
    except NewProjectError as exc:
        if project_id:
            _cleanup_proposal(project_id)
        bridge.cleanup_request(request_id)
        _exec_task_manager.remove(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
        return {"request_id": request_id, "status": "failed", "error": str(exc)}

    bridge.cleanup_request(request_id)
    _exec_task_manager.remove(request_id)
    audit.finish_file(request_id, audit.STATUS_COMPLETED)
    return {"request_id": request_id, "status": "completed", "result": result}


def _cleanup_discarded_proposal(request_id: str) -> None:
    """丢弃已完成但未确认的候选：按 proposal_meta.json 中持久化的 request_id
    定位并删除其临时 proposal 工作区（proposal token 随之失效，confirm 将拒绝）。
    """
    root = get_proposals_root()
    if not root.exists():
        return
    for meta_file in root.glob("*/proposal_meta.json"):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if meta.get("request_id") != request_id:
            continue
        project_id = str(meta.get("project_id") or "")
        if project_id:
            _cleanup_proposal(project_id)
        else:
            shutil.rmtree(meta_file.parent, ignore_errors=True)
        return


def cancel_new_project_request(request_id: str) -> dict[str, Any]:
    """取消等待：终止运行中的 Direct adapter（如有）、标记 canceled、
    删除 response 与临时候选。幂等。"""
    request_id = (request_id or "").strip()
    if not request_id:
        raise NewProjectError("缺少任务标识（request_id）。")

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
        _cleanup_discarded_proposal(request_id)
    _exec_task_manager.remove(request_id)
    return {"request_id": request_id, "status": "canceled"}


# ---------------------------------------------------------------------------
# 作者明确确认后创建正式作品
# ---------------------------------------------------------------------------

def confirm_new_project(proposal_token: str) -> dict[str, Any]:
    """作者明确确认：用后台保存的那一版候选创建正式作品。

    确认必须带后台生成的 proposal token；前端不能仅凭一句 confirmed=true
    写入任意内容。创建成功后：
    - 通过 frozen validate_author_intent 的正式 author_intent
    - 通过现有 StoryDesign Decision / planning diff / persist_state_transition
      登记 approved direction（不新增 Schema、不直接改 JSON）
    - 不生成正文、不进入 StoryPlan / StoryWrite
    """
    proposal_token = (proposal_token or "").strip()
    if not proposal_token:
        raise NewProjectError("缺少候选确认标识（proposal token）。")

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
        raise NewProjectError("候选已失效或不存在，请重新生成。")

    meta = json.loads((matched / "proposal_meta.json").read_text(encoding="utf-8"))
    project_id = meta["project_id"]
    name = meta["name"]

    candidate_path = matched / "designs" / f"{_CANDIDATE_ID}.json"
    if not candidate_path.exists():
        raise NewProjectError("候选数据缺失，请重新生成。")
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    content = candidate.get("content") or {}

    author_intent = {
        "work_direction": content.get("work_direction") or "",
        "reader_promise": content.get("reader_promise") or "",
        "hard_constraints": content.get("hard_constraints") or [],
        "open_space": content.get("open_space") or [],
    }
    if not author_intent["work_direction"] or not author_intent["reader_promise"]:
        raise NewProjectError("候选缺少完整的故事方向，无法创建正式作品。")

    try:
        created = create_project(name=name, author_intent=author_intent)
    except (PWContractError, PWWorkspaceError) as exc:
        raise NewProjectError(str(exc)) from exc

    project_dir = Path(created["project_dir"])
    direction_registered = False
    warning: Optional[str] = None
    state_rev: Optional[int] = None
    try:
        brief = json.loads((matched / "briefs" / f"{_BRIEF_ID}.json").read_text(encoding="utf-8"))
        context = json.loads((matched / "contexts" / f"{_CONTEXT_ID}.json").read_text(encoding="utf-8"))
        loaded = load_project(project_dir)
        base_state = loaded["state"]
        state_rev = base_state.get("state_rev")

        decision_id = f"decision-{project_id}"
        plan_id = f"plan-{project_id}"
        decision = create_decision_record(
            decision_id=decision_id,
            brief=brief,
            context=context,
            candidate=candidate,
            author_action="choose",
            author_confirmation_ref=f"author:workbench:{proposal_token}",
            final_decision={"selected": "confirmed_direction"},
        )
        diff = make_planning_diff(
            diff_id=f"diff-{project_id}",
            state=base_state,
            decision=decision,
            plan={
                "id": plan_id,
                "text": author_intent["work_direction"],
                "kind": "confirmed_direction",
            },
        )
        new_state = apply_diff(base_state, diff, decision)
        persist_state_transition(
            project_dir=str(project_dir),
            expected_base_state=base_state,
            new_state=new_state,
        )
        state_rev = new_state.get("state_rev")
        direction_registered = True
    except Exception:  # noqa: BLE001 — 任何后处理异常都算 partial success
        direction_registered = False
        warning = "作品已创建，但故事方向的规划登记未完成。正式 Author Intent 已保存。"
    finally:
        _cleanup_proposal(project_id)

    # 审计：作者确认（authority.confirmed）；request_id 可能为空（兼容旧候选）
    audit.append_event(
        str(meta.get("request_id") or ""), audit.EVENT_AUTHORITY_CONFIRMED, "new_project",
        details={"project_id": created["project_id"], "direction_registered": direction_registered},
    )
    audit.finish_file(str(meta.get("request_id") or ""), audit.STATUS_COMPLETED)

    return {
        "project_id": created["project_id"],
        "name": created["name"],
        "project_dir": str(created["project_dir"]),
        "state_rev": state_rev,
        "approved_direction_registered": direction_registered,
        "warning": warning,
        "message": "作品已创建",
    }
