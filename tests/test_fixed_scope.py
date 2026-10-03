"""Restricted edition: selection and conversion cannot restore excluded content."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fixtures import loco, standard_mod, tool_machine, whistle, write_pack
from rr2dv import appmodel, installs, pipeline, rrmod, stock
from rr2dv.machine import Machine


SUPPORTED = {'ls-440-a23', 'ls-442-a26', 'ls-280-c25', 'ls-2100-d46', 'ls-2102-f71',
             'ls-260-g25', 'ls-282-k35', 'ls-462-p18', 'ls-460-t17', 'ls-460-t22'}


class FixedScope(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.m = standard_mod(self.root)
        for ident in stock.REAL_STEAM:
            write_pack(self.m['search'] / ident, objects=[loco(ident)],
                       assets={ident: {'filename': ident + '.prefab'}})
        self.whistles = self.m['search'] / stock.WHISTLE_PACK / 'Definitions.json'
        data = json.loads(self.whistles.read_text())
        data['objects'].append(whistle('wh-6-reading', 'TestChime'))
        self.whistles.write_text(json.dumps(data), encoding='utf-8')
        self.machine = Machine(None, tool_machine(self.root))

    def index(self, ident='ls-440-a23'):
        return rrmod.Index(self.m['search'] / ident, [self.m['search']])

    def test_exact_ten_supported_names_and_complete_reference(self):
        self.assertEqual(stock.SUPPORTED_STEAM, SUPPORTED)
        self.assertEqual(set(stock.STEAM) & stock.REAL_STEAM, SUPPORTED)
        self.assertEqual(stock.EXCLUDED_STEAM, stock.REAL_STEAM - SUPPORTED)
        self.assertEqual(len(stock.EXCLUDED_STEAM), 11)
        self.assertEqual(stock.validate_table(), [])

    def test_desktop_lists_only_supported_installed_stock(self):
        controller = appmodel.Controller()
        controller.machine = self.machine
        actual = {entry.folder for entry in controller.list_locos()} & stock.REAL_STEAM
        self.assertEqual(actual, SUPPORTED)

    def test_supported_packs_resolve_by_name_and_path(self):
        rr = installs.railroader(self.machine)
        for ident in SUPPORTED:
            with self.subTest(ident=ident):
                pack = self.m['search'] / ident
                self.assertEqual(installs.stock_pack(rr, ident), pack)
                self.assertEqual(installs.stock_pack(rr, pack), pack)
                inv = rrmod.inventory(self.index(ident), ident, hash_files=False)
                self.assertEqual(rrmod.blocking(inv), [])

    def test_excluded_conversions_refused_before_runs_or_tools(self):
        work = self.machine.work_root
        with patch.object(pipeline, 'extract') as extract:
            for ident in stock.EXCLUDED_STEAM:
                for target in (ident, self.m['search'] / ident):
                    with self.subTest(target=str(target)):
                        with self.assertRaisesRegex(installs.InstallError, 'not supported'):
                            pipeline.convert(target, self.machine)
            extract.assert_not_called()
        self.assertFalse(work.exists())

    def test_inventory_and_requested_identifier_cannot_bypass_scope(self):
        index = self.index()
        for ident in stock.EXCLUDED_STEAM:
            with self.subTest(ident=ident):
                inv = rrmod.inventory(index, ident, hash_files=False)
                self.assertEqual(rrmod.blocking(inv)[0]['code'], 'unsupported-locomotive')
                self.assertNotIn('parts', inv)
                chosen, why = pipeline.choose_locomotive(index, ident)
                self.assertIsNone(chosen)
                self.assertIn('not supported', why)

    def test_index_and_scan_do_not_offer_excluded_locomotives(self):
        index = rrmod.Index(self.m['search'])
        found = {obj['identifier'] for _, obj in index.steam_locomotives()} & stock.REAL_STEAM
        self.assertEqual(found, SUPPORTED)
        for ident in stock.EXCLUDED_STEAM:
            report = appmodel.scan_report(self.m['search'] / ident, [self.m['search']])
            self.assertEqual(report['steam_locomotives'], [])
            self.assertEqual(report['inventories'], {})

    def test_reading_hidden_but_other_whistles_retained(self):
        ids = {option['id'] for option in rrmod.whistle_options(self.index())}
        self.assertNotIn('wh-6-reading', ids)
        self.assertTrue({'wh-test', 'wh-other'} <= ids)

    def test_explicit_reading_refused_without_mesh_or_credit(self):
        inv = rrmod.inventory(self.index(), 'ls-440-a23', hash_files=False, whistle='wh-6-reading')
        self.assertEqual(rrmod.blocking(inv)[0]['code'], 'unsupported-whistle')
        self.assertFalse(inv['whistle']['placed'])
        self.assertFalse(any(part.get('whistle') == 'wh-6-reading' for part in inv['parts']))
        self.assertFalse(any(item['id'] == 'wh-6-reading' for item in inv['sources'][0]['contentCredits']))

    def test_source_default_reading_refused_and_supported_override_works(self):
        file = self.m['search'] / 'ls-440-a23' / 'Definitions.json'
        obj = loco('ls-440-a23', whistle='wh-6-reading')
        file.write_text(json.dumps({'objects': [obj]}), encoding='utf-8')
        inv = rrmod.inventory(self.index(), 'ls-440-a23', hash_files=False)
        self.assertEqual(rrmod.blocking(inv)[0]['code'], 'unsupported-whistle')
        inv = rrmod.inventory(self.index(), 'ls-440-a23', hash_files=False, whistle='wh-other')
        self.assertEqual(rrmod.blocking(inv), [])
        self.assertEqual(inv['whistle']['id'], 'wh-other')
        self.assertTrue(inv['whistle']['placed'])

    def test_reading_request_blocks_pipeline_before_extraction(self):
        with patch.object(pipeline, 'extract') as extract:
            outcome = pipeline.convert('ls-440-a23', self.machine, whistle='wh-6-reading')
            extract.assert_not_called()
        self.assertEqual(outcome.code, pipeline.EXIT_FAILED)
        self.assertIn('Reading 6-Chime', outcome.message)
