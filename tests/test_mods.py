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

    def test_licence_files_are_not_read(self):
        (self.m["mod"] / "LICENSE.txt").write_text(STRICT)
        (self.m["mod"] / "LICENSE.pdf").write_bytes(b"%PDF-1.4")
        inv = self.inv()
        self.assertEqual(blocking(inv), [])
        self.assertFalse([i for i in inv["issues"] if "licen" in i["code"] or "licen" in i["message"].casefold()])
        self.assertTrue(all("licences" not in m for m in inv["mods"]))

    def test_parts_from_other_installed_mods_are_used(self):
        self.parts_mod()
        (self.m["search"] / "PartsMod" / "LICENSE").write_text(STRICT)
        inv = self.inv()
        self.assertEqual(([p["asset"] for p in inv["parts"]], inv["left_out"]), (["bell", "horn"], []))
        self.assertIn("PartsMod", [m["id"] for m in inv["mods"]])

    def test_railroader_game_parts_are_used(self):
        game = self.tmp / "Railroader" / "Railroader_Data" / "StreamingAssets" / "AssetPacks"
        self.parts_mod(where=game / "PartsMod")
        inv = inventory(Index(self.m["mod"], [self.m["search"], game]), "ts-260-a")
        self.assertEqual(blocking(inv), [])
        self.assertEqual([p["asset"] for p in inv["parts"]], ["bell", "horn"])

    def test_trucks_and_tenders_from_other_mods_are_used(self):
        write_pack(self.m["search"] / "TenderMod" / "Tenders", objects=[tender("tt-ext", truck="test-truck-2s")],
                   assets={"tt-ext": {"filename": "tt-ext.prefab"}}, bundle_name="Bundle")
        (self.m["mod"] / "ts-260-a" / "Definitions.json").write_text(json.dumps({"objects": [loco("ts-260-a", tender="tt-ext")]}))
        inv = self.inv()
        self.assertEqual(blocking(inv), [])
        self.assertEqual({v["id"]: v["role"] for v in inv["vehicles"]}, {"ts-260-a": "locomotive", "tt-ext": "tender", "test-truck-2s": "truck"})
        self.assertEqual([p["name"] for p in inv["packs"]], ["ts-260-a", "Tenders", "Trucks"])

    def test_broken_part_is_left_out_never_staged_or_placed(self):
        self.parts_mod(catalogue=False)
        out = convert(self.m["mod"], self.machine, search=[self.m["search"]])
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

    def test_mods_list_names_whose_work_is_used(self):
        (self.m["search"] / "TruckMod" / "info.json").write_text('{"Id": "TruckMod"}')
        inv = self.inv()
        self.assertEqual(sorted(m["id"] for m in inv["mods"]), ["TruckMod", "test-loco-mod"])


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
        out = convert(self.m["mod"], self.machine, search=[self.m["search"]])
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
        out = convert(self.m["mod"], self.machine, search=[self.m["search"]])
        self.assertEqual(out.code, EXIT_FAILED)
        self.assertIn("--audio", out.message)
        out = convert(self.m["mod"], self.machine, search=[self.m["search"]], audio="S282")
        self.assertEqual(out.code, EXIT_INCOMPLETE, out.message)
        self.assertEqual(out.run.record["answers"]["audio"]["basis"], "S282")
        self.assertEqual(read_json(out.run.file)["answers"]["audio"]["rule"], "chosen by the user")


if __name__ == "__main__":
    unittest.main()
