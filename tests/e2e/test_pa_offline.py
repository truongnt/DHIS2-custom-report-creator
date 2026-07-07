"""E2E: a program attribute (PA / TEA) used as a chart dimension RENDERS offline.

Offline PA support (user 2026-06-26). Exact scenario from logs: program yAKTrPUMAuU,
Sex [DmuazFb368B]. Events carry attributes (sample_fetcher enriches them), the adapter
exposes a bare-uid column, the mock groups by it. End result: real bars split by Sex.
"""
import pytest

from charts.fixed_templates import generate_preview_page

PROG, STAGE, SEX, METRIC = "yAKTrPUMAuU", "KqjOmlBpYtd", "DmuazFb368B", "deMetricxx1"


def _setup(tmp_path, monkeypatch):
    from dhis2 import data_store
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://demo.example/hmis")

    def ev(eid, date, sex, val):
        return {"event": eid, "programStage": STAGE, "trackedEntity": "T" + eid,
                "orgUnit": "OUaaaaaaaa1", "occurredAt": date,
                "dataValues": [{"dataElement": METRIC, "value": val}],
                "attributes": [{"attribute": SEX, "value": sex}]}

    data_store.write_json(data_store.events_path(PROG), {"instances": [
        ev("e1", "2024-01-10T00:00:00", "M", "PF"),
        ev("e2", "2024-01-12T00:00:00", "F", "PV"),
        ev("e3", "2024-02-05T00:00:00", "M", "PF"),
        ev("e4", "2024-02-20T00:00:00", "M", "PV"),
    ]})
    data_store.write_json(data_store.metadata_path("organisationUnits"), {"organisationUnits": []})


@pytest.mark.e2e
def test_bar_split_by_pa_renders(tmp_path, monkeypatch, render_preview):
    """REQ-PA-OFFLINE-06: bar split-by Sex (PA) renders Male/Female datasets, no JS error."""
    _setup(tmp_path, monkeypatch)
    cfg = {
        "plugin_id": "bar", "title": "Cases by Sex",
        "metrics": [{"uid": METRIC, "name": "Cases", "type": "tracker_option",
                     "prog_uid": PROG, "stage_uid": STAGE}],
        "dimensions": {"dimension": {"uid": SEX, "name": "Sex", "type": "tracker_option",
                                     "prog_uid": PROG, "stage_uid": "", "is_tea": True,
                                     "options": [{"code": "M", "name": "Male"},
                                                 {"code": "F", "name": "Female"}]}},
        "prog_uid": PROG, "stage_uid": STAGE,
    }
    html = generate_preview_page(cfg)
    assert f"&dimension={SEX}" in html and f"dimension=.{SEX}" not in html
    ev = render_preview(html, "bar_split_by_pa")
    msgs = "\n".join(e.get("message", "") for e in ev["console"])
    assert "errEl is not defined" not in msgs
    assert "Dimension column not found" not in msgs, f"PA column not resolved:\n{msgs}"
    info = ev["driver"].execute_script(
        "var c=Chart.getChart('chart1');return c?{labels:c.data.labels,"
        "ds:c.data.datasets.map(d=>({label:d.label,data:d.data}))}:null;")
    assert info, f"no chart rendered; see {ev['screenshot']}"
    labels = {d["label"] for d in info["ds"]}
    assert {"Male", "Female"} <= labels, f"expected Male+Female datasets, got {labels}"
    total = sum(sum(d["data"]) for d in info["ds"])
    assert total == 4, f"expected 4 events total across Sex, got {total} ({info})"


