"""The `import` stage: assemble a fresh Unity 2019.4.40f1 project for one conversion from the cached AssetRipper exports.

Follows our proven setup (G-29 setup_build_project.ps1, pilots.py prepare; guide B04 steps 4-5):
- the locomotive's pack export is the project; its clip paths are restored with our strict resolver
  (tooling/builder/tools/resolve_clip_paths.py), which writes nothing unless every clip resolves. A clip that fits
  several prefabs with different paths ("tied") is bound to the one prefab whose own clip map names it (board X30);
  a tied clip no map names, or that several maps name, stays an error;
- a tender prefab from another pack, and every part prefab, are copied with their GUID closure
  (tooling/builder/tools/pilot/copy_deps.py; scripts skipped, .meta kept) under Assets/RR/<root>/<pack>;
  vehicle packs also get their clips restored;
- ProjectVersion 2019.4.40f1, asset pipeline mode 1, render-pipeline packages removed, TextMeshPro 2.1.6 + uGUI 1.0.0;
- CarCreator 3.1.9 unpacked with its original GUIDs;
- the shared builder core (tooling/builder/tools/unity/*.cs, incl. LlwVehicleRecord.cs) copied into Assets/Editor.
Duplicate GUIDs anywhere in the result are an error (B04). Cached exports are only read.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath

from .jsonio import sha256_file, write_json
from .probeinput import MAP_ENTRY
from .safety import UnsafePath, _bad_part

UNITY_VERSION = "2019.4.40f1"
UNITY_REVISION = "ffc62b691db5"
PACKAGES_REMOVED = re.compile(r"render-pipelines|shadergraph|visualeffectgraph")
PACKAGES_ADDED = {"com.unity.textmeshpro": "2.1.6", "com.unity.ugui": "1.0.0"}
IGNORED_DIRS = ("Library", "Temp", "Logs", "obj")
# Code from the source export is never compiled into our project (board X27): Railroader mods' scripts are
# AssetRipper stubs at best and arbitrary code at worst. Meshes, materials, clips and their GUIDs are kept; the
# cached export keeps everything for later probes. Our trusted CarCreator and builder core are added afterwards.
SOURCE_CODE_SUFFIXES = {".cs", ".dll", ".asmdef", ".asmref", ".rsp", ".pdb", ".mdb", ".so", ".dylib", ".jslib"}
ASSET_PIPELINE_MODE = 1  # Asset Database v2 (UnityEditor.AssetPipelineMode.Version2 = 1; board X27)
MINIMAL_EDITOR_SETTINGS = ("%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n--- !u!159 &1\nEditorSettings:\n"
                           "  m_ObjectHideFlags: 0\n  m_SerializationMode: 2\n  m_AssetPipelineMode: 1\n")


class ProjectError(RuntimeError):
    """The Unity project could not be assembled."""


def tooling_root() -> Path:
    # A frozen Windows release keeps the snapshot beside its bundled Python modules.
    root = (Path(sys._MEIPASS) / "tooling" if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parents[2] / "tooling")
    if not (root / "builder" / "tools" / "unity").is_dir():
        raise ProjectError(f"builder tooling not found at {root}; rr2dv needs the repository's tooling/ folder")
    return root


def _tool(script: str, *args) -> str:
    path = tooling_root() / "builder" / "tools" / script
    command = [sys.executable]
    if getattr(sys, "frozen", False):
        command.append("--rr2dv-tool")
    proc = subprocess.run([*command, str(path), *map(str, args)], capture_output=True, text=True)
    if proc.returncode:
        raise ProjectError(f"{Path(script).name} failed: {(proc.stderr or proc.stdout).strip().splitlines()[-1:]}")
    return proc.stdout


class ModelNotExported(ProjectError):
    """A catalogue model the export does not hold exactly once: a clear stop for the user, not an unexpected error."""


def find_prefab(assets: Path, filename: str) -> Path:
    if not filename.casefold().endswith(".prefab"):
        filename += ".prefab"
    prefabs = sorted(assets.rglob("*.prefab"))
    hits = [p for p in prefabs if p.name.casefold() == filename.casefold()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        names = ", ".join(p.relative_to(assets).as_posix() for p in prefabs[:12]) or "none"
        more = f" (and {len(prefabs) - 12} more)" if len(prefabs) > 12 else ""
        raise ModelNotExported(f"the model {filename} is not in the exported pack {assets.parent.parent.name}: the pack's "
                           f"Catalog.json names it, but the export holds these prefabs: {names}{more}")
    raise ModelNotExported(f"the model {filename} is in the exported pack {assets.parent.parent.name} more than once: "
                       + ", ".join(p.relative_to(assets).as_posix() for p in hits) + "; never a first match (D03)")


TEXTURE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff", ".psd", ".exr", ".bmp", ".dds", ".hdr", ".gif"}
GUID_REF = re.compile(rb"guid: ([0-9a-f]{32})")


def referenced_files(assets: Path, roots: list[Path]) -> set[Path] | None:
    """Every file the root prefabs reach through Unity GUID references (prefab -> materials -> textures, clips, meshes),
    followed through the YAML files of the export. None when a root is missing: then nothing may be left out."""
    by_guid: dict[str, Path] = {}
    for meta in assets.rglob("*.meta"):
        try:
            head = meta.read_bytes()[:400]
        except OSError:
            continue
        m = GUID_REF.search(head)
        if m:
            by_guid[m.group(1).decode()] = meta.with_suffix("")
    if not roots or any(not r.is_file() for r in roots):
        return None
    seen: set[Path] = set()
    todo = list(roots)
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        seen.add(f)
        if f.suffix.casefold() in TEXTURE_SUFFIXES or not f.is_file():
            continue
        try:
            data = f.read_bytes()
        except OSError:
            continue
        if not data.startswith(YAML_HEADER):
            continue
        for g in GUID_REF.findall(data):
            target = by_guid.get(g.decode())
            if target is not None and target not in seen:
                todo.append(target)
    return seen


TIED = "Tied prefabs"
NO_FIT = "No prefab resolves every clip binding"
UNREACHABLE = ("no prefab's clip map names it and no serialized file in the export references its GUID: "
               "unreachable")
YAML_HEADER = b"%YAML"


def _guid_of(meta: Path) -> str | None:
    m = re.search(r"^guid: (\w+)", meta.read_text(encoding="utf-8-sig", errors="replace"), re.M)
    return m[1] if m else None


def clip_owners(source_assets: Path) -> dict[str, list[dict]]:
    """Each clip (path relative to source_assets) -> the prefabs whose clip maps name it, with the map key."""
    clip_by_guid = {}
    for meta in source_assets.rglob("*.anim.meta"):
        g = _guid_of(meta)
        if g:
            clip_by_guid[g] = meta.relative_to(source_assets).as_posix()[:-5]
    owners: dict[str, list[dict]] = {}
    for prefab in sorted(source_assets.rglob("*.prefab")):
        rel = prefab.relative_to(source_assets).as_posix()
        for key, g in MAP_ENTRY["clip"].findall(prefab.read_text(encoding="utf-8-sig", errors="replace")):
            if g in clip_by_guid:
                entry = {"prefab": rel, "key": key.strip()}
                if entry not in owners.setdefault(clip_by_guid[g], []):
                    owners[clip_by_guid[g]].append(entry)
    return owners


def guid_references(source_assets: Path, guids: dict[str, str]) -> dict[str, list[str]]:
    """Every serialized Unity file (text YAML, not .meta) in the export that mentions each GUID, by clip."""
    found: dict[str, list[str]] = {clip: [] for clip in guids.values()}
    if not guids:
        return found
    for f in sorted(source_assets.rglob("*")):
        if not f.is_file() or f.suffix == ".meta":
            continue
        with f.open("rb") as fh:
            if fh.read(len(YAML_HEADER)) != YAML_HEADER:
                continue
        text = f.read_text(encoding="utf-8-sig", errors="replace")
        rel = f.relative_to(source_assets).as_posix()
        for g, clip in guids.items():
            if g in text and rel != clip:
                found[clip].append(rel)
    return found


def _resolve(source_assets: Path, dest_assets: Path, report: Path, bindings: Path | None = None) -> dict:
    args = [source_assets, report, "--apply", dest_assets] + (["--bindings", bindings] if bindings else [])
    try:
        _tool("resolve_clip_paths.py", *args)
    except ProjectError:
        if not report.is_file():
            raise
    return json.loads(report.read_text(encoding="utf-8"))


def _mirror(source_assets: Path, target: Path, skip: set[str] = frozenset(), only: set[str] | None = None) -> None:
    """The resolver's inputs (prefabs and clips, with their .meta files), limited to `only` when given and without
    `skip`. Hard links where possible; the source export is never changed."""
    for f in sorted(list(source_assets.rglob("*.prefab")) + list(source_assets.rglob("*.anim"))):
        rel = f.relative_to(source_assets).as_posix()
        if rel in skip or (only is not None and rel not in only):
            continue
        for g in (f, f.with_name(f.name + ".meta")):
            if not g.is_file():
                continue
            dst = target / g.relative_to(source_assets)
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(g, dst)
            except OSError:
                shutil.copy2(g, dst)


def _resolver_module():
    """Our canonical resolver, loaded (not copied) so a diagnosis reads prefabs and clips exactly as it does."""
    import importlib.util
    path = tooling_root() / "builder" / "tools" / "resolve_clip_paths.py"
    spec = importlib.util.spec_from_file_location("rr2dv_resolve_clip_paths", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def diagnose_clips(source_assets: Path, clips: list[str], out: Path) -> Path:
    """For clips the resolver could not restore, write what a person needs to decide the fix: which prefab's clip map
    names each clip, how many of its bindings each prefab can resolve, and, for each binding the best prefab lacks,
    whether any prefab in the export has that path at all (a stale binding in the source, versus a path that lives in
    another prefab)."""
    resolver = _resolver_module()
    tables = [(p.relative_to(source_assets).as_posix(), resolver.prefab_paths(p)) for p in sorted(source_assets.rglob("*.prefab"))]
    owners = clip_owners(source_assets)
    findings = {}
    for clip in clips:
        path = source_assets / clip
        if not path.is_file():
            continue
        hashes = sorted({int(h, 16) for h in resolver.PAT.findall(path.read_text(encoding="utf-8-sig", errors="replace"))})
        fits = sorted(((name, sum(1 for h in hashes if h in table)) for name, table in tables), key=lambda t: (-t[1], t[0]))
        best_name = fits[0][0] if fits else None
        best = dict(tables).get(best_name, {})
        unresolved = [h for h in hashes if h not in best]
        findings[clip] = {
            "bindings": len(hashes),
            "named_by": owners.get(clip, []),
            "best_prefabs": [{"prefab": n, "resolves": k} for n, k in fits[:3]],
            "resolved_in_best": sorted({next(iter(best[h])) for h in hashes if h in best and len(best[h]) == 1})[:40],
            "unresolved_in_best": [{"hash": f"0x{h:x}", "found_in": [n for n, t in tables if h in t][:5]} for h in unresolved],
        }
    write_json(out, {"note": "bindings are hashed paths; found_in [] means no prefab in this export has that path "
                             "(verified against the export only, not Railroader at runtime)", "clips": findings})
    return out


def resolve_clips(source_assets: Path, dest_assets: Path, report: Path, only: set[str] | None = None) -> dict:
    """Restore clip paths of `source_assets` into `dest_assets`. With `only` (paths relative to source_assets), just
    those prefabs and clips take part: a dependency pack is resolved against the prefabs we use from it, not every
    variant in its export (X35: all six Fox truck prefabs name one shared Brakes clip; the C21 tender uses one)."""
    if only is None:
        return _resolve_clips(source_assets, dest_assets, report)
    selected = report.with_name(report.stem + "-selected")
    if selected.exists():
        shutil.rmtree(selected)
    _mirror(source_assets, selected, only=only)
    try:
        out = _resolve_clips(selected, dest_assets, report, full_assets=source_assets)
    finally:
        shutil.rmtree(selected, ignore_errors=True)
    return {**out, "selected": len(only)}


def _absent_plan(source_assets: Path, full_assets: Path, clip: str, owners: list[dict]) -> tuple[dict | None, str]:
    """A clip no prefab fully resolves (X39, GN A-18: Drivers 37 of 40 targets in its model, Whistle 0 of 1). Kept only
    when the source says whose it is and the rest of its targets exist nowhere: exactly one prefab's clip map names it,
    and every binding that prefab lacks is in no prefab of the pack's whole export. Those bindings keep their
    placeholder path (they animate nothing in the exported model; the build stage removes them through Unity before
    our builder, which rejects unresolved bindings); the others are restored exactly as the resolver would, restricted
    to the named prefab. Anything else is (None, why)."""
    named = sorted({o["prefab"] for o in owners})
    if len(named) != 1:
        return None, (f"{', '.join(named)} name it" if named else "no prefab's clip map names it")
    resolver = _resolver_module()
    tables = [(p.relative_to(source_assets).as_posix(), resolver.prefab_paths(p)) for p in sorted(source_assets.rglob("*.prefab"))]
    owner = dict(tables).get(named[0])
    if owner is None:
        return None, f"{named[0]} is not among the prefabs resolved"
    text = (source_assets / clip).read_text(encoding="utf-8-sig")
    hashes = {int(h, 16) for h in resolver.PAT.findall(text)}
    absent = sorted(h for h in hashes if h not in owner)
    full = [(p.relative_to(full_assets).as_posix(), resolver.prefab_paths(p)) for p in sorted(full_assets.rglob("*.prefab"))]
    elsewhere = {f"0x{h:x}": [n for n, t in full if h in t] for h in absent}
    if any(elsewhere.values()):
        where = "; ".join(f"{h} in {', '.join(ns)}" for h, ns in elsewhere.items() if ns)
        return None, f"{named[0]} lacks targets that other prefabs have ({where})"
    try:
        mapping = resolver.select_mapping({h for h in hashes if h in owner}, tables, named[0])
    except ValueError as e:
        return None, str(e)
    return {"prefab": named[0], "owners": owners, "bindings": len(hashes), "restored": len(mapping),
            "absent": [f"0x{h:x}" for h in absent],
            "text": resolver.PAT.sub(lambda m: mapping.get(int(m[1], 16), m[0]), text)}, ""


def _resolve_clips(source_assets: Path, dest_assets: Path, report: Path, full_assets: Path | None = None) -> dict:
    """Restore clip paths with our strict resolver. A clip that fits several prefabs with different paths ("tied") is
    decided from the source, never by first match (X30, X33): bound to the one prefab whose clip map names it, else to
    the one prefab that references it anywhere; a clip no serialized file references at all is unreachable and is left
    out of the project, with a report. A clip no prefab fully resolves is kept only under `_absent_plan` (X39).
    Anything else stays an error. The evidence is written either way. `full_assets` is the pack's whole export when
    `source_assets` is a selection from it."""
    full_assets = full_assets or source_assets
    result = _resolve(source_assets, dest_assets, report)
    bound: dict[str, str] = {}
    excluded: list[str] = []
    partial: dict[str, dict] = {}
    errors = result.get("errors", [])
    tied = [e["clip"] for e in errors if TIED in e.get("error", "") and e.get("clip")]
    no_fit = [e["clip"] for e in errors if NO_FIT in e.get("error", "") and e.get("clip")]
    if errors and len(tied) + len(no_fit) == len(errors):
        owners = clip_owners(source_assets)
        unowned = [c for c in tied + no_fit if not owners.get(c)]
        guids = {g: c for c in unowned for g in [_guid_of(source_assets / (c + ".meta"))] if g}
        refs = guid_references(source_assets, guids)
        decisions, unresolved = {}, {}
        for c in tied:
            named = sorted({o["prefab"] for o in owners.get(c, [])})
            referenced = refs.get(c, [])
            prefabs = sorted({r for r in referenced if r.endswith(".prefab")})
            if len(named) == 1:
                bound[c] = named[0]
                decisions[c] = {"decision": "bound", "by": "clip map", "prefab": named[0], "owners": owners[c]}
            elif named:
                unresolved[c] = f"{', '.join(named)} name it"
                decisions[c] = {"decision": "error", "owners": owners[c]}
            elif len(prefabs) == 1 and len(referenced) == 1:
                bound[c] = prefabs[0]
                decisions[c] = {"decision": "bound", "by": "serialized reference", "prefab": prefabs[0], "references": referenced}
            elif not referenced and c in refs:
                excluded.append(c)
                decisions[c] = {"decision": "left out", "why": UNREACHABLE, "references": []}
            else:
                unresolved[c] = ("referenced by " + ", ".join(referenced)) if referenced else "no GUID in its .meta"
                decisions[c] = {"decision": "error", "references": referenced}
        for c in no_fit:
            if not owners.get(c) and c in refs and not refs[c]:
                excluded.append(c)
                decisions[c] = {"decision": "left out", "why": UNREACHABLE, "references": []}
                continue
            plan, why = _absent_plan(source_assets, full_assets, c, owners.get(c, []))
            if plan is None:
                unresolved[c] = f"{NO_FIT}; {why}"
                decisions[c] = {"decision": "error", "why": why, "owners": owners.get(c, [])}
                continue
            partial[c] = plan
            decisions[c] = {"decision": "kept, absent bindings unresolved", "by": "clip map", "prefab": plan["prefab"],
                            "owners": plan["owners"], "bindings": plan["bindings"], "restored": plan["restored"],
                            "absent": plan["absent"]}
        evidence = report.with_name(report.stem + "-bindings.json")
        write_json(evidence, {"rule": "tied clip -> the one prefab whose clip map names it, else the one prefab that "
                                      "references it; unreferenced -> left out; a clip no prefab fully resolves -> kept "
                                      "when one prefab's clip map names it and every target it lacks is in no prefab of "
                                      "the export (those bindings animate nothing and keep their placeholder path); "
                                      "otherwise an error",
                              "clips": decisions})
        if unresolved:
            detail = "; ".join(f"{c}: {why}" for c, why in sorted(unresolved.items()))
            if all(c in no_fit for c in unresolved):
                where = evidence
                try:
                    where = diagnose_clips(full_assets, sorted(unresolved), report.with_name(report.stem + "-diagnosis.json"))
                except Exception:
                    pass
                raise ProjectError(f"resolve_clip_paths: {len(unresolved)} clip(s) did not resolve: {detail} (see {where})")
            raise ProjectError(f"animation clips fit several prefabs and the source does not say which: {detail} (see {evidence})")
        plain = report.with_name(report.stem + "-bindings.plain.json")
        write_json(plain, bound)
        source = source_assets
        if excluded or partial:
            source = report.with_name(report.stem + "-resolver-input")
            if source.exists():
                shutil.rmtree(source)
            _mirror(source_assets, source, set(excluded) | set(partial))
        try:
            if any(source.rglob("*.anim")):
                result = _resolve(source, dest_assets, report, plain if bound else None)
            else:  # every clip was set aside above: nothing left for the resolver, which would call that an error
                result = {"clips": [], "errors": [], "applied": True}
                write_json(report, result)
        finally:
            if source != source_assets:
                shutil.rmtree(source, ignore_errors=True)
        if not result.get("errors") and result.get("applied"):
            for c in excluded:  # unreachable: nothing in the project may carry its placeholder paths
                for f in (dest_assets / c, dest_assets / (c + ".meta")):
                    if f.is_file():
                        f.unlink()
            for c, plan in partial.items():
                target = dest_assets / c
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(plan["text"], encoding="utf-8")
    if result.get("errors") or not result.get("applied"):
        errors = result.get("errors") or [{"error": "not applied"}]
        first = errors[0]
        where = report
        try:  # the diagnosis is extra help; failing to write it must not hide the real error
            where = diagnose_clips(full_assets, [e["clip"] for e in errors if e.get("clip")],
                                   report.with_name(report.stem + "-diagnosis.json"))
        except Exception:
            pass
        raise ProjectError(f"resolve_clip_paths: {len(errors)} clip(s) did not resolve, first "
                           f"{first.get('clip', '')}: {first.get('error')}; see {where}")
    absent = [{"clip": c, "prefab": p["prefab"], "keys": sorted({o["key"] for o in p["owners"]}), "bindings": p["bindings"],
               "restored": p["restored"], "absent": p["absent"]} for c, p in sorted(partial.items())]
    return {"clips": len(result.get("clips", [])) + len(partial), "report": report.name, "bound": len(bound),
            "left_out": excluded, "absent_bindings": absent}


def set_project_settings(project: Path) -> None:
    settings = project / "ProjectSettings"
    settings.mkdir(exist_ok=True)
    (settings / "ProjectVersion.txt").write_text(
        f"m_EditorVersion: {UNITY_VERSION}\nm_EditorVersionWithRevision: {UNITY_VERSION} ({UNITY_REVISION})\n", encoding="ascii")
    editor = settings / "EditorSettings.asset"
    if not editor.is_file():
        editor.write_text(MINIMAL_EDITOR_SETTINGS, encoding="utf-8")
    else:
        text = editor.read_text(encoding="utf-8")
        line = f"  m_AssetPipelineMode: {ASSET_PIPELINE_MODE}"
        text, n = re.subn(r"^  m_AssetPipelineMode: *\S*[ \t]*$", line, text, count=1, flags=re.M)
        if not n:
            text, n = re.subn(r"^(EditorSettings:[ \t]*\r?\n)", r"\g<1>" + line + "\n", text, count=1, flags=re.M)
        if not n:
            raise ProjectError("EditorSettings.asset has no EditorSettings: block; refusing to guess its format")
        editor.write_text(text, encoding="utf-8")
    manifest_path = project / "Packages" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig")) if manifest_path.is_file() else {}
    deps = {k: v for k, v in manifest.get("dependencies", {}).items() if not PACKAGES_REMOVED.search(k)}
    deps.update(PACKAGES_ADDED)
    manifest["dependencies"] = dict(sorted(deps.items()))
    write_json(manifest_path, manifest)


def import_unitypackage(package: Path, project: Path) -> int:
    """Unpack a .unitypackage (tar.gz of <guid>/{pathname,asset,asset.meta}) into the project, safely."""
    root = project.resolve()
    written = 0
    with tarfile.open(package, "r:gz") as archive:
        groups: dict[str, dict[str, tarfile.TarInfo]] = {}
        for member in archive.getmembers():
            key, sep, leaf = member.name.partition("/")
            if sep and leaf:
                if not (member.isfile() or member.isdir()):
                    raise UnsafePath(f"{package.name}: unexpected entry type {member.name!r}")
                groups.setdefault(key, {})[leaf] = member
        for key in sorted(groups):
            members = groups[key]
            if "pathname" not in members:
                continue
            relative = archive.extractfile(members["pathname"]).read().decode("utf-8").splitlines()[0].strip()
            parts = PurePosixPath(relative).parts
            if not parts or parts[0] != "Assets" or relative.startswith("/") or any(_bad_part(p) for p in parts):
                raise UnsafePath(f"{package.name}: unsafe package path {relative!r}")
            dest = project.joinpath(*parts)
            if not dest.resolve().is_relative_to(root):
                raise UnsafePath(f"{package.name}: {relative!r} escapes the project")
            if "asset" in members:
                if dest.exists():
                    raise ProjectError(f"{package.name} would overwrite {relative}")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(archive.extractfile(members["asset"]).read())
                written += 1
            else:
                dest.mkdir(parents=True, exist_ok=True)
            if "asset.meta" in members:
                Path(str(dest) + ".meta").write_bytes(archive.extractfile(members["asset.meta"]).read())
    return written


def check_guids(assets: Path) -> int:
    seen: dict[str, Path] = {}
    for meta in sorted(assets.rglob("*.meta")):
        m = re.search(r"^guid: (\w+)", meta.read_text(encoding="utf-8-sig", errors="replace"), re.M)
        if not m:
            continue
        if m[1] in seen:
            raise ProjectError(f"duplicate GUID {m[1]}: {seen[m[1]].relative_to(assets)} and {meta.relative_to(assets)}")
        seen[m[1]] = meta
    return len(seen)


def _subfolder(pack: dict) -> str:
    """Assets/RR/<root>/<pack path>, each folder name reduced to safe characters."""
    segments = [re.sub(r"[^A-Za-z0-9_. -]", "_", s).strip(" .") or "_" for s in (pack.get("path") or pack["name"]).split("/")]
    return "/".join(["RR", pack["root"], *segments])


def assemble(run_path: Path, inv: dict, exports: dict[str, dict], car_creator: Path) -> dict:
    project = run_path / "unity" / "project"
    if project.exists():
        raise ProjectError(f"{project} already exists; runs never reuse a project")
    reports = run_path / "import"
    reports.mkdir(parents=True, exist_ok=True)

    def export_of(pack: dict) -> Path:
        key = f"{pack['root']}:{pack['path'] or pack['name']}"
        if key not in exports:
            raise ProjectError(f"no export for pack {key}")
        return Path(exports[key]["path"]) / "ExportedProject"

    main_pack = inv["locomotive"]["pack"]
    main = export_of(main_pack)
    excluded: list[str] = []

    # Only the textures our prefabs reach are imported: a mod shipping several complete skins (PLW Trojan: a texture set
    # per livery) otherwise makes Unity import every one, 10 minutes instead of 2. Other assets are copied as before.
    main_assets = main / "Assets"
    roots = []
    wanted = [v["prefab"] for v in inv.get("vehicles", []) if v["pack"] == main_pack] + \
             [p["filename"] for p in inv.get("parts", []) if p.get("pack_ref") == main_pack]
    for filename in wanted:
        try:
            roots.append(find_prefab(main_assets, filename))
        except ProjectError:  # the import reports it properly below; prune nothing
            roots = []
            break
    used = referenced_files(main_assets, roots) if roots and len(roots) == len(wanted) else None
    unused_textures: list[str] = []

    def skip(folder, names):
        out = {n for n in names if n in IGNORED_DIRS}
        if used is not None and Path(folder).is_relative_to(main_assets):
            for n in names:
                base = n[:-5] if n.endswith(".meta") else n
                path = Path(folder, base)
                if Path(base).suffix.casefold() in TEXTURE_SUFFIXES and path.is_file() and path not in used:
                    out.add(n)
                    if not n.endswith(".meta"):
                        unused_textures.append(path.relative_to(main).as_posix())
        for n in names:
            suffix = Path(n[:-5] if n.endswith(".meta") else n).suffix.casefold()
            if suffix in SOURCE_CODE_SUFFIXES and Path(folder, n).is_file():
                out.add(n)
                if not n.endswith(".meta"):
                    excluded.append(Path(folder, n).relative_to(main).as_posix())
        return out

    shutil.copytree(main, project, ignore=skip)
    assets = project / "Assets"
    result = {"project": project.relative_to(run_path).as_posix(), "unity": f"{UNITY_VERSION} ({UNITY_REVISION})",
              "clips": {"main": resolve_clips(main / "Assets", assets, reports / "clips-main.json")},
              "vehicles": [], "parts": []}

    copied: dict[tuple[str, str], str] = {}
    selected: dict[str, tuple[Path, set[str]]] = {}  # vehicle pack subfolder -> (its export Assets, prefabs we use)

    def bring(pack: dict, filename: str, vehicle: bool) -> str:
        """Unity path of a prefab: in the main export as is, else copied with its dependencies."""
        if pack == main_pack:
            return find_prefab(assets, filename).relative_to(project).as_posix()
        key = (f"{pack['root']}:{pack['path'] or pack['name']}", filename.casefold())
        if key in copied:
            return copied[key]
        src_assets = export_of(pack) / "Assets"
        prefab = find_prefab(src_assets, filename)
        sub = _subfolder(pack)
        _tool("pilot/copy_deps.py", src_assets, prefab.relative_to(src_assets), assets, sub)
        for f in sorted((assets / sub).rglob("*")):  # our own fresh folder: drop any code copy_deps followed
            if f.is_file() and Path(f.name[:-5] if f.name.endswith(".meta") else f.name).suffix.casefold() in SOURCE_CODE_SUFFIXES:
                if not f.name.endswith(".meta"):
                    excluded.append(f"{sub}/{f.relative_to(assets / sub).as_posix()}")
                f.unlink()
        if vehicle:
            selected.setdefault(sub, (src_assets, set()))[1].add(prefab.relative_to(src_assets).as_posix())
        copied[key] = f"Assets/{sub}/{prefab.relative_to(src_assets).as_posix()}"
        return copied[key]

    for v in inv.get("vehicles", []):
        result["vehicles"].append({**v, "unity_prefab": bring(v["pack"], v["prefab"], vehicle=True)})
    # Each vehicle pack from another export is resolved once, against the prefabs we use from it and the clips copied
    # with them (their dependency closure), before any part is added to the same folder.
    for sub, (src_assets, prefabs) in sorted(selected.items()):
        clips = {f.relative_to(assets / sub).as_posix() for f in (assets / sub).rglob("*.anim")}
        name = re.sub(r"[^A-Za-z0-9_-]", "_", sub)
        result["clips"][sub] = resolve_clips(src_assets, assets / sub, reports / f"clips-{name}.json", only=prefabs | clips)
    for part in inv.get("parts", []):
        result["parts"].append({**part, "unity_prefab": bring(part["pack_ref"], part["filename"], vehicle=False)})

    result["excluded_source_code"] = sorted(excluded)
    result["unused_textures"] = {"left_out": sorted(unused_textures), "complete_copy": used is None,
                                 "rule": "textures no converted prefab references (GUIDs through materials) are not imported"}
    set_project_settings(project)
    result["car_creator"] = {"file": car_creator.name, "sha256": sha256_file(car_creator),
                             "files": import_unitypackage(car_creator, project)}
    editor = assets / "Editor"
    editor.mkdir(parents=True, exist_ok=True)
    core = {}
    for script in sorted((tooling_root() / "builder" / "tools" / "unity").glob("*.cs")):
        target = editor / script.name
        if target.exists():
            raise ProjectError(f"export already contains Assets/Editor/{script.name}")
        shutil.copyfile(script, target)
        core[f"builder/tools/unity/{script.name}"] = sha256_file(script)
    result["core_scripts"] = core
    app = {}
    for script in sorted((Path(__file__).parent / "unity").glob("*.cs")):  # rr2dv's own editor scripts (probe)
        target = editor / script.name
        if target.exists():
            raise ProjectError(f"app script {script.name} clashes with Assets/Editor/{script.name}")
        shutil.copyfile(script, target)
        app[f"rr2dv/unity/{script.name}"] = sha256_file(script)
    result["app_scripts"] = app
    # rr2dv's own materials (fallbacks, e.g. the dark gunmetal for material slots the export left empty)
    materials = assets / "Rr2dv" / "Materials"
    materials.mkdir(parents=True, exist_ok=True)
    for mat in sorted((Path(__file__).parent / "unity" / "materials").iterdir()):
        target = materials / mat.name
        if target.exists():
            raise ProjectError(f"app material {mat.name} clashes with {target}")
        shutil.copyfile(mat, target)
        if mat.suffix == ".mat":
            app[f"rr2dv/unity/materials/{mat.name}"] = sha256_file(mat)
    result["unique_guids"] = check_guids(assets)
    write_json(run_path / "unity" / "project.json", result)
    return result
