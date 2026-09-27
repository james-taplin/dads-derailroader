"""The logs we diagnose with: each run's run.log, and the app-wide rr2dv.log."""
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from fixtures import loco, part, standard_mod, tender, tool_machine
from rr2dv import applog, cli
from rr2dv.machine import Machine
from rr2dv.pipeline import EXIT_FAILED, EXIT_INCOMPLETE, convert


class Logs(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.m = standard_mod(self.tmp)
        self.machine = Machine(None, tool_machine(self.tmp))
        os.environ["RR2DV_LOG_DIR"] = str(self.tmp / "logs")
        self.addCleanup(os.environ.pop, "RR2DV_LOG_DIR", None)
        applog.reset()
        self.addCleanup(applog.reset)

    def test_run_log_tells_the_whole_run_in_order(self):
        image = {"kind": "CustomImage", "name": "logo", "textureName": "nosuchmod.logo.png"}
        (self.m["mod"] / "ts-260-a" / "Definitions.json").write_text(json.dumps({"objects": [
            loco("ts-260-a", tender="tt-260-a", parts=[part("Test Loco Mod\\parts", "bell", "bell1")], extra_components=[image]),
            tender("tt-260-a", truck="test-truck-2s")]}))
        out = convert(self.m["mod"], self.machine)
        self.assertEqual(out.code, EXIT_INCOMPLETE, out.message)
        text = (out.run.path / "run.log").read_text(encoding="utf-8")
        for expected in ("rr2dv ", "Python ", "Railroader: ", "Derail Valley: ", "input: ", "[locate] started",
                         "[link] done", "warning missing-texture: ts-260-a: image 'nosuchmod.logo.png'", "Unity result: ", "review: WheelRadius", "[build] needs_answer",
                         "run incomplete"):
            self.assertIn(expected, text)
        stages = [line.split("[")[1].split("]")[0] for line in text.splitlines() if "] started" in line]
        self.assertEqual(stages, ["locate", "link", "stage", "extract", "import", "probe", "record", "build"])

    def test_unexpected_error_keeps_its_traceback(self):
        with mock.patch("rr2dv.pipeline.inventory", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                convert(self.m["mod"], self.machine)
        run_dir = next(p for p in (self.tmp / "work").iterdir() if not p.name.startswith("_"))
        text = (run_dir / "run.log").read_text(encoding="utf-8")
        self.assertIn("unexpected error:", text)
        self.assertIn("Traceback (most recent call last)", text)
        self.assertIn("RuntimeError: boom", text)
        self.assertIn("[link] failed: RuntimeError: boom", text)

    def test_app_log_records_commands_and_bugs_with_tracebacks(self):
        settings = self.tmp / "machine.json"
        settings.write_text(json.dumps(self.machine.values))
        err = io.StringIO()
        with mock.patch("rr2dv.cli.cmd_list", side_effect=KeyError("bug")), redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = cli.main(["--machine", str(settings), "list"])
        self.assertEqual(code, EXIT_FAILED)
        self.assertIn(str(applog.log_file()), err.getvalue())
        text = applog.log_file().read_text(encoding="utf-8")
        for expected in ("command: rr2dv --machine", "unexpected error", "Traceback", "KeyError: 'bug'"):
            self.assertIn(expected, text)

    def test_logging_never_stops_the_app(self):
        blocker = self.tmp / "not-a-folder"
        blocker.write_text("x")
        os.environ["RR2DV_LOG_DIR"] = str(blocker / "logs")
        applog.reset()
        applog.get().info("goes nowhere")  # no exception


if __name__ == "__main__":
    unittest.main()
