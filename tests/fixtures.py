"""Synthetic Railroader mods for tests. Shapes follow real Definitions.json/Catalog.json fields; contents are made up."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def write_pack(folder: Path, objects=None, assets=None, bundle: bytes | None = b"bundle-bytes",
               bundle_name: str = "bundle", trailing_commas: bool = False) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    if objects is not None:
        text = json.dumps({"objects": objects}, indent=2)
        if trailing_commas:  # Railroader tolerates these; so must we
            text = text.replace("\n  ]\n}", ",\n  ],\n}")
        (folder / "Definitions.json").write_text(text, encoding="utf-8")
    if assets is not None:
        (folder / "Catalog.json").write_text(json.dumps({"assets": assets}), encoding="utf-8")
    if bundle is not None:
        (folder / bundle_name).write_bytes(bundle + folder.name.encode())
    return folder


def part(pack_identifier: str, asset: str, name: str) -> dict:
    return {"kind": "PrefabModelComponent", "model": {"assetPackIdentifier": pack_identifier, "assetIdentifier": asset},
            "name": name, "transform": {"position": [0, 0, 0], "rotation": [0, 0, 0, 1], "scale": [1, 1, 1]},
            "parent": None, "enabled": True}


def loco(ident: str, tender: str = "", truck: str = "", parts=(), kind: str = "SteamLocomotive", whistle: str | None = "wh-test",
         heating_surface: float | None = 1500.0, extra_components=()) -> dict:
    components = [
        {"kind": "RadialControl", "purpose": "Throttle", "name": "Throttle", "animation": {"clipName": "Throttle"}},
        {"kind": "RadialControl", "purpose": "Reverser", "name": "Reverser", "animation": {"clipName": "Reverser"}},
        {"kind": "ToggleAnimation", "name": "Cab Door Left"},
        *parts,
    ]
    if whistle:
        components.append({"kind": "Whistle", "defaultWhistleIdentifier": whistle, "name": "Whistle"})
    components += list(extra_components)
    d = {"kind": kind, "archetype": "LocomotiveSteam", "modelIdentifier": ident,
         "tenderIdentifier": tender, "truckIdentifier": truck, "components": components}
    if heating_surface is not None:
        d["totalHeatingSurface"] = heating_surface
    return {"identifier": ident, "metadata": {"name": f"Test {ident}"}, "definition": d}


def tender(ident: str, truck: str = "") -> dict:
    return {"identifier": ident, "metadata": {"name": f"Test {ident}"},
            "definition": {"kind": "Car", "archetype": "Tender", "modelIdentifier": ident, "truckIdentifier": truck,
                           "components": [{"kind": "ToggleAnimation", "name": "Water Hatch"}]}}


def truck(ident: str) -> dict:
    return {"identifier": ident, "definition": {"kind": "Truck", "modelIdentifier": ident, "components": []}}


def standard_mod(base: Path) -> dict:
    """A tender loco with one part in a second pack, whose trucks live in a separate mod (search root)."""
    mod = base / "input" / "Test Loco Mod"
    mod.mkdir(parents=True)
    (mod / "info.json").write_text('{"id": "test-loco-mod"}', encoding="utf-8")
    write_pack(mod / "ts-260-a",
               objects=[loco("ts-260-a", tender="tt-260-a", parts=[part("Test Loco Mod\\parts", "bell", "bell1")]),
                        tender("tt-260-a", truck="test-truck-2s")],
               assets={"ts-260-a": {"filename": "ts-260-a.prefab"}, "tt-260-a": {"filename": "tt-260-a.prefab"}},
               trailing_commas=True)
    write_pack(mod / "parts", assets={"bell": {"filename": "bell.prefab"}})
    search = base / "rrmods"
    write_pack(search / "TruckMod" / "Trucks", objects=[truck("test-truck-2s")],
               assets={"test-truck-2s": {"filename": "Test-Truck-2s.prefab"}}, bundle_name="Bundle")
    return {"mod": mod, "search": search}


def tree_state(root: Path) -> dict:
    """Every file under root with its hash and modification time, to prove nothing was written."""
    state = {}
    for current, _, files in os.walk(root):
        for name in files:
            p = Path(current) / name
            state[p.relative_to(root).as_posix()] = (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
    return state
