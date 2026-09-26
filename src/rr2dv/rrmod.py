"""Read-only index of Railroader asset packs and per-locomotive dependency closure.

A Railroader mod holds one or more asset packs: folders with Definitions.json and/or Catalog.json plus a
`bundle`. Objects in Definitions.json reference each other by identifier (tender, truck) and reference assets
in other packs through PrefabModelComponent models. This module finds every pack and object a steam
locomotive needs, from the input mod first and then from extra search roots (the Railroader Mods folder,
base-game asset packs). Nothing here writes to disk.

Resolution is deterministic: the input root outranks search roots, and search roots rank in the order given.
Two candidates at the same rank are an error, never a first match (guide rule D03).
"""
from __future__ import annotations

import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from .jsonio import SourceError, read_json_lenient, sha256_file
from .safety import is_link

DEFINITIONS = "definitions.json"
CATALOG = "catalog.json"
BUNDLE = "bundle"
MAX_DEPTH = 4  # Mods/<mod>/<pack> is depth 2; allow a little extra nesting
SKIP_DIRS = {".git", "__pycache__", "library", "temp", "logs", "obj"}

STEAM_LOCOMOTIVE = "SteamLocomotive"
TENDER = "Tender"


def definition(obj: dict) -> dict:
    d = obj.get("definition")
    return d if isinstance(d, dict) else {}


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

    def as_dict(self) -> dict:
        return {"severity": self.severity, "code": self.code, "message": self.message}


@dataclass
class Pack:
    root: Root
    path: Path
    files: dict[str, Path]  # lower-cased known file name -> actual path
    objects: list[dict] = field(default_factory=list)
    assets: dict[str, dict] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def rel(self) -> str:
        rel = self.path.relative_to(self.root.path).as_posix()
        return "" if rel == "." else rel

    @property
    def mod(self) -> str:
        """Folder name directly above the pack, the prefix assetPackIdentifier uses."""
        parent = self.path.parent
        return parent.name if parent != self.path else ""

    def describe(self) -> dict:
        return {"name": self.name, "root": self.root.label, "path": self.rel}


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


def _find_packs(root: Root) -> Iterable[Path]:
    base_depth = len(root.path.parts)
    for current, dirs, files in os.walk(root.path, followlinks=False):
        here = Path(current)
        names = {f.casefold() for f in files}
        if DEFINITIONS in names or CATALOG in names:
            dirs[:] = []  # packs do not nest
            yield here
            continue
        if len(here.parts) - base_depth >= MAX_DEPTH:
            dirs[:] = []
        dirs[:] = sorted(d for d in dirs if d.casefold() not in SKIP_DIRS and not is_link(here / d))


def _pack_files(path: Path) -> dict[str, Path]:
    found = {}
    for entry in sorted(path.iterdir()):
        key = entry.name.casefold()
        if key in (DEFINITIONS, CATALOG, BUNDLE) and entry.is_file() and not entry.is_symlink():
            found[key] = entry
    return found


