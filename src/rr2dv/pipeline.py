"""The conversion pipeline: runs each available stage in order and stops at the first one that fails or is
not implemented yet.

W25: the input is a mod folder in the user's own Railroader Mods folder (never a zip; only ever read), and the
result goes into their own Derail Valley Mods folder, only after the personal-use notice (consent.py). Both installs
are found before anything runs, checked again before the Unity build, and again right before installing."""
from __future__ import annotations

import hashlib
import json
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from typing import Callable

from . import (assetripper, audit, build, buildrecord, consent, geometryreview, installs, probeinput, projectcache, publish, record,
               unityproject, unityrun, workspace, rebuild, review)
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
    cache = (machine.work_root / "_cache" / "assetripper" if workspace.keep_files(machine)
             else run.path / 'extracted')
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
            ask: Callable = consent.ask, on_progress: Callable[[str | None, str, str], None] | None = None,
            geometry_review: Path | None = None, prebuild_review=None) -> Outcome:
    # Both installs (and CCL) first (W25), then the input must be a mod in the Railroader Mods folder.
    rr, dv = _installs(machine)
    input_path = installs.mod_in_railroader(rr, mod)
    work_root = machine.work_root.resolve()
    # Refuse bad targets before creating anything: where first (a clearer answer), then Unity's path limit.
    guard = [("input mod", input_path), ("Railroader install", rr.root), ("Derail Valley install", dv.root)]
    check_write_target(work_root, guard)
    check_work_root(work_root)
    roots = search_roots(rr, search)

    request = {"input": str(input_path), "locomotive": loco, "railroader": rr.describe(), "derail_valley": dv.describe(),
               "search_roots": [str(p) for p in roots], "audio": audio, "livery": livery, "wheel_radius": wheel_radius,
               "geometry_review": str(geometry_review) if geometry_review else None}
    cleanup_warnings = workspace.recover(work_root)
    run = Run.create(work_root, loco or input_path.name, request)
    run.listener = on_progress
    lease = None if workspace.keep_files(machine) else workspace.begin(run)
    for warning in cleanup_warnings:
        run.log(warning)
    tools = {k: machine.values.get(k) for k in ("unity", "carCreator", "assetRipper", "python", "workRoot")}
    run.log("settings: " + (str(machine.source) if machine.source else "none (defaults)") + "\n"
            + "\n".join(f"{k}: {v or '(not set)'}" for k, v in tools.items()) + "\n"
            + f"Railroader: {rr.root} ({rr.source})\nDerail Valley: {dv.root} ({dv.source}), Mods {dv.mods}\n"
            + f"input: {input_path}\nlocomotive: {loco or '(one in the mod)'}; livery: {livery or '(default)'}; "
            + f"audio: {audio or '(boiler-size rule)'}; wheel radius: {wheel_radius or '(pending)'}\n"
            + "search: " + ", ".join(str(r) for r in roots))
    try:
        rebuild.capture(run, machine)
        outcome = _stages(run, input_path, loco, roots, audio, machine, livery, wheel_radius, ask, geometry_review, prebuild_review)
    except BaseException as e:  # include interruption; stop tools and retain a truthful receipt before cleanup
        current = next((n for n, s in run.record["stages"].items() if s["status"] == "running"), None)
        message = f"{type(e).__name__}: {e}"
        run.log("unexpected error:\n" + traceback.format_exc())
        if current:
            run.finish(current, "failed", message)
        run.close("failed", message)
        try:  # the app and the command line point the user at this run's folder and run.log
            e.rr2dv_run = run
        except AttributeError:
            pass
        raise
    finally:
        try:
            rebuild.save(run)
        finally:
            if lease is not None:
                workspace.finish(run, lease)
    if run.record.get('cleanup', {}).get('status') == 'pending':
        outcome.message += '; temporary cleanup pending: ' + run.record['cleanup'].get('error', '')
    return outcome


def _installs(machine: Machine) -> tuple[installs.Install, installs.Install]:
    """Railroader, Derail Valley and Custom Car Loader, found (again) at each boundary W25 names."""
    rr = installs.railroader(machine)
    dv = installs.derail_valley(machine)
    if not installs.ccl_installed(dv):
        raise installs.InstallError(f"Custom Car Loader ({installs.CCL_MOD_ID}) is not installed in {dv.mods}; "
                                    "install it first, the converted pack needs it")
    return rr, dv


def install_pack(run: Run, machine: Machine, pack_dir: Path, expected: dict[str, str], sources: list[dict],
                 ask: Callable = consent.ask) -> Path:
    """The publish stage: Derail Valley is found again, CCL must be there, then the notice, then the install."""
    _, dv = _installs(machine)
    details = {"run": run.path.name, "input": run.record["request"]["input"],
               "locomotive": run.record.get("answers", {}).get("locomotive"),
               "input_fingerprint": run.record.get("input_fingerprint")}
    dest, acknowledgement = publish.install(pack_dir, dv, expected, sources, details, ask)
    run.record["notice"] = acknowledgement  # notice version, when it was acknowledged, the sources it listed
    run.save()
    return dest


