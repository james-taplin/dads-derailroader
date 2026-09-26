from pathlib import Path
import copy
import json
import tempfile
import unittest

from audit_new_loco import unwrap, warning_errors, Snapshot, validate_snapshot
from audit_source_closure import source_closure


class FirstBuildAuditTests(unittest.TestCase):
    def test_numeric_evidence_wrappers_are_unwrapped_recursively(self):
        data={'config':{'WheelRadius':{'value':.49,'unit':'m','basis':'measured','evidence':['probe']},
                        'nested':{'value':{'x':1,'y':2},'unit':'m','basis':'source'}}}
        self.assertEqual(unwrap(data)['config'],{'WheelRadius':.49,'nested':{'x':1,'y':2}})

    def test_unknown_warning_fails(self):
        errors,_=warning_errors('WARN bad valve\n',{'exported':True,'warnings':1},[])
        self.assertIn('Warnings differ from exact reviewed dispositions',errors)

    def test_warning_disposition_must_have_reason(self):
        errors,_=warning_errors('WARN cosmetic\n',{'exported':True,'warnings':1},[{'line':'WARN cosmetic','reason':''}])
        self.assertTrue(any('nonempty review reasons' in e for e in errors))

    def test_exact_warning_order_and_counter(self):
        dispositions=[{'line':'WARN a','reason':'Reviewed mesh overlap.'},{'line':'WARN b','reason':'Reviewed mesh overlap.'}]
        self.assertEqual(warning_errors('WARN a\nWARN b',{'exported':True,'warnings':2},dispositions)[0],[])
        self.assertTrue(warning_errors('WARN b\nWARN a',{'exported':True,'warnings':2},dispositions)[0])
        self.assertTrue(warning_errors('WARN a\nWARN b',{'exported':True,'warnings':1},dispositions)[0])

    def test_exception_or_unexported_result_fails(self):
        self.assertTrue(warning_errors('EXCEPTION importer',{'exported':True,'warnings':0},[])[0])
        self.assertTrue(warning_errors('',{'exported':False,'warnings':0},[])[0])

    def test_source_closure_detects_missing_dependency_and_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); assets=root/'Assets'; clips=assets/'AnimationClip'; clips.mkdir(parents=True)
            prefab=assets/'body.prefab'
            prefab.write_text('%YAML 1.1\n--- !u!1 &1\nGameObject:\n  m_Name: Root\n--- !u!4 &2\nTransform:\n  m_GameObject: {fileID: 1}\n  m_Father: {fileID: 0}\n  missing: {fileID: 1, guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, type: 2}\n')
            (clips/'a.anim').write_text('%YAML 1.1\nAnimationClip:\n    path: Missing/Handle\n')
            result=source_closure(root,root,{}, {'SrcPrefab':'Assets/body.prefab'})
            self.assertEqual(result['status'],'failed')
            self.assertTrue(any('Unresolved source GUID' in e for e in result['errors']))
            self.assertTrue(any('clip paths' in e for e in result['errors']))


if __name__=='__main__':unittest.main(verbosity=2)
