"""Tool discovery uses common locations without replacing paths the user chose."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rr2dv.machine import Machine
from rr2dv.toolfinder import discover


class Discovery(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        for relative in ("Games/Unity 2019.4.40f1/Editor/Unity.exe",
                         "Downloads/CarCreator_3.1.9.unitypackage",
                         "Desktop/AssetRipper/AssetRipper.GUI.Free.exe"):
            file = self.root / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            file.touch()

    def test_finds_required_tools_and_keeps_existing_python(self):
        found = discover(Machine(None, {}), {"python": sys.executable}, search_roots=[self.root])
        self.assertEqual(set(found), {"unity", "carCreator", "assetRipper"})
        self.assertEqual(Path(found["unity"]).name, "Unity.exe")
        self.assertEqual(Path(found["carCreator"]).name, "CarCreator_3.1.9.unitypackage")

    def test_existing_file_is_not_replaced(self):
        own = self.root / "Chosen" / "Unity.exe"
        own.parent.mkdir()
        own.touch()
        found = discover(Machine(None, {}), {"unity": str(own), "python": sys.executable},
                         search_roots=[self.root])
        self.assertNotIn("unity", found)

    def test_frozen_app_needs_no_external_python(self):
        with patch.object(sys, "frozen", True, create=True):
            found = discover(Machine(None, {}), {}, search_roots=[self.root])
        self.assertEqual(set(found), {"unity", "carCreator", "assetRipper"})

    def test_wrong_versions_are_ignored(self):
        wrong = self.root / "Other"
        wrong.mkdir()
        (wrong / "CarCreator_3.0.0.unitypackage").touch()
        (wrong / "Unity.exe").touch()
        found = discover(Machine(None, {}), {"python": sys.executable}, search_roots=[wrong])
        self.assertEqual(found, {})


if __name__ == "__main__":
    unittest.main()
