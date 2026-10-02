"""Regression cases from the October stock-steam report batch."""
import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from rr2dv.build import BuildError, _part_specs
from rr2dv.record import BASIS


class SteamLicence(unittest.TestCase):
    def test_vanilla_steam_registry_ids(self):
        # DV build 99 resources.assets: GeneralLicenseType_S060 and
        # GeneralLicenseType_SH282 contain these exact length-prefixed IDs.
        self.assertEqual(BASIS["tank"]["License"], "S060")
        self.assertEqual(BASIS["tender"]["License"], "SH282")


class WhistlePlacement(unittest.TestCase):
    def setUp(self):
        self.fitting = {"name": "Whistle", "kind": "Whistle", "parent": None,
                        "transform": {"position": [0, 4.036, -.271],
                                      "rotation": [0, 0, 0, 1], "scale": [1.1, 1.1, 1.1]}}
        self.control = {"name": "Whistle", "kind": "RadialControl",
                        "parent": {"path": ["engine", "Whistle", "Bone.010", "Bone.002"]},
                        "transform": {"position": [.779, .285, 0]}}
        self.part = {"owner": "test", "component": "Whistle mesh", "source_component": "Whistle",
                     "whistle": "test-whistle", "unity_prefab": "Assets/Whistle.prefab"}

    def test_same_named_control_never_owns_the_whistle_mesh(self):
        for comps in ([self.fitting, self.control], [self.control, self.fitting]):
            result = _part_specs("test", {"components": comps}, [self.part])[0]
            self.assertEqual(result["parentPath"], "")
            for field in ("position", "rotation", "scale"):
                self.assertEqual(result[field], self.fitting["transform"][field])

    def test_real_fitting_parent_is_preserved(self):
        self.fitting["parent"] = {"path": ["engine", "Boiler"]}
        result = _part_specs("test", {"components": [self.fitting, self.control]}, [self.part])[0]
        self.assertEqual(result["parentPath"], "engine/Boiler")

    def test_missing_or_ambiguous_fitting_cannot_silently_use_a_control(self):
        for comps in ([self.control], [self.fitting, copy.deepcopy(self.fitting), self.control]):
            with self.assertRaisesRegex(BuildError, "Whistle"):
                _part_specs("test", {"components": comps}, [self.part])


@unittest.skipUnless(os.environ.get('RR2DV_TEST_UNITY') and os.environ.get('RR2DV_TEST_CAR_CREATOR'),
                     'requires Unity and Car Creator for native steam repair export tests')
class NativeSteamRepairs(unittest.TestCase):
    def test_independent_loads_and_water_indicators_survive_export(self):
        from rr2dv.unityproject import import_unitypackage, set_project_settings, tooling_root
        from rr2dv.unityrun import run_method
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='rr2dv-steam-repair-') as tmp:
            project = Path(tmp) / 'project'
            editor = project / 'Assets/Editor'
            editor.mkdir(parents=True)
            manifest = project / 'Packages/manifest.json'
            manifest.parent.mkdir()
            modules = ('assetbundle', 'animation', 'audio', 'physics', 'jsonserialize',
                       'imgui', 'ui', 'uielements', 'particlesystem', 'screencapture')
            manifest.write_text(json.dumps({'dependencies': {
                'com.unity.modules.' + name: '1.0.0' for name in modules}}))
            set_project_settings(project)
            import_unitypackage(Path(os.environ['RR2DV_TEST_CAR_CREATOR']), project)
            for folder in (tooling_root() / 'builder/tools/unity', repo / 'src/rr2dv/unity'):
                for script in folder.glob('*.cs'):
                    shutil.copy2(script, editor / script.name)
            shutil.copy2(repo / 'tests/unity_runtime/SteamRepairRegression.cs', editor / 'SteamRepairRegression.cs')
            output = Path(tmp) / 'out'
            result = run_method(Path(os.environ['RR2DV_TEST_UNITY']), project,
                                'CclLocoBuild.SteamRepairRegression', output,
                                {'CCL_BUILD_OUT': str(output)}, timeout=600)
            self.assertEqual(result, {'passed': True, 'prefabs': 4, 'bundleReload': True, 'exit_code': 0})
