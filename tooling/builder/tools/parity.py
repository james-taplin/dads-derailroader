"""Compare serialized assets after replacing local IDs with semantic object names."""
from pathlib import Path
import argparse, collections, hashlib, json, math
from workspace import CONFIG, enable_unitypy
enable_unitypy()
import UnityPy

def signature(bundle):
    env=UnityPy.load(str(bundle));readers=list(env.objects)
    if len({o.assets_file.name for o in readers})!=1:raise ValueError('Multiple serialized files require explicit cross-file keys')
    external=[dict(path=str(x.path),guid=bytes(x.guid).hex(),type=x.type) for x in readers[0].assets_file.externals]
    data={o.path_id:o.read_typetree() for o in readers};types={o.path_id:o.type.name for o in readers}
    transforms={d['m_GameObject']['m_PathID']:i for i,d in data.items() if types[i] in ('Transform','RectTransform')}
    def tree(tid,seen=()):
        if tid in seen:raise ValueError('Transform cycle')
        t=data[tid];name=data[t['m_GameObject']['m_PathID']]['m_Name'];parent=t['m_Father']['m_PathID']
        return (tree(parent,seen+(tid,))+'/' if parent else '')+name
    def label(i):
        d=data[i];kind=types[i]
        if kind=='GameObject':return 'GameObject:'+tree(transforms[i])
        if kind=='MonoBehaviour':kind+=':'+data[d['m_Script']['m_PathID']]['m_ClassName']
        if 'm_GameObject' in d and d['m_GameObject']['m_PathID'] in transforms:
            go=d['m_GameObject']['m_PathID'];base=tree(transforms[go])
            siblings=[c['component']['m_PathID'] for c in data[go]['m_Component']]
            return kind+':'+base+':'+str(siblings.index(i))
        return kind+':'+str(d.get('m_Name',d.get('m_ClassName','')))
    labels={i:label(i) for i in data}
    def norm(v):
        if isinstance(v,dict):
            if set(v)=={'m_FileID','m_PathID'}:
                fid=v['m_FileID'];pid=v['m_PathID']
                if fid:
                    if fid<1 or fid>len(external):raise ValueError('Invalid external file reference')
                    return {'reference':str(pid),'file':external[fid-1]}
                return {'reference':labels.get(pid,str(pid)),'file':0}
            return {k:norm(x) for k,x in v.items()}
        if isinstance(v,(list,tuple)):return [norm(x) for x in v]
        if isinstance(v,bytes):return {'bytes_sha256':hashlib.sha256(v).hexdigest()}
        if isinstance(v,float):return round(v,6) if math.isfinite(v) else str(v)
        return v
    result=collections.defaultdict(list)
    for i,d in data.items():
        # AssetBundle stores serialization directory/order, not locomotive semantics.
        if types[i]=='AssetBundle':continue
        canonical=json.dumps(norm(d),sort_keys=True,separators=(',',':'),ensure_ascii=True)
        result[labels[i]].append(hashlib.sha256(canonical.encode()).hexdigest())
    return {k:sorted(v) for k,v in result.items()}

def compare(profile,run,reference):
    pack=CONFIG['profiles'][profile]['pack'];a=run/pack/'ccl_bundle';b=reference/pack/'ccl_bundle'
    actual=signature(a);expected=signature(b)
    differences=[k for k in sorted(set(actual)|set(expected)) if actual.get(k)!=expected.get(k)]
    warnings=lambda p:[l for l in (p/'build_report.txt').read_text().splitlines() if l.startswith('WARN ')]
    report=dict(schema=1,audit_kind='frozen_semantic_parity',status='passed' if not differences and warnings(run)==warnings(reference) else 'failed',
        profile=profile,reference=str(reference),bundle_sha256=hashlib.sha256(a.read_bytes()).hexdigest(),reference_bundle_sha256=hashlib.sha256(b.read_bytes()).hexdigest(),
        differing_objects=differences,object_groups=len(actual),warnings=warnings(run),warnings_match=warnings(run)==warnings(reference),
        comparator_version=2,comparison='All serialized object fields except AssetBundle directory metadata; local IDs resolved to semantic names; external file indices resolved to path/GUID/type; floats rounded to 6 decimals.',runtime_validated=False)
    (run/'parity_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','profile','object_groups','differing_objects','warnings_match')},indent=2),flush=True)
    return report['status']=='passed'

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('profile',choices=CONFIG['profiles']);p.add_argument('run',type=Path);p.add_argument('reference',type=Path);a=p.parse_args()
    raise SystemExit(0 if compare(a.profile,a.run,a.reference) else 1)
