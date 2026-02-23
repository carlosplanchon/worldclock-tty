import json

import pytest

from worldclock_tty.chronos import (
    DEFAULT_TIMEZONES,
    _get_city,
    _load_config,
    _save_config,
)


class TestGetCity:
    def test_standard_iana(self):
        assert _get_city("America/Buenos_Aires") == "Buenos Aires"

    def test_underscores_replaced(self):
        assert _get_city("Asia/Hong_Kong") == "Hong Kong"

    def test_plain_zone(self):
        assert _get_city("UTC") == "UTC"

    def test_two_part_zone(self):
        assert _get_city("US/Eastern") == "Eastern"

    def test_no_trailing_underscore_artifact(self):
        assert "_" not in _get_city("Europe/New_York")

    @pytest.mark.parametrize("tz", DEFAULT_TIMEZONES)
    def test_all_defaults_parse(self, tz):
        city = _get_city(tz)
        assert isinstance(city, str)
        assert len(city) > 0
        assert "_" not in city


class TestConfig:
    def test_load_returns_defaults_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "worldclock_tty.chronos.CONFIG_PATH", tmp_path / "config.json"
        )
        assert _load_config() == DEFAULT_TIMEZONES

    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.json"
        monkeypatch.setattr("worldclock_tty.chronos.CONFIG_PATH", config_path)

        zones = ["America/New_York", "Asia/Tokyo"]
        _save_config(zones)
        assert _load_config() == zones

    def test_save_creates_parent_dirs(self, tmp_path, monkeypatch):
        config_path = tmp_path / "nested" / "dir" / "config.json"
        monkeypatch.setattr("worldclock_tty.chronos.CONFIG_PATH", config_path)

        _save_config(["UTC"])
        assert config_path.exists()

    def test_saved_file_is_valid_json(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.json"
        monkeypatch.setattr("worldclock_tty.chronos.CONFIG_PATH", config_path)

        _save_config(["Europe/London"])
        data = json.loads(config_path.read_text())
        assert "timezones" in data
        assert data["timezones"] == ["Europe/London"]

    def test_load_does_not_mutate_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "worldclock_tty.chronos.CONFIG_PATH", tmp_path / "config.json"
        )
        result = _load_config()
        result.append("EXTRA")
        assert "EXTRA" not in DEFAULT_TIMEZONES
