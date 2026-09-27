"""What the desktop app (gui.py) and the command line share: settings, the game installs, the mods to choose from,
a mod's scan report and a conversion. No widgets here, so all of it is testable without a screen."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from . import consent, installs, machine as machine_mod
from .jsonio import read_json, write_json
from .pipeline import Outcome, convert, search_roots
from .record import liveries
from .rrmod import Index, blocking, definition, inventory

# Settings the app edits, in the order its Settings dialog shows them: (key, label, kind, required).
SETTINGS = [
    ("unity", "Unity 2019.4.40f1 (Unity.exe)", "file", True),
    ("carCreator", "CarCreator 3.1.9 package (.unitypackage)", "file", True),
    ("assetRipper", "AssetRipper", "file", True),
    ("python", "Python for the builder scripts", "file", True),
    ("workRoot", "Work folder (short path, e.g. C:\\rr2dv)", "dir", False),
    ("railroader", "Railroader install (empty: find through Steam)", "dir", False),
    ("game", "Derail Valley install (empty: find through Steam)", "dir", False),
]


def scan_report(root: Path, search: Sequence[Path], hash_files: bool = False) -> dict:
    """Everything `rr2dv scan` shows for one mod: its steam locos, each one's inventory and liveries."""
    index = Index(root, search)
    locos = index.steam_locomotives(input_only=True)
    return {
        "schema": 1,
        "roots": [{"label": r.label, "path": str(r.path)} for r in index.roots],
        "packs_indexed": len(index.packs),
        "index_issues": [i.as_dict() for i in index.issues],
        "steam_locomotives": [{"id": o["identifier"], "name": (o.get("metadata") or {}).get("name"), "pack": p.describe(),
                               "liveries": [l[0] for l in liveries(definition(o))]} for p, o in locos],
        "other_locomotives": [{"id": o["identifier"], "kind": o["definition"].get("kind")} for _, o in index.other_locomotives()],
        "inventories": {o["identifier"]: inventory(index, o["identifier"], hash_files) for _, o in locos},
    }


@dataclass
class ModEntry:
    folder: str
    locos: list[tuple[str, str]] = field(default_factory=list)  # (identifier, display name)


@dataclass
class Installs:
    railroader: installs.Install | None = None
    derail_valley: installs.Install | None = None
    ccl: bool = False
    problems: dict[str, str] = field(default_factory=dict)  # "railroader" | "derail_valley" | "ccl" -> why

    @property
    def ready(self) -> bool:
        return not self.problems


class Controller:
    def __init__(self, settings_path: Path | None = None):
        self.settings_path = Path(settings_path) if settings_path else machine_mod.default_path()
        self.machine = machine_mod.load(self.settings_path)

    # ---- settings -------------------------------------------------------------------------------------------------
    def reload(self) -> None:
        self.machine = machine_mod.load(self.settings_path)

    def settings(self) -> dict:
        return dict(self.machine.values)

    def save_settings(self, changes: dict[str, str]) -> None:
        """Merge edited values into the settings file; an empty value removes the key (so Steam detection applies)."""
        values = read_json(self.settings_path) if self.settings_path.is_file() else {}
        for key, value in changes.items():
            value = (value or "").strip()
            if value:
                values[key] = value
            else:
                values.pop(key, None)
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(self.settings_path, values)
        self.reload()

    def checks(self) -> list[machine_mod.Check]:
        return machine_mod.doctor(self.machine)

    # ---- installs and mods ----------------------------------------------------------------------------------------
    def installs(self) -> Installs:
        found = Installs()
        try:
            found.railroader = installs.railroader(self.machine)
        except installs.InstallError as e:
            found.problems["railroader"] = str(e)
        try:
            found.derail_valley = installs.derail_valley(self.machine)
            found.ccl = installs.ccl_installed(found.derail_valley)
            if not found.ccl:
                found.problems["ccl"] = f"Custom Car Loader is not installed in {found.derail_valley.mods}"
        except installs.InstallError as e:
            found.problems["derail_valley"] = str(e)
        return found

    def tools_missing(self) -> list[str]:
        return [label for key, label, kind, required in SETTINGS
                if required and not ((p := self.machine.path(key)) and (p.is_file() if kind == "file" else p.is_dir()))]

    def list_mods(self, progress: Callable[[int, int], None] | None = None) -> list[ModEntry]:
        """Folders in the Railroader Mods folder that contain steam locomotives."""
        rr = installs.railroader(self.machine)
        folders = sorted((p for p in rr.mods.iterdir() if p.is_dir()), key=lambda p: p.name.casefold())
        out = []
        for i, folder in enumerate(folders):
            if progress:
                progress(i, len(folders))
            locos = Index(folder).steam_locomotives(input_only=True)
            if locos:
                out.append(ModEntry(folder.name, [(o["identifier"], (o.get("metadata") or {}).get("name") or o["identifier"])
                                                  for _, o in locos]))
        return out

    def scan(self, folder: str) -> dict:
        rr = installs.railroader(self.machine)
        mod = installs.mod_in_railroader(rr, folder)
        return scan_report(mod, search_roots(rr, self.machine.search_roots()))

    def convert(self, folder: str, loco: str, livery: str | None = None, audio: str | None = None,
                wheel_radius: float | None = None, on_progress=None, ask: Callable = consent.ask,
                geometry_review: Path | None = None, prebuild_review=None) -> Outcome:
        return convert(folder, self.machine, loco, self.machine.search_roots(), audio, livery, wheel_radius,
                       ask=ask, on_progress=on_progress, geometry_review=geometry_review, prebuild_review=prebuild_review)


def blocking_issues(report: dict, loco: str) -> list[dict]:
    return blocking(report["inventories"][loco])
