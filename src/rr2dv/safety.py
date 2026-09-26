"""Path guards and safe archive extraction. Every write the app makes goes through these checks."""
from __future__ import annotations

import os
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterable

MAX_ZIP_ENTRIES = 200_000
MAX_ZIP_BYTES = 64 * 1024**3  # uncompressed ceiling; a Railroader mod is far smaller
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


def safe_extract_zip(archive: Path, dest: Path) -> list[Path]:
    """Extract into a new, empty folder. Rejects absolute paths, '..', drive letters, links, duplicate
    names that differ only in case, and archives that would expand past MAX_ZIP_BYTES."""
    if dest.exists() and any(dest.iterdir()):
        raise UnsafePath(f"extraction folder is not empty: {dest}")
    written = []
    with zipfile.ZipFile(archive) as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            raise UnsafePath(f"{archive.name}: too many entries ({len(infos)})")
        if sum(i.file_size for i in infos) > MAX_ZIP_BYTES:
            raise UnsafePath(f"{archive.name}: expands past {MAX_ZIP_BYTES} bytes")
        seen: set[str] = set()
        plan = []
        for info in infos:
            name = info.filename.replace("\\", "/")
            parts = PurePosixPath(name).parts
            if not parts or name.startswith("/") or any(_bad_part(p) for p in parts):
                raise UnsafePath(f"{archive.name}: unsafe entry name {info.filename!r}")
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise UnsafePath(f"{archive.name}: link entries are not allowed ({info.filename!r})")
            key = name.rstrip("/").casefold()
            if key in seen:
                raise UnsafePath(f"{archive.name}: duplicate entry {info.filename!r}")
            seen.add(key)
            plan.append((info, dest.joinpath(*parts)))
        dest.mkdir(parents=True, exist_ok=True)
        root = dest.resolve()
        for info, target in plan:
            if not target.resolve().is_relative_to(root):
                raise UnsafePath(f"{archive.name}: entry escapes the extraction folder ({info.filename!r})")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "xb") as out:
                for chunk in iter(lambda: src.read(1 << 20), b""):
                    out.write(chunk)
            written.append(target)
    return written
