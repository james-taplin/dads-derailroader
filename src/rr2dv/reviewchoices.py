"""Source suggestions and automatically remembered per-source vehicle choices."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

from .jsonio import read_json, write_json

IDENTITY = ('schema', 'adapterVersion', 'vehicleId', 'fingerprint', 'catalogueHash')


def suggest(req, source):
    values, evidence = {}, {}

    def put(key, value, basis, why):
        values[key] = value
        evidence[key] = {'basis': basis, 'evidence': why}

    put('trainBrake', req.get('suggestedBrake') or 'manual-lap',
        'source' if req.get('suggestedBrake') else 'DV_choice',
        'Source brake valve' if req.get('suggestedBrake') else 'Suggested manual-lap valve; source does not specify it')
    put('spawnMode', 'radio-only', 'DV_choice', 'Suggested: spawn with the radio')
    put('spawnTracks', [], 'DV_choice', 'No automatic spawn tracks for radio-only')
    put('physics', 'legacy-equivalent', 'DV_choice', 'Existing tractive-effort approximation; confirm the appropriate steam profile')
    put('steamHeat', 'basis-approximation', 'DV_choice', 'Source thermal regime unknown; retain the DV basis')
    put('dynamo', 'yes' if req.get('sourceHasDynamo', True) else 'no', 'source',
        'The source has a Dynamo component' if req.get('sourceHasDynamo', True)
        else 'The source has no Dynamo component: no dynamo, lamps or cab light')
    if req.get('stokerEvidence'):
        put('firing', 'mechanical-stoker', 'source', 'The source has a stoker/auger component (' +
            ', '.join(req['stokerEvidence'][:3]) + '): a mechanical stoker; the shovel stays as a backup')
    else:
        put('firing', 'hand-fired', 'DV_choice', 'Railroader definitions do not say how the fire is fed: hand-fired unless you '
            'know otherwise (oil burner: tank locos only; mechanical stoker: coal fed by a steam stoker, shovel kept)')
    components = [c for c in source.get('components') or [] if isinstance(c, dict) and c.get('enabled', True)]
    heat = [c['isSuperheated'] for c in [source, *components] if type(c.get('isSuperheated')) is bool]
    if heat and len(set(heat)) == 1:
        put('steamHeat', 'superheated' if heat[0] else 'saturated', 'source', 'Explicit source isSuperheated flag')
    count = source.get('numCylinders', source.get('cylinderCount'))
    if type(count) is int and count in (2, 3, 4):
        put('cylinders', count, 'source', 'Explicit source cylinder count')
    else:
        articulated = any(c.get('kind') == 'ArticulatedSteamEngineComponent' for c in components)
        put('cylinders', 4 if articulated else 2, 'analogue_estimate',
            'Two engine units suggest four cylinders; confirm' if articulated else 'Two-cylinder starting assumption; confirm physical count')
    ratio = source.get('gearRatio')
    if type(ratio) in (int, float) and math.isfinite(ratio) and 1 < ratio <= 100:
        put('physics', 'geared', 'source', 'Explicit source gear reduction')
        put('gearRatio', ratio, 'source', 'Source gearRatio; engine RPM / wheel RPM')
        put('gearEvidence', 'Definitions.gearRatio', 'source', 'Source gearRatio')
    put('efficiency', 1, 'DV_choice', 'Ideal transmission starting assumption; confirm efficiency if geared')
    candidates = req.get('wheelCandidates') or []
    wheelsets = req.get('wheelsets') or []
    main_index = source.get('mainDriverIndex', 0)
    main = wheelsets[main_index] if type(main_index) is int and 0 <= main_index < len(wheelsets) else {}
    main_clip = (main.get('animation') or {}).get('clipName')
    high = [c for c in candidates if c.get('confidence') == 'high' and c.get('tread') and c.get('meshesUsed')]
    matched = [c for c in high if c.get('clip') == main_clip]
    # A unique measured radius is a suggestion, still confirmed in the review. A
    # shaft's nominal diameter must never win over a measured tyre candidate.
    radii = {round(c['tread'], 6) for c in high}
    # A low-confidence main-driver tread that agrees with the source size (within 10%) is a real tyre, not a shaft
    # (DM&IR M-3: 0.8001 m measured, 0.80 m source; the profile was left blank, 2026-09-28).
    source_r = main.get('diameter') / 2 if isinstance(main.get('diameter'), (int, float)) and main['diameter'] > 0 else None
    tyre_like = any(c.get('clip') == main_clip and c.get('tread') and source_r and abs(c['tread'] - source_r) <= .1 * source_r
                    for c in candidates)
    radius = req.get('initialRadius')
    if radius:
        put('wheelRadius', radius, 'DV_choice', 'Previously entered driving tyre radius')
    elif len(matched) == 1:
        put('wheelRadius', matched[0]['tread'], 'measured', 'High-confidence tyre candidate for the source main driving animation; confirm')
    elif len(radii) == 1 and not tyre_like:
        # only when the main driver is no tyre (a geared loco's shaft): then the one confident tyre elsewhere is the
        # powered wheel. A tyre-like main driver keeps its own size: the RLW RXM-1 took its trailing wheel (0.647 m,
        # high) for the 0.915 m drivers (low, 0.947 m measured), 2026-09-29.
        put('wheelRadius', high[0]['tread'], 'measured', 'Only distinct high-confidence measured tyre radius; confirm it belongs to the powered wheels')
    elif values.get('physics') != 'geared' and isinstance(main.get('diameter'), (int, float)) and main['diameter'] > 0:
        # never on a geared loco: its main driver can be a shaft, whose diameter is no tyre
        # No confident measurement: the source's own driver diameter, not a blank box or a doubtful measurement
        # (James, 2026-09-28; K-66). It has been within ~4% of the measured tyre on every loco tested so far.
        put('wheelRadius', round(main['diameter'] / 2, 4), 'source',
            'Source main driver diameter / 2 (no confident tyre measurement); confirm against the renders')
    if main_clip and not matched and not tyre_like and high and any(c.get('clip') == main_clip for c in candidates) and values['physics'] != 'geared':
        put('physics', '', 'DV_choice',
            'The source main animation is not a confirmed tyre group. Choose direct-drive approximation or geared reduction; do not treat a shaft as a driving wheel')
    values['acknowledgeExperimental'] = False
    return {'values': values, 'provenance': evidence, 'origin': 'Suggested from source data, measurements and labelled defaults'}


def profile_path(root: Path, req) -> Path:
    identity = {key: req[key] for key in IDENTITY}
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return Path(root) / 'reviews' / (key + '.json')


def prepare(req, root: Path):
    """Use exact-source saved answers, including reports made before the profile store existed."""
    from .review import resolve
    result = copy.deepcopy(req)
    direct = profile_path(root, req)
    history = Path(root) / 'reports'
    paths = [direct]
    if history.is_dir():
        paths += sorted(history.glob('*/prebuild-review.json'), key=lambda p: p.parent.name, reverse=True)
    for path in paths:
        try:
            saved = read_json(path)
            if any(saved.get(k) != req[k] for k in IDENTITY):
                continue
            resolved = resolve(req, saved)
        except (OSError, ValueError, TypeError, AttributeError, KeyError):
            continue
        values = resolved['values']
        values['acknowledgeExperimental'] = False
        result['prefill'] = {'values': values,
            'provenance': saved.get('provenance', resolved['provenance']),
            'metricProvenance': saved.get('metricProvenance', resolved.get('metricProvenance', {})),
            'origin': 'Previous choices restored for this vehicle and unchanged source'}
        break
    return result


def remember(root: Path, reviewed):
    write_json(profile_path(root, reviewed), reviewed)
