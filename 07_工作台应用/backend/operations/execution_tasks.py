# -*- coding: utf-8 -*-
"""最小 Direct 执行任务管理器（in-process，仅 threading）。

用途：让 StoryPlan Direct 的 Agent 调用在 pywebview/API 调用线程之外运行，
prepare 立即返回，轮询/取消走现有请求生命周期。

职责边界（只做薄胶水，不建平台）：
- 为 request_id 启动一个后台可调用对象（一次）；
- 维护任务状态：pending / running / completed / failed / canceled；
- 运行期间保留实际 Adapter 实例（取消时调用 adapter.cancel()）；
- 同一时刻只允许一个活跃 Direct 任务（忙碌保护，防 active 指针竞态）；
- 提供终态查询与记录移除；终态记录由 Author Operation 生命周期负责移除。

明确不做：Redis / Celery / asyncio 框架转换 / 持久队列 / 重试 / 调度 /
恢复 / 流式框架 / 事件总线 / 工作流引擎 / 多 Agent 编排。
"""
from __future__ import annotations

import datetime
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

TASK_PENDING = "pending"
TASK_RUNNING = "running"
TASK_COMPLETED = "completed"
TASK_FAILED = "failed"
TASK_CANCELED = "canceled"

_TERMINAL = frozenset({TASK_COMPLETED, TASK_FAILED, TASK_CANCELED})


@dataclass
class ExecutionTask:
    """一个 request_id 的运行中/终态任务记录（仅非机密执行元数据）。"""

    request_id: str
    state: str = TASK_PENDING
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    adapter: Optional[Any] = None          # 运行中的 Adapter 实例（cancel 需要）
    execution: dict = field(default_factory=dict)  # 非机密：mode/agent/model
    error: Optional[str] = None            # 内部诊断（不进入对外快照）
    thread: Optional[threading.Thread] = None  # worker 线程（join 用）


class ExecutionTaskManager:
    """In-process 单活跃槽任务管理器（thread-safe）。

    并发模型：一次至多一个活跃 Direct 任务。取消是异步的（adapter.cancel()
    只请求终止子进程），因此 `_active` 在 worker 线程真正退出前保持占用，
    防止取消过程中第二个任务抢占 active 指针。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, ExecutionTask] = {}
        self._active: Optional[str] = None

    # ---------------- 查询 ----------------

    def is_busy(self) -> bool:
        """是否已有活跃（运行中或正在收尾）的 Direct 任务。"""
        with self._lock:
            return self._active is not None

    def is_canceled(self, request_id: str) -> bool:
        """任务是否已取消；记录已移除时保守视为已取消（丢弃晚结果）。"""
        with self._lock:
            task = self._tasks.get(request_id)
            if task is None:
                return True
            return task.state == TASK_CANCELED

    def get(self, request_id: str) -> Optional[dict]:
        """返回任务当前状态快照（非机密；无记录返回 None）。"""
        with self._lock:
            task = self._tasks.get(request_id)
            if task is None:
                return None
            duration_ms = None
            if task.finished_at is not None and task.started_at is not None:
                duration_ms = int(round((task.finished_at - task.started_at) * 1000))
            return {
                "request_id": task.request_id,
                "state": task.state,
                "execution": dict(task.execution),
                "started_at": _iso(task.started_at),
                "finished_at": _iso(task.finished_at),
                "duration_ms": duration_ms,
            }

    # ---------------- 启动 ----------------

    def start(
        self,
        request_id: str,
        worker: Callable[[], None],
        adapter: Optional[Any] = None,
        execution: Optional[dict] = None,
    ) -> bool:
        """启动后台 worker；已有活跃 Direct 任务时返回 False（忙碌保护）。"""
        with self._lock:
            if self._active is not None:
                return False
            existing = self._tasks.get(request_id)
            if existing is not None and existing.state not in _TERMINAL:
                return False
            task = ExecutionTask(
                request_id=request_id,
                state=TASK_RUNNING,
                started_at=time.time(),
                adapter=adapter,
                execution=dict(execution or {}),
            )
            self._tasks[request_id] = task
            self._active = request_id
        thread = threading.Thread(
            target=self._run_worker,
            args=(request_id, worker),
            name=f"storyplan-direct-{request_id[:8]}",
            daemon=True,
        )
        task.thread = thread
        thread.start()
        return True

    def _run_worker(self, request_id: str, worker: Callable[[], None]) -> None:
        """worker 线程骨架：异常兜底标记 failed；退出时释放活跃槽。"""
        try:
            worker()
        except Exception as exc:  # noqa: BLE001 — worker 异常 → failed
            with self._lock:
                task = self._tasks.get(request_id)
                if task is not None and task.state not in _TERMINAL:
                    task.state = TASK_FAILED
                    task.error = str(exc)
                    task.finished_at = time.time()
        finally:
            with self._lock:
                if self._active == request_id:
                    self._active = None

    def finish(self, request_id: str, state: str) -> bool:
        """worker 正常完成后标记终态；已终态（含 canceled）时忽略。"""
        if state not in (TASK_COMPLETED, TASK_FAILED):
            raise ValueError(f"finish 只接受 completed/failed：{state!r}")
        with self._lock:
            task = self._tasks.get(request_id)
            if task is None or task.state in _TERMINAL:
                return False
            task.state = state
            task.finished_at = time.time()
            return True

    # ---------------- 取消 ----------------

    def cancel(self, request_id: str) -> bool:
        """请求取消：标记 canceled 并调用运行中 adapter 的 cancel()（幂等）。

        晚完成的 AgentResult 由 worker 侧的 is_canceled 检查 + 桥请求的
        canceled 状态双重丢弃，不会变成可接受的响应。
        """
        adapter = None
        with self._lock:
            task = self._tasks.get(request_id)
            if task is None or task.state in _TERMINAL:
                return False
            adapter = task.adapter
            task.state = TASK_CANCELED
            task.finished_at = time.time()
        if adapter is not None:
            try:
                adapter.cancel()
            except Exception:  # noqa: BLE001 — cancel 尽力而为
                pass
        return True

    def remove(self, request_id: str) -> None:
        """移除任务记录（Author Operation 生命周期终态时调用；幂等）。

        注意：不直接清理 `_active` —— 活跃槽由 worker 线程退出时释放，
        避免 worker 仍在运行期间被误判为空闲而并发启动第二个任务。
        """
        with self._lock:
            self._tasks.pop(request_id, None)

    def join(self, request_id: str, timeout: float = 5.0) -> bool:
        """等待该任务的 worker 线程完全退出（响应已写入或已丢弃）。

        用于确定性等待终态（测试/收尾）；记录不存在时返回 False。
        """
        with self._lock:
            task = self._tasks.get(request_id)
            thread = task.thread if task is not None else None
        if thread is None:
            return False
        thread.join(timeout)
        return not thread.is_alive()


def _iso(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat(timespec="seconds")


# 生产单例（测试通过替换 sp_ops._exec_task_manager 使用独立实例）
manager = ExecutionTaskManager()