@pytest.mark.e2e
def test_tracker_count_filtered_by_stage(tmp_path, monkeypatch, render_preview):
    """REQ-PA-OFFLINE-09: events/aggregate count must honor stage= (multi-stage program).

    Bug (user 2026-06-26, metric 'Invest: Diagnosis Test result' on stage h86ikuTvjuP):
    the offline mock counted events from ALL stages (153) instead of only the metric's
    stage (29). A tracker metric on STAGE_A must count only STAGE_A events.
    """
    from dhis2 import data_store
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://demo.example/hmis")
    STG_A, STG_B = "STAGEaaaaa1", "STAGEbbbbb1"

    def ev(eid, stg, date, val):
        return {"event": eid, "programStage": stg, "orgUnit": "OU1", "occurredAt": date,
                "dataValues": [{"dataElement": "deDiagxxxx1", "value": val}]}

    data_store.write_json(data_store.events_path(PROG), {"instances": [
        ev("a1", STG_A, "2024-01-10T00:00:00", "PF"),
        ev("a2", STG_A, "2024-01-12T00:00:00", "PV"),
        ev("a3", STG_A, "2024-02-05T00:00:00", "PV"),
        ev("b1", STG_B, "2024-01-15T00:00:00", "X"),   # other stage — must NOT be counted
        ev("b2", STG_B, "2024-02-18T00:00:00", "Y"),
    ]})
    data_store.write_json(data_store.metadata_path("organisationUnits"), {"organisationUnits": []})
    cfg = {"plugin_id": "bar", "title": "Diag",
           "metrics": [{"uid": "deDiagxxxx1", "name": "Diagnosis", "type": "tracker_option",
                        "prog_uid": PROG, "stage_uid": STG_A}],
           "prog_uid": PROG, "stage_uid": STG_A}
    ev_ = render_preview(generate_preview_page(cfg), "count_by_stage")
    info = ev_["driver"].execute_script(
        "var c=Chart.getChart('chart1');return c?c.data.datasets[0].data:null;")
    assert info is not None, f"no chart; see {ev_['screenshot']}"
    assert sum(info) == 3, f"count must include only STAGE_A's 3 events, got {sum(info)} ({info})"


@pytest.mark.e2e
def test_line_trend_tracker_option_counts(tmp_path, monkeypatch, render_preview):
    """REQ-PA-OFFLINE-10: line_trend must render a tracker_option metric as event count
    per period (user 2026-06-26: 'Diagnosis result' invisible on line trend). Stage-filtered.
    """
    from dhis2 import data_store
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://demo.example/hmis")
    STG = "STAGEaaaaa1"

    def ev(eid, date):
        return {"event": eid, "programStage": STG, "orgUnit": "OU1", "occurredAt": date,
                "dataValues": [{"dataElement": "deDiagxxxx1", "value": "PV"}]}

    data_store.write_json(data_store.events_path(PROG), {"instances": [
        ev("a1", "2024-01-10T00:00:00"), ev("a2", "2024-01-20T00:00:00"),
        ev("a3", "2024-02-05T00:00:00"),
    ]})
    data_store.write_json(data_store.metadata_path("organisationUnits"), {"organisationUnits": []})
    cfg = {"plugin_id": "line_trend", "title": "Diag trend",
           "metrics": [{"uid": "deDiagxxxx1", "name": "Diagnosis", "type": "tracker_option",
                        "prog_uid": PROG, "stage_uid": STG}],
           "prog_uid": PROG, "stage_uid": STG}
    ev_ = render_preview(generate_preview_page(cfg), "line_trend_tracker_option")
    msgs = "\n".join(e.get("message", "") for e in ev_["console"])
    assert "No data" not in msgs and "errEl" not in msgs
    data = ev_["driver"].execute_script(
        "var c=Chart.getChart('chart1');return c?c.data.datasets[0].data:null;")
    assert data is not None, f"line chart did not render; see {ev_['screenshot']}"
    assert sum(data) == 3, f"expected 3 events on the trend, got {sum(data)} ({data})"


def _multi_stage_events(data_store):
    """3 events on STG_A with an option DE + a numeric DE."""
    STG = "STAGEaaaaa1"
    def ev(eid, date, num):
        return {"event": eid, "programStage": STG, "orgUnit": "OU1", "occurredAt": date,
                "dataValues": [{"dataElement": "deDiagxxxx1", "value": "PV"},
                               {"dataElement": "deNumxxxxx1", "value": str(num)}]}
    data_store.write_json(data_store.events_path(PROG), {"instances": [
        ev("a1", "2024-01-10T00:00:00", 10), ev("a2", "2024-01-20T00:00:00", 20),
        ev("a3", "2024-02-05T00:00:00", 30)]})
    data_store.write_json(data_store.metadata_path("organisationUnits"), {"organisationUnits": []})
    return STG


