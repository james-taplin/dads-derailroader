from pathlib import Path
import json,hashlib
import UnityPy
import numpy as np
from UnityPy.helpers.MeshHelper import MeshHandler
OUT=Path(__file__).parent
SRC=Path('B:/SteamLibrary/steamapps/common/Derail Valley/DerailValley_Data/resources.assets')
e=UnityPy.load(str(SRC))
objs={o.path_id:o for o in e.objects}
def tree(pid):return objs[pid].read_typetree()
def xyz(d):return [d['x'],d['y'],d['z']]
def mat(t):
 x,y,z,w=[t['m_LocalRotation'][k] for k in ['x','y','z','w']]
 r=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
 m=np.eye(4);m[:3,:3]=r*np.array(xyz(t['m_LocalScale']));m[:3,3]=xyz(t['m_LocalPosition']);return m
summary={'source':str(SRC),'source_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest(),'fittings':[]}
for gid,key in [(94263,'handbrake_small'),(33063,'brake_release')]:
 records=[]; render=[];colliders=[]
 def walk(gid,m,path,root=False):
  g=tree(gid);comps=[objs[c['component']['m_PathID']] for c in g['m_Component']];tr=next(tree(c.path_id) for c in comps if c.type.name=='Transform');m=m if root else m@mat(tr);path=path+'/'+g['m_Name']
  records.append({'path':path,'gameObjectId':gid,'localPosition':tr['m_LocalPosition'],'localRotation':tr['m_LocalRotation'],'localScale':tr['m_LocalScale']})
  for c in comps:
   if c.type.name=='MeshFilter':
    ref=tree(c.path_id)['m_Mesh'];assert ref['m_FileID']==0
    mesh=objs[ref['m_PathID']].read();h=MeshHandler(mesh);h.process();v=np.asarray(h.m_Vertices);v=(m@np.concatenate([v,np.ones((len(v),1))],axis=1).T).T[:,:3];tri=[j for s in h.get_triangles() for t in s for j in t]
    meshdata={'name':g['m_Name'],'sourceMeshId':ref['m_PathID'],'path':path,'vertices':[dict(zip(['x','y','z'],a)) for a in v.tolist()],'triangles':tri}
    filename=key+'_'+g['m_Name']+'.json';(OUT/filename).write_text(json.dumps(meshdata,separators=(',',':')))
    render.append({'name':g['m_Name'],'path':path,'meshId':ref['m_PathID'],'vertexCount':len(v),'min':v.min(0).tolist(),'max':v.max(0).tolist(),'sweptRadiusAroundZ':float(np.linalg.norm(v[:,:2],axis=1).max()),'json':filename})
    # Exact Unity XYZ and triangle winding; no OBJ exporter handedness transforms.
    rows=['# Coordinates/winding are Unity-native; prefer companion JSON to avoid OBJ import conversions.','o '+g['m_Name']]+['v '+' '.join(format(a,'.9g') for a in pt) for pt in v]+['f '+' '.join(str(i+1) for i in tri[j:j+3]) for j in range(0,len(tri),3)]
    (OUT/(key+'_'+g['m_Name']+'.obj')).write_text('\n'.join(rows))
   if 'Collider' in c.type.name:
    d=tree(c.path_id);colliders.append({'path':path,'type':c.type.name,'transformToRoot':m.tolist(),'settings':{k:d[k] for k in ['m_IsTrigger','m_Center','m_Size','m_Radius','m_Height','m_Direction'] if k in d}})
  for child in tr['m_Children']:walk(tree(child['m_PathID'])['m_GameObject']['m_PathID'],m,path)
 walk(gid,np.eye(4),'',True)
 summary['fittings'].append({'name':key,'sourceGameObjectId':gid,'hierarchy':records,'meshes':render,'colliders':colliders})
(OUT/'stock_fittings_geometry.json').write_text(json.dumps(summary,indent=2))
print(json.dumps([{k:v for k,v in a.items() if k in ['name','meshes']} for a in summary['fittings']],indent=2))
