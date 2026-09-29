"""The desktop app's logic (appmodel.Controller), without a screen."""
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
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

    def test_lists_base_game_locomotive_packs_after_the_mods(self):
        # 0.3 (James): Railroader's own locomotive packs (AssetPacks/<pack>: Bundle, Catalog.json, Definitions.json)
        packs = self.tmp / "Railroader" / "Railroader_Data" / "StreamingAssets" / "AssetPacks"
        write_pack(packs / "ls-282-k28t", objects=[loco("ls-282-k28t")], assets={"ls-282-k28t": {"filename": "k28t.prefab"}})
        write_pack(packs / "truck.archbar.diamond", assets={"t": {"filename": "t.prefab"}})
        mods = self.c.list_mods()
        base = [m for m in mods if m.base]
        self.assertEqual([(m.label, m.locos) for m in base], [("ls-282-k28t", [("ls-282-k28t", "Test ls-282-k28t")])])
        self.assertEqual(Path(base[0].folder), packs / "ls-282-k28t")
        self.assertFalse(any(m.base for m in mods[:-1]))
        report = self.c.scan(base[0].folder)  # the full path is what the window hands on
        self.assertEqual([l["id"] for l in report["steam_locomotives"]], ["ls-282-k28t"])

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
                         ["locate", "link", "stage", "extract", "import", "probe", "record", "build"])
        self.assertEqual(events[-1][:2], (None, "incomplete"))

    def test_geometry_reviews_lists_only_what_the_build_would_accept(self):
        # RLW RXM-1B, 2026-09-29: the box should offer the runs' reviews that fit, newest first, not only Browse
        from rr2dv import installs
        from rr2dv.pipeline import fingerprint, search_roots
        from rr2dv.rrmod import Index, inventory
        rr = installs.railroader(self.c.machine)
        index = Index(installs.mod_in_railroader(rr, "Test Loco Mod"), search_roots(rr, self.c.machine.search_roots()))
        fp = fingerprint(inventory(index, "ts-260-a"))

        def review(run, name, band, fprint=fp, vid="ts-260-a"):
            path = self.c.reports() / run / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"schema": 1, "inputFingerprint": fprint, "vehicles": {vid: {"EndBeamProbeHeight": {
                "value": band, "unit": "m", "basis": "measured", "evidence": ["survey"]}}}}))
            return str(path)
        self.assertEqual(self.c.geometry_reviews("Test Loco Mod", "ts-260-a"), [])
        old = review("20260929-190000-ts", "geometry-review-proposed.json", [1.4, 1.6])
        review("20260929-191000-ts", "geometry-review.json", [1.4, 1.6])  # the same band used again: listed once
        new = review("20260929-192000-ts", "geometry-review-proposed.json", [1.0, 1.2])
        review("20260929-193000-ts", "geometry-review-proposed.json", [1.0, 1.2], fprint="other source")
        review("20260929-194000-ts", "geometry-review-proposed.json", [1.0, 1.2], vid="another-loco")
        found = self.c.geometry_reviews("Test Loco Mod", "ts-260-a")
        self.assertEqual([r["path"] for r in found], [new, review("20260929-191000-ts", "geometry-review.json", [1.4, 1.6])])
        self.assertIn("loco 1.00..1.20 m", found[0]["label"])
        self.assertNotIn(old, [r["path"] for r in found])  # older copy of the same band

    def test_saving_settings_merges_and_empty_removes(self):
        self.c.save_settings({"workRoot": str(self.tmp / "w2"), "railroader": ""})
        values = json.loads(self.settings.read_text())
        self.assertEqual(values["workRoot"], str(self.tmp / "w2"))
        self.assertNotIn("railroader", values)
        self.assertIn("unity", values)
        self.assertEqual(self.c.machine.values["workRoot"], str(self.tmp / "w2"))
        self.assertEqual([k for k, *_ in SETTINGS][:3], ["unity", "carCreator", "assetRipper"])

    def test_check_previews_unsaved_tool_path(self):
        candidate = self.tmp / "Unity 2019.4.40f1" / "Unity.exe"
        candidate.parent.mkdir()
        candidate.touch()
        checks = self.c.checks({"unity": str(candidate)})
        unity = next(check for check in checks if check.name == "Unity Editor")
        self.assertEqual(unity.status, "ok")
        self.assertEqual(unity.detail, str(candidate))
        self.assertNotEqual(json.loads(self.settings.read_text())["unity"], str(candidate))

    def test_frozen_app_uses_bundled_python(self):
        self.c.machine.values.pop("python")
        with patch.object(__import__("sys"), "frozen", True, create=True):
            self.assertFalse(any("Python" in label for label in self.c.tools_missing()))
            python = next(check for check in self.c.checks() if check.name == "tooling Python")
        self.assertEqual(python.status, "ok")
        self.assertIn("included", python.detail)


if __name__ == "__main__":
    unittest.main()
