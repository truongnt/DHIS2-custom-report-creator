"""
UI integration test suite for DHIS2 Auto Report (PySide6).

Runs WITHOUT live DHIS2 network access.
Simulates user interactions via QTest + direct method injection.

Run:
    python test_ui.py [-v]
"""
import sys, os, json, unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

REPO = Path(__file__).parent
sys.path.insert(0, str(REPO))

from PySide6.QtWidgets import QApplication, QLineEdit, QCheckBox, QComboBox, QMessageBox
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest

# ── Fixture metadata (no network needed) ──────────────────────────────────────
FIXTURE_META = {
    "programs": [{"id": "yAKTrPUMAuU", "displayName": "Malaria Case Register"}],
    "data_elements": [
        {"id": "de001", "displayName": "Confirmed Cases"},
        {"id": "de002", "displayName": "Deaths"},
        {"id": "de003", "displayName": "Suspected Cases"},
    ],
    "program_stage_data_elements": [
        {
            "id": "psde001",
            "displayName": "Diagnosis Test Result",
            "program": {"id": "yAKTrPUMAuU", "displayName": "Malaria Case Register"},
            "stage":   {"id": "stg001",       "displayName": "Case Registration"},
            "optionSet": {"options": [
                {"code": "PF", "displayName": "P. falciparum"},
                {"code": "PV", "displayName": "P. vivax"},
            ]},
        },
        {
            "id": "psde002",
            "displayName": "Outcome",
            "program": {"id": "yAKTrPUMAuU", "displayName": "Malaria Case Register"},
            "stage":   {"id": "stg001",       "displayName": "Case Registration"},
            "optionSet": None,
        },
    ],
    "indicators": [],
    "program_indicators": [],
    "tracked_entity_attributes": [],
    "datasets": [],
    "org_unit_levels": [],
    "_filter_config": {},
}

_app = None


def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


def _make_window():
    """Create AppWindow with all credential calls mocked (no network)."""
    with (
        patch("config.credentials.load_profiles", return_value=[]),
        patch("config.credentials.load_api_key",  return_value=""),
        patch("config.credentials.load_password", return_value=""),
    ):
        from ui.app_window import AppWindow
        from ui.qt_utils import APP_QSS
        app = _get_app()
        app.setStyleSheet(APP_QSS)
        win = AppWindow()
        win.show()
        app.processEvents()
        return win


def _simulate_connect(win, meta=None):
    """Inject metadata directly — bypasses all network code."""
    if meta is None:
        meta = FIXTURE_META
    win._metadata = meta
    win._on_connect_done(
        display="Test User",
        count=0,
        cached_at="2026-01-01 00:00 UTC",
        from_cache=True,
    )
    _get_app().processEvents()


# ═══════════════════════════════════════════════════════════════════════════════
# Category 1 — Startup & Init
# ═══════════════════════════════════════════════════════════════════════════════

class TestStartup(unittest.TestCase):

    def setUp(self):
        self.win = _make_window()

    def tearDown(self):
        self.win.close()
        _get_app().processEvents()

    def test_1_1_window_title(self):
        """1.1 — Window title is 'DHIS2 Auto Report'."""
        self.assertEqual(self.win.windowTitle(), "DHIS2 Auto Report")

    def test_1_2_minimum_size(self):
        """1.2 — Window minimum size >= 1024x640."""
        ms = self.win.minimumSize()
        self.assertGreaterEqual(ms.width(),  1024)
        self.assertGreaterEqual(ms.height(), 640)

    def test_1_3_sidebar_has_3_nav_buttons(self):
        """1.3 — Sidebar has exactly 3 nav buttons: config, chart_editor, dashboard."""
        self.assertEqual(len(self.win._nav_btns), 3)
        for key in ("config", "chart_editor", "dashboard"):
            self.assertIn(key, self.win._nav_btns)

    def test_1_4_config_panel_shown_by_default(self):
        """1.4 — Config panel (QStackedWidget index 0) shown at startup."""
        self.assertEqual(self.win._content.currentIndex(), 0)
        self.assertEqual(self.win._active_panel, "config")

    def test_1_5_chart_editor_and_dashboard_disabled(self):
        """1.5 — Chart Editor + Dashboard nav buttons disabled before connect."""
        self.assertFalse(self.win._nav_btns["chart_editor"].isEnabled())
        self.assertFalse(self.win._nav_btns["dashboard"].isEnabled())
        self.assertTrue(self.win._nav_btns["config"].isEnabled())


