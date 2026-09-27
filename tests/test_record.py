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
        out = convert(self.m["mod"], self.tmp / "out", self.machine, search=[self.m["search"]], **kw)
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
        self.assertEqual(rec["hooks"]["SimSpec"]["poweredAxles"]["value"], {"value": 3})
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

    def test_tender_runs_on_vanilla_dv_bogies(self):
        rec = read_json(self.run_convert().path / "record" / "vehicle-record.json")
        t = rec["tender"]
        self.assertEqual((t["config"]["WheelRadius"]["value"], t["config"]["WheelRadius"]["basis"]), (0.459, "DV_choice"))
        bogies = t["metadata"]["vanillaBogies"]
        self.assertEqual((bogies["BogieType"], bogies["value"], bogies["centres"]["value"]), ("Default", 200, [2.0, -2.0]))
        self.assertEqual([r["id"] for r in bogies["replaces"]], ["test-truck-2s"])
        self.assertIn("BogieBufferTypes.cs", bogies["evidence"][0])

    def test_livery_choice_is_checked(self):
        with self.assertRaisesRegex(ValueError, "livery 'Green'"):
            convert(self.m["mod"], self.tmp / "out", self.machine, search=[self.m["search"]], livery="Green")


if __name__ == "__main__":
    unittest.main()
