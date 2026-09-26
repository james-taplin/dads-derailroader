"""Launch one immutable Unity export/test and wait for its actual outcome."""
from pathlib import Path
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time
from workspace import WORKSPACE, ROOT, CONFIG, MACHINE, profile_path
from prepare import prepare

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,data):p.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
def frozen_project(profile):
    project=profile_path(profile,'frozenProject')
    if not project.exists():
        source=profile_path(profile,'sourceProject')
        for folder in ('Assets','Packages','ProjectSettings'):shutil.copytree(source/folder,project/folder)
        dump(project/'migration-frozen.json',{'profile':profile,'source':str(source)})
    elif not (project/'migration-frozen.json').exists():raise ValueError('Unowned frozen project')
    groups=['g29'] if profile=='g29' else ['c21','c21-profile']
    manifest={}
    for group in groups:
        for p in sorted((ROOT/'baseline'/group).glob('*.cs')):
            shutil.copy2(p,project/'Assets/Editor'/p.name)
            manifest[p.relative_to(WORKSPACE).as_posix()]=sha(p)
    return project,manifest

def main():
    p=argparse.ArgumentParser();p.add_argument('profile',choices=CONFIG['profiles']);p.add_argument('run')
    p.add_argument('--frozen',action='store_true');p.add_argument('--tests',action='store_true');p.add_argument('--share',action='store_true');p.add_argument('--timeout',type=int,default=1200)
    a=p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+',a.run) or a.run.upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:raise ValueError('Invalid run name')
    if a.frozen and (a.tests or a.share):raise ValueError('Frozen replay cannot alter tests/audio')
    output=profile_path(a.profile,'builds')/a.run
    if output.exists():raise FileExistsError('Choose a new run name: '+str(output))
    if a.frozen:project,hashes=frozen_project(a.profile)
    else:
        project=prepare(a.profile);hashes=json.loads((project/'unified-scripts.json').read_text())
    if (project/'Temp/UnityLockfile').exists():raise ValueError('Project has an active/stale Unity lock; inspect before launch')
    output.mkdir(parents=True);dump(output/'source_hashes.json',hashes)
    method='UnifiedBuilderTests.Run' if a.tests else a.profile.upper()+'Config.Build'
    env=os.environ.copy();env.update(CCL_BUILD_OUT=str(output),RLW_PROBE_OUT=str(output),G29_SHARE='1' if a.share else '0')
    if not a.frozen:
        record=ROOT/'catalog'/(CONFIG['profiles'][a.profile]['catalogId']+'.json')
        env['CCL_CATALOG_RECORD']=str(record);shutil.copy2(record,output/'catalog_record.json')
    else:env.pop('CCL_CATALOG_RECORD',None)
    cmd=[MACHINE['unity'],'-projectPath',str(project),'-executeMethod',method,'-logFile',str(output/'unity_editor.log')]
    info=subprocess.STARTUPINFO();info.dwFlags|=subprocess.STARTF_USESHOWWINDOW;info.wShowWindow=0
    start=time.time();proc=subprocess.Popen(cmd,cwd=WORKSPACE,env=env,startupinfo=info)
    dump(output/'launch.json',dict(command=cmd,pid=proc.pid,profile=a.profile,frozen=a.frozen,share=a.share,started=time.strftime('%Y-%m-%dT%H:%M:%S')))
    print(f'Running {method}, PID {proc.pid}, output {output}',flush=True)
    try:code=proc.wait(timeout=a.timeout)
    except subprocess.TimeoutExpired:
        dump(output/'process_result.json',dict(status='timeout',pid=proc.pid,seconds=time.time()-start));raise RuntimeError('Unity timed out; process remains available for inspection')
    dump(output/'process_result.json',dict(exit_code=code,seconds=time.time()-start))
    if code:raise RuntimeError('Unity failed; inspect '+str(output/'unity_editor.log'))
    result_file=output/('editor_tests.json' if a.tests else 'result.json')
    if a.frozen and a.profile=='g29' and not result_file.exists():
        report=(output/'build_report.txt').read_text()
        pack=output/CONFIG['profiles'][a.profile]['pack']
        if 'EXCEPTION' in report or not all((pack/name).is_file() for name in ('Info.json','ccl_bundle')):raise RuntimeError('Legacy frozen export failed')
        result={'exported':True,'evidence':'Legacy G29 has no result.json; verified process exit, report and exported files. Full parity required below.'}
        dump(output/'legacy_completion.json',result)
    else:result=json.loads(result_file.read_text())
    if a.tests:
        if result.get('failed') or not result.get('passed'):raise RuntimeError(result)
        print(json.dumps(result));return
    if not result.get('exported'):raise RuntimeError('Build did not export')
    if a.frozen:
        from parity import compare
        if not compare(a.profile,output,profile_path(a.profile,'baselineBuild')):raise RuntimeError('Frozen parity failed')
    else:
        from audit_build import audit
        if not audit(a.profile,output,a.share):raise RuntimeError('Bundle audit failed')
    print('Validated '+str(output),flush=True)

if __name__=='__main__':main()
