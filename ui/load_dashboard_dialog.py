"""LoadDashboardDialog — pick a saved dashboard to load (table view)."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget

from ui.entity_table_dialog import EntityTableDialog


class LoadDashboardDialog(EntityTableDialog):
    def __init__(self, parent: QWidget, dashboards: list[dict]):
        super().__init__(parent, dashboards,
                         window_title="Load Dashboard",
                         intro="Select a dashboard to load into the canvas:")

    def _row_for(self, dash: dict):
        name = dash.get("name", "?")
        n = len(dash.get("cards", []))
        # Prefer the user-entered description; fall back to the chart count.
        desc = (dash.get("description") or "").strip() or f"{n} chart{'s' if n != 1 else ''}"
        typ = {"ai": "AI Chat", "manual": "Manual"}.get(dash.get("mode", "manual"),
                                                         dash.get("mode", "Manual"))
        date = (dash.get("updated_at", dash.get("created_at", "")) or "")[:10]
        return name, desc, typ, date

    def _delete(self, dash: dict) -> None:
        from config.dashboard_library import delete_dashboard
        delete_dashboard(dash.get("id", ""))
