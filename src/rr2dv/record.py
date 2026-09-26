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
# DV-side engine/boiler choices shared by our accepted profiles (S16 record, G29 config).
DV_ENGINE = {"minCutoff": 0.1, "maxCutoff": 0.85, "throttleMaxFlow": 2.3, "steamChestVolume": 300, "maxCondensationRate": 0.008}
DV_BOILER = {"defaultFeedwaterTemperature": 25, "waterConsumptionMultiplier": 1, "maxBlowdownRate": 10,
             "maxSafetyValveVentRate": 1.5, "spawnPressure": 1}


def env(value, unit: str, basis: str, *evidence: str) -> dict:
    return {"value": value, "unit": unit, "basis": basis, "evidence": list(evidence)}


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


def component_list(d: dict) -> list[dict]:
    out = []
    for c in components(d):
        if c.get("kind") == "DefaultLivelryComponent":
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


def draft(run_path: Path, inv: dict, probe_input: dict, probe_output: dict | None, answers: dict) -> dict:
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

    # Wheel radius: the probe's tread candidate when measured, else pending (the source radius is nominal).
    main_index = d.get("mainDriverIndex", 0)
    main_ws = (d.get("wheelsets") or [{}])[main_index] if d.get("wheelsets") else {}
    measured = None
    for v in (probe_output or {}).get("vehicles", []):
        if v.get("id") == loco_id:
            wheel = next((w for w in v.get("wheels", []) if w.get("clip") == (main_ws.get("animation") or {}).get("clipName")), None)
            if wheel and wheel.get("treadCandidate"):
                measured = wheel["treadCandidate"]
    wheel_radius = env(measured, "m", "measured", "probe/probe.json#wheels.treadCandidate") if measured else None
    if not measured:
        pending.append("WheelRadius: probe tread radius (source nominal is " + f"{main_ws.get('diameter', 0) / 2:g} m)")

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
    bore = equivalent_bore_m(te, measured, psig, stroke) if measured else None
    if bore is None:
        pending.append("steamEngine.cylinderBore: needs the measured wheel radius (E03)")
    code_mods = sorted({c["provider"] for c in inv.get("code_mods", [])})
    if code_mods:
        pending.append(f"simulation: Railroader figures depend on {', '.join(code_mods)}; review pull and cylinders (E02)")

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
        "Components": env(component_list(d), "mixed", "source", src("components")),
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
    pending += ["WeightEmptyKg: mass ledger needs the boiler's spawn water (boiler size from the probe; E04)",
                "Bogies: running-gear layout from measured axles (A04)", "CollisionBoxes: from measured geometry (A06)",
                "boiler diameter/length/capacityMultiplier/spawnWaterLevel: from measured boiler geometry"]

    sim = {
        "steamEngine": {"numCylinders": env(2, "count", "source", "guide E02: RR base cylinder count is two"),
                        "cylinderBore": env(bore, "m", "derived", src("pistonDiameterInches"), "guide E02/E03") if bore else None,
                        "pistonStroke": env(stroke, "m", "derived", src("pistonStrokeInches")),
                        **{k: env(v, "1" if k != "steamChestVolume" else "L", "DV_choice", "accepted profiles S16/G29") for k, v in DV_ENGINE.items()}},
        "boiler": {"safetyValveOpeningPressure": env(open_bar, "bar", "derived", src("maximumBoilerPressure"), "psig to absolute bar"),
                   "safetyValveClosingPressure": env(close_bar, "bar", "derived", src("maximumBoilerPressure"), "3 psi reseat"),
                   "maxInjectorRate": env(injector_l_s(hs), "L/s", "analogue_estimate", src("totalHeatingSurface"), "guide E06") if hs else None,
                   **{k: env(v, "1", "DV_choice", "accepted profiles S16/G29") for k, v in DV_BOILER.items()}},
        "firebox": {"maxCoalCapacity": env(firebed, "kg", "analogue_estimate", src("totalHeatingSurface"), "guide E06 scaled from G29") if firebed else None,
                    "burnTime": env(burn, "s", "analogue_estimate", src("totalHeatingSurface"), "guide E06 scaled from G29") if burn else None,
                    "coalDumpRate": env(5, "kg/s", "DV_choice", "accepted profiles"), "coalConsumptionMultiplier": env(1, "1", "DV_choice", "guide E06")},
        "exhaust": {"passiveExhaust": env(0.4, "1", "DV_choice", "accepted profiles")},
        "poweredAxles": env({"value": powered}, "count", "derived", src("wheelsets"), f"driven wheelsets {driven} (main driver diameter +/-3%)"),
    }
    record = {"schemaVersion": 1, "vehicleId": loco_id, "config": config, "hooks": {"SimSpec": sim},
              "metadata": {"status": "draft", "generator": "rr2dv record stage",
                           "tractiveEffort": {"lbf": te, "basis": te_basis},
                           "massLedger": {"sourceWeightLb": d.get("weightEmpty"),
                                          "sourceWeightKg": (d.get("weightEmpty") or 0) * LB_KG,
                                          "interpretation": "working order incl. boiler water (guide E04); spawn water to subtract is pending"},
                           "audio": inv["audio"], "codeMods": code_mods, "pending": pending}}
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
            "Components": env(component_list(td), "mixed", "source", tsrc("components")),
            "RrEndFront": env(td.get("positionHead", (td.get("length") or 0) / 2), "m", "source", tsrc("positionHead/length")),
            "RrEndRear": env(td.get("positionTail", -(td.get("length") or 0) / 2), "m", "source", tsrc("positionTail/length")),
            "WaterCapacityL": env(tcaps.get("WaterCapacityL"), "L", "derived", tsrc("loadSlots")) if "WaterCapacityL" in tcaps else None,
            "CoalCapacityKg": env(tcaps.get("CoalCapacityKg"), "kg", "derived", tsrc("loadSlots")) if "CoalCapacityKg" in tcaps else None,
            "CouplerHeight": env(1.05, "m", "DV_choice", "guide C03 default"),
            "WeightEmptyKg": env((td.get("weightEmpty") or 0) * LB_KG, "kg", "source", tsrc("weightEmpty")) if td.get("weightEmpty") else None,
        }, "hooks": {}}
        pending += ["tender: trucks layout and collision boxes from measured geometry"]
    return record
