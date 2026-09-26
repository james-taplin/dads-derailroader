"""Independent catalogue coverage and numerical consistency checks for the survey."""
from oil_cup_survey import *
from PIL import Image,ImageDraw,ImageFont
reports=[]; allids=set()
for folder in sorted(CAT.glob('ls-*')):
    p=OUT/folder.name;d=json.loads((p/'classified_survey.json').read_text());a=d['accepted']
    source=json.loads((folder/'Definitions.json').read_text(encoding='utf-8-sig'))
    loco=next(o['definition'] for o in source['objects'] if o['definition']['kind']=='SteamLocomotive')
    drivers=[x for x in loco['wheelsets'] if 'driver' in (x.get('animation') or {}).get('clipName','').lower()]
    expected=2*sum(x['numberOfAxles']+1 for x in drivers)
    assert len(a)==expected,(folder.name,len(a),expected)
    assert sum(x['center_m'][0]>0 for x in a)==expected//2
    assert sum('Main Rod' in x['path'] for x in a)==2*len(drivers)
    assert sha(folder/'bundle')==d['bundle_sha256'] and sha(folder/'Definitions.json')==d['definition_sha256']
    assert all(not c['unresolved'] for c in d['clips'])
    assert all(not m['skinned'] for m in d['meshes'])
    g=np.load(p/'geometry.npz');max_delta=0;max_face_shift=0
    for c in a:
        assert c['stable_id'] not in allids;allids.add(c['stable_id'])
        i=next(i for i,m in enumerate(d['meshes']) if m['path']==c['path'])
        assert d['meshes'][i]['animated_ancestors']
        local=np.array(c['local_top_center']);assert np.isfinite(local).all()
        assert c['top_face_area_m2']>0
        if c['classification']=='tall_oiler':assert c['footprint_min_gap_m'] is not None and c['footprint_min_gap_m']<.02
        for phase in range(4):
            pp=points(local[None,:],g['matrices'][phase,i])[0]
            max_delta=max(max_delta,float(np.linalg.norm(pp-c['phase_top_centers'][phase])))
        old=points(np.array(c['aabb_local_top_center'])[None,:],g['matrices'][0,i])[0]
        max_face_shift=max(max_face_shift,float(np.linalg.norm(old-c['phase_top_centers'][0])))
    assert max_delta<1e-8
    distances=[]
    for phase in range(4):
        for i,c in enumerate(a):
            for other in a[i+1:]:
                if (c['center_m'][0]>0)==(other['center_m'][0]>0):
                    distances.append(float(np.linalg.norm(np.array(c['phase_top_centers'][phase])-other['phase_top_centers'][phase])))
    reports.append({'id':folder.name,'expected_from_definition':expected,'measured':len(a),'source_hashes_unchanged':True,
        'unresolved_driver_bindings':0,'max_manifest_transform_error_m':max_delta,'max_top_face_vs_AABB_shift_m':max_face_shift,
        'minimum_same_side_anchor_separation_at_four_phases_m':min(distances),'result':'passed'})
assert len(reports)==25
# Independent historical Unity measurement of the G29 right rear oiler.
d=json.loads((OUT/'ls-260-g29/classified_survey.json').read_text())
rear=next(c for c in d['accepted'] if c['path']=='Main/Empty.031/Connecting Rod Left.001' and c['center_m'][2]<-1)
assert np.max(np.abs(np.array(rear['center_m'])-[.952,.827,-1.737]))<.0006
assert np.max(np.abs(np.array(rear['size_m'])-[.077,.103,.084]))<.0006
write(OUT/'validation.json',{'status':'passed','locomotives':25,'anchors':len(allids),'historical_G29_Unity_reference_agrees_within_m':.0006,
    'scope':'source bundle, topology, manifests and four-phase offline transforms; not Unity or DV runtime validation','models':reports})
# Review sheets keep each individual fleet entry visible, including siblings.
for batch in range(5):
    canvas=Image.new('RGB',(1800,1850),'#101821');draw=ImageDraw.Draw(canvas)
    for row,r in enumerate(reports[batch*5:(batch+1)*5]):
        src=Image.open(OUT/r['id']/'mount_details.png');src.thumbnail((900,340))
        phase=Image.open(OUT/r['id']/'four_phases.png');phase.thumbnail((850,340))
        y=row*370;draw.text((10,y+2),r['id'],font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',20),fill='white')
        canvas.paste(src,(0,y+30));canvas.paste(phase,(920,y+30))
    canvas.save(OUT/f'review_sheet_{batch+1}.png')
print(json.dumps({'locomotives':25,'anchors':len(allids),'status':'passed','tall':sum(x['tall'] for x in json.loads((OUT/'fleet_summary.json').read_text())),
    'original_rule_passes':sum(x['original_rule_passes'] for x in json.loads((OUT/'fleet_summary.json').read_text())),
    'max_AABB_shift_mm':1000*max(x['max_top_face_vs_AABB_shift_m'] for x in reports)},indent=2))
