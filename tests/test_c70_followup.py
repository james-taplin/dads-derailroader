import json
import math
import tempfile
import unittest
from pathlib import Path

from rr2dv.audit import audit_input
from rr2dv.review import apply


class FollowupTests(unittest.TestCase):
    def test_ancillary_audit_counts_unique_enabled_source_clips(self):
        def toggle(clip, title='Window', key='window', enabled=True):
            return {'kind': 'ToggleAnimation', 'extra': json.dumps({
                'animation': {'clipName': clip}, 'title': title, 'key': key, 'enabled': enabled})}
        record = {'vehicleId': 'arbitrary', 'config': {
            'CarId': 'x', 'CarName': 'Example', 'WeightEmptyKg': 1, 'WheelRadius': .5,
            'Components': [toggle('A'), toggle('A'), toggle('B', enabled=False),
                           toggle('Fire', 'Firebox Door'), toggle('Cocks', key='cylCock'), toggle('Roof')]}}
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit_input(record, Path(tmp))['openingCount'], 2)
            del record['vehicleId']
            self.assertEqual(audit_input(record, Path(tmp))['openingCount'], 2)
            # a toggle the builder disclosed as left out (L-27's duplicate roof hatch) is not expected in the pack
            record['config']['Components'][-1]['name'] = 'Roof Hatch 1'
            from rr2dv.audit import left_out_openings
            gone = left_out_openings(["rr2dv ancillary toggle 'Roof Hatch 1' left out (not interactive; ...): reason"])
            self.assertEqual(gone, {('Roof Hatch 1', None)})
            self.assertEqual(audit_input(record, Path(tmp), gone)['openingCount'], 1)
            # two toggles share a name (ALCo K-66): only the one whose clip the warning names is left out
            record['config']['Components'][-1]['name'] = 'A'
            gone = left_out_openings(["rr2dv ancillary toggle 'A' left out (not interactive; its model stays as modelled): "
                                      "Declared toggle target is not moved by its clip: Roof / Main/Hatch"])
            self.assertEqual(gone, {('A', 'Roof')})
            self.assertEqual(audit_input(record, Path(tmp), gone)['openingCount'], 1)

    def test_geared_report_keeps_units_and_does_not_invent_a_speed_limit(self):
        record = {'config': {}, 'metadata': {}, 'hooks': {'SimSpec': {'steamEngine': {}}}}
        reviewed = {'values': {'wheelRadius': .5, 'spawnTracks': [], 'cylinders': 2,
                              'physics': 'geared', 'steamHeat': 'saturated', 'gearRatio': 3, 'efficiency': .9},
                    'sourceSpecs': {'pistonDiameterInches': 10}, 'fingerprint': 'test', 'catalogueEvidence': 'test'}
        profile = apply(record, reviewed)['metadata']['simulationProfile']
        at60 = profile['speedDiagnostics'][-1]
        self.assertAlmostEqual(at60['wheelRpm'], 1000 / math.pi, places=2)
        self.assertAlmostEqual(at60['engineRpm'], 3000 / math.pi, places=2)
        self.assertAlmostEqual(at60['doubleActingExhaustEventsPerSecond'], 200 / math.pi, places=2)
        self.assertFalse(profile['runtimeValidated'])
        self.assertTrue(any('Gearbox 1/2' in item for item in profile['limitations']))
        self.assertEqual(profile['results'], [])


if __name__ == '__main__':
    unittest.main()
