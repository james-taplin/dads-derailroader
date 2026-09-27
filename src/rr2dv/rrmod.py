"""Read-only index of Railroader mods and per-locomotive dependency closure.

A Railroader mod is a folder with an info.json. It holds one or more asset packs: folders with Definitions.json
and/or Catalog.json plus a `bundle`. Objects in Definitions.json reference each other by identifier (tender,
truck) and reference assets in other packs through PrefabModelComponent models. Trucks are not followed: every
converted car runs on vanilla Derail Valley bogies. Mods can also carry optional
component-group files (an object `identifier` plus `bulkAdds`, e.g. alternative heralds) and images referenced
as "<mod id>.<file name>".

This module finds every pack, group file and image a steam locomotive needs, from the input first and then from
extra search roots (the Railroader Mods folder, base-game asset packs), and applies the licence policy in
licences.py to the mod and everything it depends on. Nothing here writes to disk.

Resolution is deterministic: the input root outranks search roots, and search roots rank in the order given.
Two candidates at the same rank are an error, never a first match (guide rule D03).
"""
from __future__ import annotations

import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from . import licences
from .jsonio import SourceError, read_json_lenient, sha256_file
from .safety import is_link

DEFINITIONS = "definitions.json"
CATALOG = "catalog.json"
BUNDLE = "bundle"
INFO = "info.json"
MAX_DEPTH = 4  # Mods/<mod>/<pack> is depth 2; allow a little extra nesting
SKIP_DIRS = {".git", "__pycache__", "library", "temp", "logs", "obj"}

STEAM_LOCOMOTIVE = "SteamLocomotive"
TENDER = "Tender"

# Component kinds that only work with a code mod installed in Railroader. Each entry needs evidence.
CODE_MOD_KINDS = {
    "ArticulatedSteamEngineComponent": ("LegosBetterSteam",
                                        "guide E02: LegosBetterSteam components change pull and steam use ('diamater' spelling)"),
}

# Audio is never converted: every sound (whistle, bell, chuff, pumps...) aliases to vanilla Derail Valley S060 or
# S282 audio, chosen by boiler size. Heating surface below the cut-off counts as a small boiler.
AUDIO_BASES = ("S060", "S282")
SMALL_BOILER_MAX_HEATING_FT2 = 1500.0  # ~32,000 lbf tank (GWR 7200: ~1,478 ft2) = S060; USRA 0-6-0 tender (1,886 ft2) = S282
SOUND_KINDS = {"Whistle", "Bell", "Chuff", "Compressor", "Dynamo"}

# Features of a mod's own files that only work with a code mod. Each entry needs evidence.
FEATURE_PROVIDERS = {
    "component-groups": ("LegosLibraryOfStuff",
                         "GN M-2 keeps its group files in LegosLibraryOfStuff/Definitions/; guide GUIDE_Railroader_to_DV_CCL.md "
                         "section C: its heralds and tender text come from LegosLibraryOfStuff decal groups"),
}


def audio_basis(loco_definition: dict, override: str | None = None) -> dict:
    """Which vanilla DV loco's sounds a conversion uses. Deterministic; `override` records a user answer."""
    hs = loco_definition.get("totalHeatingSurface")
    if override:
        if override not in AUDIO_BASES:
            raise ValueError(f"audio must be one of {', '.join(AUDIO_BASES)}")
        return {"basis": override, "rule": "chosen by the user"}
    if isinstance(hs, (int, float)) and not isinstance(hs, bool) and hs > 0:
        small = hs < SMALL_BOILER_MAX_HEATING_FT2
        return {"basis": "S060" if small else "S282",
                "rule": f"totalHeatingSurface {hs:g} ft2 {'<' if small else '>='} {SMALL_BOILER_MAX_HEATING_FT2:g} ft2 "
                        f"({'small' if small else 'big'} boiler)"}
    return {"basis": None, "rule": "no totalHeatingSurface in the definition"}


def definition(obj: dict) -> dict:
    d = obj.get("definition")
    return d if isinstance(d, dict) else {}


def components(d: dict) -> list[dict]:
    comps = d.get("components")
    return [c for c in comps if isinstance(c, dict)] if isinstance(comps, list) else []


@dataclass(frozen=True)
class Root:
    rank: int  # 0 = input; 1.. = search roots in the order given
    label: str
    path: Path


