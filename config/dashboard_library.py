"""Local storage for saved dashboard configurations."""
from __future__ import annotations
import json
import uuid
from datetime import datetime
from pathlib import Path

_LIBRARY_FILE = Path(__file__).parent / "dashboard_library.json"


def load_dashboards() -> list[dict]:
    """Return list of saved dashboard dicts."""
    if not _LIBRARY_FILE.exists():
        return []
    try:
        return json.loads(_LIBRARY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_dashboard(name: str, cards: list[dict], mode: str = "manual",
                   chat_history: list[dict] | None = None,
                   filters: dict | None = None,
                   description: str = "",
                   custom_css: str = "") -> dict:
    """Save a dashboard by name (upserts on name). Returns saved entry.

    mode         : "manual" | "ai" — which builder produced it (REQ-DASH-03).
    chat_history : optional conversation log, persisted only for AI dashboards.
    filters      : optional shared OU/Period filter defaults (REQ-DASH-FILTER).
    description  : optional free-text shown in the Open list (REQ-UI-LOAD-02).
    custom_css   : optional dashboard-level CSS applied to the whole page (REQ-DASH-CSS).
    """
    dashboards = load_dashboards()
    existing = next((d for d in dashboards if d.get("name") == name), None)
    entry = {
        "id": existing["id"] if existing else uuid.uuid4().hex[:10],
        "name": name,
        "description": description,
        "mode": mode,
        "cards": cards,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if filters is not None:
        entry["filters"] = filters
    if chat_history is not None:
        entry["chat_history"] = chat_history
    if custom_css:
        entry["custom_css"] = custom_css
    if not existing:
        entry["created_at"] = entry["updated_at"]
    else:
        entry["created_at"] = existing.get("created_at", entry["updated_at"])
        dashboards.remove(existing)
    dashboards.append(entry)
    _LIBRARY_FILE.write_text(
        json.dumps(dashboards, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return entry


def delete_dashboard(dashboard_id: str) -> None:
    dashboards = [d for d in load_dashboards() if d.get("id") != dashboard_id]
    _LIBRARY_FILE.write_text(
        json.dumps(dashboards, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get_dashboard(name: str) -> dict | None:
    return next((d for d in load_dashboards() if d.get("name") == name), None)


# Dashboard-specific keys a card owns regardless of its source chart — placement /
# sizing on the canvas. Everything else (plugin_options, metrics, dimensions, title…)
# is chart content and is refreshed from the library on sync.
_CARD_LAYOUT_KEYS = ("col_width", "layout")


def sync_cards_with_charts(cards: list[dict], charts: list[dict]) -> list[dict]:
    """Refresh each card's content from its source chart (matched by ``id``) so a
    dashboard always reflects the latest chart options at preview / export / deploy
    time, while keeping the card's own canvas layout.

    A card whose ``id`` has no match in ``charts`` (source chart deleted, or an
    AI-generated card with no library entry) is returned unchanged.
    """
    by_id = {c.get("id"): c for c in charts if c.get("id")}
    out: list[dict] = []
    for card in cards:
        src = by_id.get(card.get("id"))
        if not src:
            out.append(card)
            continue
        merged = dict(src)                       # latest chart content
        for k in _CARD_LAYOUT_KEYS:              # keep dashboard placement / sizing
            if k in card:
                merged[k] = card[k]
        out.append(merged)
    return out
