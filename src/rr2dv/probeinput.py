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
        vehicles.append({"id": v["id"], "role": v["role"], "prefab": v["unity_prefab"], "wheelsets": wheelsets,
                         "components": comps, "animationMap": maps["clip"], "materialMap": maps["material"]})
    data = {"schema": 1, "vehicles": vehicles, "missing": missing}
    write_json(project / INPUT_ASSET, data)
    return data
