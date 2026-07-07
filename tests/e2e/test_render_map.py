"""
E2E render test for Area Map — proves the choropleth ACTUALLY draws province polygons
in Leaflet (not just that the HTML mentions geoFeatures). Catches the "map error / blank"
class of bug. Evidence: screenshot + console log under test-evidence/.

Run: pip install -r requirements-dev.txt ; pytest tests/e2e/test_render_map.py -m e2e -s
"""
import pytest

from dhis2 import data_store
from charts.fixed_templates import generate_preview_page

PROG, STAGE, DENUM = "MAPprog0001", "MAPstage001", "MAPdenum001"
PROV1, PROV2 = "PROVaaaaaa1", "PROVbbbbbb2"
DIST1, DIST2 = "DISTaaaaaa1", "DISTbbbbbb2"


def _setup_data(tmp_path, monkeypatch):
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    base = "https://demo.example/hmis"
    data_store.set_active_instance(base)

    def ev(eid, ou, val, date):
        return {"event": eid, "programStage": STAGE, "orgUnit": ou,
                "occurredAt": date, "dataValues": [{"dataElement": DENUM, "value": val}]}

    data_store.write_json(data_store.events_path(PROG), {"instances": [
        ev("E1", DIST1, "10", "2024-01-10T00:00:00"),
        ev("E2", DIST1, "20", "2024-02-10T00:00:00"),
        ev("E3", DIST1, "30", "2024-03-10T00:00:00"),
        ev("E4", DIST2, "5",  "2024-01-12T00:00:00"),
        ev("E5", DIST2, "15", "2024-02-12T00:00:00"),
    ]})
    data_store.write_json(data_store.metadata_path("organisationUnits"), {"organisationUnits": [
        {"id": PROV1, "name": "Province 1", "level": 2, "parent": {"id": "NATION00001"},
         "geometry": {"type": "Polygon", "coordinates": [[[100, 15], [100, 16], [101, 16], [101, 15], [100, 15]]]}},
        {"id": PROV2, "name": "Province 2", "level": 2, "parent": {"id": "NATION00001"},
         "geometry": {"type": "Polygon", "coordinates": [[[101, 15], [101, 16], [102, 16], [102, 15], [101, 15]]]}},
        {"id": DIST1, "name": "District 1", "level": 3, "parent": {"id": PROV1},
         "geometry": {"type": "Point", "coordinates": [100.5, 15.5]}},
        {"id": DIST2, "name": "District 2", "level": 3, "parent": {"id": PROV2},
         "geometry": {"type": "Point", "coordinates": [101.5, 15.5]}},
    ]})


@pytest.mark.e2e
def test_area_map_renders_polygons(tmp_path, monkeypatch, render_map_preview):
    """REQ-MAP-AM-01: ou_level Level 2 → province polygons drawn, no map error."""
    _setup_data(tmp_path, monkeypatch)
    cfg = {
        "plugin_id": "area_map", "title": "E2E Area Map",
        "metrics": [{"uid": DENUM, "name": "Cases", "type": "tracker_numeric",
                     "agg": "SUM", "prog_uid": PROG, "stage_uid": STAGE}],
        "prog_uid": PROG, "stage_uid": STAGE,
        "plugin_options": {"ou_level": "Level 2"},
    }
    html = generate_preview_page(cfg)
    ev = render_map_preview(html, "area_map_level2")

    assert ev["leaflet"], f"no Leaflet container; see {ev['screenshot']}"
    assert ev["w"] > 0 and ev["h"] > 0, f"map has no size; see {ev['screenshot']}"
    assert not ev["err_shown"], f"map error banner: {ev['err_text']!r}; see {ev['screenshot']}"
    assert ev["polygons"] >= 2, (
        f"expected ≥2 province polygons, got {ev['polygons']}; see {ev['screenshot']}"
    )
    assert not ev["severe"], (
        "JS console errors:\n" + "\n".join(e.get("message", "") for e in ev["severe"])
    )


HC1, HC2 = "HCaaaaaaaa1", "HCbbbbbbbb2"


def _setup_point_data(tmp_path, monkeypatch):
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://demo.example/hmis")

    def ev(eid, ou, val, date):
        return {"event": eid, "programStage": STAGE, "orgUnit": ou,
                "occurredAt": date, "dataValues": [{"dataElement": DENUM, "value": val}]}

    data_store.write_json(data_store.events_path(PROG), {"instances": [
        ev("P1", HC1, "10", "2024-01-10T00:00:00"),
        ev("P2", HC1, "20", "2024-02-10T00:00:00"),
        ev("P3", HC2, "7",  "2024-01-12T00:00:00"),
    ]})
    # Level-4 health centres with POINT geometry → bubbles
    data_store.write_json(data_store.metadata_path("organisationUnits"), {"organisationUnits": [
        {"id": HC1, "name": "Health Centre 1", "level": 4, "parent": {"id": "DIST0000001"},
         "geometry": {"type": "Point", "coordinates": [100.5, 15.5]}},
        {"id": HC2, "name": "Health Centre 2", "level": 4, "parent": {"id": "DIST0000002"},
         "geometry": {"type": "Point", "coordinates": [101.5, 16.0]}},
    ]})


