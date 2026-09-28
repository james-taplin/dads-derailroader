import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fixtures import standard_mod, tool_machine, tree_state
from rr2dv import workspace
from rr2dv.jsonio import read_json, sha256_file
from rr2dv.machine import Machine
from rr2dv.pipeline import convert
from rr2dv.runs import Run


class TemporaryConversions(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.addCleanup(os.environ.pop, 'FAKE_AR_STATE', None)
        self.addCleanup(os.environ.pop, 'FAKE_UNITY_MODE', None)
        self.mod = standard_mod(self.root)
        values = tool_machine(self.root)
        values.pop('keepWorkFiles')  # Exercise the real default, not the diagnostic fixture setting.
        self.machine = Machine(None, values)

    def run_conversion(self, **kwargs):
        return convert(self.mod['mod'], self.machine, search=[self.mod['search']], **kwargs)

    def assert_clean(self, outcome):
        run = outcome.run
        self.assertEqual(run.path.parent.name, 'reports')
        self.assertEqual(run.record['cleanup']['status'], 'done')
        self.assertFalse(Path(run.record['cleanup']['temporary_path']).exists())
        self.assertFalse((self.machine.work_root / '_cache').exists())
        for name in ('inputs', 'unity', 'extracted', 'build'):
            self.assertFalse((run.path / name).exists(), name)
        self.assertEqual(read_json(run.file)['cleanup']['status'], 'done')
        if run.record['stages']['probe']['status'] == 'done':  # blocks point the user at these measurements
            for name in ('probe/probe.json', 'probe/result.json', 'probe/probe-input.json'):
                self.assertTrue((run.path / name).is_file(), name)

    def test_installed_output_survives_cleanup_without_a_duplicate(self):
        source = tree_state(Path(self.machine.values['railroader']))
        out = self.run_conversion(wheel_radius=.598, ask=lambda *a: True)
        self.assertEqual(out.code, 0, out.message)
        self.assert_clean(out)
        self.assertFalse((self.machine.work_root / 'output').exists())
        dest = Path(out.run.record['output'])
        for name, digest in out.run.record['pack']['files'].items():
            self.assertEqual(sha256_file(dest / name), digest)
        self.assertEqual(tree_state(Path(self.machine.values['railroader'])), source)
        recipe = read_json(out.run.path / 'rebuild.json')
        self.assertIsNone(recipe['seed'])
        self.assertEqual(recipe['answers']['wheelRadius']['value'], .598)
        self.assertTrue(all(f['sha256'] for f in recipe['source_files']))
        self.assertTrue(recipe['environment']['app_sources']['pipeline.py'])
        self.assertTrue(recipe['environment']['tools']['unity']['sha256'])
        self.assertEqual(recipe['expected_pack_files'], out.run.record['pack']['files'])
        self.assertEqual(recipe['recipe_sha256'], out.run.record['recipe_sha256'])

    def test_declined_pack_is_preserved_and_verified_before_cleanup(self):
        out = self.run_conversion(wheel_radius=.598, ask=lambda *a: False)
        self.assertEqual(out.code, 3, out.message)
        self.assert_clean(out)
        output = Path(out.run.record['output'])
        self.assertTrue(output.is_relative_to(self.machine.work_root / 'output'))
        for name, digest in out.run.record['pack']['files'].items():
            self.assertEqual(sha256_file(output / name), digest)

    def test_answer_stop_keeps_candidate_but_no_ripped_assets(self):
        out = self.run_conversion()
        self.assertEqual(out.code, 3)
        self.assert_clean(out)
        self.assertTrue(out.run.record['blocks'])
        self.assertNotIn('output', out.run.record)

    def test_tool_failure_keeps_diagnostics_but_no_workspace(self):
        with patch('rr2dv.pipeline.extract', side_effect=RuntimeError('ripper failed')):
            with self.assertRaisesRegex(RuntimeError, 'ripper failed') as caught:
                self.run_conversion()
        run = caught.exception.rr2dv_run
        self.assert_clean(type('Result', (), {'run': run})())
        self.assertIn('ripper failed', (run.path / 'run.log').read_text())

    def test_failed_pack_preservation_never_deletes_only_copy(self):
        original = workspace.sha256_file
        with patch.object(workspace, 'sha256_file', return_value='wrong'):
            out = self.run_conversion(wheel_radius=.598, ask=lambda *a: False)
        self.assertEqual(out.run.record['cleanup']['status'], 'pending')
        self.assertTrue(Path(out.run.record['cleanup']['temporary_path']).exists())
        self.assertIn('cleanup pending', out.message)
        workspace.recover(self.machine.work_root)
        report = read_json(self.machine.work_root / 'reports' / out.run.path.name / 'run.json')
        self.assertEqual(report['cleanup']['status'], 'done')
        for name, digest in report['pack']['files'].items():
            self.assertEqual(original(Path(report['output']) / name), digest)


class WorkspaceGuards(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)

    def test_live_workspace_and_unowned_legacy_folder_are_left_alone(self):
        run = Run.create(self.root, 'active', {})
        lease = workspace.begin(run)
        legacy = self.root / 'legacy'
        legacy.mkdir()
        (legacy / 'precious').write_text('keep')
        try:
            workspace.recover(self.root)
            self.assertTrue(run.path.exists())
            self.assertEqual((legacy / 'precious').read_text(), 'keep')
        finally:
            lease.close()
        workspace.recover(self.root)
        self.assertFalse(run.path.exists())
        self.assertEqual(read_json(self.root / 'reports' / run.path.name / 'run.json')['status'], 'interrupted')

    def test_cleanup_failure_is_recorded_and_retried(self):
        run = Run.create(self.root, 'locked', {})
        lease = workspace.begin(run)
        run.close('failed', 'test')
        original = run.path
        def partly_deleted(*args):
            (original / workspace.MARKER).unlink()
            (original / 'run.json').unlink()
            raise PermissionError('locked')
        with patch.object(workspace, 'remove_tree', side_effect=partly_deleted):
            workspace.finish(run, lease)
        self.assertTrue(original.exists())
        self.assertEqual(run.record['cleanup']['status'], 'pending')
        workspace.recover(self.root)
        self.assertFalse(original.exists())
        self.assertEqual(read_json(run.file)['cleanup']['status'], 'done')

    def test_reject_root_outside_and_link_boundaries(self):
        for target in (self.root, self.root.parent):
            with self.assertRaises(ValueError):
                workspace.remove_tree(target, self.root)
        inside = self.root / 'inside'
        inside.mkdir()
        (inside / 'file').write_text('keep')
        with patch.object(workspace, 'is_link', side_effect=lambda p: p.name == 'file'):
            with self.assertRaises(ValueError):
                workspace.remove_tree(inside, self.root)
        self.assertEqual((inside / 'file').read_text(), 'keep')

    def test_recipe_identity_is_stable_and_changes_with_reviewed_answers(self):
        from rr2dv import rebuild
        run = Run.create(self.root, 'recipe', {'locomotive': 'test'})
        run.record['answers'] = {'wheelRadius': {'value': .5}}
        rebuild.save(run)
        first = read_json(run.path / 'rebuild.json')['recipe_sha256']
        rebuild.save(run)
        self.assertEqual(read_json(run.path / 'rebuild.json')['recipe_sha256'], first)
        run.record['answers']['wheelRadius']['value'] = .6
        rebuild.save(run)
        self.assertNotEqual(read_json(run.path / 'rebuild.json')['recipe_sha256'], first)

    def test_interrupted_unity_is_stopped_before_cleanup_can_start(self):
        from rr2dv import unityrun
        process = Mock()
        process.wait.side_effect = KeyboardInterrupt
        process.poll.return_value = None
        with patch.object(unityrun.subprocess, 'Popen', return_value=process), patch.object(unityrun.procs, 'stop') as stop:
            with self.assertRaises(KeyboardInterrupt):
                unityrun._launch(Path('Unity'), self.root, 'Test', self.root / 'log', {}, 10)
        stop.assert_called_once_with(process)
