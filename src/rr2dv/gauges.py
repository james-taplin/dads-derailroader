"""Bespoke fitting input for the initial C-25 pressuremeter pilot.

Only numerical fits/resource names ship; donor game geometry is resolved by CCL.
Other locomotives keep their existing instruments until their fits are reviewed.
"""
import json
import math
from pathlib import Path


class GaugeError(ValueError):
    pass


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
        raise GaugeError('Gauge pilot requires an acceptance state')
    instruments = profile.get('instruments')
    if not isinstance(instruments, list) or not instruments:
        raise GaugeError('Gauge pilot has no instruments')
    config = record['config']
    components = config['Components']
    components = components.get('value', []) if isinstance(components, dict) else components
    seen = set()
    for fit in instruments:
        reading = fit.get('reading')
        if reading not in ('boiler', 'brake', 'speed', 'chest') or reading in seen:
            raise GaugeError('Unknown or duplicate pilot gauge reading')
        seen.add(reading)
        matches = [c for c in components if c.get('kind') == 'Gauge' and c.get('name') == fit.get('sourceGauge')]
        if len(matches) != 1:
            raise GaugeError(f"Pilot gauge {fit.get('sourceGauge')!r} must resolve uniquely")
        style = json.loads(matches[0]['extra']).get('style')
        if (reading in ('boiler', 'chest') and style != 'BoilerPressure'
                or reading == 'brake' and style != 'DualBrakeCylinderLine'
                or reading == 'speed' and not str(style).startswith('Speedometer')):
            raise GaugeError('Pilot gauge style does not match its intended reading')
        if reading == 'boiler' and fit['sourceGauge'] != config.get('MainPressureGauge'):
            raise GaugeError('Pilot boiler gauge is not the main boiler instrument')
        for field, size in (('position', 3), ('rotation', 4), ('supportPoint', 3)):
            vector = fit.get(field)
            if not isinstance(vector, list) or len(vector) != size or any(
                    not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in vector):
                raise GaugeError(f'Invalid gauge {field}')
        if abs(sum(v*v for v in fit['rotation'])-1) > .001:
            raise GaugeError('Gauge rotation must be a unit quaternion')
        if isinstance(fit.get('scale'), bool) or not isinstance(fit.get('scale'), (float, int)) or not .5 <= fit['scale'] <= 1.5:
            raise GaugeError('Pilot gauge scale is outside the reviewed range')
        if not fit.get('supportPath') or not fit.get('evidence'):
            raise GaugeError('Pilot gauge requires measured support evidence')
    return dict(schema=1, carId=config['CarId'], state=profile['state'], instruments=instruments)
