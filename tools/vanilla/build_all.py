"""Unattended test build of the stock steam locomotives: every pack built and audited, nothing installed, reports zipped.

Meant for a Codex (or anyone's) session while the owner is away. For each pack it runs the app's own conversion with:
  - the pre-build review answered with the vehicle choices the app already suggests (the prefilled answers of the review window,
    taken as they are: what pressing "confirm" in the window does);
  - the personal-use notice REFUSED, so nothing is ever installed (the notice needs a person; nothing here skips it): a pack that
    builds and passes its audit ends "built and audited but not installed" (exit 3), which is the success this run looks for;
  - the review window's "I acknowledge experimental physics and pending in-game calibration" box ticked ONLY with --acknowledge-experimental
    (the owner must have allowed it; without it every pack stops at the review);
  - optionally (--accept-proposed-geometry, off unless the owner said so) the app's own measured end-beam proposal when a build stops
    with "geometry review required", up to 3 rounds per pack (a loco and its tender can each need one). Every proposal used is
    listed in the summary with its band.
Work files are NOT kept (the settings are used as they are), so each run folder is deleted after its pack, as in the real app.
The compact reports of every attempt (run.log, build_report.txt, audit.json, review and geometry files) go to <out-dir>/results/<pack>/
and <out-dir>/vf_build.zip is rebuilt after every pack. Rerun the same command to resume (packs already built are skipped; --force).

  set PYTHONPATH=src
  python tools\\vanilla\\build_all.py --dry-run
  python tools\\vanilla\\build_all.py --pilot --acknowledge-experimental --accept-proposed-geometry     (K-28T and T-17)
  python tools\\vanilla\\build_all.py --acknowledge-experimental --accept-proposed-geometry             (all 21)

Exit codes: 0 every pack built and audited, 1 some packs failed (zip still written), 2 preflight failed, 130 interrupted.
"""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
import time
import traceback
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "src"))

from rr2dv import __version__, installs, machine as machine_mod, review, reviewchoices, stock  # noqa: E402
from rr2dv.jsonio import read_json  # noqa: E402

PILOT = ["ls-282-k28t", "ls-460-t17"]
MAX_ROUNDS = 3
MIN_FREE_GB = 15
KEEP = ("run.log", "build_report.txt", "audit.json", "audit.log", "review-questions.json", "prebuild-review.json",
        "geometry-review-proposed.json", "geometry-review.json", "run.json", "result.json", "rebuild.json")


def say(msg: str) -> None:
    print(time.strftime("%H:%M:%S ") + msg, flush=True)


def confirm_suggested(questions, acknowledge: bool = False):
    """The review window's prefilled answers, unchanged (what 'confirm' does). The window's tick-box 'I acknowledge experimental physics
    and pending in-game calibration' is a person's answer: it is ticked only when the owner allowed it (--acknowledge-experimental)."""
    prefill = (questions.get("prefill") or {}).get("values")
    if not prefill:
        raise review.ReviewError("no suggested answers were offered for this vehicle")
    values = dict(prefill)
    if acknowledge:
        values["acknowledgeExperimental"] = True
    return {**{k: questions[k] for k in reviewchoices.IDENTITY}, "values": values}


def refuse_notice(*_a, **_k):
    return False


