"""
data_store.py — On-disk layout for downloaded SAMPLE data + metadata, in raw DHIS2 format.

Layout (per DHIS2 instance):

    data/<instance_slug>/
      events/    events_{program}.json        # raw /api/tracker/events response (sample)
      metadata/  organisationUnits.json        # all OU level 1–5, raw objects (incl. geometry)
                 optionSets.json               # options inline, raw
                 programs.json / dataSets.json # only the selected ones, raw
                 dataElements.json / ...       # one file per DHIS2 metadata type key

Everything is stored in DHIS2's native JSON format — no custom wrapper, no transform.

A module-level "active instance" is set on connect so the preview generator
(which has no DHIS2 client/base_url) can read the right folder without threading
base_url through every call — mirrors how ui/preview_server holds global proxy state.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_APP_DIR    = Path(__file__).resolve().parent.parent
_DATA_ROOT  = _APP_DIR / "data"

# Set by set_active_instance() on connect; read by the preview generator.
_active_slug: str | None = None


def url_slug(base_url: str) -> str:
    """Turn a server URL into a safe directory name (same scheme as dhis2/cache.py)."""
    slug = re.sub(r"https?://", "", base_url or "")
    slug = re.sub(r"[/\\:?&=]", "_", slug)
    return slug.strip("_")[:80]


# ── Active-instance state ───────────────────────────────────────────────────

def set_active_instance(base_url: str) -> None:
    """Record which instance's data dir the preview generator should read from."""
    global _active_slug
    _active_slug = url_slug(base_url)


def active_slug() -> str | None:
    return _active_slug


# ── Path helpers ────────────────────────────────────────────────────────────

def instance_dir(base_url: str | None = None) -> Path:
    """Root data dir for an instance. Uses the active instance when base_url is None."""
    slug = url_slug(base_url) if base_url else _active_slug
    if not slug:
        raise ValueError("No active DHIS2 instance set; pass base_url explicitly.")
    return _DATA_ROOT / slug


def events_dir(base_url: str | None = None) -> Path:
    return instance_dir(base_url) / "events"


def metadata_dir(base_url: str | None = None) -> Path:
    return instance_dir(base_url) / "metadata"


def events_path(prog_uid: str, base_url: str | None = None) -> Path:
    return events_dir(base_url) / f"events_{prog_uid}.json"


def metadata_path(type_name: str, base_url: str | None = None) -> Path:
    return metadata_dir(base_url) / f"{type_name}.json"


# ── Raw read/write (native DHIS2 JSON, no wrapper) ──────────────────────────

def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_events(prog_uid: str, base_url: str | None = None):
    """Read the raw events file for a program (active instance by default)."""
    try:
        return read_json(events_path(prog_uid, base_url))
    except ValueError:
        return None


def load_metadata(type_name: str, base_url: str | None = None):
    """Read one raw metadata-type file (e.g. 'organisationUnits')."""
    try:
        return read_json(metadata_path(type_name, base_url))
    except ValueError:
        return None
