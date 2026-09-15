#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BookDistill shared dynamic Reader pool (deterministic, cross-process).

The parallel BookDistill architecture runs one ``/gowrite`` main Agent that
coordinates a *shared* pool of one-batch Reader subagents. This module is the
minimal, deterministic, Windows-safe local slot primitive that bounds how many
Readers may run at once **across every BookDistill run on this machine**.

Design constraints (task contract §6):

* Global hard limit ``READER_LIMIT = 16``. The local Qoder CN 1.1.52 runtime
  defaults to 20 concurrent subagents; Go Write self-imposes 16 so at least 4
  subagent slots stay free for everything else. This is an application-level
  Reader budget shared by *all* concurrent BookDistill runs — it is not 16 main
  tasks, and it is not a per-book budget.
* Local Only, file-based, atomic, cross-process. No DB / daemon / service /
  event bus / second Agent runtime / SDK / worktree.
* A lease binds ``request_id`` / ``run_id`` / ``batch_id`` / a unique
  ``lease_token`` so a stale or foreign lease can never be confused with a live
  one, and only the true owner (or a reconcile of the same request) releases it.

Atomicity comes from publishing a fully-written same-directory temp file with
``os.link(temp, slot)``. Hard-link creation is atomic and refuses to overwrite
an existing target, so two processes racing for the same slot cannot both win
and an occupied slot is never visible before its lease metadata is complete.

