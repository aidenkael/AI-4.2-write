# -*- coding: utf-8 -*-
"""Qoder 桌面端薄桥（Go Write 管长期记忆，Qoder 只执行当前任务）。

架构（已确认，不重新讨论）：
- Go Write 只负责：生成唯一 request_id → 保存当前完整 Agent task →
  指定结果写回位置 → 等待/检测结果 → 校验 request_id →
  把模型最终结果交回现有严格业务解析。
- Qoder 桌面端（作者常用会话，可随时丢弃）执行后端分配的 `/gowrite:<slot>`：
  原子 claim 固定 slot → 读取该请求 → 按 task 执行 → 写 response 文件。

本模块是纯文件协议，不调用任何模型 API，不复制任何 StoryDesign / StoryPlan
/ StoryWrite 业务规则（真正的业务要求由 pending task 提供）。

文件布局（全部在 06_工作区/应用开发/.qoder_bridge/，Local Only，可删除）：
- slots/<slot>.json             四个固定 Interactive slot（精确绑定 request_id）
- claims/<request_id>.claim     跨 Qoder 会话/进程的原子执行 claim
- requests/<request_id>.json     待执行任务（Go Write 写，Qoder 读）
- responses/<request_id>.json    执行结果（Qoder 写，Go Write 读）

请求存储与 Interactive slot 分配分离：
- 任何请求（Interactive / Direct）都写入 requests/<request_id>.json；
- 只有 Interactive 请求通过 ``activate_for_gowrite=True`` 分配固定 slot；
  Direct 请求不分配 slot；
- 仅 material_distill 可占用多个 slot；所有其他 Author Operation 仍独占，
  并与 material_distill 双向互斥。

安全：
- request_id 是防串任务的唯一键；response 必须携带相同 request_id。
- 取消/超时/完成后清理请求文件；旧 response 永远不可能被下一次接受。
- 本模块绝不读写 03_作品工程 / Story State / 正式正文。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import uuid
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# 路径与常量
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]

# 临时桥根目录：06_工作区/应用开发/.qoder_bridge（已 gitignore，Local Only）
_BRIDGE_ROOT = _REPO_ROOT / "06_工作区" / "应用开发" / ".qoder_bridge"

REQUEST_SCHEMA = "gowrite_request/v1"
RESPONSE_SCHEMA = "gowrite_response/v1"

# 当前生产流程允许的响应状态（其余状态一律按坏信封拒绝）
_ALLOWED_RESPONSE_STATUSES = frozenset({"completed", "failed"})

# 默认任务超时：作者可能 Alt+Tab 后稍晚才执行 /gowrite，给 30 分钟
DEFAULT_TASK_TIMEOUT_SECONDS = 30 * 60
INTERACTIVE_SLOT_COUNT = 4
_MATERIAL_KINDS = frozenset({"book_distill_propose", "method_distill_propose"})
_INTERACTIVE_ALLOCATION_LOCK = threading.RLock()

# 本机 Qoder 桌面端窗口标题匹配词（AppActivate 按标题部分匹配）
_QODER_WINDOW_TITLE = "Qoder"


def get_bridge_root() -> Path:
    """桥根目录（测试可 monkeypatch 本函数）。"""
    return _BRIDGE_ROOT


# ---------------------------------------------------------------------------
# 内部路径
# ---------------------------------------------------------------------------

def _requests_dir() -> Path:
    return get_bridge_root() / "requests"


def _responses_dir() -> Path:
    return get_bridge_root() / "responses"


def _active_path() -> Path:
    return get_bridge_root() / "active.json"


def _slots_dir() -> Path:
    return get_bridge_root() / "slots"


def _claims_dir() -> Path:
    return get_bridge_root() / "claims"


def _slot_path(slot: int) -> Path:
    return _slots_dir() / f"{slot}.json"


def _claim_path(request_id: str) -> Path:
    return _claims_dir() / f"{request_id}.claim"


def request_path(request_id: str) -> Path:
    return _requests_dir() / f"{request_id}.json"


def response_path(request_id: str) -> Path:
    return _responses_dir() / f"{request_id}.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# 请求创建（Go Write 侧）
# ---------------------------------------------------------------------------

def create_request(
    task: str,
    kind: str,
    meta: Optional[dict[str, Any]] = None,
    timeout_seconds: Optional[int] = None,
    request_id: Optional[str] = None,
    phase: Optional[str] = None,
    activate_for_gowrite: bool = False,
) -> str:
    """生成唯一 request_id 并保存完整 Agent task。

    返回 request_id。request 文件包含 response_path，Qoder 只按此路径写回。
    ``request_id`` 可选：调用方预生成时（如任务文本需要内嵌 request_id）
    可显式传入；缺省自动生成。``phase`` 可选：两阶段交互桥的阶段标记
    （缺省不写入；其它操作不受影响）。

    存储与激活分离（Go Write 生命周期根不变量）：
    - 创建请求文件 != 把请求暴露给 Qoder /gowrite；
    - ``activate_for_gowrite=False``（缺省，Direct 一律如此）：只写请求文件，
      绝不触碰 active.json；
    - ``activate_for_gowrite=True``（仅 Interactive）：显式把本请求设为
      /gowrite 活跃任务；若已存在其它活跃 /gowrite 请求则删除刚创建的
      请求文件并抛 ``BridgeBusyError``（绝不静默覆盖 active.json）。
    """
    request_id = request_id or uuid.uuid4().hex
    timeout = timeout_seconds or DEFAULT_TASK_TIMEOUT_SECONDS
    created = datetime.now(timezone.utc)
    expires = created + timedelta(seconds=timeout)

    request: dict[str, Any] = {
        "schema": REQUEST_SCHEMA,
        "request_id": request_id,
        "kind": kind,
        "created_at": created.isoformat(timespec="seconds"),
        "expires_at": expires.isoformat(timespec="seconds"),
        "wait_timeout_seconds": timeout,
        "state": "pending",  # pending | canceled | completed | failed
        "task": task,        # 完整 Agent task（业务规则全部在这里）
        "response_path": str(response_path(request_id)),
        "meta": meta or {},
    }
    if phase is not None:
        request["phase"] = phase

    requests_dir = _requests_dir()
    requests_dir.mkdir(parents=True, exist_ok=True)
    _responses_dir().mkdir(parents=True, exist_ok=True)
    (requests_dir / f"{request_id}.json").write_text(
        json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if activate_for_gowrite and not allocate_interactive_slot(request_id):
        # 没有空闲槽：绝不覆盖其它 Interactive 请求；回滚刚创建的请求文件。
        try:
            (requests_dir / f"{request_id}.json").unlink(missing_ok=True)
        except OSError:
            pass
        raise BridgeBusyError()
    return request_id


class BridgeBusyError(Exception):
    """已有活跃的 /gowrite 请求（交互桥忙碌），禁止覆盖。"""

    def __init__(self) -> None:
        super().__init__("Agent 并行任务已达上限，请等待或取消一个任务。")


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    """Small local-file atomic replace; request files are never a global selector."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def allocate_interactive_slot(request_id: str) -> bool:
    """Reserve one slot while preserving material-only concurrency."""
    with _INTERACTIVE_ALLOCATION_LOCK:
        req = get_request(request_id)
        if req is None or req.get("state") != "pending":
            return False
        existing = req.get("slot")
        if isinstance(existing, int) and 1 <= existing <= INTERACTIVE_SLOT_COUNT:
            return True

        occupied: list[dict[str, Any]] = []
        for slot in range(1, INTERACTIVE_SLOT_COUNT + 1):
            other_id = _slot_request_id(slot)
            if not other_id or other_id == request_id:
                continue
            other = get_request(other_id)
            if other and other.get("state") == "pending":
                occupied.append(other)
        request_is_material = req.get("kind") in _MATERIAL_KINDS
        if occupied and (
            not request_is_material
            or any(other.get("kind") not in _MATERIAL_KINDS for other in occupied)
        ):
            return False

        _slots_dir().mkdir(parents=True, exist_ok=True)
        for slot in range(1, INTERACTIVE_SLOT_COUNT + 1):
            path = _slot_path(slot)
            try:
                fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                continue
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump({"request_id": request_id}, handle, ensure_ascii=False)
                req["slot"] = slot
                req["agent_command"] = f"/gowrite:{slot}"
                req["execution_phase"] = "waiting_agent"
                _write_json_atomic(request_path(request_id), req)
                return True
            except Exception:
                path.unlink(missing_ok=True)
                raise
        return False


