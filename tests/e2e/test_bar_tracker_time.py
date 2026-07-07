"""Regression: bar + tracker_option metric must count events PER PERIOD (monthly),
bucketed by event date — not collapse to one column. (User report 2026-06-26.)"""
import pytest
from dhis2 import data_store
from charts.fixed_templates import generate_preview_page

PROG, STAGE, DEOPT = "BTprog00001", "BTstage0001", "BTdeopt0001"


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(data_store, "_DATA_ROOT", tmp_path)
    data_store.set_active_instance("https://demo.example/hmis")
    ev = lambda eid, date, val: {"event": eid, "programStage": STAGE, "orgUnit": "OUaaaaaaaa1",
                                 "occurredAt": date, "dataValues": [{"dataElement": DEOPT, "value": val}]}
    data_store.write_json(data_store.events_path(PROG), {"instances": [
        ev("a", "2024-01-10T00:00:00", "PF"),
        ev("b", "2024-02-12T00:00:00", "PV"),
        ev("c", "2024-02-20T00:00:00", "PF"),
        ev("d", "2024-03-05T00:00:00", "PF"),
    ]})
    data_store.write_json(data_store.metadata_path("organisationUnits"), {"organisationUnits": []})


@pytest.mark.e2e
def test_bar_tracker_option_counts_by_month(tmp_path, monkeypatch, render_preview):
    """REQ-REGR-TIME-01: tracker_option metric → event count per month (≥3 bars), default event date."""
    _setup(tmp_path, monkeypatch)
    cfg = {"plugin_id": "bar", "title": "Diagnosis",
           "metrics": [{"uid": DEOPT, "name": "Diagnosis", "type": "tracker_option", "agg": "SUM",
                        "prog_uid": PROG, "stage_uid": STAGE,
                        "options": [{"code": "PF", "name": "PF"}, {"code": "PV", "name": "PV"}]}]}
    ev = render_preview(generate_preview_page(cfg), "bar_tracker_monthly")
    severe = [e for e in ev["severe"] if "favicon" not in (e.get("message") or "").lower()]
    assert not severe, "JS errors:\n" + "\n".join(e.get("message", "") for e in severe)
    info = ev["driver"].execute_script(
        "var c=Chart.getChart('chart1');return c?{labels:c.data.labels,"
        "vals:c.data.datasets[0].data}:null;")
    assert info, f"no chart; see {ev['screenshot']}"
    assert len(info["labels"]) >= 3, f"expected ≥3 monthly bars, got {info['labels']} ({ev['screenshot']})"
    assert sum(info["vals"]) == 4, f"expected 4 events total, got {info['vals']}"
