import math
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from fixtures import standard_mod, tool_machine
from rr2dv import record
from rr2dv.jsonio import read_json
from rr2dv.machine import Machine
from rr2dv.pipeline import EXIT_INCOMPLETE, convert


class Formulas(unittest.TestCase):
    """The guide's formulas must reproduce our reviewed S16 figures (14x22 in, 165 psig, 0.98 m drivers)."""
    S16 = {"maximumBoilerPressure": 165, "pistonDiameterInches": 14, "pistonStrokeInches": 22, "mainDriverIndex": 0,
           "publishedTractiveEffort": 0, "wheelsets": [{"diameter": 0.98, "numberOfAxles": 3}]}

    def test_tractive_effort_and_bore(self):
        te, basis = record.tractive_effort_lbf(self.S16)
        self.assertAlmostEqual(te, 15674.34, places=6)
        self.assertEqual(basis, "RR fallback")
        self.assertAlmostEqual(record.equivalent_bore_m(te, 0.488783, 165, 22 * 0.0254), 0.32743955050496004, places=12)
        self.assertEqual(record.tractive_effort_lbf({**self.S16, "publishedTractiveEffort": 20000}), (20000.0, "published"))

    def test_safety_injector_firebox(self):
        opening, closing = record.safety_bar(165)
        self.assertAlmostEqual(opening, 12.389603999999999, places=12)
        self.assertAlmostEqual(closing, 12.182761199999998, places=12)
        self.assertEqual((record.injector_l_s(876), record.injector_l_s(1735)), (1.8, 3.5))
        firebed, burn = record.firebox_estimate(1735)
        self.assertEqual(firebed, 65)
        self.assertAlmostEqual(burn, 155.0)

    def test_drivers_by_diameter(self):
        m2 = {"mainDriverIndex": 1, "wheelsets": [{"diameter": 0.79, "numberOfAxles": 1}, {"diameter": 1.37, "numberOfAxles": 3},
                                                  {"diameter": 1.37, "numberOfAxles": 4}]}
        self.assertEqual(record.drivers(m2), [1, 2])

    def test_load_slots(self):
        caps = record.load_capacities({"loadSlots": [{"requiredLoadIdentifier": "water", "maximumCapacity": 1000},
                                                     {"requiredLoadIdentifier": "Coal", "maximumCapacity": 2000}]})
        self.assertAlmostEqual(caps["WaterCapacityL"], 3785.411784)
        self.assertAlmostEqual(caps["CoalCapacityKg"], 907.18474)


