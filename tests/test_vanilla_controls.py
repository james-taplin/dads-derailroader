"""Control physics and anchors changed after the 2026-09-30 game test of the stock locos."""
import re
import unittest
from pathlib import Path

from rr2dv import buildrecord

SRC = Path(__file__).resolve().parent.parent / "src" / "rr2dv"


class Physics(unittest.TestCase):
    def test_the_throttle_and_cutoff_have_fewer_notches_and_less_inertia(self):
        t, r = buildrecord.LEVER_PHYSICS["throttle"], buildrecord.LEVER_PHYSICS["reverser"]
        self.assertEqual((t[0], r[0]), (11, 21))
        self.assertLessEqual(t[3], 4)   # mass
        self.assertLessEqual(r[3], 6)
        self.assertEqual({d[0]: d[3] for d in buildrecord.DRIVING}["Throttle"], 11)
        self.assertEqual({d[0]: d[3] for d in buildrecord.DRIVING}["Reverser"], 21)

    def test_the_whistle_springs_back_hard_and_moves_quickly(self):
        n, spring, damper, mass, drag, _, _, _, frac = buildrecord.LEVER_PHYSICS["whistle"]
        self.assertEqual(n, 0)
        self.assertGreaterEqual(spring, 100)
        self.assertLessEqual(mass, 2)
        self.assertLessEqual(drag, 2)
        self.assertEqual(frac, 0.5)

    def test_the_csharp_numbers_for_generated_levers_match_the_table(self):
        text = (SRC / "unity" / "Rr2dvInteractions.cs").read_text(encoding="utf-8")
        _, spring, damper, mass, drag, _, _, _, frac = buildrecord.LEVER_PHYSICS["whistle"]
        self.assertIn(f"Phys(control, 0, travel, 0, {spring}, {damper}, {mass}f, {drag}f, 0, travel * .{int(frac * 10)}f, 100)", text)
        t, r = buildrecord.LEVER_PHYSICS["throttle"], buildrecord.LEVER_PHYSICS["reverser"]
        self.assertIn(f"throttle ? {t[1]}f : {r[1]}f, {t[2]}f, throttle ? {t[3]}f : {r[3]}f, throttle ? {t[4]}f : {r[4]}f", text)
        self.assertIn(f"throttle ? {t[7]}f : {r[7]}f", text)
        self.assertEqual(t[2], r[2])  # the C# uses one damper for both


class Anchors(unittest.TestCase):
    def test_a_control_does_not_replace_the_steam_anchor_of_the_same_name(self):
        whistle = {"kind": "Whistle", "name": "Whistle", "resolved": True, "position": [0.003, 3.96, -0.447]}
        handle = {"kind": "RadialControl", "name": "Whistle", "resolved": True, "position": [1.0, 3.62, -2.57]}
        for order in ([whistle, handle], [handle, whistle]):
            got = buildrecord._Builder.anchors({"anchors": order})
            self.assertEqual(got["Whistle"]["position"], [0.003, 3.96, -0.447])
            self.assertEqual(buildrecord._control_anchor({"anchors": order}, "Whistle"), [1.0, 3.62, -2.57])

    def test_two_controls_or_two_plain_anchors_keep_the_later_one_as_before(self):
        a = {"kind": "Decal", "name": "X", "resolved": True, "position": [1, 1, 1]}
        b = {"kind": "Decal", "name": "X", "resolved": True, "position": [2, 2, 2]}
        self.assertEqual(buildrecord._Builder.anchors({"anchors": [a, b]})["X"]["position"], [2, 2, 2])


if __name__ == "__main__":
    unittest.main()
