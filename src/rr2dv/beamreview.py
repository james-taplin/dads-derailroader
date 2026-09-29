"""A proposed end-beam geometry review, measured from the failed build's end-beam survey.

When the builder stops on an end beam, the app writes build/out/endbeam-survey.json (Rr2dvPlacement): per end, the
upright transverse faces across x -1..1 m and the builder's own default check (x -0.6..0.6 m, 1 cm depth bins, 20 rays)
for each 0.2 m band from 0.2 to 2.0 m. This turns it into a geometryreview file the user can choose to use (never applied
automatically). A band is proposed only when, at every end the builder rigs on a beam:
  - the builder's own check passes in that band (20 hits, a 20-ray depth bin);
  - the face is broad: 3 or more of those rays either side of x +-0.3 m (the builder's automatic-search rule);
  - it lies within 0.35 m of the source car end, when known (the builder's constraint);
  - the same plane (within 3 cm) is seen in another, non-overlapping band: the end structure, not a lone fitting.
Of those, the band nearest coupler height wins, then the most rays. Anything weaker gets no proposal.
"""
from __future__ import annotations

from pathlib import Path

from .jsonio import read_json, write_json

MAX_FROM_SOURCE_END_M = 0.35
SAME_PLANE_M = 0.03
MIN_RAYS = 20
MIN_SIDE_RAYS = 3


def _passes(core: dict, source_end) -> bool:
    return (core['hits'] >= MIN_RAYS and core['bin'] >= MIN_RAYS and core['binLeft'] >= MIN_SIDE_RAYS
            and core['binRight'] >= MIN_SIDE_RAYS and (source_end is None or abs(core['beam'] - source_end) <= MAX_FROM_SOURCE_END_M))


def _corroboration(end: dict, core: dict):
    return next((f for f in end.get('faces', []) if (f['high'] <= core['low'] + 1e-6 or f['low'] >= core['high'] - 1e-6)
                 and abs(f['z'] - core['beam']) <= SAME_PLANE_M and f['left'] >= 1 and f['right'] >= 1), None)


def propose(survey: dict, fingerprint: str, vehicle_id: str, run_name: str) -> tuple[dict | None, str]:
    """(review, why): a geometryreview document for this vehicle, or None and the reason there is none."""
    ends = [e for e in survey.get('ends', []) if e.get('rigged')]
    if not ends:
        return None, 'no end of this car is rigged on a measured beam'
    coupler = survey.get('couplerHeight', 1.05)
    lows = sorted({round(c['low'], 3) for e in ends for c in e.get('core', [])})
    candidates = []
    for low in lows:
        picks = []
        for e in ends:
            core = next((c for c in e.get('core', []) if round(c['low'], 3) == low), None)
            if not core or not _passes(core, e.get('sourceEnd')):
                break
            other = _corroboration(e, core)
            if not other:
                break
            picks.append((e, core, other))
        else:
            mid = low + 0.1
            candidates.append((abs(mid - coupler), -sum(c['bin'] for _, c, _ in picks), low, picks))
    if not candidates:
        return None, ('no height band gives a broad, corroborated transverse face within 0.35 m of the source car end '
                      'that passes the builder\'s own check: a manual geometry review is needed')
    _, _, low, picks = min(candidates, key=lambda c: (c[0], c[1], c[2]))
    high = round(low + 0.2, 3)
    evidence = [f"rr2dv end-beam survey, run {run_name} (build_report.txt and endbeam-survey.json); proposed by rr2dv, "
                f"accepted by the user"]
    for e, core, other in picks:
        src = e.get('sourceEnd')
        evidence.append(
            f"{e['end']}: band {low:.2f}..{high:.2f} m, the builder's own check finds {core['bin']}/{core['hits']} rays on one face "
            f"at z {core['beam']:.3f} ({core['binLeft']} left / {core['binRight']} right of 0.3 m; {', '.join(core['parts'])})"
            + (f", {core['beam'] - src:+.3f} m from the source car end {src:.3f}" if src is not None else ""))
        evidence.append(
            f"{e['end']}: the same plane at {other['low']:.2f}..{other['high']:.2f} m: z {other['z']:.3f}, {other['rays']} rays "
            f"({other['left']} left / {other['right']} right; {', '.join(other['parts'])})")
    review = {'schema': 1, 'inputFingerprint': fingerprint, 'vehicles': {vehicle_id: {'EndBeamProbeHeight': {
        'value': [round(low, 3), high], 'unit': 'm', 'basis': 'measured', 'evidence': evidence}}}}
    return review, f'band {low:.2f}..{high:.2f} m'


def write_proposal(run_path: Path, fingerprint: str, loco_id: str, tender_id: str | None,
                   reviewed: dict | None = None) -> tuple[Path | None, str]:
    """After a failed build: the proposal in the run folder (copied to the reports folder at cleanup), or why there is none.
    Bands already reviewed for this run's other car are carried over, so using the proposal keeps them (RLW RXM-1B: the
    loco's reviewed front band, then the tender's rear stopped, 2026-09-29)."""
    survey_path = run_path / 'build' / 'out' / 'endbeam-survey.json'
    if not survey_path.is_file():
        return None, ''
    survey = read_json(survey_path)
    vehicle = tender_id if survey.get('isTender') and tender_id else loco_id
    review, why = propose(survey, fingerprint, vehicle, run_path.name)
    if review is None:
        return None, why
    if reviewed and reviewed.get('inputFingerprint') == fingerprint:
        kept = {k: v for k, v in (reviewed.get('vehicles') or {}).items() if k != vehicle}
        review['vehicles'] = {**kept, **review['vehicles']}
        if kept:
            why += '; keeps the reviewed band for ' + ', '.join(sorted(kept))
    path = run_path / 'geometry-review-proposed.json'
    write_json(path, review)
    return path, why