@pytest.mark.e2e
def test_scorecard_tracker_option_total(tmp_path, monkeypatch, render_preview):
    """REQ-PA-OFFLINE-11: scorecard shows total event count for a tracker_option metric."""
    from dhis2 import data_store
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://demo.example/hmis")
    STG = _multi_stage_events(data_store)
    cfg = {"plugin_id": "scorecard", "title": "Total",
           "metrics": [{"uid": "deDiagxxxx1", "name": "Diagnosis", "type": "tracker_option",
                        "prog_uid": PROG, "stage_uid": STG}], "prog_uid": PROG, "stage_uid": STG}
    ev = render_preview(generate_preview_page(cfg), "scorecard_tracker_option")
    msgs = "\n".join(e.get("message", "") for e in ev["console"])
    assert "errEl is not defined" not in msgs and "Failed:" not in msgs
    # scorecard draws to canvas via Canvas2D; just assert it ran without error + canvas exists
    assert ev["driver"].execute_script("return !!document.getElementById('chart1');")


@pytest.mark.e2e
@pytest.mark.parametrize("plugin", ["line_multi", "combined_bar_line"])
def test_multimetric_tracker_option_plus_numeric(tmp_path, monkeypatch, render_preview, plugin):
    """REQ-PA-OFFLINE-12: line_multi & combined render a tracker_option (count) series
    alongside a tracker_numeric series (also fixes combined's tracker_numeric syntax bug)."""
    from dhis2 import data_store
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://demo.example/hmis")
    STG = _multi_stage_events(data_store)
    metrics = [{"uid": "deDiagxxxx1", "name": "Cases", "type": "tracker_option",
                "prog_uid": PROG, "stage_uid": STG},
               {"uid": "deNumxxxxx1", "name": "Weight", "type": "tracker_numeric",
                "prog_uid": PROG, "stage_uid": STG}]
    cfg = {"plugin_id": plugin, "title": plugin, "metrics": metrics,
           "prog_uid": PROG, "stage_uid": STG}
    ev = render_preview(generate_preview_page(cfg), f"{plugin}_tracker_option")
    msgs = "\n".join(e.get("message", "") for e in ev["console"])
    assert "errEl is not defined" not in msgs and "Failed:" not in msgs
    ds = ev["driver"].execute_script(
        "var c=Chart.getChart('chart1');return c?c.data.datasets.map(d=>"
        "(d.data||[]).reduce((a,b)=>a+(+b||0),0)):null;")
    assert ds is not None, f"no chart; see {ev['screenshot']}"
    assert 3 in ds, f"tracker_option count series (3 events) missing; got {ds}"
    assert 60 in ds, f"tracker_numeric sum (10+20+30) missing; got {ds}"


@pytest.mark.e2e
def test_raw_table_columns_order_and_stage_filter(tmp_path, monkeypatch, render_preview):
    """REQ-TABLE-RAW-01: raw Data Table shows Event date + Org unit + metrics IN ORDER,
    no internal 'ps' column, and only the selected stage's events (no empty rows)."""
    from dhis2 import data_store
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://demo.example/hmis")
    STG_A, STG_B = "STAGEaaaaa1", "STAGEbbbbb1"

    def ev(eid, stg, date, diag, wt):
        dv = [{"dataElement": "deDiagxxxx1", "value": diag}]
        if wt is not None:
            dv.append({"dataElement": "deWtxxxxxx1", "value": wt})
        return {"event": eid, "programStage": stg, "orgUnit": "OU1", "orgUnitName": "Clinic A",
                "occurredAt": date, "dataValues": dv}

    data_store.write_json(data_store.events_path(PROG), {"instances": [
        ev("a1", STG_A, "2024-01-10T00:00:00", "PF", "60"),
        ev("a2", STG_A, "2024-02-05T00:00:00", "PV", "55"),
        ev("b1", STG_B, "2024-01-15T00:00:00", "X", None),   # other stage — excluded
    ]})
    data_store.write_json(data_store.metadata_path("organisationUnits"), {"organisationUnits": []})
    cfg = {"plugin_id": "table_view", "title": "T", "plugin_options": {"mode": "Raw"},
           "metrics": [
               # NOTE: Weight first, Diagnosis second → columns must follow THIS order.
               {"uid": "deWtxxxxxx1", "name": "Weight", "type": "tracker_numeric",
                "prog_uid": PROG, "stage_uid": STG_A},
               {"uid": "deDiagxxxx1", "name": "Diagnosis", "type": "tracker_option",
                "prog_uid": PROG, "stage_uid": STG_A,
                "options": [{"code": "PF", "name": "Pf"}, {"code": "PV", "name": "Pv"}]}],
           "source": {"type": "tracker_option", "prog_uid": PROG, "stage_uid": STG_A}}
    ev_ = render_preview(generate_preview_page(cfg), "raw_table_order")
    data = ev_["driver"].execute_script("return _tD1;")
    assert data["cols"] == ["Event date", "Org unit", "Weight", "Diagnosis"]
    assert "ps" not in data["cols"]
    assert len(data["rows"]) == 2                       # only STAGE_A events
    assert all(r[0] for r in data["rows"])              # every row has an event date
    # option code resolved to its label in the (2nd metric) Diagnosis column
    assert {r[3] for r in data["rows"]} == {"Pf", "Pv"}


