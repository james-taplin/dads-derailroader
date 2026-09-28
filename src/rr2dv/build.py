"""The `build` stage: complete the vehicle record, prepare the run's Unity project and build the CCL pack with our builder
core (tooling/builder/tools/unity, through LlwVehicleRecord.Build) in Unity 2019.4.

Inputs: the draft record, the probe's measurements and the run's own project (never the cached export). Outputs, all in
the run folder: build/vehicle-record.json (the record built from), build/review.json (every automatic choice, for
review), build/out/ (the core's build_report.txt, result.json, renders and the exported pack folder, plus prep.json
from Rr2dvBuild: bindings removed, AudioSources stripped, parts placed). A successful build is a candidate for runtime
checks, not an accepted pack (CTRL-01/CTRL-02).
"""
from __future__ import annotations

from pathlib import Path

from . import buildrecord, recordcheck, unityrun
from .jsonio import read_json, read_json_lenient, sha256_file, write_json
from .rrmod import components, definition

BUILD_INPUT = "Assets/Rr2dv/BuildInput.json"


class BuildError(RuntimeError):
    """The pack could not be built; the message says why and where to look."""


def definitions(run_path: Path, inv: dict) -> dict[str, dict]:
    """Each vehicle's staged definition, by identifier."""
    out: dict[str, dict] = {}
    for v in inv["vehicles"]:
        folder = run_path / "inputs" / v["pack"]["root"] / (v["pack"]["path"] or v["pack"]["name"])
        path = next((p for p in folder.iterdir() if p.name.casefold() == "definitions.json"), None)
        if path is None:
            continue
        objects = {o["identifier"]: o for o in read_json_lenient(path).get("objects", []) if isinstance(o, dict)}
        if v["id"] in objects:
            out[v["id"]] = definition(objects[v["id"]])
    return out


def _part_specs(owner: str, d: dict, parts: list[dict]) -> list[dict]:
    """Where Railroader places each part: its component's transform, under its parent path. A part anchored inside
    another part comes after it, so the parent exists when it is placed."""
    comps = {c.get("name"): c for c in components(d) if c.get("kind") == "PrefabModelComponent"}
    specs = []
    for p in parts:
        if p["owner"] != owner or p.get("enabled") is False:
            continue
        c = comps.get(p["component"]) or {}
        t = c.get("transform") or {}
        parent = c.get("parent") or {}
        specs.append({"name": p["component"], "parentPath": "/".join(parent.get("path", [])) if isinstance(parent, dict) else "",
                      "prefab": p["unity_prefab"], "position": t.get("position", [0, 0, 0]), "rotation": t.get("rotation", [0, 0, 0, 1]),
                      "scale": t.get("scale", [1, 1, 1])})
    names = {s["name"] for s in specs}
    ordered, placed = [], set()
    while specs:
        ready = [s for s in specs if (s["parentPath"].split("/")[0] not in names or s["parentPath"].split("/")[0] in placed)]
        if not ready:
            raise BuildError(f"{owner}: parts anchored inside each other in a loop: {', '.join(s['name'] for s in specs)}")
        for s in ready:
            ordered.append(s)
            placed.add(s["name"])
            specs.remove(s)
    return ordered


