"""Numerical, per-locomotive running-gear oil-cup fittings; no game assets."""
import copy
import json
import math
from pathlib import Path


class OilingError(ValueError):
    pass


def library(path=None):
    data = json.loads((Path(path) if path else Path(__file__).with_name('oil_fits.json')).read_text(encoding='utf-8'))
    if data.get('schema') != 1 or not isinstance(data.get('profiles'), dict):
        raise OilingError('Unsupported oil-cup fitting library')
    return data


def prepare(record, path=None, source_files=None):
    source = record['vehicleId']
    profile = library(path)['profiles'].get(source)
    if profile is None:
        from .stock import REAL_STEAM
        if source in REAL_STEAM:
            raise OilingError(f'{source}: missing measured oil-cup fitting')
        return None
    from . import stock
    if profile.get('sourceSha256') != stock.entry(source)['sourceSha256']:
        raise OilingError(f'{source}: source hashes differ from the measured oil-cup fitting')
    if source_files is not None and any(source_files.get(name) != digest for name, digest in profile['sourceSha256'].items()):
        raise OilingError(f'{source}: game files changed; remeasure the oil-cup fitting before using it')
    cfg = record['config']
    units = cfg['EngineUnits']
    units = units['value'] if isinstance(units, dict) else units
    axles = sum(len(u['DriverParts']) for u in units)
    if axles != len(profile.get('axleZ', [])) or not 1 <= axles <= 6:
        raise OilingError('Driven-axle count differs from the measured oil-cup fitting')
    if any(isinstance(z, bool) or not isinstance(z, (int, float)) or not math.isfinite(z) for z in profile['axleZ']) or len(set(profile['axleZ'])) != axles:
        raise OilingError('Driven-axle positions must be finite and distinct')
    radius = cfg['WheelRadius']
    radius = radius['value'] if isinstance(radius, dict) else radius
    if isinstance(radius, bool) or not isinstance(radius, (float, int)) or not math.isfinite(radius) or abs(radius-profile['wheelRadius']) > .0001:
        raise OilingError('Driver radius differs from the measured oil-cup fitting')
    points = profile.get('points', [])
    if len(points) < max(6, 2*axles) or len(points) > 12 or len(points) % 2:
        raise OilingError('Oil cups must cover every driven axle in pairs and total six to twelve')
    for i, point in enumerate(points):
        side = -1 if i % 2 == 0 else 1
        expected_axle = i//2 if i < axles*2 else -1
        if point.get('tag') != f"oil_{i//2+1}{'L' if side < 0 else 'R'}" or point.get('side') != side or point.get('axle') != expected_axle:
            raise OilingError('Oil-cup tags must identify a complete pair at every driven axle')
        local = point.get('local')
        if not isinstance(local, list) or len(local) != 3 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in local):
            raise OilingError('Oil-cup fitting requires a finite local position')
        if not point.get('parentPath') or not point.get('role') or not point.get('evidence'):
            raise OilingError('Oil-cup fitting requires a moving-part path and support evidence')
        phase = point.get('phase')
        if isinstance(phase, bool) or not isinstance(phase, (int, float)) or not math.isfinite(phase) or not 0 <= phase < 1:
            raise OilingError('Oil-cup support pose must be within one revolution')
    if not profile.get('state'):
        raise OilingError('Oil-cup fitting requires an acceptance state')
    return dict(schema=1, carId=cfg['CarId'], state=profile['state'], axleZ=profile['axleZ'], points=copy.deepcopy(points))
