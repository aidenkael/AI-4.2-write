from __future__ import annotations

import json
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
    (dist / "index.html").write_text("built\n", encoding="utf-8")
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


def test_node_manifest_and_python_checker_agree_on_real_sources():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the cross-language manifest check")
    app = Path(__file__).parents[1]
    ui = app / "ui"
    dist = ui / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "index.html").write_text("test fixture\n", encoding="utf-8")
    subprocess.run([node, "scripts/write-runtime-manifest.mjs"], cwd=ui, check=True)
    manifest = json.loads((dist / "gowrite-runtime.json").read_text(encoding="utf-8"))
    assert manifest == {"schema_version": SCHEMA_VERSION, **runtime_source_digests(app)}
    assert runtime_build_status(app) == "current"
