"""A crashed Unity editor must say so, with its exit code decoded and the end of its own log (field report 2026-10-01: exit code 3221226525)."""
import tempfile
import unittest
from pathlib import Path

from rr2dv import unityrun


class CrashMessage(unittest.TestCase):
    def test_the_windows_crash_code_from_the_field_report_is_decoded(self):
        text = unityrun._crash_meaning(3221226525)
        self.assertIn("0xC000041D", text)
        self.assertIn("graphics driver", text)

    def test_an_unknown_code_is_shown_in_hex_and_a_clean_exit_adds_nothing(self):
        self.assertEqual(unityrun._crash_meaning(1), " = 0x00000001")
        self.assertEqual(unityrun._crash_meaning(0), "")

    def test_the_log_tail_is_the_last_lines_and_a_missing_log_adds_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "unity-2.log"
            log.write_text("\n".join(f"line {i}" for i in range(30)) + "\n")
            tail = unityrun._log_tail(log, lines=3)
            self.assertIn("line 29", tail)
            self.assertNotIn("line 20", tail)
            self.assertEqual(unityrun._log_tail(Path(tmp) / "nope.log"), "")


if __name__ == "__main__":
    unittest.main()


class NonAsciiTests(unittest.TestCase):
    def test_detects_cyrillic_and_skips_empty(self):
        from rr2dv import unityrun
        found = unityrun.non_ascii_paths({"TEMP": "C:\\Users\\Иван\\AppData\\Local\\Temp", "TMP": None, "Unity": "C:\\Unity\\Editor\\Unity.exe"})
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].startswith("TEMP: "))

    def test_hint_in_crash_message(self):
        from rr2dv import unityrun
        self.assertIn("non-English characters", unityrun._non_ascii_hint({"USERPROFILE": "C:\\Users\\Иван"}))
        self.assertEqual(unityrun._non_ascii_hint({"USERPROFILE": "C:\\Users\\Ivan"}), "")
