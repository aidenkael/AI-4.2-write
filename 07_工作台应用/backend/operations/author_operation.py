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
    "material_classify_propose": "material_classify",
    # 蒸馏归一化为同一个作者面操作（后端已按素材类型分派 BookDistill / MethodDistill）
    "book_distill_propose": "material_distill",
    "method_distill_propose": "material_distill",
}

# 交互等待时的作者可读消息（阶段相关）
_WAITING_MESSAGES: dict[tuple[str, str], str] = {
    ("story_write_propose", "pending_selection"): "等待 Qoder /gowrite：正在选择本次写作上下文",
    ("story_write_propose", "pending_prose"): "上下文已准备好，请再次执行 /gowrite 生成正文",
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
    state = "orphaned" if orphaned else ("running" if execution_mode == "direct" else "pending")
    return {
        "request_id": str(request.get("request_id") or ""),
        "kind": operation,
        "bridge_kind": kind,
        "project_id": str(meta.get("project_id") or "") or None,
        "execution_mode": execution_mode,
        "agent_id": execution.get("agent_id") or None,
        "model": execution.get("model") or None,
        "phase": phase if isinstance(phase, str) and phase else None,
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


def get_active_author_operation() -> dict[str, Any]:
    """返回当前唯一待办作者操作（无则 data=None 语义由调用方处理）。

    返回 dict 或 None；只含非机密事实（见模块 docstring）。
    """
    # 1. 优先：/gowrite 活跃请求（Interactive，作者动作待办）
    active_id = bridge.get_active_request_id()
    if active_id:
        request = bridge.get_request(active_id)
        if request is not None and request.get("state") == "pending":
            return _facts_from_request(request, orphaned=False)
        # 活跃指针已失效（请求不存在或已终态）：清掉陈旧指针，绝不指向旧任务
        bridge.clear_active_if(active_id)

    # 2. Direct pending 请求：只有任务管理器里仍有真实 worker 才可恢复
    for request in _direct_pending_requests():
        request_id = str(request.get("request_id") or "")
        task = execution_tasks.manager.get(request_id)
        if task is None:
            # 进程重启后 worker 已不存在：fail closed（清理请求，绝不当运行中）
            bridge.cleanup_request(request_id)
            execution_tasks.manager.remove(request_id)
            facts = _facts_from_request(request, orphaned=True)
            return facts
        return _facts_from_request(request, orphaned=False)

    return None
