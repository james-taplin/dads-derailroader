"""Stock-locomotive bulk measurement run: one command, resumable, never stops on one bad pack.

For each of the 21 stock steam packs (the 3 diesels have no project: the pipeline is steam only):
  1. project: run the pipeline as far as the pre-build review (answers refused, nothing built, nothing installed). The
     imported and probed Unity project is kept in the run folder (keepWorkFiles) and reused from the cache when possible.
  2. measure: run VfMeasure.cs (M1-M13) once in that project.
Small results go to <out-dir>/results/<pack>/ as they finish, and <out-dir>/vf_bulk.zip is rebuilt after every pack, so a
crash, a closed window or a power cut loses at most one pack. Rerun the same command to resume: packs that already
passed with the same VfMeasure.cs are skipped (--force redoes them).

  set PYTHONPATH=src
  python tools\\vanilla\\run_bulk.py --dry-run                 (checks only: nothing is launched)
  python tools\\vanilla\\run_bulk.py --pilot                   (K-28T and T-17 first, about 10 minutes)
  python tools\\vanilla\\run_bulk.py                           (all 21, about 1-2 hours)

Read-only towards Railroader and Derail Valley. Never installs. Nothing large goes in the zip.
Exit codes: 0 every pack passed, 1 some packs failed (zip still written), 2 preflight failed (nothing was run), 130 interrupted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "src"))  # so `python tools/vanilla/run_bulk.py` works without PYTHONPATH

from rr2dv import __version__, installs, machine as machine_mod, stock, unityrun  # noqa: E402
from rr2dv.jsonio import read_json  # noqa: E402

SCRIPT = HERE / "VfMeasure.cs"
METHOD = "VfMeasure.Run"          # run_oil.py swaps these five for the oil-cup map; nothing else differs
OUTNAME = "vf-measure.json"
OUT_PREFIX = "vf-measure"
ZIP_NAME = "vf_bulk.zip"
TOOL_NAME = "run_bulk.py"
OUT_DEFAULT = "vf_bulk_out"
PILOT = ["ls-282-k28t", "ls-460-t17"]
PROJECT_FILE = Path("unity") / "project" / "Assets" / "Rr2dv" / "ProbeInput.json"
KEEP_FROM_RUN = ["run.log", "inventory.json", "review-questions.json", "probe/probe.json", "record/vehicle-record.json"]
MEASURE_TIMEOUT_S = 1800
MIN_FREE_GB = 25


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def say(msg: str) -> None:
    print(time.strftime("%H:%M:%S ") + msg, flush=True)


def git_commit() -> str:
    try:
        return subprocess.run(["git", "-C", str(HERE), "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              timeout=20).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def preflight(machine, rr, out_dir: Path) -> tuple[list[str], list[str]]:
    """(problems that stop the run, notes). Everything here is checked before anything long starts."""
    problems, notes = [], []
    if sys.version_info < (3, 11):
        problems.append(f"Python {sys.version.split()[0]} is too old; 3.11 or newer is needed")
    if not SCRIPT.is_file():
        problems.append(f"{SCRIPT} is missing: restore it from the repository")
    if machine.values.get("keepWorkFiles") is not True:
        machine.values["keepWorkFiles"] = True  # this run only, in memory: the settings file is never edited
        notes.append('"keepWorkFiles" is off in the settings; it is switched on for this run only (the file is not changed)')
    unity = machine.path("unity")
    if not unity or not Path(unity).is_file():
        problems.append("Unity 2019.4.40f1 is not set up: add `unity` to the settings file (see `python -m rr2dv doctor`)")
    ar = machine.path("assetRipper")
    if not ar or not Path(ar).is_file():
        problems.append("AssetRipper is not set up: add `assetRipper` to the settings file (see `python -m rr2dv doctor`)")
    try:
        machine_mod.check_work_root(machine.work_root)
    except ValueError as e:
        problems.append(str(e))
    try:
        installs.derail_valley(machine)
    except Exception as e:
        problems.append(f"Derail Valley was not found ({e}); the pipeline needs both installs")
    have = sorted(p.name for p in rr.asset_packs.iterdir() if p.is_dir())
    missing = [p for p in stock.STEAM if p not in have]
    if missing:
        problems.append(f"{len(missing)} stock steam packs are not in {rr.asset_packs}: {', '.join(missing)}")
    if stock.WHISTLE_PACK not in have:
        problems.append(f"the whistle pack {stock.WHISTLE_PACK} is missing from the Railroader AssetPacks folder")
    out_dir.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(out_dir).free / 2**30
    work = machine.work_root
    work.mkdir(parents=True, exist_ok=True)
    free_work = shutil.disk_usage(work).free / 2**30
    for label, gb in (("output folder", free), ("work folder", free_work)):
        if gb < MIN_FREE_GB:
            problems.append(f"only {gb:.0f} GB free on the {label} drive; {MIN_FREE_GB} GB are needed")
    running = [p for p in work.glob("*/unity/project/Temp/UnityLockfile")] if work.is_dir() else []
    if running:
        notes.append(f"{len(running)} kept project(s) have a Unity lock file; close Unity editors if a pack reports 'open in another Unity editor'")
    notes.append(f"Python {sys.version.split()[0]} on {platform.platform()}; rr2dv {__version__} at git {git_commit()}")
    return problems, notes


def newest_run_with_project(root: Path, pack: str, after: set[str]) -> Path | None:
    runs = sorted((p for p in root.iterdir() if p.is_dir() and p.name not in after and f"-{pack}-" in p.name), key=lambda p: p.name)
    ok = [p for p in runs if (p / PROJECT_FILE).is_file()]
    return ok[-1] if ok else None


def ensure_project(machine, pack: str) -> tuple[Path | None, dict]:
    """Run the pipeline up to the pre-build review with every answer refused; return the run folder holding the project."""
    from rr2dv import review
    from rr2dv.pipeline import convert

    def refuse_install(*_a, **_k):
        return False

    def refuse_review(_questions):
        raise review.ReviewError("bulk run: questions captured, no answers given")

    root = machine.work_root
    before = {p.name for p in root.iterdir()} if root.is_dir() else set()
    info: dict = {}
    try:
        outcome = convert(pack, machine, ask=refuse_install, prebuild_review=refuse_review)
        info = {"exit": outcome.code, "message": outcome.message}
        run = outcome.run.path if outcome.run else None
    except Exception as e:
        info = {"exit": "exception", "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc().splitlines()[-8:]}
        run = None
    if run is None or not (run / PROJECT_FILE).is_file():
        run = newest_run_with_project(root, pack, before)
    if run is None:
        info["problem"] = "no Unity project was left behind (see run.log in the run folder, if any)"
    return run, info


def copy_results(run: Path, pack_dir: Path) -> list[str]:
    pack_dir.mkdir(parents=True, exist_ok=True)
    got = []
    for rel in KEEP_FROM_RUN:
        f = run / rel
        if f.is_file():
            dest = pack_dir / rel.replace("/", "__")
            shutil.copyfile(f, dest)
            got.append(dest.name)
    return got


def measure(machine, run: Path, pack_dir: Path) -> dict:
    project = run / "unity" / "project"
    editor = project / "Assets" / "Editor"
    editor.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SCRIPT, editor / SCRIPT.name)
    n = 1
    while (run / f"{OUT_PREFIX}-{n}").exists():
        n += 1
    out = run / f"{OUT_PREFIX}-{n}"
    t0 = time.time()
    entry: dict = {}
    try:
        result = unityrun.run_method(machine.path("unity"), project, METHOD, out, {"VF_OUT": str(out)},
                                     timeout=MEASURE_TIMEOUT_S)
        entry["result"] = result
    except Exception as e:
        entry["result"] = {"status": "error", "error": f"{type(e).__name__}: {e}"}
    entry["seconds"] = round(time.time() - t0, 1)
    pack_dir.mkdir(parents=True, exist_ok=True)
    for name in (OUTNAME, "result.json", "launch.json"):
        if (out / name).is_file():
            shutil.copyfile(out / name, pack_dir / name)
    for log in sorted(out.glob("unity-*.log")):
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        (pack_dir / (log.name + ".tail.txt")).write_text("\n".join(lines[-200:]), encoding="utf-8")
    entry.update(check_output(pack_dir / OUTNAME, run))
    return entry


def check_output(path: Path, run: Path) -> dict:
    """Did Unity really measure what we asked? Facts only; the analysis is done offline."""
    if not path.is_file():
        return {"verdict": "FAILED", "why": "no vf-measure.json was written"}
    try:
        data = read_json(path)
        expected = len(read_json(run / PROJECT_FILE).get("vehicles", []))
    except Exception as e:
        return {"verdict": "FAILED", "why": f"unreadable output: {type(e).__name__}: {e}"}
    vehicles = data.get("vehicles") or []
    facts = {"vehicles": len(vehicles), "expectedVehicles": expected, "problems": len(data.get("problems") or []),
             "axles": sum(len(v.get("axles") or []) for v in vehicles),
             "columnsWithColliderYs": sum(1 for v in vehicles for c in (v.get("columns") or []) if c.get("colliderYs")),
             "sweeps": sum(len(v.get("sweeps") or []) for v in vehicles),
             "renderers": sum(len(v.get("renderers") or []) for v in vehicles),
             "hulls": sum(len(v.get("hulls") or []) for v in vehicles),
             "visibleLevels": sum(len(v.get("visibleLevels") or []) for v in vehicles)}
    if len(vehicles) != expected:
        return {"verdict": "FAILED", "why": f"{len(vehicles)} vehicles measured, {expected} expected", **facts}
    if facts["axles"] == 0:
        return {"verdict": "FAILED", "why": "no wheel axles were measured", **facts}
    if facts["renderers"] == 0:
        return {"verdict": "FAILED", "why": "no renderers were measured", **facts}
    return {"verdict": "OK" if not facts["problems"] else "OK-with-problems", **facts}


def build_zip(out_dir: Path, summary: dict, hashes: dict) -> Path:
    zip_path = out_dir / ZIP_NAME
    results = out_dir / "results"
    files = sorted(p for p in results.rglob("*") if p.is_file()) if results.is_dir() else []
    manifest = "".join(f"{sha256(p)}  results/{p.relative_to(results).as_posix()}\n" for p in files)
    tmp = out_dir / (ZIP_NAME + ".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("summary.json", json.dumps(summary, indent=1))
        z.writestr("game-hashes.json", json.dumps(hashes, indent=1))
        z.writestr("MANIFEST.sha256", manifest)
        for p in files:
            z.write(p, "results/" + p.relative_to(results).as_posix())
    tmp.replace(zip_path)
    return zip_path


def game_hashes(rr, cache: Path) -> dict:
    if cache.is_file():
        return read_json(cache)
    hashes = {}
    for d in sorted(rr.asset_packs.iterdir()):
        if d.is_dir() and d.name.startswith(("ls-", "ld-", "truck.", "audio.whistles")):
            hashes[d.name] = {f.name: sha256(f) for f in sorted(d.iterdir()) if f.is_file()}
    cache.write_text(json.dumps(hashes, indent=1), encoding="utf-8")
    return hashes


def choose_packs(rr, a) -> list[str]:
    steam = sorted(stock.STEAM)
    if a.packs:
        want = [p.strip() for p in a.packs.split(",") if p.strip()]
        bad = [p for p in want if p not in steam]
        if bad:
            sys.exit(f"not a stock steam pack: {bad}")
        return want
    return list(PILOT) if a.pilot else steam


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--machine", help="settings file (default: the app's)")
    ap.add_argument("--out-dir", default=OUT_DEFAULT, help=f"results and the zip go here (default ./{OUT_DEFAULT})")
    ap.add_argument("--pilot", action="store_true", help="only " + ", ".join(PILOT))
    ap.add_argument("--packs", help="comma-separated pack names")
    ap.add_argument("--force", action="store_true", help="measure again even where a passed result exists")
    ap.add_argument("--dry-run", action="store_true", help="preflight and the plan only; launch nothing")
    a = ap.parse_args()

    machine = machine_mod.load(Path(a.machine) if a.machine else None)
    out_dir = Path(a.out_dir).resolve()
    rr = installs.railroader(machine)
    problems, notes = preflight(machine, rr, out_dir)
    packs = choose_packs(rr, a)
    for n in notes:
        say("note: " + n)
    if problems:
        for p in problems:
            say("PROBLEM: " + p)
        say("nothing was run. Fix the problems above and rerun.")
        return 2
    say(f"preflight ok. {len(packs)} pack(s): {' '.join(packs)}")
    if a.dry_run:
        say("dry run: stopping here")
        return 0

    script_sha = sha256(SCRIPT)
    state_file = out_dir / "state.json"
    state = read_json(state_file) if state_file.is_file() else {}
    say("hashing the game packs (once; cached in game-hashes.json)")
    hashes = game_hashes(rr, out_dir / "game-hashes.json")
    summary = {"tool": TOOL_NAME, "rr2dv": __version__, "git": git_commit(), "python": sys.version.split()[0],
               "os": platform.platform(), "railroader": str(rr.root), "unity": str(machine.path("unity")),
               "script_sha256": script_sha, "packs": state.get("packs", {})}
    t_start = time.time()
    done_seconds: list[float] = []
    try:
        for i, pack in enumerate(packs, 1):
            prev = summary["packs"].get(pack, {})
            if not a.force and prev.get("verdict", "").startswith("OK") and prev.get("script_sha256") == script_sha:
                say(f"[{i}/{len(packs)}] {pack}: already measured ({prev['verdict']}), skipped")
                continue
            eta = ""
            if done_seconds:
                eta = f" (about {round(sum(done_seconds) / len(done_seconds) * (len(packs) - i + 1) / 60)} min left)"
            say(f"[{i}/{len(packs)}] {pack}: preparing the Unity project{eta}")
            t0 = time.time()
            pack_dir = out_dir / "results" / pack
            if pack_dir.exists():
                shutil.rmtree(pack_dir)
            entry: dict = {"script_sha256": script_sha}
            run, info = ensure_project(machine, pack)
            entry["pipeline"] = info
            if run is None:
                entry["verdict"] = "FAILED"
                entry["why"] = info.get("problem") or "the pipeline left no project"
            else:
                entry["run"] = run.name
                entry["files"] = copy_results(run, pack_dir)
                say(f"[{i}/{len(packs)}] {pack}: measuring")
                entry.update(measure(machine, run, pack_dir))
            entry["seconds"] = round(time.time() - t0, 1)
            summary["packs"][pack] = entry
            done_seconds.append(entry["seconds"])
            say(f"[{i}/{len(packs)}] {pack}: {entry['verdict']} in {entry['seconds']} s"
                + (f" ({entry['why']})" if entry.get("why") else ""))
            state_file.write_text(json.dumps({"packs": summary["packs"]}, indent=1), encoding="utf-8")
            build_zip(out_dir, summary, hashes)
    except KeyboardInterrupt:
        say("interrupted; the zip so far is written. Rerun the same command to resume.")
        build_zip(out_dir, summary, hashes)
        return 130
    zip_path = build_zip(out_dir, summary, hashes)
    failed = [p for p in packs if not summary["packs"].get(p, {}).get("verdict", "FAILED").startswith("OK")]
    say(f"finished in {round((time.time() - t_start) / 60)} min. wrote {zip_path}")
    if failed:
        say(f"FAILED packs ({len(failed)}): {', '.join(failed)}. Send the zip anyway; rerun the same command to retry only these.")
        return 1
    say("all packs measured. Send " + str(zip_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
