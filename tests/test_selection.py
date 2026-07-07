"""Tests for config.selection — per-instance in-use metadata selection (REQ-META-SEL)."""
from __future__ import annotations

import pytest

import config.selection as sel


@pytest.fixture(autouse=True)
def _tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(sel, "_CACHE_ROOT", tmp_path)


URL = "https://hmis.gov.la/hmis"


def test_empty_when_missing():
    """REQ-META-SEL-01: no file → empty set."""
    assert sel.load_selection(URL) == set()


def test_save_load_round_trip():
    """REQ-META-SEL-02: saved UIDs come back as a set."""
    sel.save_selection(URL, ["a1", "b2", "c3"])
    assert sel.load_selection(URL) == {"a1", "b2", "c3"}


def test_dedup_and_skip_blanks():
    """REQ-META-SEL-03: duplicates and blanks are dropped on save."""
    sel.save_selection(URL, ["a1", "a1", "", "b2", None])
    assert sel.load_selection(URL) == {"a1", "b2"}


def test_per_instance_isolation():
    """REQ-META-SEL-04: different DHIS2 URLs don't share selections."""
    sel.save_selection(URL, ["a1"])
    sel.save_selection("https://other.org/dhis", ["z9"])
    assert sel.load_selection(URL) == {"a1"}
    assert sel.load_selection("https://other.org/dhis") == {"z9"}


def test_overwrite_replaces():
    """REQ-META-SEL-05: saving again replaces the previous set."""
    sel.save_selection(URL, ["a1", "b2"])
    sel.save_selection(URL, ["c3"])
    assert sel.load_selection(URL) == {"c3"}
