# -*- coding: utf-8 -*-
"""Qoder Adapter（薄胶水，双原生路径）。

QoderAdapter 内部支持两种原生路径，业务层仍只看到同一个 QoderAdapter：

1. Qoder 自带模型（Token Plan）：直接调用原生 CLI
       qodercli -p [--model X] [--reasoning-effort L] <task>
   （-p = 非交互 print 模式；headless 默认 --permission-mode dont_ask，
   拒绝未批准工具而不挂起等待交互。）

2. 用户自己的 Token Plan / API 模型（BYOK）：通过官方 qoder-agent-sdk
   的 query() + resolve_model 回调，在运行时传入 provider / model /
   api_key / 必要官方模型参数。SDK 复用 qodercli 本地登录
   （qoder_agent_sdk.qodercli_auth()）。

职责边界（只做薄胶水，不扩建平台）：
- 只负责：调用原生 Qoder、cwd、task、model、reasoning effort（当前调用
  路径支持时）、最终输出、error、cancel、capabilities、BYOK 时调用官方 SDK。
- 不复制 Qoder 的 Agent loop / 文件工具 / Shell 工具 / 权限体系 / session
  系统 / Qoder Skills / 模型目录 / provider 目录 —— 这些全部由 Qoder 提供。
- 不硬编码 Qoder 模型名单；模型 / provider 目录通过
  qodercli --list-models 与官方 SDK list_byok_providers() 动态读取。
- BYOK 的 provider / api_key 属于 Qoder 特有配置，由 QoderBYOKConfig
  构造参数负责，不进入统一 AgentRequest。

能力声明按当前配置返回实际 capabilities（CLI 与 SDK 两路径能力如实区分）。
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from agents.base import AgentAdapter, AgentRequest, AgentResult

# BYOK 配置中 style 缺省由 SDK 补 "openai"，url 缺省由 SDK / provider 决定
_DEFAULT_PERMISSION_MODE = "dontAsk"  # SDK 取值；CLI 路径翻译为 dont_ask


def _first_output_line(probe: subprocess.CompletedProcess[str]) -> Optional[str]:
    """取本机版本探针的第一行；失败时不把错误文本伪装成版本。"""
    if probe.returncode != 0:
        return None
    return next((line.strip() for line in probe.stdout.splitlines() if line.strip()), None)


def _read_wrapper(path: str) -> str:
    p = Path(path)
    if p.suffix.upper() not in (".CMD", ".BAT"):
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="ignore")[:5000]
    except OSError:
        return ""


def _is_qoder_dispatcher(path: str) -> bool:
    """判断公开 ``qoder`` 是否只是 Desktop/旧 CLI 的分发入口。"""
    p = Path(path)
    if p.stem.lower() != "qoder":
        return False
    wrapper = _read_wrapper(path)
    return any(marker in wrapper for marker in (
        "BRIDGE_DISPATCHER", "qoder-npm-dispatcher", "qoder-dispatcher.ps1",
    ))


def _legacy_cli_candidates() -> list[str]:
    """列出真正的旧版 qodercli 入口，不返回公开 qoder dispatcher。"""
    candidates: list[str] = []
    legacy_override = os.environ.get("QODERCLI_PATH")
    if legacy_override:
        candidates.append(legacy_override)
    found = shutil.which("qodercli")
    if found:
        candidates.append(found)
    user_cli = Path.home() / ".qoder" / "bin" / "qodercli" / "qodercli.exe"
    if user_cli.is_file():
        candidates.append(str(user_cli))
    return candidates


def _actual_cli_entry(candidate: str) -> str:
    """把公开 dispatcher 规范化为其实际 qodercli，避免混报 Desktop/CLI。"""
    if not _is_qoder_dispatcher(candidate):
        return candidate
    candidate_key = os.path.normcase(os.path.abspath(candidate))
    for legacy in _legacy_cli_candidates():
        if not Path(legacy).is_file():
            continue
        if os.path.normcase(os.path.abspath(legacy)) != candidate_key:
            return legacy
    return candidate


def _desktop_candidates() -> list[str]:
    """从 Desktop 安装位置发现 Qoder，不借用 qoder/qodercli 的 CLI 状态。"""
    candidates: list[str] = []
    explicit = os.environ.get("QODER_IDE_BIN")
    if explicit:
        candidates.append(explicit)
    if os.name == "nt":
        for env_name in ("ProgramFiles", "LOCALAPPDATA"):
            root = os.environ.get(env_name)
            if not root:
                continue
            base = Path(root)
            candidates.extend((
                str(base / "Qoder" / "Qoder.exe"),
                str(base / "Programs" / "Qoder" / "Qoder.exe"),
            ))
        public = shutil.which("qoder")
        if public:
            public_path = Path(public)
            if public_path.parent.name.lower() == "bin":
                candidates.append(str(public_path.parent.parent / "Qoder.exe"))
    return candidates


def _discover_desktop() -> dict[str, Any]:
    """返回独立 Desktop 证据；只执行本机 ``--version``，不触发模型。"""
    seen: set[str] = set()
    for raw in _desktop_candidates():
        candidate = Path(raw)
        key = os.path.normcase(os.path.abspath(str(candidate)))
        if key in seen:
            continue
        seen.add(key)
        if not candidate.is_file():
            continue

        desktop_path = candidate
        launcher_path: Optional[Path] = None
        if candidate.name.lower() == "qoder.exe":
            native = candidate.parent / "bin" / "code.cmd"
            launcher_path = native if native.is_file() else None
        elif candidate.parent.name.lower() == "bin":
            installed_exe = candidate.parent.parent / "Qoder.exe"
            if installed_exe.is_file():
                desktop_path = installed_exe
            native = candidate.parent / "code.cmd"
            launcher_path = native if native.is_file() else candidate
        else:
            launcher_path = candidate

        version: Optional[str] = None
        version_error: Optional[str] = None
        if launcher_path:
            try:
                probe = subprocess.run(
                    [str(launcher_path), "--version"], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=12,
                )
                version = _first_output_line(probe)
                if not version:
                    version_error = "Desktop 版本探针未返回可用版本"
            except Exception as exc:  # noqa: BLE001
                version_error = f"Desktop 版本检测失败：{exc}"
        return {
            "installed": True,
            "status": "installed" if version else "installed_version_unknown",
            "path": str(desktop_path),
            "launcher_path": str(launcher_path) if launcher_path else None,
            "version": version,
            "error": version_error,
        }
    return {
        "installed": False,
        "status": "not_detected",
        "path": None,
        "launcher_path": None,
        "version": None,
        "error": None,
    }


def _default_cli() -> str:
    """解析可执行的 Qoder Agent CLI。

    新版 Qoder CN 的公开 ``qoder`` 是统一 dispatcher，旧安装则可能只提供
    ``qodercli``。显式覆盖优先，其后逐一用本机 ``--help`` 验证 Agent CLI
    flags；不会仅凭文件名猜测入口。
    """
    candidates: list[str] = []
    for env_name in ("QODER_CLI_BIN", "QODERCLI_PATH"):
        value = os.environ.get(env_name)
        if value:
            p = Path(value)
            if not p.is_file():
                raise RuntimeError(f"环境变量 {env_name} 指向不存在的文件: {value}")
            candidates.append(str(p))
    for command in ("qoder", "qodercli"):
        found = shutil.which(command)
        if found:
            candidates.append(found)
    user_cli = Path.home() / ".qoder" / "bin" / "qodercli" / "qodercli.exe"
    if user_cli.is_file():
        candidates.append(str(user_cli))

    errors: list[str] = []
    seen: set[str] = set()
    for raw_candidate in candidates:
        candidate = _actual_cli_entry(raw_candidate)
        key = os.path.normcase(os.path.abspath(candidate))
        if key in seen:
            continue
        seen.add(key)
        try:
            cmd = _resolve_cmd(candidate)
            probe = subprocess.run(
                cmd + ["--help"], capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=12,
            )
            help_text = f"{probe.stdout}\n{probe.stderr}"
            if "--print" in help_text and "--list-models" in help_text:
                return candidate
            errors.append(f"{Path(candidate).name} 不是 Agent CLI")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{Path(candidate).name}: {exc}")
    detail = "；".join(errors[-3:])
    raise RuntimeError(f"找不到可用的 Qoder Agent CLI{f'（{detail}）' if detail else ''}")


def _find_legacy_cli() -> Optional[str]:
    """找到 dispatcher 最终调用的 qodercli，用于绕过 Windows CMD 编码层。"""
    for candidate in _legacy_cli_candidates():
        if Path(candidate).is_file():
            return candidate
    return None


def _resolve_cmd(cli_path: str) -> list[str]:
    """解析 CLI 入口为实际子进程命令。

    Windows 上 npm 安装的 qodercli 是 .CMD 包装器，CMD.exe 通过系统 ANSI
    代码页（如中文 Windows 的 CP936）处理命令行参数，导致 Python subprocess
    传递的 UTF-8 中文字符损坏。解决方法：检测 .CMD 包装器，直接调用
    Node.js + JS bundle，绕过 CMD.exe 的代码页转换。

    非 Windows 或无法解析时返回原始 [cli_path]。
    """
    if os.name != "nt":
        return [cli_path]
    p = Path(cli_path)
    if p.suffix.upper() not in (".CMD", ".BAT"):
        return [cli_path]
    wrapper = _read_wrapper(cli_path)
    # Qoder CN 的 qoder.cmd → ~/.qoder/entry dispatcher → qodercli。直接解析
    # 最终 CLI，保留原有绕过 CMD/CP936 的中文参数修复。
    if p.stem.lower() == "qoder" and (
        "BRIDGE_DISPATCHER" in wrapper or "qoder-npm-dispatcher" in wrapper
        or "qoder-dispatcher.ps1" in wrapper
    ):
        legacy = _find_legacy_cli()
        if legacy and os.path.normcase(os.path.abspath(legacy)) != os.path.normcase(os.path.abspath(cli_path)):
            return _resolve_cmd(legacy)
    npm_dir = p.parent
    # 定位 Node.js：优先 npm 目录下的 node.exe，其次系统 PATH
    node_exe = shutil.which("node")
    if not node_exe:
        return [cli_path]
    # 定位 JS bundle（npm 标准布局）
    bundle = npm_dir / "node_modules" / "@qoder-ai" / "qodercli" / "bundle" / "qodercli.js"
    if bundle.is_file():
        return [node_exe, str(bundle)]
    return [cli_path]


@dataclass
class QoderBYOKConfig:
    """Qoder 特有 BYOK 配置（只进 QoderAdapter，不进统一 AgentRequest）。

    provider / model / api_key 为运行时必需；url / style / reasoning_effort
    为可选的官方模型参数（对应 SDK CustomModel 与 resolve_model parameters）。
    """

    provider: str
    model: str
    api_key: str
    url: Optional[str] = None
    style: Optional[str] = None  # "openai" | "anthropic"；缺省由 SDK 补 "openai"
    reasoning_effort: Optional[str] = None  # 默认推理强度（request 可覆盖）


class QoderAdapter(AgentAdapter):
    """Qoder Adapter：CLI 自带模型路径 + SDK BYOK 路径。"""

    name = "qoder"

    @classmethod
    def discover(cls) -> dict[str, Any]:
        """发现 Qoder/Qoder CN 的交互与直接执行能力，不发送模型请求。"""
        errors: list[str] = []
        config_dir = Path.home() / ".qoder"

        desktop = _discover_desktop()
        desktop_installed = bool(desktop["installed"])
        if desktop.get("error"):
            errors.append(str(desktop["error"]))

        command_path = config_dir / "commands" / "gowrite.md"
        command_ready = False
        if command_path.is_file():
            try:
                command_text = command_path.read_text(encoding="utf-8", errors="replace")
                command_ready = ".qoder_bridge" in command_text and "request_id" in command_text
            except OSError:
                command_ready = False

        cli_path: Optional[str] = None
        cli_version: Optional[str] = None
        cli_usable = False
        cli_kind = "not_detected"
        launch: list[str] = []
        auth_status = "not_detected"
        allow_byok = False
        profiles: list[dict[str, Any]] = []
        try:
            cli_path = _default_cli()
            launch = _resolve_cmd(cli_path)
            cli_kind = "legacy_qodercli" if any(
                "qodercli" in str(part).lower() for part in (cli_path, *launch)
            ) else "current_cli"
            help_probe = subprocess.run(
                launch + ["--help"], capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=12,
            )
            help_text = f"{help_probe.stdout}\n{help_probe.stderr}"
            cli_usable = (
                "--print" in help_text
                and "--list-models" in help_text
            )
            if not cli_usable:
                raise RuntimeError("检测到 CLI 文件，但未通过直接执行能力验证")
            version_probe = subprocess.run(
                launch + ["--version"], capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=12,
            )
            cli_version = _first_output_line(version_probe)

            logged_in: Optional[bool] = None
            status_probe = subprocess.run(
                launch + ["status", "-o", "json"], capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=12,
            )
            if status_probe.returncode == 0:
                try:
                    status = json.loads(status_probe.stdout)
                    logged_in = bool(status.get("logged_in"))
                    allow_byok = bool(status.get("allow_byok"))
                    cli_version = str(status.get("version") or cli_version or "") or None
                    auth_status = "authenticated" if logged_in else "not_authenticated"
                except (ValueError, TypeError):
                    auth_status = "unknown"
            else:
                auth_status = "unknown"

            native_models: list[str] = []
            native_error: Optional[str] = None
            if logged_in:
                try:
                    native_models = cls(cli_path=cli_path).list_qoder_models()
                except Exception as exc:  # noqa: BLE001
                    native_error = str(exc)
            elif logged_in is False:
                native_error = "Qoder CLI 当前未登录"
            profiles.append({
                "id": "native",
                "display_name": "Qoder 账户",
                "type": "native_account",
                "available": bool(logged_in and native_models),
                "model_selection": "selectable",
                "models": [
                    {"id": model, "display_name": model, "selectable": True}
                    for model in native_models
                ],
                "reasoning_effort_options": ["none", "low", "medium", "high", "xhigh", "max"],
                "error": native_error,
            })

            if allow_byok and logged_in:
                try:
                    providers = cls(cli_path=cli_path).list_byok_providers() or []
                    for provider in providers:
                        provider_id = str(provider.get("key") or "").strip()
                        for provider_type in provider.get("types") or []:
                            type_id = str(provider_type.get("key") or "").strip()
                            models = provider_type.get("models") or []
                            if not provider_id or not type_id:
                                continue
                            profiles.append({
                                "id": f"byok:{provider_id}:{type_id}",
                                "display_name": str(provider_type.get("display_name") or provider.get("display_name") or provider_id),
                                "type": "byok",
                                "provider_id": provider_id,
                                "available": bool(models),
                                "model_selection": "selectable",
                                "models": [
                                    {
                                        "id": str(model.get("key") or ""),
                                        "display_name": str(model.get("display_name") or model.get("key") or ""),
                                        "selectable": True,
                                        "reasoning_efforts": model.get("efforts") or [],
                                    }
                                    for model in models if model.get("key")
                                ],
                                "reasoning_effort_options": ["none", "low", "medium", "high", "xhigh", "max"],
                            })
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"Qoder BYOK 目录读取失败：{exc}")
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))

        direct_available = any(profile.get("available") for profile in profiles)
        installed = desktop_installed or cli_path is not None
        components = []
        if desktop.get("version"):
            components.append(f"Desktop {desktop['version']}")
        if cli_version:
            legacy_suffix = "（旧版兼容）" if cli_kind == "legacy_qodercli" else ""
            components.append(f"CLI {cli_version}{legacy_suffix}")
        environment_version = " / ".join(components) or None
        bridge_ready = desktop_installed and command_ready
        if not desktop_installed:
            interactive_hint = "未检测到 Qoder Desktop；交互桥不可用。"
        elif not command_ready:
            interactive_hint = "已检测到 Qoder Desktop，但未检测到适用于当前 Desktop 的 /gowrite 命令文件。"
        else:
            interactive_hint = None
        return {
            "agent_id": cls.name,
            "display_name": "Qoder / Qoder CN",
            "installed": installed,
            "available": bridge_ready or direct_available,
            "version": environment_version,
            "errors": errors,
            "desktop": desktop,
            "cli": {
                "detected": cli_path is not None,
                "usable": cli_usable,
                "status": (
                    auth_status if cli_usable
                    else "unusable" if cli_path
                    else "not_detected"
                ),
                "kind": cli_kind,
                "path": cli_path,
                "resolved_command": launch if cli_path else [],
                "version": cli_version,
            },
            "interactive": {
                "available": desktop_installed,
                "bridge_ready": bridge_ready,
                "command_name": "/gowrite",
                "command_ready": command_ready,
                "command_path": str(command_path),
                "relevant_status": {
                    "desktop_path": desktop.get("path"),
                    "desktop_version": desktop.get("version"),
                    "desktop_status": desktop.get("status"),
                    "config_dir": str(config_dir) if config_dir.is_dir() else None,
                },
                "repair_hint": interactive_hint,
            },
            "direct": {
                "available": direct_available,
                "auth_status": auth_status,
                "execution_profiles": profiles,
                "capabilities": {
                    "run": cli_usable,
                    "cancel": True,
                    "model_selection": "profile",
                    "reasoning_effort": True,
                    "byok": allow_byok,
                },
                "executable_path": cli_path,
                "resolved_command": launch if cli_path else [],
                "cli_version": cli_version,
                "cli_kind": cli_kind,
            },
        }

    def __init__(
        self,
        cli_path: Optional[str] = None,
        launch: Optional[list[str]] = None,
        byok: Optional[QoderBYOKConfig] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """byok 为 None → CLI 自带模型路径；否则 → SDK BYOK 路径。

        launch：可执行起点 argv（如 ["qodercli"] 或测试注入的假入口）；
        缺省为 [cli_path]，cli_path 缺省按 QODERCLI_PATH → PATH 解析。
        """
        self._byok = byok
        self._timeout = timeout
        if launch is not None:
            self._launch = list(launch)
            self._cli_path: Optional[str] = None  # 仅 list_qoder_models 需要真实 CLI
        else:
            self._cli_path = cli_path if cli_path is not None else _default_cli()
            self._launch = [self._cli_path]
        # 实际子进程命令（Windows 上绕过 CMD 包装器直接调 Node.js，避免中文编码损坏）
        if self._cli_path:
            self._subprocess_cmd = _resolve_cmd(self._cli_path)
        else:
            self._subprocess_cmd = self._launch
        # CLI 路径的进程句柄 / 取消状态
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._cancelled = threading.Event()

    # ---------------- 能力声明（按当前配置返回实际能力） ----------------

    def capabilities(self) -> dict[str, Any]:
        if self._byok is not None:
            # SDK query() 是单向一次性调用，官方文档明确无 interrupt；
            # 不为此自造跨线程中断，如实声明 cancel=False。
            return {
                "run": True,
                "cwd": True,
                "final_output": True,
                "cancel": False,
                "stream": False,
                "resume": False,
                "session": False,
                "model_selection": "byok_resolve_model",
                "reasoning_effort": True,   # 经 resolve_model parameters.reasoningEffort
                "byok": True,
            }
        return {
            "run": True,
            "cwd": True,
            "final_output": True,
            "cancel": True,   # CLI 子进程可直接 terminate
            "stream": False,
            "resume": False,
            "session": False,
            "model_selection": "cli_flag",  # qodercli -m <model>
            "reasoning_effort": True,       # qodercli --reasoning-effort <level>
            "byok": False,
        }

    # ---------------- 执行 ----------------

    def run(self, request: AgentRequest) -> AgentResult:
        if self._byok is not None:
            return self._run_byok(request)
        return self._run_cli(request)

    def cancel(self) -> bool:
        """终止当前运行中的 CLI 子进程；BYOK 路径（SDK query 无 interrupt）不支持。"""
        with self._lock:
            proc = self._proc
        if proc is None or proc.poll() is not None:
            return False
        self._cancelled.set()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                return False
        return True

    # ---------------- CLI 路径（Qoder 自带模型） ----------------

    def _run_cli(self, request: AgentRequest) -> AgentResult:
        self._cancelled.clear()
        cmd = self._subprocess_cmd + ["-p", "--permission-mode", "dont_ask", "--output-format", "json"]
        if request.model:
            cmd += ["--model", request.model]
        if request.reasoning_effort:
            cmd += ["--reasoning-effort", request.reasoning_effort]
        cmd.append(request.task)

        with self._lock:
            if self._proc is not None:
                return AgentResult(status="failed", error="adapter 已有任务在运行", agent=self.name)
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=request.cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
            except Exception as exc:  # noqa: BLE001
                return AgentResult(status="failed", error=f"启动失败: {exc}", agent=self.name)
            self._proc = proc

        try:
            out, err = proc.communicate(timeout=self._timeout)
        except subprocess.TimeoutExpired:
            with self._lock:
                self._proc = None
            try:
                proc.kill()
                proc.communicate()
            except Exception:  # noqa: BLE001
                pass
            return AgentResult(status="failed", error=f"超时（{self._timeout} 秒）", agent=self.name)
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._proc = None
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
            return AgentResult(status="failed", error=str(exc), agent=self.name)
        finally:
            with self._lock:
                self._proc = None

        if self._cancelled.is_set():
            return AgentResult(
                status="cancelled", output=self._extract_cli_result(out), agent=self.name,
                exit_code=proc.returncode,
            )
        if proc.returncode != 0:
            return AgentResult(
                status="failed", output=self._extract_cli_result(out),
                error=(err.strip() or f"非 0 退出码 {proc.returncode}"),
                agent=self.name, exit_code=proc.returncode,
            )
        # CLI 退出码 0 但信封标记错误（如模型配额耗尽）：转 failed 而非 completed
        cli_error = self._extract_cli_error(out)
        if cli_error:
            return AgentResult(
                status="failed", output=self._extract_cli_result(out),
                error=cli_error, agent=self.name, exit_code=proc.returncode,
            )
        return AgentResult(status="completed", output=self._extract_cli_result(out), agent=self.name,
                           exit_code=proc.returncode)

    @staticmethod
    def _extract_cli_result(raw_output: str) -> str:
        """从 --output-format json 的 CLI 输出中提取 result 字段。

        CLI 返回 JSON 信封（含 type/result/duration_ms 等元数据），
        业务层只需要 result 字段的模型文本。如果解析失败，回退到原始文本。
        """
        text = (raw_output or "").strip()
        if not text:
            return text
        try:
            import json as _json
            data = _json.loads(text)
            if isinstance(data, dict) and "result" in data:
                return str(data["result"]).strip()
        except (ValueError, TypeError):
            pass
        return text

    @staticmethod
    def _extract_cli_error(raw_output: str) -> Optional[str]:
        """检查 CLI JSON 信封中是否包含错误信息。

        CLI 有时退出码 0 但信封标记 is_error=true（如模型配额耗尽），
        此时需要从 errors 字段提取可读错误信息。无错误时返回 None。
        """
        text = (raw_output or "").strip()
        if not text:
            return None
        try:
            import json as _json
            data = _json.loads(text)
            if isinstance(data, dict) and data.get("is_error"):
                errors = data.get("errors")
                if isinstance(errors, list) and errors:
                    return "; ".join(str(e) for e in errors)
                subtype = data.get("subtype", "")
                return f"CLI 返回错误（{subtype}）" if subtype else "CLI 返回未知错误"
        except (ValueError, TypeError):
            pass
        return None

    # ---------------- SDK BYOK 路径 ----------------

    def _make_resolver(
        self, model: str, reasoning_effort: Optional[str]
    ) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """构造官方 resolve_model 回调（ModelPolicyProvider）。

        回调返回 ModelPolicyResult：model 为 CustomModel 字典
        （provider / model / api_key / url / style），parameters 携带
        官方模型参数（reasoningEffort 等）。
        """

        def resolver(context: dict[str, Any]) -> dict[str, Any]:
            custom: dict[str, Any] = {
                "provider": self._byok.provider,  # type: ignore[union-attr]
                "model": model,
                "api_key": self._byok.api_key,  # type: ignore[union-attr]
            }
            if self._byok.url:  # type: ignore[union-attr]
                custom["url"] = self._byok.url
            if self._byok.style:  # type: ignore[union-attr]
                custom["style"] = self._byok.style
            result: dict[str, Any] = {"model": custom}
            if reasoning_effort:
                result["parameters"] = {"reasoningEffort": reasoning_effort}
            return result

        return resolver

    def _run_byok(self, request: AgentRequest) -> AgentResult:
        """BYOK：经官方 SDK query() 调用，resolve_model 提供运行时凭据。

        SDK 会自行拉起 qodercli 子进程；query() 为单向一次性调用，
        无 interrupt（capabilities.cancel=False 如实声明）。
        """
        byok = self._byok
        assert byok is not None
        model = request.model or byok.model
        effort = request.reasoning_effort or byok.reasoning_effort

        try:
            from qoder_agent_sdk import QoderAgentOptions, qodercli_auth, query
            from qoder_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock
        except Exception as exc:  # noqa: BLE001
            return AgentResult(status="failed", error=f"qoder-agent-sdk 不可用: {exc}", agent=self.name)

        async def _collect() -> AgentResult:
            options = QoderAgentOptions(
                cwd=request.cwd,
                auth=qodercli_auth(),  # 复用 qodercli 本地登录
                resolve_model=self._make_resolver(model, effort),
                permission_mode=_DEFAULT_PERMISSION_MODE,  # headless：拒绝未批准工具
            )
            text_parts: list[str] = []
            final_result: Optional[str] = None
            error_msg: Optional[str] = None
            try:
                async for msg in query(prompt=request.task, options=options):
                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if isinstance(block, TextBlock) and block.text:
                                text_parts.append(block.text)
                        if getattr(msg, "error", None):
                            error_msg = str(msg.error)
                    elif isinstance(msg, ResultMessage):
                        if msg.result:
                            final_result = msg.result
                        if msg.is_error:
                            error_msg = "; ".join(msg.errors or []) or "Qoder 返回错误"
            except Exception as exc:  # noqa: BLE001（SDK 内部错误 / 进程非 0 退出等）
                return AgentResult(
                    status="failed", output="\n".join(text_parts).strip(),
                    error=f"Qoder SDK 调用失败: {exc}", agent=self.name,
                )
            output = final_result or "\n".join(text_parts)
            if error_msg:
                return AgentResult(status="failed", output=output.strip(),
                                   error=error_msg, agent=self.name)
            return AgentResult(status="completed", output=output.strip(), agent=self.name)

        holder: dict[str, Any] = {}

        def _worker() -> None:
            try:
                coro = _collect()
                if self._timeout is not None:
                    coro = asyncio.wait_for(coro, timeout=self._timeout)
                holder["result"] = asyncio.run(coro)
            except Exception as exc:  # noqa: BLE001
                holder["result"] = AgentResult(
                    status="failed", error=f"Qoder SDK 调用失败: {exc}", agent=self.name,
                )

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join()
        return holder.get("result") or AgentResult(
            status="failed", error="Qoder SDK 调用无结果", agent=self.name,
        )

    # ---------------- 最薄查询能力（模型 / provider 目录，不硬编码） ----------------

    def list_qoder_models(self) -> list[str]:
        """Qoder 自带模型：读取 qodercli --list-models 当前真实输出。

        输出为简单表格（首行为表头 MODEL），逐行取模型名；
        禁止在 AI-write 中硬编码名单，Qoder 增删模型后本方法自然跟随。
        """
        cmd = self._subprocess_cmd + ["--list-models"]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=60,
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"qodercli --list-models 执行失败: {exc}") from exc
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or f"qodercli --list-models 退出码 {proc.returncode}")
        lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        if lines and lines[0].upper() == "MODEL":
            lines = lines[1:]
        return lines

    def list_byok_providers(self) -> Optional[list[dict[str, Any]]]:
        """BYOK provider / model 目录：通过官方 SDK 当前接口读取。

        返回 QoderSDKClient.list_byok_providers() 的原始结果
        （list[BYOKProviderInfo]），CLI 不支持时返回 None；模型目录
        由 Qoder 提供，AI-write 不复制也不硬编码。
        """
        try:
            from qoder_agent_sdk import QoderAgentOptions, QoderSDKClient, qodercli_auth
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"qoder-agent-sdk 不可用: {exc}") from exc

        holder: dict[str, Any] = {}

        async def _query() -> Optional[list[dict[str, Any]]]:
            async with QoderSDKClient(
                options=QoderAgentOptions(auth=qodercli_auth())
            ) as client:
                return await client.list_byok_providers()

        def _worker() -> None:
            try:
                holder["result"] = asyncio.run(_query())
            except Exception as exc:  # noqa: BLE001
                holder["error"] = exc

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join()
        if "error" in holder:
            raise RuntimeError(f"Qoder SDK 读取 BYOK 目录失败: {holder['error']}")
        return holder.get("result")
