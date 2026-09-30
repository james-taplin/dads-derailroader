import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from fixtures import fake_assetripper, fake_carcreator, fake_tool, fake_unity, standard_mod
from rr2dv.assetripper import ExportError, export, settings_from_form
from rr2dv.jsonio import read_json, sha256_file
from rr2dv.machine import Machine
from rr2dv.pipeline import EXIT_INCOMPLETE, convert


class Form(unittest.TestCase):
    def test_form_is_submitted_like_a_browser_with_target_version_set(self):
        html = """<input name="TargetVersion" value="2022.3.0f1"><input type="checkbox" name="A" checked>
        <input type="checkbox" name="B"><input name="C" value="x" disabled><input type="submit" name="go" value="Save">
        <select name="S"><option value="1"><option value="2" selected></select>"""
        self.assertEqual(settings_from_form(html), {"TargetVersion": "2019.4.40f1", "A": "", "S": "2"})

    def test_unknown_settings_page_is_refused(self):
        with self.assertRaises(ExportError):
            settings_from_form("<input name='Other' value='1'>")


class Export(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        os.environ["FAKE_AR_STATE"] = str(self.tmp / "state")
        self.addCleanup(os.environ.pop, "FAKE_AR_STATE", None)
        self.exe = fake_assetripper(self.tmp / "tools")
        self.bundle = self.tmp / "pack" / "bundle"
        self.bundle.parent.mkdir()
        self.bundle.write_bytes(b"unity bundle")
        self.sha = sha256_file(self.bundle)
        self.cache = self.tmp / "cache"

    def exports_made(self):
        f = self.tmp / "state" / "exports.txt"
        return int(f.read_text()) if f.exists() else 0

    def test_export_then_reuse_from_cache(self):
        first = export(self.exe, self.bundle, self.sha, self.cache)
        self.assertFalse(first["cached"])
        path = Path(first["path"])
        self.assertTrue((path / "ExportedProject" / "Assets" / "PrefabInstance" / "pack.prefab").is_file())
        info = read_json(path / "export.json")
        self.assertEqual((info["bundle_sha256"], info["target"]), (self.sha, "2019.4.40f1"))
        self.assertEqual(json.loads((self.tmp / "state" / "settings.json").read_text())["TargetVersion"], "2019.4.40f1")
        second = export(self.exe, self.bundle, self.sha, self.cache)
        self.assertEqual((second["cached"], second["path"]), (True, first["path"]))
        self.assertEqual(self.exports_made(), 1)

    def test_failed_export_leaves_no_cache_entry(self):
        os.environ["FAKE_AR_FAIL"] = "1"
        self.addCleanup(os.environ.pop, "FAKE_AR_FAIL", None)
        with self.assertRaises(ExportError):
            export(self.exe, self.bundle, self.sha, self.cache)
        names = [p.name for p in self.cache.iterdir()]
        self.assertTrue(all(n.startswith(".failed-") for n in names), names)
        self.assertTrue((self.cache / names[0] / "logs" / "assetripper.log").is_file())
        del os.environ["FAKE_AR_FAIL"]
        self.assertFalse(export(self.exe, self.bundle, self.sha, self.cache)["cached"])

    def test_assetripper_that_will_not_start(self):
        broken = fake_tool(self.tmp / "tools", "broken", "#!/usr/bin/env python3\nimport sys\nsys.exit(3)\n")
        with self.assertRaisesRegex(ExportError, "exited during startup"):
            export(broken, self.bundle, self.sha, self.cache, startup_timeout=10)

    def test_assetripper_that_cannot_be_launched(self):
        bogus = self.tmp / "tools" / "not-a-program.txt"
        bogus.parent.mkdir(parents=True, exist_ok=True)
        bogus.write_text("hello")
        with self.assertRaisesRegex(ExportError, "could not be started"):
            export(bogus, self.bundle, self.sha, self.cache, startup_timeout=10)

    def test_second_conversion_reuses_every_export(self):
        m = standard_mod(self.tmp / "mods")
        machine = Machine(None, {**m["games"], "keepWorkFiles": True, "workRoot": str(self.tmp / "work"), "assetRipper": str(self.exe),
                                 "unity": str(fake_unity(self.tmp / "tools")), "carCreator": str(fake_carcreator(self.tmp / "tools" / "CarCreator_3.1.9.unitypackage"))})
        a = convert(m["mod"], machine)
        self.assertEqual(a.code, EXIT_INCOMPLETE, a.message)
        self.assertIn("4 bundle(s) exported (0 reused", a.run.record["stages"]["extract"]["detail"])
        b = convert(m["mod"], machine)
        self.assertIn("4 bundle(s) exported (4 reused", b.run.record["stages"]["extract"]["detail"])
        self.assertEqual(self.exports_made(), 4)


if __name__ == "__main__":
    unittest.main()
