"""
Integration tests for the Login / Connection screen — see docs/LOGIN_REQUIREMENTS.md.

Drives the real AppWindow via pytest-qt (qtbot), with credentials/network mocked.
Each test's docstring carries the REQ-ID(s) it verifies → picked up by the
traceability report (test-evidence/<ts>/traceability.md).

Run: pip install -r requirements-dev.txt ; pytest tests/integration -m integration
"""
from unittest.mock import patch, MagicMock

import pytest
from PySide6.QtWidgets import QLineEdit, QMessageBox

from config.credentials import profile_label

pytestmark = pytest.mark.integration

PROFILE = {"url": "https://hmis.gov.la/hmis", "username": "admin"}


# ─── Startup / access control ────────────────────────────────────────────────

def test_nav_locked_before_connect(make_window):
    """REQ-LOGIN-STATE-04: Chart Editor + Dashboard nav locked until connected."""
    win = make_window()
    assert win._nav_btns["config"].isEnabled()
    assert not win._nav_btns["chart_editor"].isEnabled()
    assert not win._nav_btns["dashboard"].isEnabled()


# ─── Saved profiles ──────────────────────────────────────────────────────────

def test_profile_dropdown_lists_saved(make_window):
    """REQ-LOGIN-PROFILE-01: dropdown lists saved profiles as '{user} @ {url}'."""
    win = make_window(profiles=[PROFILE])
    labels = [win.profile_menu.itemText(i) for i in range(win.profile_menu.count())]
    assert labels[0] == "— Saved profiles —"
    assert profile_label(PROFILE) in labels


def test_select_profile_fills_and_autoconnects(make_window, qtbot):
    """REQ-LOGIN-PROFILE-02: selecting a profile fills fields and auto-connects."""
    win = make_window()
    with patch("config.credentials.load_profiles", return_value=[PROFILE]), \
         patch("config.credentials.load_password", return_value="secret"), \
         patch.object(type(win), "_on_connect") as mock_conn:
        win._on_profile_selected(profile_label(PROFILE))
        assert win.url_entry.text() == PROFILE["url"]
        assert win.user_entry.text() == PROFILE["username"]
        assert win.pass_entry.text() == "secret"
        qtbot.wait(160)            # 100ms scheduled auto-connect
        assert mock_conn.called


def test_save_profile_requires_url_user(make_window):
    """REQ-LOGIN-PROFILE-03: Save profile needs URL+username, then calls save_profile."""
    win = make_window()
    with patch("config.credentials.save_profile") as mock_save, \
         patch("config.credentials.load_profiles", return_value=[]):
        win.url_entry.setText(""); win.user_entry.setText(""); win.pass_entry.setText("")
        win._on_save_profile()
        assert not mock_save.called          # nothing entered → no save
        win.url_entry.setText(PROFILE["url"]); win.user_entry.setText("admin")
        win.pass_entry.setText("pw")
        win._on_save_profile()
        mock_save.assert_called_once()


def test_delete_profile_confirms(make_window):
    """REQ-LOGIN-PROFILE-04: deleting a profile shows confirm and calls delete_profile."""
    win = make_window(profiles=[PROFILE])
    win.profile_menu.setCurrentText(profile_label(PROFILE))
    with patch.object(QMessageBox, "question",
                      return_value=QMessageBox.StandardButton.Yes), \
         patch("config.credentials.load_profiles", return_value=[PROFILE]), \
         patch("config.credentials.delete_profile") as mock_del:
        win._on_delete_profile()
        mock_del.assert_called_once_with(PROFILE["url"], PROFILE["username"])


# ─── Auto-connect & API key restore ──────────────────────────────────────────

def test_autoconnect_first_profile_on_startup(qtbot):
    """REQ-LOGIN-AUTO-02: first saved profile auto-connects when a password exists."""
    with patch("config.credentials.load_profiles", return_value=[PROFILE]), \
         patch("config.credentials.load_api_key", return_value=""), \
         patch("config.credentials.load_password", return_value="secret"), \
         patch("ui.app_window.AppWindow._on_connect") as mock_conn:
        from ui.app_window import AppWindow
        win = AppWindow()
        qtbot.addWidget(win)
        qtbot.wait(260)                       # 200ms scheduled auto-connect
        assert mock_conn.called
        win.close()


