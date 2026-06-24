"""
Saved chart template configs — persisted to config/saved_templates.json.
Each entry is a chart config dict with an extra "name" and "created_at" field.
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

_FILE = Path(__file__).parent / "saved_templates.json"


def load_templates() -> list[dict]:
    if not _FILE.exists():
        return []
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_template(config: dict, name: str) -> dict:
    """Save or overwrite a template by name. Returns the saved entry."""
    templates = [t for t in load_templates() if t.get("name") != name]
    entry = {
        "name": name,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        **{k: v for k, v in config.items() if k not in ("card_id", "n", "html_path")},
    }
    templates.insert(0, entry)
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(templates, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


def delete_template(name: str) -> None:
    templates = [t for t in load_templates() if t.get("name") != name]
    _FILE.write_text(json.dumps(templates, ensure_ascii=False, indent=2), encoding="utf-8")
