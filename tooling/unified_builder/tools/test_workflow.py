import json, tempfile, unittest
from pathlib import Path
from catalog import read_def, make_record, CAT, wheel_role
from resolve_clip_paths import select_mapping, resolve

class Workflow(unittest.TestCase):
    def test_ambiguous_prefab_tie_rejected(self):
        with self.assertRaises(ValueError): select_mapping({1},[('a',{1:{'Main/Rod'}}),('b',{1:{'Tender/Main/Rod'}})])
    def test_identical_mapping_tie_allowed(self):
        self.assertEqual(select_mapping({1},[('a',{1:{'Rod'}}),('b',{1:{'Rod'}})]),{1:'Rod'})
    def test_duplicate_paths_rejected(self):
        with self.assertRaises(ValueError):select_mapping({1},[('a',{1:{'a/Rod','b/Rod'}})])
    def test_unresolved_rejected(self):
        with self.assertRaises(ValueError):select_mapping({1,2},[('a',{1:{'Rod'}})])
    def test_explicit_prefab_binding(self):
        self.assertEqual(select_mapping({1},[('a',{1:{'Rod'}}),('b',{1:{'Tender/Rod'}})],'b'),{1:'Tender/Rod'})
    def test_failed_preflight_does_not_write(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);src=root/'source';src.mkdir();(src/'a.anim').write_text('path_0x00000001_Rod')
            dest=root/'destination'
            with self.assertRaises(ValueError):resolve(src,root/'report.json',dest)
            self.assertFalse(dest.exists())
    def test_json_trailing_commas_preserves_strings(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'d.json';p.write_text('{"literal":",}","a":[1,],}')
            self.assertEqual(read_def(p),{'literal':',}','a':[1]})
    def test_catalog_radius_and_auxiliary_classification(self):
        r=make_record(CAT/'ls-282-k35a');self.assertEqual(r['ponies'],[{'key':'Pilot','radius_m':.42},{'key':'Trailing','radius_m':.47}])
        self.assertIsNone(r['profile']);self.assertTrue(r['missing'])
        r=make_record(CAT/'ls-260-g29');w=next(w for w in r['wheels'] if w['key']=='Wrench')
        self.assertEqual((w['role'],w['radius_m']),('auxiliary',1.5))
    def test_mallet_has_two_driver_groups(self):
        r=make_record(CAT/'ls-2442-l29');self.assertEqual(sum(w['role']=='driver' for w in r['wheels']),2)

if __name__=='__main__':unittest.main(verbosity=2)
