"""Settings a Railroader code mod reads from a loco's own definition (never its DLL: CLAUDE.md, personal use).

A code-mod component changes how the loco behaves in Railroader, but Derail Valley never runs that code, so what it does
has to be built into the pack deliberately through a vehicle choice. Each known component kind has an interpreter that
turns its definition fields into choices; any other code-mod component has its numeric settings listed, with the ones
that look like a multiplier, ratio or gear flagged, so nothing is dropped silently (James, 2026-09-28).
"""
from __future__ import annotations

import math
import re

from .rrmod import CODE_MOD_KINDS, components

INCH_M = 0.0254
FLAGGED = re.compile(r"multipl|ratio|gear|power|factor|scale|boost|efficien", re.I)
SKIP = {"kind", "name", "transform", "parent", "enabled"}


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def settings(comp: dict) -> dict:
    """The component's own scalar settings (numbers, flags, text), as the definition gives them."""
    return {k: v for k, v in comp.items() if k not in SKIP and isinstance(v, (int, float, str, bool))}


def _base_te(d: dict) -> tuple[float, float] | None:
    """Railroader's own simple-engine pull 0.85·P·d²·S/D (guide E02) and the main driver diameter in inches."""
    sets = d.get("wheelsets") or []
    main = d.get("mainDriverIndex", 0)
    dia = _num((sets[main] if isinstance(main, int) and 0 <= main < len(sets) else {}).get("diameter"))
    p, bore, stroke = (_num(d.get(k)) for k in ("maximumBoilerPressure", "pistonDiameterInches", "pistonStrokeInches"))
    if not all((dia, p, bore, stroke)):
        return None
    dia_in = dia / INCH_M
    return .85 * p * bore ** 2 * stroke / dia_in, dia_in


def _legos_articulated(d: dict, s: dict) -> dict:
    """LegosBetterSteam ArticulatedSteamEngineComponent: a second engine (fields 'diamater' - the mod's spelling - and
    'stroke', 'cylinderType' 0 simple / 1 compound / 2 compound with a simpling valve, 'baseIsLP'). Our decompile notes
    (tooling/GUIDE_Railroader_to_DV_CCL.md, 'Runtime mods change the pull'): starting pull = base engine + second
    engine; simple adds 0.85·P·d²·S/D, compound adds 0.923·(0.85·P·(d·0.2055/D_m·39.37))/2. Pull at speed barely changes."""
    base = _base_te(d)
    d2, s2 = _num(s.get("diamater", s.get("diameter"))), _num(s.get("stroke"))
    mode = s.get("cylinderType")
    notes = []
    if base is None or not d2:
        return {"options": [], "notes": ["LegosBetterSteam articulated engine: not enough figures to compute its pull"]}
    te, dia_in = base
    p = _num(d.get("maximumBoilerPressure"))
    simple = te + .85 * p * d2 ** 2 * (s2 or _num(d.get("pistonStrokeInches"))) / dia_in
    compound = te + .923 * (.85 * p * (d2 * .2055 / (dia_in * INCH_M) * 39.37)) / 2
    if s.get("baseIsLP"):
        notes.append("baseIsLP is set: the base engine is the low-pressure side; its effect on pull is not in our notes")
    options = [{"id": "legos-compound", "label": "LegosBetterSteam compound", "lbf": round(compound)},
               {"id": "legos-simple", "label": "LegosBetterSteam simple", "lbf": round(simple)}]
    if mode == 0:
        options.reverse()
    notes.append({0: "the mod runs this engine simple", 1: "the mod runs this engine compound",
                  2: "the mod runs this engine compound with a simpling valve (not a Derail Valley control yet)"}
                 .get(mode, f"cylinderType {mode!r} is not one our notes describe"))
    return {"options": options, "notes": notes, "cylinders": 4}


INTERPRETERS = {"ArticulatedSteamEngineComponent": _legos_articulated}


def review(d: dict) -> dict:
    """Pull options and listed settings for the pre-build review. The first option is the suggestion."""
    out = {"options": [], "notes": [], "unrecognised": []}
    published = _num(d.get("publishedTractiveEffort"))
    base = _base_te(d)
    for comp in components(d):
        kind = str(comp.get("kind"))
        if kind not in CODE_MOD_KINDS:
            continue
        provider = CODE_MOD_KINDS[kind][0]
        found = settings(comp)
        if kind in INTERPRETERS:
            got = INTERPRETERS[kind](d, found)
            out["options"] += [{**o, "provider": provider, "evidence": f"{provider} {kind} settings in the definition"}
                               for o in got["options"]]
            out["notes"] += [f"{provider} {kind}: {n}" for n in got["notes"]]
            if got.get("cylinders"):
                out["cylinders"] = got["cylinders"]
        else:
            out["unrecognised"].append({"provider": provider, "kind": kind, "settings": found,
                                        "flagged": sorted(k for k in found if FLAGGED.search(k))})
    if out["options"]:  # the mod's own figure first: Railroader runs it when the mod is installed (guide E02)
        if published:
            out["options"].append({"id": "published", "label": "Published tractive effort", "lbf": round(published),
                                   "evidence": "Definitions.publishedTractiveEffort"})
        elif base:
            out["options"].append({"id": "railroader", "label": "Railroader without the mod", "lbf": round(base[0]),
                                   "evidence": "0.85 x P x d² x S / D from the definition"})
    return out