class Index:
    def __init__(self, input_path: Path, search_paths: Sequence[Path] = ()):
        self.roots = [Root(0, "input", input_path.resolve())]
        self.roots += [Root(i, f"search{i}", p.resolve()) for i, p in enumerate(search_paths, start=1)]
        self.packs: list[Pack] = []
        self.issues: list[Issue] = []
        self._objects: dict[str, list[tuple[Pack, dict]]] = defaultdict(list)
        self._packs_by_name: dict[str, list[Pack]] = defaultdict(list)
        seen: set[Path] = set()
        for root in self.roots:
            if not root.path.is_dir():
                sev = "error" if root.rank == 0 else "warning"
                self.issues.append(Issue(sev, "root-missing", f"{root.label} folder not found: {root.path}"))
                continue
            for path in _find_packs(root):
                resolved = path.resolve()
                if resolved in seen:  # e.g. input folder sits inside a search root
                    continue
                seen.add(resolved)
                self._load(Pack(root, path, _pack_files(path)))

    def _load(self, pack: Pack) -> None:
        where = f"{pack.root.label}:{pack.rel or '.'}"
        try:
            if DEFINITIONS in pack.files:
                objects = read_json_lenient(pack.files[DEFINITIONS]).get("objects", [])
                pack.objects = [o for o in objects if isinstance(o, dict) and isinstance(o.get("identifier"), str)]
            if CATALOG in pack.files:
                assets = read_json_lenient(pack.files[CATALOG]).get("assets", {})
                pack.assets = assets if isinstance(assets, dict) else {}
        except (SourceError, AttributeError) as e:
            sev = "error" if pack.root.rank == 0 else "warning"
            self.issues.append(Issue(sev, "pack-unreadable", f"{where}: {e}"))
            return
        self.packs.append(pack)
        self._packs_by_name[pack.name.casefold()].append(pack)
        for obj in pack.objects:
            self._objects[obj["identifier"]].append((pack, obj))

    # ---- lookups --------------------------------------------------------------------------------------

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
            narrowed = [p for p in candidates if p.mod.casefold() == segments[-2].casefold()]
            candidates = narrowed or candidates
        return _rank_pick(candidates, lambda p: p.root.rank)

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
    places = ", ".join(f"{p.root.label}:{p.rel}" for p in (c[0] if isinstance(c, tuple) else c for c in res.candidates))
    return f"{what} matches more than one pack at the same priority ({places}); remove the duplicate or pass it as the input"


def _external_refs(owner: str, component: dict) -> list[dict]:
    refs = []
    whistle = component.get("defaultWhistleIdentifier")
    if isinstance(whistle, str) and whistle:
        refs.append({"kind": "whistle", "id": whistle, "owner": owner})
    texture = component.get("textureName")
    if isinstance(texture, str) and texture:
        refs.append({"kind": "decal_texture", "id": texture, "owner": owner})
    return refs


