"""
Regression tests — one scenario per real bug, built from the exact user-chosen
parameters (see docs/TESTING_PROCESS.md §9). Each test must fail on the buggy code
and pass once fixed, and stays forever so the bug cannot recur.

Run: pip install -r requirements-dev.txt ; pytest tests/e2e/test_regressions.py -m e2e -s
"""
import pytest

from charts.fixed_templates import generate_preview_page


@pytest.mark.e2e
def test_format_period_label_null_safe(render_preview):
    """REQ-REGR-PE-01: formatPeriodLabel(undefined/null) must not throw.

    Bug: bar chart with a tracker_option metric (pe empty) →
    'TypeError: can't access property "match", pe is undefined' — a missing period
    bucket reached formatPeriodLabel(undefined) and killed the whole chart.
    """
    cfg = {"plugin_id": "bar", "title": "regr",
           "metrics": [{"uid": "deBar000001", "name": "Cases", "type": "aggregate", "agg": "SUM"}]}
    ev = render_preview(generate_preview_page(cfg), "regr_formatperiod")
    res = ev["driver"].execute_script(
        "try { return {ok:true,"
        " u: formatPeriodLabel(undefined),"
        " n: formatPeriodLabel(null),"
        " m: formatPeriodLabel(202401)};"   # numeric coerced to '202401'
        "} catch(e) { return {ok:false, err:String(e)}; }"
    )
    assert res["ok"], f"formatPeriodLabel threw: {res.get('err')}"
    assert res["u"] == "" and res["n"] == ""
    assert res["m"] == "Jan 2024"            # String() coercion still formats


@pytest.mark.e2e
def test_bar_tracker_option_metric_renders(render_preview):
    """REQ-REGR-PE-01: the exact user config (bar + tracker_option metric) renders, no JS error.

    From logs/debug: plugin=bar metrics=[Diagnosis Test result [tracker_option]] pe= ou_level=.
    """
    cfg = {
        "plugin_id": "bar", "title": "Invest: Diagnosis Test result",
        "metrics": [{"uid": "deOPT000001", "name": "Diagnosis Test result",
                     "type": "tracker_option", "agg": "SUM",
                     "prog_uid": "PROG0000001", "stage_uid": "STAGE000001",
                     "options": [{"code": "PF", "name": "P. falciparum"},
                                 {"code": "PV", "name": "P. vivax"}]}],
    }
    ev = render_preview(generate_preview_page(cfg), "regr_bar_tracker_option")
    severe = [e for e in ev["severe"] if "favicon" not in (e.get("message") or "").lower()]
    assert not severe, "JS console errors:\n" + "\n".join(e.get("message", "") for e in severe)
    assert ev["canvas_present"], f"chart did not render; see {ev['screenshot']}"


# Exact user-logged parameters (logs/debug_20260626_122852.log + captured preview HTML):
# program yAKTrPUMAuU (Malaria Case Register), dimension DE DmuazFb368B = "Sex" (PA/TEA,
# Male/Female). The TEA dimension produced URL "&dimension=.DmuazFb368B" (empty-stage
# prefix) → catIdx<0 → renderChart1Real referenced errEl (out of scope) → crash.
_PROG, _STAGE, _SEX = "yAKTrPUMAuU", "KqjOmlBpYtd", "DmuazFb368B"


@pytest.mark.e2e
def test_bar_tea_dimension_no_errEl_crash(tmp_path, monkeypatch, render_preview):
    """REQ-REGR-ERREL-01: bar split-by a program attribute (Sex) whose column isn't in the
    response must NOT crash with 'errEl is not defined' (errEl was wrongly referenced inside
    renderChartNReal). Exact user config: program yAKTrPUMAuU, dimension Sex [DmuazFb368B]."""
    from dhis2 import data_store
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://demo.example/hmis")
    data_store.write_json(data_store.events_path(_PROG), {"instances": [
        {"event": "e1", "programStage": _STAGE, "orgUnit": "OU1",
         "occurredAt": "2024-01-10T00:00:00",
         "dataValues": [{"dataElement": "deMetricxx1", "value": "1"}]},
    ]})
    data_store.write_json(data_store.metadata_path("organisationUnits"), {"organisationUnits": []})
    cfg = {
        "plugin_id": "bar", "title": "Sex",
        "metrics": [{"uid": "deMetricxx1", "name": "Cases", "type": "tracker_option",
                     "prog_uid": _PROG, "stage_uid": _STAGE}],
        # PA/TEA dimension (program-level, stage_uid empty)
        "dimensions": {"dimension": {"uid": _SEX, "name": "Sex", "type": "tracker_option",
                                     "prog_uid": _PROG, "stage_uid": "", "is_tea": True,
                                     "options": [{"code": "M", "name": "Male"},
                                                 {"code": "F", "name": "Female"}]}},
        "prog_uid": _PROG, "stage_uid": _STAGE,
    }
    html = generate_preview_page(cfg)
    # The TEA dimension must be queried by its BARE uid, never the empty-stage ".uid" form.
    assert f"&dimension={_SEX}" in html, "TEA dimension should use bare uid"
    assert f"dimension=.{_SEX}" not in html, "empty-stage '.uid' prefix must be gone"
    ev = render_preview(html, "bar_tea_dim_no_crash")
    msgs = "\n".join(e.get("message", "") for e in ev["console"])
    assert "errEl is not defined" not in msgs, f"errEl scope crash recurred:\n{msgs}"
