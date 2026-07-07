import json
import re

import pendulum
import pytest
from typer.testing import CliRunner

from worldclock_tty.chronos import (
    Chronos,
    DEFAULT_TIMEZONES,
    THEMES,
    _DEFAULT_THEME,
    _ELEMENTS,
    _config_dir,
    _dtg,
    _dtg_parts,
    _get_city,
    _is_valid_color,
    _load_config,
    _load_theme_name,
    _military_letter,
    _parse_color_override,
    _save_config,
    _save_theme_name,
    _seconds_until_next_tick,
    _theme_palette,
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

    def test_missing_timezones_key_uses_defaults(self, config_path):
        # A config without a 'timezones' key (e.g. theme-only) is valid.
        config_path.write_text('{"theme": "matrix"}')
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert _text(result).strip().splitlines() == list(DEFAULT_TIMEZONES)

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


class TestMilitaryLetter:
    @pytest.mark.parametrize(
        "hours,letter",
        [
            (0, "Z"),    # Zulu
            (1, "A"),    # Alpha
            (9, "I"),    # India (last before the skipped J)
            (10, "K"),   # Kilo (J is skipped)
            (12, "M"),   # Mike
            (-1, "N"),   # November
            (-3, "P"),   # Papa (Montevideo / Buenos Aires)
            (-12, "Y"),  # Yankee
        ],
    )
    def test_whole_hour_offsets(self, hours, letter):
        assert _military_letter(hours * 3600) == letter

    def test_juliet_is_never_emitted(self):
        letters = {_military_letter(h * 3600) for h in range(-12, 13)}
        assert "J" not in letters

    def test_half_hour_offset_has_no_letter(self):
        assert _military_letter(int(5.5 * 3600)) is None  # India +5:30

    def test_quarter_hour_offset_has_no_letter(self):
        assert _military_letter(int(5.75 * 3600)) is None  # Nepal +5:45

    @pytest.mark.parametrize("hours", [13, 14, -13])
    def test_offsets_beyond_twelve_have_no_letter(self, hours):
        assert _military_letter(hours * 3600) is None


class TestMilitaryDisplay:
    def test_letter_replaces_numeric_by_default(self):
        c = Chronos(military=True)
        assert c._offset_label(-3 * 3600) == "P"

    def test_zulu_for_utc(self):
        assert Chronos(military=True)._offset_label(0) == "Z"

    def test_utc_flag_shows_both(self):
        c = Chronos(military=True, show_utc=True)
        assert c._offset_label(-3 * 3600) == "P UTC-3"

    def test_non_military_shows_numeric(self):
        assert Chronos()._offset_label(-3 * 3600) == "UTC-3"

    def test_utc_flag_ignored_without_military(self):
        assert Chronos(show_utc=True)._offset_label(-3 * 3600) == "UTC-3"

    def test_no_letter_falls_back_to_numeric(self):
        c = Chronos(military=True)
        assert c._offset_label(int(5.5 * 3600)) == "UTC+5:30"

    def test_entry_uses_letter_in_military_mode(self):
        # "UTC" here is the city name; the offset field must read "Z", not "UTC+0".
        plain, _ = Chronos(military=True)._entry("UTC")
        assert " Z " in f" {plain} "
        assert "UTC+0" not in plain

    def _captured_flags(self, monkeypatch, args):
        captured = {}
        monkeypatch.setattr(
            Chronos,
            "print_time_screen",
            lambda self, tzs: captured.update(
                military=self.military, show_utc=self.show_utc
            ),
        )
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        return captured

    def test_military_flag_wired(self, config_path, monkeypatch):
        assert self._captured_flags(monkeypatch, ["--military"]) == {
            "military": True,
            "show_utc": False,
        }

    def test_zulu_alias_wired(self, config_path, monkeypatch):
        assert self._captured_flags(monkeypatch, ["--zulu"]) == {
            "military": True,
            "show_utc": False,
        }

    def test_military_utc_flags_wired(self, config_path, monkeypatch):
        assert self._captured_flags(monkeypatch, ["--military", "--utc"]) == {
            "military": True,
            "show_utc": True,
        }

    def test_defaults_are_non_military(self, config_path, monkeypatch):
        assert self._captured_flags(monkeypatch, []) == {
            "military": False,
            "show_utc": False,
        }


class TestDtg:
    def test_shape(self):
        t = pendulum.datetime(2026, 7, 4, 14, 38, 22, tz="UTC")
        assert re.fullmatch(r"\d{6}[A-Z*] [A-Z]{3} \d{2}", _dtg(t))

    def test_zulu_for_utc(self):
        t = pendulum.datetime(2026, 7, 4, 14, 38, tz="UTC")
        assert _dtg(t) == "041438Z JUL 26"

    def test_letter_reflects_offset(self):
        t = pendulum.datetime(2026, 7, 4, 14, 38, tz="America/Montevideo")  # UTC-3
        assert _dtg(t) == "041438P JUL 26"

    def test_month_is_uppercased(self):
        t = pendulum.datetime(2026, 1, 9, 5, 7, tz="UTC")
        assert _dtg(t) == "090507Z JAN 26"

    def test_letter_override_forces_juliet(self):
        t = pendulum.datetime(2026, 7, 4, 14, 38, tz="America/Montevideo")
        assert _dtg(t, letter="J") == "041438J JUL 26"

    def test_offset_without_letter_uses_asterisk(self):
        t = pendulum.datetime(2026, 7, 4, 14, 38, tz="Asia/Kolkata")  # UTC+5:30
        assert _dtg(t) == "041438* JUL 26"

    def test_parts_split(self):
        t = pendulum.datetime(2026, 7, 4, 14, 38, tz="UTC")
        assert _dtg_parts(t) == ("041438Z", "JUL 26")


_DTG_CELL = re.compile(r"\d{6}[A-Z*] [A-Z]{3} \d{2}$")


class TestFullMilitaryDisplay:
    def test_entry_ends_with_dtg(self):
        plain, _ = Chronos(full_military=True)._entry("UTC")
        assert _DTG_CELL.search(plain.rstrip())

    def test_entry_has_no_numeric_offset_column(self):
        # "UTC" appears as the city name; the numeric "UTC+0" offset must not.
        plain, _ = Chronos(full_military=True)._entry("UTC")
        assert "UTC+" not in plain

    def test_full_military_overrides_other_offset_flags(self):
        # full_military takes over even when the other offset flags are set.
        plain, _ = Chronos(
            full_military=True, military=True, show_utc=True, show_offset=False
        )._entry("UTC")
        assert _DTG_CELL.search(plain.rstrip())
        assert "UTC+" not in plain

    def _captured_full(self, monkeypatch, args):
        captured = {}
        monkeypatch.setattr(
            Chronos,
            "print_time_screen",
            lambda self, tzs: captured.update(full_military=self.full_military),
        )
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        return captured["full_military"]

    def test_full_military_flag_wired(self, config_path, monkeypatch):
        assert self._captured_full(monkeypatch, ["--full-military"]) is True

    def test_dtg_alias_wired(self, config_path, monkeypatch):
        assert self._captured_full(monkeypatch, ["--dtg"]) is True

    def test_default_is_not_full_military(self, config_path, monkeypatch):
        assert self._captured_full(monkeypatch, []) is False


class TestColorValidation:
    @pytest.mark.parametrize("value", ["green", "cornflower_blue", "0", "75", "255"])
    def test_accepts_names_and_codes(self, value):
        assert _is_valid_color(value)

    @pytest.mark.parametrize("value", ["notacolor", "256", "999", "", "#ff8800"])
    def test_rejects_invalid(self, value):
        assert not _is_valid_color(value)


class TestParseColorOverride:
    def test_name_value(self):
        assert _parse_color_override("city=green") == ("city", "green")

    def test_code_value(self):
        assert _parse_color_override("time=226") == ("time", "226")

    def test_tolerates_surrounding_whitespace(self):
        assert _parse_color_override(" local-time = 82 ") == ("local-time", "82")

    def test_missing_equals_raises(self):
        with pytest.raises(ValueError, match="ELEMENT=COLOR"):
            _parse_color_override("citygreen")

    def test_unknown_element_raises(self):
        with pytest.raises(ValueError, match="Unknown element"):
            _parse_color_override("foo=green")

    def test_invalid_color_raises(self):
        with pytest.raises(ValueError, match="Invalid color"):
            _parse_color_override("city=notacolor")


class TestThemePalette:
    def test_default_reproduces_original_palette(self):
        # Guards against accidental drift of the built-in look.
        assert _theme_palette("default") == {
            "city": "75", "offset": "240", "time": "255",
            "label": "11", "date": "244", "local-time": "255",
        }

    def test_unknown_theme_is_none(self):
        assert _theme_palette("nope") is None

    @pytest.mark.parametrize("name", list(THEMES))
    def test_every_theme_covers_all_elements(self, name):
        palette = _theme_palette(name)
        assert set(palette) == set(_ELEMENTS)
        assert all(_is_valid_color(c) for c in palette.values())

    def test_partial_theme_merges_over_default(self, monkeypatch):
        monkeypatch.setitem(THEMES, "half", {"city": "green"})
        palette = _theme_palette("half")
        assert palette["city"] == "green"          # from the partial theme
        assert palette["time"] == _DEFAULT_THEME["time"]  # filled from default


class TestThemePersistence:
    def _theme_in_config(self, config_path):
        return json.loads(config_path.read_text()).get("theme")

    def test_set_persists_theme(self, config_path):
        result = runner.invoke(app, ["theme", "set", "matrix"])
        assert result.exit_code == 0
        assert self._theme_in_config(config_path) == "matrix"

    def test_set_unknown_theme_rejected(self, config_path):
        result = runner.invoke(app, ["theme", "set", "bogus"])
        assert result.exit_code == 1
        assert "Unknown theme" in _text(result)
        assert not config_path.exists()

    def test_list_marks_saved_theme(self, config_path):
        _save_theme_name("amber")
        result = runner.invoke(app, ["theme", "list"])
        assert result.exit_code == 0
        lines = _text(result).strip().splitlines()
        assert any(line.startswith("amber") and "saved" in line for line in lines)

    def test_reset_clears_theme(self, config_path):
        _save_theme_name("ocean")
        result = runner.invoke(app, ["theme", "reset"])
        assert result.exit_code == 0
        assert _load_theme_name() is None

    def test_theme_survives_add(self, config_path):
        _save_theme_name("matrix")
        result = runner.invoke(app, ["add", "America/Chicago"])
        assert result.exit_code == 0
        assert self._theme_in_config(config_path) == "matrix"
        assert "America/Chicago" in _load_config()

    def test_theme_survives_reset(self, config_path):
        _save_theme_name("matrix")
        runner.invoke(app, ["reset"])
        assert _load_theme_name() == "matrix"
        assert _load_config() == DEFAULT_TIMEZONES


class TestColorResolution:
    """The palette handed to Chronos: theme (flag > saved > default) + --color."""

    def _captured_palette(self, monkeypatch, args):
        captured = {}
        monkeypatch.setattr(
            Chronos,
            "print_time_screen",
            lambda self, tzs: captured.update(palette=self.palette),
        )
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        return captured["palette"]

    def test_default_when_nothing_set(self, config_path, monkeypatch):
        assert self._captured_palette(monkeypatch, []) == _DEFAULT_THEME

    def test_theme_flag_selects_palette(self, config_path, monkeypatch):
        assert self._captured_palette(monkeypatch, ["--theme", "matrix"]) == _theme_palette("matrix")

    def test_saved_theme_used_without_flag(self, config_path, monkeypatch):
        _save_theme_name("amber")
        assert self._captured_palette(monkeypatch, []) == _theme_palette("amber")

    def test_flag_overrides_saved_theme(self, config_path, monkeypatch):
        _save_theme_name("amber")
        assert self._captured_palette(monkeypatch, ["--theme", "ocean"]) == _theme_palette("ocean")

    def test_color_override_layers_on_theme(self, config_path, monkeypatch):
        palette = self._captured_palette(
            monkeypatch, ["--theme", "matrix", "--color", "time=196"]
        )
        assert palette["time"] == "196"                       # override wins
        assert palette["city"] == _theme_palette("matrix")["city"]  # theme kept

    def test_multiple_color_overrides(self, config_path, monkeypatch):
        palette = self._captured_palette(
            monkeypatch, ["--color", "city=green", "--color", "label=201"]
        )
        assert palette["city"] == "green"
        assert palette["label"] == "201"

    def test_unknown_theme_falls_back_to_default(self, config_path, monkeypatch):
        # Warns on stderr but still runs with the default palette (exit 0).
        assert self._captured_palette(monkeypatch, ["--theme", "nope"]) == _DEFAULT_THEME

    def test_invalid_color_exits(self, config_path):
        result = runner.invoke(app, ["--color", "city=notacolor"])
        assert result.exit_code == 1
        assert "Invalid color" in _text(result)


class TestChronosPalette:
    def test_defaults_to_default_theme(self):
        assert Chronos().palette == _DEFAULT_THEME

    def test_stores_given_palette(self):
        pal = _theme_palette("matrix")
        assert Chronos(palette=pal).palette == pal

    def test_bold_is_structural(self):
        # label and local-time stay bold; entries do not. Force ANSI on so the
        # assertion is meaningful even though pytest's stdout is not a TTY.
        import colored

        colored.set_tty_aware(False)
        try:
            bold = colored.attr("bold")
            c = Chronos()
            assert bold  # sanity: color is actually being emitted
            assert c.LOCAL_LABEL.startswith(bold)
            assert c.LOCAL_TIME.startswith(bold)
            assert not c.CITY.startswith(bold)
        finally:
            colored.set_tty_aware(True)


class TestVersion:
    def test_version_flag_prints_and_exits(self):
        from worldclock_tty import __version__

        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        out = _text(result)
        assert "worldclock-tty" in out
        assert __version__ in out

    def test_version_short_circuits_before_config(self, config_path):
        # Eager: prints even when the config is corrupt (never loads it).
        config_path.write_text("{ garbage")
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "invalid" not in _text(result).lower()


class TestNextTick:
    @pytest.mark.parametrize(
        "second,interval,expected",
        [
            (3, 5, 2),    # 12:00:03 -> :05
            (7, 5, 3),    # :07 -> :10
            (58, 5, 2),   # :58 -> :00 of the next minute
            (0, 5, 5),    # already on a boundary -> a full interval to the next
            (3, 2, 1),    # :03 -> :04
            (0, 2, 2),
        ],
    )
    def test_delay_to_next_boundary(self, second, interval, expected):
        t = pendulum.datetime(2026, 7, 4, 12, 0, second, tz="UTC")
        assert _seconds_until_next_tick(t, interval) == expected

    def test_includes_subsecond_position(self):
        t = pendulum.datetime(2026, 7, 4, 12, 0, 3, 500000, tz="UTC")  # :03.5
        assert _seconds_until_next_tick(t, 2) == pytest.approx(0.5)  # -> :04

    def test_aligns_to_the_minute(self):
        t = pendulum.datetime(2026, 7, 4, 12, 0, 41, tz="UTC")
        assert _seconds_until_next_tick(t, 60) == 19  # -> 12:01:00

    def test_aligns_to_five_minute_mark(self):
        t = pendulum.datetime(2026, 7, 4, 12, 3, 0, tz="UTC")
        assert _seconds_until_next_tick(t, 300) == 120  # -> 12:05:00

    def test_delay_always_within_interval(self):
        # Never 0 (no busy loop) and never past a full interval.
        for second in range(60):
            t = pendulum.datetime(2026, 7, 4, 12, 0, second, tz="UTC")
            assert 0 < _seconds_until_next_tick(t, 5) <= 5


class TestRefreshInterval:
    def _captured_refresh(self, monkeypatch, args):
        captured = {}
        monkeypatch.setattr(
            Chronos,
            "print_time_screen",
            lambda self, tzs: captured.update(refresh=self.refresh),
        )
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        return captured["refresh"]

    def test_default_is_one_second(self, config_path, monkeypatch):
        assert self._captured_refresh(monkeypatch, []) == 1

    def test_interval_flag_wired(self, config_path, monkeypatch):
        assert self._captured_refresh(monkeypatch, ["--interval", "5"]) == 5

    def test_short_flag_wired(self, config_path, monkeypatch):
        assert self._captured_refresh(monkeypatch, ["-n", "2"]) == 2

    def test_zero_rejected(self, config_path):
        result = runner.invoke(app, ["-n", "0"])
        assert result.exit_code != 0

    def test_chronos_defaults_to_one(self):
        assert Chronos().refresh == 1
