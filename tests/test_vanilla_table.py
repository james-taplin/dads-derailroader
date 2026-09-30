"""The per-locomotive table (src/rr2dv/stock_locos.json) and what the pipeline takes from it."""
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fixtures import standard_mod, tool_machine
from rr2dv import stock
from rr2dv.jsonio import read_json
from rr2dv.machine import Machine
from rr2dv.pipeline import convert


class Table(unittest.TestCase):
    def test_the_table_is_complete_for_all_21_locomotives(self):
        self.assertEqual(stock.validate_table(), [])
        self.assertEqual(set(stock.table()["locos"]), set(stock.REAL_STEAM))

    def test_a_table_missing_a_fact_is_reported(self):
        data = json.loads(json.dumps(stock.table()))
        del data["locos"]["ls-282-k28t"]["driver"]["evidence"]
        data["locos"]["ls-060-s23"]["answers"]["cylinders"] = 3
        data["locos"]["ls-284-b65"]["sourceSha256"]["Bundle"] = "abc"
        del data["locos"]["ls-440-a23"]["cab"]
        problems = "\n".join(stock.validate_table(data))
        for text in ("ls-282-k28t: the driver radius", "ls-060-s23: answers", "ls-284-b65: sourceSha256", "ls-440-a23: 'cab' is missing"):
            self.assertIn(text, problems)

    def test_build_status_reports_an_unknown_build_and_never_refuses(self):
        e = stock.entry("ls-282-k28t")
        files = [{"name": n, "sha256": e["sourceSha256"][n]} for n in stock.HASHED_FILES]
        self.assertTrue(stock.build_status("ls-282-k28t", [{"name": "ls-282-k28t", "files": files}])[0])
        files[2] = {"name": "Definitions.json", "sha256": "0" * 64}
        ok, text = stock.build_status("ls-282-k28t", [{"name": "ls-282-k28t", "files": files}])
        self.assertFalse(ok)
        self.assertIn("unknown game build: Definitions.json", text)

    def test_a_hidden_mesh_without_a_reason_is_reported(self):
        data = json.loads(json.dumps(stock.table()))
        data["locos"]["ls-282-k35"]["hide"][0]["why"] = ""
        self.assertIn("every hidden mesh needs a path and a reason", "\n".join(stock.validate_table(data)))

    def test_the_b65_tender_band_james_accepted_is_in_the_table(self):
        band = stock.entry("ls-284-b65")["endBeam"]["lt-284-b65"]
        self.assertEqual(band["band"], [1.0, 1.2])
        self.assertTrue(any("accepted by James" in e for e in band["evidence"]))

    @unittest.skipUnless(os.environ.get("RR2DV_RAILROADER"), "needs a Railroader install")
    def test_the_table_agrees_with_the_real_definitions(self):
        packs = Path(os.environ["RR2DV_RAILROADER"]) / "Railroader_Data" / "StreamingAssets" / "AssetPacks"
        for name, e in stock.table()["locos"].items():
            raw = re.sub(r",(\s*[}\]])", r"\1", (packs / name / "Definitions.json").read_text(encoding="utf-8-sig"))
            objs = {o["identifier"]: o["definition"] for o in json.loads(raw)["objects"]}
            loco = next(d for d in objs.values() if d["kind"] == "SteamLocomotive")
            main = loco["wheelsets"][loco["mainDriverIndex"]]
            self.assertAlmostEqual(e["driver"]["radiusM"], main["diameter"] / 2, places=4, msg=name)
            self.assertEqual(e["tank"], not loco.get("tenderIdentifier"), name)
            self.assertEqual(e["displayName"], stock.STEAM[name], name)
            wh = next((c for c in loco["components"] if c["kind"] == "Whistle"), {}).get("defaultWhistleIdentifier") or ""
            self.assertEqual(e["whistle"]["definitionId"], wh, name)


class PipelineUsesTheTable(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        for var in ("FAKE_AR_STATE", "FAKE_UNITY_MODE"):
            self.addCleanup(os.environ.pop, var, None)
        self.m = standard_mod(self.tmp)
        self.machine = Machine(None, tool_machine(self.tmp))
        self.entry = {"endBeam": {"tt-260-a": {"band": [1.0, 1.2], "evidence": ["synthetic: accepted by the tester"]}}}

    def run_to_link(self, matches=True, **kw):
        with mock.patch.object(stock, "entry", return_value=self.entry), \
                mock.patch.object(stock, "build_status", return_value=(matches, "synthetic")):
            return convert(self.m["mod"], self.machine, ask=lambda *a: False, wheel_radius=.598, **kw)

    def test_a_matching_table_band_is_applied_like_a_reviewed_geometry_file(self):
        out = self.run_to_link()
        review = read_json(out.run.path / "geometry-review.json")
        self.assertEqual(review["vehicles"]["tt-260-a"]["EndBeamProbeHeight"]["value"], [1.0, 1.2])
        self.assertIn("vanilla table", review["vehicles"]["tt-260-a"]["EndBeamProbeHeight"]["evidence"][-1])
        self.assertEqual(review["inputFingerprint"], out.run.record["input_fingerprint"])
        rec = read_json(out.run.path / "build/vehicle-record.json")
        self.assertEqual(rec["tender"]["config"]["EndBeamProbeHeight"]["value"], [1.0, 1.2])

    def test_an_unknown_build_gets_no_band_and_the_run_says_so(self):
        out = self.run_to_link(matches=False)
        self.assertFalse((out.run.path / "geometry-review.json").exists())
        self.assertFalse(out.run.record["answers"]["vanillaTable"]["matches"])

    def test_meshes_the_table_hides_go_into_the_build_input_with_their_prefab(self):
        self.entry["hide"] = [{"path": "engine/Plane.010", "why": "synthetic cord"}]
        out = self.run_to_link()
        data = read_json(next(out.run.path.glob("unity/project/Assets/Rr2dv/BuildInput.json")))
        self.assertEqual([(h["path"], h["why"]) for h in data["hide"]], [("engine/Plane.010", "synthetic cord")])
        self.assertTrue(data["hide"][0]["prefab"].startswith("Assets/"))

    def test_a_loco_without_hidden_meshes_has_an_empty_list(self):
        out = self.run_to_link()
        data = read_json(next(out.run.path.glob("unity/project/Assets/Rr2dv/BuildInput.json")))
        self.assertEqual(data["hide"], [])

    def test_the_users_own_review_file_wins_over_the_table(self):
        first = self.run_to_link(matches=False)
        review = {"schema": 1, "inputFingerprint": first.run.record["input_fingerprint"], "vehicles": {"tt-260-a": {"EndBeamProbeHeight": {
            "value": [.7, .85], "unit": "m", "basis": "derived", "evidence": ["user file"]}}}}
        path = self.tmp / "review.json"
        path.write_text(json.dumps(review))
        out = self.run_to_link(geometry_review=path)
        self.assertEqual(read_json(out.run.path / "geometry-review.json"), review)


if __name__ == "__main__":
    unittest.main()