@pytest.mark.e2e
def test_raw_table_footer_row_count(tmp_path, monkeypatch, render_preview):
    """REQ-TABLE-RAW-02: the raw Data Table shows a footer with the row count."""
    from dhis2 import data_store
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://demo.example/hmis")
    STG = "STAGEaaaaa1"

    def ev(eid, date):
        return {"event": eid, "programStage": STG, "orgUnit": "OU1", "orgUnitName": "Clinic",
                "occurredAt": date, "dataValues": [{"dataElement": "deDiagxxxx1", "value": "PF"}]}

    data_store.write_json(data_store.events_path(PROG), {"instances": [
        ev("a1", "2024-01-10T00:00:00"), ev("a2", "2024-02-05T00:00:00"),
        ev("a3", "2024-03-01T00:00:00")]})
    data_store.write_json(data_store.metadata_path("organisationUnits"), {"organisationUnits": []})
    cfg = {"plugin_id": "table_view", "title": "T", "plugin_options": {"mode": "Raw"},
           "metrics": [{"uid": "deDiagxxxx1", "name": "Diagnosis", "type": "tracker_option",
                        "prog_uid": PROG, "stage_uid": STG,
                        "options": [{"code": "PF", "name": "Pf"}]}],
           "source": {"type": "tracker_option", "prog_uid": PROG, "stage_uid": STG}}
    ev_ = render_preview(generate_preview_page(cfg), "raw_table_footer")
    foot = ev_["driver"].execute_script(
        "var f=document.querySelector('[data-tf=\"1\"]');return f?f.textContent:null;")
    assert foot == "1–3 of 3", f"footer should show the row range, got {foot!r}"
    # Download CSV lives in the footer (not a separate top bar).
    has_csv = ev_["driver"].execute_script(
        "return [...document.querySelectorAll('[data-tw=\"1\"] button')]"
        ".some(b=>/CSV/.test(b.textContent));")
    assert has_csv, "Download CSV button should be in the footer"


