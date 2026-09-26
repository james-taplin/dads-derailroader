"""Inspect the exported C21 bundle, not just editor build success. Requires UnityPy."""
import collections
import hashlib
import json
from pathlib import Path
import re
import sys
import UnityPy

run = Path(sys.argv[1]).resolve()
pack = run / 'LLW C-21'
bundle = pack / 'ccl_bundle'
errors = []
def check(value, message):
    if not value:
        errors.append(message)

result = json.loads((run / 'result.json').read_text())
report = (run / 'build_report.txt').read_text()
warnings = [line for line in report.splitlines() if line.startswith('WARN ')]
check(result['exported'], 'Build did not export')
check(result['warnings'] == len(warnings), 'Build warning count disagrees with report')
info = json.loads((pack / 'Info.json').read_text())
check(info['Id'] == 'LLW_C21' and 'DVCustomCarLoader' in info['Requirements'], 'Mod metadata/dependency mismatch')
if info['Version'] == '0.1.3':
    # The source models' decorative knuckle heads overlap the stock DV hook/
    # chain visual boxes. Keep all eight warnings visible and reject any new kind.
    check(len(warnings) == 8 and all(re.match(r'^WARN \[coupler_rig_(front|rear)\] (hook|screw chain|cock valve|air hose):', w) for w in warnings),
          'Unexpected warning in coupler build: ' + str(warnings))
    for rig, beam, live in [('front', 5.189, 5.747), ('rear', -2.917, -3.475)]:
        match = re.search(r'^\[coupler_rig_' + rig + r'\] at .*?: end beam z ([-\d.]+) .*?live coupler z ([-\d.]+);', report, re.M)
        check(match is not None and abs(float(match[1]) - beam) < .015 and abs(float(match[2]) - live) < .015,
              f'{rig} live coupler is not on the measured end beam')
    check('tender placed at z -7.445' in report, 'RR loco-tender spacing changed')
else:
    check(not warnings, 'Unreviewed build warnings: ' + str(warnings))
env = UnityPy.load(str(bundle))
objects = {o.path_id: o for o in env.objects}
scripts = {o.path_id: o.read_typetree() for o in env.objects if o.type.name == 'MonoScript'}
assemblies = sorted(set(d['m_AssemblyName'] for d in scripts.values()))
check(all(a in ('CCL.Types.dll', 'CCL.Types') for a in assemblies), 'Unexpected script assemblies: ' + str(assemblies))
by_class = collections.defaultdict(list)
for o in env.objects:
    if o.type.name != 'MonoBehaviour':
        continue
    d = o.read_typetree()
    script = scripts.get(d['m_Script']['m_PathID'])
    check(script is not None, 'Missing script for behaviour ' + str(o.path_id))
    if script:
        by_class[script['m_ClassName']].append(d)

types = {d['id']: d for d in by_class['CustomCarType']}
check(set(types) == {'LLW_C21', 'LLW_C21_Tender'}, 'Expected one locomotive and one tender type')
check(abs(types['LLW_C21']['wheelRadius'] - 0.545) < 0.001, 'Driver radius mismatch')
check(types['LLW_C21']['GeneralLicense'] == 'SH282', 'Invalid locomotive license')
variants = {d['id']: d for d in by_class['CustomCarVariant']}
check(variants['LLW_C21']['TrainsetLiveries'] == ['LLW_C21', 'LLW_C21_Tender'], 'Locomotive does not spawn as paired trainset')
check(len(by_class['CarAutoCoupler']) == 1 and len(by_class['RigidCoupler']) == 1, 'Tender coupling components absent')
check(len(by_class['KeepCoupledInteriorLoaded']) == 1, 'Tender does not keep locomotive interior loaded')
check(len(by_class['CabTeleportDestinationProxy']) == 1, 'Cab teleport destination absent')

sim_counts = []
for sim in by_class['SimConnectionsDefinitionProxy']:
    refs = sim['executionOrder']
    ids = []
    for ref in refs:
        obj = objects.get(ref['m_PathID'])
        check(obj is not None, 'Missing simulation execution entry')
        if obj:
            d = obj.read_typetree()
            ids.append(d.get('ID'))
    check(None not in ids and len(ids) == len(set(ids)), 'Duplicate/null simulation IDs')
    sim_counts.append(len(ids))
check(len(sim_counts) == 2, 'Expected locomotive and tender simulations')

reader = by_class['LocoControlsReaderProxy'][0]
for field in ('cabLight', 'headlightsFront', 'cylCock', 'injector', 'firedoor', 'blower', 'damper', 'blowdown', 'coalDump', 'lubricator', 'bell'):
    check(reader.get(field, {}).get('m_PathID', 0) != 0, 'HUD control missing: ' + field)
indicator = by_class['LocoIndicatorReaderProxy'][0]
for field in ('speed', 'steam', 'chestPressure', 'brakePipe', 'mainReservoir', 'brakeCylinder', 'locoWaterLevel', 'locoCoalLevel', 'tenderWaterLevel', 'tenderCoalLevel'):
    check(indicator.get(field, {}).get('m_PathID', 0) != 0, 'HUD indicator missing: ' + field)
firebox_indicator = objects[indicator['locoCoalLevel']['m_PathID']].read_typetree()
check(abs(firebox_indicator['maxValue'] - 100) < 0.01, 'Firebox indicator capacity differs from configured 100 kg')
feeders = by_class['InteractablePortFeederProxy']
ports = sorted(set(d.get('portId', '') for d in feeders))
for port in ('throttle.EXT_IN','reverser.CONTROL_EXT_IN','brake.EXT_IN','indBrake.EXT_IN','whistle.EXT_IN'):
    check(port in ports, 'Core driving control missing: ' + port)

audit = dict(status='passed' if not errors else 'failed', errors=errors,
    bundle_sha256=hashlib.sha256(bundle.read_bytes()).hexdigest(), bundle_bytes=bundle.stat().st_size,
    script_assemblies=assemblies, car_types=sorted(types), simulation_component_counts=sim_counts,
    control_ports=ports, runtime_validated=False,
    build_warnings=warnings,
    limitations=['Actual game spawn/driving/braking/save-reload not exercised by this static bundle audit'])
(run / 'bundle_audit.json').write_text(json.dumps(audit, indent=2))
print(json.dumps(audit, indent=2))
sys.exit(bool(errors))
