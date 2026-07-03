#!/usr/bin/env python3

import json
import os
import sys
from pathlib import Path
from time import sleep
from typing import NoReturn

import typer
from colored import attr, fg
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


def _config_error(detail: object) -> NoReturn:
    typer.echo(
        f"Config file at {CONFIG_PATH} is invalid ({detail}).\n"
        "Fix it by hand or run 'worldclock-tty reset' to restore the defaults.",
        err=True,
    )
    raise typer.Exit(1)


def _load_config() -> list[str]:
    if not CONFIG_PATH.exists():
        return list(DEFAULT_TIMEZONES)
    try:
        timezones = json.loads(CONFIG_PATH.read_text())["timezones"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        _config_error(exc)
    if not isinstance(timezones, list):
        _config_error("'timezones' must be a list")
    return timezones


def _save_config(timezones: list[str]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({"timezones": timezones}, indent=2))


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


class Chronos:
    R = attr("reset")

    ENTRY_WIDTH = 30  # fixed column width: city+offset (left) + gap + time (right)

    # Local header
    LOCAL_LABEL = attr("bold") + fg(11)   # bold yellow
    LOCAL_DATE  = fg(244)                  # dim gray
    LOCAL_TIME  = attr("bold") + fg(255)   # bold white

    # World clock entries
    CITY   = fg(75)   # cornflower blue
    OFFSET = fg(240)  # medium gray
    TIME   = fg(255)  # white

    def __init__(self, show_offset: bool = True, time_format: str = "HH:mm:ss") -> None:
        self.show_offset = show_offset
        self.time_format = time_format

    def _entry(self, tz: str) -> tuple[str, str]:
        """Return (plain, colored) for a timezone row, time right-justified."""
        city = _get_city(tz)
        t = now(tz)
        time_str = t.format(self.time_format)
        if self.show_offset:
            sign = "+" if t.offset >= 0 else "-"
            h, m = divmod(abs(t.offset) // 60, 60)
            offset_str = f"UTC{sign}{h}:{m:02d}" if m else f"UTC{sign}{h}"
            offset_display = f"{offset_str:<6}"
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
                local_tz   = _get_city(local.tzinfo.name)
                local_date = local.format("YYYY-MM-DD")
                local_time = local.format(self.time_format)
                sys.stdout.write(
                    f"{self.LOCAL_LABEL}LOCAL [{local_tz}]:{self.R} "
                    f"{self.LOCAL_DATE}{local_date}{self.R} "
                    f"{self.LOCAL_TIME}{local_time}{self.R}\033[K\n"
                )

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


@app.callback(invoke_without_command=True)
def run(
    ctx: typer.Context,
    sort: bool = typer.Option(True, "--sort/--no-sort", help="Sort timezones by UTC offset."),
    show_offset: bool = typer.Option(True, "--offset/--no-offset", help="Show UTC offset alongside times."),
    hour12: bool = typer.Option(False, "--12h/--24h", help="Use a 12-hour clock with AM/PM."),
) -> None:
    """Display the world clock."""
    if ctx.invoked_subcommand is None:
        timezones = _load_config()
        if sort:
            timezones = sorted(timezones, key=lambda tz: now(tz).offset)
        time_format = "hh:mm:ss A" if hour12 else "HH:mm:ss"
        Chronos(show_offset=show_offset, time_format=time_format).print_time_screen(timezones)


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


def main() -> None:
    app()
