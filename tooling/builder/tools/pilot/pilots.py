"""Prepare C21/S16 source-inspection projects. Never installs into Derail Valley.

All writes are constrained to this workflow directory. Source packages and the
G29 handover are read-only inputs. Uses Python's standard library only.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workspace import WORKSPACE, CONFIG, MACHINE, location
ROOT=WORKSPACE/'reference/private/pilot-import-work'
SOURCE=WORKSPACE/'reference/private/pilot-original'
TOOLS=Path(__file__).resolve().parent
CATALOG=location(CONFIG['sourceCatalog'])
G29=WORKSPACE/'reference/private/g29-original'
PILOTS = {
    'c21': ('ls-280-c21', 'c21', 'C21'),
    's16': ('ls-060-s16', 'ls-060-s16', 'S16'),
}


def inside(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f'Output outside workflow workspace: {path}')
    return path


def write_json(path, value):
    path = inside(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(script, *args):
    subprocess.run([sys.executable, str((TOOLS.parent if script == 'resolve_clip_paths.py' else TOOLS) / script), *map(str, args)],
                   cwd=ROOT, check=True)


def find_prefab(assets, filename):
    hits = [p for p in assets.rglob('*.prefab') if p.name.casefold() == filename.casefold()]
    if len(hits) != 1:
        raise ValueError(f'Expected one {filename} under {assets}; found {hits}')
    return hits[0]


def guid_index(assets):
    result = {}
    for meta in assets.rglob('*.meta'):
        match = re.search(r'^guid: (\w+)', meta.read_text(encoding='utf-8-sig'), re.M)
        if match:
            guid = match[1]
            if guid in result:
                raise ValueError(f'Duplicate GUID {guid}: {meta} and {result[guid]}')
            result[guid] = meta.with_suffix('')
    return result


def package_import(package, project):
    with tarfile.open(package, 'r:gz') as archive:
        groups = {}
        for member in archive.getmembers():
            key, sep, leaf = member.name.partition('/')
            if sep:
                groups.setdefault(key, {})[leaf] = member
        for members in groups.values():
            if 'pathname' not in members:
                continue
            relative = archive.extractfile(members['pathname']).read().decode().splitlines()[0]
            if not relative.startswith('Assets/'):
                raise ValueError(f'Unexpected package path: {relative}')
            dest = inside(project / relative)
            if not dest.is_relative_to(project):
                raise ValueError(f'Package path escapes project: {relative}')
            if 'asset' in members:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(archive.extractfile(members['asset']).read())
            else:
                dest.mkdir(parents=True, exist_ok=True)
            if 'asset.meta' in members:
                Path(str(dest) + '.meta').write_bytes(archive.extractfile(members['asset.meta']).read())


def manifest(key):
    ident, export, prefix = PILOTS[key]
    definitions = read_json(CATALOG / ident / 'Definitions.json')
    objects = definitions['objects']
    loco = next(o for o in objects if o['identifier'] == ident)
    packs = {ident}
    unresolved = []
    references = []
    for obj in objects:
        for comp in obj['definition'].get('components', []):
            if comp['kind'] == 'PrefabModelComponent':
                model = comp['model']
                pack = model['assetPackIdentifier'].replace('\\', '/').split('/')[-1]
                packs.add(pack)
                catalog = read_json(CATALOG / pack / 'Catalog.json')
                asset = catalog['assets'].get(model['assetIdentifier'])
                if asset is None:
                    raise ValueError(f'Unresolved part: {pack}/{model["assetIdentifier"]}')
                references.append({'owner': obj['identifier'], 'component': comp['name'],
                                   'pack': pack, 'asset': model['assetIdentifier'], 'filename': asset['filename'],
                                   'transform': comp['transform'], 'parent': comp.get('parent'),
                                   'source_enabled': comp.get('enabled', True)})
            if comp.get('textureName'):
                unresolved.append({'kind': 'decal_texture', 'id': comp['textureName']})
            if comp.get('defaultWhistleIdentifier'):
                unresolved.append({'kind': 'source_whistle', 'id': comp['defaultWhistleIdentifier']})
    records = []
    for pack in sorted(packs):
        for file in sorted((CATALOG / pack).iterdir()):
            if file.is_file():
                records.append({'path': str(file.relative_to(WORKSPACE)), 'sha256': sha(file)})
    if loco['definition'].get('tenderIdentifier'):
        tender = next(o for o in objects if o['identifier'] == loco['definition']['tenderIdentifier'])
        if tender['definition']['truckIdentifier'] != 'fox-truck-2s':
            raise ValueError('Pilot only supports the verified Fox-truck-2s dependency.')
        for file in (WORKSPACE / 'reference/private/FoxTrucks' / 'FoxTrucks').iterdir():
            if file.is_file():
                records.append({'path': str(file.relative_to(WORKSPACE)), 'sha256': sha(file)})
    result = {
        'pilot': key, 'locomotive': ident, 'prefix': prefix, 'main_export': export,
        'stage': 'source inspection; not a playable DV conversion',
        'unity_version': '2019.4.40f1', 'car_creator_version': '3.1.9',
        'source_objects': objects, 'part_references': references,
        'required_packs': sorted(packs), 'source_hashes': records,
        'external_fidelity_references': list({(v['kind'], v['id']): v for v in unresolved}.values()),
        'appearance_policy': 'Livery/optional parts must be explicitly selected after source inspection; enabled flags are not a selection rule.',
        'build_state': 'Not configured. Cab measurements, mechanical assignments and simulation calibration are required before export.',
    }
    write_json(ROOT / 'analysis' / key / 'source_inventory.json', result)
    return result


def prepare(key):
    ident, export, prefix = PILOTS[key]
    source = SOURCE / 'assetripper' / export / 'ExportedProject'
    project = inside(ROOT / 'unity' / f'{prefix}_CCL')
    if project.exists():
        raise FileExistsError(f'Project already exists; preserved without overwrite: {project}')
    data = manifest(key)
    # Fail before creating the project if an export is missing.
    for pack in data['required_packs']:
        if pack != ident and not (SOURCE / 'assetripper' / pack / 'ExportedProject' / 'Assets').is_dir():
            raise FileNotFoundError(f'Missing export: {pack}')
    shutil.copytree(source, project, ignore=shutil.ignore_patterns('Library', 'Temp', 'Logs', 'obj'))
    assets = project / 'Assets'
    analysis = inside(ROOT / 'analysis' / key)
    analysis.mkdir(parents=True, exist_ok=True)
    # Target project settings are already proven by the G29 workflow.
    for folder in ['ProjectSettings', 'Packages']:
        shutil.copytree(G29 / 'unity' / 'G29_CCL' / folder, project / folder, dirs_exist_ok=True)
    run('resolve_clip_paths.py', source / 'Assets', analysis / 'clip_paths.json', '--apply', assets)
    clip_report = json.loads((analysis / 'clip_paths.json').read_text())
    if clip_report.get('errors') or not clip_report.get('applied') or not clip_report.get('clips'):
        raise ValueError(f'Unresolved main animation bindings: {analysis / "clip_paths.txt"}')
    imported = {}
    for ref in data['part_references']:
        pack = ref['pack']
        asset_key = (pack, ref['filename'])
        if asset_key not in imported:
            src_assets = SOURCE / 'assetripper' / pack / 'ExportedProject' / 'Assets'
            prefab = find_prefab(src_assets, ref['filename'])
            subfolder = f'LLWParts/{pack}'
            run('copy_deps.py', src_assets, prefab.relative_to(src_assets), assets, subfolder)
            imported[asset_key] = 'Assets/' + subfolder + '/' + prefab.relative_to(src_assets).as_posix()
        ref['unity_prefab'] = imported[asset_key]
    truck = None
    if key == 'c21':
        fox_assets = G29 / 'assetripper' / 'export_fox' / 'ExportedProject' / 'Assets'
        # Reuse only when the provided source bundle is identical to its preserved input.
        if sha(WORKSPACE / 'reference/private/FoxTrucks' / 'FoxTrucks' / 'Bundle') != sha(G29 / 'source' / 'FoxTrucks' / 'Bundle'):
            raise ValueError('Fox bundle differs from the preserved export input; re-export it first.')
        prefab = find_prefab(fox_assets, 'Fox-Truck-2s.prefab')
        run('copy_deps.py', fox_assets, prefab.relative_to(fox_assets), assets, 'FoxTrucks')
        truck = 'Assets/FoxTrucks/' + prefab.relative_to(fox_assets).as_posix()
        # Restore the dependency clip too, not only the locomotive clips.
        run('resolve_clip_paths.py', fox_assets, analysis / 'fox_clip_paths.txt', '--apply', assets / 'FoxTrucks')
    package_import(Path(MACHINE['carCreator']), project)
    editor = assets / 'Editor'
    editor.mkdir(exist_ok=True)
    for script in (SOURCE / 'tools' / 'unity').glob('*.cs'):
        shutil.copy2(script, editor / script.name)
    paths = []
    targets = []
    for obj in data['source_objects']:
        prefab = find_prefab(assets, obj['definition']['modelIdentifier'] + '.prefab')
        path = prefab.relative_to(project).as_posix()
        cls = prefix + ('TenderDefs' if obj['identifier'].startswith('lt-') else 'Defs')
        targets.append(f'{cls}={obj["identifier"]}={path}')
        paths.append({'id': obj['identifier'], 'prefab': path})
    run('gen_defs.py', CATALOG / ident / 'Definitions.json', assets, editor / f'{prefix}Defs.cs', *targets)
    # Full JSON is authoritative source data; generated classes are a convenience view.
    write_json(assets / 'PilotSource.json', data)
    probe = {'pilot': key, 'vehicles': paths,
             'parts': [{'id': f'{p}/{f}', 'prefab': path} for (p, f), path in imported.items()],
             'truck': truck or ''}
    write_json(assets / 'PilotProbeInput.json', probe)
    data['project'] = str(project.relative_to(ROOT))
    data['vehicle_prefabs'] = paths
    data['truck_prefab'] = truck
    data['guid_count'] = len(guid_index(assets))
    write_json(ROOT / 'config' / f'{key}.json', data)
    write_json(analysis / 'preparation.json', {'status': 'prepared', 'project': str(project),
        'vehicles': paths, 'unique_guids': data['guid_count'], 'source_hashes': data['source_hashes'],
        'runtime_validated': False, 'ccl_car_exported': False})
    print(f'{key}: prepared {project}; {data["guid_count"]} unique GUIDs; no game installation')


def verify(key):
    data = read_json(ROOT / 'config' / f'{key}.json')
    for record in data['source_hashes']:
        if sha(WORKSPACE / record['path']) != record['sha256']:
            raise ValueError(f'Source changed: {record["path"]}')
    project = inside(ROOT / data['project'])
    guids = guid_index(project / 'Assets')
    for asset in data['vehicle_prefabs'] + [{'prefab': r['unity_prefab']} for r in data['part_references']]:
        if not (project / asset['prefab']).is_file():
            raise FileNotFoundError(asset['prefab'])
    print(f'{key}: source hashes unchanged; {len(guids)} unique GUIDs; all requested prefab files present')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inventory', 'prepare', 'verify'])
    parser.add_argument('pilot', choices=list(PILOTS))
    args = parser.parse_args()
    {'inventory': manifest, 'prepare': prepare, 'verify': verify}[args.action](args.pilot)
