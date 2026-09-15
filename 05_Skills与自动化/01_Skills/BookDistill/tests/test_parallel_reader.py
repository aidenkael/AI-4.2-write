# -*- coding: utf-8 -*-
"""BookDistill 并行 Reader 编排确定性测试（任务书 §14）。

覆盖检查点：
1. manifest coverage 与 200KB batch 语义未变；
2. Reader selection（reader-dispatch）不重复 pending batch（跳过 completed / 已租约）；
3. 多 request 共用 Reader pool 且总 active 永不 >16；
4. lease acquire/release 在 temp root 下 atomic/idempotent；
5. 每个 Reader contract 只处理一个 batch；
6. Reader contract 不允许 reading-commit；
8. 合法 finished-but-uncommitted note 可直接恢复 commit；
9. partial temp note 不被接受；
10. 错 request/run/manifest/source note 被拒绝；
11. completed batch 不再 dispatch。
零模型、零网络、零真实书籍（全部 tmp fixture）。
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[1] / "scripts"))
sys.path.insert(0, str(_HERE.parents[1]))

import reading_ledger as rl  # noqa: E402
import reader_pool as rp  # noqa: E402
import book_distill as bd  # noqa: E402

_REPO_ROOT = _HERE.parents[4]
_READER_AGENT = _REPO_ROOT / ".qoder" / "agents" / "gowrite-bookdistill-reader.md"


def _make_source(root: Path, *, chapters: int, lines_each: int = 300,
                 book_id: str = "book_9001", source_sha: str = "f" * 64) -> Path:
    """Valid SourcePrepare-style PASS package: <book_id>_<name>/chapters + metadata.json."""
    sp = root / f"{book_id}_测试书"
    (sp / "chapters").mkdir(parents=True)
    for i in range(1, chapters + 1):
        text = "\n".join(f"第{i}章 第{j}行 内容" for j in range(1, lines_each + 1))
        (sp / "chapters" / f"{i:04d}.md").write_text(text, encoding="utf-8")
    (sp / "metadata.json").write_text(json.dumps({
        "book_id": book_id, "book": "测试书", "status": "PASS", "skill_version": "0.4.0",
        "unit_semantics": "chapter", "unit_boundary_source": "epub_nav_anchor",
        "chapter_files": chapters, "selected_source": {"sha256": source_sha, "path": f"{book_id}.epub"},
    }, ensure_ascii=False), encoding="utf-8")
    return sp


def _snapshot(fp: str = "c" * 64, *, chapters: int = 40) -> dict:
    return {"book_id": "book_9001", "sp_version": "0.4.0", "source_sha256": "f" * 64,
            "chapter_count": chapters, "chapter_content_fingerprint": fp,
            "unit_semantics": "chapter", "unit_boundary_source": "epub_nav_anchor"}


def _setup(root: Path, *, chapters: int = 40, request_id: str = "r1", run_id: str = "r1"):
    sp = _make_source(root, chapters=chapters)
    bd_dir = root / "bd"
    manifest = rl.build_manifest(sp, request_id=request_id, run_id=run_id,
                                 source_id="book_9001", source_snapshot=_snapshot(chapters=chapters))
    rl.write_manifest(bd_dir, manifest)
    rl.init_ledger(bd_dir, manifest)
    return sp, bd_dir, manifest


def _args(**kw) -> types.SimpleNamespace:
    base = {"output": None, "input": None, "pool_root": None, "limit": 0,
            "batch": None, "temp": None, "lease": None, "request_id": None, "note": None}
    base.update(kw)
    return types.SimpleNamespace(**base)


def _run(fn, args) -> tuple[int, dict]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = fn(args)
    raw = buf.getvalue().strip()
    return rc, (json.loads(raw) if raw else {})


def _acquire(bd_dir: Path, manifest: dict, batch_id: str, pool: Path, *, token: str, limit: int = 16) -> dict:
    """Acquire a live Reader lease so the formal note-publish path accepts it."""
    lease = rp.acquire_lease(pool, request_id=str(manifest["request_id"]),
                             run_id=str(manifest["run_id"]), batch_id=batch_id,
                             limit=limit, lease_token=token)
    assert lease is not None, "test lease acquire failed (pool full?)"
    return lease


def _publish(bd_dir: Path, manifest: dict, batch: dict, pool: Path, *, token: str = "tok",
             limit: int = 16, **note_kw) -> tuple[int, dict]:
    """Acquire a real lease, write a valid temp note, publish through the CLI."""
    _acquire(bd_dir, manifest, batch["batch_id"], pool, token=token, limit=limit)
    tmp_note = _valid_temp_note(bd_dir, manifest, batch, token=token, **note_kw)
    return _run(bd.cmd_note_publish, _args(output=str(bd_dir), batch=batch["batch_id"],
                                           temp=str(tmp_note), lease=token,
                                           pool_root=str(pool), limit=limit))


def _valid_temp_note(bd_dir: Path, manifest: dict, batch: dict, *, token: str = "tok",
                     finding_count: int = 0, extra_finding: str | None = None,
                     override: dict | None = None) -> Path:
    spans = [{ "span_id": s["span_id"], "unit_file": s["unit_file"],
              "start_line": s["start_line"], "end_line": s["end_line"]}
             for s in batch["spans"]]
    text = rl.render_batch_note_template(
        batch_id=batch["batch_id"], request_id=manifest["request_id"], run_id=manifest["run_id"],
        manifest_hash=manifest["manifest_hash"], source_fingerprint=manifest["source_fingerprint"],
        spans=spans)
    text = text.replace('"finding_count": 0', f'"finding_count": {finding_count}')
    if extra_finding:
        text = text.replace("## 未解决问题 / 待跨批核对",
                            f"## 来源绑定 findings（source-bound）\n{extra_finding}\n\n## 未解决问题 / 待跨批核对")
    if override:
        block = json.loads(text[text.index("```json") + 7: text.index("```", text.index("```json") + 7)])
        block.update(override)
        head = text[:text.index("```json")]
        text = head + "```json\n" + json.dumps(block, ensure_ascii=False, indent=2) + "\n```\n"
    tmp = rl.unique_temp_note_path(bd_dir, batch["batch_id"], token)
    tmp.write_text(text, encoding="utf-8")
    return tmp


def _first_batch(bd_dir: Path) -> dict:
    return rl.next_pending_batch(bd_dir)


class BatchSemanticsUnchangedTest(unittest.TestCase):
    def test_point1_200kb_batch_bound_and_coverage_unchanged(self):
        """检查点 1：200KB batch 上限与 gap-free 覆盖语义未变。"""
        self.assertEqual(rl.MAX_BATCH_BYTES, 200 * 1024)
        self.assertEqual(rl.MAX_SPAN_LINES, 2000)
        with tempfile.TemporaryDirectory() as tmp:
            sp, bd_dir, manifest = _setup(Path(tmp), chapters=40)
            cov = rl.validate_manifest_coverage(manifest, sp)
            self.assertTrue(cov["ok"], cov["errors"])
            self.assertGreater(len(manifest["batches"]), 1)
            self.assertEqual(manifest["batch_bounds"]["max_batch_bytes"], 200 * 1024)


class ReaderPoolPrimitiveTest(unittest.TestCase):
    def test_atomic_no_overwrite_two_process_competitors(self):
        """两个跨进程竞争者只有一个取得同一 slot，loser 不覆盖 winner。"""
        with tempfile.TemporaryDirectory() as tmp:
            pool = Path(tmp) / "pool"
            barrier = Path(tmp) / "go"
            ready = [Path(tmp) / f"ready_{i}" for i in range(2)]
            worker = "\n".join([
                "import sys, time",
                "from pathlib import Path",
                f"sys.path.insert(0, {str(_HERE.parents[1] / 'scripts')!r})",
                "import reader_pool as rp",
                "pool, barrier, ready, name = map(Path, sys.argv[1:])",
                "ready.touch()",
                "while not barrier.exists(): time.sleep(0.001)",
                "lease = rp.acquire_lease(pool, request_id=str(name), run_id=str(name), batch_id='B0001', limit=1)",
                "print('won' if lease else 'lost')",
            ])
            procs = [subprocess.Popen(
                [sys.executable, "-c", worker, str(pool), str(barrier), str(ready[i]), f"r{i}"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            ) for i in range(2)]
            for _ in range(5000):
                if all(path.exists() for path in ready):
                    break
                import time
                time.sleep(0.001)
            self.assertTrue(all(path.exists() for path in ready))
            barrier.touch()
            results = []
            for proc in procs:
                stdout, stderr = proc.communicate(timeout=10)
                self.assertEqual(proc.returncode, 0, stderr)
                results.append(stdout.strip())
            self.assertEqual(sorted(results), ["lost", "won"])
            self.assertEqual(rp.active_count(pool, limit=1), 1)
            self.assertEqual(len(rp.read_leases(pool, limit=1)), 1)

    def test_interrupted_publication_never_leaves_reserved_empty_slot(self):
        """发布前中断不会留下占池 slot，后续竞争者仍可获取。"""
        with tempfile.TemporaryDirectory() as tmp:
            pool = Path(tmp) / "pool"
            with mock.patch.object(rp.os, "link", side_effect=OSError("simulated interruption")):
                with self.assertRaises(rp.ReaderPoolError):
                    rp.acquire_lease(pool, request_id="rA", run_id="rA", batch_id="B0001", limit=1)
            self.assertEqual(rp.active_count(pool, limit=1), 0)
            lease = rp.acquire_lease(pool, request_id="rB", run_id="rB", batch_id="B0002", limit=1)
            self.assertIsNotNone(lease)
            self.assertEqual(len(rp.read_leases(pool, limit=1)), 1)

    def test_point4_acquire_release_atomic_idempotent(self):
        """检查点 4：lease acquire/release 在 temp root 下 atomic/idempotent。"""
        with tempfile.TemporaryDirectory() as tmp:
            pool = Path(tmp) / "pool"
            lease = rp.acquire_lease(pool, request_id="rA", run_id="rA", batch_id="B0001")
            self.assertIsNotNone(lease)
            self.assertEqual(rp.active_count(pool), 1)
            token = lease["lease_token"]
            self.assertTrue(rp.release_lease(pool, token, request_id="rA"))
            self.assertEqual(rp.active_count(pool), 0)
            # idempotent：再释放同一 token 不报错、返回 False。
            self.assertFalse(rp.release_lease(pool, token, request_id="rA"))
            # foreign token 不能释放别人的租约。
            l2 = rp.acquire_lease(pool, request_id="rA", run_id="rA", batch_id="B0002")
            self.assertFalse(rp.release_lease(pool, "not-the-token", request_id="rA"))
            self.assertEqual(rp.active_count(pool), 1)
            self.assertTrue(rp.release_lease(pool, l2["lease_token"]))

    def test_point3_shared_pool_global_limit_16(self):
        """检查点 3：多 request 共用 pool，总 active 永不 >16。"""
        with tempfile.TemporaryDirectory() as tmp:
            pool = Path(tmp) / "pool"
            self.assertEqual(rp.READER_LIMIT, 16)
            leases = []
            for i in range(20):
                rid = "rA" if i % 2 == 0 else "rB"
                got = rp.acquire_lease(pool, request_id=rid, run_id=rid, batch_id=f"B{i:04d}")
                leases.append(got)
            acquired = [x for x in leases if x is not None]
            self.assertEqual(len(acquired), 16)
            self.assertEqual(rp.active_count(pool), 16)
            self.assertLessEqual(rp.active_count(pool), rp.READER_LIMIT)
            # 两个 request 都在同一池里共享。
            self.assertTrue(rp.slots_held_by_request(pool, "rA") > 0)
            self.assertTrue(rp.slots_held_by_request(pool, "rB") > 0)

    def test_point3_reconcile_only_own_request(self):
        """检查点 3/8：reconcile 只释放本 request 的租约，不动其它书。"""
        with tempfile.TemporaryDirectory() as tmp:
            pool = Path(tmp) / "pool"
            a = [rp.acquire_lease(pool, request_id="rA", run_id="rA", batch_id=f"B{i:04d}") for i in range(3)]
            b = rp.acquire_lease(pool, request_id="rB", run_id="rB", batch_id="B9000")
            self.assertEqual(rp.active_count(pool), 4)
            released = rp.reconcile_request_leases(pool, "rA")
            self.assertEqual(released, 3)
            self.assertEqual(rp.active_count(pool), 1)
            self.assertEqual(rp.slots_held_by_request(pool, "rB"), 1)
            self.assertIsNotNone(b)

    def test_stale_reclaim_does_not_touch_fresh(self):
        """保守 age-based reclaim 只回收超时孤儿，不动新鲜租约。"""
        with tempfile.TemporaryDirectory() as tmp:
            pool = Path(tmp) / "pool"
            fresh = rp.acquire_lease(pool, request_id="rA", run_id="rA", batch_id="B0001")
            # now 远在 stale 阈值之内 → 不回收。
            n = rp.reclaim_stale_leases(pool, stale_after_seconds=3600, now_ts=fresh["acquired_at"] + 10)
            self.assertEqual(n, 0)
            self.assertEqual(rp.active_count(pool), 1)
            # now 超过阈值 → 回收。
            n2 = rp.reclaim_stale_leases(pool, stale_after_seconds=3600, now_ts=fresh["acquired_at"] + 7200)
            self.assertEqual(n2, 1)
            self.assertEqual(rp.active_count(pool), 0)

    def test_malformed_fresh_slot_is_fail_closed(self):
        """新的 malformed slot 无 owner 证据，不得立即误删。"""
        with tempfile.TemporaryDirectory() as tmp:
            pool = Path(tmp) / "pool"
            pool.mkdir()
            slot = pool / "slot_00.lease"
            slot.write_text("", encoding="utf-8")
            mtime = slot.stat().st_mtime
            reclaimed = rp.reclaim_stale_leases(
                pool, stale_after_seconds=3600, now_ts=mtime + 10, limit=1)
            self.assertEqual(reclaimed, 0)
            self.assertTrue(slot.exists())
            self.assertEqual(rp.active_count(pool, limit=1), 1)

    def test_malformed_stale_slot_is_reclaimed(self):
        """malformed slot 超过保守 stale 边界后可回收，不会永久缩池。"""
        with tempfile.TemporaryDirectory() as tmp:
            pool = Path(tmp) / "pool"
            pool.mkdir()
            slot = pool / "slot_00.lease"
            slot.write_text("not-json", encoding="utf-8")
            old = 1_000_000.0
            os.utime(slot, (old, old))
            reclaimed = rp.reclaim_stale_leases(
                pool, stale_after_seconds=3600, now_ts=old + 7200, limit=1)
            self.assertEqual(reclaimed, 1)
            self.assertFalse(slot.exists())
            self.assertIsNotNone(rp.acquire_lease(
                pool, request_id="rB", run_id="rB", batch_id="B0002", limit=1,
                now_ts=old + 7200))


class ReaderDispatchTest(unittest.TestCase):
    def test_point2_point11_dispatch_skips_completed_and_leased(self):
        """检查点 2/11：dispatch 不重复 pending batch，跳过 completed 与已租约批次。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp, bd_dir, manifest = _setup(root, chapters=40)
            pool = root / "pool"
            rc, d1 = _run(bd.cmd_reader_dispatch, _args(output=str(bd_dir), input=str(sp), pool_root=str(pool)))
            self.assertEqual(rc, 0, d1)
            self.assertIsNotNone(d1["dispatch"])
            b1 = d1["dispatch"]["batch_id"]
            self.assertEqual(d1["active_readers"], 1)
            # 再 dispatch：绝不重复同一 pending batch（已租约），返回下一批。
            rc, d2 = _run(bd.cmd_reader_dispatch, _args(output=str(bd_dir), input=str(sp), pool_root=str(pool)))
            b2 = d2["dispatch"]["batch_id"]
            self.assertNotEqual(b1, b2)
            # 完成 b1（真实 lease + publish + commit + release）后，dispatch 绝不再返回 b1。
            rc, pub = _publish(bd_dir, manifest, d1["dispatch"], pool, token=d1["dispatch"]["lease_token"])
            self.assertEqual(rc, 0, pub)
            rc, _c = _run(bd.cmd_reading_commit, _args(output=str(bd_dir), batch=b1))
            self.assertEqual(rc, 0)
            bd.cmd_reader_release(_args(lease=d1["dispatch"]["lease_token"], pool_root=str(pool)))
            seen = set()
            for _ in range(6):
                rc, dd = _run(bd.cmd_reader_dispatch, _args(output=str(bd_dir), input=str(sp), pool_root=str(pool)))
                if dd.get("dispatch") is None:
                    break
                b = dd["dispatch"]
                seen.add(b["batch_id"])
                _publish(bd_dir, manifest, b, pool, token=b["lease_token"])
                _run(bd.cmd_reading_commit, _args(output=str(bd_dir), batch=b["batch_id"]))
                bd.cmd_reader_release(_args(lease=b["lease_token"], pool_root=str(pool)))
            self.assertNotIn(b1, seen)

    def test_point3_dispatch_pool_full(self):
        """检查点 3：池满时 dispatch 返回 pool_full 且不再占租约。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp, bd_dir, manifest = _setup(root, chapters=40)
            pool = root / "pool"
            # limit=1：先占满，再 dispatch → pool_full。
            rc, d1 = _run(bd.cmd_reader_dispatch, _args(output=str(bd_dir), input=str(sp), pool_root=str(pool), limit=1))
            self.assertIsNotNone(d1["dispatch"])
            rc, d2 = _run(bd.cmd_reader_dispatch, _args(output=str(bd_dir), input=str(sp), pool_root=str(pool), limit=1))
            self.assertTrue(d2["pool_full"])
            self.assertIsNone(d2["dispatch"])
            self.assertEqual(rp.active_count(pool, limit=1), 1)

    def test_a4_dispatch_requires_input(self):
        """A4：正式 dispatch 缺 --input 立即 fail closed，且未占用 Reader 槽。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp, bd_dir, manifest = _setup(root, chapters=40)
            pool = root / "pool"
            rc, out = _run(bd.cmd_reader_dispatch, _args(output=str(bd_dir), input=None, pool_root=str(pool)))
            self.assertEqual(rc, 1)
            self.assertFalse(out.get("ok"))
            self.assertEqual(rp.active_count(pool), 0)

    def test_a4_dispatch_rejects_foreign_source_identity(self):
        """A4：来源 SHA 与当前 manifest 不一致（错书/旧包）必须在 spawn 前 fail closed。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp, bd_dir, manifest = _setup(root, chapters=40)
            pool = root / "pool"
            meta_path = sp / "metadata.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["selected_source"]["sha256"] = "0" * 64  # 篡改来源身份
            meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            rc, out = _run(bd.cmd_reader_dispatch, _args(output=str(bd_dir), input=str(sp), pool_root=str(pool)))
            self.assertEqual(rc, 1)
            self.assertFalse(out.get("ok"))
            self.assertEqual(rp.active_count(pool), 0)


class NotePublishAtomicityTest(unittest.TestCase):
    def test_point8_finished_uncommitted_note_is_commit_ready(self):
        """检查点 8：合法 finished-but-uncommitted canonical note 可直接恢复 commit。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp, bd_dir, manifest = _setup(root, chapters=40)
            pool = root / "pool"
            batch = _first_batch(bd_dir)
            bid = batch["batch_id"]
            rc, pub = _publish(bd_dir, manifest, batch, pool, token="t1", finding_count=0)
            self.assertEqual(rc, 0, pub)
            self.assertTrue((rl.batch_notes_dir(bd_dir) / f"{bid}.md").exists())
            # temp note 已清理。
            self.assertFalse(rl.unique_temp_note_path(bd_dir, bid, "t1").exists())
            # 未 commit 前：has_valid_canonical_note 为真，dispatch 把它列入 commit_ready 且不重读。
            self.assertTrue(rl.has_valid_canonical_note(bd_dir, bid))
            rc, d = _run(bd.cmd_reader_dispatch, _args(output=str(bd_dir), input=str(sp), pool_root=str(pool)))
            self.assertIn(bid, d["commit_ready"])
            # 直接串行 commit 成功（恢复路径：不重读）。
            rc, _c = _run(bd.cmd_reading_commit, _args(output=str(bd_dir), batch=bid))
            self.assertEqual(rc, 0)
            self.assertTrue(rl.read_ledger(bd_dir)["batches"][bid]["status"] == rl.BATCH_STATUS_COMPLETED)

    def test_point9_partial_temp_note_rejected(self):
        """检查点 9：partial / 未检查六域的 temp note 不被接受（持有 live lease 仍失败于内容）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp, bd_dir, manifest = _setup(root, chapters=40)
            pool = root / "pool"
            batch = _first_batch(bd_dir)
            bid = batch["batch_id"]
            _acquire(bd_dir, manifest, bid, pool, token="partial")
            tmp = rl.unique_temp_note_path(bd_dir, bid, "partial")
            tmp.write_text("# Batch %s\n\n半成品，没有 JSON 块\n" % bid, encoding="utf-8")
            rc, out = _run(bd.cmd_note_publish, _args(output=str(bd_dir), batch=bid, temp=str(tmp),
                                                      lease="partial", pool_root=str(pool)))
            self.assertEqual(rc, 1)
            self.assertFalse(out.get("ok"))
            self.assertFalse((rl.batch_notes_dir(bd_dir) / f"{bid}.md").exists())
            self.assertFalse(rl.has_valid_canonical_note(bd_dir, bid))

    def test_point10_wrong_binding_note_rejected(self):
        """检查点 10：错 request/run/manifest/source 的 note 被拒绝。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp, bd_dir, manifest = _setup(root, chapters=40)
            pool = root / "pool"
            batch = _first_batch(bd_dir)
            bid = batch["batch_id"]
            for field, bad in (("request_id", "OTHER"), ("run_id", "OTHER"),
                               ("manifest_hash", "deadbeef"), ("source_fingerprint", "f" * 64)):
                tok = f"t_{field}"
                _acquire(bd_dir, manifest, bid, pool, token=tok)
                tmp = _valid_temp_note(bd_dir, manifest, batch, token=tok, override={field: bad})
                rc, out = _run(bd.cmd_note_publish, _args(output=str(bd_dir), batch=bid, temp=str(tmp),
                                                          lease=tok, pool_root=str(pool)))
                self.assertEqual(rc, 1, f"{field} 应被拒绝")
                self.assertFalse(out.get("ok"))
                bd.cmd_reader_release(_args(lease=tok, pool_root=str(pool)))
            self.assertFalse((rl.batch_notes_dir(bd_dir) / f"{bid}.md").exists())

    def test_point6_out_of_span_evidence_rejected(self):
        """检查点 6/10：note 引用越出本批 span 的证据被拒绝（Reader 只能引用本批原文）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp, bd_dir, manifest = _setup(root, chapters=40)
            pool = root / "pool"
            batch = _first_batch(bd_dir)
            bid = batch["batch_id"]
            _acquire(bd_dir, manifest, bid, pool, token="oob")
            tmp = _valid_temp_note(bd_dir, manifest, batch, token="oob", finding_count=1,
                                   extra_finding="- [OBSERVATION] dimension:结构 | x｜证据：chapters/9999.md#L1-L2｜置信度：高")
            rc, out = _run(bd.cmd_note_publish, _args(output=str(bd_dir), batch=bid, temp=str(tmp),
                                                     lease="oob", pool_root=str(pool)))
            self.assertEqual(rc, 1)
            self.assertFalse(out.get("ok"))

    def test_point11_publish_refuses_completed_batch(self):
        """检查点 11：completed batch 不再被重复发布 note（不重派/不覆盖）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp, bd_dir, manifest = _setup(root, chapters=40)
            pool = root / "pool"
            batch = _first_batch(bd_dir)
            bid = batch["batch_id"]
            rc, pub = _publish(bd_dir, manifest, batch, pool, token="c1")
            self.assertEqual(rc, 0, pub)
            _run(bd.cmd_reading_commit, _args(output=str(bd_dir), batch=bid))
            bd.cmd_reader_release(_args(lease="c1", pool_root=str(pool)))
            # 已 completed：持新 lease 再 publish 也必须被拒（拒绝覆盖 completed batch）。
            rc, out = _publish(bd_dir, manifest, batch, pool, token="c2")
            self.assertEqual(rc, 1)
            self.assertFalse(out.get("ok"))


