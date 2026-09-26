"""One folder per conversion run, holding every input copy, record and log. Runs are never reused."""
from __future__ import annotations

import re
import secrets
import shutil
import time
from pathlib import Path

from . import __version__
from .jsonio import read_json, sha256_file, write_json

# Stage order follows the guide's acceptance states (Q01): located -> metadata linked -> extracted ->
# Unity inspected -> exported -> audited. `available` marks what this version implements.
STAGES = [
    ("locate", "Find the locomotive in the input", True),
    ("link", "Resolve tender, trucks and parts", True),
    ("stage", "Copy the required packs into the run folder", True),
    ("extract", "Export the bundles with AssetRipper", True),
    ("import", "Prepare the Unity project", True),
    ("probe", "Measure the model", False),
    ("record", "Generate the vehicle record", False),
    ("build", "Build the CCL pack in Unity", False),
    ("audit", "Check the built pack", False),
    ("publish", "Copy the finished pack to the output folder", True),
]
STAGE_NAMES = [s[0] for s in STAGES]


def _safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", text)[:40] or "run"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class Run:
    def __init__(self, path: Path):
        self.path = path
        self.file = path / "run.json"
        self.record = read_json(self.file) if self.file.exists() else {}

    @classmethod
    def create(cls, work_root: Path, label: str, request: dict) -> "Run":
        work_root.mkdir(parents=True, exist_ok=True)
        run_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{_safe(label)}-{secrets.token_hex(3)}"
        path = work_root / run_id
        path.mkdir()  # never exist_ok: a run folder is always new
        run = cls(path)
        run.record = {
            "schema": 1,
            "run_id": run_id,
            "app_version": __version__,
            "created": _now(),
            "request": request,
            "status": "running",
            "stages": {name: {"status": "pending"} for name in STAGE_NAMES},
        }
        run.save()
        return run

    def save(self) -> None:
        write_json(self.file, self.record)

    def begin(self, stage: str) -> None:
        self.record["stages"][stage] = {"status": "running", "started": _now()}
        self.save()

    def finish(self, stage: str, status: str, detail: str = "", **extra) -> None:
        entry = self.record["stages"][stage]
        entry.update(status=status, finished=_now(), detail=detail, **extra)
        self.save()

    def close(self, status: str, detail: str = "") -> None:
        self.record.update(status=status, finished=_now(), detail=detail)
        self.save()


def stage_inputs(run: Run, inventory: dict, index) -> dict:
    """Copy every file of every required pack into run/inputs and check each copy against the hash taken
    during `link`. A mismatch means the source changed underneath us; the run stops."""
    by_key = {(p.root.label, p.rel): p for p in index.packs}
    roots = {r.label: r.path for r in index.roots}
    staged = []

    def copy_checked(src: Path, target: Path, expected: str, label: str) -> None:
        shutil.copyfile(src, target)
        actual = sha256_file(target)
        if actual != expected:
            raise RuntimeError(f"{src} changed while it was being copied (hash {actual[:12]} != {expected[:12]}); rerun when nothing else is writing to the mod")
        staged.append({"pack": label, "file": target.relative_to(run.path).as_posix(), "sha256": actual})

    for rec in inventory["packs"]:
        pack = by_key[(rec["root"], rec["path"])]
        dest = run.path / "inputs" / rec["root"] / (rec["path"] or pack.name)
        dest.mkdir(parents=True, exist_ok=False)
        for f in rec["files"]:
            src = next(p for p in pack.files.values() if p.name == f["name"])
            copy_checked(src, dest / f["name"], f["sha256"], rec["name"])
    for rec in inventory.get("extra_files", []):  # optional component groups, images
        target = run.path / "inputs" / rec["root"] / rec["path"]
        if target.exists():
            raise RuntimeError(f"two inputs map to {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        copy_checked(roots[rec["root"]] / rec["path"], target, rec["sha256"], rec["role"])
    return {"files": staged}
