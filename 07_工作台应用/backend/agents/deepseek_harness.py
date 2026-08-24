# -*- coding: utf-8 -*-
"""DeepSeek Harness headless Adapter（薄胶水）。

直接复用本机已安装 DeepSeek Harness 的原始运行方式（已实测可用）：

    node <dsh>/lib/bin.js --profile headless "<task>"

职责边界（只做薄胶水，不扩建平台）：
- 只负责：subprocess 启动、cwd 传入、任务传入、stdout 作为最终结果、
  stderr / 非 0 退出码 → failed、可终止当前子进程 → cancelled。
- 不复制 Harness 的 Agent loop / 工具 / 权限 / 模型 / Skill / session 等内部能力；
- 不自行实现它当前没有的 stream / resume / model CLI 功能（能力表如实声明）。
- 不修改 DeepSeek Harness；不把 E:\\DeepSeek Harness 业务逻辑硬编码到
  Author Operations。启动位置作为配置传入（launch 参数 / 环境变量 DSH_BIN /
  PATH 上的 dsh / 本机已验证的默认安装位），后续由设置页正式配置。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from agents.base import AgentAdapter, AgentRequest, AgentResult

# 本机已验证可用的默认安装位（仅作回退默认；优先：launch 参数 → DSH_BIN → PATH dsh）
_LOCAL_DSH_BIN = Path(r"E:\DeepSeek Harness\node_modules\@deepseek-ai\dsh\lib\bin.js")


def _default_launch() -> list[str]:
    env_bin = os.environ.get("DSH_BIN")
    if env_bin:
        p = Path(env_bin)
        if p.exists():
            return ["node", str(p)]
        raise RuntimeError(f"环境变量 DSH_BIN 指向不存在的文件: {env_bin}")
    dsh = shutil.which("dsh")
    if dsh:
        return [dsh]
    if _LOCAL_DSH_BIN.exists():
        return ["node", str(_LOCAL_DSH_BIN)]
    raise RuntimeError(
        "找不到 DeepSeek Harness 启动入口（可用 launch 参数或环境变量 DSH_BIN 指定）"
    )


class DeepSeekHarnessAdapter(AgentAdapter):
    """DeepSeek Harness headless 子进程 Adapter。"""

    name = "deepseek_harness"

    @classmethod
    def discover(cls) -> dict:
        """发现本机 Harness profiles、已配置模型与 web 状态，不执行模型。"""
        errors: list[str] = []
        try:
            launch = _default_launch()
        except Exception as exc:  # noqa: BLE001
            return {
                "agent_id": cls.name,
                "display_name": "DeepSeek Harness",
                "installed": False,
                "available": False,
                "version": None,
                "errors": [str(exc)],
                "interactive": {
                    "available": False, "bridge_ready": False,
                    "command_name": "/gowrite", "command_ready": False,
                },
                "direct": {
                    "available": False, "auth_status": "not_detected",
                    "execution_profiles": [], "capabilities": {},
                },
            }

        version: Optional[str] = None
        try:
            probe = subprocess.run(
                launch + ["--version"], capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=12,
            )
            version = next((line.strip() for line in probe.stdout.splitlines() if line.strip()), None)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Harness 版本检测失败：{exc}")

        dsh_home = Path(os.environ.get("DSH_HOME") or (Path.home() / ".dsh"))
        credentials_path = dsh_home / ".credentials.yaml"
        auth_status = "configured" if credentials_path.is_file() and credentials_path.stat().st_size > 0 else "not_detected"

        def dump_profile(profile: str) -> Optional[str]:
            try:
                result = subprocess.run(
                    launch + ["--profile", profile, "--dump-config"],
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=20,
                )
                if result.returncode != 0:
                    errors.append(result.stderr.strip() or f"Harness {profile} profile 读取失败")
                    return None
                return result.stdout
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Harness {profile} profile 读取失败：{exc}")
                return None

        headless_dump = dump_profile("headless")
        provider: Optional[str] = None
        model: Optional[str] = None
        if headless_dump:
            block = re.search(
                r"(?ms)^- id: agent-default-model\s+.*?(?=^- id:|\Z)",
                headless_dump,
            )
            if block:
                provider_match = re.search(r"(?m)^\s+provider:\s*([^\r\n#]+)", block.group(0))
                model_match = re.search(r"(?m)^\s+model:\s*([^\r\n#]+)", block.group(0))
                provider = provider_match.group(1).strip(" '\"") if provider_match else None
                model = model_match.group(1).strip(" '\"") if model_match else None

        profiles: list[dict] = []
        headless_available = bool(headless_dump and provider and model)
        if headless_dump:
            profiles.append({
                "id": "headless",
                "display_name": "Harness Headless",
                "type": "harness_profile",
                "available": headless_available,
                "model_selection": "managed",
                "provider_id": provider,
                "models": ([{
                    "id": model,
                    "display_name": model,
                    "selectable": False,
                    "selected": True,
                }] if model else []),
                "error": None if headless_available else "未检测到 profile 的当前 provider/model",
            })

        web_dump = dump_profile("web")
        command_ready = bool(web_dump and re.search(r"(?im)^\s*(?:-\s*)?(?:id|name):\s*[^\r\n]*gowrite", web_dump))
        web_url = os.environ.get("DSH_WEB_URL", "http://127.0.0.1:3080")
        parsed_url = urllib.parse.urlsplit(web_url)
        safe_host = parsed_url.hostname or "local"
        if parsed_url.port:
            safe_host = f"{safe_host}:{parsed_url.port}"
        safe_web_url = urllib.parse.urlunsplit((parsed_url.scheme or "http", safe_host, parsed_url.path, "", ""))
        web_running = False
        try:
            with urllib.request.urlopen(web_url, timeout=2) as response:  # noqa: S310 — localhost/default 可覆盖
                web_running = 200 <= response.status < 400
        except Exception:
            web_running = False
        web_profile_available = bool(web_dump)

        return {
            "agent_id": cls.name,
            "display_name": "DeepSeek Harness",
            "installed": True,
            "available": True,
            "version": version,
            "errors": errors,
            "interactive": {
                "available": web_profile_available,
                "bridge_ready": command_ready and web_running,
                "command_name": "/gowrite",
                "command_ready": command_ready,
                "relevant_status": {
                    "profile": "web",
                    "runtime": "running" if web_running else "stopped",
                    "url": safe_web_url,
                },
                "repair_hint": None if command_ready else "Harness 已提供命令运行时，但当前 profile 未配置 Go Write 的 /gowrite 插件。",
            },
            "direct": {
                "available": headless_available,
                "auth_status": auth_status,
                "execution_profiles": profiles,
                "capabilities": cls(launch=launch).capabilities(),
                "executable_path": " ".join(launch),
            },
        }

    def __init__(
        self,
        launch: Optional[list[str]] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """launch：可执行起点 argv（如 ["node", ".../bin.js"] 或 ["dsh"]）。"""
        self._launch = launch if launch is not None else _default_launch()
        self._timeout = timeout
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._cancelled = threading.Event()

    # ---------------- 能力声明（只按当前真实能力） ----------------

    def capabilities(self) -> dict:
        return {
            "run": True,
            "cwd": True,
            "final_output": True,
            "cancel": True,
            "stream": False,          # headless 仅最终消息，无流式
            "resume": False,          # headless 不支持恢复会话
            "session": False,         # headless 不输出 session_id
            "model_selection": "profile_managed",  # 模型由 Harness profile 配置决定
        }

    # ---------------- 执行 ----------------

    def run(self, request: AgentRequest) -> AgentResult:
        self._cancelled.clear()
        cmd = self._launch + ["--profile", "headless", request.task]
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
                status="cancelled", output=out.strip(), agent=self.name,
                exit_code=proc.returncode,
            )
        if proc.returncode != 0:
            return AgentResult(
                status="failed", output=out.strip(),
                error=(err.strip() or f"非 0 退出码 {proc.returncode}"),
                agent=self.name, exit_code=proc.returncode,
            )
        return AgentResult(status="completed", output=out.strip(), agent=self.name,
                           exit_code=proc.returncode)

    def cancel(self) -> bool:
        """终止当前运行中的子进程；成功终止返回 True，结果转 cancelled。"""
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
