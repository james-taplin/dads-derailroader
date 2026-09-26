"""Verify configured fields on both simulation definitions and sibling controllers."""
import copy
import json
import unittest
from workspace import WORKSPACE
from audit_new_loco import load_bundle,Snapshot,validate_snapshot,ptr


class S16SimulationFieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run=WORKSPACE/'locos'/'s16'/'builds'/'test04'
        cls.objects,cls.kinds=load_bundle(run/'LLW S16'/'ccl_bundle')
        cls.record=json.loads((run/'vehicle_record.json').read_text(encoding='utf-8-sig'))
        cls.gate=json.loads((run/'sim_ports.json').read_text(encoding='utf-8-sig'))

    def validate(self,objects):
        return validate_snapshot(Snapshot(objects,self.kinds),self.record,self.gate,'')[0]

    def test_real_same_node_controller_field_matches(self):
        self.assertFalse(any('Simulation setting mismatch' in e for e in self.validate(self.objects)))

    def test_wrong_controller_value_rejected(self):
        objects=copy.deepcopy(self.objects)
        Snapshot(objects,self.kinds).classes['FireboxSimControllerProxy'][0]['coalConsumptionMultiplier']=2.0
        self.assertIn('Simulation setting mismatch firebox.coalConsumptionMultiplier',self.validate(objects))

    def test_missing_controller_value_rejected(self):
        objects=copy.deepcopy(self.objects)
        del Snapshot(objects,self.kinds).classes['FireboxSimControllerProxy'][0]['coalConsumptionMultiplier']
        self.assertIn('Simulation setting mismatch firebox.coalConsumptionMultiplier',self.validate(objects))

    def test_controller_on_wrong_node_rejected(self):
        objects=copy.deepcopy(self.objects)
        Snapshot(objects,self.kinds).classes['FireboxSimControllerProxy'][0]['m_GameObject']['m_PathID']=0
        self.assertIn('Simulation setting mismatch firebox.coalConsumptionMultiplier',self.validate(objects))

    def test_ambiguous_same_node_field_rejected(self):
        objects=copy.deepcopy(self.objects)
        Snapshot(objects,self.kinds).classes['FireboxDefinitionProxy'][0]['coalConsumptionMultiplier']=1.0
        self.assertIn('Ambiguous simulation setting firebox.coalConsumptionMultiplier',self.validate(objects))

    def test_cab_floor_bounds_reject_old_roof_destination(self):
        record=copy.deepcopy(self.record);record['config']['CabFloorProbeHeight']=2.2
        message='Cab teleport destination is outside the reviewed floor probe bounds'
        self.assertIn(message,validate_snapshot(Snapshot(self.objects,self.kinds),record,self.gate,'')[0])
        objects=copy.deepcopy(self.objects);s=Snapshot(objects,self.kinds)
        cab=s.classes['CabTeleportDestinationProxy'][0]
        s.transforms[ptr(cab['m_GameObject'])]['m_LocalPosition']['y']=1.4
        self.assertNotIn(message,validate_snapshot(s,record,self.gate,'')[0])


if __name__=='__main__': unittest.main(verbosity=2)
