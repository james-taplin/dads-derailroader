"""Finding the Railroader and Derail Valley installs (W25).

rr2dv converts a mod from the user's own Railroader Mods folder and installs the result into their own Derail Valley
Mods folder, so both installs must be found before anything runs: when checking the machine (`rr2dv doctor`), when a
conversion starts, and again just before installing. The settings file wins (`railroader`, `game`, `mods`); otherwise
the Steam libraries are searched (Steam's registry entry or default folder, then steamapps/libraryfolders.vdf).
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

RAILROADER = ("Railroader", "Railroader_Data")
DERAIL_VALLEY = ("Derail Valley", "DerailValley_Data")
CCL_MOD_ID = "DVCustomCarLoader"
DEFAULT_STEAM = (Path("C:/Program Files (x86)/Steam"), Path("C:/Program Files/Steam"))


class InstallError(RuntimeError):
    """A required game install or its Mods folder was not found."""


@dataclass(frozen=True)
class Install:
    game: str
    root: Path
    mods: Path
    source: str  # "settings" or "steam"

    def describe(self) -> dict:
        return {"game": self.game, "root": str(self.root), "mods": str(self.mods), "source": self.source}

    @property
    def asset_packs(self) -> Path:
        """Railroader's base-game asset packs: each locomotive pack is a folder here with Catalog.json, Definitions.json
        and its bundle (e.g. ls-282-k28t)."""
        return self.root / "Railroader_Data" / "StreamingAssets" / "AssetPacks"


def steam_roots(machine) -> list[Path]:
    """Steam install folders: settings `steamRoots`, then the registry (Windows), then the default locations."""
    listed = machine.values.get("steamRoots") or []
    roots = [Path(p) for p in ([listed] if isinstance(listed, str) else listed) if isinstance(p, str) and p.strip()]
    if sys.platform == "win32" and not machine.values.get("steamRoots"):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                roots.append(Path(winreg.QueryValueEx(key, "SteamPath")[0]))
        except OSError:
            pass
        roots += list(DEFAULT_STEAM)
    unique = []
    for r in roots:
        if r not in unique:
            unique.append(r)
    return unique


def steam_libraries(steam_root: Path) -> list[Path]:
    """The Steam root plus every library listed in steamapps/libraryfolders.vdf ("path" entries)."""
    libraries = [steam_root]
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    try:
        text = vdf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return libraries
    for raw in re.findall(r'"path"\s+"([^"]+)"', text):
        p = Path(raw.replace("\\\\", "\\"))
        if p not in libraries:
            libraries.append(p)
    return libraries


def _valid(root: Path, data_folder: str) -> bool:
    return (root / data_folder).is_dir()


def _find(machine, game: tuple[str, str], root_key: str, mods_key: str | None) -> Install:
    name, data = game
    configured = machine.path(root_key)
    if configured is not None:
        if not _valid(configured, data):
            raise InstallError(f"{name} not found at {configured} (no {data} folder); fix `{root_key}` in the settings file")
        root, source = configured, "settings"
    else:
        hits = []
        for steam in steam_roots(machine):
            for library in steam_libraries(steam):
                candidate = library / "steamapps" / "common" / name
                if _valid(candidate, data) and candidate not in hits:
                    hits.append(candidate)
        if not hits:
            raise InstallError(f"{name} was not found in any Steam library; set `{root_key}` in the settings file to its install folder")
        if len(hits) > 1:
            raise InstallError(f"{name} is installed in several Steam libraries ({', '.join(map(str, hits))}); "
                               f"set `{root_key}` in the settings file to the one to use")
        root, source = hits[0], "steam"
    mods = (machine.path(mods_key) if mods_key else None) or root / "Mods"
    if not mods.is_dir():
        raise InstallError(f"{name} has no Mods folder at {mods}" +
                           ("; install Unity Mod Manager and Custom Car Loader first" if name == DERAIL_VALLEY[0] else ""))
    return Install(name, root, mods, source)


def railroader(machine) -> Install:
    return _find(machine, RAILROADER, "railroader", None)


def derail_valley(machine) -> Install:
    return _find(machine, DERAIL_VALLEY, "game", "mods")


def ccl_installed(dv: Install) -> bool:
    """Custom Car Loader is a Unity Mod Manager mod: a Mods/<folder>/Info.json whose Id is DVCustomCarLoader."""
    for info in dv.mods.glob("*/Info.json"):
        try:
            if re.search(r'"Id"\s*:\s*"' + CCL_MOD_ID + '"', info.read_text(encoding="utf-8-sig", errors="replace")):
                return True
        except OSError:
            continue
    return False


def mod_in_railroader(rr: Install, given: str | os.PathLike) -> Path:
    """The input: a folder directly inside the Railroader Mods folder, or (0.3, James) a base-game asset pack directly in
    Railroader_Data/StreamingAssets/AssetPacks, by name or by path (W25: no zips, nothing from elsewhere). A bare name is
    looked up in Mods first. A link or junction placed in either folder counts as being in it. Both are only read."""
    text = str(given)
    candidate = Path(text)
    if not candidate.is_absolute() and len(candidate.parts) == 1:
        candidate = rr.mods / text if (rr.mods / text).is_dir() or not (rr.asset_packs / text).is_dir() else rr.asset_packs / text
    candidate = Path(os.path.abspath(candidate))
    parents = {Path(os.path.realpath(rr.mods)), Path(os.path.realpath(rr.asset_packs))}
    if Path(os.path.realpath(candidate.parent)) not in parents:
        raise InstallError(f"{given} is not a mod folder in the Railroader Mods folder ({rr.mods}) or a base-game asset pack "
                           f"in {rr.asset_packs}; rr2dv converts only those (give the folder name, e.g. \"Some Loco Mod\")")
    if not candidate.is_dir():
        raise InstallError(f"{candidate} is not a folder; rr2dv converts a mod folder from {rr.mods}, not an archive")
    return candidate


def is_base_game(rr: Install, folder: Path) -> bool:
    return Path(os.path.realpath(Path(folder).parent)) == Path(os.path.realpath(rr.asset_packs))
