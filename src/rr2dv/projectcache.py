"""Reuse of the imported and probed Unity project between runs (board W34: every rerun repeated the 4-5 minute import).

The key is content-addressed: the exact input bytes (inventory fingerprint and extra files), the AssetRipper exports,
CarCreator's hash, rr2dv's version and every script that shapes the project or the probe (our import and probe code,
the builder core and our editor scripts in the snapshot). Answers (livery, audio, wheel radius) do not enter the
import or the probe, so a rerun with a new answer hits the cache; anything else that changed misses it.

A hit copies the saved project (with Unity's Library, so Unity does not import it again) and the probe's results
into the NEW run folder: runs are never reused, and the cache is only read after it was completely written (it is
renamed into place). Only the newest KEEP entries are kept; only this cache's own folders are ever deleted.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
import uuid
from pathlib import Path

from . import __version__
from .jsonio import read_json, sha256_file, write_json

KEEP = 3
COMPLETE = "complete.json"
SKIP = ("Temp", "Logs", "obj")  # Unity's lock and session files never travel


def _scripts() -> dict[str, str]:
    """What shapes the imported project and the probe's measurements. The build-only editor scripts are not in the key:
    a restored project gets the current ones (refresh_scripts), so a builder fix does not repeat the import and probe
    (PLW Trojan: about 10 minutes, 2026-09-28)."""
    from .unityproject import tooling_root
    here = Path(__file__).resolve().parent
    tools = tooling_root() / "builder" / "tools"
    files = [here / n for n in ("unityproject.py", "probeinput.py", "assetripper.py", "projectcache.py")]
    files += [here / "unity" / "Rr2dvProbe.cs"]
    files += [tools / "resolve_clip_paths.py", tools / "pilot" / "copy_deps.py"]
    return {f.name: sha256_file(f) for f in files if f.is_file()}


def refresh_scripts(run_path: Path) -> dict:
    """Replace a restored project's editor scripts and app materials with the current ones (Unity recompiles them at
    the next launch; the imported assets and their Library stay). Returns the updated project info."""
    from .unityproject import tooling_root
    info_file = run_path / "unity" / "project.json"
    info = read_json(info_file)
    project = run_path / info["project"]
    editor = project / "Assets" / "Editor"
    here = Path(__file__).resolve().parent
    groups = {"core_scripts": ("builder/tools/unity/", tooling_root() / "builder" / "tools" / "unity"),
              "app_scripts": ("rr2dv/unity/", here / "unity")}
    for field, (prefix, folder) in groups.items():
        current = {f.name: f for f in sorted(folder.glob("*.cs"))}
        for name in [k[len(prefix):] for k in (info.get(field) or {}) if k.startswith(prefix) and k.endswith(".cs")]:
            if name not in current:  # a script since removed must not stay behind and break the compile
                for stale in (editor / name, editor / (name + ".meta")):
                    if stale.is_file():
                        stale.unlink()
        kept = {k: v for k, v in (info.get(field) or {}).items() if not k.endswith(".cs")}
        for name, script in current.items():
            shutil.copyfile(script, editor / name)
            kept[prefix + name] = sha256_file(script)
        info[field] = kept
    materials = project / "Assets" / "Rr2dv" / "Materials"
    materials.mkdir(parents=True, exist_ok=True)
    for mat in sorted((here / "unity" / "materials").iterdir()):
        shutil.copyfile(mat, materials / mat.name)
    write_json(info_file, info)
    return info


def discard(work_root: Path, cache_key: str) -> bool:
    """Delete one entry (after that loco built and passed its audit); returns whether there was one."""
    entry = _root(work_root) / cache_key
    if not (entry / COMPLETE).is_file():
        return False
    shutil.rmtree(entry, ignore_errors=True)
    for folder in (entry.parent, entry.parent.parent):  # _cache/projects, then _cache, only when left empty
        try:
            folder.rmdir()
        except OSError:
            break
    return True


def _export_signature(path: Path) -> str:
    """Every file of an export by path and size: the export folder is named by its bundle's content, and a fresh
    export of the same bundle in each run (temporary files deleted) must still hit; a changed file size misses."""
    h = hashlib.sha256()
    for f in sorted(p for p in path.rglob("*") if p.is_file()):
        h.update(f"{f.relative_to(path).as_posix()}|{f.stat().st_size}\n".encode())
    return h.hexdigest()


def key(inv: dict, exports: dict, car_creator: Path) -> str:
    from .pipeline import fingerprint
    data = {"version": __version__, "input": fingerprint(inv), "extra": inv.get("extra_files", []),
            "exports": sorted((k, Path(v["path"]).name, _export_signature(Path(v["path"]))) for k, v in exports.items()),
            "carCreator": sha256_file(car_creator), "scripts": _scripts()}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:24]


def _root(work_root: Path) -> Path:
    return work_root / "_cache" / "projects"


def restore(work_root: Path, cache_key: str, run_path: Path) -> dict | None:
    """Copy a cached project and probe into run_path; returns the project info, or None when there is no entry."""
    entry = _root(work_root) / cache_key
    if not (entry / COMPLETE).is_file():
        return None
    shutil.copytree(entry / "project", run_path / "unity" / "project", ignore=shutil.ignore_patterns(*SKIP))
    shutil.copyfile(entry / "project.json", run_path / "unity" / "project.json")
    if (entry / "import").is_dir():
        shutil.copytree(entry / "import", run_path / "import", dirs_exist_ok=True)
    shutil.copytree(entry / "probe", run_path / "probe")
    (entry / COMPLETE).touch()  # most recently used
    return read_json(run_path / "unity" / "project.json")


def save(work_root: Path, cache_key: str, run_path: Path) -> bool:
    """Save this run's imported project and probe results under the key (after a successful probe, before the build
    changes the project). Never overwrites an entry; returns whether it saved."""
    root = _root(work_root)
    entry = root / cache_key
    if entry.exists():
        return False
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / f".saving-{uuid.uuid4().hex[:12]}"
    try:
        shutil.copytree(run_path / "unity" / "project", tmp / "project", ignore=shutil.ignore_patterns(*SKIP))
        shutil.copyfile(run_path / "unity" / "project.json", tmp / "project.json")
        if (run_path / "import").is_dir():
            shutil.copytree(run_path / "import", tmp / "import")
        shutil.copytree(run_path / "probe", tmp / "probe")
        write_json(tmp / COMPLETE, {"key": cache_key, "from_run": run_path.name, "saved": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
        tmp.rename(entry)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    prune(work_root)
    return True


def prune(work_root: Path, keep: int = KEEP) -> None:
    root = _root(work_root)
    entries = sorted((p for p in root.iterdir() if p.is_dir() and (p / COMPLETE).is_file()),
                     key=lambda p: (p / COMPLETE).stat().st_mtime, reverse=True)
    for old in entries[keep:]:
        shutil.rmtree(old, ignore_errors=True)
    for stale in root.glob(".saving-*"):  # an interrupted save from an earlier run
        if time.time() - stale.stat().st_mtime > 24 * 3600:
            shutil.rmtree(stale, ignore_errors=True)
