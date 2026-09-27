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
        self.assertEqual([i["radius"] for i in t["innerSurfaces"]][:1], [0.447])

    # X33: the real S16 probe (Unity 2019.4). The tyre band (0.48889 m, 0.719..0.801 m, 518 vertices) lost on width to
    # inner surfaces up to 0.189 m wide at lower radii; those lie under the tread and flange. Figures from X33, the
    # flange side and chamfer bands shaped around them.
    REAL = {"clip": "Drivers", "sourceRadius": 0.49,
            "meshes": [{"path": "Main/Driver1/Cylinder.002", "used": True}],
            "bands": [dict(band(0.52049, 0.6672, 0.690, 300)), band(0.505, 0.690, 0.700, 60), band(0.495, 0.700, 0.712, 60),
                      band(0.4902, 0.712, 0.7185, 40),
                      {**band(0.4888870, 0.7190644, 0.8014112, 518), "modeRadius": 0.488783, "modeVertices": 480,
                       "radiusMin": 0.48851, "radiusMax": 0.48899},
                      band(0.485, 0.8014, 0.808, 80),
                      band(0.4469613, 0.6672196, 0.8198932, 1632), band(0.430, 0.6312500, 0.8198912, 900)]}

    def test_real_s16_profile_picks_the_tyre_not_the_wider_inner_surfaces(self):
        t = wheels.tread(self.REAL)
        self.assertEqual(t["tread"], 0.488783)       # the exact-radius mode, not the 1 mm bin mean
        self.assertAlmostEqual(t["span"], 0.0823468, places=6)
        self.assertEqual((t["flangeRadius"], t["confidence"]), (0.52049, "high"))
        self.assertEqual([i["radius"] for i in t["innerSurfaces"]][:2], [0.430, 0.4469613])
        self.assertLess(t["radiusSpread"], 0.0005)

    def test_width_alone_never_wins(self):
        """The old rule (widest band) picks 0.447 on the real profile; the outer-surface rule must not."""
        self.assertNotAlmostEqual(wheels.tread(self.REAL)["tread"], 0.447, places=2)
        self.assertGreater(wheels.covered(wheels._merged([band(0.447, 0.6672, 0.8199)])[0],
                                          wheels._merged([band(0.4889, 0.7191, 0.8014), band(0.52, 0.6672, 0.7185)])), 0.5)

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
