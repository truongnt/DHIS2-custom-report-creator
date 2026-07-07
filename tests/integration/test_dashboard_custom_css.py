"""
Integration tests — dashboard-level custom CSS (PART L of docs/DASHBOARD_REQUIREMENTS.md).

Prove that:
- assemble_dashboard injects user CSS into <head>, AFTER the default <style> (so it overrides),
- empty CSS injects no extra style tag,
- custom_css round-trips through save/load,
- the panel threads custom_css into Preview / Export.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def _cfg(title, w=6):
    return {"title": title, "col_width": w, "template_label": "Bar",
            "template_id": "bar_monthly"}


def test_assemble_injects_custom_css():
    """REQ-DASH-CSS-03: user CSS lands in a dedicated <style> block in <head>."""
    from charts.fixed_templates import assemble_dashboard
    css = ".card-header{background:#900 !important;}"
    html = assemble_dashboard([_cfg("A")], title="T", custom_css=css)
    assert 'id="dashboard-custom-css"' in html
    assert css in html
    # Must sit inside <head> (before <body>) so it applies before render.
    assert html.index("dashboard-custom-css") < html.index("<body")


def test_custom_css_overrides_default_style():
    """REQ-DASH-CSS-03: the custom block appears AFTER the default <style> → wins on specificity ties."""
    from charts.fixed_templates import assemble_dashboard
    css = "body{background:#000;}"
    html = assemble_dashboard([_cfg("A")], title="T", custom_css=css)
    default_style = html.index(".card-header")            # from the default <style>
    custom_block = html.index("dashboard-custom-css")
    assert custom_block > default_style


def test_empty_css_adds_no_style_tag():
    """REQ-DASH-CSS-03: no custom CSS → no dashboard-custom-css tag at all."""
    from charts.fixed_templates import assemble_dashboard
    for css in (None, "", "   "):
        html = assemble_dashboard([_cfg("A")], title="T", custom_css=css)
        assert "dashboard-custom-css" not in html


def test_custom_css_round_trips_through_save_load(qtbot, tmp_path, monkeypatch):
    """REQ-DASH-CSS-04: custom_css persists with the dashboard entry and restores on load."""
    import config.dashboard_library as lib
    monkeypatch.setattr(lib, "_LIBRARY_FILE", tmp_path / "dash.json")
    from ui.dashboard_builder_panel import DashboardBuilderPanel

    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    p._manual_btn.click()
    p.add_card(_cfg("A", 6))
    p._dash_custom_css = ".card{border-radius:12px;}"

    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.information", lambda *a, **k: None)
    monkeypatch.setattr("ui.save_entity_dialog.SaveEntityDialog.prompt",
                        staticmethod(lambda *a, **k: ("DashCss", "")))
    p._on_save_dashboard()

    saved = lib.load_dashboards()[0]
    assert saved["custom_css"] == ".card{border-radius:12px;}"

    p2 = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p2)
    p2.load_dashboard_entry(saved)
    assert p2._dash_custom_css == ".card{border-radius:12px;}"


def test_preview_passes_custom_css(qtbot, monkeypatch):
    """REQ-DASH-CSS-05: Preview threads custom_css into the assembled HTML."""
    served = {}
    monkeypatch.setattr("ui.preview_window.update_preview",
                        lambda html, title="": served.update(html=html))
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    p._manual_btn.click()
    p.add_card(_cfg("A", 6))
    p._dash_custom_css = ".chart-wrapper{outline:2px solid lime;}"
    p._on_preview()
    assert ".chart-wrapper{outline:2px solid lime;}" in served["html"]
    assert 'id="dashboard-custom-css"' in served["html"]


def test_style_templates_available(qtbot):
    """REQ-DASH-CSS-06: a set of ready-made style templates exists, incl. an editable Base."""
    from ui.dashboard_css_dialog import STYLE_TEMPLATES
    assert "Base (current defaults)" in STYLE_TEMPLATES
    # A few themes to choose from.
    assert {"Dark", "Compact"}.issubset(STYLE_TEMPLATES.keys())
    assert all(css.strip() for css in STYLE_TEMPLATES.values())


def test_apply_template_fills_editor(qtbot):
    """REQ-DASH-CSS-06: picking a template loads its CSS into the editor."""
    from ui.dashboard_css_dialog import CustomCssDialog, STYLE_TEMPLATES
    dlg = CustomCssDialog(None, "")            # empty editor → no confirm prompt
    qtbot.addWidget(dlg)
    dlg.apply_template("Dark")
    assert dlg._edit.toPlainText() == STYLE_TEMPLATES["Dark"]


def test_base_template_targets_real_default_selectors(qtbot):
    """REQ-DASH-CSS-06: the Base template edits the SAME selectors the page actually uses,
    so tweaking it overrides the real defaults (not dead CSS)."""
    from ui.dashboard_css_dialog import STYLE_TEMPLATES
    from charts.fixed_templates import assemble_dashboard
    base = STYLE_TEMPLATES["Base (current defaults)"]
    html = assemble_dashboard([_cfg("A")], title="T")
    # selector-in-base → marker the rendered page must contain for that selector to bite.
    for selector, marker in ((".card-header", ".card-header"),
                             ("#controls", 'id="controls"'),
                             (".chart-wrapper", "chart-wrapper")):
        assert selector in base                # base template mentions it
        assert marker in html                  # and the rendered page really uses it


def test_insert_color_at_cursor(qtbot):
    """REQ-DASH-CSS-07: colour hex is inserted into the editor at the cursor."""
    from ui.dashboard_css_dialog import CustomCssDialog
    dlg = CustomCssDialog(None, "body{color:}")
    qtbot.addWidget(dlg)
    # Place cursor right before the closing brace, then insert a hex.
    cur = dlg._edit.textCursor()
    cur.setPosition(len("body{color:"))
    dlg._edit.setTextCursor(cur)
    dlg.insert_at_cursor("#ff8800")
    assert dlg._edit.toPlainText() == "body{color:#ff8800}"


def test_card_spacing_css_helper():
    """REQ-DASH-CSS-08: helper builds gutter CSS AND neutralises mb-4 so the gap is exact."""
    from ui.dashboard_css_dialog import card_spacing_css
    css = card_spacing_css(30)
    assert "--bs-gutter-x:30px" in css and "--bs-gutter-y:30px" in css
    assert ".container-fluid .row" in css
    # The fixed mb-4 on each card column must be cancelled or it stacks onto the gutter.
    assert "margin-bottom:0 !important" in css


def test_spacing_targets_the_real_card_columns():
    """REQ-DASH-CSS-08: the columns the spacing CSS targets are the columns cards render into."""
    from ui.dashboard_css_dialog import card_spacing_css
    from charts.fixed_templates import assemble_dashboard
    html = assemble_dashboard([_cfg("A", 6), _cfg("B", 6)], title="T", custom_css=card_spacing_css(40))
    assert 'class="col-md-6 mb-4"' in html          # cards are mb-4 columns …
    assert 'margin-bottom:0 !important' in html      # … which the injected CSS neutralises


def test_base_template_spaces_cards():
    """REQ-DASH-CSS-08: the Base template already controls card spacing via grid gutters."""
    from ui.dashboard_css_dialog import STYLE_TEMPLATES
    assert "--bs-gutter" in STYLE_TEMPLATES["Base (current defaults)"]


def test_open_selects_matching_template(qtbot):
    """REQ-DASH-CSS-11: opening with CSS equal to a template selects that template in the dropdown."""
    from ui.dashboard_css_dialog import CustomCssDialog, STYLE_TEMPLATES
    dlg = CustomCssDialog(None, STYLE_TEMPLATES["Dark"])
    qtbot.addWidget(dlg)
    assert dlg._tmpl.currentText() == "Dark"


def test_open_custom_css_shows_hint(qtbot):
    """REQ-DASH-CSS-11: opening with CSS that matches no template leaves the hint selected."""
    from ui.dashboard_css_dialog import CustomCssDialog, _PICK_HINT
    dlg = CustomCssDialog(None, ".xyz{color:hotpink;}")
    qtbot.addWidget(dlg)
    assert dlg._tmpl.currentText() == _PICK_HINT


def test_edited_template_saves_as_new(qtbot, tmp_path, monkeypatch):
    """REQ-DASH-CSS-10: editing a template and naming it persists a new user template."""
    import config.css_template_library as lib
    monkeypatch.setattr(lib, "_LIBRARY_FILE", tmp_path / "css_templates.json")
    from ui.dashboard_css_dialog import CustomCssDialog, STYLE_TEMPLATES
    dlg = CustomCssDialog(None, STYLE_TEMPLATES["Dark"])   # opens on "Dark"
    qtbot.addWidget(dlg)
    assert dlg._tmpl.currentText() == "Dark"
    # User edits the CSS → now differs from every known template.
    dlg._edit.setPlainText(STYLE_TEMPLATES["Dark"] + "\n.card{border-radius:20px;}")
    # On Apply the dialog asks for a name; accept with "Dark rounded".
    monkeypatch.setattr("PySide6.QtWidgets.QInputDialog.getText",
                        staticmethod(lambda *a, **k: ("Dark rounded", True)))
    dlg._on_ok()
    saved = lib.load_css_templates()
    assert "Dark rounded" in saved
    assert ".card{border-radius:20px;}" in saved["Dark rounded"]


def test_user_template_appears_in_dropdown(qtbot, tmp_path, monkeypatch):
    """REQ-DASH-CSS-10: a saved user template is merged into a freshly opened dialog's dropdown."""
    import config.css_template_library as lib
    monkeypatch.setattr(lib, "_LIBRARY_FILE", tmp_path / "css_templates.json")
    lib.save_css_template("My brand", ".card-header{background:#e91e63;}")
    from ui.dashboard_css_dialog import CustomCssDialog
    dlg = CustomCssDialog(None, "")
    qtbot.addWidget(dlg)
    assert dlg._tmpl.findText("My brand") >= 0
    # And opening on that exact CSS selects it.
    dlg2 = CustomCssDialog(None, ".card-header{background:#e91e63;}")
    qtbot.addWidget(dlg2)
    assert dlg2._tmpl.currentText() == "My brand"