def inventory(index: Index, loco_id: str, hash_files: bool = True) -> dict:
    """Dependency closure of one steam locomotive, as a deterministic JSON-ready dict."""
    issues: list[Issue] = []
    res = index.find_object(loco_id)
    if res.hit is None:
        code, msg = ("ambiguous", _ambiguous(f"locomotive {loco_id}", res)) if res.candidates else ("not-found", f"locomotive {loco_id} not found")
        return {"schema": 1, "locomotive": {"id": loco_id}, "issues": [Issue("error", code, msg).as_dict()]}
    loco_pack, loco = res.hit
    ldef = definition(loco)
    if ldef.get("kind") != STEAM_LOCOMOTIVE:
        issues.append(Issue("error", "not-steam", f"{loco_id} is {ldef.get('kind')!r}, not a steam locomotive"))

    packs: dict[Path, Pack] = {loco_pack.path: loco_pack}
    vehicles = [(loco_pack, loco)]  # objects whose models and parts we follow

    tender_info = None
    tender_id = ldef.get("tenderIdentifier")
    if isinstance(tender_id, str) and tender_id:
        tres = index.find_object(tender_id)
        if tres.hit:
            tpack, tender = tres.hit
            packs[tpack.path] = tpack
            vehicles.append((tpack, tender))
            tender_info = {"id": tender_id, "pack": tpack.describe()}
            if definition(tender).get("archetype") != TENDER:
                issues.append(Issue("warning", "tender-archetype", f"tender {tender_id} has archetype {definition(tender).get('archetype')!r}"))
        elif tres.candidates:
            issues.append(Issue("error", "ambiguous", _ambiguous(f"tender {tender_id}", tres)))
        else:
            issues.append(Issue("error", "missing-tender", f"tender {tender_id} not found in the input or search folders"))

    trucks = []
    for vpack, vehicle in list(vehicles):
        truck_id = definition(vehicle).get("truckIdentifier")
        if not (isinstance(truck_id, str) and truck_id):
            continue
        tres = index.find_object(truck_id)
        if tres.hit:
            tpack, truck = tres.hit
            packs[tpack.path] = tpack
            vehicles.append((tpack, truck))
            trucks.append({"id": truck_id, "owner": vehicle["identifier"], "pack": tpack.describe()})
        elif tres.candidates:
            issues.append(Issue("error", "ambiguous", _ambiguous(f"truck {truck_id}", tres)))
        else:
            issues.append(Issue("error", "missing-truck",
                                f"truck {truck_id} (used by {vehicle['identifier']}) not found; add the folder of the mod that provides it"))

    parts, external = [], []
    kinds: Counter = Counter()
    radial, toggles = [], []
    for vpack, vehicle in vehicles:
        vdef = definition(vehicle)
        model = vdef.get("modelIdentifier")
        if isinstance(model, str) and model and vpack.assets and model not in vpack.assets:
            issues.append(Issue("warning", "model-not-in-catalog", f"{vehicle['identifier']}: model {model!r} is not listed in {vpack.name}/Catalog.json"))
        is_car = vehicle is loco or (tender_info and vehicle["identifier"] == tender_info["id"])
        for comp in vdef.get("components", []) or []:
            if not isinstance(comp, dict):
                continue
            if is_car:
                kinds[str(comp.get("kind", "?"))] += 1
                if comp.get("kind") == "RadialControl":
                    radial.append({"owner": vehicle["identifier"], "purpose": comp.get("purpose"), "name": comp.get("name")})
                elif comp.get("kind") == "ToggleAnimation":
                    toggles.append({"owner": vehicle["identifier"], "name": comp.get("name")})
            external += _external_refs(vehicle["identifier"], comp)
            if comp.get("kind") != "PrefabModelComponent":
                continue
            m = comp.get("model") or {}
            pack_ident, asset_ident = m.get("assetPackIdentifier"), m.get("assetIdentifier")
            label = f"{vehicle['identifier']}/{comp.get('name')}"
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
            prefix = [s for s in pack_ident.replace("\\", "/").split("/") if s][:-1]
            if prefix and ppack.mod.casefold() != prefix[-1].casefold():
                issues.append(Issue("warning", "pack-folder-mismatch",
                                    f"{label}: {pack_ident!r} matched pack {ppack.root.label}:{ppack.rel} by name only (its mod folder is {ppack.mod!r})"))
            asset = ppack.assets.get(asset_ident)
            if not isinstance(asset, dict):
                issues.append(Issue("error", "missing-part-asset", f"{label}: asset {asset_ident!r} not in {ppack.name}/Catalog.json"))
                continue
            packs[ppack.path] = ppack
            parts.append({"owner": vehicle["identifier"], "component": comp.get("name"), "pack": ppack.name,
                          "asset": asset_ident, "filename": asset.get("filename"), "enabled": comp.get("enabled", True)})

    ordered = sorted(packs.values(), key=lambda p: (p.root.rank, p.rel))
    pack_records = []
    for p in ordered:
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

    unique_external = sorted({(r["kind"], r["id"], r["owner"]) for r in external})
    result = {
        "schema": 1,
        "locomotive": {"id": loco_id, "name": (loco.get("metadata") or {}).get("name"), "pack": loco_pack.describe()},
        "tender": tender_info,
        "trucks": trucks,
        "parts": parts,
        "packs": pack_records,
        "external_refs": [{"kind": k, "id": i, "owner": o} for k, i, o in unique_external],
        "controls": {"radial": radial, "toggles": toggles},
        "component_kinds": dict(sorted(kinds.items())),
        "issues": list({(i.severity, i.code, i.message): i.as_dict() for i in issues}.values()),
    }
    return result


def blocking(inv: dict) -> list[dict]:
    return [i for i in inv.get("issues", []) if i["severity"] == "error"]
