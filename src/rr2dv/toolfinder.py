"""Bounded discovery of the four external tools needed for a conversion."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections import deque
from pathlib import Path
from typing import Mapping, Sequence

from .machine import CARCREATOR_VERSION, MIN_TOOL_PYTHON, UNITY_VERSION, Machine

REQUIRED = ("unity", "carCreator", "assetRipper", "python")
SKIP_DIRS = {".git", "node_modules", "library", "temp", "logs", "_cache", "runs", "__pycache__"}


def _python_works(path: Path) -> bool:
    if path.name.casefold() != "python.exe" and sys.platform == "win32":
        return False
    try:
        result = subprocess.run([str(path), "-c", "import sys; print(*sys.version_info[:2])"],
                                capture_output=True, text=True, timeout=5)
        return result.returncode == 0 and tuple(map(int, result.stdout.split())) >= MIN_TOOL_PYTHON
    except (OSError, subprocess.SubprocessError, ValueError):
        return False


def _matches(key: str, path: Path) -> bool:
    if not path.is_file():
        return False
    name = path.name.casefold()
    if key == "unity":
        return name == "unity.exe" and UNITY_VERSION in str(path)
    if key == "carCreator":
        return name.endswith(".unitypackage") and "carcreator" in name and CARCREATOR_VERSION in name
    if key == "assetRipper":
        return name.startswith("assetripper") and name.endswith(".exe")
    return key == "python" and _python_works(path)


def _files(root: Path, depth_limit: int = 6, directory_limit: int = 2500):
    """Walk likely install folders without following links or scanning entire game libraries."""
    pending = deque([(root, 0)])
    visited = 0
    while pending and visited < directory_limit:
        folder, depth = pending.popleft()
        try:
            with os.scandir(folder) as scan:
                entries = sorted(scan, key=lambda entry: entry.name.casefold())
        except OSError:
            continue
        visited += 1
        for entry in entries:
            try:
                if entry.is_file(follow_symlinks=False):
                    yield Path(entry.path)
                elif (depth < depth_limit and entry.is_dir(follow_symlinks=False)
                      and entry.name.casefold() not in SKIP_DIRS
                      and not entry.name.casefold().startswith((".venv", "venv"))):
                    pending.append((Path(entry.path), depth + 1))
            except OSError:
                continue


def _roots(machine: Machine) -> list[Path]:
    home = Path.home()
    roots = [home / "Desktop" / "Derail Valley Mods", home / "Downloads", home / "Desktop", home / "Documents"]
    for name in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        if os.environ.get(name):
            roots.append(Path(os.environ[name]) / "Unity")
            roots.append(Path(os.environ[name]) / "Unity Hub")
            roots.extend(Path(os.environ[name]).glob("Python*"))
    if os.environ.get("LOCALAPPDATA"):
        local = Path(os.environ["LOCALAPPDATA"])
        roots.extend((local / "Programs" / "Python", local / "Python", local / "Programs" / "Unity Hub"))
    paths = [Path.cwd(), home, machine.work_root]
    paths.extend(path for key in ("game", "railroader") if (path := machine.path(key)))
    anchors = {path.anchor for path in paths if path.anchor}
    roots.extend(Path(anchor) / "Games" for anchor in sorted(anchors))
    roots.extend(Path(anchor) / "Unity" for anchor in sorted(anchors))
    roots.extend(Path(anchor) / "Tools" for anchor in sorted(anchors))
    roots.extend(Path(anchor) / "Apps" for anchor in sorted(anchors))
    return list(dict.fromkeys(root for root in roots if root.is_dir()))


def discover(machine: Machine, entered: Mapping[str, str], *, search_roots: Sequence[Path] | None = None) -> dict[str, str]:
    """Find missing/nonexistent tool paths. Existing files entered by the user are never replaced."""
    required = REQUIRED[:-1] if getattr(sys, "frozen", False) else REQUIRED
    missing = {key for key in required if not (entered.get(key) and Path(entered[key]).is_file())}
    found: dict[str, str] = {}
    if not missing:
        return found

    def take(key: str, candidate: Path | None) -> None:
        if key in missing and candidate and _matches(key, candidate):
            found[key] = str(candidate)
            missing.remove(key)

    for key in tuple(missing):
        take(key, machine.path(key))

    if "python" in missing:
        executable = Path(sys.executable)
        take("python", executable if not getattr(sys, "frozen", False) else None)
        take("python", executable.with_name("python.exe") if not getattr(sys, "frozen", False) else None)
        if shutil.which("python"):
            take("python", Path(shutil.which("python")))
        take("python", Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime"
             / "dependencies" / "python" / "python.exe")
        if os.environ.get("LOCALAPPDATA"):
            local = Path(os.environ["LOCALAPPDATA"])
            for root in (local / "Programs" / "Python", local / "Python"):
                for candidate in sorted(root.glob("*/python.exe")):
                    take("python", candidate)
                    if "python" not in missing:
                        break

    if "unity" in missing:
        for name in ("UNITY_EDITOR_PATH", "UNITY_PATH"):
            if os.environ.get(name):
                take("unity", Path(os.environ[name]))
        for name in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
            if os.environ.get(name):
                take("unity", Path(os.environ[name]) / "Unity" / "Hub" / "Editor" / UNITY_VERSION / "Editor" / "Unity.exe")

    if "assetRipper" in missing:
        for name in ("AssetRipper.GUI.Free.exe", "AssetRipper.GUI.exe", "AssetRipper.exe"):
            if shutil.which(name):
                take("assetRipper", Path(shutil.which(name)))

    roots = list(search_roots) if search_roots is not None else _roots(machine)
    for root in roots:
        if not missing:
            break
        for file in _files(root):
            name = file.name.casefold()
            if "unity" in missing and name == "unity.exe":
                take("unity", file)
            elif "carCreator" in missing and name.endswith(".unitypackage") and "carcreator" in name:
                take("carCreator", file)
            elif "assetRipper" in missing and name.startswith("assetripper") and name.endswith(".exe"):
                take("assetRipper", file)
            elif "python" in missing and name == "python.exe":
                take("python", file)
            if not missing:
                break
    return found
