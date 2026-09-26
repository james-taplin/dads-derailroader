"""Print the transform tree (local position, component types) of GameObjects in a CCL bundle whose path matches a regex.
Used to see how working CCL cars place bogies, axles, coupler rigs and colliders.

usage: dump_ccl_transforms.py <ccl_bundle> <path regex> [max depth below match]
"""
import re, sys, UnityPy

src, rx = sys.argv[1], re.compile(sys.argv[2])
max_depth = int(sys.argv[3]) if len(sys.argv) > 3 else 3
env = UnityPy.load(src)
objs = {o.path_id: o for o in env.objects}
scripts = {o.path_id: o.read_typetree()['m_ClassName'] for o in env.objects if o.type.name == 'MonoScript'}

go_name, go_comps, tf_go, tf_data = {}, {}, {}, {}
for o in env.objects:
    if o.type.name == 'GameObject':
        d = o.read_typetree()
        go_name[o.path_id] = d['m_Name']
        go_comps[o.path_id] = [c['component']['m_PathID'] for c in d['m_Component']]
    elif o.type.name == 'Transform':
        d = o.read_typetree()
        tf_data[o.path_id] = d
        tf_go[o.path_id] = d['m_GameObject']['m_PathID']


def path(tf):
    parts = []
    while tf:
        parts.append(go_name.get(tf_go.get(tf), '?'))
        tf = tf_data.get(tf, {}).get('m_Father', {}).get('m_PathID')
    return '/'.join(reversed(parts))


def comp_names(go):
    out = []
    for pid in go_comps.get(go, []):
        o = objs.get(pid)
        if not o or o.type.name == 'Transform':
            continue
        if o.type.name == 'MonoBehaviour':
            try:
                out.append(scripts.get(o.read_typetree()['m_Script']['m_PathID'], 'MB'))
            except Exception:
                out.append('MB')
        elif o.type.name == 'BoxCollider':
            d = o.read_typetree()
            c, s = d['m_Center'], d['m_Size']
            out.append(f"Box(c {c['x']:.2f},{c['y']:.2f},{c['z']:.2f} s {s['x']:.2f},{s['y']:.2f},{s['z']:.2f})")
        else:
            out.append(o.type.name)
    return ','.join(out)


def walk(tf, depth, indent):
    d = tf_data[tf]
    p = d['m_LocalPosition']
    r = d['m_LocalRotation']
    rot = '' if abs(r['w']) > 0.9999 else f" rot({r['x']:.3f},{r['y']:.3f},{r['z']:.3f},{r['w']:.3f})"
    print(f"{'  ' * indent}{go_name.get(tf_go[tf])}  ({p['x']:.3f}, {p['y']:.3f}, {p['z']:.3f}){rot}  {comp_names(tf_go[tf])}")
    if depth < max_depth:
        for c in d['m_Children']:
            if c['m_PathID'] in tf_data:
                walk(c['m_PathID'], depth + 1, indent + 1)


roots = [tf for tf in tf_data if rx.search(path(tf))]
# only the top-most matches
roots = [tf for tf in roots if not any(p != tf and path(tf).startswith(path(p) + '/') for p in roots)]
for tf in sorted(roots, key=path):
    print('====', path(tf))
    walk(tf, 0, 0)
