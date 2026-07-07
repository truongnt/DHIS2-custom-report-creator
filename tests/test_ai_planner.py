"""Tests for llm.ai_dashboard_planner — AI chart recommendation engine.

REQ-PLANNER-01  build_context flattens metadata into de_list
REQ-PLANNER-02  descriptions are embedded in de_list entries
REQ-PLANNER-03  de_list is truncated to max_items
REQ-PLANNER-04  mock_key returns recommendations using preset scenario
REQ-PLANNER-05  mock placeholder UIDs resolve to real UIDs from de_list
REQ-PLANNER-06  recommendations with unknown chart_type are filtered out
REQ-PLANNER-07  recommendations with unknown de_uid are filtered out
REQ-PLANNER-08  recommendations missing title are filtered out
REQ-PLANNER-09  mock_response overrides mock_key
REQ-PLANNER-10  recs_to_chart_configs produces valid chart config dicts
REQ-PLANNER-11  missing ai_client + no mock raises ValueError
REQ-PLANNER-12  AI JSON response with markdown fences is parsed correctly
REQ-PLANNER-13  dashboard_library save + load round-trip
REQ-PLANNER-14  dashboard_library delete removes entry
"""
from __future__ import annotations

import json
import sys
import pytest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from llm.ai_dashboard_planner import (
    CHART_TYPE_CATALOG,
    MOCK_SCENARIOS,
    build_context,
    recommend_charts,
    recs_to_chart_configs,
    _parse_response,
    _validate,
)

# ── Sample metadata ───────────────────────────────────────────────────────────

_SAMPLE_META = {
    "indicators": [
        {"id": "ind001", "displayName": "Confirmed Malaria Cases"},
        {"id": "ind002", "displayName": "Test Positivity Rate"},
    ],
    "program_indicators": [
        {"id": "pi001", "displayName": "PI Malaria Incidence"},
    ],
    "data_elements": [
        {"id": "de001", "displayName": "Malaria Confirmed"},
    ],
    "program_stage_data_elements": [
        {"id": "psde001", "displayName": "Tracker DE: Result"},
    ],
    "tracked_entity_attributes": [
        {"id": "tea001", "displayName": "Patient Age"},
    ],
}

_SAMPLE_DESCS = {
    "ind001": "Number of lab-confirmed malaria cases",
    "pi001":  "Malaria incidence per 1000 population",
}


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestBuildContext:

    def test_de_list_contains_all_kinds(self):
        """REQ-PLANNER-01 build_context flattens all metadata kinds."""
        ctx = build_context(_SAMPLE_META, {})
        kinds = {d["kind"] for d in ctx["de_list"]}
        assert "indicator" in kinds
        assert "program_indicator" in kinds
        assert "data_element" in kinds
        assert "tracker_de" in kinds
        assert "tracked_attr" in kinds

    def test_descriptions_embedded(self):
        """REQ-PLANNER-02 descriptions from local store appear in de_list."""
        ctx = build_context(_SAMPLE_META, _SAMPLE_DESCS)
        entry = next(d for d in ctx["de_list"] if d["uid"] == "ind001")
        assert entry["description"] == "Number of lab-confirmed malaria cases"

    def test_missing_description_is_empty_string(self):
        """REQ-PLANNER-02 no description → empty string, not None."""
        ctx = build_context(_SAMPLE_META, {})
        for d in ctx["de_list"]:
            assert isinstance(d["description"], str)

    def test_max_items_truncates(self):
        """REQ-PLANNER-03 de_list respects max_items."""
        ctx = build_context(_SAMPLE_META, {}, max_items=3)
        assert len(ctx["de_list"]) <= 3

    def test_chart_types_present(self):
        """build_context includes chart_types catalog."""
        ctx = build_context(_SAMPLE_META, {})
        assert ctx["chart_types"] == CHART_TYPE_CATALOG
        assert len(ctx["chart_types"]) >= 10


