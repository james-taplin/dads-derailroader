"""Read-only index of Railroader's own asset packs and the dependency closure of one stock steam locomotive.

An asset pack is a folder with Definitions.json and/or Catalog.json plus a `bundle`. Objects in Definitions.json
reference each other by identifier (tender, truck) and reference assets in other packs through PrefabModelComponent
models. This module finds every pack a stock steam locomotive needs, from the input pack first and then from the search
roots (Railroader's asset packs). Every dependency found is used; only a part broken in its own pack is left out.
Nothing here writes to disk.

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
from . import attribution, stock
from .safety import is_link

DEFINITIONS = "definitions.json"
CATALOG = "catalog.json"
BUNDLE = "bundle"
MAX_DEPTH = 4  # AssetPacks/<pack> is depth 1; allow a little extra nesting
SKIP_DIRS = {".git", "__pycache__", "library", "temp", "logs", "obj"}

STEAM_LOCOMOTIVE = "SteamLocomotive"
TENDER = "Tender"

# Audio is never converted: every sound (whistle, bell, chuff, pumps...) aliases to vanilla Derail Valley S060 or
# S282 audio, chosen by boiler size. Heating surface below the cut-off counts as a small boiler.
AUDIO_BASES = ("S060", "S282")
SMALL_BOILER_MAX_HEATING_FT2 = 1500.0  # ~32,000 lbf tank (GWR 7200: ~1,478 ft2) = S060; USRA 0-6-0 tender (1,886 ft2) = S282
SOUND_KINDS = {"Whistle", "Bell", "Chuff", "Compressor", "Dynamo"}

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
    return _real_main_driver(d) if isinstance(d, dict) else {}


def _phantom(ws: dict) -> bool:
    """A wheelset with no animation clip and no model part: nothing in the model turns or stands for it."""
    return not (ws.get("animation") or {}).get("clipName") and not (ws.get("transform") or {}).get("path")


def _real_main_driver(d: dict) -> dict:
    """ALCo 3-cylinder Mikado (2026-09-28): mainDriverIndex names a wheelset with no clip and no model part (4 axles over
    the same 5.2 m as the animated 'Drivers' wheelset). When exactly one animated wheelset has the same axle count over
    an overlapping span, it is the main driver and the phantom is dropped; the change is noted in rr2dvWheelsetNotes."""
    sets = d.get("wheelsets")
    main = d.get("mainDriverIndex", 0)
    if not isinstance(sets, list) or not isinstance(main, int) or not 0 <= main < len(sets) or not isinstance(sets[main], dict):
        return d
    ghost = sets[main]
    if not _phantom(ghost):
        return d
    def overlaps(ws):
        span = (float(ws.get("length") or 0) + float(ghost.get("length") or 0)) / 2
        return abs(float(ws.get("offset") or 0) - float(ghost.get("offset") or 0)) < max(span, 0.5)
    twins = [i for i, ws in enumerate(sets) if i != main and isinstance(ws, dict) and not _phantom(ws)
             and ws.get("numberOfAxles") == ghost.get("numberOfAxles") and overlaps(ws)]
    if len(twins) != 1:
        return d
    real = twins[0]
    kept = [ws for i, ws in enumerate(sets) if i != main]
    twin = sets[real]
    name = (twin.get("animation") or {}).get("clipName") or "/".join((twin.get("transform") or {}).get("path") or [])
    note = (f"main driver wheelset {main} (diameter {ghost.get('diameter')} m, {ghost.get('numberOfAxles')} axles) has no "
            f"animation and no model part; wheelset {real} ({name!r}, diameter {twin.get('diameter')} m, same axles and "
            "span) is used as the main driver and the empty one is left out")
    return {**d, "wheelsets": kept, "mainDriverIndex": real - (1 if real > main else 0),
            "rr2dvWheelsetNotes": list(d.get("rr2dvWheelsetNotes") or []) + [note]}


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


GAME_DATA = "railroader_data"  # Railroader's own asset packs live under Railroader_Data/StreamingAssets/AssetPacks


def _rel(root: Root, path: Path) -> str:
    rel = path.relative_to(root.path).as_posix()
    return "" if rel == "." else rel


@dataclass
class Pack:
    root: Root
    path: Path
    files: dict[str, Path]  # lower-cased known file name -> actual path
    objects: list[dict] = field(default_factory=list)
    assets: dict[str, dict] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)  # lower-cased file name -> why it could not be read

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def rel(self) -> str:
        return _rel(self.root, self.path)

    def describe(self) -> dict:
        return {"name": self.name, "root": self.root.label, "path": self.rel}

    def model_prefab(self, model: str) -> str:
        """Prefab file name for a model identifier: the catalogue entry's file, else "<model>.prefab"."""
        asset = self.assets.get(model)
        name = asset["filename"] if isinstance(asset, dict) and isinstance(asset.get("filename"), str) else model
        # some catalogues give the file without its extension (e.g. "truck.usra-andrews70t"); dots in ids are not one
        return name if name.casefold().endswith(".prefab") else name + ".prefab"

    def has_model(self, model: str) -> bool:
        """A model identifier names a catalogue key or a prefab file (LLW uses one string for both; others don't)."""
        if model in self.assets:
            return True
        stems = {Path(str(a.get("filename", ""))).stem.casefold() for a in self.assets.values() if isinstance(a, dict)}
        return model.casefold() in stems


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
        self.issues: list[Issue] = []
        self._objects: dict[str, list[tuple[Pack, dict]]] = defaultdict(list)
        self._packs_by_name: dict[str, list[Pack]] = defaultdict(list)
        seen: set[Path] = set()
        for root in self.roots:
            if not root.path.is_dir():
                sev = "error" if root.rank == 0 else "warning"
                self.issues.append(Issue(sev, "root-missing", f"{root.label} folder not found: {root.path}"))
                continue
            for folder, files, is_pack in _walk(root):
                resolved = folder.resolve()
                if resolved in seen:  # the input pack sits inside the asset packs search root
                    continue
                seen.add(resolved)
                if is_pack:
                    self._load_pack(root, folder, files)

    # ---- loading ------------------------------------------------------------------------------------------

    def _load_pack(self, root: Root, folder: Path, files: list[str]) -> None:
        pack = Pack(root, folder, _known_files(folder, files))
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

    # ---- lookups --------------------------------------------------------------------------------------

    def unreadable_definitions(self, max_rank: int | None = None) -> list[Pack]:
        return [p for p in self.packs if DEFINITIONS in p.errors and (max_rank is None or p.root.rank <= max_rank)]

    def find_object(self, identifier: str) -> Resolution:
        return _rank_pick(self._objects.get(identifier, []), lambda po: po[0].root.rank)

    def find_pack(self, pack_identifier: str) -> Resolution:
        """assetPackIdentifier names the pack folder (Railroader's own packs use the bare pack name); a path-like
        identifier is matched on its last segment."""
        segments = [s for s in pack_identifier.replace("\\", "/").split("/") if s]
        if not segments:
            return Resolution()
        return _rank_pick(self._packs_by_name.get(segments[-1].casefold(), []), lambda p: p.root.rank)

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


