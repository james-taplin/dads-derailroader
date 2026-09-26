"""Dump the RLW prefab hierarchy, materials and animation-clip bindings from an AssetRipper export.

usage: analyze_export.py <ExportedProject\\Assets> <out_dir>
"""
import os, re, sys, glob, yaml
from collections import defaultdict

assets, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)

class L(yaml.SafeLoader):
    pass
L.add_multi_constructor('tag:unity3d.com', lambda l, s, n: l.construct_mapping(n, deep=True))


def load_docs(path):
    txt = open(path, encoding='utf-8').read()
    docs = {}
    for m in re.finditer(r'^--- !u!(\d+) &(-?\d+)[^\n]*\n(.*?)(?=^--- |\Z)', txt, re.S | re.M):
        cls, fid, body = int(m.group(1)), int(m.group(2)), m.group(3)
        d = yaml.load(body, Loader=L)
        (typ, val), = d.items()
        docs[fid] = (cls, typ, val)
    return docs


guid_name = {}
for meta in glob.glob(os.path.join(assets, '**', '*.meta'), recursive=True):
    g = re.search(r'guid: (\w+)', open(meta, encoding='utf-8').read())
    if g:
        guid_name[g.group(1)] = os.path.relpath(meta[:-5], assets)


def pairs(x):
    if isinstance(x, dict):
        return list(x.items())
    return [next(iter(e.items())) for e in x or []]


def ref(r):
    if not r or not r.get('guid'):
        return None
    return guid_name.get(r['guid'], r['guid'])


def v3(d):
    return '(%.4g, %.4g, %.4g)' % tuple(float(d[k]) for k in 'xyz')


def q(d):
    return '(%.4g, %.4g, %.4g, %.4g)' % tuple(float(d[k]) for k in 'xyzw')


def dump_prefab(path, fh):
    docs = load_docs(path)
    go_comps = defaultdict(list)
    tf_of_go = {}
    for fid, (cls, typ, v) in docs.items():
        if isinstance(v, dict) and 'm_GameObject' in v:
            go = v['m_GameObject']['fileID']
            go_comps[go].append((fid, cls, typ, v))
            if cls == 4:
                tf_of_go[go] = fid
    name = {fid: v['m_Name'] for fid, (cls, typ, v) in docs.items() if cls == 1}
    tfs = {fid: v for fid, (cls, typ, v) in docs.items() if cls == 4}
    roots = [f for f, v in tfs.items() if v['m_Father']['fileID'] == 0]
    stats = defaultdict(int)

    def walk(tfid, depth, path):
        t = tfs[tfid]
        go = t['m_GameObject']['fileID']
        nm = name.get(go, '?')
        p = path + '/' + nm if path else nm
        active = docs[go][2].get('m_IsActive', 1)
        s = t['m_LocalScale']
        extra = []
        for fid, cls, typ, v in go_comps[go]:
            if cls == 4:
                continue
            stats[typ] += 1
            if cls == 33:
                extra.append('mesh=' + str(ref(v['m_Mesh'])).replace('Mesh\\', ''))
            elif cls == 23:
                mats = [str(ref(m)).replace('Material\\', '') for m in v.get('m_Materials') or []]
                extra.append('mats=' + '|'.join(mats) + ('' if v.get('m_Enabled', 1) else ' [rend OFF]'))
            elif cls == 64:
                extra.append('MeshCollider(%s convex=%s trig=%s)' % (str(ref(v['m_Mesh'])).replace('Mesh\\', ''), v.get('m_Convex'), v.get('m_IsTrigger')))
            elif cls == 65:
                extra.append('BoxCollider(c=%s s=%s)' % (v3(v['m_Center']), v3(v['m_Size'])))
            elif cls == 114:
                extra.append('MB ' + str(ref(v['m_Script'])))
            else:
                extra.append(typ)
        fh.write('%s%s%s  p=%s r=%s%s  %s\n' % ('  ' * depth, nm, '' if active else ' [INACTIVE]', v3(t['m_LocalPosition']), q(t['m_LocalRotation']),
                                               '' if (s['x'], s['y'], s['z']) == (1, 1, 1) else ' s=' + v3(s), '; '.join(extra)))
        for c in t.get('m_Children') or []:
            walk(c['fileID'], depth + 1, p)

    for r in roots:
        walk(r, 0, '')
    fh.write('\nCOMPONENT COUNTS: %s\n' % dict(stats))


with open(os.path.join(out, 'hierarchy.txt'), 'w', encoding='utf-8') as fh:
    for pf in sorted(glob.glob(os.path.join(assets, '**', '*.prefab'), recursive=True)):
        fh.write('==== %s\n' % os.path.relpath(pf, assets))
        dump_prefab(pf, fh)
        fh.write('\n')

# animation clips
with open(os.path.join(out, 'clips.txt'), 'w', encoding='utf-8') as fh:
    for ap in sorted(glob.glob(os.path.join(assets, 'AnimationClip', '*.anim'))):
        (cls, typ, c), = load_docs(ap).values()
        st = c.get('m_AnimationClipSettings', {})
        fh.write('==== %s  legacy=%s  rate=%s  start=%s stop=%s loop=%s\n' % (
            os.path.basename(ap), c.get('m_Legacy'), c.get('m_SampleRate'), st.get('m_StartTime'), st.get('m_StopTime'), st.get('m_LoopTime')))
        binds = defaultdict(set)
        for key, kind in (('m_RotationCurves', 'rot'), ('m_CompressedRotationCurves', 'crot'), ('m_EulerCurves', 'euler'),
                          ('m_PositionCurves', 'pos'), ('m_ScaleCurves', 'scale')):
            for cv in c.get(key) or []:
                binds[cv['path']].add(kind)
        for cv in c.get('m_FloatCurves') or []:
            binds[cv['path']].add('float:%s.%s' % (cv.get('classID'), cv['attribute']))
        for cv in c.get('m_PPtrCurves') or []:
            binds[cv['path']].add('pptr:' + cv['attribute'])
        for path in sorted(binds):
            fh.write('   %-70s %s\n' % (path, ','.join(sorted(binds[path]))))
        ev = c.get('m_Events') or []
        if ev:
            fh.write('   events: %s\n' % [e.get('functionName') for e in ev])

# materials
with open(os.path.join(out, 'materials.txt'), 'w', encoding='utf-8') as fh:
    for mp in sorted(glob.glob(os.path.join(assets, 'Material', '*.mat'))):
        (cls, typ, m), = load_docs(mp).values()
        sh = ref(m['m_Shader']) or m['m_Shader']
        props = m.get('m_SavedProperties', {})
        tex = []
        for k, v in pairs(props.get('m_TexEnvs')):
            r = ref(v['m_Texture'])
            if r:
                tex.append('%s=%s' % (k, r.replace('Texture2D\\', '')))
        cols = []
        for k, v in pairs(props.get('m_Colors')):
            if k in ('_BaseColor', '_Color', '_EmissionColor'):
                cols.append('%s=(%.3g,%.3g,%.3g,%.3g)' % (k, v['r'], v['g'], v['b'], v['a']))
        fl = []
        for k, v in pairs(props.get('m_Floats')):
            if k in ('_Smoothness', '_Metallic', '_Surface', '_AlphaClip', '_Cutoff', '_Glossiness', '_BumpScale'):
                fl.append('%s=%g' % (k, v))
        fh.write('%-40s %s\n   %s\n   %s  %s  kw=%s\n' % (m['m_Name'], sh, ' '.join(tex), ' '.join(cols), ' '.join(fl), m.get('m_ShaderKeywords') or m.get('m_ValidKeywords')))
print('done')
