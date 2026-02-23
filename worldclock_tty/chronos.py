#!/usr/bin/env python3

import json
import sys
from pathlib import Path
from time import sleep

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

CONFIG_PATH = Path.home() / ".config" / "chronos" / "config.json"


def _get_city(tz: str) -> str:
    """Extract a display name from a timezone string.

    Handles plain zones (UTC), two-part zones (US/Eastern),
    and standard IANA zones (America/Buenos_Aires).
    """
    return tz.split("/")[-1].replace("_", " ")


def _load_config() -> list[str]:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())["timezones"]
    return list(DEFAULT_TIMEZONES)


def _save_config(timezones: list[str]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({"timezones": timezones}, indent=2))


class Chronos:
    R = attr("reset")

    # Local header
    LOCAL_LABEL = attr("bold") + fg(11)   # bold yellow
    LOCAL_DATE  = fg(244)                  # dim gray
    LOCAL_TIME  = attr("bold") + fg(255)   # bold white

    # World clock entries
    CITY  = fg(75)   # cornflower blue
    SEP   = fg(238)  # dark gray
    TIME  = fg(255)  # white

    def _entry(self, tz: str) -> tuple[str, str]:
        """Return (plain, colored) for a timezone row."""
        city = _get_city(tz)
        time_str = now(tz).format("HH:mm:ss")
        plain   = f"{city}: {time_str}"
        colored = f"{self.CITY}{city}{self.R}{self.SEP}:{self.R} {self.TIME}{time_str}{self.R}"
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
                local_time = local.format("HH:mm:ss")
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
                    pad = 25 - len(lp)
                    sys.stdout.write(f"{lc}{' ' * pad} {rc}\033[K\n")

                sys.stdout.flush()
                sleep(1)
        except KeyboardInterrupt:
            pass


app = typer.Typer(help="World clock for the terminal.")


@app.callback(invoke_without_command=True)
def run(ctx: typer.Context) -> None:
    """Display the world clock."""
    if ctx.invoked_subcommand is None:
        Chronos().print_time_screen(_load_config())


@app.command()
def add(timezone: str = typer.Argument(help="Timezone to add, e.g. America/Chicago")) -> None:
    """Add a timezone to the clock."""
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