@pytest.mark.e2e
def test_point_map_renders_bubbles(tmp_path, monkeypatch, render_map_preview):
    """REQ-MAP-PM-01: ou_level Level 4 → bubbles drawn at point locations, no map error."""
    _setup_point_data(tmp_path, monkeypatch)
    cfg = {
        "plugin_id": "point_map", "title": "E2E Point Map",
        "metrics": [{"uid": DENUM, "name": "Cases", "type": "tracker_numeric",
                     "agg": "SUM", "prog_uid": PROG, "stage_uid": STAGE}],
        "prog_uid": PROG, "stage_uid": STAGE,
        # overlay_levels default is ("Level 2",); our fixture only has level-4 geo, so
        # disable overlay borders to isolate the bubble layer for this test.
        "plugin_options": {"ou_level": "Level 4", "overlay_levels": []},
    }
    html = generate_preview_page(cfg)
    ev = render_map_preview(html, "point_map_level4")

    assert ev["leaflet"], f"no Leaflet container; see {ev['screenshot']}"
    assert ev["w"] > 0 and ev["h"] > 0, f"map has no size; see {ev['screenshot']}"
    assert not ev["err_shown"], f"map error: {ev['err_text']!r}; see {ev['screenshot']}"
    assert ev["polygons"] >= 2, (
        f"expected ≥2 bubbles (circleMarker paths), got {ev['polygons']}; see {ev['screenshot']}"
    )
    assert not ev["severe"], "JS errors:\n" + "\n".join(e.get("message", "") for e in ev["severe"])


def _setup_point_with_borders(tmp_path, monkeypatch):
    """Level-2 provinces (polygons → overlay borders) + level-4 health centres (points → bubbles)."""
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://demo.example/hmis")

    def ev(eid, ou, val, date):
        return {"event": eid, "programStage": STAGE, "orgUnit": ou,
                "occurredAt": date, "dataValues": [{"dataElement": DENUM, "value": val}]}

    data_store.write_json(data_store.events_path(PROG), {"instances": [
        ev("B1", HC1, "10", "2024-01-10T00:00:00"),
        ev("B2", HC2, "7",  "2024-01-12T00:00:00"),
    ]})
    data_store.write_json(data_store.metadata_path("organisationUnits"), {"organisationUnits": [
        {"id": PROV1, "name": "Province 1", "level": 2, "parent": {"id": "NATION00001"},
         "geometry": {"type": "Polygon", "coordinates": [[[100, 15], [100, 16], [101, 16], [101, 15], [100, 15]]]}},
        {"id": PROV2, "name": "Province 2", "level": 2, "parent": {"id": "NATION00001"},
         "geometry": {"type": "Polygon", "coordinates": [[[101, 15], [101, 16], [102, 16], [102, 15], [101, 15]]]}},
        {"id": HC1, "name": "Health Centre 1", "level": 4, "parent": {"id": PROV1},
         "geometry": {"type": "Point", "coordinates": [100.5, 15.5]}},
        {"id": HC2, "name": "Health Centre 2", "level": 4, "parent": {"id": PROV2},
         "geometry": {"type": "Point", "coordinates": [101.5, 15.5]}},
    ]})


@pytest.mark.e2e
def test_point_map_overlay_borders(tmp_path, monkeypatch, render_map_preview):
    """REQ-MAP-PM-OVERLAY-01: overlay_levels draws administrative border lines behind the bubbles."""
    _setup_point_with_borders(tmp_path, monkeypatch)
    cfg = {
        "plugin_id": "point_map", "title": "E2E Point Map + Borders",
        "metrics": [{"uid": DENUM, "name": "Cases", "type": "tracker_numeric",
                     "agg": "SUM", "prog_uid": PROG, "stage_uid": STAGE}],
        "prog_uid": PROG, "stage_uid": STAGE,
        "plugin_options": {"ou_level": "Level 4", "overlay_levels": ["Level 2"]},
    }
    html = generate_preview_page(cfg)
    ev = render_map_preview(html, "point_map_overlay")

    assert ev["leaflet"], f"no Leaflet container; see {ev['screenshot']}"
    assert not ev["err_shown"], f"map error: {ev['err_text']!r}; see {ev['screenshot']}"
    assert not ev["severe"], "JS errors:\n" + "\n".join(e.get("message", "") for e in ev["severe"])
    # 2 bubbles + 2 province border polygons = ≥4 SVG paths (vs 2 with no overlay)
    assert ev["polygons"] >= 4, (
        f"expected bubbles + border lines (≥4 paths), got {ev['polygons']}; see {ev['screenshot']}"
    )


@pytest.mark.e2e
def test_area_map_reload_no_reinit_error(tmp_path, monkeypatch, render_map_preview, _chrome_driver):
    """REQ-MAP-RELOAD-01: re-running loadData (e.g. applying a filter) must NOT raise the
    Leaflet 'Map container is already initialized' error — the map rebuilds cleanly."""
    _setup_data(tmp_path, monkeypatch)
    cfg = {
        "plugin_id": "area_map", "title": "E2E Area Reload",
        "metrics": [{"uid": DENUM, "name": "Cases", "type": "tracker_numeric",
                     "agg": "SUM", "prog_uid": PROG, "stage_uid": STAGE}],
        "prog_uid": PROG, "stage_uid": STAGE,
        "plugin_options": {"ou_level": "Level 2"},
    }
    html = generate_preview_page(cfg)
    render_map_preview(html, "area_map_reload1")          # first render (served + driven)

    d = _chrome_driver
    d.get_log("browser")                                  # drain existing logs
    d.execute_script("loadData();")                       # simulate clicking ↻ Load data
    import time; time.sleep(3)
    msgs = " ".join(e.get("message", "") for e in d.get_log("browser"))
    assert "already initialized" not in msgs.lower(), f"Leaflet re-init error on reload:\n{msgs}"
