"""Each build gets only its own native pages, metadata and localization keys."""
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
from zipfile import ZipFile

from rr2dv import catalogue, stock
from rr2dv.audit import audit_input
from rr2dv.jsonio import read_json
from rr2dv.unityproject import check_guids


def record(loco_id):
    entry=stock.entry(loco_id)
    cfg={'CarId':'RR2DV_'+loco_id.upper().replace('-','_'),'CarName':entry['displayName'],
         'WeightEmptyKg':1,'WheelRadius':.5,'RrLevers':[],'Placed':[],'Components':[]}
    rec={'vehicleId':loco_id,'config':cfg,'metadata':{},'hooks':{'SimSpec':{}}}
    if not entry['tank']:
        rec['tender']={'config':{**cfg,'CarId':cfg['CarId']+'_TENDER','CarName':cfg['CarName']+' Tender'}}
    return rec


class Catalogue(unittest.TestCase):
    def test_all_21_builds_import_only_their_single_or_paired_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp)
            for loco_id in stock.REAL_STEAM:
                with self.subTest(loco=loco_id):
                    rec=record(loco_id)
                    before=copy.deepcopy(rec)
                    result=catalogue.prepare(project,rec)
                    self.assertEqual(rec,before,'catalogue attachment must not tune vehicle physics')
                    entry=stock.entry(loco_id)
                    wanted={loco_id} | ({entry['tender']['id']} if rec.get('tender') else set())
                    folder=project/catalogue.ASSETS
                    self.assertEqual({p.name for p in folder.iterdir() if p.is_dir()},wanted)
                    self.assertEqual({p['sourceId'] for p in result['pages']},wanted)
                    self.assertEqual({p['carId'] for p in result['pages']},
                                     {rec['config']['CarId']} | ({rec['tender']['config']['CarId']} if rec.get('tender') else set()))
                    self.assertEqual(len(list(folder.rglob('*.asset'))),len(wanted))
                    self.assertEqual(len(list(folder.rglob('*.prefab'))),len(wanted))
                    self.assertEqual(len(list(folder.rglob('*.png'))),len(wanted))
                    self.assertTrue(all(key.split('/')[2] in wanted for key in result['termKeys']))
                    self.assertEqual(check_guids(folder),len(wanted)*4)
                    manifest=read_json(project/catalogue.INPUT)
                    self.assertEqual([p['consist'] for p in manifest['pages']],['1/2','2/2'] if rec.get('tender') else ['1/1'])

    def test_unrelated_run_assets_survive_refresh_but_old_library_pages_do_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp)
            unrelated=project/'Assets/Rr2dv/BuildInput.json'
            unrelated.parent.mkdir(parents=True)
            unrelated.write_text('preserve me')
            catalogue.prepare(project,record('ls-2102-f71'))
            catalogue.prepare(project,record('ls-282-k28t'))
            self.assertFalse((project/catalogue.ASSETS/'ls-2102-f71').exists())
            self.assertEqual(unrelated.read_text(),'preserve me')

    def test_tender_count_mismatch_stops_before_copying_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec=record('ls-2102-f71'); rec.pop('tender')
            with self.assertRaisesRegex(catalogue.CatalogueError,'mapping differs'):
                catalogue.prepare(Path(tmp),rec)
            self.assertFalse((Path(tmp)/catalogue.ASSETS).exists())

    def test_damaged_asset_is_rejected_before_replacing_the_project_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            project=folder/'project'
            catalogue.prepare(project,record('ls-282-k28t'))
            source=read_json(catalogue.DATA/'index.json')
            with ZipFile(catalogue.DATA/'steam-pages.zip') as original, ZipFile(folder/'steam-pages.zip','w') as damaged:
                for name in original.namelist():
                    data=original.read(name)
                    damaged.writestr(name,data+b'changed' if name.endswith('ls-282-k28t-catalogue.asset') else data)
            (folder/'index.json').write_text(__import__('json').dumps(source))
            existing=(project/catalogue.ASSETS/'ls-282-k28t/ls-282-k28t-catalogue.asset').read_bytes()
            with mock.patch.object(catalogue,'DATA',folder), self.assertRaisesRegex(catalogue.CatalogueError,'integrity check'):
                catalogue.prepare(project,record('ls-282-k28t'))
            self.assertEqual((project/catalogue.ASSETS/'ls-282-k28t/ls-282-k28t-catalogue.asset').read_bytes(),existing)

    def test_wrong_tender_identity_stops_even_if_the_page_count_matches(self):
        index = read_json(catalogue.DATA/'index.json')
        index['locomotives']['ls-2102-f71'][1]['sourceId'] = 'lt-480-c40'
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(catalogue, 'read_json', return_value=index):
            with self.assertRaisesRegex(catalogue.CatalogueError, 'identities differ'):
                catalogue.prepare(Path(tmp), record('ls-2102-f71'))
            self.assertFalse((Path(tmp)/catalogue.ASSETS).exists())

    def test_audit_receives_exact_pages_and_text_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec=record('ls-2102-f71')
            rec['metadata']['catalogue']=catalogue.prepare(Path(tmp),rec)
            inp=audit_input(rec,Path(tmp))
            self.assertEqual(inp['cataloguePages'],rec['metadata']['catalogue']['pages'])
            self.assertEqual(inp['catalogueTermKeys'],rec['metadata']['catalogue']['termKeys'])
            self.assertEqual(len(inp['cataloguePages']),2)

    def test_synthetic_nonstock_records_do_not_get_random_stock_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(catalogue.prepare(Path(tmp),{'vehicleId':'ts-260-a'}))
            self.assertFalse((Path(tmp)/catalogue.ASSETS).exists())

    def test_only_native_steam_authoring_assets_are_bundled_with_the_app(self):
        with ZipFile(catalogue.DATA/'steam-pages.zip') as archive:
            names=archive.namelist()
        self.assertEqual(len([n for n in names if n.endswith('-catalogue.asset')]),41)
        self.assertFalse(any(n.startswith('ld-') for n in names))
        self.assertFalse(any(n.endswith(('.cs','.dll','.pdf','.anim')) for n in names))


