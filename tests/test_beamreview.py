import copy
import tempfile
import unittest
from pathlib import Path

from rr2dv import beamreview, geometryreview
from rr2dv.jsonio import read_json, write_json


def core(low, beam, hits, binned, left, right, parts=("Cube.027",)):
    return {"low": low, "high": round(low + .2, 3), "hits": hits, "bin": binned, "beam": beam,
            "binLeft": left, "binRight": right, "parts": list(parts)}


def face(low, z, rays, left, right, parts=("Cube.120",)):
    return {"low": low, "high": round(low + .2, 3), "z": z, "rays": rays, "left": left, "right": right, "parts": list(parts)}


def survey():
    """Shaped like the RLW RXM-1B front (2026-09-29): the default band fails, a broad face at 1.5..1.7 m on the same plane
    as the pilot face at 0.4..0.6 m, 0.175 m behind the source car end; the rear is a drawbar end."""
    front = {"end": "front", "dir": 1, "rigged": True, "sourceEnd": 7.5,
             "faces": [face(0.4, 7.314, 20, 10, 10), face(1.5, 7.325, 47, 16, 16, ("Cube.027", "Cylinder.048")),
                       face(0.2, 7.82, 9, 2, 2)],
             "core": [core(0.4, 7.52, 60, 12, 2, 2), core(0.9, 7.6, 65, 10, 1, 1), core(1.5, 7.325, 60, 26, 8, 8, ("Cube.027", "Cylinder.048"))]}
    rear = {"end": "rear", "dir": -1, "rigged": False, "sourceEnd": -8.23, "faces": [], "core": []}
    return {"schema": 1, "car": "RR2DV_X", "isTender": False, "couplerHeight": 1.05, "ends": [front, rear]}


class Proposal(unittest.TestCase):
    def test_broad_corroborated_face_is_proposed_and_validates(self):
        review, why = beamreview.propose(survey(), "f" * 64, "loco-a", "run-1")
        self.assertEqual(review["vehicles"]["loco-a"]["EndBeamProbeHeight"]["value"], [1.5, 1.7])
        self.assertEqual(review["vehicles"]["loco-a"]["EndBeamProbeHeight"]["basis"], "measured")
        self.assertIn("1.50..1.70", why)
        self.assertTrue(geometryreview.validate(review, "f" * 64, {"loco-a", "tender-a"}))

    def test_no_proposal_without_the_same_plane_at_another_height(self):
        data = survey()
        data["ends"][0]["faces"] = [f for f in data["ends"][0]["faces"] if f["low"] == 1.5]
        review, why = beamreview.propose(data, "f" * 64, "loco-a", "run-1")
        self.assertIsNone(review)
        self.assertIn("manual geometry review", why)

    def test_no_proposal_far_from_the_source_end(self):
        data = survey()
        data["ends"][0]["sourceEnd"] = 8.0  # 0.675 m from the face
        self.assertIsNone(beamreview.propose(data, "f" * 64, "loco-a", "run-1")[0])

    def test_narrow_face_is_not_a_beam(self):
        data = survey()
        data["ends"][0]["core"][2]["binLeft"] = 1
        self.assertIsNone(beamreview.propose(data, "f" * 64, "loco-a", "run-1")[0])

    def test_every_rigged_end_must_pass_in_the_same_band(self):
        data = survey()
        data["ends"][1] = copy.deepcopy(data["ends"][0])
        data["ends"][1]["end"] = "rear"
        data["ends"][1]["core"][2]["bin"] = 5
        self.assertIsNone(beamreview.propose(data, "f" * 64, "loco-a", "run-1")[0])

    def test_band_nearest_coupler_height_wins(self):
        data = survey()
        data["ends"][0]["core"].append(core(1.0, 7.31, 60, 24, 6, 6, ("Body265.009",)))
        data["ends"][0]["faces"].append(face(1.0, 7.31, 8, 3, 3))
        review, _ = beamreview.propose(data, "f" * 64, "loco-a", "run-1")
        self.assertEqual(review["vehicles"]["loco-a"]["EndBeamProbeHeight"]["value"], [1.0, 1.2])

    def test_written_for_the_tender_when_the_tender_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run-1"
            data = survey()
            data["isTender"] = True
            write_json(run / "build" / "out" / "endbeam-survey.json", data)
            path, _ = beamreview.write_proposal(run, "f" * 64, "loco-a", "tender-a")
            self.assertEqual(list(read_json(path)["vehicles"]), ["tender-a"])

    def test_the_other_cars_reviewed_band_is_kept(self):
        # RLW RXM-1B: the loco's front band was reviewed, then the tender's rear stopped
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run-1"
            data = survey()
            data["isTender"] = True
            write_json(run / "build" / "out" / "endbeam-survey.json", data)
            loco_band = {"value": [1.5, 1.7], "unit": "m", "basis": "measured", "evidence": ["survey"]}
            reviewed = {"schema": 1, "inputFingerprint": "f" * 64, "vehicles": {"loco-a": {"EndBeamProbeHeight": loco_band}}}
            path, why = beamreview.write_proposal(run, "f" * 64, "loco-a", "tender-a", reviewed)
            proposal = read_json(path)
            self.assertEqual(proposal["vehicles"]["loco-a"]["EndBeamProbeHeight"], loco_band)
            self.assertEqual(proposal["vehicles"]["tender-a"]["EndBeamProbeHeight"]["value"], [1.5, 1.7])
            self.assertIn("keeps the reviewed band for loco-a", why)
            self.assertTrue(geometryreview.validate(proposal, "f" * 64, {"loco-a", "tender-a"}))

    def test_nothing_without_a_survey(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(beamreview.write_proposal(Path(tmp), "f" * 64, "loco-a", None), (None, ""))


if __name__ == "__main__":
    unittest.main()