def _stages(run: Run, input_path: Path, loco: str | None, search: Sequence[Path],
            audio: str | None, machine: Machine, livery: str | None = None, wheel_radius: float | None = None,
            ask: Callable = consent.ask, geometry_review: Path | None = None, prebuild_review=None) -> Outcome:
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
    for issue in inv["issues"]:
        run.log(f"  {issue['severity']:7} {issue['code']}: {issue['message']}")
    run.record["input_fingerprint"] = fingerprint(inv)
    if geometry_review:
        cars = {chosen} | ({inv['tender']['id']} if inv.get('tender') else set())
        try:
            reviewed = geometryreview.validate(read_json(geometry_review), run.record['input_fingerprint'], cars)
        except (ValueError, OSError) as e:
            return fail('link', f'geometry review: {e}')
        run.record['answers']['geometryReview'] = reviewed
        write_json(run.path / 'geometry-review.json', reviewed)
        run.log('reviewed geometry saved to geometry-review.json (source fingerprint matched)')
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
    for key, e in exports.items():
        run.log(f"  {key}: {'cached' if e['cached'] else 'exported'} -> {e['path']}")
    run.finish("extract", "done", f"{len(exports)} bundle(s) exported ({reused} reused from cache)")

    run.begin("import")
    car_creator = machine.path("carCreator")
    if car_creator is None or not car_creator.is_file():
        raise FileNotFoundError("CarCreator 3.1.9 is not set up: add `carCreator` to the settings file (see `rr2dv doctor`)")
    cache_key = projectcache.key(inv, exports, car_creator) if workspace.keep_files(machine) else None
    project = projectcache.restore(machine.work_root.resolve(), cache_key, run.path) if cache_key else None
    cached = project is not None
    if cached:
        run.log(f"  reused the imported project and its probe results from an earlier run (cache {cache_key}); "
                "Unity does not import or measure again")
    else:
        project = unityproject.assemble(run.path, inv, exports, car_creator)
    absent = [{"export": name, **a} for name, c in sorted(project["clips"].items()) for a in c.get("absent_bindings", [])]
    for a in absent:
        run.log(f"  clip {a['clip']} ({', '.join(a['keys'])}): {len(a['absent'])} of {a['bindings']} binding(s) target "
                f"objects not in any model of the export; kept with the other {a['restored']} restored (review item)")
    run.finish("import", "done", f"Unity {project['unity']} project with {len(project['vehicles'])} vehicle(s), "
                                 f"{len(project['parts'])} part(s), {project['unique_guids']} GUIDs"
                                 + (" (reused from an earlier run)" if cached else ""))

    run.begin("probe")
    if cached:
        probe_in = read_json(run.path / project["project"] / probeinput.INPUT_ASSET)
        result = read_json(run.path / "probe" / "result.json")
    else:
        probe_in = probeinput.build(run.path, inv, project)
        result = unityrun.run_method(machine.path("unity"), run.path / project["project"], "Rr2dvProbe.Run", run.path / "probe",
                                     {"RR2DV_PROBE_OUT": str(run.path / "probe")})
    if result.get("status") not in ("passed", "problems"):
        return fail("probe", f"Unity probe failed: {result.get('error') or result}")
    problems = result.get("problems", 0)
    run.log("  Unity result: " + json.dumps(result, sort_keys=True))
    probe_file = run.path / "probe" / "probe.json"
    if probe_file.exists():
        for line in (read_json(probe_file).get("problems") or [])[:50]:
            run.log(f"  probe problem: {line}")
    if not cached and cache_key:
        try:
            if projectcache.save(machine.work_root.resolve(), cache_key, run.path):
                run.log(f"  saved the imported project and probe results for reruns (cache {cache_key})")
        except OSError as e:  # a full disk must not stop the conversion: the cache is only a speed-up
            run.log(f"  could not save the project for reruns: {e}")
    run.finish("probe", "done", f"{len(probe_in['vehicles'])} vehicle(s) measured; {problems} problem(s) to review"
                                + (" (see probe/probe.json)" if problems else "") + (" (from an earlier run)" if cached else ""))

    run.begin("record")
    probe_out_file = run.path / "probe" / "probe.json"
    probe_out = read_json(probe_out_file) if probe_out_file.exists() else None
    if livery:
        run.record["answers"]["livery"] = livery
    if wheel_radius:
        run.record["answers"]["wheelRadius"] = {"value": wheel_radius, "evidence": ["user answer --wheel-radius (reviewed tread band)"]}
    draft = record.draft(run.path, inv, probe_in, probe_out, run.record["answers"], absent_bindings=absent)
    write_json(run.path / "record" / "vehicle-record.json", draft)
    pending = draft["metadata"]["pending"]
    for item in pending:
        run.log(f"  review: {item}")
    for w in draft["metadata"].get("wheelCandidates", []):
        run.log(f"  wheel {w.get('clip')}: tread {w.get('tread')} ({w.get('confidence')}), flange {w.get('flangeRadius')}, "
                f"source {w.get('sourceRadius')}; notes: {'; '.join(w.get('notes') or []) or 'none'}")
    run.finish("record", "done", f"draft vehicle record with {len(pending)} item(s) pending review (record/vehicle-record.json)")

    if prebuild_review is not None:
        run.begin("review")
        questions = review.request(draft, build.definitions(run.path, inv), probe_out, run.record['input_fingerprint'])
        write_json(run.path / 'review-questions.json', questions)
        try:
            response = prebuild_review(questions) if callable(prebuild_review) else read_json(Path(prebuild_review))
            reviewed = review.resolve(questions, response)
        except (review.ReviewError, OSError, ValueError) as error:
            run.finish('review', 'needs_answer', str(error))
            run.close('incomplete', str(error))
            return Outcome(EXIT_INCOMPLETE, str(error), run)
        run.record['answers']['prebuildReview'] = reviewed
        run.record['answers']['wheelRadius'] = {'value': reviewed['values']['wheelRadius'], 'evidence': ['Pre-build review: physical driving tyre radius']}
        draft = record.draft(run.path, inv, probe_in, probe_out, run.record['answers'], absent_bindings=absent)
        draft['metadata']['review'] = reviewed
        write_json(run.path / 'prebuild-review.json', reviewed)
        write_json(run.path / 'record/vehicle-record.json', draft)
        run.finish('review', 'done', 'Saved brake, spawning, wheel and simulation choices with source identity')
    else:
        run.finish('review', 'done', 'Legacy API caller: existing conversion settings')

    # build: both installs are found again first (W25)
    _installs(machine)
    run.begin("build")
    try:
        prepared = build.prepare(run.path, inv, probe_in, probe_out, project, draft, run.record["answers"], absent)
    except buildrecord.Blocked as blocked:
        write_json(run.path / "build" / "blocks.json", blocked.items)
        run.record["blocks"] = blocked.items
        for item in blocked.items:
            run.log(f"  block {item['code']}: {item['message']}")
        message = "; ".join(i["message"] for i in blocked.items)
        if all(i["code"].startswith("needs-") for i in blocked.items):  # only answers missing: give them and convert again
            run.finish("build", "needs_answer", message)
            run.close("incomplete", message)
            return Outcome(EXIT_INCOMPLETE, message, run)
        return fail("build", f"{len(blocked.items)} thing(s) to resolve before building: {message}")
    except build.BuildError as e:
        return fail("build", str(e))
    for choice in prepared["choices"]:
        run.log(f"  choice: {choice}")
    try:
        built = build.run(run.path, machine.path("unity"), project, prepared["record"])
    except build.BuildError as e:
        return fail("build", str(e))
    write_json(run.path / "build" / "built.json", built)
    for w in built["warnings"]:
        run.log(f"  builder warning: {w}")
    pack = Path(built["pack"])
    run.record["pack"] = {"name": pack.name, "files": built["files"]}
    run.finish("build", "done", f"pack {pack.name!r} exported ({len(built['files'])} file(s)); {len(built['warnings'])} builder "
                                f"warning(s) and {len(prepared['choices'])} automatic choice(s) to review (build/review.json)")

    run.begin("audit")
    try:
        summary = audit.run(run.path, machine.path("unity"), project, prepared["record"], built)
    except audit.AuditError as e:
        return fail("audit", str(e))
    for w in summary["warnings"]:
        run.log(f"  audit note: {w}")
    if summary["status"] != "passed":
        for e in summary["errors"]:
            run.log(f"  audit error: {e}")
        return fail("audit", f"{len(summary['errors'])} problem(s): " + "; ".join(summary["errors"][:5])
                    + (" (see audit/summary.json)" if len(summary["errors"]) > 5 else ""))
    run.finish("audit", "done", "passed (no audio, CCL scripts only, HUD controls present); in-game checks still pending")

    run.begin("publish")
    try:
        dest = install_pack(run, machine, pack, built["files"], inv.get("sources", []), ask)
    except (publish.InstallRefused, consent.ConsentError) as e:
        run.finish("publish", "not_installed", str(e))
        run.close("incomplete", f"built and audited, not installed: {e}")
        return Outcome(EXIT_INCOMPLETE, f"built and audited, not installed: {e}", run)
    run.record["installed"] = str(dest)
    run.finish("publish", "done", f"installed into {dest}")
    message = (f"installed into {dest}. It is a candidate: check it in Derail Valley (controls, closed valves, "
               "brakes, lamps, coupling) before calling it done")
    run.close("done", message)
    return Outcome(EXIT_OK, message, run)
