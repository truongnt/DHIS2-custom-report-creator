"""
html_from_image.py — Generate a self-contained HTML widget from an uploaded image
using Claude's vision capability.

Used by the Custom HTML chart editor: the user uploads a screenshot/mock-up of a
table or report, and Claude returns HTML/CSS/JS that reproduces its layout. Output is
inserted directly into the HTML editor.

The image is sent to the Anthropic API (external). Callers should confirm with the user
before sending potentially sensitive screenshots.
"""
from __future__ import annotations

import base64
import re

import anthropic

_MEDIA_BY_EXT = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".gif": "image/gif",
}


def media_type_for(path: str) -> str:
    """Best-effort media type from a file extension (defaults to image/png)."""
    path = (path or "").lower()
    for ext, mt in _MEDIA_BY_EXT.items():
        if path.endswith(ext):
            return mt
    return "image/png"


def _strip_fences(text: str) -> str:
    """Strip a leading ```html / ``` fence and trailing ``` if the model wrapped output."""
    s = (text or "").strip()
    if s.startswith("```"):
        first_nl = s.find("\n")
        if first_nl != -1:
            s = s[first_nl + 1:]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    return s.strip()


def _to_snippet(html: str) -> str:
    """If the model returned a full document, reduce it to a (style + body) snippet so it
    nests cleanly inside the widget iframe."""
    if html.lstrip()[:20].lower().startswith("<!doctype") or re.search(r"<html[\s>]", html, re.I):
        styles = "".join(re.findall(r"<style\b[^>]*>.*?</style>", html, re.S | re.I))
        m = re.search(r"<body\b[^>]*>(.*?)</body>", html, re.S | re.I)
        body = m.group(1) if m else html
        return (styles + "\n" + body).strip()
    return html


def build_prompt(columns: list[str] | None = None) -> str:
    """The instruction text sent alongside the image (static-layout reproduction)."""
    cols = ""
    if columns:
        cols = ("\nIf the layout clearly maps to these data columns you MAY reference them via "
                "{{Column}} placeholders: " + ", ".join(columns) + ". Otherwise keep numbers static.")
    return (
        "You are an expert front-end developer. Reproduce the attached image as faithfully as "
        "possible as a SINGLE self-contained HTML snippet: one top-level <div> with an inline "
        "<style>, and (only if needed) a <script> using vanilla JavaScript. Do NOT use external "
        "CDNs, frameworks, fonts, or network requests.\n"
        "Reproduce precisely:\n"
        "- Layout & structure (use a real <table> with border-collapse for tabular content; "
        "use colspan/rowspan to match merged cells and grouped rows).\n"
        "- Colours: sample the actual header band, section-row shading, borders and text colours "
        "from the image (use hex values).\n"
        "- Typography: font sizes, weights, italic, and small sub-text / formula captions.\n"
        "- Alignment, indentation of sub-rows, padding, and thin cell borders.\n"
        "- The EXACT numbers, labels and symbols shown (e.g. %, NA, 1*). Static values are fine.\n"
        "Make it fill its container width (width:100%). Be thorough — reproduce every row and "
        "column, not a simplified version. Output ONLY the HTML — no markdown fences, no commentary."
        + cols
    )


def generate_html_from_image(image_bytes: bytes, media_type: str, api_key: str,
                             model: str, columns: list[str] | None = None,
                             max_tokens: int = 8192) -> str:
    """Send the image + instructions to Claude (vision) and return cleaned HTML.

    Raises on API / SDK errors (caller handles).
    """
    client = anthropic.Anthropic(api_key=api_key)
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image",
                 "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": build_prompt(columns)},
            ],
        }],
    )
    text = "".join(getattr(b, "text", "") for b in msg.content
                   if getattr(b, "type", "") == "text")
    return _to_snippet(_strip_fences(text))
