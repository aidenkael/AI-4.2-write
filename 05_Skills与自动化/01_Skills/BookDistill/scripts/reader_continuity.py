#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ordered reader-continuity spine for BookDistill.

Parallel batch Readers are deliberately source-local.  This module supplies the
separate, strictly ordered first-reading state they cannot truthfully produce.
The literary payload stays as natural language; deterministic fields only bind
that payload to the current request/run/source and to an exact manifest prefix.

All artifacts live below ``_work/reader_continuity`` and are discovery inputs,
never canonical BKP knowledge.  The module has no model/runtime dependency.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import reading_ledger as rl
except ModuleNotFoundError:  # pragma: no cover - package-style import
    from . import reading_ledger as rl  # type: ignore


STATE_SCHEMA = "gowrite_book_distill_reader_continuity/v1"
CANDIDATE_SCHEMA = "gowrite_book_distill_reader_continuity_candidate/v1"
DIRNAME = "reader_continuity"
STATE_FILENAME = "state.json"
TMP_DIRNAME = ".tmp"
LEASE_BATCH_ID = "CONTINUITY_SPINE"

SOURCE_REF_RE = re.compile(r"^([A-Za-z0-9_./\-]+\.md)#L(\d+)(?:-L?(\d+))?$")


class ReaderContinuityError(Exception):
    """Deterministic reader-continuity contract violation."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_sha256(value: dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_text(raw)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def continuity_dir(bd_dir: Path) -> Path:
    return rl.work_dir(Path(bd_dir)) / DIRNAME


def state_path(bd_dir: Path) -> Path:
    return continuity_dir(bd_dir) / STATE_FILENAME


def temp_dir(bd_dir: Path) -> Path:
    return continuity_dir(bd_dir) / TMP_DIRNAME


def unique_temp_candidate_path(bd_dir: Path, batch_id: str, lease_token: str) -> Path:
    safe = "".join(ch for ch in str(lease_token) if ch.isalnum() or ch in ("-", "_")) or "nolease"
    path = temp_dir(bd_dir) / f"{batch_id}.{safe}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def read_state(bd_dir: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(state_path(bd_dir).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def state_fingerprint(bd_dir: Path) -> str:
    """Hash the exact persisted state for completion-receipt binding."""
    try:
        return hashlib.sha256(state_path(bd_dir).read_bytes()).hexdigest()
    except OSError:
        return ""


def _identity(manifest: dict[str, Any]) -> dict[str, str]:
    return {
        "request_id": str(manifest.get("request_id") or ""),
        "run_id": str(manifest.get("run_id") or ""),
        "source_id": str(manifest.get("source_id") or ""),
        "manifest_hash": str(manifest.get("manifest_hash") or ""),
        "source_fingerprint": str(manifest.get("source_fingerprint") or ""),
    }


def initialize_state(bd_dir: Path, manifest: dict[str, Any]) -> Path:
    """Create a fresh state bound to ``manifest``.

    ``prepare`` first removes the prior continuity directory, so this function
    never silently adopts a state from another source/run.
    """
    batches = manifest.get("batches") or []
    if not isinstance(batches, list) or not batches:
        raise ReaderContinuityError("reading manifest 没有可供连续阅读的 batch。")
    identity = _identity(manifest)
    if any(not value for value in identity.values()):
        raise ReaderContinuityError("reading manifest 缺少 continuity 所需身份字段。")
    empty = ""
    state: dict[str, Any] = {
        "schema": STATE_SCHEMA,
        **identity,
        "state_revision": 0,
        "completed_batch_ids": [],
        "source_position": None,
        "rolling_state": empty,
        "rolling_state_sha256": _sha256_text(empty),
        "history": [],
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    path = state_path(bd_dir)
    _atomic_write_json(path, state)
    return path


def _batch_map(manifest: dict[str, Any]) -> tuple[list[str], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    batches = manifest.get("batches") or []
    spans = manifest.get("spans") or []
    batch_ids = [str(batch.get("batch_id") or "") for batch in batches]
    return batch_ids, {str(b.get("batch_id")): b for b in batches}, {str(s.get("span_id")): s for s in spans}


def batch_spans(manifest: dict[str, Any], batch_id: str) -> list[dict[str, Any]]:
    _ids, batches, spans = _batch_map(manifest)
    batch = batches.get(batch_id)
    if batch is None:
        raise ReaderContinuityError(f"manifest 不存在 batch：{batch_id}")
    result = [spans[sid] for sid in batch.get("span_ids") or [] if sid in spans]
    if len(result) != len(batch.get("span_ids") or []):
        raise ReaderContinuityError(f"batch {batch_id} 的 span 映射不完整。")
    return result


def span_source_ref(span: dict[str, Any]) -> str:
    return f"{span['unit_file']}#L{int(span['start_line'])}-L{int(span['end_line'])}"


def expected_source_refs(manifest: dict[str, Any], batch_id: str) -> list[str]:
    return [span_source_ref(span) for span in batch_spans(manifest, batch_id)]


def validate_state(
    bd_dir: Path,
    manifest: dict[str, Any] | None = None,
    *,
    require_complete: bool = False,
) -> dict[str, Any]:
    manifest = manifest or rl.read_manifest(Path(bd_dir))
    state = read_state(Path(bd_dir))
    errors: list[str] = []
    if manifest is None:
        errors.append("缺少 reading_manifest.json。")
    if state is None:
        errors.append("缺少或无法解析 reader continuity state。")
    if errors:
        return {"ok": False, "complete": False, "errors": errors, "completed_batches": 0, "total_batches": 0}
    assert manifest is not None and state is not None

    if state.get("schema") != STATE_SCHEMA:
        errors.append(f"continuity state schema 非法：{state.get('schema')!r}")
    for key, expected in _identity(manifest).items():
        if str(state.get(key) or "") != expected:
            errors.append(f"continuity state {key} 与当前 manifest 不一致。")

    batch_ids, _batches, _spans = _batch_map(manifest)
    completed = state.get("completed_batch_ids")
    history = state.get("history")
    if not isinstance(completed, list) or any(not isinstance(v, str) for v in completed):
        errors.append("continuity completed_batch_ids 结构非法。")
        completed = []
    if completed != batch_ids[:len(completed)]:
        errors.append("continuity 已完成 batch 不是 manifest 的严格连续前缀。")
    if not isinstance(history, list):
        errors.append("continuity history 结构非法。")
        history = []
    if len(history) != len(completed):
        errors.append("continuity history 数量与已完成 batch 数不一致。")
    if state.get("state_revision") != len(completed):
        errors.append("continuity state_revision 与已完成 batch 数不一致。")

    previous_hash = _sha256_text("")
    for index, event in enumerate(history):
        bid = completed[index] if index < len(completed) else ""
        if not isinstance(event, dict):
            errors.append(f"continuity history[{index}] 结构非法。")
            continue
        if event.get("batch_id") != bid:
            errors.append(f"continuity history[{index}] batch_id 顺序错误。")
        if event.get("previous_state_sha256") != previous_hash:
            errors.append(f"continuity history[{index}] 状态 hash 链断裂。")
        try:
            refs = expected_source_refs(manifest, bid)
        except ReaderContinuityError as exc:
            errors.append(str(exc))
            refs = []
        if event.get("source_refs") != refs:
            errors.append(f"continuity history[{index}] source_refs 不是该 batch 的完整原文范围。")
        next_hash = str(event.get("rolling_state_sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", next_hash):
            errors.append(f"continuity history[{index}] rolling_state_sha256 非法。")
        previous_hash = next_hash

    rolling = state.get("rolling_state")
    if not isinstance(rolling, str):
        errors.append("continuity rolling_state 必须是自然语言字符串。")
        rolling = ""
    final_hash = _sha256_text(rolling)
    if state.get("rolling_state_sha256") != final_hash:
        errors.append("continuity rolling_state 内容与 hash 不一致。")
    if history:
        if not isinstance(history[-1], dict) or history[-1].get("rolling_state_sha256") != final_hash:
            errors.append("continuity 当前 rolling state 与 history 末端不一致。")
    if not history and final_hash != _sha256_text(""):
        errors.append("continuity 尚未推进时 rolling state 必须为空。")

    expected_position = None
    if completed:
        try:
            last_spans = batch_spans(manifest, completed[-1])
            last = last_spans[-1]
            expected_position = {
                "batch_id": completed[-1],
                "unit_file": last["unit_file"],
                "end_line": int(last["end_line"]),
            }
        except (ReaderContinuityError, IndexError, KeyError, TypeError, ValueError) as exc:
            errors.append(f"continuity source_position 无法映射当前 manifest：{exc}")
    if state.get("source_position") != expected_position:
        errors.append("continuity source_position 与已完成前缀末端不一致。")

    complete = len(completed) == len(batch_ids) and bool(batch_ids)
    if require_complete and not complete:
        errors.append("reader continuity spine 尚未按原著顺序读完整个 manifest。")
    return {
        "ok": not errors,
        "complete": complete,
        "errors": errors,
        "completed_batches": len(completed),
        "total_batches": len(batch_ids),
        "next_batch_id": batch_ids[len(completed)] if len(completed) < len(batch_ids) else None,
        "state_revision": state.get("state_revision"),
        "source_position": state.get("source_position"),
    }


def next_batch_payload(bd_dir: Path, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return only prior rolling state plus the exact next source batch.

    No BookProfile, local Reader note, convergence result, or future span is
    included.  This is the mechanical no-lookahead boundary.
    """
    manifest = manifest or rl.read_manifest(Path(bd_dir))
    if manifest is None:
        raise ReaderContinuityError("缺少 reading_manifest.json。")
    check = validate_state(bd_dir, manifest)
    if not check["ok"]:
        raise ReaderContinuityError("continuity state 校验失败：" + "；".join(check["errors"][:5]))
    state = read_state(bd_dir)
    assert state is not None
    if check["complete"]:
        return {"complete": True, "next_batch": None}
    batch_id = str(check["next_batch_id"])
    spans = batch_spans(manifest, batch_id)
    return {
        "complete": False,
        "batch_id": batch_id,
        "spans": spans,
        "source_refs": [span_source_ref(span) for span in spans],
        "expected_revision": int(state["state_revision"]),
        "previous_state_sha256": str(state["rolling_state_sha256"]),
        "rolling_state": str(state["rolling_state"]),
        "source_position": state.get("source_position"),
    }


