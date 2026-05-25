"""
Lưu và tải DHIS2 connection profiles + Anthropic API key.

  Non-sensitive (URL, username, profile list):
      Stored in  config/profiles.json  (plain JSON, next to this file)

  Sensitive (password, API key):
      Stored in  Windows Credential Manager  via the `keyring` library
      (DPAPI-encrypted, only accessible by the same Windows user)

Keyring service names:
  DHIS2 password : "DHIS2AutoReport:<url_slug>"  →  username = <username>
  Anthropic key  : "DHIS2AutoReport:anthropic"   →  username = "api_key"
"""
from __future__ import annotations
import json
import re
from pathlib import Path

try:
    import keyring
    _KEYRING_OK = True
except ImportError:
    _KEYRING_OK = False

_CONFIG_FILE = Path(__file__).parent / "profiles.json"
_APP = "DHIS2AutoReport"


# ── Internal helpers ───────────────────────────────────────────────────────────

def _url_slug(url: str) -> str:
    slug = re.sub(r"https?://", "", url.rstrip("/"))
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", slug)[:60]


def _load_config() -> dict:
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"profiles": []}


def _save_config(data: dict) -> None:
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── DHIS2 Profiles ────────────────────────────────────────────────────────────

def save_profile(url: str, username: str, password: str) -> None:
    """
    Save a DHIS2 connection profile.
    URL + username go to profiles.json; password goes to Windows Credential Manager.
    """
    url = url.strip().rstrip("/")
    data = _load_config()

    # Upsert the profile entry (URL + username only)
    profiles: list[dict] = data.get("profiles", [])
    existing = next((p for p in profiles if p["url"] == url and
                     p["username"] == username), None)
    if not existing:
        profiles.append({"url": url, "username": username})
        data["profiles"] = profiles
        _save_config(data)

    # Store password in keyring
    if _KEYRING_OK and password:
        keyring.set_password(f"{_APP}:{_url_slug(url)}", username, password)


def load_profiles() -> list[dict]:
    """Return list of saved profiles: [{"url": ..., "username": ...}, ...]."""
    return _load_config().get("profiles", [])


def load_password(url: str, username: str) -> str:
    """Retrieve stored password from Windows Credential Manager, or ''."""
    if not _KEYRING_OK:
        return ""
    url = url.strip().rstrip("/")
    return keyring.get_password(f"{_APP}:{_url_slug(url)}", username) or ""


def delete_profile(url: str, username: str) -> None:
    """Remove a saved profile and its stored password."""
    url = url.strip().rstrip("/")
    data = _load_config()
    data["profiles"] = [
        p for p in data.get("profiles", [])
        if not (p["url"] == url and p["username"] == username)
    ]
    _save_config(data)

    if _KEYRING_OK:
        try:
            keyring.delete_password(f"{_APP}:{_url_slug(url)}", username)
        except Exception:
            pass


# ── Anthropic API Key ─────────────────────────────────────────────────────────

def save_api_key(api_key: str) -> None:
    """Store Anthropic API key in Windows Credential Manager."""
    if _KEYRING_OK and api_key:
        keyring.set_password(f"{_APP}:anthropic", "api_key", api_key)


def load_api_key() -> str:
    """Retrieve saved Anthropic API key, or ''."""
    if not _KEYRING_OK:
        return ""
    return keyring.get_password(f"{_APP}:anthropic", "api_key") or ""


def delete_api_key() -> None:
    if _KEYRING_OK:
        try:
            keyring.delete_password(f"{_APP}:anthropic", "api_key")
        except Exception:
            pass


# ── Convenience: label for display ───────────────────────────────────────────

def profile_label(profile: dict) -> str:
    url = profile.get("url", "")
    user = profile.get("username", "")
    slug = re.sub(r"https?://", "", url)[:40]
    return f"{user}  @  {slug}"