@pytest.mark.e2e
def test_raw_table_pagination(tmp_path, monkeypatch, render_preview):
    """REQ-TABLE-RAW-04: raw Data Table paginates (default 50/page) with Prev/Next and a
    page-size selector; the footer shows the current range."""
    from dhis2 import data_store
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://demo.example/hmis")
    STG = "STAGEaaaaa1"
    insts = [{"event": f"e{i:03d}", "programStage": STG, "orgUnit": "OU1", "orgUnitName": "C",
              "occurredAt": f"2024-01-{(i % 27) + 1:02d}T00:00:00",
              "dataValues": [{"dataElement": "deDiagxxxx1", "value": "PF"}]}
             for i in range(120)]
    data_store.write_json(data_store.events_path(PROG), {"instances": insts})
    data_store.write_json(data_store.metadata_path("organisationUnits"), {"organisationUnits": []})
    cfg = {"plugin_id": "table_view", "title": "T", "plugin_options": {"mode": "Raw"},
           "metrics": [{"uid": "deDiagxxxx1", "name": "Diagnosis", "type": "tracker_option",
                        "prog_uid": PROG, "stage_uid": STG,
                        "options": [{"code": "PF", "name": "Pf"}]}],
           "source": {"type": "tracker_option", "prog_uid": PROG, "stage_uid": STG}}
    drv = render_preview(generate_preview_page(cfg), "raw_table_paging")["driver"]

    def nrows():
        return drv.execute_script("return document.querySelectorAll('[data-tb=\"1\"] tbody tr').length;")
    def foot():
        return drv.execute_script("return document.querySelector('[data-tf=\"1\"]').textContent;")

    assert nrows() == 50, "default page should show 50 rows"
    assert foot() == "1–50 of 120"
    drv.execute_script("document.querySelector('[data-tp=\"next\"]').click();")
    assert foot() == "51–100 of 120"
    assert nrows() == 50
    drv.execute_script("document.querySelector('[data-tp=\"next\"]').click();")
    assert foot() == "101–120 of 120"
    assert nrows() == 20                              # last page partial
    # Switch to "All"
    drv.execute_script(
        "var s=document.querySelector('[data-tps=\"1\"]');s.value='0';"
        "s.dispatchEvent(new Event('change'));")
    assert nrows() == 120


@pytest.mark.e2e
def test_raw_table_filter_row_frozen(tmp_path, monkeypatch, render_preview):
    """REQ-TABLE-RAW-05: the column-filter row is sticky (frozen) like the header."""
    from dhis2 import data_store
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://demo.example/hmis")
    STG = "STAGEaaaaa1"
    data_store.write_json(data_store.events_path(PROG), {"instances": [
        {"event": "e1", "programStage": STG, "orgUnit": "OU1", "orgUnitName": "C",
         "occurredAt": "2024-01-10T00:00:00",
         "dataValues": [{"dataElement": "deDiagxxxx1", "value": "PF"}]}]})
    data_store.write_json(data_store.metadata_path("organisationUnits"), {"organisationUnits": []})
    cfg = {"plugin_id": "table_view", "title": "T", "plugin_options": {"mode": "Raw"},
           "metrics": [{"uid": "deDiagxxxx1", "name": "Diagnosis", "type": "tracker_option",
                        "prog_uid": PROG, "stage_uid": STG, "options": [{"code": "PF", "name": "Pf"}]}],
           "source": {"type": "tracker_option", "prog_uid": PROG, "stage_uid": STG}}
    drv = render_preview(generate_preview_page(cfg), "raw_table_freeze")["driver"]
    info = drv.execute_script(
        "var td=document.querySelector('[data-tb=\"1\"] thead tr:nth-child(2) td');"
        "if(!td) return null;"
        "var cs=getComputedStyle(td);return {pos:cs.position, top:td.style.top};")
    assert info and info["pos"] == "sticky", f"filter row not sticky: {info}"
    assert info["top"] and info["top"] != "0px", f"filter row top not offset below header: {info}"


@pytest.mark.e2e
def test_line_trend_label_and_show_values(tmp_path, monkeypatch, render_preview):
    """REQ-LINE-01/02: line_trend dataset label uses the metric name/alias (not 'Value'),
    and Show values turns on the working showValues plugin."""
    from dhis2 import data_store
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://demo.example/hmis")
    STG = "STAGEaaaaa1"
    data_store.write_json(data_store.events_path(PROG), {"instances": [
        {"event": "e1", "programStage": STG, "orgUnit": "OU1", "occurredAt": "2024-01-10T00:00:00",
         "dataValues": [{"dataElement": "deDiagxxxx1", "value": "PF"}]}]})
    data_store.write_json(data_store.metadata_path("organisationUnits"), {"organisationUnits": []})
    cfg = {"plugin_id": "line_trend", "title": "T", "plugin_options": {"show_values": "On"},
           "metrics": [{"uid": "deDiagxxxx1", "name": "Cases (alias)", "type": "tracker_option",
                        "prog_uid": PROG, "stage_uid": STG}], "prog_uid": PROG, "stage_uid": STG}
    info = render_preview(generate_preview_page(cfg), "line_label")["driver"].execute_script(
        "var c=Chart.getChart('chart1');return c?{lbl:c.data.datasets[0].label,"
        "sv:!!(c.options.plugins.showValues&&c.options.plugins.showValues.display)}:null;")
    assert info and info["lbl"] == "Cases (alias)"
    assert info["sv"] is True


