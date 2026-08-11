"""BKP Registry: auto-discover formal BKPs via identity.json."""

import json
import os
from pathlib import Path


def discover_bkps(base_dir: str) -> list:
    """Scan 02_原著蒸馏/*/bkp/identity.json, return list of BKP info dicts."""
    distill_dir = Path(base_dir) / "02_原著蒸馏"
    if not distill_dir.exists():
        return []

    bkps = []
    for bkp_dir in sorted(distill_dir.iterdir()):
        if not bkp_dir.is_dir():
            continue
        identity_path = bkp_dir / "bkp" / "identity.json"
        if not identity_path.exists():
            continue
        try:
            with open(identity_path, "r", encoding="utf-8") as f:
                identity = json.load(f)
            bkps.append({
                "book_id": identity["book"]["book_id"],
                "title": identity["book"]["title"],
                "author": identity["book"]["author"],
                "category": identity["book"].get("category", ""),
                "bkp_dir": str(bkp_dir / "bkp"),
                "identity": identity,
            })
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[WARN] Failed to load {identity_path}: {e}")

    return bkps
