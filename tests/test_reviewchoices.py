import copy
import tempfile
import unittest
from pathlib import Path

from rr2dv import oiling, review, reviewchoices, stock
from rr2dv.jsonio import read_json, write_json


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


def stock_questions(pack='ls-060-s23', radius=None):
    profile = oiling.library()['profiles'][pack]
    radius = profile['wheelRadius'] if radius is None else radius
    source = {'mainDriverIndex': 0, 'wheelsets': [{'animation': {'clipName': 'Drivers'},
              'diameter': radius * 2, 'numberOfAxles': len(profile['axleZ'])}]}
    return review.request({'vehicleId': pack, 'config': {'CarName': stock.STEAM[pack]},
        'metadata': {'wheelCandidates': [{'clip': 'Drivers', 'tread': radius + .0352723715782166,
            'confidence': 'low', 'meshesUsed': ['drivers']}]}}, {pack: source}, {}, 'source-a')


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

    def test_a_tyre_like_main_driver_keeps_its_size_over_another_wheelsets_confident_tyre(self):
        # RLW RXM-1, 2026-09-29: drivers 0.947 m measured (low) against 0.915 m source; the trailing wheel's 0.647 m
        # (high) was prefilled as the loco's wheel radius
        req = questions()
        req['wheelCandidates'][1]['confidence'] = 'low'
        req['wheelCandidates'][1]['tread'] = .78  # within 10% of the source 0.75 m: a tyre
        prefill = reviewchoices.suggest(req, {'mainDriverIndex': 1})
        self.assertEqual(prefill['values']['wheelRadius'], .75)
        self.assertEqual(prefill['provenance']['wheelRadius']['basis'], 'source')

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
    def test_s23_low_confidence_saved_radius_resets_only_radius_for_confirmation(self):
        req = stock_questions()
        saved = confirmed(req)
        saved['values'].update(wheelRadius=.6829723715782166, trainBrake='self-lapping')
        saved['provenance']['wheelRadius'] = {'basis': 'DV_choice', 'evidence': 'Previously accepted candidate'}
        before = copy.deepcopy(req)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reviewchoices.remember(root, saved)
            result = reviewchoices.prepare(req, root)
            self.assertEqual(result['prefill']['values']['wheelRadius'], .6477)
            self.assertEqual(result['prefill']['values']['trainBrake'], 'self-lapping')
            self.assertEqual(result['prefill']['provenance']['wheelRadius']['basis'], 'source')
            self.assertIn('0.682972', result['prefill']['origin'])
            self.assertIn('0.6477', result['prefill']['origin'])
            self.assertFalse(result['prefill']['values']['acknowledgeExperimental'])
            self.assertEqual(read_json(reviewchoices.profile_path(root, req)), saved)
            self.assertEqual(req, before)

    def test_radius_recovery_applies_to_every_stock_loco_and_old_report_history(self):
        for pack in sorted(stock.REAL_STEAM):
            with self.subTest(pack=pack), tempfile.TemporaryDirectory() as tmp:
                req = stock_questions(pack)
                saved = confirmed(req)
                expected = req['prefill']['values']['wheelRadius']
                saved['values']['wheelRadius'] += .035
                root = Path(tmp)
                write_json(root / 'reports/old/prebuild-review.json', saved)
                result = reviewchoices.prepare(req, root)
                self.assertEqual(result['prefill']['values']['wheelRadius'], expected)
                self.assertIn('restored for review', result['prefill']['origin'])

    def test_a_changed_source_radius_is_not_overwritten_with_reference_geometry(self):
        req = stock_questions(radius=.70)
        saved = confirmed(req)
        saved['values']['wheelRadius'] = .71
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reviewchoices.remember(root, saved)
            result = reviewchoices.prepare(req, root)
        self.assertEqual(result['prefill']['values']['wheelRadius'], .71)
        self.assertNotIn('restored for review', result['prefill']['origin'])
        profile = oiling.library()['profiles']['ls-060-s23']
        rec = {'vehicleId':'ls-060-s23', 'config':{'CarId':'s23', 'WheelRadius':.71,
               'EngineUnits':[{'DriverParts':['driver']*len(profile['axleZ'])}]}}
        with self.assertRaisesRegex(oiling.OilingError, '0.71.*0.6477.*pre-build review'):
            oiling.prepare(rec)

    def test_supported_saved_radius_keeps_its_existing_provenance(self):
        req = stock_questions()
        saved = confirmed(req)
        saved['provenance']['wheelRadius'] = {'basis': 'DV_choice', 'evidence': 'Confirmed correct source radius'}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reviewchoices.remember(root, saved)
            result = reviewchoices.prepare(req, root)
        self.assertEqual(result['prefill']['values']['wheelRadius'], .6477)
        self.assertEqual(result['prefill']['provenance']['wheelRadius'], saved['provenance']['wheelRadius'])
        self.assertNotIn('restored for review', result['prefill']['origin'])

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
    def test_restored_stock_radius_and_explanation_are_visible_and_require_confirmation(self):
        from rr2dv.reviewgui import show
        from threading import Event
        from tkinter import ttk
        req = stock_questions()
        saved = confirmed(req)
        saved['values']['wheelRadius'] = .6829723715782166
        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp)
            reviewchoices.remember(root_path, saved)
            req = reviewchoices.prepare(req, root_path)
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        state = show(root, req, {'event': Event()})
        root.update_idletasks()
        self.assertEqual(state['fields']['wheelRadius'].get(), '0.6477')
        def labels(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Label):
                    var = child.cget('textvariable')
                    yield root.getvar(var) if var else child.cget('text')
                yield from labels(child)
        self.assertIn(req['prefill']['origin'], list(labels(state['window'])))
        self.assertFalse(state['ack'].get())
        with self.assertRaises(review.ReviewError): state['collect']()
        state['ack'].set(True)
        self.assertEqual(state['collect']()['values']['wheelRadius'], .6477)

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