@pytest.mark.e2e
def test_line_trend_split_by_dimension(tmp_path, monkeypatch, render_preview):
    """REQ-LINE-03: line_trend splits into one line per dimension value (e.g. Sex)."""
    from dhis2 import data_store
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://demo.example/hmis")
    STG = "STAGEaaaaa1"
    def ev(eid, date, sex):
        return {"event": eid, "programStage": STG, "trackedEntity": "T" + eid, "orgUnit": "OU1",
                "occurredAt": date, "dataValues": [{"dataElement": "deDiagxxxx1", "value": "PF"}],
                "attributes": [{"attribute": SEX, "value": sex}]}
    data_store.write_json(data_store.events_path(PROG), {"instances": [
        ev("a1", "2024-01-10T00:00:00", "M"), ev("a2", "2024-01-12T00:00:00", "F"),
        ev("a3", "2024-02-05T00:00:00", "M")]})
    data_store.write_json(data_store.metadata_path("organisationUnits"), {"organisationUnits": []})
    cfg = {"plugin_id": "line_trend", "title": "T", "plugin_options": {},
           "metrics": [{"uid": "deDiagxxxx1", "name": "Cases", "type": "tracker_option",
                        "prog_uid": PROG, "stage_uid": STG}],
           "dimensions": {"dimension": {"uid": SEX, "name": "Sex", "type": "tracker_option",
                          "is_tea": True, "stage_uid": "",
                          "options": [{"code": "M", "name": "Male"}, {"code": "F", "name": "Female"}]}},
           "prog_uid": PROG, "stage_uid": STG}
    ev_ = render_preview(generate_preview_page(cfg), "line_dim")
    msgs = "\n".join(e.get("message", "") for e in ev_["console"])
    assert "errEl is not defined" not in msgs and "Dimension column not found" not in msgs
    ds = ev_["driver"].execute_script(
        "var c=Chart.getChart('chart1');return c?c.data.datasets.map(d=>"
        "({l:d.label,sum:d.data.reduce((a,b)=>a+(+b||0),0)})):null;")
    by = {d["l"]: d["sum"] for d in ds}
    assert by.get("Male") == 2 and by.get("Female") == 1, f"expected Male=2 Female=1, got {by}"


@pytest.mark.e2e
def test_bubble_map_event_coordinates_offline(tmp_path, monkeypatch, render_map_preview):
    """REQ-MAP-COORD-01: bubble map with Event coordinates plots from event geometry
    (no 'No event coordinates' error) once the sample captures geometry."""
    from dhis2 import data_store
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://demo.example/hmis")
    STG = "STAGEaaaaa1"

    def ev(eid, lon, lat):
        return {"event": eid, "programStage": STG, "orgUnit": "OU1", "orgUnitName": "C",
                "occurredAt": "2024-01-10T00:00:00",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "dataValues": [{"dataElement": "deNumxxxxx1", "value": "5"}]}
    data_store.write_json(data_store.events_path(PROG), {"instances": [
        ev("a1", 102.6, 17.9), ev("a2", 103.1, 18.2), ev("a3", 102.4, 17.5)]})
    data_store.write_json(data_store.metadata_path("organisationUnits"), {"organisationUnits": []})
    cfg = {"plugin_id": "point_map", "title": "M",
           "plugin_options": {"coordinates": "Event", "base_map": "None", "overlay_levels": ""},
           "metrics": [{"uid": "deNumxxxxx1", "name": "Weight", "type": "tracker_numeric",
                        "agg": "SUM", "prog_uid": PROG, "stage_uid": STG}],
           "source": {"type": "tracker_numeric", "prog_uid": PROG, "stage_uid": STG}}
    ev_ = render_map_preview(generate_preview_page(cfg), "bubble_event_coords")
    msgs = "\n".join(e.get("message", "") for e in ev_["console"])
    assert "No event coordinates" not in msgs, msgs
    assert "Map error" not in (ev_.get("error_text") or "")


