# -*- coding: utf-8 -*-
"""新建作品 Author Operations：第一条真实作者使用链（“我有个想法”）。

架构（已确认）：Go Write 管长期记忆；Qoder 桌面端只作为当前任务的交互式
Agent 执行器。Go Write 绝不直接调用模型 API，也不使用 qodercli -p 作为
Token Plan 作者路径。

链路：
  作者想法 → Go Write 准备本轮 Agent 任务（唯一 request_id + 完整 task +
  结果写回位置）→ 页面提示“请到 Qoder 输入 /gowrite 并回车” →
  作者在 Qoder 桌面端执行 /gowrite（用桌面端已配置好的百炼 Token Plan 模型）
  → Qoder 写回 response 文件 → Go Write 检测到结果 → 校验 request_id →
  现有严格 JSON/字段验证 → 现有 StoryDesign 生成 proposal_noncanonical 候选
  （临时 pre-project 工作区）→ UI 展示 → 作者明确确认 →
  ProjectWorkspace.create_project 创建正式作品

约束（遵守现有冻结合同）：
- 不修改 StoryDesign / ProjectWorkspace；不创建空壳项目。
- 确认前绝不写 03_作品工程；候选全部落在可删除的临时工作区。
- 确认必须带后台生成的 proposal token；禁止信任前端自行构造隐藏内容。
- Token 禁止进入 Prompt / UI / 日志 / Bridge 返回值。
- 新增作品只写 Author Intent + 空 Story State + 空索引；不生成正文。
- 桥文件全部在 06_工作区/应用开发/.qoder_bridge（Local Only，可删除）；
  绝不用正式作品作为 Agent 桥。
"""
from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

from operations import qoder_bridge as bridge

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

# Agent 任务模板：只要求结构化结果，明确不读文件不写文件
# 注意：作者想法放在最后，避免模型先回应角色设定而忽略 JSON 输出要求
# 该模板是唯一业务 Prompt 来源；/gowrite 不复制规则，只执行这里保存的 task。
_AGENT_TASK_TEMPLATE = """只做语义与创意分析，不读取或修改任何文件。

请针对以下作者想法，直接输出一个合法的 JSON 对象（不要任何额外文字、不要 markdown 代码块标记）。
结构必须如下：

{{
  "semantic_interpretation": {{
    "scope": "story_design",
    "objective": "本次设计的目标（一句话）",
    "knowledge_needs": [],
    "selected_bkp_ids": [],
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

直接输出 JSON，不要输出任何其他内容。"""

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


def _write_temp_pre_project(proposal_dir: Path, project_id: str, name: str, idea: str) -> None:
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

    所有策略只负责提取，不做字段校验；字段校验由调用方完成。
    全部失败时，返回去掉代码块后的最佳尝试（让调用方报精确错误）。
    """
    stripped = text.strip()
    if not stripped:
        return stripped

    # 1. 直接解析
    try:
        json.loads(stripped)
        return stripped
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. 标准 markdown 代码块（首行 ``` 且末行 ```）
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2 and lines[-1].strip() == "```":
            inner = "\n".join(lines[1:-1]).strip()
            try:
                json.loads(inner)
                return inner
            except (json.JSONDecodeError, ValueError):
                pass

    # 3. 查找任意位置的代码块围栏（处理模型先输出文字再给代码块的情况）
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

    # 4. 最外层花括号匹配
    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidate = stripped[first_brace:last_brace + 1]
        try:
            json.loads(candidate)
            return candidate
        except (json.JSONDecodeError, ValueError):
            pass

    # 全部失败：返回去掉围栏后的最佳尝试（供错误诊断）
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
    JSON 提取使用 _extract_json_from_output 的多策略链；提取后做严格字段校验。
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

    # --- semantic_interpretation 严格校验 ---
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
    if "assumptions" not in si:
        raise NewProjectError("Agent 输出缺少 semantic_interpretation.assumptions（应为列表）。")
    _validate_str_list(si["assumptions"], "semantic_interpretation.assumptions")

    # --- model_output 严格校验 ---
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
# 准备本轮 Agent 任务（不运行模型；Qoder 桌面端执行 /gowrite）
# ---------------------------------------------------------------------------

def prepare_new_project(name: str, idea: str) -> dict[str, Any]:
    """“我有个想法”：Go Write 准备本轮 Agent 任务（pending request）。

    只做：校验输入 → 临时 pre-project 工作区 → 唯一 request_id → 保存完整
    task → 指定结果写回位置 → 尽力把 Qoder 切到前台（失败静默）。
    不调用任何模型 API；模型执行由作者在 Qoder 桌面端输入 /gowrite 完成。
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
    proposal_dir = _proposal_dir(project_id)
    if proposal_dir.exists():
        # 同一作品名的旧候选已存在：先清掉，保证每次提案从干净状态开始
        shutil.rmtree(proposal_dir, ignore_errors=True)
    _write_temp_pre_project(proposal_dir, project_id, name, idea)

    task = _AGENT_TASK_TEMPLATE.format(name=name, idea=idea)
    request_id = bridge.create_request(
        task=task,
        kind="story_design_propose",
        meta={"name": name, "idea": idea, "project_id": project_id},
    )
    return {
        "request_id": request_id,
        "name": name,
        "status": "task_prepared",
        "message": "任务已准备好，请到 Qoder 输入 /gowrite 并回车。",
    }


