"""Tread candidates from the probe's wheel radius bands (board X30, X33). A candidate is for review, never a measurement.

The probe reports every 1 mm radius band of the wheel meshes' surface near the source radius, with the lateral extent
it covers (axle-centric, sides folded) and the most common exact radius in it. A tyre tread is the wheel's OUTER surface
across the tyre's width (S16 reviewed: r 0.488783 m across x 0.726..0.801 m): only the flange beside it is bigger.
Rims, inner faces and wheel centres can form wider bands, but they lie under the tread and flange (X33: on the real S16
a 0.189 m band at a lower radius beat the 0.082 m tyre band on width alone). So a band mostly covered laterally by
larger-radius bands is an inner surface; among the outer bands the widest is the tread, and the largest radius overall,
when bigger, is the flange. Anything short of a clear answer is marked low confidence.
"""
from __future__ import annotations

MERGE_M = 0.0005         # bands closer than this are one surface split across two 1 mm bins
COVERED_MAX = 0.5        # an outer surface has at most half its width under larger-radius bands
MIN_TREAD_SPAN_M = 0.02
RIVAL_SHARE = 0.6        # another outer band this wide makes the choice ambiguous
SOURCE_AGREEMENT = 0.05  # a tread more than 5% from the source radius needs a closer look
MODE_SHARE = 0.25        # the exact-radius mode stands for the band when it holds this share of its vertices


def _merged(bands: list[dict]) -> list[dict]:
    out: list[dict] = []
    for b in sorted((b for b in bands if b.get("vertices", 0) > 0), key=lambda b: b["radius"]):
        b = {"modeRadius": b["radius"], "modeVertices": 0, "radiusMin": b["radius"], "radiusMax": b["radius"], **b}
        if out and b["radius"] - out[-1]["radius"] < MERGE_M:
            a = out[-1]
            n = a["vertices"] + b["vertices"]
            mode = a if a["modeVertices"] >= b["modeVertices"] else b
            out[-1] = {"radius": (a["radius"] * a["vertices"] + b["radius"] * b["vertices"]) / n, "vertices": n,
                       "modeRadius": mode["modeRadius"], "modeVertices": mode["modeVertices"],
                       "radiusMin": min(a["radiusMin"], b["radiusMin"]), "radiusMax": max(a["radiusMax"], b["radiusMax"]),
                       "lateralMin": min(a["lateralMin"], b["lateralMin"]), "lateralMax": max(a["lateralMax"], b["lateralMax"])}
        else:
            out.append(b)
    for b in out:
        b["span"] = b["lateralMax"] - b["lateralMin"]
    return out


def covered(band: dict, larger: list[dict]) -> float:
    """Share of band's lateral extent that larger-radius bands also cover."""
    lo, hi = band["lateralMin"], band["lateralMax"]
    pieces = sorted((max(lo, o["lateralMin"]), min(hi, o["lateralMax"])) for o in larger
                    if o["lateralMax"] > lo and o["lateralMin"] < hi)
    if hi <= lo:
        return 1.0 if pieces else 0.0
    total, end = 0.0, lo
    for a, b in pieces:
        if b > end:
            total += b - max(a, end)
            end = b
    return total / (hi - lo)


def _radius(b: dict) -> float:
    return b["modeRadius"] if b["modeVertices"] >= MODE_SHARE * b["vertices"] else b["radius"]


def tread(wheel: dict) -> dict:
    """{clip, sourceRadius, tread, lateral, span, flangeRadius, confidence, notes, alternatives, ...} for one wheelset."""
    source = wheel.get("sourceRadius") or 0.0
    out = {"clip": wheel.get("clip", ""), "sourceRadius": source, "tread": None, "lateral": None, "span": None,
           "radiusSpread": None, "flangeRadius": None, "confidence": "none", "notes": [], "alternatives": [], "innerSurfaces": [],
           "meshesUsed": [m["path"] for m in wheel.get("meshes", []) if m.get("used")]}
    bands = _merged(wheel.get("bands") or [])
    if not bands:
        out["notes"].append("no wheel surface measured near the source radius")
        return out
    for b in bands:
        b["covered"] = covered(b, [o for o in bands if o["radius"] > b["radius"]])
    outer = [b for b in bands if b["covered"] <= COVERED_MAX]
    chosen = max(outer, key=lambda b: (b["span"], b["radius"]))
    top = max(bands, key=lambda b: b["radius"])
    out.update(tread=_radius(chosen), lateral=[chosen["lateralMin"], chosen["lateralMax"]], span=chosen["span"],
               radiusSpread=chosen["radiusMax"] - chosen["radiusMin"])
    rivals = sorted((b for b in outer if b is not chosen and b is not top), key=lambda b: -b["span"])
    out["alternatives"] = [{"radius": _radius(b), "span": b["span"]} for b in rivals[:3]]
    out["innerSurfaces"] = [{"radius": b["radius"], "span": b["span"], "covered": round(b["covered"], 3)}
                            for b in sorted((b for b in bands if b["covered"] > COVERED_MAX), key=lambda b: -b["span"])[:3]]
    if top is not chosen:
        out["flangeRadius"] = _radius(top)
    else:
        out["notes"].append("no flange found above the tread")
    if chosen["span"] < MIN_TREAD_SPAN_M:
        out["notes"].append(f"widest outer band is only {chosen['span'] * 1000:.0f} mm; the tread may be coned")
    if rivals and rivals[0]["span"] >= RIVAL_SHARE * chosen["span"]:
        out["notes"].append(f"another outer band at {_radius(rivals[0]):.4f} m is nearly as wide")
    if source and abs(out["tread"] - source) > SOURCE_AGREEMENT * source:
        out["notes"].append(f"tread differs from the source radius {source:g} m by more than {SOURCE_AGREEMENT:.0%}")
    if not out["meshesUsed"]:
        out["notes"].append("no wheel-like mesh identified")
    out["confidence"] = "low" if out["notes"] else "high"
    return out