@unittest.skipUnless(os.environ.get('RR2DV_TEST_UNITY') and os.environ.get('RR2DV_TEST_CAR_CREATOR'),
                     'set RR2DV_TEST_UNITY and RR2DV_TEST_CAR_CREATOR for native catalogue export tests')
class NativeCatalogue(unittest.TestCase):
    def test_selected_pages_survive_root_export_for_every_livery(self):
        from rr2dv.unityproject import import_unitypackage, set_project_settings, tooling_root
        from rr2dv.unityrun import run_method
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='rr2dv-cat-') as tmp:
            root = Path(tmp)
            project = root/'project'
            editor = project/'Assets/Editor'
            editor.mkdir(parents=True)
            # Use the converter's settings with the standard built-in modules needed
            # by a native bundle. No source-game project or installed mod is touched.
            manifest = project/'Packages/manifest.json'
            manifest.parent.mkdir()
            modules = ('assetbundle', 'animation', 'audio', 'physics', 'jsonserialize',
                       'imgui', 'ui', 'uielements', 'particlesystem', 'screencapture')
            manifest.write_text(json.dumps({'dependencies': {
                'com.unity.modules.'+name: '1.0.0' for name in modules}}))
            set_project_settings(project)
            import_unitypackage(Path(os.environ['RR2DV_TEST_CAR_CREATOR']), project)
            for folder in (tooling_root()/'builder/tools/unity', repo/'src/rr2dv/unity'):
                for script in folder.glob('*.cs'):
                    shutil.copy2(script, editor/script.name)
            shutil.copy2(repo/'tests/unity_runtime/CatalogueRegression.cs', editor/'CatalogueRegression.cs')
            for loco_id in ('ls-2102-f71', 'ls-282-k28t', 'ls-480-c40'):
                catalogue.prepare(root/'staging', record(loco_id))
                shutil.copytree(root/'staging'/catalogue.ASSETS, project/catalogue.ASSETS, dirs_exist_ok=True)
                selection = project/'Assets/Rr2dv'/('selection-'+loco_id+'.json')
                selection.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(root/'staging'/catalogue.INPUT, selection)
            check_guids(project/'Assets')
            output = root/'out'
            result = run_method(Path(os.environ['RR2DV_TEST_UNITY']), project, 'CatalogueRegression.Run', output,
                                {'CATALOGUE_TEST_OUT': str(output)}, timeout=600)
            self.assertEqual(result, {'passed': True, 'packs': 3, 'rootOnlyExport': True,
                                     'unrelatedPagesRejected': True, 'missingLiveryPagesRejected': True, 'exit_code': 0})


if __name__=='__main__':
    unittest.main()
