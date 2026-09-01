# -*- coding: utf-8 -*-
"""故事规划 Author Operations：第二条真实作者使用链（"一起往前想"）。

链路（统一请求生命周期，执行模式由已保存 Settings 决定）：
  作品概览 → 作者自然语言提出"接下来想怎么发展"
  → Go Write 读取 Settings 执行配置 → 准备本轮 Agent 任务（pending request）
  → Interactive：提示作者到 Qoder 桌面端执行 /gowrite；
     Direct：Go Write 通过现有 Agent registry/adapter 与精确配置的内置/
     自定义模型在后台任务管理器执行同一任务（prepare 立即返回，可轮询/取消）
  → 两种模式都写回同一请求响应信封 → 同一严格 finalize
  → 现有 StoryPlan 形成 proposal_noncanonical 候选（临时 planning 工作区）
  → UI 展示 → 作者明确确认 → approved_plan writeback → 刷新概览

知识选择绑定（Knowledge Selection Binding，当前 P0 真实使用阻塞）：
- Agent 任务不再要求模型在见到检索结果前编造/选择知识 ref。
- knowledge_needs = []：不调用 KnowledgeRetrieve，不要求快照，选择知识为空，
  规划正常继续，0 条知识是一等合法结果。
- knowledge_needs 非空：Agent 在本次 /gowrite 执行内运行
  `retrieval_snapshot.py "<query>"` —— 这是整个流程中**唯一一次**确定性
  KnowledgeRetrieve 执行（统一多源：参考作品 BKP / 方法知识 / 已验证知识混合在同一个包内，模型不选择存储）。该调用同时：
    a) 把候选（含 selection_ref = source_kind/source_id/source_anchor、
       scope/boundary/provenance 与 package_fingerprint）返回给模型；
    b) 把精确序列化 RetrievalPackage 写入请求级快照
       （<planning_dir>/retrieval/package.json，非权威、可删除、随临时
       planning 生命周期清理），并绑定 request_id/project_id/
       planning_turn_id/query/指纹。
  模型只从该显示包中选择 selection_ref，并在最终 JSON 中回显 package_fingerprint。
- Go Write finalize **绝不再次执行 KnowledgeRetrieve**：只读取已存在的快照，
  校验请求/项目/planning turn/查询/包身份，把反序列化后的包绑定给 Context。
  快照缺失、无法解析、身份或查询不匹配 → 拒绝本次知识选择（整轮 failed）。
  旧版快照不兼容，fail closed。

约束（遵守现有冻结合同）：
- 不修改 StoryPlan / StoryDesign / ProjectWorkspace；不创建空壳规划。
- 确认前绝不写正式 Story State；候选全部落在可删除的临时工作区。
- 确认必须带后台生成的 planning token；禁止信任前端自行构造隐藏内容。
- Token 禁止进入 Prompt / UI / 日志 / Bridge 返回值。
- 不生成正文；不进入 StoryWrite。
- 执行模式由已保存的 Settings 决定（复用现有 Settings 契约，不重复解析、不造路由）：
  - Interactive（交互桥）：保留现有 Qoder Desktop /gowrite 流程，Go Write
    不调用后台 Agent。
  - Direct（直连）：仅当 Settings 显式配置 Direct + 有效 Agent/模型且作者
    明确发起 StoryPlan 动作时，才通过现有 Agent registry/adapter 与精确配置的
    内置/自定义模型执行；绝不隐藏调用、绝不静默回退到其他 Agent/模型或交互模式。
- 两种模式使用同一个任务文本、同一个请求生命周期、同一个 _finalize_story_plan。
"""
from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import shutil
import sys
import types
import uuid
from pathlib import Path
from typing import Any, Callable

from operations import agent_runner
from operations import execution_audit as audit
from operations import execution_tasks
from operations import qoder_bridge as bridge
from operations import project_model as project_model_ops
from operations.project_snapshot import focused_task_context, get_project_snapshot
from operations.agent_runner import AgentRunError
from config.settings import EXECUTION_MODE_DIRECT, SettingsStore

# Direct 执行任务管理器（in-process 单活跃槽；测试可替换为独立实例）
_exec_task_manager = execution_tasks.manager

# 稳定忙碌错误：另一个 Direct StoryPlan 任务正在执行
_DIRECT_BUSY_ERROR = "已有直连规划任务正在执行，请先等待其完成或取消该任务，再发起新的规划。"

# ---------------------------------------------------------------------------
# Frozen runtime imports — NEVER copy their rules; always call them directly.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]

if str(_REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "StoryPlan") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "StoryPlan"))
if str(_REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))

from project_workspace import (  # noqa: E402  ProjectWorkspace frozen runtime
    ContractError as PWContractError,
    WorkspaceError as PWWorkspaceError,
    load_project,
    persist_state_transition,
    resolve_project,
    _safe_write_file,
)
from story_plan import (  # noqa: E402  StoryPlan frozen runtime
    ContractError as SPContractError,
    apply_diff,
    compile_plan_brief,
    create_decision_record,
    initialize_project,
    make_plan_diff,
    resolve_plan_activity,
    run_story_plan,
    write_json,
    read_json,
)

# 临时 planning 工作区根（06_工作区/应用开发 已 gitignore，Local Only，可删除）
_PLANNING_ROOT = (
    Path(__file__).resolve().parents[3] / "06_工作区" / "应用开发" / ".planning"
)

# 请求级检索快照 CLI（Agent 在 /gowrite 执行内运行；唯一的确定性检索入口）。
# 它同时把候选返回给模型，并把精确序列化 RetrievalPackage 写入请求级快照。
_RETRIEVAL_SCRIPT = Path(__file__).resolve().parent / "retrieval_snapshot.py"

# 单次规划允许注入的最大知识条数（与 E1 build_context 默认上限一致）
_MAX_KNOWLEDGE_HITS = 3

