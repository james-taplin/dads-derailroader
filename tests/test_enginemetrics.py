import copy
import tempfile
import unittest
from pathlib import Path

from rr2dv import enginemetrics as metrics, review, reviewchoices
from rr2dv.record import env, equivalent_bore_m, safety_bar, firebox_estimate, injector_l_s


def fixture():
    source = {'pistonDiameterInches': 14, 'pistonStrokeInches': 16, 'maximumBoilerPressure': 180,
              'totalHeatingSurface': 1150, 'weightOnDrivers': 120000, 'publishedTractiveEffort': 24000,
              'wheelsets': [{'diameter': .9}]}
    opening, closing = safety_bar(180)
    bed, burn = firebox_estimate(1150)
    wrap = lambda v: env(v, 'test', 'source', 'fixture')
    record = {'vehicleId': 'example', 'config': {'CarName': 'Example', 'WheelRadius': wrap(.45), 'SimBasis': 0},
              'metadata': {'tractiveEffort': {'lbf': 24000}, 'pending': []},
              'hooks': {'SimSpec': {
                  'steamEngine': {'numCylinders': wrap(2), 'cylinderBore': wrap(equivalent_bore_m(24000,.45,180,.4064)), 'pistonStroke': wrap(.4064)},
                  'boiler': {'safetyValveOpeningPressure': wrap(opening), 'safetyValveClosingPressure': wrap(closing), 'maxInjectorRate': wrap(injector_l_s(1150))},
                  'firebox': {'maxCoalCapacity': wrap(bed), 'burnTime': wrap(burn), 'coalConsumptionMultiplier': wrap(1)}}}}
    req = review.request(record, {'example': source}, {}, 'fingerprint')
    values = {**copy.deepcopy(req['prefill']['values']), 'physics': 'legacy-equivalent', 'acknowledgeExperimental': True}
    return record, req, values


def resolve(req, values):
    return review.resolve(req, {**{k:req[k] for k in reviewchoices.IDENTITY}, 'values':values})


