"""Persistent JSON store for saved charts (reusable entities like Superset charts)."""
from __future__ import annotations
import json
import uuid
from datetime import datetime
from pathlib import Path

_LIBRARY_FILE = Path(__file__).parent / "chart_library.json"


def load_charts() -> list[dict]:
    if not _LIBRARY_FILE.exists():
        return []
    try:
        return json.loads(_LIBRARY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_chart(chart: dict) -> dict:
    """Save or update a chart. Adds id + created_at if missing. Returns the saved chart."""
    if not chart.get("id"):
        chart = dict(chart, id=uuid.uuid4().hex[:10],
                     created_at=datetime.now().isoformat(timespec="seconds"))
    charts = load_charts()
    idx = next((i for i, c in enumerate(charts) if c.get("id") == chart["id"]), None)
    if idx is not None:
        charts[idx] = chart
    else:
        charts.append(chart)
    _LIBRARY_FILE.write_text(
        json.dumps(charts, indent=2, ensure_ascii=False), encoding="utf-8")
    return chart


def delete_chart(chart_id: str):
    charts = [c for c in load_charts() if c.get("id") != chart_id]
    _LIBRARY_FILE.write_text(
        json.dumps(charts, indent=2, ensure_ascii=False), encoding="utf-8")
