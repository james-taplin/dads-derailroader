"""Copy one prefab and everything it references (by GUID, transitively) from an AssetRipper Assets dir into another Assets dir.

Scripts (.cs) are skipped: the prefab's MonoBehaviours become 'missing script' components, which the builder strips.
Files keep their names and .meta (same GUIDs) and land under <dest>/<subfolder>/<original relative path>.

usage: copy_deps.py <src Assets dir> <prefab path relative to it> <dest Assets dir> <subfolder>
"""
import os, re, shutil, sys, glob

src, prefab, dest, sub = sys.argv[1:5]
guid_file = {}
for meta in glob.glob(os.path.join(src, '**', '*.meta'), recursive=True):
    m = re.search(r'guid: (\w+)', open(meta, encoding='utf-8', errors='ignore').read())
    if m:
        guid_file[m.group(1)] = meta[:-5]

todo, done = [os.path.join(src, prefab)], set()
while todo:
    f = todo.pop()
    if f in done or not os.path.isfile(f):
        continue
    done.add(f)
    if f.endswith('.cs'):
        continue
    if not f.endswith(('.prefab', '.mat', '.anim', '.asset', '.controller', '.shader')):
        continue
    for g in set(re.findall(r'guid: (\w+)', open(f, encoding='utf-8', errors='ignore').read())):
        if g in guid_file:
            todo.append(guid_file[g])

n = 0
for f in sorted(done):
    if f.endswith('.cs') or not os.path.isfile(f):
        continue
    rel = os.path.relpath(f, src)
    out = os.path.join(dest, sub, rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    shutil.copy2(f, out)
    if os.path.isfile(f + '.meta'):
        shutil.copy2(f + '.meta', out + '.meta')
    n += 1
print('copied', n, 'files ->', os.path.join(dest, sub))
