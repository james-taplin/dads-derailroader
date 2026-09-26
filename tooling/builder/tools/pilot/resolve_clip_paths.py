"""Resolve all clips before applying any writes. Ambiguous mappings are errors, including tied prefabs."""
from pathlib import Path
import argparse, json, re, zlib

PAT=re.compile(r'path_0x([0-9A-Fa-f]+)_\w+')

def prefab_paths(path):
    names,parents,gameobjects={},{},{}
    for m in re.finditer(r'^--- !u!(\d+) &(-?\d+)[^\n]*\n(.*?)(?=^--- |\Z)',path.read_text(encoding='utf-8-sig'),re.S|re.M):
        cls,fid,body=m.groups()
        if cls=='1': names[fid]=re.search(r'm_Name: (.*)',body)[1].strip()
        elif cls=='4':
            gameobjects[fid]=re.search(r'm_GameObject: \{fileID: (-?\d+)\}',body)[1]
            parents[fid]=re.search(r'm_Father: \{fileID: (-?\d+)\}',body)[1]
    table={}
    for node in gameobjects:
        parts=[];seen=set()
        while parents.get(node,'0')!='0':
            if node in seen:raise ValueError('Cyclic prefab hierarchy: '+str(path))
            seen.add(node);parts.append(names[gameobjects[node]]);node=parents[node]
        full='/'.join(reversed(parts))
        for rel in {full,full.partition('/')[2]} if '/' in full else {full}:
            table.setdefault(zlib.crc32(rel.encode()),set()).add(full)
    return table

def select_mapping(hashes,tables,binding=None):
    if not hashes:return {}
    candidates=[]
    for name,table in tables:
        if binding is not None and name!=binding:continue
        if all(h in table for h in hashes):
            if any(len(table[h])!=1 for h in hashes):
                raise ValueError('Ambiguous hash/path within '+name)
            candidates.append({h:next(iter(table[h])) for h in hashes})
    if not candidates:raise ValueError('No prefab resolves every clip binding')
    if any(m!=candidates[0] for m in candidates[1:]):
        raise ValueError('Tied prefabs imply different paths; provide explicit relative-prefab binding')
    return candidates[0]

def resolve(src,report,dest=None,bindings=None):
    src=Path(src).resolve();report=Path(report);dest=Path(dest).resolve() if dest else None
    if dest==src:raise ValueError('Never rewrite original exports in place')
    tables=[(p.relative_to(src).as_posix(),prefab_paths(p)) for p in sorted(src.rglob('*.prefab'))]
    planned=[];results=[];errors=[];bindings=bindings or {}
    for path in sorted(src.rglob('*.anim')):
        rel=path.relative_to(src).as_posix();text=path.read_text(encoding='utf-8-sig')
        hashes={int(h,16) for h in PAT.findall(text)}
        try:
            mapping=select_mapping(hashes,tables,bindings.get(rel))
            planned.append((rel,PAT.sub(lambda m:mapping[int(m[1],16)],text)))
            results.append(dict(clip=rel,bindings=len(mapping),status='resolved'))
        except ValueError as e:errors.append(dict(clip=rel,error=str(e)))
    if not planned and not errors:errors.append(dict(error='No animation clips found'))
    if set(bindings)-{r['clip'] for r in results}- {e.get('clip') for e in errors}:
        errors.append(dict(error='Explicit bindings refer to missing clips'))
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(dict(clips=results,errors=errors,applied=bool(dest and not errors)),indent=2)+'\n')
    if errors:raise ValueError(f'{len(errors)} clip-resolution errors; no files written')
    if dest:
        for rel,text in planned:
            target=dest/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text,encoding='utf-8')
    return results

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('report',type=Path)
    p.add_argument('--apply',type=Path);p.add_argument('--bindings',type=Path);a=p.parse_args()
    resolve(a.source,a.report,a.apply,json.loads(a.bindings.read_text()) if a.bindings else None)
