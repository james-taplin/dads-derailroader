"""Read LLW and installed dependency metadata; emit a design inventory only.

Does not extract bundles, prepare Unity projects, or install anything. Every
output stays in LLW Pilot Workflows/analysis/catalogue. Original files are read-only.
"""
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / 'LLW Generic Locomotive Catalog'
MODS = Path('B:/SteamLibrary/steamapps/common/Railroader/Mods')
OUT = ROOT / 'analysis/catalogue'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def file_record(path):
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)}


def emit(name, value):
    dest = (OUT / name).resolve()
    if not dest.is_relative_to(ROOT):
        raise ValueError('Output outside workflow workspace')
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def main():
    objects, origins, catalogs, repairs = {}, {}, {}, []
    source_files = sorted(SOURCE.rglob('Definitions.json'))
    for path in source_files:
        for obj in read(path).get('objects', []):
            ident = obj['identifier']
            if ident in objects:
                raise ValueError(f'Duplicate source identifier: {ident}')
            objects[ident], origins[ident] = obj, path
    for path in sorted(SOURCE.rglob('Catalog.json')):
        try:
            data = read(path)
        except json.JSONDecodeError:
            raw = path.read_text(encoding='utf-8-sig')
            edits = []
            if path.parent.name == 'k50parts':
                broken, fixed = '"name": "headlight5,', '"name": "headlight5",'
                if raw.count(broken) != 1:
                    raise
                edits.append({'find': broken, 'replace': fixed})
                raw = raw.replace(broken, fixed)
            elif path.parent.name != 'k35parts':
                raise
            match = re.search(r',\s*}\s*}\s*$', raw)
            if match:
                broken, fixed = match.group(), match.group()[1:]
                edits.append({'find': broken, 'replace': fixed})
                raw = raw.replace(broken, fixed)
            data = json.loads(raw)
            repairs.append({'source': file_record(path), 'status': 'design-only in-memory parse repair',
                            'edits': edits,
                            'policy': 'Original untouched; future exporter needs a hashed working overlay.'})
        catalogs[path.parent.name.casefold()] = (path, data)

    # Index metadata providers, never infer a provider from a consumer's field.
    definitions, assets = defaultdict(list), defaultdict(list)
    scan_errors, scanned = [], 0
    for path in sorted(MODS.rglob('*.json')):
        if path.name.casefold() not in ('definitions.json', 'catalog.json'):
            continue
        scanned += 1
        try:
            data = read(path)
        except (json.JSONDecodeError, UnicodeError) as exc:
            scan_errors.append({'path': str(path), 'error': str(exc)})
            continue
        if not isinstance(data, dict):
            continue
        for obj in data.get('objects', []) or []:
            if isinstance(obj, dict) and obj.get('identifier') and obj.get('definition'):
                definitions[obj['identifier']].append({'path': str(path), 'object': obj})
        for ident, entry in (data.get('assets') or {}).items():
            assets[ident].append({'catalog': str(path), 'pack': data.get('identifier'),
                                  'asset': entry, 'bundle_exists': (path.parent / 'Bundle').is_file()})

    locos = sorted(k for k, v in objects.items() if v['definition']['kind'] == 'SteamLocomotive')
    # Railroader serializes tender definitions as kind Car, with LT identifiers.
    tenders = sorted(k for k, v in objects.items() if k.startswith('lt-') and v['definition']['kind'] == 'Car')
    # Retain all source values, including auxiliary wheelset records, unchanged.
    rows, needed_images, needed_whistles, needed_trucks = [], set(), set(), set()
    for ident in locos:
        obj = objects[ident]
        definition = obj['definition']
        tender = definition.get('tenderIdentifier')
        owners = [ident] + ([tender] if tender else [])
        references, images, whistles, packs, issues = [], set(), set(), set(), []
        for owner in owners:
            if owner not in objects:
                raise ValueError(f'Missing cross-package tender: {owner}')
            packs.add(origins[owner].parent.name)
            for comp in objects[owner]['definition'].get('components', []) or []:
                if comp.get('textureName'):
                    images.add(comp['textureName'])
                if comp.get('defaultWhistleIdentifier'):
                    whistles.add(comp['defaultWhistleIdentifier'])
                if comp.get('kind') != 'PrefabModelComponent':
                    continue
                model = comp['model']
                pack = model['assetPackIdentifier'].replace('\\', '/').split('/')[-1]
                asset_id = model['assetIdentifier']
                packs.add(pack)
                catalog = catalogs.get(pack.casefold())
                entry = catalog[1]['assets'].get(asset_id) if catalog else None
                ref = {'owner': owner, 'component': comp.get('name'), 'pack': pack,
                       'asset': asset_id, 'filename': entry.get('filename') if entry else None,
                       'status': 'metadata_linked' if entry else 'missing_catalog_entry'}
                references.append(ref)
                if not entry:
                    issues.append(f'Unresolved part {pack}/{asset_id}')
        truck = objects[tender]['definition'].get('truckIdentifier') if tender else None
        if truck:
            needed_trucks.add(truck)
        needed_images.update(images)
        needed_whistles.update(whistles)
        if any(p.casefold() == 'k50parts' for p in packs):
            issues.append('k50parts/Catalog.json needs working-copy quote and trailing-comma repair')
        if any(p.casefold() == 'k35parts' for p in packs):
            issues.append('k35parts/Catalog.json needs strict-JSON trailing-comma repair')
        family = ident.split('-')[-1].upper()
        if ident.endswith('-rv'):
            family = 'C35'
        for base in ['S16', 'C48', 'K35', 'P39', 'D47']:
            if base in family:
                family = base
        wave = {'S16': 1, 'C21': 1, 'G29': 0, 'S32': 2, 'S44': 2, 'G19': 2,
                'C35': 2, 'S34': 3, 'C48': 3, 'K27': 4, 'K35': 4, 'K50': 4,
                'K56': 4, 'P39': 5, 'D47': 5, 'L29': None}[family]
        rows.append({'id': ident, 'name': obj['metadata']['name'], 'family': family,
                     'wave': wave, 'scope': 'advanced_separate' if family == 'L29' else 'conventional',
                     'stage': 'design only; see pilot evidence separately',
                     'source_definition': str(origins[ident]), 'tender': tender or None, 'truck': truck,
                     'source_main_driver_index': definition.get('mainDriverIndex'),
                     'source_wheelsets': definition.get('wheelsets'),
                     'required_packs': sorted(packs), 'part_references': references,
                     'images': sorted(images), 'whistles': sorted(whistles), 'issues': sorted(set(issues))})

    # Include extra tender truck types without silently extending main work scope.
    extra_trucks = {objects[t]['definition'].get('truckIdentifier') for t in tenders} - needed_trucks - {None, ''}
    dependencies = []
    for ident in sorted(needed_images):
        filename = ident.removeprefix('msl-decal-pack.')
        path = MODS / 'MSLDecalPack/LegosLogosFolder' / filename
        dependencies.append({'id': ident, 'kind': 'image',
                             'status': 'exact_loose_file' if path.is_file() else 'not_found',
                             'file': file_record(path) if path.is_file() else None,
                             'next': 'Import with matching source crop, placement and transparency.'})
    for ident in sorted(needed_whistles):
        hits = assets.get(ident, [])
        audio_hits = [h for h in hits if h['asset'].get('type') == 'audio']
        providers = [p for p in definitions.get(ident, []) if p['object']['definition'].get('kind') == 'Whistle']
        model_refs = []
        for provider in providers:
            model = provider['object']['definition'].get('model') or {}
            model_hits = [h for h in assets.get(model.get('assetIdentifier'), [])
                          if h['pack'] == model.get('assetPackIdentifier')]
            model_refs.append({'reference': model, 'candidates': model_hits})
        dependencies.append({'id': ident, 'kind': 'whistle',
                             'status': 'audio_catalog_candidates' if audio_hits else 'audio_not_found_in_scanned_catalogs',
                             'definitions': providers, 'audio_candidates': audio_hits, 'model_links': model_refs,
                             'next': 'Extract and compare exact AudioClip; resolve duplicate pack IDs and record loop/pitch settings. Definition alone does not prove audio availability.'})
    for ident in sorted(needed_trucks | extra_trucks):
        providers = [p for p in definitions.get(ident, []) if p['object']['definition'].get('kind') == 'Truck']
        links = []
        for p in providers:
            model = p['object']['definition'].get('modelIdentifier')
            links.extend(assets.get(model, []))
            if model not in assets:
                for asset_id, candidates in assets.items():
                    if asset_id.casefold() == model.casefold():
                        links.extend([dict(h, identifier_case_difference={'requested': model, 'catalog': asset_id}) for h in candidates])
        alternate = assets.get(ident, []) if not links else []
        dependencies.append({'id': ident, 'kind': 'truck', 'extra_tender_only': ident in extra_trucks,
                             'status': 'definition_and_catalog' if providers and links else 'incomplete_or_not_found',
                             'definitions': providers, 'model_candidates': links,
                             'identifier_candidates_requiring_review': alternate,
                             'next': 'Inspect extracted mesh, axle diameter, pivot, wheel transforms and brake animation before DV use.'})

    files = {}
    for item in dependencies:
        for node in walk(item):
            for key in ('path', 'catalog'):
                value = node.get(key)
                if not isinstance(value, str):
                    continue
                path = Path(value)
                if path.is_file():
                    files[str(path)] = path
                    if path.name.casefold() in ('catalog.json', 'definitions.json'):
                        bundle = path.parent / 'Bundle'
                        if bundle.is_file():
                            files[str(bundle)] = bundle
    relevant_mods = {path.relative_to(MODS).parts[0] for path in files.values()}
    for mod in relevant_mods:
        for path in (MODS / mod).glob('*'):
            if path.name.casefold() == 'info.json':
                files[str(path)] = path
    snapshots = [file_record(p) for p in sorted(files.values())]
    comparisons = []
    for path in source_files + sorted(SOURCE.rglob('Catalog.json')):
        installed = MODS / SOURCE.name / path.relative_to(SOURCE)
        comparisons.append({'relative_path': path.relative_to(SOURCE).as_posix(),
                            'source_sha256': sha(path),
                            'installed_sha256': sha(installed) if installed.is_file() else None,
                            'identical': installed.is_file() and sha(path) == sha(installed)})
    report = {'schema_version': 1, 'source_root': str(SOURCE), 'mods_root': str(MODS),
              'scope': '24 conventional locomotives; L29 separately deferred; no new fleet builds',
              'counts': {'locomotives': len(locos), 'conventional': sum(r['scope'] == 'conventional' for r in rows),
                         'all_tenders': len(tenders), 'referenced_tenders': len({r['tender'] for r in rows if r['tender']}),
                         'scanned_mod_metadata_files': scanned},
              'locomotives': rows, 'all_tender_definitions': [objects[t] for t in tenders],
              'parse_repairs': repairs, 'scan_errors': scan_errors,
              'installed_catalogue_comparison': comparisons}
    emit('fleet_inventory.json', report)
    emit('dependency_registry.json', {'dependencies': dependencies, 'source_files': snapshots,
                                    'coverage': 'All parseable Definitions.json and Catalog.json under Mods plus exact MSL image files. Malformed metadata listed in fleet inventory; DLL contents and bundle payloads not audited.',
                                    'release_rights': 'Not inferred from installation; retain individual dependency attribution.'})
    print(json.dumps({'counts': report['counts'], 'scan_errors': len(scan_errors),
                      'source_differences': sum(not r['identical'] for r in comparisons),
                      'dependencies': [{'id': d['id'], 'status': d['status']} for d in dependencies],
                      'output': str(OUT)}, indent=2))


if __name__ == '__main__':
    main()