def render_candidate_template(
    manifest: dict[str, Any], payload: dict[str, Any]
) -> dict[str, Any]:
    """Machine identity + two intentionally free-form literary fields."""
    return {
        "schema": CANDIDATE_SCHEMA,
        **_identity(manifest),
        "batch_id": payload["batch_id"],
        "expected_revision": payload["expected_revision"],
        "previous_state_sha256": payload["previous_state_sha256"],
        "source_refs": payload["source_refs"],
        "experience_update": "",
        "rolling_state": "",
    }


def _read_candidate(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReaderContinuityError(f"continuity candidate 缺失或不是合法 JSON：{exc}") from exc
    if not isinstance(value, dict):
        raise ReaderContinuityError("continuity candidate 必须是 JSON object。")
    return value


def _validate_candidate(candidate: dict[str, Any], manifest: dict[str, Any], state: dict[str, Any], batch_id: str) -> list[str]:
    errors: list[str] = []
    if candidate.get("schema") != CANDIDATE_SCHEMA:
        errors.append("candidate schema 非法。")
    for key, expected in _identity(manifest).items():
        if str(candidate.get(key) or "") != expected:
            errors.append(f"candidate {key} 与当前 manifest 不一致。")
    if candidate.get("batch_id") != batch_id:
        errors.append("candidate batch_id 不是当前期待 batch。")
    if candidate.get("expected_revision") != state.get("state_revision"):
        errors.append("candidate expected_revision 已过期。")
    if candidate.get("previous_state_sha256") != state.get("rolling_state_sha256"):
        errors.append("candidate previous_state_sha256 已过期。")
    refs = candidate.get("source_refs")
    if refs != expected_source_refs(manifest, batch_id):
        errors.append("candidate source_refs 必须精确覆盖当前 batch，且不得引用未来或其他 batch。")
    experience = candidate.get("experience_update")
    rolling = candidate.get("rolling_state")
    if not isinstance(experience, str) or not experience.strip():
        errors.append("candidate experience_update 必须是非空自然语言阅读变化。")
    if not isinstance(rolling, str) or not rolling.strip():
        errors.append("candidate rolling_state 必须是非空自然语言连续阅读状态。")
    return errors


def commit_candidate(
    bd_dir: Path,
    batch_id: str,
    candidate_path: Path,
    *,
    lease_token: str,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate and atomically advance exactly one manifest-prefix batch."""
    bd_dir = Path(bd_dir)
    manifest = manifest or rl.read_manifest(bd_dir)
    if manifest is None:
        raise ReaderContinuityError("缺少 reading_manifest.json。")
    expected_path = unique_temp_candidate_path(bd_dir, batch_id, lease_token).resolve()
    if Path(candidate_path).resolve() != expected_path:
        raise ReaderContinuityError("candidate path 未绑定当前 batch/lease。")
    candidate = _read_candidate(expected_path)
    candidate_sha = _canonical_sha256(candidate)
    state = read_state(bd_dir)
    if state is None:
        raise ReaderContinuityError("缺少 reader continuity state。")
    check = validate_state(bd_dir, manifest)
    if not check["ok"]:
        raise ReaderContinuityError("continuity state 校验失败：" + "；".join(check["errors"][:5]))

    completed = list(state.get("completed_batch_ids") or [])
    if batch_id in completed:
        index = completed.index(batch_id)
        history = state.get("history") or []
        if index < len(history) and history[index].get("candidate_sha256") == candidate_sha:
            try:
                expected_path.unlink(missing_ok=True)
            except OSError:
                pass
            return {"ok": True, "idempotent": True, "batch_id": batch_id,
                    "state_revision": state.get("state_revision"), "complete": check["complete"]}
        raise ReaderContinuityError("已提交 batch 不得用不同 candidate 重复推进或覆盖有效 state。")

    next_id = check.get("next_batch_id")
    if batch_id != next_id:
        raise ReaderContinuityError(f"continuity 必须严格按序推进：当前期待 {next_id}，收到 {batch_id}。")
    errors = _validate_candidate(candidate, manifest, state, batch_id)
    if errors:
        raise ReaderContinuityError("continuity candidate 校验失败：" + "；".join(errors))

    rolling = str(candidate["rolling_state"]).strip()
    experience = str(candidate["experience_update"]).strip()
    new_hash = _sha256_text(rolling)
    refs = expected_source_refs(manifest, batch_id)
    spans = batch_spans(manifest, batch_id)
    last = spans[-1]
    event = {
        "batch_id": batch_id,
        "source_refs": refs,
        "experience_update": experience,
        "previous_state_sha256": state["rolling_state_sha256"],
        "rolling_state_sha256": new_hash,
        "candidate_sha256": candidate_sha,
        "committed_at": _now_iso(),
    }
    state["completed_batch_ids"] = completed + [batch_id]
    state["state_revision"] = int(state["state_revision"]) + 1
    state["source_position"] = {
        "batch_id": batch_id,
        "unit_file": last["unit_file"],
        "end_line": int(last["end_line"]),
    }
    state["rolling_state"] = rolling
    state["rolling_state_sha256"] = new_hash
    state["history"] = list(state.get("history") or []) + [event]
    state["updated_at"] = _now_iso()
    _atomic_write_json(state_path(bd_dir), state)
    try:
        expected_path.unlink(missing_ok=True)
    except OSError:
        pass
    complete = len(state["completed_batch_ids"]) == len(manifest.get("batches") or [])
    return {"ok": True, "idempotent": False, "batch_id": batch_id,
            "state_revision": state["state_revision"], "complete": complete,
            "source_position": state["source_position"]}
