# -*- coding: utf-8 -*-
"""故事规划 Author Operations：第二条真实作者使用链（"一起往前想"）。

链路（统一 /gowrite 桥模式）：
  作品概览 → 作者自然语言提出"接下来想怎么发展"
  → Go Write 准备本轮 Agent 任务（pending request）
  → 提示作者到 Qoder 桌面端执行 /gowrite
  → Qoder 返回结果 → Go Write 严格解析
  → 现有 StoryPlan 形成 proposal_noncanonical 候选（临时 planning 工作区）
  → UI 展示 → 作者明确确认 → approved_plan writeback → 刷新概览

约束（遵守现有冻结合同）：
- 不修改 StoryPlan / StoryDesign / ProjectWorkspace；不创建空壳规划。
- 确认前绝不写正式 Story State；候选全部落在可删除的临时工作区。
- 确认必须带后台生成的 planning token；禁止信任前端自行构造隐藏内容。
- Token 禁止进入 Prompt / UI / 日志 / Bridge 返回值。
- 不生成正文；不进入 StoryWrite。
- **不调用 run_task / 后台 Agent；模型执行统一由 Qoder 桌面端 /gowrite 完成。**
"""
from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

from operations import qoder_bridge as bridge

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

# Agent 任务模板：只要求结构化结果，明确不读文件不写文件
# 注意：作者问题放在最后，避免模型先回应角色设定而忽略 JSON 输出要求
_AGENT_TASK_TEMPLATE = """只做语义与创意分析，不读取或修改任何文件。

请针对以下作者规划问题，直接输出一个合法的 JSON 对象（不要任何额外文字、不要 markdown 代码块标记）。
结构必须如下：

{{
  "semantic_interpretation": {{
    "objective": "本次规划的目标（一句话）",
    "knowledge_needs": [],
    "selected_bkp_ids": [],
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
  }}
}}

作品信息：
- 作品名：{name}
- 已确定的故事方向：{work_direction}
- 读者主要期待：{reader_promise}
- 当前已守住的约束：{hard_constraints}
- 当前可以自由变化的部分：{open_space}
- 当前已确定的规划：
{current_planning}

作者本轮问题：{author_question}

直接输出 JSON，不要输出任何其他内容。"""


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
    if "selected_bkp_ids" not in si:
        raise StoryPlanningError("Agent 输出缺少 semantic_interpretation.selected_bkp_ids（应为列表）。")
    _validate_str_list(si["selected_bkp_ids"], "semantic_interpretation.selected_bkp_ids")
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

    return {"semantic_interpretation": si, "planning_target": pt, "model_output": mo}


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
    """'一起往前想'第一步：读取正式作品 → 构造 Agent task → 创建桥请求。

    不调用任何模型。模型执行由作者在 Qoder 桌面端输入 /gowrite 完成。
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

    # 3. 构造 Agent 任务
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

    task = _AGENT_TASK_TEMPLATE.format(
        name=name,
        work_direction=work_direction,
        reader_promise=reader_promise,
        hard_constraints=hard_constraints,
        open_space=open_space,
        current_planning=current_planning,
        author_question=author_question,
    )

    # 4. 创建临时 planning 工作区（供后续 finalize 使用）
    planning_turn_id = uuid.uuid4().hex[:12]
    planning_dir = _planning_dir(project_id, planning_turn_id)
    if planning_dir.exists():
        shutil.rmtree(planning_dir, ignore_errors=True)
    planning_dir.mkdir(parents=True, exist_ok=False)

    # 5. 复制正式 intent/state 到临时工作区根级（StoryPlan 要求根级文件）
    paths = initialize_project(planning_dir)
    write_json(paths["intent"], intent)
    write_json(paths["state"], state)

    # 6. 创建桥请求（不运行模型；Qoder 桌面端 /gowrite 执行）
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
        },
    )

    # 7. 尽力把 Qoder 桌面端切到前台
    bridge.focus_qoder_window()

    return {
        "request_id": request_id,
        "project_id": project_id,
        "name": name,
        "status": "task_prepared",
        "message": "任务已准备好，请到 Qoder 输入 /gowrite 并回车。",
    }


def _response_output_text(response: dict[str, Any]) -> str:
    """从 response 提取模型最终结果文本（result 优先，output 兜底）。"""
    result = response.get("result")
    if isinstance(result, dict) and result:
        return json.dumps(result, ensure_ascii=False)
    output = response.get("output")
    if isinstance(output, str) and output.strip():
        return output
    raise StoryPlanningError("Qoder 返回结果缺少模型输出。")


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

    # 5. 构造 planning_target
    agent_target = parsed["planning_target"]
    planning_target = {
        "target_id": f"target-{planning_turn_id}",
        "description": agent_target["description"],
        "scope_kind": agent_target.get("scope_kind") or "free",
    }
    if "scope" in agent_target:
        planning_target["scope"] = agent_target["scope"]

    # 6. 调用 frozen StoryPlan
    brief_id = f"plan-brief-{planning_turn_id}"
    context_id = f"plan-context-{planning_turn_id}"
    candidate_id = f"plan-{planning_turn_id}"

    planning_sources = meta.get("planning_sources") or []

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
        )
    except SPContractError as exc:
        _cleanup_planning(project_id, planning_turn_id)
        raise StoryPlanningError(f"StoryPlan 拒绝生成候选：{exc}") from exc

    candidate = sp_result["candidate"]
    if candidate.get("status") != "proposal_noncanonical":
        _cleanup_planning(project_id, planning_turn_id)
        raise StoryPlanningError("候选状态异常（非 proposal_noncanonical），已中止。")

    # 7. 保存元信息（token 用于确认时校验）
    planning_meta = {
        "kind": "story_plan_proposal",
        "project_id": project_id,
        "name": meta.get("name") or "",
        "planning_turn_id": planning_turn_id,
        "planning_token": uuid.uuid4().hex,
        "author_question": meta.get("author_question") or "",
        "source_versions": {
            "intent_rev": meta.get("intent_rev"),
            "state_rev": meta.get("state_rev"),
        },
    }
    write_json(planning_dir / "planning_meta.json", planning_meta)

    # 8. 返回给 UI 的最小展示形状
    content = candidate.get("content") or {}
    planning_items_raw = content.get("planning_items") or []
    planning_items_display = [
        item.get("description") or "" for item in planning_items_raw if isinstance(item, dict)
    ]

    return {
        "planning_token": planning_meta["planning_token"],
        "project_id": project_id,
        "name": meta.get("name") or "",
        "status": "proposal_noncanonical",
        "candidate": {
            "proposal": content.get("proposal") or "",
            "planning_items": planning_items_display,
        },
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
        return {"request_id": request_id, "status": "canceled"}
    if state == "completed":
        bridge.cleanup_request(request_id)
        return {"request_id": request_id, "status": "completed", "error": None}
    if state == "failed":
        bridge.cleanup_request(request_id)
        return {
            "request_id": request_id,
            "status": "failed",
            "error": request.get("error") or "任务失败，请重新发起。",
        }

    # pending：先查超时，再查 response
    if bridge.is_expired(request):
        if project_id and planning_turn_id:
            _cleanup_planning(project_id, planning_turn_id)
        bridge.cleanup_request(request_id)
        return {"request_id": request_id, "status": "expired", "error": "任务已超时，请重新发起。"}

    response = bridge.read_response(request_id)
    if response is None:
        return {"request_id": request_id, "status": "pending"}

    try:
        result = _finalize_story_plan(request, response)
    except StoryPlanningError as exc:
        if project_id and planning_turn_id:
            _cleanup_planning(project_id, planning_turn_id)
        bridge.cleanup_request(request_id)
        return {"request_id": request_id, "status": "failed", "error": str(exc)}

    # 成功：清理桥文件（保留临时 planning 工作区，供确认时使用）
    bridge.cleanup_request(request_id)
    return {"request_id": request_id, "status": "completed", "result": result}


def cancel_story_plan_request(request_id: str) -> dict[str, Any]:
    """取消等待：标记 canceled、删除临时 planning 工作区。"""
    request_id = (request_id or "").strip()
    if not request_id:
        raise StoryPlanningError("缺少任务标识（request_id）。")

    request = bridge.get_request(request_id)
    if request is not None:
        bridge.mark_canceled(request_id)
        meta = request.get("meta") or {}
        project_id = str(meta.get("project_id") or "")
        planning_turn_id = str(meta.get("planning_turn_id") or "")
        if project_id and planning_turn_id:
            _cleanup_planning(project_id, planning_turn_id)
        bridge.clear_active_if(request_id)
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

    # 5. Stale 检查：Brief 编译时的 intent_rev/state_rev 必须与当前一致
    source_versions = brief.get("source_versions", {})
    if source_versions.get("intent_rev") != current_intent.get("intent_rev"):
        _cleanup_planning(project_id, planning_turn_id)
        raise StoryPlanningError("作品在这期间已经有了新的变化，请重新生成这次规划。")
    if source_versions.get("state_rev") != current_state.get("state_rev"):
        _cleanup_planning(project_id, planning_turn_id)
        raise StoryPlanningError("作品在这期间已经有了新的变化，请重新生成这次规划。")

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
    except (SPContractError, PWContractError, PWWorkspaceError) as exc:
        _cleanup_planning(project_id, planning_turn_id)
        raise StoryPlanningError(f"写入规划失败：{exc}") from exc

    # 9. 清理临时规划工作区
    _cleanup_planning(project_id, planning_turn_id)

    return {
        "project_id": project_id,
        "name": loaded["name"],
        "state_rev": new_state.get("state_rev"),
        "message": "规划已确认并写入",
    }
