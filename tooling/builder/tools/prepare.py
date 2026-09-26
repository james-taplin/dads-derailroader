"""Clone a reference project's inputs once; refresh only the unified editor scripts thereafter."""
from pathlib import Path
import argparse, hashlib, json, shutil
from catalog import CAT, make_record, sha

from workspace import ROOT, WORKSPACE, CONFIG, profile_path
SOURCES = {p:profile_path(p,'sourceProject') for p in CONFIG['profiles']}

def prepare(profile):
    cid={'g29':'ls-260-g29','c21':'ls-280-c21'}[profile]
    record_path=ROOT/'catalog'/f'{cid}.json'
    record=json.loads(record_path.read_text())
    fresh=make_record(CAT/cid)
    if record!=fresh:
        raise RuntimeError('Catalogue inputs/overrides changed; regenerate catalog.py and review before building')
    source = SOURCES[profile]
    project = profile_path(profile,'project')
    if (project/'Temp/UnityLockfile').exists():
        raise RuntimeError('Close the unified project before refreshing scripts')
    if not project.exists():
        for sub in ('Assets', 'Packages', 'ProjectSettings'):
            shutil.copytree(source/sub, project/sub)
        (project/'unified-project.json').write_text(json.dumps({'source':str(source),'profile':profile},indent=2))
    elif not (project/'unified-project.json').exists():
        raise RuntimeError('Refusing to modify an unowned project')
    scripts = sorted((ROOT/'tools/unity').glob('*.cs')) + sorted(profile_path(profile,'profile').glob('*.cs'))
    manifest = {}
    for f in scripts:
        shutil.copy2(f, project/'Assets/Editor'/f.name)
        manifest[str(f.relative_to(WORKSPACE))] = hashlib.sha256(f.read_bytes()).hexdigest()
    manifest[str(record_path.relative_to(WORKSPACE))]=sha(record_path)
    manifest[f'builder/overrides/{cid}.json']=sha(ROOT/'overrides'/f'{cid}.json')
    (project/'unified-scripts.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(project)
    return project

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('profile',choices=SOURCES)
    prepare(parser.parse_args().profile)
