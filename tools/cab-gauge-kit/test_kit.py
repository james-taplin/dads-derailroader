import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

spec=importlib.util.spec_from_file_location('kit',Path(__file__).with_name('run.py'))
kit=importlib.util.module_from_spec(spec);spec.loader.exec_module(kit)


class KitTests(unittest.TestCase):
    def test_fleet_has_21_unique_locos(self):
        self.assertEqual(len(set(kit.IDS)),21)

    def test_export_never_includes_geometry_or_private_inputs(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            for name in ('report.html','gauges.csv','summary.json','result.json','input.json','unity.log','secret.bin','failure.txt'):
                (p/name).write_text('test')
            kit.results_zip(p)
            with ZipFile(p/'gauge-results.zip') as z:
                self.assertEqual(set(z.namelist()),{'report.html','gauges.csv','summary.json','result.json'})

    def test_failed_inspection_not_reported_as_pass(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            (p/'result.json').write_text(json.dumps(dict(completed=False,findings=[dict(id='k35',error='<missing>',gauges=[])])))
            s=kit.report(p)
            self.assertFalse(s['completed'])
            self.assertEqual(s['gauges'],0)
            self.assertIn('&lt;missing&gt;',(p/'report.html').read_text())

    def test_kit_archive_roundtrip_excludes_unlisted_files(self):
        spec=importlib.util.spec_from_file_location('pack',Path(__file__).with_name('package.py'))
        pack=importlib.util.module_from_spec(spec);spec.loader.exec_module(pack)
        with tempfile.TemporaryDirectory() as t:
            p=Path(t); pack.HERE=p
            for name in pack.SOURCE:
                (p/name).write_text('synthetic fixture')
            (p/'game-mesh.bin').write_bytes(b'not distributable')
            pack.package(p/'kit.zip')
            with ZipFile(p/'kit.zip') as z:
                self.assertEqual(set(z.namelist()),{'Cab-Gauge-Kit/'+n for n in pack.SOURCE}|{'Cab-Gauge-Kit/SHA256.json'})
            with self.assertRaises(ValueError): pack.package(p/'kit.zip')


if __name__=='__main__': unittest.main()