# Agent 任务模板：两阶段。第一阶段语义分析；第二阶段（仅 knowledge_needs
# 非空）运行确定性检索命令查看真实候选，然后从该候选中选择 selection_ref。
# 模型不得在见到检索结果前编造/选择知识 ref。
_AGENT_TASK_TEMPLATE = """你是 Go Write 的规划执行器。必须严格按下列顺序执行：先完成语义分析；若 knowledge_needs 非空，必须在生成最终 JSON 之前先用本地命令/工具执行下面给出的检索命令并读取其结果；完成检索与选择后，才输出最终 JSON。本任务不是纯文本生成任务；中间的工具调用属于任务执行过程，不属于最终回复。

流程分两个阶段：

第一阶段：语义分析
针对作者规划问题，先完成语义分析（objective / knowledge_needs / assumptions / deliberate_open_space），并给出规划目标（planning_target）与规划建议草稿（model_output）。knowledge_needs 为空列表是合法的。

第二阶段：知识检索与选择（仅当 knowledge_needs 非空；必须执行）
若 knowledge_needs 非空，在生成最终 JSON 之前，你必须先用可用的本地命令/工具执行以下确定性只读检索命令：
  python {retrieval_command} "<query>"
其中 <query> 是把你第一阶段列出的全部 knowledge_needs 用中文分号（；）连接成的单个字符串（直接替换命令中的 <query> 占位符）。
该命令会把本次检索包（RetrievalPackage，混合参考作品知识/方法知识/已验证知识）写入当前请求的临时快照（不改动任何作品或业务文件），然后向终端输出一个 JSON，其中 package_fingerprint 是本次检索包的身份指纹，package.hits 数组内每个候选项含 selection_ref、source_kind、source_id、source_title、statement、scope、boundary、evidence 等字段；selection_ref 形如 "<source_kind>/<source_id>/<source_anchor>"（例如 reference_bkp/book_a/K001、method_source/book_0138/M0003、validated_knowledge/pkg_opening_hook/V0001）。
你必须读取该命令实际输出的 package：只从中选择 0 到 {max_knowledge_hits} 个 selection_ref，填入 semantic_interpretation.selected_knowledge_refs；并把命令输出的 package_fingerprint 原样填入 semantic_interpretation.package_ref。
严禁编造命令输出中不存在的 selection_ref 或 package_fingerprint；若没有合适的候选，selected_knowledge_refs 保持空列表（0 条知识是合法结果）。
若 knowledge_needs 为空：不要运行检索命令，selected_knowledge_refs 必须为 []，package_ref 必须为空字符串 ""。

最终回复
最终回复必须只有合法 JSON 对象（不要任何额外文字、不要 markdown 代码块标记）。结构必须如下：

{{
  "semantic_interpretation": {{
    "objective": "本次规划的目标（一句话）",
    "knowledge_needs": [],
    "selected_knowledge_refs": [],
    "package_ref": "",
    "assumptions": ["AI 解读中的假设，作者尚未确认"],
    "deliberate_open_space": ["作者明确保留自由的部分"]
  }},
  "planning_target": {{
    "description": "规划范围的语义描述（一句话）",
    "scope_kind": "free",
    "scope": "可选的范围说明"
  }},
  "model_output": {{
    "proposal": "作者可读的整体规划建议（一段话）",
    "planning_items": [
      {{"description": "第一条规划建议"}},
      {{"description": "第二条规划建议"}}
    ]
  }},
  "planning_projection": {{
    "domain_profile": null,
    "characters": [{{"key": "本候选内唯一人物键", "title": "人物名", "one_line_intro": "可选", "role_identity": "可选", "goal_desire": "可选"}}],
    "relationships": [{{"source_key": "人物键", "target_key": "人物键", "label": "关系", "description": "可选"}}],
    "settings": [{{"key": "唯一键", "title": "设定名", "description": "可选"}}],
    "systems": [{{"key": "唯一键", "title": "通用系统名", "type": "武力/职业/声誉/经济/自定义等", "levels_stages": []}}],
    "locations": [{{"key": "唯一键", "title": "地点名", "type": "可选"}}],
    "organizations": [{{"key": "唯一键", "title": "组织名", "purpose": "可选"}}],
    "storylines": [{{"key": "唯一键", "title": "故事线名", "description": "可选"}}],
    "events": [{{"key": "唯一键", "title": "计划事件", "description": "可选", "time_anchor": "仅显式已知时填写"}}],
    "foreshadowing": [{{"key": "唯一键", "title": "伏笔/承诺", "status": "planned", "description": "可选"}}],
    "mystery_information": [],
    "chapter_changes": [{{"title": "第1章", "chapter_number": 1, "min_words": 2500, "max_words": 4000, "task": "章节任务", "previous_recap": "上一章实际回顾", "synopsis": "章节梗概", "pov": "可选", "planned_location": "可选", "planned_time": "仅显式", "participating_characters": [], "new_characters": [], "key_beats": [], "foreshadowing": [], "conflict": "", "emotional_movement": "", "information_release_gap": "", "end_state_hook": "", "storyline": "", "stage": "", "notes": ""}}]
  }}
}}

planning_projection 只投影 model_output 中明确出现的结构化事实；未提到的类别必须是空列表，domain_profile 未涉及时为 null。所有投影仍是 future/planned，不是当前 Canon。关系端点可引用本投影 characters 的 key，或上下文给出的明确人物 ref，绝不按姓名猜测。章节变化只有在候选明确给出合法目标字数范围时才填写，否则保持空列表。世界/人物/关系/system/伏笔设计需要外部方法时可声明对应 knowledge_needs；空 needs 不检索。

作品信息：
- 作品名：{name}
- 已确定的故事方向：{work_direction}
- 读者主要期待：{reader_promise}
- 当前已守住的约束：{hard_constraints}
- 当前可以自由变化的部分：{open_space}
- 当前已确定的规划：
{current_planning}

作者本轮问题：{author_question}

最终回复必须只有合法 JSON；但在生成最终回复之前，若 knowledge_needs 非空，你必须先调用工具执行检索命令并读取结果。工具调用属于任务执行过程，不属于最终回复。"""


class StoryPlanningError(Exception):
    """故事规划操作错误（面向 UI 的稳定错误类型，普通用户可读）。"""


# ---------------------------------------------------------------------------
# 临时 planning 工作区
# ---------------------------------------------------------------------------

def get_planning_root() -> Path:
    """临时规划工作区根目录（测试可 monkeypatch 此函数）。"""
    return _PLANNING_ROOT


def _planning_dir(project_id: str, planning_turn_id: str) -> Path:
    return get_planning_root() / project_id / planning_turn_id


def _cleanup_planning(project_id: str, planning_turn_id: str) -> None:
    """确认后删除临时规划工作区（可删除原则）。"""
    shutil.rmtree(_planning_dir(project_id, planning_turn_id), ignore_errors=True)


# ---------------------------------------------------------------------------
# Knowledge Selection Binding：精确检索包捕获、快照与绑定
# ---------------------------------------------------------------------------

def _retrieve_package(query: str) -> Any:
    """运行现有 KnowledgeRetrieve 能力（确定性、无模型调用），返回 RetrievalPackage。

    与 Agent 在 /gowrite 执行内运行的命令使用同一脚本、同一 top_k 默认值，
    保证"模型实际看到的候选"与"Go Write 捕获的精确检索包"一致。
    """
    retrieve_dir = _REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "KnowledgeRetrieve"
    if str(retrieve_dir) not in sys.path:
        sys.path.insert(0, str(retrieve_dir))
    module_name = "ai_write_knowledge_retrieve_runtime"
    module = sys.modules.get(module_name)
    if module is None:
        spec = importlib.util.spec_from_file_location(module_name, retrieve_dir / "run.py")
        if spec is None or spec.loader is None:
            raise StoryPlanningError("无法加载 KnowledgeRetrieve")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    return module.retrieve(query)


def _package_snapshot_dict(package: Any) -> dict[str, Any]:
    """把 RetrievalPackage 序列化为可比较、可重建的字典（非权威记录；通用身份）。"""
    if hasattr(package, "to_dict"):
        return package.to_dict()
    return {
        "status": getattr(package, "status", "OK"),
        "candidate_count": getattr(package, "candidate_count", 0),
        "hits": [
            {
                "selection_ref": getattr(hit, "selection_ref", "") or (
                    f"{getattr(hit, 'source_kind', '')}/{getattr(hit, 'source_id', '')}/"
                    f"{getattr(hit, 'source_anchor', '')}"),
                "source_kind": getattr(hit, "source_kind", ""),
                "source_id": getattr(hit, "source_id", ""),
                "source_title": getattr(hit, "source_title", ""),
                "source_anchor": getattr(hit, "source_anchor", ""),
                "source": getattr(hit, "source", ""),
                "statement": getattr(hit, "statement", ""),
                "scope": getattr(hit, "scope", None),
                "boundary": getattr(hit, "boundary", None),
                "confidence": getattr(hit, "confidence", None),
                "evidence": list(getattr(hit, "evidence", []) or []),
                "rank": getattr(hit, "rank", 0),
                "relevance_reason": getattr(hit, "relevance_reason", ""),
            }
            for hit in getattr(package, "hits", [])
        ],
    }


