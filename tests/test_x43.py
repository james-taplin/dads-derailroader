"""Regression cases from X43; synthetic inputs only."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rr2dv import buildrecord, cli, probeinput


class X43(unittest.TestCase):
    def test_geometry_review_rejects_stale_sources_and_unsafe_or_unproven_fields(self):
        import copy
        from rr2dv.geometryreview import validate
        good = {'schema': 1, 'inputFingerprint': 'source-hash', 'vehicles': {'x': {
            'EndBeamProbeHeight': {'value': [1.0, 1.2], 'unit': 'm', 'basis': 'derived',
                                   'evidence': ['measured broad face at y 1.0..1.2']}}}}
        self.assertEqual(validate(good, 'source-hash', {'x'}), good)
        bad = []
        for value in ([1.2, 1.0], [0, 3], [1, 1.01], [float('nan'), 1.2], [True, 1.2]):
            d = copy.deepcopy(good)
            d['vehicles']['x']['EndBeamProbeHeight']['value'] = value
            bad.append(d)
        for field, value in [('evidence', []), ('basis', 'analogue_estimate'), ('unit', 'ft')]:
            d = copy.deepcopy(good)
            d['vehicles']['x']['EndBeamProbeHeight'][field] = value
            bad.append(d)
        d = copy.deepcopy(good)
        d['vehicles']['x']['HideFrontCoupler'] = True
        bad.append(d)
        for d in bad:
            with self.subTest(d=d), self.assertRaises(ValueError):
                validate(d, 'source-hash', {'x'})
        with self.assertRaises(ValueError):
            validate(good, 'changed-source', {'x'})
        with self.assertRaises(ValueError):
            validate(good, 'source-hash', {'another-car'})

    def test_audit_keeps_text_manifests_out_of_bundle_loader(self):
        from rr2dv.audit import audit_input
        rec = {"config": {"CarId": "X", "CarName": "X", "WeightEmptyKg": 1, "WheelRadius": .5}}
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp)
            for name in ('Info.json', 'ccl_bundle', 'ccl_bundle.manifest', 'X', 'X.manifest'):
                (pack / name).touch()
            self.assertCountEqual([Path(p).name for p in audit_input(rec, pack)['bundles']], ['X', 'ccl_bundle'])

    def test_nested_load_animation_is_created_before_its_parent(self):
        b = buildrecord._Builder({}, {}, {"vehicles": []}, {}, {}, {})
        parent = ['Door', '', 'fireboxDoor.EXT_IN', False]
        child = ['Latch', '', 'fireboxDoor.EXT_IN', False]
        ov = {"clips": [{"key": "Door", "poses": [{"path": "Main/Door"}]},
                        {"key": "Latch", "poses": [{"path": "Main/Door/Latch"}]}]}
        self.assertEqual(b._ordered_loads([parent, child], ov), [child, parent])
        self.assertEqual(b.blocks, [])
        ov['clips'][0]['poses'].append({"path": "Main/Other/Child"})
        ov['clips'][1]['poses'].append({"path": "Main/Other"})
        b._ordered_loads([parent, child], ov)
        self.assertEqual(b.blocks[0]['code'], 'animation-order')

    def test_driver_prompt_never_falls_back_to_pilot(self):
        definition = {"mainDriverIndex": 1, "wheelsets": [{"diameter": .69}, {"diameter": 1.09}]}
        wheels = [{"clip": "Pilot"}, {"clip": "Drivers"}]
        pilot = {"clip": "Pilot", "tread": .34589}
        driver = {"clip": "Drivers", "tread": .48432}
        self.assertEqual(buildrecord.driving_candidate([pilot, driver], wheels, definition), driver)
        self.assertIsNone(buildrecord.driving_candidate([pilot], wheels, definition))
        self.assertIsNone(buildrecord.driving_candidate([pilot, driver], wheels, {}))

    def test_rerun_keeps_global_machine_option_before_subcommand(self):
        args = cli.build_parser().parse_args(['--machine', 'C:/private config/machine.json', 'convert',
                                              'Test Mod', '--loco', 'test', '--geometry-review', 'C:/review.json'])
        run = SimpleNamespace(record={"blocks": [{"code": "needs-wheel-radius", "candidate": .48432}]})
        with patch.object(cli.machine_mod, 'load', return_value=SimpleNamespace(search_roots=lambda: [])), \
             patch.object(cli, 'convert', return_value=SimpleNamespace(run=run, code=3, message='review')), \
             patch.object(cli, '_print_run'), contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(cli.cmd_convert(args), 3)
        self.assertIn(f'rr2dv --machine "{args.machine}" convert "Test Mod" --loco test', stdout.getvalue())
        self.assertIn(f'--geometry-review "{args.geometry_review}"', stdout.getvalue())

    def test_renderer_material_route_ignores_non_renderer_references(self):
        guid, other = 'a' * 32, 'b' * 32
        with tempfile.TemporaryDirectory() as tmp:
            prefab = Path(tmp) / 'model.prefab'
            prefab.write_text(f'''%YAML 1.1
--- !u!23 &10
MeshRenderer:
  m_Materials:
  - {{fileID: 2100000, guid: {guid}, type: 2}}
  - {{fileID: 0}}
  m_Other: {{guid: {other}}}
--- !u!137 &11
SkinnedMeshRenderer:
  m_Materials:
  - {{fileID: 2100000, guid: {guid}, type: 2}}
--- !u!114 &12
MonoBehaviour:
  m_Materials:
  - {{fileID: 2100000, guid: {other}, type: 2}}
''')
            self.assertEqual(probeinput.renderer_materials(prefab, {guid: 'Assets/paint.mat'}),
                             [{"key": 'renderer:' + guid, "asset": 'Assets/paint.mat', "guid": guid}])
            self.assertEqual(probeinput.renderer_materials(prefab, {})[0]['asset'], '')

    def test_renderer_route_does_not_guess_livery_colours(self):
        b = buildrecord._Builder({}, {}, {"vehicles": [{"id": "x", "materialMode": "renderer-untinted"}]}, {}, {}, {})
        b._material_review({"Liveries": [["Red", [["base", "ff0000"]]]]}, 'x')
        self.assertEqual(b.blocks[0]['code'], 'untinted-livery')
        b.blocks.clear()
        b._material_review({"Liveries": [["Default", []]]}, 'x')
        self.assertEqual(b.blocks, [])
        self.assertIn('No livery colours invented', b.choices[0])

    def test_car_space_handle_requires_one_nearby_animated_hierarchy(self):
        comp = {"kind": "RadialControl", "name": "Throttle", "parentPath": "",
                "extra": json.dumps({"purpose": "Throttle", "radius": .3, "animation": {"clipName": "Throttle"}})}
        ov = {"nodes": [{"path": "engine/handle", "position": [0, 2, -2]}],
              "anchors": [{"name": "Throttle", "resolved": True, "position": [0, 2.1, -2]}],
              "clips": [{"key": "Throttle", "poses": [{"path": "engine/handle"}, {"path": "engine/handle/rod"}]}]}
        b = buildrecord._Builder({}, {}, {"vehicles": []}, {}, {}, {})
        levers = b._levers({}, [comp], ov, {"Throttle": "x"}, 'test')[0]
        self.assertEqual(levers[0]['Path'], 'engine/handle')
        ov['clips'][0]['poses'].append({"path": "engine/remote"})
        self.assertEqual(b._levers({}, [comp], ov, {"Throttle": "x"}, 'test')[0], [])
        ov['clips'][0]['poses'].pop()
        ov['anchors'][0]['position'] = [0, 3, -2]
        self.assertEqual(b._levers({}, [comp], ov, {"Throttle": "x"}, 'test')[0], [])

    def test_blocked_preparation_preserves_choices_without_a_completed_record(self):
        from rr2dv import build
        draft = {"vehicleId": "x", "config": {"CarId": "X"}, "metadata": {"pending": ['runtime']}}
        with tempfile.TemporaryDirectory() as tmp, patch.object(build, 'definitions', return_value={}), \
             patch.object(buildrecord, 'complete', side_effect=buildrecord.Blocked(
                 [{"code": "needs-wheel-radius", "message": "review"}], ['analogue estimate'])):
            with self.assertRaises(buildrecord.Blocked):
                build.prepare(Path(tmp), {}, {}, {}, {"parts": []}, draft, {}, [])
            review = json.loads((Path(tmp) / 'build/review.json').read_text())
            self.assertEqual(review['choices'], ['analogue estimate'])
            self.assertEqual(review['status'], 'blocked')
            self.assertFalse((Path(tmp) / 'build/vehicle-record.json').exists())
