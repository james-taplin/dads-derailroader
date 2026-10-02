import copy
import json
import os
import re
import unittest
from pathlib import Path

from rr2dv import buildrecord, gauges, stock
from rr2dv.record import component_list, env


def source_components(profile):
    return [dict(kind='Gauge', name=m['name'], pos=m['position'], rot=m['rotation'], scale=m['scale'],
                 parentPath='', extra=json.dumps(dict(style=m['style'], enabled=True))) for m in profile['sourceMounts']]


def apply(pack, components):
    cfg = dict(Components=env(copy.deepcopy(components), 'mixed', 'source', 'source definition'))
    flat = copy.deepcopy(components)
    builder = buildrecord._Builder({}, {}, {'vehicles': []}, {}, {}, {})
    builder._ensure_gauges(cfg, flat, pack)
    return cfg, flat


class FleetLayouts(unittest.TestCase):
    def test_all_21_layouts_have_their_mount_count_and_essential_readings(self):
        profiles = gauges.library()['profiles']
        self.assertEqual(set(profiles), stock.REAL_STEAM)
        counts = {2: 0, 3: 0, 4: 0}
        for pack, profile in profiles.items():
            cfg, flat = apply(pack, source_components(profile))
            instruments = [c for c in flat if c['kind']=='Gauge']
            expected = min(4, len(profile['sourceMounts']))
            self.assertEqual(len(instruments), expected, pack)
            counts[expected] += 1
            roles = [f['reading'] for f in profile['instruments']]
            self.assertEqual(roles, ['boiler', 'brake', 'speed', 'chest'][:expected], pack)
            self.assertEqual(len({c['name'] for c in instruments}), expected, pack)
            self.assertFalse(any(c['name'].startswith('rr2dv generated') for c in instruments), pack)
            for component in instruments:
                # The pinned core reads style with a compact-JSON regex, not a JSON parser.
                self.assertIsNotNone(re.search(r'"style":"([^"]*)"', component['extra']), pack)
            cfg['CarId'] = 'RR2DV_'+pack.replace('-', '_').upper()
            cfg['MainPressureGauge'] = instruments[0]['name']
            self.assertEqual(gauges.prepare(dict(vehicleId=pack, config=cfg))['instruments'], profile['instruments'])
        self.assertEqual(counts, {2: 2, 3: 7, 4: 12})

    def test_master_table_and_fitting_library_cannot_silently_disagree(self):
        for pack, profile in gauges.library()['profiles'].items():
            self.assertEqual(stock.entry(pack)['gauges']['fittings'], profile['instruments'], pack)
            self.assertEqual(stock.entry(pack)['gauges']['sourceMounts'], profile['sourceMounts'], pack)
            self.assertIn('awaiting-game-acceptance', stock.entry(pack)['gauges']['acceptance'])

    def test_a_changed_source_mount_is_refused_instead_of_using_a_stale_fit(self):
        pack = 'ls-280-c25'
        for change in ('count', 'name', 'style', 'position', 'rotation', 'scale', 'short-vector', 'nan'):
            components = copy.deepcopy(source_components(gauges.library()['profiles'][pack]))
            if change=='count': components.pop()
            elif change=='name': components[0]['name']='changed'
            elif change=='style': components[0]['extra']='{"style":"Quadruplex"}'
            elif change=='short-vector': components[0]['pos'].pop()
            elif change=='nan': components[0]['pos'][0]=float('nan')
            else: components[0][dict(position='pos', rotation='rot', scale='scale')[change]][0] += .1
            with self.subTest(change=change), self.assertRaises(gauges.GaugeError):
                apply(pack, components)

    def test_adapter_input_rejects_missing_or_nonfinite_attachments(self):
        from test_gauge_pilot import record
        import tempfile
        for support in ([], [dict(point=[0, 0, float('nan')], radial=[0, 0, 0], supportPath='mesh')]*3):
            invalid = copy.deepcopy(gauges.library())
            fit = invalid['profiles']['ls-440-a23']['instruments'][0]
            fit['supports'] = support or [{}]
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'fits.json';path.write_text(json.dumps(invalid))
                with self.assertRaises(gauges.GaugeError):gauges.prepare(record('ls-440-a23'), path)

    def test_master_refresh_rejects_changed_source_and_preserves_game_evidence(self):
        import importlib.util
        path=Path(__file__).resolve().parents[1]/'tools/vanilla/update_tuning.py'
        spec=importlib.util.spec_from_file_location('tuning_refresh', path)
        refresh=importlib.util.module_from_spec(spec);spec.loader.exec_module(refresh)
        table=copy.deepcopy(stock.table());pack='ls-280-c25'
        table['locos'][pack]['repairs']['dynamoJet']['gameAcceptance']='test evidence'
        updated=refresh.reconcile(table, gauges.library()['profiles'])
        self.assertEqual(updated['locos'][pack]['repairs']['dynamoJet']['gameAcceptance'], 'test evidence')
        table['locos'][pack]['sourceSha256']['Bundle']='0'*64
        with self.assertRaises(ValueError):refresh.reconcile(table, gauges.library()['profiles'])

    @unittest.skipUnless(os.environ.get('RR2DV_RAILROADER'), 'needs a Railroader install')
    def test_layouts_apply_to_actual_source_definitions_for_every_loco(self):
        packs = Path(os.environ['RR2DV_RAILROADER'])/'Railroader_Data/StreamingAssets/AssetPacks'
        for pack in sorted(stock.REAL_STEAM):
            data = json.loads(re.sub(r',(\s*[}\]])', r'\1', (packs/pack/'Definitions.json').read_text(encoding='utf-8-sig')))
            definition = next(o['definition'] for o in data['objects'] if o['definition']['kind']=='SteamLocomotive')
            cfg, flat = apply(pack, component_list(definition))
            expected = stock.entry(pack)['gauges']['physicalReadings']
            self.assertEqual(len([c for c in flat if c['kind']=='Gauge']), len(expected), pack)


