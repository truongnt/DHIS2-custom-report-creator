"""sample_fetcher PA enrichment — attach tracked-entity attributes (program
attributes) onto sample events so they can be charted offline.

Offline PA support (user 2026-06-26: "phải lấy hết cả PA của prog"). No network.
"""
import pytest

from dhis2 import sample_fetcher as sf

SEX = "DmuazFb368B"


class _FakeClient:
    """Returns a canned trackedEntities response and records the calls made."""
    def __init__(self, te_payload):
        self._te = te_payload
        self.calls = []

    def get(self, path, params=None, timeout=None):
        self.calls.append((path, params))
        return self._te


def _events():
    return {"instances": [
        {"event": "E1", "trackedEntity": "TEI1", "dataValues": []},
        {"event": "E2", "trackedEntity": "TEI2", "dataValues": []},
        {"event": "E3", "trackedEntity": "TEI1", "dataValues": []},  # shares TEI1
    ]}


def test_enrich_attaches_attributes_to_each_event():
    """REQ-PA-OFFLINE-03: each event gets its TEI's attributes attached in-place."""
    te = {"instances": [
        {"trackedEntity": "TEI1", "attributes": [{"attribute": SEX, "value": "M"}]},
        {"trackedEntity": "TEI2", "attributes": [{"attribute": SEX, "value": "F"}]},
    ]}
    raw = _events()
    n = sf.enrich_events_with_attributes(_FakeClient(te), "PROG1", raw)
    assert n == 3
    vals = [ev["attributes"][0]["value"] for ev in raw["instances"]]
    assert vals == ["M", "F", "M"]   # TEI1→M, TEI2→F, TEI1→M


def test_enrich_noop_when_already_present():
    """REQ-PA-OFFLINE-04: if events already carry attributes, no fetch is made."""
    raw = {"instances": [
        {"event": "E1", "trackedEntity": "TEI1",
         "attributes": [{"attribute": SEX, "value": "M"}]}]}
    client = _FakeClient({"instances": []})
    n = sf.enrich_events_with_attributes(client, "PROG1", raw)
    assert n == 0
    assert client.calls == [], "must not call the API when attributes already present"


def test_enrich_handles_no_tei():
    """REQ-PA-OFFLINE-05: events without trackedEntity are tolerated (event programs)."""
    raw = {"instances": [{"event": "E1", "dataValues": []}]}
    n = sf.enrich_events_with_attributes(_FakeClient({"instances": []}), "PROG1", raw)
    assert n == 0


# ── Event-fetch params (regression: live 409 "Org unit ... does not exist") ──────

import pytest
from requests.exceptions import HTTPError


class _Resp:
    def __init__(self, status, text=""):
        self.status_code = status
        self.text = text


class _OUFakeClient:
    """409s on DESCENDANTS (mimics the live instance), serves events on ACCESSIBLE."""
    def __init__(self):
        self.event_calls = []
        self.te_calls = []

    def get(self, path, params=None, timeout=None):
        params = params or {}
        if path == "tracker/events":
            self.event_calls.append(params)
            if params.get("orgUnitMode") == "DESCENDANTS":
                err = HTTPError("409")
                err.response = _Resp(409, '{"message":"Org unit ... does not exist"}')
                raise err
            # ACCESSIBLE → one event with a tracked entity
            return {"instances": [
                {"event": "E1", "programStage": "STG1", "trackedEntity": "TEI1",
                 "orgUnit": "OU1", "occurredAt": "2024-01-10T00:00:00", "dataValues": []}]}
        if path == "tracker/trackedEntities":
            self.te_calls.append(params)
            return {"instances": [
                {"trackedEntity": "TEI1", "attributes": [{"attribute": SEX, "value": "M"}]}]}
        return {}


def test_events_fall_back_to_accessible_on_ou_409(tmp_path, monkeypatch):
    """REQ-PA-OFFLINE-07: a DESCENDANTS 409 must fall back to ACCESSIBLE, not lose the program."""
    from dhis2 import data_store
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://demo.example/hmis")
    client = _OUFakeClient()
    n = sf.fetch_events_sample(client, "PROG1", ["ROOT1"], "https://demo.example/hmis")
    assert n == 1, "should have saved the ACCESSIBLE result after DESCENDANTS 409"
    modes = [c.get("orgUnitMode") for c in client.event_calls]
    assert modes == ["DESCENDANTS", "ACCESSIBLE"], f"expected fallback order, got {modes}"
    # PA attached + persisted
    saved = data_store.load_events("PROG1")
    assert saved["instances"][0]["attributes"][0]["value"] == "M"


def test_enrich_uses_semicolon_separator():
    """REQ-PA-OFFLINE-08: TEI ids must be joined with ';' (comma/repeat return 0 live)."""
    client = _OUFakeClient()
    raw = {"instances": [
        {"event": "E1", "trackedEntity": "TEIaaa", "dataValues": []},
        {"event": "E2", "trackedEntity": "TEIbbb", "dataValues": []}]}
    sf.enrich_events_with_attributes(client, "PROG1", raw)
    assert client.te_calls, "trackedEntities must be queried"
    assert client.te_calls[0]["trackedEntity"] == "TEIaaa;TEIbbb"
    assert client.te_calls[0]["orgUnitMode"] == "ACCESSIBLE"
    assert client.te_calls[0]["program"] == "PROG1"
