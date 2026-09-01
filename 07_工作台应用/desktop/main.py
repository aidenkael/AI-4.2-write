#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI-write 桌面壳（pywebview）——第一轮最小骨架。

职责：
- 启动 pywebview 窗口（Windows 使用现有 WebView2 Runtime）
- 加载 React (Vite) 页面：默认加载构建产物 dist/index.html；--dev 加载 Vite dev server
- 注册唯一 Bridge 入口 AppApi（backend/bridge/app_api.py）

不实现：系统托盘、自动更新、安装程序、任何 Skill 接入。
"""
from __future__ import annotations

import argparse
from importlib.metadata import version
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # 07_工作台应用/
BACKEND_DIR = ROOT / "backend"
BRIDGE_DIR = BACKEND_DIR / "bridge"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BRIDGE_DIR))

from runtime_manifest import runtime_build_status
from startup_diagnostics import (
    STARTUP_FAILURE_EXIT_CODE,
    StartupDiagnostics,
    fatal_unshown_window,
    runtime_facts,
)

VITE_DEV_URL = "http://127.0.0.1:5173"
DIST_INDEX = ROOT / "ui" / "dist" / "index.html"


def _require_current_runtime_build() -> None:
    status = runtime_build_status(ROOT)
    if status != "current":
        if status == "missing":
            raise SystemExit("[desktop] 构建产物缺少或不完整；请先执行：cd ui && npm run build")
        raise SystemExit("[desktop] 前端构建产物与当前 Python/前端源码不一致；请先执行：cd ui && npm run build")


def resolve_url(dev: bool) -> str:
    if dev:
        return VITE_DEV_URL
    if not DIST_INDEX.exists():
        print(f"[desktop] 未找到构建产物：{DIST_INDEX}")
        print("[desktop] 请先执行：cd 07_工作台应用/ui && npm run build")
        raise SystemExit(2)
    _require_current_runtime_build()
    return DIST_INDEX.resolve().as_uri()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="AI-write desktop workbench shell（第一轮骨架）")
    ap.add_argument("--dev", action="store_true",
                    help="加载 Vite dev server（需先 cd ui && npm run dev）")
    ap.add_argument("--check-runtime-build", action="store_true",
                    help="只检查生产构建是否存在且与当前源码一致")
    args = ap.parse_args(argv)

    if args.check_runtime_build:
        status = runtime_build_status(ROOT)
        print(f"[desktop] 运行时构建状态：{status}")
        return 0 if status == "current" else 1

    diagnostics = StartupDiagnostics.open_default()
    diagnostics.record("process.start", app_root=str(ROOT), dev_mode=args.dev, **runtime_facts())
    try:
        status = runtime_build_status(ROOT)
        diagnostics.record("runtime_build.checked", status=status)
        url = resolve_url(args.dev)
        diagnostics.record("url.resolved", source="vite" if args.dev else "production_dist")

        import webview  # noqa: PLC0415
        from app_api import AppApi  # noqa: PLC0415

        diagnostics.record("webview.imported", pywebview_version=version("pywebview"))
        api = AppApi()
        diagnostics.record("app_api.initialized")
        window = webview.create_window(
            "Go Write",
            url,
            js_api=api,
            width=1280,
            height=800,
            min_size=(960, 600),
        )
        if window is None:
            raise RuntimeError("pywebview did not create the main window object")

        window.events.shown += lambda: diagnostics.record(
            "window.shown", renderer=getattr(webview, "renderer", None), title=window.title
        )
        window.events.loaded += lambda: diagnostics.record("window.loaded")
        window.events.closed += lambda: diagnostics.record("window.closed")
        diagnostics.record("window.created", title=window.title)
        watchdog = threading.Thread(
            target=fatal_unshown_window,
            args=(diagnostics, window.events.shown, window.events.closed),
            name="gowrite-window-lifecycle-watchdog",
            daemon=True,
        )
        watchdog.start()
        diagnostics.record("webview.start.enter")
        webview.start()
        if not window.events.shown.is_set():
            diagnostics.record("webview.start.returned_without_window")
            diagnostics.record("process.exit", reason="no_window_shown", exit_code=STARTUP_FAILURE_EXIT_CODE)
            return STARTUP_FAILURE_EXIT_CODE
        diagnostics.record("webview.start.returned", window_loaded=window.events.loaded.is_set())
        diagnostics.record("process.exit", reason="normal_window_lifecycle", exit_code=0)
        return 0
    except BaseException as exc:  # desktop startup must make every failure visible to BAT
        diagnostics.record_exception("startup.exception", exc)
        diagnostics.record("process.exit", reason="exception", exit_code=STARTUP_FAILURE_EXIT_CODE)
        return STARTUP_FAILURE_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main())
