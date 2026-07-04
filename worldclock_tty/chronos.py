#!/usr/bin/env python3

import json
import os
import sys
from pathlib import Path
from time import sleep
from typing import NoReturn

import typer
from colored import attr, fg
from colored.library import Library
from pendulum import now

DEFAULT_TIMEZONES = [
    "America/Buenos_Aires",
    "America/Caracas",
    "America/La_Paz",
    "America/Lima",
    "America/Los_Angeles",
    "America/Montevideo",
    "America/New_York",
    "America/Sao_Paulo",
    "Asia/Bangkok",
    "Asia/Dubai",
    "Asia/Hong_Kong",
    "Asia/Istanbul",
    "Asia/Tokyo",
    "Asia/Vladivostok",
    "Atlantic/Bermuda",
    "Atlantic/Canary",
    "Australia/Sydney",
    "Europe/London",
    "Europe/Madrid",
    "Europe/Moscow",
    "Europe/Rome",
    "Pacific/Honolulu",
]

def _config_dir() -> Path:
    """Base directory for the config, honoring ``XDG_CONFIG_HOME``.

    Per the XDG spec, a relative or empty value is ignored and falls
    back to ``~/.config``.
    """
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    base = Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / ".config"
    return base / "worldclock-tty"


CONFIG_PATH = _config_dir() / "config.json"


def _get_city(tz: str) -> str:
    """Extract a display name from a timezone string.

    Handles plain zones (UTC), two-part zones (US/Eastern),
    and standard IANA zones (America/Buenos_Aires).
    """
    return tz.split("/")[-1].replace("_", " ")


# NATO/military zone letters for whole-hour offsets. East of UTC runs
# A..M (skipping J, reserved for local time); west runs N..Y; Z is UTC+0.
_MIL_EAST = "ABCDEFGHIKLM"   # +1 .. +12
_MIL_WEST = "NOPQRSTUVWXY"   # -1 .. -12


def _military_letter(offset_seconds: int) -> str | None:
    """Return the military zone letter for a UTC offset given in seconds.

    Offsets that aren't a whole number of hours (e.g. India +5:30) or that
    fall outside ±12h (e.g. Kiritimati +14) have no official designator and
    return ``None``.
    """
    if offset_seconds % 3600:
        return None
    hours = offset_seconds // 3600
    if hours == 0:
        return "Z"
    if 1 <= hours <= 12:
        return _MIL_EAST[hours - 1]
    if -12 <= hours <= -1:
        return _MIL_WEST[-hours - 1]
    return None


def _dtg_parts(t, letter: str | None = None) -> tuple[str, str]:
    """Split a military Date-Time Group into (time_group, calendar).

    ``time_group`` is ``DDHHMM`` plus the zone letter (e.g. ``041438P``);
    ``calendar`` is the ``MON YY`` tail (e.g. ``JUL 26``). Passing ``letter``
    overrides the zone letter derived from ``t``, forcing ``J``
    (Juliet, local time) on the observer's own clock. Offsets with no
    official designator use ``*``.
    """
    if letter is None:
        letter = _military_letter(t.offset) or "*"
    time_group = f"{t.format('DDHHmm')}{letter}"
    calendar = f"{t.format('MMM').upper()} {t.format('YY')}"
    return time_group, calendar


def _dtg(t, letter: str | None = None) -> str:
    """Full military Date-Time Group, e.g. ``041438P JUL 26``."""
    time_group, calendar = _dtg_parts(t, letter)
    return f"{time_group} {calendar}"


def _config_error(detail: object) -> NoReturn:
    typer.echo(
        f"Config file at {CONFIG_PATH} is invalid ({detail}).\n"
        "Fix it by hand or run 'worldclock-tty reset' to restore the defaults.",
        err=True,
    )
    raise typer.Exit(1)


def _read_config_safe() -> dict:
    """Best-effort read of the config object; never raises.

    Returns ``{}`` when the file is missing or unreadable, so callers that
    merge-and-save (timezones, theme) don't clobber a sibling key and can
    still recover from a corrupt file.
    """
    try:
        data = json.loads(CONFIG_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_config(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2))


