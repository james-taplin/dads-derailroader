import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from rr2dv.machine import Machine, doctor, load
from rr2dv.safety import UnsafePath, check_write_target, is_link


class Guards(unittest.TestCase):
    def test_write_target_inside_a_protected_folder_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp) / "Derail Valley"
            with self.assertRaises(UnsafePath):
                check_write_target(game / "Mods" / "x", [("Derail Valley install", game)])
            check_write_target(Path(tmp) / "work", [("Derail Valley install", game)])

    @unittest.skipIf(sys.platform == "win32", "symlink creation needs privileges on Windows")
    def test_links_are_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            real, link = Path(tmp) / "real", Path(tmp) / "link"
            real.mkdir()
            os.symlink(real, link)
            self.assertTrue(is_link(link))
            self.assertFalse(is_link(real))


class MachineSettings(unittest.TestCase):
    def test_llw_machine_file_loads_and_derives_search_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            rr = tmp / "Railroader"
            (rr / "Mods").mkdir(parents=True)
            settings = tmp / "machine.local.json"
            settings.write_text('{"schema": 1, "python": "%s", "railroader": "%s", "mods": "", "workRoot": "%s"}'
                                % (sys.executable.replace("\\", "/"), rr.as_posix(), (tmp / "w").as_posix()))
            m = load(settings)
            self.assertEqual(m.search_roots(), [])  # the install's own folders are added by the pipeline
            results = {c.name: c.status for c in doctor(m)}
            self.assertEqual(results["tooling Python"], "ok")
            self.assertEqual(results["Unity Editor"], "fail")
            self.assertEqual(results["work folder"], "ok")
            self.assertEqual(results["Railroader install"], "fail")  # no Railroader_Data here

    def test_search_roots_accepts_a_single_string(self):
        self.assertEqual(Machine(None, {"searchRoots": "D:/RR/Mods"}).search_roots(), [Path("D:/RR/Mods")])
        self.assertEqual(Machine(None, {"searchRoots": 5}).search_roots(), [])

    def test_work_folder_path_length(self):
        # X29: build the boundary from a real absolute root and check the fully assembled longest path.
        import os
        from rr2dv.machine import LONGEST_PROJECT_PATH, WINDOWS_MAX_PATH, check_work_root, max_work_root_length
        from rr2dv.runs import RUN_ID_MAX
        base = os.path.realpath(tempfile.gettempdir())
        limit = max_work_root_length()

        def root_of(length):
            return Path(base) / ("x" * (length - len(base) - 1))

        def assembled(root):
            return os.path.realpath(root) + "/" + "r" * RUN_ID_MAX + "/unity/project/" + LONGEST_PROJECT_PATH

        at_limit = root_of(limit)
        self.assertEqual(len(assembled(at_limit)), WINDOWS_MAX_PATH)
        check_work_root(at_limit)
        with self.assertRaisesRegex(ValueError, "at most"):
            check_work_root(root_of(limit + 1))
        self.assertEqual(limit, 74)

    def test_missing_settings_file_is_empty_not_an_error(self):
        m = load(Path(tempfile.gettempdir()) / "no-such-rr2dv-settings.json")
        self.assertIsNone(m.source)
        self.assertEqual(m.search_roots(), [])


if __name__ == "__main__":
    unittest.main()
