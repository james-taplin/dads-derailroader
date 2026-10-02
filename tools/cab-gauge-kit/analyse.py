"""Summarise a completed gauge-kit receipt by the actual readings, not gauge names.

This describes existing installed slots. It does not certify a replacement fits.
No game assets are read or copied by this report step.
"""
import argparse
import csv
import json
from pathlib import Path

from run import IDS


def readings(gauge):
    needles = gauge.get('needles') or []
    ports = ';'.join(n.get('port', '') for n in needles)
    readers = ';'.join(n.get('reader', '') for n in needles)
    result = set()
    for key, port in [('boiler', 'boiler.PRESSURE'),
                      ('chest', 'steamEngine.STEAM_CHEST_PRESSURE'),
                      ('speed', 'traction.WHEEL_SPEED_KMH_EXT_IN')]:
        if 'portId='+port+';' in ports+';':
            result.add(key)
    if 'IndicatorBrakeCylinderReaderProxy' in readers and 'IndicatorBrakePipeReaderProxy' in readers:
        result.add('brake')
    return result


def candidate(gauge):
    return (not gauge.get('error') and gauge['orientation'] == 'rear-facing'
            and gauge['mounting'] == 'supported-candidate'
            and all(n.get('referenceValid') for n in gauge.get('needles') or []))


def describe(gauges):
    if not gauges:
        return 'No physical dial'
    # Prefer complete support and a face aimed rearward; names do not determine the reading.
    gauge = min(gauges, key=lambda g: (not candidate(g),
                                      g['mounting'] != 'supported-candidate', g['rearAngle']))
    if gauge.get('error'):
        return 'Measurement failed'
    face = 'rear' if gauge['orientation'] == 'rear-facing' else (
        'sideways' if gauge['orientation'] == 'sideways' else f"angled {gauge['rearAngle']:.0f} deg")
    mount = {'supported-candidate': 'supported candidate',
             'unsupported-within-30mm': 'unsupported',
             'partial-support-review': 'partial support',
             'intersects-surface': 'intersects surface'}.get(gauge['mounting'], 'unmeasured')
    return face+'; '+mount


def summarise(data):
    findings = data.get('findings') or []
    ids = [f['id'] for f in findings]
    if not data.get('completed') or len(ids) != 21 or set(ids) != set(IDS):
        raise ValueError('Requires a completed receipt with all 21 unique locomotive IDs')
    rows = []
    for finding in findings:
        if finding.get('error') or any(g.get('error') for g in finding['gauges']):
            raise ValueError('Receipt contains a failed measurement')
        groups = {key: [g for g in finding['gauges'] if key in readings(g)]
                  for key in ('boiler', 'brake', 'speed', 'chest')}
        row = dict(loco=finding['id'], boiler=describe(groups['boiler']),
                   main_brake=describe(groups['brake']), speed=describe(groups['speed']),
                   chest=describe(groups['chest']),
                   chest_decision='existing candidate slot' if any(candidate(g) for g in groups['chest'])
                   else 'rework existing slot' if groups['chest'] else 'defer until a mount is demonstrated',
                   inspected_bundle_sha256=finding['sha256'])
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipt', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    rows = summarise(json.loads(args.receipt.read_text()))
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output/'fleet.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    text = '| Loco | Boiler | Main brake: pipe + cylinder | Speed | Optional chest |\n'
    text += '|---|---|---|---|---|\n'
    for row in rows:
        code = row['loco'].upper()
        code = code[:1]+'-'+code[1:]
        text += '| '+' | '.join((code, row['boiler'], row['main_brake'], row['speed'], row['chest']))+' |\n'
    (args.output/'fleet-table.md').write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
