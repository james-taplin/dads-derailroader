"""W25: finding both game installs, the Railroader-Mods-only input rule, the personal-use notice and installing into
the Derail Valley Mods folder."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from fixtures import game_installs
from rr2dv import consent, installs
from rr2dv.jsonio import read_json, sha256_file
from rr2dv.machine import Machine
from rr2dv.publish import MARKER, NOTICE_FILE, PROVENANCE_FILE, InstallRefused, install
from rr2dv.safety import UnsafePath


class Detection(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def steam(self, *libraries: Path) -> Path:
        steam = self.tmp / "Steam"
        (steam / "steamapps").mkdir(parents=True, exist_ok=True)
        entries = "".join(f'\t"{i}"\n\t{{\n\t\t"path"\t\t"{str(p).replace(chr(92), chr(92) * 2)}"\n\t}}\n' for i, p in enumerate(libraries))
        (steam / "steamapps" / "libraryfolders.vdf").write_text('"libraryfolders"\n{\n' + entries + "}\n")
        return steam

    def game(self, library: Path, name: str, data: str) -> Path:
        root = library / "steamapps" / "common" / name
        (root / data).mkdir(parents=True)
        (root / "Mods").mkdir()
        return root

    def test_found_through_steam_libraries(self):
        lib = self.tmp / "SteamLibrary"
        rr = self.game(lib, "Railroader", "Railroader_Data")
        dv = self.game(self.tmp / "Steam", "Derail Valley", "DerailValley_Data")
        machine = Machine(None, {"steamRoots": [str(self.steam(lib))]})
        self.assertEqual((installs.railroader(machine).root, installs.railroader(machine).source), (rr, "steam"))
        self.assertEqual(installs.derail_valley(machine).mods, dv / "Mods")

    def test_settings_win_and_are_checked(self):
        games = game_installs(self.tmp)
        found = installs.railroader(Machine(None, games))
        self.assertEqual((found.source, found.mods), ("settings", Path(games["railroader"]) / "Mods"))
        with self.assertRaisesRegex(installs.InstallError, "no Railroader_Data"):
            installs.railroader(Machine(None, {"railroader": str(self.tmp / "nowhere")}))

    def test_missing_or_ambiguous_or_no_mods_folder(self):
        machine = Machine(None, {"steamRoots": [str(self.tmp / "no-steam")]})
        with self.assertRaisesRegex(installs.InstallError, "not found in any Steam library"):
            installs.derail_valley(machine)
        a, b = self.tmp / "LibA", self.tmp / "LibB"
        self.game(a, "Railroader", "Railroader_Data")
        self.game(b, "Railroader", "Railroader_Data")
        with self.assertRaisesRegex(installs.InstallError, "several Steam libraries"):
            installs.railroader(Machine(None, {"steamRoots": [str(self.steam(a, b))]}))
        dv = self.tmp / "DV"
        (dv / "DerailValley_Data").mkdir(parents=True)
        with self.assertRaisesRegex(installs.InstallError, "Unity Mod Manager"):
            installs.derail_valley(Machine(None, {"game": str(dv)}))

    def test_ccl_is_recognised_by_its_mod_id(self):
        games = game_installs(self.tmp)
        dv = installs.derail_valley(Machine(None, games))
        self.assertTrue(installs.ccl_installed(dv))
        shutil.rmtree(dv.mods / "DVCustomCarLoader")
        self.assertFalse(installs.ccl_installed(dv))

    def test_input_is_a_stock_steam_pack_directly_in_the_asset_packs_folder(self):
        rr = installs.railroader(Machine(None, game_installs(self.tmp)))
        pack = rr.asset_packs / "ls-282-k28t"
        pack.mkdir(parents=True)
        self.assertEqual(installs.stock_pack(rr, "ls-282-k28t"), pack)
        self.assertEqual(installs.stock_pack(rr, pack), pack)
        (rr.asset_packs / "SomeMod").mkdir()
        (rr.asset_packs / "truck.archbar.diamond").mkdir()
        (pack / "sub").mkdir()
        for bad in (pack / "sub", self.tmp, "Missing Mod", "SomeMod", "truck.archbar.diamond", "ls-460-t17",  # not installed
                    rr.asset_packs.parent, rr.asset_packs / ".." / "AssetPacks" / "SomeMod"):
            with self.assertRaises(installs.InstallError, msg=str(bad)):
                installs.stock_pack(rr, bad)

    def test_stock_diesels_are_known_but_refused(self):
        rr = installs.railroader(Machine(None, game_installs(self.tmp)))
        (rr.asset_packs / "ld-gp9").mkdir(parents=True)
        with self.assertRaisesRegex(installs.InstallError, "not supported in this release"):
            installs.stock_pack(rr, "ld-gp9")

    def test_a_folder_in_a_railroader_mods_folder_is_never_read(self):
        rr = installs.railroader(Machine(None, game_installs(self.tmp)))
        (rr.root / "Mods" / "ls-282-k28t").mkdir(parents=True)  # a mod folder carrying a stock name
        with self.assertRaises(installs.InstallError):
            installs.stock_pack(rr, "ls-282-k28t")  # the asset pack is missing: the Mods folder is not a substitute
        with self.assertRaises(installs.InstallError):
            installs.stock_pack(rr, rr.root / "Mods" / "ls-282-k28t")

    def test_railroader_needs_no_mods_folder(self):
        games = game_installs(self.tmp)
        self.assertFalse((Path(games["railroader"]) / "Mods").exists())
        self.assertEqual(installs.railroader(Machine(None, games)).source, "settings")

    @unittest.skipIf(sys.platform == "win32", "symlink creation needs privileges on Windows")
    def test_a_link_placed_in_the_asset_packs_folder_is_refused(self):
        rr = installs.railroader(Machine(None, game_installs(self.tmp)))
        real = self.tmp / "elsewhere" / "ls-282-k28t"
        real.mkdir(parents=True)
        os.symlink(real, rr.asset_packs / "ls-282-k28t")
        with self.assertRaisesRegex(installs.InstallError, "link"):
            installs.stock_pack(rr, "ls-282-k28t")


class Notice(unittest.TestCase):
    def test_ten_separate_clicks_are_needed(self):
        now = [0.0]
        counter = consent.Counter(clock=lambda: now[0])
        for i in range(consent.REQUIRED_CLICKS - 1):
            self.assertFalse(counter.click())
            now[0] += 0.3
        self.assertEqual(counter.count, 9)
        self.assertTrue(counter.click())
        self.assertEqual(consent.REQUIRED_CLICKS, 10)

    def test_rushed_clicks_do_not_count(self):
        now = [0.0]
        counter = consent.Counter(clock=lambda: now[0])
        for _ in range(50):
            counter.click()
            now[0] += 0.01
        self.assertEqual(counter.count, 2)
        self.assertFalse(counter.done)

    def test_notice_says_what_it_must(self):
        text = consent.notice_text("RR2DV_TS_260_A", ["test-loco-mod (credited: Eilelwen)", "FoxTrucks"])
        for phrase in ("PERSONAL USE ONLY", "remain with their respective rights holders",
                       "does not grant you permission to redistribute", "unless the applicable licences already permit it",
                       "may infringe copyright", "Check the permissions for every source asset",
                       "Source content detected:\n  test-loco-mod (credited: Eilelwen)\n  FoxTrucks", "10 times",
                       "notice version 1.0"):
            self.assertIn(phrase, text if "\n" in phrase else " ".join(text.split()))
        self.assertNotIn("illegal", text)  # James, 2026-09-27: only claims the tool can stand behind

    def test_changed_wording_needs_a_new_notice_version(self):
        self.assertEqual((consent.NOTICE_VERSION, consent.TEMPLATE_SHA256),
                         ("1.0", "387b127795393d40d536bc6101b070a04210b5cd2ffa72db1fe7ef7803d9c838"),
                         "the notice text changed: bump NOTICE_VERSION and update the pinned hash here")


class Install(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.dv = installs.derail_valley(Machine(None, game_installs(self.tmp)))
        self.pack = self.tmp / "build" / "RR2DV_TEST"
        self.pack.mkdir(parents=True)
        (self.pack / "Info.json").write_text('{"Id": "RR2DV_TEST"}')
        (self.pack / "ccl_bundle").write_bytes(b"bundle")
        (self.pack / "build_notes.txt").write_text("not installed")
        self.expected = {n: sha256_file(self.pack / n) for n in ("Info.json", "ccl_bundle")}
        self.asked = []

    def agree(self, pack, credits):
        self.asked.append((pack, list(credits)))
        return True

    SOURCES = [{"id": "test-loco-mod", "kind": "mod", "root": "input", "path": "", "credits": ["Test Author"]},
               {"id": "Railroader (base game asset packs)", "kind": "game", "root": "", "path": "", "credits": [],
                "packs": ["truck.archbar.diamond"]}]

    def run_install(self, ask=None):
        dest, record = install(self.pack, self.dv, self.expected, self.SOURCES,
                               {"run": "r1", "input": "Mods/Test Loco Mod", "locomotive": "ts-260-a"}, ask or self.agree)
        self.record = record
        return dest

    def leftovers(self):
        return [p.name for p in self.dv.mods.iterdir() if p.name.startswith(".rr2dv-")]

    def test_installs_the_files_with_notice_and_marker_after_consent(self):
        dest = self.run_install()
        self.assertEqual(dest, self.dv.mods / "rr2dv_RR2DV_TEST")  # every rr2dv pack sorts together (James, 2026-09-29)
        self.assertEqual(sorted(p.name for p in dest.iterdir()), ["Info.json", NOTICE_FILE, PROVENANCE_FILE, "ccl_bundle", MARKER])
        marker = read_json(dest / MARKER)
        self.assertEqual((marker["generator"], marker["clicks"], marker["notice_version"]), ("rr2dv", 10, "1.0"))
        self.assertEqual(marker["sources"], self.SOURCES)
        self.assertEqual(self.record["acknowledged"], marker["acknowledged"])
        provenance = (dest / PROVENANCE_FILE).read_text()
        for line in ("Notice version: 1.0", "Acknowledged: " + marker["acknowledged"], "Source content detected:",
                     "  - test-loco-mod (credited: Test Author) [input]", "  - Railroader (base game asset packs)\n",
                     "      truck.archbar.diamond", "Converted from: Mods/Test Loco Mod (locomotive ts-260-a)"):
            self.assertIn(line, provenance)
        self.assertIn("PERSONAL USE ONLY", (dest / NOTICE_FILE).read_text())
        self.assertEqual(self.asked, [("RR2DV_TEST", ["test-loco-mod (credited: Test Author)", "Railroader (base game asset packs)"])])
        self.assertEqual(self.leftovers(), [])

    def test_declined_notice_installs_nothing(self):
        with self.assertRaisesRegex(InstallRefused, "not agreed"):
            self.run_install(ask=lambda pack, credits: False)
        self.assertFalse((self.dv.mods / "rr2dv_RR2DV_TEST").exists())
        self.assertEqual(self.leftovers(), [])

    def test_retires_its_own_unprefixed_install_of_the_same_loco_only(self):
        dest = self.run_install()
        legacy = self.dv.mods / "RR2DV_TEST"
        os.rename(dest, legacy)  # as installed before the prefix
        other = self.dv.mods / "Other"
        shutil.copytree(legacy, other)  # ours, but a different loco under another name: kept
        dest = self.run_install()
        self.assertTrue(dest.is_dir())
        self.assertFalse(legacy.exists())
        self.assertEqual(self.record["replacedFolder"], "RR2DV_TEST")
        self.assertTrue(other.is_dir())
        legacy.mkdir()
        (legacy / "Info.json").write_text("someone else's mod")  # not ours: never touched
        self.run_install()
        self.assertEqual((legacy / "Info.json").read_text(), "someone else's mod")
        self.assertEqual(self.leftovers(), [])

    def test_replaces_only_its_own_earlier_conversion(self):
        self.run_install()
        (self.pack / "ccl_bundle").write_bytes(b"new bundle")
        self.expected["ccl_bundle"] = sha256_file(self.pack / "ccl_bundle")
        dest = self.run_install()
        self.assertEqual((dest / "ccl_bundle").read_bytes(), b"new bundle")
        self.assertEqual(len(self.asked), 2, "the notice is shown every time")
        self.assertEqual(self.leftovers(), [])

    def test_never_touches_another_mods_folder(self):
        other = self.dv.mods / "rr2dv_RR2DV_TEST"
        other.mkdir()
        (other / "Info.json").write_text("someone else's mod")
        with self.assertRaisesRegex(InstallRefused, "not made by rr2dv"):
            self.run_install()
        self.assertEqual((other / "Info.json").read_text(), "someone else's mod")
        self.assertEqual(self.asked, [], "no notice for an install that cannot happen")

    def test_failed_copy_keeps_the_previous_conversion(self):
        self.run_install()
        bad = dict(self.expected, ccl_bundle="0" * 64)
        with self.assertRaises(ValueError):
            install(self.pack, self.dv, bad, self.SOURCES, {}, self.agree)
        self.assertEqual((self.dv.mods / "rr2dv_RR2DV_TEST" / "ccl_bundle").read_bytes(), b"bundle")
        self.assertEqual(self.leftovers(), [])

    def test_refuses_odd_names(self):
        with self.assertRaises(UnsafePath):
            install(self.pack, self.dv, {"../Info.json": "x"}, [], {}, self.agree)
        with self.assertRaises(UnsafePath):
            install(self.pack, self.dv, {MARKER: "x"}, [], {}, self.agree)
        with self.assertRaises(UnsafePath):
            install(self.pack, self.dv, {PROVENANCE_FILE: "x"}, [], {}, self.agree)


if __name__ == "__main__":
    unittest.main()
