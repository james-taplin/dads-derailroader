"""Stock-locomotive oil-cup map run: the bulk run's machinery with VfOil.cs in place of VfMeasure.cs.

For each of the 21 stock steam packs it prepares the Unity project exactly as run_bulk.py does (pipeline up to the pre-build
review, every answer refused, nothing built, nothing installed), then runs VfOil.Run once in it. VfOil applies the oil-cup
requirements (main-rod ends as a left/right pair, 4 x 3 cm level seat within 0.3 m of the end, clear 3.5 cm x 9 cm cup space
through a whole turn, 12 cm apart, running boards only as a fallback) to the source prefab and records every candidate and the
reason it passed or failed. Small results (JSON, plus a few dozen small pictures of the running gear with the candidates marked) go to <out-dir>/results/<pack>/ as each pack finishes and <out-dir>/vf_oil.zip is
rebuilt after every pack, so a crash loses at most one pack. Rerun the same command to resume (--force redoes passed packs).

  set PYTHONPATH=src
  python tools\\vanilla\\run_oil.py --dry-run               (checks only: nothing is launched)
  python tools\\vanilla\\run_oil.py --pilot                 (K-28T and T-17 first)
  python tools\\vanilla\\run_oil.py                         (all 21)

Kept projects from a bulk run are reused when their inputs match, so this is much faster after run_bulk.py. Read-only towards
Railroader and Derail Valley. Never installs. The zip is about 10-15 MB because of the pictures.
Exit codes: 0 every pack passed, 1 some packs failed (zip still written), 2 preflight failed, 130 interrupted.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_bulk  # noqa: E402
from rr2dv.jsonio import read_json  # noqa: E402

run_bulk.SCRIPT = HERE / "VfOil.cs"
run_bulk.METHOD = "VfOil.Run"
run_bulk.OUTNAME = "vf-oil.json"
run_bulk.OUT_PREFIX = "vf-oil"
run_bulk.ZIP_NAME = "vf_oil.zip"
run_bulk.TOOL_NAME = "run_oil.py"
run_bulk.OUT_DEFAULT = "vf_oil_out"
run_bulk.RENDER_DIR = "oil-renders"


def check_output(path: Path, run: Path) -> dict:
    """Did Unity really map what we asked? Facts only; the analysis is done offline."""
    if not path.is_file():
        return {"verdict": "FAILED", "why": "no vf-oil.json was written"}
    try:
        data = read_json(path)
        expected = len(read_json(run / run_bulk.PROJECT_FILE).get("vehicles", []))
    except Exception as e:
        return {"verdict": "FAILED", "why": f"unreadable output: {type(e).__name__}: {e}"}
    vehicles = data.get("vehicles") or []
    locos = [v for v in vehicles if not v.get("skipped")]
    facts = {"vehicles": len(vehicles), "expectedVehicles": expected, "problems": len(data.get("problems") or []),
             "locos": len(locos), "movingParts": sum(len(v.get("movingParts") or []) for v in locos),
             "rods": sum(len(v.get("rods") or []) for v in locos),
             "mainRods": sum(1 for v in locos for r in (v.get("rods") or []) if r.get("verdict") == "main rod"),
             "endSeats": sum(len(v.get("endSeats") or []) for v in locos),
             "pairs": sum(len(v.get("pairs") or []) for v in locos),
             "boardSeats": sum(len(v.get("boardSeats") or []) for v in locos),
             "renders": sum(len(v.get("renders") or []) for v in locos),
             "nubParts": sum(len(v.get("nubParts") or []) for v in locos),
             "nubIslands": sum(len(p.get("islands") or []) for v in locos for p in (v.get("nubParts") or [])),
             "nubBumps": sum(len(p.get("bumps") or []) for v in locos for p in (v.get("nubParts") or []))}
    if len(vehicles) != expected:
        return {"verdict": "FAILED", "why": f"{len(vehicles)} vehicles mapped, {expected} expected", **facts}
    if not locos:
        return {"verdict": "FAILED", "why": "no locomotive body was mapped", **facts}
    if facts["movingParts"] == 0:
        return {"verdict": "FAILED", "why": "no moving parts were found: the driving clips did not move anything", **facts}
    return {"verdict": "OK" if not facts["problems"] else "OK-with-problems", **facts}


run_bulk.check_output = check_output

if __name__ == "__main__":
    sys.exit(run_bulk.main())
