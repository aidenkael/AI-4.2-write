# -*- coding: utf-8 -*-
"""Qoder 桌面端薄桥（Go Write 管长期记忆，Qoder 只执行当前任务）。

架构（已确认，不重新讨论）：
- Go Write 只负责：生成唯一 request_id → 保存当前完整 Agent task →
  指定结果写回位置 → 等待/检测结果 → 校验 request_id →
  把模型最终结果交回现有严格业务解析。
- Qoder 桌面端（作者常用会话，可随时丢弃）只负责执行 `/gowrite`：
  读 active.json → 读请求文件 → 按 task 执行 → 写 response 文件。

本模块是纯文件协议，不调用任何模型 API，不复制任何 StoryDesign / StoryPlan
/ StoryWrite 业务规则（真正的业务要求由 pending task 提供）。

文件布局（全部在 06_工作区/应用开发/.qoder_bridge/，Local Only，可删除）：
- active.json                    当前活跃请求指针（Qoder 从这里找任务）
- requests/<request_id>.json     待执行任务（Go Write 写，Qoder 读）
- responses/<request_id>.json    执行结果（Qoder 写，Go Write 读）

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
import uuid
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

# 默认任务超时：作者可能 Alt+Tab 后稍晚才执行 /gowrite，给 30 分钟
DEFAULT_TASK_TIMEOUT_SECONDS = 30 * 60

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
) -> str:
    """生成唯一 request_id，保存完整 Agent task，并成为当前活跃请求。

    返回 request_id。request 文件包含 response_path，Qoder 只按此路径写回。
    """
    request_id = uuid.uuid4().hex
    timeout = timeout_seconds or DEFAULT_TASK_TIMEOUT_SECONDS
    created = datetime.now(timezone.utc)
    expires = created + timedelta(seconds=timeout)

    request: dict[str, Any] = {
        "schema": REQUEST_SCHEMA,
        "request_id": request_id,
        "kind": kind,
        "created_at": created.isoformat(timespec="seconds"),
        "expires_at": expires.isoformat(timespec="seconds"),
        "state": "pending",  # pending | canceled | completed | failed
        "task": task,        # 完整 Agent task（业务规则全部在这里）
        "response_path": str(response_path(request_id)),
        "meta": meta or {},
    }

    requests_dir = _requests_dir()
    requests_dir.mkdir(parents=True, exist_ok=True)
    _responses_dir().mkdir(parents=True, exist_ok=True)
    (requests_dir / f"{request_id}.json").write_text(
        json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # 更新活跃请求指针（Qoder /gowrite 从这里找任务；最新请求优先）
    _active_path().write_text(
        json.dumps({"active_request_id": request_id}, ensure_ascii=False),
        encoding="utf-8",
    )
    return request_id


def get_active_request_id() -> Optional[str]:
    """当前活跃请求 id（Qoder /gowrite 入口）。"""
    path = _active_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    rid = data.get("active_request_id")
    return rid if isinstance(rid, str) and rid else None


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

def read_response(request_id: str) -> Optional[dict[str, Any]]:
    """读取 response 文件；不存在返回 None。

    严格验收：文件必须是合法 JSON，否则直接返回携带相同 request_id 的失败
    信封（由调用方转成普通可读错误；request_id 仍是原值，便于防串校验）。
    Go Write 绝不根据字符位置猜测或修改 Qoder 写回的原始 JSON —— 产生合法
    JSON 是 Qoder 的职责（/gowrite 必须用标准 JSON parser 自验证）。
    """
    path = response_path(request_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "schema": RESPONSE_SCHEMA,
            "request_id": request_id,
            "status": "failed",
            "result": None,
            "output": None,
            "error": "结果文件不是合法 JSON，Go Write 已丢弃。",
        }
    return data


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
    request_path(request_id).write_text(
        json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    try:
        response_path(request_id).unlink(missing_ok=True)
    except OSError:
        pass
    return True


def clear_active_if(request_id: str) -> None:
    """若 active 指针仍指向该请求则清掉（取消/终态时调用）。"""
    active = get_active_request_id()
    if active == request_id:
        try:
            _active_path().unlink(missing_ok=True)
        except OSError:
            pass


def cleanup_request(request_id: str) -> None:
    """终态清理：删除请求/响应文件，并清掉可能指向本请求的 active 指针。"""
    try:
        request_path(request_id).unlink(missing_ok=True)
        response_path(request_id).unlink(missing_ok=True)
    except OSError:
        pass
    clear_active_if(request_id)


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
    for d in (_requests_dir(), _responses_dir()):
        shutil.rmtree(d, ignore_errors=True)
    try:
        _active_path().unlink(missing_ok=True)
    except OSError:
        pass
