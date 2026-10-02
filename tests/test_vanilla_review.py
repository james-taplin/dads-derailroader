"""The vanilla edition's reviewed answers for stock steam locomotives (reviewchoices._stock_answers)."""
import json
import os
import re
import unittest
from pathlib import Path
from unittest import mock

from rr2dv import reviewchoices, stock


def req(ident, source, candidates=None, stoker=None):
    return {"vehicleId": ident, "wheelsets": source["wheelsets"], "wheelCandidates": candidates or [], "hasTender": True,
            "sourceHasDynamo": True, "stokerEvidence": stoker or [], "suggestedBrake": None}


SOURCE = {"kind": "SteamLocomotive", "mainDriverIndex": 1, "wheelsets": [
    {"diameter": 0.7, "animation": {"clipName": "Pilot"}}, {"diameter": 1.118, "animation": {"clipName": "Drivers"}}]}


class StockAnswers(unittest.TestCase):
    def test_a_stock_loco_gets_the_reviewed_answers_whatever_the_probe_suggested(self):
        wrong = [{"clip": "Drivers", "tread": 0.49, "confidence": "high", "meshesUsed": True}]
        with mock.patch.dict(stock.STEAM, {"ls-x": "X"}):
            out = reviewchoices.suggest(req("ls-x", SOURCE, wrong, stoker=["tender Toggle 'Auger'"]), SOURCE)
        v = out["values"]
        self.assertEqual((v["wheelRadius"], v["cylinders"], v["firing"], v["dynamo"]), (0.559, 2, "hand-fired", "yes"))
        self.assertIs(v["acknowledgeExperimental"], False)  # still the user's click
        self.assertIn("stock", out["origin"])

    def test_other_ids_keep_the_generic_suggestion(self):
        out = reviewchoices.suggest(req("not-stock", SOURCE), SOURCE)
        self.assertNotIn("stock", out["origin"])

    @unittest.skipUnless(os.environ.get("RR2DV_RAILROADER"), "needs a Railroader install")
    def test_every_real_stock_loco_gets_its_nominal_radius(self):
        packs = Path(os.environ["RR2DV_RAILROADER"]) / "Railroader_Data" / "StreamingAssets" / "AssetPacks"
        for name in sorted(stock.REAL_STEAM):
            raw = re.sub(r",(\s*[}\]])", r"\1", (packs / name / "Definitions.json").read_text(encoding="utf-8-sig"))
            source = next(o["definition"] for o in json.loads(raw)["objects"] if o["definition"]["kind"] == "SteamLocomotive")
            v = reviewchoices.suggest(req(name, source), source)["values"]
            main = source["wheelsets"][source["mainDriverIndex"]]
            self.assertAlmostEqual(v["wheelRadius"], main["diameter"] / 2, places=4, msg=name)
            self.assertEqual(v["cylinders"], 2, name)


if __name__ == "__main__":
    unittest.main()
