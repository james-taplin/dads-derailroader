"""Curate an author-review handoff. Never zip the private project tree wholesale."""
from pathlib import Path
import argparse, hashlib, json, re, shutil, zipfile
from audit_build import audit, PACK, ROOT
from workspace import WORKSPACE, CONFIG, profile_path

def package(name,g29,c21):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',name):raise ValueError('One safe directory name required')
    destination=WORKSPACE/'share'/name
    if destination.exists() or destination.with_suffix('.zip').exists():raise ValueError('Fresh package name required')
    # Re-read bundles; do not trust stale audit JSON or a path supplied from another workspace.
    runs={'g29':g29.resolve(),'c21':c21.resolve()}
    for profile,run in runs.items():
        if profile_path(profile,'builds') not in run.parents:raise ValueError('Build outside this profile workspace')
        if not audit(profile,run,share=True):raise ValueError('Share audit failed: '+profile)
    files=[]
    for profile,run in runs.items():
        for basename in ('Info.json','ccl_bundle'):
            files.append((run/PACK[profile]/basename,Path('mods')/PACK[profile]/basename))
        for basename in ('bundle_audit.json','source_hashes.json','build_report.txt'):
            files.append((run/basename,Path('evidence')/profile/basename))
    for folder in ('tools','overrides'):
        for p in sorted((ROOT/folder).rglob('*')):
            if p.is_file() and p.suffix in ('.cs','.py','.ps1','.json') and '__pycache__' not in p.parts:
                files.append((p,Path('builder')/p.relative_to(ROOT)))
    for profile in CONFIG['profiles']:
        for p in sorted(profile_path(profile,'profile').glob('*.cs')):
            files.append((p,Path('profiles')/profile/p.name))
    for basename in ('README.md','MIGRATION_PLAN.md','UnityProjectContext.md'):
        files.append((ROOT/basename,Path('builder')/basename))
    files.append((WORKSPACE/'GUIDE_UNIFIED_LLW_CONVERSION.md',Path('builder/docs/GUIDE_UNIFIED_LLW_CONVERSION.md')))
    if (ROOT/'analysis/VALIDATION.md').exists():files.append((ROOT/'analysis/VALIDATION.md',Path('evidence/VALIDATION.md')))
    manifest=[]
    for source,relative in files:
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        manifest.append(dict(path=relative.as_posix(),bytes=source.stat().st_size,sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
    (destination/'README.txt').write_text('LLW author review package. Built with Codex/Claude AI assistance.\nInstall mods with Unity Mod Manager and CCL 3.1.9. Do not install duplicates of the same IDs.\nNew unified G29 0.9.2 and C21 0.1.4; in-game testing remains pending.\nG29 uses stock DV audio; both bundles contain no AudioClips. Fox truck meshes are included in compiled packs; no Fox source exports are included.\nBuilder code requires separate private source exports and CarCreator acquisition; this is not a self-contained Unity project.\nNo source game audio, decompiled game code, Unity caches, CarCreator package or third-party exports are included.\n',encoding='utf-8')
    (destination/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(destination.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(destination.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(destination))
    print(destination.with_suffix('.zip'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('g29',type=Path);p.add_argument('c21',type=Path);a=p.parse_args()
    package(a.name,a.g29,a.c21)
