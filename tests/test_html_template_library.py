"""
Tests for config.html_template_library — the 'image → HTML' reuse store.

REQ-HTMPL-01  save_template persists image + html and is retrievable by hash
REQ-HTMPL-02  dedup: re-saving the same image upserts (one entry), updates html/model
REQ-HTMPL-03  find_by_hash returns None for an unknown image
REQ-HTMPL-04  list/index newest-first; delete removes entry + image file
"""
import importlib
from pathlib import Path

import pytest

import config.html_template_library as htl


@pytest.fixture
def lib(tmp_path, monkeypatch):
    """Point the library at a temp dir so tests don't touch real config/."""
    d = tmp_path / "html_templates"
    monkeypatch.setattr(htl, "_DIR", d)
    monkeypatch.setattr(htl, "_INDEX", d / "index.json")
    return htl


IMG_A = b"\x89PNG\r\n\x1a\n-fake-image-a"
IMG_B = b"\x89PNG\r\n\x1a\n-fake-image-b"


def test_save_and_retrieve(lib):  # REQ-HTMPL-01
    entry = lib.save_template(IMG_A, "<b>hi</b>", model="claude-opus-4-8",
                              created_at="2026-06-30 10:00")
    assert entry["hash"] == lib.image_hash(IMG_A)
    assert lib.image_path(entry).exists()
    found = lib.find_by_hash(lib.image_hash(IMG_A))
    assert found and found["html"] == "<b>hi</b>"
    assert found["model"] == "claude-opus-4-8"


def test_dedup_upsert(lib):  # REQ-HTMPL-02
    lib.save_template(IMG_A, "<p>v1</p>", model="haiku", created_at="2026-06-30 10:00")
    lib.save_template(IMG_A, "<p>v2</p>", model="opus", created_at="2026-06-30 11:00")
    items = lib.load_index()
    assert len(items) == 1                      # one entry, not two
    assert items[0]["html"] == "<p>v2</p>"      # html updated
    assert items[0]["model"] == "opus"          # model updated


def test_find_unknown(lib):  # REQ-HTMPL-03
    assert lib.find_by_hash("deadbeef") is None


def test_list_order_and_delete(lib):  # REQ-HTMPL-04
    e1 = lib.save_template(IMG_A, "a", created_at="2026-06-30 10:00")
    e2 = lib.save_template(IMG_B, "b", created_at="2026-06-30 11:00")
    items = lib.load_index()
    assert [i["id"] for i in items] == [e2["id"], e1["id"]]   # newest first
    img_b = lib.image_path(e2)
    assert img_b.exists()
    lib.delete_template(e2["id"])
    assert lib.find_by_hash(e2["hash"]) is None
    assert not img_b.exists()                                 # image file removed
    assert len(lib.load_index()) == 1
