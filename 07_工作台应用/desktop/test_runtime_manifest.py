from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import main as desktop_main  # noqa: E402
from runtime_manifest import SCHEMA_VERSION, runtime_build_status, runtime_source_digests  # noqa: E402


def _fixture(tmp_path: Path) -> Path:
    app = tmp_path / "workbench"
    (app / "backend").mkdir(parents=True)
    (app / "desktop").mkdir()
    (app / "ui" / "src").mkdir(parents=True)
    (app / "ui" / "scripts").mkdir()
    for path, content in {
        app / "backend" / "runtime.py": "RUNTIME = 1\n",
        app / "backend" / "test_runtime.py": "TEST = 1\n",
        app / "backend" / "conftest.py": "CONFIG = 1\n",
        app / "desktop" / "main.py": "MAIN = 1\n",
        app / "desktop" / "runtime_manifest.py": "HELPER = 1\n",
        app / "ui" / "src" / "App.tsx": "export const App = 1\n",
        app / "ui" / "index.html": "<div id=app></div>\n",
        app / "ui" / "package.json": "{}\n",
        app / "ui" / "package-lock.json": "{}\n",
        app / "ui" / "vite.config.ts": "export default {}\n",
        app / "ui" / "tsconfig.json": "{}\n",
        app / "ui" / "scripts" / "write-runtime-manifest.mjs": "export {}\n",
    }.items():
        path.write_text(content, encoding="utf-8")
    return app


def _current_build(app: Path) -> None:
    dist = app / "ui" / "dist"
    dist.mkdir(exist_ok=True)
    assets = dist / "assets"
    assets.mkdir(exist_ok=True)
    (assets / "index.js").write_text("console.log('fixture')\n", encoding="utf-8")
    (assets / "index.css").write_text("body { color: black; }\n", encoding="utf-8")
    (dist / "index.html").write_text(
        '<link rel="modulepreload" href="./assets/index.js">\n'
        '<link rel="stylesheet" href="./assets/index.css">\n'
        '<script type="module" src="./assets/index.js"></script>\n',
        encoding="utf-8",
    )
    (dist / "gowrite-runtime.json").write_text(json.dumps({
        "schema_version": SCHEMA_VERSION,
        **runtime_source_digests(app),
    }), encoding="utf-8")


def test_missing_stale_and_current_build_status(tmp_path: Path):
    app = _fixture(tmp_path)
    assert runtime_build_status(app) == "missing"
    (app / "ui" / "dist").mkdir()
    (app / "ui" / "dist" / "index.html").write_text("built\n", encoding="utf-8")
    (app / "ui" / "dist" / "gowrite-runtime.json").write_text("{}", encoding="utf-8")
    assert runtime_build_status(app) == "stale"
    _current_build(app)
    assert runtime_build_status(app) == "current"


def test_desktop_check_mode_requests_build_for_missing_or_stale_and_skips_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    app = _fixture(tmp_path)
    monkeypatch.setattr(desktop_main, "ROOT", app)
    assert desktop_main.main(["--check-runtime-build"]) == 1
    _current_build(app)
    assert desktop_main.main(["--check-runtime-build"]) == 0
    (app / "backend" / "runtime.py").write_text("RUNTIME = 2\n", encoding="utf-8")
    assert desktop_main.main(["--check-runtime-build"]) == 1


def test_test_only_backend_python_does_not_invalidate_build(tmp_path: Path):
    app = _fixture(tmp_path)
    _current_build(app)
    (app / "backend" / "test_runtime.py").write_text("TEST = 2\n", encoding="utf-8")
    (app / "backend" / "conftest.py").write_text("CONFIG = 2\n", encoding="utf-8")
    assert runtime_build_status(app) == "current"


def test_runtime_backend_python_change_invalidates_build(tmp_path: Path):
    app = _fixture(tmp_path)
    _current_build(app)
    (app / "backend" / "runtime.py").write_text("RUNTIME = 2\n", encoding="utf-8")
    assert runtime_build_status(app) == "stale"


def test_included_ui_build_input_change_invalidates_build(tmp_path: Path):
    app = _fixture(tmp_path)
    _current_build(app)
    (app / "ui" / "tsconfig.json").write_text('{"changed": true}\n', encoding="utf-8")
    assert runtime_build_status(app) == "stale"


def test_complete_build_requires_referenced_javascript_and_stylesheet(tmp_path: Path):
    app = _fixture(tmp_path)
    _current_build(app)
    (app / "ui" / "dist" / "assets" / "index.js").unlink()
    assert runtime_build_status(app) == "missing"
    _current_build(app)
    (app / "ui" / "dist" / "assets" / "index.css").unlink()
    assert runtime_build_status(app) == "missing"


def test_unreferenced_generated_file_is_not_required(tmp_path: Path):
    app = _fixture(tmp_path)
    _current_build(app)
    assert not (app / "ui" / "dist" / "assets" / "unused.js").exists()
    assert runtime_build_status(app) == "current"


def _directory_fingerprint(directory: Path) -> str | None:
    if not directory.exists():
        return None
    digest = hashlib.sha256()
    for path in sorted(directory.rglob("*"), key=lambda item: item.relative_to(directory).as_posix().lower()):
        if path.is_file():
            digest.update(path.relative_to(directory).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def test_node_manifest_and_python_checker_agree_on_tmp_fixture_without_real_dist_mutation(tmp_path: Path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the cross-language manifest check")
    app = _fixture(tmp_path)
    real_dist = Path(__file__).parents[1] / "ui" / "dist"
    before = _directory_fingerprint(real_dist)
    script = (
        "import { createRuntimeManifest } from './scripts/write-runtime-manifest.mjs';"
        "const manifest = await createRuntimeManifest({"
        "uiDir: process.env.GOWRITE_TEST_UI_DIR, "
        "appDir: process.env.GOWRITE_TEST_APP_DIR, "
        "repoDir: process.env.GOWRITE_TEST_REPO_DIR});"
        "process.stdout.write(JSON.stringify(manifest));"
    )
    env = {
        **os.environ,
        "GOWRITE_TEST_UI_DIR": str(app / "ui"),
        "GOWRITE_TEST_APP_DIR": str(app),
        "GOWRITE_TEST_REPO_DIR": str(tmp_path),
    }
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=Path(__file__).parents[1] / "ui", check=True, capture_output=True, text=True, env=env,
    )
    manifest = json.loads(result.stdout)
    assert manifest == {"schema_version": SCHEMA_VERSION, **runtime_source_digests(app)}
    assert _directory_fingerprint(real_dist) == before
