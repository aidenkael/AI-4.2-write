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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # 07_工作台应用/
BACKEND_DIR = ROOT / "backend"
BRIDGE_DIR = BACKEND_DIR / "bridge"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BRIDGE_DIR))

import webview  # noqa: E402
from app_api import AppApi  # noqa: E402

VITE_DEV_URL = "http://127.0.0.1:5173"
DIST_INDEX = ROOT / "ui" / "dist" / "index.html"


def resolve_url(dev: bool) -> str:
    if dev:
        return VITE_DEV_URL
    if not DIST_INDEX.exists():
        print(f"[desktop] 未找到构建产物：{DIST_INDEX}")
        print("[desktop] 请先执行：cd 07_工作台应用/ui && npm run build")
        raise SystemExit(2)
    return DIST_INDEX.resolve().as_uri()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="AI-write desktop workbench shell（第一轮骨架）")
    ap.add_argument("--dev", action="store_true",
                    help="加载 Vite dev server（需先 cd ui && npm run dev）")
    args = ap.parse_args(argv)

    url = resolve_url(args.dev)
    api = AppApi()
    webview.create_window(
        "AI-write",
        url,
        js_api=api,
        width=1280,
        height=800,
        min_size=(960, 600),
    )
    webview.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
