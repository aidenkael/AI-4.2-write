from __future__ import annotations

import threading
import sys
import types
from pathlib import Path

import main as desktop_main
from startup_diagnostics import StartupDiagnostics, resolve_config_root, startup_log_path, window_lifecycle_outcome


def test_startup_log_uses_existing_config_convention(tmp_path: Path):
    configured = tmp_path / "configured"
    assert resolve_config_root({"AI_WRITE_CONFIG_DIR": str(configured)}) == configured
    assert startup_log_path({"AI_WRITE_CONFIG_DIR": str(configured)}) == configured / "logs" / "desktop-startup.log"
    assert startup_log_path({}, tmp_path / "home") == tmp_path / "home" / ".ai-write" / "logs" / "desktop-startup.log"


def test_diagnostics_records_safe_stage_and_exception(tmp_path: Path):
    path = tmp_path / "logs" / "desktop-startup.log"
    path.parent.mkdir()
    diagnostics = StartupDiagnostics(path)
    diagnostics.record("window.created", title="Go Write")
    try:
        raise RuntimeError("renderer unavailable")
    except RuntimeError as exc:
        diagnostics.record_exception("startup.exception", exc)
    content = path.read_text(encoding="utf-8")
    assert '"stage": "window.created"' in content
    assert '"exception_type": "RuntimeError"' in content
    assert "renderer unavailable" in content
    assert "API_KEY=" not in content
    assert "prompt" not in content.lower()


def test_window_lifecycle_distinguishes_shown_closed_and_timeout():
    shown = threading.Event()
    closed = threading.Event()
    shown.set()
    assert window_lifecycle_outcome(shown, closed, 0) == "shown"
    shown.clear()
    closed.set()
    assert window_lifecycle_outcome(shown, closed, 0) == "closed_before_shown"
    closed.clear()
    assert window_lifecycle_outcome(shown, closed, 0) == "shown_timeout"


class _FakeEvent(threading.Event):
    def __init__(self) -> None:
        super().__init__()
        self._handlers = []

    def __iadd__(self, handler):
        self._handlers.append(handler)
        return self

    def set(self) -> None:
        super().set()
        for handler in self._handlers:
            handler()


class _FakeWindow:
    def __init__(self) -> None:
        self.title = "Go Write"
        self.events = types.SimpleNamespace(
            shown=_FakeEvent(), loaded=_FakeEvent(), closed=_FakeEvent(),
        )


def _fake_modules(window: _FakeWindow, start) -> tuple[types.ModuleType, types.ModuleType]:
    webview = types.ModuleType("webview")
    webview.renderer = "edgechromium"
    webview.create_window = lambda *args, **kwargs: window
    webview.start = start
    app_api = types.ModuleType("app_api")
    app_api.AppApi = type("AppApi", (), {})
    return webview, app_api


def test_main_returns_nonzero_when_webview_returns_without_shown_window(tmp_path: Path, monkeypatch):
    log = StartupDiagnostics(tmp_path / "desktop-startup.log")
    window = _FakeWindow()
    webview, app_api = _fake_modules(window, lambda: None)
    monkeypatch.setitem(sys.modules, "webview", webview)
    monkeypatch.setitem(sys.modules, "app_api", app_api)
    monkeypatch.setattr(desktop_main, "resolve_url", lambda dev: "file:///test")
    monkeypatch.setattr(desktop_main, "runtime_build_status", lambda root: "current")
    monkeypatch.setattr(desktop_main.StartupDiagnostics, "open_default", lambda: log)
    monkeypatch.setattr(desktop_main, "fatal_unshown_window", lambda *args: None)

    assert desktop_main.main([]) == 70
    assert "webview.start.returned_without_window" in log.path.read_text(encoding="utf-8")


def test_main_converts_startup_exception_to_nonzero_and_logs_it(tmp_path: Path, monkeypatch):
    log = StartupDiagnostics(tmp_path / "desktop-startup.log")
    window = _FakeWindow()
    webview, app_api = _fake_modules(window, lambda: None)
    webview.create_window = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("renderer unavailable"))
    monkeypatch.setitem(sys.modules, "webview", webview)
    monkeypatch.setitem(sys.modules, "app_api", app_api)
    monkeypatch.setattr(desktop_main, "resolve_url", lambda dev: "file:///test")
    monkeypatch.setattr(desktop_main, "runtime_build_status", lambda root: "current")
    monkeypatch.setattr(desktop_main.StartupDiagnostics, "open_default", lambda: log)

    assert desktop_main.main([]) == 70
    content = log.path.read_text(encoding="utf-8")
    assert "startup.exception" in content
    assert "renderer unavailable" in content


def test_main_returns_success_after_shown_window_lifecycle(tmp_path: Path, monkeypatch):
    log = StartupDiagnostics(tmp_path / "desktop-startup.log")
    window = _FakeWindow()
    webview, app_api = _fake_modules(window, lambda: window.events.shown.set())
    monkeypatch.setitem(sys.modules, "webview", webview)
    monkeypatch.setitem(sys.modules, "app_api", app_api)
    monkeypatch.setattr(desktop_main, "resolve_url", lambda dev: "file:///test")
    monkeypatch.setattr(desktop_main, "runtime_build_status", lambda root: "current")
    monkeypatch.setattr(desktop_main.StartupDiagnostics, "open_default", lambda: log)
    monkeypatch.setattr(desktop_main, "fatal_unshown_window", lambda *args: None)

    assert desktop_main.main([]) == 0
    assert "webview.start.returned" in log.path.read_text(encoding="utf-8")


def test_official_launcher_keeps_cmd_control_text_ascii_safe():
    launcher = Path(__file__).parents[2] / "启动Go Write.bat"
    payload = launcher.read_bytes()
    assert all(byte < 128 for byte in payload)
    content = payload.decode("ascii")
    assert 'for /d %%D in ("%ROOT%07_*")' in content
    assert '"%ROOT%.venv\\Scripts\\python.exe" desktop\\main.py' in content
    assert "desktop-startup.log" in content
