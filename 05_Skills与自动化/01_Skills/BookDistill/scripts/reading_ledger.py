#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BookDistill reading manifest / ledger / completion receipt (deterministic).

Long-document learning cannot be proven by an Agent's self-report. This module
provides the mechanical primitives that make whole-book reading resumable and
verifiable:

* ``reading_manifest.json`` — a run-bound, source-fingerprinted plan that lists
  every span of the frozen SourcePrepare input and groups them into bounded
  batches. Spans are gap-free, non-overlapping, and stable-ordered.
* ``reading_ledger.json`` — atomic, idempotent per-batch state
  (``pending``/``completed``) tied to ``request_id`` / ``run_id`` /
  ``manifest_hash`` / ``source_fingerprint``. Resume never replays completed
  batches; a fingerprint change invalidates the ledger.
* ``completion_receipt.json`` — a deterministic receipt written only after the
  ledger is complete, the acceptance gate passes, and the source identity
  still matches. The Qoder bridge may use a valid receipt to recover the
  settlement when the normal response envelope is missing, but the receipt
  never bypasses any quality gate.

The primitives are consumed by ``book_distill.py`` (CLI) and by the Workbench
backend (``operations/materials.py``); this file intentionally does not import
from either, so it can be exercised in focused tests without the full runtime.

Six check domains are audited per batch. ``0 findings`` in a domain is legal;
``unchecked`` is not.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Contract constants
# ---------------------------------------------------------------------------

MANIFEST_SCHEMA = "gowrite_book_distill_reading_manifest/v1"
LEDGER_SCHEMA = "gowrite_book_distill_reading_ledger/v1"
RECEIPT_SCHEMA = "gowrite_book_distill_completion_receipt/v1"

MANIFEST_FILENAME = "reading_manifest.json"
LEDGER_FILENAME = "reading_ledger.json"
RECEIPT_FILENAME = "completion_receipt.json"
BATCH_NOTES_DIRNAME = "batch_notes"
# Per-run unique temp notes live here before deterministic validation + atomic
# publish to the canonical ``batch_notes/<batch_id>.md``. A Reader never writes a
# canonical completed note directly. Process-only; never published to 02.
BATCH_NOTE_TMP_DIRNAME = ".tmp"

# A source ref inside a batch note: ``<unit_file>.md#L<start>[-L<end>]`` where
# unit_file is ``chapters/NNNN`` (BookDistill) or ``sections/S####`` (Method).
NOTE_REF_RE = re.compile(r"([A-Za-z0-9_./\-]+\.md)#L(\d+)(?:-L?(\d+))?")

# The six check domains every batch note must audit. ``0 findings`` is legal;
# ``unchecked`` is not. The names are the canonical Chinese labels used by the
# Agent contract, acceptance gate, and audit trail.
SIX_DOMAINS: tuple[str, ...] = (
    "故事与大纲",
    "人物与关系",
    "章节与场景",
    "冲突与节奏",
    "世界与题材",
    "语言与读者体验",
)

# Conservative internal batching bounds. These are deliberately *not* author
# settings: they exist so a single batch stays well inside any reasonable model
# context window while still amortizing per-batch overhead. Do not surface
# them in the UI.
MAX_BATCH_BYTES = 200 * 1024        # 200 KB of UTF-8 source text per batch
MAX_SPAN_LINES = 2000               # a single span larger than this is split
MIN_SPAN_LINES = 50                 # avoid degenerate tiny tail spans

BATCH_STATUS_PENDING = "pending"
BATCH_STATUS_COMPLETED = "completed"
_ALLOWED_BATCH_STATUSES = frozenset({BATCH_STATUS_PENDING, BATCH_STATUS_COMPLETED})

_WORK_DIRNAME = "_work"


class ReadingLedgerError(Exception):
    """Deterministic reading-manifest/ledger contract violation."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def _atomic_write_text(path: Path, text: str) -> None:
    """Atomic text replace (temp file in same dir -> os.replace). Windows-safe."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def work_dir(bd_dir: Path) -> Path:
    """Process-only working directory (never published to 02)."""
    return Path(bd_dir) / _WORK_DIRNAME


def manifest_path(bd_dir: Path) -> Path:
    return work_dir(bd_dir) / MANIFEST_FILENAME


def ledger_path(bd_dir: Path) -> Path:
    return work_dir(bd_dir) / LEDGER_FILENAME


def receipt_path(bd_dir: Path) -> Path:
    return work_dir(bd_dir) / RECEIPT_FILENAME


def batch_notes_dir(bd_dir: Path) -> Path:
    return work_dir(bd_dir) / BATCH_NOTES_DIRNAME


def batch_note_tmp_dir(bd_dir: Path) -> Path:
    """Per-run unique temp notes (validated + atomically published from here)."""
    return work_dir(bd_dir) / BATCH_NOTES_DIRNAME / BATCH_NOTE_TMP_DIRNAME


