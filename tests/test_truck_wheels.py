"""Exported wheel-spindle regression using owned synthetic geometry, no game assets."""
import os
from pathlib import Path
import shutil
import tempfile
import unittest


@unittest.skipUnless(os.environ.get('RR2DV_TEST_UNITY') and os.environ.get('RR2DV_TEST_CAR_CREATOR'),
                     'requires Unity and Car Creator for native truck spindle export checks')
class NativeTruckSpindles(unittest.TestCase):
    def test_centred_spindles_preserve_resting_geometry_and_rolling_radius(self):
        from test_dynamo_jets import assemble
        from rr2dv.unityrun import run_method
        repo = Path(__file__).resolve().parents[1]
        work = repo/'rr2dv_work'; work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='truck-test-', dir=work) as tmp:
            project = Path(tmp)/'project'; assemble(project)
            shutil.copy2(repo/'tests/unity_runtime/TruckWheelOrbitRegression.cs', project/'Assets/Editor/TruckWheelOrbitRegression.cs')
            output = Path(tmp)/'out'
            result = run_method(Path(os.environ['RR2DV_TEST_UNITY']), project, 'TruckWheelOrbitRegression.RunSynthetic',
                                output, dict(CCL_BUILD_OUT=str(output)), timeout=600)
            self.assertTrue(result['passed'])
            self.assertTrue(result['reproduced'])
            self.assertTrue(result['bundleReload'])
            self.assertEqual(result['wheelsets'], 4)
            self.assertGreater(result['beforeTravel'], .08)
            self.assertLess(result['afterTravel'], .0005)
            self.assertEqual(result['exit_code'], 0)
