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


def _default_cli() -> str:
    """解析 qodercli 可执行入口（QODERCLI_PATH → PATH 上的 qodercli）。"""
    env = os.environ.get("QODERCLI_PATH")
    if env:
        p = Path(env)
        if p.exists():
            return str(p)
        raise RuntimeError(f"环境变量 QODERCLI_PATH 指向不存在的文件: {env}")
    cli = shutil.which("qodercli")
    if cli:
        return cli
    raise RuntimeError("找不到 Qoder CLI（可用 launch 参数或环境变量 QODERCLI_PATH 指定）")


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
