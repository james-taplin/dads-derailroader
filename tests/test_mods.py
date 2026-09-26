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
from rr2dv.licences import terms_in
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
        self.machine = Machine(None, {"workRoot": str(self.tmp / "work"), "assetRipper": str(fake_assetripper(self.tmp / "tools")),
                                      "unity": str(fake_unity(self.tmp / "tools")), "carCreator": str(fake_carcreator(self.tmp / "tools" / "CarCreator_3.1.9.unitypackage"))})

    def inv(self, **kw):
        return inventory(Index(self.m["mod"], [self.m["search"]]), "ts-260-a", **kw)


class Licences(Base):
    def test_terms(self):
        self.assertEqual(terms_in(STRICT), ["no-modification", "no-reverse-engineering", "no-redistribution", "personal-use-only"])
        self.assertEqual(terms_in("MIT License. Permission is hereby granted, free of charge, to any person obtaining a copy "
                                  "of this software, to deal in the Software without restriction, including without limitation "
                                  "the rights to use, copy, modify, merge, publish."), [])
        self.assertEqual(terms_in("Licensed under CC BY-NC-ND 4.0."), ["no-derivatives", "no-commercial-use"])
        self.assertEqual(terms_in("Please do not port this locomotive to other games."), ["no-porting"])
        self.assertEqual(terms_in("You may not redistribute any portion of this mod."), ["no-redistribution"])
        readme = "Install: do not edit the folder name.\n\nLicence: free to use, please credit me."
        self.assertEqual(terms_in(readme, readme=True), [])
        self.assertIn("no-modification", terms_in("Licence: no modifications allowed.", readme=True))

    def assertStopped(self, outcome, code):
        self.assertEqual(outcome.code, EXIT_FAILED, outcome.message)
        self.assertEqual(outcome.run.record["stages"]["link"]["status"], "failed")
        issues = read_json(outcome.run.path / "inventory.json")["issues"]
        self.assertIn(code, [i["code"] for i in issues if i["severity"] == "error"])
        self.assertFalse((outcome.run.path / "inputs").exists())

    def test_forbidding_licence_stops_the_conversion_with_no_way_round_it(self):
        (self.m["mod"] / "LICENSE.txt").write_text(STRICT)
        before = tree_state(self.tmp / "input")
        out = convert(self.m["mod"], self.tmp / "out", self.machine, search=[self.m["search"]])
        self.assertStopped(out, "licence-forbids-conversion")
        self.assertIn("will not convert", out.message)
        self.assertEqual(tree_state(self.tmp / "input"), before)
        import inspect
        from rr2dv import cli, pipeline
        self.assertNotIn("accept", inspect.signature(pipeline.convert).parameters)
        self.assertNotIn("--accept-licence", cli.build_parser().format_help() + cli.build_parser()._subparsers._group_actions[0].choices["convert"].format_help())

    def test_licence_files_are_found_by_name_anywhere_near_the_top_of_the_mod(self):
        (self.m["mod"] / "docs").mkdir()
        (self.m["mod"] / "docs" / "Copyright notice.md").write_text("No modifications of any kind are permitted.")
        self.assertIn("licence-forbids-conversion", codes(self.inv()))

    def test_unreadable_licence_stops(self):
        (self.m["mod"] / "LICENSE.pdf").write_bytes(b"%PDF-1.4")
        self.assertIn("licence-unreadable", codes(self.inv()))

    def parts_mod(self, licence: str | None = STRICT, where=None):
        base = where or (self.m["search"] / "PartsMod")
        write_pack(base / "extras", assets={"horn": {"filename": "horn.prefab"}})
        (base / "info.json").write_text('{"Id": "PartsMod"}')
        if licence:
            (base / "LICENSE").write_text(licence)
        (self.m["mod"] / "ts-260-a" / "Definitions.json").write_text(json.dumps({"objects": [
            loco("ts-260-a", tender="tt-260-a", parts=[part("Test Loco Mod\\parts", "bell", "bell1"), part("PartsMod\\extras", "horn", "horn1")]),
            tender("tt-260-a", truck="test-truck-2s")]}))

    def test_a_restricted_dependency_mods_parts_are_left_out_not_copied(self):
        self.parts_mod()
        inv = self.inv()
        self.assertEqual(blocking(inv), [])
        self.assertEqual([p["asset"] for p in inv["parts"]], ["bell"])
        self.assertEqual([(l["what"], l["asset"]) for l in inv["left_out"]], [("part", "horn")])
        self.assertIn("forbids", inv["left_out"][0]["reason"])
        self.assertNotIn("extras", [p["name"] for p in inv["packs"]])
        self.assertNotIn("PartsMod", [m["id"] for m in inv["mods"]])
        self.assertIn("left-out", codes(inv))

    def test_unrestricted_dependency_mods_parts_are_used(self):
        self.parts_mod(licence=None)
        inv = self.inv()
        self.assertEqual(([p["asset"] for p in inv["parts"]], inv["left_out"]), (["bell", "horn"], []))
        self.assertIn("PartsMod", [m["id"] for m in inv["mods"]])

    def test_unreadable_dependency_licence_leaves_its_parts_out(self):
        self.parts_mod(licence=None)
        (self.m["search"] / "PartsMod" / "LICENSE.pdf").write_bytes(b"%PDF-1.4")
        inv = self.inv()
        self.assertEqual(blocking(inv), [])
        self.assertIn("cannot be read", inv["left_out"][0]["reason"])

    def test_railroader_game_parts_are_left_out(self):
        game = self.tmp / "Railroader" / "Railroader_Data" / "StreamingAssets" / "AssetPacks"
        self.parts_mod(licence=None, where=game / "PartsMod")
        inv = inventory(Index(self.m["mod"], [self.m["search"], game]), "ts-260-a")
        self.assertEqual(blocking(inv), [])
        self.assertEqual([(l["asset"], l["reason"]) for l in inv["left_out"]], [("horn", "Railroader game content")])

    def test_left_out_parts_are_never_staged_or_placed(self):
        self.parts_mod()
        out = convert(self.m["mod"], self.tmp / "out", self.machine, search=[self.m["search"]])
        self.assertEqual(out.code, EXIT_INCOMPLETE, out.message)
        self.assertFalse((out.run.path / "inputs" / "search1").exists())
        rec = read_json(out.run.path / "record" / "vehicle-record.json")
        placed = [c["name"] for c in rec["config"]["Components"]["value"]]
        self.assertIn("bell1", placed)
        self.assertNotIn("horn1", placed)
        self.assertEqual([l["asset"] for l in rec["metadata"]["leftOut"]], ["horn"])
        self.assertIn("left out: 1", " ".join(rec["metadata"]["pending"]))

    def test_a_restricted_tender_still_stops_the_conversion(self):
        write_pack(self.m["search"] / "TenderMod" / "Tenders", objects=[tender("tt-ext")], assets={"tt-ext": {"filename": "tt-ext.prefab"}})
        (self.m["search"] / "TenderMod" / "info.json").write_text('{"Id": "TenderMod"}')
        (self.m["search"] / "TenderMod" / "LICENSE").write_text(STRICT)
        (self.m["mod"] / "ts-260-a" / "Definitions.json").write_text(json.dumps({"objects": [loco("ts-260-a", tender="tt-ext")]}))
        self.assertEqual([i["data"]["mod"] for i in blocking(self.inv())], ["TenderMod"])

    def test_a_truck_mod_never_counts_because_trucks_are_replaced(self):
        (self.m["search"] / "TruckMod" / "info.json").write_text('{"Id": "TruckMod"}')
        (self.m["search"] / "TruckMod" / "LICENSE").write_text(STRICT)
        inv = self.inv()
        self.assertEqual(blocking(inv), [])
        self.assertNotIn("TruckMod", [m["id"] for m in inv["mods"]])
        self.assertEqual(inv["trucks"][0]["replaced_by"], "vanilla Derail Valley bogies")

    def test_restricted_mods_images_are_left_out(self):
        decals = self.m["search"] / "DecalPack"
        decals.mkdir()
        (decals / "info.json").write_text('{"Id": "decal-pack"}')
        (decals / "safety.png").write_bytes(b"x")
        (decals / "LICENSE.txt").write_text("No derivative works.")
        group = {"identifier": "tt-260-a", "GroupName": "Safety", "bulkAdds": [{"kind": "CustomImage", "textureName": "decal-pack.safety.png"}]}
        (self.m["mod"] / "safety.json").write_text(json.dumps(group))
        inv = self.inv()
        self.assertEqual(blocking(inv), [])
        self.assertEqual([(l["what"], l["id"]) for l in inv["left_out"]], [("image", "decal-pack.safety.png")])
        self.assertEqual(inv["extra_files"][0]["role"], "component-group")
        self.assertEqual(len(inv["extra_files"]), 1)
        (decals / "LICENSE.txt").unlink()
        inv = self.inv()
        self.assertEqual((inv["left_out"], len(inv["extra_files"])), ([], 2))

    def test_no_licence_file_means_no_restriction(self):
        inv = self.inv()
        self.assertEqual(blocking(inv), [])
        self.assertTrue(all(m["licences"] == [] for m in inv["mods"]))

    def test_unrelated_installed_mods_do_not_count(self):
        other = self.m["search"] / "SomeOtherMod"
        other.mkdir()
        (other / "info.json").write_text('{"Id": "SomeOtherMod"}')
        (other / "LICENSE").write_text(STRICT)
        self.assertEqual(blocking(self.inv()), [])

    def test_permissive_terms_are_information_only(self):
        (self.m["mod"] / "README.md").write_text("Licence: free to use. Please do not redistribute.")
        inv = self.inv()
        self.assertEqual(blocking(inv), [])
        self.assertIn("licence-terms", codes(inv))


