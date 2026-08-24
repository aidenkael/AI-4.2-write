# -*- coding: utf-8 -*-
"""Qoder CN adapter. Discovery only invokes local CLI inspection commands."""
from __future__ import annotations

import json
import os
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


def _discover_desktop() -> dict[str, Any]:
    override = os.environ.get("QODER_CN_DESKTOP_PATH")
    candidates = [Path(override)] if override else []
    if os.name == "nt" and os.environ.get("ProgramFiles"): candidates.append(Path(os.environ["ProgramFiles"]) / "Qoder" / "Qoder.exe")
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


def _parse_models(output: str) -> list[dict[str, str]]:
    try:
        raw = json.loads(output); rows = raw.get("models", raw) if isinstance(raw, dict) else raw
        if isinstance(rows, list):
            parsed = [{"id": str(item.get("id") or item.get("name")).strip(), "display_name": str(item.get("name") or item.get("id")).strip()} if isinstance(item, dict) else {"id": str(item).strip(), "display_name": str(item).strip()} for item in rows]
            return [item for item in parsed if item["id"]]
    except ValueError: pass
    rows = [line.strip() for line in output.splitlines() if line.strip()]
    if rows and rows[0].upper() in {"MODEL", "MODELS"}: rows = rows[1:]
    return [{"id": row, "display_name": row} for row in rows]


def _command_paths() -> list[Path]:
    return [Path.home() / ".qoder-cn" / "commands" / "gowrite.md", Path.home() / ".lingma" / "commands" / "gowrite.md"]


def command_definition() -> str:
    return "---\ndescription: Execute the active Go Write request and write its response\n---\nRead `06_工作区/应用开发/.qoder_bridge/active.json`, then read the referenced request. Execute only its `task`. Write one UTF-8 JSON response to the request's `response_path` with schema `gowrite_response/v1`, the same `request_id`, status `completed` or `failed`, and either `output` or `error`. Do not invent or alter Go Write business rules; the request task is authoritative.\n"


def command_ready() -> bool:
    definition = command_definition()
    return any(path.is_file() and path.read_text(encoding="utf-8", errors="replace") == definition for path in _command_paths())


def install_command() -> dict[str, Any]:
    installed, errors = [], []
    for path in _command_paths():
        try:
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(command_definition(), encoding="utf-8"); installed.append(str(path))
        except OSError as exc: errors.append(f"{path}: {exc}")
    return {"installed_paths": installed, "command_ready": command_ready(), "errors": errors}


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
            else: models = _parse_models(listed.stdout); auth_status = "authenticated" if models else "unknown"
        except Exception as exc: errors.append(str(exc))
        profile = {"id": "qoder_cn", "display_name": "Qoder CN", "type": "agent_managed", "available": bool(cli_path and models), "model_selection": "selectable", "models": [{**model, "selectable": True} for model in models], "reasoning_effort_options": ["none", "low", "medium", "high", "xhigh", "max"], "error": None if cli_path and models else "Qoder CN 模型目录当前不可用"}
        ready = command_ready()
        return {"agent_id": cls.name, "display_name": "Qoder CN", "installed": bool(desktop["installed"] or cli_path), "available": bool(cli_path and models), "version": " / ".join(value for value in (desktop["version"], cli_version) if value) or None, "errors": errors, "desktop": desktop, "cli": {"detected": bool(cli_path), "usable": bool(cli_path), "status": "usable" if cli_path else "not_detected", "kind": "qoder_cn", "path": cli_path, "resolved_command": [cli_path] if cli_path else [], "version": cli_version}, "interactive": {"available": bool(desktop["installed"]), "bridge_ready": bool(desktop["installed"] and ready), "command_name": "/gowrite", "command_ready": ready, "relevant_status": {"cli_command": str(_command_paths()[0]), "ide_command": str(_command_paths()[1])}, "repair_hint": None if ready else "未安装 Go Write 的 /gowrite 命令，可使用“安装/修复命令”。"}, "direct": {"available": bool(cli_path and models), "auth_status": auth_status, "execution_profiles": [profile], "capabilities": cls(cli_path=cli_path).capabilities() if cli_path else {}}}

    def __init__(self, cli_path: Optional[str] = None, launch: Optional[list[str]] = None, timeout: Optional[float] = None) -> None:
        self._launch = launch if launch is not None else [cli_path or _default_cli()]; self._timeout = timeout; self._proc: Optional[subprocess.Popen[str]] = None; self._lock = threading.Lock(); self._cancelled = threading.Event()

    def capabilities(self) -> dict[str, Any]:
        return {"run": True, "cwd": True, "final_output": True, "cancel": True, "stream": False, "resume": False, "session": False, "model_selection": "cli_flag", "reasoning_effort": True, "byok": False}

    def run(self, request: AgentRequest) -> AgentResult:
        self._cancelled.clear(); cmd = self._launch + ["-p", "-o", "json"]
        if request.cwd: cmd += ["--cwd", request.cwd]
        if request.model: cmd += ["--model", request.model]
        if request.reasoning_effort: cmd += ["--reasoning-effort", request.reasoning_effort]
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