def test_api_key_restored(qtbot):
    """REQ-LOGIN-AUTO-03: saved Anthropic API key is restored into the field."""
    import os
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}), \
         patch("config.credentials.load_profiles", return_value=[]), \
         patch("config.credentials.load_password", return_value=""), \
         patch("config.credentials.load_api_key", return_value="sk-ant-test"):
        from ui.app_window import AppWindow
        win = AppWindow()
        qtbot.addWidget(win)
        assert win.apikey_entry.text() == "sk-ant-test"
        win.close()


# ─── Connect flow ────────────────────────────────────────────────────────────

def test_connect_rejects_empty_fields(make_window):
    """REQ-LOGIN-CONN-01: missing URL/user/pass → no connect thread started."""
    win = make_window()
    with patch("ui.app_window.threading.Thread") as mock_thread:
        win.url_entry.setText(""); win.user_entry.setText(""); win.pass_entry.setText("")
        win._on_connect()
        assert not mock_thread.called


def test_connect_starts_worker_and_sets_button(make_window):
    """REQ-LOGIN-CONN-02: valid input → 'Connecting…' button + background worker thread."""
    win = make_window()
    with patch("ui.app_window.threading.Thread") as mock_thread:
        win.url_entry.setText(PROFILE["url"])
        win.user_entry.setText("admin"); win.pass_entry.setText("pw")
        win._on_connect()
        assert mock_thread.called
        assert not win.connect_btn.isEnabled()
        assert "Connecting" in win.connect_btn.text()


def test_connect_done_unlocks_ui(make_window):
    """REQ-LOGIN-CONN-05: successful connect enables nav, shows Change, opens Chart Editor."""
    win = make_window()
    win._on_connect_done("Test User", 0, None, False)
    assert win._nav_btns["chart_editor"].isEnabled()
    assert win._nav_btns["dashboard"].isEnabled()
    assert not win.change_conn_btn.isHidden()      # shown (window itself isn't show()n)
    assert win._content.currentIndex() == 1        # chart_editor panel


def test_connect_fail_resets_button(make_window):
    """REQ-LOGIN-CONN-06: failed connect re-enables Connect and shows error status."""
    win = make_window()
    win.connect_btn.setEnabled(False)
    win._on_connect_fail("Connection refused")
    assert win.connect_btn.isEnabled()
    assert "failed" in win.conn_status.text().lower()


# ─── Post-connect state ──────────────────────────────────────────────────────

def test_filter_btn_enabled_after_connect(make_window):
    """REQ-LOGIN-STATE-03: the Metadata Library's Filters && Load button enables after connect
    (the scope filter moved off the login screen into the Metadata Library)."""
    win = make_window()
    assert not win._metadata_editor._filter_btn.isEnabled()
    win._on_connect_done("U", 0, None, False)
    assert win._metadata_editor._filter_btn.isEnabled()


def test_change_connection_reopens_login(make_window):
    """REQ-LOGIN-STATE-02: Change connection re-shows the login frame and resets Connect."""
    win = make_window()
    win._on_connect_done("U", 0, None, False)
    win._on_change_connection()
    assert not win._login_frame.isHidden()
    assert win.connect_btn.isEnabled()
    assert win.connect_btn.text() == "Connect"


# ─── API key ─────────────────────────────────────────────────────────────────

def test_apikey_masked(make_window):
    """REQ-LOGIN-APIKEY-01: API key field uses password echo mode."""
    win = make_window()
    assert win.apikey_entry.echoMode() == QLineEdit.EchoMode.Password


