"""Reviewed physical specifications, explicit simulation adjustments and labelled estimates."""
from __future__ import annotations

import copy
import math

from .record import (INCH_M, LBF_N, env, equivalent_bore_m, safety_bar,
                     injector_l_s, firebox_estimate)

# key, label, unit, minimum, maximum, effect
FIELDS = (
    ('boreIn', 'Cylinder bore', 'in', 1, 60, 'Physical bore; equivalent-bore profile retains its existing calibration method.'),
    ('strokeIn', 'Piston stroke', 'in', 1, 100, 'Sets simulation piston stroke.'),
    ('pressurePsi', 'Working boiler pressure', 'psi gauge', 5, 1000, 'Sets safety opening pressure; reseats 3 psi below this.'),
    ('heatingFt2', 'Total heating area', 'ft²', 1, 20000, 'Scales the existing injector and firebed estimates; not a measured evaporation rate.'),
    ('boilerDiameterM', 'Simulation boiler diameter', 'm', .1, 6, 'Optional. Blank keeps the current DV boiler basis; not the outer cladding diameter.'),
    ('boilerLengthM', 'Simulation boiler length', 'm', .1, 30, 'Optional. Enter with diameter; affects boiler capacity and thermal response.'),
    ('boilerCapacityFactor', 'Boiler capacity multiplier', '×', .01, 10, 'Optional simulation adjustment. Blank keeps the current basis factor.'),
    ('fuelMultiplier', 'Coal consumption adjustment', '×', .05, 20, 'Simulation setting, not a historical fuel-use figure. 1 retains normal consumption.'),
    ('driverWeightLb', 'Weight on driven wheels', 'lb', 1, 2000000, 'Reference for factor of adhesion only; does not change locomotive mass or axle loading.'),
    ('referenceTeLbf', 'Published tractive effort', 'lbf', 1, 1000000, 'Optional comparison figure; does not force the simulation to match it.'),
)
KEYS = {f[0] for f in FIELDS}
SOURCE = {'boreIn': 'pistonDiameterInches', 'strokeIn': 'pistonStrokeInches',
          'pressurePsi': 'maximumBoilerPressure', 'heatingFt2': 'totalHeatingSurface',
          'driverWeightLb': 'weightOnDrivers', 'referenceTeLbf': 'publishedTractiveEffort'}
HOOKS = {'boilerDiameterM': ('boiler', 'diameter'), 'boilerLengthM': ('boiler', 'length'),
         'boilerCapacityFactor': ('boiler', 'capacityMultiplier'),
         'fuelMultiplier': ('firebox', 'coalConsumptionMultiplier')}
# Pinned CCL 3.1.9 BoilerDefinitionProxy.ApplyS060Defaults / ApplyS282Defaults.
# These are inherited simulation values, not measurements of the source locomotive.
BOILER_BASIS = {0: (1.25, 4.6, .85, 3600), 1: (1.7, 8.8, .85, 13000)}


def defaults(record, source):
    values, provenance = {}, {}
    sim = record.get('hooks', {}).get('SimSpec', {})
    basis_id = record.get('config', {}).get('SimBasis')
    if isinstance(basis_id, dict): basis_id = basis_id.get('value')
    boiler = BOILER_BASIS.get(basis_id)
    for key, label, unit, lo, hi, effect in FIELDS:
        value, basis, evidence = None, 'unknown', 'Not supplied; keep blank unless you have a reliable value.'
        if key in SOURCE:
            value = source.get(SOURCE[key])
            basis, evidence = 'source', 'Definitions.' + SOURCE[key]
        elif key in HOOKS:
            component, field = HOOKS[key]
            wrapped = sim.get(component, {}).get(field) or {}
            value = wrapped.get('value')
            basis, evidence = wrapped.get('basis', 'DV_choice'), '; '.join(wrapped.get('evidence', []))
            if value is None and boiler and key in ('boilerDiameterM', 'boilerLengthM', 'boilerCapacityFactor'):
                value = boiler[('boilerDiameterM', 'boilerLengthM', 'boilerCapacityFactor').index(key)]
                basis, evidence = 'DV_choice', 'Inherited CCL 3.1.9 ' + ('S060' if basis_id == 0 else 'S282') + ' boiler; not a source measurement'
        if type(value) not in (float, int) or not math.isfinite(value) or not lo <= value <= hi:
            value, basis, evidence = None, 'unknown', 'Not supplied as a valid value; current simulation basis is retained.'
        values[key] = value
        provenance[key] = {'basis': basis, 'evidence': evidence, 'unit': unit}
    spawn = sim.get('boiler', {}).get('spawnWaterLevel', {}).get('value', boiler[3] if boiler else None)
    return {'values': values, 'provenance': provenance, 'spawnWaterL': spawn,
            'legacyTargetLbf': record.get('metadata', {}).get('tractiveEffort', {}).get('lbf')}