Recovery: the on-disk lease files are the only truth. ``reconcile_request_leases``
lets a resuming main Agent safely drop its own request's leases before it
re-dispatches (the bridge claim guarantees a single main per request). A
conservative age-based ``reclaim_stale_leases`` (default 24h, matching the
bridge's running hard-stale bound) prevents a crashed-and-never-resumed run from
permanently shrinking the pool — without any heartbeat service.

This file intentionally imports nothing from ``book_distill`` / ``reading_ledger``
/ the Workbench backend so it can be exercised in focused tests.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Contract constants
# ---------------------------------------------------------------------------

# Application-level global Reader budget shared by every concurrent BookDistill
# run on this machine. Deliberately below the local runtime's default concurrent
# subagent limit (20) so >=4 subagent slots remain free. NOT a per-book budget
# and NOT 16 Go Write main tasks. Do not surface in the UI.
READER_LIMIT = 16

LEASE_SCHEMA = "gowrite_book_distill_reader_lease/v1"

# Conservative orphan bound. A lease older than this is treated as belonging to a
# runner that will never resume (mirrors the bridge RUNNING_HARD_STALE_SECONDS).
# A live batch completes in minutes, so this never reclaims an active Reader.
DEFAULT_STALE_AFTER_SECONDS = 24 * 60 * 60


class ReaderPoolError(Exception):
    """Deterministic Reader-pool contract violation."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


def _slot_path(pool_root: Path, slot: int) -> Path:
    return Path(pool_root) / f"slot_{slot:02d}.lease"


def _read_lease_file(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _publish_lease_no_overwrite(path: Path, lease: dict[str, Any]) -> bool:
    """Atomically publish complete lease JSON without replacing a winner.

    The temp file is complete and durable before its inode is linked at the slot
    path. ``os.link`` is a same-directory atomic no-overwrite operation on the
    supported Windows filesystem: ``FileExistsError`` means another acquirer
    won. A crash before the link leaves no occupied slot; a crash after it leaves
    a complete, parseable lease (and at worst an unreferenced temp pathname).
    """
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(lease, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(tmp_name, path)
        except FileExistsError:
            return False
        return True
    finally:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Acquire / release
# ---------------------------------------------------------------------------

def acquire_lease(
    pool_root: Path,
    *,
    request_id: str,
    run_id: str,
    batch_id: str,
    limit: int = READER_LIMIT,
    lease_token: str | None = None,
    now_ts: float | None = None,
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
) -> dict[str, Any] | None:
    """Atomically acquire one Reader slot for ``(request_id, batch_id)``.

    Returns the lease dict on success, or ``None`` when the global pool is full
    (every one of the ``limit`` slots is currently held). Never exceeds
    ``limit`` live leases: each complete temp lease is published with an atomic
    no-overwrite hard link, so a concurrent acquirer cannot take the same slot.

    Opportunistically reclaims leases older than ``stale_after_seconds`` first so
    a crashed-and-never-resumed run cannot permanently shrink the pool.
    """
    if limit <= 0:
        raise ReaderPoolError("Reader pool limit 必须为正整数。")
    pool_root = Path(pool_root)
    pool_root.mkdir(parents=True, exist_ok=True)
    now = now_ts if now_ts is not None else _now_ts()

    # Opportunistic age-based reclaim (cheap, deterministic, no heartbeat).
    reclaim_stale_leases(pool_root, stale_after_seconds=stale_after_seconds,
                         now_ts=now, limit=limit)

    token = lease_token or uuid.uuid4().hex
    for slot in range(limit):
        path = _slot_path(pool_root, slot)
        lease = {
            "schema": LEASE_SCHEMA,
            "slot": slot,
            "lease_token": token,
            "request_id": request_id,
            "run_id": run_id,
            "batch_id": batch_id,
            "acquired_at": now,
            "acquired_at_iso": _iso(now),
        }
        try:
            if _publish_lease_no_overwrite(path, lease):
                return dict(lease)
        except OSError as exc:  # pragma: no cover - defensive
            raise ReaderPoolError(f"无法创建 Reader lease 槽：{exc}") from exc
    return None


def release_lease(
    pool_root: Path,
    lease_token: str,
    *,
    request_id: str | None = None,
    limit: int = READER_LIMIT,
) -> bool:
    """Release the lease with ``lease_token`` (idempotent).

    Only the exact token owner releases the slot; when ``request_id`` is given it
    must also match, so a foreign token can never free someone else's Reader.
    Returns True when a lease was removed, False when nothing matched.
    """
    pool_root = Path(pool_root)
    if not pool_root.is_dir() or not lease_token:
        return False
    for slot in range(limit):
        path = _slot_path(pool_root, slot)
        lease = _read_lease_file(path)
        if lease is None:
            # An unparseable/empty reserved slot with no verifiable owner is not
            # released by token match; leave it to reconcile/reclaim.
            continue
        if lease.get("lease_token") != lease_token:
            continue
        if request_id is not None and lease.get("request_id") != request_id:
            continue
        try:
            os.unlink(str(path))
        except OSError:
            return False
        return True
    return False


# ---------------------------------------------------------------------------
# Introspection / recovery
# ---------------------------------------------------------------------------

def read_leases(pool_root: Path, *, limit: int = READER_LIMIT) -> list[dict[str, Any]]:
    """All currently-held leases (parseable slot files), ordered by slot."""
    pool_root = Path(pool_root)
    leases: list[dict[str, Any]] = []
    if not pool_root.is_dir():
        return leases
    for slot in range(limit):
        lease = _read_lease_file(_slot_path(pool_root, slot))
        if lease is not None:
            leases.append(lease)
    return leases


def active_count(pool_root: Path, *, limit: int = READER_LIMIT) -> int:
    """Number of occupied slots (existence-based; a reserved slot counts)."""
    pool_root = Path(pool_root)
    if not pool_root.is_dir():
        return 0
    return sum(1 for slot in range(limit) if _slot_path(pool_root, slot).exists())


def slots_held_by_request(pool_root: Path, request_id: str, *, limit: int = READER_LIMIT) -> int:
    """How many live leases are bound to ``request_id`` (fairness diagnostics)."""
    return sum(1 for lease in read_leases(pool_root, limit=limit)
               if lease.get("request_id") == request_id)


def reconcile_request_leases(pool_root: Path, request_id: str, *, limit: int = READER_LIMIT) -> int:
    """Release every lease bound to ``request_id``; return how many were dropped.

    A resuming main Agent calls this before re-dispatching. It is safe because
    the bridge claim guarantees a single live main per request, so any lease
    still bound to this request belongs to the interrupted run being resumed.
    Leases of *other* requests are never touched (multi-book pool sharing).
    """
    pool_root = Path(pool_root)
    if not pool_root.is_dir() or not request_id:
        return 0
    released = 0
    for slot in range(limit):
        path = _slot_path(pool_root, slot)
        lease = _read_lease_file(path)
        if lease is None or lease.get("request_id") != request_id:
            continue
        try:
            os.unlink(str(path))
            released += 1
        except OSError:
            continue
    return released


def reclaim_stale_leases(
    pool_root: Path,
    *,
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
    now_ts: float | None = None,
    limit: int = READER_LIMIT,
) -> int:
    """Release leases older than ``stale_after_seconds``; return the count.

    Conservative orphan recovery without a heartbeat service. Parseable leases
    use their bound ``acquired_at``. A historical/abnormal malformed slot has no
    verifiable owner metadata, so it is never reconciled by request and is only
    reclaimed when the slot file's own mtime exceeds the same stale boundary.
    Fresh malformed files therefore remain fail-closed instead of being deleted
    on sight, while old malformed files cannot shrink the pool forever.
    """
    pool_root = Path(pool_root)
    if not pool_root.is_dir():
        return 0
    now = now_ts if now_ts is not None else _now_ts()
    reclaimed = 0
    for slot in range(limit):
        path = _slot_path(pool_root, slot)
        lease = _read_lease_file(path)
        if lease is None:
            try:
                acquired = path.stat().st_mtime
            except OSError:
                continue
        else:
            acquired = lease.get("acquired_at")
            if not isinstance(acquired, (int, float)):
                try:
                    acquired = path.stat().st_mtime
                except OSError:
                    continue
        if now - float(acquired) > stale_after_seconds:
            try:
                os.unlink(str(path))
                reclaimed += 1
            except OSError:
                continue
    return reclaimed
