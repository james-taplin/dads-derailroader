import os
import shutil
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from rr2dv.jsonio import sha256_file
from rr2dv.machine import Machine, doctor, load
from rr2dv.publish import publish
from rr2dv.safety import UnsafePath, safe_extract_zip


class Zip(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def archive(self, entries, symlink=None):
        path = self.tmp / f"a{len(list(self.tmp.iterdir()))}.zip"
        with zipfile.ZipFile(path, "w") as zf:
            for name, data in entries:
                zf.writestr(name, data)
            if symlink:
                info = zipfile.ZipInfo(symlink)
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                zf.writestr(info, "/etc/passwd")
        return path

    def test_normal_archive(self):
        written = safe_extract_zip(self.archive([("mod/a.json", "{}"), ("mod/sub/b", "x")]), self.tmp / "out")
        self.assertEqual(sorted(p.relative_to(self.tmp / "out").as_posix() for p in written), ["mod/a.json", "mod/sub/b"])

    def test_rejects_unsafe_entries_and_writes_nothing(self):
        for entries, link in ([("../x", "1")], None), ([("/abs", "1")], None), ([("C:/x", "1")], None), \
                             ([("a/../../x", "1")], None), ([("A.txt", "1"), ("a.TXT", "2")], None), ([], "mod/link"), \
                             ([("mod/CON.txt", "1")], None), ([("mod/file.txt:stream", "1")], None), ([("mod/trailing. ", "1")], None):
            dest = self.tmp / f"dest{len(list(self.tmp.iterdir()))}"
            with self.subTest(entries=entries, link=link), self.assertRaises(UnsafePath):
                safe_extract_zip(self.archive(entries, link), dest)
            self.assertFalse(dest.exists() and any(dest.iterdir()))
        self.assertFalse((self.tmp.parent / "x").exists())

    def test_refuses_non_empty_destination(self):
        dest = self.tmp / "dest"
        dest.mkdir()
        (dest / "keep").write_text("mine")
        with self.assertRaises(UnsafePath):
            safe_extract_zip(self.archive([("a", "1")]), dest)
        self.assertEqual((dest / "keep").read_text(), "mine")


class Publish(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.pack = self.tmp / "build" / "Test Pack"
        self.pack.mkdir(parents=True)
        (self.pack / "Info.json").write_text('{"Id": "TEST"}')
        (self.pack / "ccl_bundle").write_bytes(b"bundle")
        (self.pack / "build_notes.txt").write_text("not published")
        self.expected = {n: sha256_file(self.pack / n) for n in ("Info.json", "ccl_bundle")}
        self.out = self.tmp / "out"

    def leftovers(self):
        return [p.name for p in self.out.iterdir() if p.name.startswith(".rr2dv-stage")] if self.out.exists() else []

    def test_publishes_exactly_the_expected_files(self):
        dest = publish(self.pack, self.out, self.expected, [])
        self.assertEqual(sorted(p.name for p in dest.iterdir()), ["Info.json", "ccl_bundle"])
        self.assertEqual(self.leftovers(), [])

    def test_never_overwrites(self):
        publish(self.pack, self.out, self.expected, [])
        (self.out / "Test Pack" / "Info.json").write_text("user edit")
        with self.assertRaises(FileExistsError):
            publish(self.pack, self.out, self.expected, [])
        self.assertEqual((self.out / "Test Pack" / "Info.json").read_text(), "user edit")

    def test_hash_mismatch_leaves_nothing_behind(self):
        bad = dict(self.expected, ccl_bundle="0" * 64)
        with self.assertRaises(ValueError):
            publish(self.pack, self.out, bad, [])
        self.assertFalse((self.out / "Test Pack").exists())
        self.assertEqual(self.leftovers(), [])

    def test_refuses_protected_targets_and_odd_names(self):
        with self.assertRaises(UnsafePath):
            publish(self.pack, self.tmp / "DV" / "Mods", self.expected, [("Derail Valley Mods folder", self.tmp / "DV" / "Mods")])
        with self.assertRaises(UnsafePath):
            publish(self.pack, self.out, {"../Info.json": "x"}, [])
        self.assertFalse(self.out.exists())

    @unittest.skipIf(sys.platform == "win32", "symlink creation needs privileges on Windows")
    def test_refuses_linked_output_folder(self):
        real = self.tmp / "real"
        real.mkdir()
        os.symlink(real, self.out)
        with self.assertRaises(UnsafePath):
            publish(self.pack, self.out, self.expected, [])


class MachineSettings(unittest.TestCase):
    def test_llw_machine_file_loads_and_derives_search_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            rr = tmp / "Railroader"
            (rr / "Mods").mkdir(parents=True)
            settings = tmp / "machine.local.json"
            settings.write_text('{"schema": 1, "python": "%s", "railroader": "%s", "mods": "", "workRoot": "%s"}'
                                % (sys.executable.replace("\\", "/"), rr.as_posix(), (tmp / "w").as_posix()))
            m = load(settings)
            self.assertEqual(m.search_roots(), [rr / "Mods", rr / "Railroader_Data" / "StreamingAssets" / "AssetPacks"])
            self.assertEqual([label for label, _ in m.protected()], ["Railroader install"])
            results = {c.name: c.status for c in doctor(m)}
            self.assertEqual(results["tooling Python"], "ok")
            self.assertEqual(results["Unity Editor"], "fail")
            self.assertEqual(results["work folder"], "ok")

    def test_search_roots_accepts_a_single_string(self):
        self.assertEqual(Machine(None, {"searchRoots": "D:/RR/Mods"}).search_roots(), [Path("D:/RR/Mods")])
        self.assertEqual(Machine(None, {"searchRoots": 5}).search_roots(), [])

    def test_work_folder_path_length(self):
        # X29: build the boundary from a real absolute root and check the fully assembled longest path.
        import os
        from rr2dv.machine import LONGEST_PROJECT_PATH, WINDOWS_MAX_PATH, check_work_root, max_work_root_length
        from rr2dv.runs import RUN_ID_MAX
        base = os.path.realpath(tempfile.gettempdir())
        limit = max_work_root_length()

        def root_of(length):
            return Path(base) / ("x" * (length - len(base) - 1))

        def assembled(root):
            return os.path.realpath(root) + "/" + "r" * RUN_ID_MAX + "/unity/project/" + LONGEST_PROJECT_PATH

        at_limit = root_of(limit)
        self.assertEqual(len(assembled(at_limit)), WINDOWS_MAX_PATH)
        check_work_root(at_limit)
        with self.assertRaisesRegex(ValueError, "at most"):
            check_work_root(root_of(limit + 1))
        self.assertEqual(limit, 74)

    def test_missing_settings_file_is_empty_not_an_error(self):
        m = load(Path(tempfile.gettempdir()) / "no-such-rr2dv-settings.json")
        self.assertIsNone(m.source)
        self.assertEqual(m.search_roots(), [])


if __name__ == "__main__":
    unittest.main()