class EngineMetrics(unittest.TestCase):
    def test_accepting_defaults_preserves_simulation_numbers(self):
        record, req, values = fixture()
        result = review.apply(record, resolve(req, values))
        for component, fields in record['hooks']['SimSpec'].items():
            for field, value in fields.items():
                self.assertEqual(result['hooks']['SimSpec'][component][field]['value'], value['value'])
        self.assertEqual(values['engineMetrics']['boilerDiameterM'], 1.25)
        self.assertNotIn('diameter', result['hooks']['SimSpec']['boiler'])

    def test_edits_reach_simulation_with_unit_conversions(self):
        record, req, values = fixture()
        values['physics'] = 'simple'
        values['engineMetrics'].update(boreIn=15, strokeIn=18, pressurePsi=200, heatingFt2=1735,
                                      boilerDiameterM=1.4, boilerLengthM=4, boilerCapacityFactor=.8, fuelMultiplier=1.25)
        result = review.apply(record, resolve(req, values))
        sim = result['hooks']['SimSpec']
        self.assertAlmostEqual(sim['steamEngine']['cylinderBore']['value'], .381)
        self.assertAlmostEqual(sim['steamEngine']['pistonStroke']['value'], .4572)
        self.assertAlmostEqual(sim['boiler']['safetyValveOpeningPressure']['value'], safety_bar(200)[0])
        self.assertEqual(sim['firebox']['maxCoalCapacity']['value'], 65)
        self.assertEqual(sim['firebox']['coalConsumptionMultiplier']['value'], 1.25)
        self.assertEqual(sim['boiler']['diameter']['value'], 1.4)
        self.assertEqual(sim['boiler']['length']['value'], 4)
        self.assertAlmostEqual(sim['boiler']['spawnWaterLevel']['value'], 3600*(1.4/1.25)**2*(4/4.6)*(.8/.85))
        self.assertEqual(record['hooks']['SimSpec']['firebox']['coalConsumptionMultiplier']['value'], 1)

    def test_nominal_te_adhesion_and_gearing(self):
        _, req, values = fixture()
        values['physics'] = 'simple'
        result = metrics.estimates(values, req['engineMetrics'])
        expected = .85 * 180 * 14**2 * 16 / (.9/.0254)
        self.assertAlmostEqual(result['nominalTeLbf'], expected)
        self.assertAlmostEqual(result['factorOfAdhesion'], 120000/expected)
        values.update(physics='geared', gearRatio=2, efficiency=.9)
        self.assertAlmostEqual(metrics.estimates(values, req['engineMetrics'])['nominalTeLbf'], expected*1.8)
        values['engineMetrics']['driverWeightLb'] = None
        self.assertIsNone(metrics.estimates(values, req['engineMetrics'])['factorOfAdhesion'])

    def test_reference_te_cannot_silently_retune_engine(self):
        record, req, values = fixture()
        baseline = review.apply(record, resolve(req, values))
        values['engineMetrics']['referenceTeLbf'] = 45000
        edited = review.apply(record, resolve(req, values))
        self.assertEqual(baseline['hooks']['SimSpec'], edited['hooks']['SimSpec'])

    def test_equivalent_profile_retunes_from_physical_edits(self):
        record, req, values = fixture()
        old_bore = record['hooks']['SimSpec']['steamEngine']['cylinderBore']['value']
        values['engineMetrics']['boreIn'] = 28
        result = review.apply(record, resolve(req, values))
        self.assertAlmostEqual(result['hooks']['SimSpec']['steamEngine']['cylinderBore']['value'], old_bore*2)
        self.assertAlmostEqual(result['metadata']['simulationProfile']['simulationBoreM'], old_bore*2)

    def test_invalid_values_and_partial_boiler_rejected(self):
        _, req, values = fixture()
        for key, value in [('pressurePsi','nan'),('boreIn',True),('fuelMultiplier',0),('pressurePsi',''),
                           ('boilerDiameterM',''),('heatingFt2',1)]:
            v = copy.deepcopy(values); v['engineMetrics'][key]=value
            with self.subTest(key=key, value=value), self.assertRaises(review.ReviewError): resolve(req,v)

    def test_old_review_is_upgraded_and_metric_override_remembered(self):
        _, req, values = fixture()
        values.pop('engineMetrics')
        saved = resolve(req,values)
        self.assertEqual(saved['values']['engineMetrics']['pressurePsi'],180)
        saved['values']['engineMetrics']['pressurePsi']=200
        with tempfile.TemporaryDirectory() as temp:
            reviewchoices.remember(Path(temp),saved)
            restored=reviewchoices.prepare(req,Path(temp))
        self.assertEqual(restored['prefill']['values']['engineMetrics']['pressurePsi'],200)
        self.assertEqual(restored['engineMetrics']['values']['pressurePsi'],180)
        self.assertFalse(restored['prefill']['values']['acknowledgeExperimental'])

    def test_provenance_and_original_source_are_preserved(self):
        _, req, values = fixture()
        values['engineMetrics']['pressurePsi']=200
        values['engineMetricNotes']='Works drawing, revised boiler'
        result=resolve(req,values)
        self.assertEqual(result['metricProvenance']['pressurePsi']['basis'],'DV_choice')
        self.assertEqual(result['metricProvenance']['boreIn']['basis'],'source')
        self.assertEqual(result['sourceSpecs']['maximumBoilerPressure'],180)
        self.assertIn('Works drawing', result['metricProvenance']['pressurePsi']['evidence'])
        self.assertEqual(result['metricProvenance']['pressurePsi']['unit'],'psi gauge')


class EngineForm(unittest.TestCase):
    def test_live_estimates_edit_and_restore(self):
        import tkinter as tk
        from threading import Event
        from rr2dv.reviewgui import show
        try: root=tk.Tk()
        except tk.TclError: self.skipTest('needs Tk display')
        root.withdraw()
        self.addCleanup(root.destroy)
        _,req,_=fixture()
        state=show(root,req,{'event':Event()})
        root.update_idletasks()
        fields=state['engine']['fields']
        self.assertEqual(fields['pressurePsi'].get(),'180')
        before=state['engine']['summary'].get()
        fields['pressurePsi'].set('200')
        self.assertNotEqual(before,state['engine']['summary'].get())
        state['ack'].set(True)
        self.assertEqual(state['collect']()['values']['engineMetrics']['pressurePsi'],200)
        state['engine']['restore']('pressurePsi')
        self.assertEqual(state['collect']()['values']['engineMetrics']['pressurePsi'],180)
        state['window'].destroy()
        root.update_idletasks()