def _model_credit_fields(pack: Pack, model: str) -> list[tuple]:
    """Only definitions/catalogue entries matching the selected model, not its whole pack."""
    fields = []
    for obj in pack.objects:
        d = definition(obj)
        ref = d.get('modelIdentifier') or (d.get('model') or {}).get('assetIdentifier')
        if obj['identifier'] == model or (ref == model and d.get('kind') not in
                {'Whistle', 'SteamLocomotive', 'DieselLocomotive', 'Car', 'Truck'}):
            meta = obj.get('metadata') or {}
            fields.append((meta.get('credits'), meta.get('name') or obj['identifier']))
    for key, asset in pack.assets.items():
        if isinstance(asset, dict) and (key == model or Path(str(asset.get('filename', ''))).stem.casefold() == Path(model).stem.casefold()):
            meta = asset.get('metadata') or {}
            fields.append((meta.get('credits') or asset.get('credits'), meta.get('name') or asset.get('name') or key))
    return fields


def _whistle_credit(index: Index, pack: Pack, obj: dict) -> dict:
    meta = obj.get('metadata') or {}
    model = definition(obj).get('model') or {}
    mpack = pack
    if model.get('assetPackIdentifier'):
        found = index.find_pack(model['assetPackIdentifier'])
        mpack = found.hit
    fields = [(meta.get('credits'), meta.get('name') or obj['identifier'])]
    if mpack and isinstance(model.get('assetIdentifier'), str):
        fields += _model_credit_fields(mpack, model['assetIdentifier'])
    return attribution.content(obj['identifier'], meta.get('name'), 'whistle definition and mesh',
                               pack.name, fields)


