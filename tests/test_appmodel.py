"""The desktop app's logic (appmodel.Controller), without a screen."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fixtures import loco, part, standard_mod, tool_machine, write_pack
from rr2dv.appmodel import SETTINGS, Controller, blocking_issues
from rr2dv.pipeline import EXIT_INCOMPLETE


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.m = standard_mod(self.tmp)
        write_pack(self.m["search"] / "Another Loco Mod" / "a", objects=[loco("ls-460-a", parts=[part("Nope\\x", "y", "z")])],
                   assets={"ls-460-a": {"filename": "a.prefab"}})
        self.settings = self.tmp / "settings" / "machine.json"
        self.settings.parent.mkdir()
        values = tool_machine(self.tmp)
        values["python"] = str(Path(__import__("sys").executable))
        self.settings.write_text(json.dumps(values))
        self.c = Controller(self.settings)

    def test_installs_and_tools(self):
        found = self.c.installs()
        self.assertTrue(found.ready, found.problems)
        self.assertEqual((found.railroader.mods, found.ccl), (self.m["search"], True))
        self.assertEqual(self.c.tools_missing(), [])

    def test_lists_only_mods_with_steam_locomotives(self):
        seen = []
        mods = self.c.list_mods(lambda i, n: seen.append((i, n)))
        self.assertEqual([(m.folder, m.locos) for m in mods],
                         [("Another Loco Mod", [("ls-460-a", "Test ls-460-a")]), ("Test Loco Mod", [("ts-260-a", "Test ts-260-a")])])
        self.assertEqual(seen[-1][1], 3)  # TruckMod was read too, and has no locomotive

    def test_scan_gives_liveries_and_blockers(self):
        report = self.c.scan("Test Loco Mod")
        self.assertEqual(report["steam_locomotives"][0]["liveries"], [])
        self.assertEqual(blocking_issues(report, "ts-260-a"), [])
        self.assertEqual([i["code"] for i in blocking_issues(self.c.scan("Another Loco Mod"), "ls-460-a")], ["missing-part-pack"])

    def test_convert_reports_every_stage(self):
        events = []
        outcome = self.c.convert("Test Loco Mod", "ts-260-a", on_progress=lambda *e: events.append(e))
        self.assertEqual(outcome.code, EXIT_INCOMPLETE, outcome.message)
        self.assertEqual([e[0] for e in events if e[1] == "running"],
                         ["locate", "link", "stage", "extract", "import", "probe", "record"])
        self.assertEqual(events[-1][:2], (None, "incomplete"))

    def test_saving_settings_merges_and_empty_removes(self):
        self.c.save_settings({"workRoot": str(self.tmp / "w2"), "railroader": ""})
        values = json.loads(self.settings.read_text())
        self.assertEqual(values["workRoot"], str(self.tmp / "w2"))
        self.assertNotIn("railroader", values)
        self.assertIn("unity", values)
        self.assertEqual(self.c.machine.values["workRoot"], str(self.tmp / "w2"))
        self.assertEqual([k for k, *_ in SETTINGS][:3], ["unity", "carCreator", "assetRipper"])


if __name__ == "__main__":
    unittest.main()
