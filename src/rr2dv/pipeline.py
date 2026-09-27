"""The conversion pipeline: runs each available stage in order and stops at the first one that fails or is
not implemented yet.

W25: the input is a mod folder in the user's own Railroader Mods folder (never a zip; only ever read), and the
result goes into their own Derail Valley Mods folder, only after the personal-use notice (consent.py). Both installs
are found before anything runs, checked again before the Unity build, and again right before installing."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from typing import Callable

from . import assetripper, consent, installs, probeinput, publish, record, unityproject, unityrun
from .jsonio import read_json, write_json
from .machine import Machine, check_work_root
from .rrmod import Index, blocking, inventory
from .runs import STAGES, Run, stage_inputs
from .safety import check_write_target

EXIT_OK, EXIT_FAILED, EXIT_INCOMPLETE = 0, 1, 3


@dataclass
class Outcome:
    code: int
    message: str
    run: Run | None = None


def search_roots(rr: installs.Install, extra: Sequence[Path] = ()) -> list[Path]:
    """Extra folders first, then the Railroader Mods folder and the base-game asset packs."""
    roots = [Path(p) for p in extra] + [rr.mods, rr.root / "Railroader_Data" / "StreamingAssets" / "AssetPacks"]
    return [r for i, r in enumerate(roots) if r not in roots[:i]]


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


def convert(mod: str | Path, machine: Machine, loco: str | None = None, search: Sequence[Path] = (),
            audio: str | None = None, livery: str | None = None, wheel_radius: float | None = None,
            ask: Callable = consent.ask) -> Outcome:
    # Both installs first (W25), then the input must be a mod in the Railroader Mods folder.
    rr = installs.railroader(machine)
    dv = installs.derail_valley(machine)
    input_path = installs.mod_in_railroader(rr, mod)
    work_root = machine.work_root.resolve()
    # Refuse bad targets before creating anything.
    check_work_root(work_root)
    guard = [("input mod", input_path), ("Railroader install", rr.root), ("Derail Valley install", dv.root)]
    check_write_target(work_root, guard)
    roots = search_roots(rr, search)

    request = {"input": str(input_path), "locomotive": loco, "railroader": rr.describe(), "derail_valley": dv.describe(),
               "search_roots": [str(p) for p in roots], "audio": audio, "livery": livery, "wheel_radius": wheel_radius}
    run = Run.create(work_root, loco or input_path.name, request)
    try:
        return _stages(run, input_path, loco, roots, audio, machine, livery, wheel_radius)
    except Exception as e:  # record the failure on the run, then let the caller report it
        current = next((n for n, s in run.record["stages"].items() if s["status"] == "running"), None)
        message = f"{type(e).__name__}: {e}"
        if current:
            run.finish(current, "failed", message)
        run.close("failed", message)
        raise


def install_pack(run: Run, machine: Machine, pack_dir: Path, expected: dict[str, str], sources: list[dict],
                 ask: Callable = consent.ask) -> Path:
    """The publish stage: Derail Valley is found again, CCL must be there, then the notice, then the install."""
    dv = installs.derail_valley(machine)
    if not installs.ccl_installed(dv):
        raise installs.InstallError(f"Custom Car Loader ({installs.CCL_MOD_ID}) is not installed in {dv.mods}; "
                                    "install it first, the converted pack needs it")
    details = {"run": run.path.name, "input": run.record["request"]["input"],
               "locomotive": run.record.get("answers", {}).get("locomotive"),
               "input_fingerprint": run.record.get("input_fingerprint")}
    dest, acknowledgement = publish.install(pack_dir, dv, expected, sources, details, ask)
    run.record["notice"] = acknowledgement  # notice version, when it was acknowledged, the sources it listed
    run.save()
    return dest


def _stages(run: Run, input_path: Path, loco: str | None, search: Sequence[Path],
            audio: str | None, machine: Machine, livery: str | None = None, wheel_radius: float | None = None) -> Outcome:
    def fail(stage: str, message: str, code: int = EXIT_FAILED) -> Outcome:
        run.finish(stage, "failed", message)
        run.close("failed", message)
        return Outcome(code, message, run)

    run.begin("locate")
    index = Index(input_path, search)
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
        if name == "build":  # found again before the Unity build (W25)
            installs.railroader(machine)
            installs.derail_valley(machine)
        if not available:
            message = f"stopped before '{name}' ({description}): not implemented yet"
            run.finish(name, "not_available", message)
            run.close("incomplete", message)
            return Outcome(EXIT_INCOMPLETE, message, run)
    run.close("done")
    return Outcome(EXIT_OK, "done", run)
