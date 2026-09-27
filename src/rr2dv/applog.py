"""The app-wide log: `%LOCALAPPDATA%\\rr2dv\\logs\\rr2dv.log` (or `$RR2DV_LOG_DIR`), rotated at 1 MB, 5 files kept.

Each conversion also writes its own `run.log` in its run folder (runs.py); this log holds what happens outside a run:
commands started, games found or not, mods listed and scanned, and every unexpected error with its full traceback,
from the command line and the desktop app alike. Logging must never stop the app: if the folder cannot be written,
nothing is logged.
"""
from __future__ import annotations

import logging
import os
import platform
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import __version__

_logger: logging.Logger | None = None


def app_revision() -> str:
    """The app's version, plus the git commit when it runs from a clone of our repository (X37: tells results apart
    across quick updates). Read from .git directly, so git itself is not needed."""
    root = Path(__file__).resolve().parents[2] / ".git"
    try:
        head = (root / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref: "):
            ref = head[5:]
            ref_file = root / ref
            if ref_file.is_file():
                commit = ref_file.read_text(encoding="utf-8").strip()
            else:
                packed = (root / "packed-refs").read_text(encoding="utf-8")
                commit = next(line.split()[0] for line in packed.splitlines() if line.endswith(" " + ref))
            return f"{__version__} ({ref.rsplit('/', 1)[-1]} {commit[:10]})"
        return f"{__version__} ({head[:10]})"
    except (OSError, StopIteration):
        return __version__


def log_dir() -> Path:
    override = os.environ.get("RR2DV_LOG_DIR")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / ".local" / "share") / "rr2dv" / "logs"


def log_file() -> Path:
    return log_dir() / "rr2dv.log"


def get() -> logging.Logger:
    global _logger
    if _logger is None:
        _logger = logging.getLogger("rr2dv")
        _logger.setLevel(logging.INFO)
        _logger.propagate = False
        try:
            log_dir().mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(log_file(), maxBytes=1_000_000, backupCount=5, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
            _logger.addHandler(handler)
            _logger.info("rr2dv %s, Python %s, %s", app_revision(), sys.version.split()[0], platform.platform())
        except OSError:
            _logger.addHandler(logging.NullHandler())
    return _logger


def reset() -> None:
    """Close the log file (tests switch RR2DV_LOG_DIR between cases)."""
    global _logger
    if _logger is not None:
        for handler in list(_logger.handlers):
            handler.close()
            _logger.removeHandler(handler)
    _logger = None