# ═══════════════════════════════════════════════════════════════════════════════
# Category 2 — Config Panel: Connection
# ═══════════════════════════════════════════════════════════════════════════════

class TestConnection(unittest.TestCase):

    def setUp(self):
        self.win = _make_window()

    def tearDown(self):
        self.win.close()
        _get_app().processEvents()

    def test_2_4_fields_editable(self):
        """2.4 — URL / Username / Password fields are not read-only."""
        self.assertFalse(self.win.url_entry.isReadOnly())
        self.assertFalse(self.win.user_entry.isReadOnly())
        self.assertFalse(self.win.pass_entry.isReadOnly())

    def test_2_5_password_masked(self):
        """2.5 — Password field uses Password echo mode."""
        self.assertEqual(self.win.pass_entry.echoMode(),
                         QLineEdit.EchoMode.Password)

    def test_2_6_connect_button_disabled_during_connect(self):
        """2.6 — Connect button disabled during a connect attempt."""
        with patch.object(self.win, "_connect_worker", return_value=None):
            self.win.url_entry.setText("https://test.local")
            self.win.user_entry.setText("admin")
            self.win.pass_entry.setText("secret")
            self.win._on_connect()
            _get_app().processEvents()
            self.assertFalse(self.win.connect_btn.isEnabled())
        self.win.connect_btn.setEnabled(True)
        self.win.connect_btn.setText("Connect")

    def test_2_7_connected_state(self):
        """2.7 — After successful connect: button shows Connected, login frame hidden."""
        _simulate_connect(self.win)
        self.assertFalse(self.win.connect_btn.isEnabled())
        self.assertIn("Connected", self.win.connect_btn.text())
        # isHidden() reflects explicit hide() regardless of parent panel visibility
        self.assertTrue(self.win._login_frame.isHidden())
        self.assertFalse(self.win.change_conn_btn.isHidden())
        self.assertEqual(self.win._content.currentIndex(), 1)

    def test_2_8_failed_connect_resets_button(self):
        """2.8 — Failed connect re-enables Connect button, shows error in status."""
        self.win._on_connect_fail("Connection refused")
        _get_app().processEvents()
        self.assertTrue(self.win.connect_btn.isEnabled())
        self.assertEqual(self.win.connect_btn.text(), "Connect")
        self.assertIn("Connection failed", self.win.conn_status.text())

    def test_2_9_conn_status_shows_user_and_de_count(self):
        """2.9 — conn_status label shows user name and DE count."""
        _simulate_connect(self.win)
        text = self.win.conn_status.text()
        self.assertIn("Test User", text)
        self.assertIn("3", text)  # fixture has 3 data_elements

    def test_2_13_change_conn_btn_appears_after_connect(self):
        """2.13 — change_conn_btn explicitly hidden before connect, shown after."""
        self.assertTrue(self.win.change_conn_btn.isHidden())
        _simulate_connect(self.win)
        self.assertFalse(self.win.change_conn_btn.isHidden())

    def test_2_14_auto_switch_to_chart_editor(self):
        """2.14 — After connect, app switches to Chart Editor panel (index 1)."""
        _simulate_connect(self.win)
        self.assertEqual(self.win._content.currentIndex(), 1)
        self.assertEqual(self.win._active_panel, "chart_editor")

    def test_2_15_nav_buttons_enabled_after_connect(self):
        """2.15 — Chart Editor + Dashboard nav buttons enabled after connect."""
        _simulate_connect(self.win)
        self.assertTrue(self.win._nav_btns["chart_editor"].isEnabled())
        self.assertTrue(self.win._nav_btns["dashboard"].isEnabled())


# ═══════════════════════════════════════════════════════════════════════════════
# Category 5 — Navigation
# ═══════════════════════════════════════════════════════════════════════════════