def _slot_request_id(slot: int) -> Optional[str]:
    try:
        data = json.loads(_slot_path(slot).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    request_id = data.get("request_id")
    return request_id if isinstance(request_id, str) and request_id else None


def claim_request_for_slot(slot: int) -> Optional[dict[str, Any]]:
    """Atomically claim exactly the request reserved for ``slot``.

    The O_EXCL claim is process-safe across separate Qoder sessions.  A second
    execution, a stale command, or a canceled request fails closed.
    """
    if slot not in range(1, INTERACTIVE_SLOT_COUNT + 1):
        return None
    request_id = _slot_request_id(slot)
    if not request_id:
        return None
    req = get_request(request_id)
    if not req or req.get("state") != "pending" or req.get("execution_phase") != "waiting_agent":
        return None
    try:
        _claims_dir().mkdir(parents=True, exist_ok=True)
        fd = os.open(str(_claim_path(request_id)), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(str(slot))
        # Re-read after acquiring the claim so cancellation cannot become runnable.
        req = get_request(request_id)
        if not req or req.get("state") != "pending" or req.get("execution_phase") != "waiting_agent":
            _claim_path(request_id).unlink(missing_ok=True)
            return None
        req["execution_phase"] = "running"
        _write_json_atomic(request_path(request_id), req)
        return req
    except Exception:
        _claim_path(request_id).unlink(missing_ok=True)
        raise


def release_claim(request_id: str) -> None:
    _claim_path(request_id).unlink(missing_ok=True)


def release_interactive_slot(request_id: str) -> None:
    req = get_request(request_id)
    slot = req.get("slot") if isinstance(req, dict) else None
    if isinstance(slot, int) and _slot_request_id(slot) == request_id:
        _slot_path(slot).unlink(missing_ok=True)
    release_claim(request_id)


def activate_request(request_id: str) -> bool:
    """Compatibility name: allocate one exact Interactive slot."""
    # Compatibility name for callers not yet migrated. It does not create or
    # consult a global active pointer.
    return allocate_interactive_slot(request_id)


def get_active_request_id() -> Optional[str]:
    """Removed global-selection API. Interactive tasks are slot-bound."""
    return None


def get_request(request_id: str) -> Optional[dict[str, Any]]:
    """读取请求文件；不存在返回 None。"""
    path = request_path(request_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def is_expired(request: dict[str, Any]) -> bool:
    """请求是否已超时（现在 > expires_at）。"""
    if request.get("execution_phase") == "running":
        return False
    raw = request.get("expires_at")
    if not raw:
        return False
    try:
        expires = datetime.fromisoformat(raw)
    except ValueError:
        return False
    return datetime.now(timezone.utc) > expires


# ---------------------------------------------------------------------------
# 结果读取（Go Write 侧）
# ---------------------------------------------------------------------------

class BridgeProtocolError(Exception):
    """桥协议错误：响应信封缺少有效载荷或字段类型非法（普通可读错误）。"""


def _failed_response(request_id: str, error: str) -> dict[str, Any]:
    """稳定失败信封（与畸形 JSON 的失败信封同构，request_id 保持原值）。"""
    return {
        "schema": RESPONSE_SCHEMA,
        "request_id": request_id,
        "status": "failed",
        "result": None,
        "output": None,
        "error": error,
    }


def read_response(request_id: str) -> Optional[dict[str, Any]]:
    """读取 response 文件；不存在返回 None。

    信封边界集中校验（consumer 永远只看到合法信封）：
    - schema 必须恰为 gowrite_response/v1；
    - request_id 必须与请求一致；
    - status 必须是当前生产流程使用的状态（completed / failed）；
    - result 必须是 dict 或 null；output / error 必须是 str 或 null；
    - completed 必须携带有效载荷（result 对象或非空 output 文本）；
      failed 必须携带可用的 error；
    - output 中出现对象/数组（应放 result）→ 直接拒绝，绝不静默接受。

    任一条件不满足 → 返回携带相同 request_id 的稳定失败信封（含桥协议错误），
    绝不把 AttributeError/TypeError 传给业务层，也绝不猜测修复畸形 JSON。
    产生合法 JSON 是 Qoder 的职责（/gowrite 必须用标准 JSON parser 自验证）。
    """
    path = response_path(request_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _failed_response(request_id, "结果文件不是合法 JSON，Go Write 已丢弃。")
    if not isinstance(data, dict):
        return _failed_response(request_id, "结果信封不是 JSON 对象，已拒绝。")
    if data.get("schema") != RESPONSE_SCHEMA:
        return _failed_response(request_id, f"结果信封 schema 不是 {RESPONSE_SCHEMA}，已拒绝。")
    if data.get("request_id") != request_id:
        return _failed_response(request_id, "结果 request_id 与当前任务不一致，已拒绝。")
    status = data.get("status")
    if status not in _ALLOWED_RESPONSE_STATUSES:
        return _failed_response(request_id, f"结果信封 status 非法（{status!r}），已拒绝。")
    result = data.get("result")
    output = data.get("output")
    error = data.get("error")
    if result is not None and not isinstance(result, dict):
        return _failed_response(request_id, "结果信封 result 类型错误（应为 JSON 对象或 null），已拒绝。")
    if output is not None and not isinstance(output, str):
        return _failed_response(request_id, "结果信封 output 类型错误（应为字符串或 null），已拒绝；对象/数组必须放在 result。")
    if error is not None and not isinstance(error, str):
        return _failed_response(request_id, "结果信封 error 类型错误（应为字符串或 null），已拒绝。")
    if status == "completed":
        if result is None and not (isinstance(output, str) and output.strip()):
            return _failed_response(request_id, "completed 结果缺少有效载荷（result 对象或非空 output 文本）。")
    elif status == "failed":
        if not (isinstance(error, str) and error.strip()):
            return _failed_response(request_id, "failed 结果缺少可用的 error。")
    return data


def response_result_text(response: dict[str, Any]) -> str:
    """把已校验信封中的模型结果提取为 JSON 文本（result 对象优先，output 纯文本兜底）。

    read_response 已保证 result 为 dict/null、output 为 str/null；本函数绝不对
    未知类型调用字符串方法。result 为对象 → json.dumps(ensure_ascii=False)；
    否则取非空 output 文本；均无 → 抛 BridgeProtocolError。
    """
    result = response.get("result")
    if isinstance(result, dict) and result:
        return json.dumps(result, ensure_ascii=False)
    output = response.get("output")
    if isinstance(output, str) and output.strip():
        return output
    raise BridgeProtocolError("执行结果缺少模型输出。")


def write_response(
    request_id: str,
    *,
    result: Optional[dict[str, Any]] = None,
    output: Optional[str] = None,
    status: str = "completed",
    error: Optional[str] = None,
) -> Path:
    """写 response 文件（测试与模拟 Agent 用；真实写回由 Qoder /gowrite 完成）。

    result / output 二选一：result 为结构化对象（首选），output 为模型原始文本。
    """
    response: dict[str, Any] = {
        "schema": RESPONSE_SCHEMA,
        "request_id": request_id,
        "created_at": _now_iso(),
        "status": status,
        "result": result,
        "output": output,
        "error": error,
    }
    _responses_dir().mkdir(parents=True, exist_ok=True)
    path = response_path(request_id)
    path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 状态变更与清理
# ---------------------------------------------------------------------------

def mark_canceled(request_id: str) -> bool:
    """把请求标记为 canceled（同时删除可能已存在的 response，防止旧结果被接受）。"""
    req = get_request(request_id)
    if req is None:
        return False
    req["state"] = "canceled"
    _write_json_atomic(request_path(request_id), req)
    release_interactive_slot(request_id)
    try:
        response_path(request_id).unlink(missing_ok=True)
    except OSError:
        pass
    return True


def clear_active_if(request_id: str) -> None:
    """Compatibility cleanup: release only this request's reserved slot."""
    release_interactive_slot(request_id)


def clear_response(request_id: str) -> None:
    """只删除 response 文件（两阶段交互桥：阶段间消费后清除，等第二次 /gowrite）。"""
    try:
        response_path(request_id).unlink(missing_ok=True)
    except OSError:
        pass


def set_request_task(request_id: str, task: str, *, phase: Optional[str] = None) -> bool:
    """原地更新请求文件的任务文本（两阶段交互桥：阶段 1 验收后换成阶段 2 任务）。

    Two-phase Interactive requests release their old claim, retain their slot,
    return to waiting_agent, and renew only the waiting deadline.
    请求不存在或已终态时返回 False。
    """
    req = get_request(request_id)
    if req is None:
        return False
    if req.get("state") != "pending":
        return False
    req["task"] = task
    if phase is not None:
        req["phase"] = phase
    if isinstance(req.get("slot"), int):
        release_claim(request_id)
        req["execution_phase"] = "waiting_agent"
        timeout = int(req.get("wait_timeout_seconds") or DEFAULT_TASK_TIMEOUT_SECONDS)
        req["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=timeout)).isoformat(timespec="seconds")
    _write_json_atomic(request_path(request_id), req)
    return True


def cleanup_request(request_id: str) -> None:
    """终态清理：删除请求/响应文件，并清掉可能指向本请求的 active 指针。"""
    release_interactive_slot(request_id)
    try:
        request_path(request_id).unlink(missing_ok=True)
        response_path(request_id).unlink(missing_ok=True)
    except OSError:
        pass
    # Old active.json is no longer read. Remove a stale legacy file only.
    try:
        _active_path().unlink(missing_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# 非侵入：把已运行的 Qoder 桌面端切到前台（尽力而为，失败静默）
# ---------------------------------------------------------------------------
# 只做前台切换（Windows AppActivate 按窗口标题匹配），绝不模拟键盘 / 回车
# / 提交任务；做不到时作者自己 Alt+Tab 即可。

def focus_qoder_window() -> bool:
    """尝试把 Qoder 桌面端切到前台；成功返回 True，失败静默返回 False。"""
    if os.name != "nt":
        return False
    try:
        proc = subprocess.Popen(
            [
                "powershell", "-NoProfile", "-NonInteractive", "-Command",
                f"(New-Object -ComObject WScript.Shell).AppActivate('{_QODER_WINDOW_TITLE}')",
            ],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        proc.wait(timeout=10)
        return True
    except Exception:  # noqa: BLE001 — 尽力而为，任何失败都不影响主流程
        return False


def cleanup_bridge_root() -> None:
    """清理桥根下的临时产物（requests/responses/active.json）。

    保留静态文件（如 gowrite.md.template）；不影响正式作品。
    """
    for d in (_requests_dir(), _responses_dir(), _slots_dir(), _claims_dir()):
        shutil.rmtree(d, ignore_errors=True)
    try:
        _active_path().unlink(missing_ok=True)
    except OSError:
        pass


if __name__ == "__main__":
    # Qoder custom commands use this tiny deterministic entrypoint before they
    # read a task. It deliberately prints only the claimable request JSON.
    if len(sys.argv) == 3 and sys.argv[1] == "claim":
        try:
            claimed = claim_request_for_slot(int(sys.argv[2]))
        except ValueError:
            claimed = None
        if claimed is not None:
            print(json.dumps(claimed, ensure_ascii=False))
            raise SystemExit(0)
    raise SystemExit(1)
