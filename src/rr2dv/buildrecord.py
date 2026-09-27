"""The first half of the `build` stage: complete the draft vehicle record (record.py) into one our builder core can build
(tooling/builder/VEHICLE_RECORD.md, loader LlwVehicleRecord.cs), from the definitions and the probe's measurements.

Every value keeps B03 provenance ({value, unit, basis, evidence}). What the core needs but nothing measures is a
recorded choice (basis DV_choice or analogue_estimate) with its reason, and each such choice is listed for review in
metadata.buildChoices; a built pack is a candidate for runtime checks, never accepted (CTRL-01/02, Q04). What cannot
be derived at all stops the build with a block that says what to do (docs/resolving-blocks.md). Nothing here guesses a
value the X30 rule reserves for a person: the driver tread radius comes only from the user's reviewed answer.

Railroader conventions used (checked against our G-29/C-21/S-16 profiles):
- a wheelset's axles are evenly spaced over `length`, centred at `offset` (G-29: 3 drivers over 4.1 m); the probe's
  rotating wheel nodes are matched to those positions, so other rotating parts (C-21 expansion links) are ignored;
- the car's ends are positionHead/positionTail (loco) or +-length/2 (tender); coupled cars are 1 m apart;
- a tender's trucks sit at +-truckSeparation/2; RR places each truck prefab at runtime.
"""
from __future__ import annotations

import math
import re

from . import wheels
from .record import LB_KG, env

# Starting lever joint physics per control role, from the last user-accepted G-29 profile (tooling/locos/g29/profile/
# G29Config.cs RrLevers). Board X42: accepted builds are evidence, not templates, so these are analogue estimates to be
# checked in game per loco (CTRL-01); notch counts divide each lever's own measured sweep. Order: notches, spring, damper,
# mass, drag, angularDrag, scroll, scrollSpring; the whistle's scroll is a quarter of its sweep (scrollAngleFraction).
G29 = "tooling/locos/g29/profile/G29Config.cs"
LEVER_PHYSICS = {
    "throttle": (21, 50, 15, 15, 10, 0, 1, 400, None),
    "reverser": (41, 85, 15, 30, 15, 0, 1, 200, None),
    "trainBrake": (11, 85, 15, 30, 16, 0, 1, 100, None),
    "indBrake": (11, 65, 0, 30, 16, 0, 1, 100, None),
    "whistle": (0, 50, 5, 5, 5, 0, 1, 100, 0.25),
    "toggle": (2, 85, 15, 10, 15, 0, 1, 0, None),
}
# Railroader RadialControl purpose -> (role, DV port, ControlControlsWizard type, toggle, label)
PURPOSES = {
    "throttle": ("throttle", "throttle.EXT_IN", 0, False, None),
    "reverser": ("reverser", "reverser.CONTROL_EXT_IN", 1, False, None),
    "trainbrake": ("trainBrake", "brake.EXT_IN", 2, False, None),
    "locomotivebrake": ("indBrake", "indBrake.EXT_IN", 3, False, None),
    "independentbrake": ("indBrake", "indBrake.EXT_IN", 3, False, None),
    "whistle": ("whistle", "whistle.EXT_IN", 14, False, None),
    "horn": ("whistle", "whistle.EXT_IN", 14, False, None),
    "cylindercock": ("toggle", "cylinderCock.EXT_IN", 22, True, "car/cyl_cock"),
    "cylindercocks": ("toggle", "cylinderCock.EXT_IN", 22, True, "car/cyl_cock"),
    "bell": ("toggle", "bellControl.EXT_IN", 15, True, "car/bell"),
}
# Generated backhead controls for DV functions (G-29's set; the core's own joint physics for generated wheels/levers).
# (name, port, ctl, wheel, toggle, notches, label, range degrees or 0 for the core default)
GENERATED = [
    ("Injector", "injector.EXT_IN", 17, True, True, 18, "car/injector", 0),
    ("Blower", "blower.EXT_IN", 19, True, True, 18, "car/blower", 0),
    ("Blowdown", "blowdown.EXT_IN", 18, True, True, 10, "car/water_dump", 0),
    ("Damper", "damper.EXT_IN", 20, False, True, 8, "car/damper", 0),
    ("Fire door", "fireboxDoor.EXT_IN", 21, False, True, 2, "car/fire_door", 0),
    ("Air pump", "compressorControl.EXT_IN", 23, True, True, 2, "car/air_pump", 0),
    ("Dynamo", "dynamoControl.EXT_IN", 24, True, True, 2, "car/dynamo", 0),
    ("Sander", "sander.CONTROL_EXT_IN", 13, True, True, 2, "car/sander", 0),
    ("Coal dump", "coalDumpControl.EXT_IN", -1, False, False, 3, "car/ash_pan", 0),
    ("Cab light", "cabLight.EXT_IN", 12, False, True, 2, "car/cab_lights", 45),
    ("Headlights", "headlightDecoder.HEADLIGHTS_EXT_IN", 10, False, False, 7, "car/headlights", 90),
    ("Lubricator", "lubricatorControl.EXT_IN", 25, False, False, 2, "car/lubricator", 35),
    ("Brake cutout", "brakeCutout.EXT_IN", 5, False, True, 2, "car/brake_cutout", 0),
]
# Driving controls a loco needs even when Railroader models no handle for them: a generated backhead lever instead.
DRIVING = [("Throttle", "throttle.EXT_IN", 0, 21), ("Reverser", "reverser.CONTROL_EXT_IN", 1, 41),
           ("Train brake", "brake.EXT_IN", 2, 11), ("Independent brake", "indBrake.EXT_IN", 3, 11),
           ("Whistle", "whistle.EXT_IN", 14, 0), ("Cylinder cocks", "cylinderCock.EXT_IN", 22, 2),
           ("Bell", "bellControl.EXT_IN", 15, 2)]

AXLE_MATCH_M = 0.25        # a measured wheel node belongs to an RR axle position within this distance
AXLE_GROUP_M = 0.05        # wheel nodes this close in z are one axle (left and right wheels)
BACKHEAD_BIN_M = 0.02
BACKHEAD_MIN_HITS = 12
BACKHEAD_HALF_WIDTH = 0.7
CONTROL_SPACING_X, CONTROL_SPACING_Y = 0.2, 0.25
DOOR_CLEARANCE_M = 0.3
RENDER = "rr2dv render views from the model bounds"
SPAWN_TRACKS = [300, 400, 1100, 1400, 1700]  # G-29/S-16: CoalMineSouth, CoalPowerPlant, IronMineEast, OilRefinery, Sawmill


class Blocked(Exception):
    """The record cannot be completed; each item says what is missing and what to do."""

    def __init__(self, items: list[dict], choices: list[str] | None = None):
        super().__init__("; ".join(i["message"] for i in items))
        self.items = items
        self.choices = list(choices or [])


def _plain(n):
    """Strip B03 envelopes (the loader's Unwrap)."""
    if isinstance(n, dict):
        if "value" in n and ("unit" in n or "basis" in n or "evidence" in n):
            return _plain(n["value"])
        return {k: _plain(v) for k, v in n.items()}
    if isinstance(n, list):
        return [_plain(v) for v in n]
    return n


def _extra(c: dict) -> dict:
    import json
    try:
        return json.loads(c.get("extra") or "{}")
    except ValueError:
        return {}


def safe_name(text: str, fallback: str) -> str:
    """A pack/car name that is also a safe folder name on Windows (CCL exports the pack into a folder of this name)."""
    name = re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 _.()'&+-]", "", str(text or ""))).strip(" .")
    return name[:60] or fallback


def rr_axles(ws: dict) -> list[float]:
    """Axle z positions of a Railroader wheelset: evenly spaced over its length, centred at its offset."""
    n = int(ws.get("axles") or ws.get("numberOfAxles") or 0)
    off, length = float(ws.get("offset") or 0), float(ws.get("length") or 0)
    if n <= 1:
        return [off] * n
    return [off + length / 2 - i * length / (n - 1) for i in range(n)]


