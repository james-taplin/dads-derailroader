import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

from fixtures import fake_assetripper, fake_carcreator, fake_unity, standard_mod
from rr2dv.jsonio import read_json, sha256_file
from rr2dv.machine import Machine
from rr2dv.pipeline import EXIT_FAILED, EXIT_INCOMPLETE, convert
from rr2dv.safety import UnsafePath
from rr2dv.unityproject import ProjectError, check_guids, import_unitypackage, resolve_clips, set_project_settings, tooling_root


class Import(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.m = standard_mod(self.tmp)
        os.environ["FAKE_AR_STATE"] = str(self.tmp / "state")
        self.addCleanup(os.environ.pop, "FAKE_AR_STATE", None)
        self.cc = fake_carcreator(self.tmp / "tools" / "CarCreator_3.1.9.unitypackage")
        self.machine = Machine(None, {**self.m["games"], "keepWorkFiles": True, "workRoot": str(self.tmp / "work"), "assetRipper": str(fake_assetripper(self.tmp / "tools")),
                                      "carCreator": str(self.cc), "unity": str(fake_unity(self.tmp / "tools"))})

    def convert(self):
        out = convert(self.m["mod"], self.machine)
        self.assertEqual(out.code, EXIT_INCOMPLETE, out.message)
        return out.run.path, out.run.path / "unity" / "project"

    def test_project_is_assembled_from_the_exports(self):
        run, project = self.convert()
        info = read_json(run / "unity" / "project.json")
        assets = project / "Assets"
        # main pack: loco + tender prefabs in place, clip placeholder restored to the real path
        self.assertEqual({v["role"]: v["unity_prefab"] for v in info["vehicles"]}, {
            "locomotive": "Assets/PrefabInstance/ts-260-a.prefab",
            "tender": "Assets/PrefabInstance/tt-260-a.prefab",
            "truck": "Assets/RR/search1/TruckMod/Trucks/PrefabInstance/Test-Truck-2s.prefab"})
        self.assertIn("path: Wheel", (assets / "AnimationClip" / "Drivers.anim").read_text())
        truck_clips = info["clips"]["RR/search1/TruckMod/Trucks"]
        self.assertEqual((truck_clips["clips"], truck_clips["selected"]), (1, 2))  # the truck prefab and its clip only
        self.assertNotIn("path_0x", (assets / "RR/search1/TruckMod/Trucks/AnimationClip/Drivers.anim").read_text())
        # part copied with its material dependency and GUIDs intact
        part = info["parts"][0]
        self.assertEqual(part["unity_prefab"], "Assets/RR/input/parts/PrefabInstance/bell.prefab")
        self.assertTrue((assets / "RR/input/parts/Material/bell_paint.mat.meta").is_file())
        # project settings as our G-29 setup made them
        self.assertIn("m_EditorVersion: 2019.4.40f1", (project / "ProjectSettings/ProjectVersion.txt").read_text())
        self.assertIn("m_AssetPipelineMode: 1", (project / "ProjectSettings/EditorSettings.asset").read_text())
        deps = read_json(project / "Packages/manifest.json")["dependencies"]
        self.assertEqual(deps, {"com.unity.modules.physics": "1.0.0", "com.unity.textmeshpro": "2.1.6", "com.unity.ugui": "1.0.0"})
        # CarCreator and the shared core
        self.assertEqual((assets / "CarCreator/CCL.Types.dll").read_bytes(), b"dll")
        self.assertEqual(info["car_creator"]["sha256"], sha256_file(self.cc))
        core = tooling_root() / "builder/tools/unity"
        for script in core.glob("*.cs"):
            self.assertEqual(sha256_file(assets / "Editor" / script.name), sha256_file(script))
        self.assertIn("builder/tools/unity/LlwVehicleRecord.cs", info["core_scripts"])
        self.assertGreater(info["unique_guids"], 5)

    def test_source_code_is_kept_out_of_the_project(self):
        run, project = self.convert()
        assets = project / "Assets"
        leftovers = [p.relative_to(assets).as_posix() for p in assets.rglob("*")
                     if p.suffix in (".cs", ".dll", ".asmdef") and not p.relative_to(assets).as_posix().startswith(("Editor/", "CarCreator/"))]
        self.assertEqual(leftovers, [])
        excluded = read_json(run / "unity" / "project.json")["excluded_source_code"]
        self.assertIn("Assets/Plugins/RR.Runtime.dll", excluded)
        self.assertIn("Assets/Scripts/Assembly-CSharp/AnimationMap.cs", excluded)
        self.assertIn("RR/input/parts/Plugins/RR.Runtime.dll", excluded)  # followed by copy_deps, then dropped
        self.assertFalse((assets / "Plugins/RR.Runtime.dll.meta").exists())
        cache = self.tmp / "work" / "_cache" / "assetripper"
        self.assertTrue(list(cache.rglob("RR.Runtime.dll")))  # cached export untouched

    def test_cached_exports_are_not_modified(self):
        self.convert()
        cache = self.tmp / "work" / "_cache" / "assetripper"
        anims = list(cache.rglob("Drivers.anim"))
        self.assertTrue(anims)
        self.assertTrue(all("path_0x" in a.read_text() for a in anims))

    def test_unresolvable_clip_stops_the_import(self):
        self.convert()  # fills the export cache
        cache = self.tmp / "work" / "_cache" / "assetripper"
        for anim in cache.rglob("Drivers.anim"):
            anim.write_text("AnimationClip:\n  - path: path_0xdeadbeef_x\n")
        # both the loco's and the tender's clip maps name Drivers, so the absent-binding rule does not apply (X39)
        with self.assertRaisesRegex(ProjectError, "resolve_clip_paths.*ts-260-a.prefab, PrefabInstance/tt-260-a.prefab name it.*clips-main-diagnosis.json"):
            convert(self.m["mod"], self.machine)
        run = sorted((self.tmp / "work").glob("2*"))[-1]
        diagnosis = read_json(run / "import" / "clips-main-diagnosis.json")["clips"]["AnimationClip/Drivers.anim"]
        self.assertEqual(diagnosis["bindings"], 1)
        self.assertEqual(diagnosis["unresolved_in_best"], [{"hash": "0xdeadbeef", "found_in": []}])
        self.assertEqual([o["prefab"] for o in diagnosis["named_by"]][:1], ["PrefabInstance/ts-260-a.prefab"])
        record = read_json(sorted((self.tmp / "work").glob("2*"))[-1] / "run.json")
        self.assertEqual((record["status"], record["stages"]["import"]["status"]), ("failed", "failed"))

    def test_missing_carcreator_is_reported(self):
        self.machine.values["carCreator"] = str(self.tmp / "nope.unitypackage")
        with self.assertRaisesRegex(FileNotFoundError, "carCreator"):
            convert(self.m["mod"], self.machine)


class Pieces(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def package(self, pathname, data=b"x"):
        path = self.tmp / "p.unitypackage"
        with tarfile.open(path, "w:gz") as tar:
            for leaf, blob in (("pathname", pathname.encode()), ("asset", data)):
                info = tarfile.TarInfo(f"g1/{leaf}")
                info.size = len(blob)
                tar.addfile(info, io.BytesIO(blob))
        return path

    def test_unitypackage_paths_are_confined(self):
        project = self.tmp / "project"
        project.mkdir()
        for bad in ("../evil.txt", "/abs.txt", "Assets/../../evil.txt", "Library/x.txt", "Assets/CON.txt"):
            with self.subTest(bad=bad), self.assertRaises(UnsafePath):
                import_unitypackage(self.package(bad), project)
        self.assertFalse((self.tmp / "evil.txt").exists())
        self.assertEqual(import_unitypackage(self.package("Assets/ok.txt"), project), 1)
        with self.assertRaises(ProjectError):  # never overwrite
            import_unitypackage(self.package("Assets/ok.txt"), project)

    def test_duplicate_guids_are_rejected(self):
        assets = self.tmp / "Assets"
        (assets / "a").mkdir(parents=True)
        (assets / "a" / "x.mat.meta").write_text("guid: abc\n")
        (assets / "y.mat.meta").write_text("guid: abc\n")
        with self.assertRaisesRegex(ProjectError, "duplicate GUID abc"):
            check_guids(assets)

    def test_asset_pipeline_mode_is_normalised(self):
        project = self.tmp / "p"
        settings = project / "ProjectSettings"
        settings.mkdir(parents=True)
        cases = {"EditorSettings:\n  m_SerializationMode: 2\n  m_AssetPipelineMode: 0\n": 1,
                 "EditorSettings:\n  m_SerializationMode: 2\n  m_AssetPipelineMode: 1\n": 1,
                 "EditorSettings:\n  m_SerializationMode: 2\n": 1,
                 None: 1}
        for text in cases:
            with self.subTest(text=text):
                target = settings / "EditorSettings.asset"
                target.unlink(missing_ok=True)
                if text is not None:
                    target.write_text(text)
                set_project_settings(project)
                out = target.read_text()
                self.assertEqual(out.count("m_AssetPipelineMode"), 1)
                self.assertIn("m_AssetPipelineMode: 1", out)
                self.assertIn("m_SerializationMode: 2", out)
        (settings / "EditorSettings.asset").write_text("Something: else\n")
        with self.assertRaises(ProjectError):
            set_project_settings(project)

    def test_settings_without_a_manifest(self):
        project = self.tmp / "p"
        project.mkdir()
        set_project_settings(project)
        self.assertEqual(read_json(project / "Packages/manifest.json")["dependencies"],
                         {"com.unity.textmeshpro": "2.1.6", "com.unity.ugui": "1.0.0"})


def _prefab(root: str, child: str, clips: dict) -> str:
    """Prefab YAML: root / child / Hatch, with a Railroader-style clip map."""
    text = "%YAML 1.1\n"
    fid = 100
    parent = "0"
    for name in (root, child, "Hatch"):
        text += (f"--- !u!1 &{fid}\nGameObject:\n  m_Name: {name}\n--- !u!4 &{fid + 1}\nTransform:\n"
                 f"  m_GameObject: {{fileID: {fid}}}\n  m_Father: {{fileID: {parent}}}\n")
        parent, fid = str(fid + 1), fid + 100
    text += "--- !u!114 &900\nMonoBehaviour:\n  clips:\n"
    for key, g in clips.items():
        text += f"  - name: {key}\n    clip: {{fileID: 7400000, guid: {g}, type: 2}}\n"
    return text


class TiedClips(unittest.TestCase):
    """A clip whose paths fit two prefabs differently is bound to the prefab whose own clip map names it (X30)."""

    def setUp(self):
        import zlib
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.src = self.tmp / "src"
        (self.src / "PrefabInstance").mkdir(parents=True)
        (self.src / "AnimationClip").mkdir()
        (self.src / "PrefabInstance" / "loco.prefab").write_text(_prefab("loco", "Cab", {"Drivers": "a1"}))
        (self.src / "PrefabInstance" / "tender.prefab").write_text(_prefab("tender", "Body", {"Hatch": "b1"}))
        self.clip = "AnimationClip:\n  m_FloatCurves:\n  - path: path_0x%x_hatch\n" % zlib.crc32(b"Hatch")
        (self.src / "AnimationClip" / "Hatch.anim").write_text(self.clip)
        (self.src / "AnimationClip" / "Hatch.anim.meta").write_text("guid: b1\n")

    def test_tied_clip_is_bound_to_its_owner(self):
        dest = self.tmp / "dest"
        out = resolve_clips(self.src, dest, self.tmp / "reports" / "clips-main.json")
        self.assertEqual((out["clips"], out["bound"]), (1, 1))
        self.assertIn("path: Body/Hatch", (dest / "AnimationClip" / "Hatch.anim").read_text())
        evidence = read_json(self.tmp / "reports" / "clips-main-bindings.json")["clips"]
        self.assertEqual(evidence, {"AnimationClip/Hatch.anim": {"decision": "bound", "by": "clip map", "prefab": "PrefabInstance/tender.prefab",
                                                                 "owners": [{"prefab": "PrefabInstance/tender.prefab", "key": "Hatch"}]}})

    def add_unowned_twin(self):
        (self.src / "AnimationClip" / "Hatch_0.anim").write_text(self.clip)
        (self.src / "AnimationClip" / "Hatch_0.anim.meta").write_text("guid: c1\n")

    def test_unowned_clip_nothing_references_is_left_out(self):
        # X33 (C21): four *_0/box clips fit loco and tender and no clip map names them.
        self.add_unowned_twin()
        dest = self.tmp / "dest"
        shutil.copytree(self.src, dest)  # the project starts as a copy of the export
        out = resolve_clips(self.src, dest, self.tmp / "reports" / "clips-main.json")
        self.assertEqual((out["bound"], out["left_out"]), (1, ["AnimationClip/Hatch_0.anim"]))
        self.assertIn("path: Body/Hatch", (dest / "AnimationClip" / "Hatch.anim").read_text())
        self.assertFalse((dest / "AnimationClip" / "Hatch_0.anim").exists())
        self.assertFalse((dest / "AnimationClip" / "Hatch_0.anim.meta").exists())
        self.assertTrue((self.src / "AnimationClip" / "Hatch_0.anim").exists(), "the export is never changed")
        decision = read_json(self.tmp / "reports" / "clips-main-bindings.json")["clips"]["AnimationClip/Hatch_0.anim"]
        self.assertEqual((decision["decision"], decision["references"]), ("left out", []))
        self.assertFalse((self.tmp / "reports" / "clips-main-resolver-input").exists())

    def test_unowned_clip_one_prefab_references_is_bound_to_it(self):
        self.add_unowned_twin()
        loco = self.src / "PrefabInstance" / "loco.prefab"
        loco.write_text(loco.read_text() + "--- !u!111 &950\nAnimation:\n  m_Animations:\n  - {fileID: 7400000, guid: c1, type: 2}\n")
        dest = self.tmp / "dest"
        out = resolve_clips(self.src, dest, self.tmp / "reports" / "clips-main.json")
        self.assertEqual((out["bound"], out["left_out"]), (2, []))
        self.assertIn("path: Cab/Hatch", (dest / "AnimationClip" / "Hatch_0.anim").read_text())
        decision = read_json(self.tmp / "reports" / "clips-main-bindings.json")["clips"]["AnimationClip/Hatch_0.anim"]
        self.assertEqual((decision["by"], decision["references"]), ("serialized reference", ["PrefabInstance/loco.prefab"]))

    def test_unowned_clip_referenced_elsewhere_stays_an_error_with_evidence(self):
        self.add_unowned_twin()
        (self.src / "AnimatorController").mkdir()
        (self.src / "AnimatorController" / "Tender.controller").write_text("%YAML 1.1\nAnimatorState:\n  m_Motion: {fileID: 7400000, guid: c1, type: 2}\n")
        dest = self.tmp / "dest"
        with self.assertRaisesRegex(ProjectError, "Hatch_0.anim: referenced by AnimatorController/Tender.controller"):
            resolve_clips(self.src, dest, self.tmp / "reports" / "clips-main.json")
        self.assertFalse(dest.exists(), "nothing is written unless every clip resolves")
        decisions = read_json(self.tmp / "reports" / "clips-main-bindings.json")["clips"]
        self.assertEqual((decisions["AnimationClip/Hatch.anim"]["decision"], decisions["AnimationClip/Hatch_0.anim"]["decision"]),
                         ("bound", "error"))

    def test_shared_clip_resolves_against_the_one_prefab_we_use(self):
        # X35: every Fox truck variant names the same Brakes clip; the C21 tender uses one of them.
        (self.src / "PrefabInstance" / "loco.prefab").write_text(_prefab("loco", "Cab", {"Hatch": "b1"}))
        with self.assertRaisesRegex(ProjectError, "name it"):
            resolve_clips(self.src, self.tmp / "all", self.tmp / "reports" / "clips-all.json")
        dest = self.tmp / "dest"
        out = resolve_clips(self.src, dest, self.tmp / "reports" / "clips-truck.json",
                            only={"PrefabInstance/tender.prefab", "AnimationClip/Hatch.anim"})
        self.assertEqual((out["clips"], out["selected"]), (1, 2))
        self.assertIn("path: Body/Hatch", (dest / "AnimationClip" / "Hatch.anim").read_text())
        self.assertFalse((self.tmp / "reports" / "clips-truck-selected").exists())
        self.assertTrue((self.src / "PrefabInstance" / "loco.prefab").is_file(), "the export is never changed")

    def test_two_used_prefabs_needing_different_paths_stay_an_error(self):
        (self.src / "PrefabInstance" / "loco.prefab").write_text(_prefab("loco", "Cab", {"Hatch": "b1"}))
        with self.assertRaisesRegex(ProjectError, "name it"):
            resolve_clips(self.src, self.tmp / "dest", self.tmp / "reports" / "clips-truck.json",
                          only={"PrefabInstance/tender.prefab", "PrefabInstance/loco.prefab", "AnimationClip/Hatch.anim"})

    def test_clip_named_by_two_prefabs_stays_an_error(self):
        (self.src / "PrefabInstance" / "loco.prefab").write_text(_prefab("loco", "Cab", {"Hatch": "b1"}))
        with self.assertRaisesRegex(ProjectError, "loco.prefab, PrefabInstance/tender.prefab name it"):
            resolve_clips(self.src, self.tmp / "dest", self.tmp / "reports" / "clips-main.json")



class AbsentBindings(unittest.TestCase):
    """X39 (GN A-18): a clip whose clip map owner has most of its targets and whose other targets are in no prefab of
    the export is kept; the absent bindings keep their placeholder and are listed. Anything else stays an error."""

    def setUp(self):
        import zlib
        self.crc = lambda path: "0x%x" % zlib.crc32(path.encode())
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.src = self.tmp / "src"
        (self.src / "PrefabInstance").mkdir(parents=True)
        (self.src / "AnimationClip").mkdir()
        (self.src / "PrefabInstance" / "loco.prefab").write_text(_prefab("loco", "Cab", {"Whistle": "w1"}))
        (self.src / "PrefabInstance" / "tender.prefab").write_text(_prefab("tender", "Body", {}))
        (self.src / "AnimationClip" / "Whistle.anim.meta").write_text("guid: w1\n")

    def clip(self, *paths):
        text = "AnimationClip:\n  m_FloatCurves:\n" + "".join(f"  - path: path_{self.crc(p)}_x\n" for p in paths)
        (self.src / "AnimationClip" / "Whistle.anim").write_text(text)
        return text

    def resolve(self, **kw):
        return resolve_clips(self.src, self.tmp / "dest", self.tmp / "reports" / "clips-main.json", **kw)

    def test_absent_targets_are_kept_and_listed(self):
        self.clip("Cab/Hatch", "Cab/Gone")
        out = self.resolve()
        self.assertEqual(out["absent_bindings"], [{"clip": "AnimationClip/Whistle.anim", "prefab": "PrefabInstance/loco.prefab",
                                                   "keys": ["Whistle"], "bindings": 2, "restored": 1, "absent": [self.crc("Cab/Gone")]}])
        text = (self.tmp / "dest" / "AnimationClip" / "Whistle.anim").read_text()
        self.assertIn("path: Cab/Hatch\n", text)
        self.assertIn(f"path: path_{self.crc('Cab/Gone')}_x", text)
        decision = read_json(self.tmp / "reports" / "clips-main-bindings.json")["clips"]["AnimationClip/Whistle.anim"]
        self.assertEqual((decision["decision"], decision["restored"]), ("kept, absent bindings unresolved", 1))

    def test_clip_with_no_target_in_the_model_is_kept_unchanged(self):
        text = self.clip("Cab/Gone")
        out = self.resolve()
        self.assertEqual((out["absent_bindings"][0]["restored"], out["clips"]), (0, 1))
        self.assertEqual((self.tmp / "dest" / "AnimationClip" / "Whistle.anim").read_text(), text)

    def test_targets_in_another_prefab_stay_an_error(self):
        self.clip("Cab/Hatch", "Body")
        with self.assertRaisesRegex(ProjectError, "lacks targets that other prefabs have .*tender.prefab.*clips-main-diagnosis.json"):
            self.resolve()
        self.assertFalse((self.tmp / "dest").exists(), "nothing is written unless every clip is decided")

    def test_targets_in_a_prefab_we_do_not_use_still_count(self):
        # a dependency pack is resolved against the prefabs we use, but "absent" means absent from its whole export
        self.clip("Cab/Hatch", "Body")
        with self.assertRaisesRegex(ProjectError, "lacks targets that other prefabs have"):
            self.resolve(only={"PrefabInstance/loco.prefab", "AnimationClip/Whistle.anim"})

    def test_clip_no_map_names_stays_an_error(self):
        (self.src / "PrefabInstance" / "loco.prefab").write_text(_prefab("loco", "Cab", {}))
        (self.src / "PrefabInstance" / "loco.prefab").write_text(
            (self.src / "PrefabInstance" / "loco.prefab").read_text() + "  - {fileID: 7400000, guid: w1, type: 2}\n")
        self.clip("Cab/Hatch", "Cab/Gone")
        with self.assertRaisesRegex(ProjectError, "no prefab's clip map names it"):
            self.resolve()


class UnusedTextures(unittest.TestCase):
    def test_only_textures_the_prefabs_reach_are_kept(self):
        # PLW Trojan shape: a texture set per skin in one export; the converted prefab's material uses one of them
        from rr2dv.unityproject import referenced_files
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        guid = lambda n: f"{n:032x}"
        def asset(rel, n, body=None):
            path = tmp / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body if body is not None else b"\x89PNG")
            (tmp / (rel + ".meta")).write_text(f"fileFormatVersion: 2\nguid: {guid(n)}\n")
            return path
        prefab = asset("PrefabInstance/loco.prefab", 1, f"%YAML 1.1\n  m_Materials:\n  - {{fileID: 2100000, guid: {guid(2)}, type: 2}}\n".encode())
        asset("Material/red.mat", 2, f"%YAML 1.1\n  m_Texture: {{fileID: 2800000, guid: {guid(3)}, type: 3}}\n".encode())
        red = asset("Texture2D/3GWR 1340 Red_BumpMap.png", 3)
        asset("Material/copper.mat", 4, f"%YAML 1.1\n  m_Texture: {{fileID: 2800000, guid: {guid(5)}, type: 3}}\n".encode())
        copper = asset("Texture2D/4GWR 1340 Copper_Occlusion.png", 5)
        used = referenced_files(tmp, [prefab])
        self.assertIn(red, used)
        self.assertNotIn(copper, used)
        self.assertIsNone(referenced_files(tmp, [tmp / "missing.prefab"]))  # a missing root prunes nothing


if __name__ == "__main__":
    unittest.main()


class NoClipsInExport(unittest.TestCase):
    def test_an_export_with_no_animation_clips_resolves_to_nothing(self):
        import tempfile
        from rr2dv import unityproject
        with tempfile.TemporaryDirectory() as tmp:
            src, dest = Path(tmp) / "src", Path(tmp) / "dest"
            (src / "Truck").mkdir(parents=True)
            (src / "Truck" / "truck.prefab").write_text("%YAML 1.1\n")
            out = unityproject.resolve_clips(src, dest, Path(tmp) / "clips-truck.json")
            self.assertEqual(out["clips"], 0)
            self.assertEqual(out["absent_bindings"], [])
