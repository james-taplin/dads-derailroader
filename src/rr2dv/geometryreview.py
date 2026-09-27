"""Explicit per-car geometry corrections, tied to the exact source fingerprint."""
from __future__ import annotations

import math


def validate(data: dict, fingerprint: str, vehicle_ids: set[str]) -> dict:
    """Only the measured end-beam sampling band is currently supported; never arbitrary config."""
    if not isinstance(data, dict) or set(data) != {'schema', 'inputFingerprint', 'vehicles'} or data['schema'] != 1:
        raise ValueError('geometry review must contain schema 1, inputFingerprint and vehicles')
    if data['inputFingerprint'] != fingerprint:
        raise ValueError('geometry review belongs to different source files; remeasure the current source')
    cars = data['vehicles']
    if not isinstance(cars, dict) or not cars or set(cars) - vehicle_ids:
        raise ValueError('geometry review must name only the selected locomotive or its tender')
    for vid, fields in cars.items():
        if not isinstance(fields, dict) or set(fields) != {'EndBeamProbeHeight'}:
            raise ValueError(f'{vid}: only EndBeamProbeHeight can be reviewed here')
        band = fields['EndBeamProbeHeight']
        if not isinstance(band, dict) or set(band) != {'value', 'unit', 'basis', 'evidence'}:
            raise ValueError(f'{vid}: beam band needs value, unit, basis and evidence')
        value = band['value']
        if (not isinstance(value, list) or len(value) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in value) or
                not 0 <= value[0] < value[1] <= 2 or not .09999 <= value[1] - value[0] <= .40001):
            raise ValueError(f'{vid}: beam band must be two finite heights in 0..2 m, spanning 0.1..0.4 m')
        evidence = band['evidence']
        if (band['unit'] != 'm' or band['basis'] not in ('measured', 'derived') or
                not isinstance(evidence, list) or not evidence or
                any(not isinstance(e, str) or not e.strip() for e in evidence)):
            raise ValueError(f'{vid}: beam band needs metre units, measured/derived basis and nonempty evidence')
    return data
