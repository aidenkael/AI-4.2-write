# -*- coding: utf-8 -*-
"""Post-Action Writeback Git 测试（Phase 2B2）。

全部在 tmp git repo + local bare origin 中运行，禁止拿真实 origin 做破坏性 Git 测试。
覆盖：
  A. CLEAN_SYNCED_PREFLIGHT_PASS   干净且同步 → precheck PASS
  B. DIRTY_PREFLIGHT_FAIL          tracked dirty → precheck FAIL
  C. NON_MAIN_FAIL                 非 main 分支 → precheck FAIL
  D. ALLOWLIST_COMMIT_PUSH_PASS    allowlist 内变更 → commit + fast-forward push → OK
  E. NO_CHANGES_NO_COMMIT           无 tracked 变化 → NO_TRACKED_CHANGES（不制造空 commit）
  F. UNEXPECTED_TRACKED_DIFF_FAIL  allowlist 外 tracked 变更 → STOP_UNEXPECTED_DIFF
  G. REMOTE_ADVANCED_FAIL          远端前进 → STOP_REMOTE_ADVANCED（拒绝自动恢复）
  H. NO_FORCE_MERGE_REBASE          代码路径不存在 merge/rebase/force/reset/restore/clean/pull
  I. RAW_SOURCE_NOT_STAGED         ignored raw 文件不进入 commit（第二道 allowlist 过滤）
  J. PUSH_RESULT                   成功 push 后 HEAD == origin/main
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import post_action  # noqa: E402


def _run(cmd: list, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return _run(["git", *args], cwd)


@pytest.fixture()
def repo(tmp_path) -> tuple[Path, Path]:
    """work repo + local bare origin；初始 main 一个空 commit 并已 push 同步。"""
    work = tmp_path / "work"
    bare = tmp_path / "origin.git"
    work.mkdir()
    _git(work, "init", "-b", "main")
    _git(work, "config", "user.email", "test@example.com")
    _git(work, "config", "user.name", "test")
    (work / ".gitignore").write_text("*.epub\n*.txt\n", encoding="utf-8")  # 模拟真实仓库 raw 忽略
    (work / "tracked_a.md").write_text("a0", encoding="utf-8")
    (work / "other.md").write_text("o0", encoding="utf-8")  # allowlist 外的 tracked 文件
    _git(work, "add", "-A")
    _git(work, "commit", "-m", "init")
    _git(tmp_path, "init", "--bare", str(bare))
    _git(work, "remote", "add", "origin", str(bare))
    _git(work, "push", "-u", "origin", "main")
    # bare HEAD 指向 main（否则后续 clone 检出 detached HEAD，remote-advance 场景失效）
    _git(bare, "symbolic-ref", "HEAD", "refs/heads/main")
    return work, bare


# ---------- A. CLEAN_SYNCED_PREFLIGHT_PASS ----------

def test_clean_synced_preflight_pass(repo):
    work, _ = repo
    ok, reason = post_action.precheck(work)
    assert ok is True and reason == "OK"


# ---------- B. DIRTY_PREFLIGHT_FAIL ----------

def test_dirty_preflight_fail(repo):
    work, _ = repo
    (work / "tracked_a.md").write_text("a1", encoding="utf-8")  # tracked 修改
    ok, reason = post_action.precheck(work)
    assert ok is False and reason == "DIRTY_WORKTREE"


# ---------- C. NON_MAIN_FAIL ----------

def test_non_main_fail(repo):
    work, _ = repo
    _git(work, "switch", "-c", "dev")
    ok, reason = post_action.precheck(work)
    assert ok is False and reason.startswith("NOT_MAIN")


# ---------- D. ALLOWLIST_COMMIT_PUSH_PASS ----------

def test_allowlist_commit_push_pass(repo):
    work, _ = repo
    (work / "tracked_a.md").write_text("a1", encoding="utf-8")
    out = post_action.safe_commit_push(work, ["tracked_a.md"], "test: allowlist change")
    assert out == "OK"
    assert post_action.head_sha(work, "HEAD") == post_action.head_sha(work, "origin/main")


# ---------- E. NO_CHANGES_NO_COMMIT ----------

def test_no_changes_no_commit(repo):
    work, _ = repo
    out = post_action.safe_commit_push(work, ["tracked_a.md"], "test: noop")
    assert out == "NO_TRACKED_CHANGES"
    # 不制造空 commit：HEAD 未前进
    assert post_action.head_sha(work) == post_action.head_sha(work, "origin/main")


# ---------- F. UNEXPECTED_TRACKED_DIFF_FAIL ----------

def test_unexpected_tracked_diff_fail(repo):
    work, _ = repo
    (work / "tracked_a.md").write_text("a1", encoding="utf-8")  # allowlist 内
    (work / "other.md").write_text("o1", encoding="utf-8")      # allowlist 外 tracked 变更
    out = post_action.safe_commit_push(work, ["tracked_a.md"], "test: unexpected")
    assert out == "STOP_UNEXPECTED_DIFF"


# ---------- G. REMOTE_ADVANCED_FAIL ----------

def test_remote_advanced_fail(repo):
    work, bare = repo
    # 另一个 clone 向 bare origin 推一个 commit
    other = repo[0].parent / "other"
    _run(["git", "clone", "-b", "main", str(bare), str(other)], repo[0].parent)
    _git(other, "config", "user.email", "t2@t")
    _git(other, "config", "user.name", "t2")
    (other / "tracked_a.md").write_text("remote change", encoding="utf-8")
    _git(other, "add", "-A")
    _git(other, "commit", "-m", "remote advance")
    p = _git(other, "push", "origin", "main")
    assert p.returncode == 0, f"other push 必须真正推进远端，否则测试无效: {p.stderr}"
    # 本地 action sync 必须拒绝（不自动 merge/rebase/pull）
    (work / "tracked_a.md").write_text("local change", encoding="utf-8")
    out = post_action.safe_commit_push(work, ["tracked_a.md"], "test: divergence")
    assert out == "STOP_REMOTE_ADVANCED"


# ---------- H. NO_FORCE_MERGE_REBASE ----------

def test_no_force_merge_rebase():
    src = Path(post_action.__file__).read_text(encoding="utf-8")
    banned = ("merge", "rebase", "reset", "restore", "clean", "pull", "--force")
    for kw in banned:
        # 只禁止作为 git 子命令/flag 出现（docstring 描述性文字不受限）
        assert re.search(rf'"({kw})"', src) is None, f"post_action 源码出现禁止操作: {kw}"
    assert '"push", "origin", "main"' in src  # 只允许普通 push


# ---------- I. RAW_SOURCE_NOT_STAGED ----------

def test_raw_source_not_staged(repo):
    work, _ = repo
    # ignored raw 文件（.gitignore 全局忽略 *.epub）
    raw = work / "01_原始素材" / "00_待入库" / "novel.epub"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b"raw epub bytes")
    (work / "tracked_a.md").write_text("a1", encoding="utf-8")
    out = post_action.safe_commit_push(work, ["tracked_a.md", "01_原始素材"], "test: raw")
    assert out == "OK"
    files = _git(work, "show", "--name-only", "--format=", "HEAD").stdout
    assert "novel.epub" not in files  # raw 源文件绝不进 commit
    assert raw.exists()  # 文件仍在磁盘（Local Only）


# ---------- J. PUSH_RESULT ----------

def test_push_result_head_matches_origin(repo):
    work, _ = repo
    (work / "tracked_a.md").write_text("a1", encoding="utf-8")
    out = post_action.safe_commit_push(work, ["tracked_a.md"], "test: push result")
    assert out == "OK"
    assert post_action.head_sha(work) == post_action.head_sha(work, "origin/main")
    # bare origin 的 main 分支与本地一致（用 rev-parse，不依赖 bare HEAD 指向）
    r = _run(["git", "-C", str(repo[1]), "rev-parse", "main"], repo[1].parent)
    assert r.stdout.strip() == post_action.head_sha(work)
