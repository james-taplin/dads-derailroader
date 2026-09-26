"""Classify and render measured source islands; does not edit any conversion."""
from oil_cup_survey import *
from PIL import Image, ImageDraw, ImageFont
import csv, html
FONT='C:/Windows/Fonts/segoeui.ttf'
def font(s):return ImageFont.truetype(FONT,s)

def classify(d,g):
    accepted=[]
    for c in d['candidates']:
        path=c['path']; rod=any(x in path.lower() for x in ['connecting rod','main rod'])
        sz=np.array(c['size_m']); sup=c['support']; family=None
        idx=next(i for i,m in enumerate(d['meshes']) if m['path']==path)
        v=points(g[f'{idx}_v'],g['matrices'][0,idx]);f=g[f'{idx}_f']
        # Check support under multiple low cap vertices, not just under a tilted AABB centre.
        lows=v[c['vertex_ids']];lows=lows[lows[:,1]<c['bottom_m']+sz[1]*.2]
        hits=[surface_below(v,f,p[0],p[2],p[1],c['triangle_ids']) for p in lows]
        hits=[x for x in hits if x and x['abs_up_normal']>.7 and x['gap_m']>=-.0001]
        c['footprint_min_gap_m']=min((x['gap_m'] for x in hits),default=None)
        if rod and c['shape_pass'] and sup and sup['gap_m']<.03 and sup['abs_up_normal']>.9:
            family='tall_oiler'
        if rod and c['triangles']==28 and .01<sz[1]<.04 and sz[0]>sz[1]*1.5 and sz[2]>sz[1]*1.5 and sup and sup['gap_m']<.02 and sup['abs_up_normal']>.9:
            siblings=d['meshes'][idx]['small_islands'];center=np.array(c['center_m'])
            seats=[x for x in siblings if x['triangles'] in (48,56,64) and np.linalg.norm((np.array(x['center_m'])-center)[[0,2]])<.002 and 0<center[1]-x['center_m'][1]<.035]
            if seats:family='shallow_plug';c['seat_triangles']=seats[0]['triangles']
        c['classification']=family or ('seat_or_washer' if rod and sz[1]<min(sz[0],sz[2])*.3 else 'rejected_non_mount')
        if family:
            c['stable_id']=hashlib.sha256((d['id']+'|'+path+'|'+','.join(map(str,c['triangle_ids']))).encode()).hexdigest()[:16]
            c['index']=len(accepted);c['label']=f'O{len(accepted)+1:02d}'
            accepted.append(c)
    # A D47 oiler is stacked on a shallow hex base: one bearing, not two consumers.
    for c in accepted:
        above=[a for a in accepted if a is not c and a['path']==c['path'] and a['classification']=='tall_oiler'
            and np.linalg.norm((np.array(a['center_m'])-c['center_m'])[[0,2]])<.006 and a['top_m']>c['top_m']+.015]
        if above:c['classification']='base_under_tall_oiler'
    accepted=[c for c in accepted if c['classification'] in ('tall_oiler','shallow_plug')]
    for i,c in enumerate(accepted):
        c['index']=i;c['label']=f'O{i+1:02d}'
        idx=next(j for j,m in enumerate(d['meshes']) if m['path']==c['path'])
        w=points(g[f'{idx}_v'],g['matrices'][0,idx]); f=g[f'{idx}_f']; ids=np.array(c['triangle_ids']);tri=w[f[ids]]
        cross=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);area=np.linalg.norm(cross,axis=1)/2
        norms=cross/np.maximum(2*area[:,None],1e-15);norms[norms[:,1]<0]*=-1;cent=tri.mean(1)
        options=np.where((norms[:,1]>.8)&(area>1e-12))[0]
        best=options[np.argmax(cent[options,1])];normal=norms[best];plane=cent[best]@normal
        mask=(norms@normal>.99999)&(np.abs(cent@normal-plane)<1e-5)&(area>1e-12)
        top=np.average(cent[mask],axis=0,weights=area[mask]);local=points(top[None,:],np.linalg.inv(g['matrices'][0,idx]))[0]
        c['aabb_local_top_center']=c['local_top_center'];c['local_top_center']=local.tolist()
        c['phase_top_centers']=[points(local[None,:],m[idx])[0].tolist() for m in g['matrices']]
        c['top_face_normal_phase0']=normal.tolist();c['top_face_area_m2']=float(area[mask].sum());c['top_face_triangle_ids']=ids[mask].tolist()
        c['landmark_method']='area_weighted_centroid_of_highest_upward_coplanar_cap_face'
    d['accepted']=accepted
    return accepted