class TestNavigation(unittest.TestCase):

    def setUp(self):
        self.win = _make_window()
        _simulate_connect(self.win)

    def tearDown(self):
        self.win.close()
        _get_app().processEvents()

    def test_5_1_nav_switches_panels(self):
        """5.1 — _show_panel() switches to correct QStackedWidget indices."""
        self.win._show_panel("config")
        _get_app().processEvents()
        self.assertEqual(self.win._content.currentIndex(), 0)

        self.win._show_panel("chart_editor")
        _get_app().processEvents()
        self.assertEqual(self.win._content.currentIndex(), 1)

        self.win._show_panel("dashboard")
        _get_app().processEvents()
        self.assertEqual(self.win._content.currentIndex(), 2)

    def test_5_2_active_nav_button_has_dhis2_blue(self):
        """5.2 — Active nav button stylesheet contains DHIS2 blue colour (#1a6fa8)."""
        self.win._show_panel("chart_editor")
        _get_app().processEvents()
        style = self.win._nav_btns["chart_editor"].styleSheet()
        self.assertIn("1a6fa8", style.lower())

    def test_5_4_switch_to_dashboard_calls_refresh_library(self):
        """5.4 — Switching to Dashboard panel calls refresh_library() once."""
        with patch.object(self.win._dashboard_builder, "refresh_library") as mock_ref:
            self.win._show_panel("dashboard")
            _get_app().processEvents()
            mock_ref.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# Category 6 — Chart Editor: Chart Type Section
# ═══════════════════════════════════════════════════════════════════════════════

class TestChartTypeSection(unittest.TestCase):

    def setUp(self):
        self.win = _make_window()
        _simulate_connect(self.win)
        self.editor = self.win._chart_editor
        _get_app().processEvents()

    def tearDown(self):
        self.win.close()
        _get_app().processEvents()

    def test_6_1_chart_tile_count(self):
        """6.1 — At least 7 chart type tiles in the grid (actual count depends on plugin system)."""
        self.assertGreaterEqual(len(self.editor._chart_tiles), 7)

    def test_6_4_clicking_tile_sets_selected_template(self):
        """6.4 — Clicking a chart tile selects that template."""
        first_id = next(iter(self.editor._chart_tiles))
        tile = self.editor._chart_tiles[first_id]
        QTest.mouseClick(tile, Qt.MouseButton.LeftButton)
        _get_app().processEvents()
        self.assertIsNotNone(self.editor._selected_template)
        self.assertEqual(self.editor._selected_template["id"], first_id)

    def test_6_5_grid_collapses_after_selection(self):
        """6.5 — Chart grid collapses and summary row appears after tile click."""
        first_id = next(iter(self.editor._chart_tiles))
        QTest.mouseClick(self.editor._chart_tiles[first_id], Qt.MouseButton.LeftButton)
        _get_app().processEvents()
        self.assertFalse(self.editor._chart_grid_outer.isVisible())
        self.assertTrue(self.editor._chart_sel_row.isVisible())

    def test_6_6_expand_chart_grid_works(self):
        """6.6 — _expand_chart_grid() re-shows tile grid and hides summary row."""
        first_id = next(iter(self.editor._chart_tiles))
        QTest.mouseClick(self.editor._chart_tiles[first_id], Qt.MouseButton.LeftButton)
        _get_app().processEvents()
        self.editor._expand_chart_grid()
        _get_app().processEvents()
        self.assertTrue(self.editor._chart_grid_outer.isVisible())
        self.assertFalse(self.editor._chart_sel_row.isVisible())


# ═══════════════════════════════════════════════════════════════════════════════
# Category 7 — Chart Editor: Source Section
# ═══════════════════════════════════════════════════════════════════════════════

