# -*- coding: utf-8 -*-
"""BookDistill ordered reader-continuity deterministic contract tests.

No model and no real book: fixtures prove no-lookahead payload boundaries,
ordered/resumable/idempotent state transitions, run/source invalidation, and
coexistence with the existing shared parallel Reader pool.
"""
import io
import json
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[1] / "scripts"))
sys.path.insert(0, str(_HERE.parents[1]))

import book_distill as bd  # noqa: E402
import reader_continuity as rc  # noqa: E402
import reader_pool as rp  # noqa: E402
import reading_ledger as rl  # noqa: E402


def _source(root: Path, *, chapters: int = 80, lines_each: int = 300) -> Path:
    sp = root / "book_9001_连续阅读测试"
    (sp / "chapters").mkdir(parents=True)
    for chapter in range(1, chapters + 1):
        text = "\n".join(
            f"CHAPTER_{chapter:04d}_ONLY 第{chapter}章第{line}行"
            for line in range(1, lines_each + 1)
        )
        (sp / "chapters" / f"{chapter:04d}.md").write_text(text, encoding="utf-8")
    (sp / "metadata.json").write_text(json.dumps({
        "book_id": "book_9001", "book": "连续阅读测试", "status": "PASS",
        "skill_version": "0.4.0", "unit_semantics": "chapter",
        "unit_boundary_source": "epub_nav_anchor", "chapter_files": chapters,
        "selected_source": {"sha256": "f" * 64, "path": "book_9001.epub"},
    }, ensure_ascii=False), encoding="utf-8")
    return sp


def _snapshot(*, chapters: int = 80, fingerprint: str = "c" * 64) -> dict:
    return {
        "book_id": "book_9001", "sp_version": "0.4.0", "source_sha256": "f" * 64,
        "chapter_count": chapters, "chapter_content_fingerprint": fingerprint,
        "unit_semantics": "chapter", "unit_boundary_source": "epub_nav_anchor",
    }


def _setup(root: Path, *, request_id: str = "req1", run_id: str = "run1"):
    sp = _source(root)
    bd_dir = root / "bd"
    manifest = rl.build_manifest(
        sp, request_id=request_id, run_id=run_id, source_id="book_9001",
        source_snapshot=_snapshot(),
    )
    assert len(manifest["batches"]) > 2
    rl.write_manifest(bd_dir, manifest)
    rl.init_ledger(bd_dir, manifest)
    rc.initialize_state(bd_dir, manifest)
    return sp, bd_dir, manifest


def _candidate(bd_dir: Path, manifest: dict, payload: dict, token: str, *,
               experience: str, rolling: str, refs=None) -> tuple[Path, dict]:
    value = rc.render_candidate_template(manifest, payload)
    value["experience_update"] = experience
    value["rolling_state"] = rolling
    if refs is not None:
        value["source_refs"] = refs
    path = rc.unique_temp_candidate_path(bd_dir, payload["batch_id"], token)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return path, value


def _args(**values):
    base = {"output": None, "input": None, "pool_root": None, "limit": 0,
            "batch": None, "candidate": None, "lease": None, "request_id": None}
    base.update(values)
    return types.SimpleNamespace(**base)


def _run(function, args):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        result = function(args)
    return result, json.loads(buffer.getvalue())


def _complete_local(bd_dir: Path, manifest: dict) -> None:
    while True:
        batch = rl.next_pending_batch(bd_dir)
        if batch is None:
            return
        note = rl.batch_notes_dir(bd_dir) / f"{batch['batch_id']}.md"
        note.write_text(rl.render_batch_note_template(
            batch_id=batch["batch_id"], request_id=manifest["request_id"],
            run_id=manifest["run_id"], manifest_hash=manifest["manifest_hash"],
            source_fingerprint=manifest["source_fingerprint"], spans=batch["spans"]),
            encoding="utf-8")
        rl.commit_batch(bd_dir, batch["batch_id"], note)


def _complete_continuity(bd_dir: Path, manifest: dict) -> None:
    while True:
        payload = rc.next_batch_payload(bd_dir, manifest)
        if payload.get("complete"):
            return
        token = "complete-fixture"
        path, _ = _candidate(
            bd_dir, manifest, payload, token,
            experience=f"{payload['batch_id']} 改变了当前预测。",
            rolling=f"已顺序读到 {payload['batch_id']}，仍保留未决问题。",
        )
        rc.commit_candidate(bd_dir, payload["batch_id"], path,
                            lease_token=token, manifest=manifest)