class LeaseConstrainPublishTest(unittest.TestCase):
    """A2：lease 必须真正约束 Reader publish（迟到 Reader 不能污染恢复后的运行）。"""

    def test_a2_old_reader_cannot_publish_after_reconcile_new_owner(self):
        """old lease -> reconcile -> new lease -> old publish 失败；new owner 成功。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp, bd_dir, manifest = _setup(root, chapters=40)
            pool = root / "pool"
            batch = _first_batch(bd_dir)
            bid = batch["batch_id"]
            # old reader 取得 lease OLD 并写好 temp note，但尚未 publish。
            _acquire(bd_dir, manifest, bid, pool, token="OLD", limit=1)
            old_tmp = _valid_temp_note(bd_dir, manifest, batch, token="OLD")
            # Main 恢复：reconcile 释放本 request 全部租约。
            rp.reconcile_request_leases(pool, str(manifest["request_id"]), limit=1)
            # 新 owner 取得 NEW lease。
            _acquire(bd_dir, manifest, bid, pool, token="NEW", limit=1)
            # old reader 迟到 publish：lease 不再是它的 → 必须失败，不污染。
            rc, out = _run(bd.cmd_note_publish, _args(output=str(bd_dir), batch=bid, temp=str(old_tmp),
                                                      lease="OLD", pool_root=str(pool), limit=1))
            self.assertEqual(rc, 1, out)
            self.assertFalse(out.get("ok"))
            self.assertFalse((rl.batch_notes_dir(bd_dir) / f"{bid}.md").exists())
            # new owner publish 成功。
            new_tmp = _valid_temp_note(bd_dir, manifest, batch, token="NEW")
            rc, out = _run(bd.cmd_note_publish, _args(output=str(bd_dir), batch=bid, temp=str(new_tmp),
                                                      lease="NEW", pool_root=str(pool), limit=1))
            self.assertEqual(rc, 0, out)
            self.assertTrue((rl.batch_notes_dir(bd_dir) / f"{bid}.md").exists())

    def test_a2_publish_requires_live_lease(self):
        """A2：伪造/不存在 lease token 的 publish 必须失败（即使 note 内容合法）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp, bd_dir, manifest = _setup(root, chapters=40)
            pool = root / "pool"
            batch = _first_batch(bd_dir)
            bid = batch["batch_id"]
            tmp_note = _valid_temp_note(bd_dir, manifest, batch, token="ghost")
            rc, out = _run(bd.cmd_note_publish, _args(output=str(bd_dir), batch=bid, temp=str(tmp_note),
                                                     lease="ghost", pool_root=str(pool)))
            self.assertEqual(rc, 1)
            self.assertFalse(out.get("ok"))
            self.assertFalse((rl.batch_notes_dir(bd_dir) / f"{bid}.md").exists())


