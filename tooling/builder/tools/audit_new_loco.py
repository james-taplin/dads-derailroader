"""First-build gates for a single coal-fired tank locomotive; no predecessor needed.

Expectations come from the reviewed runtime JSON record. Warning dispositions are
exact full lines plus reasons in profile/warning_dispositions.json. Runtime and
visual acceptance remain separate from these serialized/export checks.
"""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import math
import re
import sys

# Explicit CCL components used by the established steam builder and tank's
# handbrake feeder. A newly introduced component needs a deliberate review.
ALLOWED_COMPONENTS = set('''AnalogSetValueJoystickInputProxy AnimatorPortReaderProxy AudioLayerProxy
BaseControlsOverriderProxy BasePortsOverriderProxy BlowbackParticlePortReaderProxy BoilerDefinitionProxy
BoilerSimControllerProxy BroadcastPortValueConsumerProxy BroadcastPortValueProviderProxy ButtonProxy CabLightsControllerProxy
CabTeleportDestinationProxy CarAutoCoupler CarLightsOptimizerProxy CoalPileSimControllerProxy CompressorSimControllerProxy
ConfigurablePortDefinitionProxy ConfigurablePortsDefinitionProxy CopyChuffSystem CopyVanillaAudioSystem
CopyVanillaParticleSystem CustomCarPack CustomCarType CustomCarVariant CustomWheelSlideSparks
CylinderCockParticlePortReaderProxy DamageControllerProxy DynamoDefinitionProxy EngineOnReaderProxy
EnvironmentDamagerProxy ExplosionActivationOnSignalProxy ExternalControlDefinitionProxy FireProxy
FireboxDefinitionProxy FireboxSimControllerProxy FuseControllerDefinitionProxy GrabberRaycastPassThroughProxy
HandbrakeFeederProxy HeadlightBeamControllerProxy HeadlightProxy HeadlightSetup HeadlightsMainControllerProxy
HeadlightsSubControllerStandardProxy HornControlProxy IndependentFusesDefinitionProxy IndicatorBrakeCylinderReaderProxy
IndicatorBrakePipeReaderProxy IndicatorBrakeReservoirReaderProxy IndicatorGaugeProxy IndicatorPortReaderProxy
IndicatorScalerProxy IndicatorSliderProxy InteractablePortFeederProxy InteriorNonStandardLayerProxy ItemLightProxy ItemUseRedirectProxy
ItemUseTargetProxy KeepCoupledInteriorLoaded LabelLocalizer LampLogicDefinitionProxy LayeredAudioPortReaderProxy
LayeredAudioProxy LeverProxy LightShadowQualityProxy LocoControlsReaderProxy LocoIndicatorReaderProxy
LocoResourceReceiverProxy MagicShovellingProxy ManualOilingPoint ManualOilingPointsDefinitionProxy
MaterialGrabberRenderer MechanicalLubricatorDefinitionProxy MouseScrollKeyboardInputProxy
MultiplePortDecoderEncoderDefinitionProxy MultiplePortSumDefinitionProxy NonPhysicsCoalTargetProxy
OverridableControlProxy ParticlesPortReadersControllerProxy PositionSyncProviderProxy PowerOffControlProxy
PoweredWheelProxy PoweredWheelRotationViaAnimationProxy PoweredWheelsManagerProxy PullerProxy
ReciprocatingSteamEngineDefinitionProxy ResourceContainerProxy ResourceMassPortReaderProxy ReverserDefinitionProxy
RigidCoupler SanderDefinitionProxy ShovelCoalPileProxy SimConnectionsDefinitionProxy SmoothedOutputDefinitionProxy
StaticInteractionAreaProxy SteamBellDefinitionProxy SteamCompressorDefinitionProxy SteamExhaustDefinitionProxy
SteamSmokeParticlePortReaderProxy TeleportHoverGlowProxy ToggleValueKeyboardInputProxy TractionDefinitionProxy
TractionPortFeedersProxy TunnelParticleDampeningProxy VanillaHUDLayout VehicleAOShadow VirtualHandbrakeOverrider
VolumetricLightBeamProxy WaterDetectorDefinitionProxy WaterDetectorPortFeederProxy WheelRotationViaAnimationProxy
WheelslipControllerProxy WheelslipSparksControllerProxy'''.split())


