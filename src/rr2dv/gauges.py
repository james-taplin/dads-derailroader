"""Measured cab instrument layouts, separate from common assembly construction.

Only numerical fits/resource names ship; donor game geometry is resolved by CCL.
Every profile records its source mounts and acceptance state; no neighbour offsets are inferred.
"""
import json
import math
import copy
from pathlib import Path


class GaugeError(ValueError):
    pass


def library(path=None):
    data = json.loads((Path(path) if path else Path(__file__).with_name('gauge_fits.json')).read_text(encoding='utf-8'))
    if data.get('schema') != 1 or not isinstance(data.get('profiles'), dict):
        raise GaugeError('Unsupported cab gauge fitting library')
    return data


STYLES = {'boiler': 'BoilerPressure', 'chest': 'BoilerPressure',
          'brake': 'DualBrakeCylinderLine', 'speed': 'Speedometer100'}


def apply_layout(cfg, comps, source, choose):
    """Apply an explicit reviewed layout only when every original source mount still agrees."""
    profile = library()['profiles'].get(source)
    if not profile or not profile.get('sourceMounts'):
        return False
    from .record import env
    original = [c for c in comps if c.get('kind') == 'Gauge']
    mounts = profile['sourceMounts']
    if len(original) != len(mounts):
        raise GaugeError(f'{source}: source gauge count differs from measured fitting; review the new game build')
    for actual, expected in zip(original, mounts):
        if actual['name'] != expected['name'] or json.loads(actual['extra'])['style'] != expected['style']:
            raise GaugeError(f'{source}: source gauge identity differs from measured fitting')
        for actual_key, expected_key in (('pos', 'position'), ('rot', 'rotation'), ('scale', 'scale')):
            if len(actual[actual_key]) != len(expected[expected_key]) or any(
                    not isinstance(a, (int, float)) or isinstance(a, bool) or not math.isfinite(a)
                    or abs(a-b) > .0001 for a, b in zip(actual[actual_key], expected[expected_key])):
                raise GaugeError(f'{source}: source gauge transform differs from measured fitting')
    replacement = []
    for fit in profile['instruments']:
        component = copy.deepcopy(original[fit['sourceIndex']])
        component.update(name=fit['sourceGauge'], parentPath='',
                         pos=env(fit['position'], 'm', 'measured', fit['evidence']),
                         # Core generated faces look along +Z; the donor assembly looks along -Z.
                         rot=fit['coreRotation'], scale=[.8*fit['scale'], .8*fit['scale'], 1.0],
                         extra=json.dumps(dict(style=STYLES[fit['reading']], enabled=True), separators=(',', ':')))
        replacement.append(component)
    value = cfg['Components']['value']
    value[:] = [c for c in value if c.get('kind') != 'Gauge'] + replacement
    comps[:] = [c for c in comps if c.get('kind') != 'Gauge'] + [dict(c, pos=c['pos']['value']) for c in replacement]
    cfg['Components']['basis'] = 'derived'
    cfg['Components']['evidence'].append(f'{source}: measured {len(replacement)}-instrument layout from gauge_fits.json; game acceptance pending')
    choose(f'measured {len(replacement)}-instrument cab layout: '+', '.join(f['reading'] for f in profile['instruments'])+
           '; complete housings and measured supports; numerical speed and reservoir remain on F4')
    return True


def prepare(record, library=None):
    library = Path(library) if library else Path(__file__).with_name('gauge_fits.json')
    data = json.loads(library.read_text(encoding='utf-8'))
    if data.get('schema') != 1 or not isinstance(data.get('profiles'), dict):
        raise GaugeError('Unsupported cab gauge fitting library')
    source = record['vehicleId']
    profile = data['profiles'].get(source)
    if profile is None:
        return None
    if not isinstance(profile, dict) or not isinstance(profile.get('state'), str) or not profile['state']:
        raise GaugeError('Gauge fitting requires an acceptance state')
    instruments = profile.get('instruments')
    if not isinstance(instruments, list) or not instruments:
        raise GaugeError('Gauge fitting has no instruments')
    config = record['config']
    components = config['Components']
    components = components.get('value', []) if isinstance(components, dict) else components
    seen = set()
    for fit in instruments:
        reading = fit.get('reading')
        if reading not in ('boiler', 'brake', 'speed', 'chest') or reading in seen:
            raise GaugeError('Unknown or duplicate fitted gauge reading')
        seen.add(reading)
        matches = [c for c in components if c.get('kind') == 'Gauge' and c.get('name') == fit.get('sourceGauge')]
        if len(matches) != 1:
            raise GaugeError(f"Fitted gauge {fit.get('sourceGauge')!r} must resolve uniquely")
        style = json.loads(matches[0]['extra']).get('style')
        if (reading in ('boiler', 'chest') and style != 'BoilerPressure'
                or reading == 'brake' and style != 'DualBrakeCylinderLine'
                or reading == 'speed' and not str(style).startswith('Speedometer')):
            raise GaugeError('Fitted gauge style does not match its intended reading')
        if reading == 'boiler' and fit['sourceGauge'] != config.get('MainPressureGauge'):
            raise GaugeError('Fitted boiler gauge is not the main boiler instrument')
        for field, size in (('position', 3), ('rotation', 4), ('supportPoint', 3)):
            vector = fit.get(field)
            if not isinstance(vector, list) or len(vector) != size or any(
                    not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in vector):
                raise GaugeError(f'Invalid gauge {field}')
        if abs(sum(v*v for v in fit['rotation'])-1) > .001:
            raise GaugeError('Gauge rotation must be a unit quaternion')
        if isinstance(fit.get('scale'), bool) or not isinstance(fit.get('scale'), (float, int)) or not .5 <= fit['scale'] <= 1.5:
            raise GaugeError('Fitted gauge scale is outside the reviewed range')
        if not fit.get('supportPath') or not fit.get('evidence'):
            raise GaugeError('Fitted gauge requires measured support evidence')
        supports = fit.get('supports', [])
        if not isinstance(supports, list) or supports and len(supports) < 3:
            raise GaugeError('Gauge adapter needs at least three measured attachments')
        for support in supports:
            if not isinstance(support, dict) or not support.get('supportPath'):
                raise GaugeError('Gauge adapter attachment needs a support path')
            for field in ('point', 'radial'):
                vector = support.get(field)
                if not isinstance(vector, list) or len(vector) != 3 or any(
                        not isinstance(v, (float, int)) or isinstance(v, bool) or not math.isfinite(v) for v in vector):
                    raise GaugeError('Gauge adapter attachment needs finite point/radial vectors')
    return dict(schema=1, carId=config['CarId'], state=profile['state'], instruments=instruments)
