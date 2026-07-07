"""
Integration tests for the HTML template gallery dialog (ui.html_template_gallery).

REQ-HTMPL-05  gallery lists saved templates as cards; 'Use' sets result_html
REQ-HTMPL-06  empty store shows a placeholder, no crash
"""
import pytest

pytest.importorskip("PySide6")

import config.html_template_library as htl
from ui.html_template_gallery import HtmlTemplateGallery


@pytest.fixture
def lib(tmp_path, monkeypatch):
    d = tmp_path / "html_templates"
    monkeypatch.setattr(htl, "_DIR", d)
    monkeypatch.setattr(htl, "_INDEX", d / "index.json")
    return htl


def test_gallery_use_returns_html(qtbot, lib):  # REQ-HTMPL-05
    lib.save_template(b"img-bytes-x", "<div>saved</div>", model="claude-opus-4-8",
                      created_at="2026-06-30 10:00")
    dlg = HtmlTemplateGallery()
    qtbot.addWidget(dlg)
    entry = lib.load_index()[0]
    dlg._use(entry)                       # simulate clicking "Use"
    assert dlg.result_html == "<div>saved</div>"


def test_gallery_empty(qtbot, lib):  # REQ-HTMPL-06
    dlg = HtmlTemplateGallery()
    qtbot.addWidget(dlg)
    assert dlg.result_html is None        # nothing selected, no crash