class TestSourceSection(unittest.TestCase):

    def setUp(self):
        self.win = _make_window()
        _simulate_connect(self.win)
        self.editor = self.win._chart_editor
        _get_app().processEvents()

    def tearDown(self):
        self.win.close()
        _get_app().processEvents()

    def test_7_1_program_checkbox_exists(self):
        """7.1 — Program (Tracker) checkbox exists and is a QCheckBox."""
        self.assertIsNotNone(self.editor._src_prog_cb)
        self.assertIsInstance(self.editor._src_prog_cb, QCheckBox)

    def test_7_2_aggregate_checkbox_exists(self):
        """7.2 — Aggregate Dataset checkbox exists and is a QCheckBox."""
        self.assertIsNotNone(self.editor._src_agg_cb)
        self.assertIsInstance(self.editor._src_agg_cb, QCheckBox)

    def test_7_3_program_dropdown_populated(self):
        """7.3 — Program dropdown contains fixture program after metadata load."""
        items = [self.editor._prog_menu.itemText(i)
                 for i in range(self.editor._prog_menu.count())]
        self.assertIn("Malaria Case Register", items)

    def test_7_4_selecting_program_populates_stage_dropdown(self):
        """7.4 — Selecting a program populates the stage dropdown with stages."""
        self.editor._src_prog_cb.setChecked(True)
        _get_app().processEvents()
        idx = self.editor._prog_menu.findText("Malaria Case Register")
        self.assertGreater(idx, 0)
        self.editor._prog_menu.setCurrentIndex(idx)
        _get_app().processEvents()
        self.assertGreater(self.editor._stage_menu.count(), 1)
        items = [self.editor._stage_menu.itemText(i)
                 for i in range(self.editor._stage_menu.count())]
        self.assertIn("Case Registration", items)

    def test_7_5_after_prog_select_de_items_populated(self):
        """7.5 — After program selection, _current_de_items is non-empty."""
        from charts.fixed_templates import FIXED_TEMPLATES
        self.editor._on_chart_type_click(FIXED_TEMPLATES[0])
        _get_app().processEvents()
        self.editor._src_prog_cb.setChecked(True)
        _get_app().processEvents()
        idx = self.editor._prog_menu.findText("Malaria Case Register")
        self.editor._prog_menu.setCurrentIndex(idx)
        _get_app().processEvents()
        self.assertGreater(len(self.editor._current_de_items), 0)

    def test_7_7_prog_checkbox_shows_hides_menu(self):
        """7.7 — Unchecking Program hides prog_menu; checking shows it."""
        self.editor._src_prog_cb.setChecked(True)
        _get_app().processEvents()
        self.assertTrue(self.editor._prog_menu.isVisible())

        self.editor._src_prog_cb.setChecked(False)
        _get_app().processEvents()
        self.assertFalse(self.editor._prog_menu.isVisible())

    def test_7_7b_agg_checkbox_shows_hides_search(self):
        """7.7b — Checking Agg shows agg_search_entry; unchecking hides it."""
        self.editor._src_agg_cb.setChecked(True)
        _get_app().processEvents()
        self.assertTrue(self.editor._agg_search_entry.isVisible())

        self.editor._src_agg_cb.setChecked(False)
        _get_app().processEvents()
        self.assertFalse(self.editor._agg_search_entry.isVisible())


# ═══════════════════════════════════════════════════════════════════════════════
# Category 8 — Chart Editor: Metrics Section
# ═══════════════════════════════════════════════════════════════════════════════

