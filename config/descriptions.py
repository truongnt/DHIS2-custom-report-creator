"""Local storage for user-written DE/PA/PI descriptions, keyed by DHIS2 instance URL."""
from __future__ import annotations
import json
import re
from pathlib import Path

_CACHE_ROOT = Path(__file__).parent.parent / "cache"


def _desc_path(base_url: str) -> Path:
    slug = re.sub(r"[^\w]", "_", base_url.rstrip("/"))
    return _CACHE_ROOT / slug / "descriptions.json"


def load_descriptions(base_url: str) -> dict[str, str]:
    """Return {uid: description_text} for this DHIS2 instance."""
    path = _desc_path(base_url)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_description(base_url: str, uid: str, description: str) -> None:
    """Persist description for a single uid."""
    path = _desc_path(base_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_descriptions(base_url)
    if description.strip():
        data[uid] = description.strip()
    else:
        data.pop(uid, None)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def save_descriptions_bulk(base_url: str, updates: dict[str, str]) -> None:
    """Persist multiple uid→description pairs at once."""
    path = _desc_path(base_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_descriptions(base_url)
    for uid, desc in updates.items():
        if desc.strip():
            data[uid] = desc.strip()
        else:
            data.pop(uid, None)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
