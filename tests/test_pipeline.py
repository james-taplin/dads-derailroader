import io
import json
import sys
import shutil
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

import os

from fixtures import fake_assetripper, fake_carcreator, fake_unity, loco, standard_mod, tree_state, write_pack
from rr2dv import cli
from rr2dv.jsonio import read_json, sha256_file
from rr2dv.machine import Machine
from rr2dv.pipeline import EXIT_FAILED, EXIT_INCOMPLETE, convert
from rr2dv.runs import Run, stage_inputs
from rr2dv.rrmod import Index, inventory
from rr2dv.safety import UnsafePath


def with_fake_assetripper(test, tmp: Path) -> str:
    os.environ["FAKE_AR_STATE"] = str(tmp / "ar-state")
    test.addCleanup(os.environ.pop, "FAKE_AR_STATE", None)
    return str(fake_assetripper(tmp / "tools"))


@unittest.skipIf(sys.platform == "win32", "fake AssetRipper is a POSIX script")
class Pipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.m = standard_mod(self.tmp)
        self.machine = Machine(None, {"workRoot": str(self.tmp / "work"), "assetRipper": with_fake_assetripper(self, self.tmp),
                                      "unity": str(fake_unity(self.tmp / "tools")), "carCreator": str(fake_carcreator(self.tmp / "tools" / "CarCreator_3.1.9.unitypackage"))})
        self.out = self.tmp / "out"

    def test_convert_stages_inputs_and_never_writes_to_the_input(self):
        before = tree_state(self.tmp / "input")
        search_before = tree_state(self.m["search"])
        outcome = convert(self.m["mod"], self.out, self.machine, search=[self.m["search"]])
        self.assertEqual(outcome.code, EXIT_INCOMPLETE, outcome.message)
        self.assertEqual(tree_state(self.tmp / "input"), before)
        self.assertEqual(tree_state(self.m["search"]), search_before)
        self.assertFalse(self.out.exists())

        run = outcome.run
        stages = {k: v["status"] for k, v in run.record["stages"].items()}
        self.assertEqual([stages[s] for s in ("locate", "link", "stage", "extract", "import", "probe", "record", "build")],
                         ["done", "done", "done", "done", "done", "done", "done", "not_available"])
        self.assertEqual(read_json(run.file)["status"], "incomplete")
        self.assertEqual((run.record["answers"]["locomotive"], run.record["answers"]["audio"]["basis"]), ("ts-260-a", "S060"))
        staged = read_json(run.path / "staged.json")["files"]
        self.assertEqual(len(staged), 8)  # 3 loco pack + 2 parts pack + 3 truck pack
        for f in staged:
            self.assertEqual(sha256_file(run.path / f["file"]), f["sha256"])
        self.assertTrue((run.path / "inputs" / "search1" / "TruckMod" / "Trucks" / "Bundle").is_file())

    def test_unrelated_broken_pack_does_not_stop_convert(self):
        bad = self.m["mod"] / "k50parts"
        bad.mkdir()
        (bad / "Catalog.json").write_text('{"assets": {"x": "a\x01b"}}')
        outcome = convert(self.m["mod"], self.out, self.machine, search=[self.m["search"]])
        self.assertEqual(outcome.code, EXIT_INCOMPLETE, outcome.message)
        self.assertIn("pack-unreadable", (outcome.run.path / "index_issues.json").read_text())

    def test_same_input_same_fingerprint(self):
        a = convert(self.m["mod"], self.out, self.machine, search=[self.m["search"]]).run
        b = convert(self.m["mod"], self.out, self.machine, search=[self.m["search"]]).run
        self.assertNotEqual(a.path, b.path)
        self.assertEqual(a.record["input_fingerprint"], b.record["input_fingerprint"])

    def test_zip_input_is_extracted_into_the_run(self):
        archive = self.tmp / "mod.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            for p in sorted(self.m["mod"].rglob("*")):
                zf.write(p, p.relative_to(self.m["mod"].parent).as_posix())
        outcome = convert(archive, self.out, self.machine, search=[self.m["search"]])
        self.assertEqual(outcome.code, EXIT_INCOMPLETE, outcome.message)
        self.assertTrue((outcome.run.path / "source" / "Test Loco Mod" / "ts-260-a" / "bundle").is_file())
        self.assertEqual(outcome.run.record["request"]["input_sha256"], sha256_file(archive))

    def test_blocking_issue_stops_at_link(self):
        outcome = convert(self.m["mod"], self.out, self.machine)  # no search root: truck missing
        self.assertEqual(outcome.code, EXIT_FAILED)
        self.assertEqual(outcome.run.record["stages"]["link"]["status"], "failed")
        self.assertIn("test-truck-2s", outcome.message)
        self.assertFalse((outcome.run.path / "inputs").exists())

    def test_several_locomotives_need_a_choice(self):
        write_pack(self.m["mod"] / "ts-060-b", objects=[loco("ts-060-b")], assets={"ts-060-b": {"filename": "b.prefab"}})
        outcome = convert(self.m["mod"], self.out, self.machine, search=[self.m["search"]])
        self.assertEqual(outcome.code, EXIT_FAILED)
        self.assertIn("--loco", outcome.message)
        outcome = convert(self.m["mod"], self.out, self.machine, loco="ts-060-b", search=[self.m["search"]])
        self.assertEqual(outcome.code, EXIT_INCOMPLETE, outcome.message)
        outcome = convert(self.m["mod"], self.out, self.machine, loco="nope", search=[self.m["search"]])
        self.assertIn("not a steam locomotive", outcome.message)

    def test_refuses_output_or_work_folder_inside_protected_places(self):
        with self.assertRaises(UnsafePath):
            convert(self.m["mod"], self.m["mod"] / "out", self.machine)
        with self.assertRaises(UnsafePath):
            convert(self.m["mod"], self.tmp / "work" / "x", self.machine)
        inside = Machine(None, {"workRoot": str(self.m["mod"] / "runs"), "assetRipper": self.machine.values["assetRipper"]})
        with self.assertRaises(UnsafePath):
            convert(self.m["mod"], self.out, inside)
        dv = self.tmp / "DV" / "Mods"
        dv.mkdir(parents=True)
        guarded = Machine(None, {"workRoot": str(self.tmp / "work"), "mods": str(dv)})
        with self.assertRaises(UnsafePath):
            convert(self.m["mod"], dv, guarded)
        self.assertFalse((self.tmp / "work").exists(), "nothing may be created before the guards pass")

    def test_too_long_work_folder_is_refused_before_anything_is_created(self):
        from rr2dv.machine import max_work_root_length
        deep = self.tmp / ("w" * max_work_root_length())
        machine = Machine(None, {**self.machine.values, "workRoot": str(deep)})
        with self.assertRaisesRegex(ValueError, "workRoot"):
            convert(self.m["mod"], self.out, machine, search=[self.m["search"]])
        self.assertFalse(deep.exists())

    def test_source_changing_during_copy_stops_the_run(self):
        index = Index(self.m["mod"], [self.m["search"]])
        inv = inventory(index, "ts-260-a")
        inv["packs"][0]["files"][0]["sha256"] = "0" * 64
        run = Run.create(self.tmp / "work", "t", {})
        with self.assertRaises(RuntimeError):
            stage_inputs(run, inv, index)

    def test_unexpected_error_marks_the_run_failed(self):
        archive = self.tmp / "evil.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("../escape.txt", "x")
        with self.assertRaises(UnsafePath):
            convert(archive, self.out, self.machine)
        run_dir = next((self.tmp / "work").iterdir())
        record = read_json(run_dir / "run.json")
        self.assertEqual((record["status"], record["stages"]["locate"]["status"]), ("failed", "failed"))
        self.assertFalse((self.tmp / "escape.txt").exists())