def test_save_api_key(make_window):
    """REQ-LOGIN-APIKEY-02: Save API key persists via save_api_key; empty → no save."""
    win = make_window()
    with patch("config.credentials.save_api_key") as mock_save:
        win.apikey_entry.setText("")
        win._on_save_api_key()
        assert not mock_save.called
        win.apikey_entry.setText("sk-ant-xyz")
        win._on_save_api_key()
        mock_save.assert_called_once_with("sk-ant-xyz")


# ─── AI model ────────────────────────────────────────────────────────────────

def test_model_mapping(make_window):
    """REQ-LOGIN-MODEL-01: each dropdown label maps to its model id (Opus → 4.8)."""
    win = make_window()
    ids = set(win._MODEL_OPTIONS.values())
    assert "claude-opus-4-8" in ids
    for label, mid in win._MODEL_OPTIONS.items():
        win.model_combo.setCurrentText(label)
        assert win._get_model() == mid


def test_model_default(make_window):
    """REQ-LOGIN-MODEL-02: unknown selection falls back to Haiku default."""
    win = make_window()
    win.model_combo.clear()                      # currentText() == "" → default
    assert win._get_model() == "claude-haiku-4-5-20251001"


# ─── Password reveal (new feature) ───────────────────────────────────────────

def test_password_reveal_toggle(make_window):
    """REQ-LOGIN-UX-01: 👁 toggles the password field between hidden and shown."""
    win = make_window()
    assert win.pass_entry.echoMode() == QLineEdit.EchoMode.Password
    win.pass_reveal_btn.setChecked(True)
    assert win.pass_entry.echoMode() == QLineEdit.EchoMode.Normal
    win.pass_reveal_btn.setChecked(False)
    assert win.pass_entry.echoMode() == QLineEdit.EchoMode.Password


def test_apikey_reveal_toggle(make_window):
    """REQ-LOGIN-UX-01: 👁 toggles the API key field too."""
    win = make_window()
    win.apikey_reveal_btn.setChecked(True)
    assert win.apikey_entry.echoMode() == QLineEdit.EchoMode.Normal


# ─── URL validation (new feature) ────────────────────────────────────────────

def test_url_validators(make_window):
    """REQ-LOGIN-VAL-01: URL normalisation + validation rules."""
    win = make_window()
    assert win._normalize_url("hmis.gov.la/hmis/") == "https://hmis.gov.la/hmis"
    assert win._normalize_url("  https://x.org  ") == "https://x.org"
    assert win._is_valid_url("https://hmis.gov.la")
    assert not win._is_valid_url("ftp://x")
    assert not win._is_valid_url("hmis.gov.la")   # no scheme (pre-normalise)


def test_connect_rejects_invalid_url(make_window):
    """REQ-LOGIN-VAL-01: invalid server URL → no connect thread, error shown."""
    win = make_window()
    with patch("ui.app_window.threading.Thread") as mock_thread:
        win.url_entry.setText("http://")          # normalises to 'http:' → no host
        win.user_entry.setText("admin"); win.pass_entry.setText("pw")
        win._on_connect()
        assert not mock_thread.called
        # invalid-URL message goes to the status bar (status_label), not conn_status
        assert "url" in win.status_label.text().lower()


# ─── Credential storage (security) ───────────────────────────────────────────

def test_save_profile_splits_storage(tmp_path, monkeypatch):
    """REQ-LOGIN-SEC-01/02: URL+username → profiles.json; password → keyring only."""
    import config.credentials as cred
    monkeypatch.setattr(cred, "_CONFIG_FILE", tmp_path / "profiles.json")
    sets = {}
    monkeypatch.setattr(cred, "_KEYRING_OK", True)
    monkeypatch.setattr(cred, "keyring",
                        MagicMock(set_password=lambda s, u, p: sets.update({(s, u): p})),
                        raising=False)
    cred.save_profile("https://hmis.gov.la/hmis", "admin", "s3cret")

    disk = (tmp_path / "profiles.json").read_text(encoding="utf-8")
    assert "admin" in disk and "hmis.gov.la" in disk
    assert "s3cret" not in disk                   # password never on disk
    assert "s3cret" in sets.values()              # password went to keyring


