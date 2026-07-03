import json
import re

import pytest
from typer.testing import CliRunner

from worldclock_tty.chronos import (
    Chronos,
    DEFAULT_TIMEZONES,
    _config_dir,
    _get_city,
    _load_config,
    _save_config,
    app,
)

runner = CliRunner()


def _text(result):
    """Combined stdout + stderr, robust across Click versions.

    Click 8.2 split stderr out of ``.output``; some CLI messages use
    ``err=True``, so gather both to keep message assertions version-proof.
    """
    parts = [result.output]
    try:
        parts.append(result.stderr)
    except (ValueError, AttributeError):
        pass
    return "".join(p for p in parts if p)


@pytest.fixture
def config_path(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr("worldclock_tty.chronos.CONFIG_PATH", path)
    return path


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


class TestConfigDir:
    def test_uses_xdg_config_home_when_absolute(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        assert _config_dir() == tmp_path / "worldclock-tty"

    def test_falls_back_to_home_config_when_unset(self, tmp_path, monkeypatch):
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        assert _config_dir() == tmp_path / ".config" / "worldclock-tty"

    def test_ignores_relative_xdg(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", "relative/dir")
        monkeypatch.setenv("HOME", str(tmp_path))
        assert _config_dir() == tmp_path / ".config" / "worldclock-tty"

    def test_dir_named_after_package_not_chronos(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        assert _config_dir().name == "worldclock-tty"
        assert "chronos" not in str(_config_dir())


class TestCli:
    def _zones(self, config_path):
        return json.loads(config_path.read_text())["timezones"]

    # --- add ---
    def test_add_valid_zone(self, config_path):
        result = runner.invoke(app, ["add", "America/Chicago"])
        assert result.exit_code == 0
        assert "Added" in _text(result)
        assert "America/Chicago" in self._zones(config_path)

    def test_add_invalid_zone_rejected_and_not_saved(self, config_path):
        result = runner.invoke(app, ["add", "Foo/Bar"])
        assert result.exit_code == 1
        assert "not a valid" in _text(result)
        assert not config_path.exists()

    def test_add_empty_zone_rejected(self, config_path):
        result = runner.invoke(app, ["add", ""])
        assert result.exit_code == 1
        assert not config_path.exists()

    def test_add_wrong_case_rejected(self, config_path):
        result = runner.invoke(app, ["add", "america/lima"])
        assert result.exit_code == 1
        assert not config_path.exists()

    def test_add_duplicate_rejected(self, config_path):
        _save_config(["America/New_York"])
        result = runner.invoke(app, ["add", "America/New_York"])
        assert result.exit_code == 1
        assert "already" in _text(result)
        assert self._zones(config_path) == ["America/New_York"]

    # --- remove ---
    def test_remove_existing_zone(self, config_path):
        _save_config(["America/New_York", "Asia/Tokyo"])
        result = runner.invoke(app, ["remove", "Asia/Tokyo"])
        assert result.exit_code == 0
        assert self._zones(config_path) == ["America/New_York"]

    def test_remove_missing_zone_rejected(self, config_path):
        _save_config(["America/New_York"])
        result = runner.invoke(app, ["remove", "Asia/Tokyo"])
        assert result.exit_code == 1
        assert "not found" in _text(result)
        assert self._zones(config_path) == ["America/New_York"]

    # --- list ---
    def test_list_shows_configured_zones(self, config_path):
        _save_config(["America/New_York", "Asia/Tokyo"])
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        out = _text(result)
        assert "America/New_York" in out
        assert "Asia/Tokyo" in out

    def test_list_uses_defaults_when_no_config(self, config_path):
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert _text(result).strip().splitlines() == list(DEFAULT_TIMEZONES)

    # --- reset ---
    def test_reset_restores_defaults(self, config_path):
        _save_config(["America/New_York"])
        result = runner.invoke(app, ["reset"])
        assert result.exit_code == 0
        assert self._zones(config_path) == DEFAULT_TIMEZONES

    # --- corrupt config ---
    def test_malformed_json_reported(self, config_path):
        config_path.write_text("{ not valid json")
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 1
        text = _text(result)
        assert "invalid" in text.lower()
        assert "reset" in text  # guides the user to the fix

    def test_missing_timezones_key_reported(self, config_path):
        config_path.write_text('{"foo": "bar"}')
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 1
        assert "invalid" in _text(result).lower()

    def test_timezones_not_a_list_reported(self, config_path):
        config_path.write_text('{"timezones": "America/Lima"}')
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 1

    def test_toplevel_not_object_reported(self, config_path):
        config_path.write_text("[1, 2, 3]")
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 1

    def test_reset_recovers_from_corrupt_config(self, config_path):
        config_path.write_text("{ garbage")
        result = runner.invoke(app, ["reset"])
        assert result.exit_code == 0
        assert self._zones(config_path) == DEFAULT_TIMEZONES


class TestTimeFormat:
    def test_default_is_24h(self):
        assert Chronos().time_format == "HH:mm:ss"

    def test_entry_uses_24h_by_default(self):
        plain, _ = Chronos(show_offset=False)._entry("UTC")
        assert re.search(r"\d\d:\d\d:\d\d$", plain.rstrip())
        assert "AM" not in plain and "PM" not in plain

    def test_entry_uses_12h_format(self):
        plain, _ = Chronos(show_offset=False, time_format="hh:mm:ss A")._entry("UTC")
        assert re.search(r"\d\d:\d\d:\d\d (AM|PM)$", plain.rstrip())

    def _captured_format(self, monkeypatch, flag):
        captured = {}
        monkeypatch.setattr(
            Chronos,
            "print_time_screen",
            lambda self, tzs: captured.update(fmt=self.time_format),
        )
        result = runner.invoke(app, [flag] if flag else [])
        assert result.exit_code == 0
        return captured["fmt"]

    def test_24h_flag_selects_24h(self, config_path, monkeypatch):
        assert self._captured_format(monkeypatch, "--24h") == "HH:mm:ss"

    def test_12h_flag_selects_12h(self, config_path, monkeypatch):
        assert self._captured_format(monkeypatch, "--12h") == "hh:mm:ss A"

    def test_no_flag_defaults_to_24h(self, config_path, monkeypatch):
        assert self._captured_format(monkeypatch, "") == "HH:mm:ss"