def render_panel(d,g,phase,side,box=(1350,440),focus=None):
    W,H=box;im=Image.new('RGB',(W,H),'#101821');draw=ImageDraw.Draw(im)
    sels=[c for c in d['accepted'] if (c['center_m'][0]>0)==(side>0)]
    rods=[(i,m) for i,m in enumerate(d['meshes']) if any(s in m['path'].lower() for s in ['connecting rod','main rod'])]
    if focus:
        rods=[(i,m) for i,m in rods if m['path']==focus['path']]
        sels=[focus]
    ww=[points(g[f'{i}_v'],g['matrices'][phase,i]) for i,m in rods]
    if focus:
        center=np.array(focus['phase_top_centers'][phase]); z0,z1=center[2]-.19,center[2]+.19;y0,y1=center[1]-.21,center[1]+.12
    else:
        vals=np.concatenate([w for w in ww if np.mean(w[:,0])*side>0]);lo=vals.min(0);hi=vals.max(0)
        z0,z1=lo[2]-.2,hi[2]+.2;y0,y1=lo[1]-.12,hi[1]+.18
    scale=min((W-40)/(z1-z0),(H-65)/(y1-y0));zc=(z0+z1)/2;yc=(y0+y1)/2
    def project(p):return ((p[2]-zc)*scale+W/2,H/2+20-(p[1]-yc)*scale)
    tris=[]
    for (idx,m),w in zip(rods,ww):
        if np.mean(w[:,0])*side<=0:continue
        f=g[f'{idx}_f'];faces=w[f]; normal=np.cross(faces[:,1]-faces[:,0],faces[:,2]-faces[:,0]);length=np.linalg.norm(normal,axis=1)
        normal/=np.maximum(length[:,None],1e-12)
        shade=np.clip(.45+.4*np.abs(normal[:,0])+.15*normal[:,1],.2,1)
        selection={j:c for c in sels if c['path']==m['path'] for j in c['triangle_ids']}
        for j,t in enumerate(faces):
            if t[:,2].max()<z0 or t[:,2].min()>z1 or t[:,1].max()<y0 or t[:,1].min()>y1:continue
            c=selection.get(j); color=tuple(int(k*shade[j]) for k in ((251,185,62) if c else (155,173,190)))
            tris.append((t[:,0].mean()*side,[project(p) for p in t],color))
    for _,poly,color in sorted(tris,key=lambda x:x[0]):draw.polygon(poly,fill=color)
    for c in sels:
        p=np.array(c['phase_top_centers'][phase]);x,y=project(p)
        if -20<x<W+20 and -20<y<H+20:
            draw.ellipse((x-3,y-3,x+3,y+3),fill='#80edc0')
            # Two main-crank mounts share z but have distinct x; alternate label heights.
            lift=35 if 'Main Rod' in c['path'] else 5
            dx=-35 if 'Main Rod' in c['path'] else 8
            draw.line((x,y,x+dx,y-13-lift),fill='#80edc0',width=1)
            draw.text((x+dx,y-32-lift),c['label'],font=font(17),fill='#80edc0')
    draw.text((18,10),f"{'X+ side' if side>0 else 'X- side'}  |  {phase*90} degrees",font=font(19),fill='#f0f5fa')
    return im