def test_keyring_unavailable_returns_empty(monkeypatch):
    """REQ-LOGIN-SEC-04: with keyring unavailable, password/key load returns ''."""
    import config.credentials as cred
    monkeypatch.setattr(cred, "_KEYRING_OK", False)
    assert cred.load_password("https://x", "admin") == ""
    assert cred.load_api_key() == ""


# ─── Second batch: deeper flow / storage REQs ────────────────────────────────

def test_startup_loads_profiles_and_key(qtbot):
    """REQ-LOGIN-AUTO-01: startup populates the profile dropdown and restores the key."""
    import os
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}), \
         patch("config.credentials.load_profiles", return_value=[PROFILE]), \
         patch("config.credentials.load_password", return_value=""), \
         patch("config.credentials.load_api_key", return_value="sk-k"):
        from ui.app_window import AppWindow
        win = AppWindow()
        qtbot.addWidget(win)
        labels = [win.profile_menu.itemText(i) for i in range(win.profile_menu.count())]
        assert profile_label(PROFILE) in labels
        assert win.apikey_entry.text() == "sk-k"
        win.close()


def test_fields_hidden_after_connect(make_window):
    """REQ-LOGIN-STATE-01: after connect the login frame is hidden (not editable)."""
    win = make_window()
    assert not win._login_frame.isHidden()
    win._on_connect_done("U", 0, None, False)
    assert win._login_frame.isHidden()


def test_profile_upsert_no_duplicate(tmp_path, monkeypatch):
    """REQ-LOGIN-PROFILE-05: saving the same (url,user) twice does not duplicate."""
    import config.credentials as cred
    monkeypatch.setattr(cred, "_CONFIG_FILE", tmp_path / "profiles.json")
    monkeypatch.setattr(cred, "_KEYRING_OK", True)
    monkeypatch.setattr(cred, "keyring", MagicMock(), raising=False)
    cred.save_profile("https://hmis.gov.la/hmis", "admin", "p1")
    cred.save_profile("https://hmis.gov.la/hmis", "admin", "p2")   # same identity
    profiles = cred.load_profiles()
    assert len([p for p in profiles
                if p["url"] == "https://hmis.gov.la/hmis" and p["username"] == "admin"]) == 1


def test_test_connection_calls_me_endpoint():
    """REQ-LOGIN-CONN-03: DHIS2Client.test_connection authenticates via /api/me."""
    from dhis2.client import DHIS2Client
    c = DHIS2Client("https://hmis.gov.la/hmis", "admin", "pw")
    resp = MagicMock()
    resp.json.return_value = {"name": "Admin User", "username": "admin"}
    resp.raise_for_status.return_value = None
    with patch.object(c._session, "get", return_value=resp) as mock_get:
        me = c.test_connection()
        assert me["name"] == "Admin User"
        called_url = mock_get.call_args[0][0]
        assert "me.json" in called_url


def _patch_worker_deps(cache_value, fetch_all_mock):
    """Patch everything _connect_worker imports; returns a contextmanager list."""
    client = MagicMock()
    client.test_connection.return_value = {"name": "U", "username": "u"}
    client.base_url = "https://hmis.gov.la/hmis"
    return [
        patch("dhis2.client.DHIS2Client", return_value=client),
        patch("dhis2.filter_options.fetch_all_filter_options", return_value={}),
        patch("dhis2.cache.load", return_value=cache_value),
        patch("dhis2.cache.load_filter_cfg", return_value={}),
        patch("dhis2.cache.save"),
        patch("dhis2.metadata.fetch_all", fetch_all_mock),
        # _on_connect_done (triggered by the emitted signal) would kick off the real
        # background sample download — stub it out for these worker-logic tests.
        patch("ui.app_window.AppWindow._download_sample_background"),
    ]


