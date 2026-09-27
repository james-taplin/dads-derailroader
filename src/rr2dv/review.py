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
        'pendingCapabilities': ['Compound/simple switching: prototype not validated',
            'Oil-fired regime combinations: not validated', 'Diesel mechanical/hydraulic/electric: adapters pending',
            'Articulated geometry and steam calibration: in-game validation required'],
    }
    return questions


def resolve(req, answer):
    if not isinstance(answer, dict): raise ReviewError('Review cancelled; no build started')
    for key in ('schema', 'adapterVersion', 'vehicleId', 'fingerprint', 'catalogueHash'):
        if answer.get(key) != req[key]: raise ReviewError(f'Stale or different review: {key}; review this source again')
    v = copy.deepcopy(answer.get('values', {}))
    for key, allowed in (('trainBrake', BRAKES), ('spawnMode', SPAWNING), ('physics', PHYSICS), ('steamHeat', HEAT)):
        if v.get(key) not in allowed: raise ReviewError(f'Choose {key}: {", ".join(allowed)}')
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
    return result


def apply(record, reviewed):
    """Emit loader-compatible values and keep physical specifications separate from simulation estimates."""
    rec = copy.deepcopy(record)
    v, specs = reviewed['values'], reviewed['sourceSpecs']
    cfg, meta = rec['config'], rec['metadata']
    meta['review'] = reviewed
    meta['sourceSpecs'] = {'basis': 'source', 'evidence': ['Definitions.json', reviewed['fingerprint']], 'values': specs}
    cfg['WheelRadius'] = env(v['wheelRadius'], 'm', 'DV_choice', 'User reviewed physical wheel tread radius')
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
    limitations = list(meta.get('pending', []))
    limitations += ['Steam/fuel consumption and drawbar pull have not been calibrated in game',
                    'Track lengths are CCL 3.1.9 nominal lengths; game settings affect radio availability']
    if v['physics'] == 'geared': limitations.append('Fixed geared prototype; source animation phase, adhesion and RPM need in-game checks')
    if v['steamHeat'] == 'basis-approximation': limitations.append('Steam thermal regime retains DV basis; not source-validated')
    meta['simulationProfile'] = {'id': v['physics'], 'version': ADAPTER_VERSION, 'runtimeValidated': False,
        'physicalCylinders': v['cylinders'], 'simulationBoreM': bore, 'steamHeat': v['steamHeat'],
        'gearRatio': v.get('gearRatio', 1), 'efficiency': v.get('efficiency', 1),
        'derivation': 'engine RPM = wheel RPM * ratio; wheel torque = engine torque * ratio * efficiency',
        'calibrationTargets': ['starting pull', 'adhesion', 'sustained pull by speed', 'steam/water use', 'fuel use'],
        'results': [], 'limitations': limitations,
        'controlAllocation': {'dynamicBrake': 'reserved for oil firing', 'gearboxA': 'reserved for atomizer',
                              'gearboxB': 'reserved for simpling; not implemented'}}
    return rec


def _cli_interactive(req):
    import sys
    if not sys.stdin.isatty():
        raise ReviewError('Pre-build answers required: use the GUI or --review-file. See review-questions.json in the report.')
    print('Review:', req['name'], '\nSource wheelsets:', req['wheelsets'])
    print('Measured candidates:', req['wheelCandidates'])
    v = {}
    for key, options in [('trainBrake', BRAKES), ('spawnMode', SPAWNING), ('physics', PHYSICS), ('steamHeat', HEAT)]:
        v[key] = input(key + ' [' + ', '.join(options) + ']: ').strip()
    v['wheelRadius'] = input('Physical driving tyre RADIUS in metres: ')
    v['cylinders'] = int(input('Physical cylinder count [2, 3, 4]: '))
    v['spawnTracks'] = []
    if v['spawnMode'] == 'manual':
        for t in req['tracks']:
            if t['suitable']: print(t['id'], t['name'], t['length_m'], 'm')
        v['spawnTracks'] = [int(x.strip()) for x in input('Track IDs, comma separated: ').split(',')]
    if v['physics'] == 'geared':
        for key in ('gearRatio', 'efficiency', 'gearEvidence'): v[key] = input(key + ': ')
        v['poweredWheelsets'] = [int(x.strip()) for x in input('Physical powered wheelset indices (exclude shafts): ').split(',')]
    if v['physics'] == 'geared':
        v['unpoweredWheelsets'] = [int(x.strip()) for x in input('Unpowered physical wheelset indices, if any: ').split(',') if x.strip()]
    v['acknowledgeExperimental'] = input('Uncalibrated prototype; in-game validation required. Continue? [yes]: ').strip().lower() == 'yes'
    return {**{k:req[k] for k in ('schema','adapterVersion','vehicleId','fingerprint','catalogueHash')}, 'values':v}


def cli(req):
    try:
        return _cli_interactive(req)
    except EOFError:
        raise ReviewError('Pre-build answers required: use the GUI or --review-file. See review-questions.json in the report.') from None
