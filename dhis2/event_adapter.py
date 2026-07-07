"""
event_adapter.py — Read RAW DHIS2 data (tracker events + org units) from data_store
and adapt it to the in-memory fixture shape the preview/aggregation layer expects.

On-disk format is native DHIS2 (see data_store). The browser mock (_mockDhis2Get) and
charts/plugins/*.aggregate_for_dim were written against the legacy "headers/rows" shape
(an analytics/events/query response). Rather than rewrite those, we convert raw events
→ {headers, rows} here, at preview-build time.

Raw tracker event (fields=*, optionally enriched with TEI attributes by sample_fetcher):
  { "event","status","program","programStage","orgUnit","orgUnitName",
    "occurredAt","enrollment","trackedEntity",
    "dataValues":[{"dataElement","value"}, ...],
    "attributes":[{"attribute","value"}, ...] }   # program attributes (PA / TEA)

Program attributes become BARE-uid columns (no stage prefix), matching how DHIS2
event analytics returns a program-attribute dimension. This lets a PA be used as a
chart dimension/metric/filter offline (see _mockDhis2Get + aggregate_for_dim).

Produced fixture (legacy-compatible):
  { "_format":"tracker_events_v1", "_prog_uid","_stage_uid", "_geo":{lvl:[geoFeat]},
    "headers":[{"name":..}], "rows":[[..]] }
"""
from __future__ import annotations

import json

from dhis2 import data_store

# Standard columns emitted first, matching analytics/events/query naming.
_STD_COLS = ["psi", "ps", "eventdate", "ou", "ouname", "longitude", "latitude"]


def _events_array(raw: dict | None) -> list[dict]:
    """Extract the events list, tolerating version key differences (instances|events)."""
    if not isinstance(raw, dict):
        return raw if isinstance(raw, list) else []
    for key in ("instances", "events"):
        arr = raw.get(key)
        if isinstance(arr, list):
            return arr
    return []


def events_to_rows(raw: dict | list, stage_uid: str = "") -> dict:
    """
    Convert raw tracker events → {headers, rows, _stage_uid}.

    DE columns are named "{programStage}.{dataElement}" (same as analytics/events/query),
    so both _mockDhis2Get.findCol() and aggregate_for_dim() resolve them.
    """
    events = _events_array(raw) if isinstance(raw, dict) else (raw or [])

    de_cols: list[str] = []          # ordered "{stage}.{de}" column names
    seen_cols: set[str] = set()
    attr_cols: list[str] = []        # ordered bare program-attribute uid columns
    seen_attr: set[str] = set()
    row_dicts: list[dict] = []

    for ev in events:
        ps = ev.get("programStage") or stage_uid or ""
        # Event point coordinates (for the bubble map's "Event" coordinate source).
        lon = lat = ""
        geom = ev.get("geometry") or {}
        if isinstance(geom, dict) and geom.get("type") == "Point":
            co = geom.get("coordinates") or []
            if isinstance(co, (list, tuple)) and len(co) >= 2:
                lon, lat = co[0], co[1]
        rd = {
            "psi":       ev.get("event", ""),
            "ps":        ps,
            "eventdate": ev.get("occurredAt") or ev.get("eventDate") or "",
            "ou":        ev.get("orgUnit", ""),
            "ouname":    ev.get("orgUnitName", ""),
            "longitude": lon,
            "latitude":  lat,
        }
        for dv in ev.get("dataValues", []) or []:
            de = dv.get("dataElement")
            if not de:
                continue
            col = f"{ps}.{de}"
            if col not in seen_cols:
                seen_cols.add(col)
                de_cols.append(col)
            rd[col] = dv.get("value", "")
        # Program attributes (PA / TEA) → BARE-uid columns. The new tracker API keeps
        # attributes on the tracked entity, so sample_fetcher copies them onto each event.
        for at in ev.get("attributes", []) or []:
            a = at.get("attribute")
            if not a:
                continue
            if a not in seen_attr:
                seen_attr.add(a)
                attr_cols.append(a)
            rd[a] = at.get("value", "")
        row_dicts.append(rd)

    col_order = _STD_COLS + de_cols + attr_cols
    headers = [{"name": c} for c in col_order]
    rows = [[rd.get(c, "") for c in col_order] for rd in row_dicts]

    # Pick a representative stage if none supplied (first event's stage).
    resolved_stage = stage_uid or (row_dicts[0]["ps"] if row_dicts else "")
    return {"headers": headers, "rows": rows, "_stage_uid": resolved_stage}


def geo_from_orgunits(ou_list: list[dict] | None) -> dict[str, list]:
    """
    Convert raw organisationUnits (with geometry) → geoFeatures-shaped dict keyed by level:
      { "2": [{id, na, le, pi, ty, co}, ...], "3": [...] }
    ty: 1 = Point, 2 = Polygon/MultiPolygon (depth handled by the map plugin).
    co: JSON string of geometry.coordinates.
    """
    by_level: dict[str, list] = {}
    for ou in ou_list or []:
        geom = ou.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        if not gtype or coords is None:
            continue
        level = ou.get("level")
        if level is None and ou.get("path"):
            level = ou["path"].strip("/").count("/") + 1
        if level is None:
            continue
        feat = {
            "id": ou.get("id", ""),
            "na": ou.get("name") or ou.get("displayName", ""),
            "le": int(level),
            "pi": (ou.get("parent") or {}).get("id", ""),
            "ty": 1 if gtype == "Point" else 2,
            "co": json.dumps(coords),
        }
        by_level.setdefault(str(int(level)), []).append(feat)
    return by_level


def build_fixture(prog_uid: str, stage_uid: str = "",
                  base_url: str | None = None) -> dict | None:
    """
    Load raw events + org units from data_store (active instance by default) and
    return a legacy-compatible fixture dict, or None if no event data on disk.
    """
    raw = data_store.load_events(prog_uid, base_url)
    if raw is None:
        return None
    conv = events_to_rows(raw, stage_uid)
    if not conv["rows"]:
        return None

    ou_meta = data_store.load_metadata("organisationUnits", base_url)
    ou_list = (ou_meta or {}).get("organisationUnits") if isinstance(ou_meta, dict) else ou_meta
    geo = geo_from_orgunits(ou_list)

    return {
        "_format":    "tracker_events_v1",
        "_prog_uid":  prog_uid,
        "_stage_uid": conv["_stage_uid"],
        "_geo":       geo,
        "headers":    conv["headers"],
        "rows":       conv["rows"],
    }
