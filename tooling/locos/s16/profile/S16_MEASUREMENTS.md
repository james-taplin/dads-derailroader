# S16 measured conversion profile

This profile converts LLW `ls-060-s16` as a single 0-6-0 tank locomotive, with S060 simulation and onboard coal/water. It is a personal-use conversion of supplied Railroader assets. The profile JSON is authoritative; this note explains choices and does not certify in-game acceptance.

## Fixed source and appearance

- Car ID `LLW_S16`, pack/name `LLW S16`, version `0.1.0` pre-release; `Lined` livery.
- Small Electric Headlight, Shotgun Stack and ladder parts selected from S16 pack. No tender, pony truck or plow.
- Driver clip and valve gear, brakes, whistle linkage, regulator linkage, bell/pump loops, both fire-door mechanisms, two cab doors, six windows, roof vent, both tank hatches and water/coal level clips retained.
- Exact `wh-1-reading` audio plus source bell, compressor and generator in the personal build. Share-mode loader strips imported audio and retains stock DV replacements.

## Measurements and physics

`analysis/measure01/measure_report.txt` records material/island bounds, parent component transforms, control endpoints and floor/backhead rays. `analysis/wheel-measure01/wheel_details.txt` separates the constant tread band from the flange.

- Wheel tread radius **0.488783 m**, constant across tyre x=0.726..0.801 m; source nominal radius is 0.49 m. Wheel flange is larger and is not used for motion.
- Physical axles at z=1.22865, -0.00004, -1.15851 m. Front/rear DV pivots use the outer drivers; all three axles are powered.
- Boiler body material envelope diameter1.26843 m and effective length3.89015 m. Internal steam/water volume4000 L and 76% initial fill remain an engineering estimate; the outer jacket envelope alone does not prove internal tube/firebox displacement.
- Source cylinders14 x22 in, pressure165 psig, heating surface876 ft²; source fallback TE approximately15674 lbf. Effective DV cylinder bore is calculated from the source TE target, source stroke and measured wheel radius.
- Source pressure conversion gives12.389604 bar absolute opening pressure and12.182761 bar absolute reseat pressure (3psi hysteresis).
- Firebed33 kg and maximum firing approximately0.212 kg/s scale the documented G29 estimate by source heating surface876/1735. This remains an estimate requiring driving feedback.

## Explicit mass ledger

Source `weightEmpty=80000 lb` converts to36287.3896 kg. Historical dry weight is not supplied. The deliberate DV interpretation treats that figure as an operating locomotive with its boiler water but without separately counted Railroader load-slot coal/water. It is an assumption, not a proven historic specification.

At explicitly configured1 bar absolute spawn pressure, installed DV SteamTables gives specific volume1.049301 L/kg. Initial boiler water3040 L therefore weighs2897.166780552 kg. Profile base dry mass is **33390.222819448 kg**, so base plus boiler water recovers the source mass exactly. The onboard water tank3785.411784 L and coal bunker907.18474 kg are separate resources. Firebox coal, sand and lubricating oil also remain additional DV masses; their source inclusion is unknown. This uses the corrected E04 density formula and does not modify G29/C21.

## Cab and source fittings

Measured floor is y=1.03924 m on the centre strip and 1.05718 m either side. Cab teleport is within the rear cab aisle at z=-2.65 m. `CabFloorProbeHeight=2.2 m` starts the downward floor ray below the roof: test05 confirms the resulting teleport y=1.039 m. The former generic 3.5 m start hit the S16 roof at y=3.430 m. The boiler backhead face is z=-2.09076 m; fire door centre is approximately (0.0159, 1.4742, -2.1318) m.

Six authored592-triangle valve-wheel islands become injector, blower, air-pump, dynamo, sander and blowdown controls. Remaining DV service functions use generated controls on measured backhead space. Grip boxes are interaction design choices derived from handholds, not source dimensions.

The existing core weld tolerance of0.0001 mesh-local units becomes10 mm on the100x source model and incorrectly joins thin wheel rings to nearby pipework. S16 opts into a0.0000001 local-unit weld for mesh `Cylinder.018` only, reproducing the10 µm world measurement. Other profiles retain the original tolerance.

The source `Bell2` valve makes a full360° rotation, so its start/end quaternions are identical. The port-driving bell valve uses the original mesh with an explicit90° saved two-state joint; the external bell still swings with `Bell1`.

