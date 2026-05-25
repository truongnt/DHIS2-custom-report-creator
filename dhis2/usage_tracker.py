"""
Track how many times each indicator/data-element UID has been used
in a successfully generated report, per server URL.

Storage: <app_dir>/cache/<url_slug>/usage.json
Schema:
{
  "indicators":         {"UID": count, ...},
  "program_indicators": {"UID": count, ...},
  "data_elements":      {"UID": count, ...}
}
"""
from __future__ import annotations
import json
import re
from pathlib import Path

_APP_DIR   = Path(__file__).resolve().parent.parent
_CACHE_ROOT = _APP_DIR / "cache"

_TYPES = ("indicators", "program_indicators", "data_elements")


def _slug(url: str) -> str:
    slug = re.sub(r"https?://", "", url)
    slug = re.sub(r"[/\\:?&=]", "_", slug)
    return slug.strip("_")[:80]


def _usage_path(base_url: str) -> Path:
    return _CACHE_ROOT / _slug(base_url) / "usage.json"


def _load(base_url: str) -> dict:
    path = _usage_path(base_url)
    if not path.exists():
        return {t: {} for t in _TYPES}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {t: {} for t in _TYPES}


def _save(base_url: str, data: dict) -> None:
    path = _usage_path(base_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def record_usage(base_url: str, pinned: dict) -> None:
    """
    Increment usage count for each UID that was pinned for a report.
    pinned = {"indicators": [uid, ...], "program_indicators": [...], "data_elements": [...]}
    """
    data = _load(base_url)
    for kind in _TYPES:
        for uid in pinned.get(kind, []):
            data.setdefault(kind, {})[uid] = data[kind].get(uid, 0) + 1
    _save(base_url, data)


def get_counts(base_url: str) -> dict:
    """
    Returns {kind: {uid: count}} for all tracked UIDs.
    """
    return _load(base_url)


def get_sorted_uids(base_url: str, kind: str) -> list[tuple[str, int]]:
    """
    Returns [(uid, count), ...] sorted by count descending.
    kind: 'indicators' | 'program_indicators' | 'data_elements'
    """
    data = _load(base_url)
    counts = data.get(kind, {})
    return sorted(counts.items(), key=lambda x: x[1], reverse=True)
