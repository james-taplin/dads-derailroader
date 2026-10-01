import os
import unittest
from pathlib import Path

import fixtures  # noqa: F401
from rr2dv import appdir, applog, machine


class PortableFolderTests(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in ("RR2DV_HOME", "RR2DV_LOG_DIR")}
        os.environ.pop("RR2DV_LOG_DIR", None)

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_everything_lives_in_rr2dv_work_beside_the_app(self):
        os.environ.pop("RR2DV_HOME", None)
        home = appdir.app_root() / "rr2dv_work"
        self.assertEqual(appdir.data_dir(), home)
        self.assertEqual(machine.default_path(), home / "machine.json")
        self.assertEqual(machine.default_work_root(), home / "runs")
        self.assertEqual(applog.log_dir(), home / "logs")

    def test_override(self):
        os.environ["RR2DV_HOME"] = "/x/y"
        self.assertEqual(machine.default_work_root(), Path("/x/y/runs"))


if __name__ == "__main__":
    unittest.main()
