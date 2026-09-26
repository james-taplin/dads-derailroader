import json,numpy as np
from pathlib import Path
p=Path(__file__).parent
for n in ['handbrake_small_HandWheel_01','brake_release_BrakeCylinderRelease','brake_release_BrakeCylinderReleaseValve']:
 d=json.loads((p/(n+'.json')).read_text());v=np.array([[w[k] for k in ['x','y','z']] for w in d['vertices']]);tr=np.array(d['triangles']).reshape(-1,3)
 print(n)
 if n.startswith('handbrake'):
  for rad in [.04,.08,.12,.17]:
   a=v[np.linalg.norm(v[:,:2],axis=1)>rad];print('rad >',rad,'min',a.min(0),'max',a.max(0))
 # Merge vertices in position to identify connected geometry islands despite UV/normals.
 keys=[tuple(np.round(a,5)) for a in v];indices={};ids=[]
 for k in keys:
  if k not in indices:indices[k]=len(indices)
  ids.append(indices[k])
 par=list(range(len(indices)))
 def find(i):
  while par[i]!=i:par[i]=par[par[i]];i=par[i]
  return i
 for a,b,c in tr:
  x=find(ids[a]);y=find(ids[b]);z=find(ids[c]);par[y]=x;par[z]=x
 groups={}
 for i in range(len(v)):groups.setdefault(find(ids[i]),[]).append(i)
 for idx in sorted(groups.values(),key=len,reverse=True):
  a=v[idx];print('component',len(idx),'min',a.min(0),'max',a.max(0))
