"""Generate source-hashed fleet records; measured profiles remain separate, explicit inputs."""
from pathlib import Path
import argparse, hashlib, json, math, re

ROOT=Path(__file__).resolve().parents[1]
CAT=ROOT.parent/'LLW Generic Locomotive Catalog'
SURVEY=ROOT.parent/'LLW Pilot Workflows/analysis/oil-cup-survey-20260926'

def read_def(path):
    text=path.read_text(encoding='utf-8-sig')
    # Remove trailing commas without rewriting quoted text.
    text=re.sub(r'"(?:\\.|[^"\\])*"|,(?=\s*[}\]])',lambda m: m[0] if m[0].startswith('"') else '',text)
    return json.loads(text)

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def wheel_role(key):
    if key.startswith('Drivers'): return 'driver'
    if key in ('Pilot','Trailing'): return 'pony'
    return 'auxiliary'

def make_record(folder):
    path=folder/'Definitions.json'; objects=read_def(path)['objects']
    loco=next(o for o in objects if o['identifier']==folder.name)
    d=loco['definition']; wheels=[]
    for w in d['wheelsets']:
        key=w['animation']['clipName'];role=wheel_role(key)
        wheels.append(dict(key=key,role=role,radius_m=w['diameter']/2,axles=w['numberOfAxles'],
            offset_m=w['offset'],length_m=w['length'],source_transform=w.get('transform')))
    driver=d['wheelsets'][d['mainDriverIndex']]
    if wheel_role(driver['animation']['clipName'])!='driver': raise ValueError('Unexpected main driver')
    te=d.get('publishedTractiveEffort') or .85*d['maximumBoilerPressure']*d['pistonDiameterInches']**2*d['pistonStrokeInches']/(driver['diameter']/.0254)
    source_mass=d['weightEmpty']*.45359237
    record=dict(schema=1,id=folder.name,name=loco['metadata']['name'],
        source=dict(definitions=str(path),definitions_sha256=sha(path),bundle=str(folder/'Bundle'),bundle_sha256=sha(folder/'Bundle')),
        wheels=wheels,ponies=[dict(key=w['key'],radius_m=w['radius_m']) for w in wheels if w['role']=='pony'],
        source_physics=dict(weightEmpty_kg=source_mass,mass_semantics='working_order_interpretation; explicit water ledger required',
            weightOnDrivers_kg=d['weightOnDrivers']*.45359237,pressure_psig=d['maximumBoilerPressure'],
            bore_m=d['pistonDiameterInches']*.0254,stroke_m=d['pistonStrokeInches']*.0254,heating_surface_ft2=d['totalHeatingSurface']),
        derived=dict(tractive_effort_lbf=te,tractive_effort_basis='published' if d.get('publishedTractiveEffort') else 'RR .85*p*d^2*s/D fallback',
            equivalent_bore_m=d['pistonDiameterInches']*.0254*math.sqrt(.85),bore_basis='approximate full-cutoff mean-pull; measured config wins'),
        source_ends_m=dict(front=d['positionHead'],rear=d['positionTail']),
        tender_id=d.get('tenderIdentifier') or None,source_objects=objects,
        component_routes={kind:[c for c in d['components'] if c['kind']==kind] for kind in sorted({c['kind'] for c in d['components']})},
        status='requires_measured_profile',profile=None,missing=['source export/import and clip binding','driver geometry and bogie layout','collision and cab access',
            'fitting final poses','oil save-index selection and phase clearance','control grips and backhead fittings','sim mass/water/steaming ledger','family regression build'])
    manifest=SURVEY/folder.name/'anchor_manifest.json'
    if manifest.exists():
        anchors=json.loads(manifest.read_text())
        if anchors['source_bundle_sha256']!=record['source']['bundle_sha256']:raise ValueError('Stale oil survey: '+folder.name)
        record['oil_candidates']=dict(manifest=str(manifest),sha256=sha(manifest),count=anchors['oiling_point_count'],
            status='measured_source_candidates; not a save-index layout',shallow_count=sum(a['mount_type']=='shallow_plug' for a in anchors['anchors']))
    override=ROOT/'overrides'/f'{folder.name}.json'
    if override.exists():
        ov=json.loads(override.read_text())
        if ov['source_bundle_sha256']!=record['source']['bundle_sha256']:raise ValueError('Stale measured override: '+folder.name)
        record['measured_override']=dict(path=str(override),sha256=sha(override),data=ov)
        record['profile']=ov['profile'];record['status']='profile_available; build/audit/runtime status is separate';record['missing']=[]
    return record

def generate():
    out=ROOT/'catalog';out.mkdir(exist_ok=True)
    records=[make_record(p) for p in sorted(CAT.glob('ls-*')) if p.is_dir()]
    for r in records:(out/(r['id']+'.json')).write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
    index=dict(schema=1,count=len(records),profiles=[r['id'] for r in records if r['profile']],
        unequal_pony=[r['id'] for r in records if len({p['radius_m'] for p in r['ponies']})>1],
        source_candidate_count=sum(r.get('oil_candidates',{}).get('count',0) for r in records),
        records=[dict(id=r['id'],status=r['status'],profile=r['profile']) for r in records])
    (out/'index.json').write_text(json.dumps(index,indent=2)+'\n')
    print(json.dumps({k:v for k,v in index.items() if k!='records'},indent=2))

if __name__=='__main__': generate()
