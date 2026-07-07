"""
html_template_library.py — Persistent store for AI 'image → HTML' generations.

Each upload that is generated is saved (the source image + the generated HTML) so the
user can:
  • reuse a previous result without calling the API again,
  • be warned when re-uploading the same image (dedup by image content hash),
  • browse/pick past templates from a gallery.

Layout (global, not per-instance):
  config/html_templates/
    index.json            # [{id, hash, image, model, name, created_at, html}, ...]
    <hash>.png            # the (downscaled) source image
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

_DIR = Path(__file__).parent / "html_templates"
_INDEX = _DIR / "index.json"


def _ensure_dir() -> None:
    _DIR.mkdir(parents=True, exist_ok=True)


def image_hash(image_bytes: bytes) -> str:
    """Stable content hash for dedup (first 16 hex of sha1)."""
    return hashlib.sha1(image_bytes).hexdigest()[:16]


def load_index() -> list[dict]:
    if not _INDEX.exists():
        return []
    try:
        data = json.loads(_INDEX.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_index(items: list[dict]) -> None:
    _ensure_dir()
    _INDEX.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def find_by_hash(h: str) -> dict | None:
    return next((e for e in load_index() if e.get("hash") == h), None)


def image_path(entry: dict) -> Path:
    """Absolute path to an entry's stored image."""
    return _DIR / (entry.get("image") or "")


def save_template(image_bytes: bytes, html: str, model: str = "",
                  name: str = "", created_at: str = "") -> dict:
    """Upsert a template by image hash. Writes the image file + index entry.

    Re-generating the same image updates its html/model/created_at but keeps one entry.
    """
    _ensure_dir()
    h = image_hash(image_bytes)
    img_name = f"{h}.png"
    (_DIR / img_name).write_bytes(image_bytes)

    items = load_index()
    entry = next((e for e in items if e.get("hash") == h), None)
    created = created_at or time.strftime("%Y-%m-%d %H:%M")
    if entry is None:
        entry = {"id": h, "hash": h, "image": img_name,
                 "name": name or f"Template {created}",
                 "model": model, "created_at": created, "html": html}
        items.insert(0, entry)            # newest first
    else:
        entry["html"] = html
        entry["model"] = model or entry.get("model", "")
        entry["created_at"] = created
        if name:
            entry["name"] = name
        entry["image"] = img_name
    _write_index(items)
    return entry


def delete_template(template_id: str) -> None:
    items = load_index()
    keep, removed = [], []
    for e in items:
        (removed if e.get("id") == template_id else keep).append(e)
    for e in removed:
        try:
            (_DIR / (e.get("image") or "")).unlink(missing_ok=True)
        except Exception:
            pass
    _write_index(keep)