# ---------------------------------------------------------------------------
# 等待/检测 Qoder 写回结果（request_id 校验 → 严格解析 → StoryDesign 候选）
# ---------------------------------------------------------------------------

def _response_output_text(response: dict[str, Any]) -> str:
    """从 response 提取模型最终结果文本。

    result（结构化对象）优先，output（模型原始文本）兜底；都没有则报错。
    提取后统一走现有 _parse_agent_result 严格校验，不新增第二条宽松通道。
    """
    result = response.get("result")
    if isinstance(result, dict) and result:
        return json.dumps(result, ensure_ascii=False)
    output = response.get("output")
    if isinstance(output, str) and output.strip():
        return output
    raise NewProjectError("Qoder 返回结果缺少模型输出。")


def _finalize_request(request: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    """response → request_id 校验 → 现有严格业务解析 → StoryDesign 候选。

    只返回展示形状（同旧 propose 返回），不写 03_作品工程；proposal token
    来自临时工作区 proposal_meta.json，绝不进入 Prompt / UI 之外的通道。
    """
    # 1. request_id 防串任务：不一致直接丢弃，绝不让旧结果串到新请求
    if response.get("request_id") != request["request_id"]:
        raise NewProjectError("返回结果与任务不匹配（request_id 不一致），已丢弃。")

    # 2. 状态校验
    resp_status = response.get("status")
    if resp_status not in (None, "completed"):
        err = response.get("error") or f"Qoder 返回状态异常：{resp_status}"
        raise NewProjectError(err)

    # 3. 提取模型最终结果 → 现有严格 JSON/字段验证
    raw = _response_output_text(response)
    parsed = _parse_agent_result(raw)

    # 4. 现有 StoryDesign 生成候选（临时 pre-project 工作区）
    meta = request.get("meta") or {}
    project_id = str(meta.get("project_id") or "")
    proposal_dir = _proposal_dir(project_id)
    try:
        sd_result = run_story_design(
            project_dir=proposal_dir,
            author_input=meta.get("idea") or "",
            brief_id=_BRIEF_ID,
            context_id=_CONTEXT_ID,
            candidate_id=_CANDIDATE_ID,
            semantic_interpretation=parsed["semantic_interpretation"],
            model_output=parsed["model_output"],
        )
    except SDContractError as exc:
        raise NewProjectError(f"StoryDesign 拒绝生成候选：{exc}") from exc

    candidate = sd_result["candidate"]
    if candidate.get("status") != "proposal_noncanonical":
        raise NewProjectError("候选状态异常（非 proposal_noncanonical），已中止。")

    proposal_meta = _load_proposal_meta(project_id)
    content = candidate.get("content") or {}
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
        "message": "候选已生成（未写入正式作品，等待你的确认）",
    }


