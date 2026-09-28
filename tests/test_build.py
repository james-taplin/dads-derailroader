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
        self.assertEqual([s["status"] for s in run.record["stages"].values()], ["done"] * len(run.record["stages"]))
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
        self.assertEqual((t["Trucks"][0]["Wheelset"], t["WheelRadius"]), (buildrecord.TRUCK_WHEEL_PREFIX, 0.42))
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

    def test_reviewed_geometry_is_preserved_and_stale_review_stops_before_tools(self):
        first = self.convert()
        review = {'schema': 1, 'inputFingerprint': first.run.record['input_fingerprint'],
                  'vehicles': {'ts-260-a': {'EndBeamProbeHeight': {
                      'value': [.7, .85], 'unit': 'm', 'basis': 'derived', 'evidence': ['synthetic measured beam']}}}}
        path = self.tmp / 'review.json'
        path.write_text(json.dumps(review))
        out = self.convert(agree=False, wheel_radius=.598, geometry_review=path)
        self.assertEqual(out.code, EXIT_INCOMPLETE, out.message)
        self.assertEqual(read_json(out.run.path / 'geometry-review.json'), review)
        self.assertEqual(out.run.record['answers']['geometryReview'], review)
        rec = read_json(out.run.path / 'build/vehicle-record.json')
        self.assertEqual(rec['config']['EndBeamProbeHeight'], review['vehicles']['ts-260-a']['EndBeamProbeHeight'])
        self.assertNotIn('EndBeamProbeHeight', rec['tender']['config'])
        review['inputFingerprint'] = 'changed'
        path.write_text(json.dumps(review))
        out = self.convert(wheel_radius=.598, geometry_review=path)
        self.assertEqual(out.code, EXIT_FAILED)
        self.assertIn('different source', out.message)
        self.assertEqual(out.run.record['stages']['stage']['status'], 'pending')

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

    def test_missing_cylinder_cock_uses_reviewable_front_bogie_fallback(self):
        defs = self.m["mod"] / "ts-260-a" / "Definitions.json"
        data = json.loads(defs.read_text().replace(",\n  ],\n}", "\n  ]\n}"))
        comps = data["objects"][0]["definition"]["components"]
        data["objects"][0]["definition"]["components"] = [c for c in comps if c.get("kind") != "CylinderCock"]
        defs.write_text(json.dumps(data))
        out = self.convert(wheel_radius=0.598)
        self.assertEqual(out.code, EXIT_OK, out.message)
        rec = read_json(out.run.path / "build/vehicle-record.json")
        self.assertEqual(recordcheck.check(rec), [])
        cocks = [c for c in rec["config"]["Components"]["value"] if c["kind"] == "CylinderCock"]
        self.assertEqual(len(cocks), 1)
        self.assertEqual(cocks[0]["pos"]["basis"], "analogue_estimate")
        self.assertEqual(cocks[0]["pos"]["value"][:2], [1.1, 0.598])
        self.assertEqual(buildrecord._plain(rec["config"]["CrackPos"])[1:], cocks[0]["pos"]["value"][1:])
        self.assertTrue(any("no source CylinderCock" in c for c in rec["metadata"]["buildChoices"]))


    def test_model_file_without_extension_is_found(self):
        from rr2dv.rrmod import Pack
        pack = Pack(root=None, path=Path("p"), files={}, assets={"t": {"filename": "truck.usra-andrews70t"}})
        self.assertEqual(pack.model_prefab("t"), "truck.usra-andrews70t.prefab")
        self.assertEqual(pack.model_prefab("other"), "other.prefab")

    def test_missing_model_names_what_the_export_holds(self):
        from rr2dv.unityproject import ModelNotExported, find_prefab
        assets = self.tmp / "x" / "ExportedProject" / "Assets"
        (assets / "PrefabInstance").mkdir(parents=True)
        (assets / "PrefabInstance" / "USRA_Andrews.prefab").write_text("")
        self.assertEqual(find_prefab(assets, "usra_andrews").name, "USRA_Andrews.prefab")
        with self.assertRaisesRegex(ModelNotExported, "truck.usra-andrews70t.prefab is not in the exported pack x.*PrefabInstance/USRA_Andrews.prefab"):
            find_prefab(assets, "truck.usra-andrews70t")



