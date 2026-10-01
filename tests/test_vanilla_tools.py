"""tools/vanilla/run_bulk.py (the bulk measurement run for Codex) on the fake tools: preflight, resume, failure handling."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from fixtures import standard_mod, tool_machine
from rr2dv import stock

SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "vanilla" / "run_bulk.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("run_bulk", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BulkRun(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        for var in ("FAKE_AR_STATE", "FAKE_UNITY_MODE"):
            self.addCleanup(os.environ.pop, var, None)
        standard_mod(self.tmp)
        patch = mock.patch.dict(stock.STEAM, {"ts-260-a": "Test loco"}, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        self.settings = self.tmp / "settings.json"
        self.settings.write_text(json.dumps(tool_machine(self.tmp)))
        self.out = self.tmp / "out"
        self.tool = load_tool()
        self.tool.MIN_FREE_GB = 0

    def run_tool(self, *args):
        argv = ["run_bulk.py", "--machine", str(self.settings), "--out-dir", str(self.out), *args]
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(buf):
            code = self.tool.main()
        return code, buf.getvalue()

    def summary(self):
        with zipfile.ZipFile(self.out / "vf_bulk.zip") as z:
            return json.loads(z.read("summary.json")), z.namelist()

    def test_dry_run_launches_nothing(self):
        code, text = self.run_tool("--dry-run")
        self.assertEqual(code, 0, text)
        self.assertIn("preflight ok", text)
        self.assertFalse((self.out / "vf_bulk.zip").exists())
        self.assertEqual(list((self.tmp / "work").glob("*")), [])

    def test_preflight_names_every_problem_and_runs_nothing(self):
        values = json.loads(self.settings.read_text())
        values["unity"] = str(self.tmp / "no-such-unity.exe")
        self.settings.write_text(json.dumps(values))
        code, text = self.run_tool()
        self.assertEqual(code, 2)
        self.assertIn("Unity 2019.4.40f1 is not set up", text)
        self.assertIn("nothing was run", text)
        self.assertFalse((self.out / "vf_bulk.zip").exists())

    def test_a_pack_is_measured_and_zipped_and_the_rerun_resumes(self):
        code, text = self.run_tool()
        self.assertEqual(code, 0, text)
        summary, names = self.summary()
        entry = summary["packs"]["ts-260-a"]
        self.assertEqual(entry["verdict"], "OK", entry)
        self.assertGreaterEqual(entry["columnsWithColliderYs"], 1)
        for n in ("results/ts-260-a/vf-measure.json", "results/ts-260-a/result.json", "results/ts-260-a/review-questions.json",
                  "results/ts-260-a/probe__probe.json", "MANIFEST.sha256", "game-hashes.json"):
            self.assertIn(n, names)
        self.assertFalse([n for n in names if n.endswith((".bundle", ".prefab", ".dll", ".png"))])
        code, text = self.run_tool()
        self.assertEqual(code, 0)
        self.assertIn("already measured", text)
        code, text = self.run_tool("--force")
        self.assertNotIn("already measured", text)

    def test_a_failed_measure_is_reported_and_retried_never_skipped(self):
        os.environ["FAKE_UNITY_MODE"] = "vf-fail"
        code, text = self.run_tool()
        self.assertEqual(code, 1, text)
        self.assertIn("FAILED packs", text)
        self.assertEqual(self.summary()[0]["packs"]["ts-260-a"]["verdict"], "FAILED")
        os.environ.pop("FAKE_UNITY_MODE")
        code, text = self.run_tool()
        self.assertEqual(code, 0, text)
        self.assertNotIn("already measured", text)

    def test_keep_work_files_is_forced_on_in_memory_and_the_settings_file_is_untouched(self):
        values = json.loads(self.settings.read_text())
        values["keepWorkFiles"] = False
        self.settings.write_text(json.dumps(values))
        before = self.settings.read_bytes()
        code, text = self.run_tool()
        self.assertEqual(code, 0, text)
        self.assertIn("switched on for this run only", text)
        self.assertEqual(self.settings.read_bytes(), before)

    def test_only_stock_steam_packs_can_be_named(self):
        with self.assertRaises(SystemExit):
            self.run_tool("--packs", "not-a-loco")

    def test_the_script_in_the_repo_is_the_one_that_compiles_against_the_editor_api(self):
        text = (SCRIPT.parent / "VfMeasure.cs").read_text()
        self.assertIn("public static void Run()", text)
        self.assertIn("colliderYs", text)


class OilRun(BulkRun):
    """tools/vanilla/run_oil.py is run_bulk.py with VfOil.cs: same preflight, resume and failure handling."""

    def setUp(self):
        super().setUp()
        spec = importlib.util.spec_from_file_location("run_oil", SCRIPT.with_name("run_oil.py"))
        self.oil = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(SCRIPT.parent))
        self.addCleanup(sys.path.remove, str(SCRIPT.parent))
        spec.loader.exec_module(self.oil)
        self.tool = self.oil.run_bulk
        self.tool.MIN_FREE_GB = 0
        for name in ("SCRIPT", "METHOD", "OUTNAME", "OUT_PREFIX", "ZIP_NAME", "TOOL_NAME", "OUT_DEFAULT", "check_output"):
            self.addCleanup(setattr, self.tool, name, getattr(self.tool, name))
        self.oil_settings()

    def oil_settings(self):
        for name, value in (("SCRIPT", SCRIPT.with_name("VfOil.cs")), ("METHOD", "VfOil.Run"), ("OUTNAME", "vf-oil.json"),
                            ("OUT_PREFIX", "vf-oil"), ("ZIP_NAME", "vf_oil.zip"), ("TOOL_NAME", "run_oil.py")):
            setattr(self.tool, name, value)
        self.tool.check_output = self.oil.check_output

    def summary(self):
        with zipfile.ZipFile(self.out / "vf_oil.zip") as z:
            return json.loads(z.read("summary.json")), z.namelist()

    def test_a_pack_is_measured_and_zipped_and_the_rerun_resumes(self):
        code, text = self.run_tool()
        self.assertEqual(code, 0, text)
        summary, names = self.summary()
        entry = summary["packs"]["ts-260-a"]
        self.assertEqual(entry["verdict"], "OK", entry)
        self.assertEqual(summary["tool"], "run_oil.py")
        self.assertGreaterEqual(entry["mainRods"], 1)
        for n in ("results/ts-260-a/vf-oil.json", "results/ts-260-a/result.json", "results/ts-260-a/probe__probe.json", "MANIFEST.sha256"):
            self.assertIn(n, names)
        code, text = self.run_tool()
        self.assertIn("already measured", text)

    def test_the_oil_script_in_the_repo_has_its_entry_point(self):
        text = SCRIPT.with_name("VfOil.cs").read_text()
        self.assertIn("public static void Run()", text)
        self.assertIn("vf-oil.json", text)

    @unittest.skipUnless(shutil.which("mcs"), "needs the Mono C# compiler (mcs)")
    def test_the_oil_script_type_checks_against_the_unity_stand_ins(self):
        import subprocess
        stubs = SCRIPT.parent.parent.parent / "tests" / "unity_stubs" / "UnityStubs.cs"
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(["mcs", "-target:library", "-langversion:7", f"-out:{tmp}/oil.dll", str(stubs), str(SCRIPT.with_name("VfOil.cs"))],
                                  capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