def get_new_project_request(request_id: str) -> dict[str, Any]:
    """轮询 Qoder 写回结果（UI 每 2-3 秒调用一次）。

    返回 status：pending（继续等）/ completed（含候选）/ failed / expired /
    canceled。终态（completed/failed/expired/canceled）都会清理桥文件，
    保证旧结果不可能被下一次请求接受。
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

    # pending：先查超时（有超时要求），再查 response
    if bridge.is_expired(request):
        if project_id:
            _cleanup_proposal(project_id)
        bridge.cleanup_request(request_id)
        return {"request_id": request_id, "status": "expired", "error": "任务已超时，请重新发起。"}

    response = bridge.read_response(request_id)
    if response is None:
        return {"request_id": request_id, "status": "pending"}

    try:
        result = _finalize_request(request, response)
    except NewProjectError as exc:
        if project_id:
            _cleanup_proposal(project_id)
        bridge.cleanup_request(request_id)
        return {"request_id": request_id, "status": "failed", "error": str(exc)}

    # 成功：清理桥文件（保留临时候选工作区，供确认时使用）
    bridge.cleanup_request(request_id)
    return {"request_id": request_id, "status": "completed", "result": result}


def cancel_new_project_request(request_id: str) -> dict[str, Any]:
    """取消等待：标记 canceled、删除可能已存在的 response 与临时候选。

    取消后旧结果不可能被接受（state=canceled 优先于任何迟到的 response）；
    下一次请求使用全新 request_id，天然隔离。request 文件保留 canceled 状态，
    由下一次轮询返回 canceled 并清理。
    """
    request_id = (request_id or "").strip()
    if not request_id:
        raise NewProjectError("缺少任务标识（request_id）。")

    request = bridge.get_request(request_id)
    if request is not None:
        bridge.mark_canceled(request_id)
        project_id = str((request.get("meta") or {}).get("project_id") or "")
        if project_id:
            _cleanup_proposal(project_id)
        # active 不再指向已取消请求，Qoder /gowrite 不会执行已取消的任务
        bridge.clear_active_if(request_id)
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

    # 用 token 反查项目：token 存在 proposal_meta.json 中
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

    # 读取后台保存的候选（designs/design-idea-001.json），只信这一版
    candidate_path = matched / "designs" / f"{_CANDIDATE_ID}.json"
    if not candidate_path.exists():
        raise NewProjectError("候选数据缺失，请重新生成。")
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    content = candidate.get("content") or {}

    # 正式 Author Intent（必须通过 frozen validate_author_intent；project_id/intent_rev 由 create_project 注入）
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

    # --- create_project 已成功：从此刻起，本次"创建作品"已经成功 ---
    # 后续任何后处理失败都只记录 partial success，不抛异常。
    project_dir = Path(created["project_dir"])
    direction_registered = False
    warning: Optional[str] = None
    state_rev: Optional[int] = None
    try:
        # 读取 brief/context（临时工作区内，与 candidate 同一 project_id）
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
        # 作品已创建成功；approved direction 登记失败不阻塞整体成功。
        # 如实记录 partial success，允许作者进入作品概览。
        # 注意：底层异常文本不返回前端（仅记录 warning 固定提示）。
        direction_registered = False
        warning = "作品已创建，但故事方向的规划登记未完成。正式 Author Intent 已保存。"
    finally:
        # 无论后处理成功还是失败，都清理临时候选，避免作者再次确认同一 proposal
        _cleanup_proposal(project_id)

    return {
        "project_id": created["project_id"],
        "name": created["name"],
        "project_dir": str(created["project_dir"]),
        "state_rev": state_rev,
        "approved_direction_registered": direction_registered,
        "warning": warning,
        "message": "作品已创建",
    }