class Draft(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.addCleanup(os.environ.pop, "FAKE_AR_STATE", None)
        self.m = standard_mod(self.tmp)
        self.machine = Machine(None, tool_machine(self.tmp))

    def run_convert(self, **kw):
        out = convert(self.m["mod"], self.machine, search=[self.m["search"]], ask=lambda pack, sources: False, **kw)
        self.assertEqual(out.code, EXIT_INCOMPLETE, out.message)
        return out.run

    def test_draft_record_from_source_data(self):
        run = self.run_convert()
        rec = read_json(run.path / "record" / "vehicle-record.json")
        c = rec["config"]
        self.assertEqual((rec["schemaVersion"], rec["vehicleId"], c["CarId"]), (1, "ts-260-a", "RR2DV_TS_260_A"))
        self.assertEqual(c["SimBasis"]["value"], 1)          # tender loco: tender ports
        self.assertEqual(c["License"], "SH282")
        self.assertEqual(c["ChuffType"]["value"], 0)          # 1200 ft2 heating surface -> S060 sounds
        self.assertEqual(c["Sounds"], [])
        self.assertEqual(c["AnimationMap"], {"Drivers": "Assets/AnimationClip/Drivers.anim"})
        self.assertEqual(c["Wheelsets"]["value"], [[0.0, 2.4, 1.2, 3, "Drivers"]])
        self.assertIsNone(c["WheelRadius"])                   # fake probe measured nothing: pending, not guessed
        self.assertIsNone(rec["hooks"]["SimSpec"]["steamEngine"]["cylinderBore"])
        powered = rec["hooks"]["SimSpec"]["poweredAxles"]
        self.assertEqual(sorted(powered), ["value"])  # same shape as the reviewed S16 record
        self.assertEqual((powered["value"]["value"], powered["value"]["unit"]), (3, "count"))
        pending = " ".join(rec["metadata"]["pending"])
        for item in ("WheelRadius", "cylinderBore", "WeightEmptyKg", "Bogies", "CollisionBoxes", "tender"):
            self.assertIn(item, pending)
        t = rec["tender"]["config"]
        self.assertTrue(t["IsTender"])
        self.assertAlmostEqual(t["WaterCapacityL"]["value"], 6000 * 3.785411784)
        self.assertEqual(t["Liveries"], [["Black", [["Body", "#191919"]]]])
        for env in (c["SimBasis"], c["RrEndFront"], t["WaterCapacityL"], rec["hooks"]["SimSpec"]["boiler"]["safetyValveOpeningPressure"]):
            self.assertTrue(env["unit"] and env["basis"] and env["evidence"], env)

    def test_probe_candidate_is_never_taken_as_measured(self):
        run = self.run_convert()
        inv = read_json(run.path / "inventory.json")
        probe_in = read_json(run.path / "unity/project/Assets/Rr2dv/ProbeInput.json")
        probe_out = {"vehicles": [{"id": "ts-260-a", "wheels": [{"clip": "Drivers", "sourceRadius": 0.6, "bands": [
            {"radius": 0.598, "lateralMin": 0.70, "lateralMax": 0.78, "vertices": 50},
            {"radius": 0.62, "lateralMin": 0.68, "lateralMax": 0.69, "vertices": 20}]}]}]}
        rec = record.draft(run.path, inv, probe_in, probe_out, {})
        self.assertIsNone(rec["config"]["WheelRadius"])
        self.assertIsNone(rec["hooks"]["SimSpec"]["steamEngine"]["cylinderBore"])
        candidate = rec["metadata"]["wheelCandidates"][0]
        self.assertEqual((candidate["tread"], candidate["flangeRadius"]), (0.598, 0.62))
        self.assertIn("probe candidate 0.598000 m", " ".join(rec["metadata"]["pending"]))

    def test_absent_animation_targets_are_review_items(self):
        run = self.run_convert()
        inv = read_json(run.path / "inventory.json")
        probe_in = read_json(run.path / "unity/project/Assets/Rr2dv/ProbeInput.json")
        absent = [{"export": "main", "clip": "AnimationClip/Whistle.anim", "prefab": "PrefabInstance/ts-260-a.prefab",
                   "keys": ["Whistle"], "bindings": 1, "restored": 0, "absent": ["0xd579eece"]},
                  {"export": "main", "clip": "AnimationClip/Drivers.anim", "prefab": "PrefabInstance/ts-260-a.prefab",
                   "keys": ["Drivers"], "bindings": 40, "restored": 37, "absent": ["0x1", "0x2", "0x3"]}]
        rec = record.draft(run.path, inv, probe_in, None, {}, absent_bindings=absent)
        self.assertEqual(rec["metadata"]["absentBindings"], absent)
        pending = " | ".join(rec["metadata"]["pending"])
        self.assertIn("animation Whistle: animates nothing in the exported model", pending)
        self.assertIn("control it belongs to still works", pending)
        self.assertIn("animation Drivers: 3 of its 40 bindings target objects that are in no model of the export", pending)

    def test_material_problems_and_sources_travel_with_the_record(self):
        run = self.run_convert()
        inv = read_json(run.path / "inventory.json")
        probe_in = read_json(run.path / "unity/project/Assets/Rr2dv/ProbeInput.json")
        probe_out = {"vehicles": [], "problems": ["truck.x: 1 missing material(s) on truck03/Wheel1_LOD0",
                                                  "ts-260-a: clip Drivers binds missing path path_0x1"]}
        rec = record.draft(run.path, inv, probe_in, probe_out, {})
        self.assertEqual(rec["metadata"]["materialProblems"], ["truck.x: 1 missing material(s) on truck03/Wheel1_LOD0"])
        self.assertIn("materials: 1 renderer(s) have an empty material slot", " ".join(rec["metadata"]["pending"]))
        self.assertEqual(rec["metadata"]["sources"], inv["sources"])
        self.assertTrue(rec["metadata"]["sources"])

    def test_reviewed_radius_fills_the_bore(self):
        run = self.run_convert(wheel_radius=0.598)
        rec = read_json(run.path / "record" / "vehicle-record.json")
        self.assertEqual((rec["config"]["WheelRadius"]["value"], rec["config"]["WheelRadius"]["basis"]), (0.598, "measured"))
        self.assertEqual(run.record["answers"]["wheelRadius"]["value"], 0.598)
        bore = rec["hooks"]["SimSpec"]["steamEngine"]["cylinderBore"]["value"]
        te = 0.85 * 180 * 16 ** 2 * 24 / (1.2 / 0.0254)
        self.assertAlmostEqual(bore, record.equivalent_bore_m(te, 0.598, 180, 24 * 0.0254))
        self.assertNotIn("cylinderBore", " ".join(rec["metadata"]["pending"]))

    def test_draft_values_carry_real_units_and_review_items(self):
        rec = read_json(self.run_convert().path / "record" / "vehicle-record.json")
        sim = rec["hooks"]["SimSpec"]
        units = {k: sim["boiler"][k]["unit"] for k in ("defaultFeedwaterTemperature", "maxBlowdownRate", "maxSafetyValveVentRate",
                                                       "spawnPressure", "safetyValveOpeningPressure")}
        self.assertEqual(units, {"defaultFeedwaterTemperature": "degC", "maxBlowdownRate": "L/s", "maxSafetyValveVentRate": "kg/s",
                                 "spawnPressure": "bar absolute", "safetyValveOpeningPressure": "bar absolute"})
        self.assertEqual((sim["steamEngine"]["throttleMaxFlow"]["unit"], sim["steamEngine"]["throttleMaxFlow"]["basis"]),
                         ("kg/s", "analogue_estimate"))
        self.assertIn("not validated", sim["exhaust"]["passiveExhaust"]["notes"])
        pending = " ".join(rec["metadata"]["pending"])
        for item in ("poweredAxles", "source weight", "per-engine calibration"):
            self.assertIn(item, pending)

    def test_livery_choice_is_checked(self):
        with self.assertRaisesRegex(ValueError, "livery 'Green'"):
            convert(self.m["mod"], self.machine, search=[self.m["search"]], livery="Green")


class LiveryColours(unittest.TestCase):
    def test_a_colour_listed_twice_keeps_the_first(self):
        # RLW RMWF-2 'RLW Grey' lists 'roof' twice; the builder keys colours by id ignoring case and stopped on the repeat
        from rr2dv import buildrecord
        b = object.__new__(buildrecord._Builder)
        chosen = []
        b.choose = chosen.append
        cfg = {"Liveries": [["RLW Grey", [["Roof", "#111111"], ["Body", "#222222"], ["roof", "#333333"]]]], "Livery": "RLW Grey"}
        b._liveries(cfg, "rlw-2-8-8-4-l")
        self.assertEqual(cfg["Liveries"][0][1], [["Roof", "#111111"], ["Body", "#222222"]])
        self.assertIn("'roof' more than once (#333333 dropped, #111111 kept)", chosen[0])



class UnevenAxles(unittest.TestCase):
    def test_unevenly_spaced_drivers_use_the_measured_positions(self):
        # base-game T-17 ten-wheeler: drivers at 2.179, 0.579 and -2.179 m; the definition's 3 axles over 4.362 m
        # put the middle one at 0, 0.58 m from the model's wheel
        from rr2dv import buildrecord
        nodes = {f"engine/Drivers/W{i}": [0, .711, z] for i, z in enumerate((2.179, .579, -2.179))}
        wheel_out = {"sourceRadius": .71, "rotatingPaths": list(nodes),
                     "meshes": [{"path": p + "/Cylinder", "used": True, "maxRadius": .72} for p in nodes]}
        ws = {"offset": 0.0, "length": 4.362, "diameter": 1.42, "axles": 3, "clip": "Drivers"}
        axles = buildrecord.measured_axles(ws, wheel_out, nodes)
        self.assertEqual([round(a["z"], 3) for a in axles], [2.179, .579, -2.179])
        self.assertTrue(all(a["part"] and a["uneven"] for a in axles))
        # a wheel missing is still missing: no spacing rule invents it
        wheel_out["meshes"].pop(1)
        self.assertIn(None, [a["part"] for a in buildrecord.measured_axles(ws, wheel_out, nodes)])


if __name__ == "__main__":
    unittest.main()
