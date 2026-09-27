"""Compact rebuild identity: exact recorded inputs/settings, not a promise of byte-identical Unity bundles."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

from .applog import app_revision
from .jsonio import read_json, sha256_file, write_json
from .machine import UNITY_VERSION, CARCREATOR_VERSION


def capture(run, machine):
    from .unityproject import tooling_root
    here = Path(__file__).parent
    sources = {p.relative_to(here).as_posix(): sha256_file(p)
               for p in sorted(here.rglob('*')) if p.suffix in ('.py', '.cs')}
    snapshot = tooling_root()
    tools = {}
    for key in ('unity', 'assetRipper', 'carCreator'):
        path = machine.path(key)
        tools[key] = {'path': str(path) if path else None,
                      'sha256': sha256_file(path) if path and path.is_file() else None}
    run.record['rebuild_environment'] = {
        'app_revision': app_revision(), 'app_sources': sources,
        'snapshot_files': {p.relative_to(snapshot).as_posix(): sha256_file(p)
                           for p in sorted(snapshot.rglob('*')) if p.is_file()},
        'tools': tools, 'required_unity': UNITY_VERSION, 'required_carcreator': CARCREATOR_VERSION,
        'python': sys.version, 'platform': platform.platform(),
    }


def save(run):
    inv_path = run.path / 'inventory.json'
    inv = read_json(inv_path) if inv_path.is_file() else {}
    files = []
    for pack in inv.get('packs', []):
        for file in pack.get('files', []):
            files.append({'root': pack['root'], 'path': str(Path(pack['path'] or pack['name']) / file['name']),
                          'sha256': file.get('sha256')})
    files.extend({k: f.get(k) for k in ('root', 'path', 'sha256')} for f in inv.get('extra_files', []))
    recipe = {
        'schema': 1, 'seed': None,
        'reproduction': 'Same source bytes, code, tools and answers required; byte-identical bundles not verified.',
        'source_files': sorted(files, key=lambda f: (f['root'], f['path'])),
        'source_fingerprint': run.record.get('input_fingerprint'),
        'answers': run.record.get('answers', {}),
        'request': run.record['request'],
        'environment': run.record.get('rebuild_environment', {}),
        'expected_pack_files': run.record.get('pack', {}).get('files', {}),
    }
    identity = {k: recipe[k] for k in ('source_files', 'answers', 'environment')}
    recipe['recipe_sha256'] = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    write_json(run.path / 'rebuild.json', recipe)
    run.record['recipe_sha256'] = recipe['recipe_sha256']
    run.save()
