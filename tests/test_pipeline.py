import io
import json
import sys
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock
from pathlib import Path

import os

from fixtures import fake_assetripper, fake_carcreator, fake_unity, loco, standard_mod, tree_state, write_pack
from rr2dv import cli
from rr2dv.installs import InstallError
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


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.m = standard_mod(self.tmp)
        self.machine = Machine(None, {**self.m["games"], "workRoot": str(self.tmp / "work"), "assetRipper": with_fake_assetripper(self, self.tmp),
                                      "unity": str(fake_unity(self.tmp / "tools")), "carCreator": str(fake_carcreator(self.tmp / "tools" / "CarCreator_3.1.9.unitypackage"))})
        self.out = self.tmp / "out"

    def test_convert_stages_inputs_and_never_writes_to_either_game(self):
        rr_before, dv_before = tree_state(self.tmp / "Railroader"), tree_state(self.tmp / "Derail Valley")
        outcome = convert(self.m["mod"], self.machine, search=[self.m["search"]])
        self.assertEqual(outcome.code, EXIT_INCOMPLETE, outcome.message)
        self.assertEqual(tree_state(self.tmp / "Railroader"), rr_before)
        self.assertEqual(tree_state(self.tmp / "Derail Valley"), dv_before)  # installing needs the build first

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
        outcome = convert(self.m["mod"], self.machine, search=[self.m["search"]])
        self.assertEqual(outcome.code, EXIT_INCOMPLETE, outcome.message)
        self.assertIn("pack-unreadable", (outcome.run.path / "index_issues.json").read_text())

    def test_same_input_same_fingerprint(self):
        a = convert(self.m["mod"], self.machine, search=[self.m["search"]]).run
        b = convert(self.m["mod"], self.machine, search=[self.m["search"]]).run
        self.assertNotEqual(a.path, b.path)
        self.assertEqual(a.record["input_fingerprint"], b.record["input_fingerprint"])

    def test_input_is_a_mod_in_the_railroader_mods_folder_by_name_or_path(self):
        by_name = convert("Test Loco Mod", self.machine)
        self.assertEqual(by_name.code, EXIT_INCOMPLETE, by_name.message)
        self.assertEqual(by_name.run.record["request"]["input"], str(self.m["mod"]))
        elsewhere = self.tmp / "Downloads" / "Test Loco Mod"
        shutil.copytree(self.m["mod"], elsewhere)
        archive = self.tmp / "mod.zip"
        archive.write_bytes(b"PK\x05\x06" + b"\0" * 18)
        for bad in (elsewhere, archive, self.m["mod"] / "ts-260-a", "No Such Mod"):
            with self.assertRaises(InstallError, msg=str(bad)):
                convert(bad, self.machine)
        runs = [p for p in (self.tmp / "work").iterdir() if not p.name.startswith("_")]
        self.assertEqual(len(runs), 1, "only the good run was created")

    def test_both_installs_are_needed_before_anything_starts(self):
        for missing in ("railroader", "game"):
            values = {k: v for k, v in self.machine.values.items() if k != missing}
            with self.assertRaisesRegex(InstallError, "Steam"):
                convert(self.m["mod"], Machine(None, {**values, "steamRoots": [str(self.tmp / "no-steam")]}))
        self.assertFalse((self.tmp / "work").exists())

    def test_custom_car_loader_is_needed_before_anything_starts(self):
        shutil.rmtree(self.tmp / "Derail Valley" / "Mods" / "DVCustomCarLoader")
        with self.assertRaisesRegex(InstallError, "Custom Car Loader"):
            convert(self.m["mod"], self.machine)
        self.assertFalse((self.tmp / "work").exists())

    def test_blocking_issue_stops_at_link(self):
        shutil.rmtree(self.m["mod"] / "parts")
        outcome = convert(self.m["mod"], self.machine)
        self.assertEqual(outcome.code, EXIT_FAILED)
        self.assertEqual(outcome.run.record["stages"]["link"]["status"], "failed")
        self.assertIn("parts", outcome.message)
        self.assertFalse((outcome.run.path / "inputs").exists())

    def test_several_locomotives_need_a_choice(self):
        write_pack(self.m["mod"] / "ts-060-b", objects=[loco("ts-060-b")], assets={"ts-060-b": {"filename": "b.prefab"}})
        outcome = convert(self.m["mod"], self.machine, search=[self.m["search"]])
        self.assertEqual(outcome.code, EXIT_FAILED)
        self.assertIn("--loco", outcome.message)
        outcome = convert(self.m["mod"], self.machine, loco="ts-060-b", search=[self.m["search"]])
        self.assertEqual(outcome.code, EXIT_INCOMPLETE, outcome.message)
        outcome = convert(self.m["mod"], self.machine, loco="nope", search=[self.m["search"]])
        self.assertIn("not a steam locomotive", outcome.message)

    def test_refuses_a_work_folder_inside_the_input_or_either_game(self):
        for inside in (self.m["mod"] / "runs", self.tmp / "Railroader" / "runs", self.tmp / "Derail Valley" / "runs"):
            machine = Machine(None, {**self.machine.values, "workRoot": str(inside)})
            with self.assertRaises(UnsafePath, msg=str(inside)):
                convert(self.m["mod"], machine)
            self.assertFalse(inside.exists(), "nothing may be created before the guards pass")

    def test_too_long_work_folder_is_refused_before_anything_is_created(self):
        from rr2dv.machine import max_work_root_length
        deep = self.tmp / ("w" * max_work_root_length())
        machine = Machine(None, {**self.machine.values, "workRoot": str(deep)})
        with self.assertRaisesRegex(ValueError, "workRoot"):
            convert(self.m["mod"], machine, search=[self.m["search"]])
        self.assertFalse(deep.exists())

    def test_source_changing_during_copy_stops_the_run(self):
        index = Index(self.m["mod"], [self.m["search"]])
        inv = inventory(index, "ts-260-a")
        inv["packs"][0]["files"][0]["sha256"] = "0" * 64
        run = Run.create(self.tmp / "work", "t", {})
        with self.assertRaises(RuntimeError):
            stage_inputs(run, inv, index)

    def test_unexpected_error_marks_the_run_failed(self):
        with mock.patch("rr2dv.pipeline.inventory", side_effect=RuntimeError("boom")):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                convert(self.m["mod"], self.machine)
        run_dir = next((self.tmp / "work").iterdir())
        record = read_json(run_dir / "run.json")
        self.assertEqual((record["status"], record["stages"]["link"]["status"]), ("failed", "failed"))


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.m = standard_mod(self.tmp)
        settings = self.tmp / "machine.json"
        settings.write_text(json.dumps({**self.m["games"], "workRoot": str(self.tmp / "work"),
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
        code, text = self.run_cli("scan", "Test Loco Mod", "--json", str(report))
        self.assertEqual(code, 0, text)
        self.assertIn("ts-260-a - Test ts-260-a: ready for the next stage", text)
        self.assertIn("Reverser, Throttle", text)
        self.assertEqual(list(read_json(report)["inventories"]), ["ts-260-a"])

    def test_scan_blocked_without_search_roots(self):
        code, text = self.run_cli("scan", "Test Loco Mod", "--no-default-search")
        self.assertEqual(code, EXIT_FAILED)
        self.assertIn("BLOCKED", text)

    def test_zip_or_outside_folder_is_refused(self):
        archive = self.tmp / "mod.zip"
        archive.write_bytes(b"PK\x05\x06" + b"\0" * 18)
        with redirect_stderr(io.StringIO()) as err:
            code, _ = self.run_cli("scan", str(archive))
        self.assertEqual(code, EXIT_FAILED)
        self.assertIn("Railroader Mods folder", err.getvalue())

    def test_list_shows_steam_loco_mods(self):
        code, text = self.run_cli("list")
        self.assertEqual(code, 0, text)
        self.assertIn("Test Loco Mod: ts-260-a (Test ts-260-a)", text)
        self.assertNotIn("TruckMod", text)

    def test_doctor_reports_both_installs_and_ccl(self):
        code, text = self.run_cli("doctor")
        for line in ("[ok  ] Railroader install", "[ok  ] Derail Valley Mods folder", "[ok  ] Custom Car Loader"):
            self.assertIn(line, text)

    def test_convert_reports_where_it_stopped(self):
        code, text = self.run_cli("convert", "Test Loco Mod")
        self.assertEqual(code, EXIT_INCOMPLETE, text)
        self.assertIn("extract  done", text)
        self.assertIn("import   done", text)
        self.assertIn("probe    done", text)
        self.assertIn("record   done", text)
        self.assertIn("build    not_available", text)
        self.assertIn("Run folder:", text)


if __name__ == "__main__":
    unittest.main()
