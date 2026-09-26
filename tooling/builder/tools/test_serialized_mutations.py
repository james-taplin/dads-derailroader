"""Mutation tests against a real installed CCL tank bundle; does not edit it.

The ALCo is an oil-burning four-axle tank and intentionally is NOT a passing S16
fixture. Tests compare targeted error deltas, not its unrelated differences.
Requires the private installed ALCo fixture under MACHINE['mods'] and the
preserved S16 test04 vehicle_record.json. No extracted game assets are distributed.
"""
import copy
import json
import unittest
from pathlib import Path
from workspace import WORKSPACE,MACHINE
from audit_new_loco import load_bundle,Snapshot,validate_snapshot


class SerializedMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.objects,cls.kinds=load_bundle(Path(MACHINE['mods'])/'ALCo 1610'/'ccl_bundle')
        cls.record=json.loads((WORKSPACE/'locos'/'s16'/'builds'/'test04'/'vehicle_record.json').read_text(encoding='utf-8-sig'))
        s=Snapshot(cls.objects,cls.kinds);sim=s.classes['SimConnectionsDefinitionProxy'][0]
        ports={};refs={}
        for p in sim['executionOrder']:
            d=cls.objects[p['m_PathID']];ports[d['ID']]=set();refs[d['ID']]=set()
        def add(table,value):
            if value and '.' in value:
                owner,key=value.split('.',1)
                if owner in table:table[owner].add(key)
        for link in sim['portReferenceConnections']:
            add(ports,link['portId']);add(refs,link['portReferenceId'])
        for link in sim['connections']:
            add(ports,link['fullPortIdIn']);add(ports,link['fullPortIdOut'])
        for component in s.classes['InteractablePortFeederProxy']+s.classes['AnimatorPortReaderProxy']+s.classes['IndicatorPortReaderProxy']:
            add(ports,component['portId'])
        cls.gate={'schema':1,'carId':'LLW_S16','components':[dict(id=cls.objects[p['m_PathID']]['ID'],
            componentClass=s.behaviour_class[p['m_PathID']],ports=sorted(ports[cls.objects[p['m_PathID']]['ID']]),
            references=sorted(refs[cls.objects[p['m_PathID']]['ID']])) for p in sim['executionOrder']]}

    def validate(self,objects):
        return validate_snapshot(Snapshot(objects,self.kinds),self.record,self.gate,'')[0]

    def test_duplicate_execution_id_is_rejected(self):
        objects=copy.deepcopy(self.objects);s=Snapshot(objects,self.kinds)
        sim=s.classes['SimConnectionsDefinitionProxy'][0];sim['executionOrder'].append(sim['executionOrder'][0])
        self.assertIn('Missing/duplicate simulation execution IDs',self.validate(objects))

    def test_wrong_resource_route_is_rejected(self):
        objects=copy.deepcopy(self.objects);s=Snapshot(objects,self.kinds)
        sim=s.classes['SimConnectionsDefinitionProxy'][0]
        next(x for x in sim['portReferenceConnections'] if x['portReferenceId']=='boiler.WATER')['portId']='water.MADE_UP'
        errors=self.validate(objects)
        self.assertIn('Missing referenced port water.MADE_UP',errors)
        self.assertIn('Tank resource routing mismatch boiler.WATER',errors)
        self.assertIn('CCL AfterImport JSON differs from serialized portReferenceConnections',errors)

    def test_feeder_typo_is_rejected(self):
        objects=copy.deepcopy(self.objects);s=Snapshot(objects,self.kinds)
        s.classes['InteractablePortFeederProxy'][0]['portId']='throttle.TYPO'
        self.assertTrue(any('feeder references missing port' in e and 'throttle.TYPO' in e for e in self.validate(objects)))

    def test_duplicate_oil_tag_is_rejected(self):
        objects=copy.deepcopy(self.objects);s=Snapshot(objects,self.kinds)
        s.classes['ManualOilingPoint'][0]['SyncTag']=s.classes['ManualOilingPoint'][1]['SyncTag']
        self.assertIn('Missing/duplicate oil cup tags',self.validate(objects))


if __name__=='__main__':unittest.main(verbosity=2)