@unittest.skipIf(sys.platform == "win32", "fake AssetRipper is a POSIX script")
class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.m = standard_mod(self.tmp)
        settings = self.tmp / "machine.json"
        settings.write_text(json.dumps({"workRoot": str(self.tmp / "work"), "searchRoots": [str(self.m["search"])],
                                        "assetRipper": with_fake_assetripper(self, self.tmp),
                                        "unity": str(fake_unity(self.tmp / "tools")), "carCreator": str(fake_carcreator(self.tmp / "tools" / "CarCreator_3.1.9.unitypackage"))}))
        self.base = ["--machine", str(settings)]

    def run_cli(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main([*self.base, *args])
        return code, buf.getvalue()

    def test_scan_reports_and_writes_json(self):
        report = self.tmp / "report.json"
        code, text = self.run_cli("scan", str(self.m["mod"]), "--json", str(report))
        self.assertEqual(code, 0, text)
        self.assertIn("ts-260-a - Test ts-260-a: ready for the next stage", text)
        self.assertIn("Reverser, Throttle", text)
        self.assertEqual(list(read_json(report)["inventories"]), ["ts-260-a"])

    def test_scan_blocked_without_search_roots(self):
        code, text = self.run_cli("scan", str(self.m["mod"]), "--no-default-search")
        self.assertEqual(code, EXIT_FAILED)
        self.assertIn("BLOCKED", text)

    def test_convert_reports_where_it_stopped(self):
        code, text = self.run_cli("convert", str(self.m["mod"]), "--out", str(self.tmp / "out"))
        self.assertEqual(code, EXIT_INCOMPLETE, text)
        self.assertIn("extract  done", text)
        self.assertIn("import   done", text)
        self.assertIn("probe    done", text)
        self.assertIn("record   done", text)
        self.assertIn("build    not_available", text)
        self.assertIn("Run folder:", text)


if __name__ == "__main__":
    unittest.main()
