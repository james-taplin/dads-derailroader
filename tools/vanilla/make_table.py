"""Builds src/rr2dv/stock_locos.json, the per-locomotive table of the vanilla edition (one entry per stock steam loco).

Everything in the table is either copied from Railroader's own definitions, measured (the Codex bulk runs of 2026-09-30:
docs/stock-measurements.md) or an explicit decision by James; each entry says which. Run it after a new Railroader build
or new measurements, review the diff, commit the result. Usage:

  python tools/vanilla/make_table.py --railroader <Railroader folder> --hashes game-hashes.json --bulk <unzipped vf_bulk.zip> \
      [--out src/rr2dv/stock_locos.json]
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from rr2dv import stock  # noqa: E402

GAME_BUILD = "20238526"
MEASURED = "Codex bulk measurement run 2026-09-30 (docs/stock-measurements.md)"

# What happened when each loco was converted with this edition (run logs and build reports James sent, 2026-09-30).
# Status is "untested" until a run exists; nothing here is in-game acceptance.
OBSERVED = {
    "ls-282-k28t": {"status": "converted", "audit": "passed", "oilCupPairs": 1, "notes": [
        "big-end pair placed; small-end pair dropped (something visible above the crosshead end)",
        "5 gauges placed next to model parts (nearest part 0.04-0.08 m)", "17 generated backhead controls"]},
    "ls-060-s23": {"status": "converted", "audit": "passed", "oilCupPairs": 1, "notes": [
        "round 1: LOD meshes counted as geometry: main rod found as the LOD2 copy, small end blocked by Cab_1_LOD3, right number plate unsupported",
        "round 2 (LOD0-only queries): main rods are LOD0, both plates placed; small end still blocked (Cab_1_LOD0 above the crosshead end)",
        "tender brake release: no seat found (10 warnings) in both rounds, rod left pointing sideways; not a LOD problem; skin-profile diagnostic added",
        "speedometer generated beside the DRME gauge (same angled panel); 28 + 14 + 24 material slots took the fallback"]},
    "ls-440-a23": {"status": "converted", "audit": "passed", "oilCupPairs": 1, "notes": [
        "no LOD meshes; small-end pair blocked by real geometry (Driversnstuff_003_low)", "throttle and whistle handles do not move their own part: generated levers",
        "gauges report no nearest model part (dials are part of one large mesh)"]},
    "ls-462-p48": {"status": "converted", "audit": "passed", "oilCupPairs": 1, "notes": [
        "big end: no level spot on the rod; small end blocked; one running-board pair placed instead",
        "round 2: Quadruplex built as DV's main-reservoir/equalizing gauge, brake-cylinder gauge generated 0.33 m beside it: the HUD now has brake pipe, cylinder and main reservoir readings",
        "front doors left out (overlap another moving assembly)", "tender brake release: no seat found in both rounds", "coupling: no draw-gear part meets the other car (96 mm)"]},
    "ls-282-k35": {"status": "converted", "audit": "not seen", "oilCupPairs": 1, "notes": [
        "big-end pair placed; small end blocked by the piston above the crosshead end", "end beam: the core's automatic height search resolved the ambiguity (band 0.20..0.40 m, front)",
        "no brake or speed gauge in the model and both boiler gauges face sideways: the first build generated the three missing gauges along the car axis beside the boiler "
        "(floating); now generated on the backhead plate facing the crew (untested)", "tender brake release seated"]},
    "ls-284-b65": {"status": "converted", "audit": "passed", "oilCupPairs": 1, "notes": [
        "first run stopped at the tender end beam (ambiguous); James accepted the proposed band 1.00..1.20 m",
        "loco and tender bodies overlap in 38 cells (worst -204 mm): check the join in game", "tender brake release seated"]},
}

# The end-beam band James accepted for a tender (board 2026-09-30), keyed by the tender's vehicle id.
END_BEAM = {
    "ls-284-b65": {"lt-284-b65": {
        "band": [1.0, 1.2],
        "evidence": ["rr2dv end-beam survey, run 20260930-210241-ls-284-b65-540f18: rear, band 1.00..1.20 m, 31/65 rays on one face at z -6.936 "
                     "(4 left / 4 right of 0.3 m; Tender_LOD0), +0.064 m from the source car end -7.000; the same plane at 1.20..1.40 m: z -6.936, 7 rays",
                     "the broader face at z -6.858 (48 rays, 24 left / 24 right) lies 8 cm further in; accepted by James 2026-09-30 after the first run stopped"]}},
}


# Meshes left out of the pack (bespoke, James 2026-09-30). K-35's bell cords are skinned planes that ran out to infinity in game
# (three planes on one 20-bone chain); the bell itself, its lever and its sound are unaffected. Temporary: the build report's
# "rr2dv skinned" lines measure every skinned mesh so the cause can be found and the cords restored.
HIDE = {
    "ls-282-k35": [{"path": "engine/Plane.010", "why": "bell cord (skinned, bone chain Bone.013): stretched to infinity in game"},
                   {"path": "engine/Plane.024", "why": "bell cord (skinned, bone chain Bone.013): stretched to infinity in game"},
                   {"path": "engine/Plane.017", "why": "bell cord (skinned, bone chain Bone.013): stretched to infinity in game"}],
}


def load_definitions(packs: Path, name: str) -> dict:
    raw = re.sub(r",(\s*[}\]])", r"\1", (packs / name / "Definitions.json").read_text(encoding="utf-8-sig"))
    return {o["identifier"]: o for o in json.loads(raw)["objects"]}


def whyte(loco: dict) -> str:
    """Whyte notation from the wheelsets: leading wheels - driving wheels - trailing wheels (0 when a group is absent)."""
    sets = loco["wheelsets"]
    main = sets[loco["mainDriverIndex"]]
    lead = sum(int(w["numberOfAxles"]) * 2 for w in sets if w["offset"] > main["offset"] + .01)
    trail = sum(int(w["numberOfAxles"]) * 2 for w in sets if w["offset"] < main["offset"] - .01)
    return f"{lead}-{int(main['numberOfAxles']) * 2}-{trail}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--railroader", required=True)
    ap.add_argument("--hashes", required=True)
    ap.add_argument("--bulk", required=True, help="the unzipped vf_bulk.zip")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "src" / "rr2dv" / "stock_locos.json"))
    a = ap.parse_args()
    packs = Path(a.railroader) / "Railroader_Data" / "StreamingAssets" / "AssetPacks"
    hashes = json.loads(Path(a.hashes).read_text())
    bulk = Path(a.bulk) / "results"
    whistles = load_definitions(packs, stock.WHISTLE_PACK)
    out: dict = {}
    for pack, display in stock.STEAM.items():
        objs = load_definitions(packs, pack)
        loco = next(o["definition"] for o in objs.values() if o["definition"]["kind"] == "SteamLocomotive")
        tender = objs.get(loco.get("tenderIdentifier") or "")
        comps = [c for c in loco["components"] if c.get("enabled", True)]
        main = loco["wheelsets"][loco["mainDriverIndex"]]
        measure = json.loads((bulk / pack / "vf-measure.json").read_text())
        ve = next(v for v in measure["vehicles"] if v["role"] == "locomotive")
        probe = json.loads((bulk / pack / "probe__probe.json").read_text())
        pv = next(v for v in probe["vehicles"] if v["role"] == "locomotive")
        backhead = statistics.median(r["z"] for r in pv["cabRays"] if r.get("hit"))
        tips = sorted({round((x["maxRadius"] - main["diameter"] / 2) * 1000) for x in ve["axles"]
                       if x["bands"] and abs(x["lowestY"]) < .06 and abs(x["pivotAboveLowest"] - x["maxRadius"]) < .01 and x["clip"] == main["animation"]["clipName"]})
        hull = [l for h in ve["hulls"] if h["path"].lower() == "collision" for l in h["levels"]
                if l["areaUp"] >= .5 and .6 <= l["y"] <= 2.5 and l["xMax"] - l["xMin"] >= 1.4 and l["zMax"] >= backhead - 2 and l["zMin"] <= backhead - .3]
        confined = [l for l in hull if l["zMax"] <= backhead + .6]
        best = max(confined or hull, key=lambda l: l["areaUp"])
        styles = sorted({json.loads(json.dumps(c)).get("style") for c in comps if c["kind"] == "Gauge"})
        normal = {"BoilerPressure", "DualBrakeCylinderLine", "DualReservoirMainEq", "Speedometer100"}
        generated = sorted(normal - {"DualReservoirMainEq" if s == "Quadruplex" else s for s in styles})
        whistle = next((c for c in comps if c["kind"] == "Whistle"), {})
        wid = whistle.get("defaultWhistleIdentifier") or ""
        oddities = [f"{o['path']}: {o['what']}" for o in (ve.get("oddities") or []) if "collision" not in o["path"].lower() or "scale" not in o["what"]]
        names = [r["path"].split("/")[-1] for r in ve["renderers"]]
        files = hashes[pack]
        out[pack] = {
            "displayName": display,
            "whyte": whyte(loco),
            "tank": tender is None,
            "tender": None if tender is None else {"id": tender["identifier"], "truckPack": tender["definition"]["truckIdentifier"],
                                                   "lengthM": tender["definition"]["length"]},
            "source": {"pistonDiameterInches": loco["pistonDiameterInches"], "pistonStrokeInches": loco["pistonStrokeInches"],
                       "maximumBoilerPressure": loco["maximumBoilerPressure"], "totalHeatingSurface": loco["totalHeatingSurface"],
                       "weightEmpty": loco["weightEmpty"], "weightOnDrivers": loco["weightOnDrivers"], "brakeValveType": loco.get("brakeValveType") or ""},
            "driver": {"mainDriverIndex": loco["mainDriverIndex"], "clip": main["animation"]["clipName"], "axles": main["numberOfAxles"],
                       "radiusM": round(main["diameter"] / 2, 4), "basis": "source",
                       "evidence": f"definition driver diameter / 2 is the tread: {MEASURED}: the highest point of every rail-touching driving wheel is "
                                   f"{tips[0]}..{tips[-1]} mm above it (flange), level with it on blind drivers",
                       "flangeTipAboveTreadMm": [tips[0], tips[-1]]},
            "answers": {"cylinders": 2, "cylindersBasis": "James 2026-09-30: all stock locomotives are two-cylinder; a compound is simulated as a simple engine",
                        "firing": "hand-fired", "dynamo": "yes", "physics": "legacy-equivalent", "trainBrake": loco.get("brakeValveType") or "manual-lap",
                        "spawnMode": "radio-only", "basis": "James 2026-09-30 (coal, hand-fired, no auto-stoking, dynamo on every loco); physics/brake/spawn are the app's defaults"},
            "whistle": {"definitionId": wid, "built": wid or stock.DEFAULT_WHISTLE,
                        "basis": "definition" if wid else "James 2026-09-30: wh-3-std when the definition names none",
                        "model": whistles[wid or stock.DEFAULT_WHISTLE]["definition"]["model"]["assetIdentifier"]},
            "gauges": {"inModel": styles, "generated": generated,
                       "rule": "Quadruplex is built as DualReservoirMainEq; missing normal DV gauges are generated beside the nearest brake (else boiler) gauge (James 2026-09-30)"},
            "cab": {"backheadZ": round(backhead, 3), "floorFromCollisionHullM": round(best["y"], 2), "floorAreaM2": round(best["areaUp"], 1),
                    "floorConfinedToCab": bool(confined), "otherLevelsM": sorted({round(l["y"], 2) for l in hull if abs(l["y"] - best["y"]) > .05}),
                    "basis": f"{MEASURED}, M14 collision-hull flat levels; evidence for checks, not read by the build"},
            "endBeam": END_BEAM.get(pack) or {"none": "not needed in any run so far (builds without a review)" if pack in OBSERVED else "untested"},
            "lodMeshes": any(re.search(r"(?i)lod[1-9]\d*$", n) for n in names),
            "knownOddities": oddities,
            "hide": HIDE.get(pack, []),
            "conversion": OBSERVED.get(pack, {"status": "untested", "notes": []}),
            "sourceSha256": {"Bundle": files["Bundle"], "Catalog.json": files["Catalog.json"], "Definitions.json": files["Definitions.json"]},
        }
    table = {"schema": 1, "gameBuild": GAME_BUILD, "measured": MEASURED, "locos": out}
    # Keep the maintained fitting policy when regenerating the source measurements.
    # Refuse stale source hashes rather than silently resurrecting neighbour-generated faces.
    from update_tuning import reconcile
    fits = Path(__file__).resolve().parents[2] / 'src/rr2dv/gauge_fits.json'
    existing = Path(a.out)
    if existing.is_file():
        previous = json.loads(existing.read_text(encoding='utf-8'))
        for pack, entry in table['locos'].items():
            prior = previous.get('locos', {}).get(pack, {})
            if prior.get('sourceSha256') == entry['sourceSha256']:
                entry['repairs'] = prior.get('repairs', {})
                if any(vid != 'none' for vid in prior.get('endBeam', {})):
                    entry['endBeam'] = prior['endBeam']
                if 'oiling' in prior:
                    entry['oiling'] = prior['oiling']
                for key in ('historicalPolicy', 'installedBaseline'):
                    if key in prior.get('gauges', {}):
                        entry['gauges'][key] = prior['gauges'][key]
    table = reconcile(table, json.loads(fits.read_text(encoding='utf-8'))['profiles'])
    Path(a.out).write_text(json.dumps(table, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {a.out}: {len(out)} locos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
