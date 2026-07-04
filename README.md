# worldclock-tty

[![CI](https://github.com/carlosplanchon/worldclock-tty/actions/workflows/ci.yml/badge.svg)](https://github.com/carlosplanchon/worldclock-tty/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/worldclock-tty.svg)](https://pypi.org/project/worldclock-tty/)
[![Python versions](https://img.shields.io/pypi/pyversions/worldclock-tty.svg)](https://pypi.org/project/worldclock-tty/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/carlosplanchon/worldclock-tty)

A terminal-based world clock that displays multiple timezones in real-time.

![worldclock-tty screenshot](https://raw.githubusercontent.com/carlosplanchon/worldclock-tty/refs/heads/main/worldclock_tty/assets/screenshot.png)

This program is a heavy refactor of a timezone clock I made in 2016.

## Installation
```bash
uv tool install worldclock-tty
```

## Usage

Run the clock:

```
worldclock-tty
```

Press `Ctrl+C` to exit.

The display shows your local time at the top, followed by all configured timezones in two columns, updated every second.

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--sort` / `--no-sort` | on | Sort timezones by UTC offset (lowest first). |
| `--offset` / `--no-offset` | on | Show the UTC offset (e.g. `UTC-3`) next to each time. |
| `--12h` / `--24h` | `--24h` | Use a 12-hour clock with AM/PM instead of 24-hour. |
| `--military` / `--no-military` | off | Show NATO/military zone letters (`Z`, `N`, `P`, …) instead of `UTC±N`. Alias: `--zulu`. |
| `--utc` | off | With `--military`, also show the numeric offset next to the letter. |
| `--full-military` / `--no-full-military` | off | Show a full military Date-Time Group (e.g. `041430Z JUL 26`). Alias: `--dtg`. |
| `--theme` | saved or `default` | Color theme for this run: `default`, `mono`, `matrix`, `amber`, `ocean`. |
| `--color` | (none) | Per-element color override, e.g. `--color city=green` (repeatable). |

```
worldclock-tty --no-sort          # keep the order from config
worldclock-tty --no-offset        # hide UTC offset labels
worldclock-tty --12h              # 12-hour clock with AM/PM
worldclock-tty --military         # Zulu/November letters instead of UTC±N
worldclock-tty --military --utc   # letters and the numeric offset (e.g. P UTC-3)
worldclock-tty --full-military    # DTG format: 041430Z JUL 26
worldclock-tty --theme matrix     # use a color theme for this run
worldclock-tty --color time=green --color city=45   # tweak individual colors
worldclock-tty --no-sort --no-offset
```

Military zone letters map each whole-hour UTC offset to a letter: `Z` is UTC+0,
`A`…`M` run east (skipping `J`, reserved for local time), and `N`…`Y` run west.
Offsets with no official designator (half-hour zones like India at `UTC+5:30`,
or anything beyond ±12h) fall back to the numeric `UTC±N`.

`--full-military` (`--dtg`) replaces each time with a **Date-Time Group**:
`DDHHMM` + zone letter + `MON YY`, e.g. `041430Z JUL 26` (day 04, 14:30, Zulu,
July 2026). It is minute-precision and always 24-hour, so it overrides the
offset and `--12h` flags. The `LOCAL` header uses `J` (Juliet), the military
designator for local time; zones with no official letter use `*`.

## Colors and themes

Every element on screen is colorable: `city`, `offset`, `time` (the world-clock
rows) and `label`, `date`, `local-time` (the `LOCAL` header). Colors are given
as a **name** (e.g. `green`, `cornflower_blue`) or a **256-color code** (`0`–`255`).

Pick a built-in **theme** for a run, or override individual elements with
`--color` (repeatable). Precedence, lowest to highest: `default`, the saved
theme, `--theme`, then `--color`.

```
worldclock-tty --theme ocean
worldclock-tty --theme matrix --color time=196     # theme, then tweak one element
worldclock-tty --color label=cyan --color city=45  # override on the default theme
```

Save a theme as your default. That is the **only** thing persisted in the config;
per-run `--color` tweaks are never saved:

```
worldclock-tty theme set matrix    # persist as the default
worldclock-tty theme list          # list themes; the saved one is marked
worldclock-tty theme reset         # back to the built-in default
```

Built-in themes: `default`, `mono`, `matrix`, `amber`, `ocean`.

## Managing timezones

Timezones are stored in `$XDG_CONFIG_HOME/worldclock-tty/config.json` (defaults to `~/.config/worldclock-tty/config.json`). Use IANA timezone names (e.g. `America/Chicago`, `Europe/Paris`).

```
worldclock-tty add America/Chicago       # add a timezone
worldclock-tty remove America/Chicago    # remove a timezone
worldclock-tty list                      # show configured timezones
worldclock-tty reset                     # restore built-in defaults
```

### Default timezones

America/Buenos\_Aires, America/Caracas, America/La\_Paz, America/Lima, America/Los\_Angeles, America/Montevideo, America/New\_York, America/Sao\_Paulo, Asia/Bangkok, Asia/Dubai, Asia/Hong\_Kong, Asia/Istanbul, Asia/Tokyo, Asia/Vladivostok, Atlantic/Bermuda, Atlantic/Canary, Australia/Sydney, Europe/London, Europe/Madrid, Europe/Moscow, Europe/Rome, Pacific/Honolulu.

## Requirements

Python 3.10+

## License

MIT
