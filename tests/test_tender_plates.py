"""A tender with no road-number decals gets plates on the middle of each side (buildrecord._Builder._tender_fallback_plates)."""
import json
import unittest

from rr2dv import buildrecord, recordcheck


class TenderPlates(unittest.TestCase):
    def build(self):
        builder = buildrecord._Builder({}, {}, {"vehicles": []}, {}, {}, {})
        cfg = {"Components": buildrecord.env([], "mixed", "source", "source definitions")}
        comps = []
        pairs = builder._tender_fallback_plates(cfg, comps, [-1.5, 0.0, -4.4], [1.5, 4.0, 4.4], 4.46, -4.46)
        return builder, cfg, comps, pairs

    def test_two_plates_one_per_side_at_the_middle(self):
        builder, cfg, comps, pairs = self.build()
        self.assertEqual([p[0] for p in pairs], ["[car plate anchor1]", "[car plate anchor2]"])
        by_name = {c["name"]: c for c in comps}
        left, right = (by_name[p[1]] for p in pairs)
        self.assertLess(left["pos"]["value"][0] if isinstance(left["pos"], dict) else left["pos"][0], 0)
        self.assertGreater(right["pos"]["value"][0] if isinstance(right["pos"], dict) else right["pos"][0], 0)
        for c in comps:
            self.assertEqual(c["kind"], "Decal")
            self.assertEqual(json.loads(c["extra"])["content"], "RoadNumber")
        self.assertEqual(len(cfg["Components"]["value"]), 2)
        self.assertTrue(any("tender number plates" in c for c in builder.choices))

    def test_the_synthetic_decals_pass_the_record_evidence_rules(self):
        _, cfg, _, _ = self.build()
        errors = []
        recordcheck._evidence(cfg["Components"], "config.Components", False, errors)
        self.assertEqual(errors, [])


class TenderLettering(unittest.TestCase):
    def test_lettering_pair_is_used_before_the_fallback(self):
        def decal(name, content, x):
            return {"kind": "Decal", "name": name, "extra": json.dumps({"content": content})}, \
                   {"position": [x, 2.0, 0.5], "resolved": True}
        items = [decal("L", "Lettering", -1.5), decal("R", "Lettering", 1.5), decal("Logo", "Logo", 1.5)]
        comps = [i[0] for i in items]
        anchors = {i[0]["name"]: i[1] for i in items}
        builder = buildrecord._Builder({}, {}, {"vehicles": []}, {}, {}, {})
        self.assertEqual(builder._plates(comps, anchors, tender=True), [["[car plate anchor1]", "L"], ["[car plate anchor2]", "R"]])
        self.assertEqual(builder._plates(comps, anchors), [])  # a loco never uses lettering


if __name__ == "__main__":
    unittest.main()
