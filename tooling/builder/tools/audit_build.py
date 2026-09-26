"""Audit exported CCL data against frozen G29/C21 references. Never installs a pack."""
from pathlib import Path
import argparse, collections, hashlib, json, math, re, sys
from workspace import ROOT, WORKSPACE, CONFIG, profile_path, enable_unitypy
enable_unitypy()
import UnityPy
REF={p:profile_path(p,'baselineBuild') for p in CONFIG['profiles']}
PACK={'g29':'LLW G-29','c21':'LLW C-21'}

def load(bundle):
    env=UnityPy.load(str(bundle)); objects={o.path_id:o.read_typetree() for o in env.objects}
    kinds={o.path_id:o.type.name for o in env.objects}
    scripts={i:d for i,d in objects.items() if kinds[i]=='MonoScript'}
    classes=collections.defaultdict(list)
    for i,d in objects.items():
        if kinds[i]=='MonoBehaviour':
            script=scripts.get(d['m_Script']['m_PathID'])
            classes[script['m_ClassName'] if script else 'MISSING_SCRIPT'].append(d)
    transforms={d['m_GameObject']['m_PathID']:d for i,d in objects.items() if kinds[i]=='Transform'}
    def name(d):return objects[d['m_GameObject']['m_PathID']]['m_Name']
    def path(d):
        parts=[name(d)];p=d['m_Father']['m_PathID'];seen=set()
        while p:
            if p in seen:raise ValueError('Cyclic hierarchy')
            seen.add(p);d=objects[p];parts.append(name(d));p=d['m_Father']['m_PathID']
        return '/'.join(reversed(parts))
    return objects,kinds,scripts,classes,transforms,name,path

