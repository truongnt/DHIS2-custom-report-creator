"""Integration-tier fixtures — drive the real AppWindow via pytest-qt (qtbot)."""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture
def make_window(qtbot):
    """Factory: build AppWindow with credential lookups mocked (no network/keyring).

    Usage: win = make_window()                          # no saved profiles
           win = make_window(profiles=[{...}], password="pw")
    Auto-connect (when profiles+password given) schedules _on_connect via QTimer —
    patch AppWindow._on_connect in the test if you don't want the real worker to run.
    """
    created = []

    def _make(profiles=None, api_key="", password=""):
        with patch("config.credentials.load_profiles", return_value=profiles or []), \
             patch("config.credentials.load_api_key", return_value=api_key), \
             patch("config.credentials.load_password", return_value=password):
            from ui.app_window import AppWindow
            win = AppWindow()
        qtbot.addWidget(win)
        created.append(win)
        return win

    yield _make

    for w in created:
        try:
            w.close()
        except Exception:
            pass