@unittest.skipUnless(all(os.environ.get(k) for k in (
    'RR2DV_TEST_UNITY', 'RR2DV_TEST_CAR_CREATOR', 'RR2DV_TEST_DV_GAME',
    'RR2DV_PRESSURE_MESHES', 'RR2DV_FLEET_ASSEMBLY_INPUT')),
    'requires local fleet cases, Unity, Creator, DV and private donor buffers')
class NativeFleet(unittest.TestCase):
    def test_all_21_export_reload_resources_readers_and_calibration(self):
        import shutil
        import tempfile
        from test_dynamo_jets import assemble
        from rr2dv.unityrun import run_method
        repo=Path(__file__).resolve().parents[1]
        game=Path(os.environ['RR2DV_TEST_DV_GAME'])
        work=repo/'rr2dv_work';work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='fleet-gauges-', dir=work) as tmp:
            project=Path(tmp)/'project';assemble(project)
            for source in (repo/'tests/unity_runtime/FleetGaugeRegression.cs',
                           repo/'tests/unity_runtime/PressuremeterRegression.cs',
                           repo/'tools/cab-gauge-kit/GaugeProbe.cs'):
                shutil.copy2(source,project/'Assets/Editor'/source.name)
            output=Path(tmp)/'out'
            result=run_method(Path(os.environ['RR2DV_TEST_UNITY']),project,
                'CclLocoBuild.FleetGaugeRegression',output,dict(
                    CCL_BUILD_OUT=str(output),FLEET_ASSEMBLY_INPUT=os.environ['RR2DV_FLEET_ASSEMBLY_INPUT'],
                    RR2DV_GAME_MANAGED=str(game/'DerailValley_Data/Managed'),
                    RR2DV_CCL_RUNTIME=str(game/'Mods/DVCustomCarLoader'),
                    RR2DV_PRESSURE_MESHES=os.environ['RR2DV_PRESSURE_MESHES']),timeout=900)
            self.assertEqual(result,dict(passed=True,locomotives=21,instruments=73,needleSamples=282,
                                       bundleReload=True,actualCclBinding=True,gameTested=False,exit_code=0))


if __name__=='__main__':
    unittest.main()
