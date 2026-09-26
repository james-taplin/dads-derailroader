"""Explicit-target installation with fresh audit, immutable rollback and hash checks."""
from pathlib import Path
import argparse, hashlib, json, re, shutil, time, uuid
from workspace import WORKSPACE, CONFIG, MACHINE, profile_path
from audit_build import audit

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def install(profile,run,target_root,replace=False,allow_game=False):
    run=Path(run).resolve();target_root=Path(target_root).resolve();game=Path(MACHINE['mods']).resolve()
    if not run.is_relative_to(profile_path(profile,'builds').resolve()):raise ValueError('Run outside this profile workspace')
    if (target_root==game or target_root.is_relative_to(game)) and not allow_game:raise ValueError('Game installation requires explicit --allow-game')
    if not audit(profile,run):raise ValueError('Fresh audit failed')
    evidence=json.loads((run/'bundle_audit.json').read_text());pack=CONFIG['profiles'][profile]['pack'];source=run/pack
    if evidence.get('schema')!=1 or evidence.get('profile')!=profile or evidence.get('status')!='passed' or sha(source/'ccl_bundle')!=evidence['bundle_sha256']:raise ValueError('Audit schema/profile/hash mismatch')
    info=json.loads((source/'Info.json').read_text())
    if info['Id']!='LLW_'+profile.upper():raise ValueError('Pack ID mismatch')
    destination=target_root/pack
    if destination.is_symlink() or (hasattr(destination,'is_junction') and destination.is_junction()):raise ValueError('Linked install target refused')
    if destination.exists() and not replace:raise FileExistsError('Use --replace with verified rollback')
    key=time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8];record=WORKSPACE/'reference/private/rollback'/key
    record.mkdir(parents=True);target_root.mkdir(parents=True,exist_ok=True)
    rollback=None
    if destination.exists():
        rollback=record/pack;shutil.copytree(destination,rollback)
        old={str(p.relative_to(destination)):sha(p) for p in destination.rglob('*') if p.is_file()}
        if old!={str(p.relative_to(rollback)):sha(p) for p in rollback.rglob('*') if p.is_file()}:raise ValueError('Rollback hash mismatch')
        (record/'rollback-hashes.json').write_text(json.dumps(old,indent=2)+'\n')
    stage=target_root/('.llw-stage-'+key);stage.mkdir()
    for name in ('Info.json','ccl_bundle'):shutil.copy2(source/name,stage/name)
    if sha(stage/'ccl_bundle')!=evidence['bundle_sha256']:raise ValueError('Staged pack hash mismatch')
    # Rename the old pack aside; do not delete it. Rollback snapshot is also retained.
    previous=record/'previous-live'
    if destination.exists() and destination.drive.lower()!=previous.drive.lower():raise ValueError('Replacement requires same-volume rollback storage')
    if destination.exists():destination.rename(previous)
    try:stage.rename(destination)
    except BaseException:
        if previous.exists():previous.rename(destination)
        raise
    result=dict(schema=1,profile=profile,run=str(run),target=str(destination),bundle_sha256=sha(destination/'ccl_bundle'),rollback=str(rollback) if rollback else None,previous=str(previous) if previous.exists() else None,game_install=target_root==game)
    (record/'install.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('profile',choices=CONFIG['profiles']);p.add_argument('run',type=Path);p.add_argument('--target-root',required=True,type=Path);p.add_argument('--replace',action='store_true');p.add_argument('--allow-game',action='store_true');a=p.parse_args()
    install(a.profile,a.run,a.target_root,a.replace,a.allow_game)
