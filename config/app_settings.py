"""
app_settings.py — small app-wide settings store as a JSON file in the app folder.

Replaces QSettings (which on Windows writes to the registry) so all persisted state is a
plain file next to the other config (config/app_settings.json) — easy to inspect, back up,
or reset. Use for non-sensitive UI preferences only (e.g. the chosen AI model label).
Secrets (passwords, API keys) still go to the Windows Credential Manager, never here.
"""
from __future__ import annotations

import json
from pathlib import Path

_FILE = Path(__file__).parent / "app_settings.json"


def _load() -> dict:
    if not _FILE.exists():
        return {}
    try:
        data = json.loads(_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get(key: str, default=None):
    return _load().get(key, default)


def set(key: str, value) -> None:
    data = _load()
    data[key] = value
    try:
        _FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