Nested fire-door animation order is child `FBD2` before parent `FBD`; reversing it makes the parent regroup move the child's source path before it can be found.

The tank hatches use `AnimatedToggles`, matching the source interactions' explicit “Click to Open” / “Click to Close” messages. Each grip follows the full authored position and rotation tracks. The original left hatch travels considerably down and forward, while the right hatch moves mostly sideways with only 4 degrees of rotation; raw bundle inspection confirms these asymmetric tracks are original source data. A fixed-axis rotary joint could not follow them. Test05 retains both source clips and uses button toggles without changing the animation.

Brake hangers use the actual rotating nodes and bones; the two sliding links (`Main/Empty.041` and `.042`) use brake-cylinder-driven sliders. Compressor and lubricator linkage loops are retained separately.

## Coupling hardware and exposed grips

Twenty-eight reviewed islands in the merged `Cylinder.018` mesh are removed: the obsolete Railroader uncoupling bars and their supports, central drawgear housings, and housing fasteners. The 2,744 removed triangles are selected by unique world centre, bounds size and triangle count, with a 1 mm matching tolerance. Wooden beams, footboards, footboard brackets and the cab shell remain intact. `coupler_island_review.json` and `.png` document the exact selection; independent decoding of the source mesh verifies every selector.

The actual stock hook plates remain visible (`HideHookPlates=false`). The stock plate at its source scale spans x=±0.308676 m and y=0.850604..1.092568 m. Its back is approximately 23 mm inside the measured beam after CCL's native placement; its lower 90 mm overlaps the front wooden beam vertically and 123 mm overlaps the rear beam. These stock plates support the replacement hook without inventing a new housing. Front and rear coupling rigs retain the standard 1.05 m height and native beam-to-rig distance of 0.309 m.

Test05 reports three conservative mesh-box warnings: front cock valve, rear hook, and rear cock valve. The front valve warning is a bounding-box overlap with a footboard bracket; the actual valve mesh is clear. The rear hook and valve meshes partially meet the sloping lower cab panel. The user explicitly accepted coupling mesh overlaps provided the grabbable colliders are exposed, so no speculative rig or hose shifts were made.

`analysis/coupler-review/stock_grab_access.json` measures the installed stock trigger colliders through their complete prefab transforms at the unchanged test05 rig positions. The cock and screw buttons each have 54/54 unobstructed centre/corner rays at both ends, using six standing and crouched approaches. Both hook snap spheres have 42/42 unobstructed samples. The actual parked chain grab knobs and initial free-hose connector grips each have 36/42 clear sphere samples at both ends; their inboard samples meet the beam, while their exposed faces and centres are available. **All ten targets have clear centre rays from all six approaches.**

The cock trigger centres are approximately (-0.3981, 0.9955, 3.4619) m at the front and (0.3981, 0.9955, -3.7165) m at the rear. Chain knobs use the installed 0.23 m trigger radius and hose connector grips use the installed 0.112 m radius. The parked chain and initial hose poses follow independently inspected runtime placement code. The test checks retained source body triangles and supports the stated exposure acceptance; settled hose physics and an actual game interaction check are separate from this geometric proof.

## Oiling and validation

Eight source tall oilers were reviewed in the preserved source mount sheet: three side-rod crank points plus one main-rod big end per side. The final build selects **six functional cups**: both connecting rods set `skipFront=true`, while their rear and middle cups and both main-rod cups remain functional. The two forward side-rod oilers retain their original cosmetic geometry. Tags are generated for the selected six and `OilingPointCount` derives from that same selected set. Stock per-point rates are retained, so aggregate demand matches the stock six-point workload.

The corrected test04c screen baked geometry into world scale before creating collision probes. All eight candidate cups and their actual 90-degree lids cleared source and neighbouring geometry at 32 crank phases across three reverser settings. The forward candidates were accessible in only 36/96 visibility samples, while the retained six achieved 90..96/96. Omitting the forward candidates is therefore a service-access decision, not a collision fix. The rebuilt six-point arrangement receives its own final screen; the prior test04b hierarchy-scaled collider results were invalid and are not used as evidence.

Source survey geometry does not establish in-game nozzle reach. The actual built providers, full body/tank geometry, cup/lid geometry and multiple crank/reverser phases are checked separately; manual driving and oiler interaction still require the game.
