"""Record source-grounded implementation settings; does not invent cab geometry."""
from pilots import ROOT, PILOTS, read_json, write_json

PORTS = {
    'Throttle': ('throttle.EXT_IN', 0),
    'Reverser': ('reverser.CONTROL_EXT_IN', 1),
    'LocomotiveBrake': ('indBrake.EXT_IN', 3),
    'TrainBrake': ('brake.EXT_IN', 2),
    'Whistle': ('whistle.EXT_IN', 14),
}

for pilot in PILOTS:
    manifest = read_json(ROOT / 'config' / f'{pilot}.json')
    specifications = []
    for obj in manifest['source_objects']:
        definition = obj['definition']
        components = definition.get('components', [])
        wheels = []
        for wheelset in definition.get('wheelsets', []):
            clip = wheelset['animation']['clipName']
            role = 'powered' if clip == 'Drivers' else 'unpowered' if clip in ('Pilot', 'Trailing') else 'auxiliary_animation'
            wheels.append({'role': role, 'source': wheelset,
                           'nominal_radius_m': wheelset['diameter'] / 2 if role != 'auxiliary_animation' else None,
                           'measured_radius_m': None})
        controls = []
        for comp in components:
            if comp['kind'] == 'RadialControl':
                target = PORTS.get(comp.get('purpose'))
                controls.append({'source_name': comp['name'], 'source_purpose': comp.get('purpose'),
                    'source_parent': comp.get('parent'), 'source_animation': comp.get('animation'),
                    'target_port': target[0] if target else None, 'target_control_id': target[1] if target else None,
                    'grip_and_joint_validation': 'pending Unity measurements and in-game test'})
        capacities = {}
        for slot in definition.get('loadSlots', []):
            factor = {'Gallons': 3.785411784, 'Pounds': 0.45359237}[slot['loadUnits']]
            capacities[slot['requiredLoadIdentifier']] = {
                'source_value': slot['maximumCapacity'], 'source_unit': slot['loadUnits'],
                'dv_value': slot['maximumCapacity'] * factor,
                'dv_unit': 'litres' if slot['loadUnits'] == 'Gallons' else 'kg'}
        specifications.append({
            'id': obj['identifier'], 'kind': definition['kind'],
            'proposed_dv_id': 'LLW_C21_Tender' if obj['identifier'].startswith('lt-') else 'LLW_' + pilot.upper(),
            'simulation_basis': 'TenderSimCreator' if definition['kind'] == 'Car' else
                                'S282 separate tender' if definition.get('tenderIdentifier') else 'S060 onboard resources',
            'source_mass_lb': definition['weightEmpty'],
            'source_mass_converted_kg': definition['weightEmpty'] * 0.45359237,
            'dv_dry_mass_kg': None,
            'mass_review': 'Confirm whether source mass includes operating water before assigning DV dry mass.',
            'source_cylinders_inches': [definition.get('pistonDiameterInches'), definition.get('pistonStrokeInches')],
            'source_boiler_pressure_psig': definition.get('maximumBoilerPressure'),
            'capacities': capacities, 'wheelsets': wheels, 'controls': controls,
            'source_anchors': [c for c in components if c['kind'] in ('Seat','Gauge','PrefabControl','Chuff','CylinderCock','LoadTarget')],
            'source_option_groups': [c for c in components if c['kind'] == 'ComponentGroup'],
            'source_liveries': [c for c in components if c['kind'] == 'DefaultLivelryComponent'],
            'pending_measurements': ['tread radii and axle locations', 'coupling planes and collision boxes',
                'cab floor/teleport volume', 'control axes, grips and gauge readability',
                'boiler volume and DV steam-flow calibration'] if definition['kind'] != 'Car' else
                ['tender coupling planes/collision', 'Fox truck placement and tread radius', 'coal and water loading interaction'],
        })
    write_json(ROOT / 'config' / f'{pilot}-integration.json', {
        'stage': 'source-derived integration specification; not a finished LocoConfig',
        'vehicles': specifications, 'external_fidelity_references': manifest['external_fidelity_references']})
    print(pilot + ': integration specification written')
