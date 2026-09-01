"""Small, safe, persistent diagnostics for the Go Write desktop shell."""
from __future__ import annotations

import json
import os
import sys
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

CONFIG_DIR_ENV = "AI_WRITE_CONFIG_DIR"
DEFAULT_CONFIG_DIRNAME = ".ai-write"
STARTUP_LOG_RELATIVE_PATH = Path("logs") / "desktop-startup.log"
STARTUP_FAILURE_EXIT_CODE = 70
WINDOW_SHOWN_TIMEOUT_SECONDS = 20.0


def resolve_config_root(
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Use the established application config convention without a new authority."""
    configured = (environ if environ is not None else os.environ).get(CONFIG_DIR_ENV)
    if configured:
        return Path(configured)
    return (home if home is not None else Path.home()) / DEFAULT_CONFIG_DIRNAME


def startup_log_path(
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    return resolve_config_root(environ=environ, home=home) / STARTUP_LOG_RELATIVE_PATH


class StartupDiagnostics:
    """Append only fixed, startup-safe facts; never capture environment or app data."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    @classmethod
    def open_default(cls) -> "StartupDiagnostics":
        path = startup_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        return cls(path)

    def record(self, stage: str, **details: Any) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            **details,
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(encoded + "\n")
                handle.flush()

    def record_exception(self, stage: str, exc: BaseException) -> None:
        self.record(
            stage,
            exception_type=type(exc).__name__,
            exception_message=str(exc),
            traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        )


def window_lifecycle_outcome(shown_event: Any, closed_event: Any, timeout: float) -> str:
    """Return an event-driven lifecycle outcome suitable for deterministic tests."""
    if shown_event.wait(timeout):
        return "shown"
    return "closed_before_shown" if closed_event.is_set() else "shown_timeout"


def fatal_unshown_window(
    diagnostics: StartupDiagnostics,
    shown_event: Any,
    closed_event: Any,
    timeout: float = WINDOW_SHOWN_TIMEOUT_SECONDS,
) -> None:
    """Fail closed only when pywebview never emits its documented shown event."""
    outcome = window_lifecycle_outcome(shown_event, closed_event, timeout)
    if outcome == "shown":
        return
    diagnostics.record("window.lifecycle_failed", outcome=outcome, timeout_seconds=timeout)
    diagnostics.record("process.exit", reason=outcome, exit_code=STARTUP_FAILURE_EXIT_CODE)
    # webview.start blocks the main thread. A daemon thread is the only safe way to
    # turn a renderer that never creates a native window into an observable failure.
    os._exit(STARTUP_FAILURE_EXIT_CODE)


def runtime_facts() -> dict[str, str]:
    return {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
    }
