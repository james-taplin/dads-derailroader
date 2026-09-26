"""Read-only LLW bundle survey. Outputs live in analysis/oil-cup-survey-20260926."""
import sys, json, hashlib, zlib, struct, math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workspace import enable_unitypy, WORKSPACE, CONFIG, location
enable_unitypy()
import numpy as np
import UnityPy
from UnityPy.helpers.MeshHelper import MeshHandler
ROOT = WORKSPACE
CAT = location(CONFIG['sourceCatalog'])
OUT = WORKSPACE / 'analysis/catalogue/oil-cup-survey-new'
OUT.mkdir(exist_ok=True, parents=True)

def vec(v): return np.array([v.x,v.y,v.z],dtype=float)
def quat(v): return np.array([v.x,v.y,v.z,v.w],dtype=float)
def matrix(p,q,s):
    x,y,z,w=q/np.linalg.norm(q)
    m=np.eye(4); m[:3,:3]=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
        [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)], [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])@np.diag(s)
    m[:3,3]=p; return m
def points(v,m): return v@m[:3,:3].T+m[:3,3]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d): p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')

class Clip:
    def __init__(self,d,paths):
        self.name=d['m_Name']; self.bindings=[]; self.unresolved=[]
        data=d['m_MuscleClip']['m_Clip']['data']; self.duration=d['m_MuscleClip']['m_StopTime']
        stream=data['m_StreamedClip']; raw=struct.pack('<'+'I'*len(stream['data']),*stream['data']); off=0
        self.curves=[[] for _ in range(stream['curveCount'])]
        while off<len(raw):
            t,n=struct.unpack_from('<fi',raw,off);off+=8
            for _ in range(n):
                idx,*coeff=struct.unpack_from('<i4f',raw,off);off+=20
                self.curves[idx].append((t,coeff))
        self.dense=data['m_DenseClip']; self.const=data['m_ConstantClip']['data']
        cursor=0
        for b in d['m_ClipBindingConstant']['genericBindings']:
            size={1:3,2:4,3:3,4:3}.get(b['attribute'],1) if b['typeID']==4 else 1
            hits=paths.get(b['path'],[])
            if len(hits)!=1: self.unresolved.append(b)
            else:self.bindings.append((hits[0],b['attribute'],cursor,size))
            cursor+=size
        assert cursor==len(self.curves)+self.dense['m_CurveCount']+len(self.const),(self.name,cursor)
    def sample(self,t):
        v=[]
        for curve in self.curves:
            ts=[x[0] for x in curve]; k=max(0,int(np.searchsorted(ts,t,side='right'))-1)
            at,c=curve[k]; dt=t-at
            v.append(c[3] if not np.isfinite(dt) or abs(dt)>1e15 else ((c[0]*dt+c[1])*dt+c[2])*dt+c[3])
        d=self.dense; n=d['m_CurveCount']
        if n:
            frame=np.clip((t-d['m_BeginTime'])*d['m_SampleRate'],0,d['m_FrameCount']-1)
            lo=int(frame); hi=min(lo+1,d['m_FrameCount']-1); a=frame-lo
            vals=np.array(d['m_SampleArray']).reshape(-1,n)
            v.extend(vals[lo]*(1-a)+vals[hi]*a)
        v.extend(self.const)
        return {(path,attr):np.array(v[i:i+n]) for path,attr,i,n in self.bindings}

def islands(v,f):
    # Weld only coincident vertices (10 micrometres in physical space), retaining original vertex IDs.
    _,inv=np.unique(np.round(v/1e-5).astype(np.int64),axis=0,return_inverse=True)
    parent=list(range(int(inv.max())+1))
    def find(a):
        while parent[a]!=a:parent[a]=parent[parent[a]];a=parent[a]
        return a
    for a,b,c in inv[f]:
        a=find(a);parent[find(b)]=a;parent[find(c)]=a
    groups={}
    for i,a in enumerate(inv[f[:,0]]):groups.setdefault(find(a),[]).append(i)
    return [np.array(g) for g in groups.values()]

