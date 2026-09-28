"""Versioned experimental pre-build decisions, shared by CLI and GUI."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

from .record import env, INCH_M

SCHEMA = 1
ADAPTER_VERSION = 'experimental-1'
BRAKES = ('self-lapping', 'manual-lap')
SPAWNING = ('radio-only', 'manual', 'automatic')
PHYSICS = ('legacy-equivalent', 'simple', 'geared')
HEAT = ('basis-approximation', 'saturated', 'superheated')
DYNAMO = ('yes', 'no')
# What a loco without a dynamo leaves out: electric lamps and cab light, and the controls that work them (James, 2026-09-28:
# the RLW RPP-1 has none, but got a dynamo, its steam jet by the chimney, lamps and their controls).
DYNAMO_CONTROLS = ('Dynamo', 'Cab light', 'Headlights')
# How the fire is fed (James, 2026-09-28). Oil burner: our builder core's OilFiring (the 'coal' container holds fuel oil, a
# CCL stoker fires it; oil valve in the HUD dynamic-brake slot, atomizer valve in gearbox 1). Mechanical stoker: shown so it
# can be chosen, but not buildable until the builder core keeps coal and gives the stoker steam use (board W57).
FIRING = ('hand-fired', 'oil-burner', 'mechanical-stoker')
OIL_VALVE, ATOMIZER_VALVE = 'oilValve', 'atomizerValve'


class ReviewError(ValueError):
    pass


def catalogue():
    path = Path(__file__).with_name('spawn_tracks.json')
    return json.loads(path.read_text()), hashlib.sha256(path.read_bytes()).hexdigest()


def request(record, definitions, probe, fingerprint):
    """No classification from vehicle names; source facts and user choices stay separate."""
    ident = record['vehicleId']
    source = definitions[ident]
    cat, digest = catalogue()
    cfg = record['config']
    cars = [cfg] + ([record['tender']['config']] if record.get('tender') else [])
    lengths = []
    for car in cars:
        front, rear = car.get('RrEndFront'), car.get('RrEndRear')
        if isinstance(front, dict): front = front.get('value')
        if isinstance(rear, dict): rear = rear.get('value')
        lengths.append(front - rear if isinstance(front, (float, int)) and isinstance(rear, (float, int)) else None)
    length = sum(lengths) + (len(cars) - 1) if all(x and x > 0 for x in lengths) else None
    # Explicit conservative DV choice: 1 m coupler separation, 2 m total end clearance.
    required = length + 2 if length else None
    tracks = [{**t, 'suitable': bool(required and t['length_m'] >= required and not t['restriction'])}
              for t in cat['tracks']]
    specs = {k: copy.deepcopy(source[k]) for k in ('kind', 'pistonDiameterInches', 'pistonStrokeInches',
             'maximumBoilerPressure', 'publishedTractiveEffort', 'weightOnDrivers', 'totalHeatingSurface',
             'mainDriverIndex', 'wheelsets', 'numCylinders', 'cylinderCount', 'gearRatio', 'brakeValveType') if k in source}
    questions = {
        'schema': SCHEMA, 'adapterVersion': ADAPTER_VERSION, 'vehicleId': ident,
        'fingerprint': fingerprint, 'catalogueHash': digest, 'catalogueEvidence': cat['evidence'],
        'name': cfg['CarName'], 'sourceSpecs': specs, 'consistLengthM': length, 'requiredTrackLengthM': required,
        'lengthBasis': 'source car ends + 1 m per coupling; 2 m total clearance (DV choice)',
        'tracks': tracks, 'wheelsets': source.get('wheelsets', []),
        'wheelCandidates': record['metadata'].get('wheelCandidates', []),
        'initialRadius': cfg.get('WheelRadius', {}).get('value') if isinstance(cfg.get('WheelRadius'), dict) else None,
        'suggestedBrake': source.get('brakeValveType') if source.get('brakeValveType') in BRAKES else None,
        'hasTender': bool(record.get('tender')),
        'sourceHasDynamo': any(isinstance(c, dict) and c.get('kind') == 'Dynamo' for c in _components(record)),
        'pendingCapabilities': ['Compound/simple switching: prototype not validated',
            'Oil-fired regime combinations: not validated', 'Diesel mechanical/hydraulic/electric: adapters pending',
            'Articulated geometry and steam calibration: in-game validation required'],
    }
    from . import codemods
    questions['codeMods'] = codemods.review(source)
    from .reviewchoices import suggest
    questions['prefill'] = suggest(questions, source)
    if questions['codeMods']['options']:
        first = questions['codeMods']['options'][0]
        questions['prefill']['values']['pullBasis'] = first['id']
        questions['prefill']['provenance']['pullBasis'] = {'basis': 'source', 'evidence':
            f"{first['label']} ({first['lbf']} lbf): {first['evidence']}; Railroader runs this when the mod is installed"}
    from . import enginemetrics
    questions['engineMetrics'] = enginemetrics.defaults(record, source)
    questions['prefill']['values']['engineMetrics'] = copy.deepcopy(questions['engineMetrics']['values'])
    questions['prefill']['metricProvenance'] = copy.deepcopy(questions['engineMetrics']['provenance'])
    return questions


def _components(record):
    comps = record['config'].get('Components') or []
    if isinstance(comps, dict): comps = comps.get('value') or []
    return comps


def resolve(req, answer):
    if not isinstance(answer, dict): raise ReviewError('Review cancelled; no build started')
    for key in ('schema', 'adapterVersion', 'vehicleId', 'fingerprint', 'catalogueHash'):
        if answer.get(key) != req[key]: raise ReviewError(f'Stale or different review: {key}; review this source again')
    v = copy.deepcopy(answer.get('values', {}))
    from . import enginemetrics
    v['engineMetrics'] = enginemetrics.resolve(req, v)
    notes = v.get('engineMetricNotes', '')
    if not isinstance(notes, str) or len(notes) > 2000: raise ReviewError('Engine specification notes must be text, up to 2000 characters')
    v['engineMetricNotes'] = notes.strip()
    pull_ids = [o['id'] for o in (req.get('codeMods') or {}).get('options', [])]
    if pull_ids:
        v.setdefault('pullBasis', pull_ids[0])  # a review saved before the choice existed: the suggestion
        if v['pullBasis'] not in pull_ids:
            raise ReviewError('Choose the pull to build to: ' + ', '.join(pull_ids))
    else:
        v.pop('pullBasis', None)
    if 'dynamo' not in v:  # a review saved before this choice existed: the source's own answer
        v['dynamo'] = 'yes' if req.get('sourceHasDynamo', True) else 'no'
    v.setdefault('firing', 'hand-fired')  # a review saved before this choice existed
    for key, allowed in (('trainBrake', BRAKES), ('spawnMode', SPAWNING), ('physics', PHYSICS), ('steamHeat', HEAT), ('dynamo', DYNAMO),
                         ('firing', FIRING)):
        if v.get(key) not in allowed: raise ReviewError(f'Choose {key}: {", ".join(allowed)}')
    if v['firing'] == 'oil-burner' and req.get('hasTender'):
        raise ReviewError('Oil burner firing is built for tank locos only so far: the builder core turns the loco\'s own coal '
                          'container into fuel oil, and a tender\'s coal space would still take coal. Choose hand-fired')
    if v['firing'] == 'mechanical-stoker':
        raise ReviewError('Mechanical stoker firing is not built yet: it needs a builder core change (keep coal, stoker steam use). '
                          'Choose hand-fired or oil-burner')
    def number(key, lo, hi):
        try: value = float(v.get(key))
        except (ValueError, TypeError): raise ReviewError(f'{key} requires a number')
        if not math.isfinite(value) or not lo <= value <= hi: raise ReviewError(f'{key} must be between {lo} and {hi}')
        v[key] = value
        return value
    number('wheelRadius', .1, 1.5)
    if v.get('cylinders') not in (2, 3, 4): raise ReviewError('Choose the physical cylinder count: 2, 3 or 4')
    if v['physics'] == 'geared':
        number('gearRatio', 1.000001, 100)
        number('efficiency', .01, 1)
        if not str(v.get('gearEvidence', '')).strip(): raise ReviewError('Record the source or assumption for the gear ratio')
        indices = v.get('poweredWheelsets')
        if not isinstance(indices, list) or not indices: raise ReviewError('Select the physical powered wheelsets (not engine shafts)')
        if any(type(i) is not int or i < 0 or i >= len(req['wheelsets']) for i in indices):
            raise ReviewError('Invalid powered wheelset index')
        v['poweredWheelsets'] = sorted(set(indices))
        unpowered = v.get('unpoweredWheelsets', [])
        if not isinstance(unpowered, list) or any(type(i) is not int or i < 0 or i >= len(req['wheelsets']) for i in unpowered):
            raise ReviewError('Invalid unpowered physical wheelset index')
        if set(indices) & set(unpowered): raise ReviewError('A wheelset cannot be both powered and unpowered')
        v['unpoweredWheelsets'] = sorted(set(unpowered))
    else:
        for key in ('gearRatio', 'efficiency', 'gearEvidence', 'poweredWheelsets', 'unpoweredWheelsets'): v.pop(key, None)
    eligible = {t['id'] for t in req['tracks'] if t['suitable']}
    selected = v.get('spawnTracks', [])
    if not isinstance(selected, list) or any(type(i) is not int for i in selected): raise ReviewError('Invalid track list')
    if v['spawnMode'] == 'radio-only':
        if selected: raise ReviewError('Radio-only cannot include normal spawn tracks')
    elif v['spawnMode'] == 'automatic': selected = sorted(eligible)
    elif not selected or not set(selected) <= eligible: raise ReviewError('Select at least one suitable track')
    if v['spawnMode'] != 'radio-only' and not selected: raise ReviewError('No verified suitable tracks; choose radio-only explicitly')
    v['spawnTracks'] = sorted(set(selected))
    if v.get('acknowledgeExperimental') is not True:
        raise ReviewError('Acknowledge experimental physics and pending in-game calibration')
    result = {k: req[k] for k in ('schema', 'adapterVersion', 'vehicleId', 'fingerprint', 'catalogueHash')}
    result.update(values=v, provenance={k: {'basis': 'DV_choice', 'evidence': 'Explicit pre-build user review'} for k in v}, basis='DV_choice', evidence=['Explicit pre-build user review'],
                  catalogueEvidence=req['catalogueEvidence'], sourceSpecs=req['sourceSpecs'],
                  consistLengthM=req['consistLengthM'], requiredTrackLengthM=req['requiredTrackLengthM'],
                  lengthBasis=req['lengthBasis'])
    if v['trainBrake'] == req.get('suggestedBrake'):
        result['provenance']['trainBrake'] = {'basis': 'source', 'evidence': 'Definitions.brakeValveType; confirmed in review'}
    prefill = req.get('prefill', {})
    for key, provenance in prefill.get('provenance', {}).items():
        if key in v and v[key] == prefill.get('values', {}).get(key):
            result['provenance'][key] = copy.deepcopy(provenance)
    result['codeMods'] = copy.deepcopy(req.get('codeMods') or {'options': [], 'notes': [], 'unrecognised': []})
    result['engineMetrics'] = copy.deepcopy(req.get('engineMetrics', {}))
    result['metricProvenance'] = {}
    for key, value in v['engineMetrics'].items():
        baseline = req.get('engineMetrics', {})
        if value == baseline.get('values', {}).get(key):
            provenance = baseline.get('provenance', {}).get(key, {})
        elif value == prefill.get('values', {}).get('engineMetrics', {}).get(key):
            provenance = prefill.get('metricProvenance', {}).get(key, {'basis': 'DV_choice', 'evidence': 'Previously reviewed value'})
        else:
            provenance = {'basis': 'DV_choice', 'evidence': 'Edited and confirmed in engine specifications' + ('; ' + v['engineMetricNotes'] if v['engineMetricNotes'] else '')}
        result['metricProvenance'][key] = copy.deepcopy(provenance)
        result['metricProvenance'][key]['unit'] = next(field[2] for field in enginemetrics.FIELDS if field[0] == key)
    result['engineEstimates'] = enginemetrics.estimates(v, result['engineMetrics'])
    return result


def apply(record, reviewed):
    """Emit loader-compatible values and keep physical specifications separate from simulation estimates."""
    rec = copy.deepcopy(record)
    v, specs = reviewed['values'], reviewed['sourceSpecs']
    cfg, meta = rec['config'], rec['metadata']
    meta['review'] = reviewed
    meta['sourceSpecs'] = {'basis': 'source', 'evidence': ['Definitions.json', reviewed['fingerprint']], 'values': specs}
    radius_basis = reviewed.get('provenance', {}).get('wheelRadius', {})
    cfg['WheelRadius'] = env(v['wheelRadius'], 'm', radius_basis.get('basis', 'DV_choice'),
                             radius_basis.get('evidence', 'User reviewed physical wheel tread radius'))
    cfg['SpawnTracks'] = env(v['spawnTracks'], 'CCL track enum', 'DV_choice', 'Pre-build spawn review', reviewed['catalogueEvidence'])
    sim = rec['hooks']['SimSpec']['steamEngine']
    sim['numCylinders'] = env(v['cylinders'], 'count', 'DV_choice', 'User reviewed physical cylinder count')
    if v['physics'] != 'legacy-equivalent':
        bore = specs['pistonDiameterInches'] * INCH_M
        basis, why = 'source', 'Definitions pistonDiameterInches; no equivalent-cylinder fitting'
    else:
        # Retain the existing TE target, but derive its equivalent bore for the reviewed cylinder count.
        old_bore = sim.get('cylinderBore')
        if old_bore is None: raise ReviewError('Legacy equivalent bore requires a reviewed radius before drafting')
        bore = old_bore['value'] * math.sqrt(2 / v['cylinders'])
        basis, why = 'derived', 'Existing E03 target rescaled for reviewed cylinder count; approximation'
    sim['cylinderBore'] = env(bore, 'm', basis, why)
    if v.get('dynamo') == 'no':
        _without_dynamo(rec)
    if v.get('firing') == 'oil-burner':
        _oil_burner(rec)
    from . import enginemetrics
    enginemetrics.apply(rec, reviewed)
    bore = sim['cylinderBore']['value']
    limitations = list(meta.get('pending', []))
    limitations += ['Steam/fuel consumption and drawbar pull have not been calibrated in game',
                    'Track lengths are CCL 3.1.9 nominal lengths; game settings affect radio availability']
    if v['physics'] == 'geared':
        limitations.append('Fixed reduction, not a selectable gearbox: Gearbox 1/2 cannot change ratio; source animation phase, adhesion and RPM need in-game checks')
    if v.get('firing') == 'oil-burner':
        limitations.append('Oil burner: feed rate, firebox multiplier and atomizer pressure are our builder core defaults (ALCo 1610 '
                           'pattern), not calibrated for this loco; refuelling from the diesel pump is untested in game')
    if v['steamHeat'] == 'basis-approximation': limitations.append('Steam thermal regime retains DV basis; not source-validated')
    meta['simulationProfile'] = {'id': v['physics'], 'version': ADAPTER_VERSION, 'runtimeValidated': False,
        'physicalCylinders': v['cylinders'], 'simulationBoreM': bore, 'steamHeat': v['steamHeat'],
        'gearRatio': v.get('gearRatio', 1), 'efficiency': v.get('efficiency', 1),
        'derivation': 'engine RPM = wheel RPM * ratio; wheel torque = engine torque * ratio * efficiency',
        'calibrationTargets': ['starting pull', 'adhesion', 'sustained pull by speed', 'steam/water use', 'fuel use'],
        'results': [], 'limitations': limitations,
        'controlAllocation': {'dynamicBrake': 'reserved for oil firing', 'gearboxA': 'reserved for atomizer',
                              'gearboxB': 'reserved for simpling; not implemented'}}
    if v['physics'] == 'geared':
        meta['simulationProfile']['speedDiagnostics'] = [
            {'speedKmh': speed,
             'wheelRpm': round(speed / 3.6 / (2 * math.pi * v['wheelRadius']) * 60, 2),
             'engineRpm': round(speed / 3.6 / (2 * math.pi * v['wheelRadius']) * 60 * v['gearRatio'], 2),
             'doubleActingExhaustEventsPerSecond': round(speed / 3.6 / (2 * math.pi * v['wheelRadius']) * v['gearRatio'] * v['cylinders'] * 2, 2)}
            for speed in (10, 30, 50, 60)]
    _pull_basis(rec, reviewed, v)
    return rec


def _pull_basis(rec, reviewed, v):
    """A code mod's pull (LegosBetterSteam...) built into Derail Valley: with the legacy-equivalent profile the
    equivalent bore is resized so DV's formula gives the chosen figure (pull scales with bore squared). Other profiles
    use the physical bore, which cannot carry a second engine: listed as a limitation."""
    option = next((o for o in reviewed.get('codeMods', {}).get('options', []) if o['id'] == v.get('pullBasis')), None)
    if not option:
        return
    meta = rec['metadata']
    meta['pullBasis'] = option
    sim = rec['hooks']['SimSpec']['steamEngine']
    current = (meta.get('tractiveEffort') or {}).get('lbf')
    if v['physics'] == 'legacy-equivalent' and current and sim.get('cylinderBore') and option['lbf'] != current:
        bore = sim['cylinderBore']['value'] * math.sqrt(option['lbf'] / current)
        sim['cylinderBore'] = env(bore, 'm', 'derived', f"Equivalent bore resized for {option['label']} "
                                  f"({option['lbf']} lbf instead of {round(current)} lbf): {option['evidence']}")
        meta['tractiveEffort'] = {**(meta.get('tractiveEffort') or {}), 'lbf': option['lbf'], 'basis': option['label']}
    elif v['physics'] != 'legacy-equivalent':
        meta['simulationProfile'].setdefault('limitations', []).append(
            f"{option['label']} ({option['lbf']} lbf) cannot be matched with a physical-bore profile; choose legacy-equivalent to build to it")


def _oil_burner(rec):
    """Oil firing through our builder core (guide D05): fuel oil in the 'coal' container, oil valve on the HUD's
    dynamic-brake slot, atomizer valve on gearbox 1 (lights the burner from cold), no coal pile to shovel from."""
    cfg, hooks, meta = rec['config'], rec['hooks'], rec['metadata']
    firing = {'ValveId': OIL_VALVE, 'AtomizerValveId': ATOMIZER_VALVE}
    # CCL's stoker multiplier "MUST match the multiplier in the firebox controller" (SteamMechanicalStokerDefinition)
    multiplier = ((hooks.get('SimSpec') or {}).get('firebox') or {}).get('coalConsumptionMultiplier')
    if isinstance(multiplier, dict): multiplier = multiplier.get('value')
    if isinstance(multiplier, (int, float)): firing['FireboxMultiplier'] = multiplier
    cfg['OilFiring'] = env(firing, 'config', 'DV_choice',
                           'Pre-build review: oil burner; feed rate and pressures are the builder core defaults, the firebox '
                           'multiplier matches the firebox')
    cfg['ControlsReaderExtra'] = env({'gearboxA': ATOMIZER_VALVE + '.EXT_IN'}, 'port', 'DV_choice',
                                     'Pre-build review: oil burner atomizer on the gearbox 1 HUD slot')
    cfg.pop('CoalTargetComp', None)  # no coal to shovel
    cfg.pop('CoalLoad', None)
    hooks.pop('CoalPile', None)
    if isinstance(cfg.get('LoadAnimations'), list):
        cfg['LoadAnimations'] = [l for l in cfg['LoadAnimations'] if l[2] != 'coal.NORMALIZED']
    meta['firing'] = 'oil-burner'


def _without_dynamo(rec):
    """No dynamo: no electric lamps or cab light, no controls for them; the build stage takes them off the HUD."""
    cfg = rec['config']
    placed = cfg.get('Placed')
    if isinstance(placed, dict):
        placed['value'] = [p for p in placed.get('value') or [] if p.get('Name') not in DYNAMO_CONTROLS]
    lenses = cfg.get('LampLenses')
    if isinstance(lenses, dict):
        lenses['value'] = []
        lenses['basis'], lenses['evidence'] = 'DV_choice', ['Pre-build review: no dynamo, so no electric lamps']
    cfg.pop('CabLightProbe', None)
    cfg.pop('LampShots', None)
    rec['metadata']['noDynamo'] = True


def _cli_interactive(req):
    import sys
    if not sys.stdin.isatty():
        raise ReviewError('Pre-build answers required: use the GUI or --review-file. See review-questions.json in the report.')
    print('Review:', req['name'], '\nSource wheelsets:', req['wheelsets'])
    print('Measured candidates:', req['wheelCandidates'])
    v = copy.deepcopy(req.get('prefill', {}).get('values', {}))
    print(req.get('prefill', {}).get('origin', ''))
    def prompt(key, label):
        default = v.get(key, '')
        if isinstance(default, list): default = ','.join(map(str, default))
        return input(f'{label} [{default}]: ').strip() or str(default)
    for key, options in [('trainBrake', BRAKES), ('spawnMode', SPAWNING), ('physics', PHYSICS), ('steamHeat', HEAT)]:
        v[key] = prompt(key, key + ' (' + ', '.join(options) + ')')
    v['wheelRadius'] = prompt('wheelRadius', 'Physical driving tyre RADIUS in metres')
    v['cylinders'] = int(prompt('cylinders', 'Physical cylinder count: 2, 3 or 4'))
    if v['spawnMode'] == 'manual':
        for t in req['tracks']:
            if t['suitable']: print(t['id'], t['name'], t['length_m'], 'm')
        v['spawnTracks'] = [int(x.strip()) for x in prompt('spawnTracks', 'Track IDs, comma separated').split(',') if x.strip()]
    else:
        v['spawnTracks'] = []
    if v['physics'] == 'geared':
        for key in ('gearRatio', 'efficiency', 'gearEvidence'): v[key] = prompt(key, key)
        v['poweredWheelsets'] = [int(x.strip()) for x in prompt('poweredWheelsets', 'Physical powered wheelset indices (exclude shafts)').split(',') if x.strip()]
    if v['physics'] == 'geared':
        v['unpoweredWheelsets'] = [int(x.strip()) for x in prompt('unpoweredWheelsets', 'Unpowered physical wheelset indices, if any').split(',') if x.strip()]
    from . import enginemetrics
    v.setdefault('engineMetrics', copy.deepcopy(req.get('engineMetrics', {}).get('values', {})))
    print('Engine estimates:', enginemetrics.estimates(v, req.get('engineMetrics', {})))
    if input('Edit engine specifications? [no]: ').strip().lower() == 'yes':
        for key, label, unit, lo, hi, effect in enginemetrics.FIELDS:
            current = v['engineMetrics'].get(key)
            raw = input(f'{label} ({unit}) [{current if current is not None else "inherit / unknown"}]; - clears optional value: ').strip()
            if raw: v['engineMetrics'][key] = None if raw == '-' else raw
        v['engineMetricNotes'] = input('Source / notes for edited figures (optional): ').strip()
    v['acknowledgeExperimental'] = input('Uncalibrated prototype; in-game validation required. Continue? [yes]: ').strip().lower() == 'yes'
    return {**{k:req[k] for k in ('schema','adapterVersion','vehicleId','fingerprint','catalogueHash')}, 'values':v}


def cli(req):
    try:
        return _cli_interactive(req)
    except EOFError:
        raise ReviewError('Pre-build answers required: use the GUI or --review-file. See review-questions.json in the report.') from None