def unwrap(value):
    if isinstance(value, dict):
        if 'value' in value and 'unit' in value and 'basis' in value:
            return unwrap(value['value'])
        return {k: unwrap(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unwrap(v) for v in value]
    return value


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def ptr(value):
    return value.get('m_PathID', 0) if isinstance(value, dict) else 0


def near(a, b, tolerance=0.0001):
    return isinstance(a, (int, float)) and math.isfinite(a) and abs(a-b) <= tolerance


def load_bundle(bundle):
    from workspace import enable_unitypy
    enable_unitypy()
    import UnityPy
    env = UnityPy.load(str(bundle))
    objects = {o.path_id: o.read_typetree() for o in env.objects}
    kinds = {o.path_id: o.type.name for o in env.objects}
    return objects, kinds


class Snapshot:
    def __init__(self, objects, kinds):
        self.objects, self.kinds = objects, kinds
        self.scripts = {i:d for i,d in objects.items() if kinds[i] == 'MonoScript'}
        self.classes = collections.defaultdict(list)
        self.class_ids = collections.defaultdict(list)
        self.behaviour_class = {}
        for i,d in objects.items():
            if kinds[i] == 'MonoBehaviour':
                cls = self.scripts.get(ptr(d.get('m_Script')), {}).get('m_ClassName', 'MISSING_SCRIPT')
                self.classes[cls].append(d)
                self.class_ids[cls].append(i)
                self.behaviour_class[i] = cls
        self.transforms = {ptr(d['m_GameObject']):d for i,d in objects.items() if kinds[i] == 'Transform'}

    def name(self, component):
        return self.objects.get(ptr(component.get('m_GameObject')), {}).get('m_Name', '')

    def path(self, transform):
        result, seen = [], set()
        while transform:
            result.append(self.name(transform))
            parent = ptr(transform.get('m_Father'))
            if parent in seen:
                raise ValueError('Cyclic transform hierarchy')
            seen.add(parent)
            transform = self.objects.get(parent)
        return '/'.join(reversed(result))

    def world_position(self, transform):
        value=[0.,0.,0.];seen=set()
        while transform:
            p,q,scale=(transform[k] for k in ('m_LocalPosition','m_LocalRotation','m_LocalScale'))
            x,y,z=(value[i]*scale[a] for i,a in enumerate('xyz'))
            qx,qy,qz,qw=(q[a] for a in 'xyzw')
            tx,ty,tz=2*(qy*z-qz*y),2*(qz*x-qx*z),2*(qx*y-qy*x)
            value=[x+qw*tx+qy*tz-qz*ty+p['x'],y+qw*ty+qz*tx-qx*tz+p['y'],z+qw*tz+qx*ty-qy*tx+p['z']]
            parent=ptr(transform.get('m_Father'))
            if parent in seen: raise ValueError('Cyclic transform hierarchy')
            seen.add(parent);transform=self.objects.get(parent)
        return value


def warning_errors(report, result, dispositions):
    warnings = [line for line in report.splitlines() if line.startswith('WARN ')]
    errors = []
    if not isinstance(dispositions, list) or any(not isinstance(x,dict) or
            not x.get('line','').startswith('WARN ') or not str(x.get('reason','')).strip() for x in dispositions):
        errors.append('Warning dispositions require exact WARN lines and nonempty review reasons')
        expected = []
    else:
        expected = [x['line'] for x in dispositions]
    if warnings != expected:
        errors.append('Warnings differ from exact reviewed dispositions')
    if result.get('warnings') != len(warnings):
        errors.append('Warning counter mismatch')
    if 'EXCEPTION' in report or not result.get('exported'):
        errors.append('Build did not complete an exception-free export')
    return errors, warnings


def validate_snapshot(snapshot, record, gate, report, share=False):
    """Pure serialized checks; separately callable for mutation tests."""
    s = snapshot
    objects, kinds, classes = s.objects, s.kinds, s.classes
    raw = unwrap(record)
    cfg, hooks = raw['config'], raw.get('hooks', {})
    cid = cfg['CarId']
    errors, evidence = [], {}
    def check(ok, message):
        if not ok: errors.append(message)
    def one(cls):
        entries = classes[cls]
        check(len(entries) == 1, 'Expected exactly one ' + cls)
        return entries[0] if len(entries) == 1 else {}
    def valid_pointer(value, kind=None):
        ident = ptr(value)
        return ident in objects and (kind is None or kinds[ident] == kind)

    assemblies = sorted({d.get('m_AssemblyName','') for d in s.scripts.values()})
    check(bool(assemblies) and all(a in ('CCL.Types', 'CCL.Types.dll') for a in assemblies),
          'Bundle contains a script assembly outside the CCL.Types allowlist')
    check(not classes['MISSING_SCRIPT'], 'Bundle has unresolved MonoBehaviour scripts')
    unexpected=sorted(k for k,v in classes.items() if v and k not in ALLOWED_COMPONENTS)
    check(not unexpected, 'Unreviewed CCL component classes: '+str(unexpected))
    check(not cfg.get('Tender') and not cfg.get('IsTender'), 'First-build auditor supports one tank locomotive')
    types = classes['CustomCarType']
    check(len(types) == 1 and types[0].get('id') == cid, 'Expected exactly the reviewed single locomotive identity')
    cartype = types[0] if len(types) == 1 else {}
    check(cartype.get('IsSteamLocomotive') == 1 and cartype.get('KindSelection') == 2, 'Car must be a steam locomotive')
    check(near(cartype.get('wheelRadius'), cfg['WheelRadius']), 'Measured driver radius differs from record')
    check(near(cartype.get('mass'), cfg['WeightEmptyKg'], 0.1), 'Dry/base mass differs from reviewed ledger')
    check(cartype.get('GeneralLicense') == cfg.get('License'), 'Locomotive licence differs from record')
    check(cartype.get('brakes',{}).get('hasHandbrake') == 1, 'Tank locomotive needs its own handbrake')
    check(cartype.get('brakes',{}).get('hasCompressor') == 1, 'Tank locomotive needs compressor-enabled brakes')
    variant = one('CustomCarVariant')
    check(variant.get('id') == cid, 'Livery identity differs from locomotive')
    check(objects.get(ptr(variant.get('parentType')),{}).get('id') == cid, 'Livery parent type is invalid')
    for field in ('prefab','interiorPrefab','externalInteractablesPrefab'):
        check(valid_pointer(variant.get(field), 'GameObject'), 'Missing livery prefab: '+field)
    check(not variant.get('TrainsetLiveries'), 'Single tank must not spawn a tender trainset')
    check(not variant.get('HideFrontCoupler') and not variant.get('HideBackCoupler'), 'Both tank couplers must remain available')
    check(bool(variant.get('HideHookPlates'))==bool(cfg.get('HideHookPlates',True)),
          'Hook plate visibility differs from reviewed configuration')
    for cls in ('CarAutoCoupler','RigidCoupler','KeepCoupledInteriorLoaded','VirtualHandbrakeOverrider'):
        check(not classes[cls], 'Unexpected tender-only component '+cls)
    cab=one('CabTeleportDestinationProxy')
    if cfg.get('CabFloorProbeHeight') is not None:
        destination=objects.get(ptr(cab.get('roomscaleTeleportPosition')), {})
        check(bool(destination) and kinds.get(ptr(cab.get('roomscaleTeleportPosition')))=='Transform',
              'Missing roomscale cab teleport destination')
        if destination:
            height=s.world_position(destination)[1]
            check(0<height<cfg['CabFloorProbeHeight'], 'Cab teleport destination is outside the reviewed floor probe bounds')
    for name in ('[coupler_rig_front]','[coupler_rig_rear]','[car plate anchor1]','[car plate anchor2]'):
        matches = [t for t in s.transforms.values() if s.name(t) == name]
        check(len(matches) == 1, 'Expected unique '+name)
        if len(matches) == 1 and name.startswith('[car plate'):
            t=matches[0]; q=t['m_LocalRotation']; x=t['m_LocalPosition']['x']
            check(x*(1-2*(q['y']**2+q['z']**2)) > 0, 'Plate faces inward: '+s.path(t))
        if len(matches) == 1 and name.startswith('[coupler_rig'):
            t=matches[0]
            check(near(t['m_LocalPosition']['y'], cfg.get('CouplerHeight',1.05),0.002), 'Coupler height mismatch '+name)
    for direction in ('front','rear'):
        check(re.search(r'^\[coupler_rig_'+direction+r'\] at .*end beam z [-\d.]+ .*live coupler z [-\d.]+;', report,re.M),
              'Missing measured outer-coupler validation '+direction)
    check('final stock release:' in report or 'stock brake release:' in report,
          'Missing final brake-release fitting validation')
    check('stock handbrake:' in report,
          'Missing final handbrake fitting validation')

    sim = one('SimConnectionsDefinitionProxy')
    execution = sim.get('executionOrder',[])
    sim_objects = [objects.get(ptr(x),{}) for x in execution]
    ids=[x.get('ID') for x in sim_objects]
    check(bool(ids) and all(isinstance(x,str) and x for x in ids) and len(ids)==len(set(ids)), 'Missing/duplicate simulation execution IDs')
    by_id={d.get('ID'):d for d in sim_objects if d.get('ID')}
    check(gate.get('schema') == 1 and gate.get('carId') == cid, 'Missing/wrong pre-export CCL port-schema gate')
    port_entries=gate.get('components',[])
    check([d.get('id') for d in port_entries] == ids, 'Port schema does not match serialized simulation execution order')
    check(len(port_entries)==len(execution), 'Port-schema component count mismatch')
    ports, references=set(),set()
    for index,e in enumerate(port_entries):
        ident=e.get('id','')
        if index<len(execution):
            check(e.get('componentClass')==s.behaviour_class.get(ptr(execution[index])), 'Port schema class mismatch '+ident)
        ports.update(ident+'.'+p for p in e.get('ports',[]))
        references.update(ident+'.'+p for p in e.get('references',[]))
    for key in ('connections','portReferenceConnections'):
        stored=sim.get(key,[])
        try: imported=json.loads(sim.get(key+'Json',''))
        except (ValueError,TypeError): imported=None
        check(imported==stored, 'CCL AfterImport JSON differs from serialized '+key)
    for link in sim.get('connections',[]):
        for key in ('fullPortIdOut','fullPortIdIn'):
            check(link.get(key) in ports,'Missing connected port '+str(link.get(key)))
    links=sim.get('portReferenceConnections',[])
    check(len({x.get('portReferenceId') for x in links})==len(links), 'Duplicate port-reference assignments')
    route={x.get('portReferenceId'):x.get('portId') for x in links}
    for reference,port in route.items():
        check(reference in references, 'Missing reference endpoint '+str(reference))
        check(not port or port in ports, 'Missing referenced port '+str(port))
    for reference,port in {'boiler.WATER':'water.AMOUNT','boiler.WATER_CONSUMPTION':'water.CONSUME_EXT_IN',
                            'lubricator.OIL':'oil.AMOUNT','oilingPoints.OIL_STORAGE':'oil.AMOUNT',
                            'oilingPoints.OIL_CONSUMPTION':'oil.CONSUME_EXT_IN'}.items():
        check(route.get(reference)==port, 'Tank resource routing mismatch '+reference)
    check(not any(x.startswith('tender') for x in ids), 'Tank simulation contains tender resource proxies')
    resources={d.get('ID'):d for d in classes['ResourceContainerProxy']}
    for resource,expected in (('water',cfg['WaterCapacityL']),('coal',cfg['CoalCapacityKg'])):
        check(resource in resources and near(resources[resource].get('capacity'),expected,0.02), 'Resource capacity mismatch '+resource)
        check(resource in resources and 0<=resources[resource].get('defaultValue',-1)<=expected+0.02, 'Invalid spawn resource '+resource)
    for component,fields in hooks.get('SimSpec',{}).items():
        if component.startswith('_'):continue
        check(component in by_id, 'Reviewed simulation component missing '+component)
        for field,expected in fields.items():
            if field.startswith('_'): continue
            if isinstance(expected,(int,float)):
                # ApplySpec addresses the named simulation GameObject and finds
                # its MonoBehaviour declaring this field. Controllers such as
                # FireboxSimControllerProxy share that node with the execution
                # definition; they are not themselves execution-order entries.
                owner=ptr(by_id.get(component,{}).get('m_GameObject'))
                candidates=[]
                if owner:
                    for ident,data in objects.items():
                        if kinds[ident]!='MonoBehaviour' or ptr(data.get('m_GameObject'))!=owner: continue
                        actual=data
                        for part in field.split('.'):
                            if not isinstance(actual,dict) or part not in actual: break
                            actual=actual[part]
                        else:
                            candidates.append(actual)
                check(len(candidates)<=1, 'Ambiguous simulation setting '+component+'.'+field)
                check(len(candidates)==1 and near(candidates[0],expected,max(0.001,abs(expected)*0.00001)),
                      'Simulation setting mismatch '+component+'.'+field)
    mass_ports={d.get('resourceMassPortId') for d in classes['ResourceMassPortReaderProxy']}
    check('boiler.WATER_MASS' in mass_ports, 'Boiler water mass is not counted dynamically')
    controls=sorted({d.get('portId','') for d in classes['InteractablePortFeederProxy']})
    for toggle in cfg.get('AnimatedToggles',[]):
        name,port=toggle['Name'],toggle['Port']
        buttons=[b for b in classes['ButtonProxy'] if s.name(b)=='C_'+name]
        check(len(buttons)==1, 'Missing/duplicate animated toggle '+name)
        if len(buttons)==1:
            button=buttons[0];owner=ptr(button.get('m_GameObject'))
            check(bool(button.get('isToggle')) and not button.get('isTogglingBack') and
                  not button.get('createRigidbody') and not button.get('useJoints'),
                  'Animated toggle must follow the source clip without button physics '+name)
            feeders=[f for f in classes['InteractablePortFeederProxy'] if ptr(f.get('m_GameObject'))==owner]
            check(len(feeders)==1 and feeders[0].get('portId')==port, 'Animated toggle feeder mismatch '+name)
        readers=[r for r in classes['AnimatorPortReaderProxy'] if s.name(r)=='[anim] control follow '+name]
        check(len(readers)==1 and readers[0].get('portId')==port, 'Animated toggle source motion reader mismatch '+name)
    # Brake controls are provided by DV's brake subsystem, outside CCL executionOrder.
    runtime_control_ports={'brake.EXT_IN','indBrake.EXT_IN','handbrake.EXT_IN','brakeCutout.EXT_IN'}
    check(all(p in ports|runtime_control_ports for p in controls), 'Interactable feeder references missing port: '+str([p for p in controls if p not in ports|runtime_control_ports]))
    for p in ('throttle.EXT_IN','reverser.CONTROL_EXT_IN','brake.EXT_IN','indBrake.EXT_IN','whistle.EXT_IN'):
        check(p in controls,'Missing primary cab control '+p)
    for cls in ('AnimatorPortReaderProxy','IndicatorPortReaderProxy'):
        for d in classes[cls]:
            port=d.get('portId','')
            check(bool(port) and port in ports, cls+' references missing port '+port)
    reader=one('LocoControlsReaderProxy'); indicator=one('LocoIndicatorReaderProxy')
    for field in ('cabLight','headlightsFront','cylCock','injector','firedoor','blower','damper','blowdown','coalDump','lubricator','bell'):
        check(valid_pointer(reader.get(field)), 'Missing HUD control '+field)
    for field in ('speed','steam','chestPressure','brakePipe','mainReservoir','brakeCylinder','locoWaterLevel','locoCoalLevel'):
        check(valid_pointer(indicator.get(field)), 'Missing HUD indicator '+field)

    radius=cfg['WheelRadius']; wheel=one('PoweredWheelRotationViaAnimationProxy')
    check(near(wheel.get('wheelRadius'),radius), 'Powered animation radius mismatch')
    animators=[ptr(x.get('animator')) for x in wheel.get('animatorSetups',[])]
    check(bool(animators) and len(animators)==len(set(animators)) and all(kinds.get(i)=='Animator' for i in animators), 'Invalid/unregistered powered animator regions')
    check([ptr(x) for x in wheel.get('_animators',[])]==animators, 'Serialized animation setup/cache differ')
    # Pony wheelsets are unpowered; the engine units name the actual powered driver axles.
    expected_axles=sum(len(unit.get('DriverParts',[])) for unit in cfg.get('EngineUnits',[]))
    if not expected_axles: expected_axles=3
    managers=one('PoweredWheelsManagerProxy')
    check(len(managers.get('poweredWheels',[]))==expected_axles, 'Powered axle count differs from source layout')
    check(all(valid_pointer(x,'MonoBehaviour') for x in managers.get('poweredWheels',[])), 'Missing powered wheel references')
    check(near(by_id.get('poweredAxles',{}).get('value'),expected_axles), 'Simulation powered axle count mismatch')

    cups,providers=classes['ManualOilingPoint'],classes['PositionSyncProviderProxy']
    oil_tags = [a['Tag'] for a in cfg.get('OilAnchors',[])] if cfg.get('OilAnchors') else [s.name(s.transforms[ptr(c['m_GameObject'])]) for c in cups]
    # RodOilers produce stable MOP 1..N tags; explicit anchors carry their own order.
    if cfg.get('RodOilers'):oil_tags=['MOP '+str(i+1) for i in range(len(cups))]
    consumer_tags=[c.get('SyncTag') for c in cups]; provider_tags=[p.get('syncTag') for p in providers]
    count=len(cups); oil_def=one('ManualOilingPointsDefinitionProxy')
    check(count>0 and len(set(consumer_tags))==count, 'Missing/duplicate oil cup tags')
    check(sorted(consumer_tags)==sorted(provider_tags)==sorted(oil_tags), 'Oil provider/consumer tag correspondence mismatch')
    check(oil_def.get('OilingPointCount')==count and len(oil_def.get('oilingPoints',[]))==count, 'Oil simulation count differs from physical cups')
    expected_oil=raw.get('metadata',{}).get('expectedOilPoints')
    check(isinstance(expected_oil,int) and expected_oil>0 and count==expected_oil,'Oil point count differs from reviewed geometry')
    cup_by_go={ptr(c.get('m_GameObject')):c.get('SyncTag') for c in cups}
    parents={ptr(s.transforms[go].get('m_Father')) for go in cup_by_go if go in s.transforms}
    check(len(parents)==1,'Oil cups do not share one save-index hierarchy')
    oil_order=[]
    if len(parents)==1:
        for child in objects[next(iter(parents))].get('m_Children',[]):
            go=ptr(objects.get(ptr(child),{}).get('m_GameObject'))
            if go in cup_by_go:oil_order.append(cup_by_go[go])
        check(oil_order==oil_tags,'Oil save-index order differs from configured tag order')
    for p in providers:
        tr=s.transforms.get(ptr(p.get('m_GameObject')),{}); parent=objects.get(ptr(tr.get('m_Father')),{}); go=objects.get(ptr(parent.get('m_GameObject')), {})
        check(any(kinds.get(ptr(c.get('component'))) in ('MeshFilter','SkinnedMeshRenderer') for c in go.get('m_Component',[])), 'Oil provider is not parented to source rod geometry')
    if cfg.get('RodOilers') or cfg.get('OilAnchors'):
        check(f'oil phase validation: {count} animated rod providers, four phases, source seat proximity passed' in report, 'Missing four-phase moving-oil validation')
    audio=[d.get('m_Name','') for i,d in objects.items() if kinds[i]=='AudioClip']
    if share:check(not audio,'Share bundle contains AudioClips')
    evidence.update(script_assemblies=assemblies,control_ports=controls,sim_ids=ids,resource_routes=route,
                    base_mass_kg=cartype.get('mass'),wheel_radius_m=cartype.get('wheelRadius'),oil_tags=sorted(consumer_tags),
                    oil_save_order=oil_order,audio_clips=audio,share_audio_pass=not audio,expected_axles=expected_axles)
    return errors,evidence


def audit(profile, run, share=False):
    from workspace import ROOT,WORKSPACE,CONFIG,profile_path
    run=Path(run).resolve(); settings=CONFIG['profiles'][profile]; profile_dir=profile_path(profile,'profile')
    record_candidates=[p for p in profile_dir.glob('*.json') if isinstance((j:=read_json(p)),dict) and j.get('schemaVersion')==1 and 'config' in j]
    if len(record_candidates)!=1:raise ValueError('Expected one reviewed runtime JSON record in '+str(profile_dir))
    record_path=record_candidates[0];record=read_json(record_path); cfg=unwrap(record)['config']
    bundle=run/settings['pack']/'ccl_bundle'; report=(run/'build_report.txt').read_text(encoding='utf-8-sig')
    disposition_path=profile_dir/'warning_dispositions.json'
    dispositions=read_json(disposition_path) if disposition_path.exists() else []
    errors,warnings=warning_errors(report,read_json(run/'result.json'),dispositions)
    info=read_json(bundle.parent/'Info.json')
    if info.get('Id')!=cfg['CarId'] or not set(cfg.get('Requirements',['DVCustomCarLoader'])).issubset(info.get('Requirements',[])):
        errors.append('Pack identity/dependency metadata differs from reviewed record')
    objects,kinds=load_bundle(bundle)
    failures,evidence=validate_snapshot(Snapshot(objects,kinds),record,read_json(run/'sim_ports.json'),report,share)
    errors.extend(failures)
    from audit_source_closure import source_closure
    source_spec=read_json(profile_dir/(profile+'.json'))
    closure=source_closure(profile_path(profile,'project'),WORKSPACE/CONFIG['sourceCatalog'],source_spec,cfg)
    (run/'source_closure.json').write_text(json.dumps(closure,indent=2)+'\n',encoding='utf-8')
    errors.extend(closure['errors'])
    hashes=read_json(run/'source_hashes.json')
    expected=list((ROOT/'tools/unity').glob('*.cs'))+list(profile_dir.glob('*.cs'))+list(profile_dir.glob('*.json'))
    expected += [p for p in (profile_dir/'assets').rglob('*') if p.is_file()]
    expected += [ROOT/'catalog'/(settings['catalogId']+'.json'),ROOT/'overrides'/(settings['catalogId']+'.json')]
    expected_keys={p.relative_to(WORKSPACE).as_posix() for p in expected}
    normalized={str(k).replace('\\','/'):v for k,v in hashes.items()}
    if set(normalized)!=expected_keys:errors.append('Source manifest coverage mismatch')
    drift=[p for p,digest in normalized.items() if p not in expected_keys or not (WORKSPACE/p).is_file() or sha(WORKSPACE/p)!=digest]
    if drift:errors.append('Source changed since export: '+str(drift))
    process=read_json(run/'process_result.json') if (run/'process_result.json').exists() else {}
    if process.get('exit_code')!=0:errors.append('Unity process did not report successful completion')
    output=dict(schema=1,audit_kind='new_locomotive',status='failed' if errors else 'passed',profile=profile,
                errors=errors,reference='',warnings=warnings,warning_dispositions=dispositions,
                bundle_sha256=sha(bundle),bundle_bytes=bundle.stat().st_size,
                source_manifest_sha256=sha(run/'source_hashes.json'),runtime_record_sha256=sha(record_path),
                runtime_validated=False,limitations=['No in-game driving, interaction, save/reload or VR acceptance is implied by serialized checks.'],**evidence)
    (run/'bundle_audit.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:output[k] for k in ('status','profile','errors','bundle_sha256','base_mass_kg')},indent=2))
    return not errors


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('profile');p.add_argument('run',type=Path);p.add_argument('--share',action='store_true');a=p.parse_args()
    sys.exit(0 if audit(a.profile,a.run,a.share) else 1)
