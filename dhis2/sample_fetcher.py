"""
sample_fetcher.py — Download SAMPLE data + metadata in raw DHIS2 format after connect.

Replaces the old analytics-based dhis2/fixture_fetcher.py download path. Everything is
saved verbatim (native DHIS2 JSON) under data/<instance_slug>/ via dhis2.data_store.

  • Events  : GET /api/tracker/events  (one sample page per selected program, fields=*)
  • Metadata: dependency export per selected program / dataSet, split into one file per type,
              plus all organisation units (level 1–5, with geometry).

See docs/DATA_EXPORT_REQUIREMENTS.md.
"""
from __future__ import annotations

import threading

from dhis2 import data_store


def _log(msg: str) -> None:
    """Best-effort line into the app's session debug log (logs/debug_*.log)."""
    try:
        from ui.debug_logger import log as _applog
        _applog("SAMPLE", msg)
    except Exception:
        pass

_EVENT_SAMPLE_SIZE = 200   # REQ-EVT-01: ~100–200 sample events per program
_OU_FIELDS = "id,name,level,path,parent[id],geometry"
# Limited event field set — fields=* is heavy enough to time out on large instances.
# Covers everything event_adapter.events_to_rows needs (DEs + the join keys for PA).
_EVENT_FIELDS = ("event,status,program,programStage,orgUnit,orgUnitName,occurredAt,"
                 "enrollment,trackedEntity,geometry,dataValues[dataElement,value]")

# Non-collection keys returned by dependency export that we don't split into files.
_SKIP_META_KEYS = {"system", "date"}


# ── User scope ──────────────────────────────────────────────────────────────

def get_user_root_ous(client) -> list[str]:
    """Root org unit UIDs for the logged-in user (REQ: root OU + DESCENDANTS)."""
    try:
        me = client.get("me.json", params={"fields": "organisationUnits[id]"})
        return [o["id"] for o in me.get("organisationUnits", []) if o.get("id")]
    except Exception:
        return []


# ── Events ────────────────────────────────────────────────────────────────

def _events_list(raw: dict) -> list[dict]:
    """Events array, tolerating version key differences (instances|events)."""
    return raw.get("instances") or raw.get("events") or []


def enrich_events_with_attributes(client, prog_uid: str, raw: dict) -> int:
    """
    Copy each event's tracked-entity ATTRIBUTES (program attributes / PA) onto the event
    so the offline preview can use a PA as a dimension/metric/filter. The new tracker API
    keeps attributes on the tracked entity, not the event, so we fetch them separately and
    attach them in-place. Best-effort: returns how many events were enriched (0 on any issue).

    No-op when events already carry attributes (some API versions include them inline).
    """
    events = _events_list(raw)
    if not events or any(ev.get("attributes") for ev in events):
        return 0
    tei_ids, seen = [], set()
    for ev in events:
        t = ev.get("trackedEntity")
        if t and t not in seen:
            seen.add(t)
            tei_ids.append(t)
    if not tei_ids:
        return 0

    attr_by_tei: dict[str, list] = {}
    for i in range(0, len(tei_ids), 100):       # keep the URL bounded
        batch = tei_ids[i:i + 100]
        try:
            resp = client.get("tracker/trackedEntities", params={
                "trackedEntity": ";".join(batch),
                "program":       prog_uid,
                "orgUnitMode":   "ACCESSIBLE",
                "fields":        "trackedEntity,attributes[attribute,value]",
                "pageSize":      len(batch), "page": 1,
            }, timeout=120)
        except Exception:
            continue
        for te in resp.get("instances") or resp.get("trackedEntities") or []:
            tid = te.get("trackedEntity")
            if tid:
                attr_by_tei[tid] = te.get("attributes", []) or []

    n = 0
    for ev in events:
        attrs = attr_by_tei.get(ev.get("trackedEntity"))
        if attrs and not ev.get("attributes"):
            ev["attributes"] = attrs
            n += 1
    return n