def audit(profile,run,share=False):
    pack=run/PACK[profile];bundle=pack/'ccl_bundle';report=(run/'build_report.txt').read_text()
    baseline=REF[profile];oldreport=(baseline/'build_report.txt').read_text();errors=[]
    def check(ok,message):
        if not ok:errors.append(message)
    result=json.loads((run/'result.json').read_text());check(result['exported'],'Build did not export')
    warnings=[l for l in report.splitlines() if l.startswith('WARN ')]
    oldwarnings=[l for l in oldreport.splitlines() if l.startswith('WARN ')]
    check(warnings==oldwarnings,'Warning dispositions differ from exact accepted reference')
    check(result['warnings']==len(warnings),'Warning counter mismatch')
    check('EXCEPTION' not in report,'Build exception')
    info=json.loads((pack/'Info.json').read_text());cid='LLW_'+profile.upper()
    check(info['Id']==cid and 'DVCustomCarLoader' in info['Requirements'],'Metadata/dependency mismatch')
    objects,kinds,scripts,classes,transforms,name,path=load(bundle)
    audio=[d.get('m_Name','') for i,d in objects.items() if kinds[i]=='AudioClip']
    if share:check(not audio,'Share bundle contains AudioClips: '+str(audio))
    old=load(baseline/PACK[profile]/'ccl_bundle');oldclasses=old[3]
    assemblies=sorted({d['m_AssemblyName'] for d in scripts.values()})
    check(all(a in ('CCL.Types','CCL.Types.dll') for a in assemblies),'Non-CCL script assembly in bundle')
    check(not classes['MISSING_SCRIPT'],'Missing behaviour scripts')
    types={d['id']:d for d in classes['CustomCarType']};oldtypes={d['id']:d for d in oldclasses['CustomCarType']}
    check(set(types)=={cid,cid+'_Tender'},'Expected locomotive + tender types')
    for car in types:
        check(abs(types[car]['wheelRadius']-oldtypes[car]['wheelRadius'])<1e-5,'Changed measured driver/tender radius '+car)
    mass=types[cid]['mass'];water=math.pi*1.5**2/4*5*.85*1000*.75 if profile=='c21' else 6080
    expected=92000*.45359237-water if profile=='c21' else oldtypes[cid]['mass']
    check(abs(mass-expected)<.1,'Base mass ledger mismatch')
    variants={d['id']:d for d in classes['CustomCarVariant']}
    check(variants[cid]['TrainsetLiveries']==[cid,cid+'_Tender'],'Paired spawn missing')
    for cls in ('CarAutoCoupler','RigidCoupler','KeepCoupledInteriorLoaded','CabTeleportDestinationProxy'):
        check(len(classes[cls])==1,'Expected exactly one '+cls)
    plates=[t for t in transforms.values() if name(t) in ('[car plate anchor1]','[car plate anchor2]')]
    check(len(plates)==4,'Expected four plate anchors')
    plate_data=[]
    for t in plates:
        q=t['m_LocalRotation'];x=t['m_LocalPosition']['x'];right_x=1-2*(q['y']**2+q['z']**2)
        check(x*right_x>0,'Inward plate: '+path(t));plate_data.append(dict(path=path(t),x=x,right_x=right_x))
    cup_class='ManualOilingPoint';provider_class='PositionSyncProviderProxy'
    cups=classes[cup_class];providers=classes[provider_class];count=6 if profile=='g29' else 8
    check(len(cups)==len(providers)==count,'Cup/provider count changed')
    check(sorted(c['SyncTag'] for c in cups)==sorted(p['syncTag'] for p in providers),'Cup/provider tags differ')
    def cup_order(data):
        obs,_,_,cls,tfs,_,_=data
        parent_ids={tfs[c['m_GameObject']['m_PathID']]['m_Father']['m_PathID'] for c in cls[cup_class]}
        if len(parent_ids)!=1:return []
        return [obs[obs[ch['m_PathID']]['m_GameObject']['m_PathID']]['m_Name'] for ch in obs[next(iter(parent_ids))]['m_Children']]
    order=cup_order((objects,kinds,scripts,classes,transforms,name,path))
    check(order==cup_order(old),'Oil save-index order changed')
    for p in providers:
        tr=transforms[p['m_GameObject']['m_PathID']];parent=objects[tr['m_Father']['m_PathID']]
        comps=objects[parent['m_GameObject']['m_PathID']]['m_Component']
        check(any(kinds[c['component']['m_PathID']]=='MeshFilter' for c in comps),'Oil provider not parented to rod mesh')
    for cls in ('WheelRotationViaAnimationProxy','PoweredWheelRotationViaAnimationProxy'):
        radii=sorted(d['wheelRadius'] for d in classes[cls]);oldr=sorted(d['wheelRadius'] for d in oldclasses[cls])
        check(len(radii)==len(oldr) and all(abs(a-b)<1e-5 for a,b in zip(radii,oldr)),'Wheel animation radius/count changed: '+cls)
    for sim in classes['SimConnectionsDefinitionProxy']:
        ids=[objects.get(p['m_PathID'],{}).get('ID') for p in sim['executionOrder']]
        check(None not in ids and len(ids)==len(set(ids)),'Missing/duplicate simulation execution IDs')
    check(len(classes['SimConnectionsDefinitionProxy'])==2,'Expected two simulations')
    reader=classes['LocoControlsReaderProxy'][0];indicator=classes['LocoIndicatorReaderProxy'][0]
    for field in ('cabLight','headlightsFront','cylCock','injector','firedoor','blower','damper','blowdown','coalDump','lubricator','bell'):
        check(reader.get(field,{}).get('m_PathID',0)!=0,'Missing HUD control '+field)
    for field in ('speed','steam','chestPressure','brakePipe','mainReservoir','brakeCylinder','locoWaterLevel','locoCoalLevel','tenderWaterLevel','tenderCoalLevel'):
        check(indicator.get(field,{}).get('m_PathID',0)!=0,'Missing HUD indicator '+field)
    firebox=objects[indicator['locoCoalLevel']['m_PathID']]
    check(abs(firebox['maxValue']-(65 if profile=='g29' else 100))<.01,'Wrong firebox indicator range')
    ports=sorted({d.get('portId','') for d in classes['InteractablePortFeederProxy']})
    check(ports==sorted({d.get('portId','') for d in oldclasses['InteractablePortFeederProxy']}),'Control ports changed')
    beam_pattern=r'^\[coupler_rig_(front|rear)\] at .*?: end beam z ([-\d.]+) .*?live coupler z ([-\d.]+);'
    check(re.findall(beam_pattern,report,re.M)==re.findall(beam_pattern,oldreport,re.M),'Outer coupler geometry changed')
    expected_gap='-8.194' if profile=='g29' else '-7.445'
    check('tender placed at z '+expected_gap in report,'Tender drawbar spacing changed')
    check(f'oil phase validation: {count} animated rod providers, four phases, source seat proximity passed' in report,'Four-phase oil validation absent')
    check('solid overlap: 0 cells' in report,'Nonzero solid overlap at drawbar')
    hashes=json.loads((run/'source_hashes.json').read_text());drift=[]
    expected_sources=list((ROOT/'tools/unity').glob('*.cs'))+list(profile_path(profile,'profile').glob('*.cs'))
    cid=CONFIG['profiles'][profile]['catalogId']
    expected_sources += [ROOT/'catalog'/f'{cid}.json',ROOT/'overrides'/f'{cid}.json']
    expected_keys={p.relative_to(WORKSPACE).as_posix() for p in expected_sources}
    normalized={str(k).replace(chr(92),'/'):v for k,v in hashes.items()}
    check(set(normalized)==expected_keys,'Source manifest coverage mismatch')
    for file,digest in normalized.items():
        if file not in expected_keys or hashlib.sha256((WORKSPACE/file).read_bytes()).hexdigest()!=digest:drift.append(file)
    check(not drift,'Build does not use current source: '+str(drift))
    output=dict(schema=1,audit_kind='current_profile',source_manifest_sha256=hashlib.sha256((run/'source_hashes.json').read_bytes()).hexdigest(),status='passed' if not errors else 'failed',profile=profile,errors=errors,
        bundle_sha256=hashlib.sha256(bundle.read_bytes()).hexdigest(),bundle_bytes=bundle.stat().st_size,
        reference=str(baseline),warnings=warnings,script_assemblies=assemblies,
        plates=plate_data,oil_save_order=order,control_ports=ports,base_mass_kg=mass,spawn_boiler_water_l=water,
        audio_clips=audio,share_audio_pass=not audio,
        third_party_assets='Fox tender truck meshes remain inside compiled packs, as in C14; no third-party source exports are packaged by share_project.py',
        runtime_validated=False,limitations=['No game spawn/driving/save reload or VR test of merged output','Render cups/hardware are measured stand-ins, not runtime replacements'])
    (run/'bundle_audit.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({k:output[k] for k in ('status','profile','errors','bundle_sha256','base_mass_kg')},indent=2))
    return not errors

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('profile',choices=REF);p.add_argument('run',type=Path);p.add_argument('--share',action='store_true');a=p.parse_args()
    sys.exit(0 if audit(a.profile,a.run.resolve(),a.share) else 1)
