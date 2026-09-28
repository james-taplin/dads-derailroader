import copy
import tempfile
import unittest
from pathlib import Path

from rr2dv import review, reviewchoices
from rr2dv.jsonio import write_json


def questions(source=None):
    source = source or {'wheelsets': [{'animation': {'clipName': 'Pilot'}, 'diameter': .8},
                                    {'animation': {'clipName': 'Drivers'}, 'diameter': 1.5}], 'mainDriverIndex': 1}
    candidates = [{'clip': 'Pilot', 'tread': .4, 'confidence': 'high', 'meshesUsed': ['pilot']},
                  {'clip': 'Drivers', 'tread': .75, 'confidence': 'high', 'meshesUsed': ['drivers']}]
    return review.request({'vehicleId': 'any/unsafe:name', 'config': {'CarName': 'Arbitrary', 'RrEndFront': 5, 'RrEndRear': -5},
                           'metadata': {'wheelCandidates': candidates}}, {'any/unsafe:name': source}, {}, 'source-a')


def confirmed(req):
    return review.resolve(req, {**{k: req[k] for k in reviewchoices.IDENTITY},
                               'values': {**req['prefill']['values'], 'acknowledgeExperimental': True}})


class Suggestions(unittest.TestCase):
    def test_measured_main_driver_prefills_without_review_json(self):
        req = questions()
        value = confirmed(req)
        self.assertEqual(value['values']['wheelRadius'], .75)
        self.assertEqual(value['provenance']['wheelRadius']['basis'], 'measured')
        self.assertEqual(value['values']['trainBrake'], 'manual-lap')
        self.assertFalse(req['prefill']['values']['acknowledgeExperimental'])

    def test_missing_geometry_falls_back_to_the_source_driver_radius(self):
        # James, 2026-09-28: the source size beats a blank box; labelled as source for confirmation
        req = questions()
        req['wheelCandidates'] = []
        prefill = reviewchoices.suggest(req, {'mainDriverIndex': 1})
        main = req['wheelsets'][1]
        self.assertEqual(prefill['values']['wheelRadius'], round(main['diameter'] / 2, 4))
        self.assertEqual(prefill['provenance']['wheelRadius']['basis'], 'source')
        self.assertNotIn('gearRatio', prefill['values'])

    def test_a_geared_loco_never_takes_a_shaft_diameter_as_its_radius(self):
        req = questions()
        req['wheelCandidates'] = []
        prefill = reviewchoices.suggest(req, {'mainDriverIndex': 1, 'gearRatio': 3.5})
        self.assertNotIn('wheelRadius', prefill['values'])

    def test_unique_high_confidence_tyre_wins_over_low_confidence_shaft(self):
        req = questions()
        req['wheelCandidates'][1]['confidence'] = 'low'
        req['wheelCandidates'][1]['tread'] = .3  # a shaft: far from the source 0.75 m
        prefill = reviewchoices.suggest(req, {'mainDriverIndex': 1})
        self.assertEqual(prefill['values']['wheelRadius'], .4)
        self.assertEqual(prefill['values']['physics'], '')

    def test_a_low_confidence_main_tread_near_the_source_size_is_a_tyre(self):
        # DM&IR M-3: 0.8001 m measured, 0.80 m source; the steam profile stays suggested
        req = questions()
        req['wheelCandidates'][1]['confidence'] = 'low'
        prefill = reviewchoices.suggest(req, {'mainDriverIndex': 1})
        self.assertEqual(prefill['values']['physics'], 'legacy-equivalent')
        self.assertIn('confirm', prefill['provenance']['wheelRadius']['evidence'])

    def test_source_facts_and_articulated_assumption_are_distinguished(self):
        req = questions({'mainDriverIndex': 0, 'wheelsets': [{'animation': {'clipName': 'Drivers'}}],
                         'brakeValveType': 'self-lapping', 'components': [
                             {'kind': 'ArticulatedSteamEngineComponent', 'isSuperheated': True}]})
        v = req['prefill']
        self.assertEqual(v['values']['cylinders'], 4)
        self.assertEqual(v['provenance']['cylinders']['basis'], 'analogue_estimate')
        self.assertEqual(v['values']['steamHeat'], 'superheated')
        self.assertEqual(v['provenance']['steamHeat']['basis'], 'source')
        self.assertEqual(v['values']['trainBrake'], 'self-lapping')
        self.assertEqual(reviewchoices.suggest(req, {'numCylinders': 3})['values']['cylinders'], 3)

    def test_names_do_not_select_physics_or_cylinder_count(self):
        req = questions()
        req['name'] = 'Four Cylinder Geared Superheated Mallet'
        v = reviewchoices.suggest(req, {})['values']
        self.assertEqual(v['physics'], 'legacy-equivalent')
        self.assertEqual(v['cylinders'], 2)
        self.assertEqual(v['steamHeat'], 'basis-approximation')