def driving_candidate(candidates: list[dict], wheelsets: list[dict], definition: dict, powered_indices=None) -> dict | None:
    """Offer only a powered wheelset, preferring the explicitly selected main driver."""
    from .record import drivers
    powered = drivers(definition) if powered_indices is None else powered_indices
    main = definition.get("mainDriverIndex", 0)
    indices = ([main] if main in powered else []) + [i for i in powered if i != main]
    for i in indices:
        if not isinstance(i, int) or not 0 <= i < len(wheelsets):
            continue
        clip = wheelsets[i].get("clip")
        hits = [c for c in candidates if clip and c.get("clip") == clip and c.get("tread")]
        if len(hits) == 1:
            return hits[0]
    return None


def _owner(path: str, rotating: list[str]) -> str | None:
    hits = [p for p in rotating if path == p or path.startswith(p + "/")]
    return max(hits, key=len) if hits else None


def measured_axles(ws_in: dict, wheel_out: dict | None, nodes: dict[str, list[float]]) -> list[dict]:
    """Each RR axle of a wheelset, with the probe's rotating wheel node at that position when there is one."""
    expected = rr_axles(ws_in)
    groups: list[dict] = []
    rotating = (wheel_out or {}).get("rotatingPaths") or []
    for mesh in (wheel_out or {}).get("meshes") or []:
        if not mesh.get("used"):
            continue
        declared = ws_in.get('transformPath')
        if declared and not (mesh['path'] == declared or mesh['path'].startswith(declared + '/')):
            continue
        owner = _owner(mesh["path"], rotating)
        if owner is None or owner not in nodes:
            continue
        z = nodes[owner][2]
        g = next((g for g in groups if abs(g["z"] - z) <= AXLE_GROUP_M), None)
        if g is None:
            groups.append({"z": z, "paths": [owner]})
        elif owner not in g["paths"]:
            g["paths"].append(owner)
    if ws_in.get('transformPath') and len(groups) == len(expected) and groups:
        # An explicit source transform identifies the physical truck even when its mesh positions
        # differ from the source simulation offsets. Keep the measured geometry and report both.
        return [{'z': g['z'], 'part': sorted(g['paths'])[0], 'basis': 'measured', 'rr': z}
                for g, z in zip(sorted(groups, key=lambda g: -g['z']), expected)]
    out = []
    for z in expected:
        near = sorted((g for g in groups if abs(g["z"] - z) <= AXLE_MATCH_M), key=lambda g: (abs(g["z"] - z), g["z"]))
        if near:
            g = groups.pop(groups.index(near[0]))
            out.append({"z": g["z"], "part": sorted(g["paths"])[0], "basis": "measured", "rr": z})
        else:
            out.append({"z": z, "part": None, "basis": "source", "rr": z})
    return out


def common_parent(paths: list[str]) -> str:
    parents = [p.rsplit("/", 1)[0] if "/" in p else "" for p in paths]
    if not parents:
        return ""
    split = [p.split("/") if p else [] for p in parents]
    prefix = []
    for segs in zip(*split):
        if len(set(segs)) != 1:
            break
        prefix.append(segs[0])
    return "/".join(prefix)


def backhead(rays: list[dict]) -> dict | None:
    """The backhead plate: the most common z (2 cm bins) of rays that meet a surface facing the cab."""
    # within +-0.7 m of the centreline: further out the cab's front wall faces the cab too and could outvote the plate
    facing = [r for r in rays or [] if r.get("hit") and r.get("normalZ", 0) < -0.5 and abs(r.get("x", 0)) <= BACKHEAD_HALF_WIDTH]
    if not facing:
        return None
    bins: dict[int, list[dict]] = {}
    for r in facing:
        bins.setdefault(round(r["z"] / BACKHEAD_BIN_M), []).append(r)
    key, hits = max(bins.items(), key=lambda kv: (len(kv[1]), -kv[0]))
    if len(hits) < BACKHEAD_MIN_HITS:
        return None
    z = sum(h["z"] for h in hits) / len(hits)
    return {"z": z, "hits": len(hits), "of": len(rays), "points": [(h["x"], h["y"]) for h in hits]}


def control_positions(points: list[tuple[float, float]], door: tuple[float, float], avoid: list[tuple[float, float]],
                      count: int) -> list[tuple[float, float]]:
    """Places on the flat backhead plate for generated controls: clear of the fire door and each other, preferring
    the band 0.3-0.9 m above the door, nearest the centreline first; deterministic."""
    dx, dy = door
    free = [(x, y) for x, y in points
            if math.hypot(x - dx, y - dy) >= DOOR_CLEARANCE_M and dy - 0.2 <= y <= dy + 1.2
            and all(math.hypot(x - ax, y - ay) >= 0.15 for ax, ay in avoid)]
    free.sort(key=lambda p: (0 if dy + 0.3 <= p[1] <= dy + 0.9 else 1, round(abs(p[1] - (dy + 0.5)), 2), round(abs(p[0]), 2), p[0], p[1]))
    chosen: list[tuple[float, float]] = []
    for x, y in free:
        if all(abs(x - cx) >= CONTROL_SPACING_X - 1e-6 or abs(y - cy) >= CONTROL_SPACING_Y - 1e-6 for cx, cy in chosen):
            chosen.append((round(x, 3), round(y, 3)))
            if len(chosen) == count:
                break
    return chosen


def _anchor(anchors: dict, name: str) -> list[float] | None:
    a = anchors.get(name)
    return a["position"] if a and a.get("resolved") and a.get("position") else None


def truck_geometry(truck_out: dict) -> dict | None:
    """Axle offsets, tread radius and wheel-node name prefix of a truck prefab, from the probe's truck wheels."""
    meshes = [w for w in truck_out.get("truckWheels") or [] if "lod" not in w["path"].casefold() or "lod0" in w["path"].casefold()]
    if not meshes:
        return None
    axles: list[dict] = []
    for w in sorted(meshes, key=lambda w: -w["centre"][2]):
        g = next((a for a in axles if abs(a["z"] - w["centre"][2]) <= AXLE_GROUP_M), None)
        if g is None:
            axles.append({"z": w["centre"][2], "meshes": [w]})
        else:
            g["meshes"].append(w)
    treads = []
    for a in axles:
        cand = wheels.tread({"clip": "", "sourceRadius": 0.0, "bands": [b for w in a["meshes"] for b in w.get("bands") or []],
                             "meshes": [{"path": w["path"], "used": True} for w in a["meshes"]]})
        a["tread"] = cand
        if cand["tread"]:
            treads.append(cand["tread"])
    if not treads:
        return None
    names = sorted({w["wheelNode"].rsplit("/", 1)[-1] for w in truck_out.get("truckWheels") or []})
    prefix = names[0]
    for n in names[1:]:
        while not n.startswith(prefix):
            prefix = prefix[:-1]
    nodes = [n["path"] for n in truck_out.get("nodes") or []]
    wheel_nodes = {w["wheelNode"] for w in truck_out.get("truckWheels") or []}
    strays = [p for p in nodes if p.rsplit("/", 1)[-1].startswith(prefix)
              and not any(p == w or p.startswith(w + "/") for w in wheel_nodes)] if prefix else []
    return {"axles": [a["z"] for a in axles], "radius": sum(treads) / len(treads), "treads": [a["tread"] for a in axles],
            "prefix": prefix if prefix.casefold().startswith("wheel") and not strays else None, "strays": strays,
            "names": names}


def _shots(files: list[tuple[list[float], list[float], float, str]]) -> dict:
    return env([{"Pos": p, "Look": l, "Fov": f, "File": n} for p, l, f, n in files], "m/deg", "DV_choice", RENDER)


def _r(v, n: int = 4):
    return [round(x, n) for x in v] if isinstance(v, (list, tuple)) else round(v, n)


