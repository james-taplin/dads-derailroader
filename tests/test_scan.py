import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fixtures import loco, part, standard_mod, tender, truck, write_pack
from rr2dv.jsonio import read_json_lenient, sha256_file
from rr2dv.rrmod import Index, blocking, inventory


def codes(inv):
    return sorted(i["code"] for i in inv["issues"])


class LenientJson(unittest.TestCase):
    def test_trailing_commas_removed_outside_strings_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "d.json"
            p.write_text('{"a": "x,}", "b": [1, 2,], "c": {"d": ",]",},}', encoding="utf-8")
            self.assertEqual(read_json_lenient(p), {"a": "x,}", "b": [1, 2], "c": {"d": ",]"}})


class Scan(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.m = standard_mod(self.tmp)

    def test_full_closure_resolves_across_mods(self):
        index = Index(self.m["mod"], [self.m["search"]])
        self.assertEqual([o["identifier"] for _, o in index.steam_locomotives()], ["ts-260-a"])
        inv = inventory(index, "ts-260-a")
        self.assertEqual(blocking(inv), [])
        self.assertEqual(inv["tender"]["id"], "tt-260-a")
        self.assertEqual([t["id"] for t in inv["trucks"]], ["test-truck-2s"])
        self.assertEqual(inv["trucks"][0]["pack"]["root"], "search1")
        self.assertEqual([(p["pack"], p["asset"], p["filename"]) for p in inv["parts"]], [("parts", "bell", "bell.prefab")])
        self.assertEqual([p["name"] for p in inv["packs"]], ["parts", "ts-260-a", "Trucks"])
        self.assertEqual((inv["audio"]["basis"], inv["audio"]["replaces"]), ("S060", ["Chuff", "Whistle"]))
        self.assertEqual([c["purpose"] for c in inv["controls"]["radial"]], ["Throttle", "Reverser"])
        bundle = self.m["mod"] / "ts-260-a" / "bundle"
        rec = next(p for p in inv["packs"] if p["name"] == "ts-260-a")
        self.assertIn({"name": "bundle", "bytes": bundle.stat().st_size, "sha256": sha256_file(bundle)}, rec["files"])

    def test_missing_truck_blocks(self):
        inv = inventory(Index(self.m["mod"]), "ts-260-a")
        self.assertEqual(codes(inv), ["missing-truck"])

    def test_duplicate_identifier_at_same_rank_is_an_error_not_a_first_match(self):
        write_pack(self.m["mod"] / "copy", objects=[tender("tt-260-a")], assets={})
        inv = inventory(Index(self.m["mod"], [self.m["search"]]), "ts-260-a")
        self.assertIn("ambiguous", codes(inv))

    def test_input_outranks_search_roots(self):
        write_pack(self.m["mod"] / "localtrucks", objects=[truck("test-truck-2s")], assets={})
        inv = inventory(Index(self.m["mod"], [self.m["search"]]), "ts-260-a")
        self.assertEqual(blocking(inv), [])
        self.assertEqual(inv["trucks"][0]["pack"]["root"], "input")

    def test_malformed_objects_do_not_crash(self):
        write_pack(self.m["mod"] / "odd", objects=[{"identifier": "x", "definition": []},
                                                  {"identifier": "y", "definition": {"kind": "SteamLocomotive",
                                                   "components": [{"kind": 5}, "junk", {"kind": "PrefabModelComponent"}]}}], assets={})
        index = Index(self.m["mod"], [self.m["search"]])
        inv = inventory(index, "y")
        self.assertIn("bad-part", codes(inv))
        self.assertEqual(inv["component_kinds"], {"5": 1, "PrefabModelComponent": 1})

    def test_missing_part_asset_and_bundle(self):
        (self.m["mod"] / "parts" / "Catalog.json").write_text('{"assets": {}}')
        (self.m["mod"] / "ts-260-a" / "bundle").unlink()
        inv = inventory(Index(self.m["mod"], [self.m["search"]]), "ts-260-a")
        self.assertEqual(codes(inv), ["left-out", "missing-bundle"])
        self.assertEqual([i["code"] for i in blocking(inv)], ["missing-bundle"])
        self.assertEqual(inv["left_out"][0]["asset"], "bell")
        self.assertIn("broken in the source mod", inv["left_out"][0]["reason"])
        self.assertNotIn("parts", [p["name"] for p in inv["packs"]])

    def test_empty_asset_reference_is_left_out_with_its_anchored_components(self):
        bad = part("Test Loco Mod\\parts", "", "PrefabModelComponent 12")
        lamp = {"kind": "Headlight", "name": "lamp", "parent": {"path": ["PrefabModelComponent 12", "glass"]}}
        (self.m["mod"] / "ts-260-a" / "Definitions.json").write_text(json.dumps({"objects": [
            loco("ts-260-a", tender="tt-260-a", parts=[part("Test Loco Mod\\parts", "bell", "bell1"), bad], extra_components=[lamp]),
            tender("tt-260-a", truck="test-truck-2s")]}))
        inv = inventory(Index(self.m["mod"], [self.m["search"]]), "ts-260-a")
        self.assertEqual(blocking(inv), [])
        self.assertEqual([p["asset"] for p in inv["parts"]], ["bell"])
        self.assertEqual((inv["left_out"][0]["asset"], inv["left_out"][0]["anchored"]), ("", ["lamp"]))
        self.assertIn("loses its anchor: lamp", inv["left_out"][0]["effect"])

    def test_broken_unrelated_pack_is_only_a_warning(self):
        # X24: one bad Catalog.json elsewhere in the catalogue must not stop every loco.
        bad = self.m["mod"] / "k50parts"
        bad.mkdir()
        (bad / "Catalog.json").write_text('{"assets": {"a": "bad\u0001"}}'.replace("\\u0001", "\x01"))
        index = Index(self.m["mod"], [self.m["search"]])
        self.assertEqual([(i.severity, i.code) for i in index.issues], [("warning", "pack-unreadable")])
        self.assertEqual(blocking(inventory(index, "ts-260-a")), [])

    def test_broken_needed_pack_is_an_error(self):
        (self.m["mod"] / "parts" / "Catalog.json").write_text("{not json")
        inv = inventory(Index(self.m["mod"], [self.m["search"]]), "ts-260-a")
        self.assertEqual(codes(inv), ["pack-unreadable"])
        (self.m["mod"] / "parts" / "Catalog.json").write_text('{"assets": {"bell": {"filename": "bell.prefab"}}}')
        (self.m["mod"] / "ts-260-a" / "Catalog.json").write_text("[")
        self.assertIn("pack-unreadable", codes(inventory(Index(self.m["mod"], [self.m["search"]]), "ts-260-a")))

    def test_unreadable_definitions_are_named_when_something_is_missing(self):
        broken = self.m["mod"] / "broken"
        broken.mkdir()
        (broken / "Definitions.json").write_text("{oops")
        inv = inventory(Index(self.m["mod"]), "ts-260-a")  # truck mod not searched
        missing = next(i for i in inv["issues"] if i["code"] == "missing-truck")
        self.assertIn("input:broken", missing["message"])
        self.assertIn("unreadable-definitions", codes(inv))

    def test_input_inside_search_root_is_indexed_once(self):
        index = Index(self.m["mod"], [self.tmp / "input"])
        self.assertEqual(len([p for p in index.packs if p.name == "ts-260-a"]), 1)

    def test_same_bytes_give_same_inventory_anywhere(self):
        first = inventory(Index(self.m["mod"], [self.m["search"]]), "ts-260-a")
        moved = self.tmp / "elsewhere"
        moved_packs = moved / "Railroader_Data" / "StreamingAssets" / "AssetPacks"
        shutil.copytree(self.m["search"], moved_packs)
        second = inventory(Index(moved_packs / "ts-260-a", [moved_packs]), "ts-260-a")
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_non_steam_locomotives_are_listed_not_converted(self):
        write_pack(self.m["mod"] / "diesel", objects=[loco("ds-1", kind="DieselLocomotive")], assets={})
        index = Index(self.m["mod"], [self.m["search"]])
        self.assertEqual([o["identifier"] for _, o in index.other_locomotives()], ["ds-1"])
        self.assertIn("not-steam", codes(inventory(index, "ds-1")))


if __name__ == "__main__":
    unittest.main()
