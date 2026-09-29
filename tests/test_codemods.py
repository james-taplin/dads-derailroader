import copy
import math
import unittest

from rr2dv import codemods, review
from test_enginemetrics import fixture, resolve


def articulated(mode=1, **extra):
    return {"maximumBoilerPressure": 200, "pistonDiameterInches": 20, "pistonStrokeInches": 26,
            "mainDriverIndex": 0, "wheelsets": [{"diameter": 1.4, "numberOfAxles": 4, "animation": {"clipName": "D"}}],
            "components": [{"kind": "ArticulatedSteamEngineComponent", "name": "m", "diamater": 26, "stroke": 26,
                            "cylinderType": mode, **extra}]}


class CodeMods(unittest.TestCase):
    def test_legos_articulated_gives_the_mod_pull_first_for_its_own_mode(self):
        base = .85 * 200 * 20 ** 2 * 26 / (1.4 / .0254)
        simple = base + .85 * 200 * 26 ** 2 * 26 / (1.4 / .0254)
        out = codemods.review(articulated(mode=0))
        self.assertEqual(out["options"][0]["id"], "legos-simple")
        self.assertEqual(out["options"][0]["lbf"], round(simple))
        self.assertEqual(out["options"][-1]["id"], "railroader")
        self.assertEqual(out["options"][-1]["lbf"], round(base))
        self.assertEqual(codemods.review(articulated(mode=1))["options"][0]["id"], "legos-compound")
        self.assertEqual(out["cylinders"], 4)

    def test_published_figure_is_offered_when_the_definition_has_one(self):
        d = articulated()
        d["publishedTractiveEffort"] = 50000
        self.assertEqual(codemods.review(d)["options"][-1], {"id": "published", "label": "Published tractive effort",
                                                            "lbf": 50000, "evidence": "Definitions.publishedTractiveEffort"})

    def test_no_code_mod_offers_nothing(self):
        d = articulated()
        d["components"] = []
        self.assertEqual(codemods.review(d)["options"], [])

    def test_the_chosen_pull_resizes_the_equivalent_bore(self):
        record, req, values = fixture()
        req["codeMods"] = {"options": [{"id": "legos-simple", "label": "LegosBetterSteam simple", "lbf": 48000,
                                        "evidence": "test"}], "notes": [], "unrecognised": []}
        values["pullBasis"] = "legos-simple"
        before = review.apply(copy.deepcopy(record), resolve(req, {**values, "pullBasis": "legos-simple"}))
        bore = before["hooks"]["SimSpec"]["steamEngine"]["cylinderBore"]["value"]
        plain = record["hooks"]["SimSpec"]["steamEngine"]["cylinderBore"]["value"]
        self.assertAlmostEqual(bore, plain * math.sqrt(48000 / 24000), places=6)
        self.assertEqual(before["metadata"]["tractiveEffort"]["lbf"], 48000)