def prepare(run_path: Path, inv: dict, probe_in: dict, probe_out: dict | None, project: dict, draft: dict,
            answers: dict, absent: list[dict]) -> dict:
    """The record to build from and Rr2dvBuild's input. Raises buildrecord.Blocked when the record cannot be completed."""
    defs = definitions(run_path, inv)
    cars = {draft["vehicleId"]: draft["config"]["CarId"]}
    if draft.get("tender"):
        cars[inv["tender"]["id"]] = draft["tender"]["config"]["CarId"]
    composites, specs = {}, []
    for vid, car_id in cars.items():
        parts = _part_specs(vid, defs.get(vid, {}), project.get("parts", []))
        if not parts:
            continue
        source = next(v["unity_prefab"] for v in project["vehicles"] if v["id"] == vid)
        target = f"Assets/RR2DV/{car_id}/source/{vid}.prefab"
        composites[vid] = target
        specs.append({"vehicle": vid, "source": source, "target": target, "parts": parts})
    try:
        rec, choices = buildrecord.complete(draft, inv, probe_in, probe_out, project, answers, defs, composites)
    except buildrecord.Blocked as e:
        write_json(run_path / "build/review.json", {"status": "blocked", "choices": e.choices,
                   "pending": draft["metadata"]["pending"], "blocks": e.items})
        raise
    if answers.get('prebuildReview'):
        from . import review
        rec = review.apply(rec, answers['prebuildReview'])
    errors = recordcheck.check(rec)
    if errors:  # our own bug if it happens: the completed record must pass the loader's rules
        raise BuildError("the completed vehicle record breaks the loader's rules: " + "; ".join(errors[:5])
                         + (f" (+{len(errors) - 5} more)" if len(errors) > 5 else ""))
    build = run_path / "build"
    write_json(build / "vehicle-record.json", rec)
    write_json(build / "review.json", {"choices": choices, "pending": rec["metadata"]["pending"]})
    prefabs = sorted({v["unity_prefab"] for v in project.get("vehicles", [])} | {p["unity_prefab"] for p in project.get("parts", [])})
    clips = []
    for a in absent:
        asset = f"Assets/{a['clip']}" if a["export"] == "main" else f"Assets/{a['export']}/{a['clip']}"
        clips.append({"clip": asset, "hashes": a["absent"]})
    wheel_nodes = (rec.get("tender") or {}).get("metadata", {}).get("truckWheelNodes")
    data = {"schema": 1, "absentBindings": clips, "audioStrip": prefabs, "composites": specs, "review": answers.get("prebuildReview", {}).get("values"),
            "truckWheels": [wheel_nodes] if wheel_nodes else [],
            "reversedClips": rec["metadata"].get("reversedClips") or [],
            "noDynamo": bool(rec["metadata"].get("noDynamo"))}
    write_json(run_path / project["project"] / BUILD_INPUT, data)
    return {"record": rec, "choices": choices, "input": data}


def run(run_path: Path, unity: Path | None, project: dict, rec: dict) -> dict:
    """Build in Unity; returns the result with the pack folder and its files' hashes. Raises BuildError."""
    out = run_path / "build" / "out"
    env = {"CCL_VEHICLE_RECORD": str((run_path / "build" / "vehicle-record.json").resolve()), "CCL_BUILD_OUT": str(out.resolve()),
           "CCL_SHARE": "1",  # stock Derail Valley audio only; no custom sounds (James, W5)
           "CCL_NEW_LOCO": "0" if rec.get("tender") else "1",  # the core's new-loco gate supports tank locos only
           "CCL_CATALOG_RECORD": "", "RLW_BUILD_OUT": ""}
    result = unityrun.run_method(unity, run_path / project["project"], "Rr2dvBuild.Build", out, env)
    report = (out / "build_report.txt").read_text(encoding="utf-8", errors="replace") if (out / "build_report.txt").exists() else ""
    warnings = [line[5:] for line in report.splitlines() if line.startswith("WARN ")]
    prep = read_json(out / "prep.json") if (out / "prep.json").exists() else {}
    if prep.get("error"):
        raise BuildError("preparing the Unity project failed: " + prep["error"].splitlines()[0] + f" (see {out / 'prep.json'})")
    if not result.get("exported"):
        why = next((line for line in report.splitlines() if line.startswith("EXCEPTION") or "validation failed" in line), "")
        detail = next((line for line in report.splitlines()[1:3] if line.strip()), "") if "validation failed" in why else ""
        raise BuildError("the builder did not export a pack" + (f": {why[:400]}" if why else "")
                         + (f" {detail[:300]}" if detail else "") + f" (see {out / 'build_report.txt'})")
    name = rec["config"]["CarName"]
    pack = out / name
    if not (pack / "Info.json").is_file():
        raise BuildError(f"the builder reported an export but {pack} has no Info.json")
    files = {f.name: sha256_file(f) for f in sorted(pack.iterdir()) if f.is_file()}
    return {"exported": True, "warnings": warnings, "pack": str(pack), "files": files, "prep": prep,
            "unity": {k: result.get(k) for k in ("exit_code", "warnings", "runtimeValidated")}}
