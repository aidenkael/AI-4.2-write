# -*- coding: utf-8 -*-
"""验证式执行审计（gowrite_execution_audit/v1）。

目的（可观测性，不是新的工作流引擎）：
作者在任何任务后都能回答：
- Agent 是否真的运行过？用了哪种执行模式 / 哪个 Agent / 哪个模型？
- 哪些 Go Write Skills 真的执行了（StoryDesign / StoryPlan / StoryWrite /
  ContextCompiler / KnowledgeRetrieve / MaterialIntake / SourcePrepare /
  BookDistill —— 只有真实 runtime 调用点才记录）？
- KnowledgeRetrieve 是否运行？候选 / 选中 / 实际注入 Context 的 refs？
- 操作是完成 / 失败 / 取消？耗时多少？

规则：
- 只记录**机械验证**事件（实际 callsite），不记录模型自述；
- 审计写入失败**绝不**使作者操作失败（best-effort、隔离）；
- 存储：06_工作区/运行审计/YYYY-MM-DD/<request_id>.json（Local Only，可删除）；
- 开销：仅标准库 JSON/文件系统；无 AI、无数据库、无后台服务；
- 不存储：API Key / 凭据 / 完整 prompt / 完整模型输出 / 完整正文 /
  BKP 卡全文 / 源书文本。

进程边界说明：retrieval_snapshot.py 是 Agent 在 /gowrite 执行内启动的独立
子进程；主进程先创建审计文件（operation.started / bridge.waiting），子进程
通过 append_event()（load→append→save）写入 retrieval 事件，主进程 finalize
再补 retrieval.selected / context.bound / candidate.created 并 finish()。
"""
from __future__ import annotations

import datetime
import json
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any, Optional

SCHEMA = "gowrite_execution_audit/v1"

# 事件类型（可扩展；required kinds 之外的额外 kind 允许用于真相标注）
EVENT_OPERATION_STARTED = "operation.started"
EVENT_AGENT_DIRECT_PROCESS_STARTED = "agent.direct_process_started"
EVENT_BRIDGE_WAITING = "bridge.waiting"
EVENT_BRIDGE_RESPONSE_RECEIVED = "bridge.response_received"
EVENT_BRIDGE_RESPONSE_DISCARDED = "bridge.response_discarded"
EVENT_AGENT_COMPLETED = "agent.completed"
EVENT_AGENT_FAILED = "agent.failed"
EVENT_AGENT_CANCELED = "agent.canceled"
EVENT_SKILL_STARTED = "skill.started"
EVENT_SKILL_COMPLETED = "skill.completed"
EVENT_SKILL_FAILED = "skill.failed"
EVENT_RETRIEVAL_REQUESTED = "retrieval.requested"
EVENT_RETRIEVAL_PACKAGE_BUILT = "retrieval.package_built"
EVENT_RETRIEVAL_SELECTED = "retrieval.selected"
EVENT_CONTEXT_BOUND = "context.bound"
EVENT_CANDIDATE_CREATED = "candidate.created"
EVENT_AUTHORITY_CONFIRMED = "authority.confirmed"

STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELED = "canceled"

_TERMINAL_STATUSES = frozenset({STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELED})

_REPO_ROOT = Path(__file__).resolve().parents[3]
_AUDIT_ROOT = _REPO_ROOT / "06_工作区" / "运行审计"

# 进程内活跃 recorder（按 request_id；跨进程用文件 append_event 兜底）
_lock = threading.Lock()
_ACTIVE_RECORDERS: dict[str, "AuditRecorder"] = {}


def get_audit_root() -> Path:
    """审计根目录（测试可 monkeypatch 本函数）。"""
    return _AUDIT_ROOT


def _day_dir(day: Optional[str] = None) -> Path:
    day = day or datetime.datetime.now().strftime("%Y-%m-%d")
    return get_audit_root() / day


def audit_path(request_id: str, day: Optional[str] = None) -> Path:
    return _day_dir(day) / f"{request_id}.json"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _now_ts() -> float:
    return datetime.datetime.now(datetime.timezone.utc).timestamp()


def new_request_id() -> str:
    return uuid.uuid4().hex


