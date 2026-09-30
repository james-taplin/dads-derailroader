"""Command line: `rr2dv doctor`, `rr2dv list`, `rr2dv scan`, `rr2dv convert`.

Locomotives are named by their Railroader asset-pack name: `rr2dv scan ls-282-k28t`. Only the 21 stock steam locomotives
are accepted (see stock.py)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import review
from . import __version__, applog, installs, machine as machine_mod, stock
from .consent import ConsentError
from .appmodel import scan_report
from .jsonio import write_json
from .pipeline import EXIT_FAILED, convert, search_roots
from .publish import InstallRefused
from .rrmod import Index, blocking, inventory
from .safety import UnsafePath

MARK = {"ok": "ok  ", "warn": "WARN", "fail": "FAIL", "skip": "--  ", "error": "ERROR", "warning": "WARN", "info": "info"}


def cmd_doctor(args) -> int:
    machine = machine_mod.load(args.machine)
    checks = machine_mod.doctor(machine)
    for c in checks:
        print(f"[{MARK[c.status]}] {c.name}: {c.detail}")
    failed = [c for c in checks if c.status == "fail"]
    print(f"\n{len(failed)} problem(s) must be fixed before converting." if failed else "\nReady.")
    return EXIT_FAILED if failed else 0


def _scan(root: Path, search: list[Path], hash_files: bool) -> dict:
    return scan_report(root, search, hash_files)


def cmd_gui(args) -> int:
    from . import gui  # Tk is only needed for the desktop app
    return gui.main(["--machine", str(args.machine)] if args.machine else [])


def cmd_list(args) -> int:
    machine = machine_mod.load(args.machine)
    rr = installs.railroader(machine)
    present = 0
    print(f"Stock steam locomotives (Railroader asset packs in {rr.asset_packs}):")
    for pack, name in stock.STEAM.items():
        here = (rr.asset_packs / pack).is_dir()
        present += here
        print(f"  {pack}: {name}" + ("" if here else "  (pack not found)"))
    print("\nNot supported in this release: " + ", ".join(f"{p} ({n})" for p, n in stock.DIESEL.items()))
    print(f"\n{present} of {len(stock.STEAM)} stock steam locomotives found")
    return 0


def cmd_scan(args) -> int:
    machine = machine_mod.load(args.machine)
    rr = installs.railroader(machine)
    target = installs.stock_pack(rr, args.input)
    report = _scan(target, search_roots(rr), not args.no_hash)

    for issue in report["index_issues"]:
        print(f"[{MARK[issue['severity']]}] {issue['message']}")
    print(f"{report['packs_indexed']} packs indexed.")
    for other in report["other_locomotives"]:
        print(f"  skipped {other['id']}: {other['kind']} (only steam locomotives are converted)")
    if not report["steam_locomotives"]:
        print("No steam locomotive found in the input.")
    for loco in report["steam_locomotives"]:
        inv = report["inventories"][loco["id"]]
        errors = blocking(inv)
        state = "BLOCKED" if errors else "ready for the next stage"
        tender = inv.get("tender") or {}
        print(f"\n{loco['id']} - {loco['name']}: {state}")
        print(f"  tender: {tender.get('id', 'none')}; trucks: {', '.join(t['id'] for t in inv['trucks']) or 'none'}; "
              f"parts: {len(inv['parts'])}; packs: {', '.join(p['name'] for p in inv['packs'])}")
        purposes = sorted({c['purpose'] for c in inv['controls']['radial'] if c.get('purpose')})
        print(f"  controls: {', '.join(purposes) or 'none'}; toggles: {len(inv['controls']['toggles'])}")
        print(f"  uses work from: {', '.join(m['id'] for m in inv['mods']) or 'none'}")
        for dep in inv.get("railroader_only", []):
            print(f"  uses {dep['id']} in Railroader only ({'installed' if dep['installed'] else 'not found'}); not needed in Derail Valley")
        for g in inv["optional_groups"]:
            print(f"  optional group for {g['target']}: {g['group_name']} ({g['file']['path']})")
        found = sum(1 for tex in inv["textures"] if tex["file"])
        if inv["textures"]:
            print(f"  images: {found} of {len(inv['textures'])} found")
        audio = inv["audio"]
        print(f"  sounds: vanilla {audio['basis'] or '(choose S060 or S282)'} - {audio['rule']}")
        for issue in inv["issues"]:
            print(f"  [{MARK[issue['severity']]}] {issue['message']}")
    if args.json:
        write_json(Path(args.json), report)
        print(f"\nReport written to {args.json}")
    any_ready = any(not blocking(report["inventories"][l["id"]]) for l in report["steam_locomotives"])
    return 0 if any_ready else EXIT_FAILED


def cmd_convert(args) -> int:
    machine = machine_mod.load(args.machine)
    try:
        outcome = convert(args.input, machine, args.loco, args.audio, args.livery, args.wheel_radius,
                          geometry_review=args.geometry_review, prebuild_review=args.review_file or review.cli)
    except Exception as e:  # stopped inside a run: show how far it got and where its log is, then report the error
        _print_run(getattr(e, "rr2dv_run", None))
        raise
    _print_run(outcome.run)
    print(outcome.message)
    radius = next((b for b in (outcome.run.record.get("blocks") or [] if outcome.run else [])
                   if b.get("code") == "needs-wheel-radius" and b.get("candidate")), None)
    if radius:  # the rerun command, with every answer already given, for the user to check and run
        parts = ["rr2dv"] + (["--machine", f'"{args.machine}"'] if args.machine else []) + \
                ["convert", f'"{args.input}"'] + (["--loco", args.loco] if args.loco else []) + \
                (["--livery", f'"{args.livery}"'] if args.livery else []) + (["--audio", args.audio] if args.audio else []) + \
                (["--geometry-review", f'"{args.geometry_review}"'] if args.geometry_review else []) + \
                ["--wheel-radius", f"{radius['candidate']:.4f}"]
        print("\nAfter checking the candidate against the tyre in the model, convert again with:\n  " + " ".join(parts))
    return outcome.code


def _print_run(run) -> None:
    if run:
        for name, stage in run.record["stages"].items():
            if stage["status"] != "pending":
                print(f"  {name:8} {stage['status']:13} {stage.get('detail', '')}")
        print(f"\nRun folder: {run.path}\nRun log:    {run.path / 'run.log'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rr2dv", description="Convert Railroader's stock steam locomotives into Derail Valley CCL packs.")
    parser.add_argument("--version", action="version", version=f"rr2dv {__version__}")
    parser.add_argument("--machine", type=Path, help=f"settings file (default {machine_mod.default_path()})")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="check that the tools and both game installs are in place").set_defaults(func=cmd_doctor)
    sub.add_parser("list", help="list the stock steam locomotives this edition converts").set_defaults(func=cmd_list)
    sub.add_parser("gui", help="open the desktop app").set_defaults(func=cmd_gui)

    scan = sub.add_parser("scan", help="show what a stock steam locomotive needs (read-only)")
    scan.add_argument("input", help="stock locomotive pack name, e.g. ls-282-k28t")
    scan.add_argument("--json", metavar="FILE", help="also write the full report as JSON")
    scan.add_argument("--no-hash", action="store_true", help="skip file hashes (faster)")
    scan.set_defaults(func=cmd_scan)

    conv = sub.add_parser("convert", help="convert one stock steam locomotive into your Derail Valley Mods folder")
    conv.add_argument("input", help="stock locomotive pack name, e.g. ls-282-k28t (never modified)")
    conv.add_argument("--loco", help="locomotive identifier (the pack's own; normally not needed)")
    conv.add_argument("--livery", help="livery name to use (default: the locomotive's first)")
    conv.add_argument("--audio", choices=["S060", "S282"],
                      help="vanilla Derail Valley sound set to use instead of the boiler-size rule")
    conv.add_argument("--wheel-radius", type=float, metavar="METRES",
                      help="driving wheel tread radius you have reviewed (see metadata.wheelCandidates in the draft record)")
    conv.add_argument("--geometry-review", type=Path, metavar="FILE",
                      help="reviewed per-car end-beam band JSON, tied to the exact source fingerprint")
    conv.add_argument("--review-file", type=Path, help="saved pre-build answers tied to this source; otherwise review interactively")
    conv.set_defaults(func=cmd_convert)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    log = applog.get()
    log.info("command: rr2dv %s", " ".join(argv if argv is not None else sys.argv[1:]))
    try:
        code = args.func(args)
        log.info("command finished with exit code %s", code)
        return code
    except (UnsafePath, FileNotFoundError, FileExistsError, ValueError, OSError, RuntimeError,
            installs.InstallError, InstallRefused, ConsentError) as e:
        log.warning("stopped: %s", e, exc_info=True)
        print(f"error: {e}", file=sys.stderr)
        return EXIT_FAILED
    except Exception as e:  # a bug: keep the traceback for diagnosis, tell the user where it is
        log.exception("unexpected error")
        print(f"unexpected error: {type(e).__name__}: {e}\nDetails (with traceback): {applog.log_file()}", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
