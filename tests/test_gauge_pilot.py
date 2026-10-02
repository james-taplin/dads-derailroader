import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

from rr2dv import gauges


def record(source='ls-280-c25'):
    profile = gauges.library()['profiles'].get(source)
    fits = profile['instruments'] if profile else []
    return dict(vehicleId=source, config=dict(CarId='RR2DV_'+source.replace('-', '_').upper(),
        MainPressureGauge=next((f['sourceGauge'] for f in fits if f['reading']=='boiler'), ''),
        Components=dict(value=[dict(kind='Gauge', name=f['sourceGauge'], extra=json.dumps(dict(style=gauges.STYLES[f['reading']]))) for f in fits])))


class GaugePilot(unittest.TestCase):
    def test_every_stock_cab_selects_its_measured_layout(self):
        fit = gauges.prepare(record())
        self.assertEqual(fit['carId'], 'RR2DV_LS_280_C25')
        self.assertEqual([g['reading'] for g in fit['instruments']], ['boiler', 'brake'])
        for source, profile in gauges.library()['profiles'].items():
            self.assertEqual(gauges.prepare(record(source))['instruments'], profile['instruments'])
        self.assertIsNone(gauges.prepare(record('synthetic-not-stock')))

    def test_missing_ambiguous_or_wrong_reading_gauge_fails(self):
        for change in ('missing', 'duplicate', 'wrong-style', 'wrong-main'):
            rec = record()
            components = rec['config']['Components']['value']
            if change == 'missing': components.clear()
            elif change == 'duplicate': components.append(copy.deepcopy(components[0]))
            elif change == 'wrong-style': components[0]['extra'] = '{"style":"DualReservoirMainEq"}'
            else: rec['config']['MainPressureGauge'] = 'Other gauge'
            with self.subTest(change=change), self.assertRaises(gauges.GaugeError):
                gauges.prepare(rec)

    def test_invalid_fit_never_becomes_a_generic_fallback(self):
        data = json.loads(Path(gauges.__file__).with_name('gauge_fits.json').read_text())
        for field, value in [('rotation', [0, 0, 0, 0]), ('position', [0, 1]),
                             ('supportPath', ''), ('scale', 0), ('scale', True), ('evidence', '')]:
            invalid = copy.deepcopy(data)
            invalid['profiles']['ls-280-c25']['instruments'][0][field] = value
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)/'fits.json'; path.write_text(json.dumps(invalid))
                with self.subTest(field=field), self.assertRaises(gauges.GaugeError):
                    gauges.prepare(record(), path)


@unittest.skipUnless(all(os.environ.get(k) for k in ('RR2DV_TEST_UNITY', 'RR2DV_TEST_CAR_CREATOR',
                       'RR2DV_TEST_DV_GAME', 'RR2DV_PRESSURE_MESHES')),
                     'requires Unity, Creator, local DV install and private diagnostic donor buffers')
class NativeGaugePilot(unittest.TestCase):
    def test_export_lod_runtime_calibration_and_numerical_speed_hud(self):
        import shutil
        from test_dynamo_jets import assemble
        from rr2dv.unityrun import run_method
        repo = Path(__file__).resolve().parents[1]
        game = Path(os.environ['RR2DV_TEST_DV_GAME'])
        # Keep native projects beside the app, as the production converter does;
        # Windows Temp may have a different access policy for spawned Unity workers.
        work = repo/'rr2dv_work'; work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='gauge-test-', dir=work) as tmp:
            project = Path(tmp)/'project'; assemble(project)
            for source in (repo/'tests/unity_runtime/PressuremeterRegression.cs', repo/'tools/cab-gauge-kit/GaugeProbe.cs'):
                shutil.copy2(source, project/'Assets/Editor'/source.name)
            inputs = project/'Assets/Rr2dv/BuildInput.json'; inputs.parent.mkdir(exist_ok=True)
            inputs.write_text(json.dumps(dict(gauges=gauges.prepare(record()))))
            output = Path(tmp)/'out'
            result = run_method(Path(os.environ['RR2DV_TEST_UNITY']), project, 'CclLocoBuild.PressuremeterRegression',
                                output, dict(CCL_BUILD_OUT=str(output), RR2DV_GAME_MANAGED=str(game/'DerailValley_Data/Managed'),
                                             RR2DV_CCL_RUNTIME=str(game/'Mods/DVCustomCarLoader'),
                                             RR2DV_PRESSURE_MESHES=os.environ['RR2DV_PRESSURE_MESHES']), timeout=600)
            for key in ('passed', 'bundleReload', 'lodGrabbers', 'actualCclBinding', 'actualDvIndicator', 'numericalHud'):
                self.assertTrue(result[key], (key, result))
            self.assertEqual(result['pressureSamples'], 3)
            self.assertEqual(result['speedSamples'], 4)
            self.assertEqual(result['exit_code'], 0)
            self.assertFalse(result['gameTested'])


if __name__ == '__main__':
    unittest.main()