def whistle_options(index: Index) -> list[dict]:
    """Every whistle Railroader offers (objects of kind Whistle), by identifier: {id, name, model, audio}."""
    out = []
    for pack, obj in index.objects_of_kind("Whistle"):
        d = definition(obj)
        model, audio = d.get("model") or {}, d.get("audio") or {}
        out.append({"id": obj["identifier"], "name": (obj.get("metadata") or {}).get("name") or obj["identifier"],
                    "model": model.get("assetIdentifier"), "audio": audio.get("assetIdentifier"),
                    "contentCredit": _whistle_credit(index, pack, obj)})
    return sorted(out, key=lambda o: o["id"])


def _whistle(index: Index, loco_id: str, ldef: dict, chosen: str | None, packs: dict, parts: list, left_out: list,
             issues: list) -> dict:
    comp = next((c for c in components(ldef) if c.get("kind") == "Whistle"), None)
    source, wanted = "default", stock.DEFAULT_WHISTLE
    named = comp.get("defaultWhistleIdentifier") if comp else None
    if isinstance(named, str) and named:
        source, wanted = "definition", named
    if chosen:
        source, wanted = "option", chosen
    info = {"id": wanted, "source": source, "component": comp.get("name") if comp else None, "model": None, "audio": None,
            "name": None, "placed": False, "enabled": comp is not None and comp.get('enabled', True), "options": whistle_options(index)}
    if comp is None:
        issues.append(Issue("warning", "no-whistle-component", f"{loco_id} has no Whistle component; no whistle mesh is placed"))
        return info

    def leave_out(reason: str) -> dict:
        left_out.append({"what": "whistle", "owner": loco_id, "component": comp.get("name"), "asset": wanted, "reason": reason,
                         "effect": "no whistle mesh", "anchored": []})
        issues.append(Issue("warning" if source != "option" else "error", "whistle-left-out" if source != "option" else "unknown-whistle",
                            f"{loco_id}: whistle {wanted!r} {reason}" + ("" if source == "option" else "; no whistle mesh is placed")))
        return info

    res = index.find_object(wanted)
    if res.hit is None:
        return leave_out("was not found among Railroader's whistles")
    wpack, wobj = res.hit
    d = definition(wobj)
    if d.get("kind") != "Whistle":
        return leave_out(f"is a {d.get('kind')!r}, not a whistle")
    model, audio = d.get("model") or {}, d.get("audio") or {}
    info.update(name=(wobj.get("metadata") or {}).get("name") or wanted, model=model.get("assetIdentifier"), audio=audio.get("assetIdentifier"))
    pack_ident, asset_ident = model.get("assetPackIdentifier"), model.get("assetIdentifier")
    mpack = wpack  # an empty pack identifier names the whistle's own pack
    if isinstance(pack_ident, str) and pack_ident:
        pres = index.find_pack(pack_ident)
        if pres.hit is None:
            return leave_out(f"needs pack {pack_ident!r}, which was not found")
        mpack = pres.hit
    asset = mpack.assets.get(asset_ident) if isinstance(asset_ident, str) else None
    if not isinstance(asset, dict) or not isinstance(asset.get("filename"), str):
        return leave_out(f"has model {asset_ident!r}, which is not in {mpack.name}/Catalog.json")
    packs[wpack.path] = wpack
    packs[mpack.path] = mpack
    parts.append({"owner": loco_id, "component": "Whistle mesh", "source_component": comp.get("name"), "whistle": wanted,
                  "pack": mpack.name, "pack_ref": mpack.describe(), "asset": asset_ident, "filename": asset["filename"],
                  "enabled": comp.get("enabled", True)})
    info["placed"] = True
    info['contentCredit'] = _whistle_credit(index, wpack, wobj)
    return info


