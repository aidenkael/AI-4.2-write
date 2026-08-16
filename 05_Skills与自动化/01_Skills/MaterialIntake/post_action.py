#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Post-Action Writeback（Phase 2B2）：极薄的 deterministic Git helper。

职责：
  PRECHECK         动作开始前校验：git repo / branch=main / fetch / HEAD==origin/main / porcelain 空
  SAFE_COMMIT_PUSH 动作完成后：fetch → remote 未前进 → allowlist diff → commit → 普通 fast-forward push

设计约束（对应 SKILL 第 22-30 节）：
  - 绝不 merge / rebase / force / reset / restore / clean
  - 远端前进 → STOP，不做自动恢复
  - allowlist 之外的任何 tracked change → POST_ACTION_UNEXPECTED_DIFF / STOP
  - 原始素材（*.epub/*.txt/*.pdf/*.mobi/*.azw3/*.zip）、06_工作区/SourcePrepare/、
    collection_manifest.json 无论任何 action 都绝不 staging（allowlist 误含也会被第二道过滤拦截）
  - 无 tracked state change → NO_TRACKED_CHANGES（不制造空 commit）

返回值为稳定字符串枚举：
  OK                    commit + push 成功，HEAD == origin/main
  NO_TRACKED_CHANGES    action 成功但无 tracked 变化，不 commit 不 push
  STOP_*                precheck / diff / remote 任一条件不满足，保留现场
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

RAW_SOURCE_SUFFIXES = (".epub", ".txt", ".pdf", ".mobi", ".azw3", ".zip")
NEVER_STAGE_MARKERS = (
    "06_工作区/SourcePrepare/",
    "collection_manifest.json",
)
# 01_原始素材 下允许进 Git 的 tracked 元数据（raw 文件由 .gitignore + 第二道过滤双重排除）
MI_TRACKED_ALLOW = {"素材资产.json", "素材清单.csv", "素材总索引.md", "README.md"}


def _run(cmd: list, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return _run(["git", *args], root)


def is_repo(root: Path) -> bool:
    r = _git(root, "rev-parse", "--is-inside-work-tree")
    return r.returncode == 0


def current_branch(root: Path) -> str:
    r = _git(root, "branch", "--show-current")
    return r.stdout.strip()


def head_sha(root: Path, ref: str = "HEAD") -> str:
    r = _git(root, "rev-parse", ref)
    return r.stdout.strip()


def porcelain(root: Path) -> list[str]:
    """返回 porcelain 行（忽略空行）。"""
    r = _git(root, "status", "--porcelain")
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def _porcelain_path(ln: str) -> str:
    """从 porcelain 行提取相对路径（处理 'XY path' 与 rename 'R old -> new' 与 untracked '?? dir/'）。"""
    body = ln[3:].strip()
    if " -> " in body:
        body = body.split(" -> ", 1)[1]
    return body


def path_allowed(rel: str, allowlist: list[str]) -> bool:
    """rel（posix）是否命中 allowlist（精确匹配或位于 allowlist 前缀目录下）。"""
    rel = rel.rstrip("/")
    for allow in allowlist:
        a = allow.rstrip("/")
        if rel == a or rel.startswith(a + "/"):
            return True
    return False


def path_never_stage(rel: str) -> bool:
    """第二道过滤：原始素材 / SP workspace / manifest 绝不 staging（即使 allowlist 误含）。"""
    if rel.endswith(RAW_SOURCE_SUFFIXES):
        return True
    relp = rel.replace("\\", "/")
    if any(relp == m.rstrip("/") or relp.startswith(m) for m in NEVER_STAGE_MARKERS):
        return True
    if relp.startswith("01_原始素材/") and Path(relp).name not in MI_TRACKED_ALLOW \
            and relp not in ("01_原始素材",):
        # 01_原始素材 下只允许 tracked 元数据；.gitkeep 目录条目按目录整体放行（由 git add 尊重 ignore）
        if Path(relp).name != ".gitkeep":
            return True
    return False


def precheck(root: Path) -> tuple[bool, str]:
    """动作开始前校验。返回 (ok, reason)。失败原因打印后由调用方 STOP。"""
    if not is_repo(root):
        return False, "NOT_GIT_REPO"
    branch = current_branch(root)
    if branch != "main":
        return False, f"NOT_MAIN:{branch}"
    f = _git(root, "fetch", "origin")
    if f.returncode != 0:
        return False, "FETCH_FAILED"
    if head_sha(root, "HEAD") != head_sha(root, "origin/main"):
        return False, "HEAD_AHEAD_OF_ORIGIN"
    if porcelain(root):
        return False, "DIRTY_WORKTREE"
    return True, "OK"


def _collect_changes(root: Path, allowlist: list[str]) -> tuple[list[str], list[str]]:
    """遍历 porcelain，返回 (allowed_paths, unexpected_paths)。"""
    allowed, unexpected = [], []
    for ln in porcelain(root):
        rel = _porcelain_path(ln)
        if not rel:
            continue
        if path_allowed(rel, allowlist) and not path_never_stage(rel):
            allowed.append(rel)
        else:
            unexpected.append(rel)
    return allowed, unexpected


def safe_commit_push(root: Path, allowlist: list[str], message: str) -> str:
    """动作完成后安全 commit + 普通 fast-forward push。返回状态枚举。"""
    if not is_repo(root):
        return "STOP_NOT_GIT_REPO"
    branch = current_branch(root)
    if branch != "main":
        return f"STOP_NOT_MAIN:{branch}"

    # 1) 再次 fetch；远端必须 == HEAD（任务期间前进 → STOP，不自动恢复）
    f = _git(root, "fetch", "origin")
    if f.returncode != 0:
        return "STOP_FETCH_FAILED"
    if head_sha(root, "HEAD") != head_sha(root, "origin/main"):
        return "STOP_REMOTE_ADVANCED"

    # 2) 检查 tracked diff 只含 allowlist
    allowed, unexpected = _collect_changes(root, allowlist)
    if unexpected:
        print(f"[post-action] POST_ACTION_UNEXPECTED_DIFF × {len(unexpected)}：")
        for rel in unexpected:
            print(f"  - {rel}")
        return "STOP_UNEXPECTED_DIFF"

    if not allowed:
        return "NO_TRACKED_CHANGES"

    # 3) 精确 stage（git add -- path...），不用 git add -A 全仓
    staged = []
    for rel in sorted(set(allowed)):
        r = _git(root, "add", "--", rel)
        if r.returncode == 0:
            staged.append(rel)
    if not staged:
        return "NO_TRACKED_CHANGES"

    # 4) 第二道保护：staged 清单绝不含原始素材 / SP workspace / manifest
    r = _git(root, "diff", "--cached", "--name-only")
    cached = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    bad = [p for p in cached if path_never_stage(p)]
    if bad:
        print(f"[post-action] STAGED_FORBIDDEN × {len(bad)}：{bad}")
        print("[post-action] 已 STOP，保留 staged 现场供人工处理，不做自动 unstage")
        return "STOP_STAGED_FORBIDDEN"

    # 5) commit
    c = _git(root, "commit", "-m", message)
    if c.returncode != 0:
        print(f"[post-action] commit 失败：{c.stderr.strip()}")
        return "STOP_COMMIT_FAILED"

    # 6) 普通 fast-forward push（禁止 force）
    p = _git(root, "push", "origin", "main")
    if p.returncode != 0:
        print(f"[post-action] push 失败：{p.stderr.strip()}")
        return "STOP_PUSH_FAILED"

    # 7) 确认 HEAD == origin/main
    if head_sha(root, "HEAD") != head_sha(root, "origin/main"):
        return "STOP_PUSH_VERIFY_FAILED"
    print(f"[post-action] pushed {head_sha(root)[:12]} -> origin/main")
    return "OK"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Post-Action Writeback helper（PRECHECK + SAFE_COMMIT_PUSH）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("precheck", help="动作开始前校验 git 状态")
    p1.add_argument("--root", default=os.getcwd())

    p2 = sub.add_parser("push", help="动作完成后安全 commit + fast-forward push")
    p2.add_argument("--root", default=os.getcwd())
    p2.add_argument("--message", required=True)
    p2.add_argument("--allow", action="append", required=True,
                    help="允许的 tracked path / 目录前缀（可多次指定）")

    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if args.cmd == "precheck":
        ok, reason = precheck(root)
        print(f"PRECHECK={'PASS' if ok else 'FAIL'} reason={reason}")
        return 0 if ok else 1
    outcome = safe_commit_push(root, args.allow, args.message)
    print(f"OUTCOME={outcome}")
    return 0 if outcome in ("OK", "NO_TRACKED_CHANGES") else 1


if __name__ == "__main__":
    raise SystemExit(main())
