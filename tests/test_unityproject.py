import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

from fixtures import fake_assetripper, fake_carcreator, standard_mod
from rr2dv.jsonio import read_json, sha256_file
from rr2dv.machine import Machine
from rr2dv.pipeline import EXIT_FAILED, EXIT_INCOMPLETE, convert
from rr2dv.safety import UnsafePath
from rr2dv.unityproject import ProjectError, check_guids, import_unitypackage, set_project_settings, tooling_root


@unittest.skipIf(sys.platform == "win32", "fake AssetRipper is a POSIX script")
class Import(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.m = standard_mod(self.tmp)
        os.environ["FAKE_AR_STATE"] = str(self.tmp / "state")
        self.addCleanup(os.environ.pop, "FAKE_AR_STATE", None)
        self.cc = fake_carcreator(self.tmp / "tools" / "CarCreator_3.1.9.unitypackage")
        self.machine = Machine(None, {"workRoot": str(self.tmp / "work"), "assetRipper": str(fake_assetripper(self.tmp / "tools")),
                                      "carCreator": str(self.cc)})

    def convert(self):
        out = convert(self.m["mod"], self.tmp / "out", self.machine, search=[self.m["search"]])
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
        with self.assertRaisesRegex(ProjectError, "resolve_clip_paths"):
            convert(self.m["mod"], self.tmp / "out", self.machine, search=[self.m["search"]])
        record = read_json(sorted((self.tmp / "work").glob("2*"))[-1] / "run.json")
        self.assertEqual((record["status"], record["stages"]["import"]["status"]), ("failed", "failed"))

    def test_missing_carcreator_is_reported(self):
        self.machine.values["carCreator"] = str(self.tmp / "nope.unitypackage")
        with self.assertRaisesRegex(FileNotFoundError, "carCreator"):
            convert(self.m["mod"], self.tmp / "out", self.machine, search=[self.m["search"]])


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


if __name__ == "__main__":
    unittest.main()
