"""
fixture_fetcher.py — Fetch raw DHIS2 event data for a program stage and save
as a local JSON fixture used by the preview/sample chart system.

The fixture contains one row per event with ALL tracker DEs as columns, so any
dimension DE can be used in sample mode without re-fetching from the server.

Fixture format (saved to C:/Temp/test_fixture_{prog_uid}.json):
{
  "_format":     "raw_events_v1",
  "_prog_uid":   "...",
  "_stage_uid":  "...",
  "_fetched_at": "2026-01-01T00:00:00",
  "headers": [{"name": "pe"}, {"name": "ou"}, {"name": "stgUid.deUid"}, ...],
  "rows":    [["202401", "orgUID", "PF", ...], ...]
}
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

FIXTURE_DIR      = Path(__file__).parent.parent / "fixtures"
_MAX_ROWS        = 5000   # safety cap — enough for sample charts
_MAX_DES_PER_REQ = 20     # keep URL under ~4 KB; batch when exceeded


def fixture_path(prog_uid: str, stage_uid: str = "") -> Path:
    if stage_uid:
        return FIXTURE_DIR / f"test_fixture_{prog_uid}_{stage_uid}.json"
    return FIXTURE_DIR / f"test_fixture_{prog_uid}.json"


def _fetch_events_single(
    client, prog_uid: str, stage_uid: str,
    dimensions: list[str], page_size: int,
) -> dict:
    """One GET call to analytics/events/query/{prog_uid}."""
    return client.get(
        f"analytics/events/query/{prog_uid}",
        params={"stage": stage_uid, "dimension": dimensions,
                "pageSize": page_size, "page": 1},
        timeout=120,
    )


def _fetch_events_batched(
    client, prog_uid: str, stage_uid: str,
    de_uids: list[str], ou: str, pe: str,
) -> dict:
    """
    Fetch DEs in batches of _MAX_DES_PER_REQ and join rows by psi (event ID).

    DHIS2 always returns psi as the first column, so it works as a join key.
    Events with no value for a given DE will have "" for that column.
    """
    batches = [de_uids[i:i + _MAX_DES_PER_REQ]
               for i in range(0, len(de_uids), _MAX_DES_PER_REQ)]

    seen_hdr_names: set[str] = set()
    all_hdr_names: list[str] = []   # ordered
    psi_data: dict[str, dict[str, str]] = {}  # psi → {col_name: value}

    for batch in batches:
        dims = ([f"pe:{pe}", f"ou:{ou}"]
                + [f"{stage_uid}.{d}" for d in batch])
        try:
            resp = _fetch_events_single(client, prog_uid, stage_uid, dims, _MAX_ROWS)
        except Exception:
            continue  # skip bad DE batch, keep going

        hdr_names = [h["name"] for h in resp.get("headers", [])]
        rows       = resp.get("rows", [])

        for h in hdr_names:
            if h not in seen_hdr_names:
                seen_hdr_names.add(h)
                all_hdr_names.append(h)

        for row in rows:
            if not row:
                continue
            psi = row[0]
            row_dict = dict(zip(hdr_names, row))
            if psi not in psi_data:
                psi_data[psi] = row_dict
            else:
                psi_data[psi].update(row_dict)

    return {
        "headers": [{"name": n} for n in all_hdr_names],
        "rows": [
            [rd.get(h, "") for h in all_hdr_names]
            for rd in psi_data.values()
        ],
    }


def fetch_and_save(
    client,
    prog_uid:  str,
    stage_uid: str,
    de_uids:   list[str],
    ou:        str = "USER_ORGUNIT",
    pe:        str = "LAST_12_MONTHS",
    on_done:   Callable[[bool, str], None] | None = None,
) -> None:
    """
    Fetch raw events (all supplied DEs) and save fixture to disk.

    Runs synchronously — wrap in a thread if calling from UI.
    Batches automatically when de_uids > _MAX_DES_PER_REQ to avoid URL length errors.
    Calls on_done(success: bool, message: str) when finished.
    """
    try:
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

        if len(de_uids) <= _MAX_DES_PER_REQ:
            dims = ([f"pe:{pe}", f"ou:{ou}"]
                    + [f"{stage_uid}.{d}" for d in de_uids])
            data = _fetch_events_single(client, prog_uid, stage_uid, dims, _MAX_ROWS)
        else:
            data = _fetch_events_batched(client, prog_uid, stage_uid, de_uids, ou, pe)

        # Fetch OU boundary data for map charts (Levels 2–5)
        geo: dict[str, list] = {}
        for level in [2, 3, 4, 5]:
            try:
                feat = client.get(
                    "geoFeatures",
                    params={"ou": f"ou:{ou};LEVEL-{level}",
                            "displayProperty": "NAME", "pr": "false"},
                    timeout=60,
                )
                if isinstance(feat, list) and feat:
                    geo[str(level)] = feat
            except Exception:
                pass

        payload = {
            "_format":     "raw_events_v1",
            "_prog_uid":   prog_uid,
            "_stage_uid":  stage_uid,
            "_fetched_at": datetime.now(timezone.utc).isoformat(),
            "_geo":        geo,
            "headers":     data.get("headers", []),
            "rows":        data.get("rows", []),
        }

        out = fixture_path(prog_uid, stage_uid)
        out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        n = len(payload["rows"])
        if on_done:
            on_done(True, f"Saved {n} events to {out.name}")
    except Exception as exc:
        if on_done:
            on_done(False, str(exc))


def fetch_and_save_async(
    client,
    prog_uid:  str,
    stage_uid: str,
    de_uids:   list[str],
    ou:        str = "USER_ORGUNIT",
    pe:        str = "LAST_12_MONTHS",
    on_done:   Callable[[bool, str], None] | None = None,
) -> threading.Thread:
    """Non-blocking wrapper — returns the started Thread."""
    t = threading.Thread(
        target=fetch_and_save,
        args=(client, prog_uid, stage_uid, de_uids, ou, pe, on_done),
        daemon=True,
    )
    t.start()
    return t


def load_raw_events(prog_uid: str, stage_uid: str = "") -> dict | None:
    """
    Read fixture from disk. Tries stage-specific path first, then prog-only path.
    Returns None if not found or wrong format.
    """
    for fp in [fixture_path(prog_uid, stage_uid), fixture_path(prog_uid)]:
        if not fp.exists():
            continue
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            if data.get("_format") == "raw_events_v1":
                return data
        except Exception:
            pass
    return None


def aggregate_for_dim(
    raw: dict,
    stage_uid: str,
    de_uid:    str,
) -> dict[str, list]:
    """
    Aggregate raw_events_v1 fixture into:
      {
        "labels":   ["Jan 2025", ...],       # periods, formatted
        "datasets": [{"label": "PF", "data": [3,5,...]}, ...]
      }

    Returns {} if the fixture doesn't have the requested DE column.
    """
    import re

    headers = [h["name"] for h in raw.get("headers", [])]
    rows    = raw.get("rows", [])

    # Try explicit pe column first; fall back to eventdate (DHIS2 often omits pe)
    pe_idx = next((i for i, h in enumerate(headers) if h == "pe"), None)
    use_eventdate = False
    if pe_idx is None:
        pe_idx = next((i for i, h in enumerate(headers) if h == "eventdate"), None)
        use_eventdate = (pe_idx is not None)

    cat_hdr = f"{stage_uid}.{de_uid}"
    cat_idx = next((i for i, h in enumerate(headers)
                    if h in (cat_hdr, de_uid)), None)

    if pe_idx is None or cat_idx is None or not rows:
        return {}

    _MONTHS = ["Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"]

    def _to_yyyymm(pe: str) -> str:
        """Convert either '202501' or '2025-01-15 00:00:00.0' to '202501'."""
        if use_eventdate:
            m = re.match(r'^(\d{4})-(\d{2})', pe)
            return (m.group(1) + m.group(2)) if m else pe
        return pe

    def _fmt(pe: str) -> str:
        m = re.match(r'^(\d{4})(\d{2})$', pe)
        return (_MONTHS[int(m.group(2)) - 1] + " " + m.group(1)) if m else pe

    # Count events per (period, category)
    counts: dict[str, dict[str, int]] = {}
    periods_seen: list[str] = []
    for row in rows:
        raw_pe = row[pe_idx]  if pe_idx  < len(row) else ""
        cat    = row[cat_idx] if cat_idx < len(row) else ""
        if not raw_pe or not cat:
            continue
        pe = _to_yyyymm(raw_pe)   # normalize eventdate → YYYYMM if needed
        if pe not in counts:
            counts[pe] = {}
            periods_seen.append(pe)
        counts[pe][cat] = counts[pe].get(cat, 0) + 1

    if not counts:
        return {}

    periods  = sorted(set(periods_seen))
    labels   = [_fmt(p) for p in periods]
    all_cats = sorted({cat for pc in counts.values() for cat in pc})

    datasets = [
        {
            "label": cat,
            "data":  [counts.get(pe, {}).get(cat, 0) for pe in periods],
        }
        for cat in all_cats
        if any(counts.get(pe, {}).get(cat, 0) > 0 for pe in periods)
    ]

    if not datasets:
        return {}

    totals = [sum(ds["data"][i] for ds in datasets) for i in range(len(periods))]
    return {"labels": labels, "datasets": datasets, "totals": totals}
