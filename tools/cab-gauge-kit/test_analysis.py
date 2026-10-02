import copy
import unittest

import analyse


class AnalysisTests(unittest.TestCase):
    def test_reading_comes_from_wiring_not_the_gauge_name(self):
        gauge = dict(path='gauge Boiler Pressure Main', needles=[dict(
            port='portId=steamEngine.STEAM_CHEST_PRESSURE;indicatorRangeScalerPortId=', reader='')])
        self.assertEqual(analyse.readings(gauge), {'chest'})
        gauge['needles'][0]['port'] = 'portId=boiler.PRESSURE_FAKE;indicatorRangeScalerPortId='
        self.assertEqual(analyse.readings(gauge), set())

    def test_main_brake_requires_pipe_and_application_not_reservoir(self):
        gauge = dict(needles=[dict(port='', reader='IndicatorBrakeReservoirReaderProxy'),
                              dict(port='', reader='IndicatorBrakePipeReaderProxy')])
        self.assertNotIn('brake', analyse.readings(gauge))
        gauge['needles'][0]['reader'] = 'IndicatorBrakeCylinderReaderProxy'
        self.assertIn('brake', analyse.readings(gauge))

    def test_missing_needle_reference_cannot_be_an_existing_candidate(self):
        gauge = dict(error='', orientation='rear-facing', mounting='supported-candidate',
                     needles=[dict(referenceValid=True)])
        self.assertTrue(analyse.candidate(gauge))
        broken = copy.deepcopy(gauge)
        broken['needles'][0]['referenceValid'] = False
        self.assertFalse(analyse.candidate(broken))

    def test_incomplete_fleet_and_duplicate_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            analyse.summarise(dict(completed=False, findings=[]))
        with self.assertRaises(ValueError):
            analyse.summarise(dict(completed=True, findings=[dict(id='a23')]*21))


if __name__ == '__main__':
    unittest.main()
