"""What the desktop app (gui.py) and the command line share: settings, the game installs, the mods to choose from,
a mod's scan report and a conversion. No widgets here, so all of it is testable without a screen."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from . import consent, geometryreview, installs, machine as machine_mod
from .jsonio import read_json, write_json
from .pipeline import Outcome, convert, fingerprint, search_roots
from .record import liveries
from .rrmod import Index, blocking, definition, inventory

# Settings the app edits, in the order its Settings dialog shows them: (key, label, kind, required).
SETTINGS = [
    ("unity", "Unity 2019.4.40f1 (Unity.exe)", "file", True),
    ("carCreator", "CarCreator 3.1.9 package (.unitypackage)", "file", True),
    ("assetRipper", "AssetRipper", "file", True),
    ("python", "Python (included in the Windows app; source runs need it)", "file", not getattr(sys, "frozen", False)),
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
    folder: str  # a Mods folder's name, or a base-game asset pack's full path (what `convert` and `scan` take)
    locos: list[tuple[str, str]] = field(default_factory=list)  # (identifier, display name)
    base: bool = False  # a Railroader base-game asset pack
    label: str = ""  # the folder's own name, for display

    def __post_init__(self):
        self.label = self.label or Path(self.folder).name


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

    def checks(self, changes: dict[str, str] | None = None) -> list[machine_mod.Check]:
        """Check saved settings, or preview values currently shown in the Settings dialog."""
        if changes is None:
            return machine_mod.doctor(self.machine)
        values = dict(self.machine.values)
        for key, value in changes.items():
            if value.strip():
                values[key] = value.strip()
            else:
                values.pop(key, None)
        return machine_mod.doctor(machine_mod.Machine(self.machine.source, values))

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
                if required and not (key == "python" and getattr(sys, "frozen", False))
                and not ((p := self.machine.path(key)) and (p.is_file() if kind == "file" else p.is_dir()))]

    def list_mods(self, progress: Callable[[int, int], None] | None = None) -> list[ModEntry]:
        """Folders in the Railroader Mods folder that contain steam locomotives, then Railroader's own base-game asset
        packs that do (0.3: every locomotive pack there has its Definitions.json, catalogue and bundle)."""
        rr = installs.railroader(self.machine)
        mods = sorted((p for p in rr.mods.iterdir() if p.is_dir()), key=lambda p: p.name.casefold())
        packs = sorted((p for p in rr.asset_packs.iterdir() if p.is_dir()), key=lambda p: p.name.casefold()) \
            if rr.asset_packs.is_dir() else []
        out = []
        for i, folder in enumerate(mods + packs):
            if progress:
                progress(i, len(mods) + len(packs))
            base = i >= len(mods)
            try:
                locos = Index(folder).steam_locomotives(input_only=True)
            except Exception:  # one unreadable pack never hides the rest
                continue
            if locos:
                out.append(ModEntry(str(folder) if base else folder.name,
                                    [(o["identifier"], (o.get("metadata") or {}).get("name") or o["identifier"]) for _, o in locos],
                                    base=base, label=folder.name))
        return out

    def scan(self, folder: str) -> dict:
        rr = installs.railroader(self.machine)
        mod = installs.mod_in_railroader(rr, folder)
        return scan_report(mod, search_roots(rr, self.machine.search_roots()))

    def reports(self) -> Path:
        """Where finished and failed runs keep their compact reports (workspace.finish)."""
        return self.machine.work_root / "reports"

    def geometry_reviews(self, folder: str, loco: str) -> list[dict]:
        """Geometry reviews in the reports folder that this locomotive's current source files would accept."""
        rr = installs.railroader(self.machine)
        mod = installs.mod_in_railroader(rr, folder)
        return compatible_reviews(self.reports(), Index(mod, search_roots(rr, self.machine.search_roots())), loco)

    def convert(self, folder: str, loco: str, livery: str | None = None, audio: str | None = None,
                wheel_radius: float | None = None, on_progress=None, ask: Callable = consent.ask,
                geometry_review: Path | None = None, prebuild_review=None) -> Outcome:
        return convert(folder, self.machine, loco, self.machine.search_roots(), audio, livery, wheel_radius,
                       ask=ask, on_progress=on_progress, geometry_review=geometry_review, prebuild_review=prebuild_review)


def compatible_reviews(reports: Path, index: Index, loco: str) -> list[dict]:
    """Every geometry review (proposed or used) under `reports` that the build would accept for `loco` now: same input
    fingerprint and only this loco and its tender, newest run first, identical contents once. The user still chooses
    one; nothing is applied automatically (no automatic beam approval)."""
    inv = inventory(index, loco)
    if any(i["severity"] == "error" for i in inv["issues"]) or not reports.is_dir():
        return []
    tender = (inv.get("tender") or {}).get("id")
    cars = {loco} | ({tender} if tender else set())
    found, seen = [], set()
    for path in sorted(reports.glob("*/geometry-review*.json"), key=lambda p: (p.parent.name, "proposed" in p.name), reverse=True):
        try:
            data = geometryreview.validate(read_json(path), fingerprint(inv), cars)
        except (OSError, ValueError, KeyError, TypeError):
            continue
        key = repr(sorted((vid, tuple(f["EndBeamProbeHeight"]["value"])) for vid, f in data["vehicles"].items()))
        if key in seen:
            continue
        seen.add(key)
        bands = ", ".join(f"{'loco' if vid == loco else 'tender'} {f['EndBeamProbeHeight']['value'][0]:.2f}..{f['EndBeamProbeHeight']['value'][1]:.2f} m"
                          for vid, f in sorted(data["vehicles"].items(), key=lambda v: v[0] != loco))
        missing = " (no tender band)" if tender and tender not in data["vehicles"] else ""
        kind = "proposed" if "proposed" in path.name else "used"
        found.append({"path": str(path), "label": f"{path.parent.name[:15]} {kind}: {bands}{missing}",
                      "cars": sorted(data["vehicles"])})
    return found


def blocking_issues(report: dict, loco: str) -> list[dict]:
    return blocking(report["inventories"][loco])