class Rules(unittest.TestCase):
    def test_a_lone_driver_off_the_definition_is_matched_and_side_cranks_are_not_wheels(self):
        # RLW RPP-1 single-wheeler (real probe figures): driver at z 0 (definition 0.5 m), crank pivots 6-9 m to the side
        nodes = {"Second Driver.001": [0.0, 1.238, 0.0], "Empty.001": [-8.708, 1.255, 2.1], "Empty.010": [6.012, 1.254, 1.773]}
        wout = {"sourceRadius": 1.24, "rotatingPaths": sorted(nodes), "meshes": [
            {"path": "Second Driver.001", "used": True, "reason": "", "maxRadius": 1.273},
            {"path": "Empty.001/Cylinder.013", "used": False, "reason": "not centred on the axle", "maxRadius": 1.359},
            {"path": "Empty.010/Cylinder.043", "used": False, "reason": "not centred on the axle", "maxRadius": 1.359}]}
        axles = buildrecord.measured_axles({"offset": 0.5, "length": 0, "axles": 1}, wout, nodes)
        self.assertEqual([(a["part"], a["shift"]) for a in axles], [("Second Driver.001", -0.5)])
        self.assertEqual(buildrecord.measured_axles({"offset": 1.6, "length": 0, "axles": 1}, wout, nodes)[0]["part"], None)

    def test_each_truck_axle_gets_its_own_wheel_node(self):
        w = lambda path, z: {"path": path, "wheelNode": "", "centre": [0, 0.42, z]}
        # truck.archbar.diamond (L-27 tender): one container for both axles' bones -> the bones, never the container
        self.assertEqual(buildrecord.axle_nodes([w("t/Wheels Animation/Bone.001/Frame2_LOD0", -0.842),
                                                 w("t/Wheels Animation/Bone.002/Frame1_LOD0", 0.842)]),
                         ["t/Wheels Animation/Bone.001", "t/Wheels Animation/Bone.002"])
        # truck.commonwealth.a (H9 tender): one mesh per axle per LOD, siblings under each LOD group
        lods = [w(f"t/truck_LOD{l}/whl{i}_LOD{l}", z) for l in (0, 1) for i, z in ((1, 1.275), (2, 0.0), (3, -1.288))]
        self.assertEqual(len(buildrecord.axle_nodes(lods)), 6)
        # Fox-style: a Wheel node per axle holding its meshes
        self.assertEqual(buildrecord.axle_nodes([w("t/Wheel1/a", 0.8), w("t/Wheel1/b", 0.8), w("t/Wheel2/a", -0.8)]),
                         ["t/Wheel1", "t/Wheel2"])

    def test_a_small_backhead_uses_the_upper_plate_before_stopping(self):
        # PLW Trojan shape: a flat plate from 1.7 to 2.9 m with the fire door at 1.32 m
        points = [(round(-0.7 + 0.1 * i, 1), round(1.72 + 0.1 * j, 2)) for i in range(14) for j in range(13)]
        usual = buildrecord.control_positions(points, (0.0, 1.321), [], 30)
        spots, tier = buildrecord.fitted_positions(points, (0.0, 1.321), [], len(usual) + 3)
        self.assertEqual((len(spots), tier), (len(usual) + 3, 1))
        spots, tier = buildrecord.fitted_positions(points, (0.0, 1.321), [], 500)  # never fits: the most any rule gives
        self.assertLess(len(spots), 500)

    def test_a_handle_that_only_slides_is_not_a_lever(self):
        # GN L-27 (real probe poses): the throttle handle slides 50 mm; the reverser swings 46.2 deg
        v = {"clips": [{"key": "Throttle", "poses": [{"path": "e/Throttle", "startEuler": [0, 0, 0], "endEuler": [0, 0, 0]}]},
                       {"key": "Reverser", "poses": [{"path": "e/Rev", "startEuler": [0, 180, 180], "endEuler": [-12.7, 0, 0]}]}]}
        self.assertEqual(buildrecord.pose_turn_deg(v, "Throttle", "e/Throttle"), 0.0)
        self.assertAlmostEqual(buildrecord.pose_turn_deg(v, "Reverser", "e/Rev"), 167.3, places=1)
        self.assertAlmostEqual(buildrecord.pose_turn_deg(
            {"clips": [{"key": "R", "poses": [{"path": "p", "startEuler": [10, 0, 0], "endEuler": [56.2, 0, 0]}]}]}, "R", "p"), 46.2, places=3)
        self.assertIsNone(buildrecord.pose_turn_deg(v, "Throttle", "elsewhere"))

    def test_wheel_evidence_says_why_no_wheel_was_found(self):
        self.assertIn("rotates no transform", buildrecord.wheel_evidence({"rotatingPaths": []}))
        text = buildrecord.wheel_evidence({"rotatingPaths": ["Main/Drivers"], "meshes": [
            {"used": False, "reason": "not centred on the axle"}, {"used": False, "reason": "not centred on the axle"}]})
        self.assertIn("1 transform(s) (Main/Drivers)", text)
        self.assertIn("2 not centred on the axle", text)

    def test_cylinder_cock_fallback_injects_only_when_source_anchor_is_missing(self):
        builder = buildrecord._Builder({}, {}, {"vehicles": []}, {}, {}, {})
        cfg = {"Components": buildrecord.env([], "mixed", "source", "source definitions")}
        comps = []
        cocks, pos = builder._ensure_cylinder_cock(cfg, comps, [{"z": 1.2}, {"z": 0.8}],
                                                     [-1.5, 0, -4.4], [1.5, 4, 5.5], 0.598)
        self.assertEqual(pos, [1.1, 0.598, 2.2])
        self.assertEqual(cocks[0]["kind"], "CylinderCock")
        self.assertEqual(cfg["Components"]["value"][0]["pos"]["basis"], "analogue_estimate")
        self.assertEqual(cfg["Components"]["basis"], "derived")
        evidence_errors = []
        recordcheck._evidence(cfg["Components"], "config.Components", False, evidence_errors)
        self.assertEqual(evidence_errors, [])
        self.assertTrue(any("no source CylinderCock" in c for c in builder.choices))

        original = {"kind": "CylinderCock", "name": "source cock", "pos": [0.9, 0.3, 1.0]}
        cfg = {"Components": buildrecord.env([original], "mixed", "source", "source definitions")}
        cocks, pos = builder._ensure_cylinder_cock(cfg, [original], [{"z": 1.2}],
                                                     [-1.5, 0, -4.4], [1.5, 4, 5.5], 0.598)
        self.assertIsNone(pos)
        self.assertEqual(cocks, [original])
        self.assertEqual(cfg["Components"]["value"], [original])

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

    def test_abbreviated_truck_wheel_names(self):
        # truck.commonwealth.a (Western Maryland H9 tender): whl1..3, each one mesh for both sides, with LOD copies
        wheel = lambda i, lod, z: {"path": f"truck/truck_LOD{lod}/whl{i}_LOD{lod}", "wheelNode": f"truck/truck_LOD{lod}/whl{i}_LOD{lod}",
                                   "centre": [0, 0.43, z], "bands": [{"radius": 0.44, "vertices": 9, "lateralMin": 0.7, "lateralMax": 0.8}]}
        wheels = [wheel(i, lod, z) for lod in (0, 1) for i, z in ((1, 1.275), (2, 0.0), (3, -1.288))]
        truck = {"truckWheels": wheels, "nodes": [{"path": w["wheelNode"]} for w in wheels] + [{"path": "truck/truck_LOD0/truck.004_LOD0"}]}
        geo = buildrecord.truck_geometry(truck)
        self.assertEqual((geo["prefix"], geo["axles"]), ("whl", [1.275, 0.0, -1.288]))

    def test_one_axle_definition_over_a_long_wheelset_counts_the_model_wheels(self):
        # Western Maryland H9 (real probe figures): the definition gives Drivers 1 axle over 5.51 m; the model has four
        # wheels at axle height, one of them off-centre (counterweight), and rods/cranks higher up that must not count.
        nodes = {"e/D/drivers": [0, 0.7816, -0.8333], "e/D/drivers.001": [0, 0.7815, 0.9610], "e/D/drivers.002": [0, 0.7815, -2.6091],
                 "e/D/drivers.003": [0, 0.7815, 2.7555], "e/D/rods_008_L": [-1.4055, 1.4901, 1.5831]}
        mesh = lambda p, used, reason="", r=0.805: {"path": p, "used": used, "reason": reason, "maxRadius": r}
        wout = {"sourceRadius": 0.775, "rotatingPaths": sorted(nodes), "meshes": [
            mesh("e/D/drivers/driver2", False, "not centred on the axle"), mesh("e/D/drivers.001/driver1", True),
            mesh("e/D/drivers.002/driver3", True), mesh("e/D/drivers.003/driver0", True),
            mesh("e/D/rods_008_L/Cylinder.076", True, r=0.67), mesh("e/D/drivers/rods/Cylinder.761", False, "not centred on the axle", 3.75)]}
        ws = {"clip": "Drivers", "offset": 0.0, "length": 5.51094, "diameter": 1.55, "axles": 1}
        self.assertEqual(buildrecord.inferred_axle_count(ws, wout, nodes), 4)
        axles = buildrecord.measured_axles({**ws, "axles": 4}, wout, nodes)
        self.assertEqual([a["part"] for a in axles], ["e/D/drivers.003", "e/D/drivers.001", "e/D/drivers", "e/D/drivers.002"])
        self.assertIsNone(buildrecord.inferred_axle_count({**ws, "axles": 4}, wout, nodes))  # a consistent definition is kept

    def test_wheels_offset_as_a_set_from_the_definition(self):
        # RLW ROF-1 (real probe figures): five drivers at the definition's spacing, all 0.875 m further forward, and a
        # centred connecting rod (4.4x the wheel) at axle height that must not count as a wheel
        zs = [4.279, 2.577, 0.875, -0.827, -2.529]
        nodes = {f"D{i}": [0.004, 0.804, z] for i, z in enumerate(zs)} | {"D2/Rod": [0.874, 0.804, 0.454]}
        meshes = [{"path": f"D{i}/wheel", "used": True, "reason": "", "maxRadius": 0.835} for i in range(5)]
        meshes.append({"path": "D2/Rod/rod", "used": True, "reason": "", "maxRadius": 3.532})
        wout = {"sourceRadius": 0.8025, "rotatingPaths": sorted(nodes), "meshes": meshes}
        axles = buildrecord.measured_axles({"offset": 0.0, "length": 6.808, "axles": 5}, wout, nodes)
        self.assertEqual([a["part"] for a in axles], ["D0", "D1", "D2", "D3", "D4"])
        self.assertEqual({a["shift"] for a in axles}, {0.875})
        # a different spacing is not a shift: the axles stay unmatched and the build stops
        axles = buildrecord.measured_axles({"offset": 0.0, "length": 9.0, "axles": 5}, wout, nodes)
        self.assertTrue(any(a["part"] is None for a in axles))

    def test_truck_wheel_names(self):
        self.assertTrue(all(map(buildrecord.is_wheel_name, ['Standard 33" Wheels.001', "whl1_LOD0", "Wheel2"])))
        self.assertFalse(any(map(buildrecord.is_wheel_name, ["Bolster", "Journal Box.001", "Circle.001"])))

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