def unique_temp_note_path(bd_dir: Path, batch_id: str, lease_token: str) -> Path:
    """The unique temp note path one Reader writes before deterministic publish.

    Bound to ``lease_token`` so two Readers (or a retried Reader) for the same
    batch never share a temp file; only ``publish_batch_note`` promotes a
    validated temp note to the canonical ``batch_notes/<batch_id>.md``.
    """
    tmp_dir = batch_note_tmp_dir(bd_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    safe_token = "".join(ch for ch in str(lease_token) if ch.isalnum() or ch in ("-", "_")) or "nolease"
    return tmp_dir / f"{batch_id}.{safe_token}.md"


def _chapter_sort_key(name: str) -> tuple[int, str]:
    stem = Path(name).stem
    m = re.match(r"^(\d{4})(?:_.*)?$", stem)
    if m:
        return (int(m.group(1)), "")
    return (0, name)


def _is_chapter_file(name: str) -> bool:
    return bool(re.match(r"^\d{4}\.md$", name)) and not name.startswith("0000_")


# ---------------------------------------------------------------------------
# Span / batch construction
# ---------------------------------------------------------------------------

def _unit_files(sp_dir: Path) -> list[Path]:
    chapters_dir = Path(sp_dir) / "chapters"
    if not chapters_dir.is_dir():
        raise ReadingLedgerError(f"SourcePrepare 包缺少 chapters/ 目录：{chapters_dir}")
    files = [p for p in chapters_dir.glob("*.md") if _is_chapter_file(p.name)]
    if not files:
        raise ReadingLedgerError(f"SourcePrepare 包没有正文章节：{chapters_dir}")
    return sorted(files, key=lambda p: _chapter_sort_key(p.name))


def discover_chapter_units(sp_dir: Path) -> list[tuple[str, Path]]:
    """BookDistill units: ``chapters/NNNN.md`` in stable reading order."""
    return [(f"chapters/{p.name}", p) for p in _unit_files(sp_dir)]


def _section_sort_key(name: str) -> tuple[int, str]:
    stem = Path(name).stem
    m = re.match(r"^S(\d+)$", stem)
    if m:
        return (int(m.group(1)), "")
    return (0, name)


def discover_section_units(mp_dir: Path) -> list[tuple[str, Path]]:
    """MethodDistill units: ``sections/S####.md`` in stable order.

    MethodPrepare guarantees ``full.md`` and ``sections/`` share one cleaned
    source sequence, so section-level coverage is the authoritative whole-source
    reading plan for method knowledge distillation.
    """
    sections_dir = Path(mp_dir) / "sections"
    if not sections_dir.is_dir():
        raise ReadingLedgerError(f"MethodPrepare 包缺少 sections/ 目录：{sections_dir}")
    files = [p for p in sections_dir.glob("S*.md")]
    if not files:
        raise ReadingLedgerError(f"MethodPrepare 包没有分节：{sections_dir}")
    files = sorted(files, key=lambda p: _section_sort_key(p.name))
    return [(f"sections/{p.name}", p) for p in files]


def _split_oversized(name: str, total_lines: int) -> list[tuple[int, int]]:
    """Deterministically split an oversized unit into contiguous line spans."""
    if total_lines <= MAX_SPAN_LINES:
        return [(1, total_lines)]
    spans: list[tuple[int, int]] = []
    start = 1
    while start <= total_lines:
        end = min(start + MAX_SPAN_LINES - 1, total_lines)
        # Avoid a degenerate tiny tail: if the remainder is smaller than
        # MIN_SPAN_LINES, extend the current span to the end.
        if total_lines - end < MIN_SPAN_LINES and end < total_lines:
            end = total_lines
        spans.append((start, end))
        start = end + 1
    return spans


def build_spans_from_units(units: list[tuple[str, Path]]) -> list[dict[str, Any]]:
    """Build ordered, gap-free, non-overlapping spans from ``(ref, path)`` units.

    Each span references ``<ref>#L<start>-L<end>``. Oversized units are split
    into contiguous spans so every line of the frozen source belongs to exactly
    one span. Unit-agnostic: BookDistill chapters and MethodDistill sections
    share this primitive.
    """
    spans: list[dict[str, Any]] = []
    for ref, path in units:
        text = path.read_text(encoding="utf-8", errors="replace")
        total_lines = max(1, len(text.splitlines()))
        byte_size = len(text.encode("utf-8"))
        for start, end in _split_oversized(path.name, total_lines):
            span_bytes = byte_size if (start, end) == (1, total_lines) else max(
                1, int(byte_size * (end - start + 1) / total_lines)
            )
            spans.append({
                "unit_file": ref,
                "start_line": start,
                "end_line": end,
                "unit_lines": total_lines,
                "approx_bytes": span_bytes,
            })
    return spans


def build_spans(sp_dir: Path) -> list[dict[str, Any]]:
    """BookDistill span builder (chapters/NNNN.md)."""
    return build_spans_from_units(discover_chapter_units(sp_dir))


def _assign_span_ids(spans: list[dict[str, Any]]) -> None:
    for index, span in enumerate(spans, start=1):
        span["span_id"] = f"S{index:05d}"


def build_batches(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group contiguous spans into bounded batches (stable order, no gaps)."""
    batches: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_bytes = 0
    for span in spans:
        span_bytes = int(span.get("approx_bytes") or 0)
        if current and current_bytes + span_bytes > MAX_BATCH_BYTES:
            batches.append(current)
            current = []
            current_bytes = 0
        current.append(span)
        current_bytes += span_bytes
    if current:
        batches.append(current)
    named: list[dict[str, Any]] = []
    for index, group in enumerate(batches, start=1):
        named.append({
            "batch_id": f"B{index:04d}",
            "span_ids": [s["span_id"] for s in group],
            "total_bytes": sum(int(s.get("approx_bytes") or 0) for s in group),
            "first_unit": group[0]["unit_file"],
            "last_unit": group[-1]["unit_file"],
        })
    return named


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def compute_manifest_hash(manifest: dict[str, Any]) -> str:
    """Stable hash over the manifest content (excluding the hash field itself)."""
    payload = {k: v for k, v in manifest.items() if k != "manifest_hash"}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_text(canonical)


def build_manifest_from_units(
    units: list[tuple[str, Path]],
    *,
    request_id: str,
    run_id: str,
    source_id: str,
    source_snapshot: dict[str, Any],
    unit_semantics: str = "",
) -> dict[str, Any]:
    """Unit-agnostic manifest builder shared by BookDistill and MethodDistill."""
    spans = build_spans_from_units(units)
    _assign_span_ids(spans)
    batches = build_batches(spans)
    manifest: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "request_id": request_id,
        "run_id": run_id,
        "source_id": source_id,
        "source_snapshot": source_snapshot,
        "source_fingerprint": str(source_snapshot.get("chapter_content_fingerprint")
                                  or source_snapshot.get("prepare_fingerprint") or ""),
        "unit_semantics": unit_semantics or str(source_snapshot.get("unit_semantics") or ""),
        "created_at": _now_iso(),
        "spans": spans,
        "batches": batches,
        "six_domains": list(SIX_DOMAINS),
        "batch_bounds": {
            "max_batch_bytes": MAX_BATCH_BYTES,
            "max_span_lines": MAX_SPAN_LINES,
        },
    }
    manifest["manifest_hash"] = compute_manifest_hash(manifest)
    return manifest


def build_manifest(
    sp_dir: Path,
    *,
    request_id: str,
    run_id: str,
    source_id: str,
    source_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Build a deterministic reading manifest bound to this run and source."""
    return build_manifest_from_units(
        discover_chapter_units(sp_dir),
        request_id=request_id, run_id=run_id, source_id=source_id,
        source_snapshot=source_snapshot,
    )


def write_manifest(bd_dir: Path, manifest: dict[str, Any]) -> Path:
    path = manifest_path(bd_dir)
    _atomic_write_json(path, manifest)
    return path


def read_manifest(bd_dir: Path) -> dict[str, Any] | None:
    return _read_json(manifest_path(bd_dir))


def validate_manifest_coverage_units(
    manifest: dict[str, Any], units: list[tuple[str, Path]]
) -> dict[str, Any]:
    """Mechanically prove the manifest covers the full frozen source range.

    Unit-agnostic: works for BookDistill chapters and MethodDistill sections.
    Returns ``{"ok", "errors", "span_count", "batch_count", "unit_count"}``.
    """
    errors: list[str] = []
    spans = manifest.get("spans") or []
    batches = manifest.get("batches") or []
    if not spans:
        errors.append("manifest 没有任何 span。")
    if not batches:
        errors.append("manifest 没有任何 batch。")

    expected_units = {ref: path for ref, path in units}

    # Per-unit span coverage: gap-free, non-overlapping, ordered.
    per_unit: dict[str, list[tuple[int, int]]] = {}
    for span in spans:
        unit = span.get("unit_file")
        if unit not in expected_units:
            errors.append(f"span 引用了非当前来源的单元：{unit}")
            continue
        start = int(span.get("start_line") or 0)
        end = int(span.get("end_line") or 0)
        if start < 1 or end < start:
            errors.append(f"span 行范围非法：{unit}#L{start}-L{end}")
            continue
        per_unit.setdefault(unit, []).append((start, end))
    for unit, path in expected_units.items():
        ranges = sorted(per_unit.get(unit, []))
        if not ranges:
            errors.append(f"单元未被任何 span 覆盖：{unit}")
            continue
        total_lines = max(1, len(path.read_text(encoding="utf-8", errors="replace").splitlines()))
        cursor = 1
        for start, end in ranges:
            if start != cursor:
                errors.append(f"{unit}: span 存在 gap/overlap（期望从 L{cursor} 起，实际 L{start}）。")
                break
            cursor = end + 1
        if cursor != total_lines + 1:
            errors.append(f"{unit}: span 未覆盖到末尾（覆盖到 L{cursor - 1}，实际共 {total_lines} 行）。")

    # Batch coverage: every span belongs to exactly one batch, order stable.
    span_ids = [s.get("span_id") for s in spans]
    batched: list[str] = []
    for batch in batches:
        batched.extend(batch.get("span_ids") or [])
    if sorted(batched) != sorted(span_ids):
        errors.append("batch 聚合的 span 与 manifest span 集合不一致。")
    if batched != span_ids:
        errors.append("batch 聚合的 span 顺序与 manifest span 顺序不一致。")

    return {
        "ok": not errors,
        "errors": errors,
        "span_count": len(spans),
        "batch_count": len(batches),
        "unit_count": len(expected_units),
    }


def validate_manifest_coverage(manifest: dict[str, Any], sp_dir: Path) -> dict[str, Any]:
    """BookDistill coverage validator (chapters/NNNN.md)."""
    try:
        units = discover_chapter_units(sp_dir)
    except ReadingLedgerError as exc:
        return {"ok": False, "errors": [str(exc)], "span_count": 0, "batch_count": 0, "unit_count": 0}
    return validate_manifest_coverage_units(manifest, units)


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------

def init_ledger(bd_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Create a fresh ledger with every batch pending (idempotent per run)."""
    ledger = {
        "schema": LEDGER_SCHEMA,
        "request_id": manifest.get("request_id"),
        "run_id": manifest.get("run_id"),
        "source_id": manifest.get("source_id"),
        "manifest_hash": manifest.get("manifest_hash"),
        "source_fingerprint": manifest.get("source_fingerprint"),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "batches": {
            batch["batch_id"]: {
                "status": BATCH_STATUS_PENDING,
                "span_ids": list(batch.get("span_ids") or []),
            }
            for batch in manifest.get("batches") or []
        },
    }
    _atomic_write_json(ledger_path(bd_dir), ledger)
    batch_notes_dir(bd_dir).mkdir(parents=True, exist_ok=True)
    return ledger


def read_ledger(bd_dir: Path) -> dict[str, Any] | None:
    return _read_json(ledger_path(bd_dir))


def _ledger_matches_manifest(ledger: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if ledger.get("schema") != LEDGER_SCHEMA:
        errors.append(f"ledger schema 非法：{ledger.get('schema')!r}")
    if ledger.get("request_id") != manifest.get("request_id"):
        errors.append("ledger request_id 与 manifest 不一致。")
    if ledger.get("run_id") != manifest.get("run_id"):
        errors.append("ledger run_id 与 manifest 不一致。")
    if ledger.get("manifest_hash") != manifest.get("manifest_hash"):
        errors.append("ledger manifest_hash 与当前 manifest 不一致（来源或批次计划已变化）。")
    if ledger.get("source_fingerprint") != manifest.get("source_fingerprint"):
        errors.append("ledger source_fingerprint 与当前来源不一致。")
    ledger_batches = ledger.get("batches") or {}
    manifest_ids = [b["batch_id"] for b in manifest.get("batches") or []]
    if sorted(ledger_batches.keys()) != sorted(manifest_ids):
        errors.append("ledger 批次集合与 manifest 不一致。")
    return errors


def next_pending_batch(bd_dir: Path) -> dict[str, Any] | None:
    """Return the first pending batch (with its spans) or None when complete."""
    manifest = read_manifest(bd_dir)
    ledger = read_ledger(bd_dir)
    if manifest is None or ledger is None:
        return None
    if _ledger_matches_manifest(ledger, manifest):
        return None
    spans_by_id = {s["span_id"]: s for s in manifest.get("spans") or []}
    for batch in manifest.get("batches") or []:
        state = (ledger.get("batches") or {}).get(batch["batch_id"]) or {}
        if state.get("status") != BATCH_STATUS_COMPLETED:
            return {
                "batch_id": batch["batch_id"],
                "span_ids": list(batch.get("span_ids") or []),
                "spans": [spans_by_id[sid] for sid in batch.get("span_ids") or [] if sid in spans_by_id],
                "total_bytes": batch.get("total_bytes"),
                "first_unit": batch.get("first_unit"),
                "last_unit": batch.get("last_unit"),
                "six_domains": list(manifest.get("six_domains") or SIX_DOMAINS),
            }
    return None


def _parse_batch_note(path: Path, required_domains: tuple[str, ...] = SIX_DOMAINS) -> tuple[dict[str, Any], list[str]]:
    """Parse a batch note's structured header. Returns (data, errors).

    ``required_domains`` is the per-batch audit checklist. BookDistill uses the
    six narrative domains; MethodDistill passes its own method-oriented domains
    (or an empty tuple to only require a structured note). ``0 findings`` in a
    domain is always legal; an unchecked required domain is not.
    """
    errors: list[str] = []
    if not path.exists():
        return {}, [f"batch note 不存在：{path}"]
    text = path.read_text(encoding="utf-8")
    data: dict[str, Any] = {"raw_text": text, "sha256": _sha256_text(text)}
    # Structured JSON block (preferred, machine-auditable).
    block = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if block:
        try:
            parsed = json.loads(block.group(1))
            if isinstance(parsed, dict):
                data["structured"] = parsed
        except json.JSONDecodeError as exc:
            errors.append(f"batch note JSON 块不可解析：{exc}")
    structured = data.get("structured") or {}
    if not str(structured.get("batch_id") or "").strip():
        errors.append("batch note 缺少 batch_id。")
    if required_domains:
        domains = structured.get("domains_checked")
        if not isinstance(domains, list):
            # Back-compat: BookDistill notes may use six_domains_checked.
            domains = structured.get("six_domains_checked")
        if not isinstance(domains, list):
            errors.append("batch note 缺少 domains_checked 列表。")
        else:
            unknown = [d for d in domains if d not in required_domains]
            if unknown:
                errors.append(f"batch note 含未知检查域：{unknown}")
            missing = [d for d in required_domains if d not in domains]
            if missing:
                errors.append(f"batch note 未检查全部要求域，缺：{missing}")
        data["domains_checked"] = list(domains) if isinstance(domains, list) else []
    return data, errors


def commit_batch(
    bd_dir: Path,
    batch_id: str,
    batch_note: Path,
    *,
    required_domains: tuple[str, ...] = SIX_DOMAINS,
) -> dict[str, Any]:
    """Atomically/idempotently mark one batch completed against its note.

    The note must already audit every required domain (``0 findings`` allowed).
    The ledger entry binds batch_id + manifest_hash + source_fingerprint + note
    sha256 so a stale run can never contaminate the current one.
    """
    bd_dir = Path(bd_dir)
    manifest = read_manifest(bd_dir)
    ledger = read_ledger(bd_dir)
    if manifest is None:
        raise ReadingLedgerError("缺少 reading_manifest.json，无法 commit。")
    if ledger is None:
        raise ReadingLedgerError("缺少 reading_ledger.json，无法 commit。")
    mismatch = _ledger_matches_manifest(ledger, manifest)
    if mismatch:
        raise ReadingLedgerError("ledger 与当前 manifest 不一致：" + "；".join(mismatch))
    batches = ledger.setdefault("batches", {})
    if batch_id not in batches:
        raise ReadingLedgerError(f"batch_id 不在当前 manifest 中：{batch_id}")
    note_path = Path(batch_note)
    parsed, errors = _parse_batch_note(note_path, required_domains)
    if errors:
        raise ReadingLedgerError("batch note 校验失败：" + "；".join(errors))
    structured = parsed.get("structured") or {}
    if str(structured.get("batch_id") or "") != batch_id:
        raise ReadingLedgerError(
            f"batch note 的 batch_id={structured.get('batch_id')!r} 与提交批次 {batch_id} 不一致。"
        )
    # Expected note location keeps the ledger self-describing.
    expected = batch_notes_dir(bd_dir) / f"{batch_id}.md"
    if note_path.resolve() != expected.resolve():
        # Allow the caller to pass the canonical path only; copy otherwise.
        expected.parent.mkdir(parents=True, exist_ok=True)
        expected.write_text(parsed["raw_text"], encoding="utf-8", newline="\n")
        note_path = expected
        parsed["sha256"] = _sha256_text(parsed["raw_text"])
    state = batches[batch_id]
    state["status"] = BATCH_STATUS_COMPLETED
    state["batch_note"] = str(note_path.relative_to(bd_dir)).replace(os.sep, "/")
    state["batch_note_sha256"] = parsed["sha256"]
    state["manifest_hash"] = manifest.get("manifest_hash")
    state["source_fingerprint"] = manifest.get("source_fingerprint")
    state["completed_at"] = _now_iso()
    state["domains_checked"] = list(parsed.get("domains_checked") or [])
    state["finding_count"] = int(structured.get("finding_count") or 0)
    ledger["updated_at"] = _now_iso()
    _atomic_write_json(ledger_path(bd_dir), ledger)
    return {"ok": True, "batch_id": batch_id, "status": BATCH_STATUS_COMPLETED}


# ---------------------------------------------------------------------------
# Batch note publish (unique temp -> deterministic validation -> atomic canonical)
# ---------------------------------------------------------------------------

def _batch_span_ranges(manifest: dict[str, Any], batch_id: str) -> dict[str, list[tuple[int, int]]] | None:
    """``{unit_file: [(start, end), ...]}`` covered by one batch's spans."""
    batch = next((b for b in manifest.get("batches") or [] if b.get("batch_id") == batch_id), None)
    if batch is None:
        return None
    spans_by_id = {s.get("span_id"): s for s in manifest.get("spans") or []}
    ranges: dict[str, list[tuple[int, int]]] = {}
    for sid in batch.get("span_ids") or []:
        span = spans_by_id.get(sid)
        if not span:
            continue
        ranges.setdefault(span.get("unit_file"), []).append(
            (int(span.get("start_line") or 0), int(span.get("end_line") or 0))
        )
    return ranges


def validate_note_span_refs(note_text: str, manifest: dict[str, Any], batch_id: str) -> list[str]:
    """Every ``unit#Lx-Ly`` ref in the note must fall inside this batch's spans.

    Cheap deterministic containment check (no full Markdown parse). Keeps a
    Reader honest: it may only cite the prose it was actually assigned.
    """
    ranges = _batch_span_ranges(manifest, batch_id)
    if ranges is None:
        return [f"batch {batch_id} 不在当前 manifest 中。"]
    errors: list[str] = []
    for unit, start_s, end_s in NOTE_REF_RE.findall(note_text):
        start = int(start_s)
        end = int(end_s or start_s)
        allowed = ranges.get(unit)
        if not allowed:
            errors.append(f"note 引用了不属于本批的单元：{unit}#L{start}-L{end}")
        elif not any(s <= start and end <= e for s, e in allowed):
            errors.append(f"note 证据行号越出本批 span 范围：{unit}#L{start}-L{end}")
    return errors


def publish_batch_note(
    bd_dir: Path,
    batch_id: str,
    temp_note: Path,
    *,
    lease_token: str | None = None,
    required_domains: tuple[str, ...] = SIX_DOMAINS,
    validate_span_refs: bool = True,
) -> dict[str, Any]:
    """Validate a Reader's unique temp note, then atomically publish it canonical.

    A Reader never writes a canonical completed note directly; this is the only
    promotion path. It machine-binds the note to the *current* run:
    ``batch_id`` / ``request_id`` / ``run_id`` / ``manifest_hash`` /
    ``source_fingerprint`` must all match the on-disk manifest, the six domains
    must be checked (``0 findings`` legal, ``unchecked`` not), ``finding_count``
    must be a non-negative int, and every source ref must fall inside the batch's
    spans. Any mismatch (stale / foreign / partial note) is rejected and the temp
    note is left untouched so the batch can simply be re-read.

    Does NOT touch the ledger: only the main Agent's ``commit_batch`` marks a
    batch completed (serial, in manifest order). Refuses to clobber a note whose
    batch is already completed.
    """
    bd_dir = Path(bd_dir)
    manifest = read_manifest(bd_dir)
    if manifest is None:
        raise ReadingLedgerError("缺少 reading_manifest.json，无法发布 batch note。")
    batch_ids = [b.get("batch_id") for b in manifest.get("batches") or []]
    if batch_id not in batch_ids:
        raise ReadingLedgerError(f"batch_id 不在当前 manifest 中：{batch_id}")
    ledger = read_ledger(bd_dir)
    if ledger is not None:
        state = (ledger.get("batches") or {}).get(batch_id) or {}
        if state.get("status") == BATCH_STATUS_COMPLETED:
            raise ReadingLedgerError(f"batch {batch_id} 已 completed，拒绝重复发布 note。")
    temp_note = Path(temp_note)
    parsed, errors = _parse_batch_note(temp_note, required_domains)
    if errors:
        raise ReadingLedgerError("temp note 校验失败：" + "；".join(errors))
    structured = parsed.get("structured") or {}
    bind_errors: list[str] = []
    if str(structured.get("batch_id") or "") != batch_id:
        bind_errors.append(f"note batch_id={structured.get('batch_id')!r} 与目标批次 {batch_id} 不一致。")
    for key, current in (
        ("request_id", manifest.get("request_id")),
        ("run_id", manifest.get("run_id")),
        ("manifest_hash", manifest.get("manifest_hash")),
        ("source_fingerprint", manifest.get("source_fingerprint")),
    ):
        value = structured.get(key)
        if value in (None, ""):
            bind_errors.append(f"note 缺少绑定字段 {key}。")
        elif current is not None and value != current:
            bind_errors.append(f"note {key} 与当前运行不一致（stale/foreign note）。")
    finding_count = structured.get("finding_count")
    if isinstance(finding_count, bool) or not isinstance(finding_count, int) or finding_count < 0:
        bind_errors.append(f"note finding_count 非法：{finding_count!r}（必须为非负整数）。")
    if validate_span_refs:
        bind_errors.extend(validate_note_span_refs(parsed.get("raw_text", ""), manifest, batch_id))
    if bind_errors:
        raise ReadingLedgerError("temp note 绑定/证据校验失败：" + "；".join(bind_errors))
    canonical = batch_notes_dir(bd_dir) / f"{batch_id}.md"
    _atomic_write_text(canonical, parsed["raw_text"])
    try:
        if temp_note.resolve() != canonical.resolve():
            os.unlink(str(temp_note))
    except OSError:
        pass
    return {
        "ok": True,
        "batch_id": batch_id,
        "note_path": str(canonical),
        "finding_count": int(finding_count),
        "sha256": parsed["sha256"],
        "lease_token": lease_token,
    }


def has_valid_canonical_note(bd_dir: Path, batch_id: str, *,
                             required_domains: tuple[str, ...] = SIX_DOMAINS) -> bool:
    """True when a pending batch already has a valid canonical note (recovery).

    On resume a finished-but-uncommitted note is committed directly rather than
    re-read. Only the canonical published note counts, and it must still parse
    and audit every required domain.
    """
    canonical = batch_notes_dir(bd_dir) / f"{batch_id}.md"
    if not canonical.exists():
        return False
    _, errors = _parse_batch_note(canonical, required_domains)
    return not errors


def ledger_status(bd_dir: Path) -> dict[str, Any]:
    manifest = read_manifest(bd_dir)
    ledger = read_ledger(bd_dir)
    if manifest is None or ledger is None:
        return {"ok": False, "errors": ["缺少 manifest 或 ledger。"], "complete": False}
    mismatch = _ledger_matches_manifest(ledger, manifest)
    batches = ledger.get("batches") or {}
    total = len(batches)
    completed = sum(1 for s in batches.values() if s.get("status") == BATCH_STATUS_COMPLETED)
    return {
        "ok": not mismatch,
        "errors": mismatch,
        "request_id": manifest.get("request_id"),
        "run_id": manifest.get("run_id"),
        "manifest_hash": manifest.get("manifest_hash"),
        "source_fingerprint": manifest.get("source_fingerprint"),
        "total_batches": total,
        "completed_batches": completed,
        "pending_batches": total - completed,
        "complete": total > 0 and completed == total,
    }


def is_ledger_complete(bd_dir: Path) -> bool:
    return bool(ledger_status(bd_dir).get("complete"))


def validate_ledger(
    bd_dir: Path,
    sp_dir: Path | None = None,
    *,
    required_domains: tuple[str, ...] = SIX_DOMAINS,
    units: list[tuple[str, Path]] | None = None,
) -> dict[str, Any]:
    """Full mechanical validation: manifest coverage + ledger consistency.

    ``units`` overrides source-unit discovery (MethodDistill passes sections);
    when omitted and ``sp_dir`` is given, BookDistill chapters are discovered.
    """
    manifest = read_manifest(bd_dir)
    ledger = read_ledger(bd_dir)
    errors: list[str] = []
    if manifest is None:
        return {"ok": False, "errors": ["缺少 reading_manifest.json。"], "complete": False}
    if ledger is None:
        return {"ok": False, "errors": ["缺少 reading_ledger.json。"], "complete": False}
    coverage: dict[str, Any] = {"ok": True, "errors": []}
    if units is not None:
        coverage = validate_manifest_coverage_units(manifest, units)
    elif sp_dir is not None:
        coverage = validate_manifest_coverage(manifest, sp_dir)
    if not coverage.get("ok"):
        errors.extend(coverage["errors"])
    errors.extend(_ledger_matches_manifest(ledger, manifest))
    batches = ledger.get("batches") or {}
    completed = 0
    for batch_id, state in batches.items():
        status = state.get("status")
        if status not in _ALLOWED_BATCH_STATUSES:
            errors.append(f"batch {batch_id} 状态非法：{status!r}")
            continue
        if status != BATCH_STATUS_COMPLETED:
            continue
        completed += 1
        if state.get("manifest_hash") != manifest.get("manifest_hash"):
            errors.append(f"batch {batch_id} 的 manifest_hash 与当前 manifest 不一致。")
        if state.get("source_fingerprint") != manifest.get("source_fingerprint"):
            errors.append(f"batch {batch_id} 的 source_fingerprint 与当前来源不一致。")
        note_rel = state.get("batch_note")
        if not note_rel:
            errors.append(f"batch {batch_id} completed 但缺少 batch_note。")
            continue
        note_path = bd_dir / note_rel
        parsed, note_errors = _parse_batch_note(note_path, required_domains)
        if note_errors:
            errors.extend(f"batch {batch_id}: {e}" for e in note_errors)
            continue
        if parsed.get("sha256") != state.get("batch_note_sha256"):
            errors.append(f"batch {batch_id} 的 batch note 内容已变化（sha256 不匹配）。")
        if required_domains:
            checked = state.get("domains_checked") or []
            missing = [d for d in required_domains if d not in checked]
            if missing:
                errors.append(f"batch {batch_id} 未检查全部要求域，缺：{missing}。")
    complete = completed == len(batches) and len(batches) > 0 and not errors
    return {
        "ok": not errors,
        "errors": errors,
        "complete": complete,
        "total_batches": len(batches),
        "completed_batches": completed,
        "coverage": coverage,
    }


# ---------------------------------------------------------------------------
# Completion receipt
# ---------------------------------------------------------------------------

def write_completion_receipt(
    bd_dir: Path,
    *,
    request_id: str,
    run_id: str,
    source_id: str,
    source_snapshot: dict[str, Any],
    acceptance_status: str,
    canonical_card_count: int,
    gate_version: str,
) -> Path:
    """Write the deterministic completion receipt.

    Callers MUST only invoke this after the reading ledger is complete and the
    acceptance gate has truly passed for the current source identity. The
    receipt is the bridge's fallback completion signal; it never bypasses the
    backend's independent finalize re-verification.
    """
    manifest = read_manifest(bd_dir)
    ledger = read_ledger(bd_dir)
    if manifest is None or ledger is None:
        raise ReadingLedgerError("缺少 manifest/ledger，无法写 completion receipt。")
    if acceptance_status != "PASS":
        raise ReadingLedgerError(f"acceptance_status 必须为 PASS，当前 {acceptance_status!r}。")
    if not is_ledger_complete(bd_dir):
        raise ReadingLedgerError("reading ledger 未完整结算，拒绝写 completion receipt。")
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "request_id": request_id,
        "run_id": run_id,
        "source_id": source_id,
        "source_snapshot": source_snapshot,
        "manifest_hash": manifest.get("manifest_hash"),
        "source_fingerprint": manifest.get("source_fingerprint"),
        "ledger_complete": True,
        "total_batches": len(ledger.get("batches") or {}),
        "acceptance_status": acceptance_status,
        "canonical_card_count": int(canonical_card_count),
        "gate_version": gate_version,
        "created_at": _now_iso(),
    }
    receipt["receipt_sha256"] = _sha256_text(
        json.dumps({k: v for k, v in receipt.items() if k != "receipt_sha256"},
                   ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    path = receipt_path(bd_dir)
    _atomic_write_json(path, receipt)
    return path


def read_completion_receipt(bd_dir: Path) -> dict[str, Any] | None:
    return _read_json(receipt_path(bd_dir))


def validate_completion_receipt(
    receipt: dict[str, Any] | None,
    bd_dir: Path,
    *,
    request_id: str,
    source_id: str,
    source_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Strictly validate a receipt against the current active request/source.

    A receipt that fails any check must never trigger finalize. The backend
    still re-runs the deterministic gate independently; this validation only
    decides whether the missing-response fallback may proceed at all.
    """
    errors: list[str] = []
    if not isinstance(receipt, dict):
        return {"ok": False, "errors": ["completion receipt 不存在或不可解析。"], "valid": False}
    if receipt.get("schema") != RECEIPT_SCHEMA:
        errors.append(f"receipt schema 非法：{receipt.get('schema')!r}")
    if receipt.get("request_id") != request_id:
        errors.append("receipt request_id 与当前 active request 不一致。")
    if receipt.get("source_id") != source_id:
        errors.append("receipt source_id 与当前素材不一致。")
    if receipt.get("source_snapshot") != source_snapshot:
        errors.append("receipt source_snapshot 与当前 SourcePrepare 快照不一致（来源已变化）。")
    if receipt.get("acceptance_status") != "PASS":
        errors.append(f"receipt acceptance_status 非 PASS：{receipt.get('acceptance_status')!r}")
    if receipt.get("ledger_complete") is not True:
        errors.append("receipt ledger_complete 非 true。")
    manifest = read_manifest(bd_dir)
    if manifest is None:
        errors.append("当前 staging 缺少 reading_manifest.json。")
    else:
        if receipt.get("manifest_hash") != manifest.get("manifest_hash"):
            errors.append("receipt manifest_hash 与当前 manifest 不一致。")
        if receipt.get("source_fingerprint") != manifest.get("source_fingerprint"):
            errors.append("receipt source_fingerprint 与当前 manifest 不一致。")
    # Self-integrity: receipt_sha256 must match its own content.
    stored = receipt.get("receipt_sha256")
    recomputed = _sha256_text(
        json.dumps({k: v for k, v in receipt.items() if k != "receipt_sha256"},
                   ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    if stored != recomputed:
        errors.append("receipt_sha256 自校验失败（内容可能被篡改）。")
    return {"ok": not errors, "errors": errors, "valid": not errors}


# ---------------------------------------------------------------------------
# Batch note template (Agent-facing)
# ---------------------------------------------------------------------------

def render_batch_note_template(
    *,
    batch_id: str,
    request_id: str,
    run_id: str,
    manifest_hash: str,
    source_fingerprint: str,
    spans: Iterable[dict[str, Any]],
    required_domains: tuple[str, ...] = SIX_DOMAINS,
    domain_heading: str = "六域检查（checked 必填；0 findings 合法，unchecked 不合法）",
) -> str:
    span_list = list(spans)
    span_refs = ", ".join(
        f"{s['unit_file']}#L{s['start_line']}-L{s['end_line']}" for s in span_list
    )
    domains = list(required_domains)
    domains_json = json.dumps(domains, ensure_ascii=False)
    domain_lines = "\n".join(f"- {d}：checked | findings: 0" for d in domains)
    return f"""# Batch {batch_id} Reading Note

- request_id: `{request_id}`
- run_id: `{run_id}`
- manifest_hash: `{manifest_hash}`
- source_fingerprint: `{source_fingerprint}`
- spans: {span_refs}

## 直接阅读记录

（在此记录本批原文的真实阅读观察。必须基于当前上下文中的原文，不得从其它批次摘要二次总结。）

## {domain_heading}

{domain_lines}

## 来源绑定 findings（source-bound）

格式：`- [OBSERVATION] dimension:维度 | 一句话观察｜证据：<unit>#L起始-L结束｜置信度：高/中/低`

## 未解决问题 / 待跨批核对

（记录需要在后续收敛阶段跨批核对的问题。）

```json
{{
  "schema": "gowrite_book_distill_batch_note/v1",
  "batch_id": "{batch_id}",
  "request_id": "{request_id}",
  "run_id": "{run_id}",
  "manifest_hash": "{manifest_hash}",
  "source_fingerprint": "{source_fingerprint}",
  "domains_checked": {domains_json},
  "finding_count": 0,
  "span_count": {len(span_list)}
}}
```
"""
