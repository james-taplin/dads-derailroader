"""Read-only installed-pack gauge measurements. Python 3.11+, UnityPy, licensed Unity 2019.4.40f1."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import time
from zipfile import ZipFile, ZIP_DEFLATED

HERE = Path(__file__).resolve().parent
IDS = ('a23 a26 b65 c25 c40 c46 c55 d46 f71 g16 g25 k28t k35 p18 p43 p48 s23 s51 t17 t21 t22').split()
PRESSURE_MESHES = ('s060_gauge_pressuremeter', 's060_gauge_label_pressuremeter',
                   's060_gauge_glass_pressuremeter', 's060_needle_pressuremeter')


def export_donor_meshes(resources, output):
    """Private diagnostic buffers only; never included in the result or kit ZIP."""
    from types import SimpleNamespace
    import UnityPy
    env = UnityPy.load(str(resources))
    objects = [o for o in env.objects if o.type.name == 'Mesh' and o.read().m_Name in PRESSURE_MESHES]
    names = [o.read().m_Name for o in objects]
    if len(names) != len(PRESSURE_MESHES) or set(names) != set(PRESSURE_MESHES):
        raise ValueError('Missing or ambiguous DV pressuremeter donor resources')
    path = output/'donor-meshes.bin'
    export_meshes(SimpleNamespace(objects=objects), path)
    return str(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def export_meshes(env, path):
    from UnityPy.helpers.MeshHelper import MeshHandler
    meshes = [o for o in env.objects if o.type.name == 'Mesh']
    with path.open('wb') as f:
        f.write(struct.pack('<i', len(meshes)))
        for obj in meshes:
            mesh = obj.read()
            data = MeshHandler(mesh)
            data.process()
            name = mesh.m_Name.encode('utf-8')
            vertices = [n for v in data.m_Vertices for n in v]
            indices = [n for sub in data.get_triangles() for tri in sub for n in tri]
            f.write(struct.pack('<i', len(name)) + name)
            f.write(struct.pack('<i', len(vertices)//3))
            f.write(struct.pack('<' + 'f'*len(vertices), *vertices))
            f.write(struct.pack('<i', len(indices)))
            f.write(struct.pack('<' + 'i'*len(indices), *indices))


def prepare_cases(mods, output, only):
    import UnityPy
    cases = []
    seen = set()
    for bundle in sorted(mods.glob('*/ccl_bundle')):
        if not bundle.parent.name.lower().startswith('rr2dv_'):
            continue
        env = UnityPy.load(str(bundle))
        names = {o.read().m_Name for o in env.objects if o.type.name == 'GameObject'}
        for name in sorted(names):
            if not re.fullmatch(r'RR2DV_LS_[A-Z0-9_]+_interior', name):
                continue
            car_id = name.removesuffix('_interior')
            short = car_id.split('_')[-1].lower()
            if short not in IDS or (only and short not in only):
                continue
            if short in seen:
                raise ValueError(f'Duplicate installed pack for {short}; select an unambiguous Mods folder')
            seen.add(short)
            mesh = output/'meshes'/f'{short}.bin'
            mesh.parent.mkdir(exist_ok=True)
            export_meshes(env, mesh)
            cases.append(dict(id=short, carId=car_id, bundle=str(bundle.resolve()), sha256=sha(bundle), meshData=str(mesh)))
    expected = set(only or IDS)
    if seen != expected:
        raise ValueError(f'Fleet incomplete: missing {sorted(expected-seen)}; found {sorted(seen)}')
    return cases


def create_project(source, output):
    """Copy only Creator and settings into a NEW disposable project, never source Editor scripts."""
    project = output/'project'
    if project.exists():
        raise ValueError('Output project already exists; use a fresh output directory')
    if not (source/'Assets/CarCreator/Bin').is_dir():
        raise ValueError('--creator-project must contain imported Car Creator 3.1.9 Assets/CarCreator/Bin')
    for rel in ('Assets/CarCreator', 'Packages', 'ProjectSettings'):
        shutil.copytree(source/rel, project/rel)
    version = project/'ProjectSettings/ProjectVersion.txt'
    if '2019.4.40f1' not in version.read_text():
        raise ValueError('Creator project must use Unity 2019.4.40f1')
    (project/'Assets/Editor').mkdir()
    shutil.copyfile(HERE/'GaugeProbe.cs', project/'Assets/Editor/GaugeProbe.cs')
    return project


def run_unity(unity, project, output, timeout):
    env = dict(os.environ, GAUGE_INPUT=str(output/'input.json'), GAUGE_OUTPUT=str(output))
    log = output/'unity.log'
    kwargs = {}
    if os.name == 'nt':
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        info.wShowWindow = 0
        kwargs['startupinfo'] = info
    command = [str(unity), '-projectPath', str(project), '-executeMethod', 'GaugeProbe.Run', '-logFile', str(log)]
    process = subprocess.Popen(command, env=env, **kwargs)
    deadline = time.monotonic()+timeout
    try:
        while process.poll() is None:
            time.sleep(2)
            text = log.read_text(errors='replace') if log.exists() else ''
            if re.search(r'error CS\d+|Scripts have compiler errors|No valid Unity Editor license', text):
                raise RuntimeError('Unity compilation/licensing failed; see unity.log')
            if time.monotonic() > deadline:
                raise TimeoutError('Unity timed out; see unity.log')
        return process.returncode
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def report(output):
    data = json.loads((output/'result.json').read_text())
    rows = []
    for loco in data.get('findings') or []:
        for g in loco.get('gauges') or []:
            rows.append(dict(loco=loco['id'], gauge=g['path'], orientation=g['orientation'],
                             rear_angle_deg=round(g['rearAngle'], 2), upright_angle_deg=round(g['uprightAngle'], 2),
                             mounting=g['mounting'], support_of_9=g['nearSupport'], intersections=g['intersections'],
                             housing_mounting=g.get('housingMounting', ''), housing_support_of_9=g.get('housingSupport', 0),
                             diameter_mm=round(g['diameter']*1000, 1), x=g['position']['x'], y=g['position']['y'], z=g['position']['z'],
                             error=g.get('error', '')))
    with (output/'gauges.csv').open('w', newline='', encoding='utf-8') as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    sections = []
    for loco in data.get('findings') or []:
        gauges = loco.get('gauges') or []
        table = []
        for g in gauges:
            samples = g.get('samples') or []
            gaps = ', '.join(f"{s['gap']*1000:.1f}mm" if s['found'] else 'no hit' for s in samples)
            needles = '; '.join(f"{n['name']}: {n['reader']} {n['port']} [{n['min']}..{n['max']}]" for n in g.get('needles') or [])
            mount = g['mounting'] + ('; housing pad: '+g['housingMounting']+f" ({g['housingSupport']}/9)" if g.get('housingMounting') else '')
            table.append('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in (g['path'],g['orientation'],round(g['rearAngle'],1),mount,f"{g['nearSupport']}/9",gaps,needles,g.get('error','')) )+'</tr>')
        # Asset-free plan diagram: one metre = 100 pixels; rear is down.
        svg = '<svg viewBox="0 0 600 800" width="450" role="img"><rect width="600" height="800" fill="#eef2f6"/><text x="15" y="25">TOP VIEW: front up, rear/crew down; x right</text>'
        if gauges:
            zmid = sum(g['position']['z'] for g in gauges)/len(gauges)
            for i,g in enumerate(gauges):
                x=300+100*g['position']['x']; y=400-100*(g['position']['z']-zmid)
                nx=g['faceNormal']['x']; nz=g['faceNormal']['z']; color='#16854b' if g['orientation']=='rear-facing' else '#c43131'
                svg+=f'<circle cx="{x}" cy="{y}" r="6" fill="{color}"/><line x1="{x}" y1="{y}" x2="{x+40*nx}" y2="{y-40*nz}" stroke="{color}" stroke-width="3"/><text x="{x+8}" y="{y-8}">{i+1}</text>'
        svg+='</svg>'
        sections.append('<h2>'+html.escape(loco['id'])+'</h2><p>'+html.escape(loco.get('error') or '')+'</p>'+svg+
                        '<table><tr><th>Gauge (diagram order)</th><th>Facing</th><th>Rear angle</th><th>Mount</th><th>Support</th><th>Centre/rim gaps</th><th>Needle wiring</th><th>Error</th></tr>'+''.join(table)+'</table>')
    page='''<!doctype html><meta charset="utf-8"><title>Cab gauge measurements</title>
<style>body{font:15px system-ui;margin:28px;color:#182433}td,th{padding:8px;border:1px solid #ccd3da;text-align:left}table{border-collapse:collapse;font-size:12px}td{max-width:400px;overflow-wrap:anywhere}</style>
<h1>Cab gauge measurements</h1><p>Read-only exported-pack geometry. Rear-facing means within 15 degrees of -Z.
Supported candidate means at least 7/9 centre/rim samples within 30 mm behind the face, no intersection over 2 mm.
These thresholds are screening rules, not approved mounting dimensions. Brackets, labels, glass/readability, physics and game behaviour require review.
The diagram is a measurement schematic, not a rendered cab. Needle ranges are an inventory, not a calibration test.</p>'''+''.join(sections)
    (output/'report.html').write_text(page, encoding='utf-8')
    summary = dict(completed=data.get('completed', False), locomotives=len(data.get('findings') or []), gauges=len(rows),
                   rear_facing=sum(r['orientation']=='rear-facing' for r in rows),
                   supported_candidates=sum(r['mounting']=='supported-candidate' for r in rows),
                   regression=data.get('regression'))
    (output/'summary.json').write_text(json.dumps(summary, indent=2))
    return summary


def results_zip(output):
    # Deliberate allowlist: no meshes, bundles, Unity project, screenshots or machine-path logs.
    with ZipFile(output/'gauge-results.zip', 'w', ZIP_DEFLATED) as z:
        for name in ('report.html', 'gauges.csv', 'summary.json', 'result.json'):
            if (output/name).is_file():
                z.write(output/name, name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mods', type=Path, required=True)
    parser.add_argument('--unity', type=Path, required=True)
    parser.add_argument('--creator-project', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New output directory; never an existing conversion project')
    parser.add_argument('--only', help='Comma-separated loco codes, e.g. k35,p18,t21,t22; default all21')
    parser.add_argument('--timeout', type=int, default=900)
    parser.add_argument('--dv-resources', type=Path, help='Local DV resources.assets, needed for runtime-grabber gauge geometry')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error('--output must not already exist')
    only = [x.strip().lower().replace('-', '') for x in args.only.split(',')] if args.only else None
    if only and (len(set(only)) != len(only) or set(only)-set(IDS)):
        parser.error('Unknown or duplicate locomotive codes')
    output.mkdir(parents=True)
    try:
        project = create_project(args.creator_project.resolve(), output)
        cases = prepare_cases(args.mods.resolve(), output, only)
        if args.dv_resources:
            donors = export_donor_meshes(args.dv_resources.resolve(), output)
            for case in cases: case['donorMeshData'] = donors
        (output/'input.json').write_text(json.dumps(dict(cases=cases), indent=2))
        code = run_unity(args.unity.resolve(), project, output, args.timeout)
        unchanged = all(sha(c['bundle']) == c['sha256'] for c in cases)
        if not unchanged:
            raise RuntimeError('Installed bundle changed during inspection; discard measurements and rerun')
        summary = report(output)
        summary['unity_exit_code'] = code
        summary['installed_hashes_unchanged'] = unchanged
        (output/'summary.json').write_text(json.dumps(summary, indent=2))
        results_zip(output)
        print(json.dumps(summary, indent=2))
        print(output/'report.html')
        return 0 if code==0 and summary['completed'] else 1
    except Exception as e:
        (output/'failure.txt').write_text(str(e))
        print(f'Inspection incomplete: {e}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