def surface_below(v,f,x,z,y,exclude):
    tri=v[f]; a=tri[:,0];u=tri[:,1]-a;w=tri[:,2]-a
    det=u[:,0]*w[:,2]-u[:,2]*w[:,0]; valid=np.abs(det)>1e-12
    aa=np.zeros(len(f));bb=aa.copy()
    aa[valid]=((x-a[valid,0])*w[valid,2]-(z-a[valid,2])*w[valid,0])/det[valid]
    bb[valid]=(u[valid,0]*(z-a[valid,2])-u[valid,2]*(x-a[valid,0]))/det[valid]
    height=a[:,1]+aa*u[:,1]+bb*w[:,1]
    valid&=(aa>=-1e-6)&(bb>=-1e-6)&(aa+bb<=1.000001)&(height<=y+0.0001)
    valid[exclude]=False
    if not valid.any():return None
    i=np.where(valid)[0][np.argmax(height[valid])]
    normal=np.cross(u[i],w[i]);normal/=max(np.linalg.norm(normal),1e-12)
    return {'gap_m':float(y-height[i]),'surface_y':float(height[i]),'abs_up_normal':float(abs(normal[1])),'triangle':int(i)}

def survey(folder):
    e=UnityPy.load(str(folder/'bundle')); cid=folder.name
    root=next(v.read() for k,v in e.container.items() if k.lower().endswith('/'+cid+'.prefab'))
    nodes={}; paths={}; objects={}; byhash={}; renders=[]
    def walk(go,parent,path):
        comps=[c.component.read() for c in go.m_Component]
        tr=next(c for c in comps if c.object_reader.type.name in ('Transform','RectTransform'))
        nodes[path]=(parent,vec(tr.m_LocalPosition),quat(tr.m_LocalRotation),vec(tr.m_LocalScale));objects[tr.object_reader.path_id]=path
        paths[path]=tr
        for rel in {path,path.partition('/')[2]} if '/' in path else {path}:
            h=zlib.crc32(rel.encode());byhash.setdefault(h,[])
            if path not in byhash[h]:byhash[h].append(path)
        mf=next((c for c in comps if c.object_reader.type.name=='MeshFilter'),None)
        sk=next((c for c in comps if c.object_reader.type.name=='SkinnedMeshRenderer'),None)
        if mf and mf.m_Mesh.path_id:renders.append((path,mf.m_Mesh.read(),False))
        if sk and sk.m_Mesh.path_id:renders.append((path,sk.m_Mesh.read(),True))
        for child in tr.m_Children:
            cg=child.read().m_GameObject.read();walk(cg,path,(path+'/' if path else '')+cg.m_Name)
    walk(root,None,'')
    clips=[]
    for o in e.objects:
        if o.type.name=='AnimationClip':
            d=o.read_typetree()
            if 'driver' in d['m_Name'].lower():clips.append(Clip(d,byhash))
    animated={b[0] for c in clips for b in c.bindings}
    def matrices(phase=None):
        vals={}
        if phase is not None:
            for c in clips:vals.update(c.sample(phase*c.duration))
        mats={}
        for path,(parent,p,q,s) in nodes.items():
            pp=vals.get((path,1),p);qq=vals.get((path,2),q);ss=vals.get((path,3),s)
            if (path,4) in vals:
                # Unity Euler order Z-X-Y.
                rx,ry,rz=np.radians(vals[(path,4)]/2)
                def qm(a,b):
                    av=a[:3];bv=b[:3];return np.r_[a[3]*bv+b[3]*av+np.cross(av,bv),a[3]*b[3]-av@bv]
                qq=qm(qm(np.array([0,np.sin(ry),0,np.cos(ry)]),np.array([np.sin(rx),0,0,np.cos(rx)])),np.array([0,0,np.sin(rz),np.cos(rz)]))
            mats[path]=(mats[parent] if parent is not None else np.eye(4))@matrix(pp,qq,ss)
        return mats
    mats=matrices(0); phases=[matrices(p) for p in [0,.25,.5,.75]]
    report={'id':cid,'bundle_sha256':sha(folder/'bundle'),'definition_sha256':sha(folder/'Definitions.json'),
        'clips':[{'name':c.name,'duration':c.duration,'bindings':len(c.bindings),'unresolved':c.unresolved} for c in clips],
        'renderers_total':len(renders),'meshes':[],'candidates':[],'named_oil_objects':[p for p in nodes if any(s in p.lower() for s in ['oil cup','oiler','lubricator'])]}
    geoms=[]
    for path,mesh,skin in renders:
        ancestors=[p for p in animated if path==p or path.startswith(p+'/')]
        rod=any(s in path.lower() for s in [' rod','rods','crosshead','crank','link'])
        if not ancestors and not rod:continue
        h=MeshHandler(mesh);h.process();v=np.array(h.m_Vertices);f=np.array([t for sub in h.get_triangles() for t in sub],dtype=int)
        if not len(f):continue
        w=points(v,mats[path]); groups=islands(w,f)
        fingerprint=hashlib.sha256(v.astype('<f4').tobytes()+f.astype('<i4').tobytes()).hexdigest()
        md={'path':path,'mesh':mesh.m_Name,'mesh_path_id':mesh.object_reader.path_id,'sha256_geometry':fingerprint,'skinned':skin,
            'animated_ancestors':ancestors,'islands':len(groups),'triangles':len(f),'small_islands':[]}
        for inds in groups:
            ids=np.unique(f[inds]);ww=w[ids];lo=ww.min(0);hi=ww.max(0);sz=hi-lo;center=(lo+hi)/2
            if max(sz)>.3 or len(inds)<12:continue
            below=surface_below(w,f,center[0],center[2],lo[1],inds)
            shape=bool(max(sz)<.12 and sz[1]>max(sz[0],sz[2]) and len(inds)>=60)
            candidate=bool(shape and rod and ancestors and not skin)
            data={'triangle_ids':inds.tolist(),'vertex_ids':ids.tolist(),'triangles':len(inds),'size_m':sz.tolist(),'center_m':center.tolist(),
                'bottom_m':lo[1].item(),'top_m':hi[1].item(),'shape_pass':shape,'support':below}
            # Retain broad rod candidates: many LLW caps are shallow 28-triangle plugs.
            bearing_rod=any(s in path.lower() for s in ['connecting rod','main rod'])
            broad=bool(bearing_rod and max(sz)<.13 and len(inds)>=28 and sz[1]>.01 and ancestors and not skin)
            md['small_islands'].append(data)
            if candidate or broad:
                top=np.array([center[0],hi[1],center[2]]);local=points(top[None,:],np.linalg.inv(mats[path]))[0]
                data.update({'path':path,'mesh_sha256':fingerprint,'mesh_path_id':mesh.object_reader.path_id,'local_top_center':local.tolist(),
                    'phase_top_centers':[points(local[None,:],m[path])[0].tolist() for m in phases],
                    'support_pass':bool(below and below['gap_m']<=.020 and below['abs_up_normal']>.7)})
                report['candidates'].append(data)
        report['meshes'].append(md);geoms.append((path,v,f,md))
    report['candidates'].sort(key=lambda d:(d['center_m'][0]>0,d['center_m'][2],d['center_m'][0],d['path']))
    for i,d in enumerate(report['candidates'],1):d['id']=f'{cid}:C{i:02d}'
    out=OUT/cid;out.mkdir(exist_ok=True);write(out/'survey.json',report)
    np.savez_compressed(out/'geometry.npz',**{f'{i}_{key}':data for i,(_,v,f,_) in enumerate(geoms) for key,data in [('v',v),('f',f)]},
        matrices=np.array([[m[p] for p,_,_,_ in geoms] for m in phases]))
    print(cid,'meshes',len(geoms),'clips',[c.name for c in clips],'unresolved',sum(len(c.unresolved) for c in clips),'candidates',len(report['candidates']),flush=True)
    return report

def explore():
    e = UnityPy.load(str(CAT/'ls-260-g29/bundle'))
    for o in e.objects:
        if o.type.name == 'AnimationClip':
            d=o.read_typetree()
            print(d['m_Name'], list(d))
            if d['m_Name']=='Drivers':
                (OUT/'animation_structure.json').write_text(json.dumps(d,indent=2))
                print(str(d)[:2500])
    root=next(v.read() for k,v in e.container.items() if k.endswith('/ls-260-g29.prefab'))
    print('ROOT',root)
    for o in e.objects:
        if o.type.name=='Mesh' and o.read().m_Name.startswith('Connecting Rod'):
            m=o.read(); h=MeshHandler(m);h.process(); print(m.m_Name,h.m_Vertices[:2],h.get_triangles()[:1]); break

if __name__=='__main__':
    folders=[CAT/x for x in sys.argv[1:]] if len(sys.argv)>1 else sorted(CAT.glob('ls-*'))
    for folder in folders:survey(folder)