class TestMockRecommend:

    def test_mock_key_malaria(self):
        """REQ-PLANNER-04 mock_key returns recommendations from MOCK_SCENARIOS."""
        ctx = build_context(_SAMPLE_META, {})
        recs = recommend_charts("malaria", ctx, mock_key="malaria_overview")
        assert isinstance(recs, list)
        assert len(recs) > 0

    def test_placeholder_uid_resolved(self):
        """REQ-PLANNER-05 __FIRST__ / __SECOND__ resolve to actual UIDs."""
        ctx = build_context(_SAMPLE_META, {})
        recs = recommend_charts("x", ctx, mock_key="malaria_overview")
        first_uid = ctx["de_list"][0]["uid"]
        assert all(r["de_uid"] != "__FIRST__" for r in recs)
        assert any(r["de_uid"] == first_uid for r in recs)

    def test_mock_response_overrides_key(self):
        """REQ-PLANNER-09 explicit mock_response is used instead of mock_key."""
        ctx = build_context(_SAMPLE_META, {})
        custom = [
            {"title": "Custom Chart", "chart_type": "bar_monthly",
             "de_uid": "ind001", "rationale": "Custom"}
        ]
        recs = recommend_charts("x", ctx, mock_key="malaria_overview",
                                mock_response=custom)
        assert len(recs) == 1
        assert recs[0]["title"] == "Custom Chart"

    def test_all_mock_scenarios_parseable(self):
        """REQ-PLANNER-04 all built-in mock scenarios work without errors."""
        ctx = build_context(_SAMPLE_META, {})
        for key in MOCK_SCENARIOS:
            recs = recommend_charts("test", ctx, mock_key=key)
            assert isinstance(recs, list)

    def test_no_client_no_mock_raises(self):
        """REQ-PLANNER-11 missing everything raises ValueError."""
        ctx = build_context(_SAMPLE_META, {})
        with pytest.raises(ValueError, match="Provide ai_client"):
            recommend_charts("x", ctx)


class TestValidation:

    def test_unknown_chart_type_filtered(self):
        """REQ-PLANNER-06 bad chart_type removed."""
        ctx = build_context(_SAMPLE_META, {})
        recs = [
            {"title": "Good", "chart_type": "bar_monthly", "de_uid": "ind001", "rationale": "ok"},
            {"title": "Bad",  "chart_type": "nonexistent",  "de_uid": "ind001", "rationale": "bad"},
        ]
        valid = _validate(recs, ctx["de_list"])
        assert len(valid) == 1
        assert valid[0]["title"] == "Good"

    def test_unknown_de_uid_filtered(self):
        """REQ-PLANNER-07 bad de_uid removed."""
        ctx = build_context(_SAMPLE_META, {})
        recs = [
            {"title": "Good", "chart_type": "bar_monthly", "de_uid": "ind001", "rationale": "ok"},
            {"title": "Bad",  "chart_type": "bar_monthly", "de_uid": "unknown999", "rationale": "bad"},
        ]
        valid = _validate(recs, ctx["de_list"])
        assert len(valid) == 1

    def test_missing_title_filtered(self):
        """REQ-PLANNER-08 missing title removed."""
        ctx = build_context(_SAMPLE_META, {})
        recs = [
            {"title": "",    "chart_type": "bar_monthly", "de_uid": "ind001", "rationale": "ok"},
            {"title": "OK",  "chart_type": "bar_monthly", "de_uid": "ind001", "rationale": "ok"},
        ]
        valid = _validate(recs, ctx["de_list"])
        assert len(valid) == 1
        assert valid[0]["title"] == "OK"


class TestParseResponse:

    def test_plain_json_array(self):
        """_parse_response handles bare JSON array."""
        text = '[{"title":"T","chart_type":"bar","de_uid":"x","rationale":"r"}]'
        result = _parse_response(text)
        assert len(result) == 1

    def test_markdown_fenced(self):
        """REQ-PLANNER-12 markdown code fence is stripped."""
        text = '```json\n[{"title":"T","chart_type":"bar","de_uid":"x","rationale":"r"}]\n```'
        result = _parse_response(text)
        assert len(result) == 1

    def test_invalid_json_returns_empty(self):
        """Corrupt JSON → empty list, no exception."""
        result = _parse_response("not json at all")
        assert result == []

    def test_empty_text_returns_empty(self):
        result = _parse_response("")
        assert result == []


class TestRecsToConfigs:

    def test_valid_recs_produce_configs(self):
        """REQ-PLANNER-10 recs_to_chart_configs returns chart config dicts."""
        ctx = build_context(_SAMPLE_META, {})
        recs = [
            {"title": "My Chart", "chart_type": "bar_monthly",
             "de_uid": "ind001", "rationale": "test"},
        ]
        configs = recs_to_chart_configs(recs, ctx["de_list"])
        assert len(configs) == 1
        cfg = configs[0]
        assert cfg["template_id"] == "bar_monthly"
        assert cfg["title"] == "My Chart"
        assert cfg["metrics"][0]["uid"] == "ind001"   # plugins read "uid" → dx:<uid>
        assert cfg["_ai_generated"] is True

    def test_unknown_uid_skipped(self):
        """Recs with uid not in de_list are skipped silently."""
        ctx = build_context(_SAMPLE_META, {})
        recs = [
            {"title": "X", "chart_type": "bar", "de_uid": "NOT_EXIST", "rationale": "r"},
        ]
        configs = recs_to_chart_configs(recs, ctx["de_list"])
        assert configs == []

    def test_de_type_mapping_indicator(self):
        """Indicator kind maps to 'indicator' de_type."""
        ctx = build_context(_SAMPLE_META, {})
        recs = [{"title": "T", "chart_type": "scorecard",
                 "de_uid": "ind001", "rationale": "r"}]
        configs = recs_to_chart_configs(recs, ctx["de_list"])
        assert configs[0]["metrics"][0]["type"] == "indicator"

    def test_de_type_mapping_tracker(self):
        """tracker_de kind maps to 'tracker_numeric' de_type."""
        ctx = build_context(_SAMPLE_META, {})
        recs = [{"title": "T", "chart_type": "bar",
                 "de_uid": "psde001", "rationale": "r"}]
        configs = recs_to_chart_configs(recs, ctx["de_list"])
        assert configs[0]["metrics"][0]["type"] == "tracker_numeric"