class RememberedChoices(unittest.TestCase):
    def test_profile_roundtrip_resets_confirmation_and_preserves_provenance(self):
        req = questions()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            saved = confirmed(req)
            saved['values']['trainBrake'] = 'self-lapping'
            reviewchoices.remember(root, saved)
            path = reviewchoices.profile_path(root, req)
            self.assertEqual(path.parent, root / 'reviews')
            result = reviewchoices.prepare(req, root)
            self.assertEqual(result['prefill']['values']['trainBrake'], 'self-lapping')
            self.assertFalse(result['prefill']['values']['acknowledgeExperimental'])
            self.assertEqual(result['prefill']['provenance']['wheelRadius']['basis'], 'measured')
            self.assertEqual(req['prefill']['values']['trainBrake'], 'manual-lap')

    def test_012_reports_are_discovered_without_importing_a_file(self):
        req = questions()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            saved = confirmed(req)
            saved['values']['trainBrake'] = 'self-lapping'
            write_json(root / 'reports/20260928-old/prebuild-review.json', saved)
            stale = copy.deepcopy(saved)
            stale['fingerprint'] = 'changed'
            write_json(root / 'reports/20260929-new/prebuild-review.json', stale)
            result = reviewchoices.prepare(req, root)
            self.assertEqual(result['prefill']['values']['trainBrake'], 'self-lapping')
            self.assertIn('restored', result['prefill']['origin'])

    def test_changed_identity_never_reuses_answers(self):
        req = questions()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / 'reports/old/prebuild-review.json', confirmed(req))
            for key in ('vehicleId', 'fingerprint', 'adapterVersion', 'catalogueHash'):
                changed = {**req, key: 'different'}
                self.assertEqual(reviewchoices.prepare(changed, root)['prefill'], req['prefill'])

    def test_invalid_profile_falls_back_to_valid_report(self):
        req = questions()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            saved = confirmed(req)
            write_json(root / 'reports/old/prebuild-review.json', saved)
            write_json(reviewchoices.profile_path(root, req), {'invalid': True})
            self.assertIn('restored', reviewchoices.prepare(req, root)['prefill']['origin'])


try:
    import tkinter as tk
    probe = tk.Tk()
    probe.withdraw()
    probe.update_idletasks()
    probe.destroy()
    HAVE_TK = True
except Exception:
    HAVE_TK = False


@unittest.skipUnless(HAVE_TK, 'needs Tk')
class ReviewWindow(unittest.TestCase):
    def test_populated_form_builds_without_a_json_file_and_hides_unused_gears(self):
        from rr2dv.reviewgui import show
        from threading import Event
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        state = show(root, questions(), {'event': Event()})
        root.update_idletasks()
        self.assertEqual(state['fields']['wheelRadius'].get(), '0.75')
        self.assertEqual(state['tabs'].tab(state['wheels'], 'state'), 'disabled')
        self.assertFalse(state['ack'].get())
        state['ack'].set(True)
        self.assertEqual(state['collect']()['values']['wheelRadius'], .75)
        state['fields']['physics'].set('geared')
        self.assertEqual(state['tabs'].tab(state['wheels'], 'state'), 'normal')
        state['fields']['gearRatio'].set('2')
        state['fields']['gearEvidence'].set('Reviewed source ratio')
        state['wheelRoles'][0].set('Unpowered')
        state['wheelRoles'][1].set('Powered')
        values = state['collect']()['values']
        self.assertEqual(values['poweredWheelsets'], [1])
        self.assertEqual(values['unpoweredWheelsets'], [0])
