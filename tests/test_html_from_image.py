"""Tests for llm.html_from_image — AI 'generate HTML from image' (Custom HTML widget).

REQ-HTMLAI-01  media_type_for maps extensions; defaults to png
REQ-HTMLAI-02  fences (```html …```) are stripped from model output
REQ-HTMLAI-03  generate_html_from_image sends an image block (base64) + instructions
               and returns cleaned HTML
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import llm.html_from_image as hfi


def test_media_type_for():
    """REQ-HTMLAI-01."""
    assert hfi.media_type_for("a.png") == "image/png"
    assert hfi.media_type_for("a.JPG") == "image/jpeg"
    assert hfi.media_type_for("a.jpeg") == "image/jpeg"
    assert hfi.media_type_for("a.webp") == "image/webp"
    assert hfi.media_type_for("a.bmp") == "image/png"     # default


def test_strip_fences():
    """REQ-HTMLAI-02."""
    assert hfi._strip_fences("```html\n<div>x</div>\n```") == "<div>x</div>"
    assert hfi._strip_fences("```\n<p>y</p>\n```") == "<p>y</p>"
    assert hfi._strip_fences("<b>z</b>") == "<b>z</b>"


def test_generate_sends_image_and_returns_html(monkeypatch):
    """REQ-HTMLAI-03: builds an image+text message and returns fenced-stripped HTML."""
    captured = {}

    class _Block:
        type = "text"
        text = "```html\n<div class='r'>Report</div>\n```"

    class _Msg:
        content = [_Block()]

    class _Messages:
        def create(self, **kw):
            captured.update(kw)
            return _Msg()

    class _FakeClient:
        def __init__(self, api_key=None):
            captured["api_key"] = api_key
            self.messages = _Messages()

    monkeypatch.setattr(hfi.anthropic, "Anthropic", _FakeClient)

    out = hfi.generate_html_from_image(b"PNGDATA", "image/png", "key-123",
                                       "claude-sonnet-4-6", columns=["Cases", "Sex"])
    assert out == "<div class='r'>Report</div>"
    assert captured["api_key"] == "key-123"
    assert captured["model"] == "claude-sonnet-4-6"
    content = captured["messages"][0]["content"]
    img = next(b for b in content if b["type"] == "image")
    assert img["source"]["media_type"] == "image/png"
    assert img["source"]["data"] == base64.standard_b64encode(b"PNGDATA").decode()
    txt = next(b for b in content if b["type"] == "text")["text"]
    assert "self-contained HTML" in txt and "Cases" in txt   # instructions + columns


def test_to_snippet_extracts_body_and_style():
    """REQ-HTMLAI-04: a full HTML document is reduced to a (style + body) snippet so it
    nests cleanly inside the widget iframe; a plain snippet passes through."""
    full = ("<!DOCTYPE html><html><head><style>.t{color:red}</style></head>"
            "<body><div>Report</div></body></html>")
    out = hfi._to_snippet(full)
    assert "<style>.t{color:red}</style>" in out
    assert "<div>Report</div>" in out
    assert "<html" not in out.lower() and "<!doctype" not in out.lower()
    # plain snippet unchanged
    assert hfi._to_snippet("<div>x</div>") == "<div>x</div>"