class TestDashboardLibrary:

    def test_save_and_load(self, tmp_path, monkeypatch):
        """REQ-PLANNER-13 dashboard_library save + load round-trip."""
        import config.dashboard_library as _lib
        monkeypatch.setattr(_lib, "_LIBRARY_FILE", tmp_path / "dashboards.json")
        from config.dashboard_library import save_dashboard, load_dashboards
        cards = [{"template_id": "bar_monthly", "title": "Test Chart"}]
        save_dashboard("My Dashboard", cards)
        dashes = load_dashboards()
        assert len(dashes) == 1
        assert dashes[0]["name"] == "My Dashboard"
        assert dashes[0]["cards"] == cards
        assert "id" in dashes[0]
        assert "created_at" in dashes[0]

    def test_upsert_by_name(self, tmp_path, monkeypatch):
        """Saving same name again overwrites cards."""
        import config.dashboard_library as _lib
        monkeypatch.setattr(_lib, "_LIBRARY_FILE", tmp_path / "dashboards.json")
        from config.dashboard_library import save_dashboard, load_dashboards
        save_dashboard("Dash", [{"a": 1}])
        save_dashboard("Dash", [{"b": 2}])
        dashes = load_dashboards()
        assert len(dashes) == 1
        assert dashes[0]["cards"] == [{"b": 2}]

    def test_delete(self, tmp_path, monkeypatch):
        """REQ-PLANNER-14 delete removes entry by id."""
        import config.dashboard_library as _lib
        monkeypatch.setattr(_lib, "_LIBRARY_FILE", tmp_path / "dashboards.json")
        from config.dashboard_library import save_dashboard, load_dashboards, delete_dashboard
        entry = save_dashboard("ToDelete", [])
        assert len(load_dashboards()) == 1
        delete_dashboard(entry["id"])
        assert load_dashboards() == []

    def test_empty_library_returns_empty_list(self, tmp_path, monkeypatch):
        """No file → empty list, no error."""
        import config.dashboard_library as _lib
        monkeypatch.setattr(_lib, "_LIBRARY_FILE", tmp_path / "nonexistent.json")
        from config.dashboard_library import load_dashboards
        assert load_dashboards() == []


class TestCardLibrarySync:
    """REQ-DASH-SYNC: dashboard cards refresh chart content from the library by id at
    preview/export/deploy, while keeping their own canvas layout."""

    def test_card_picks_up_latest_chart_options(self):
        """REQ-DASH-SYNC-01: edited chart option (show_values) flows into the card."""
        from config.dashboard_library import sync_cards_with_charts
        card = {"id": "abc", "plugin_id": "point_map", "col_width": 4,
                "layout": {"w": 4, "h": 2},
                "plugin_options": {"show_values": "Hide"}}
        chart = {"id": "abc", "plugin_id": "point_map",
                 "plugin_options": {"show_values": "Show"}, "title": "New title"}
        out = sync_cards_with_charts([card], [chart])[0]
        assert out["plugin_options"]["show_values"] == "Show"   # content refreshed
        assert out["title"] == "New title"
        assert out["col_width"] == 4 and out["layout"] == {"w": 4, "h": 2}  # layout kept

    def test_unmatched_card_kept_as_snapshot(self):
        """REQ-DASH-SYNC-02: card whose source chart was deleted is left unchanged."""
        from config.dashboard_library import sync_cards_with_charts
        card = {"id": "gone", "plugin_options": {"show_values": "Hide"}}
        out = sync_cards_with_charts([card], [{"id": "other"}])
        assert out == [card]

    def test_ai_card_without_id_untouched(self):
        """REQ-DASH-SYNC-03: AI/generated cards (no id) pass through verbatim."""
        from config.dashboard_library import sync_cards_with_charts
        card = {"mode": "ai", "html_path": "x.html"}
        assert sync_cards_with_charts([card], [{"id": "abc"}]) == [card]