def preflight(machine, out_dir: Path) -> tuple[list[str], list[str]]:
    problems, notes = [], []
    if sys.version_info < (3, 11):
        problems.append(f"Python {sys.version.split()[0]} is too old; 3.11 or newer is needed")
    for key, label in (("unity", "Unity 2019.4.40f1"), ("assetRipper", "AssetRipper")):
        p = machine.path(key)
        if not p or not Path(p).is_file():
            problems.append(f"{label} is not set up: add `{key}` to the settings file (see `python -m rr2dv doctor`)")
    try:
        machine_mod.check_work_root(machine.work_root)
    except ValueError as e:
        problems.append(str(e))
    try:
        rr = installs.railroader(machine)
        installs.derail_valley(machine)
    except Exception as e:
        problems.append(f"an install was not found ({e}); the pipeline needs both")
        return problems, notes
    have = {p.name for p in rr.asset_packs.iterdir() if p.is_dir()}
    missing = [p for p in stock.STEAM if p not in have]
    if missing:
        problems.append(f"{len(missing)} stock steam packs are not in {rr.asset_packs}: {', '.join(missing)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    machine.work_root.mkdir(parents=True, exist_ok=True)
    for label, path in (("output folder", out_dir), ("work folder", machine.work_root)):
        free = shutil.disk_usage(path).free / 2**30
        if free < MIN_FREE_GB:
            problems.append(f"only {free:.0f} GB free on the {label} drive; {MIN_FREE_GB} GB are needed")
    if machine.values.get("keepWorkFiles") is True:
        notes.append('"keepWorkFiles" is ON in the settings: run folders will pile up (about 0.5 GB each). Switch it off for this run.')
    notes.append(f"work folder: {machine.work_root}")
    notes.append(f"Python {sys.version.split()[0]} on {platform.platform()}; rr2dv {__version__}")
    return problems, notes


def copy_reports(machine, run, pack_dir: Path, tag: str) -> list[str]:
    """The compact reports of one attempt (the run folder itself may already be deleted)."""
    got = []
    for base in (machine.work_root / "reports" / run.path.name, run.path):
        if not base.is_dir():
            continue
        for name in KEEP:
            f = base / name
            for src in ([f] if f.is_file() else []) + ([base / "build" / "out" / name] if (base / "build" / "out" / name).is_file() else []):
                dest = pack_dir / f"{tag}__{src.name}"
                if not dest.exists():
                    shutil.copyfile(src, dest)
                    got.append(dest.name)
    return got


def stage(run, name: str) -> str:
    return ((run.record.get("stages") or {}).get(name) or {}).get("status", "")


def build_pack(machine, pack: str, accept_geometry: bool, pack_dir: Path, acknowledge: bool = False) -> dict:
    from rr2dv.pipeline import convert
    pack_dir.mkdir(parents=True, exist_ok=True)
    entry: dict = {"rounds": [], "geometryUsed": []}
    geometry = None
    for n in range(1, MAX_ROUNDS + 1):
        info: dict = {"round": n, "geometryReview": str(geometry) if geometry else None}
        try:
            outcome = convert(pack, machine, ask=refuse_notice, prebuild_review=lambda q: confirm_suggested(q, acknowledge), geometry_review=geometry)
            run = outcome.run
            info.update(exit=outcome.code, message=outcome.message, run=run.path.name if run else None)
        except Exception as e:
            run = getattr(e, "rr2dv_run", None)
            info.update(exit="exception", error=f"{type(e).__name__}: {e}", traceback=traceback.format_exc().splitlines()[-6:])
            outcome = None
        if run is not None:
            info["reports"] = copy_reports(machine, run, pack_dir, f"r{n}")
            info["stages"] = {k: v.get("status") for k, v in (run.record.get("stages") or {}).items() if v.get("status") != "pending"}
        entry["rounds"].append(info)
        built = run is not None and stage(run, "audit") == "done" and stage(run, "build") == "done"
        if built:
            entry["verdict"] = "BUILT"
            entry["why"] = "built and audited; not installed (the notice was refused)" if stage(run, "publish") != "done" else "built, audited and installed"
            return entry
        proposal = machine.work_root / "reports" / run.path.name / "geometry-review-proposed.json" if run is not None else None
        if accept_geometry and proposal is not None and proposal.is_file() and "geometry review required" in (info.get("message") or ""):
            geometry = pack_dir / f"proposed-geometry-round{n}.json"
            shutil.copyfile(proposal, geometry)
            data = read_json(geometry)
            entry["geometryUsed"].append({"round": n, "file": geometry.name, "summary": json.dumps(data)[:600]})
            say(f"{pack}: round {n} stopped for geometry review; using the app's proposal ({geometry.name})")
            continue
        break
    entry["verdict"] = "FAILED"
    entry["why"] = (entry["rounds"][-1].get("message") or entry["rounds"][-1].get("error") or "unknown")[:500]
    return entry


def build_zip(out_dir: Path, summary: dict) -> Path:
    path = out_dir / "vf_build.zip"
    tmp = out_dir / "vf_build.zip.tmp"
    results = out_dir / "results"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("summary.json", json.dumps(summary, indent=1))
        for f in sorted(results.rglob("*")) if results.is_dir() else []:
            if f.is_file():
                z.write(f, "results/" + f.relative_to(results).as_posix())
    tmp.replace(path)
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--machine", help="settings file (default: the app's)")
    ap.add_argument("--out-dir", default="vf_build_out")
    ap.add_argument("--pilot", action="store_true", help="only " + ", ".join(PILOT))
    ap.add_argument("--packs", help="comma-separated pack names")
    ap.add_argument("--accept-proposed-geometry", action="store_true",
                    help="when a build stops for geometry review, use the app's own measured proposal and build again (the owner must have allowed it)")
    ap.add_argument("--acknowledge-experimental", action="store_true",
                    help="tick the review window's 'I acknowledge experimental physics and pending in-game calibration' (the owner must have allowed it)")
    ap.add_argument("--force", action="store_true", help="build again even where a pack already built in this out-dir")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    machine = machine_mod.load(Path(a.machine) if a.machine else None)
    out_dir = Path(a.out_dir).resolve()
    steam = sorted(stock.STEAM)
    packs = [p.strip() for p in a.packs.split(",") if p.strip()] if a.packs else (list(PILOT) if a.pilot else steam)
    bad = [p for p in packs if p not in steam]
    if bad:
        sys.exit(f"not a stock steam pack: {bad}")
    problems, notes = preflight(machine, out_dir)
    for n in notes:
        say("note: " + n)
    if problems:
        for p in problems:
            say("PROBLEM: " + p)
        say("nothing was run. Fix the problems above and rerun.")
        return 2
    say(f"preflight ok. {len(packs)} pack(s): {' '.join(packs)}; geometry proposals {'ACCEPTED' if a.accept_proposed_geometry else 'not accepted'}; experimental-physics box {'TICKED' if a.acknowledge_experimental else 'not ticked'}; installing: never")
    if a.dry_run:
        say("dry run: stopping here")
        return 0
    state_file = out_dir / "state.json"
    state = read_json(state_file) if state_file.is_file() else {}
    summary = {"tool": "build_all.py", "rr2dv": __version__, "python": sys.version.split()[0], "os": platform.platform(),
               "acceptProposedGeometry": a.accept_proposed_geometry, "packs": state.get("packs", {})}
    t_start = time.time()
    try:
        for i, pack in enumerate(packs, 1):
            prev = summary["packs"].get(pack, {})
            if not a.force and prev.get("verdict") == "BUILT":
                say(f"[{i}/{len(packs)}] {pack}: already built, skipped")
                continue
            say(f"[{i}/{len(packs)}] {pack}: building")
            t0 = time.time()
            pack_dir = out_dir / "results" / pack
            if pack_dir.exists():
                shutil.rmtree(pack_dir)
            entry = build_pack(machine, pack, a.accept_proposed_geometry, pack_dir, a.acknowledge_experimental)
            entry["seconds"] = round(time.time() - t0, 1)
            summary["packs"][pack] = entry
            say(f"[{i}/{len(packs)}] {pack}: {entry['verdict']} in {entry['seconds']} s ({entry['why']})")
            state_file.write_text(json.dumps({"packs": summary["packs"]}, indent=1), encoding="utf-8")
            build_zip(out_dir, summary)
    except KeyboardInterrupt:
        say("interrupted; the zip so far is written. Rerun the same command to resume.")
        build_zip(out_dir, summary)
        return 130
    zip_path = build_zip(out_dir, summary)
    failed = [p for p in packs if summary["packs"].get(p, {}).get("verdict") != "BUILT"]
    say(f"finished in {round((time.time() - t_start) / 60)} min. wrote {zip_path}")
    if failed:
        say(f"FAILED packs ({len(failed)}): {', '.join(failed)}. Send the zip anyway; rerun the same command to retry only these.")
        return 1
    say("all packs built and audited. Send " + str(zip_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
