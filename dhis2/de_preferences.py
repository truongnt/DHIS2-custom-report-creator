"""Persist user DE swap history and verify results to improve future LLM DE selection."""
from __future__ import annotations
import json, re
from pathlib import Path

_APP_DIR    = Path(__file__).resolve().parent.parent
_CACHE_ROOT = _APP_DIR / "cache"


def _slug(base_url: str) -> str:
    slug = re.sub(r"https?://", "", base_url)
    slug = re.sub(r"[/\\:?&=]", "_", slug)
    return slug.strip("_")[:80]


def _dir(base_url: str) -> Path:
    d = _CACHE_ROOT / _slug(base_url)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(base_url: str, filename: str) -> Path:
    return _dir(base_url) / filename


# ── Swap history ──────────────────────────────────────────────────────────────

def load_swaps(base_url: str) -> dict[str, str]:
    """Returns {original_id: preferred_id}."""
    p = _path(base_url, "de_swaps.json")
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_swaps(base_url: str, new_swaps: dict[str, str]) -> None:
    """Merge new swaps into existing history (original_id → preferred_id)."""
    existing = load_swaps(base_url)
    existing.update(new_swaps)
    p = _path(base_url, "de_swaps.json")
    p.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Verify log ────────────────────────────────────────────────────────────────
# Format: {uid: {displayName, valid, invalid}}
# valid/invalid = cumulative count of times this UID was seen in verified reports.

def load_verify_log(base_url: str) -> dict[str, dict]:
    """Returns {uid: {displayName, valid, invalid}}."""
    p = _path(base_url, "de_verify_log.json")
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_verify_results(
    base_url: str,
    valid_uids: set[str],
    invalid_uids: set[str],
    id_to_name: dict[str, str],
) -> None:
    """Increment valid/invalid counters for each UID found in a verified report."""
    log = load_verify_log(base_url)
    for uid in valid_uids:
        e = log.setdefault(uid, {"displayName": "", "valid": 0, "invalid": 0})
        e["valid"] += 1
        if id_to_name.get(uid):
            e["displayName"] = id_to_name[uid]
    for uid in invalid_uids:
        e = log.setdefault(uid, {"displayName": "UNKNOWN", "valid": 0, "invalid": 0})
        e["invalid"] += 1
    p = _path(base_url, "de_verify_log.json")
    p.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def get_known_invalid_uids(base_url: str, min_invalid: int = 1) -> set[str]:
    """Return UIDs that have been invalid at least min_invalid times and never valid."""
    log = load_verify_log(base_url)
    return {
        uid for uid, e in log.items()
        if e.get("invalid", 0) >= min_invalid and e.get("valid", 0) == 0
    }


# ── Confirmed DEs ─────────────────────────────────────────────────────────────
# Tracks UIDs the user explicitly accepted in DE Review dialog.
# Used to bias future LLM DE selection toward known-good choices.

def load_confirmed_des(base_url: str) -> dict[str, dict]:
    """Returns {uid: {displayName, count}} of user-confirmed DEs."""
    p = _path(base_url, "de_confirmed.json")
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_confirmed_des(base_url: str, confirmed_list: list[dict]) -> None:
    """Increment confirmation count for each DE the user explicitly confirmed."""
    existing = load_confirmed_des(base_url)
    for de in confirmed_list:
        uid = de.get("id")
        if not uid:
            continue
        entry = existing.get(uid, {"displayName": "", "count": 0})
        entry["displayName"] = de.get("displayName") or entry["displayName"]
        entry["count"] = entry.get("count", 0) + 1
        existing[uid] = entry
    p = _path(base_url, "de_confirmed.json")
    p.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def get_top_confirmed_uids(base_url: str, top_n: int = 20) -> list[tuple[str, str]]:
    """Returns top N (uid, displayName) pairs sorted by confirmation count."""
    confirmed = load_confirmed_des(base_url)
    sorted_items = sorted(confirmed.items(), key=lambda kv: kv[1].get("count", 0), reverse=True)
    return [(uid, e.get("displayName", "")) for uid, e in sorted_items[:top_n]]


# ── Form state ────────────────────────────────────────────────────────────────

def save_form_state(base_url: str, state: dict) -> None:
    """Persist QuickFormPanel field values for a given server."""
    p = _path(base_url, "form_state.json")
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_form_state(base_url: str) -> dict:
    """Load previously saved QuickFormPanel field values."""
    p = _path(base_url, "form_state.json")
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
