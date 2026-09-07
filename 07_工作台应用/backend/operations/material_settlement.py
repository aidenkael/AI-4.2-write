# -*- coding: utf-8 -*-
"""Workbench-local serialization for shared material truth mutations."""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator


_LOCK = threading.RLock()
_ACTIVE_MATERIAL_ASSETS: set[str] = set()


@contextmanager
def serialized() -> Iterator[None]:
    """Hold the one shared material mutation/final-settlement lock."""
    with _LOCK:
        yield


@contextmanager
def claim_active_asset(asset_id: str) -> Iterator[bool]:
    """Atomically claim a task without holding the lock during its long work."""
    claimed = False
    with _LOCK:
        if asset_id not in _ACTIVE_MATERIAL_ASSETS:
            _ACTIVE_MATERIAL_ASSETS.add(asset_id)
            claimed = True
    try:
        yield claimed
    finally:
        if claimed:
            with _LOCK:
                _ACTIVE_MATERIAL_ASSETS.discard(asset_id)
