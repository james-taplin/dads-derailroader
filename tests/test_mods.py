"""Mod-level behaviour: licences, optional component groups, images, code-mod components, audio."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import os
import sys

from fixtures import fake_assetripper, fake_carcreator, fake_unity, loco, part, standard_mod, tender, tree_state, write_pack
from rr2dv.jsonio import read_json, sha256_file
from rr2dv.machine import Machine
from rr2dv.pipeline import EXIT_FAILED, EXIT_INCOMPLETE, convert
from rr2dv.rrmod import Index, audio_basis, blocking, inventory

STRICT = "You may not open, decompile, reverse engineer, or modify any part of the Mod. No redistribution. Personal use only."


def codes(inv):
    return sorted(i["code"] for i in inv["issues"])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.m = standard_mod(self.tmp)
        os.environ["FAKE_AR_STATE"] = str(self.tmp / "ar-state")
        self.addCleanup(os.environ.pop, "FAKE_AR_STATE", None)
        self.machine = Machine(None, {**self.m["games"], "workRoot": str(self.tmp / "work"), "assetRipper": str(fake_assetripper(self.tmp / "tools")),
                                      "unity": str(fake_unity(self.tmp / "tools")), "carCreator": str(fake_carcreator(self.tmp / "tools" / "CarCreator_3.1.9.unitypackage"))})

    def inv(self, **kw):
        return inventory(Index(self.m["mod"], [self.m["search"]]), "ts-260-a", **kw)


class Dependencies(Base):
    """W25: every dependency in the user's own install is used; licences are not read; only a part broken in its own
    mod is left out, with what it takes with it."""

    def parts_mod(self, where=None, catalogue=True):
        base = where or (self.m["search"] / "PartsMod")
        write_pack(base / "extras", assets={"horn": {"filename": "horn.prefab"}} if catalogue else {"other": {"filename": "o.prefab"}})
        (base / "info.json").write_text('{"Id": "PartsMod"}')
        (self.m["mod"] / "ts-260-a" / "Definitions.json").write_text(json.dumps({"objects": [
            loco("ts-260-a", tender="tt-260-a", parts=[part("Test Loco Mod\\parts", "bell", "bell1"), part("PartsMod\\extras", "horn", "horn1")]),
            tender("tt-260-a", truck="test-truck-2s")]}))

    def test_railroader_game_parts_are_used(self):
        game = self.tmp / "Railroader" / "Railroader_Data" / "StreamingAssets" / "AssetPacks"
        self.parts_mod(where=game / "PartsMod")
        inv = inventory(Index(self.m["mod"], [self.m["search"], game]), "ts-260-a")
        self.assertEqual(blocking(inv), [])
        self.assertEqual([p["asset"] for p in inv["parts"]], ["bell", "horn", "TestChime"])  # TestChime: the whistle mesh

    def test_trucks_and_tenders_from_other_mods_are_used(self):
        write_pack(self.m["search"] / "TenderMod" / "Tenders", objects=[tender("tt-ext", truck="test-truck-2s")],
                   assets={"tt-ext": {"filename": "tt-ext.prefab"}}, bundle_name="Bundle")
        (self.m["mod"] / "ts-260-a" / "Definitions.json").write_text(json.dumps({"objects": [loco("ts-260-a", tender="tt-ext")]}))
        inv = self.inv()
        self.assertEqual(blocking(inv), [])
        self.assertEqual({v["id"]: v["role"] for v in inv["vehicles"]}, {"ts-260-a": "locomotive", "tt-ext": "tender", "test-truck-2s": "truck"})
        self.assertEqual([p["name"] for p in inv["packs"]], ["ts-260-a", "Tenders", "Trucks", "audio.whistles01"])

    def test_broken_part_is_left_out_never_staged_or_placed(self):
        self.parts_mod(catalogue=False)
        out = convert(self.m["mod"], self.machine)
        self.assertEqual(out.code, EXIT_INCOMPLETE, out.message)
        self.assertFalse((out.run.path / "inputs" / "search1" / "PartsMod").exists())
        rec = read_json(out.run.path / "record" / "vehicle-record.json")
        placed = [c["name"] for c in rec["config"]["Components"]["value"]]
        self.assertIn("bell1", placed)
        self.assertNotIn("horn1", placed)
        self.assertEqual([l["asset"] for l in rec["metadata"]["leftOut"]], ["horn"])
        self.assertIn("left out: 1", " ".join(rec["metadata"]["pending"]))

    def test_components_anchored_in_a_left_out_part_are_not_placed(self):
        from rr2dv import record
        c = {"kind": "Headlight", "name": "lamp", "parent": {"path": ["horn1", "glass"]}}
        left = [{"what": "part", "owner": "ts-260-a", "pack_identifier": "PartsMod\\extras", "asset": "horn", "anchored": ["lamp"]}]
        self.assertTrue(record.left_out_component(c, "ts-260-a", left))
        self.assertFalse(record.left_out_component(c, "tt-260-a", left))

    def test_sources_credit_railroader_only(self):
        # Source files come from Railroader's own asset packs and are credited as base-game content.
        objects = [loco("ts-260-a", tender="tt-260-a", parts=[part("ts-260-a\\parts", "bell", "bell1")]),
                   tender("tt-260-a", truck="game-truck")]
        (self.m["mod"] / "ts-260-a" / "Definitions.json").write_text(json.dumps({"objects": objects}))
        game = self.tmp / "Railroader" / "Railroader_Data" / "StreamingAssets" / "AssetPacks"
        write_pack(game / "game-truck", objects=[{"identifier": "game-truck", "definition": {"kind": "Truck", "modelIdentifier": "game-truck"}}],
                   assets={"game-truck": {"filename": "game-truck.prefab"}})
        inv = inventory(Index(self.m["mod"], [self.m["search"], game]), "ts-260-a")
        self.assertEqual(blocking(inv), [])
        self.assertEqual([(s["id"], s["kind"], s["credits"]) for s in inv["sources"]], [("Railroader (base game asset packs)", "game", [])])
        self.assertIn("game-truck", inv["sources"][0]["packs"])
        self.assertIn("ts-260-a", inv["sources"][0]["packs"])


class Definitions(Base):
    def test_model_may_name_a_prefab_file_instead_of_a_catalogue_key(self):
        pack = self.m["mod"] / "ts-260-a"
        cat = json.loads((pack / "Catalog.json").read_text())
        cat["assets"] = {"ts-260-a": {"filename": "ts-260-a.prefab"}, "tt-260-a-v2": {"filename": "tt-260-a.prefab"}}
        (pack / "Catalog.json").write_text(json.dumps(cat))
        self.assertNotIn("model-not-in-catalog", codes(self.inv()))
        cat["assets"] = {"ts-260-a": {"filename": "ts-260-a.prefab"}}
        (pack / "Catalog.json").write_text(json.dumps(cat))
        self.assertIn("model-not-in-catalog", codes(self.inv()))

class Audio(Base):
    def test_boiler_size_rule(self):
        self.assertEqual(audio_basis({"totalHeatingSurface": 1300})["basis"], "S060")  # C-21, small tender engine
        self.assertEqual(audio_basis({"totalHeatingSurface": 1478})["basis"], "S060")  # GWR 7200, ~32,000 lbf tank
        self.assertEqual(audio_basis({"totalHeatingSurface": 1500})["basis"], "S282")
        self.assertEqual(audio_basis({"totalHeatingSurface": 1735})["basis"], "S282")  # G-29
        self.assertEqual(audio_basis({"totalHeatingSurface": 1886})["basis"], "S282")  # USRA 0-6-0 tender switcher
        self.assertEqual(audio_basis({"totalHeatingSurface": 6730})["basis"], "S282")
        self.assertIsNone(audio_basis({})["basis"])
        self.assertEqual(audio_basis({"totalHeatingSurface": 6730}, "S060")["rule"], "chosen by the user")
        with self.assertRaises(ValueError):
            audio_basis({}, "S999")

    def test_missing_heating_surface_needs_an_answer(self):
        write_pack(self.m["mod"] / "ts-260-a",
                   objects=[loco("ts-260-a", tender="tt-260-a", heating_surface=None), tender("tt-260-a", truck="test-truck-2s")],
                   assets={"ts-260-a": {"filename": "a.prefab"}, "tt-260-a": {"filename": "t.prefab"}})
        out = convert(self.m["mod"], self.machine)
        self.assertEqual(out.code, EXIT_FAILED)
        self.assertIn("--audio", out.message)
        out = convert(self.m["mod"], self.machine, audio="S282")
        self.assertEqual(out.code, EXIT_INCOMPLETE, out.message)
        self.assertEqual(out.run.record["answers"]["audio"]["basis"], "S282")
        self.assertEqual(read_json(out.run.file)["answers"]["audio"]["rule"], "chosen by the user")


if __name__ == "__main__":
    unittest.main()


class PhantomMainDriver(unittest.TestCase):
    def test_a_main_driver_with_no_clip_or_part_hands_over_to_its_animated_twin(self):
        from rr2dv.rrmod import definition
        sets = [{"offset": 5.75, "length": 1, "diameter": .85, "numberOfAxles": 1, "animation": {"clipName": "Pilot"}},
                {"offset": .1, "length": 5.2, "diameter": 1.5, "numberOfAxles": 4, "animation": {"clipName": "Drivers"}, "transform": None},
                {"offset": 0, "length": 5.2, "diameter": .99, "numberOfAxles": 4, "animation": None, "transform": {"path": None}},
                {"offset": -4.75, "length": 1, "diameter": 1.2, "numberOfAxles": 1, "animation": {"clipName": "Trailing"}}]
        d = definition({"definition": {"mainDriverIndex": 2, "wheelsets": sets}})
        self.assertEqual(len(d["wheelsets"]), 3)
        self.assertEqual(d["wheelsets"][d["mainDriverIndex"]]["animation"]["clipName"], "Drivers")
        self.assertTrue(d["rr2dvWheelsetNotes"])

    def test_a_normal_main_driver_is_untouched(self):
        from rr2dv.rrmod import definition
        raw = {"mainDriverIndex": 0, "wheelsets": [{"numberOfAxles": 3, "animation": {"clipName": "Drivers"}}]}
        self.assertIs(definition({"definition": raw}), raw)
