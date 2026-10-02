"""Native regression for the requested dynamo exhaust facing correction."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest


def assemble(project):
    from rr2dv.unityproject import import_unitypackage, set_project_settings, tooling_root
    repo = Path(__file__).resolve().parents[1]
    editor = project/'Assets/Editor'
    editor.mkdir(parents=True)
    manifest = project/'Packages/manifest.json'
    manifest.parent.mkdir()
    modules = ('assetbundle', 'animation', 'audio', 'physics', 'jsonserialize',
               'imgui', 'ui', 'uielements', 'particlesystem', 'screencapture')
    manifest.write_text(json.dumps({'dependencies': {
        'com.unity.modules.'+name: '1.0.0' for name in modules}}))
    set_project_settings(project)
    import_unitypackage(Path(os.environ['RR2DV_TEST_CAR_CREATOR']), project)
    for folder in (tooling_root()/'builder/tools/unity', repo/'src/rr2dv/unity'):
        for script in folder.glob('*.cs'):
            shutil.copy2(script, editor/script.name)
    shutil.copy2(repo/'tests/unity_runtime/DynamoJetRegression.cs', editor/'DynamoJetRegression.cs')


@unittest.skipUnless(os.environ.get('RR2DV_TEST_UNITY') and os.environ.get('RR2DV_TEST_CAR_CREATOR'),
                     'requires Unity and Car Creator for native dynamo jet export tests')
class NativeDynamoJets(unittest.TestCase):
    def test_facing_tilt_position_and_other_jets_survive_export(self):
        from rr2dv.unityrun import run_method
        work = Path(__file__).resolve().parents[1]/'rr2dv_work'; work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='rr2dv-dynamo-', dir=work) as tmp:
            project = Path(tmp)/'project'
            assemble(project)
            output = Path(tmp)/'out'
            result = run_method(Path(os.environ['RR2DV_TEST_UNITY']), project, 'CclLocoBuild.DynamoJetRegression',
                                output, {'CCL_BUILD_OUT': str(output)}, timeout=600)
            self.assertEqual(result, {'passed': True, 'prefabs': 8, 'bundleReload': True, 'exit_code': 0})


if __name__ == '__main__':
    unittest.main()
