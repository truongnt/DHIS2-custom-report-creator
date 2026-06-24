"""
Preview window — delegates to preview_server (local HTTP + browser).
Kept as a thin wrapper so chart_editor_panel.py imports stay the same.
"""
from ui.preview_server import update_preview, _browser_opened, PORT

__all__ = ["update_preview"]
