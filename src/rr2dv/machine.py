"""Per-machine settings (tool locations) and the `doctor` preflight check.

Keys match tooling/machine.local.example.json, so an existing LLW machine.local.json loads unchanged. The app adds
`workRoot` (where run folders go) and `searchRoots` (extra folders to look in for dependencies).
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .jsonio import read_json

TOOL_KEYS = ("python", "unity", "unityPySitePackages", "carCreator", "mods", "game", "ilspy", "assetRipper", "railroader")
UNITY_VERSION = "2019.4.40f1"
CARCREATOR_VERSION = "3.1.9"
MIN_TOOL_PYTHON = (3, 11)
# Unity 2019.4 cannot open files whose full path passes Windows' 260-character limit (board X28: two uGUI package
# test files failed under a 92-character work folder). Longest path we know of inside a generated project:
LONGEST_PROJECT_PATH = "Library/PackageCache/com.unity.ugui@1.0.0/Tests/Editor/Canvas/CanvasElementsMaintainValidPositionsWhenCameraOrthoSizeIsZero.cs"
WINDOWS_MAX_PATH = 259  # MAX_PATH 260 including the terminating null


def max_work_root_length() -> int:
    from .runs import RUN_ID_MAX
    return WINDOWS_MAX_PATH - len(LONGEST_PROJECT_PATH) - len("/unity/project/") - RUN_ID_MAX


def check_work_root(path: Path) -> None:
    """Refuse a work folder too long for the Unity projects built inside it."""
    real = os.path.realpath(path)
    if len(real) > max_work_root_length():
        raise ValueError(f"the work folder path is {len(real)} characters ({real}); Unity 2019.4 needs it to be at most "
                         f"{max_work_root_length()}. Set a short `workRoot` in the settings file, e.g. C:\\rr2dv")


def default_path() -> Path:
    base = os.environ.get("APPDATA")
    return (Path(base) if base else Path.home() / ".config") / "rr2dv" / "machine.json"


def default_work_root() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / ".local" / "share") / "rr2dv" / "runs"


@dataclass
class Machine:
    source: Path | None
    values: dict

    def path(self, key: str) -> Path | None:
        value = self.values.get(key)
        return Path(value) if isinstance(value, str) and value.strip() else None

    @property
    def work_root(self) -> Path:
        return self.path("workRoot") or default_work_root()

    def search_roots(self) -> list[Path]:
        """Explicit searchRoots first, then the Railroader Mods folder and base-game asset packs."""
        listed = self.values.get("searchRoots", [])
        if isinstance(listed, str):
            listed = [listed]
        roots = [Path(p) for p in listed if isinstance(p, str) and p.strip()] if isinstance(listed, list) else []
        rr = self.path("railroader")
        if rr:
            roots += [rr / "Mods", rr / "Railroader_Data" / "StreamingAssets" / "AssetPacks"]
        unique = []
        for r in roots:
            if r not in unique:
                unique.append(r)
        return unique

    def protected(self) -> list[tuple[str, Path]]:
        """Folders the app must never write into without an explicit, separate install step."""
        out = []
        for key, label in (("mods", "Derail Valley Mods folder"), ("game", "Derail Valley install"), ("railroader", "Railroader install")):
            p = self.path(key)
            if p:
                out.append((label, p))
        return out


def load(path: Path | None = None) -> Machine:
    path = path or default_path()
    if not path.exists():
        return Machine(None, {})
    values = read_json(path)
    if not isinstance(values, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return Machine(path, values)


@dataclass
class Check:
    status: str  # ok | warn | fail | skip
    name: str
    detail: str


def _exists(machine: Machine, key: str, kind: str, required: bool, name: str) -> tuple[Check, Path | None]:
    p = machine.path(key)
    if p is None:
        return Check("fail" if required else "skip", name, f"`{key}` not set"), None
    ok = p.is_file() if kind == "file" else p.is_dir()
    if not ok:
        return Check("fail" if required else "warn", name, f"{kind} not found: {p}"), None
    return Check("ok", name, str(p)), p


def doctor(machine: Machine) -> list[Check]:
    checks = [Check("ok" if machine.source else "warn", "settings file",
                    str(machine.source) if machine.source else f"none found; expected at {default_path()}")]

    check, py = _exists(machine, "python", "file", True, "tooling Python")
    if py:
        try:
            out = subprocess.run([str(py), "-c", "import sys;print('%d.%d.%d' % sys.version_info[:3])"],
                                 capture_output=True, text=True, timeout=60, check=True).stdout.strip()
            version = tuple(int(x) for x in out.split("."))
            check = Check("ok" if version[:2] >= MIN_TOOL_PYTHON else "fail", "tooling Python", f"{py} ({out})")
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            check = Check("fail", "tooling Python", f"{py} did not run: {e}")
    checks.append(check)

    check, unity = _exists(machine, "unity", "file", True, "Unity Editor")
    if unity and UNITY_VERSION not in str(unity):
        check = Check("warn", "Unity Editor", f"{unity}: path does not mention {UNITY_VERSION}; the builder needs exactly that version")
    checks.append(check)

    check, cc = _exists(machine, "carCreator", "file", True, "CarCreator package")
    if cc and CARCREATOR_VERSION not in cc.name:
        check = Check("warn", "CarCreator package", f"{cc.name}: expected CarCreator {CARCREATOR_VERSION}")
    checks.append(check)

    checks.append(_exists(machine, "assetRipper", "file", True, "AssetRipper")[0])
    checks.append(_exists(machine, "unityPySitePackages", "dir", False, "UnityPy site-packages (audits)")[0])
    checks.append(_exists(machine, "railroader", "dir", False, "Railroader install (dependency search)")[0])
    checks.append(_exists(machine, "mods", "dir", False, "Derail Valley Mods (install only)")[0])

    for root in machine.search_roots():
        checks.append(Check("ok" if root.is_dir() else "warn", "search root", str(root)))

    work = machine.work_root
    try:
        work.mkdir(parents=True, exist_ok=True)
        probe = work / f".rr2dv-write-test-{os.getpid()}"
        probe.write_bytes(b"")
        probe.unlink()
        try:
            check_work_root(work)
            checks.append(Check("ok", "work folder", str(work)))
        except ValueError as e:
            checks.append(Check("fail", "work folder", str(e)))
    except OSError as e:
        checks.append(Check("fail", "work folder", f"{work} is not writable: {e}"))

    if sys.version_info[:2] < MIN_TOOL_PYTHON:
        checks.append(Check("fail", "app Python", f"{sys.version.split()[0]}; need {MIN_TOOL_PYTHON[0]}.{MIN_TOOL_PYTHON[1]}+"))
    return checks