def fetch_events_sample(client, prog_uid: str, root_ous: list[str],
                        base_url: str, page_size: int = _EVENT_SAMPLE_SIZE) -> int:
    """
    Fetch one sample page of events for a program and save the RAW response.
    Returns the number of events saved (0 on failure / no data).
    """
    base = {
        "program":  prog_uid,
        "fields":   _EVENT_FIELDS,
        "pageSize":  page_size,
        "page":      1,
        "order":     "occurredAt:desc",
    }
    # Preferred: scope to the user's root org units + descendants. Some instances reject
    # the configured OUs for tracker (409 "does not exist"); fall back to ACCESSIBLE,
    # which returns events under every org unit the user can see (verified working).
    attempts = []
    if root_ous:
        attempts.append({**base, "orgUnit": root_ous, "orgUnitMode": "DESCENDANTS"})
    attempts.append({**base, "orgUnitMode": "ACCESSIBLE"})

    raw = None
    for params in attempts:
        try:
            raw = client.get("tracker/events", params=params, timeout=120)
            if _events_list(raw):
                break
        except Exception as e:
            _log(f"program {prog_uid}: events attempt failed "
                 f"({params.get('orgUnitMode')}): {type(e).__name__}: {e}")
            raw = None
    if raw is None:
        return 0
    # Attach program-attribute values (PA) so they can be charted offline. Best-effort —
    # a failure here must not lose the events we already fetched.
    try:
        n_enriched = enrich_events_with_attributes(client, prog_uid, raw)
        _log(f"program {prog_uid}: enriched {n_enriched} events with PA attributes")
    except Exception as e:
        _log(f"program {prog_uid}: PA enrich FAILED {type(e).__name__}: {e}")
    # Tolerate version key differences (instances|events) for the count only.
    n = len(_events_list(raw))
    data_store.write_json(data_store.events_path(prog_uid, base_url), raw)
    return n


# ── Metadata ────────────────────────────────────────────────────────────────

def _merge_bundle(into: dict[str, dict], bundle: dict) -> None:
    """Merge a dependency-export bundle into {type: {id: obj}} (dedup by id)."""
    if not isinstance(bundle, dict):
        return
    for type_key, items in bundle.items():
        if type_key in _SKIP_META_KEYS or not isinstance(items, list):
            continue
        bucket = into.setdefault(type_key, {})
        for obj in items:
            uid = obj.get("id")
            if uid and uid not in bucket:
                bucket[uid] = obj


def fetch_metadata_export(client, program_ids: list[str], dataset_ids: list[str],
                          base_url: str) -> dict[str, int]:
    """
    Dependency-export each selected program / dataSet, plus all org units (level 1–5),
    then write one raw file per metadata type. Returns {type: count}.
    """
    merged: dict[str, dict] = {}

    for pid in program_ids:
        try:
            _merge_bundle(merged, client.get(f"programs/{pid}/metadata.json",
                                             params={"skipSharing": "true"}, timeout=120))
        except Exception:
            pass
    for dsid in dataset_ids:
        try:
            _merge_bundle(merged, client.get(f"dataSets/{dsid}/metadata.json",
                                             params={"skipSharing": "true"}, timeout=120))
        except Exception:
            pass

    # Org units: all levels 1–5 with geometry (REQ-META-04). Fetched separately —
    # not part of program/dataSet dependency closures.
    try:
        ou = client.get("organisationUnits.json",
                        params={"fields": _OU_FIELDS, "paging": "false"}, timeout=180)
        for obj in ou.get("organisationUnits", []):
            uid = obj.get("id")
            if uid:
                merged.setdefault("organisationUnits", {})[uid] = obj
    except Exception:
        pass

    # Write one file per type, in native DHIS2 collection shape: {"<type>": [...]}.
    counts: dict[str, int] = {}
    for type_key, bucket in merged.items():
        items = list(bucket.values())
        data_store.write_json(data_store.metadata_path(type_key, base_url),
                              {type_key: items})
        counts[type_key] = len(items)
    return counts


# ── Orchestration ─────────────────────────────────────────────────────────

def download_sample_data(client, base_url: str,
                         program_ids: list[str], dataset_ids: list[str]) -> None:
    """Synchronous: fetch metadata export + a sample of events for each program."""
    data_store.set_active_instance(base_url)
    fetch_metadata_export(client, program_ids, dataset_ids, base_url)

    root_ous = get_user_root_ous(client)
    _log(f"start: {len(program_ids)} programs, root_ous={root_ous or '(none)'}")
    for pid in program_ids:
        try:
            n = fetch_events_sample(client, pid, root_ous, base_url)
            _log(f"program {pid}: saved {n} events")
        except Exception as e:
            # isolate per-program failures (REQ-EVT-05) but record why — include the
            # server's response body, which carries the real DHIS2 validation message.
            body = ""
            resp = getattr(e, "response", None)
            if resp is not None:
                try:
                    body = (resp.text or "")[:600]
                except Exception:
                    pass
            _log(f"program {pid}: FAILED {type(e).__name__}: {e} | body={body}")


def download_sample_data_async(client, base_url: str,
                               program_ids: list[str], dataset_ids: list[str]) -> threading.Thread:
    """Non-blocking wrapper — returns the started daemon thread."""
    t = threading.Thread(
        target=download_sample_data,
        args=(client, base_url, program_ids, dataset_ids),
        daemon=True,
    )
    t.start()
    return t
