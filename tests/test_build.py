import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from fixtures import loco, part, standard_mod, tender, tool_machine, tree_state
from rr2dv import buildrecord, recordcheck
from rr2dv.jsonio import read_json
from rr2dv.machine import Machine
from rr2dv.pipeline import EXIT_FAILED, EXIT_INCOMPLETE, EXIT_OK, convert


class BuildStages(unittest.TestCase):
    """build -> audit -> publish with the fake Unity (tests/fixtures.py): data flow and stops, not Unity itself."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        for var in ("FAKE_AR_STATE", "FAKE_UNITY_MODE"):
            self.addCleanup(os.environ.pop, var, None)
        self.m = standard_mod(self.tmp)
        self.machine = Machine(None, tool_machine(self.tmp))
        self.asked = []

    def convert(self, agree=True, **kw):
        def ask(pack, sources):
            self.asked.append((pack, sources))
            return agree
        return convert(self.m["mod"], self.machine, search=[self.m["search"]], ask=ask, **kw)

    def test_reviewed_radius_builds_audits_and_installs_after_the_notice(self):
        rr_before = tree_state(Path(self.machine.values["railroader"]))
        out = self.convert(wheel_radius=0.598)
        self.assertEqual(out.code, EXIT_OK, out.message)
        run = out.run
        self.assertEqual([s["status"] for s in run.record["stages"].values()], ["done"] * 10)
        rec = read_json(run.path / "build/vehicle-record.json")
        self.assertEqual(recordcheck.check(rec), [])
        cfg = buildrecord._plain(rec["config"])
        self.assertEqual(cfg["WheelRadius"], 0.598)
        # 2-6-0 style fixture (3 drivers, no pony): front bogie on driver 1, rear bogie on drivers 2-3, pivots at the ends
        self.assertEqual([(b["Axles"], b["PivotAxle"]) for b in cfg["Bogies"]], [([1.2], 0), ([0.0, -1.2], 1)])
        self.assertEqual(cfg["EngineUnits"][0]["DriverParts"], ["Main/Drivers1", "Main/Drivers2", "Main/Drivers3"])
        self.assertEqual((cfg["ChimneyComp"], cfg["WhistleComp"], cfg["CabSeatComp"]), ("Chuff", "Whistle", "Engineer Seat"))
        self.assertAlmostEqual(cfg["BackheadZ"], -1.8)  # fake cab rays: plate 0.5 m ahead of the seats at z -2.3
        ports = {p["Port"] for p in cfg["Placed"]}
        for port in ("throttle.EXT_IN", "injector.EXT_IN", "blower.EXT_IN", "fireboxDoor.EXT_IN", "cabLight.EXT_IN"):
            self.assertIn(port, ports)
        cocks = next(c for c in cfg["Components"] if c["kind"] == "CylinderCock")
        self.assertEqual(cocks["pos"][0], 1.1)  # RR spawns the drain jets at +-radius
        self.assertEqual(cfg["SrcPrefab"], "Assets/RR2DV/RR2DV_TS_260_A/source/ts-260-a.prefab")  # the model with its bell part
        t = buildrecord._plain(rec["tender"]["config"])
        self.assertEqual([b["Axles"] for b in t["Bogies"]], [[2.84, 1.16], [-1.16, -2.84]])
        self.assertEqual((t["Trucks"][0]["Wheelset"], t["WheelRadius"]), ("Wheel", 0.42))
        # Rr2dvBuild's input: the part is placed, every prefab loses its AudioSources
        inp = read_json(run.path / "unity/project/Assets/Rr2dv/BuildInput.json")
        self.assertEqual([p["name"] for p in inp["composites"][0]["parts"]], ["bell1"])
        self.assertTrue(inp["audioStrip"])
        env = read_json(run.path / "build/out/record_seen.json")["env"]
        self.assertEqual(env, {"CCL_SHARE": "1", "CCL_NEW_LOCO": "0", "CCL_CATALOG_RECORD": ""})
        # the audit asked Unity for the driving controls and the HUD's controls
        audit_in = read_json(run.path / "audit/audit.json")["input"]
        self.assertIn("whistle.EXT_IN", audit_in["ports"])
        self.assertIn("injector", audit_in["controls"])
        # installed after the notice, with the audited files, NOTICE, provenance and marker
        self.assertEqual(len(self.asked), 1)
        dest = self.m["dv_mods"] / cfg["CarName"]
        self.assertEqual(sorted(p.name for p in dest.iterdir()),
                         ["Info.json", "NOTICE.txt", "SOURCE_PROVENANCE.txt", "ccl_bundle", "rr2dv.json"])
        self.assertIn("candidate", out.message)
        review = read_json(run.path / "build/review.json")
        self.assertTrue(any("G-29's joint physics" in c or "generated backhead controls" in c for c in review["choices"]))
        self.assertEqual(tree_state(Path(self.machine.values["railroader"])), rr_before)

    def test_declined_notice_installs_nothing(self):
        out = self.convert(agree=False, wheel_radius=0.598)
        self.assertEqual(out.code, EXIT_INCOMPLETE, out.message)
        self.assertEqual(out.run.record["stages"]["publish"]["status"], "not_installed")
        self.assertEqual(sorted(p.name for p in self.m["dv_mods"].iterdir()), ["DVCustomCarLoader"])

    def test_without_the_radius_it_asks_and_offers_the_candidate(self):
        out = self.convert()
        self.assertEqual(out.code, EXIT_INCOMPLETE, out.message)
        self.assertEqual(out.run.record["stages"]["build"]["status"], "needs_answer")
        block = read_json(out.run.path / "build/blocks.json")[0]
        self.assertEqual(block["code"], "needs-wheel-radius")
        self.assertAlmostEqual(block["candidate"], 0.5988)
        self.assertEqual(self.asked, [])

    def test_a_failed_build_says_why(self):
        os.environ["FAKE_UNITY_MODE"] = "build-fails"
        out = self.convert(wheel_radius=0.598)
        self.assertEqual(out.code, EXIT_FAILED)
        self.assertIn("insufficient end-beam rays", out.message)
        self.assertEqual(out.run.record["stages"]["build"]["status"], "failed")
        self.assertEqual(self.asked, [])

    def test_audio_in_the_bundle_stops_before_installing(self):
        os.environ["FAKE_UNITY_MODE"] = "build-audio"
        out = self.convert(wheel_radius=0.598)
        self.assertEqual(out.code, EXIT_FAILED)
        self.assertIn("AudioClip", out.message)
        self.assertEqual(self.asked, [])
        self.assertEqual(sorted(p.name for p in self.m["dv_mods"].iterdir()), ["DVCustomCarLoader"])

    def test_missing_anchor_is_a_block_with_its_reason(self):
        defs = self.m["mod"] / "ts-260-a" / "Definitions.json"
        data = json.loads(defs.read_text().replace(",\n  ],\n}", "\n  ]\n}"))
        comps = data["objects"][0]["definition"]["components"]
        data["objects"][0]["definition"]["components"] = [c for c in comps if c.get("kind") != "Chuff"]
        defs.write_text(json.dumps(data))
        out = self.convert(wheel_radius=0.598)
        self.assertEqual(out.code, EXIT_FAILED)
        self.assertIn("no Chuff (chimney) component", out.message)
        self.assertEqual(read_json(out.run.path / "build/blocks.json")[0]["code"], "missing-anchor")


class Rules(unittest.TestCase):
    def test_rr_axles_are_evenly_spaced_about_the_offset(self):
        self.assertEqual(buildrecord.rr_axles({"offset": 0, "length": 4.1, "axles": 3}), [2.05, 0.0, -2.05])
        self.assertEqual(buildrecord.rr_axles({"offset": 4.38, "length": 0, "axles": 1}), [4.38])

    def test_measured_axles_ignore_other_rotating_parts(self):
        ws = {"offset": 0, "length": 4.7, "axles": 4}
        nodes = {f"D{i}": [0, 0.5, z] for i, z in enumerate([2.35, 0.7833, -0.7833, -2.35])}
        nodes["Link"] = [0.9, 1.0, -0.2]  # C-21's expansion link: rotating, round, but not at an axle
        wheel = {"rotatingPaths": sorted(nodes), "meshes": [{"path": p + "/m", "used": True} for p in sorted(nodes)]}
        axles = buildrecord.measured_axles(ws, wheel, nodes)
        self.assertEqual([a["part"] for a in axles], ["D0", "D1", "D2", "D3"])
        self.assertTrue(all(a["basis"] == "measured" for a in axles))

    def test_backhead_is_the_most_common_cab_facing_band(self):
        rays = [{"x": x / 10, "y": 2.0, "hit": True, "z": -3.15, "normalZ": -1} for x in range(-7, 8)]
        rays += [{"x": 0.9, "y": 2.0, "hit": True, "z": -2.9, "normalZ": -1}, {"x": 1, "y": 2, "hit": False}]
        self.assertAlmostEqual(buildrecord.backhead(rays)["z"], -3.15)
        self.assertIsNone(buildrecord.backhead(rays[:5]))

    def test_control_positions_keep_clear_of_the_door_and_each_other(self):
        pts = [(x / 10, y / 10) for x in range(-8, 9) for y in range(10, 31)]
        spots = buildrecord.control_positions(pts, (0.0, 1.5), [], 13)
        self.assertEqual(len(spots), 13)
        for i, (x, y) in enumerate(spots):
            self.assertGreaterEqual(((x - 0.0) ** 2 + (y - 1.5) ** 2) ** 0.5, 0.3 - 1e-9)
            for (a, b) in spots[i + 1:]:
                self.assertTrue(abs(x - a) >= 0.2 - 1e-6 or abs(y - b) >= 0.25 - 1e-6)
        self.assertEqual(spots, buildrecord.control_positions(list(reversed(pts)), (0.0, 1.5), [], 13))  # deterministic

    def test_truck_wheel_prefix_must_not_catch_other_objects(self):
        wheel = lambda i, z: {"path": f"t/Wheel{i}", "wheelNode": f"t/Wheel{i}", "centre": [0, 0.4, z], "bands": [
            {"radius": 0.4, "vertices": 9, "lateralMin": 0.7, "lateralMax": 0.8}, {"radius": 0.43, "vertices": 3, "lateralMin": 0.69, "lateralMax": 0.7}]}
        truck = {"truckWheels": [wheel(1, 0.8), wheel(2, -0.8)], "nodes": [{"path": "t/Wheel1"}, {"path": "t/Wheel2"}]}
        geo = buildrecord.truck_geometry(truck)
        self.assertEqual((geo["prefix"], geo["axles"], geo["radius"]), ("Wheel", [0.8, -0.8], 0.4))
        truck["nodes"].append({"path": "t/WheelGuard"})
        self.assertIsNone(buildrecord.truck_geometry(truck)["prefix"])

    def test_safe_names(self):
        self.assertEqual(buildrecord.safe_name('GN A-18 "American"', "X"), "GN A-18 American")
        self.assertEqual(buildrecord.safe_name("::", "RR2DV_X"), "RR2DV_X")

    def test_radial_controls_become_levers_with_g29_physics(self):
        comps = [{"kind": "RadialControl", "name": "Throttle", "parentPath": "Main/Throttle/Grip",
                  "extra": json.dumps({"purpose": "Throttle", "animation": {"clipName": "Throttle"}})},
                 {"kind": "RadialControl", "name": "Johnson Bar", "parentPath": "Main/Rev/Bar",
                  "extra": json.dumps({"purpose": "Reverser", "animation": {"clipName": "Reverser"}})},
                 {"kind": "RadialControl", "name": "Odd", "parentPath": "Main/X", "extra": json.dumps({"purpose": "Dimmer"})}]
        ov = {"clips": [{"key": "Throttle", "poses": [{"path": "Main/Throttle"}, {"path": "Main/ThrottleRod"}]},
                        {"key": "Reverser", "poses": [{"path": "Main/Rev/Bar"}, {"path": "Main/ValveGear"}]}]}
        b = buildrecord._Builder({"vehicleId": "x", "config": {}, "hooks": {}, "metadata": {}}, {}, {"vehicles": []}, {}, {}, {})
        cfg = {}
        levers, cab, loads, taken = b._levers(cfg, comps, ov, {"Throttle": "a", "Reverser": "b"}, "x")
        self.assertEqual([(l["Path"], l["Port"], l["Ctl"]) for l in levers],
                         [("Main/Throttle", "throttle.EXT_IN", 0), ("Main/Rev/Bar", "reverser.CONTROL_EXT_IN", 1)])
        self.assertEqual(levers[0]["_phys"]["notches"], 21)  # G-29 throttle: 5 % per notch
        self.assertEqual((cfg["ReverserHandle"], cfg["ReverserClip"]), ("Main/Rev/Bar", "Reverser"))
        self.assertEqual(cab, ["Main/Throttle"])
        self.assertEqual(loads, [["Throttle", "", "throttle.EXT_IN", False]])  # the rod follows the port outside
        self.assertTrue(any("'Dimmer'" in c for c in b.choices))


class Preflight(unittest.TestCase):
    def test_reviewed_s16_record_passes(self):
        record = json.loads((Path(__file__).resolve().parents[1] / "tooling/locos/s16/profile/vehicle-record.json").read_text())
        self.assertEqual(recordcheck.check(record), [])

    def test_bare_numbers_and_unknown_fields_are_rejected(self):
        record = json.loads((Path(__file__).resolve().parents[1] / "tooling/locos/s16/profile/vehicle-record.json").read_text())
        record["config"]["CabZ"] = -2.65
        record["config"]["NoSuchField"] = "x"
        errors = recordcheck.check(record)
        self.assertIn("$record.config.CabZ: numeric setting requires value/unit/basis/evidence", errors)
        self.assertIn("$record.config.NoSuchField: unknown or readonly LocoConfig field", errors)


if __name__ == "__main__":
    unittest.main()


class RerunCache(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.addCleanup(os.environ.pop, "FAKE_AR_STATE", None)
        self.m = standard_mod(self.tmp)
        self.machine = Machine(None, tool_machine(self.tmp))

    def test_answering_reuses_the_imported_project_in_a_new_run(self):
        first = convert(self.m["mod"], self.machine, search=[self.m["search"]])
        self.assertEqual(first.code, EXIT_INCOMPLETE, first.message)
        self.assertIn("saved the imported project", (first.run.path / "run.log").read_text())
        second = convert(self.m["mod"], self.machine, search=[self.m["search"]], wheel_radius=0.5988, ask=lambda p, s: False)
        self.assertEqual(second.run.record["stages"]["audit"]["status"], "done", second.message)
        self.assertNotEqual(first.run.path, second.run.path)
        self.assertIn("reused from an earlier run", second.run.record["stages"]["import"]["detail"])
        self.assertIn("Unity does not import or measure again", (second.run.path / "run.log").read_text())
        self.assertEqual(read_json(second.run.path / "probe" / "probe.json"), read_json(first.run.path / "probe" / "probe.json"))
        # the build changed the second run's project, never the cache
        entry = next((self.tmp / "work" / "_cache" / "projects").iterdir())
        self.assertFalse((entry / "project" / "Assets" / "Rr2dv" / "BuildInput.json").exists())

    def test_a_changed_export_misses_the_cache(self):
        convert(self.m["mod"], self.machine, search=[self.m["search"]])
        for f in (self.tmp / "work" / "_cache" / "assetripper").rglob("*.prefab"):
            f.write_text(f.read_text() + "\n")
            break
        again = convert(self.m["mod"], self.machine, search=[self.m["search"]])
        self.assertNotIn("reused", again.run.record["stages"]["import"]["detail"])
