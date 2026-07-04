from importlib.metadata import PackageNotFoundError, version

from worldclock_tty.chronos import Chronos

try:
    __version__ = version("worldclock-tty")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0"

__all__ = ["Chronos"]
