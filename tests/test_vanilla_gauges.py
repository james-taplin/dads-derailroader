"""Normal Derail Valley gauges on every converted stock loco (buildrecord._Builder._ensure_gauges)."""
import json
import math
import os
import re
import unittest
from pathlib import Path

from rr2dv import buildrecord, recordcheck, stock

STYLES = ("BoilerPressure", "DualBrakeCylinderLine", "DualReservoirMainEq", "Speedometer100")


def gauge(name, style, pos, scale=0.8, rot=(0.0, 1.0, 0.0, 0.0)):
    return {"kind": "Gauge", "name": name, "parentPath": "", "extra": json.dumps({"style": style, "enabled": True}),
            "pos": list(pos), "rot": list(rot), "scale": [scale, scale, 1.0]}


def run(gauges):
    builder = buildrecord._Builder({}, {}, {"vehicles": []}, {}, {}, {})
    cfg = {"Components": buildrecord.env([dict(g) for g in gauges], "mixed", "source", "source definitions")}
    comps = [buildrecord._plain(g) for g in cfg["Components"]["value"]]
    builder._ensure_gauges(cfg, comps, "ls-x")
    return builder, cfg, cfg["Components"]["value"]


def styles(value):
    return [json.loads(c["extra"])["style"] for c in value if c["kind"] == "Gauge"]


class Gauges(unittest.TestCase):
    def test_a_quadruplex_becomes_the_normal_two_needle_gauge_and_the_missing_ones_are_generated(self):
        _, cfg, value = run([gauge("BP", "BoilerPressure", (0.1, 3.4, -5.9), 1.0), gauge("Speedo", "Speedometer100", (0.7, 3.7, -5.9), 0.6),
                             gauge("Brake", "Quadruplex", (0.87, 3.63, -5.8), 0.78)])
        self.assertNotIn("Quadruplex", styles(value))
        self.assertEqual(sorted(set(styles(value))), sorted(STYLES))
        self.assertEqual(len(value), 4)  # only the brake-cylinder gauge was added; the speedometer existed
        errors = []
        recordcheck._evidence(cfg["Components"], "config.Components", False, errors)
        self.assertEqual(errors, [])

    def test_a_loco_with_only_boiler_gauges_gets_brake_and_speed_gauges_that_do_not_overlap(self):
        builder, _, value = run([gauge("BP 1", "BoilerPressure", (0.0, 3.0, -4.0), 0.8), gauge("BP 2", "BoilerPressure", (0.3, 3.0, -4.0), 0.8)])
        self.assertEqual(sorted(set(styles(value))), sorted(STYLES))
        pos = [buildrecord._plain(c["pos"]) for c in value]
        for i, a in enumerate(pos):
            for b in pos[i + 1:]:
                self.assertGreater(math.dist(a, b), 0.12)
        self.assertTrue(any("generated one beside" in c for c in builder.choices))

    def test_nothing_changes_when_the_model_has_every_gauge(self):
        full = [gauge("BP", "BoilerPressure", (0, 3, -4)), gauge("DBCL", "DualBrakeCylinderLine", (0.3, 3, -4)),
                gauge("DRME", "DualReservoirMainEq", (0.5, 3, -4)), gauge("S", "Speedometer100", (0.7, 3, -4))]
        builder, _, value = run(full)
        self.assertEqual(len(value), 4)
        self.assertEqual(builder.choices, [])

    def test_no_gauge_at_all_leaves_the_loco_alone(self):
        builder, _, value = run([])
        self.assertEqual(value, [])
        self.assertTrue(builder.choices)

    @unittest.skipUnless(os.environ.get("RR2DV_RAILROADER"), "needs a Railroader install")
    def test_every_real_stock_loco_ends_with_all_four_normal_gauges(self):
        packs = Path(os.environ["RR2DV_RAILROADER"]) / "Railroader_Data" / "StreamingAssets" / "AssetPacks"
        for name in stock.STEAM:
            raw = re.sub(r",(\s*[}\]])", r"\1", (packs / name / "Definitions.json").read_text(encoding="utf-8-sig"))
            d = next(o["definition"] for o in json.loads(raw)["objects"] if o["definition"]["kind"] == "SteamLocomotive")
            gs = [gauge(c["name"], c["style"], c["transform"]["position"], c["transform"]["scale"][0], c["transform"]["rotation"])
                  for c in d["components"] if c["kind"] == "Gauge"]
            _, _, value = run(gs)
            self.assertEqual(sorted(set(styles(value))), sorted(STYLES), name)
            every = [(c["name"], buildrecord._plain(c["pos"])) for c in value if c["kind"] == "Gauge"]
            for n, a in every:
                if not n.startswith("rr2dv generated"):
                    continue
                for m, b in every:
                    if m != n:
                        self.assertGreater(math.dist(a, b), 0.06, f"{name}: generated gauge {n} sits on {m}")


if __name__ == "__main__":
    unittest.main()
