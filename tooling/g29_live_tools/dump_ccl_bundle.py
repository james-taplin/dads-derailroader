"""Dump every MonoBehaviour in a CCL bundle: GameObject path, script class, and its scalar fields.
Used to copy port ids / control setups from working CCL locos.

usage: dump_ccl_bundle.py <ccl_bundle> <out.txt> [name filter regex]
"""
import re, sys, UnityPy

src, out = sys.argv[1], sys.argv[2]
flt = re.compile(sys.argv[3]) if len(sys.argv) > 3 else None
env = UnityPy.load(src)
objs = {o.path_id: o for o in env.objects}

names, parent_of, go_of_tf, tf_of_go = {}, {}, {}, {}
for o in env.objects:
    if o.type.name == 'GameObject':
        d = o.read_typetree()
        names[o.path_id] = d['m_Name']
        for c in d['m_Component']:
            pid = c['component']['m_PathID']
            if pid in objs and objs[pid].type.name in ('Transform', 'RectTransform'):
                tf_of_go[o.path_id] = pid
                go_of_tf[pid] = o.path_id
    elif o.type.name == 'Transform':
        d = o.read_typetree()
        parent_of[o.path_id] = d['m_Father']['m_PathID']


def path(go):
    parts, tf = [], tf_of_go.get(go)
    while tf:
        parts.append(names.get(go_of_tf.get(tf), '?'))
        tf = parent_of.get(tf)
    return '/'.join(reversed(parts))


scripts = {}
for o in env.objects:
    if o.type.name == 'MonoScript':
        d = o.read_typetree()
        scripts[o.path_id] = d['m_ClassName']


def short(v, depth=0):
    if isinstance(v, dict):
        if set(v) == {'m_FileID', 'm_PathID'}:
            pid = v['m_PathID']
            if not pid:
                return 'null'
            t = objs.get(pid)
            if t is None:
                return f'ext:{pid}'
            if t.type.name == 'GameObject':
                return 'GO:' + path(pid)
            if t.type.name == 'MonoBehaviour':
                dd = t.read_typetree()
                return f"{scripts.get(dd['m_Script']['m_PathID'], 'MB')}@{path(dd['m_GameObject']['m_PathID'])}"
            try:
                dd = t.read_typetree()
                g = dd.get('m_GameObject', {}).get('m_PathID')
                return f'{t.type.name}@{path(g)}' if g else f"{t.type.name}:{dd.get('m_Name', pid)}"
            except Exception:
                return t.type.name
        if depth > 2:
            return '{..}'
        return '{' + ', '.join(f'{k}={short(x, depth + 1)}' for k, x in v.items() if not k.startswith('m_') or k in ('m_Name',)) + '}'
    if isinstance(v, list):
        if len(v) > 12:
            return f'[{len(v)} items: ' + ', '.join(short(x, depth + 1) for x in v[:12]) + ', ...]'
        return '[' + ', '.join(short(x, depth + 1) for x in v) + ']'
    if isinstance(v, float):
        return f'{v:.4g}'
    return repr(v) if isinstance(v, str) else str(v)


lines = []
for o in env.objects:
    if o.type.name != 'MonoBehaviour':
        continue
    try:
        d = o.read_typetree()
    except Exception as e:
        continue
    cls = scripts.get(d['m_Script']['m_PathID'], '?')
    p = path(d['m_GameObject']['m_PathID'])
    if flt and not (flt.search(cls) or flt.search(p)):
        continue
    fields = {k: v for k, v in d.items() if not k.startswith('m_')}
    lines.append(f'{p}  [{cls}]  ' + '; '.join(f'{k}={short(v)}' for k, v in fields.items()))
lines.sort()
open(out, 'w', encoding='utf-8').write('\n'.join(lines))
print(len(lines), 'MonoBehaviours')