class TestMetricsSection(unittest.TestCase):

    def setUp(self):
        self.win = _make_window()
        _simulate_connect(self.win)
        self.editor = self.win._chart_editor
        from charts.fixed_templates import FIXED_TEMPLATES
        # Select first template and program to load DEs
        self.editor._on_chart_type_click(FIXED_TEMPLATES[0])
        self.editor._src_prog_cb.setChecked(True)
        _get_app().processEvents()
        idx = self.editor._prog_menu.findText("Malaria Case Register")
        if idx > 0:
            self.editor._prog_menu.setCurrentIndex(idx)
        _get_app().processEvents()

    def tearDown(self):
        self.win.close()
        _get_app().processEvents()

    def test_8_1_de_scroll_max_height(self):
        """8.1 — DE list scroll area max height <= 145px."""
        self.assertLessEqual(self.editor._de_scroll.maximumHeight(), 145)

    def test_8_2_search_filters_de_list(self):
        """8.2 — Search text filters _current_de_items."""
        # Use _on_de_search_changed directly — avoids slow per-character QTest events
        self.editor._on_de_search_changed("")
        _get_app().processEvents()
        initial_count = len(self.editor._current_de_items)

        self.editor._on_de_search_changed("Diagnosis")
        _get_app().processEvents()
        filtered_count = len(self.editor._current_de_items)
        self.assertLessEqual(filtered_count, initial_count)

    def test_8_3_clearing_search_restores_list(self):
        """8.3 — Calling _refresh_de_list() restores full DE list after filtering."""
        # Capture initial count
        self.editor._on_de_search_changed("")
        _get_app().processEvents()
        initial_count = len(self.editor._current_de_items)

        # Filter to nothing
        self.editor._on_de_search_changed("xyz_no_match")
        _get_app().processEvents()
        self.assertEqual(len(self.editor._current_de_items), 0)

        # Restore via _refresh_de_list (what happens when user changes source)
        self.editor._refresh_de_list()
        _get_app().processEvents()
        restored = len(self.editor._current_de_items)
        self.assertGreaterEqual(restored, initial_count)

    def test_8_6_max_de_selection_enforced(self):
        """8.6 — Cannot select more DEs than template _max_des."""
        max_de = self.editor._max_des
        for de, cb, *_ in self.editor._de_checkboxes:
            cb.setChecked(True)
            self.editor._on_de_check()
            _get_app().processEvents()
        self.assertLessEqual(len(self.editor._get_selected_des()), max_de)

    def test_8_7_sel_label_reflects_selection(self):
        """8.7 — _sel_lbl shows checkmark when a DE is selected, blank when none."""
        for de, cb, *_ in self.editor._de_checkboxes:
            cb.setChecked(False)
        self.editor._on_de_check()
        _get_app().processEvents()
        self.assertNotIn("✓", self.editor._sel_lbl.text())

        if self.editor._de_checkboxes:
            de, cb, *_ = self.editor._de_checkboxes[0]
            cb.setChecked(True)
            self.editor._on_de_check()
            _get_app().processEvents()
            self.assertIn("✓", self.editor._sel_lbl.text())


# ═══════════════════════════════════════════════════════════════════════════════
# Category 13 — Chart Editor: Actions
# ═══════════════════════════════════════════════════════════════════════════════

_FAKE_CFG = {
    "template_id":    "ft_bar_monthly",
    "template_label": "Bar — monthly trend",
    "title":          "Test Chart",
    "name":           "Test Chart",
    "col_width":      6,
    "chart_color":    "#1a6fa8",
    "mode":           "fixed",
    "de_sources":     [{"uid": "psde001", "name": "Diagnosis Test Result",
                        "type": "tracker_option"}],
    "custom_options": {},
    "pinned":         {},
}


class TestChartEditorActions(unittest.TestCase):

    def setUp(self):
        self.win = _make_window()
        _simulate_connect(self.win)
        self.editor = self.win._chart_editor
        _get_app().processEvents()

    def tearDown(self):
        self.win.close()
        _get_app().processEvents()

    def test_13_1_save_adds_to_library(self):
        """13.1 — _on_save() with valid config saves chart to library."""
        from config.chart_library import load_charts, delete_chart
        with (
            patch.object(self.editor, "_build_config", return_value=dict(_FAKE_CFG)),
            patch("ui.chart_editor_panel.QInputDialog.getText",
                  return_value=("Test Chart 13_1", True)),
        ):
            self.editor._on_save()
            _get_app().processEvents()

        charts = load_charts()
        names = [c.get("name") for c in charts]
        self.assertIn("Test Chart 13_1", names)
        for c in charts:
            if c.get("name") == "Test Chart 13_1":
                delete_chart(c["id"])

    def test_13_2_add_to_dashboard_switches_panel(self):
        """13.2 — _on_add_to_dashboard() calls dashboard.add_card and switches panel."""
        with patch.object(self.editor, "_build_config", return_value=dict(_FAKE_CFG)):
            with patch.object(self.win._dashboard_builder, "add_card") as mock_add:
                self.editor._on_add_to_dashboard()
                _get_app().processEvents()
            mock_add.assert_called_once()
        self.assertEqual(self.win._content.currentIndex(), 2)