def inventory(index: Index, loco_id: str, hash_files: bool = True, audio: str | None = None, whistle: str | None = None) -> dict:
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

    # Every dependency in the user's own install is used (W25). Only a part broken in its own pack is left out, and
    # listed with what it takes with it. (Replacing dependencies with vanilla DV content is parked:
    # docs/later-dependency-replacement.md.)
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
            issues.append(Issue("error", "missing-tender", f"tender {tender_id} not found in the input or Railroader's asset packs" + _unreadable_hint(index)))

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
                                f"truck {truck_id} (used by {vehicle['identifier']}) not found in Railroader's asset packs"
                                + _unreadable_hint(index)))

    car_ids = {loco_id} | ({tender_info["id"]} if tender_info else set())
    parts = []
    sounds: set[str] = set()
    kinds: Counter = Counter()
    radial, toggles = [], []

    vehicle_records = []
    content_credits = []
    for vpack, vehicle in vehicles:
        vdef = definition(vehicle)
        vid = vehicle["identifier"]
        model = vdef.get("modelIdentifier")
        if isinstance(model, str) and model and vpack.assets and not vpack.has_model(model):
            issues.append(Issue("warning", "model-not-in-catalog", f"{vid}: model {model!r} matches no key or prefab in {vpack.name}/Catalog.json"))
        role = "locomotive" if vehicle is loco else "tender" if tender_info and vid == tender_info["id"] else "truck"
        if isinstance(model, str) and model:
            vehicle_records.append({"id": vid, "role": role, "model": model, "prefab": vpack.model_prefab(model), "pack": vpack.describe(),
                                    "credits": str((vehicle.get("metadata") or {}).get("credits") or "").strip()})
            meta = vehicle.get('metadata') or {}
            content_credits.append(attribution.content(vid, meta.get('name'), role+' model', vpack.name,
                [(meta.get('credits'), meta.get('name') or vid)] + _model_credit_fields(vpack, model)))
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
            if CATALOG in ppack.errors:
                packs[ppack.path] = ppack  # reported as pack-unreadable below
                continue
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
            if comp.get('enabled', True):
                content_credits.append(attribution.content(vid+'/'+str(comp.get('name')), comp.get('name') or asset_ident,
                    'part model', ppack.name, _model_credit_fields(ppack, asset_ident)))

    # The whistle: an optional Railroader mesh (a model in the whistle pack) placed at the locomotive's Whistle component,
    # chosen by the user, else the definition's defaultWhistleIdentifier, else the stock default. Its mesh is placed like
    # any part; a whistle that cannot be found is left out and listed, never a block.
    whistle_info = _whistle(index, loco_id, ldef, whistle, packs, parts, left_out, issues)
    if whistle_info.get('placed') and whistle_info['enabled']:
        content_credits.append(whistle_info['contentCredit'])

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

    # Source provenance for the notice and SOURCE_PROVENANCE.txt: everything used comes from Railroader's own asset packs.
    sources = [attribution.source(content_credits, sorted(p.rel or p.path.name for p in ordered))]

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
        "whistle": whistle_info,
        "left_out": left_out,
        "packs": pack_records,
        "sources": sources,
        "audio": {"source": "vanilla Derail Valley", **audio_choice},
        "controls": {"radial": radial, "toggles": toggles},
        "component_kinds": dict(sorted(kinds.items())),
        "issues": list({(i.severity, i.code, i.message): i.as_dict() for i in issues}.values()),
    }


def blocking(inv: dict) -> list[dict]:
    """Errors that stop a conversion."""
    return [i for i in inv.get("issues", []) if i["severity"] == "error"]