def resolve(req, values):
    """Old reviews gain current defaults; explicit blanks remain optional only where safe."""
    from .review import ReviewError
    specification = req.get('engineMetrics', {})
    original = specification.get('values', {})
    supplied = values.get('engineMetrics', {})
    if not isinstance(supplied, dict): raise ReviewError('Engine specifications must be a set of named values')
    if set(supplied) - KEYS: raise ReviewError('Unknown engine specification: ' + ', '.join(sorted(set(supplied) - KEYS)))
    result = {}
    for key, label, unit, lo, hi, effect in FIELDS:
        raw = supplied.get(key, original.get(key))
        if raw is None or raw == '':
            if key in ('boreIn', 'strokeIn', 'pressurePsi', 'heatingFt2', 'fuelMultiplier') and original.get(key) is not None:
                raise ReviewError(f'{label} cannot be blank; use Restore suggested value')
            result[key] = None
            continue
        try:
            if isinstance(raw, bool): raise ValueError()
            number = float(raw)
        except (ValueError, TypeError): raise ReviewError(f'{label} requires a number in {unit}') from None
        if not math.isfinite(number) or not lo <= number <= hi:
            raise ReviewError(f'{label} must be between {lo:g} and {hi:g} {unit}')
        result[key] = number
    if (result['boilerDiameterM'] is None) != (result['boilerLengthM'] is None):
        raise ReviewError('Enter both boiler diameter and length, or leave both blank to keep the current basis')
    if any(result[k] is not None and result[k] != original.get(k) for k in ('boreIn', 'strokeIn', 'pressurePsi')):
        if not all(result[k] for k in ('boreIn', 'strokeIn', 'pressurePsi')):
            raise ReviewError('Cylinder/pressure edits require bore, stroke and pressure together')
        if values.get('physics') == 'legacy-equivalent' and not specification.get('legacyTargetLbf'):
            raise ReviewError('Equivalent-bore edits need the original calibration target; choose a physical-bore profile or retain the defaults')
    if result['heatingFt2'] and result['heatingFt2'] != original.get('heatingFt2'):
        bed, burn = firebox_estimate(result['heatingFt2'])
        if bed <= 0 or burn <= 0 or injector_l_s(result['heatingFt2']) <= 0:
            raise ReviewError('Heating area is too small for the current firebed/injector estimate')
    return result


def legacy_target(context, metrics):
    target = context.get('legacyTargetLbf')
    if not target: return None
    for key, power in (('boreIn', 2), ('strokeIn', 1), ('pressurePsi', 1)):
        old, new = context.get('values', {}).get(key), metrics.get(key)
        if old and new: target *= (new / old) ** power
    return target


def estimates(values, context):
    """Existing .85 pressure-factor convention, generalized explicitly to cylinder count/gearing."""
    metrics = values.get('engineMetrics', {})
    def positive(value):
        try: result = float(value)
        except (ValueError, TypeError): return None
        return result if math.isfinite(result) and result > 0 else None
    m = {key: positive(metrics.get(key)) for key in KEYS}
    radius, cylinders = positive(values.get('wheelRadius')), positive(values.get('cylinders'))
    ratio = positive(values.get('gearRatio')) if values.get('physics') == 'geared' else 1
    efficiency = positive(values.get('efficiency')) if values.get('physics') == 'geared' else 1
    te = None
    if all((m['boreIn'], m['strokeIn'], m['pressurePsi'], radius, cylinders, ratio, efficiency)):
        te = .85 * m['pressurePsi'] * m['boreIn'] ** 2 * m['strokeIn'] / (2 * radius / INCH_M) * cylinders / 2 * ratio * efficiency
    diameter, length = m['boilerDiameterM'], m['boilerLengthM']
    volume = math.pi * (diameter / 2) ** 2 * length * 1000 if diameter and length else None
    return {'nominalTeLbf': te, 'nominalTeKn': te * LBF_N / 1000 if te else None,
            'factorOfAdhesion': m['driverWeightLb'] / te if m['driverWeightLb'] and te else None,
            'referenceTeLbf': m['referenceTeLbf'],
            'referenceDifferencePercent': 100 * (te / m['referenceTeLbf'] - 1) if te and m['referenceTeLbf'] else None,
            'boilerCylinderVolumeL': volume,
            'effectiveBoilerVolumeL': volume * m['boilerCapacityFactor'] if volume and m['boilerCapacityFactor'] else None,
            'legacyTargetLbf': legacy_target(context, m) if values.get('physics') == 'legacy-equivalent' else None,
            'assumption': 'Nominal double-acting simple-expansion estimate: 0.85 × gauge psi × bore² × stroke / wheel diameter × cylinders/2 × reduction × efficiency. Not measured drawbar pull; compound engines require separate calibration.'}