# ═══════════════════════════════════════════════════════════════════════════════
# Category 14 — Dashboard Builder Panel
# ═══════════════════════════════════════════════════════════════════════════════

_CARD_CFG = {
    "name":           "Test Card",
    "title":          "Test Card",
    "template_id":    "ft_bar_monthly",
    "template_label": "Bar",
    "col_width":      6,
    "chart_color":    "#1a6fa8",
    "mode":           "fixed",
    "de_sources":     [],
    "custom_options": {},
}


class TestDashboardBuilder(unittest.TestCase):

    def setUp(self):
        self.win = _make_window()
        _simulate_connect(self.win)
        self.win._show_panel("dashboard")
        _get_app().processEvents()
        self.dash = self.win._dashboard_builder

    def tearDown(self):
        self.win.close()
        _get_app().processEvents()

    def test_14_1_two_column_layout(self):
        """14.1 — Dashboard has a QSplitter with 2 panes."""
        from PySide6.QtWidgets import QSplitter
        splitter = self.dash.findChild(QSplitter)
        self.assertIsNotNone(splitter)
        self.assertEqual(splitter.count(), 2)

    def test_14_7_add_card_appends(self):
        """14.7 — add_card() appends to _cards and _card_widgets."""
        count_before = len(self.dash._cards)
        self.dash.add_card(dict(_CARD_CFG))
        _get_app().processEvents()
        self.assertEqual(len(self.dash._cards), count_before + 1)
        self.assertEqual(len(self.dash._card_widgets), count_before + 1)

    def test_14_8_remove_card_decrements(self):
        """14.8 — _remove_card() removes the card from _cards/_card_widgets."""
        self.dash.add_card(dict(_CARD_CFG))
        _get_app().processEvents()
        count_before = len(self.dash._cards)
        widget = self.dash._card_widgets[-1]
        self.dash._remove_card(widget)
        _get_app().processEvents()
        self.assertEqual(len(self.dash._cards), count_before - 1)

    def test_14_9_card_count_label_updates(self):
        """14.9 — _card_count_lbl shows updated count after add."""
        for w in list(self.dash._card_widgets):
            self.dash._remove_card(w)
        _get_app().processEvents()
        self.dash.add_card(dict(_CARD_CFG))
        _get_app().processEvents()
        self.assertIn("1", self.dash._card_count_lbl.text())

    def test_14_13_export_deploy_disabled_when_empty(self):
        """14.13 — Export/Deploy disabled when canvas is empty."""
        for w in list(self.dash._card_widgets):
            self.dash._remove_card(w)
        _get_app().processEvents()
        self.assertFalse(self.dash._export_btn.isEnabled())
        self.assertFalse(self.dash._deploy_btn.isEnabled())

    def test_14_13b_export_deploy_enabled_after_add(self):
        """14.13b — Export/Deploy enabled after a card is added."""
        self.dash.add_card(dict(_CARD_CFG))
        _get_app().processEvents()
        self.assertTrue(self.dash._export_btn.isEnabled())
        self.assertTrue(self.dash._deploy_btn.isEnabled())

    def test_14_14_clear_all_removes_all_cards(self):
        """14.14 — _on_clear_all() clears everything when user confirms Yes."""
        self.dash.add_card(dict(_CARD_CFG))
        self.dash.add_card(dict(_CARD_CFG))
        _get_app().processEvents()
        self.assertGreater(len(self.dash._cards), 0)

        with patch("ui.dashboard_builder_panel.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.Yes):
            self.dash._on_clear_all()
            _get_app().processEvents()

        self.assertEqual(len(self.dash._cards), 0)
        self.assertEqual(len(self.dash._card_widgets), 0)


# ═══════════════════════════════════════════════════════════════════════════════
# Category 15 — Status Bar
# ═══════════════════════════════════════════════════════════════════════════════

class TestStatusBar(unittest.TestCase):

    def setUp(self):
        self.win = _make_window()

    def tearDown(self):
        self.win.close()
        _get_app().processEvents()

    def test_15_1_status_bar_visible(self):
        """15.1 — Status bar is present and visible."""
        sb = self.win.statusBar()
        self.assertIsNotNone(sb)
        self.assertTrue(sb.isVisible())

    def test_15_2_error_status_red(self):
        """15.2 — _set_status(error=True) applies #e74c3c to status_label."""
        self.win._set_status("Something failed", error=True)
        _get_app().processEvents()
        style = self.win.status_label.styleSheet()
        self.assertIn("e74c3c", style)
        self.assertEqual(self.win.status_label.text(), "Something failed")

    def test_15_3_progress_indeterminate(self):
        """15.3 — _start_progress() sets range(0, 0) (indeterminate)."""
        self.win._start_progress()
        _get_app().processEvents()
        self.assertEqual(self.win.progress.minimum(), 0)
        self.assertEqual(self.win.progress.maximum(), 0)

    def test_15_4_progress_stops(self):
        """15.4 — _stop_progress() restores non-zero maximum."""
        self.win._start_progress()
        self.win._stop_progress()
        _get_app().processEvents()
        self.assertGreater(self.win.progress.maximum(), 0)


# ═══════════════════════════════════════════════════════════════════════════════
# Category 16 — Non-UI Regression
# ═══════════════════════════════════════════════════════════════════════════════

class TestNonUIRegression(unittest.TestCase):

    def test_16_3_all_templates_generate_html(self):
        """16.3 — Every fixed template generates non-empty HTML without exception."""
        from charts.fixed_templates import generate_preview_page, FIXED_TEMPLATES
        # Minimal sources: 2 aggregate metrics covers multi-DE plugins (line_multi,
        # grouped_bar, combined_bar_line require >= 2). de_sources + de_uid cover
        # legacy _build_per_card_js paths that don't read "metrics".
        _min_metrics = [
            {"uid": "TstDE0001", "name": "Metric A", "type": "aggregate"},
            {"uid": "TstDE0002", "name": "Metric B", "type": "aggregate"},
        ]
        _min_de_sources = [
            {"uid": "TstDE0001", "name": "Metric A", "type": "aggregate",
             "de_uid": "TstDE0001"},
        ]
        for tmpl in FIXED_TEMPLATES:
            tmpl_id = tmpl.get("id", tmpl.get("key", ""))
            cfg = {
                "plugin_id":      tmpl_id,
                "template_id":    tmpl_id,
                "title":          f"Test {tmpl.get('label', '')}",
                "col_width":      6,
                "color":          "#1a6fa8",
                "chart_color":    "#1a6fa8",
                "de_sources":     _min_de_sources,
                "metrics":        _min_metrics,
                "de_uid":         "TstDE0001",
                "custom_options": {},
                "dimensions":     {},
            }
            try:
                html = generate_preview_page(cfg, title=f"Test {tmpl.get('label', '')}")
                self.assertIn("<html", html.lower(),
                              msg=f"Template {tmpl_id} returned no <html>")
                self.assertGreater(len(html), 50)
            except Exception as exc:
                self.fail(f"Template {tmpl_id} raised: {exc}")

    def test_16_6_preview_sim_passes(self):
        """16.6 — test_preview_app_sim.py reports PASS and no FAIL."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "test_preview_app_sim.py"],
            capture_output=True, text=True,
            cwd=str(REPO), timeout=90,
        )
        output = result.stdout + result.stderr
        self.assertIn("PASS", output,
                      msg=f"test_preview_app_sim had no PASS:\n{output}")
        self.assertNotIn("FAIL", output,
                         msg=f"test_preview_app_sim has FAILs:\n{output}")


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _get_app()  # ensure QApplication exists before any TestCase.setUp
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    for cls in [
        TestStartup,
        TestConnection,
        TestNavigation,
        TestChartTypeSection,
        TestSourceSection,
        TestMetricsSection,
        TestChartEditorActions,
        TestDashboardBuilder,
        TestStatusBar,
        TestNonUIRegression,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
