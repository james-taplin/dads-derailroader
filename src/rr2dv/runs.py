"""One folder per conversion run, holding every input copy, record and log. Runs are never reused."""
from __future__ import annotations

import platform
import re
import secrets
import shutil
import sys
import time
from pathlib import Path
from typing import Callable

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
    ("probe", "Measure the model", True),
    ("record", "Generate the vehicle record", True),
    ("review", "Review brakes, spawning and simulation", True),
    ("build", "Build the CCL pack in Unity", True),
    ("audit", "Check the built pack", True),
    ("publish", "Install into the Derail Valley Mods folder after the personal-use notice", True),
]
STAGE_NAMES = [s[0] for s in STAGES]


RUN_LABEL_MAX = 20  # keeps run folder names short: Unity 2019.4 on Windows fails on paths over 260 characters
RUN_ID_MAX = len("20260926-231733") + 1 + RUN_LABEL_MAX + 1 + 6


def _safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", text)[:RUN_LABEL_MAX] or "run"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class Run:
    def __init__(self, path: Path):
        self.path = path
        self.file = path / "run.json"
        self.record = read_json(self.file) if self.file.exists() else {}
        # Called with (stage or None for the whole run, status, detail) on every change; the GUI shows progress with it.
        self.listener: Callable[[str | None, str, str], None] | None = None

    def _notify(self, stage: str | None, status: str, detail: str = "") -> None:
        if self.listener:
            self.listener(stage, status, detail)

    def log(self, text: str) -> None:
        """Append to run.log, the run's readable diary: stages, findings, answers and any error's full traceback.
        Never lets a logging problem stop the run."""
        stamp = time.strftime("%H:%M:%S")
        lines = str(text).rstrip("\n").split("\n")
        try:
            with open(self.path / "run.log", "a", encoding="utf-8") as f:
                f.write(f"{stamp}  {lines[0]}\n" + "".join(f"          {line}\n" for line in lines[1:]))
        except OSError:
            pass

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
        from .applog import app_revision
        run.log(f"rr2dv {app_revision()} run {run_id}, started {_now()}\n"
                f"Python {sys.version.split()[0]} on {platform.platform()}")
        return run

    def save(self) -> None:
        write_json(self.file, self.record)

    def begin(self, stage: str) -> None:
        self.record["stages"][stage] = {"status": "running", "started": _now()}
        self.save()
        self.log(f"[{stage}] started")
        self._notify(stage, "running")

    def finish(self, stage: str, status: str, detail: str = "", **extra) -> None:
        entry = self.record["stages"][stage]
        entry.update(status=status, finished=_now(), detail=detail, **extra)
        self.save()
        self.log(f"[{stage}] {status}" + (f": {detail}" if detail else ""))
        self._notify(stage, status, detail)

    def close(self, status: str, detail: str = "") -> None:
        self.record.update(status=status, finished=_now(), detail=detail)
        self.save()
        self.log(f"run {status}" + (f": {detail}" if detail else ""))
        self._notify(None, status, detail)


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
    return {"files": staged}
