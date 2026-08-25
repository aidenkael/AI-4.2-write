# -*- coding: utf-8 -*-
"""Qoder CN adapter. Discovery only invokes local CLI inspection commands."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Optional

from agents.base import AgentAdapter, AgentRequest, AgentResult

_PERMISSION_MODE = "dont_ask"
_REQUIRED_FLAGS = ("--print", "--list-models", "--model", "--cwd", "--output-format")


def _first_line(result: subprocess.CompletedProcess[str]) -> Optional[str]:
    return next((line.strip() for line in result.stdout.splitlines() if line.strip()), None) if not result.returncode else None


def _qoder_cn_candidates() -> list[str]:
    candidates = [value for value in [os.environ.get("QODER_CN_CLI_PATH"), shutil.which("qoderclicn")] if value]
    installed = Path.home() / ".qoder-cn" / "bin" / "qoderclicn" / "qoderclicn.exe"
    if installed.is_file():
        candidates.append(str(installed))
    return candidates


def _default_cli() -> str:
    """Locate and verify Qoder CN; never fall back to qoder/qodercli."""
    errors, seen = [], set()
    for raw in _qoder_cn_candidates():
        path = Path(raw); key = os.path.normcase(os.path.abspath(str(path)))
        if key in seen: continue
        seen.add(key)
        if not path.is_file(): errors.append(f"{path.name} 不存在"); continue
        try:
            result = subprocess.run([str(path), "--help"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=12)
            help_text = f"{result.stdout}\n{result.stderr}"
            if result.returncode == 0 and all(flag in help_text for flag in _REQUIRED_FLAGS): return str(path)
            errors.append(f"{path.name} 不是可用的 Qoder CN CLI")
        except Exception as exc: errors.append(f"{path.name}: {exc}")
    detail = "；".join(errors[-3:])
    raise RuntimeError(f"找不到可用的 Qoder CN CLI{f'（{detail}）' if detail else ''}")


def _desktop_candidates() -> list[Path]:
    """Installed Qoder Desktop/IDE executables, derived from the current install.

    The upgraded CN IDE ships as ``Qoder CN IDE.exe`` / ``QoderCN.exe`` under
    ``Program Files``; the older international build used ``Qoder/Qoder.exe``.
    Keep an env override first so a custom location always wins.
    """
    override = os.environ.get("QODER_CN_DESKTOP_PATH")
    candidates: list[Path] = [Path(override)] if override else []
    if os.name == "nt" and os.environ.get("ProgramFiles"):
        candidates.append(Path(os.environ["ProgramFiles"]) / "Qoder CN IDE" / "Qoder CN IDE.exe")
        candidates.append(Path(os.environ["ProgramFiles"]) / "QoderCN" / "QoderCN.exe")
        candidates.append(Path(os.environ["ProgramFiles"]) / "Qoder" / "Qoder.exe")
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        candidates.append(Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Qoder CN IDE" / "Qoder CN IDE.exe")
    return candidates


def _discover_desktop() -> dict[str, Any]:
    candidates = _desktop_candidates()
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if not path: return {"installed": False, "status": "not_detected", "path": None, "launcher_path": None, "version": None, "error": None}
    try:
        # Qoder Desktop is a GUI executable; invoking it with --version can
        # launch/hang the UI. Read Windows file metadata instead.
        safe_path = str(path).replace("'", "''")
        probe = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", f"[System.Diagnostics.FileVersionInfo]::GetVersionInfo('{safe_path}').ProductVersion"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=12)
        version = _first_line(probe)
        return {"installed": True, "status": "installed" if version else "installed_version_unknown", "path": str(path), "launcher_path": str(path), "version": version, "error": None}
    except Exception as exc: return {"installed": True, "status": "installed_version_unknown", "path": str(path), "launcher_path": str(path), "version": None, "error": f"Desktop 版本检测失败：{exc}"}


# Qoder CN CLI --model contract (v1.1.29 --help): "Default and New Models use
# model name; Custom uses modelID".  Custom routes are listed with an explicit
# `` (Provider) (provider/model)`` route suffix; the trailing ``provider/model``
# token is the modelID the CLI accepts for that custom route.
_CUSTOM_ROUTE_RE = re.compile(r"^(?P<name>.+?)\s+\((?P<provider>[^()]+)\)\s+\((?P<route>[^()/]+/[^()/]+)\)$")


def _parse_models(output: str) -> list[dict[str, str]]:
    """Parse only the catalog emitted by this CLI executable.

    Returns entries with ``id`` (exact CLI identifier: model name for native,
    ``provider/model`` modelID for custom routes), ``display_name``, and
    ``kind`` (``native`` / ``custom``).  The CLI emits one flat catalog with no
    explicit classification; the only structural signal for a custom route is
    the trailing ``(provider/model)`` token that the CLI itself documents as
    the custom modelID.
    """
    try:
        raw = json.loads(output)
        rows = raw.get("models", raw) if isinstance(raw, dict) else raw
        if isinstance(rows, list):
            parsed: list[dict[str, str]] = []
            for item in rows:
                if not isinstance(item, dict):
                    continue
                model_id = str(item.get("id") or item.get("name") or "").strip()
                if not model_id:
                    continue
                display = str(item.get("name") or item.get("id") or model_id).strip()
                route = str(item.get("modelID") or item.get("route") or "").strip()
                if route:
                    parsed.append({"id": route, "display_name": display, "kind": "custom"})
                else:
                    parsed.append({"id": model_id, "display_name": display, "kind": "native"})
            return [entry for entry in parsed if entry["id"]]
    except ValueError:
        pass
    rows = [line.strip() for line in output.splitlines()]
    heading = next((index for index, row in enumerate(rows) if row.upper() in {"MODEL", "MODELS"}), None)
    if heading is None:
        return []
    rows = [row for row in rows[heading + 1:] if row]
    parsed = []
    for row in rows:
        custom_match = _CUSTOM_ROUTE_RE.match(row)
        if custom_match:
            parsed.append({
                "id": custom_match.group("route"),
                "display_name": f"{custom_match.group('name')}（{custom_match.group('provider')}）",
                "kind": "custom",
            })
        else:
            parsed.append({"id": row, "display_name": row, "kind": "native"})
    # 去重：同一模型 id 只保留一次（不发明 CLI 未区分的重复路由别名）
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for entry in parsed:
        key = entry["id"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(entry)
    return unique


_QODER_DESKTOP_DATA_DIRS = (".qoder", ".qoder-cn")
_QODER_COMMAND_NAME = "gowrite.md"


def _command_paths() -> list[Path]:
    """Supported command locations, derived from the installed CN IDE contract.

    The installed Qoder CN IDE (v1.1.29) recognises both ``.qoder`` and
    ``.qoder-cn`` as user data roots (its bundle lists both in the accepted
    data-root set).  User slash commands are markdown files under
    ``<root>/commands/<name>.md``; install/readiness covers every supported
    root so the bridge is detected regardless of which app instance is active.
    """
    return [
        Path.home() / data_dir / "commands" / _QODER_COMMAND_NAME
        for data_dir in _QODER_DESKTOP_DATA_DIRS
    ]


def command_definition() -> str:
    return "---\ndescription: Execute the active Go Write request and write its response\n---\nRead `06_工作区/应用开发/.qoder_bridge/active.json`, then read the referenced request. Execute only its `task`. Write one UTF-8 JSON response to the request's `response_path` with schema `gowrite_response/v1`, the same `request_id`, status `completed` or `failed`, and either `output` or `error`. Do not invent or alter Go Write business rules; the request task is authoritative.\n"


def command_locations() -> list[dict[str, Any]]:
    """Per-location command readiness facts (real path + real content state)."""
    definition = command_definition()
    locations = []
    for path in _command_paths():
        exists = path.is_file()
        matches = False
        if exists:
            try:
                matches = path.read_text(encoding="utf-8") == definition
            except (OSError, UnicodeError):
                matches = False
        locations.append({
            "path": str(path),
            "exists": exists,
            "matches": matches,
            "ready": exists and matches,
        })
    return locations


def command_ready() -> bool:
    """Ready when the exact definition exists at any supported location."""
    return any(location["ready"] for location in command_locations())


def install_command() -> dict[str, Any]:
    paths = _command_paths()
    errors: list[str] = []
    installed_paths: list[str] = []
    for path in paths:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(command_definition(), encoding="utf-8", newline="\n")
            installed_paths.append(str(path))
        except (OSError, UnicodeError) as exc:
            errors.append(f"{path}: 写入 Qoder Desktop 命令失败：{exc}")

    ready = command_ready()
    if not ready and not errors:
        errors.append("命令已写入，但任何受支持的 Qoder 命令位置都不符合 /gowrite 命令格式")
    return {
        "installed_paths": installed_paths,
        "command_ready": ready,
        "status": "installed" if ready else "error",
        "restart_required": False,
        "errors": errors,
    }


class QoderAdapter(AgentAdapter):
    name = "qoder"

    @classmethod
    def discover(cls) -> dict[str, Any]:
        errors: list[str] = []; desktop = _discover_desktop(); cli_path = None; cli_version = None; models: list[dict[str, str]] = []; auth_status = "not_detected"
        try:
            cli_path = _default_cli()
            cli_version = _first_line(subprocess.run([cli_path, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=12))
            listed = subprocess.run([cli_path, "--list-models"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
            if listed.returncode: auth_status = "not_authenticated"; errors.append(listed.stderr.strip() or "Qoder CN CLI 未能读取模型目录")
            else:
                models = _parse_models(listed.stdout)
                if models:
                    auth_status = "authenticated"
                else:
                    auth_status = "unknown"
                    errors.append("Qoder CN CLI 未返回可识别的模型目录")
        except Exception as exc: errors.append(str(exc))
        ready = command_ready()
        locations = command_locations()
        native_models = [{"id": m["id"], "display_name": m["display_name"], "selectable": True, "source": "native"} for m in models if m.get("kind") != "custom"]
        custom_models = [{"id": m["id"], "display_name": m["display_name"], "selectable": True, "source": "custom"} for m in models if m.get("kind") == "custom"]
        # This installed CLI exposes custom routes in the same --list-models
        # catalog; the trailing ``(provider/model)`` token is the custom modelID.
        # Each displayed id is the exact identifier the CLI accepts via --model.
        return {
            "agent_id": cls.name,
            "display_name": "Qoder CN",
            "installed": bool(desktop["installed"] or cli_path),
            "available": bool(cli_path and models),
            "version": " / ".join(value for value in (desktop["version"], cli_version) if value) or None,
            "errors": errors,
            "desktop": desktop,
            "cli": {"detected": bool(cli_path), "usable": bool(cli_path), "status": "usable" if cli_path else "not_detected", "kind": "qoder_cn", "path": cli_path, "resolved_command": [cli_path] if cli_path else [], "version": cli_version},
            "interactive": {
                "available": bool(desktop["installed"]),
                "bridge_ready": bool(desktop["installed"] and ready),
                "command_name": "/gowrite",
                "command_ready": ready,
                "command_locations": locations,
                "relevant_status": {"qoder_desktop_command": "; ".join(loc["path"] for loc in locations)},
                "repair_hint": None if ready else "未安装 Go Write 的 /gowrite 命令（或已安装位置不符合格式），可使用“安装/修复命令”。",
            },
            "direct": {
                "available": bool(cli_path and models),
                "auth_status": auth_status,
                "model_selection": "selectable" if models else "none",
                "models": native_models,
                "custom_models": custom_models,
                "managed_model": None,
                "capabilities": cls(cli_path=cli_path).capabilities() if cli_path else {},
            },
        }

    def __init__(self, cli_path: Optional[str] = None, launch: Optional[list[str]] = None, timeout: Optional[float] = None) -> None:
        self._launch = launch if launch is not None else [cli_path or _default_cli()]; self._timeout = timeout; self._proc: Optional[subprocess.Popen[str]] = None; self._lock = threading.Lock(); self._cancelled = threading.Event()

    def capabilities(self) -> dict[str, Any]:
        return {"run": True, "cwd": True, "final_output": True, "cancel": True, "stream": False, "resume": False, "session": False, "model_selection": "cli_flag", "reasoning_effort": False, "byok": False}

    def run(self, request: AgentRequest) -> AgentResult:
        # CLI contract: native models use their model name; custom routes use
        # their modelID (the ``provider/model`` token from --list-models).
        self._cancelled.clear(); cmd = self._launch + ["-p", "-o", "json"]
        if request.cwd: cmd += ["--cwd", request.cwd]
        selected_model = request.custom_model or request.model
        if selected_model: cmd += ["--model", selected_model]
        cmd += ["--permission-mode", _PERMISSION_MODE, request.task]
        with self._lock:
            if self._proc is not None: return AgentResult(status="failed", error="adapter 已有任务在运行", agent=self.name)
            try: self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
            except Exception as exc: return AgentResult(status="failed", error=f"启动失败: {exc}", agent=self.name)
            proc = self._proc
        try: raw_output, error = proc.communicate(timeout=self._timeout)
        except subprocess.TimeoutExpired: proc.kill(); proc.communicate(); return AgentResult(status="failed", error=f"超时（{self._timeout} 秒）", agent=self.name)
        finally:
            with self._lock: self._proc = None
        output = self._extract_cli_result(raw_output)
        if self._cancelled.is_set(): return AgentResult(status="cancelled", output=output, agent=self.name, exit_code=proc.returncode)
        cli_error = self._extract_cli_error(raw_output)
        if proc.returncode or cli_error: return AgentResult(status="failed", output=output, error=cli_error or error.strip() or f"非 0 退出码 {proc.returncode}", agent=self.name, exit_code=proc.returncode)
        return AgentResult(status="completed", output=output, agent=self.name, exit_code=proc.returncode)

    def cancel(self) -> bool:
        with self._lock: proc = self._proc
        if proc is None or proc.poll() is not None: return False
        self._cancelled.set(); proc.terminate(); return True

    def list_qoder_models(self) -> list[str]:
        result = subprocess.run(self._launch + ["--list-models"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
        if result.returncode: raise RuntimeError(result.stderr.strip() or "qoderclicn --list-models 失败")
        return [model["id"] for model in _parse_models(result.stdout)]

    @staticmethod
    def _extract_cli_result(output: Optional[str]) -> str:
        if not output: return ""
        try:
            data = json.loads(output); return str(data.get("result", output)) if isinstance(data, dict) else output
        except ValueError: return output.strip()

    @staticmethod
    def _extract_cli_error(output: Optional[str]) -> Optional[str]:
        if not output: return None
        try:
            data = json.loads(output)
            if isinstance(data, dict) and data.get("is_error"):
                errors = data.get("errors") or data.get("error") or "Qoder CN 执行失败"; return "; ".join(errors) if isinstance(errors, list) else str(errors)
        except ValueError: pass
        return None
