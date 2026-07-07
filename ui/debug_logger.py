"""
debug_logger.py — session log for replaying user actions and capturing JS errors.

Writes to logs/debug_YYYYMMDD_HHMMSS.log in the project root.
Entries are plain-text lines: [HH:MM:SS] SOURCE  message
"""
from __future__ import annotations
import threading
import time
from datetime import datetime
from pathlib import Path

_LOG_DIR  = Path(__file__).parent.parent / "logs"
_log_file: Path | None = None
_lock     = threading.Lock()


def _ensure_file() -> Path:
    global _log_file
    if _log_file is None:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        _log_file = _LOG_DIR / f"debug_{ts}.log"
        _log_file.write_text(
            f"# Auto Report debug log — {datetime.now().isoformat()}\n",
            encoding="utf-8",
        )
    return _log_file


def log(source: str, message: str) -> None:
    """Append one log line. Thread-safe."""
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {source:<12} {message}\n"
    with _lock:
        try:
            _ensure_file().open("a", encoding="utf-8").write(line)
        except Exception:
            pass


def log_action(action: str, detail: str = "") -> None:
    """Log a user UI action."""
    log("UI", f"{action}  {detail}".rstrip())


def log_js(level: str, message: str) -> None:
    """Log a message from the browser JS layer."""
    log(f"JS:{level}", message)


def get_log_path() -> str | None:
    return str(_log_file) if _log_file else None
