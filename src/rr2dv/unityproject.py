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
    root = Path(__file__).resolve().parents[2] / "tooling"
    if not (root / "builder" / "tools" / "unity").is_dir():
        raise ProjectError(f"builder tooling not found at {root}; rr2dv needs the repository's tooling/ folder")
    return root


def _tool(script: str, *args) -> str:
    path = tooling_root() / "builder" / "tools" / script
    proc = subprocess.run([sys.executable, str(path), *map(str, args)], capture_output=True, text=True)
    if proc.returncode:
        raise ProjectError(f"{Path(script).name} failed: {(proc.stderr or proc.stdout).strip().splitlines()[-1:]}")
    return proc.stdout


def find_prefab(assets: Path, filename: str) -> Path:
    hits = [p for p in assets.rglob("*.prefab") if p.name.casefold() == filename.casefold()]
    if len(hits) != 1:
        raise ProjectError(f"expected exactly one {filename} in {assets}, found {len(hits)}")
    return hits[0]


TIED = "Tied prefabs"
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
        out = _resolve_clips(selected, dest_assets, report)
    finally:
        shutil.rmtree(selected, ignore_errors=True)
    return {**out, "selected": len(only)}


def _resolve_clips(source_assets: Path, dest_assets: Path, report: Path) -> dict:
    """Restore clip paths with our strict resolver. A clip that fits several prefabs with different paths ("tied") is
    decided from the source, never by first match (X30, X33): bound to the one prefab whose clip map names it, else to
    the one prefab that references it anywhere; a clip no serialized file references at all is unreachable and is left
    out of the project, with a report. Anything else stays an error. The evidence is written either way."""
    result = _resolve(source_assets, dest_assets, report)
    bound: dict[str, str] = {}
    excluded: list[str] = []
    tied = [e["clip"] for e in result.get("errors", []) if TIED in e.get("error", "") and e.get("clip")]
    if tied and len(tied) == len(result["errors"]):
        owners = clip_owners(source_assets)
        unowned = [c for c in tied if not owners.get(c)]
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
                decisions[c] = {"decision": "left out", "why": "no prefab's clip map names it and no serialized file in "
                                                              "the export references its GUID: unreachable", "references": []}
            else:
                unresolved[c] = ("referenced by " + ", ".join(referenced)) if referenced else "no GUID in its .meta"
                decisions[c] = {"decision": "error", "references": referenced}
        evidence = report.with_name(report.stem + "-bindings.json")
        write_json(evidence, {"rule": "tied clip -> the one prefab whose clip map names it, else the one prefab that "
                                      "references it; unreferenced -> left out; otherwise an error",
                              "clips": decisions})
        if unresolved:
            detail = "; ".join(f"{c}: {why}" for c, why in sorted(unresolved.items()))
            raise ProjectError(f"animation clips fit several prefabs and the source does not say which: {detail} (see {evidence})")
        plain = report.with_name(report.stem + "-bindings.plain.json")
        write_json(plain, bound)
        source = source_assets
        if excluded:
            source = report.with_name(report.stem + "-resolver-input")
            if source.exists():
                shutil.rmtree(source)
            _mirror(source_assets, source, set(excluded))
        try:
            result = _resolve(source, dest_assets, report, plain)
        finally:
            if source != source_assets:
                shutil.rmtree(source, ignore_errors=True)
        if not result.get("errors") and result.get("applied"):
            for c in excluded:  # unreachable: nothing in the project may carry its placeholder paths
                for f in (dest_assets / c, dest_assets / (c + ".meta")):
                    if f.is_file():
                        f.unlink()
    if result.get("errors") or not result.get("applied"):
        errors = result.get("errors") or [{"error": "not applied"}]
        first = errors[0]
        raise ProjectError(f"resolve_clip_paths: {len(errors)} clip(s) did not resolve, first "
                           f"{first.get('clip', '')}: {first.get('error')}; see {report}")
    return {"clips": len(result.get("clips", [])), "report": report.name, "bound": len(bound), "left_out": excluded}


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

    def skip(folder, names):
        out = {n for n in names if n in IGNORED_DIRS}
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
    result["unique_guids"] = check_guids(assets)
    write_json(run_path / "unity" / "project.json", result)
    return result