class CanonicalNoteCommitReadyIntegrityTest(unittest.TestCase):
    """A1：恢复 commit_ready / commit 绝不能绕过 publish 的完整校验。"""

    def test_a1_finding_count_mismatch_not_commit_ready(self):
        """绕过 publish 直接放一个 finding_count 造假的 canonical note：不得 commit_ready / 不得 commit。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp, bd_dir, manifest = _setup(root, chapters=40)
            pool = root / "pool"
            batch = _first_batch(bd_dir)
            bid = batch["batch_id"]
            forged = _valid_temp_note(bd_dir, manifest, batch, token="f", finding_count=7)
            canonical = rl.batch_notes_dir(bd_dir) / f"{bid}.md"
            canonical.write_text(forged.read_text(encoding="utf-8"), encoding="utf-8")
            self.assertFalse(rl.has_valid_canonical_note(bd_dir, bid))
            rc, d = _run(bd.cmd_reader_dispatch, _args(output=str(bd_dir), input=str(sp), pool_root=str(pool)))
            self.assertNotIn(bid, d.get("commit_ready") or [])
            with self.assertRaises(rl.ReadingLedgerError):
                rl.commit_batch(bd_dir, bid, canonical)

    def test_a1_foreign_request_canonical_note_not_commit_ready(self):
        """foreign request_id 的 canonical note 不得成为 commit_ready，也不得 commit。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp, bd_dir, manifest = _setup(root, chapters=40)
            batch = _first_batch(bd_dir)
            bid = batch["batch_id"]
            foreign = _valid_temp_note(bd_dir, manifest, batch, token="x", override={"request_id": "OTHER"})
            canonical = rl.batch_notes_dir(bd_dir) / f"{bid}.md"
            canonical.write_text(foreign.read_text(encoding="utf-8"), encoding="utf-8")
            self.assertFalse(rl.has_valid_canonical_note(bd_dir, bid))
            with self.assertRaises(rl.ReadingLedgerError):
                rl.commit_batch(bd_dir, bid, canonical)


