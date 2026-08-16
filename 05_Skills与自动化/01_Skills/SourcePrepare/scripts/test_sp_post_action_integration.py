# -*- coding: utf-8 -*-
"""SP Post-Action Writeback integration tests（Phase 2B2 第 50 节）。

fake post_action / refresh / process_book：验证 sync 触发条件（不碰真实 git）：
  1. PASS   → sync 被调用（allowlist 含 01_原始素材 元数据）
  2. REVIEW → sync 被调用
  3. FAIL   → sync 仍被调用（formal result 也 sync；退出码 2）
  4. ERROR  → 不 sync（保留现场）
  5. refresh 失败 → 不 sync（metadata 未形成）
  6. --no-git-sync → 不调用
  7. --dry-run → process_book / refresh / sync 全部不调用（绝不写文件）

运行：
  python -m pytest test_sp_post_action_integration.py -v
"""
import hashlib
import json
from pathlib import Path

import pytest

import source_prepare as sp


def _write(root: Path, rel: str, content: bytes = b"x") -> str:
    p = root / "01_原始素材" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


@pytest.fixture()
def fixture(tmp_path):
    """单 asset REFERENCE_WORK 的最小仓库。"""
    root = tmp_path
    sha = _write(root, "01_参考作品/Alpha/Alpha.epub", b"alpha epub")
    assets = [
        {"id": "book_0001", "name": "Alpha", "type": "REFERENCE_WORK",
         "author": "作者A", "tags": [], "notes": "",
         "files": [{"path": "01_参考作品/Alpha/Alpha.epub", "sha256": sha, "primary": True}],
         "purification": {"status": "未处理", "evidence": None},
         "knowledge": {"status": "未开始"}},
    ]
    ledger = {"schema_version": "1.0", "assets": assets, "containers": []}
    (root / "01_原始素材" / "素材资产.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    return root


def _invoke(root: Path, result: str, refresh_rc: int = 0,
            dry_run: bool = False, no_git_sync: bool = False) -> tuple[int, dict]:
    """以固定 process_book 结果调用 sp.main，返回 (exit_code, calls)。"""
    calls = {"process": [], "refresh": 0, "sync": []}
    mp = pytest.MonkeyPatch()

    def fake_process(r, work_name, asset_type, files, book_id, pandoc, force):
        calls["process"].append(work_name)
        return result

    def fake_refresh(r):
        calls["refresh"] += 1
        return refresh_rc

    def fake_sync(r, allowlist, message):
        calls["sync"].append({"allowlist": list(allowlist), "message": message})
        return "OK"

    mp.setattr(sp, "process_book", fake_process)
    mp.setattr(sp.material_catalog, "refresh_and_render", fake_refresh)
    mp.setattr(sp.post_action, "safe_commit_push", fake_sync)
    args = ["--root", str(root), "--all"]
    if dry_run:
        args.append("--dry-run")
    if no_git_sync:
        args.append("--no-git-sync")
    try:
        code = sp.main(args)
    finally:
        mp.undo()
    return code, calls


# ---------- 1. PASS → sync ----------

def test_pass_sync_called(fixture):
    code, calls = _invoke(fixture, "PASS Alpha")
    assert code == 0
    assert len(calls["sync"]) == 1
    al = calls["sync"][0]["allowlist"]
    assert "01_原始素材/素材资产.json" in al
    assert "01_原始素材/README.md" in al
    assert calls["sync"][0]["message"] == "chore: source-prepare writeback"


# ---------- 2. REVIEW → sync ----------

def test_review_sync_called(fixture):
    code, calls = _invoke(fixture, "REVIEW Alpha")
    assert code == 0
    assert len(calls["sync"]) == 1


# ---------- 3. FAIL → sync（formal result 也 sync；退出码 2） ----------

def test_fail_still_syncs(fixture):
    code, calls = _invoke(fixture, "FAIL Alpha")
    assert code == 2  # 批次含失败项
    assert len(calls["sync"]) == 1  # 但 FAIL 是 formal result，metadata 完整 → 仍 sync


# ---------- 4. ERROR → 不 sync（保留现场） ----------

def test_error_no_sync(fixture):
    code, calls = _invoke(fixture, "ERROR Alpha: boom")
    assert code == 2
    assert calls["sync"] == []


# ---------- 5. refresh 失败 → 不 sync（metadata 未形成） ----------

def test_refresh_fail_no_sync(fixture):
    code, calls = _invoke(fixture, "PASS Alpha", refresh_rc=1)
    assert code == 1
    assert calls["refresh"] == 1
    assert calls["sync"] == []


# ---------- 6. --no-git-sync → 不调用 ----------

def test_no_git_sync_flag(fixture):
    code, calls = _invoke(fixture, "PASS Alpha", no_git_sync=True)
    assert code == 0
    assert calls["refresh"] == 1  # local writeback 仍执行
    assert calls["sync"] == []  # 仅跳过 git sync


# ---------- 7. --dry-run → 全不调用（绝不写文件 / commit / push） ----------

def test_dry_run_no_write_no_sync(fixture):
    code, calls = _invoke(fixture, "PASS Alpha", dry_run=True)
    assert code == 0
    assert calls["process"] == []
    assert calls["refresh"] == 0
    assert calls["sync"] == []