def test_typed_from_scratch_not_prompted_to_save(qtbot, tmp_path, monkeypatch):
    """REQ-DASH-CSS-10: CSS typed with no template selected does NOT trigger the save prompt."""
    import config.css_template_library as lib
    monkeypatch.setattr(lib, "_LIBRARY_FILE", tmp_path / "css_templates.json")
    called = {"n": 0}
    monkeypatch.setattr("PySide6.QtWidgets.QInputDialog.getText",
                        staticmethod(lambda *a, **k: called.__setitem__("n", called["n"] + 1) or ("", False)))
    from ui.dashboard_css_dialog import CustomCssDialog
    dlg = CustomCssDialog(None, "")                 # hint selected
    qtbot.addWidget(dlg)
    dlg._edit.setPlainText(".from-scratch{color:red;}")
    dlg._on_ok()
    assert called["n"] == 0
    assert lib.load_css_templates() == {}


def test_apply_refreshes_open_preview(qtbot, monkeypatch):
    """REQ-DASH-CSS-09: editing CSS while a preview is open re-pushes HTML with the new CSS."""
    served = {}
    monkeypatch.setattr("ui.preview_window.update_preview",
                        lambda html, title="": served.update(html=html))
    monkeypatch.setattr("ui.preview_server.is_preview_open", lambda: True)
    monkeypatch.setattr("ui.dashboard_css_dialog.CustomCssDialog.prompt",
                        classmethod(lambda cls, parent, css="": ".card{border:3px solid red;}"))
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    p._manual_btn.click()
    p.add_card(_cfg("A", 6))
    p._on_edit_css()
    assert p._dash_custom_css == ".card{border:3px solid red;}"
    assert ".card{border:3px solid red;}" in served["html"]


