import json
import pytest

from config.settings import AppSettings, SettingsError, SettingsStore


def test_settings_round_trip_contains_only_execution_identifiers(tmp_path):
    settings = AppSettings(default_execution_mode="direct", interactive_agent="qoder", direct_agent="qoder", direct_model="actual")
    SettingsStore(tmp_path).save(settings)
    loaded = SettingsStore(tmp_path).load()
    assert loaded.direct_model == settings.direct_model
    raw = (tmp_path / "settings.json").read_text(encoding="utf-8")
    assert "byok" not in raw and "api_key" not in raw


def test_legacy_qoder_selection_migrates_to_cn_identifier(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({"default_agent": "qoder", "qoder_model": "old"}), encoding="utf-8")
    loaded = SettingsStore(tmp_path).load()
    assert loaded.direct_model == "old"


def test_corrupt_settings_raises(tmp_path):
    (tmp_path / "settings.json").write_text("{bad", encoding="utf-8")
    with pytest.raises(SettingsError): SettingsStore(tmp_path).load()
