"""Preflight for a vehicle record, with the rules our loader (tooling/builder/tools/unity/LlwVehicleRecord.cs) applies,
so a record it would reject is caught before Unity starts (a Unity round trip costs minutes). The field names come
from the snapshot's LocoConfig.cs itself, never from a copy here. This is a check, not the loader: the loader in
Unity still decides.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

BASES = {"source", "measured", "derived", "analogue_estimate", "DV_choice"}
RECORD_KEYS = {"schemaVersion", "vehicleId", "config", "hooks", "metadata", "tender"}
TENDER_KEYS = {"config", "hooks", "metadata"}
HOOKS = {"SimSpec", "CollisionBoxes", "OilPoints", "BrakeRelease", "HandbrakeWheel", "CoalPile", "LampKey", "LeverPhysics"}
REQUIRED = ["CarId", "CarName", "Version", "Author", "SrcPrefab", "Work", "BodyName", "Livery", "Components", "MaterialMap",
            "AnimationMap", "Liveries", "Wheelsets", "WeightEmptyKg", "WheelRadius", "WaterCapacityL", "CoalCapacityKg"]
LEVER_PHYSICS_FIELDS = {"path", "min", "notches", "spring", "damper", "mass", "drag", "angularDrag", "scroll", "scrollSpring",
                        "scrollAngleFraction"}


class RecordError(ValueError):
    pass


def _lococonfig() -> Path:
    from .unityproject import tooling_root
    return tooling_root() / "builder" / "tools" / "unity" / "LocoConfig.cs"


def _split_fields(decl: str) -> tuple[str, list[str]]:
    """'(string a, int b)[] X = ..., Y' -> (type, [X, Y]); generic and tuple commas are not separators."""
    depth, i = 0, 0
    while i < len(decl):
        ch = decl[i]
        if ch in "(<[":
            depth += 1
        elif ch in ")>]":
            depth -= 1
        elif ch == " " and depth == 0 and decl[:i].strip():
            break
        i += 1
    type_, rest = decl[:i].strip(), decl[i:]
    names, depth, current, skipping = [], 0, "", False
    for ch in rest:
        if ch in "(<[{":
            depth += 1
        elif ch in ")>]}":
            depth -= 1
        if depth == 0 and ch == ",":
            names.append(current)
            current, skipping = "", False
            continue
        if depth == 0 and ch == "=":
            skipping = True
        if not skipping:
            current += ch
    names.append(current)
    return type_, [n.strip() for n in names if n.strip()]


@lru_cache(maxsize=None)
def classes() -> dict[str, dict[str, str]]:
    """Public instance fields of every class in LocoConfig.cs: {class: {field: type}}."""
    text = _lococonfig().read_text(encoding="utf-8-sig")
    text = re.sub(r"//[^\n]*", "", text)
    out: dict[str, dict[str, str]] = {}
    for m in re.finditer(r"public class (\w+)\s*\{", text):
        start, depth, i = m.end(), 1, m.end()
        while depth and i < len(text):
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        body = text[start:i - 1]
        fields = {}
        for stmt in re.split(r";", body):
            stmt = " ".join(stmt.split())
            if not stmt.startswith("public ") or stmt.startswith("public " + m[1] + "("):
                continue
            decl = stmt[len("public "):]
            if decl.startswith(("static ", "const ", "readonly ")):
                continue
            type_, names = _split_fields(decl)
            for n in names:
                if re.fullmatch(r"\w+", n):
                    fields[n] = type_
        out[m[1]] = fields
    return out


def _is_envelope(n) -> bool:
    return isinstance(n, dict) and "value" in n and any(k in n for k in ("unit", "basis", "evidence"))


def _evidence(node, path: str, covered: bool, errors: list[str]) -> None:
    if _is_envelope(node):
        extra = set(node) - {"value", "unit", "basis", "evidence", "notes"}
        if extra:
            errors.append(f"{path}: unknown envelope field(s) {sorted(extra)}")
        if not isinstance(node.get("unit"), str) or not node["unit"].strip():
            errors.append(f"{path}: unit is required")
        if node.get("basis") not in BASES:
            errors.append(f"{path}: invalid or missing basis {node.get('basis')!r}")
        ev = node.get("evidence")
        if not ((isinstance(ev, str) and ev.strip()) or (isinstance(ev, list) and ev and all(isinstance(e, str) and e.strip() for e in ev))):
            errors.append(f"{path}: nonempty evidence string or string array is required")
        _evidence(node["value"], path + ".value", True, errors)
    elif isinstance(node, dict):
        for k, v in node.items():
            _evidence(v, f"{path}.{k}", covered, errors)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _evidence(v, f"{path}[{i}]", covered, errors)
    elif isinstance(node, (int, float)) and not isinstance(node, bool) and not covered:
        errors.append(f"{path}: numeric setting requires value/unit/basis/evidence")


def _unwrap(n):
    if _is_envelope(n):
        return _unwrap(n["value"])
    if isinstance(n, dict):
        return {k: _unwrap(v) for k, v in n.items()}
    if isinstance(n, list):
        return [_unwrap(v) for v in n]
    return n


def _element(type_: str) -> str | None:
    m = re.fullmatch(r"(?:List<(\w+)>|(\w+)\[\])", type_)
    return (m[1] or m[2]) if m else None


def _fields(obj, cls: str, path: str, errors: list[str]) -> None:
    known = classes().get(cls)
    if known is None or not isinstance(obj, dict):
        return
    for k, v in obj.items():
        if k not in known:
            errors.append(f"{path}.{k}: unknown or readonly {cls} field")
            continue
        type_ = known[k]
        if type_.startswith(("Func<", "Action<")):
            errors.append(f"{path}.{k}: delegate fields require a supported declarative hook")
            continue
        if v is None:
            if type_ in ("float", "int", "bool", "Vector2", "Vector3", "Quaternion"):
                errors.append(f"{path}.{k}: unknown/null cannot populate {type_}")
            continue
        inner = _element(type_)
        if inner in classes() and isinstance(v, list):
            for i, item in enumerate(v):
                _fields(item, inner, f"{path}.{k}[{i}]", errors)
        elif type_ in classes():
            _fields(v, type_, f"{path}.{k}", errors)


def _car(rec: dict, path: str, errors: list[str], tender: bool) -> None:
    extra = set(rec) - (TENDER_KEYS if tender else RECORD_KEYS)
    if extra:
        errors.append(f"{path}: unknown field(s) {sorted(extra)}")
    cfg = rec.get("config")
    if not isinstance(cfg, dict):
        errors.append(f"{path}: missing config")
        return
    _evidence(cfg, path + ".config", False, errors)
    plain = _unwrap(cfg)
    if "Tender" in plain:
        errors.append(f"{path}.config.Tender: use the tender record")
    _fields(plain, "LocoConfig", path + ".config", errors)
    for k in REQUIRED:
        v = plain.get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            errors.append(f"{path}.config.{k}: required and must be known")
    work = plain.get("Work") or ""
    if not (work.startswith("Assets/") and len(work.split("/")) >= 3 and ".." not in work and "\\" not in work):
        errors.append(f"{path}.config.Work: must be a dedicated Assets/<conversion>/<car> subtree")
    if not str(plain.get("SrcPrefab") or "").startswith("Assets/"):
        errors.append(f"{path}.config.SrcPrefab: must be an Assets path")
    num = lambda k: plain.get(k) if isinstance(plain.get(k), (int, float)) else None
    if (num("WeightEmptyKg") or 0) <= 0 or (num("WheelRadius") or 0) <= 0 or (num("WaterCapacityL") or 0) < 0 or (num("CoalCapacityKg") or 0) < 0:
        errors.append(f"{path}: mass/radius must be positive; resource capacities cannot be negative")
    for k in ("Components", "MaterialMap", "Liveries", "Wheelsets"):
        if not plain.get(k):
            errors.append(f"{path}.config.{k}: cannot be empty")
    if plain.get("Liveries") and plain.get("Livery") not in [l[0] for l in plain["Liveries"]]:
        errors.append(f"{path}.config.Livery: does not exactly match a source livery")
    if not plain.get("Bogies") and not plain.get("EngineUnits"):
        errors.append(f"{path}: requires a measured bogie or engine layout")
    hooks = rec.get("hooks") or {}
    _evidence(hooks, path + ".hooks", False, errors)
    unknown = set(hooks) - HOOKS
    if unknown:
        errors.append(f"{path}.hooks: unknown hook(s) {sorted(unknown)}")
    if "CollisionBoxes" not in hooks:
        errors.append(f"{path}.hooks.CollisionBoxes: required measured collision layout")
    if not tender and "SimSpec" not in hooks:
        errors.append(f"{path}.hooks.SimSpec: required explicit simulation specification")
    levers = {l.get("Path") for l in plain.get("RrLevers") or []}
    seen = set()
    for i, lp in enumerate(_unwrap(hooks.get("LeverPhysics")) or []):
        if set(lp) - LEVER_PHYSICS_FIELDS:
            errors.append(f"{path}.hooks.LeverPhysics[{i}]: unknown field(s) {sorted(set(lp) - LEVER_PHYSICS_FIELDS)}")
        if lp.get("path") not in levers or lp.get("path") in seen:
            errors.append(f"{path}.hooks.LeverPhysics[{i}]: physics path must select exactly one lever once: {lp.get('path')}")
        seen.add(lp.get("path"))
    missing_phys = sorted(p for p in levers if p not in seen)
    if missing_phys:
        errors.append(f"{path}: RR lever(s) without joint physics (the core needs them): {missing_phys}")
    for comp, fields in (_unwrap(hooks.get("SimSpec")) or {}).items():
        for k, v in (fields or {}).items():
            if v is None:
                errors.append(f"{path}.hooks.SimSpec.{comp}.{k}: null would be set on the simulation")


def check(record: dict) -> list[str]:
    """Every problem the loader would reject, as messages; empty when the record passes."""
    errors: list[str] = []
    if record.get("schemaVersion") != 1:
        errors.append("schemaVersion: expected 1")
    if not isinstance(record.get("vehicleId"), str) or not record["vehicleId"].strip():
        errors.append("vehicleId: required source identifier")
    _car(record, "$record", errors, tender=False)
    if record.get("tender") is not None:
        _car(record["tender"], "$record.tender", errors, tender=True)
        if not _unwrap(record["tender"].get("config", {})).get("IsTender"):
            errors.append("$record.tender: IsTender must be true")
    return errors
