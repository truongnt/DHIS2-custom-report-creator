"""
Persist DHIS2 metadata to disk so it survives app restarts.
Cache is keyed by the server URL. Each cache entry stores:
  - metadata dict (indicators, program_indicators, data_elements, datasets, programs, org_unit_levels)
  - fetched_at ISO timestamp

Cache location: <app_dir>/cache/<url_slug>/metadata.json
"""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent.parent
_CACHE_ROOT = _APP_DIR / "cache"


def _url_slug(base_url: str) -> str:
    """Turn a URL into a safe directory name."""
    slug = re.sub(r"https?://", "", base_url)
    slug = re.sub(r"[/\\:?&=]", "_", slug)
    return slug.strip("_")[:80]


def _cache_path(base_url: str) -> Path:
    return _CACHE_ROOT / _url_slug(base_url) / "metadata.json"


def save(base_url: str, metadata: dict) -> None:
    path = _cache_path(base_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "base_url":   base_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "metadata":   metadata,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load(base_url: str) -> tuple[dict | None, str | None]:
    """
    Returns (metadata, fetched_at_str) or (None, None) if no cache exists.
    fetched_at_str is a human-readable string like '2026-05-24 10:00 UTC'.
    """
    path = _cache_path(base_url)
    if not path.exists():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        ts = payload.get("fetched_at", "")
        # pretty-print the timestamp
        try:
            dt = datetime.fromisoformat(ts)
            ts_display = dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            ts_display = ts
        return payload.get("metadata", {}), ts_display
    except Exception:
        return None, None


def clear(base_url: str) -> None:
    path = _cache_path(base_url)
    if path.exists():
        path.unlink()


def cache_exists(base_url: str) -> bool:
    return _cache_path(base_url).exists()
