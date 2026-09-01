"""Deterministic source manifest rules shared by the desktop checker and build output."""
from __future__ import annotations

import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

SCHEMA_VERSION = "gowrite_runtime_manifest/v1"
APP_ROOT = Path(__file__).resolve().parents[1]
_EXCLUDED_DIRS = {
    ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache", "__pycache__",
    ".test-build", "dist", "node_modules",
}
_UI_SOURCE_SUFFIXES = {".ts", ".tsx", ".css"}


def _is_excluded(path: Path) -> bool:
    return any(part in _EXCLUDED_DIRS for part in path.parts)


def _production_backend_python(app_root: Path) -> list[Path]:
    backend = app_root / "backend"
    files = []
    for path in backend.rglob("*.py"):
        if _is_excluded(path) or "tests" in path.parts:
            continue
        if path.name == "conftest.py" or path.name.startswith("test_") or path.name.endswith("_test.py"):
            continue
        files.append(path)
    return files


def _ui_inputs(app_root: Path) -> list[Path]:
    ui = app_root / "ui"
    files = [
        path for path in (ui / "src").rglob("*")
        if path.is_file() and path.suffix in _UI_SOURCE_SUFFIXES and not _is_excluded(path)
    ]
    files.extend([
        ui / "index.html",
        ui / "package.json",
        ui / "package-lock.json",
        ui / "vite.config.ts",
        ui / "scripts" / "write-runtime-manifest.mjs",
    ])
    files.extend(sorted(
        path for path in ui.glob("tsconfig*.json") if path.name != "tsconfig.tests.json"
    ))
    return files


def _backend_inputs(app_root: Path) -> list[Path]:
    desktop = app_root / "desktop"
    desktop_files = [
        path for path in desktop.glob("*.py")
        if path.name != "conftest.py" and not path.name.startswith("test_") and not path.name.endswith("_test.py")
    ]
    return [
        *_production_backend_python(app_root),
        *desktop_files,
    ]


def _source_digest(files: list[Path], app_root: Path) -> str:
    digest = hashlib.sha256()
    repo_root = app_root.parent
    for path in sorted(files, key=lambda item: path_key(item, repo_root)):
        digest.update(path.relative_to(repo_root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def path_key(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix().lower()


def runtime_source_digests(app_root: Path = APP_ROOT) -> dict[str, str]:
    app_root = Path(app_root).resolve()
    return {
        "ui_source_sha256": _source_digest(_ui_inputs(app_root), app_root),
        "backend_source_sha256": _source_digest(_backend_inputs(app_root), app_root),
    }


def runtime_manifest_path(app_root: Path = APP_ROOT) -> Path:
    return Path(app_root).resolve() / "ui" / "dist" / "gowrite-runtime.json"


class _RuntimeAssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script" and attributes.get("src"):
            self.references.append(attributes["src"] or "")
        if tag == "link":
            rel = set((attributes.get("rel") or "").lower().split())
            if rel.intersection({"stylesheet", "modulepreload"}) and attributes.get("href"):
                self.references.append(attributes["href"] or "")


def _runtime_assets_complete(index_path: Path) -> bool:
    try:
        parser = _RuntimeAssetParser()
        parser.feed(index_path.read_text(encoding="utf-8"))
        parser.close()
    except (OSError, UnicodeError):
        return False
    dist = index_path.parent.resolve()
    for reference in parser.references:
        parsed = urlsplit(reference)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        asset_path = (dist / unquote(parsed.path)).resolve()
        try:
            asset_path.relative_to(dist)
        except ValueError:
            return False
        if not asset_path.is_file():
            return False
    return True


def runtime_build_status(app_root: Path = APP_ROOT) -> str:
    """Return ``missing``, ``stale`` or ``current`` for the production build."""
    app_root = Path(app_root).resolve()
    dist = app_root / "ui" / "dist"
    manifest_path = runtime_manifest_path(app_root)
    index_path = dist / "index.html"
    if not index_path.is_file() or not manifest_path.is_file():
        return "missing"
    if not _runtime_assets_complete(index_path):
        return "missing"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != SCHEMA_VERSION:
            return "stale"
        expected = runtime_source_digests(app_root)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "stale"
    return "current" if all(manifest.get(key) == value for key, value in expected.items()) else "stale"
