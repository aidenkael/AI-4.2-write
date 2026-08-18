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
import shutil
import subprocess
import threading
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
