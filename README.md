# worldclock-tty

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

```
worldclock-tty --no-sort          # keep the order from config
worldclock-tty --no-offset        # hide UTC offset labels
worldclock-tty --no-sort --no-offset
```

## Managing timezones

Timezones are stored in `~/.config/chronos/config.json`. Use IANA timezone names (e.g. `America/Chicago`, `Europe/Paris`).

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
