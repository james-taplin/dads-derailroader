"""The `record` stage: draft a vehicle record (guide B03, loader contract builder/VEHICLE_RECORD.md) for one conversion.

Every numeric value carries {value, unit, basis, evidence}; basis is source | measured | derived | analogue_estimate |
DV_choice. Values that need geometry the probe has not yet supplied, or a person's review, stay null and are listed in
metadata.pending: never guessed. The formulas are the guide's and reproduce the reviewed S16 figures exactly:
- tractive effort target (E02): published value, else RR's .85 * p * d^2 * s / D;
- equivalent cylinder bore (E03): A = F * r / (p_gauge * (2/pi) * (stroke/2) * cylinders), bore = sqrt(4A/pi);
- safety valves: psig * .0689476 + 1.01325 bar absolute, reseat 3 psi lower;
- injector (E06): 1.4 * max evaporation, 11.5 lb/(ft2 h) of heating surface;
- firebed and firing rate (E06): G29's accepted 65 kg / 155 s scaled by heating surface (analogue estimates).
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from . import wheels
from .jsonio import read_json_lenient
from .rrmod import components, definition

LB_KG = 0.45359237
USGAL_L = 3.785411784
INCH_M = 0.0254
LBF_N = 4.4482216
PSI_BAR = 0.0689476
ATM_BAR = 1.01325
SAFETY_HYSTERESIS_PSI = 3.0
G29_FIREBED_KG, G29_BURN_S, G29_HEATING_FT2 = 65.0, 155.0, 1735.0
EVAPORATION_LB_PER_FT2_H = 11.5
DRIVER_DIAMETER_TOLERANCE = 0.03

# Sim/HUD/licence settings by simulation basis (E01, U05): tank locos use onboard resources (S060 basis),
# tender locos use tender ports (S282 basis). Proven by the S16 (tank) and G29 (tender) profiles.
BASIS = {
    "tank": {"SimBasis": 0, "HudType": 25, "License": "SH060", "BaseCarType": 6},
    "tender": {"SimBasis": 1, "HudType": 20, "License": "SH282", "BaseCarType": 6},
}
TENDER_CAR = {"BaseCarType": 8, "License": None}
AUDIO = {"S060": {"ChuffType": 0, "WhistleSystem": 3050}, "S282": {"ChuffType": 1, "WhistleSystem": 3100}}
# Draft DV-side simulation starting points (X30): the values of our S16 draft record, with its units, bases and evidence.
# They are not validated for any loco; every one is listed for per-engine review in metadata.pending.
GUIDE = "GUIDE_UNIFIED_LLW_CONVERSION.md"
U02 = f"{GUIDE}#U02 and implementation profile choices"
E06 = f"{GUIDE}#E06"
DRAFT_ENGINE = {"minCutoff": (0.1, "1", "DV_choice", U02), "maxCutoff": (0.85, "1", "DV_choice", U02),
                "throttleMaxFlow": (2.3, "kg/s", "analogue_estimate", E06),
                "steamChestVolume": (300, "L", "analogue_estimate", E06),
                "maxCondensationRate": (0.008, "1", "analogue_estimate", E06)}
DRAFT_BOILER = {"defaultFeedwaterTemperature": (25, "degC", "DV_choice", U02),
                "waterConsumptionMultiplier": (1, "1", "DV_choice", U02), "maxBlowdownRate": (10, "L/s", "DV_choice", U02),
                "maxSafetyValveVentRate": (1.5, "kg/s", "analogue_estimate", E06),
                "spawnPressure": (1, "bar absolute", "DV_choice", f"{GUIDE}#DV integration choice")}
DRAFT_FIREBOX = {"coalDumpRate": (5, "kg/s", "DV_choice", U02), "coalConsumptionMultiplier": (1, "1", "DV_choice", U02)}
DRAFT_EXHAUST = {"passiveExhaust": (0.4, "1", "DV_choice", U02)}
DRAFT_NOTE = "draft starting point from our S16 draft record; not validated for this engine"

def env(value, unit: str, basis: str, *evidence: str) -> dict:
    return {"value": value, "unit": unit, "basis": basis, "evidence": list(evidence)}


def drafts(table: dict) -> dict:
    return {k: {**env(v, unit, basis, evidence), "notes": DRAFT_NOTE} for k, (v, unit, basis, evidence) in table.items()}


def tractive_effort_lbf(d: dict) -> tuple[float, str]:
    published = d.get("publishedTractiveEffort") or 0
    if published > 0:
        return float(published), "published"
    main = d["wheelsets"][d.get("mainDriverIndex", 0)]
    return .85 * d["maximumBoilerPressure"] * d["pistonDiameterInches"] ** 2 * d["pistonStrokeInches"] / (main["diameter"] / INCH_M), "RR fallback"


def equivalent_bore_m(te_lbf: float, wheel_radius_m: float, psig: float, stroke_m: float, cylinders: int = 2) -> float:
    area = te_lbf * LBF_N * wheel_radius_m / (psig * PSI_BAR * 1e5 * (2 / math.pi) * (stroke_m / 2) * cylinders)
    return math.sqrt(4 * area / math.pi)


def safety_bar(psig: float) -> tuple[float, float]:
    return psig * PSI_BAR + ATM_BAR, (psig - SAFETY_HYSTERESIS_PSI) * PSI_BAR + ATM_BAR


def injector_l_s(heating_ft2: float) -> float:
    return round(1.4 * heating_ft2 * EVAPORATION_LB_PER_FT2_H * LB_KG / 3600, 1)


def firebox_estimate(heating_ft2: float) -> tuple[int, float]:
    firebed = round(G29_FIREBED_KG * heating_ft2 / G29_HEATING_FT2)
    rate = (G29_FIREBED_KG / G29_BURN_S) * heating_ft2 / G29_HEATING_FT2
    return firebed, firebed / rate


def drivers(d: dict) -> list[int]:
    """Driven wheelsets: the main driver and every wheelset of the same diameter (within 3%)."""
    sets = d.get("wheelsets") or []
    if not sets:
        return []
    main = sets[d.get("mainDriverIndex", 0)]["diameter"]
    return [i for i, w in enumerate(sets) if abs(w["diameter"] - main) <= DRIVER_DIAMETER_TOLERANCE * main]


def load_capacities(d: dict) -> dict:
    """RR load slots: water in US gallons, coal in pounds (S16: 1000 gal, 2000 lb)."""
    out = {}
    for slot in d.get("loadSlots") or []:
        ident = str(slot.get("requiredLoadIdentifier", "")).casefold()
        cap = slot.get("maximumCapacity")
        if ident == "water" and cap is not None:
            out["WaterCapacityL"] = cap * USGAL_L
        elif ident == "coal" and cap is not None:
            out["CoalCapacityKg"] = cap * LB_KG
    return out


def left_out_component(c: dict, owner: str, left_out: list[dict]) -> bool:
    """A part the inventory left out (broken in its own mod): the builder must not place it or anything anchored in it."""
    model = c.get("model") or {}
    for item in left_out:
        if item["owner"] != owner:
            continue
        if item["what"] == "part" and (model.get("assetPackIdentifier"), model.get("assetIdentifier")) == (item["pack_identifier"], item["asset"]):
            return True
        # anchored inside a left-out part: its parent will not exist, and a missing parent is a build error (B03)
        if item["what"] == "part" and c.get("name") in item.get("anchored", []):
            return True
        if item["what"] == "image" and c.get("textureName") == item["id"]:
            return True
    return False


def component_list(d: dict, owner: str = "", left_out: list[dict] | None = None) -> list[dict]:
    out = []
    for c in components(d):
        if c.get("kind") == "DefaultLivelryComponent" or left_out_component(c, owner, left_out or []):
            continue
        t = c.get("transform") or {}
        parent = c.get("parent") or {}
        extra = {k: v for k, v in c.items() if k not in ("kind", "name", "parent", "transform")}
        out.append({"kind": c.get("kind"), "name": c.get("name"),
                    "parentPath": "/".join(parent.get("path", [])) if isinstance(parent, dict) else "",
                    "extra": json.dumps(extra, separators=(",", ":")), "pos": t.get("position", [0, 0, 0]),
                    "rot": t.get("rotation", [0, 0, 0, 1]), "scale": t.get("scale", [1, 1, 1])})
    return out


def liveries(d: dict) -> list:
    return [[c.get("name"), [[e.get("id"), e.get("value")] for e in c.get("idColors", [])]]
            for c in components(d) if c.get("kind") == "DefaultLivelryComponent"]


def car_id(ident: str) -> str:
    return "RR2DV_" + re.sub(r"[^A-Za-z0-9]", "_", ident).upper()


def _maps(probe_vehicle: dict, kind: str) -> dict:
    return {e["key"]: e["asset"] for e in probe_vehicle.get(kind, []) if e.get("asset")}


def draft(run_path: Path, inv: dict, probe_input: dict, probe_output: dict | None, answers: dict,
          absent_bindings: list[dict] | None = None) -> dict:
    defs = {}
    for v in inv["vehicles"]:
        folder = run_path / "inputs" / v["pack"]["root"] / (v["pack"]["path"] or v["pack"]["name"])
        path = next(p for p in folder.iterdir() if p.name.casefold() == "definitions.json")
        objects = {o["identifier"]: o for o in read_json_lenient(path).get("objects", []) if isinstance(o, dict)}
        defs[v["id"]] = (objects[v["id"]], path.relative_to(run_path).as_posix())
    loco_id = inv["locomotive"]["id"]
    loco_obj, loco_src = defs[loco_id]
    d = definition(loco_obj)
    src = lambda field: f"{loco_src}#{loco_id}.{field}"
    probe_by_id = {v["id"]: v for v in probe_input["vehicles"]}
    pending: list[str] = []
    kind = "tender" if inv.get("tender") else "tank"
    audio = inv["audio"]["basis"]
    cid = car_id(loco_id)

    # Wheel radius: never taken from a probe candidate on its own (X30). The candidates go to metadata for review;
    # WheelRadius and the bore derived from it stay pending until a person accepts a tread band.
    main_index = d.get("mainDriverIndex", 0)
    main_ws = (d.get("wheelsets") or [{}])[main_index] if d.get("wheelsets") else {}
    wheel_candidates = [wheels.tread(w) for v in (probe_output or {}).get("vehicles", []) if v.get("id") == loco_id
                        for w in v.get("wheels", [])]
    reviewed = (answers.get("wheelRadius") or {}) if isinstance(answers.get("wheelRadius"), dict) else {}
    radius = reviewed.get("value")
    wheel_radius = env(radius, "m", "measured", *(reviewed.get("evidence") or ["run answers: reviewed tread band"])) if radius else None
    if not radius:
        main = next((c for c in wheel_candidates if c["clip"] == (main_ws.get("animation") or {}).get("clipName")), None)
        found = (f"probe candidate {main['tread']:.6f} m, {main['confidence']} confidence"
                 if main and main["tread"] else "no probe candidate")
        pending.append(f"WheelRadius: review the tread candidates in metadata.wheelCandidates ({found}; source nominal "
                       f"radius {main_ws.get('diameter', 0) / 2:g} m is not the tread), then pass --wheel-radius")

    needed = [f for f in ("maximumBoilerPressure", "pistonDiameterInches", "pistonStrokeInches", "wheelsets")
              if not d.get(f)]
    if needed:
        raise ValueError(f"{loco_id}: definition lacks {', '.join(needed)}; the simulation cannot be derived")
    te, te_basis = tractive_effort_lbf(d)
    stroke = d["pistonStrokeInches"] * INCH_M
    psig = d["maximumBoilerPressure"]
    open_bar, close_bar = safety_bar(psig)
    names = [l[0] for l in liveries(d)]
    if answers.get("livery") and answers["livery"] not in names:
        raise ValueError(f"livery {answers['livery']!r} is not one of: {', '.join(map(str, names)) or 'none'}")
    hs = d.get("totalHeatingSurface") or 0
    firebed, burn = firebox_estimate(hs) if hs else (None, None)
    driven = drivers(d)
    powered = sum(d["wheelsets"][i]["numberOfAxles"] for i in driven)
    bore = equivalent_bore_m(te, radius, psig, stroke) if radius else None
    if bore is None:
        pending.append("steamEngine.cylinderBore: needs the reviewed wheel radius (E03)")
    pending.append(f"poweredAxles: inferred from driver diameter (wheelsets {driven} within 3% of the main driver); "
                   "equal diameter alone does not prove they are coupled, check the rods")
    pending.append("simulation: draft engine, boiler, firebox and exhaust choices need per-engine calibration "
                   "(throttleMaxFlow, steamChestVolume, blowdown, vent rate, firing, exhaust, cutoff range)")
    if inv.get("left_out"):
        pending.append(f"left out: {len(inv['left_out'])} part(s) broken in the source mod (metadata.leftOut with reason "
                       "and effect); check the loco still looks and works right without them")
    absent_bindings = absent_bindings or []
    for a in absent_bindings:
        what = ("animates nothing in the exported model" if not a["restored"] else
                f"{len(a['absent'])} of its {a['bindings']} bindings target objects that are in no model of the export")
        pending.append(f"animation {'/'.join(a['keys']) or a['clip']}: {what} (metadata.absentBindings); the build stage must "
                       "remove exactly those bindings before our builder and record that it did (build/prep.json); check nothing "
                       "that should move is missing"
                       + (", and that the control it belongs to still works without it" if not a["restored"] else ""))
    # Material slots the probe found empty (X40: an unresolvable reference already in the export). Never guessed or
    # dropped: the renderer keeps the slot, and a person checks whether it is used.
    material_problems = [p for p in (probe_output or {}).get("problems", []) if "missing material" in p]
    if material_problems:
        pending.append(f"materials: {len(material_problems)} renderer(s) have an empty material slot in the export "
                       f"(metadata.materialProblems, first: {material_problems[0]}); check the part looks right in the renders")
    other_loads = sorted({str(slot.get("requiredLoadIdentifier")) for obj, _ in defs.values()
                          for slot in definition(obj).get("loadSlots") or []
                          if str(slot.get("requiredLoadIdentifier", "")).casefold() not in ("water", "coal")})
    if other_loads:
        pending.append(f"simulation: carries {', '.join(other_loads)}, not coal; DV simulates a coal-fired boiler, review firing")
    caps = load_capacities(d)
    config = {
        "CarId": cid, "CarName": (loco_obj.get("metadata") or {}).get("name") or loco_id, "Version": "0.1.0",
        "Author": f"{(loco_obj.get('metadata') or {}).get('credits') or 'unknown'} (Railroader assets), personal rr2dv conversion",
        "Requirements": ["DVCustomCarLoader"], "License": BASIS[kind]["License"],
        "BaseCarType": env(BASIS[kind]["BaseCarType"], "1", "DV_choice", "guide E01/T01"),
        "SimBasis": env(BASIS[kind]["SimBasis"], "1", "DV_choice", f"guide E01: {kind} locomotive"),
        "HudType": env(BASIS[kind]["HudType"], "1", "DV_choice", "guide U05"),
        "ChuffType": env(AUDIO[audio]["ChuffType"], "1", "DV_choice", f"rr2dv audio rule: {inv['audio']['rule']}"),
        "WhistleSystem": env(AUDIO[audio]["WhistleSystem"], "1", "DV_choice", f"rr2dv audio rule: {inv['audio']['rule']}"),
        "Sounds": [], "RemoveVanillaSounds": [],
        "SrcPrefab": next(v["prefab"] for v in probe_input["vehicles"] if v["id"] == loco_id),
        "Work": f"Assets/RR2DV/{cid}/loco",
        "Livery": answers.get("livery") or (liveries(d)[0][0] if liveries(d) else None), "Liveries": liveries(d),
        "AnimationMap": _maps(probe_by_id[loco_id], "animationMap"), "MaterialMap": _maps(probe_by_id[loco_id], "materialMap"),
        "Components": env(component_list(d, loco_id, inv.get("left_out")), "mixed", "source", src("components")),
        "Wheelsets": env([[w["offset"], w["length"], w["diameter"], w["numberOfAxles"], (w.get("animation") or {}).get("clipName", "")]
                          for w in d.get("wheelsets") or []], "mixed m/count", "source", src("wheelsets")),
        "WheelRadius": wheel_radius,
        "CouplerHeight": env(1.05, "m", "DV_choice", "guide C03 default"),
        "RrEndFront": env(d.get("positionHead"), "m", "source", src("positionHead")),
        "RrEndRear": env(d.get("positionTail"), "m", "source", src("positionTail")),
        "WaterCapacityL": env(caps.get("WaterCapacityL", 0.0), "L", "derived" if "WaterCapacityL" in caps else "DV_choice",
                              src("loadSlots") if "WaterCapacityL" in caps else "guide T01: resources on the tender"),
        "CoalCapacityKg": env(caps.get("CoalCapacityKg", 0.0), "kg", "derived" if "CoalCapacityKg" in caps else "DV_choice",
                              src("loadSlots") if "CoalCapacityKg" in caps else "guide T01: resources on the tender"),
        "WeightEmptyKg": None,
        "Bogies": None,
    }
    pending += ["WeightEmptyKg: confirm how the source weight is meant (working order, empty, with or without water); "
                "the mass ledger then needs the boiler's spawn water (boiler size from the probe; E04)",
                "Bogies: running-gear layout from measured axles (A04)", "CollisionBoxes: from measured geometry (A06)",
                "boiler diameter/length/capacityMultiplier/spawnWaterLevel: from measured boiler geometry"]

    sim = {
        "steamEngine": {"numCylinders": env(2, "count", "source", "guide E02: RR base cylinder count is two"),
                        "cylinderBore": env(bore, "m", "derived", src("pistonDiameterInches"), "guide E02/E03") if bore else None,
                        "pistonStroke": env(stroke, "m", "derived", src("pistonStrokeInches")),
                        **drafts(DRAFT_ENGINE)},
        "boiler": {"safetyValveOpeningPressure": env(open_bar, "bar absolute", "derived", src("maximumBoilerPressure"), "psig to absolute bar"),
                   "safetyValveClosingPressure": env(close_bar, "bar absolute", "derived", src("maximumBoilerPressure"), "3 psi reseat"),
                   "maxInjectorRate": env(injector_l_s(hs), "L/s", "analogue_estimate", src("totalHeatingSurface"), "guide E06") if hs else None,
                   **drafts(DRAFT_BOILER)},
        "firebox": {"maxCoalCapacity": env(firebed, "kg", "analogue_estimate", src("totalHeatingSurface"), f"{E06} firebed scaled from G29 by heating surface {hs:g}/{G29_HEATING_FT2:g}") if firebed else None,
                    "burnTime": env(burn, "s", "analogue_estimate", src("totalHeatingSurface"), f"{E06} firing rate scaled from G29 by heating surface {hs:g}/{G29_HEATING_FT2:g}") if burn else None,
                    **drafts(DRAFT_FIREBOX)},
        "exhaust": drafts(DRAFT_EXHAUST),
        # B03 shape, as our reviewed S16 record: poweredAxles.value is the envelope (the SimSpec field is a struct).
        "poweredAxles": {"value": env(powered, "count", "derived", src("wheelsets"), f"driven wheelsets {driven} (main driver diameter +/-3%)")},
    }
    record = {"schemaVersion": 1, "vehicleId": loco_id, "config": config, "hooks": {"SimSpec": sim},
              "metadata": {"status": "draft", "generator": "rr2dv record stage",
                           "tractiveEffort": {"lbf": te, "basis": te_basis},
                           "massLedger": {"sourceWeightLb": d.get("weightEmpty"),
                                          "sourceWeightKg": (d.get("weightEmpty") or 0) * LB_KG,
                                          "interpretation": "working order incl. boiler water (guide E04); spawn water to subtract is pending"},
                           "wheelCandidates": wheel_candidates, "leftOut": inv.get("left_out", []),
                           "absentBindings": absent_bindings, "materialProblems": material_problems,
                           "sources": inv.get("sources", []),
                           "audio": inv["audio"], "pending": pending}}
    if inv.get("tender"):
        tender_id = inv["tender"]["id"]
        t_obj, t_src = defs[tender_id]
        td = definition(t_obj)
        tsrc = lambda field: f"{t_src}#{tender_id}.{field}"
        tcaps = load_capacities(td)
        record["tender"] = {"config": {
            "CarId": cid + "_TENDER", "CarName": (t_obj.get("metadata") or {}).get("name") or tender_id, "IsTender": True,
            "License": TENDER_CAR["License"], "BaseCarType": env(TENDER_CAR["BaseCarType"], "1", "DV_choice", "guide T01: S282Tender"),
            "SrcPrefab": probe_by_id[tender_id]["prefab"], "Work": f"Assets/RR2DV/{cid}/tender",
            "Liveries": liveries(td), "AnimationMap": _maps(probe_by_id[tender_id], "animationMap"),
            "MaterialMap": _maps(probe_by_id[tender_id], "materialMap"),
            "Components": env(component_list(td, tender_id, inv.get("left_out")), "mixed", "source", tsrc("components")),
            "RrEndFront": env(td.get("positionHead", (td.get("length") or 0) / 2), "m", "source", tsrc("positionHead/length")),
            "RrEndRear": env(td.get("positionTail", -(td.get("length") or 0) / 2), "m", "source", tsrc("positionTail/length")),
            "WaterCapacityL": env(tcaps.get("WaterCapacityL"), "L", "derived", tsrc("loadSlots")) if "WaterCapacityL" in tcaps else None,
            "CoalCapacityKg": env(tcaps.get("CoalCapacityKg"), "kg", "derived", tsrc("loadSlots")) if "CoalCapacityKg" in tcaps else None,
            "CouplerHeight": env(1.05, "m", "DV_choice", "guide C03 default"),
            "WeightEmptyKg": env((td.get("weightEmpty") or 0) * LB_KG, "kg", "source", tsrc("weightEmpty")) if td.get("weightEmpty") else None,
        }, "hooks": {}}
        pending += ["tender: trucks layout and collision boxes from measured geometry"]
    return record