@dataclass
class Issue:
    severity: str  # error: blocks conversion; warning: needs review; info
    code: str
    message: str
    data: dict | None = None

    def as_dict(self) -> dict:
        out = {"severity": self.severity, "code": self.code, "message": self.message}
        if self.data:
            out["data"] = self.data
        return out


GAME_DATA = "railroader_data"


def is_game_content(path: Path) -> bool:
    """Railroader's own asset packs live under Railroader_Data (StreamingAssets/AssetPacks)."""
    return any(part.casefold() == GAME_DATA for part in path.parts)


def _rel(root: Root, path: Path) -> str:
    rel = path.relative_to(root.path).as_posix()
    return "" if rel == "." else rel


@dataclass
class Mod:
    root: Root
    path: Path
    ident: str  # info.json Id, else the folder name
    licences: list[dict] = field(default_factory=list)

    @property
    def rel(self) -> str:
        return _rel(self.root, self.path)

    def describe(self) -> dict:
        return {"id": self.ident, "root": self.root.label, "path": self.rel, "licences": self.licences}


@dataclass
class Pack:
    root: Root
    path: Path
    files: dict[str, Path]  # lower-cased known file name -> actual path
    objects: list[dict] = field(default_factory=list)
    assets: dict[str, dict] = field(default_factory=dict)
    mod: Mod | None = None
    errors: dict[str, str] = field(default_factory=dict)  # lower-cased file name -> why it could not be read

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def rel(self) -> str:
        return _rel(self.root, self.path)

    @property
    def folder_above(self) -> str:
        """Folder name directly above the pack, the prefix assetPackIdentifier uses."""
        return self.path.parent.name

    def describe(self) -> dict:
        return {"name": self.name, "root": self.root.label, "path": self.rel}

    def model_prefab(self, model: str) -> str:
        """Prefab file name for a model identifier: the catalogue entry's file, else "<model>.prefab"."""
        asset = self.assets.get(model)
        if isinstance(asset, dict) and isinstance(asset.get("filename"), str):
            return asset["filename"]
        return model + ".prefab"

    def has_model(self, model: str) -> bool:
        """A model identifier names a catalogue key or a prefab file (LLW uses one string for both; others don't)."""
        if model in self.assets:
            return True
        stems = {Path(str(a.get("filename", ""))).stem.casefold() for a in self.assets.values() if isinstance(a, dict)}
        return model.casefold() in stems


@dataclass
class GroupFile:
    """Optional component group added to an object by a separate JSON file (identifier + bulkAdds)."""
    root: Root
    path: Path
    data: dict

    @property
    def target(self) -> str:
        return self.data["identifier"]

    def describe(self) -> dict:
        comps = [c for c in self.data.get("bulkAdds", []) if isinstance(c, dict)]
        return {"target": self.target, "group_id": self.data.get("GroupID"), "group_name": self.data.get("GroupName"),
                "file": {"root": self.root.label, "path": _rel(self.root, self.path)},
                "component_kinds": dict(sorted(Counter(str(c.get("kind", "?")) for c in comps).items()))}


class Resolution:
    """Outcome of looking something up: exactly one hit, nothing, or an ambiguous tie."""

    def __init__(self, hit=None, candidates: Sequence = ()):
        self.hit = hit
        self.candidates = list(candidates)


def _rank_pick(candidates: list, rank_of) -> Resolution:
    if not candidates:
        return Resolution()
    best = min(rank_of(c) for c in candidates)
    top = [c for c in candidates if rank_of(c) == best]
    return Resolution(top[0], top) if len(top) == 1 else Resolution(None, top)


def _walk(root: Root) -> Iterable[tuple[Path, list[str], bool]]:
    """Yield (folder, file names, is_pack) down to MAX_DEPTH, never following links, never into a pack."""
    base_depth = len(root.path.parts)
    for current, dirs, files in os.walk(root.path, followlinks=False):
        here = Path(current)
        names = {f.casefold() for f in files}
        is_pack = DEFINITIONS in names or CATALOG in names
        yield here, sorted(files), is_pack
        if is_pack or len(here.parts) - base_depth >= MAX_DEPTH:
            dirs[:] = []
        dirs[:] = sorted(d for d in dirs if d.casefold() not in SKIP_DIRS and not is_link(here / d))


