"""Path guards. Every write the app makes goes through these checks."""
from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Iterable

# Names Windows treats as devices, whatever the extension ("CON.txt" opens the console).
_WINDOWS_DEVICES = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10))}


def _bad_part(part: str) -> bool:
    return (part in ("", ".", "..") or any(c in part for c in ':*?"<>|\0') or part != part.rstrip(" .")
            or part.split(".")[0].casefold() in _WINDOWS_DEVICES)


class UnsafePath(ValueError):
    """A requested write would land somewhere the app must not touch."""


def is_within(path: Path, root: Path) -> bool:
    return path.resolve() == root.resolve() or path.resolve().is_relative_to(root.resolve())


def is_link(path: Path) -> bool:
    """True for symlinks and Windows junctions."""
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)  # Python 3.12+
    if is_junction and is_junction():
        return True
    try:
        attrs = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def check_write_target(target: Path, protected: Iterable[tuple[str, Path]]) -> None:
    """Refuse a write target inside (or equal to) any protected folder, e.g. the input mod or the game."""
    for label, root in protected:
        if root and is_within(target, root):
            raise UnsafePath(f"refusing to write inside the {label} ({root}): {target}")
