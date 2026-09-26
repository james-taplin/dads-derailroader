"""The conversion pipeline: runs each available stage in order and stops at the first one that fails or is
not implemented yet. Input folders and archives are only ever read."""
from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from . import assetripper, probeinput, record, unityproject, unityrun
from .jsonio import read_json
from .jsonio import sha256_file, write_json
from .machine import Machine, check_work_root
from .rrmod import Index, blocking, inventory
from .runs import STAGES, Run, stage_inputs
from .safety import check_write_target, safe_extract_zip

EXIT_OK, EXIT_FAILED, EXIT_INCOMPLETE = 0, 1, 3


@dataclass
class Outcome:
    code: int
    message: str
    run: Run | None = None


def input_kind(path: Path) -> str:
    if path.is_dir():
        return "folder"
    if path.is_file() and zipfile.is_zipfile(path):
        return "zip"
    raise FileNotFoundError(f"{path} is not a folder or a zip archive")


def fingerprint(inv: dict) -> str:
    """Identity of the exact input bytes a conversion used."""
    canonical = json.dumps(inv["packs"], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def choose_locomotive(index: Index, requested: str | None) -> tuple[str | None, str]:
    steam = [obj["identifier"] for _, obj in index.steam_locomotives()]
    if requested:
        if requested in steam:
            return requested, ""
        return None, f"{requested!r} is not a steam locomotive in the input; found: {', '.join(steam) or 'none'}"
    if len(steam) == 1:
        return steam[0], ""
    if not steam:
        others = [obj["identifier"] for _, obj in index.other_locomotives()]
        hint = f" (non-steam locomotives found: {', '.join(others)})" if others else ""
        return None, "no steam locomotive found in the input" + hint
    return None, "the input has several steam locomotives; choose one with --loco: " + ", ".join(steam)


def extract(run: Run, inv: dict, machine: Machine) -> dict:
    """Export every required bundle with AssetRipper (cached by bundle, extractor and target version)."""
    exe = machine.path("assetRipper")
    if exe is None or not exe.is_file():
        raise FileNotFoundError("AssetRipper is not set up: add `assetRipper` to the settings file (see `rr2dv doctor`)")
    cache = machine.work_root / "_cache" / "assetripper"
    exports = {}
    for rec in inv["packs"]:
        bundle = next((f for f in rec["files"] if f["name"].casefold() == "bundle"), None)
        if bundle is None:
            continue
        staged = run.path / "inputs" / rec["root"] / (rec["path"] or rec["name"]) / bundle["name"]
        result = assetripper.export(exe, staged, bundle["sha256"], cache)
        exports[f"{rec['root']}:{rec['path'] or rec['name']}"] = result
    return exports


def convert(input_path: Path, out_dir: Path, machine: Machine, loco: str | None = None,
            search: Sequence[Path] = (), audio: str | None = None, livery: str | None = None,
            wheel_radius: float | None = None) -> Outcome:
    input_path = input_path.resolve()
    out_dir = out_dir.resolve()
    kind = input_kind(input_path)
    work_root = machine.work_root.resolve()
    # Refuse bad targets before creating anything.
    check_work_root(work_root)
    guard = [("input mod", input_path)] + machine.protected()
    check_write_target(work_root, guard)
    check_write_target(out_dir, guard + [("app work folder", work_root)])

    request = {"input": str(input_path), "input_kind": kind, "locomotive": loco, "output": str(out_dir),
               "search_roots": [str(p) for p in search], "audio": audio, "livery": livery,
               "wheel_radius": wheel_radius}
    if kind == "zip":
        request["input_sha256"] = sha256_file(input_path)
    run = Run.create(work_root, loco or input_path.stem, request)
    try:
        return _stages(run, input_path, kind, loco, search, audio, machine, livery, wheel_radius)
    except Exception as e:  # record the failure on the run, then let the caller report it
        current = next((n for n, s in run.record["stages"].items() if s["status"] == "running"), None)
        message = f"{type(e).__name__}: {e}"
        if current:
            run.finish(current, "failed", message)
        run.close("failed", message)
        raise


def _stages(run: Run, input_path: Path, kind: str, loco: str | None, search: Sequence[Path],
            audio: str | None, machine: Machine, livery: str | None = None, wheel_radius: float | None = None) -> Outcome:
    def fail(stage: str, message: str, code: int = EXIT_FAILED) -> Outcome:
        run.finish(stage, "failed", message)
        run.close("failed", message)
        return Outcome(code, message, run)

    run.begin("locate")
    root = input_path
    if kind == "zip":
        root = run.path / "source"
        safe_extract_zip(input_path, root)
    index = Index(root, search)
    write_json(run.path / "index_issues.json", [i.as_dict() for i in index.issues])
    input_errors = [i for i in index.issues if i.severity == "error"]
    if input_errors:
        return fail("locate", "; ".join(i.message for i in input_errors))
    chosen, why = choose_locomotive(index, loco)
    if chosen is None:
        return fail("locate", why)
    run.record["answers"] = {"locomotive": chosen}
    run.finish("locate", "done", f"{chosen} ({len(index.packs)} packs indexed)")

    run.begin("link")
    inv = inventory(index, chosen, audio=audio)
    write_json(run.path / "inventory.json", inv)
    errors = blocking(inv)
    run.record["answers"]["audio"] = inv["audio"]
    if errors:
        return fail("link", f"{len(errors)} blocking issue(s): " + "; ".join(e["message"] for e in errors))
    run.record["input_fingerprint"] = fingerprint(inv)
    warnings = [i for i in inv["issues"] if i["severity"] == "warning"]
    run.finish("link", "done", f"{len(inv['packs'])} packs, {len(inv['parts'])} parts, {len(warnings)} warning(s)")

    run.begin("stage")
    staged = stage_inputs(run, inv, index)
    write_json(run.path / "staged.json", staged)
    run.finish("stage", "done", f"{len(staged['files'])} files copied and verified")

    run.begin("extract")
    exports = extract(run, inv, machine)
    write_json(run.path / "exports.json", exports)
    reused = sum(1 for e in exports.values() if e["cached"])
    run.finish("extract", "done", f"{len(exports)} bundle(s) exported ({reused} reused from cache)")

    run.begin("import")
    car_creator = machine.path("carCreator")
    if car_creator is None or not car_creator.is_file():
        raise FileNotFoundError("CarCreator 3.1.9 is not set up: add `carCreator` to the settings file (see `rr2dv doctor`)")
    project = unityproject.assemble(run.path, inv, exports, car_creator)
    run.finish("import", "done", f"Unity {project['unity']} project with {len(project['vehicles'])} vehicle(s), "
                                 f"{len(project['parts'])} part(s), {project['unique_guids']} GUIDs")

    run.begin("probe")
    probe_in = probeinput.build(run.path, inv, project)
    result = unityrun.run_method(machine.path("unity"), run.path / project["project"], "Rr2dvProbe.Run", run.path / "probe",
                                 {"RR2DV_PROBE_OUT": str(run.path / "probe")})
    if result.get("status") not in ("passed", "problems"):
        return fail("probe", f"Unity probe failed: {result.get('error') or result}")
    problems = result.get("problems", 0)
    run.finish("probe", "done", f"{len(probe_in['vehicles'])} vehicle(s) measured; {problems} problem(s) to review"
                                + (" (see probe/probe.json)" if problems else ""))

    run.begin("record")
    probe_out_file = run.path / "probe" / "probe.json"
    probe_out = read_json(probe_out_file) if probe_out_file.exists() else None
    if livery:
        run.record["answers"]["livery"] = livery
    if wheel_radius:
        run.record["answers"]["wheelRadius"] = {"value": wheel_radius, "evidence": ["user answer --wheel-radius (reviewed tread band)"]}
    draft = record.draft(run.path, inv, probe_in, probe_out, run.record["answers"])
    write_json(run.path / "record" / "vehicle-record.json", draft)
    pending = draft["metadata"]["pending"]
    run.finish("record", "done", f"draft vehicle record with {len(pending)} item(s) pending review (record/vehicle-record.json)")

    for name, description, available in STAGES[7:]:
        if not available:
            message = f"stopped before '{name}' ({description}): not implemented yet"
            run.finish(name, "not_available", message)
            run.close("incomplete", message)
            return Outcome(EXIT_INCOMPLETE, message, run)
    run.close("done")
    return Outcome(EXIT_OK, "done", run)