def _known_files(path: Path, names: Iterable[str]) -> dict[str, Path]:
    found = {}
    for name in names:
        key = name.casefold()
        entry = path / name
        if key in (DEFINITIONS, CATALOG, BUNDLE) and entry.is_file() and not is_link(entry):
            found[key] = entry
    return found


class Index:
    def __init__(self, input_path: Path, search_paths: Sequence[Path] = ()):
        self.roots = [Root(0, "input", input_path.resolve())]
        self.roots += [Root(i, f"search{i}", p.resolve()) for i, p in enumerate(search_paths, start=1)]
        self.packs: list[Pack] = []
        self.mods: list[Mod] = []
        self.groups: list[GroupFile] = []
        self.issues: list[Issue] = []
        self._objects: dict[str, list[tuple[Pack, dict]]] = defaultdict(list)
        self._packs_by_name: dict[str, list[Pack]] = defaultdict(list)
        self._mods_by_ident: dict[str, list[Mod]] = defaultdict(list)
        self._mod_files: dict[Path, dict[str, list[Path]]] = {}
        seen: set[Path] = set()
        for root in self.roots:
            if not root.path.is_dir():
                sev = "error" if root.rank == 0 else "warning"
                self.issues.append(Issue(sev, "root-missing", f"{root.label} folder not found: {root.path}"))
                continue
            mods_here: dict[Path, Mod] = {}
            for folder, files, is_pack in _walk(root):
                resolved = folder.resolve()
                if resolved in seen:  # e.g. the input folder sits inside a search root
                    continue
                seen.add(resolved)
                lowered = {f.casefold() for f in files}
                # The input folder counts as a mod even without info.json; a search root (e.g. Mods) never does.
                if INFO in lowered or (folder == root.path and root.rank == 0):
                    mods_here[folder] = self._load_mod(root, folder, files)
                if is_pack:
                    self._load_pack(root, folder, files, mods_here)
                if root.rank == 0:  # optional groups apply only from the mod being converted
                    self._load_groups(root, folder, files)

    # ---- loading ------------------------------------------------------------------------------------------

    def _load_mod(self, root: Root, folder: Path, files: list[str]) -> Mod:
        ident = folder.name
        info = next((folder / f for f in files if f.casefold() == INFO), None)
        if info:
            try:
                data = read_json_lenient(info)
                if isinstance(data, dict) and isinstance(data.get("Id") or data.get("id"), str):
                    ident = data.get("Id") or data.get("id")
            except SourceError as e:
                self.issues.append(Issue("warning", "info-unreadable", str(e)))
        mod = Mod(root, folder, ident, licences.scan_folder(folder))
        self.mods.append(mod)
        self._mods_by_ident[ident.casefold()].append(mod)
        if ident.casefold() != folder.name.casefold():
            self._mods_by_ident[folder.name.casefold()].append(mod)
        return mod

    def _load_pack(self, root: Root, folder: Path, files: list[str], mods_here: dict[Path, Mod]) -> None:
        pack = Pack(root, folder, _known_files(folder, files))
        pack.mod = next((mods_here[p] for p in [folder, *folder.parents] if p in mods_here), None)
        where = f"{root.label}:{pack.rel or '.'}"
        # A broken file only matters if a locomotive needs this pack; inventory() turns it into an error then.
        for key in (DEFINITIONS, CATALOG):
            if key not in pack.files:
                continue
            try:
                data = read_json_lenient(pack.files[key])
                if not isinstance(data, dict):
                    raise SourceError(pack.files[key], "expected a JSON object")
                if key == DEFINITIONS:
                    objects = data.get("objects", [])
                    pack.objects = [o for o in objects if isinstance(o, dict) and isinstance(o.get("identifier"), str)] \
                        if isinstance(objects, list) else []
                else:
                    assets = data.get("assets", {})
                    pack.assets = assets if isinstance(assets, dict) else {}
            except SourceError as e:
                pack.errors[key] = str(e)
                self.issues.append(Issue("warning", "pack-unreadable", f"{where}: {e} (only matters if a locomotive needs this pack)"))
        self.packs.append(pack)
        self._packs_by_name[pack.name.casefold()].append(pack)
        for obj in pack.objects:
            self._objects[obj["identifier"]].append((pack, obj))

    def _load_groups(self, root: Root, folder: Path, files: list[str]) -> None:
        for f in files:
            if not f.casefold().endswith(".json") or f.casefold() in (INFO, DEFINITIONS, CATALOG):
                continue
            try:
                data = read_json_lenient(folder / f)
            except SourceError:
                continue  # not every JSON file is ours to understand
            if isinstance(data, dict) and isinstance(data.get("identifier"), str) and isinstance(data.get("bulkAdds"), list):
                self.groups.append(GroupFile(root, folder / f, data))

    # ---- lookups --------------------------------------------------------------------------------------

    def unreadable_definitions(self, max_rank: int | None = None) -> list[Pack]:
        return [p for p in self.packs if DEFINITIONS in p.errors and (max_rank is None or p.root.rank <= max_rank)]

    def find_object(self, identifier: str) -> Resolution:
        return _rank_pick(self._objects.get(identifier, []), lambda po: po[0].root.rank)

    def find_pack(self, pack_identifier: str) -> Resolution:
        """assetPackIdentifier is "<mod folder>\\<pack>" (or just "<pack>"); match the pack folder name,
        then use the mod folder to separate same-named packs."""
        segments = [s for s in pack_identifier.replace("\\", "/").split("/") if s]
        if not segments:
            return Resolution()
        candidates = self._packs_by_name.get(segments[-1].casefold(), [])
        if len(candidates) > 1 and len(segments) > 1:
            narrowed = [p for p in candidates if p.folder_above.casefold() == segments[-2].casefold()]
            candidates = narrowed or candidates
        return _rank_pick(candidates, lambda p: p.root.rank)

    def find_mod(self, ident: str) -> Resolution:
        return _rank_pick(self._mods_by_ident.get(ident.casefold(), []), lambda m: m.root.rank)

    def find_texture(self, texture_name: str) -> tuple[Resolution, Mod | None]:
        """Images are named "<mod id>.<file name>"; find the mod, then the file anywhere inside it."""
        pieces = texture_name.split(".")
        for i in range(len(pieces) - 1, 0, -1):
            ident, filename = ".".join(pieces[:i]), ".".join(pieces[i:])
            mres = _rank_pick(self._mods_by_ident.get(ident.casefold(), []), lambda m: m.root.rank)
            if mres.hit is None:
                continue
            mod = mres.hit
            if mod.path not in self._mod_files:
                listing: dict[str, list[Path]] = defaultdict(list)
                for folder, files, _ in _walk(Root(mod.root.rank, mod.root.label, mod.path)):
                    for f in files:
                        listing[f.casefold()].append(folder / f)
                self._mod_files[mod.path] = listing
            hits = self._mod_files[mod.path].get(filename.casefold(), [])
            return (Resolution(hits[0], hits) if len(hits) == 1 else Resolution(None, hits)), mod
        return Resolution(), None

    def objects_of_kind(self, kind: str) -> list[tuple[Pack, dict]]:
        hits = [(p, o) for p in self.packs for o in p.objects if definition(o).get("kind") == kind]
        return sorted(hits, key=lambda po: (po[0].root.rank, po[0].rel, po[1]["identifier"]))

    def steam_locomotives(self, input_only: bool = True) -> list[tuple[Pack, dict]]:
        locos = self.objects_of_kind(STEAM_LOCOMOTIVE)
        return [po for po in locos if po[0].root.rank == 0] if input_only else locos

    def other_locomotives(self) -> list[tuple[Pack, dict]]:
        """Input locomotives the app does not convert (diesel, electric...)."""
        hits = []
        for pack in self.packs:
            if pack.root.rank:
                continue
            for obj in pack.objects:
                kind = definition(obj).get("kind", "")
                if isinstance(kind, str) and kind.endswith("Locomotive") and kind != STEAM_LOCOMOTIVE:
                    hits.append((pack, obj))
        return hits