class OrderedContinuityStateTest(unittest.TestCase):
    def test_batch_n_payload_contains_no_future_source(self):
        """The worker sees only prior state plus the exact next manifest batch."""
        with tempfile.TemporaryDirectory() as tmp:
            _sp, bd_dir, manifest = _setup(Path(tmp))
            first = rc.next_batch_payload(bd_dir, manifest)
            first_id = manifest["batches"][0]["batch_id"]
            future_id = manifest["batches"][1]["batch_id"]
            self.assertEqual(first["batch_id"], first_id)
            self.assertEqual(first["rolling_state"], "")
            current_units = {span["unit_file"] for span in rc.batch_spans(manifest, first_id)}
            future_units = {span["unit_file"] for span in rc.batch_spans(manifest, future_id)}
            serialized = json.dumps(first, ensure_ascii=False)
            self.assertTrue(all(unit in serialized for unit in current_units))
            self.assertTrue(all(unit not in serialized for unit in future_units - current_units))
            self.assertNotIn("book_profile", serialized.lower())
            self.assertNotIn("batch_notes", serialized.lower())
            self.assertNotIn("convergence", serialized.lower())

    def test_future_or_other_batch_refs_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _sp, bd_dir, manifest = _setup(Path(tmp))
            payload = rc.next_batch_payload(bd_dir, manifest)
            future = manifest["batches"][1]["batch_id"]
            path, _value = _candidate(
                bd_dir, manifest, payload, "tok", experience="当前疑问建立。",
                rolling="目前只知道开篇信息。",
                refs=rc.expected_source_refs(manifest, future),
            )
            with self.assertRaisesRegex(rc.ReaderContinuityError, "不得引用未来"):
                rc.commit_candidate(bd_dir, payload["batch_id"], path,
                                    lease_token="tok", manifest=manifest)

    def test_ordered_advance_and_resume_from_same_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            _sp, bd_dir, manifest = _setup(Path(tmp))
            first = rc.next_batch_payload(bd_dir, manifest)
            path, _ = _candidate(
                bd_dir, manifest, first, "tok1", experience="开篇建立了一个尚未解释的承诺。",
                rolling="我仍不知道承诺的答案，暂时信任叙述者。",
            )
            result = rc.commit_candidate(bd_dir, first["batch_id"], path,
                                         lease_token="tok1", manifest=manifest)
            self.assertEqual(result["state_revision"], 1)
            resumed = rc.next_batch_payload(bd_dir, manifest)
            self.assertEqual(resumed["batch_id"], manifest["batches"][1]["batch_id"])
            self.assertEqual(resumed["rolling_state"], "我仍不知道承诺的答案，暂时信任叙述者。")
            self.assertEqual(resumed["source_position"], result["source_position"])
            self.assertEqual(resumed["previous_state_sha256"], rc.read_state(bd_dir)["rolling_state_sha256"])

    def test_replay_is_idempotent_and_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            _sp, bd_dir, manifest = _setup(Path(tmp))
            payload = rc.next_batch_payload(bd_dir, manifest)
            path, value = _candidate(
                bd_dir, manifest, payload, "same", experience="读者建立预测。",
                rolling="预测尚未兑现。",
            )
            first = rc.commit_candidate(bd_dir, payload["batch_id"], path,
                                        lease_token="same", manifest=manifest)
            replay = rc.unique_temp_candidate_path(bd_dir, payload["batch_id"], "same")
            replay.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
            second = rc.commit_candidate(bd_dir, payload["batch_id"], replay,
                                         lease_token="same", manifest=manifest)
            self.assertFalse(first["idempotent"])
            self.assertTrue(second["idempotent"])
            self.assertEqual(rc.read_state(bd_dir)["state_revision"], 1)
            changed = dict(value)
            changed["rolling_state"] = "企图覆盖。"
            replay.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(rc.ReaderContinuityError, "不得.*覆盖"):
                rc.commit_candidate(bd_dir, payload["batch_id"], replay,
                                    lease_token="same", manifest=manifest)
            self.assertEqual(rc.read_state(bd_dir)["rolling_state"], "预测尚未兑现。")

    def test_request_run_manifest_or_source_change_rejects_old_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp, bd_dir, manifest = _setup(Path(tmp))
            variants = [
                rl.build_manifest(sp, request_id="OTHER", run_id="run1", source_id="book_9001",
                                  source_snapshot=_snapshot()),
                rl.build_manifest(sp, request_id="req1", run_id="OTHER", source_id="book_9001",
                                  source_snapshot=_snapshot()),
                rl.build_manifest(sp, request_id="req1", run_id="run1", source_id="book_9001",
                                  source_snapshot=_snapshot(fingerprint="d" * 64)),
            ]
            for changed in variants:
                check = rc.validate_state(bd_dir, changed)
                self.assertFalse(check["ok"])
                self.assertTrue(any(key in " ".join(check["errors"])
                                    for key in ("request_id", "run_id", "manifest_hash", "source_fingerprint")))

    def test_out_of_order_commit_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _sp, bd_dir, manifest = _setup(Path(tmp))
            first = rc.next_batch_payload(bd_dir, manifest)
            second_id = manifest["batches"][1]["batch_id"]
            fake = dict(first)
            fake["batch_id"] = second_id
            fake["source_refs"] = rc.expected_source_refs(manifest, second_id)
            path, _ = _candidate(bd_dir, manifest, fake, "skip",
                                 experience="跳批。", rolling="不应接受。")
            with self.assertRaisesRegex(rc.ReaderContinuityError, "严格按序"):
                rc.commit_candidate(bd_dir, second_id, path, lease_token="skip", manifest=manifest)