class ReaderContractTest(unittest.TestCase):
    def test_point5_point6_reader_agent_single_batch_no_commit(self):
        """检查点 5/6：Reader 项目级 Agent 契约=只一个 batch、禁止 reading-commit/再分派。"""
        self.assertTrue(_READER_AGENT.is_file(), f"缺少项目级 Reader Agent：{_READER_AGENT}")
        text = _READER_AGENT.read_text(encoding="utf-8")
        # frontmatter 关键字段（Qoder CN CLI 1.1.52 真实 spawn 合同）。
        self.assertIn("name: gowrite-bookdistill-reader", text)
        self.assertIn("effort: xhigh", text)
        frontmatter = text.split("---", 2)[1]
        self.assertIsNone(
            re.search(r"(?m)^model\s*:", frontmatter),
            "Reader 必须省略 model 字段，由真实 spawn 继承 Main 当前模型；不得把 inherit 当 model id",
        )
        self.assertNotIn("qwen", frontmatter.lower())
        self.assertNotIn("deepseek", frontmatter.lower())
        # 只处理一个 batch。
        self.assertIn("严格只负责一个", text)
        # 禁止 reading-commit / 再分派子 Agent。
        self.assertIn("reading-commit", text)
        self.assertTrue("不得执行" in text or "绝不" in text)
        self.assertIn("子 Agent", text)

    def test_point7_main_contract_exclusive_serial_commit(self):
        """检查点 7：Main 契约明确独占串行 commit，Reader 不 commit。"""
        from agent_task import build_distill_agent_task
        task = build_distill_agent_task(Path("sp"), Path("bd"))
        self.assertIn("按 manifest 顺序串行", task)
        self.assertIn("只有 Main 可 commit", task)
        self.assertIn("subagent_type=\"gowrite-bookdistill-reader\"", task)
        self.assertIn("reader-dispatch", task)
        self.assertIn("note-publish", task)
        self.assertIn("全局共享 Reader 池上限 16", task)

    def test_agent_task_constants_match_runtime(self):
        """防漂移：agent_task 镜像常量必须与 reader_pool / book_distill 一致。"""
        import agent_task
        self.assertEqual(agent_task.READER_LIMIT, rp.READER_LIMIT)
        self.assertEqual(agent_task.READER_SUBAGENT, bd.READER_SUBAGENT_TYPE)


if __name__ == "__main__":
    unittest.main()
