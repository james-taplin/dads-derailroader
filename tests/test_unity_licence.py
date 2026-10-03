"""A live Editor waiting for activation must not consume the hour-long probe timeout."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from rr2dv import unityrun


FIELD_STARTUP = '''[Licensing::Module] Successfully connected to LicensingClient
[LicensingClient] Licenses Updated successfully in LicensingClient
Built from '2019.4/staging' branch; Version is '2019.4.40f1'
[Licensing::Module] License is not active (com.unity.editor.ui). HasEntitlements will fail.
No valid Unity Editor license found. Please activate your license.
[Package Manager] Server::Start -- Port 63939 was selected
Failed to connect to local IPC Name not known
COMMAND LINE ARGUMENTS:
Rr2dvProbe.Run
'''


class LicenceStartup(unittest.TestCase):
    def test_report_signature_identifies_missing_licence_not_successful_client_connection(self):
        self.assertTrue(unityrun._licence_blocks_startup(FIELD_STARTUP))
        self.assertFalse(unityrun._licence_blocks_startup('[Licensing::Module] License is not active (other.entitlement)'))
        self.assertFalse(unityrun._licence_blocks_startup('Licenses Updated successfully'))

    def test_startup_progress_after_refusal_clears_the_block(self):
        for progress in ('Initialize engine version: 2019.4.40f1', 'Begin MonoManager ReloadAssembly'):
            with self.subTest(progress=progress):
                self.assertFalse(unityrun._licence_blocks_startup(FIELD_STARTUP + progress))
                self.assertTrue(unityrun._licence_blocks_startup(progress + '\n' + FIELD_STARTUP))

    def test_live_missing_licence_stops_after_grace_before_hour_timeout(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            log = project / 'unity-1.log'
            log.write_text(FIELD_STARTUP, encoding='utf-8')
            proc = Mock()
            proc.poll.return_value = None
            proc.wait.side_effect = subprocess.TimeoutExpired('Unity', 2)
            def stopped(*args, **kwargs):
                proc.poll.return_value = 1
            with patch.object(unityrun.subprocess, 'Popen', return_value=proc), \
                 patch.object(unityrun.procs, 'stop', side_effect=stopped) as stop, \
                 patch.object(unityrun.time, 'monotonic', side_effect=[0, 0, 31]):
                with self.assertRaisesRegex(unityrun.UnityError, 'no active Editor licence.*Unity Hub') as caught:
                    unityrun._launch(Path('Unity.exe'), project, 'Rr2dvProbe.Run', log, {}, 3600)
            stop.assert_called_once_with(proc, grace=60)
            self.assertEqual(proc.wait.call_count, 2)
            self.assertIn('2019.4.40f1', str(caught.exception))
            self.assertIn(str(log), str(caught.exception))
            self.assertEqual(log.read_text(), FIELD_STARTUP)

    def test_transient_refusal_does_not_kill_an_editor_that_resumes_startup(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            log = project / 'unity-1.log'
            proc = Mock()
            proc.poll.return_value = 0
            counter = 0
            def wait(**kwargs):
                nonlocal counter
                counter += 1
                if counter == 1:
                    log.write_text(FIELD_STARTUP)
                elif counter == 2:
                    log.write_text(FIELD_STARTUP + 'Initialize engine version: 2019.4.40f1')
                else:
                    return 0
                raise subprocess.TimeoutExpired('Unity', 2)
            proc.wait.side_effect = wait
            with patch.object(unityrun.subprocess, 'Popen', return_value=proc), \
                 patch.object(unityrun.procs, 'stop') as stop, \
                 patch.object(unityrun.time, 'monotonic', side_effect=[0, 0, 31]):
                result = unityrun._launch(Path('Unity.exe'), project, 'Rr2dvProbe.Run', log, {}, 3600)
            self.assertEqual(result, 0)
            stop.assert_not_called()

    def test_exited_missing_licence_is_retried_once_then_reports_activation(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            unity = project / 'Unity.exe'
            unity.touch()
            out = project / 'probe'
            def launch(unity, project, method, log, env, timeout):
                log.write_text(FIELD_STARTUP)
                return 1
            with patch.object(unityrun, '_launch', side_effect=launch) as launch:
                with self.assertRaisesRegex(unityrun.UnityError, 'after 2 attempt.*') as caught:
                    unityrun.run_method(unity, project, 'Rr2dvProbe.Run', out)
            self.assertEqual(launch.call_count, 2)
            self.assertIn('Unity Hub', str(caught.exception))
            self.assertTrue((out / 'launch.json').is_file())