class _Builder:
    def __init__(self, draft: dict, inv: dict, probe_in: dict, probe_out: dict, project: dict, answers: dict):
        self.draft, self.inv, self.answers, self.project = draft, inv, answers, project
        self.pin = {v["id"]: v for v in probe_in["vehicles"]}
        self.pout = {v["id"]: v for v in (probe_out or {}).get("vehicles", [])}
        self.blocks: list[dict] = []
        self.choices: list[str] = []

    def block(self, code: str, message: str, **extra) -> None:
        self.blocks.append({"code": code, "message": message, **extra})

    def choose(self, text: str) -> None:
        self.choices.append(text)

    # ------------------------------------------------------------------ helpers over probe data
    def probe_of(self, vid: str) -> dict:
        v = self.pout.get(vid)
        if not v or not v.get("nodes"):
            self.block("probe-missing", f"{vid}: the probe measured nothing for it (probe/probe.json); rerun the conversion")
            return {}
        return v

    @staticmethod
    def nodes(v: dict) -> dict[str, list[float]]:
        return {n["path"]: n["position"] for n in v.get("nodes") or []}

    @staticmethod
    def anchors(v: dict) -> dict:
        return {a["name"]: a for a in v.get("anchors") or []}

    @staticmethod
    def bound_paths(v: dict, key: str) -> list[str]:
        clip = next((c for c in v.get("clips") or [] if c["key"] == key), None)
        return sorted({p["path"] for p in (clip or {}).get("poses") or []})

    # ------------------------------------------------------------------ the locomotive
    def loco(self) -> dict:
        rec = self.draft
        cfg = rec["config"]
        lid = rec["vehicleId"]
        pv, ov = self.pin[lid], self.probe_of(lid)
        if not ov:
            return rec
        comps = _plain(cfg["Components"])
        anchors, nodes = self.anchors(ov), self.nodes(ov)
        anims = cfg.get("AnimationMap") or {}
        tender = self.inv.get("tender")
        name = safe_name(cfg.get("CarName"), cfg["CarId"])
        cfg["CarName"] = name
        cfg["ReleaseLabel"] = "rr2dv"
        cfg["BodyName"] = f"{lid}_body"
        self._liveries(cfg, lid)
        if not cfg.get("MaterialMap"):
            self.block("no-materials", f"{lid}: the model's material map is empty (probe/probe.json materialMap); the builder "
                                       "tints materials from it, so this model cannot be built")
        self._material_review(cfg, lid)
        self._geometry_review(cfg, lid)

        radius = (cfg.get("WheelRadius") or {}).get("value")
        if not radius:
            cands = [w for w in rec["metadata"].get("wheelCandidates") or [] if w.get("tread")]
            main = driving_candidate(cands, pv.get("wheelsets") or [], self.definition_of(lid))
            self.block("needs-wheel-radius",
                       "the driving wheel tread radius needs your review: " +
                       (f"the probe's candidate is {main['tread']:.4f} m ({main['confidence']} confidence, source "
                        f"{main['sourceRadius']:g} m); " if main else "the probe found no candidate; ") +
                       "check it against the tyre in the model, then convert again with that value "
                       "(app: Options > Wheel radius; command line: --wheel-radius)",
                       candidate=main["tread"] if main else None)
            radius = main["tread"] if main and main.get("tread") else 0.5  # only to finish the checks below; never built
        self._mass(cfg, lid, rec)

        # A typed value is not evidence that it belongs to the powered wheel.
        # Reject a pilot/tender radius (and a diameter entered as a radius).
        candidate = driving_candidate(rec['metadata'].get('wheelCandidates', []),
                                      pv.get('wheelsets', []), self.definition_of(lid), self._driver_indices(cfg))
        if candidate and candidate.get('confidence') == 'high' and radius:
            if abs(radius - candidate['tread']) > max(.01, candidate['tread'] * .03):
                self.block('needs-driver-radius',
                           f"Reviewed radius {radius:g} m disagrees with the powered-wheel tread "
                           f"{candidate['tread']:.5f} m ({candidate['clip']}); use the driving tyre radius, not a bogie wheel or diameter",
                           candidate=candidate['tread'])
        rec['metadata']['wheelRadiusCheck'] = {
            'enteredRadiusM': radius, 'poweredCandidate': candidate,
            'status': 'compared' if candidate else 'no measured powered candidate',
            'tolerance': 'max(10 mm, 3% of measured tread radius)',
        }

        # ---------------- running gear
        wheelsets = pv.get("wheelsets") or []
        wouts = ov.get("wheels") or []
        driver_idx = set(self._driver_indices(cfg))
        reviewed = self.answers.get('prebuildReview', {}).get('values', {})
        geared = reviewed.get('physics') == 'geared'
        physical_idx = driver_idx | set(reviewed.get('unpoweredWheelsets', []))
        axles, units, ponies, wheel_clips = [], [], [], []
        for i, ws in enumerate(wheelsets):
            wout = wouts[i] if i < len(wouts) else None
            if geared and i in physical_idx:
                original = self.definition_of(lid)['wheelsets'][i]
                path = (original.get('transform') or {}).get('path')
                if path:
                    ws = {**ws, 'transformPath': '/'.join(path)}
            if geared and i not in physical_idx:
                if ws.get('clip') in anims and ws['clip'] not in [wheelsets[j].get('clip') for j in physical_idx]:
                    wheel_clips.append([ws['clip'], f"shaft clip {ws['clip']}", round(ws['diameter'] / 2, 4)])
                self.choose(f"wheelset {i}: reviewed as non-physical; no axle generated; source clip retained where present")
                continue
            # One source animation can rotate wheels on several physical trucks. Match by measured
            # axle positions and source wheel size, never by vehicle ID or an animation's name.
            if geared and not ws.get('clip'):
                shared = []
                for source_ws, source_out in zip(wheelsets, wouts):
                    if source_ws.get('clip') not in anims or abs(source_ws['diameter'] - ws['diameter']) > .01:
                        continue
                    matched = measured_axles(ws, source_out, nodes)
                    if matched and all(a['part'] for a in matched): shared.append((source_ws, source_out))
                if len(shared) == 1:
                    source_ws, wout = shared[0]
                    ws = {**ws, 'clip': source_ws['clip']}
                    self.choose(f"physical wheelset {i}: measured axles share source animation {ws['clip']!r}")
            found = [m for m in (wout or {}).get("meshes") or [] if m.get("used")]
            if i not in driver_idx and not found:
                if ws.get("clip") and ws["clip"] in anims:  # G-29 'Wrench': a clip on a wheelset without a wheel
                    wheel_clips.append([ws["clip"], f"wheel clip {ws['clip']}", round(ws["diameter"] / 2, 4)])
                    self.choose(f"wheelset {ws['clip']!r} has no wheel mesh: its clip turns with the car at the source radius "
                                f"{ws['diameter'] / 2:g} m (as G-29's lubricator ratchet), no axle")
                continue
            ax = measured_axles(ws, wout, nodes)
            for a in ax:
                a.update(driver=i in driver_idx, clip=ws.get("clip"), wheelset=i)
            axles += ax
            if i in driver_idx:
                parts = [a["part"] for a in ax]
                if None in parts:
                    self.block("drivers-not-found", f"{lid}: wheelset {i} ({ws.get('clip')}) has {len(ax)} driving axle(s) in the "
                                                    f"definition but the probe found a turning wheel for only {len(ax) - parts.count(None)} "
                                                    "(probe/probe.json wheels); the builder needs every driving axle's wheel")
                if ws.get("clip") not in anims:
                    self.block("drivers-no-clip", f"{lid}: driving wheelset {i} has no animation clip in the model's clip map")
                shared_unit = next((u for u in units if u['AnimKey'] == ws.get('clip')), None)
                if shared_unit:
                    shared_unit['DriverParts'] += [p for p in parts if p and p not in shared_unit['DriverParts']]
                else:
                    units.append({"DriverParts": [p for p in parts if p], "AnimKey": ws.get("clip"), "GroupName": f"drivers {len(units) + 1}" if units else "drivers",
                                  "StartOffset": 0})
            elif ws.get("clip") in anims:
                ponies.append((ws["clip"], ax, ws))
        drivers = sorted((a for a in axles if a["driver"]), key=lambda a: -a["z"])
        if not drivers:
            self.block("no-drivers", f"{lid}: no driving wheelset found in the definition")
            return rec
        allax = sorted(axles, key=lambda a: -a["z"])
        rec['metadata']['physicalAxles'] = [dict(a) for a in allax]
        if geared and any(a['part'] and abs(a['z'] - a['rr']) > .05 for a in allax):
            self.choose('Explicit source truck transforms identify measured axles whose model positions differ from source simulation offsets; '
                        'using measured model geometry, see metadata.physicalAxles (z and rr); in-game wheelbase validation pending')
        n_front = max(1, len(drivers) // 2)
        front_drivers = drivers[:n_front]
        split = allax.index(front_drivers[-1]) + 1
        f_ax, r_ax = allax[:split], allax[split:]
        if not r_ax:
            self.block("one-axle", f"{lid}: only one axle found; Derail Valley needs two bogies")
            return rec
        f_pivot = f_ax.index(front_drivers[0])
        r_pivot = r_ax.index(drivers[-1]) if drivers[-1] in r_ax else len(r_ax) - 1
        evidence = [f"probe/probe.json wheels (nodes turned by the wheelset clips)", "Definitions wheelsets (RR axle positions)",
                    "guide A04; G-29 profile: bogies pivot on the end drivers (rigid wheelbase)"]
        cfg["Bogies"] = env([{"Bogie": "BogieF", "BogieCollider": "front", "Axles": [_r(a["z"]) for a in f_ax], "PivotAxle": f_pivot},
                             {"Bogie": "BogieR", "BogieCollider": "rear", "Axles": [_r(a["z"]) for a in r_ax], "PivotAxle": r_pivot}],
                            "m", "measured", *evidence)
        from_source = [a for a in axles if a["basis"] == "source"]
        if from_source:
            self.choose(f"{len(from_source)} axle(s) placed at Railroader's wheelset position, the probe found no wheel there: "
                        + ", ".join(f"{a['clip']} z {a['z']:.3f}" for a in from_source))
        cfg["EngineUnits"] = env(units, "m", "measured", "probe/probe.json wheels", "Definitions wheelsets")
        cfg["NestedClipGroups"] = True
        self.choose("NestedClipGroups on (each clip animates under its objects' common parent), as S-16/G-29")
        if len(units) > 1:
            self.choose(f"{len(units)} driving wheelsets with their own clips; bogies still follow the rigid-wheelbase rule: "
                        "check articulated running gear")
        if ponies:
            cfg["PonyTrucks"] = [[clip, f"pony {clip}"] for clip, _, _ in ponies]
            cfg["PonyRadii"] = env({clip: _r(ws["diameter"] / 2) for clip, _, ws in ponies}, "m", "source",
                                   *[f"Definitions wheelsets[{ws.get('clip')}].diameter / 2" for _, _, ws in ponies])
            lead = [(clip, ax) for clip, ax, _ in ponies if all(a["z"] > drivers[0]["z"] for a in ax)]
            art = []
            driver_paths = [p for u in units for p in u["DriverParts"]]
            for clip, ax in lead:
                owners = [a["part"] for a in ax if a["part"]]
                parent = common_parent(owners)
                if parent and not any(d == parent or d.startswith(parent + "/") for d in driver_paths):
                    art.append([f"Model/{cfg['BodyName']}/{parent}", "BogieF"])
                    self.choose(f"leading truck {parent!r} ({clip}) hangs on the front bogie and swings with it (G-29 pilot truck)")
            if art:
                cfg["ArticulatedParts"] = art
        if wheel_clips:
            cfg["WheelClips"] = env(wheel_clips, "m", "source", "Definitions wheelsets diameter / 2")
        if cfg.get("WheelslipFriction") is None:
            cfg["WheelslipFriction"] = env(0.25, "1", "DV_choice", "S-16 record (all weight adhesive); review with weight on drivers")
            self.choose("wheelslip friction 0.25 (S-16's value; Derail Valley counts all weight as adhesive)")

        # ---------------- ends, couplers, collision
        bmin, bmax = ov.get("boundsMin"), ov.get("boundsMax")
        front_end, rear_end = _plain(cfg.get("RrEndFront")), _plain(cfg.get("RrEndRear"))
        if bmin is None or front_end is None or rear_end is None:
            self.block("no-geometry", f"{lid}: car ends or model bounds are missing (positionHead/positionTail, probe bounds)")
            return rec
        rec["hooks"]["CollisionBoxes"] = self._collision(bmin, bmax, front_end, rear_end)
        if tender:
            cfg["HideBackCoupler"] = True
            cfg["SpawnTracks"] = env(SPAWN_TRACKS, "track id", "DV_choice", f"{G29} SpawnTracks")
        plates = self._plates(comps, anchors)
        if plates:
            cfg["PlateDecals"] = plates

        # ---------------- anchors
        chuff = next((c["name"] for c in comps if c["kind"] == "Chuff"), None)
        whistle = next((c["name"] for c in comps if c["kind"] == "Whistle"), None)
        cocks = [c for c in comps if c["kind"] == "CylinderCock"]
        for what, val in (("Chuff (chimney)", chuff), ("Whistle", whistle), ("CylinderCock", cocks)):
            if not val:
                self.block("missing-anchor", f"{lid}: the definition has no {what} component; the builder places the smoke, "
                                             "steam and their sounds from it")
        if not (chuff and whistle and cocks):
            return rec
        cfg["ChimneyComp"], cfg["WhistleComp"] = chuff, whistle
        self._cylinder_cocks(cfg, comps, lid)
        chimney = _anchor(anchors, chuff) or [0, bmax[1], bmax[2] - 1]
        whistle_at = _anchor(anchors, whistle) or chimney
        cock_at = _anchor(anchors, cocks[0]["name"]) or [0, radius, drivers[0]["z"] + 1.0]

        # ---------------- cab, backhead, fire door
        seats = [c["name"] for c in comps if c["kind"] == "Seat" and _anchor(anchors, c["name"])]
        fire = sorted((_anchor(anchors, c["name"]) for c in comps if c["kind"] == "FireboxEffect" and _anchor(anchors, c["name"])),
                      key=lambda p: p[2])
        plate = backhead(ov.get("cabRays"))
        if plate:
            back_z = plate["z"]
            cfg["BackheadZ"] = env(_r(back_z), "m", "measured", f"probe/probe.json cabRays: {plate['hits']} of {plate['of']} rays meet a "
                                                               "cab-facing surface in one 2 cm band")
        elif fire:
            back_z = fire[0][2]
            cfg["BackheadZ"] = env(_r(back_z), "m", "analogue_estimate", "rearmost FireboxEffect anchor (probe/probe.json anchors)")
            self.choose("backhead plane from the rearmost firebox glow: the cab rays found no flat backhead")
        else:
            self.block("no-backhead", f"{lid}: no backhead found (no cab rays hit a flat plate and the definition has no "
                                      "FireboxEffect); the builder needs it for the firebox and cab controls")
            return rec
        seat_at = _anchor(anchors, seats[0]) if seats else None
        door = [fire[0][0], fire[0][1], back_z] if fire else [0.0, (seat_at[1] - 0.5) if seat_at else radius * 2 + 0.8, back_z]
        cfg["FireDoorCentre"] = env(_r(door), "m", "analogue_estimate",
                                    "rearmost FireboxEffect anchor at the backhead plane" if fire else "seat height - 0.5 m at the backhead plane")
        self.choose(f"fire door centre {_r(door, 3)} (firebox glow height at the backhead); check the firebox and fire feed in the cab renders")
        cfg["BackheadRayStartZ"] = env(_r(back_z - 0.5), "m", "DV_choice", "0.5 m behind the backhead plane (S-16 0.46 m)")
        if seats:
            cfg["CabSeatComp"] = seats[0]
            cab_z = seat_at[2] + 0.3
        else:
            cab_z = back_z - 0.6
            cfg["CabZ"] = env(_r(cab_z), "m", "DV_choice", "0.6 m behind the backhead (no crew seat in the definition)")
            self.choose("cab teleport 0.6 m behind the backhead: the definition has no crew seat")
        cab_y = seat_at[1] if seat_at else door[1] + 0.5
        cfg["CabLightProbe"] = env(_r([0, cab_y + 1.0, cab_z]), "m", "DV_choice", "1 m above the crew seat; the core raycasts up to the roof")
        cfg["RenderCabLight"] = env(_r([0, cab_y + 1.0, cab_z]), "m", "DV_choice", RENDER)
        gauges = [c["name"] for c in comps if c["kind"] == "Gauge" and _extra(c).get("style") == "BoilerPressure"]
        if gauges:
            cfg["MainPressureGauge"] = gauges[0]

        # ---------------- controls
        levers, cab_objects, loads, taken = self._levers(cfg, comps, ov, anims, lid)
        cfg["RrLevers"] = env([{k: v for k, v in l.items() if k != "_phys"} for l in levers], "1", "source",
                              "Definitions RadialControl components (purpose, clip, part); ControlControlsWizard types as G-29")
        rec["hooks"]["LeverPhysics"] = env([l["_phys"] for l in levers], "mixed deg/N/kg", "analogue_estimate",
                                           f"{G29} RrLevers joint physics per control role (CTRL-01: last user-accepted G-29)")
        cfg["CabControlObjects"] = cab_objects
        missing = [d for d in DRIVING if d[1] not in taken and (d[1] != "bellControl.EXT_IN" or any(c["kind"] == "Bell" for c in comps))]
        wanted = [(n, p, ctl, False, ctl in (22, 15), notches, None, 0) for n, p, ctl, notches in missing] + \
                 [g for g in GENERATED if g[1] not in taken]
        if plate:
            avoid = [tuple(nodes[l["Path"]][:2]) for l in levers if l["Path"] in nodes]
            spots = control_positions(plate["points"], (door[0], door[1]), avoid, len(wanted))
        else:
            spots = []
        if len(spots) < len(wanted):
            self.block("no-room-for-controls", f"{lid}: found room on the backhead for {len(spots)} of the {len(wanted)} generated controls "
                                               f"({', '.join(w[0] for w in wanted[len(spots):])}); the cab rays (probe/probe.json cabRays) "
                                               "found too little flat backhead plate")
        placed = []
        for (nm, port, ctl, wheel, toggle, notches, label, rng), (x, y) in zip(wanted, spots):
            placed.append({"Name": nm, "Port": port, "Ctl": ctl, "Wheel": wheel, "Toggle": toggle, "Notches": notches,
                           **({"Label": label} if label else {}), "X": x, "Y": y, **({"Range": rng} if rng else {})})
        cfg["Placed"] = env(placed, "m/count/deg", "DV_choice",
                            "probe/probe.json cabRays: points on the flat backhead plate, 0.2 m apart, clear of the fire door",
                            f"{G29} generated controls (ports, notches, ranges); the core's own joint physics for generated controls")
        if missing:
            self.choose("no Railroader handle for " + ", ".join(m[0] for m in missing) + ": generated backhead lever(s) instead")
        self.choose(f"{len(placed)} generated backhead controls (G-29's set) at measured points on the backhead plate: "
                    "check reach, labels and the control sweep in the build report (CTRL-01)")
        self.choose("RR cab handles become DV levers with starting joint physics per role from G-29's accepted profile "
                    "(evidence, not validated for this loco's travel) and the core's handle-end grip boxes: every control "
                    "and input route still needs the in-game checks (board X42 gates, CTRL-01/CTRL-02)")

        # ---------------- clips that follow ports, loops, loads
        for c in comps:
            e = _extra(c)
            clip = (e.get("animation") or {}).get("clipName")
            if c["kind"] == "LoadAnimation" and clip in anims and e.get("loadIdentifier") in ("water", "coal") and not tender:
                loads.append([clip, "", f"{e['loadIdentifier']}.NORMALIZED", False])
            elif c["kind"] == "ToggleAnimation" and clip in anims and "firebox" in str(e.get("title", "")).casefold():
                loads.append([clip, "", "fireboxDoor.EXT_IN", False])
        cfg["LoadAnimations"] = self._ordered_loads(loads, ov)
        toggles = [c["name"] for c in comps if c["kind"] == "ToggleAnimation"
                   and "firebox" not in str(_extra(c).get("title", "")).casefold()]
        if toggles:
            self.choose(f"{len(toggles)} Railroader toggle animation(s) (doors, windows, hatches, vents) are not interactive yet and "
                        f"stay as modelled: {', '.join(toggles)}")
        loops = []
        for c in comps:
            e = _extra(c)
            clip = (e.get("animation") or {}).get("clipName")
            if clip not in anims:
                continue
            if c["kind"] == "Bell":
                loops.append([clip, "bell.BELL_NORMALIZED", 0.8])
                if _anchor(anchors, c["name"]):
                    cfg["BellSound"] = env(_r(_anchor(anchors, c["name"])), "m", "source", f"Bell component {c['name']} (probe anchors)")
            elif c["kind"] == "Compressor":
                loops.append([clip, "compressor.PRODUCTION_RATE_NORMALIZED", round(2 * float(e.get("animationSpeed") or 0.5), 4)])
        if loops:
            seen, uniq = set(), []
            for l in loops:
                if l[0] not in seen:
                    seen.add(l[0])
                    uniq.append(l)
            cfg["LoopAnimations"] = env(uniq, "cycles/s", "analogue_estimate", "S-16/G-29: bell 0.8/s; pumps 2 x RR animationSpeed (S-16)")

        # ---------------- particles and sound anchors (sound positions only; no audio is converted)
        mid_z = (bmin[2] + bmax[2]) / 2
        half = (bmax[0] - bmin[0]) / 2
        est = lambda v, why: env(_r(v), "m", "analogue_estimate", why)
        dynamo = next((_anchor(anchors, c["name"]) for c in comps if c["kind"] == "Dynamo" and _anchor(anchors, c["name"])), None)
        cfg["SafetyPos"] = est([whistle_at[0], whistle_at[1] + 0.1, whistle_at[2]], "at the whistle (safety valves share its dome/firebox top)")
        cfg["SndSafety"] = cfg["SafetyPos"]
        cfg["DynamoPos"] = env(_r(dynamo), "m", "source", "Dynamo component (probe anchors)") if dynamo else \
            est([0.0, chimney[1] - 0.3, chimney[2] - 1.0], "behind the chimney (no Dynamo component)")
        cfg["BlowdownPos"] = est([min(0.7, half), door[1] - 0.5, back_z + 0.6], "low on the firebox side (S-16/G-29 layout)")
        cfg["CrackPos"] = est([0.0, cock_at[1], cock_at[2]], "cylinder cock anchor on the centreline")
        cfg["SndCylinders"] = cfg["CrackPos"]
        cfg["SndCab"] = est([0.0, cab_y + 0.5, cab_z], "in the cab above the seats")
        cfg["SndWheels"] = est([0.0, radius, sum(a["z"] for a in drivers) / len(drivers)], "driver axle height, middle of the drivers")
        cfg["SndFire"] = est(door, "fire door")
        cfg["SndAirPump"] = est([-min(1.2, half), (bmin[1] + bmax[1]) / 2, mid_z], "side of the boiler (G-29 layout)")
        cfg["SndCoalDump"] = est([0.0, door[1] - 0.6, door[2] + 0.6], "under the firebox")
        cfg["SndCrownSheet"] = est([0.0, door[1] + 0.8, door[2] + 0.6], "above the firebox")
        cfg["SndSand"] = est([0.0, 0.6, drivers[0]["z"] + 0.6], "ahead of the first driver")
        cfg["ExplosionAnchor"] = est([0.0, (bmin[1] + bmax[1]) / 2, mid_z], "model centre")

        # ---------------- lamps, oil cups, fittings
        self._lamps(cfg, rec, comps, anchors)
        cfg["PortRefOverrides"] = env({"boiler.FEEDWATER_TEMPERATURE": ""}, "port", "DV_choice", "S-16 and G-29: no feedwater heater")
        rec["hooks"]["OilPoints"] = self._oil(drivers, radius)
        self.choose("oil-cup axle pairs are provisional: the builder first seats cups on modelled rod big-end nubs, "
                    "then tries running boards; a pair with no valid seat is omitted")
        coal_slot, water_slot = self._slots(self.definition_of(lid))
        self._resources(cfg, rec, comps, coal_slot, water_slot, tank=not tender)
        rel_z = (drivers[-1]["z"] + drivers[-2]["z"]) / 2 if len(drivers) > 1 else cab_z + 0.5
        rec["hooks"]["BrakeRelease"] = env({"pos": _r([min(1.1, half), 0.8, rel_z]), "euler": [0, 90, 0]}, "m/deg", "analogue_estimate",
                                           "hint between the rear drivers, right side; the core fits it to the frame (S-16)")
        if not tender:
            rec["hooks"]["HandbrakeWheel"] = env({"pos": _r([-0.9, cab_y - 0.3, rear_end + 0.05]), "euler": [0, 180, 0]}, "m/deg",
                                                 "analogue_estimate", "hint on the cab back, fireman's side; the core fits it to the face (S-16)")
            self.choose("handbrake wheel and brake release placed from hints fitted to the model by the core: check the marker renders")

        # ---------------- renders
        L = bmax[2] - bmin[2]
        h = bmax[1]
        cfg["ExteriorShots"] = _shots([(_r([-2.0 * L, h * 0.6, mid_z]), _r([0, h * 0.5, mid_z]), 35, "built_left.png"),
                                       (_r([L, h * 1.2, bmax[2] + L]), _r([0, h * 0.5, mid_z]), 35, "built_front34.png"),
                                       (_r([-L, h * 1.2, bmin[2] - L]), _r([0, h * 0.5, mid_z]), 35, "built_rear34.png"),
                                       (_r([-6, radius + 0.3, mid_z]), _r([0, radius, mid_z]), 35, "built_gear_left.png")])
        cfg["CabShots"] = _shots([(_r([0, cab_y + 0.6, cab_z - 0.4]), _r([0, door[1] + 0.4, back_z]), 65, "built_cab_backhead.png"),
                                  (_r([-0.2, cab_y + 0.5, cab_z - 0.3]), _r([-0.5, door[1] + 0.3, back_z]), 60, "built_backhead_left.png"),
                                  (_r([0.2, cab_y + 0.5, cab_z - 0.3]), _r([0.5, door[1] + 0.3, back_z]), 60, "built_backhead_right.png")])
        if cfg.get("LampLenses"):
            cfg["LampShots"] = _shots([(_r([3, h, bmax[2] + 6]), _r([0, h * 0.8, bmax[2]]), 40, "built_lamps_front_lit.png")])
        cfg["MarkerShots"] = _shots([(_r([-2.0 * L, h * 0.6, mid_z]), _r([0, h * 0.5, mid_z]), 35, "markers_left.png"),
                                     (_r([2.0 * L, h * 0.6, mid_z]), _r([0, h * 0.5, mid_z]), 35, "markers_right.png")])
        if tender:
            cfg["ConsistShots"] = _shots([(_r([-4 * L, h * 0.6, rear_end - 2]), _r([0, h * 0.5, rear_end - 2]), 35, "consist_left.png"),
                                          (_r([-4, h + 1.5, rear_end - 3]), _r([0, 1.5, rear_end - 0.5]), 40, "consist_drawbar.png")])
        return rec

    # ------------------------------------------------------------------ the tender
    def tender(self, loco_cfg: dict) -> dict | None:
        rec = self.draft.get("tender")
        if not rec:
            return None
        cfg = rec["config"]
        tid = self.inv["tender"]["id"]
        ov = self.probe_of(tid)
        if not ov:
            return rec
        comps = _plain(cfg["Components"])
        anchors = self.anchors(ov)
        cfg["CarName"] = safe_name(cfg.get("CarName"), cfg["CarId"])
        cfg["Version"] = loco_cfg.get("Version", "0.1.0")
        cfg["Author"] = loco_cfg.get("Author")
        cfg["BodyName"] = f"{tid}_body"
        self._liveries(cfg, tid, prefer=_plain(loco_cfg.get("Livery")))
        if not comps:
            self.block("tender-empty", f"{tid}: the tender definition has no components; the loader needs at least one")
        if not cfg.get("MaterialMap"):
            self.block("no-materials", f"{tid}: the tender model's material map is empty")
        self._material_review(cfg, tid)
        self._geometry_review(cfg, tid)
        for key in ("WeightEmptyKg", "WaterCapacityL", "CoalCapacityKg"):
            if not cfg.get(key):
                self.block("tender-data", f"{tid}: the definition lacks {key} (weightEmpty / loadSlots water and coal)")
        td = self.definition_of(tid)
        trucks = [t for t in self.inv.get("trucks", []) if t["owner"] == tid]
        truck_v = next((v for v in self.project.get("vehicles", []) if trucks and v["id"] == trucks[0]["id"]), None)
        sep = td.get("truckSeparation")
        geo = truck_geometry(self.pout.get(trucks[0]["id"], {})) if trucks else None
        if not trucks or not truck_v:
            self.block("tender-trucks", f"{tid}: no truck found for the tender (truckIdentifier)")
            return rec
        if not sep:
            self.block("tender-trucks", f"{tid}: the definition lacks truckSeparation")
            return rec
        if not geo:
            self.block("truck-wheels", f"{trucks[0]['id']}: the probe found no wheel meshes (transforms named Wheel*) on the truck prefab")
            return rec
        if not geo["prefix"]:
            self.block("truck-wheels", f"{trucks[0]['id']}: the truck's wheel objects ({', '.join(geo['names'])}) share no name prefix "
                                       "starting with 'Wheel' that no other object uses" +
                                       (f" (also: {', '.join(geo['strays'][:3])})" if geo["strays"] else ""))
            return rec
        z = sep / 2
        cfg["WheelRadius"] = env(_r(geo["radius"]), "m", "measured", f"probe/probe.json truckWheels ({trucks[0]['id']}): tread band of "
                                                                     f"{len(geo['axles'])} axle(s)")
        self.choose(f"tender wheel radius {geo['radius']:.4f} m from the truck's measured tread (turns the wheels; review with the renders)")
        offs = [_r(a) for a in geo["axles"]]
        cfg["Bogies"] = env([{"Bogie": "BogieF", "BogieCollider": "front", "Axles": [_r(z + o) for o in offs]},
                             {"Bogie": "BogieR", "BogieCollider": "rear", "Axles": [_r(-z + o) for o in offs]}],
                            "m", "derived", f"Definitions {tid}.truckSeparation / 2", "probe/probe.json truckWheels axle offsets")
        cfg["Trucks"] = env([{"Prefab": truck_v["unity_prefab"], "Wheelset": geo["prefix"], "Z": _r(z)},
                             {"Prefab": truck_v["unity_prefab"], "Wheelset": geo["prefix"], "Z": _r(-z)}],
                            "m", "source", f"Definitions {tid}.truckSeparation / 2 (RR places the trucks at +-half)")
        span = max(offs) - min(offs)
        cfg["Wheelsets"] = env([[_r(z), _r(span), _r(2 * geo["radius"]), len(offs), ""], [_r(-z), _r(span), _r(2 * geo["radius"]), len(offs), ""]],
                               "mixed m/count", "derived", "truck positions and measured axles (the tender definition has no wheelsets)")
        cfg["HideFrontCoupler"] = True
        cfg["WheelslipFriction"] = env(0.2, "1", "DV_choice", f"{G29} tender")
        bmin, bmax = ov.get("boundsMin"), ov.get("boundsMax")
        front_end, rear_end = _plain(cfg.get("RrEndFront")), _plain(cfg.get("RrEndRear"))
        if bmin is None:
            self.block("no-geometry", f"{tid}: the probe found no visible geometry on the tender")
            return rec
        rec["hooks"]["CollisionBoxes"] = self._collision(bmin, bmax, front_end, rear_end)
        plates = self._plates(comps, anchors)
        if plates:
            cfg["PlateDecals"] = plates
        anims = cfg.get("AnimationMap") or {}
        loads = []
        for c in comps:
            e = _extra(c)
            clip = (e.get("animation") or {}).get("clipName")
            if c["kind"] == "LoadAnimation" and clip in anims and e.get("loadIdentifier") in ("water", "coal"):
                loads.append([clip, "", f"{e['loadIdentifier']}.NORMALIZED", False])
        cfg["LoadAnimations"] = self._ordered_loads(loads, ov)
        coal_slot, water_slot = self._slots(td)
        self._resources(cfg, rec, comps, coal_slot, water_slot, tank=False, tender_bounds=(bmin, bmax, front_end))
        half = (bmax[0] - bmin[0]) / 2
        rec["hooks"]["HandbrakeWheel"] = env({"pos": _r([-0.9, bmax[1] * 0.65, front_end - 0.25]), "euler": [0, 180, 0]}, "m/deg",
                                             "analogue_estimate", "hint on the tender front, fireman's side; the core fits it (G-29)")
        rec["hooks"]["BrakeRelease"] = env({"pos": _r([min(1.55, half), 1.1, 0.0]), "euler": [0, 180, 0]}, "m/deg", "analogue_estimate",
                                           "hint on the right frame between the trucks; the core fits it (G-29)")
        L, h, mid = bmax[2] - bmin[2], bmax[1], (bmin[2] + bmax[2]) / 2
        cfg["ExteriorShots"] = _shots([(_r([-2.0 * L, h * 0.6, mid]), _r([0, h * 0.5, mid]), 35, "tender_left.png"),
                                       (_r([L, h * 1.2, bmax[2] + L]), _r([0, h * 0.5, mid]), 35, "tender_front34.png"),
                                       (_r([-6, 0.8, mid]), _r([0, 0.5, mid]), 35, "tender_wheels_left.png")])
        return rec

    # ------------------------------------------------------------------ pieces
    def definition_of(self, vid: str) -> dict:
        return getattr(self, "_defs", {}).get(vid, {})

    def _driver_indices(self, cfg: dict) -> list[int]:
        from .record import drivers
        reviewed = self.answers.get('prebuildReview', {}).get('values', {})
        if reviewed.get('physics') == 'geared':
            return reviewed['poweredWheelsets']
        return drivers(self.definition_of(self.draft["vehicleId"]))

    def _material_review(self, cfg: dict, vid: str) -> None:
        if self.pin[vid].get("materialMode") != "renderer-untinted":
            return
        if any(l[1] for l in cfg.get("Liveries") or []):
            self.block("untinted-livery", f"{vid}: renderer materials exist but the named tint map is absent; "
                       "livery colours cannot be mapped safely")
            return
        self.choose(f"{vid}: no named material map; renderer GUIDs identify untinted source materials. "
                    "No livery colours invented. Core 'no colour' warnings for renderer: entries are expected; "
                    "source colourizer options and final appearance remain unvalidated")

    def _geometry_review(self, cfg: dict, vid: str) -> None:
        # pipeline validates allowed fields, bounds, provenance and source fingerprint before extraction.
        fields = self.answers.get('geometryReview', {}).get('vehicles', {}).get(vid, {})
        if fields:
            import copy
            cfg['EndBeamProbeHeight'] = copy.deepcopy(fields['EndBeamProbeHeight'])
            self.choose(f"{vid}: reviewed end-beam sampling band {fields['EndBeamProbeHeight']['value']} m; "
                        "see geometry-review.json for measurements. Core ray-count and placement guards remain active")

    def _liveries(self, cfg: dict, vid: str, prefer: str | None = None) -> None:
        if not cfg.get("Liveries"):
            cfg["Liveries"] = [["Default", []]]
            cfg["Livery"] = "Default"
            self.choose(f"{vid}: the definition has no livery; one untinted 'Default' livery (the textures as exported)")
            return
        names = [l[0] for l in cfg["Liveries"]]
        if prefer in names:
            cfg["Livery"] = prefer
        elif not cfg.get("Livery"):
            cfg["Livery"] = names[0]

    def _mass(self, cfg: dict, lid: str, rec: dict) -> None:
        lb = rec["metadata"]["massLedger"].get("sourceWeightLb")
        if not lb:
            self.block("no-weight", f"{lid}: the definition has no weightEmpty")
            return
        cfg["WeightEmptyKg"] = env(round(lb * LB_KG, 3), "kg", "source", f"Definitions {lid}.weightEmpty {lb:g} lb x 0.45359237")
        self.choose("locomotive mass = Railroader's weightEmpty as given; Derail Valley adds the boiler water on top (E04: "
                    "check whether the source weight already includes it)")

    def _collision(self, bmin, bmax, front_end, rear_end) -> dict:
        lo, hi = max(bmin[2], rear_end), min(bmax[2], front_end)
        y0 = max(bmin[1], 0.35)
        width = min(bmax[0] - bmin[0], 3.0)
        return env([["body", _r([0, (y0 + bmax[1]) / 2, (lo + hi) / 2]), _r([width, bmax[1] - y0, hi - lo])]], "m", "measured",
                   "probe/probe.json model bounds, clipped to the Railroader car ends and 0.35 m above the rail")

    def _plates(self, comps: list[dict], anchors: dict) -> list:
        nums = [(c["name"], _anchor(anchors, c["name"])) for c in comps if c["kind"] == "Decal"
                and _extra(c).get("content") == "RoadNumber" and _anchor(anchors, c["name"])]
        sides = [n for n in nums if abs(n[1][0]) > 0.5]
        left = sorted((n for n in sides if n[1][0] < 0), key=lambda n: n[1][2])
        right = sorted((n for n in sides if n[1][0] > 0), key=lambda n: n[1][2])
        if left and right:
            return [["[car plate anchor1]", left[0][0]], ["[car plate anchor2]", right[0][0]]]
        self.choose("number plates stay where Custom Car Loader puts them: no road-number decal on each side")
        return []

    def _cylinder_cocks(self, cfg: dict, comps: list[dict], lid: str) -> None:
        """RR's CylinderCock anchor sits on the centreline and RR spawns the jets at +-radius (G-29 profile note)."""
        env_comps = cfg["Components"]
        for c in env_comps["value"]:
            if c["kind"] != "CylinderCock":
                continue
            r = _extra(c).get("radius")
            pos = _plain(c["pos"])
            if r and abs(pos[0]) < 0.05:
                c["pos"] = env([float(r), pos[1], pos[2]], "m", "source", f"Definitions {lid} CylinderCock {c['name']}: RR spawns the jets at +-radius")

    def _levers(self, cfg, comps, ov, anims, lid):
        levers, cab_objects, loads, taken = [], [], [], set()
        for c in comps:
            if c["kind"] != "RadialControl":
                continue
            e = _extra(c)
            purpose = str(e.get("purpose") or "").replace(" ", "").casefold()
            clip = (e.get("animation") or {}).get("clipName")
            spec = PURPOSES.get(purpose)
            if not spec:
                self.choose(f"RR control {c['name']!r} (purpose {e.get('purpose')!r}) has no Derail Valley function here; it stays as modelled")
                continue
            role, port, ctl, toggle, label = spec
            if port in taken:
                continue
            if clip not in anims:
                self.choose(f"RR control {c['name']!r} has no clip in the model's clip map: a generated lever replaces it")
                continue
            bound = self.bound_paths(ov, clip)
            parent = c.get("parentPath") or ""
            path = next((b for b in sorted(bound, key=len) if parent == b or parent.startswith(b + "/")), None)
            if not parent:
                # Some mods put interaction anchors in car space, separate from the animated handle.
                # Accept only one animated hierarchy, within that control's source interaction radius.
                roots = [p for p in bound if p and not any(p.startswith(q + "/") for q in bound if q and q != p)]
                anchor = _anchor(self.anchors(ov), c["name"])
                nodes = self.nodes(ov)
                reach = e.get("radius")
                if len(roots) == 1 and anchor and roots[0] in nodes and isinstance(reach, (int, float)) and reach > 0:
                    distance = math.dist(anchor, nodes[roots[0]])
                    if distance <= reach:
                        path = roots[0]
                        self.choose(f"RR control {c['name']!r}: car-space anchor matched to its sole animated hierarchy "
                                    f"{path!r} ({distance:.3f} m from pivot, source radius {reach:g} m); "
                                    "grip ownership, pivot/travel and response remain pending")
            if not path:
                self.choose(f"RR control {c['name']!r}: its clip {clip!r} does not move its part {parent!r}; a generated lever replaces it")
                continue
            others = [p for k in anims if k != clip for p in self.bound_paths(ov, k)]
            if any(o.startswith(path + "/") for o in others):
                self.choose(f"RR control {c['name']!r}: part {path!r} also carries parts other clips move; a generated lever replaces it")
                continue
            n, spring, damper, mass, drag, ang, scroll, sspring, frac = LEVER_PHYSICS[role]
            lever = {"Path": path, "AnimKey": clip, "Port": port, "Ctl": ctl, "Toggle": toggle, "Hidden": False, "External": False,
                     **({"Label": label} if label else {})}
            phys = {"path": path, "min": 0, "notches": n, "spring": spring, "damper": damper, "mass": mass, "drag": drag,
                    "angularDrag": ang, "scroll": scroll, "scrollSpring": sspring, **({"scrollAngleFraction": frac} if frac else {})}
            levers.append({**lever, "_phys": phys})
            taken.add(port)
            if role == "reverser":
                cfg["ReverserHandle"], cfg["ReverserClip"] = path, clip
            else:
                cab_objects.append(path)
                if role == "whistle":
                    cfg["WhistleLinkageClip"] = clip
                elif any(not (b == path or b.startswith(path + "/")) for b in bound):
                    loads.append([clip, "", port, False])  # the rest of the clip (rods) follows the port outside
        return levers, cab_objects, loads, taken

    @staticmethod
    def _unique_loads(loads: list) -> list:
        seen, out = set(), []
        for l in loads:
            if l[0] not in seen:
                seen.add(l[0])
                out.append(l)
        return out

    def _ordered_loads(self, loads: list, ov: dict) -> list:
        """Create child animation groups before a parent group moves their source hierarchy."""
        remaining = self._unique_loads(loads)
        original = list(remaining)
        paths = {row[0]: self.bound_paths(ov, row[0]) for row in remaining}
        ordered = []
        while remaining:
            ready = [row for row in remaining if not any(
                child.startswith(parent + "/")
                for other in remaining if other is not row
                for parent in paths[row[0]] if parent
                for child in paths[other[0]])]
            if not ready:
                self.block("animation-order", "load animations have conflicting parent/child ownership; "
                           "their bindings need review before building")
                return original
            for row in ready:
                ordered.append(row)
                remaining.remove(row)
        if ordered != original:
            self.choose("load animation groups created child-first to preserve nested source paths: "
                        + ", ".join(row[0] for row in ordered))
        return ordered

    def _lamps(self, cfg, rec, comps, anchors) -> None:
        lenses, front, rear = [], [], []
        for c in comps:
            if c["kind"] != "Headlight" or not _anchor(anchors, c["name"]):
                continue
            p = _anchor(anchors, c["name"])
            fwd = bool(_extra(c).get("forward", True))
            if any(math.dist(p, l[1]) < 0.15 and l[3] == fwd for l in lenses):
                continue
            key = f"L{len(lenses) + 1}"
            lenses.append([key, _r(p), 0.28, fwd])
            (front if fwd else rear).append(key)
        if not lenses:
            self.choose("no Headlight component: the headlight control works but no lamp is lit")
        cfg["LampLenses"] = env(lenses, "m", "source", "Headlight components (probe anchors); lens 0.28 m as S-16")
        cfg["FrontLow"], cfg["FrontHigh"], cfg["RearLow"], cfg["RearHigh"] = front, front, rear, rear
        rec["hooks"]["LampKey"] = {}

    @staticmethod
    def _oil(drivers: list[dict], radius: float) -> dict:
        pts = []
        for i, a in enumerate(drivers):
            for side, x in (("L", -0.95), ("R", 0.95)):
                pts.append([f"oil_{i + 1}{side}", _r([x, 2 * radius + 0.05, a["z"]])])
        return env(pts, "m", "DV_choice", "provisional axle-pair hints; final cup count follows measured rod-nub or running-board seats")

    @staticmethod
    def _slots(d: dict) -> tuple[int | None, int | None]:
        coal = water = None
        for i, s in enumerate(d.get("loadSlots") or []):
            ident = str(s.get("requiredLoadIdentifier", "")).casefold()
            if ident == "coal" and coal is None:
                coal = i
            elif ident == "water" and water is None:
                water = i
        return coal, water

    def _resources(self, cfg, rec, comps, coal_slot, water_slot, tank: bool, tender_bounds=None) -> None:
        targets = [(c["name"], _extra(c).get("slotIndex")) for c in comps if c["kind"] == "LoadTarget" and not c.get("parentPath")]
        coal = [n for n, s in targets if s == coal_slot and coal_slot is not None]
        water = [n for n, s in targets if s == water_slot and water_slot is not None]
        if coal:
            cfg["CoalTargetComp"] = coal[0]
        if water:
            cfg["WaterTargetComps"] = water
        if coal_slot is None:
            return
        if tank:
            rear = _plain(cfg["RrEndRear"])
            y = _plain(cfg.get("FireDoorCentre"))[1] if cfg.get("FireDoorCentre") else 1.4
            rec["hooks"]["CoalPile"] = env({"centre": _r([0, y, rear + 0.6]), "size": [1.5, 0.6, 0.3]}, "m", "analogue_estimate",
                                           "bunker opening at the cab back, fire door height (S-16 layout)")
        elif tender_bounds:
            bmin, bmax, front = tender_bounds
            rec["hooks"]["CoalPile"] = env({"centre": _r([0, bmax[1] * 0.65, front - 1.1]), "size": _r([min(2.2, bmax[0] - bmin[0] - 0.4), 0.9, 1.7])},
                                           "m", "analogue_estimate", "coal space at the tender front (G-29 layout)")
        self.choose("coal shovelling box placed by layout rule (S-16 bunker / G-29 tender front): check the shovel reaches it")


def complete(draft: dict, inv: dict, probe_in: dict, probe_out: dict | None, project: dict, answers: dict,
             definitions: dict[str, dict], composites: dict[str, str] | None = None) -> tuple[dict, list[str]]:
    """The buildable record and its review items; raises Blocked when it cannot be completed."""
    import copy
    rec = copy.deepcopy(draft)
    b = _Builder(rec, inv, probe_in, probe_out or {}, project, answers)
    b._defs = definitions
    b.loco()
    if rec.get("tender"):
        b.tender(rec["config"])
    if b.blocks:
        raise Blocked(b.blocks, b.choices)
    for vid, prefab in (composites or {}).items():  # the model with its parts placed (Rr2dvBuild makes it)
        cfg = rec["config"] if vid == rec["vehicleId"] else rec["tender"]["config"]
        cfg["SrcPrefab"] = prefab
    # SimSpec: unknown values stay unknown; the core keeps the Derail Valley basis default for anything not given.
    sim = rec["hooks"]["SimSpec"]
    for comp in list(sim):
        sim[comp] = {k: v for k, v in sim[comp].items() if v is not None}
        if not sim[comp]:
            del sim[comp]
    dropped = [p for p in rec["metadata"]["pending"] if p.startswith("boiler diameter")]
    if dropped:
        b.choose("boiler diameter, length, capacity and spawn water keep the Derail Valley basis boiler until measured")
    for key in ("WeightEmptyKg", "Bogies"):
        if rec["config"].get(key) is None:
            raise Blocked([{"code": "incomplete", "message": f"{key} could not be completed"}])
    rec["metadata"]["status"] = "build candidate: runtime acceptance pending (CTRL-01/CTRL-02, Q04)"
    rec["metadata"]["buildChoices"] = b.choices
    return rec, b.choices
