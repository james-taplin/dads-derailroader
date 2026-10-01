"""Where the app keeps its own files: a portable `rr2dv_work` folder beside the app, never a hidden system folder.

Frozen Windows app: next to the exe. Source run: the repository folder. `RR2DV_HOME` overrides (tests, odd setups).
Holds `machine.json` (settings), `runs/` (work and finished runs) and `logs/`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

FOLDER = "rr2dv_work"


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    override = os.environ.get("RR2DV_HOME")
    return Path(override) if override else app_root() / FOLDER
