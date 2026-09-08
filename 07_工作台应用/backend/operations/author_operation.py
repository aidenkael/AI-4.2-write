# -*- coding: utf-8 -*-
"""当前活跃作者操作恢复（App 级任务协调器 remount/reload 后的真相源）。

目的（最小恢复 API，不是任务队列）：
- 前端 remount/reload 后，App 级 AuthorTaskCoordinator 调用
  ``get_active_author_operation()`` 恢复唯一当前待办作者操作；
- 数据源只用现有桥请求文件（06_工作区/应用开发/.qoder_bridge/requests/）
  + 进程内 Direct 执行任务状态（execution_tasks.manager）——不新增数据库。

规则（与根不变量一致）：
- Interactive pending 请求可以恢复（请求文件仍在；作者 /gowrite 未执行或
  两阶段中）；
- Direct pending 请求只有在其 in-process 执行任务仍然存在/运行时才可恢复；
  进程重启后 worker 已不存在 → 按孤儿失败关闭（fail closed），绝不显示假的
  “运行中”；
- 只返回非机密事实：request_id / kind（归一化操作）/ project_id /
  execution_mode / agent_id / model（机械已知时）/ phase / state / 作者可读消息；
- 绝不返回 task/prompt 文本、token、凭据、完整输出。

单活跃语义：同一时刻至多一个 Interactive /gowrite 请求（桥激活保护）；
至多一个 Direct 执行（ExecutionTaskManager 单槽）。两者可并存时优先返回
需要作者动作的 /gowrite 活跃请求。
"""
from __future__ import annotations

from typing import Any, Optional

from operations import execution_tasks
from operations import qoder_bridge as bridge

# 桥 kind → 归一化操作名（与审计 operation 命名一致）
_KIND_TO_OPERATION: dict[str, str] = {
    "story_design_propose": "new_project",
    "story_plan_propose": "story_plan",
    "story_write_propose": "story_write",
    "review_propose": "review",
    "foundation_design_propose": "foundation_design",
    # 蒸馏归一化为同一个作者面操作（后端已按素材类型分派 BookDistill / MethodDistill）
    "book_distill_propose": "material_distill",
    "method_distill_propose": "material_distill",
}

# 交互等待时的作者可读消息（阶段相关）
_WAITING_MESSAGES: dict[tuple[str, str], str] = {
    ("story_write_propose", "pending_selection"): "等待 Qoder /gowrite：正在选择本次写作上下文",
    ("story_write_propose", "pending_prose"): "上下文已准备好，Agent 正在自动生成正文",
}


def _author_message(kind: str, phase: Optional[str], execution_mode: Optional[str], orphaned: bool) -> str:
    if orphaned:
        return "直连任务已失效（进程重启后无法恢复），请重新发起。"
    if execution_mode != "direct":
        if (kind, phase or "") in _WAITING_MESSAGES:
            return _WAITING_MESSAGES[(kind, phase or "")]
        return "等待 Qoder /gowrite 执行任务"
    return "后台 AI 正在执行"


def _facts_from_request(request: dict[str, Any], *, orphaned: bool) -> dict[str, Any]:
    kind = str(request.get("kind") or "")
    meta = request.get("meta") or {}
    execution = meta.get("execution") or {}
    execution_mode = execution.get("execution_mode")
    if execution_mode not in ("interactive_bridge", "direct"):
        execution_mode = None
    operation = _KIND_TO_OPERATION.get(kind)
    phase = request.get("phase")
    execution_phase = request.get("execution_phase")
    if execution_phase not in ("waiting_agent", "running"):
        execution_phase = "running" if execution_mode == "direct" else "waiting_agent"
    state = "orphaned" if orphaned else ("running" if execution_mode == "direct" else "pending")
    label = meta.get("target_label") or meta.get("asset_name") or meta.get("name") or None
    return {
        "request_id": str(request.get("request_id") or ""),
        "kind": operation,
        "bridge_kind": kind,
        "project_id": str(meta.get("project_id") or "") or None,
        "execution_mode": execution_mode,
        "agent_id": execution.get("agent_id") or None,
        "model": execution.get("model") or None,
        "phase": phase if isinstance(phase, str) and phase else None,
        "execution_phase": execution_phase,
        "agent_command": request.get("agent_command") if isinstance(request.get("agent_command"), str) else None,
        "asset_id": str(meta.get("asset_id") or "") or None,
        "target_label": str(label) if label else None,
        "state": state,
        "message": _author_message(kind, phase, execution_mode, orphaned),
    }


def _direct_pending_requests() -> list[dict[str, Any]]:
    """扫描桥请求目录中 state=pending 且非交互的请求（Direct 恢复候选）。"""
    found: list[dict[str, Any]] = []
    root = bridge.get_bridge_root()
    requests_dir = root / "requests"
    if not requests_dir.exists():
        return found
    try:
        entries = sorted(requests_dir.glob("*.json"))
    except OSError:
        return found
    for path in entries:
        request = bridge.get_request(path.stem)
        if request is None:
            continue
        if request.get("state") != "pending":
            continue
        meta = request.get("meta") or {}
        execution = meta.get("execution") or {}
        if execution.get("execution_mode") == "direct":
            found.append(request)
    return found


def get_active_author_operations() -> list[dict[str, Any]]:
    """All recoverable operations, including each fail-closed Direct orphan once."""
    facts: list[dict[str, Any]] = []
    root = bridge.get_bridge_root() / "requests"
    if root.exists():
        for path in sorted(root.glob("*.json")):
            request = bridge.get_request(path.stem)
            if request is None or request.get("state") != "pending":
                continue
            meta = request.get("meta") or {}
            execution = meta.get("execution") or {}
            orphaned = False
            if execution.get("execution_mode") == "direct":
                task = execution_tasks.manager.get(path.stem)
                orphaned = task is None
            item = _facts_from_request(request, orphaned=orphaned)
            if item.get("kind"):
                facts.append(item)
            if orphaned:
                bridge.cleanup_request(path.stem)
                execution_tasks.manager.remove(path.stem)
    return facts


def get_active_author_operation() -> dict[str, Any]:
    """返回当前唯一待办作者操作（无则 data=None 语义由调用方处理）。

    返回 dict 或 None；只含非机密事实（见模块 docstring）。
    """
    recovered = get_active_author_operations()
    if recovered:
        return recovered[0]

    return None
