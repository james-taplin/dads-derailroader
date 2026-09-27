import copy
import unittest
from rr2dv import review
from rr2dv.buildrecord import driving_candidate, measured_axles


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.req = review.request({'vehicleId':'x','config':{'CarName':'Example','RrEndFront':8,'RrEndRear':-8},
                                  'metadata':{}}, {'x':{'wheelsets':[{'diameter':.9},{'diameter':.4}]}}, {}, 'abc')
        self.answer = {**{k:self.req[k] for k in ('schema','adapterVersion','vehicleId','fingerprint','catalogueHash')},
                       'values':{'trainBrake':'self-lapping','spawnMode':'radio-only','physics':'simple',
                                 'steamHeat':'saturated','wheelRadius':.45,'cylinders':2,'spawnTracks':[],
                                 'acknowledgeExperimental':True}}

    def test_radio_only_and_source_identity(self):
        result = review.resolve(self.req,self.answer)
        self.assertEqual(result['values']['spawnTracks'],[])
        self.assertEqual(result['requiredTrackLengthM'],18)
        self.assertEqual(result['provenance']['trainBrake']['basis'],'DV_choice')
        self.answer['fingerprint']='other'
        with self.assertRaises(review.ReviewError): review.resolve(self.req,self.answer)

    def test_automatic_is_pool_and_manual_rejects_restricted_or_short_track(self):
        self.answer['values']['spawnMode']='automatic'
        result=review.resolve(self.req,self.answer)
        self.assertGreater(len(result['values']['spawnTracks']),5)
        self.assertNotIn(600,result['values']['spawnTracks'])
        self.answer['values'].update(spawnMode='manual',spawnTracks=[600])
        with self.assertRaises(review.ReviewError): review.resolve(self.req,self.answer)

    def test_whole_consist_length_filters_pool(self):
        req=review.request({'vehicleId':'x','config':{'CarName':'Long','RrEndFront':30,'RrEndRear':-30},
                            'tender':{'config':{'RrEndFront':15,'RrEndRear':-15}},'metadata':{}},
                           {'x':{}},{},'abc')
        self.assertEqual(req['requiredTrackLengthM'],93)
        self.assertFalse(next(t for t in req['tracks'] if t['id']==200)['suitable'])

    def test_geared_requires_physical_wheels_and_evidence(self):
        self.answer['values'].update(physics='geared',gearRatio=2.5,efficiency=.9,poweredWheelsets=[0])
        with self.assertRaises(review.ReviewError): review.resolve(self.req,self.answer)
        self.answer['values']['gearEvidence']='Explicit prototype assumption'
        result=review.resolve(self.req,self.answer)
        self.assertEqual(result['values']['poweredWheelsets'],[0])
        self.answer['values']['wheelRadius']=float('nan')
        with self.assertRaises(review.ReviewError): review.resolve(self.req,self.answer)

    def test_geared_driver_candidate_excludes_main_animation_shaft(self):
        wheels=[{'clip':'wheels'},{'clip':'shaft'}]
        candidates=[{'clip':'wheels','tread':.45},{'clip':'shaft','tread':.2}]
        definition={'mainDriverIndex':1,'wheelsets':[{'diameter':.9},{'diameter':.4}]}
        self.assertEqual(driving_candidate(candidates,wheels,definition,[0])['tread'],.45)

    def test_no_brake_inference_from_handle_label(self):
        self.answer['values']['trainBrake']='Train Brake'
        with self.assertRaises(review.ReviewError): review.resolve(self.req,self.answer)

    def test_shared_animation_uses_declared_truck_and_measured_axles(self):
        ws={'offset':-3.5,'length':1.4,'axles':2,'transformPath':'TruckM'}
        nodes={'TruckF/a':[0,.45,4], 'TruckM/a':[0,.45,-2], 'TruckM/b':[0,.45,-3.4]}
        probe={'rotatingPaths':list(nodes), 'meshes':[{'path':p+'/mesh','used':True} for p in nodes]}
        result=measured_axles(ws,probe,nodes)
        self.assertEqual([a['part'] for a in result],['TruckM/a','TruckM/b'])
        self.assertEqual([a['z'] for a in result],[-2,-3.4])
        self.assertNotEqual(result[0]['z'],result[0]['rr'])
        probe['meshes']=probe['meshes'][:2]
        self.assertTrue(any(a['part'] is None for a in measured_axles(ws,probe,nodes)))

    def test_review_does_not_mutate_saved_input(self):
        before=copy.deepcopy(self.answer)
        review.resolve(self.req,self.answer)
        self.assertEqual(self.answer,before)