def test_apply_does_not_open_preview_when_none(qtbot, monkeypatch):
    """REQ-DASH-CSS-09: no preview open → editing CSS must NOT force-open one."""
    called = {"n": 0}
    monkeypatch.setattr("ui.preview_window.update_preview",
                        lambda html, title="": called.__setitem__("n", called["n"] + 1))
    monkeypatch.setattr("ui.preview_server.is_preview_open", lambda: False)
    monkeypatch.setattr("ui.dashboard_css_dialog.CustomCssDialog.prompt",
                        classmethod(lambda cls, parent, css="": "body{margin:0;}"))
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    p._manual_btn.click()
    p.add_card(_cfg("A", 6))
    p._on_edit_css()
    assert called["n"] == 0


def test_every_template_rule_has_a_comment(qtbot):
    """REQ-DASH-CSS-12: each CSS rule line in every template carries an explanatory comment."""
    from ui.dashboard_css_dialog import STYLE_TEMPLATES
    for name, css in STYLE_TEMPLATES.items():
        for line in css.splitlines():
            s = line.strip()
            if "{" in s and "}" in s:            # a one-line rule
                assert "/*" in s and "*/" in s, f"Uncommented rule in '{name}': {s}"


def test_filter_layouts_available(qtbot):
    """REQ-DASH-CSS-13: filter-bar layout presets cover top/left/right and sticky/scroll."""
    from ui.dashboard_css_dialog import FILTER_LAYOUTS
    keys = " ".join(FILTER_LAYOUTS.keys()).lower()
    assert "top" in keys and "left" in keys and "right" in keys
    assert "sticky" in keys and "scroll" in keys
    # Layout-only: they restyle #controls but set no colours.
    for css in FILTER_LAYOUTS.values():
        assert "#controls" in css
        assert "background:#" not in css.replace(" ", "")


