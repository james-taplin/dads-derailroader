"""scripts/package_release.py: every package carries the changelog, readme, wiki and docs."""
import importlib.util
import unittest
import zipfile
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "package_release.py"


def load():
    spec = importlib.util.spec_from_file_location("package_release", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class PackageRelease(unittest.TestCase):
    def test_the_source_package_includes_the_reading_files(self):
        mod = load()
        names = {f.relative_to(mod.ROOT).as_posix() for f in mod.source_files()}
        for needed in ("CHANGELOG.md", "README.md", "LICENSE", "pyproject.toml", "Derailroader.pyw"):
            self.assertIn(needed, names)
        for folder in ("src/", "tooling/", "wiki/", "docs/"):
            self.assertTrue([n for n in names if n.startswith(folder)], folder)
        self.assertFalse([n for n in names if n.startswith(("tests/", "tools/"))])

    def test_the_windows_package_carries_them_too(self):
        mod = load()
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist" / "Derailroader"
            (dist / "_internal").mkdir(parents=True)
            (dist / "Derailroader.exe").write_bytes(b"exe")
            mod.package(dist.parent, Path(tmp) / "out")
            with zipfile.ZipFile(Path(tmp) / "out" / f"Derailroader-{mod.VERSION}-Windows.zip") as z:
                names = set(z.namelist())
        for needed in ("Derailroader/CHANGELOG.md", "Derailroader/README.md", "Derailroader/LICENSE.txt", "Derailroader/START-HERE.txt"):
            self.assertIn(needed, names)
        self.assertTrue([n for n in names if n.startswith("Derailroader/wiki/")])
        self.assertTrue([n for n in names if n.startswith("Derailroader/docs/")])


if __name__ == "__main__":
    unittest.main()
