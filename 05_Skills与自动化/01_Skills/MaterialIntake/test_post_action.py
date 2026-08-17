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


# --------------------------------------------------------------------------- #
# 中文 Git path（--porcelain=v1 -z / --name-only -z）：Windows 默认 core.quotepath=true
# 会把中文输出成 quoted/octal 转义；以下测试验证 -z 解析拿到真实路径、allowlist 匹配正确。
# --------------------------------------------------------------------------- #

@pytest.fixture()
def cn_repo(tmp_path) -> tuple[Path, Path]:
    """含真实风格中文 material state files 的 work + local bare origin。"""
    work = tmp_path / "work"
    bare = tmp_path / "origin.git"
    work.mkdir()
    _git(work, "init", "-b", "main")
    _git(work, "config", "user.email", "test@example.com")
    _git(work, "config", "user.name", "test")
    (work / ".gitignore").write_text("*.epub\n*.txt\n*.pdf\n", encoding="utf-8")
    mat = work / "01_原始素材"
    mat.mkdir()
    for name in ("素材资产.json", "素材清单.csv", "素材总索引.md"):
        (mat / name).write_text("v0\n", encoding="utf-8")
    other = work / "其他"
    other.mkdir()
    (other / "其他文件.md").write_text("o0\n", encoding="utf-8")  # 中文 allowlist 外 tracked 文件
    _git(work, "add", "-A")
    _git(work, "commit", "-m", "init cn")
    _git(tmp_path, "init", "--bare", str(bare))
    _git(work, "remote", "add", "origin", str(bare))
    _git(work, "push", "-u", "origin", "main")
    _git(bare, "symbolic-ref", "HEAD", "refs/heads/main")
    return work, bare


# ---------- A. 中文 tracked 文件命中中文 allowlist → OK ----------

def test_chinese_tracked_hits_allowlist(cn_repo):
    work, _ = cn_repo
    (work / "01_原始素材" / "素材资产.json").write_text("v1\n", encoding="utf-8")
    out = post_action.safe_commit_push(work, ["01_原始素材/素材资产.json"], "test: cn allowlist")
    assert out == "OK"
    assert post_action.head_sha(work) == post_action.head_sha(work, "origin/main")


# ---------- B. 三个真实风格 material state 路径均能正确识别 ----------

def test_chinese_three_material_paths_recognized(cn_repo):
    work, _ = cn_repo
    mat = work / "01_原始素材"
    for name in ("素材资产.json", "素材清单.csv", "素材总索引.md"):
        (mat / name).write_text("v1\n", encoding="utf-8")
    allow = ["01_原始素材/素材资产.json", "01_原始素材/素材清单.csv", "01_原始素材/素材总索引.md"]
    out = post_action.safe_commit_push(work, allow, "test: cn three material paths")
    assert out == "OK"
    files = _git(work, "-c", "core.quotepath=false", "show", "--name-only", "--format=", "HEAD").stdout
    assert "01_原始素材/素材资产.json" in files
    assert "01_原始素材/素材清单.csv" in files
    assert "01_原始素材/素材总索引.md" in files


# ---------- C. 中文 allowlist 外文件仍 STOP_UNEXPECTED_DIFF ----------

def test_chinese_outside_allowlist_stops(cn_repo):
    work, _ = cn_repo
    (work / "01_原始素材" / "素材资产.json").write_text("v1\n", encoding="utf-8")
    (work / "其他" / "其他文件.md").write_text("o1\n", encoding="utf-8")  # allowlist 外 tracked
    out = post_action.safe_commit_push(work, ["01_原始素材/素材资产.json"], "test: cn unexpected")
    assert out == "STOP_UNEXPECTED_DIFF"


# ---------- E. rename/copy 解析不把第二个 NUL path 当成独立状态记录 ----------

def test_rename_parsed_as_single_record(cn_repo):
    work, _ = cn_repo
    _git(work, "mv", "01_原始素材/素材资产.json", "01_原始素材/素材资产_改名.json")
    recs = post_action.porcelain(work)
    renames = [r for r in recs if r[0][:1] in ("R", "C")]
    assert len(renames) == 1, f"期望恰好 1 条 rename 记录，实际 {len(recs)}：{recs}"
    xy, p1, p2 = renames[0]
    assert p2 is not None  # 第二个路径（orig）并入同一记录
    assert {p1, p2} == {"01_原始素材/素材资产_改名.json", "01_原始素材/素材资产.json"}
    assert len(recs) == 1  # 第二个路径没有被当成独立状态记录


# ---------- F. 原始 epub/txt 与 06_工作区 仍绝不 stage ----------

def test_chinese_raw_workspace_never_staged(cn_repo):
    work, _ = cn_repo
    # 第二道过滤：中文 raw 与 06_工作区 路径仍被拦截
    assert post_action.path_never_stage("01_原始素材/00_待入库/某小说.epub") is True
    assert post_action.path_never_stage("01_原始素材/00_待入库/某小说.txt") is True
    assert post_action.path_never_stage("06_工作区/SourcePrepare/book_0001_某/full.md") is True
    # 端到端：ignored raw epub 不被 stage，allowlist 内中文文件正常提交
    raw = work / "01_原始素材" / "00_待入库" / "某小说.epub"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b"raw epub bytes")
    (work / "01_原始素材" / "素材资产.json").write_text("v1\n", encoding="utf-8")
    out = post_action.safe_commit_push(work, ["01_原始素材/素材资产.json"], "test: cn raw/workspace")
    assert out == "OK"
    files = _git(work, "-c", "core.quotepath=false", "show", "--name-only", "--format=", "HEAD").stdout
    assert "01_原始素材/素材资产.json" in files
    assert "某小说.epub" not in files
