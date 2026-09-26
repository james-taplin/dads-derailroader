"""Read-only source hashes, YAML dependency closure, and imported clip bindings."""
from pathlib import Path
import collections
import hashlib
import json
import re


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def transform_paths(prefab):
    names, parents, gos = {}, {}, {}
    text = prefab.read_text(encoding='utf-8-sig')
    for match in re.finditer(r'^--- !u!(\d+) &(-?\d+)[^\n]*\n(.*?)(?=^--- |\Z)',text,re.M|re.S):
        cls,fid,body = match.groups()
        if cls=='1':
            names[fid]=re.search(r'^  m_Name: (.*)$',body,re.M)[1].strip().strip('"')
        elif cls=='4':
            gos[fid]=re.search(r'm_GameObject: \{fileID: (-?\d+)\}',body)[1]
            parents[fid]=re.search(r'm_Father: \{fileID: (-?\d+)\}',body)[1]
    paths=[]
    for node in gos:
        seen=set(); parts=[]
        while parents.get(node,'0')!='0':
            if node in seen:raise ValueError('Cyclic source hierarchy')
            seen.add(node);parts.append(names[gos[node]]);node=parents[node]
        paths.append('/'.join(reversed(parts)))
    return collections.Counter(paths)


def source_closure(project, catalog, source_spec, cfg):
    project,catalog=Path(project),Path(catalog)
    errors=[]; hashes={}; visited=set(); pending=[]
    for item in source_spec.get('source_hashes',[]):
        relative=item['path'].replace('\\','/').split('/',1)[-1]
        path=catalog/relative
        if not path.is_file() or digest(path)!=item['sha256']:
            errors.append('Source package hash mismatch: '+relative)
    direct=[cfg['SrcPrefab']]+cfg.get('ExtraPrefabs',[])+cfg.get('ExtraParts',[])
    for sound in cfg.get('Sounds',[]):
        for key,value in sound.items():
            if isinstance(value,str) and value.startswith('Assets/'):
                direct.append(value)
    roots=[project/p for p in direct]
    missing=[str(p.relative_to(project)) for p in roots if not p.is_file()]
    errors.extend('Missing selected source asset: '+p for p in missing)
    guid_map={}
    for meta in (project/'Assets').rglob('*.meta'):
        found=re.search(r'^guid: ([a-fA-F0-9]{32})$',meta.read_text(encoding='utf-8-sig',errors='replace'),re.M)
        if found:
            guid=found[1].lower()
            if guid in guid_map:errors.append('Duplicate source GUID '+guid)
            guid_map[guid]=meta.with_suffix('')
    pending.extend(p for p in roots if p.is_file())
    pending.extend((project/'Assets/AnimationClip').glob('*.anim'))
    while pending:
        path=pending.pop()
        if path in visited:continue
        visited.add(path)
        if not path.is_file():
            errors.append('Missing dependency file: '+str(path));continue
        relative=path.relative_to(project).as_posix();hashes[relative]=digest(path)
        data=path.read_bytes()
        if not data.startswith(b'%YAML'):continue
        text=data.decode('utf-8-sig')
        for guid in set(re.findall(r'guid: ([a-fA-F0-9]{32})',text)):
            guid=guid.lower()
            if guid.startswith('0000000000000000'):continue # Unity built-in resources
            if guid not in guid_map:errors.append('Unresolved source GUID '+guid+' from '+relative)
            else:pending.append(guid_map[guid])
    clip_results=[]
    main=project/cfg['SrcPrefab']
    paths=transform_paths(main) if main.is_file() else {}
    for clip in sorted((project/'Assets/AnimationClip').glob('*.anim')):
        text=clip.read_text(encoding='utf-8-sig')
        # m_ClipBindingConstant.genericBindings.path stores numeric CRC hashes;
        # curve path strings are the actual transform bindings checked here.
        bindings=set(m.strip().strip('"') for m in re.findall(r'^\s+path: ?(.*)$',text,re.M) if not m.strip().isdigit())
        bad=[p for p in bindings if paths.get(p,0)!=1]
        if re.search(r'path_0x[0-9a-fA-F]+',text):bad.append('unresolved CRC32 placeholder')
        if bad:errors.append('Unresolved/ambiguous clip paths in '+clip.name+': '+repr(bad))
        clip_results.append(dict(clip=clip.name,bindings=len(bindings),errors=bad))
    if not clip_results:errors.append('No imported animation clips')
    return dict(status='failed' if errors else 'passed',errors=errors,selected_assets=direct,
                source_files=len(hashes),asset_hashes=hashes,clips=clip_results)