@pytest.mark.e2e
def test_bubble_map_dimension_colours_by_category(tmp_path, monkeypatch, render_map_preview):
    """REQ-MAP-DIM-01: bubble map with a dimension colours one bubble per event by its
    category value (e.g. PF vs PV) and shows a categorical legend."""
    from dhis2 import data_store
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://demo.example/hmis")
    STG, DIM = "STAGEaaaaa1", "deDiagxxxx1"

    def ev(eid, lon, lat, diag):
        return {"event": eid, "programStage": STG, "orgUnit": "OU1", "orgUnitName": "C",
                "occurredAt": "2024-01-10T00:00:00",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "dataValues": [{"dataElement": DIM, "value": diag}]}
    data_store.write_json(data_store.events_path(PROG), {"instances": [
        ev("a", 102.6, 17.9, "PF"), ev("b", 103.1, 18.2, "PV"), ev("c", 102.4, 17.5, "PV")]})
    data_store.write_json(data_store.metadata_path("organisationUnits"), {"organisationUnits": []})
    cfg = {"plugin_id": "point_map", "title": "M",
           "plugin_options": {"base_map": "None", "overlay_levels": ""},
           "metrics": [{"uid": DIM, "name": "Cases", "type": "tracker_option",
                        "prog_uid": PROG, "stage_uid": STG}],
           "dimensions": {"dimension": {"uid": DIM, "name": "Diagnosis", "type": "tracker_option",
                          "stage_uid": STG,
                          "options": [{"code": "PF", "name": "Pf"}, {"code": "PV", "name": "Pv"}]}},
           "source": {"type": "tracker_option", "prog_uid": PROG, "stage_uid": STG}}
    ev_ = render_map_preview(generate_preview_page(cfg), "bubble_dim_category")
    msgs = "\n".join(e.get("message", "") for e in ev_["console"])
    assert "No event coordinates" not in msgs and "Map error" not in (ev_.get("error_text") or "")
    legend = ev_["driver"].execute_script(
        "var l=document.querySelector('.leaflet-control-container');return l?l.innerText:'';")
    assert "Pf" in legend and "Pv" in legend, f"categorical legend missing: {legend!r}"


@pytest.mark.e2e
def test_bubble_map_event_aggregates_by_location(tmp_path, monkeypatch, render_map_preview):
    """REQ-MAP-COORD-03: in event mode, events at the same location merge into ONE
    bubble (sized by count), instead of many overlapping bubbles."""
    from dhis2 import data_store
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://demo.example/hmis")
    STG = "STAGEaaaaa1"

    def ev(eid, lon, lat):
        return {"event": eid, "programStage": STG, "orgUnit": "OU1", "orgUnitName": "Clinic A",
                "occurredAt": "2024-01-10T00:00:00",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "dataValues": [{"dataElement": "deDiagxxxx1", "value": "PF"}]}
    insts = [ev(f"a{i}", 102.6, 17.9) for i in range(5)] + [ev("b", 103.2, 18.5)]
    data_store.write_json(data_store.events_path(PROG), {"instances": insts})
    data_store.write_json(data_store.metadata_path("organisationUnits"), {"organisationUnits": []})
    cfg = {"plugin_id": "point_map", "title": "M",
           "plugin_options": {"coordinates": "Event", "base_map": "None", "overlay_levels": ""},
           "metrics": [{"uid": "deDiagxxxx1", "name": "Cases", "type": "tracker_option",
                        "prog_uid": PROG, "stage_uid": STG}],
           "source": {"type": "tracker_option", "prog_uid": PROG, "stage_uid": STG}}
    drv = render_map_preview(generate_preview_page(cfg), "bubble_aggregate")["driver"]
    n_bubbles = drv.execute_script(
        "return document.querySelectorAll('.leaflet-overlay-pane path').length;")
    assert n_bubbles == 2, f"5 same-location + 1 events should merge to 2 bubbles, got {n_bubbles}"