def _ambiguous(what: str, res: Resolution) -> str:
    places = []
    for c in res.candidates:
        item = c[0] if isinstance(c, tuple) else c
        places.append(f"{item.root.label}:{item.rel}" if hasattr(item, "root") else str(item))
    return f"{what} matches more than one candidate at the same priority ({', '.join(places)}); remove the duplicate or pass it as the input"


def _unreadable_hint(index: "Index") -> str:
    broken = index.unreadable_definitions()
    if not broken:
        return ""
    return f" ({len(broken)} pack(s) with an unreadable Definitions.json could hold it: " + \
        ", ".join(f"{p.root.label}:{p.rel}" for p in broken[:5]) + ("..." if len(broken) > 5 else "") + ")"


def _file_record(root: Root, path: Path, role: str, hash_files: bool) -> dict:
    rec = {"root": root.label, "path": _rel(root, path), "role": role, "bytes": path.stat().st_size}
    if hash_files:
        rec["sha256"] = sha256_file(path)
    return rec


def inventory(index: Index, loco_id: str, hash_files: bool = True, audio: str | None = None) -> dict:
    """Dependency closure of one steam locomotive, as a deterministic JSON-ready dict."""
    issues: list[Issue] = []
    res = index.find_object(loco_id)
    if res.hit is None:
        code, msg = ("ambiguous", _ambiguous(f"locomotive {loco_id}", res)) if res.candidates else ("not-found", f"locomotive {loco_id} not found" + _unreadable_hint(index))
        return {"schema": 1, "locomotive": {"id": loco_id}, "issues": [Issue("error", code, msg).as_dict()]}
    loco_pack, loco = res.hit
    ldef = definition(loco)
    hidden = index.unreadable_definitions(max_rank=loco_pack.root.rank)
    if hidden:
        issues.append(Issue("warning", "unreadable-definitions",
                            f"{len(hidden)} pack(s) have an unreadable Definitions.json ({', '.join(p.rel for p in hidden[:5])}); "
                            "a duplicate identifier hidden there cannot be detected"))
    if ldef.get("kind") != STEAM_LOCOMOTIVE:
        issues.append(Issue("error", "not-steam", f"{loco_id} is {ldef.get('kind')!r}, not a steam locomotive"))

    packs: dict[Path, Pack] = {loco_pack.path: loco_pack}
    vehicles = [(loco_pack, loco)]  # objects whose models and parts we follow

    # Problematic assets are left out, never copied (James, W22): Railroader game content, and anything from another
    # mod whose licence forbids modification or cannot be read. Their files are never staged, exported or opened, so
    # those mods' licences do not stop the conversion. DV has no vanilla equivalent for loose steam fittings (CCL's
    # mesh list has no stacks, pilots, lamps or rails), so a left-out part or image is reported for review, not swapped.
    converted = loco_pack.mod
    left_out: list[dict] = []

    def leave_out_part(vid: str, comp: dict, comps: list[dict], pack_ident: str, asset_ident, ppack: Pack, reason: str) -> None:
        # A part is a model; anything the definition anchors inside it loses its anchor too (a functional loss to review).
        name = comp.get("name")
        anchored = sorted(str(c.get("name")) for c in comps if c is not comp and isinstance(c.get("parent"), dict)
                          and (c["parent"].get("path") or [None])[0] == name)
        left_out.append({"what": "part", "owner": vid, "component": name, "pack_identifier": pack_ident,
                         "asset": asset_ident, "pack": ppack.describe(), "reason": reason,
                         "effect": "model not shown" + (f"; loses its anchor: {', '.join(anchored)}" if anchored else ""),
                         "anchored": anchored})
        issues.append(Issue("warning", "left-out", f"{vid}/{name}: part {asset_ident!r} from {ppack.name} left out: {reason}"
                            + (f"; components anchored in it: {', '.join(anchored)}" if anchored else "")))

    def problem(path: Path, mod: Mod | None) -> str | None:
        if is_game_content(path):
            return "Railroader game content"
        if mod is None or (converted is not None and mod.path == converted.path):
            return None
        for lic in mod.licences:
            if lic.get("unreadable"):
                return f"mod {mod.ident}: licence {lic['file']} cannot be read"
            if licences.forbidding(lic["terms"]):
                return f"mod {mod.ident} ({lic['file']}) forbids {licences.describe(licences.forbidding(lic['terms']))}"
        return None

    tender_info = None
    tender_id = ldef.get("tenderIdentifier")
    if isinstance(tender_id, str) and tender_id:
        tres = index.find_object(tender_id)
        if tres.hit:
            tpack, tender = tres.hit
            if is_game_content(tpack.path):
                issues.append(Issue("error", "game-content", f"tender {tender_id} is Railroader game content; rr2dv does not copy it "
                                    "and Derail Valley has no vanilla tender to put in its place"))
            packs[tpack.path] = tpack
            vehicles.append((tpack, tender))
            tender_info = {"id": tender_id, "pack": tpack.describe()}
            if definition(tender).get("archetype") != TENDER:
                issues.append(Issue("warning", "tender-archetype", f"tender {tender_id} has archetype {definition(tender).get('archetype')!r}"))
        elif tres.candidates:
            issues.append(Issue("error", "ambiguous", _ambiguous(f"tender {tender_id}", tres)))
        else:
            issues.append(Issue("error", "missing-tender", f"tender {tender_id} not found in the input or search folders" + _unreadable_hint(index)))

    # Trucks are never converted (James, W21): every car runs on vanilla Derail Valley bogies, so nothing of a truck
    # (its mod's bundle, or Railroader base-game meshes) ends up in the pack, and its licence cannot stop a conversion.
    # The truck's own definition is read for information only: what the swap leaves out.
    trucks = []
    for vpack, vehicle in list(vehicles):
        truck_id = definition(vehicle).get("truckIdentifier")
        if not (isinstance(truck_id, str) and truck_id):
            continue
        tres = index.find_object(truck_id)
        entry = {"id": truck_id, "owner": vehicle["identifier"], "replaced_by": "vanilla Derail Valley bogies",
                 "found": None, "source": None, "left_out": []}
        if tres.hit:
            tpack, truck = tres.hit
            tdef = definition(truck)
            entry["found"] = tpack.describe()
            entry["source"] = {k: tdef.get(k) for k in ("diameter", "numberOfAxles", "length") if tdef.get(k) is not None}
            entry["left_out"] = sorted({str(c.get("kind", "?")) for c in components(tdef)}
                                       | ({"brakeAnimation"} if tdef.get("brakeAnimation") else set()))
        note = "found in " + (f"{entry['found']['root']}:{entry['found']['path'] or entry['found']['name']}" if tres.hit
                              else "several places" if tres.candidates else "no indexed folder")
        issues.append(Issue("info", "truck-replaced",
                            f"truck {truck_id} (used by {vehicle['identifier']}; {note}) is replaced by vanilla Derail Valley bogies"
                            + (f"; left out: {', '.join(entry['left_out'])}" if entry["left_out"] else "")))
        trucks.append(entry)

    car_ids = {loco_id} | ({tender_info["id"]} if tender_info else set())
    groups = sorted((g for g in index.groups if g.target in car_ids), key=lambda g: _rel(g.root, g.path))

    parts, textures, code_mods = [], [], []
    sounds: set[str] = set()
    extra: dict[Path, dict] = {}
    kinds: Counter = Counter()
    radial, toggles = [], []

    def follow_textures(owner: str, comps: list[dict], via: str) -> None:
        for comp in comps:
            name = comp.get("textureName")
            if not (isinstance(name, str) and name) or any(x["id"] == name and x["owner"] == owner for x in textures):
                continue
            tres, mod = index.find_texture(name)
            entry = {"id": name, "owner": owner, "via": via, "file": None}
            reason = problem(tres.hit, mod) if tres.hit else None
            if reason:
                entry["left_out"] = reason
                left_out.append({"what": "image", "owner": owner, "id": name, "via": via, "reason": reason})
                issues.append(Issue("warning", "left-out", f"{owner}: image {name!r} left out: {reason}"))
            elif tres.hit:
                path = tres.hit
                entry["file"] = {"root": mod.root.label, "path": _rel(mod.root, path)}
                extra.setdefault(path, _file_record(mod.root, path, "texture", hash_files))
            elif tres.candidates:
                issues.append(Issue("warning", "ambiguous-texture", f"{owner}: image {name!r} matches several files in mod {mod.ident}; it will be left out"))
            else:
                where = f"mod {mod.ident}" if mod else "any indexed mod"
                issues.append(Issue("warning", "missing-texture", f"{owner}: image {name!r} not found in {where}; it will be left out"))
            textures.append(entry)

    vehicle_records = []
    for vpack, vehicle in vehicles:
        vdef = definition(vehicle)
        vid = vehicle["identifier"]
        model = vdef.get("modelIdentifier")
        if isinstance(model, str) and model and vpack.assets and not vpack.has_model(model):
            issues.append(Issue("warning", "model-not-in-catalog", f"{vid}: model {model!r} matches no key or prefab in {vpack.name}/Catalog.json"))
        role = "locomotive" if vehicle is loco else "tender"
        if isinstance(model, str) and model:
            vehicle_records.append({"id": vid, "role": role, "model": model, "prefab": vpack.model_prefab(model), "pack": vpack.describe()})
        else:
            issues.append(Issue("error", "no-model", f"{vid} ({role}) has no modelIdentifier"))
        is_car = vid in car_ids
        comps = components(vdef)
        for comp in comps:
            kind = str(comp.get("kind", "?"))
            if is_car:
                kinds[kind] += 1
                if kind == "RadialControl":
                    radial.append({"owner": vid, "purpose": comp.get("purpose"), "name": comp.get("name")})
                elif kind == "ToggleAnimation":
                    toggles.append({"owner": vid, "name": comp.get("name")})
                if kind in SOUND_KINDS:
                    sounds.add(kind)
                if kind in CODE_MOD_KINDS:
                    provider, evidence = CODE_MOD_KINDS[kind]
                    code_mods.append({"kind": kind, "provider": provider, "owner": vid, "evidence": evidence})
            if kind != "PrefabModelComponent":
                continue
            m = comp.get("model") or {}
            pack_ident, asset_ident = m.get("assetPackIdentifier"), m.get("assetIdentifier")
            label = f"{vid}/{comp.get('name')}"
            if not (isinstance(pack_ident, str) and isinstance(asset_ident, str)):
                issues.append(Issue("error", "bad-part", f"{label}: PrefabModelComponent without assetPackIdentifier/assetIdentifier"))
                continue
            pres = index.find_pack(pack_ident)
            if pres.hit is None:
                if pres.candidates:
                    issues.append(Issue("error", "ambiguous", _ambiguous(f"part pack {pack_ident}", pres)))
                else:
                    issues.append(Issue("error", "missing-part-pack", f"{label}: pack {pack_ident!r} not found"))
                continue
            ppack = pres.hit
            reason = problem(ppack.path, ppack.mod)
            if reason:
                leave_out_part(vid, comp, comps, pack_ident, asset_ident, ppack, reason)
                continue
            if CATALOG in ppack.errors:
                packs[ppack.path] = ppack  # reported as pack-unreadable below
                continue
            prefix = [s for s in pack_ident.replace("\\", "/").split("/") if s][:-1]
            if prefix and ppack.folder_above.casefold() != prefix[-1].casefold():
                issues.append(Issue("warning", "pack-folder-mismatch",
                                    f"{label}: {pack_ident!r} matched pack {ppack.root.label}:{ppack.rel} by name only (its mod folder is {ppack.folder_above!r})"))
            asset = ppack.assets.get(asset_ident)
            if not isinstance(asset, dict):
                # Broken in the source mod itself (X32: 13 installed locos): Railroader cannot load it either, so it is
                # left out and listed rather than stopping the conversion. A pack that cannot be found still stops it.
                leave_out_part(vid, comp, comps, pack_ident, asset_ident, ppack,
                               f"asset {asset_ident!r} is not in {ppack.name}/Catalog.json (broken in the source mod)")
                continue
            packs[ppack.path] = ppack
            parts.append({"owner": vid, "component": comp.get("name"), "pack": ppack.name, "pack_ref": ppack.describe(),
                          "asset": asset_ident, "filename": asset.get("filename"), "enabled": comp.get("enabled", True)})
        if is_car:
            follow_textures(vid, comps, "definition")

    group_records = []
    for g in groups:
        extra.setdefault(g.path, _file_record(g.root, g.path, "component-group", hash_files))
        follow_textures(g.target, [c for c in g.data.get("bulkAdds", []) if isinstance(c, dict)], f"group {g.data.get('GroupID')}")
        group_records.append(g.describe())
    if group_records:
        issues.append(Issue("info", "optional-groups", f"{len(group_records)} optional component group(s) to choose from: "
                            + ", ".join(str(g["group_name"]) for g in group_records)))
    for provider in sorted({c["provider"] for c in code_mods}):
        used = sorted({f"{c['owner']}:{c['kind']}" for c in code_mods if c["provider"] == provider})
        issues.append(Issue("warning", "code-mod-component",
                            f"uses {provider} ({', '.join(used)}): Railroader's figures for this loco depend on that mod; "
                            "the Derail Valley simulation must be set deliberately (guide E02)"))

    ordered = sorted(packs.values(), key=lambda p: (p.root.rank, p.rel))
    pack_records = []
    for p in ordered:
        for key, why in sorted(p.errors.items()):
            issues.append(Issue("error", "pack-unreadable", f"needed pack {p.root.label}:{p.rel or '.'} is broken: {why}"))
        if BUNDLE not in p.files:
            issues.append(Issue("error", "missing-bundle", f"pack {p.root.label}:{p.rel or '.'} has no bundle file"))
        files = []
        for key in (CATALOG, DEFINITIONS, BUNDLE):
            if key in p.files:
                f = p.files[key]
                entry = {"name": f.name, "bytes": f.stat().st_size}
                if hash_files:
                    entry["sha256"] = sha256_file(f)
                files.append(entry)
        pack_records.append({**p.describe(), "files": files})

    # Licence policy (licences.py). Only mods whose content ends up in the Derail Valley pack can stop a conversion:
    # the converted mod and every mod whose bundles or images we copy. Code mods the loco uses in Railroader are not
    # needed in Derail Valley and are never opened, so they are listed for information only.
    involved: dict[Path, Mod] = {}
    for p in ordered:
        if p.mod:
            involved[p.mod.path] = p.mod
    for path, rec in extra.items():
        owner = max((m for m in index.mods if m.root.label == rec["root"] and path.is_relative_to(m.path)),
                    key=lambda m: len(m.path.parts), default=None)
        if owner:
            involved[owner.path] = owner
    mod_records = []
    for mod in sorted(involved.values(), key=lambda m: (m.root.rank, m.rel)):
        mod_records.append(mod.describe())
        for lic in mod.licences:
            where = f"mod {mod.ident} ({lic['file']})"
            if lic.get("unreadable"):
                issues.append(Issue("error", "licence-unreadable", f"{where} cannot be read as text; rr2dv will not guess what it allows"))
            elif licences.forbidding(lic["terms"]):
                issues.append(Issue("error", "licence-forbids-conversion",
                                    f"{where} forbids {licences.describe(licences.forbidding(lic['terms']))}; rr2dv will not convert this locomotive",
                                    {"mod": mod.ident, "file": lic["file"], "sha256": lic["sha256"], "terms": lic["terms"]}))
            elif lic["terms"]:
                issues.append(Issue("info", "licence-terms", f"{where}: {', '.join(lic['terms'])}; the converted pack is for personal use"))

    providers = {c["provider"]: c["evidence"] for c in code_mods}
    if group_records:
        name, evidence = FEATURE_PROVIDERS["component-groups"]
        providers.setdefault(name, evidence)
    railroader_only = []
    for provider in sorted(providers):
        known = licences.KNOWN_LICENCES.get(provider.casefold())
        railroader_only.append({"id": provider, "installed": bool(index.find_mod(provider).candidates),
                                "evidence": providers[provider], "licence_terms": known["terms"] if known else None})
        issues.append(Issue("info", "railroader-only-dependency",
                            f"uses {provider} in Railroader; not needed in Derail Valley and none of its files are opened or copied"))

    audio_choice = audio_basis(ldef, audio)
    audio_choice["replaces"] = sorted(sounds)
    if audio_choice["basis"] is None:
        issues.append(Issue("error", "needs-answer", f"{loco_id}: {audio_choice['rule']}; choose the vanilla sound set with --audio S060 (small boiler) or --audio S282 (big boiler)"))
    return {
        "schema": 1,
        "locomotive": {"id": loco_id, "name": (loco.get("metadata") or {}).get("name"), "pack": loco_pack.describe()},
        "tender": tender_info,
        "trucks": trucks,
        "vehicles": vehicle_records,
        "parts": parts,
        "left_out": left_out,
        "packs": pack_records,
        "extra_files": sorted(extra.values(), key=lambda r: (r["root"], r["path"])),
        "mods": mod_records,
        "railroader_only": railroader_only,
        "optional_groups": group_records,
        "textures": textures,
        "code_mods": code_mods,
        "audio": {"source": "vanilla Derail Valley", **audio_choice},
        "controls": {"radial": radial, "toggles": toggles},
        "component_kinds": dict(sorted(kinds.items())),
        "issues": list({(i.severity, i.code, i.message): i.as_dict() for i in issues}.values()),
    }


def blocking(inv: dict) -> list[dict]:
    """Errors that stop a conversion. Licence errors are among them and have no override."""
    return [i for i in inv.get("issues", []) if i["severity"] == "error"]