class GroupsAndImages(Base):
    def add_group(self, name="Herald 1912", texture="Test Loco Mod.herald-1912.png"):
        group = {"identifier": "tt-260-a", "clone": False, "MakeComponentGroup": True, "GroupName": name,
                 "GroupID": "tt-260-a-" + name.replace(" ", ""),
                 "bulkAdds": [{"kind": "CustomImage", "textureName": texture, "name": "Herald", "enabled": True}]}
        (self.m["mod"] / f"TT-{name.replace(' ', '')}.json").write_text(json.dumps(group))

    def test_group_files_note_legoslibraryofstuff_without_blocking(self):
        self.add_group()
        inv = self.inv()
        self.assertEqual(blocking(inv), [])
        self.assertEqual([d["id"] for d in inv["railroader_only"]], ["LegosLibraryOfStuff"])

    def test_group_files_and_their_images_are_found_and_staged(self):
        self.add_group()
        (self.m["mod"] / "images").mkdir()
        (self.m["mod"] / "images" / "Herald-1912.PNG").write_bytes(b"png")
        inv = self.inv()
        self.assertEqual(blocking(inv), [])
        self.assertEqual([g["group_name"] for g in inv["optional_groups"]], ["Herald 1912"])
        self.assertEqual(inv["textures"][0]["file"], {"root": "input", "path": "images/Herald-1912.PNG"})
        self.assertEqual(sorted(r["role"] for r in inv["extra_files"]), ["component-group", "texture"])
        out = convert(self.m["mod"], self.tmp / "out", self.machine, search=[self.m["search"]])
        self.assertEqual(out.code, EXIT_INCOMPLETE, out.message)
        self.assertEqual((out.run.path / "inputs/input/images/Herald-1912.PNG").read_bytes(), b"png")
        self.assertTrue((out.run.path / "inputs/input/TT-Herald1912.json").is_file())

    def test_missing_image_is_a_warning_not_a_block(self):
        self.add_group()
        inv = self.inv()
        self.assertEqual(blocking(inv), [])
        self.assertIn("missing-texture", codes(inv))

    def test_groups_from_other_mods_do_not_apply(self):
        (self.m["search"] / "Addon").mkdir()
        (self.m["search"] / "Addon" / "x.json").write_text(json.dumps({"identifier": "tt-260-a", "bulkAdds": []}))
        self.assertEqual(self.inv()["optional_groups"], [])

    def test_image_found_in_another_mod_by_its_id(self):
        decals = self.m["search"] / "DecalPack"
        (decals / "Logos").mkdir(parents=True)
        (decals / "info.json").write_text('{"Id": "decal-pack"}')
        (decals / "Logos" / "safety.png").write_bytes(b"x")
        self.add_group(texture="decal-pack.safety.png")
        inv = self.inv()
        self.assertEqual(inv["textures"][0]["file"], {"root": "search1", "path": "DecalPack/Logos/safety.png"})
        self.assertEqual([m["id"] for m in inv["mods"]], ["test-loco-mod", "decal-pack"])  # info.json Id wins over folder name


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

    def test_code_mod_component_is_flagged(self):
        comp = {"kind": "ArticulatedSteamEngineComponent", "diamater": 23.5, "stroke": 32.0, "name": "x"}
        write_pack(self.m["mod"] / "ts-260-a",
                   objects=[loco("ts-260-a", tender="tt-260-a", extra_components=[comp]), tender("tt-260-a", truck="test-truck-2s")],
                   assets={"ts-260-a": {"filename": "a.prefab"}, "tt-260-a": {"filename": "t.prefab"}})
        inv = self.inv()
        self.assertEqual([c["provider"] for c in inv["code_mods"]], ["LegosBetterSteam"])
        self.assertIn("code-mod-component", codes(inv))
        # LegosBetterSteam is only needed in Railroader: listed, never opened, never blocking.
        self.assertEqual(blocking(inv), [])
        self.assertEqual([(d["id"], d["installed"]) for d in inv["railroader_only"]], [("LegosBetterSteam", False)])
        self.assertIn("no-modification", inv["railroader_only"][0]["licence_terms"])

    def test_code_mod_with_unknown_licence_does_not_block(self):
        from rr2dv import rrmod
        rrmod.CODE_MOD_KINDS["MadeUpComponent"] = ("MadeUpMod", "test")
        self.addCleanup(rrmod.CODE_MOD_KINDS.pop, "MadeUpComponent")
        write_pack(self.m["mod"] / "ts-260-a",
                   objects=[loco("ts-260-a", tender="tt-260-a", extra_components=[{"kind": "MadeUpComponent"}]),
                            tender("tt-260-a", truck="test-truck-2s")],
                   assets={"ts-260-a": {"filename": "a.prefab"}, "tt-260-a": {"filename": "t.prefab"}})
        inv = self.inv()
        self.assertEqual(blocking(inv), [])
        self.assertEqual(inv["railroader_only"][0]["licence_terms"], None)


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
        out = convert(self.m["mod"], self.tmp / "out", self.machine, search=[self.m["search"]])
        self.assertEqual(out.code, EXIT_FAILED)
        self.assertIn("--audio", out.message)
        out = convert(self.m["mod"], self.tmp / "out", self.machine, search=[self.m["search"]], audio="S282")
        self.assertEqual(out.code, EXIT_INCOMPLETE, out.message)
        self.assertEqual(out.run.record["answers"]["audio"]["basis"], "S282")
        self.assertEqual(read_json(out.run.file)["answers"]["audio"]["rule"], "chosen by the user")


if __name__ == "__main__":
    unittest.main()