def _load_config() -> list[str]:
    if not CONFIG_PATH.exists():
        return list(DEFAULT_TIMEZONES)
    try:
        data = json.loads(CONFIG_PATH.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        _config_error(exc)
    if not isinstance(data, dict):
        _config_error("config must be a JSON object")
    if "timezones" not in data:
        # A theme-only config (no timezones set) is valid: use the defaults.
        return list(DEFAULT_TIMEZONES)
    if not isinstance(data["timezones"], list):
        _config_error("'timezones' must be a list")
    return data["timezones"]


def _save_config(timezones: list[str]) -> None:
    data = _read_config_safe()
    data["timezones"] = timezones
    _write_config(data)


def _load_theme_name() -> str | None:
    """The persisted default theme name, or ``None`` when unset."""
    name = _read_config_safe().get("theme")
    return name if isinstance(name, str) else None


def _save_theme_name(name: str | None) -> None:
    """Persist (or, with ``None``, clear) the default theme in the config."""
    data = _read_config_safe()
    if name is None:
        data.pop("theme", None)
    else:
        data["theme"] = name
    _write_config(data)


def _is_valid_timezone(tz: str) -> bool:
    """Return True if `tz` is an IANA name pendulum can resolve.

    Validates against the same call the clock uses at runtime, so any
    zone accepted here is guaranteed not to break the display later.
    """
    try:
        now(tz)
    except ValueError:
        return False
    return True


# Colorable elements. ``label`` and ``local-time`` are bold as a structural
# emphasis of the header; themes and --color change only their color.
_ELEMENTS = ("city", "offset", "time", "label", "date", "local-time")
_BOLD_ELEMENTS = frozenset({"label", "local-time"})

# Each theme maps every element to a color (256-color code or name). The
# "default" theme reproduces the original hardcoded palette exactly.
THEMES: dict[str, dict[str, str]] = {
    "default": {
        "city": "75", "offset": "240", "time": "255",
        "label": "11", "date": "244", "local-time": "255",
    },
    "mono": {
        "city": "250", "offset": "240", "time": "255",
        "label": "255", "date": "244", "local-time": "255",
    },
    "matrix": {
        "city": "40", "offset": "22", "time": "46",
        "label": "46", "date": "28", "local-time": "82",
    },
    "amber": {
        "city": "214", "offset": "94", "time": "220",
        "label": "202", "date": "136", "local-time": "220",
    },
    "ocean": {
        "city": "39", "offset": "24", "time": "51",
        "label": "45", "date": "31", "local-time": "123",
    },
}

_DEFAULT_THEME = THEMES["default"]


def _is_valid_color(value: str) -> bool:
    """True if `value` is a color name or a 0-255 code the library accepts."""
    return value in Library.COLORS or value in Library.COLORS.values()


def _theme_palette(name: str) -> dict[str, str] | None:
    """Full palette for a theme name, or ``None`` if the theme is unknown.

    A theme is merged over the default so a partial theme still yields a
    color for every element.
    """
    theme = THEMES.get(name)
    if theme is None:
        return None
    palette = dict(_DEFAULT_THEME)
    palette.update(theme)
    return palette


def _parse_color_override(spec: str) -> tuple[str, str]:
    """Parse an ``ELEMENT=COLOR`` override, raising ``ValueError`` if invalid."""
    element, sep, value = spec.partition("=")
    element, value = element.strip(), value.strip()
    if not sep or not element:
        raise ValueError(
            f"Invalid --color '{spec}'; expected ELEMENT=COLOR, e.g. city=green."
        )
    if element not in _ELEMENTS:
        raise ValueError(
            f"Unknown element '{element}'. Choose from: {', '.join(_ELEMENTS)}."
        )
    if not _is_valid_color(value):
        raise ValueError(
            f"Invalid color '{value}'. Use a color name (e.g. green) or a 0-255 code."
        )
    return element, value


class Chronos:
    R = attr("reset")

    ENTRY_WIDTH = 30  # fixed column width: city+offset (left) + gap + time (right)

    def __init__(
        self,
        show_offset: bool = True,
        time_format: str = "HH:mm:ss",
        military: bool = False,
        show_utc: bool = False,
        full_military: bool = False,
        palette: dict[str, str] | None = None,
    ) -> None:
        self.show_offset = show_offset
        self.time_format = time_format
        self.military = military
        self.show_utc = show_utc
        self.full_military = full_military
        self.palette = dict(palette) if palette else dict(_DEFAULT_THEME)
        # Rendering styles keyed the way the print methods reference them.
        self.CITY = self._style("city")
        self.OFFSET = self._style("offset")
        self.TIME = self._style("time")
        self.LOCAL_LABEL = self._style("label")
        self.LOCAL_DATE = self._style("date")
        self.LOCAL_TIME = self._style("local-time")

    def _style(self, element: str) -> str:
        """ANSI prefix for an element: its structural attribute plus color."""
        color = self.palette.get(element, _DEFAULT_THEME[element])
        prefix = attr("bold") if element in _BOLD_ELEMENTS else ""
        return prefix + fg(color)

    @staticmethod
    def _utc_string(offset_seconds: int) -> str:
        """Numeric UTC offset label, e.g. ``UTC-3`` or ``UTC+5:30``."""
        sign = "+" if offset_seconds >= 0 else "-"
        h, m = divmod(abs(offset_seconds) // 60, 60)
        return f"UTC{sign}{h}:{m:02d}" if m else f"UTC{sign}{h}"

    def _offset_label(self, offset_seconds: int) -> str:
        """Offset field: military letter, numeric UTC±N, or both.

        In military mode the letter replaces the numeric offset; ``--utc``
        shows both. Offsets with no official letter fall back to numeric.
        """
        numeric = self._utc_string(offset_seconds)
        if not self.military:
            return numeric
        letter = _military_letter(offset_seconds)
        if letter is None:
            return numeric
        return f"{letter} {numeric}" if self.show_utc else letter

    def _entry(self, tz: str) -> tuple[str, str]:
        """Return (plain, colored) for a timezone row, time right-justified."""
        city = _get_city(tz)
        t = now(tz)
        if self.full_military:
            time_group, calendar = _dtg_parts(t)
            right_part = f"{time_group} {calendar}"
            gap = " " * (self.ENTRY_WIDTH - len(city) - len(right_part))
            plain = f"{city}{gap}{right_part}"
            colored = (
                f"{self.CITY}{city}{self.R}"
                f"{gap}"
                f"{self.TIME}{time_group}{self.R} "
                f"{self.OFFSET}{calendar}{self.R}"
            )
            return plain, colored
        time_str = t.format(self.time_format)
        if self.show_offset:
            offset_display = f"{self._offset_label(t.offset):<6}"
            right_part = f"{offset_display} {time_str}"
        else:
            right_part = time_str
        gap = " " * (self.ENTRY_WIDTH - len(city) - len(right_part))
        plain = f"{city}{gap}{right_part}"
        if self.show_offset:
            colored = (
                f"{self.CITY}{city}{self.R}"
                f"{gap}"
                f"{self.OFFSET}{offset_display}{self.R} "
                f"{self.TIME}{time_str}{self.R}"
            )
        else:
            colored = (
                f"{self.CITY}{city}{self.R}"
                f"{gap}"
                f"{self.TIME}{time_str}{self.R}"
            )
        return plain, colored

    def print_time_screen(self, timezones: list[str]) -> None:
        """Display the world clock. Press Ctrl+C to exit."""
        half = len(timezones) // 2
        first_run = True
        try:
            while True:
                if first_run:
                    sys.stdout.write("\033[3J\033[2J\033[H")  # clear scrollback + screen on start
                    first_run = False
                else:
                    sys.stdout.write("\033[H")  # move to home, no clear = no flicker

                local = now()
                local_tz = _get_city(local.tzinfo.name)
                if self.full_military:
                    # Juliet (J) is the military designator for local time.
                    time_group, calendar = _dtg_parts(local, letter="J")
                    header = (
                        f"{self.LOCAL_LABEL}LOCAL [{local_tz}]:{self.R} "
                        f"{self.LOCAL_TIME}{time_group}{self.R} "
                        f"{self.LOCAL_DATE}{calendar}{self.R}"
                    )
                else:
                    local_date = local.format("YYYY-MM-DD")
                    local_time = local.format(self.time_format)
                    header = (
                        f"{self.LOCAL_LABEL}LOCAL [{local_tz}]:{self.R} "
                        f"{self.LOCAL_DATE}{local_date}{self.R} "
                        f"{self.LOCAL_TIME}{local_time}{self.R}"
                    )
                sys.stdout.write(f"{header}\033[K\n")

                # Build columns as (plain, colored) pairs for correct padding
                left:  list[tuple[str, str]] = []
                right: list[tuple[str, str]] = []
                for i, tz in enumerate(timezones):
                    (right if i >= half else left).append(self._entry(tz))

                for row in range(max(len(left), len(right))):
                    lp, lc = left[row]  if row < len(left)  else ("", "")
                    rp, rc = right[row] if row < len(right) else ("", "")
                    pad = self.ENTRY_WIDTH - len(lp) + 3
                    sys.stdout.write(f"{lc}{' ' * pad}{rc}\033[K\n")

                sys.stdout.flush()
                sleep(1)
        except KeyboardInterrupt:
            pass


app = typer.Typer(help="World clock for the terminal.")


def _version_callback(value: bool) -> None:
    if value:
        # Imported lazily: at top level it would be a circular import, since
        # the package __init__ imports this module before defining __version__.
        from worldclock_tty import __version__

        typer.echo(f"worldclock-tty {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def run(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
    sort: bool = typer.Option(True, "--sort/--no-sort", help="Sort timezones by UTC offset."),
    show_offset: bool = typer.Option(True, "--offset/--no-offset", help="Show UTC offset alongside times."),
    hour12: bool = typer.Option(False, "--12h/--24h", help="Use a 12-hour clock with AM/PM."),
    military: bool = typer.Option(
        False,
        "--military/--no-military",
        "--zulu/--no-zulu",
        help="Show NATO/military zone letters (Z, N, ...) instead of UTC±N.",
    ),
    show_utc: bool = typer.Option(
        False,
        "--utc",
        help="With --military, also show the numeric UTC offset next to the letter.",
    ),
    full_military: bool = typer.Option(
        False,
        "--full-military/--no-full-military",
        "--dtg/--no-dtg",
        help="Full military Date-Time Group, e.g. 041430Z JUL 26 (overrides time/offset flags).",
    ),
    theme: str | None = typer.Option(
        None,
        "--theme",
        help="Color theme for this run: default, mono, matrix, amber, ocean. Overrides the saved theme.",
    ),
    color: list[str] = typer.Option(
        [],
        "--color",
        help="Per-element color override, e.g. --color city=green (repeatable). Elements: "
        + ", ".join(_ELEMENTS) + ".",
    ),
) -> None:
    """Display the world clock."""
    if ctx.invoked_subcommand is None:
        timezones = _load_config()
        if sort:
            timezones = sorted(timezones, key=lambda tz: now(tz).offset)
        time_format = "hh:mm:ss A" if hour12 else "HH:mm:ss"

        theme_name = theme or _load_theme_name() or "default"
        palette = _theme_palette(theme_name)
        if palette is None:
            typer.echo(
                f"Unknown theme '{theme_name}'; using 'default'. "
                "See 'worldclock-tty theme list'.",
                err=True,
            )
            palette = _theme_palette("default")
        for spec in color:
            try:
                element, value = _parse_color_override(spec)
            except ValueError as exc:
                typer.echo(str(exc), err=True)
                raise typer.Exit(1) from exc
            palette[element] = value

        Chronos(
            show_offset=show_offset,
            time_format=time_format,
            military=military,
            show_utc=show_utc,
            full_military=full_military,
            palette=palette,
        ).print_time_screen(timezones)


@app.command()
def add(timezone: str = typer.Argument(help="Timezone to add, e.g. America/Chicago")) -> None:
    """Add a timezone to the clock."""
    if not _is_valid_timezone(timezone):
        typer.echo(
            f"'{timezone}' is not a valid IANA timezone name "
            "(e.g. America/Chicago, Europe/Paris).",
            err=True,
        )
        raise typer.Exit(1)
    timezones = _load_config()
    if timezone in timezones:
        typer.echo(f"'{timezone}' is already in the list.", err=True)
        raise typer.Exit(1)
    timezones.append(timezone)
    _save_config(timezones)
    typer.echo(f"Added '{timezone}'.")


@app.command()
def remove(timezone: str = typer.Argument(help="Timezone to remove")) -> None:
    """Remove a timezone from the clock."""
    timezones = _load_config()
    if timezone not in timezones:
        typer.echo(f"'{timezone}' not found.", err=True)
        raise typer.Exit(1)
    timezones.remove(timezone)
    _save_config(timezones)
    typer.echo(f"Removed '{timezone}'.")


@app.command(name="list")
def list_zones() -> None:
    """List configured timezones."""
    for tz in _load_config():
        typer.echo(tz)


@app.command()
def reset() -> None:
    """Reset timezones to the built-in defaults."""
    _save_config(DEFAULT_TIMEZONES)
    typer.echo("Reset to defaults.")


theme_app = typer.Typer(help="Manage the saved color theme.")
app.add_typer(theme_app, name="theme")


@theme_app.command("set")
def theme_set(name: str = typer.Argument(help="Theme name, e.g. matrix")) -> None:
    """Save a color theme as the default."""
    if name not in THEMES:
        typer.echo(
            f"Unknown theme '{name}'. Available: {', '.join(THEMES)}.",
            err=True,
        )
        raise typer.Exit(1)
    _save_theme_name(name)
    typer.echo(f"Theme set to '{name}'.")


@theme_app.command("list")
def theme_list() -> None:
    """List available themes; the saved one is marked."""
    current = _load_theme_name() or "default"
    for name in THEMES:
        marker = "  (saved)" if name == current else ""
        typer.echo(f"{name}{marker}")


@theme_app.command("reset")
def theme_reset() -> None:
    """Clear the saved theme (back to the built-in default)."""
    _save_theme_name(None)
    typer.echo("Theme reset to 'default'.")


def main() -> None:
    app()
