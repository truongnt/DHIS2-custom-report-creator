"""Shared metadata display format "(DE) Name" + per-type colours (REQ-META-DISPLAY)."""
from __future__ import annotations

from ui.metadata_display import code_for, plain_label, html_label, TYPE_COLORS


def test_code_for_by_kind():
    """REQ-META-DISPLAY-01: explicit kind labels map to short codes."""
    assert code_for({"kind": "Data Element"}) == "DE"
    assert code_for({"kind": "Tracker DE"}) == "DE"
    assert code_for({"kind": "Tracked Attribute"}) == "PA"
    assert code_for({"kind": "Indicator"}) == "I"
    assert code_for({"kind": "Program Indicator"}) == "PI"
    # short codes pass through
    for c in ("DE", "PA", "I", "PI"):
        assert code_for({"kind": c}) == c


def test_code_for_inferred_from_type():
    """REQ-META-DISPLAY-01: fall back to type/flags when no kind is present."""
    assert code_for({"type": "aggregate"}) == "DE"
    assert code_for({"type": "tracker_option"}) == "DE"
    assert code_for({"type": "indicator"}) == "I"                       # no program → aggregate ind
    assert code_for({"type": "indicator", "prog_uid": "P", "is_pi": True}) == "PI"
    assert code_for({"type": "tracker_numeric", "is_tea": True}) == "PA"


def test_plain_label_format():
    """REQ-META-DISPLAY-02: canonical "(CODE) Name" format."""
    assert plain_label({"kind": "DE", "name": "Cases"}) == "(DE) Cases"
    assert plain_label({"kind": "PI", "name": "Incidence"}) == "(PI) Incidence"


def test_html_label_colours_prefix():
    """REQ-META-DISPLAY-03: the prefix is wrapped in a span with the type's colour."""
    html = html_label({"kind": "DE", "name": "Cases"})
    assert TYPE_COLORS["DE"] in html and "(DE)" in html and "Cases" in html
    # each type gets a distinct colour
    assert len(set(TYPE_COLORS.values())) == 4
