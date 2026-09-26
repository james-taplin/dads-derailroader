import unittest

from rr2dv import wheels


def band(r, lo, hi, n=100):
    return {"radius": r, "lateralMin": lo, "lateralMax": hi, "vertices": n}


class Tread(unittest.TestCase):
    """Shaped like our reviewed S16 drivers (board X30): tread r 0.488783 m across x 0.726..0.801 m, a flange above it,
    and a wide inner band at 0.447 m (the old probe's pick, by vertex count) below it."""
    S16 = {"clip": "Drivers", "sourceRadius": 0.49, "meshes": [{"path": "Wheels/Driver1", "used": True}],
           "bands": [band(0.447, 0.728, 0.799, 1632), band(0.4212, 0.74, 0.76, 892), band(0.48878, 0.726, 0.790, 400),
                     band(0.488786, 0.760, 0.801, 380), band(0.517, 0.705, 0.716, 816)]}

    def test_picks_the_widest_outer_band_not_the_most_vertices(self):
        t = wheels.tread(self.S16)
        self.assertAlmostEqual(t["tread"], 0.488783, places=5)
        self.assertEqual((t["lateral"], t["flangeRadius"], t["confidence"]), ([0.726, 0.801], 0.517, "high"))
        self.assertEqual([a["radius"] for a in t["alternatives"]], [0.447])

    def test_narrow_bands_only_is_low_confidence(self):
        coned = {**self.S16, "bands": [band(0.486 + i * 0.001, 0.72 + i * 0.01, 0.725 + i * 0.01) for i in range(6)]}
        t = wheels.tread(coned)
        self.assertEqual(t["confidence"], "low")
        self.assertTrue(any("coned" in n for n in t["notes"]))

    def test_nothing_measured(self):
        t = wheels.tread({"clip": "Drivers", "sourceRadius": 0.49, "bands": []})
        self.assertEqual((t["tread"], t["confidence"]), (None, "none"))

    def test_far_from_source_or_no_flange_is_low_confidence(self):
        t = wheels.tread({**self.S16, "bands": [band(0.45, 0.72, 0.80)]})
        self.assertEqual(t["confidence"], "low")
        self.assertEqual(len(t["notes"]), 2)


if __name__ == "__main__":
    unittest.main()