def output(d,g):
    accepted=classify(d,g);out=OUT/d['id']
    sheet=Image.new('RGB',(2700,1860),'#101821');dr=ImageDraw.Draw(sheet)
    dr.text((25,15),f"{d['id']}  |  {len(accepted)} measured oil-cup mounts",font=font(30),fill='white')
    dr.text((25,58),'SOURCE ROD GEOMETRY | amber = selected island; green = top landmark | four source-clip phases; no DV cups fitted',font=font(20),fill='#b3c4d5')
    for phase in range(4):
        for col,side in enumerate([-1,1]):sheet.paste(render_panel(d,g,phase,side),(col*1350,100+phase*440))
    sheet.save(out/'four_phases.png')
    cols=4;rows=math.ceil(len(accepted)/cols);detail=Image.new('RGB',(cols*450,rows*420+65),'#101821');dd=ImageDraw.Draw(detail)
    dd.text((15,15),d['id']+' | phase 0 details; each parent rod isolated for visibility',font=font(25),fill='white')
    for k,c in enumerate(accepted):
        panel=render_panel(d,g,0,1 if c['center_m'][0]>0 else -1,(450,365),focus=c)
        detail.paste(panel,((k%cols)*450,65+(k//cols)*420));x=(k%cols)*450+10;y=65+(k//cols)*420+365
        dd.text((x,y),f"{c['label']}  {c['classification']}  {c['triangles']} tris",font=font(18),fill='white')
        dd.text((x,y+25),' x '.join(f'{v*1000:.1f}' for v in c['size_m'])+' mm',font=font(17),fill='#b3c4d5')
    detail.save(out/'mount_details.png')
    # Immutable source identities and explicit unresolved fitting parameters for build integration.
    manifest={'schema':1,'locomotive':d['id'],'status':'source_geometry_surveyed; DV fitting/runtime pending','coordinate_space':'source prefab root; metres; not DV body space',
        'source_bundle_sha256':d['bundle_sha256'],'oiling_point_count':len(accepted),'anchors':[]}
    for c in accepted:
        manifest['anchors'].append({'stable_id':c['stable_id'],'display_label':c['label'],'proposed_index':c['index'],
            'sync_tag':f"LLW_{d['id']}_{c['stable_id']}",'parent_source_path':c['path'],'attachment':'rigid_transform',
            'mesh_sha256':c['mesh_sha256'],'mesh_path_id':c['mesh_path_id'],'island_triangle_ids':c['triangle_ids'],
            'landmark_local':c['local_top_center'],'landmark_kind':c['landmark_method'],
            'top_face_triangle_ids':c['top_face_triangle_ids'],'top_face_normal_phase0':c['top_face_normal_phase0'],
            'mount_type':c['classification'],'source_phase_positions_m':c['phase_top_centers'],
            'cup_model':None,'cup_bottom_to_pivot_m':None,'insertion_depth_m':None,'orientation_policy':'upright_position_sync; verify clearance',
            'existing_save_index_mapping':None})
    write(out/'anchor_manifest.json',manifest);write(out/'classified_survey.json',d)
    return d

def main():
    reports=[]
    for p in sorted(OUT.glob('*/survey.json')):
        d=json.loads(p.read_text());g=np.load(p.parent/'geometry.npz');reports.append(output(d,g))
        print(d['id'],len(d['accepted']),[(f,sum(c['classification']==f for c in d['accepted'])) for f in ['tall_oiler','shallow_plug']],flush=True)
    write(OUT/'fleet_summary.json',[{'id':d['id'],'count':len(d['accepted']),'tall':sum(c['classification']=='tall_oiler' for c in d['accepted']),
        'shallow':sum(c['classification']=='shallow_plug' for c in d['accepted']), 'original_rule_passes':sum(c['shape_pass'] and c['support_pass'] for c in d['accepted'])} for d in reports])
    with (OUT/'anchors.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['locomotive','label','stable_id','type','parent_path','local_x','local_y','local_z','source_x','source_y','source_z','triangles','center_support_gap_mm','footprint_min_gap_mm'])
        for d in reports:
            for c in d['accepted']:w.writerow([d['id'],c['label'],c['stable_id'],c['classification'],c['path'],*c['local_top_center'],*c['phase_top_centers'][0],c['triangles'],1000*c['support']['gap_m'],None if c['footprint_min_gap_m'] is None else 1000*c['footprint_min_gap_m']])
    page=['<!doctype html><meta charset="utf-8"><title>LLW oil-cup survey</title><style>body{background:#101821;color:#edf3f8;font:17px Segoe UI;margin:36px}a{color:#80edc0}img{width:100%;height:auto}section{margin:50px 0}table{border-collapse:collapse}td,th{padding:9px 22px;border-bottom:1px solid #52616e}summary{cursor:pointer}</style><h1>LLW catalogue oil-cup survey</h1><p>25 source locomotive models, including the L-29 Mallet. Amber: selected modelled mount. Green: proposed source landmark. Images show actual source rod triangles, not generated artwork. DV cup sizing, lid clearance and in-game movement still require fitting and validation.</p><p><a href="REPORT.md">Survey report</a> · <a href="anchors.csv">All measured anchors (CSV)</a></p><table><tr><th>Locomotive</th><th>Mounts</th><th>Tall</th><th>Shallow</th></tr>']
    for d in reports:page.append(f'<tr><td><a href="#{d["id"]}">{d["id"]}</a></td><td>{len(d["accepted"])}</td><td>{sum(c["classification"]=="tall_oiler" for c in d["accepted"])}</td><td>{sum(c["classification"]=="shallow_plug" for c in d["accepted"])}</td></tr>')
    page.append('</table>')
    for d in reports:
        cid=d['id'];page.append(f'<section id="{cid}"><h2>{cid}</h2><p><a href="{cid}/anchor_manifest.json">Anchor manifest</a> · <a href="{cid}/classified_survey.json">Full evidence, including rejected candidates</a></p><img loading="lazy" src="{cid}/mount_details.png"><details><summary>Both sides at four source animation phases</summary><img loading="lazy" src="{cid}/four_phases.png"></details></section>')
    (OUT/'index.html').write_text('\n'.join(page),encoding='utf-8')

if __name__=='__main__':main()
