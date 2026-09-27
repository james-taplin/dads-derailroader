# Pre-build review and geometry corrections

Implemented 2026-09-27. These are build candidates, not completed in-game acceptance.

## Vehicle review

The GUI pauses after source scanning and geometry probing, before the CCL build. The CLI offers the same choices
interactively, or takes `--review-file prebuild-review.json`. Without an input stream it stops with a readable
request and preserves `review-questions.json`. Cancellation does not build or install a pack.

The review contains train-brake behaviour, spawning, physical driving-wheel **radius in metres**, cylinder count,
steam thermal regime and simulation profile. The source tab shows the definition and measured tyre candidates.
The train-brake choice is required; the text “Train Brake” on a handle is not valve evidence. An explicit supported
source `brakeValveType` can prefill the choice, with source provenance after confirmation. Independent and handbrakes
remain separate.

Answers are saved per vehicle, with a source fingerprint, schema/adapter version, track-catalogue hash and field
provenance. Load the saved review on a rerun; a different source, catalogue or adapter is rejected. The rebuild receipt
retains these answers plus source/code/tool identities. There is no random conversion seed: identical recipes are
identifiable, but byte-identical Unity bundles have not been demonstrated. Changes affecting review semantics must
bump `ADAPTER_VERSION`.

## Brakes and spawning

The editor adapter writes both `CustomCarType.brakes.brakeValveType` and the custom HUD brake preset. Existing cab,
keyboard and HUD readers feed the same train-brake simulation input. The bundle audit compares actual valve type,
HUD type and emitted track pool with the record. Both valve types still need cab/keyboard/HUD hold/apply/release
testing in game; serialization checks do not establish control feel or lapping behaviour.

Radio only emits no normal locomotive spawn groups. Coupled tender trainset metadata is retained; radio availability
still depends on game settings. Manual selection lists suitable named tracks. Automatic supplies all suitable tracks
as a pool; conversion does not randomly select one location.

The catalogue is derived from CCL 3.1.9's public `LocoSpawnGroup` enum and length/restriction annotations, with its
source commit recorded. All explicitly reserved or stock-exclusive tracks are excluded conservatively. Required
length is source car-end lengths plus 1 m per coupling and 2 m total clearance. These allowances are explicit DV
choices. Unknown lengths cannot silently produce a normal spawn pool. The same output adapter serves tank and
tender engines.

## Steam profile boundaries

`metadata.sourceSpecs` preserves physical source specifications; `metadata.simulationProfile` preserves the selected
adapter, derivation, assumptions, calibration targets and empty results until measurements are available.

| Profile or capability | Current state |
| --- | --- |
| Legacy equivalent | Existing starting-pull target, equivalent bore recomputed for the selected cylinder count |
| Conventional simple | Source bore and stroke with explicitly reviewed 2, 3 or 4 cylinders; uncalibrated |
| Saturated / superheated | Boiler / firebox intake-temperature references following the CCL creator wiring; uncalibrated |
| Fixed geared steam | CCL-only prototype: engine RPM = wheel RPM × ratio; wheel torque = engine torque × ratio × efficiency; engine intake flow still supplies steam demand |
| Compound/simple switching | Pending feasibility and coupled demand/torque implementation; no torque-only “compound” mode |
| Simple articulated | Geometry/runtime acceptance and calibration pending |
| Oil-fired regime combinations | Pending; dynamic brake is reserved for firing, Gearbox A for atomizer, Gearbox B for a future simpling control |
| Diesel mechanical / hydraulic / electric | Separate adapters pending; no generic steam-to-diesel toggle |

Geared review requires a ratio, its evidence or explicit assumption, efficiency, and physical powered wheelset
indices and any unpowered physical indices. All other indices are treated as non-physical placeholders/shafts. Animation shafts must not be counted as wheel axles even if Railroader calls one the main driver. Existing
Source truck paths can associate several physical wheelsets with one shared clip. Exact measured axle counts are required; differing model/simulation positions are recorded in `metadata.physicalAxles`.
`WheelClips` carries accessory/shaft motion at its source effective radius. Models whose physical wheels cannot be
identified or animated by the current probe stop with a geometry block. Shaft phase, slip and speed remain in-game
checks; a valid CCL simulation graph does not prove a particular geared vehicle's visual conversion.

Calibration targets are starting pull, adhesion, sustained pull at several speeds, steam/water consumption and fuel
consumption. No numeric target or test result is invented when evidence is missing. Later adapters remain explicit
pending work under the [staged roadmap](feature-roadmap.md).

## Wheel support and oil cups

The driving-wheel field remains a **radius**. A high-confidence powered-wheel tread now checks the entered value
within max(10 mm, 3%). A leading/trailing/tender radius or an accidentally doubled value produces a review block.
Geared profiles use the reviewed physical wheelset indices for this comparison.

The A18 test record used the correct 0.79438 m driver radius. Its generated support colliders retained donor-local
centres at z = ±7.3 m after their objects moved. The correction clears those inherited centres, aligns support
capsules with the end axles and uses each end wheel's appropriate radius. On the A18 fixture, the front capsule is
now centred at (0, 0.35, 5.4699), and the rear at (0, 0.79438, −0.9859). Both bottoms meet the rail plane. The same
rule also corrects tender capsules. This is a confirmed generated-prefab defect; removal of the in-game pitch still
needs a fresh build/spawn test.

The old fallback already generated four A18 oil points, confirmed by its build and runtime logs. Their estimated
y = 1.63876 m position could hide them inside geometry. The fallback now requires two cups per driving axle and
measures accessible horizontal seats with room for the whole cup footprint. It keeps matching simulation/provider/
consumer tags. All four A18 points found actual running-board surfaces, with cup pivots near y = 2.04742 m.
Existing explicit moving-rod anchors remain supported. Failure to find a safe fallback seat stops the build instead
of exporting hidden cups. The search is a geometric approximation, with placement evidence in the build report.

## Evidence and remaining checks

- Real Unity 2019.4.40f1: geared RPM/torque graph and saturated temperature reference survived prefab save/reload.
- Real Unity: support capsules and all four A18 running-board seats checked on disposable generated geometry.
- Real A18 export: self-lapping + radio-only build passed the exported-bundle audit, zero source audio, CCL.Types only.
- Installed Climax: scan/probe/review completed; diagnostic record identifies six physical driving axles under the shared Drivers clip, with Crankshaft and Driveshaft retained separately. Diagnostic gearing values were assumptions, not source claims. No Climax pack was installed.
- Python tests cover source-bound review replay, cancellation, track pools/lengths/restrictions, geared wheel roles,
  brake ambiguity and existing conversion flows. CLI EOF produces a recoverable review request.
- Existing A18 cab/reverser sweep and material warnings remain visible. No in-game driving or physics acceptance is claimed.

Next game tests: spawn a fresh A18 and inspect body pitch, all tyres, four accessible oil cups and source animations;
test both brake valve types through cab/HUD/keyboard; test each spawn mode with tank and coupled tender examples;
then test a geared example at low speed, wheelslip and sustained load. Record measured results against the profile.

Temporary extraction and build folders continue to be permanently deleted through the owned-workspace cleanup path.
Small review/vehicle/rebuild receipts survive cleanup. Developer validation outputs are not installed automatically.
