"""Read existing source measurements; write only this independent design folder."""
import json, math
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent/'oil-cup-survey-20260926'

def hits(start,end,tri):
    direction=end-start; e1=tri[:,1]-tri[:,0];e2=tri[:,2]-tri[:,0]
    h=np.cross(direction,e2);det=np.einsum('ij,ij->i',e1,h)
    valid=np.abs(det)>1e-10; inv=np.zeros_like(det);inv[valid]=1/det[valid]
    s=start-tri[:,0];u=inv*np.einsum('ij,ij->i',s,h);q=np.cross(s,e1)
    v=inv*(q@direction);t=inv*np.einsum('ij,ij->i',e2,q)
    return bool(np.any(valid&(u>=0)&(v>=0)&(u+v<=1)&(t>1e-5)&(t<1-1e-5)))

results=[]
for p in sorted(SOURCE.glob('*/classified_survey.json')):
    d=json.loads(p.read_text());g=np.load(p.parent/'geometry.npz')
    anchors=[];triangles=[]
    for phase in range(4):
        parts=[]
        for i,m in enumerate(d['meshes']):
            mat=g['matrices'][phase,i];w=g[f'{i}_v']@mat[:3,:3].T+mat[:3,3]
            parts.append(w[g[f'{i}_f']])
        triangles.append(np.concatenate(parts))
    for c in d['accepted']:
        ismain='Main Rod' in c['path'];l29=d['id']=='ls-2442-l29'
        extra=any(s in d['id'] for s in ('k50','k56','p39')) or (l29 and c['path'].startswith('RearEngine/'))
        keep=not ismain or extra
        i=next(i for i,m in enumerate(d['meshes']) if m['path']==c['path'])
        local_normal=g['matrices'][0,i,:3,:3].T@np.array(c['top_face_normal_phase0'])
        angles=[];clear=[];fan=[];side=1 if c['center_m'][0]>0 else -1
        for phase in range(4):
            n=np.linalg.inv(g['matrices'][phase,i,:3,:3]).T@local_normal;n/=np.linalg.norm(n)
            angles.append(math.degrees(math.acos(np.clip(n[1],-1,1))))
            # Illustrative mouth, not an assertion about the actual DV cup dimensions.
            mouth=np.array(c['phase_top_centers'][phase])+[0,.12,0]
            start=mouth+np.array([side*.60,.30,0])
            clear.append(not hits(start,mouth,triangles[phase]))
            fan.append(sum(not hits(mouth+np.array([side*.60,rise,dz]),mouth,triangles[phase]) for rise in (.15,.30,.45) for dz in (-.35,0,.35)))
        # Gameplay selection: level side rods first, but screen out restricted approaches.
        # C21 meets its eight-point budget entirely on level rods; P39 needs both main ends.
        keep=(not ismain) if d['id']=='ls-280-c21' else (ismain or min(fan)>=3)
        anchors.append({'source_id':c['stable_id'],'source_label':c['label'],'selected':keep,
            'source_parent':c['path'],'source_mesh_sha256':c['mesh_sha256'],'role':'main_big_end' if ismain else 'side_rod_pin',
            'engine_root':c['path'].split('/')[0],'local_top_face_centre':c['local_top_center'],
            'source_phase_positions_m':c['phase_top_centers'],'sampled_top_face_tilt_deg':angles,
            'illustrative_gear_approach_clear':clear,'illustrative_fan_clear_of_9':fan})
    selected=[a for a in anchors if a['selected']]
    guides=2 if any(s in d['id'] for s in ('k50','k56','l29')) else 0
    count=len(selected)+guides
    assert count in (6,8,10);assert sum(a['source_phase_positions_m'][0][0]>0 for a in selected)==len(selected)//2
    results.append({'locomotive':d['id'],'design_tier':{6:'small',8:'medium',10:'large'}[count],
        'target_count':count,'source_bundle_sha256':d['bundle_sha256'],'anchors':anchors,
        'proposed_guide_oilers':[{'side':side,'status':'new fitting proposed; exact placement and clearance unmeasured',
            'zone':'outboard fixed crosshead-guide support; Main engine guide on L29',
            'local_position':None,'source_parent':None} for side in ('X-','X+')] if guides else []})
    print(d['id'],count,'tilt',round(max(max(a['sampled_top_face_tilt_deg']) for a in selected),2),
        'narrow fan samples',[(a['source_label'],a['illustrative_fan_clear_of_9']) for a in selected if min(a['illustrative_fan_clear_of_9'])<3],flush=True)
assert len(results)==25
data={'status':'design recommendation; not fitted or runtime validated','profile':'gameplay_6_8_10',
    'coordinate_space':'source prefab; source heights are not guaranteed DV rail-relative heights',
    'evidence':'four source phases; gear-only approach to a hypothetical mouth 0.12m above the mount; straight ray from 0.60m outboard and 0.30m above; nine-ray fan uses same outboard offset, rises 0.15/0.30/0.45m, longitudinal offsets -0.35/0/+0.35m; no body, cup, lid or player collisions tested',
    'locomotives':results}
(HERE/'layout_evidence.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
print('TOTAL',sum(r['target_count'] for r in results))
