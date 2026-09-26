import UnityPy
p='B:/SteamLibrary/steamapps/common/Derail Valley/DerailValley_Data/resources.assets'
e=UnityPy.load(p)
o={x.path_id:x for x in e.objects}
g={x.path_id:x.read_typetree() for x in e.objects if x.type.name=='GameObject'}
t={x.path_id:x.read_typetree() for x in e.objects if x.type.name=='Transform'}
gt={v['m_GameObject']['m_PathID']:k for k,v in t.items()}
for k,v in g.items():
 if v['m_Name']!='BrakeCylinderRelease':continue
 tr=t[gt[k]]; a=[]; tid=gt[k]
 while tid:
  a.append(g[t[tid]['m_GameObject']['m_PathID']]['m_Name']);tid=t[tid]['m_Father']['m_PathID']
 if 'CarFlatcar_ExternalInteractables' in a:print(k,'/'.join(a[::-1]),tr)

