import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from rr2dv import oiling, stock


def record(pack):
    profile = oiling.library()['profiles'][pack]
    return dict(vehicleId=pack, config=dict(CarId='test_'+pack,
        WheelRadius=dict(value=profile['wheelRadius']),
        EngineUnits=dict(value=[dict(DriverParts=['driver']*len(profile['axleZ']))])))


class OilFleet(unittest.TestCase):
    def test_every_stock_loco_has_a_pair_for_every_axle_and_six_to_twelve_cups(self):
        profiles = oiling.library()['profiles']
        self.assertEqual(set(profiles), stock.REAL_STEAM)
        total = 0
        for pack, profile in profiles.items():
            selection = oiling.prepare(record(pack))
            self.assertEqual(selection['points'], profile['points'], pack)
            total += len(selection['points'])
            self.assertGreaterEqual(len(selection['points']), max(6, 2*len(profile['axleZ'])))
            self.assertLessEqual(len(selection['points']), 12)
            self.assertIn('awaiting-game-acceptance', selection['state'])
            for axle in range(len(profile['axleZ'])):
                self.assertEqual([p['side'] for p in selection['points'] if p['axle']==axle], [-1, 1], pack)
            self.assertTrue(all('[anim] drivers/' in p['parentPath'] for p in selection['points']), pack)
        self.assertEqual(total, 218)

    def test_master_table_uses_the_same_numerical_fittings(self):
        for pack, profile in oiling.library()['profiles'].items():
            entry = stock.entry(pack)['oiling']
            self.assertEqual(entry['fittings'], profile['points'])
            self.assertEqual(entry['cupCount'], len(profile['points']))
            self.assertEqual(entry['drivenAxles'], len(profile['axleZ']))

    def test_stale_geometry_and_counts_are_rejected(self):
        pack = 'ls-440-a23'
        for change in ('radius', 'axles'):
            rec = record(pack)
            if change=='radius': rec['config']['WheelRadius']['value'] += .1
            else: rec['config']['EngineUnits']['value'][0]['DriverParts'].append('another')
            with self.subTest(change=change), self.assertRaises(oiling.OilingError):
                oiling.prepare(rec)
        current = oiling.library()['profiles'][pack]['sourceSha256']
        self.assertIsNotNone(oiling.prepare(record(pack), source_files=current))

    def test_source_byte_changes_reach_native_geometry_validation_for_every_loco(self):
        for pack in sorted(stock.REAL_STEAM):
            current = oiling.library()['profiles'][pack]['sourceSha256']
            for file in stock.HASHED_FILES:
                with self.subTest(pack=pack, file=file):
                    changed = dict(current, **{file:'0'*64})
                    selection = oiling.prepare(record(pack), source_files=changed)
                    self.assertEqual(selection['changedSourceFiles'], [file])
                    self.assertEqual(selection['points'], oiling.library()['profiles'][pack]['points'])
                    self.assertNotIn('changedSourceFiles', oiling.prepare(record(pack), source_files=current))
                    self.assertEqual(changed[file], '0'*64)

    def test_missing_or_invalid_input_hashes_do_not_masquerade_as_a_source_update(self):
        pack='ls-060-s23';current=oiling.library()['profiles'][pack]['sourceSha256']
        for hashes in ({}, dict(current, Bundle=None), dict(current, Bundle='invalid')):
            with self.subTest(hashes=hashes), self.assertRaisesRegex(oiling.OilingError, 'hash manifest'):
                oiling.prepare(record(pack), source_files=hashes)

    def test_changed_files_cannot_bypass_known_driver_geometry_checks(self):
        pack='ls-060-s23';current=oiling.library()['profiles'][pack]['sourceSha256']
        changed=dict(current, Bundle='0'*64)
        rec=record(pack);rec['config']['WheelRadius']['value']+=.1
        with self.assertRaisesRegex(oiling.OilingError,'Driver radius'):
            oiling.prepare(rec,source_files=changed)
        rec=record(pack);rec['config']['EngineUnits']['value'][0]['DriverParts'].append('extra')
        with self.assertRaisesRegex(oiling.OilingError,'Driven-axle count'):
            oiling.prepare(rec,source_files=changed)

    def test_missing_pairs_and_unsupported_positions_cannot_silently_disable_oiling(self):
        pack = 'ls-440-a23'
        for change in ('empty', 'five', 'thirteen', 'tag', 'side', 'axle', 'parent', 'nan', 'phase', 'source', 'missing', 'axle-nan'):
            data = copy.deepcopy(oiling.library());profile=data['profiles'][pack];point=profile['points'][0]
            if change=='empty': profile['points']=[]
            elif change=='five': profile['points']=profile['points'][:5]
            elif change=='thirteen': profile['points']+=copy.deepcopy(profile['points'][:5])
            elif change=='tag': point['tag']='oil_2L'
            elif change=='side': point['side']=1
            elif change=='axle': point['axle']=-1
            elif change=='parent': point['parentPath']=''
            elif change=='nan': point['local'][0]=float('nan')
            elif change=='phase': point['phase']=1.0
            elif change=='source': profile['sourceSha256']['Bundle']='0'*64
            elif change=='missing': del data['profiles'][pack]
            elif change=='axle-nan': profile['axleZ'][0]=float('nan')
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'fits.json';path.write_text(json.dumps(data))
                with self.subTest(change=change), self.assertRaises(oiling.OilingError):
                    oiling.prepare(record(pack), path)

    def test_returned_selection_does_not_mutate_the_library(self):
        first = oiling.prepare(record('ls-440-a23'));first['points'][0]['local'][0]=99
        self.assertNotEqual(oiling.prepare(record('ls-440-a23'))['points'][0]['local'][0], 99)