def test_connect_worker_uses_cache(make_window):
    """REQ-LOGIN-CACHE-01: with cached metadata and no force-refresh, server is not re-fetched."""
    win = make_window()
    captured = []
    win._sig_connect_done.connect(lambda *a: captured.append(a))
    cached_meta = {"indicators": [], "program_indicators": [], "data_elements": [], "programs": []}
    fetch_all = MagicMock()
    from contextlib import ExitStack
    with ExitStack() as es:
        for p in _patch_worker_deps((cached_meta, "2026-01-01 00:00 UTC"), fetch_all):
            es.enter_context(p)
        win._connect_worker("https://hmis.gov.la/hmis", "u", "p", False)
    assert not fetch_all.called                       # cache used, no server fetch
    assert captured and captured[0][3] is True        # from_cache flag emitted


def test_connect_worker_force_refresh(make_window):
    """REQ-LOGIN-CACHE-03: ↻ force-refresh bypasses cache and fetches from server."""
    win = make_window()
    win._sig_connect_done.connect(lambda *a: None)
    fetch_all = MagicMock(return_value={"indicators": [], "program_indicators": [],
                                        "data_elements": [], "programs": [], "_filter_config": {}})
    from contextlib import ExitStack
    with ExitStack() as es:
        for p in _patch_worker_deps((None, None), fetch_all):
            es.enter_context(p)
        win._connect_worker("https://hmis.gov.la/hmis", "u", "p", True)
    assert fetch_all.called                            # forced → server fetch happened


# ─── Third batch: remaining REQs ─────────────────────────────────────────────

def test_current_api_key_precedence(make_window):
    """REQ-LOGIN-APIKEY-03: field value wins; falls back to the saved/_api_key value."""
    win = make_window()
    win._api_key = "saved-key"
    win.apikey_entry.setText("")
    assert win.current_api_key() == "saved-key"
    win.apikey_entry.setText("  typed-key  ")
    assert win.current_api_key() == "typed-key"


def test_status_signal_updates_label(make_window):
    """REQ-LOGIN-CONN-04: worker→UI communication goes through Qt signals."""
    win = make_window()
    win._sig_status.emit("hello from worker")
    assert win.status_label.text() == "hello from worker"


def test_connect_worker_no_cache_fetches(make_window):
    """REQ-LOGIN-CACHE-02: no cache + no force-refresh → fetch from server (from_cache False)."""
    win = make_window()
    captured = []
    win._sig_connect_done.connect(lambda *a: captured.append(a))
    fetch_all = MagicMock(return_value={"indicators": [], "program_indicators": [],
                                        "data_elements": [], "programs": [], "_filter_config": {}})
    from contextlib import ExitStack
    with ExitStack() as es:
        for p in _patch_worker_deps((None, None), fetch_all):
            es.enter_context(p)
        win._connect_worker("https://hmis.gov.la/hmis", "u", "p", False)
    assert fetch_all.called
    assert captured and captured[0][3] is False        # not from cache


def test_cache_key_by_url(tmp_path, monkeypatch):
    """REQ-LOGIN-CACHE-04: metadata cache is keyed per-URL (different URLs don't collide)."""
    import dhis2.cache as cache
    monkeypatch.setattr(cache, "_CACHE_ROOT", tmp_path)
    cache.save("https://a.org/hmis", {"programs": ["A"]})
    cache.save("https://b.org/hmis", {"programs": ["B"]})
    meta_a, _ = cache.load("https://a.org/hmis")
    meta_b, _ = cache.load("https://b.org/hmis")
    assert meta_a["programs"] == ["A"]
    assert meta_b["programs"] == ["B"]


def test_client_holds_auth_in_memory():
    """REQ-LOGIN-SEC-03: DHIS2Client keeps credentials in memory (Basic Auth), no disk write."""
    from dhis2.client import DHIS2Client
    c = DHIS2Client("https://hmis.gov.la/hmis", "admin", "pw")
    assert c._auth.username == "admin" and c._auth.password == "pw"
    assert c._session.auth is c._auth
    assert c.base_url.endswith("/api")
