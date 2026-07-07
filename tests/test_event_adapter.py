"""
Unit tests for dhis2.event_adapter — converting RAW DHIS2 tracker events +
org units into the legacy {headers, rows, _geo} fixture shape.

No network. Run: python -m pytest tests/test_event_adapter.py -v
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dhis2 import event_adapter as ea
from dhis2 import data_store


STAGE = "STAGEuid1234"
DE_OPT = "DEoptuid5678"   # option-set DE
DE_NUM = "DEnumuid9012"   # numeric DE
OU1 = "OUaaaaaaaaa"
OU2 = "OUbbbbbbbbb"


def _raw_events(key="instances"):
    return {
        key: [
            {
                "event": "EVT0000001x", "status": "COMPLETED",
                "program": "PROGuid0001", "programStage": STAGE,
                "orgUnit": OU1, "orgUnitName": "Clinic A",
                "occurredAt": "2024-01-15T00:00:00.000",
                "dataValues": [
                    {"dataElement": DE_OPT, "value": "PF"},
                    {"dataElement": DE_NUM, "value": "12"},
                ],
            },
            {
                "event": "EVT0000002x", "status": "ACTIVE",
                "program": "PROGuid0001", "programStage": STAGE,
                "orgUnit": OU2, "orgUnitName": "Clinic B",
                "occurredAt": "2024-02-20T00:00:00.000",
                "dataValues": [
                    {"dataElement": DE_OPT, "value": "PV"},
                ],
            },
        ]
    }


# ── events_to_rows ──────────────────────────────────────────────────────────

def test_events_to_rows_key_variants():
    # REQ-EVT-08: tolerate instances|events
    for key in ("instances", "events"):
        conv = ea.events_to_rows(_raw_events(key), STAGE)
        assert len(conv["rows"]) == 2, key


def test_events_to_rows_standard_columns_present():
    conv = ea.events_to_rows(_raw_events(), STAGE)
    names = [h["name"] for h in conv["headers"]]
    for col in ("psi", "ps", "eventdate", "ou", "ouname"):
        assert col in names


def test_events_to_rows_de_columns_stage_prefixed():
    conv = ea.events_to_rows(_raw_events(), STAGE)
    names = [h["name"] for h in conv["headers"]]
    assert f"{STAGE}.{DE_OPT}" in names
    assert f"{STAGE}.{DE_NUM}" in names


def test_events_to_rows_values_aligned():
    conv = ea.events_to_rows(_raw_events(), STAGE)
    names = [h["name"] for h in conv["headers"]]
    opt_idx = names.index(f"{STAGE}.{DE_OPT}")
    num_idx = names.index(f"{STAGE}.{DE_NUM}")
    ou_idx = names.index("ou")
    # row 0 has both DEs
    assert conv["rows"][0][opt_idx] == "PF"
    assert conv["rows"][0][num_idx] == "12"
    assert conv["rows"][0][ou_idx] == OU1
    # row 1 missing the numeric DE → blank, not crash
    assert conv["rows"][1][opt_idx] == "PV"
    assert conv["rows"][1][num_idx] == ""


def test_events_to_rows_eventdate_iso_preserved():
    # adapter keeps ISO occurredAt; period bucketing happens downstream
    conv = ea.events_to_rows(_raw_events(), STAGE)
    names = [h["name"] for h in conv["headers"]]
    ed = names.index("eventdate")
    assert conv["rows"][0][ed].startswith("2024-01")


def test_events_to_rows_resolves_stage_from_event_when_blank():
    conv = ea.events_to_rows(_raw_events(), "")
    assert conv["_stage_uid"] == STAGE


def test_events_to_rows_empty():
    conv = ea.events_to_rows({"instances": []}, STAGE)
    assert conv["rows"] == []


# ── geo_from_orgunits ─────────────────────────────────────────────────────────

def test_geo_from_orgunits_polygon_and_point():
    ous = [
        {"id": OU1, "name": "Prov", "level": 2, "parent": {"id": "ROOT0000000"},
         "geometry": {"type": "Polygon", "coordinates": [[[1, 2], [3, 4], [5, 6]]]}},
        {"id": OU2, "name": "HC", "level": 4, "parent": {"id": OU1},
         "geometry": {"type": "Point", "coordinates": [10.0, 20.0]}},
        {"id": "OUnogeom999", "name": "NoGeo", "level": 3, "parent": {"id": OU1}},
    ]
    geo = ea.geo_from_orgunits(ous)
    assert set(geo.keys()) == {"2", "4"}            # no-geometry OU skipped
    poly = geo["2"][0]
    assert poly["ty"] == 2 and poly["pi"] == "ROOT0000000"
    assert json.loads(poly["co"]) == [[[1, 2], [3, 4], [5, 6]]]
    assert geo["4"][0]["ty"] == 1                    # Point


def test_geo_level_derived_from_path_when_missing():
    ous = [{"id": OU1, "name": "X", "path": "/ROOT/PROV/DIST",
            "parent": {"id": "PROV"},
            "geometry": {"type": "Point", "coordinates": [1, 2]}}]
    geo = ea.geo_from_orgunits(ous)
    assert "3" in geo   # /ROOT/PROV/DIST → level 3


# ── build_fixture (round-trip through data_store) ─────────────────────────────

def test_build_fixture_roundtrip(tmp_path, monkeypatch):
    base_url = "https://example.org/hmis"
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance(base_url)

    data_store.write_json(data_store.events_path("PROGuid0001"), _raw_events())
    data_store.write_json(
        data_store.metadata_path("organisationUnits"),
        {"organisationUnits": [
            {"id": OU1, "name": "Prov", "level": 2, "parent": {"id": "ROOT0000000"},
             "geometry": {"type": "Polygon", "coordinates": [[[1, 2], [3, 4], [5, 6]]]}},
        ]},
    )

    fx = ea.build_fixture("PROGuid0001", STAGE)
    assert fx is not None
    assert fx["_format"] == "tracker_events_v1"
    assert fx["_prog_uid"] == "PROGuid0001"
    assert fx["_stage_uid"] == STAGE
    assert len(fx["rows"]) == 2
    assert "2" in fx["_geo"]


def test_build_fixture_none_when_no_events(tmp_path, monkeypatch):
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://example.org/hmis")
    assert ea.build_fixture("MISSINGprog1", STAGE) is None


# ── Program-attribute (PA / TEA) columns — offline PA support (user 2026-06-26) ──

SEX_TEA = "DmuazFb368B"   # real "Sex" attribute uid from logs


def _raw_events_with_attrs():
    return {"instances": [
        {"event": "EVT0000001x", "programStage": STAGE, "trackedEntity": "TEI00000001",
         "orgUnit": OU1, "occurredAt": "2024-01-15T00:00:00.000",
         "dataValues": [{"dataElement": DE_OPT, "value": "PF"}],
         "attributes": [{"attribute": SEX_TEA, "value": "M"}]},
        {"event": "EVT0000002x", "programStage": STAGE, "trackedEntity": "TEI00000002",
         "orgUnit": OU2, "occurredAt": "2024-02-20T00:00:00.000",
         "dataValues": [{"dataElement": DE_OPT, "value": "PV"}],
         "attributes": [{"attribute": SEX_TEA, "value": "F"}]},
    ]}


def test_attributes_become_bare_uid_columns():
    """REQ-PA-OFFLINE-01: event attributes (PA) become BARE-uid columns with their values."""
    conv = ea.events_to_rows(_raw_events_with_attrs(), STAGE)
    names = [h["name"] for h in conv["headers"]]
    assert SEX_TEA in names, f"PA column missing: {names}"
    # No stage-prefixed variant for a PA
    assert f"{STAGE}.{SEX_TEA}" not in names
    sex_idx = names.index(SEX_TEA)
    assert [r[sex_idx] for r in conv["rows"]] == ["M", "F"]


def test_no_attributes_no_extra_columns():
    """REQ-PA-OFFLINE-02: events without attributes produce no PA columns (no regression)."""
    conv = ea.events_to_rows(_raw_events(), STAGE)
    names = [h["name"] for h in conv["headers"]]
    assert SEX_TEA not in names


def test_event_geometry_becomes_lon_lat_columns():
    """REQ-MAP-COORD-02: a Point geometry on an event → longitude/latitude columns
    (so the bubble map's 'Event' coordinate source works offline)."""
    raw = {"instances": [
        {"event": "E1", "programStage": STAGE, "orgUnit": OU1, "occurredAt": "2024-01-01",
         "geometry": {"type": "Point", "coordinates": [106.79, 16.45]},
         "dataValues": [{"dataElement": DE_NUM, "value": "5"}]},
        {"event": "E2", "programStage": STAGE, "orgUnit": OU2, "occurredAt": "2024-01-02",
         "dataValues": [{"dataElement": DE_NUM, "value": "7"}]},   # no geometry
    ]}
    conv = ea.events_to_rows(raw, STAGE)
    names = [h["name"] for h in conv["headers"]]
    assert "longitude" in names and "latitude" in names
    loni, lati = names.index("longitude"), names.index("latitude")
    assert conv["rows"][0][loni] == 106.79 and conv["rows"][0][lati] == 16.45
    assert conv["rows"][1][loni] == "" and conv["rows"][1][lati] == ""
