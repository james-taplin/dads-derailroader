"""Opt-in real Unity 2019.4 prefab-save regression (RR2DV_TEST_UNITY=/path/to/Unity)."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from rr2dv.unityrun import _launch


@unittest.skipUnless(os.environ.get('RR2DV_TEST_UNITY') and os.environ.get('RR2DV_TEST_BUILDER_PROJECT'),
                     'requires Unity and a disposable assembled builder project')
class RealPlacement(unittest.TestCase):
    def test_end_beam_height_search(self):
        repo = Path(__file__).resolve().parents[1]
        project = Path(os.environ['RR2DV_TEST_BUILDER_PROJECT']).resolve()
        editor = project / 'Assets/Editor'
        self.assertTrue((editor / 'CclLocoBuild.cs').is_file(), 'assembled builder project required')
        shutil.copyfile(repo / 'tooling/builder/tools/unity/CclLocoBuild.cs', editor / 'CclLocoBuild.cs')
        shutil.copyfile(repo / 'tests/unity_runtime/EndBeamRegression.cs', editor / 'EndBeamRegression.cs')
        receipt = project / 'end-beam-regression.txt'
        receipt.unlink(missing_ok=True)
        log = project / 'end-beam-regression.log'
        code = _launch(Path(os.environ['RR2DV_TEST_UNITY']), project, 'CclLocoBuild.EndBeamRegression', log,
                       dict(os.environ, RR2DV_BEAM_TEST_REPORT=str(receipt)), 180)
        self.assertEqual(code, 0, log.read_text(errors='replace')[-10000:])
        self.assertEqual(len(receipt.read_text().splitlines()), 12)

    def test_visible_surfaces_survive_prefab_save(self):
        repo = Path(__file__).resolve().parents[1]
        project = Path(os.environ['RR2DV_TEST_BUILDER_PROJECT']).resolve()
        editor = project / 'Assets/Editor'
        self.assertTrue((editor / 'CclLocoBuild.cs').is_file(), 'assembled builder project required')
        # Explicitly supplied disposable project; never a source game project.
        for name in ('Rr2dvPlacement.cs', 'Rr2dvFeatures.cs'):
            shutil.copyfile(repo / 'src/rr2dv/unity' / name, editor / name)
        shutil.copyfile(repo / 'tests/unity_runtime/PlacementRegression.cs', editor / 'PlacementRegression.cs')
        receipt = project / 'placement-regression-passed.json'
        receipt.unlink(missing_ok=True)
        log = project / 'placement-regression.log'
        code = _launch(Path(os.environ['RR2DV_TEST_UNITY']), project, 'CclLocoBuild.PlacementRegression',
                       log, dict(os.environ), 180)
        self.assertEqual(code, 0, log.read_text(errors='replace')[-10000:])
        self.assertEqual(json.loads(receipt.read_text()),
                         {'hiddenMeshIgnored': True, 'collisionIgnored': True, 'reloadVerified': True})


@unittest.skipUnless(os.environ.get('RR2DV_TEST_UNITY'), 'set RR2DV_TEST_UNITY for real Unity prefab tests')
class RealPrefabSave(unittest.TestCase):
    def test_missing_script_save_failure_and_recovery(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='rr2dv-prefab-') as temp:
            project = Path(temp)
            editor = project / 'Assets/Editor'
            editor.mkdir(parents=True)
            (project / 'ProjectSettings').mkdir()
            (project / 'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 2019.4.40f1\n')
            (project / 'Packages').mkdir()
            (project / 'Packages/manifest.json').write_text('{"dependencies":{}}')
            shutil.copyfile(repo / 'src/rr2dv/unity/Rr2dvBuild.cs', editor / 'Rr2dvBuild.cs')
            shutil.copyfile(repo / 'src/rr2dv/unity/Rr2dvAudit.cs', editor / 'Rr2dvAudit.cs')
            shutil.copyfile(repo / 'tests/unity_runtime/PrepRegression.cs', editor / 'PrepRegression.cs')
            shutil.copyfile(repo / 'tests/unity_runtime/AuditGraphRegression.cs', editor / 'AuditGraphRegression.cs')
            unity = Path(os.environ['RR2DV_TEST_UNITY'])
            log = project / 'regression.log'
            code = _launch(unity, project, 'PrepRegression.Run', log, dict(os.environ), 240)
            self.assertEqual(code, 0, log.read_text(errors='replace')[-14000:])
            self.assertTrue(json.loads((project / 'regression-passed.json').read_text())['reloadVerified'])
            code = _launch(unity, project, 'AuditGraphRegression.Run', log, dict(os.environ), 180)
            self.assertEqual(code, 0, log.read_text(errors='replace')[-8000:])
            self.assertTrue(json.loads((project / 'audit-graph-passed.json').read_text())['audioFound'])
            inp = project / 'Assets/Rr2dv/BuildInput.json'
            inp.parent.mkdir()
            inp.write_text(json.dumps({'schema': 1, 'audioStrip': [], 'absentBindings': [],
                                      'composites': [{'vehicle': 'bad', 'source': 'Assets/Absent.prefab',
                                                      'target': 'Assets/Generated/Bad.prefab', 'parts': []}]}))
            out = project / 'out'
            code = _launch(unity, project, 'Rr2dvBuild.Build', log, dict(os.environ, CCL_BUILD_OUT=str(out)), 180)
            self.assertEqual(code, 1, log.read_text(errors='replace')[-4000:])
            self.assertIn('model prefab not found', json.loads((out / 'prep.json').read_text())['error'])
            self.assertTrue(json.loads((out / 'result.json').read_text())['prepFailed'])
            self.assertFalse((project / 'unexpected-downstream.txt').exists())
