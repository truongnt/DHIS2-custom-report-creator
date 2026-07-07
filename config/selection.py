"""Local storage for the user's curated "in-use" metadata selection, per DHIS2 instance.

The Metadata Editor lets the user move DE / PA / I / PI items into an "in use" list;
the Chart Editor then offers metrics & dimensions ONLY from that list. Stored next to
descriptions under cache/<url_slug>/selection.json as {"in_use": [uid, …]}.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

_CACHE_ROOT = Path(__file__).parent.parent / "cache"


def _sel_path(base_url: str) -> Path:
    slug = re.sub(r"[^\w]", "_", base_url.rstrip("/"))
    return _CACHE_ROOT / slug / "selection.json"


def load_selection(base_url: str) -> set[str]:
    """Return the set of in-use metadata UIDs for this DHIS2 instance (empty if none)."""
    path = _sel_path(base_url)
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.get("in_use", []) if isinstance(data, dict) else data)
    except Exception:
        return set()


def save_selection(base_url: str, uids) -> None:
    """Persist the in-use UID set (order-stable, de-duplicated)."""
    path = _sel_path(base_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    seen: list[str] = []
    for u in uids:
        if u and u not in seen:
            seen.append(u)
    path.write_text(json.dumps({"in_use": seen}, indent=2, ensure_ascii=False),
                    encoding="utf-8")
