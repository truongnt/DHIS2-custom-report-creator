"""Tests for config.descriptions — local DE/PA description storage.

REQ-DESC-01  save_description persists a non-empty text for a UID
REQ-DESC-02  load_descriptions returns saved text after restart (file round-trip)
REQ-DESC-03  multiple UIDs are stored independently
REQ-DESC-04  empty/blank description removes the entry (no orphan keys)
REQ-DESC-05  save_descriptions_bulk persists multiple UIDs at once
REQ-DESC-06  unknown base_url returns empty dict (no error)
REQ-DESC-07  descriptions stored per-instance (different URLs don't share)
"""
from __future__ import annotations

import json
import sys
import os
from pathlib import Path

import pytest

# Resolve repo root so imports work without installation
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from config.descriptions import (
    _desc_path,
    load_descriptions,
    save_description,
    save_descriptions_bulk,
)

# ── Helpers ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_url(tmp_path, monkeypatch):
    """Patch the cache root so tests write to a temp dir, not the real cache."""
    import config.descriptions as _mod
    monkeypatch.setattr(_mod, "_CACHE_ROOT", tmp_path)
    return "https://test.example.org/dhis2"


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestDescriptions:

    def test_save_and_load(self, tmp_url):
        """REQ-DESC-01/02 save + load round-trip."""
        save_description(tmp_url, "uid001", "Confirmed malaria cases")
        data = load_descriptions(tmp_url)
        assert data["uid001"] == "Confirmed malaria cases"

    def test_multiple_uids_independent(self, tmp_url):
        """REQ-DESC-03 multiple UIDs stored independently."""
        save_description(tmp_url, "uid_a", "Description A")
        save_description(tmp_url, "uid_b", "Description B")
        data = load_descriptions(tmp_url)
        assert data["uid_a"] == "Description A"
        assert data["uid_b"] == "Description B"

    def test_empty_description_removes_key(self, tmp_url):
        """REQ-DESC-04 blank/empty description removes the key."""
        save_description(tmp_url, "uid_x", "Some text")
        assert "uid_x" in load_descriptions(tmp_url)
        save_description(tmp_url, "uid_x", "")
        assert "uid_x" not in load_descriptions(tmp_url)

    def test_whitespace_only_removes_key(self, tmp_url):
        """REQ-DESC-04 whitespace-only description also removes the key."""
        save_description(tmp_url, "uid_y", "Text")
        save_description(tmp_url, "uid_y", "   ")
        assert "uid_y" not in load_descriptions(tmp_url)

    def test_bulk_save(self, tmp_url):
        """REQ-DESC-05 save_descriptions_bulk persists multiple at once."""
        save_descriptions_bulk(tmp_url, {
            "de_001": "First indicator",
            "de_002": "Second indicator",
        })
        data = load_descriptions(tmp_url)
        assert data["de_001"] == "First indicator"
        assert data["de_002"] == "Second indicator"

    def test_unknown_url_returns_empty(self, tmp_url):
        """REQ-DESC-06 no file yet → returns empty dict."""
        data = load_descriptions("https://no-such-instance.test/dhis2")
        assert data == {}

    def test_per_instance_isolation(self, tmp_url):
        """REQ-DESC-07 different URLs don't share descriptions."""
        url_a = "https://instance-a.test/dhis2"
        url_b = "https://instance-b.test/dhis2"
        save_description(url_a, "uid_shared", "From A")
        save_description(url_b, "uid_shared", "From B")
        assert load_descriptions(url_a)["uid_shared"] == "From A"
        assert load_descriptions(url_b)["uid_shared"] == "From B"

    def test_file_is_valid_json(self, tmp_url):
        """Stored file must be valid JSON."""
        save_description(tmp_url, "uid_z", "Test")
        path = _desc_path(tmp_url)
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_overwrite_existing(self, tmp_url):
        """Saving same UID again overwrites the value."""
        save_description(tmp_url, "uid_ov", "Old text")
        save_description(tmp_url, "uid_ov", "New text")
        assert load_descriptions(tmp_url)["uid_ov"] == "New text"

    def test_bulk_empty_removes_key(self, tmp_url):
        """REQ-DESC-04 + REQ-DESC-05 bulk save with empty string removes entry."""
        save_description(tmp_url, "uid_r", "Remove me")
        save_descriptions_bulk(tmp_url, {"uid_r": "", "uid_new": "Keep"})
        data = load_descriptions(tmp_url)
        assert "uid_r" not in data
        assert data["uid_new"] == "Keep"
