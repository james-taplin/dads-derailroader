import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from fixtures import standard_mod, tool_machine
from rr2dv.jsonio import read_json
from rr2dv.machine import Machine
from rr2dv.pipeline import EXIT_INCOMPLETE, convert
from rr2dv.probeinput import prefab_maps
from rr2dv.unityrun import UnityError


class Probe(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.addCleanup(os.environ.pop, "FAKE_AR_STATE", None)
        self.addCleanup(os.environ.pop, "FAKE_UNITY_MODE", None)
        self.m = standard_mod(self.tmp)
        self.machine = Machine(None, tool_machine(self.tmp))

    def convert(self):
        return convert(self.m["mod"], self.tmp / "out", self.machine, search=[self.m["search"]])

    def test_probe_input_describes_every_vehicle_from_data(self):
        out = self.convert()
        self.assertEqual(out.code, EXIT_INCOMPLETE, out.message)
        project = out.run.path / "unity" / "project"
        data = read_json(project / "Assets/Rr2dv/ProbeInput.json")
        self.assertEqual(data["missing"], [])
        vehicles = {v["id"]: v for v in data["vehicles"]}
        self.assertEqual(sorted(vehicles), ["test-truck-2s", "ts-260-a", "tt-260-a"])
        loco = vehicles["ts-260-a"]
        self.assertEqual(loco["animationMap"][0]["key"], "Drivers")
        self.assertEqual(loco["animationMap"][0]["asset"], "Assets/AnimationClip/Drivers.anim")
        self.assertEqual(loco["materialMap"][0]["asset"], "Assets/Material/ts-260-a_paint.mat")
        self.assertEqual(loco["wheelsets"], [{"clip": "Drivers", "clipAsset": "Assets/AnimationClip/Drivers.anim",
                                              "diameter": 1.2, "offset": 0.0, "length": 2.4, "axles": 3}])
        throttle = next(c for c in loco["components"] if c["purpose"] == "Throttle")
        self.assertEqual((throttle["kind"], throttle["scale"], throttle["rotation"]), ("RadialControl", [1.0, 1.0, 1.0], [0.0, 0.0, 0.0, 1.0]))
        truck = vehicles["test-truck-2s"]
        self.assertTrue(truck["animationMap"][0]["asset"].startswith("Assets/RR/search1/TruckMod/Trucks/"))
        # the probe script itself is in the project, with its hash recorded
        self.assertTrue((project / "Assets/Editor/Rr2dvProbe.cs").is_file())
        self.assertIn("rr2dv/unity/Rr2dvProbe.cs", read_json(out.run.path / "unity/project.json")["app_scripts"])
        stage = out.run.record["stages"]["probe"]
        self.assertEqual(stage["status"], "done")
        self.assertIn("3 vehicle(s) measured; 0 problem(s)", stage["detail"])
        self.assertEqual(read_json(out.run.path / "probe/launch.json")["method"], "Rr2dvProbe.Run")

    def test_licence_flake_is_retried_once(self):
        os.environ["FAKE_UNITY_MODE"] = "flake-once"
        out = self.convert()
        self.assertEqual(out.code, EXIT_INCOMPLETE, out.message)
        self.assertEqual(len(read_json(out.run.path / "probe/launch.json")["attempts"]), 2)

    def test_missing_result_fails_the_run(self):
        os.environ["FAKE_UNITY_MODE"] = "no-result"
        with self.assertRaisesRegex(UnityError, "no result.json"):
            self.convert()
        run = sorted((self.tmp / "work").glob("2*"))[-1]
        self.assertEqual(read_json(run / "run.json")["stages"]["probe"]["status"], "failed")

    def test_compiler_errors_stop_unity_promptly(self):
        import time
        os.environ["FAKE_UNITY_MODE"] = "compile-error"
        started = time.monotonic()
        with self.assertRaisesRegex(UnityError, "did not compile.*error CS0117"):
            self.convert()
        self.assertLess(time.monotonic() - started, 60)

    def test_problems_are_reported_not_hidden(self):
        os.environ["FAKE_UNITY_MODE"] = "problems"
        out = self.convert()
        self.assertEqual(out.code, EXIT_INCOMPLETE, out.message)
        self.assertIn("1 problem(s) to review", out.run.record["stages"]["probe"]["detail"])

    def test_missing_unity_is_reported(self):
        self.machine.values["unity"] = str(self.tmp / "no-unity")
        with self.assertRaisesRegex(FileNotFoundError, "unity"):
            self.convert()


class Maps(unittest.TestCase):
    def test_unresolved_guid_is_listed_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefab = Path(tmp) / "x.prefab"
            prefab.write_text("  clips:\n  - name: Drivers\n    clip: {fileID: 7400000, guid: aaa, type: 2}\n"
                              "  - name: Throttle\n    clip: {fileID: 7400000, guid: bbb, type: 2}\n")
            maps = prefab_maps(prefab, {"aaa": "Assets/A.anim"})
            self.assertEqual([(e["key"], e["asset"]) for e in maps["clip"]], [("Drivers", "Assets/A.anim"), ("Throttle", "")])


if __name__ == "__main__":
    unittest.main()
