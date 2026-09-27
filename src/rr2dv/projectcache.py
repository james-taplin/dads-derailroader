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
    from .unityproject import tooling_root
    here = Path(__file__).resolve().parent
    tools = tooling_root() / "builder" / "tools"
    files = [here / n for n in ("unityproject.py", "probeinput.py", "assetripper.py", "projectcache.py")]
    files += sorted((here / "unity").glob("*.cs")) + sorted((tools / "unity").glob("*.cs"))
    files += [tools / "resolve_clip_paths.py", tools / "pilot" / "copy_deps.py"]
    return {f.name: sha256_file(f) for f in files if f.is_file()}


def _export_signature(path: Path) -> str:
    """Every file of a cached export by path, size and modification time: the export cache is content-addressed by
    bundle, but a changed or damaged export must still miss this cache."""
    h = hashlib.sha256()
    for f in sorted(p for p in path.rglob("*") if p.is_file()):
        st = f.stat()
        h.update(f"{f.relative_to(path).as_posix()}|{st.st_size}|{st.st_mtime_ns}\n".encode())
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
