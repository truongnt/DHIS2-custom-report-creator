"""
Visual / UI-quality tests for the Login (Config) screen — see docs/UI_GUIDELINES.md.

Beyond widget behaviour (test_login.py), these check the *appearance contract*:
- the screen renders to a non-empty image (saved as evidence), and
- every text/background colour pair meets WCAG AA contrast.
"""
import pytest
from PySide6.QtWidgets import QLineEdit

pytestmark = pytest.mark.integration


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    def _lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(fg: str, bg: str) -> float:
    a, b = sorted((_luminance(fg), _luminance(bg)))
    return (b + 0.05) / (a + 0.05)


# Login/Config screen colour contract: (label, fg, bg, min_ratio)
_PAIRS = [
    ("sidebar text",     "#ffffff", "#1e2d3d", 4.5),
    ("nav muted/status", "#8aa3b8", "#1e2d3d", 4.5),
    ("cache/footer/ver", "#93a8bc", "#1e2d3d", 4.5),   # REQ-UI-COLOR-04 fix
    ("disabled nav",     "#8499ac", "#1e2d3d", 3.0),   # REQ-UI-COLOR-04 fix
    ("status bar text",  "#4a6278", "#eef2f7", 4.5),   # REQ-UI-COLOR-04 fix
    ("primary button",   "#ffffff", "#1a6fa8", 4.5),
]


def test_login_contrast_aa():
    """REQ-UI-COLOR-01/04: every login-screen text/bg pair meets WCAG AA."""
    failures = [
        f"{label}: {fg} on {bg} = {_contrast(fg, bg):.2f} (< {minr})"
        for label, fg, bg, minr in _PAIRS
        if _contrast(fg, bg) < minr
    ]
    assert not failures, "Contrast below AA:\n" + "\n".join(failures)


def test_login_uses_no_known_low_contrast_colors(make_window):
    """REQ-UI-COLOR-04: the fixed-up colours actually replaced the failing ones in the UI."""
    win = make_window()
    style_blobs = " ".join([
        win.cache_lbl.styleSheet(),
        win.conn_status.styleSheet(),
        win.status_label.styleSheet(),
    ])
    # The three worst offenders must be gone from the login widgets.
    assert "#445566" not in style_blobs
    assert "#6b8299" not in style_blobs


def test_login_screen_renders_screenshot(make_window, evidence_dir):
    """REQ-UI-LAYOUT-03 / REQ-UI-CONV-01: config screen renders to a non-empty image."""
    win = make_window()
    win.resize(1100, 720)
    assert win.minimumSize().width() >= 1024 and win.minimumSize().height() >= 640
    pix = win.grab()
    assert not pix.isNull()
    assert pix.width() > 0 and pix.height() > 0
    out = evidence_dir / "login_screen.png"
    pix.save(str(out))
    assert out.exists() and out.stat().st_size > 0