def test_filter_layouts_cover_all_positions_x_behaviours(qtbot):
    """REQ-DASH-CSS-13: every position (top/left/right) has BOTH sticky and scroll variants."""
    from ui.dashboard_css_dialog import FILTER_LAYOUTS
    for pos in ("Top", "Left", "Right"):
        assert any(k.startswith(pos) and "sticky" in k for k in FILTER_LAYOUTS), \
               f"missing sticky for {pos}"
        assert any(k.startswith(pos) and "scroll" in k for k in FILTER_LAYOUTS), \
               f"missing scroll for {pos}"
    # The scroll side columns move with the page (float, not fixed).
    assert "float:left" in FILTER_LAYOUTS["Left sidebar · scroll"]
    assert "position:fixed" not in FILTER_LAYOUTS["Left sidebar · scroll"]


def test_filter_layout_overrides_inline_with_important(qtbot):
    """REQ-DASH-CSS-13: left/right layouts must use !important to beat #controls inline styles."""
    from ui.dashboard_css_dialog import FILTER_LAYOUTS
    left = FILTER_LAYOUTS["Left sidebar · sticky"]
    assert "position:fixed !important" in left
    assert "flex-direction:column !important" in left


def test_pick_filter_layout_appends_to_editor(qtbot):
    """REQ-DASH-CSS-13: choosing a filter layout appends its CSS at the end of the editor."""
    from ui.dashboard_css_dialog import CustomCssDialog, FILTER_LAYOUTS
    dlg = CustomCssDialog(None, "body{margin:0;}")
    qtbot.addWidget(dlg)
    idx = dlg._filt.findText("Right sidebar · sticky")
    dlg._on_pick_filter_layout(idx)
    text = dlg._edit.toPlainText()
    assert "margin-right:220px" in text
    assert text.index("body{margin:0;}") < text.index("position:fixed")
    assert dlg._filt.currentIndex() == 0          # reset back to the hint


def test_export_callback_receives_custom_css(qtbot):
    """REQ-DASH-CSS-05: export callback is handed the dashboard custom_css."""
    captured = {}
    p = DashboardBuilderPanel = None
    from ui.dashboard_builder_panel import DashboardBuilderPanel as Panel
    p = Panel(None, {"on_export": lambda cards, filters=None, custom_css="": captured.update(css=custom_css)})
    qtbot.addWidget(p)
    p._manual_btn.click()
    p.add_card(_cfg("A", 6))
    p._dash_custom_css = "body{margin:0;}"
    p._on_export()
    assert captured["css"] == "body{margin:0;}"