class AuditRecorder:
    """一次操作的审计记录器（进程内）。

    - 创建时写 operation.started 事件与记录骨架（文件已存在）；
    - event() 追加事件；finish() 写终态（finished_at / duration_ms / status）；
    - 所有写操作 best-effort：失败静默，绝不抛出。
    """

    def __init__(
        self,
        request_id: str,
        operation: str,
        project_id: Optional[str] = None,
        execution: Optional[dict] = None,
        *,
        agent_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.request_id = request_id
        self.operation = operation
        self.project_id = project_id
        self.execution = execution or {}
        self.agent_id = agent_id
        self.model = model
        self.started_at = _now_iso()
        self._started_ts = _now_ts()
        self._events: list[dict[str, Any]] = []
        self._finished = False
        self._status = STATUS_RUNNING
        self._seq = 0
        self._append_locked(
            EVENT_OPERATION_STARTED,
            component="operation",
            details={"operation": operation},
        )
        with _lock:
            _ACTIVE_RECORDERS[request_id] = self

    # ---------------- 事件 ----------------

    def event(
        self,
        kind: str,
        component: str,
        *,
        verified: bool = True,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self._append_locked(kind, component, verified=verified, details=details)

    def finish(self, status: str, error: Optional[str] = None) -> None:
        if status not in _TERMINAL_STATUSES:
            status = STATUS_FAILED
        with _lock:
            if self._finished:
                return
            self._finished = True
            self._status = status
            _ACTIVE_RECORDERS.pop(self.request_id, None)
            self._flush_locked(error=error)

    # ---------------- 内部 ----------------

    def _append_locked(
        self,
        kind: str,
        component: str,
        *,
        verified: bool = True,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self._seq += 1
        event = {
            "seq": self._seq,
            "at": _now_iso(),
            "kind": kind,
            "component": component,
            "verified": bool(verified),
        }
        if details:
            event["details"] = details
        with _lock:
            self._events.append(event)
            self._flush_locked()

    def _record_dict(self, error: Optional[str] = None) -> dict[str, Any]:
        duration_ms = None
        if self._finished:
            duration_ms = int(round((_now_ts() - self._started_ts) * 1000))
        record: dict[str, Any] = {
            "schema": SCHEMA,
            "request_id": self.request_id,
            "operation": self.operation,
            "project_id": self.project_id,
            "execution_mode": self.execution.get("execution_mode"),
            "agent_id": self.execution.get("agent_id") or self.agent_id,
            "model": self.execution.get("model") or self.model,
            "status": self._status,
            "started_at": self.started_at,
            "finished_at": _now_iso() if self._finished else None,
            "duration_ms": duration_ms,
            "events": self._merged_events(),
        }
        if error and self._status in (STATUS_FAILED, STATUS_CANCELED):
            record["error"] = error[:500]
        return record

    def _merged_events(self) -> list[dict[str, Any]]:
        """合并进程内事件 + 磁盘已有事件（子进程如 retrieval CLI 追加的）。

        按 seq 去重合并：子进程（跨进程 append_event）与主进程 recorder
        各自维护 seq；合并后以 seq 排序。避免 finish 覆盖丢失子进程事件。
        """
        by_seq: dict[int, dict[str, Any]] = {}
        for event in self._events:
            by_seq[int(event.get("seq") or 0)] = event
        try:
            path = audit_path(self.request_id)
            if path.exists():
                existing = json.loads(path.read_text(encoding="utf-8"))
                for event in existing.get("events") or []:
                    if isinstance(event, dict):
                        by_seq.setdefault(int(event.get("seq") or 0), event)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):  # noqa: BLE001
            pass
        return [by_seq[seq] for seq in sorted(by_seq)]

    def _flush_locked(self, error: Optional[str] = None) -> None:
        try:
            path = audit_path(self.request_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(self._record_dict(error), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(path)
        except OSError:  # noqa: BLE001 — 审计失败绝不阻断业务
            pass


# ---------------------------------------------------------------------------
# 跨进程 append（retrieval_snapshot.py 子进程 / 无 recorder 的调用点）
# ---------------------------------------------------------------------------

def append_event(
    request_id: str,
    kind: str,
    component: str,
    *,
    verified: bool = True,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """向已有审计记录追加事件（best-effort）。

    优先进程内 recorder；不存在时 load→append→save 文件（跨进程场景）。
    记录文件不存在时静默忽略（没有记录就不造记录）。
    """
    with _lock:
        recorder = _ACTIVE_RECORDERS.get(request_id)
    if recorder is not None:
        recorder.event(kind, component, verified=verified, details=details)
        return
    path = audit_path(request_id)
    try:
        if not path.exists():
            return
        record = json.loads(path.read_text(encoding="utf-8"))
        events = record.get("events")
        if not isinstance(events, list):
            return
        if record.get("status") in _TERMINAL_STATUSES:
            return  # 终态记录不再追加
        seq = max((int(e.get("seq") or 0) for e in events), default=0) + 1
        events.append({
            "seq": seq,
            "at": _now_iso(),
            "kind": kind,
            "component": component,
            "verified": bool(verified),
            **({"details": details} if details else {}),
        })
        record["events"] = events
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except (OSError, json.JSONDecodeError, KeyError, TypeError):  # noqa: BLE001
        pass


def finish_file(
    request_id: str,
    status: str,
    error: Optional[str] = None,
    *,
    execution: Optional[dict] = None,
) -> None:
    """跨进程/兜底终态写入：给没有 recorder 的记录补 finished_at/duration/status。"""
    if status not in _TERMINAL_STATUSES:
        status = STATUS_FAILED
    with _lock:
        recorder = _ACTIVE_RECORDERS.get(request_id)
    if recorder is not None:
        recorder.finish(status, error)
        return
    path = audit_path(request_id)
    try:
        if not path.exists():
            return
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("status") in _TERMINAL_STATUSES:
            return
        started_raw = record.get("started_at")
        started_ts = None
        if started_raw:
            try:
                started_ts = datetime.datetime.fromisoformat(started_raw).timestamp()
            except ValueError:
                started_ts = None
        record["status"] = status
        record["finished_at"] = _now_iso()
        record["duration_ms"] = (
            int(round((_now_ts() - started_ts) * 1000)) if started_ts else None
        )
        if error and status in (STATUS_FAILED, STATUS_CANCELED):
            record["error"] = error[:500]
        if execution:
            record["execution_mode"] = execution.get("execution_mode") or record.get("execution_mode")
            record["agent_id"] = execution.get("agent_id") or record.get("agent_id")
            record["model"] = execution.get("model") or record.get("model")
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except (OSError, json.JSONDecodeError, KeyError, TypeError):  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# 读取 / 清理（只读 API + 显式 clear）
# ---------------------------------------------------------------------------

def _load_record(path: Path) -> Optional[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return None
    return data


def list_execution_audits(
    limit: int = 50,
    *,
    operation: Optional[str] = None,
    status: Optional[str] = None,
    project_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """按时间倒序列出最近记录（只含摘要字段，不含完整事件列表）。"""
    root = get_audit_root()
    records: list[dict[str, Any]] = []
    if not root.exists():
        return records
    for path in sorted(root.glob("*/*.json"), reverse=True):
        record = _load_record(path)
        if record is None:
            continue
        if operation and record.get("operation") != operation:
            continue
        if status and record.get("status") != status:
            continue
        if project_id and record.get("project_id") != project_id:
            continue
        records.append({
            "request_id": record.get("request_id"),
            "operation": record.get("operation"),
            "project_id": record.get("project_id"),
            "execution_mode": record.get("execution_mode"),
            "agent_id": record.get("agent_id"),
            "model": record.get("model"),
            "status": record.get("status"),
            "started_at": record.get("started_at"),
            "finished_at": record.get("finished_at"),
            "duration_ms": record.get("duration_ms"),
            "event_count": len(record.get("events") or []),
            "error": record.get("error"),
        })
        if len(records) >= limit:
            break
    return records


def get_execution_audit(request_id: str) -> Optional[dict[str, Any]]:
    """返回完整单条记录（含事件时间线）；不存在返回 None。"""
    request_id = (request_id or "").strip()
    if not request_id:
        return None
    for day_dir in get_audit_root().glob("*"):
        if not day_dir.is_dir():
            continue
        record = _load_record(day_dir / f"{request_id}.json")
        if record is not None:
            return record
    return None


def clear_execution_audits() -> dict[str, Any]:
    """显式清理：只删除 06_工作区/运行审计（绝不触碰其他目录）。"""
    root = get_audit_root()
    count = 0
    if root.exists():
        for path in root.rglob("*"):
            if path.is_file() and path.suffix == ".json":
                count += 1
        try:
            shutil.rmtree(root, ignore_errors=True)
        except OSError:  # noqa: BLE001
            pass
    return {"cleared_files": count, "message": "执行记录已清理"}
