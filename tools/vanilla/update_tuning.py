"""Reconcile the master table with reviewed gauge fits and app repair status.

Only numerical fitting data and evidence are written. Historical conversion observations remain historical.
"""
import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from rr2dv import stock, oiling


def reconcile(table, profiles, baseline=None, oil_profiles=None):
    table = copy.deepcopy(table)
    if set(profiles) != set(stock.REAL_STEAM):
        raise ValueError('The measured fitting library must cover all 21 stock locomotives')
    findings = {f['id']: f for f in (baseline or {}).get('findings', [])}
    oil_profiles = oil_profiles if oil_profiles is not None else oiling.library()['profiles']
    if set(oil_profiles) != set(stock.REAL_STEAM):
        raise ValueError('The oil-cup fitting library must cover all 21 stock locomotives')
    for pack, entry in table['locos'].items():
        profile = profiles[pack]
        oil = oil_profiles[pack]
        if oil['sourceSha256'] != entry['sourceSha256']:
            raise ValueError(f'{pack}: source files changed; remeasure oil-cup fittings')
        prior_oil = entry.get('oiling', {})
        entry['oiling'] = dict(fittingLibrary='oil_fits.json', fittingProfile=pack,
            drivenAxles=len(oil['axleZ']), axleZ=oil['axleZ'], wheelRadiusM=oil['wheelRadius'], cupCount=len(oil['points']), fittings=oil['points'],
            acceptance=oil['state'],
            rule='A supported moving left/right pair for every driven axle; additional main-rod/crosshead bearing pairs where clear. '
                 'Six to twelve total, with 64-phase upright cup clearance and 12 cm cup spacing. '
                 'No running-board filler or silently disabled manual oiling. Game acceptance pending.')
        entry['oiling'].update({k: v for k, v in prior_oil.items() if k in ('gameAcceptance', 'gameEvidence')})
        if profile['sourceSha256'] != entry['sourceSha256']:
            raise ValueError(f'{pack}: source files changed; remeasure gauge fittings before regenerating the table')
        instruments = profile['instruments']
        gauge = entry['gauges']
        if 'historicalPolicy' not in gauge:
            gauge['historicalPolicy'] = {k: copy.deepcopy(gauge[k]) for k in ('generated', 'rule') if k in gauge}
        gauge.update(sourceMountCount=len(profile['sourceMounts']), generated=[],
                     physicalReadings=[g['reading'] for g in instruments],
                     sourceMounts=profile['sourceMounts'], fittings=instruments,
                     fittingLibrary='gauge_fits.json', fittingProfile=pack,
                     acceptance=profile['state'],
                     rule='Two mounts: boiler + pipe/cylinder brakes. Three: add speed. Four: add steam chest. '
                          'Complete housings use measured source supports/adapters; no neighbour-generated faces. '
                          'Numerical km/h and reservoir remain on F4; game acceptance pending.')
        finding = findings.get(pack.split('-')[-1])
        if finding:
            gauge['installedBaseline'] = dict(bundleSha256=finding['sha256'], date='2026-10-02',
                dialCount=len(finding['gauges']), nearbySupported=sum(g['mounting']=='supported-candidate' for g in finding['gauges']),
                status='measured installed baseline; predates this fleet fitting, not a new build acceptance')
        repairs = {
            'dynamoJet': {'builder': 'follows measured outward exhaust axis; blanket 180-degree reversal removed', 'gameAcceptance': 'pending'},
            'numericSpeedHud': {'builder': 'required absolute km/h; S282 fallback also for tanks', 'gameAcceptance': 'pending'},
            'tenderWheelPivots': {'builder': 'centred on measured source spindle after bogie support alignment' if entry['tender'] else 'not applicable: tank engine', 'gameAcceptance': 'pending' if entry['tender'] else 'not applicable'},
            'coupling': {'status': 'open', 'evidence': 'C-25 game test: pitches when coupled on level track and returns level when uncoupled' if pack=='ls-280-c25' else 'Fleet coupling overlaps/gaps remain under investigation'},
        }
        prior = entry.setdefault('repairs', {})
        for key, repair in repairs.items():
            if key in prior:
                repair.update({k: v for k, v in prior[key].items() if k in ('gameAcceptance', 'evidence')})
            prior[key] = repair
    table['tuningUpdated'] = '2026-10-02'
    table['tuningBasis'] = 'Source definitions + read-only installed fleet geometry + app-owned construction; all fitting candidates await game acceptance'
    return table


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--table', type=Path, default=ROOT/'src/rr2dv/stock_locos.json')
    parser.add_argument('--fits', type=Path, default=ROOT/'src/rr2dv/gauge_fits.json')
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    table = json.loads(args.table.read_text())
    profiles = json.loads(args.fits.read_text())['profiles']
    baseline = json.loads(args.baseline.read_text()) if args.baseline else None
    updated = reconcile(table, profiles, baseline)
    errors = stock.validate_table(updated)
    if errors:
        raise ValueError('; '.join(errors))
    args.table.write_text(json.dumps(updated, indent=1, sort_keys=True)+'\n', encoding='utf-8')
    print(f'Updated {len(profiles)} locomotive tuning records')


if __name__ == '__main__':
    main()
