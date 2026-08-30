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
import hashlib
import json
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
RUNTIME_MANIFEST = ROOT / "ui" / "dist" / "gowrite-runtime.json"


def _source_digest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    repo_root = ROOT.parent
    for path in sorted(paths, key=lambda item: item.relative_to(repo_root).as_posix().lower()):
        digest.update(path.relative_to(repo_root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _runtime_source_digests() -> dict[str, str]:
    ui_root = ROOT / "ui"
    ui_files = [
        *[path for path in (ui_root / "src").rglob("*") if path.is_file() and path.suffix in {".ts", ".tsx", ".css"}],
        ui_root / "index.html", ui_root / "package.json", ui_root / "vite.config.ts",
    ]
    backend_files = [
        *[path for path in (ROOT / "backend").rglob("*.py") if path.is_file()],
        ROOT / "desktop" / "main.py",
    ]
    return {"ui_source_sha256": _source_digest(ui_files), "backend_source_sha256": _source_digest(backend_files)}


def _require_current_runtime_build() -> None:
    if not RUNTIME_MANIFEST.exists():
        raise SystemExit("[desktop] 构建产物缺少运行时清单；请先执行：cd ui && npm run build")
    try:
        manifest = json.loads(RUNTIME_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"[desktop] 运行时清单读取失败：{exc}") from exc
    if manifest.get("schema_version") != "gowrite_runtime_manifest/v1" or any(
        manifest.get(key) != value for key, value in _runtime_source_digests().items()
    ):
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
    args = ap.parse_args(argv)

    url = resolve_url(args.dev)
    api = AppApi()
    webview.create_window(
        "Go Write",
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