def apply(record, reviewed):
    """Modify only explicitly changed metrics; accepting defaults preserves working values."""
    metrics = reviewed['values'].get('engineMetrics', {})
    context = reviewed.get('engineMetrics', {})
    original = context.get('values', {})
    sim = record['hooks']['SimSpec']
    def changed(key): return metrics.get(key) is not None and metrics.get(key) != original.get(key)
    def put(component, field, value, unit, why):
        sim.setdefault(component, {})[field] = env(value, unit, 'DV_choice', why)
    if changed('strokeIn'):
        put('steamEngine', 'pistonStroke', metrics['strokeIn'] * INCH_M, 'm', 'Reviewed piston stroke, inches converted to metres')
    if changed('pressurePsi'):
        opening, closing = safety_bar(metrics['pressurePsi'])
        put('boiler', 'safetyValveOpeningPressure', opening, 'bar absolute', 'Reviewed gauge pressure converted to absolute bar')
        put('boiler', 'safetyValveClosingPressure', closing, 'bar absolute', 'Reviewed opening pressure minus 3 psi')
    if changed('heatingFt2'):
        area = metrics['heatingFt2']
        bed, burn = firebox_estimate(area)
        put('boiler', 'maxInjectorRate', injector_l_s(area), 'L/s', 'Existing E06 estimate scaled to reviewed heating area')
        put('firebox', 'maxCoalCapacity', bed, 'kg', 'Existing E06 firebed estimate scaled to reviewed heating area')
        put('firebox', 'burnTime', burn, 's', 'Existing E06 firing-rate estimate; not historical fuel consumption')
    for key, (component, field) in HOOKS.items():
        if changed(key): put(component, field, metrics[key], 'm' if key in ('boilerDiameterM', 'boilerLengthM') else '1', 'Explicit engine specification review: ' + key)
    if any(changed(k) for k in ('boilerDiameterM', 'boilerLengthM', 'boilerCapacityFactor')):
        old = [original.get(k) for k in ('boilerDiameterM', 'boilerLengthM', 'boilerCapacityFactor')]
        new = [metrics.get(k) or original.get(k) for k in ('boilerDiameterM', 'boilerLengthM', 'boilerCapacityFactor')]
        if all(old) and all(new) and context.get('spawnWaterL') is not None:
            factor = (new[0]/old[0])**2 * new[1]/old[1] * new[2]/old[2]
            put('boiler', 'spawnWaterLevel', context['spawnWaterL'] * factor, 'L', 'Preserve existing boiler fill fraction after capacity edit')
    if any(changed(key) for key in ('boreIn', 'pressurePsi', 'strokeIn')):
        if reviewed['values']['physics'] == 'legacy-equivalent':
            target = legacy_target(context, metrics)
            if target is None: raise ValueError('Equivalent-bore edits require the original tractive-effort target')
            bore = equivalent_bore_m(target, reviewed['values']['wheelRadius'], metrics['pressurePsi'], metrics['strokeIn'] * INCH_M, reviewed['values']['cylinders'])
        else: bore = metrics['boreIn'] * INCH_M
        put('steamEngine', 'cylinderBore', bore, 'm', 'Reviewed physical dimensions; selected simulation profile retained')
    record['metadata']['engineSpecifications'] = {'values': copy.deepcopy(metrics),
        'provenance': copy.deepcopy(reviewed.get('metricProvenance', {})),
        'estimates': estimates(reviewed['values'], context)}
