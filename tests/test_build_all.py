"""tools/vanilla/build_all.py on the fake tools: builds and audits, never installs, answers the review with the suggestions."""
import contextlib
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from fixtures import standard_mod, tool_machine
from rr2dv import review, stock

SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "vanilla" / "build_all.py"


def load():
    spec = importlib.util.spec_from_file_location("build_all", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BuildAll(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        standard_mod(self.tmp)
        patch = mock.patch.dict(stock.STEAM, {"ts-260-a": "Test loco"}, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        self.settings = self.tmp / "settings.json"
        self.settings.write_text(json.dumps(tool_machine(self.tmp)))
        self.out = self.tmp / "out"
        self.tool = load()
        self.tool.MIN_FREE_GB = 0

    def run_tool(self, *args):
        argv = ["build_all.py", "--machine", str(self.settings), "--out-dir", str(self.out), *args]
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(buf):
            code = self.tool.main()
        return code, buf.getvalue()

    def test_dry_run_launches_nothing(self):
        code, text = self.run_tool("--dry-run")
        self.assertEqual(code, 0, text)
        self.assertIn("installing: never", text)
        self.assertFalse((self.out / "vf_build.zip").exists())

    def test_the_suggested_answers_are_confirmed_unchanged(self):
        req = {k: k for k in ("schema", "adapterVersion", "vehicleId", "fingerprint", "catalogueHash")}
        req["prefill"] = {"values": {"trainBrake": "manual-lap"}}
        answer = self.tool.confirm_suggested(req)
        self.assertEqual(answer["values"], {"trainBrake": "manual-lap"})
        self.assertTrue(self.tool.confirm_suggested(req, True)["values"]["acknowledgeExperimental"])
        self.assertEqual(answer["vehicleId"], "vehicleId")
        with self.assertRaises(review.ReviewError):
            self.tool.confirm_suggested({k: k for k in req if k != "prefill"})

    def test_a_pack_is_built_audited_zipped_and_never_installed(self):
        code, text = self.run_tool()
        self.assertEqual(code, 1, "without the acknowledgement every pack stops at the review")
        self.assertIn("Acknowledge experimental", text)
        code, text = self.run_tool("--acknowledge-experimental")
        self.assertEqual(code, 0, text)
        with zipfile.ZipFile(self.out / "vf_build.zip") as z:
            summary = json.loads(z.read("summary.json"))
            names = z.namelist()
        entry = summary["packs"]["ts-260-a"]
        self.assertEqual(entry["verdict"], "BUILT", entry)
        self.assertIn("not installed", entry["why"])
        self.assertFalse(list((self.tmp / "dv" / "Mods").glob("rr2dv_*")) if (self.tmp / "dv" / "Mods").is_dir() else [])
        self.assertTrue([n for n in names if n.endswith("run.log")], names)
        code, text = self.run_tool()
        self.assertIn("already built", text)


if __name__ == "__main__":
    unittest.main()