def _package_fingerprint(package: Any) -> str:
    """确定性包身份指纹（基于序列化包内容的 SHA-256）。

    Agent 回显此指纹（package_ref）；finalize 用它校验"模型声称选择的包"
    与请求级快照中的包是同一个。
    """
    canonical = json.dumps(
        _package_snapshot_dict(package), ensure_ascii=False, sort_keys=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _bound_package(package: Any, query: str) -> Callable[[str], Any]:
    """把"本次 planning turn 使用的精确检索包"绑定为 Context 的 retrieval 闭包。

    Context（E1 build_context）只消费这个包；任何与绑定查询不一致的调用
    都视为包不匹配，直接拒绝，绝不触发一次无关的后续检索。
    """

    def _retrieval(q: str) -> Any:
        if q != query:
            raise SPContractError(
                f"Context 检索查询与绑定包不一致：{q!r} != {query!r}"
            )
        return package

    return _retrieval


def _snapshot_path(planning_dir: Path) -> Path:
    """请求级检索包快照位置（planning turn 内，随临时规划生命周期清理）。"""
    return planning_dir / "retrieval" / "package.json"


def _write_snapshot(
    *,
    request_id: str,
    project_id: str,
    planning_turn_id: str,
    query: str,
    package: Any,
    planning_dir: Path,
) -> Path:
    """把精确序列化 RetrievalPackage 写入请求级快照（非权威、可删除）。

    快照绑定 request_id / project_id / planning_turn_id / 归一化 query /
    包指纹。由 Agent 侧的"唯一一次检索调用"（execute_request_scoped_retrieval）
    在模型选择候选之前写入。
    """
    snapshot = {
        "schema": "gowrite_retrieval_snapshot/v2",
        "request_id": request_id,
        "project_id": project_id,
        "planning_turn_id": planning_turn_id,
        "query": query,
        "package_fingerprint": _package_fingerprint(package),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "package": _package_snapshot_dict(package),
    }
    path = _snapshot_path(planning_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def execute_request_scoped_retrieval(query: str, request_id: str) -> Any:
    """Agent 侧（/gowrite 执行内）的"唯一一次确定性检索调用"。

    显式 request_id 绑定（与 StoryWrite/Review/NewProject 同一 P0 精确绑定；
    绝不依赖可变 active 指针）：从请求 meta 恢复 project/planning turn →
    运行现有 KnowledgeRetrieve（唯一一次执行）→ 把精确序列化包写入请求级
    快照 → 返回包对象（由 CLI 打印给模型查看）。

    模型看到的候选 == 快照中的包 == finalize 反序列化后 Context 消费的包。
    """
    request_id = (request_id or "").strip()
    if not request_id:
        raise StoryPlanningError("缺少任务标识（request_id），无法生成检索快照。")
    request = bridge.get_request(request_id)
    if request is None:
        raise StoryPlanningError("任务文件不存在或不可读，无法生成检索快照。")
    meta = request.get("meta") or {}
    project_id = str(meta.get("project_id") or "")
    planning_turn_id = str(meta.get("planning_turn_id") or "")
    if not project_id or not planning_turn_id:
        raise StoryPlanningError("任务缺少 project_id / planning_turn_id 元数据。")
    planning_dir = _planning_dir(project_id, planning_turn_id)
    audit.append_event(
        request_id, audit.EVENT_RETRIEVAL_REQUESTED, "knowledge_retrieve",
        details={"query": query[:200]},
    )
    try:
        package = _retrieve_package(query)  # 唯一一次 KnowledgeRetrieve 执行
    except StoryPlanningError:
        raise
    except Exception as exc:  # noqa: BLE001 — 检索失败 → Agent 侧命令失败，无快照可写
        raise StoryPlanningError(f"知识检索失败：{exc}") from exc
    _write_snapshot(
        request_id=request_id,
        project_id=project_id,
        planning_turn_id=planning_turn_id,
        query=query,
        package=package,
        planning_dir=planning_dir,
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


def _load_snapshot(planning_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    """读取请求级检索快照；返回 (snapshot, error)。error 非空表示缺失或不可解析。"""
    path = _snapshot_path(planning_dir)
    if not path.exists():
        return None, "检索包快照缺失：Agent 未在本轮 /gowrite 执行内生成检索快照。"
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
    planning_turn_id: str,
    query: str,
    package_ref: str,
) -> None:
    """校验快照身份：请求/项目/planning turn/归一化查询/包指纹全部一致。"""
    if snapshot.get("request_id") != request_id:
        raise StoryPlanningError("检索包快照 request_id 与当前任务不一致，已拒绝。")
    if snapshot.get("project_id") != project_id:
        raise StoryPlanningError("检索包快照 project_id 与当前任务不一致，已拒绝。")
    if snapshot.get("planning_turn_id") != planning_turn_id:
        raise StoryPlanningError("检索包快照 planning_turn_id 与当前任务不一致，已拒绝。")
    if snapshot.get("query") != query:
        raise StoryPlanningError(
            "检索包快照查询与本次 knowledge_needs 不一致（query mismatch），已拒绝。"
        )
    if not package_ref:
        raise StoryPlanningError("Agent 输出缺少检索包身份（package_ref）。")
    if snapshot.get("package_fingerprint") != package_ref:
        raise StoryPlanningError(
            "Agent 选择的检索包身份（package_ref）与绑定快照不一致，已拒绝。"
        )


def _package_from_snapshot(snapshot: dict[str, Any]) -> Any:
    """把快照中的序列化包反序列化为 E1 gate 可消费的包对象（不执行任何检索）。"""
    pkg = snapshot["package"]
    hits = []
    for h in pkg.get("hits", []):
        source_kind = h.get("source_kind", "")
        source_id = h.get("source_id", "")
        source_anchor = h.get("source_anchor", "")
        hits.append(types.SimpleNamespace(
            rank=h.get("rank", 0),
            selection_ref=h.get("selection_ref") or f"{source_kind}/{source_id}/{source_anchor}",
            source_kind=source_kind,
            source_id=source_id,
            source_title=h.get("source_title", h.get("book", "")),
            source_anchor=source_anchor,
            source=h.get("source", ""),
            statement=h.get("statement", ""),
            scope=h.get("scope", None),
            boundary=h.get("boundary", None),
            confidence=h.get("confidence", None),
            evidence=list(h.get("evidence", []) or []),
            relevance_reason=h.get("relevance_reason", ""),
        ))
    return types.SimpleNamespace(
        status=pkg.get("status", "OK"),
        gaps=list(pkg.get("gaps", []) or []),
        candidate_count=pkg.get("candidate_count", 0),
        hits=hits,
    )


# ---------------------------------------------------------------------------
# 候选解析（Agent 输出必须是合法结构化结果）
# ---------------------------------------------------------------------------

def _validate_str_list(value: Any, field_name: str) -> None:
    """校验字段必须是 list[str]；类型错误抛 StoryPlanningError。"""
    if not isinstance(value, list):
        raise StoryPlanningError(f"Agent 输出字段 {field_name} 类型错误（应为列表）。")
    for i, item in enumerate(value):
        if not isinstance(item, str):
            raise StoryPlanningError(
                f"Agent 输出字段 {field_name}[{i}] 类型错误（应为字符串）。"
            )


def _parse_agent_result(output: str) -> dict[str, Any]:
    """把 Agent 输出解析成 {semantic_interpretation, planning_target, model_output}。

    非法结构化结果：抛 StoryPlanningError（普通可读错误），不猜数据补齐、不落盘。
    严格类型检查：字段缺失或类型错误一律拒绝，不自动修复。
    """
    text = (output or "").strip()
    # 容错：去掉可能包裹的 markdown 代码块标记
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
        raise StoryPlanningError("Agent 输出不是合法结构化结果，请重试或更换表述。") from exc
    if not isinstance(data, dict):
        raise StoryPlanningError("Agent 输出不是合法结构化结果（应为 JSON 对象）。")

    # --- semantic_interpretation 严格校验 ---
    si = data.get("semantic_interpretation")
    if not isinstance(si, dict):
        raise StoryPlanningError("Agent 输出缺少 semantic_interpretation（应为对象）。")
    if not isinstance(si.get("objective"), str) or not si["objective"].strip():
        raise StoryPlanningError("Agent 输出 semantic_interpretation.objective 缺失或不是非空字符串。")
    if "knowledge_needs" not in si:
        raise StoryPlanningError("Agent 输出缺少 semantic_interpretation.knowledge_needs（应为列表）。")
    _validate_str_list(si["knowledge_needs"], "semantic_interpretation.knowledge_needs")
    if "selected_knowledge_refs" not in si:
        raise StoryPlanningError("Agent 输出缺少 semantic_interpretation.selected_knowledge_refs（应为列表）。")
    _validate_str_list(si["selected_knowledge_refs"], "semantic_interpretation.selected_knowledge_refs")
    if "package_ref" not in si or not isinstance(si.get("package_ref"), str):
        raise StoryPlanningError(
            "Agent 输出缺少 semantic_interpretation.package_ref（应为字符串：本次检索包身份指纹）。"
        )
    if "assumptions" not in si:
        raise StoryPlanningError("Agent 输出缺少 semantic_interpretation.assumptions（应为列表）。")
    _validate_str_list(si["assumptions"], "semantic_interpretation.assumptions")
    if "deliberate_open_space" in si:
        _validate_str_list(si["deliberate_open_space"], "semantic_interpretation.deliberate_open_space")

    # --- planning_target 校验 ---
    pt = data.get("planning_target")
    if not isinstance(pt, dict):
        raise StoryPlanningError("Agent 输出缺少 planning_target（应为对象）。")
    if not isinstance(pt.get("description"), str) or not pt["description"].strip():
        raise StoryPlanningError("Agent 输出 planning_target.description 缺失或不是非空字符串。")

    # --- model_output 严格校验 ---
    mo = data.get("model_output")
    if not isinstance(mo, dict):
        raise StoryPlanningError("Agent 输出缺少 model_output（应为对象）。")
    if not isinstance(mo.get("proposal"), str) or not mo["proposal"].strip():
        raise StoryPlanningError("Agent 输出缺少作者可读的规划建议（model_output.proposal）。")
    if "planning_items" not in mo:
        raise StoryPlanningError("Agent 输出缺少 model_output.planning_items（应为列表）。")
    items = mo["planning_items"]
    if not isinstance(items, list) or not items:
        raise StoryPlanningError("Agent 输出 model_output.planning_items 必须是非空列表。")
    for i, item in enumerate(items):
        if not isinstance(item, dict) or not isinstance(item.get("description"), str) or not item["description"].strip():
            raise StoryPlanningError(f"Agent 输出 model_output.planning_items[{i}] 缺少有效 description。")

    try:
        projection = project_model_ops.validate_planning_projection(data.get("planning_projection") or {})
    except project_model_ops.ProjectModelError as exc:
        raise StoryPlanningError(f"Agent 输出 planning_projection 非法：{exc}") from exc

    return {
        "semantic_interpretation": si,
        "planning_target": pt,
        "model_output": mo,
        "planning_projection": projection,
    }


# ---------------------------------------------------------------------------
# 规划来源验证
# ---------------------------------------------------------------------------

def _get_active_planning_sources(state: dict[str, Any]) -> list[dict[str, Any]]:
    """从正式 Story State 中返回所有当前 active 的 planning sources。

    使用 frozen resolve_plan_activity 的 active 投影，按 approved_plan 的
    append 顺序返回所有未被 supersede 的条目。

    StoryPlan 要求 planning source 必须是 approved_plan 中真实存在且 active 的条目。
    最终仍交给 StoryPlan.compile_plan_brief 验证 authority 是否可信。
    """
    plans = state.get("approved_plan") or []
    if not plans:
        return []

    activity = resolve_plan_activity(state)
    active_ids = set(activity["active"])

    # 按 append 顺序返回所有 active 条目
    sources = []
    for plan in plans:
        pid = plan.get("id")
        if pid and pid in active_ids:
            sources.append({"kind": "approved_plan", "ref": pid})
    return sources


# ---------------------------------------------------------------------------
# 提出规划候选
# ---------------------------------------------------------------------------

def prepare_story_plan(project_id: str, author_question: str) -> dict[str, Any]:
    """'一起往前想'第一步：读取正式作品 → 构造 Agent task → 创建请求，
    并按已保存 Settings 的执行模式准备执行。

    - Interactive（交互桥）：保留现有行为——创建请求后由作者在 Qoder 桌面端
      输入 /gowrite 执行（app_api 负责切前台）。
    - Direct（直连）：通过现有 Agent registry/adapter 与精确配置的内置/自定义
      模型直接执行同一任务，结果写回同一请求生命周期，随后由同一
      _finalize_story_plan 严格验收。配置缺失/无效 → 稳定报错，绝不回退。
    """
    author_question = (author_question or "").strip()
    if not author_question:
        raise StoryPlanningError("请写下你想一起想的问题。")

    # 1. 读取正式作品
    try:
        proj = resolve_project(project_id)
        loaded = load_project(proj["project_dir"])
    except (PWContractError, PWWorkspaceError) as exc:
        raise StoryPlanningError(str(exc)) from exc

    intent = loaded["intent"]
    state = loaded["state"]
    name = loaded["name"]

    # 2. 验证规划来源（所有 active approved_plan refs）
    planning_sources = _get_active_planning_sources(state)
    if not planning_sources:
        raise StoryPlanningError(
            "故事方向已经保存，但当前还没有可继续展开的已确认规划起点。"
        )

    # 3. 解析保存的执行配置（Settings 契约；agent_runner._build_adapter 负责
    #    直连的 Agent/模型解析与互斥校验，这里不重复实现路由）
    settings = SettingsStore().load()
    execution_mode = settings.default_execution_mode

    # 4. 构造 Agent 任务（同一任务文本：交互/直连共用）
    work_direction = intent.get("work_direction") or ""
    reader_promise = intent.get("reader_promise") or ""
    hard_constraints = ", ".join(intent.get("hard_constraints") or []) or "（暂无）"
    open_space = ", ".join(intent.get("open_space") or []) or "（暂无）"

    all_plans = state.get("approved_plan") or []
    activity = resolve_plan_activity(state)
    active_ids = set(activity["active"])
    active_descriptions = []
    for plan in all_plans:
        pid = plan.get("id")
        if pid and pid in active_ids:
            desc = plan.get("description") or plan.get("text") or ""
            if desc:
                active_descriptions.append(desc)
    if active_descriptions:
        current_planning = "\n".join(f"- {d}" for d in active_descriptions)
    else:
        current_planning = "（暂无已确定的规划）"

    # 预生成 request_id（检索命令需要内嵌真实 id；Interactive/Direct 共用）
    request_id = uuid.uuid4().hex
    effective_context = focused_task_context(project_id)

    task = _AGENT_TASK_TEMPLATE.format(
        name=name,
        work_direction=work_direction,
        reader_promise=reader_promise,
        hard_constraints=hard_constraints,
        open_space=open_space,
        current_planning=current_planning,
        author_question=author_question,
        # 显式 --request 绑定：Direct 请求绝不进入 active.json，检索命令必须
        # 按请求 id 定位（与 StoryWrite/Review/NewProject 同一 P0 精确绑定）
        retrieval_command=f'"{_RETRIEVAL_SCRIPT}" --request {request_id}',
        max_knowledge_hits=_MAX_KNOWLEDGE_HITS,
    )
    task += (
        "\n\n最新有效作者工作区（显式作者编辑优先；current 与 future/planned 严格分开）：\n"
        + json.dumps(effective_context, ensure_ascii=False, indent=2)
    )

    # 5. Direct 模式：显式配置校验（无有效配置 → 稳定报错，绝不回退）
    direct_adapter = None
    direct_agent_request = None
    execution_agent = settings.interactive_agent
    execution_model = None
    if execution_mode == EXECUTION_MODE_DIRECT:
        try:
            direct_adapter, direct_agent_request = agent_runner._build_adapter()
        except AgentRunError as exc:
            raise StoryPlanningError(f"直连执行配置不可用：{exc}") from exc
        except Exception as exc:  # noqa: BLE001 — 未知 Agent / registry 异常
            raise StoryPlanningError(f"直连执行配置不可用：{exc}") from exc
        execution_agent = direct_adapter.name
        execution_model = direct_agent_request.custom_model or direct_agent_request.model
        # 忙碌保护：另一个 Direct StoryPlan 任务正在执行时拒绝本轮，
        # 避免创建第二份工作区/请求造成 active 指针竞态
        if _exec_task_manager.is_busy():
            raise StoryPlanningError(_DIRECT_BUSY_ERROR)

    # 6. 创建临时 planning 工作区（供后续 finalize 使用）
    planning_turn_id = uuid.uuid4().hex[:12]
    planning_dir = _planning_dir(project_id, planning_turn_id)
    if planning_dir.exists():
        shutil.rmtree(planning_dir, ignore_errors=True)
    planning_dir.mkdir(parents=True, exist_ok=False)

    # 7. 复制正式 intent/state 到临时工作区根级（StoryPlan 要求根级文件）
    paths = initialize_project(planning_dir)
    write_json(paths["intent"], intent)
    write_json(paths["state"], state)

    # 8. 创建桥请求（同一请求生命周期：交互由 Qoder /gowrite 写回，
    #    直连由 Go Write 通过 adapter 执行后写回；Direct 绝不激活 /gowrite）
    try:
        request_id = bridge.create_request(
            task=task,
            kind="story_plan_propose",
            meta={
                "project_id": project_id,
                "name": name,
                "planning_turn_id": planning_turn_id,
                "author_question": author_question,
                "planning_sources": planning_sources,
                "intent_rev": intent["intent_rev"],
                "state_rev": state["state_rev"],
                "model_rev": effective_context["model_rev"],
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
        # 已有等待 /gowrite 的交互任务：绝不清除/覆盖它；回滚本轮临时工作区
        _cleanup_planning(project_id, planning_turn_id)
        raise StoryPlanningError(str(exc)) from exc

    # 9. 验证式审计（operation.started；交互桥只标 waiting，绝不声称 Agent 已启动）
    #    必须先于 Direct worker 创建：worker 线程内的 append_event 依赖进程内
    #    recorder（晚创建会丢事件）。
    execution_facts = {
        "execution_mode": execution_mode,
        "agent_id": execution_agent,
        "model": execution_model,
    }
    recorder = audit.AuditRecorder(
        request_id, "story_plan", project_id, execution=execution_facts,
    )
    if execution_mode != EXECUTION_MODE_DIRECT:
        recorder.event(audit.EVENT_BRIDGE_WAITING, component="story_plan")

    # 10. Direct 模式：后台启动唯一一次 Agent 执行（prepare 立即返回，不阻塞）
    message = "任务已准备好，请到 Qoder 输入 /gowrite 并回车。"
    if execution_mode == EXECUTION_MODE_DIRECT:
        message = "任务已通过直连模式后台执行，正在校验结果。"
        _start_direct_execution(
            direct_adapter, direct_agent_request, task, request_id,
            project_id=project_id, planning_turn_id=planning_turn_id,
        )

    return {
        "request_id": request_id,
        "project_id": project_id,
        "name": name,
        "status": "task_prepared",
        "execution_mode": execution_mode,
        "agent_id": execution_agent,
        "model": execution_model,
        "message": message,
    }


def _start_direct_execution(
    adapter: Any,
    agent_request: Any,
    task: str,
    request_id: str,
    *,
    project_id: str,
    planning_turn_id: str,
) -> None:
    """在后台任务管理器启动唯一一次 Direct Agent 执行；prepare 不等待结果。

    只允许在 Settings 显式 Direct 配置下由 prepare_story_plan 调用。竞态兜底：
    若启动失败（另一个 Direct 任务恰好抢到活跃槽），清理本轮的临时工作区与
    请求并抛稳定忙碌错误，避免孤儿任务与 active 指针竞态。
    """
    execution = {
        "execution_mode": "direct",
        "agent_id": adapter.name,
        "model": agent_request.custom_model or agent_request.model,
    }
    worker = lambda: _dispatch_direct_worker(adapter, agent_request, task, request_id)  # noqa: E731
    if not _exec_task_manager.start(
        request_id=request_id, worker=worker, adapter=adapter, execution=execution
    ):
        _cleanup_planning(project_id, planning_turn_id)
        bridge.cleanup_request(request_id)
        raise StoryPlanningError(_DIRECT_BUSY_ERROR)


def _dispatch_direct_worker(
    adapter: Any, agent_request: Any, task: str, request_id: str
) -> None:
    """后台 worker：执行唯一一次 Direct Agent 调用并写回现有响应信封。

    绝不调用 finalize —— get_story_plan_request → _finalize_story_plan 仍是
    唯一 finalize 路径。取消后晚完成的 AgentResult 一律丢弃。
    验证式审计：只在实际 callsite（adapter.run）记录。
    """
    agent_request.task = task
    agent_request.cwd = str(_REPO_ROOT)
    audit.append_event(
        request_id, audit.EVENT_AGENT_DIRECT_PROCESS_STARTED, "story_plan",
        details={"agent": adapter.name},
    )
    try:
        result = adapter.run(agent_request)
    except Exception as exc:  # noqa: BLE001 — adapter 异常 → failed 信封
        audit.append_event(request_id, audit.EVENT_AGENT_FAILED, "story_plan", details={"error": str(exc)[:200]})
        _finish_direct(request_id, status="failed", error=f"直连执行失败：{exc}")
        return
    if _exec_task_manager.is_canceled(request_id):
        return  # 已取消：晚完成结果丢弃
    if result.status != "completed":
        audit.append_event(
            request_id,
            audit.EVENT_AGENT_FAILED if result.status != "cancelled" else audit.EVENT_AGENT_CANCELED,
            "story_plan", details={"error": (result.error or "")[:200]},
        )
        _finish_direct(
            request_id,
            status="failed",
            error=result.error or f"直连执行未完成（status={result.status}）。",
        )
        return
    audit.append_event(request_id, audit.EVENT_AGENT_COMPLETED, "story_plan")
    _finish_direct(request_id, status="completed", output=result.output or "")


def _finish_direct(
    request_id: str,
    *,
    status: str,
    output: str = "",
    error: str | None = None,
) -> None:
    """把 Direct 执行结果写入现有请求响应信封并标记任务终态。

    写前再次检查取消状态（收窄取消与写回的竞态窗口）；已取消绝不写响应。
    桥请求侧 canceled 状态是最终防线：即使竞态窗口内写入了响应文件，
    get_story_plan_request 也会因请求 state==canceled 直接短路，永不 finalize。
    注意：审计记录不在这里收尾 —— finalize 事件（skill/retrieval/candidate）
    由 get_story_plan_request 的 finalize 路径追加后再 finish（否则会丢事件）。
    """
    if _exec_task_manager.is_canceled(request_id):
        return
    bridge.write_response(request_id, status=status, output=output or None, error=error)
    _exec_task_manager.finish(
        request_id,
        execution_tasks.TASK_COMPLETED if status == "completed" else execution_tasks.TASK_FAILED,
    )


def _response_output_text(response: dict[str, Any]) -> str:
    """从 response 提取模型最终结果文本（result 优先，output 兜底；共享桥 helper）。"""
    try:
        return bridge.response_result_text(response)
    except bridge.BridgeProtocolError as exc:
        raise StoryPlanningError(str(exc)) from exc


def _finalize_story_plan(
    request: dict[str, Any], response: dict[str, Any]
) -> dict[str, Any]:
    """response → 校验 → 现有严格解析 → StoryPlan 候选。"""
    # 1. request_id 防串任务
    if response.get("request_id") != request["request_id"]:
        raise StoryPlanningError("返回结果与任务不匹配（request_id 不一致），已丢弃。")

    # 2. 状态校验
    resp_status = response.get("status")
    if resp_status not in (None, "completed"):
        err = response.get("error") or f"Qoder 返回状态异常：{resp_status}"
        raise StoryPlanningError(err)

    # 3. 提取模型最终结果 → 现有严格 JSON/字段验证
    raw = _response_output_text(response)
    parsed = _parse_agent_result(raw)

    # 4. 从 request meta 恢复上下文
    meta = request.get("meta") or {}
    project_id = str(meta.get("project_id") or "")
    planning_turn_id = str(meta.get("planning_turn_id") or "")
    planning_dir = _planning_dir(project_id, planning_turn_id)

    # 5. 知识选择绑定（Knowledge Selection Binding）
    #    - knowledge_needs 为空：不调用 KnowledgeRetrieve、不要求快照，
    #      0 BKP 合法；模型不得在无知识需求时选择 BKP 或声明包身份。
    #    - knowledge_needs 非空：读取 Agent 侧"唯一一次检索调用"写入的
    #      请求级快照 → 校验请求/项目/planning turn/查询/包指纹 →
    #      反序列化该包并绑定给 Context。finalize **绝不再次执行检索**。
    knowledge_needs = list(parsed["semantic_interpretation"].get("knowledge_needs") or [])
    selected_refs = list(parsed["semantic_interpretation"].get("selected_knowledge_refs") or [])
    package_ref = str(parsed["semantic_interpretation"].get("package_ref") or "")
    retrieval: Callable[[str], Any] | None = None
    if knowledge_needs:
        query = "；".join(knowledge_needs)
        snapshot, load_error = _load_snapshot(planning_dir)
        if load_error:
            _cleanup_planning(project_id, planning_turn_id)
            raise StoryPlanningError(load_error)
        try:
            _validate_snapshot(
                snapshot,
                request_id=request["request_id"],
                project_id=project_id,
                planning_turn_id=planning_turn_id,
                query=query,
                package_ref=package_ref,
            )
        except StoryPlanningError:
            _cleanup_planning(project_id, planning_turn_id)
            raise
        package = _package_from_snapshot(snapshot)
        retrieval = _bound_package(package, query)
        audit.append_event(
            request["request_id"], audit.EVENT_RETRIEVAL_SELECTED, "knowledge_retrieve",
            details={"query": query, "refs": selected_refs, "package_ref": package_ref},
        )
    elif selected_refs or package_ref:
        _cleanup_planning(project_id, planning_turn_id)
        raise StoryPlanningError("没有知识需求却选择了知识卡或检索包身份，已拒绝。")

    # 6. 构造 planning_target
    agent_target = parsed["planning_target"]
    planning_target = {
        "target_id": f"target-{planning_turn_id}",
        "description": agent_target["description"],
        "scope_kind": agent_target.get("scope_kind") or "free",
    }
    if "scope" in agent_target:
        planning_target["scope"] = agent_target["scope"]

    # 7. 调用 frozen StoryPlan（Context 消费与模型所见完全相同的绑定包）
    brief_id = f"plan-brief-{planning_turn_id}"
    context_id = f"plan-context-{planning_turn_id}"
    candidate_id = f"plan-{planning_turn_id}"

    planning_sources = meta.get("planning_sources") or []

    audit.append_event(
        request["request_id"], audit.EVENT_SKILL_STARTED, "story_plan", details={"skill": "StoryPlan"},
    )
    try:
        sp_result = run_story_plan(
            project_dir=planning_dir,
            author_planning_question=meta.get("author_question") or "",
            planning_target=planning_target,
            planning_sources=planning_sources,
            brief_id=brief_id,
            context_id=context_id,
            candidate_id=candidate_id,
            semantic_interpretation=parsed["semantic_interpretation"],
            model_output=parsed["model_output"],
            retrieval=retrieval,
        )
    except SPContractError as exc:
        audit.append_event(
            request["request_id"], audit.EVENT_SKILL_FAILED, "story_plan", details={"skill": "StoryPlan"},
        )
        _cleanup_planning(project_id, planning_turn_id)
        raise StoryPlanningError(f"StoryPlan 拒绝生成候选：{exc}") from exc
    audit.append_event(
        request["request_id"], audit.EVENT_SKILL_COMPLETED, "story_plan", details={"skill": "StoryPlan"},
    )
    audit.append_event(
        request["request_id"], audit.EVENT_CONTEXT_BOUND, "context_compiler",
        details={"context_id": context_id, "refs": selected_refs},
    )

    candidate = sp_result["candidate"]
    if candidate.get("status") != "proposal_noncanonical":
        _cleanup_planning(project_id, planning_turn_id)
        raise StoryPlanningError("候选状态异常（非 proposal_noncanonical），已中止。")

    # 7. 保存元信息（token 用于确认时校验；request_id 用于完成后丢弃定位）
    planning_meta = {
        "kind": "story_plan_proposal",
        "project_id": project_id,
        "name": meta.get("name") or "",
        "planning_turn_id": planning_turn_id,
        "planning_token": uuid.uuid4().hex,
        "request_id": request["request_id"],
        "author_question": meta.get("author_question") or "",
        "source_versions": {
            "intent_rev": meta.get("intent_rev"),
            "state_rev": meta.get("state_rev"),
            "model_rev": meta.get("model_rev"),
        },
        "planning_projection": parsed["planning_projection"],
    }
    write_json(planning_dir / "planning_meta.json", planning_meta)
    audit.append_event(
        request["request_id"], audit.EVENT_CANDIDATE_CREATED, "story_plan",
        details={"candidate_id": candidate_id},
    )

    # 8. 返回给 UI 的最小展示形状
    content = candidate.get("content") or {}
    planning_items_raw = content.get("planning_items") or []
    planning_items_display = [
        item.get("description") or "" for item in planning_items_raw if isinstance(item, dict)
    ]

    # 9. 知识绑定摘要（可证明：retrieved/selected 都来自同一绑定包）
    retrieval_info = (sp_result.get("context") or {}).get("retrieval") or {}
    selected_hits = (sp_result.get("context") or {}).get("selected_knowledge_hits") or []
    knowledge_summary = {
        "retrieval_status": retrieval_info.get("status"),
        "retrieved_count": retrieval_info.get("candidate_count", 0),
        "selected_count": len(selected_hits),
        "gaps": retrieval_info.get("gaps", []),
    }

    return {
        "planning_token": planning_meta["planning_token"],
        "project_id": project_id,
        "name": meta.get("name") or "",
        "status": "proposal_noncanonical",
        "candidate": {
            "proposal": content.get("proposal") or "",
            "planning_items": planning_items_display,
            "planning_projection": parsed["planning_projection"],
        },
        "knowledge": knowledge_summary,
        "execution": dict(meta.get("execution") or {}),
        "message": "规划候选已生成（未写入正式作品，等待你的确认）",
    }


def get_story_plan_request(request_id: str) -> dict[str, Any]:
    """轮询 Qoder 写回结果（UI 每 2-3 秒调用一次）。

    返回 status：pending（继续等）/ completed（含候选）/ failed / expired / canceled。
    """
    request_id = (request_id or "").strip()
    if not request_id:
        raise StoryPlanningError("缺少任务标识（request_id）。")

    request = bridge.get_request(request_id)
    if request is None:
        return {"request_id": request_id, "status": "failed", "error": "任务已失效，请重新发起。"}

    state = request.get("state")
    meta = request.get("meta") or {}
    project_id = str(meta.get("project_id") or "")
    planning_turn_id = str(meta.get("planning_turn_id") or "")

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
        if project_id and planning_turn_id:
            _cleanup_planning(project_id, planning_turn_id)
        # 超时：若 Direct worker 仍在运行，请求取消运行中的 adapter（幂等）
        _exec_task_manager.cancel(request_id)
        _exec_task_manager.remove(request_id)
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error="任务已超时，请重新发起。")
        return {"request_id": request_id, "status": "expired", "error": "任务已超时，请重新发起。"}

    response = bridge.read_response(request_id)
    if response is None:
        return {"request_id": request_id, "status": "pending"}

    if response.get("request_id") != request["request_id"]:
        bridge.cleanup_request(request_id)
        _exec_task_manager.remove(request_id)
        return {"request_id": request_id, "status": "failed", "error": "返回结果与任务不匹配，已丢弃。"}

    audit.append_event(
        request_id, audit.EVENT_BRIDGE_RESPONSE_RECEIVED, "story_plan",
        details={"execution_mode": meta.get("execution", {}).get("execution_mode")},
    )
    try:
        result = _finalize_story_plan(request, response)
    except StoryPlanningError as exc:
        if project_id and planning_turn_id:
            _cleanup_planning(project_id, planning_turn_id)
        bridge.cleanup_request(request_id)
        _exec_task_manager.remove(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
        return {"request_id": request_id, "status": "failed", "error": str(exc)}

    # 成功：清理桥文件（保留临时 planning 工作区，供确认时使用）
    bridge.cleanup_request(request_id)
    _exec_task_manager.remove(request_id)
    # 候选生成 ≠ 操作完成：记录保持打开（awaiting_confirmation），
    # 等作者 Confirm（authority.confirmed → completed）或 Discard/Cancel（canceled）。
    audit.mark_awaiting_confirmation(request_id)
    return {"request_id": request_id, "status": "completed", "result": result}


def _cleanup_discarded_planning(request_id: str) -> None:
    """丢弃已完成但未确认的规划候选：按 planning_meta.json 中持久化的 request_id
    定位并删除其临时 planning 工作区（planning_token 随之失效，confirm 将拒绝）。

    只清理临时工作区（06_工作区/应用开发/.planning），绝不触碰正式 Story State，
    也绝不进入 StoryWrite。绑定校验：meta 的 project_id / planning_turn_id 必须
    与目录结构一致；无匹配时静默（幂等）。
    """
    root = get_planning_root()
    if not root.exists():
        return
    for meta_file in root.glob("*/*/planning_meta.json"):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if meta.get("request_id") != request_id:
            continue
        project_id = str(meta.get("project_id") or "")
        planning_turn_id = str(meta.get("planning_turn_id") or "")
        if (
            project_id
            and planning_turn_id
            and meta_file.parent.name == planning_turn_id
            and meta_file.parent.parent.name == project_id
        ):
            _cleanup_planning(project_id, planning_turn_id)
        else:
            # 结构不一致（异常数据）：只删除该工作区本身，绝不扩大清理范围
            shutil.rmtree(meta_file.parent, ignore_errors=True)
        return


def cancel_story_plan_request(request_id: str) -> dict[str, Any]:
    """取消/丢弃：终止运行中的 Direct adapter（如有）、标记 canceled、
    删除临时 planning 工作区。幂等；交互/直连共用同一取消语义。

    - 运行中：取消 adapter，晚完成结果丢弃，工作区清理；
    - 已完成但未确认（请求文件已被 get_story_plan_request 终态清理）：
      通过 planning_meta.json 中持久化的 request_id 定位工作区并删除 →
      planning_token 失效；
    - 绝不触碰正式 Story State，绝不确认任何内容。
    """
    request_id = (request_id or "").strip()
    if not request_id:
        raise StoryPlanningError("缺少任务标识（request_id）。")

    # Direct：先请求任务管理器取消运行中的 adapter（幂等；无任务时 no-op）
    _exec_task_manager.cancel(request_id)

    request = bridge.get_request(request_id)
    if request is not None:
        bridge.mark_canceled(request_id)
        meta = request.get("meta") or {}
        project_id = str(meta.get("project_id") or "")
        planning_turn_id = str(meta.get("planning_turn_id") or "")
        if project_id and planning_turn_id:
            _cleanup_planning(project_id, planning_turn_id)
        bridge.clear_active_if(request_id)
        audit.finish_file(request_id, audit.STATUS_CANCELED)
    else:
        # 请求文件已不存在（已完成并轮询过 / 已取消过）：按持久化 request_id
        # 清理已完成但未确认的候选工作区（幂等；无匹配时静默）。
        _cleanup_discarded_planning(request_id)
        # 审计记录（awaiting_confirmation）收尾为 canceled
        audit.finish_file(request_id, audit.STATUS_CANCELED)
    _exec_task_manager.remove(request_id)
    return {"request_id": request_id, "status": "canceled"}


# ---------------------------------------------------------------------------
# 作者明确确认后写入正式规划
# ---------------------------------------------------------------------------

def confirm_story_plan(project_id: str, planning_token: str) -> dict[str, Any]:
    """作者明确确认：用后台保存的那一版候选写入正式 approved_plan。

    确认必须带后台生成的 planning token；前端不能仅凭一句 confirmed=true
    写入任意内容。确认后：
    - 通过 frozen create_decision_record 的正式 Decision
    - 通过 StoryPlan.make_plan_diff + apply_diff + persist_state_transition
      写入 approved_plan（不新增 Schema、不直接改 JSON）
    - 不生成正文、不进入 StoryWrite
    """
    planning_token = (planning_token or "").strip()
    if not planning_token:
        raise StoryPlanningError("缺少规划确认标识（planning token）。")

    # 1. 用 token 反查规划工作区
    root = get_planning_root()
    matched: Path | None = None
    if root.exists():
        for meta_file in root.glob("*/*/planning_meta.json"):
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if meta.get("planning_token") == planning_token:
                matched = meta_file.parent
                break
    if matched is None:
        raise StoryPlanningError("规划候选已失效或不存在，请重新生成。")

    meta = json.loads((matched / "planning_meta.json").read_text(encoding="utf-8"))
    planning_turn_id = meta["planning_turn_id"]

    # 2. 读取后台保存的候选（plans/plan-<turn_id>.json），只信这一版
    candidate_path = matched / "plans" / f"plan-{planning_turn_id}.json"
    if not candidate_path.exists():
        raise StoryPlanningError("候选数据缺失，请重新生成。")
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))

    # 3. 读取 brief/context
    brief_path = matched / "briefs" / f"plan-brief-{planning_turn_id}.json"
    context_path = matched / "contexts" / f"plan-context-{planning_turn_id}.json"
    if not brief_path.exists() or not context_path.exists():
        raise StoryPlanningError("规划上下文缺失，请重新生成。")
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    context = json.loads(context_path.read_text(encoding="utf-8"))

    # 4. 读取正式作品当前状态（用于 stale 检查）
    try:
        proj = resolve_project(project_id)
        loaded = load_project(proj["project_dir"])
    except (PWContractError, PWWorkspaceError) as exc:
        raise StoryPlanningError(str(exc)) from exc

    current_intent = loaded["intent"]
    current_state = loaded["state"]
    project_dir = Path(loaded["project_dir"])
    projection = project_model_ops.validate_planning_projection(meta.get("planning_projection") or {})

    # 5. Stale 检查：Brief 编译时的 intent_rev/state_rev 必须与当前一致
    request_id = str(meta.get("request_id") or "")
    source_versions = brief.get("source_versions", {})
    if source_versions.get("intent_rev") != current_intent.get("intent_rev"):
        _cleanup_planning(project_id, planning_turn_id)
        raise StoryPlanningError("作品在这期间已经有了新的变化，请重新生成这次规划。")
    if source_versions.get("state_rev") != current_state.get("state_rev"):
        _cleanup_planning(project_id, planning_turn_id)
        raise StoryPlanningError("作品在这期间已经有了新的变化，请重新生成这次规划。")
    if get_project_snapshot(project_id).get("model_rev") != (meta.get("source_versions") or {}).get("model_rev"):
        _cleanup_planning(project_id, planning_turn_id)
        raise StoryPlanningError("作品地基或章节规划在这期间已经变化，请重新生成这次规划。")

    # 6. 构造 Decision
    decision_id = f"decision-plan-{planning_turn_id}"
    decision = create_decision_record(
        decision_id=decision_id,
        brief=brief,
        context=context,
        candidate=candidate,
        author_action="choose",
        author_confirmation_ref=f"author:workbench:{planning_token}",
        final_decision={"selected": "confirmed_planning"},
    )

    # 7. 从候选内容构造 planning items（后台生成稳定 id）
    content = candidate.get("content") or {}
    planning_items_raw = content.get("planning_items") or []
    target_ref = brief["planning_target"]["target_id"]

    planning_items = []
    for i, item in enumerate(planning_items_raw):
        desc = item.get("description") or ""
        if not desc:
            continue
        plan_id = f"plan-{planning_turn_id}-{i+1}"
        planning_items.append({
            "id": plan_id,
            "description": desc,
            "target_ref": target_ref,
        })

    if not planning_items:
        _cleanup_planning(project_id, planning_turn_id)
        raise StoryPlanningError("候选缺少有效的规划条目，无法写入。")

    # 8. 使用 StoryPlan 的 make_plan_diff（带完整验证）
    diff_id = f"diff-plan-{planning_turn_id}"
    state_file = project_dir / "_工作台状态" / "story_state.json"
    model_file = project_dir / "_工作台状态" / project_model_ops.ARTIFACT_NAME
    state_before = state_file.read_bytes()
    model_before = model_file.read_bytes() if model_file.exists() else None
    projection_model = None
    try:
        diff = make_plan_diff(
            diff_id=diff_id,
            state=current_state,
            intent=current_intent,
            decision=decision,
            brief=brief,
            plans=planning_items,
        )
        new_state = apply_diff(current_state, diff, decision)
        persist_state_transition(
            project_dir=project_dir,
            expected_base_state=current_state,
            new_state=new_state,
        )
        if any(projection.values()):
            current_model = project_model_ops.read_project_model(project_id)
            projection_model = project_model_ops.apply_planning_projection(
                project_id,
                base_model_rev=current_model["model_rev"],
                projection=projection,
                source_ref=decision_id,
            )
    except (SPContractError, PWContractError, PWWorkspaceError, project_model_ops.ProjectModelError) as exc:
        # Planning authority + future projection are one confirmation outcome.
        # If the second artifact fails, restore both exact pre-confirmation states.
        try:
            _safe_write_file(state_file, state_before)
            if model_before is None:
                if model_file.exists():
                    model_file.unlink()
            else:
                project_model_ops._atomic_write_json(
                    model_file, json.loads(model_before.decode("utf-8")),
                )
        except Exception as rollback_exc:  # noqa: BLE001
            _cleanup_planning(project_id, planning_turn_id)
            raise StoryPlanningError(f"写入规划失败且回滚未完成：{rollback_exc}") from exc
        _cleanup_planning(project_id, planning_turn_id)
        raise StoryPlanningError(f"写入规划失败：{exc}") from exc

    # 9. 清理临时规划工作区；审计 authority.confirmed
    _cleanup_planning(project_id, planning_turn_id)
    audit.append_event(
        request_id, audit.EVENT_AUTHORITY_CONFIRMED, "story_plan",
        details={"decision_id": decision_id, "plan_count": len(planning_items)},
    )
    audit.finish_file(request_id, audit.STATUS_COMPLETED)

    return {
        "project_id": project_id,
        "name": loaded["name"],
        "state_rev": new_state.get("state_rev"),
        "project_model_rev": projection_model.get("model_rev") if projection_model else None,
        "planning_projection_count": sum(
            len(items) if isinstance(items, list) else (1 if items else 0)
            for items in projection.values()
        ),
        "message": "规划已确认并写入",
    }
