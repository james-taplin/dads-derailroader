"""Tread candidates from the probe's wheel radius bands (board X30). A candidate is for review, never a measurement.

The probe reports every 1 mm radius band of the wheel meshes' outer surface near the source radius, with the lateral
extent it covers. A tyre tread is a constant-radius band across the tyre's width (S16: r 0.488783 m across
x 0.726..0.801 m); the flange tip is a narrower band at a larger radius, and the tyre's inner face or a rim can form wide
bands at smaller radii. So among the wide bands (at least SPAN_SHARE of the widest) the largest radius is the tread;
the largest radius overall, when bigger, is the flange. Anything short of a clear answer is marked low confidence.
"""
from __future__ import annotations

MERGE_M = 0.0005        # bands closer than this are one surface split across two 1 mm bins
SPAN_SHARE = 0.6
MIN_TREAD_SPAN_M = 0.02
SOURCE_AGREEMENT = 0.05  # a tread more than 5% from the source radius needs a closer look


def _merged(bands: list[dict]) -> list[dict]:
    out: list[dict] = []
    for b in sorted((b for b in bands if b.get("vertices", 0) > 0), key=lambda b: b["radius"]):
        if out and b["radius"] - out[-1]["radius"] < MERGE_M:
            a = out[-1]
            n = a["vertices"] + b["vertices"]
            out[-1] = {"radius": (a["radius"] * a["vertices"] + b["radius"] * b["vertices"]) / n, "vertices": n,
                       "lateralMin": min(a["lateralMin"], b["lateralMin"]), "lateralMax": max(a["lateralMax"], b["lateralMax"])}
        else:
            out.append(dict(b))
    for b in out:
        b["span"] = b["lateralMax"] - b["lateralMin"]
    return out


def tread(wheel: dict) -> dict:
    """{clip, sourceRadius, tread, lateral, span, flangeRadius, confidence, notes, alternatives} for one wheelset."""
    source = wheel.get("sourceRadius") or 0.0
    out = {"clip": wheel.get("clip", ""), "sourceRadius": source, "tread": None, "lateral": None, "span": None,
           "flangeRadius": None, "confidence": "none", "notes": [], "alternatives": [],
           "meshesUsed": [m["path"] for m in wheel.get("meshes", []) if m.get("used")]}
    bands = _merged(wheel.get("bands") or [])
    if not bands:
        out["notes"].append("no wheel surface measured near the source radius")
        return out
    widest = max(b["span"] for b in bands)
    wide = [b for b in bands if b["span"] >= SPAN_SHARE * widest]
    chosen = max(wide, key=lambda b: b["radius"])
    top = max(bands, key=lambda b: b["radius"])
    out.update(tread=chosen["radius"], lateral=[chosen["lateralMin"], chosen["lateralMax"]], span=chosen["span"])
    out["alternatives"] = [{"radius": b["radius"], "span": b["span"]} for b in sorted(wide, key=lambda b: -b["span"]) if b is not chosen]
    if top is not chosen:
        out["flangeRadius"] = top["radius"]
    else:
        out["notes"].append("no flange found above the tread")
    if chosen["span"] < MIN_TREAD_SPAN_M:
        out["notes"].append(f"widest constant band is only {chosen['span'] * 1000:.0f} mm; the tread may be coned")
    if source and abs(chosen["radius"] - source) > SOURCE_AGREEMENT * source:
        out["notes"].append(f"tread differs from the source radius {source:g} m by more than {SOURCE_AGREEMENT:.0%}")
    if not out["meshesUsed"]:
        out["notes"].append("no wheel-like mesh identified")
    out["confidence"] = "low" if out["notes"] else "high"
    return out
