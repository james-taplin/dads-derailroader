"""The `audit` stage: check the exported pack before anything is installed (guide Q05 for a new locomotive).

Here: the pack folder holds Info.json and its bundle(s), Info.json names the locomotive and requires Custom Car Loader,
and the hashes still match what the build produced. In Unity (Rr2dvAudit.cs, a second editor run on the same project),
the bundle is read by Unity's own loader: no AudioClips, behaviours only from CCL.Types, the HUD controls and readings,
the driving controls' ports, unique simulation IDs, one cab teleport, and each car type's mass and wheel radius as
recorded. Build-report warnings are listed for review (Q04 needs a written disposition for each; a person gives it).
Passing is not acceptance: the pack stays "runtime pending" until it has been checked in game (CTRL-01/CTRL-02).
"""
from __future__ import annotations

import json
from pathlib import Path

from . import unityrun
from .jsonio import read_json, sha256_file, write_json

AUDIT_INPUT = "Assets/Rr2dv/AuditInput.json"
REQUIRED_PORTS = ["throttle.EXT_IN", "reverser.CONTROL_EXT_IN", "brake.EXT_IN", "indBrake.EXT_IN", "whistle.EXT_IN"]
READER_CONTROLS = {"cylinderCock.EXT_IN": "cylCock", "injector.EXT_IN": "injector", "fireboxDoor.EXT_IN": "firedoor",
                   "blower.EXT_IN": "blower", "damper.EXT_IN": "damper", "blowdown.EXT_IN": "blowdown",
                   "coalDumpControl.EXT_IN": "coalDump", "lubricatorControl.EXT_IN": "lubricator",
                   "headlightDecoder.HEADLIGHTS_EXT_IN": "headlightsFront", "cabLight.EXT_IN": "cabLight", "bellControl.EXT_IN": "bell"}
INDICATORS = ["speed", "steam", "chestPressure", "brakePipe", "mainReservoir", "brakeCylinder", "locoWaterLevel",
              "locoCoalLevel", "tenderWaterLevel", "tenderCoalLevel"]


class AuditError(RuntimeError):
    pass


def _plain(n):
    from .buildrecord import _plain as p
    return p(n)


def audit_input(rec: dict, pack: Path) -> dict:
    cfg = _plain(rec["config"])
    cars = [{"id": cfg["CarId"], "mass": cfg["WeightEmptyKg"], "wheelRadius": cfg["WheelRadius"], "locomotive": True}]
    folders = [f"Assets/_CCL_CARS/{cfg['CarName']}", f"Assets/_CCL_CARS/{cfg['CarId']}"]
    if rec.get("tender"):
        t = _plain(rec["tender"]["config"])
        cars.append({"id": t["CarId"], "mass": t["WeightEmptyKg"], "wheelRadius": t["WheelRadius"], "locomotive": False})
        folders += [f"Assets/_CCL_CARS/{t['CarName']}", f"Assets/_CCL_CARS/{t['CarId']}"]
    ports = [l["Port"] for l in cfg.get("RrLevers") or [] if l.get("Port")] + [p["Port"] for p in cfg.get("Placed") or []]
    required = sorted(set(REQUIRED_PORTS) | set(ports))
    controls = sorted({READER_CONTROLS[p] for p in required if p in READER_CONTROLS})
    bundles = [str(f.resolve()) for f in sorted(pack.iterdir())
               if f.is_file() and f.name != "Info.json" and f.suffix.casefold() != ".manifest"]
    from .buildrecord import _extra
    opening_clips = set()
    for car_record in (rec, rec.get('tender')):
        if not car_record:
            continue
        for component in _plain(car_record['config']).get('Components') or []:
            if component['kind'] != 'ToggleAnimation':
                continue
            data = _extra(component)
            title = str(data.get('title', '')).casefold()
            if data.get('enabled', True) is False or 'firebox' in title or 'cylinder cocks' in title or str(data.get('key', '')).casefold() == 'cylcock':
                continue
            opening_clips.add((car_record.get('vehicleId', _plain(car_record['config'])['CarId']),
                               (data.get('animation') or {}).get('clipName')))
    return {"schema": 1, "bundles": bundles, "carFolders": folders, "cars": cars, "controls": controls, "ports": required,
            "openingCount": len(opening_clips),
            "indicators": INDICATORS, "review": rec.get("metadata", {}).get("review", {}).get("values")}


def check_pack(rec: dict, pack: Path, files: dict[str, str]) -> list[str]:
    errors = []
    cfg = _plain(rec["config"])
    now = {f.name: sha256_file(f) for f in sorted(pack.iterdir()) if f.is_file()}
    if now != files:
        errors.append("the pack changed after the build (file hashes differ)")
    if len([f for f in now if f != "Info.json"]) == 0:
        errors.append("the pack has no bundle")
    try:
        info = json.loads((pack / "Info.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        return errors + [f"Info.json unreadable: {e}"]
    if "DVCustomCarLoader" not in (info.get("Requirements") or []):
        errors.append("Info.json does not require DVCustomCarLoader")
    return errors


def run(run_path: Path, unity: Path | None, project: dict, rec: dict, built: dict) -> dict:
    pack = Path(built["pack"])
    errors = check_pack(rec, pack, built["files"])
    data = audit_input(rec, pack)
    write_json(run_path / project["project"] / AUDIT_INPUT, data)
    out = run_path / "audit"
    result = unityrun.run_method(unity, run_path / project["project"], "Rr2dvAudit.Run", out, {"RR2DV_AUDIT_OUT": str(out.resolve())})
    report = read_json(out / "audit.json") if (out / "audit.json").exists() else {}
    if result.get("status") not in ("passed", "failed") or not report:
        raise AuditError(f"the Unity audit did not finish: {result.get('error') or result} (see {out})")
    errors += report.get("errors") or []
    warnings = list(report.get("warnings") or [])
    info = json.loads((pack / "Info.json").read_text(encoding="utf-8-sig")) if (pack / "Info.json").is_file() else {}
    if info.get("Id") != _plain(rec["config"])["CarId"]:  # our G-29/C-21 packs carry the loco's CarId (audit_build.py)
        warnings.append(f"Info.json Id {info.get('Id')!r} differs from the locomotive's CarId {_plain(rec['config'])['CarId']!r}")
    summary = {"status": "passed" if not errors else "failed", "errors": errors, "warnings": warnings,
               "buildWarnings": built.get("warnings") or [], "audioClips": report.get("audioClips"),
               "scriptAssemblies": report.get("scriptAssemblies"), "portFeeders": report.get("portFeeders"),
               "files": built["files"], "runtimeValidated": False,
               "acceptance": "runtime pending: CTRL-01/CTRL-02 checks in Derail Valley are still to be done"}
    write_json(out / "summary.json", summary)
    return summary
