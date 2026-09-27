"""Build the probe's input: what to measure, for every vehicle, as data the Unity probe can read.

Railroader keeps a model's clip and material maps in its own components on the prefab. Their scripts are not in our
project (board X27), so the maps are read here from the prefab YAML, the same way our gen_defs.py reads them, and
resolved to project asset paths through the .meta GUIDs. Wheelsets and components come from the staged
Definitions.json. Nothing is guessed: an unresolvable reference is listed as missing for the probe to report.
"""
from __future__ import annotations

import re
from pathlib import Path

from .jsonio import read_json_lenient, write_json
from .rrmod import components, definition

MAP_ENTRY = {
    "material": re.compile(r"- name: (.+)\n\s+material: \{fileID: -?\d+, guid: (\w+)"),
    "clip": re.compile(r"- name: (.+)\n\s+clip: \{fileID: -?\d+, guid: (\w+)"),
}
INPUT_ASSET = "Assets/Rr2dv/ProbeInput.json"


def guid_paths(project: Path) -> dict[str, str]:
    assets = project / "Assets"
    out = {}
    for meta in assets.rglob("*.meta"):
        m = re.search(r"^guid: (\w+)", meta.read_text(encoding="utf-8-sig", errors="replace"), re.M)
        if m:
            out[m[1]] = "Assets/" + meta.relative_to(assets).as_posix()[:-5]
    return out


def prefab_maps(prefab: Path, guids: dict[str, str]) -> dict[str, list[dict]]:
    text = prefab.read_text(encoding="utf-8-sig", errors="replace")
    maps = {}
    for kind, rx in MAP_ENTRY.items():
        maps[kind] = [{"key": name.strip(), "asset": guids.get(g, ""), "guid": g} for name, g in rx.findall(text)]
    return maps


CAB_RAY_STEP = 0.1       # m between rays
CAB_RAY_HALF_WIDTH = 1.0  # rays across x -1..1 m
CAB_RAY_BELOW, CAB_RAY_ABOVE = 0.4, 1.6  # around the firebed height, up the backhead
CAB_RAY_LENGTH = 3.0


def _grid(lo: float, hi: float) -> list[float]:
    n = int(round((hi - lo) / CAB_RAY_STEP))
    return [round(lo + i * CAB_RAY_STEP, 3) for i in range(n + 1)]


def cab_spec(comps: list[dict]) -> dict | None:
    """Where the probe looks for the backhead: rays forward from the crew seats (else 1 m behind the rearmost firebox
    glow) across the cab, from just under the firebed up the backhead. Only car-space components (no parent) count."""
    free = [c for c in comps if not c["parentPath"]]
    seats = [c["position"] for c in free if c["kind"] == "Seat"]
    fire = [c["position"] for c in free if c["kind"] == "FireboxEffect"]
    fire_rear = min(fire, key=lambda p: p[2]) if fire else None
    start = min(s[2] for s in seats) if seats else (fire_rear[2] - 1.0 if fire_rear else None)
    ref_y = fire_rear[1] if fire_rear else (min(s[1] for s in seats) - 0.5 if seats else None)
    if start is None or ref_y is None:
        return None
    return {"startZ": round(start, 4), "length": CAB_RAY_LENGTH, "xs": _grid(-CAB_RAY_HALF_WIDTH, CAB_RAY_HALF_WIDTH),
            "ys": _grid(round(ref_y - CAB_RAY_BELOW, 2), round(ref_y + CAB_RAY_ABOVE, 2)),
            "basis": "seats" if seats else "firebox effects"}


def _vec(values, default):
    return [float(v) for v in values] if isinstance(values, list) and len(values) == len(default) else list(default)


def build(run_path: Path, inv: dict, project_info: dict) -> dict:
    project = run_path / project_info["project"]
    guids = guid_paths(project)
    defs_cache: dict[Path, dict] = {}

    def definition_of(vehicle: dict) -> dict:
        pack = vehicle["pack"]
        folder = run_path / "inputs" / pack["root"] / (pack["path"] or pack["name"])
        path = next((p for p in folder.iterdir() if p.name.casefold() == "definitions.json"), None)
        if path is None:
            return {}
        if path not in defs_cache:
            defs_cache[path] = {o["identifier"]: o for o in read_json_lenient(path).get("objects", []) if isinstance(o, dict)}
        return definition(defs_cache[path].get(vehicle["id"], {}))

    vehicles, missing = [], []
    for v in project_info["vehicles"]:
        d = definition_of(v)
        maps = prefab_maps(project / v["unity_prefab"], guids)
        clips = {e["key"]: e["asset"] for e in maps["clip"]}
        for kind in ("clip", "material"):
            missing += [f"{v['id']}: {kind} {e['key']!r} (guid {e['guid']}) not in project" for e in maps[kind] if not e["asset"]]
        wheelsets = []
        for w in d.get("wheelsets", []) or []:
            clip = ((w.get("animation") or {}).get("clipName") or "")
            if clip and clip not in clips:
                missing.append(f"{v['id']}: wheelset clip {clip!r} is not in the prefab's clip map")
            wheelsets.append({"clip": clip, "clipAsset": clips.get(clip, ""), "diameter": float(w.get("diameter", 0) or 0),
                              "offset": float(w.get("offset", 0) or 0), "length": float(w.get("length", 0) or 0),
                              "axles": int(w.get("numberOfAxles", 0) or 0)})
        comps = []
        for c in components(d):
            t = c.get("transform") or {}
            parent = c.get("parent") or {}
            clip = ((c.get("animation") or {}).get("clipName") or "")
            comps.append({"kind": str(c.get("kind", "")), "name": str(c.get("name", "")), "purpose": str(c.get("purpose", "") or ""),
                          "parentPath": "/".join(parent.get("path", [])) if isinstance(parent, dict) else "",
                          "position": _vec(t.get("position"), [0.0, 0.0, 0.0]), "rotation": _vec(t.get("rotation"), [0.0, 0.0, 0.0, 1.0]),
                          "scale": _vec(t.get("scale"), [1.0, 1.0, 1.0]),
                          "clip": clip, "clipAsset": clips.get(clip, "")})
        cab = cab_spec(comps) if v["role"] == "locomotive" else None
        vehicles.append({"id": v["id"], "role": v["role"], "prefab": v["unity_prefab"], "wheelsets": wheelsets,
                         "components": comps, "animationMap": maps["clip"], "materialMap": maps["material"],
                         **({"cab": cab} if cab else {})})
    data = {"schema": 1, "vehicles": vehicles, "missing": missing}
    write_json(project / INPUT_ASSET, data)
    return data
