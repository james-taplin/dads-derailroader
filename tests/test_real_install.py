"""Regression against a REAL Railroader install (skipped unless RR2DV_RAILROADER names the install folder).

Reads only Definitions.json, Catalog.json and file hashes of the stock packs; writes nothing. Run by whoever has the game:
  set RR2DV_RAILROADER=C:\\Program Files (x86)\\Steam\\steamapps\\common\\Railroader
  PYTHONPATH=src:tests python -m unittest tests.test_real_install
The expected tender and truck for each locomotive were taken from Railroader build 20238526 (VF Phase 1); a different
build may legitimately differ, and then this test says so."""
import os
import unittest
from pathlib import Path

from rr2dv import stock
from rr2dv.pipeline import search_roots
from rr2dv.rrmod import Index, blocking, inventory

# pack -> (tender id or None, truck ids)
EXPECTED = {
    "ls-060-s23": ("lt-060-s23", ["truck.andrews.type-a"]),
    "ls-080-s51": ("lt-080-s51", ["truck.bettendorf.sm"]),
    "ls-2100-d46": ("lt-2100-d46", ["truck.archbar.diamond"]),
    "ls-2102-f71": ("lt-2102-f71", ["truck.andrews.type-a"]),
    "ls-260-g16": ("lt-260-g16", ["truck.archbar.diamond"]),
    "ls-260-g25": ("lt-260-g25", ["truck.andrews.type-a"]),
    "ls-280-c25": ("lt-280-c25", ["truck.archbar.diamond"]),
    "ls-280-c46": ("lt-280-c46", ["truck.bettendorf.sm"]),
    "ls-280-c55": ("lt-280-c55", ["truck.andrews.type-a"]),
    "ls-282-k28t": (None, []),
    "ls-282-k35": ("lt-282-k35", ["truck.archbar.tatum"]),
    "ls-284-b65": ("lt-284-b65", ["truck.buckeye.conventional"]),
    "ls-440-a23": ("lt-440-a23", ["truck.archbar.tatum"]),
    "ls-442-a26": ("lt-442-a26", ["truck.bettendorf.sm"]),
    "ls-460-t17": ("lt-460-t17", ["truck.archbar.tatum"]),
    "ls-460-t21": ("lt-460-t21", ["truck.archbar.diamond"]),
    "ls-460-t22": ("lt-460-t22", ["truck.andrews.type-a"]),
    "ls-462-p18": ("lt-462-p18", ["truck.archbar.diamond"]),
    "ls-462-p43": ("lt-462-p43", ["truck.usra.2axle"]),
    "ls-462-p48": ("lt-462-p48", ["truck.commonwealth.conventional"]),
    "ls-480-c40": ("lt-480-c40", ["truck.commonwealth.fwtt"]),
}
ROOT = os.environ.get("RR2DV_RAILROADER")


@unittest.skipUnless(ROOT and Path(ROOT).is_dir(), "set RR2DV_RAILROADER to a Railroader install folder")
class RealStockPacks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from rr2dv import installs
        cls.rr = installs.railroader(__import__("rr2dv.machine", fromlist=["Machine"]).Machine(None, {"railroader": ROOT}))

    def test_expected_table_covers_exactly_the_stock_steam_list(self):
        source = (Path(__file__).resolve().parents[1] / "src" / "rr2dv" / "stock.py").read_text(encoding="utf-8")
        from test_vanilla_scope import literal_dict_keys
        self.assertEqual(set(EXPECTED), literal_dict_keys(source, "STEAM"))

    def test_every_stock_steam_locomotive_resolves_from_railroaders_own_packs_only(self):
        problems = []
        for pack, (tender, trucks) in EXPECTED.items():
            folder = self.rr.asset_packs / pack
            if not folder.is_dir():
                problems.append(f"{pack}: pack not found")
                continue
            inv = inventory(Index(folder, search_roots(self.rr)), pack, hash_files=False)
            if blocking(inv):
                problems.append(f"{pack}: blocked: {[i['code'] for i in blocking(inv)]}")
            got = ((inv.get("tender") or {}).get("id"), [t["id"] for t in inv["trucks"]])
            if got != (tender, trucks):
                problems.append(f"{pack}: tender/trucks {got} != expected {(tender, trucks)}")
            if [s["kind"] for s in inv["sources"]] != ["game"]:
                problems.append(f"{pack}: sources {[s['id'] for s in inv['sources']]}")
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
