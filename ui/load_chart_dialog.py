"""LoadChartDialog — pick a saved chart to open for editing (table view)."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget

from ui.entity_table_dialog import EntityTableDialog


def _summarize_chart(chart: dict) -> str:
    """Short description of what a chart shows: its metric(s) + program/source."""
    metrics = chart.get("metrics") or chart.get("de_sources") or []
    names = [m.get("name", "") for m in metrics if m.get("name")]
    desc = ", ".join(names)
    src = chart.get("source") or {}
    prog = src.get("prog_name") or (metrics[0].get("prog_name") if metrics else "")
    if prog:
        desc = f"{desc} · {prog}" if desc else prog
    return desc or chart.get("title", "")


class LoadChartDialog(EntityTableDialog):
    def __init__(self, parent: QWidget, charts: list[dict]):
        super().__init__(parent, charts,
                         window_title="Open Chart",
                         intro="Select a chart to open for editing:")

    def _row_for(self, chart: dict):
        name = chart.get("name") or chart.get("title", "?")
        # Prefer the user-entered description; fall back to a derived metric summary.
        desc = (chart.get("description") or "").strip() or _summarize_chart(chart)
        typ = chart.get("template_label", "") or chart.get("plugin_id", "")
        date = (chart.get("created_at", "") or "")[:10]
        return name, desc, typ, date

    def _delete(self, chart: dict) -> None:
        from config.chart_library import delete_chart
        delete_chart(chart.get("id", ""))