@unittest.skipUnless(all(os.environ.get(k) for k in (
    'RR2DV_TEST_UNITY', 'RR2DV_TEST_CAR_CREATOR', 'RR2DV_TEST_DV_GAME', 'RR2DV_FLEET_OIL_INPUT')),
    'requires local fleet mesh buffers, Unity, Creator and DV')
class NativeOilFleet(unittest.TestCase):
    def test_exported_anchors_ccl_ports_and_actual_dv_sync_through_forward_reverse_travel(self):
        import shutil
        from test_dynamo_jets import assemble
        from rr2dv.unityrun import run_method
        repo=Path(__file__).resolve().parents[1];game=Path(os.environ['RR2DV_TEST_DV_GAME'])
        work=repo/'rr2dv_work';work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='fleet-oil-',dir=work) as tmp:
            project=Path(tmp)/'project';assemble(project)
            for source in (repo/'tests/unity_runtime/FleetOilRegression.cs',repo/'tools/cab-gauge-kit/GaugeProbe.cs'):
                shutil.copy2(source,project/'Assets/Editor'/source.name)
            cases=json.loads(Path(os.environ['RR2DV_FLEET_OIL_INPUT']).read_text())
            for case in cases['cases']:
                case['oiling']['changedSourceFiles']=list(stock.HASHED_FILES)
            source_input=Path(tmp)/'changed-source-input.json';source_input.write_text(json.dumps(cases))
            output=Path(tmp)/'out'
            result=run_method(Path(os.environ['RR2DV_TEST_UNITY']),project,'CclLocoBuild.FleetOilRegression',output,dict(
                CCL_BUILD_OUT=str(output),FLEET_OIL_INPUT=str(source_input),
                RR2DV_GAME_MANAGED=str(game/'DerailValley_Data/Managed'),RR2DV_CCL_RUNTIME=str(game/'Mods/DVCustomCarLoader')),timeout=1200)
            self.assertEqual(result,dict(passed=True,locos=21,cups=218,motionSamples=55808,exit_code=0))


if __name__=='__main__':
    unittest.main()
