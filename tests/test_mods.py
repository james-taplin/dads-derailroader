"""Mod-level behaviour: licences, optional component groups, images, code-mod components, audio."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fixtures import loco, standard_mod, tender, tree_state, write_pack
from rr2dv.jsonio import read_json, sha256_file
from rr2dv.machine import Machine
from rr2dv.pipeline import EXIT_FAILED, EXIT_INCOMPLETE, convert
from rr2dv.rrmod import Index, audio_basis, blocking, inventory, read_licence_terms

STRICT = "You may not open, decompile, reverse engineer, or modify any part of the Mod. No redistribution. Personal use only."


def codes(inv):
    return sorted(i["code"] for i in inv["issues"])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.m = standard_mod(self.tmp)
        self.machine = Machine(None, {"workRoot": str(self.tmp / "work")})

    def inv(self, **kw):
        return inventory(Index(self.m["mod"], [self.m["search"]]), "ts-260-a", **kw)


class Licences(Base):
    def test_terms(self):
        p = self.tmp / "LICENSE"
        p.write_text(STRICT)
        self.assertEqual(read_licence_terms(p), ["no-reverse-engineering", "no-modification", "no-redistribution", "personal-use-only"])
        p.write_text("MIT License. Permission is hereby granted, free of charge...")
        self.assertEqual(read_licence_terms(p), [])

    def test_restrictive_licence_blocks_until_that_exact_file_is_accepted(self):
        (self.m["mod"] / "LICENSE.txt").write_text(STRICT)
        before = tree_state(self.tmp / "input")
        out = convert(self.m["mod"], self.tmp / "out", self.machine, search=[self.m["search"]])
        self.assertEqual(out.code, EXIT_FAILED)
        self.assertIn("--accept-licence", out.message)
        sha = sha256_file(self.m["mod"] / "LICENSE.txt")
        self.assertEqual(convert(self.m["mod"], self.tmp / "out", self.machine, search=[self.m["search"]],
                                 accept_licences=["0" * 16]).code, EXIT_FAILED)
        ok = convert(self.m["mod"], self.tmp / "out", self.machine, search=[self.m["search"]], accept_licences=[sha[:16]])
        self.assertEqual(ok.code, EXIT_INCOMPLETE, ok.message)
        self.assertEqual(ok.run.record["answers"]["accepted_licences"][0]["sha256"], sha)
        self.assertEqual(tree_state(self.tmp / "input"), before)

    def test_licence_of_a_mod_we_only_depend_on_through_its_bundle_counts(self):
        (self.m["search"] / "TruckMod" / "info.json").write_text('{"Id": "TruckMod"}')
        (self.m["search"] / "TruckMod" / "LICENSE").write_text(STRICT)
        inv = self.inv()
        self.assertEqual([i["data"]["mod"] for i in blocking(inv)], ["TruckMod"])

    def test_code_mod_licence_is_irrelevant_when_no_file_of_it_is_used(self):
        code_mod = self.m["search"] / "SomeCodeMod"
        code_mod.mkdir()
        (code_mod / "info.json").write_text('{"Id": "SomeCodeMod"}')
        (code_mod / "LICENSE").write_text(STRICT)
        self.assertEqual(blocking(self.inv()), [])

    def test_permissive_terms_are_information_only(self):
        (self.m["mod"] / "README.md").write_text("Free to use. Please do not redistribute.")
        inv = self.inv()
        self.assertEqual(blocking(inv), [])
        self.assertIn("licence-terms", codes(inv))


class GroupsAndImages(Base):
    def add_group(self, name="Herald 1912", texture="Test Loco Mod.herald-1912.png"):
        group = {"identifier": "tt-260-a", "clone": False, "MakeComponentGroup": True, "GroupName": name,
                 "GroupID": "tt-260-a-" + name.replace(" ", ""),
                 "bulkAdds": [{"kind": "CustomImage", "textureName": texture, "name": "Herald", "enabled": True}]}
        (self.m["mod"] / f"TT-{name.replace(' ', '')}.json").write_text(json.dumps(group))

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
        self.assertEqual(blocking(inv), [])


class Audio(Base):
    def test_boiler_size_rule(self):
        self.assertEqual(audio_basis({"totalHeatingSurface": 1735})["basis"], "S060")
        self.assertEqual(audio_basis({"totalHeatingSurface": 2000})["basis"], "S282")
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
