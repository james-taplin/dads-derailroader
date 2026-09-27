"""Command line: `rr2dv doctor`, `rr2dv list`, `rr2dv scan`, `rr2dv convert`.

Mods are named as they appear in the Railroader Mods folder (W25): `rr2dv scan "Some Loco Mod"`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, installs, machine as machine_mod
from .consent import ConsentError
from .jsonio import write_json
from .pipeline import EXIT_FAILED, convert, search_roots
from .publish import InstallRefused
from .rrmod import Index, blocking, inventory
from .safety import UnsafePath

MARK = {"ok": "ok  ", "warn": "WARN", "fail": "FAIL", "skip": "--  ", "error": "ERROR", "warning": "WARN", "info": "info"}


def _search_roots(args, machine, rr: installs.Install) -> list[Path]:
    extra = [Path(p) for p in args.search] + [r for r in machine.search_roots() if r not in args.search]
    return extra if args.no_default_search else search_roots(rr, extra)


def cmd_doctor(args) -> int:
    machine = machine_mod.load(args.machine)
    checks = machine_mod.doctor(machine)
    for c in checks:
        print(f"[{MARK[c.status]}] {c.name}: {c.detail}")
    failed = [c for c in checks if c.status == "fail"]
    print(f"\n{len(failed)} problem(s) must be fixed before converting." if failed else "\nReady.")
    return EXIT_FAILED if failed else 0


def _scan(root: Path, search: list[Path], hash_files: bool) -> dict:
    index = Index(root, search)
    locos = index.steam_locomotives()
    report = {
        "schema": 1,
        "roots": [{"label": r.label, "path": str(r.path)} for r in index.roots],
        "packs_indexed": len(index.packs),
        "index_issues": [i.as_dict() for i in index.issues],
        "steam_locomotives": [{"id": o["identifier"], "name": (o.get("metadata") or {}).get("name"), "pack": p.describe()} for p, o in locos],
        "other_locomotives": [{"id": o["identifier"], "kind": o["definition"].get("kind")} for _, o in index.other_locomotives()],
        "inventories": {o["identifier"]: inventory(index, o["identifier"], hash_files) for _, o in locos},
    }
    return report


def cmd_list(args) -> int:
    machine = machine_mod.load(args.machine)
    rr = installs.railroader(machine)
    found = 0
    for folder in sorted((p for p in rr.mods.iterdir() if p.is_dir()), key=lambda p: p.name.casefold()):
        locos = Index(folder).steam_locomotives(input_only=True)
        if locos:
            found += 1
            names = ", ".join(f"{o['identifier']} ({(o.get('metadata') or {}).get('name') or '?'})" for _, o in locos)
            print(f"{folder.name}: {names}")
    print(f"\n{found} mod(s) with steam locomotives in {rr.mods}" if found else f"No steam locomotive mods found in {rr.mods}")
    return 0


def cmd_scan(args) -> int:
    machine = machine_mod.load(args.machine)
    rr = installs.railroader(machine)
    target = installs.mod_in_railroader(rr, args.input)
    report = _scan(target, _search_roots(args, machine, rr), not args.no_hash)

    for issue in report["index_issues"]:
        print(f"[{MARK[issue['severity']]}] {issue['message']}")
    print(f"{report['packs_indexed']} packs indexed ({len(report['roots']) - 1} search folder(s)).")
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
    extra = [Path(p) for p in args.search] + machine.search_roots()
    outcome = convert(args.input, machine, args.loco, extra, args.audio, args.livery, args.wheel_radius)
    run = outcome.run
    if run:
        for name, stage in run.record["stages"].items():
            if stage["status"] != "pending":
                print(f"  {name:8} {stage['status']:13} {stage.get('detail', '')}")
        print(f"\nRun folder: {run.path}")
    print(outcome.message)
    return outcome.code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rr2dv", description="Convert Railroader steam locomotive mods into Derail Valley CCL packs.")
    parser.add_argument("--version", action="version", version=f"rr2dv {__version__}")
    parser.add_argument("--machine", type=Path, help=f"settings file (default {machine_mod.default_path()})")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="check that the tools and both game installs are in place").set_defaults(func=cmd_doctor)
    sub.add_parser("list", help="list the steam locomotive mods in the Railroader Mods folder").set_defaults(func=cmd_list)

    def with_search(p, optional_default=True):
        p.add_argument("--search", action="append", default=[], metavar="DIR", help="extra folder to look in for dependencies (repeatable)")
        if optional_default:
            p.add_argument("--no-default-search", action="store_true", help="do not search the Railroader Mods folder and base-game packs")

    scan = sub.add_parser("scan", help="list the steam locomotives in a mod and what each one needs (read-only)")
    scan.add_argument("input", help="mod folder name in the Railroader Mods folder")
    scan.add_argument("--json", metavar="FILE", help="also write the full report as JSON")
    scan.add_argument("--no-hash", action="store_true", help="skip file hashes (faster)")
    with_search(scan)
    scan.set_defaults(func=cmd_scan)

    conv = sub.add_parser("convert", help="convert one steam locomotive into your Derail Valley Mods folder")
    conv.add_argument("input", help="mod folder name in the Railroader Mods folder (never modified)")
    conv.add_argument("--loco", help="locomotive identifier, when the mod has more than one")
    conv.add_argument("--livery", help="livery name to use (default: the mod's first)")
    conv.add_argument("--audio", choices=["S060", "S282"],
                      help="vanilla Derail Valley sound set to use instead of the boiler-size rule")
    conv.add_argument("--wheel-radius", type=float, metavar="METRES",
                      help="driving wheel tread radius you have reviewed (see metadata.wheelCandidates in the draft record)")
    with_search(conv, optional_default=False)
    conv.set_defaults(func=cmd_convert)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (UnsafePath, FileNotFoundError, FileExistsError, ValueError, OSError, RuntimeError,
            installs.InstallError, InstallRefused, ConsentError) as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
