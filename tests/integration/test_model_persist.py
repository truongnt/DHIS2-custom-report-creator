"""REQ-AI-MODEL-PERSIST-01: the selected AI model is remembered across app restarts —
stored in config/app_settings.json (a file in the app folder, NOT the Windows registry)."""
import pytest
pytestmark = pytest.mark.integration


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    """Point the JSON settings store at a temp file so the test never touches real config."""
    import config.app_settings as aps
    monkeypatch.setattr(aps, "_FILE", tmp_path / "app_settings.json")
    return aps


def test_model_choice_persists(qtbot, settings_file):
    aps = settings_file
    aps.set("ai_model_label", "Opus 4.8  (best quality)")
    from ui.app_window import AppWindow
    w = AppWindow(); qtbot.addWidget(w)
    # restored from the JSON file on construction
    assert w.model_combo.currentText() == "Opus 4.8  (best quality)"
    assert w._get_model() == "claude-opus-4-8"
    # changing the combo writes back to the JSON file (not the registry)
    w.model_combo.setCurrentText("Sonnet 4.6  (balanced)")
    assert aps.get("ai_model_label") == "Sonnet 4.6  (balanced)"


def test_settings_stored_as_json_in_app_folder(settings_file):
    """REQ-AI-MODEL-PERSIST-02: the store is a JSON file under config/, not QSettings."""
    import json
    aps = settings_file
    aps.set("ai_model_label", "Haiku 4.5  (fast, cheap)")
    assert aps._FILE.exists() and aps._FILE.suffix == ".json"
    assert json.loads(aps._FILE.read_text(encoding="utf-8"))["ai_model_label"] \
        == "Haiku 4.5  (fast, cheap)"
