"""Resolve AssetRipper's unresolved clip paths (path_0x<crc32>_xxx) against the transform paths of every prefab in the export.

Unity stores only CRC32(path) in built clips; RR binds each clip to the root of the car prefab that uses it (loco, tender,
truck), so every hash should match a transform path relative to one prefab root. A clip's hashes are resolved against
the prefab that explains the most of them (ties: first prefab). Writes a report and, with --apply <dst_assets>, rewrites
the .anim files in <dst_assets> with the real paths.

usage: resolve_clip_paths.py <src_assets> <report.txt> [--apply <dst_assets>]
"""
import os, re, sys, glob, zlib

src, report = sys.argv[1], sys.argv[2]
apply_dst = sys.argv[4] if len(sys.argv) > 4 and sys.argv[3] == '--apply' else None


def prefab_paths(prefab):
    txt = open(prefab, encoding='utf-8').read()
    names, father, go_of_tf = {}, {}, {}
    for m in re.finditer(r'^--- !u!(\d+) &(-?\d+)[^\n]*\n(.*?)(?=^--- |\Z)', txt, re.S | re.M):
        cls, fid, body = m.group(1), m.group(2), m.group(3)
        if cls == '1':
            names[fid] = re.search(r'm_Name: (.*)', body).group(1).strip()
        elif cls == '4':
            go_of_tf[fid] = re.search(r'm_GameObject: \{fileID: (-?\d+)\}', body).group(1)
            father[fid] = re.search(r'm_Father: \{fileID: (-?\d+)\}', body).group(1)

    def path_of(tf):
        parts = []
        while father.get(tf, '0') != '0':
            parts.append(names[go_of_tf[tf]])
            tf = father[tf]
        return '/'.join(reversed(parts))

    # Some packs bind clips to the prefab root, others to the child holding the AnimationMap ('Master' on GN M-2)
    by_hash = {}
    for tf in go_of_tf:
        p = path_of(tf)
        for q in {p, p.partition('/')[2]} if '/' in p else {p}:
            h = zlib.crc32(q.encode('utf-8')) & 0xFFFFFFFF
            # A child-relative source hash still needs the full prefab-root path
            # in the DV working copy. E.g. hash(Main/Coal) -> Tender/Main/Coal.
            if p not in by_hash.get(h, []):
                by_hash.setdefault(h, []).append(p)
    return by_hash


prefabs = sorted(glob.glob(os.path.join(src, '**', '*.prefab'), recursive=True))
tables = [(os.path.basename(p), prefab_paths(p)) for p in prefabs]

pat = re.compile(r'path_0x([0-9A-Fa-f]+)_\w+')
out = open(report, 'w', encoding='utf-8')
for name, t in tables:
    dups = {h: v for h, v in t.items() if len(v) > 1}
    if dups:
        out.write('DUPLICATE PATHS in %s (ambiguous): %s\n' % (name, dups))
unresolved_total = 0
for ap in sorted(glob.glob(os.path.join(src, '**', '*.anim'), recursive=True)):
    t = open(ap, encoding='utf-8').read()
    found = sorted(set(pat.findall(t)))
    best = max(tables, key=lambda nt: sum(1 for h in found if int(h, 16) in nt[1])) if found else tables[0]
    out.write('==== %s  -> prefab %s\n' % (os.path.relpath(ap, src), best[0]))
    mapping = {}
    for h in found:
        hit = best[1].get(int(h, 16))
        if hit:
            mapping[h] = hit[0]
            out.write('   0x%-9s -> %s\n' % (h, hit[0]))
        else:
            unresolved_total += 1
            out.write('   0x%-9s -> ??? UNRESOLVED\n' % h)
    if apply_dst:
        new = pat.sub(lambda m: mapping.get(m.group(1), m.group(0)), t)
        # AssetRipper can put tender clips beside the prefab, and two folders
        # can contain distinct clips with the same filename. Preserve the tree.
        dst = os.path.join(apply_dst, os.path.relpath(ap, src))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'w', encoding='utf-8', newline='\n').write(new)
out.write('\nunresolved: %d\n' % unresolved_total)
out.close()
print('unresolved', unresolved_total)
if unresolved_total:
    sys.exit(2)
