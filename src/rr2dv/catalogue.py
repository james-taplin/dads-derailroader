"""Stage only the selected locomotive's native CCL catalogue pages for this build."""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import re
import shutil
from zipfile import BadZipFile, ZipFile

from . import stock
from .jsonio import read_json, sha256_file, write_json

DATA = Path(__file__).with_name('catalogue')
INPUT = 'Assets/Rr2dv/CatalogueInput.json'
ASSETS = 'Assets/RRStockCatalogue'


class CatalogueError(RuntimeError):
    pass


def prepare(project: Path, record: dict) -> dict | None:
    """Fresh or cached run project: import the exact pair/single page, preserving native GUIDs.

    No authoring library, global page registration or unrelated translation asset is imported.
    Synthetic/non-stock fixtures retain their previous behaviour.
    """
    loco_id = record['vehicleId']
    if loco_id not in stock.REAL_STEAM:
        return None
    index = read_json(DATA/'index.json')
    if index.get('schema') != 1 or loco_id not in index.get('locomotives', {}):
        raise CatalogueError(f'No catalogue mapping for {loco_id}; restore the complete app download')
    selected = index['locomotives'][loco_id]
    has_tender = bool(record.get('tender'))
    if len(selected) != (2 if has_tender else 1):
        raise CatalogueError(f'{loco_id}: catalogue engine/tender mapping differs from the build')
    entry = stock.entry(loco_id)
    expected_ids = {loco_id} | ({entry['tender']['id']} if has_tender else set())
    if ({p['sourceId'] for p in selected} != expected_ids
            or sum(p['kind'] == 'steam' and p['sourceId'] == loco_id for p in selected) != 1
            or sum(p['kind'] == 'tender' for p in selected) != int(has_tender)):
        raise CatalogueError(f'{loco_id}: catalogue page identities differ from the source engine/tender')
    pages = []
    for page in selected:
        cfg = record['tender']['config'] if page['kind']=='tender' and has_tender else record['config']
        pid = page['sourceId']
        if not re.fullmatch(r'l[st]-[a-z0-9-]+', pid):
            raise CatalogueError(f'Invalid catalogue page identifier: {pid!r}')
        pages.append({**page, 'carId':cfg['CarId'], 'assetName':pid+'-catalogue'})
    expected = {p['sourceId'] for p in pages}
    archive_path = DATA/'steam-pages.zip'
    files = {}
    try:
        archive = ZipFile(archive_path)
    except BadZipFile as e:
        raise CatalogueError('Damaged catalogue library; restore the complete app download') from e
    with archive:
        for name in archive.namelist():
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name:
                raise CatalogueError('Unsafe path in catalogue library')
            if not ((len(path.parts)==2 and path.parts[0] in expected) or name in {p+'.meta' for p in expected}):
                continue
            try:
                data = archive.read(name)
            except BadZipFile as e:
                raise CatalogueError(f'Damaged catalogue asset: {name}; restore the complete app download') from e
            digest = hashlib.sha256(data).hexdigest()
            if index['assets'].get(name) != digest:
                raise CatalogueError(f'Catalogue asset failed its integrity check: {name}')
            files[name] = data
    for pid in expected:
        for suffix in ['-catalogue.asset','-catalogue.asset.meta','-diagram.prefab','-diagram.prefab.meta','-icon.png','-icon.png.meta']:
            if f'{pid}/{pid}{suffix}' not in files:
                raise CatalogueError(f'Missing catalogue asset for {pid}: {suffix}')
    # This app-owned library lives only in the fresh run project, never the cache or a game install.
    target = project/ASSETS
    if target.exists():
        if target.is_symlink() or target.resolve().parent != (project/'Assets').resolve():
            raise CatalogueError('Catalogue assets must stay inside this run project')
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for name,data in files.items():
        dest=target/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(data)
    write_json(project/INPUT, {'schema':1,'locoSourceId':loco_id,'pages':pages})
    return {'edition':index['edition'], 'librarySha256':sha256_file(archive_path),
            'pages':[{k:p[k] for k in ('sourceId','carId','assetName','consist')} for p in pages],
            'termKeys':[t['key'] for p in pages for t in p['terms']]}