class ContinuityPoolIntegrationTest(unittest.TestCase):
    def test_continuity_uses_same_pool_and_local_readers_remain_parallel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp, bd_dir, _manifest = _setup(root)
            pool = root / "pool"
            code, start = _run(bd.cmd_continuity_start, _args(
                output=str(bd_dir), input=str(sp), pool_root=str(pool), limit=3))
            self.assertEqual(code, 0, start)
            self.assertIsNotNone(start["lease"])
            self.assertEqual(start["active_readers"], 1)
            code, local1 = _run(bd.cmd_reader_dispatch, _args(
                output=str(bd_dir), input=str(sp), pool_root=str(pool), limit=3))
            code2, local2 = _run(bd.cmd_reader_dispatch, _args(
                output=str(bd_dir), input=str(sp), pool_root=str(pool), limit=3))
            self.assertEqual((code, code2), (0, 0))
            self.assertNotEqual(local1["dispatch"]["batch_id"], local2["dispatch"]["batch_id"])
            self.assertEqual(rp.active_count(pool, limit=3), 3)
            code3, full = _run(bd.cmd_reader_dispatch, _args(
                output=str(bd_dir), input=str(sp), pool_root=str(pool), limit=3))
            self.assertEqual(code3, 0)
            self.assertTrue(full["pool_full"])
            self.assertEqual(rp.active_count(pool, limit=3), 3)

    def test_reconcile_invalidates_old_continuity_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp, bd_dir, manifest = _setup(root)
            pool = root / "pool"
            _, start = _run(bd.cmd_continuity_start, _args(
                output=str(bd_dir), input=str(sp), pool_root=str(pool), limit=2))
            token = start["lease"]["lease_token"]
            _, nxt = _run(bd.cmd_continuity_next, _args(
                output=str(bd_dir), input=str(sp), pool_root=str(pool), limit=2, lease=token))
            candidate = dict(nxt["candidate_template"])
            candidate["experience_update"] = "旧 worker 的迟到更新。"
            candidate["rolling_state"] = "不应提交。"
            Path(nxt["candidate_path"]).write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")
            rp.reconcile_request_leases(pool, manifest["request_id"], limit=2)
            code, result = _run(bd.cmd_continuity_commit, _args(
                output=str(bd_dir), batch=nxt["batch_id"], candidate=nxt["candidate_path"],
                lease=token, pool_root=str(pool), limit=2))
            self.assertEqual(code, 1)
            self.assertIn("lease", " ".join(result["errors"]))
            self.assertEqual(rc.read_state(bd_dir)["state_revision"], 0)

    def test_reading_validate_requires_both_local_and_continuity_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp, bd_dir, manifest = _setup(root)
            _complete_local(bd_dir, manifest)
            code, result = _run(bd.cmd_reading_validate, _args(
                output=str(bd_dir), input=str(sp)))
            self.assertEqual(code, 1)
            self.assertTrue(result["local_reading_complete"])
            self.assertFalse(result["continuity"]["complete"])
            _complete_continuity(bd_dir, manifest)
            code, result = _run(bd.cmd_reading_validate, _args(
                output=str(bd_dir), input=str(sp)))
            self.assertEqual(code, 0, result)
            self.assertTrue(result["complete"])


class ContinuityContractTest(unittest.TestCase):
    def test_custom_agent_and_main_contract(self):
        agent = _HERE.parents[4] / ".qoder" / "agents" / "gowrite-bookdistill-continuity.md"
        self.assertTrue(agent.is_file())
        text = agent.read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1]
        self.assertNotIn("model:", frontmatter)
        self.assertIn("continuity-next", text)
        self.assertIn("不读 BookProfile", text)
        self.assertIn("不产生 Mechanism/BKP", text)
        from agent_task import build_distill_agent_task
        task = build_distill_agent_task(Path("sp"), Path("bd"))
        self.assertIn('subagent_type="gowrite-bookdistill-continuity"', task)
        self.assertIn("continuity-start", task)
        self.assertIn("continuity state `complete=true`", task)


if __name__ == "__main__":
    unittest.main()
