"""Fingerprint the exported model/driver geometry on which an oil screen depends.

Does not use Unity object IDs as semantic identity. Comparing identical outputs
supports reusing a screen when unrelated coupler/control objects were changed.
Any changed fingerprint requires inspection or a fresh screen.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from workspace import enable_unitypy
enable_unitypy()
import UnityPy
from UnityPy.helpers.MeshHelper import MeshHandler
from audit_new_loco import Snapshot,ptr


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def fingerprint(bundle):
    env=UnityPy.load(str(bundle));readers={o.path_id:o for o in env.objects}
    objects={i:o.read_typetree() for i,o in readers.items()};kinds={i:o.type.name for i,o in readers.items()}
    s=Snapshot(objects,kinds)
    def chain(t):
        out=[]
        while t:
            go=objects[ptr(t['m_GameObject'])]
            out.append(dict(name=go['m_Name'],active=go['m_IsActive'],position=t['m_LocalPosition'],rotation=t['m_LocalRotation'],scale=t['m_LocalScale']))
            t=objects.get(ptr(t['m_Father']))
        return list(reversed(out))
    def stable(value):
        if isinstance(value,dict):
            if set(value)=={'m_FileID','m_PathID'}:
                ident=ptr(value);target=objects.get(ident,{})
                if not ident:return None
                t=target if kinds.get(ident)=='Transform' else s.transforms.get(ptr(target.get('m_GameObject')))
                return {'kind':kinds.get(ident),'name':target.get('m_Name'),'path':s.path(t) if t else None}
            return {k:stable(v) for k,v in value.items()}
        if isinstance(value,list):return [stable(v) for v in value]
        return value
    meshes={};providers={};animators={};clips={};controllers={}
    for ident,data in objects.items():
        kind=kinds[ident]
        if kind in ('MeshFilter','SkinnedMeshRenderer','Animator'):
            t=s.transforms.get(ptr(data.get('m_GameObject')))
            if not t or '/Model/' not in s.path(t):continue
            path=s.path(t)
            if kind=='Animator':
                animators[path]={'transformChain':chain(t),'data':stable(data)}
                continue
            mesh=readers[ptr(data['m_Mesh'])];handler=MeshHandler(mesh.read());handler.process()
            geometry={'vertices':handler.m_Vertices,'triangles':[triangle for sub in handler.get_triangles() for triangle in sub]}
            go=objects[ptr(data['m_GameObject'])]
            renderers=[objects[ptr(c['component'])] for c in go['m_Component'] if kinds[ptr(c['component'])] in ('MeshRenderer','SkinnedMeshRenderer')]
            meshes[path]={'meshName':objects[mesh.path_id].get('m_Name'),'geometrySHA256':digest(geometry),
                          'vertices':len(handler.m_Vertices),'triangles':len(geometry['triangles']),
                          'transformChain':chain(t),'rendererEnabled':[r['m_Enabled'] for r in renderers]}
        elif kind=='AnimationClip':
            # Clip trees contain string/path hashes and curves, not scene IDs.
            clip=dict(data);clip.pop('m_ObjectHideFlags',None)
            clips.setdefault(data['m_Name'],[]).append(digest(stable(clip)))
        elif kind in ('AnimatorController','AnimatorOverrideController'):
            controllers.setdefault(data['m_Name'],[]).append(digest(stable(data)))
    for data in s.classes['PositionSyncProviderProxy']:
        t=s.transforms[ptr(data['m_GameObject'])]
        providers[data['syncTag']]={'path':s.path(t),'transformChain':chain(t),'worldPosition':s.world_position(t)}
    semantic={'modelMeshes':meshes,'providers':providers,'modelAnimators':animators,
              'animationClips':{k:sorted(v) for k,v in clips.items()},
              'animationControllers':{k:sorted(v) for k,v in controllers.items()},
              'poweredWheelAnimation':{s.name(d):stable(d) for d in s.classes['PoweredWheelRotationViaAnimationProxy']}}
    return dict(schema=1,bundleSHA256=hashlib.sha256(Path(bundle).read_bytes()).hexdigest(),
                semanticSHA256=digest(semantic),scope='All Model MeshFilters/skinned meshes and active/transform chains; oil providers; Model animators; all exported animation curves/controllers; powered wheel animation registration/phase offsets.',
                **semantic)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('bundle',type=Path);parser.add_argument('output',type=Path);parser.add_argument('--compare',type=Path)
    args=parser.parse_args();result=fingerprint(args.bundle)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('semanticSHA256',result['semanticSHA256']);print('meshes',len(result['modelMeshes']),'providers',len(result['providers']))
    if args.compare:
        before=json.loads(args.compare.read_text(encoding='utf-8'))
        changed={key:sorted(k for k in set(before[key])|set(result[key]) if before[key].get(k)!=result[key].get(k))
                 for key in ('modelMeshes','providers','modelAnimators','animationClips','animationControllers','poweredWheelAnimation')}
        print(json.dumps({'identical':before['semanticSHA256']==result['semanticSHA256'],'changed':changed},indent=2))
        sys.exit(0 if before['semanticSHA256']==result['semanticSHA256'] else 1)
