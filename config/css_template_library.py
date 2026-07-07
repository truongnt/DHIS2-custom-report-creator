"""Local storage for user-defined dashboard CSS style templates (REQ-DASH-CSS-10).

Built-in themes live in ui.dashboard_css_dialog.STYLE_TEMPLATES; anything the user
saves from the CSS editor is persisted here and merged into the template dropdown.
"""
from __future__ import annotations
import json
from pathlib import Path

_LIBRARY_FILE = Path(__file__).parent / "css_templates.json"


def load_css_templates() -> dict[str, str]:
    """Return {name: css} of user-saved templates (empty if none / unreadable)."""
    if not _LIBRARY_FILE.exists():
        return {}
    try:
        data = json.loads(_LIBRARY_FILE.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_css_template(name: str, css: str) -> None:
    """Upsert a template by name (blank name/css is ignored)."""
    name = (name or "").strip()
    css = (css or "").strip()
    if not name or not css:
        return
    data = load_css_templates()
    data[name] = css
    _LIBRARY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def delete_css_template(name: str) -> None:
    data = load_css_templates()
    if name in data:
        del data[name]
        _LIBRARY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
