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
| Simple articulated | Geometry/runtime acceptance and calibration pending |

Geared review requires a ratio, its evidence or explicit assumption, efficiency, and physical powered wheelset
indices and any unpowered physical indices. All other indices are treated as non-physical placeholders/shafts. Animation shafts must not be counted as wheel axles even if Railroader calls one the main driver. Existing
Source truck paths can associate several physical wheelsets with one shared clip. Exact measured axle counts are required; differing model/simulation positions are recorded in `metadata.physicalAxles`.
`WheelClips` carries accessory/shaft motion at its source effective radius. Models whose physical wheels cannot be
identified or animated by the current probe stop with a geometry block. Shaft phase, slip and speed remain in-game
checks; a valid CCL simulation graph does not prove a particular geared vehicle's visual conversion.

Calibration targets are starting pull, adhesion, sustained pull at several speeds, steam/water consumption and fuel
consumption. No numeric target or test result is invented when evidence is missing. Keep unverified calibration
explicit in the vehicle record and validation notes.

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

Current stock builds use the [2026-10-02 fleet fittings](oil-cup-fleet-pass-2026-10-02.md): a supported travelling pair per driven axle, six to twelve total, with 64-phase bearing contact/clearance/spacing checks. Source fingerprints and explicit per-loco parents/local anchors are recorded in the master table. Missing supports or quota failures stop the build. Visual seating, lids and oil-can reach still need game acceptance.

The following describes the historical A18 regression before that fleet policy. The old fallback generated four A18 oil points at an estimated y = 1.63876 m, where they could hide inside geometry.
The generic builder then looked for compact, upward-facing big-end nub geometry on modelled main, side and connecting
rods first. Left and right nubs define a pair; each provider is parented to its moving rod. A missing or inaccessible
nub uses an accessible running-board seat with room for the whole cup footprint. If either side still has no seat,
the builder omits both cups in that pair and reduces the simulation, provider and interactable counts together.
When no rod nubs are detected, the provisional one-pair-per-driving-axle hints are tried on the running boards.
Existing explicit moving-rod anchors remain supported. The placement and access checks sample one model pose;
moving-clearance and in-game reach still need validation. The build report records the chosen seats and omitted pairs.
The earlier A18 board measurement placed four cups near y = 2.04742 m.

## Evidence and remaining checks

### Automatic end-beam measurement

The builder first tries its existing coupler-height band. If that band has insufficient or split hits,
it searches from 0.20 m up to coupler height for an upright transverse face. The search requires at
least 20 near-coplanar hits and multiple rows with support on both outer sides; a central opening or
drawgear obstruction is allowed. It selects the outermost qualifying face, so a broad truck crossmember
behind the beam does not win by having more hits. Where source car-end coordinates exist, measurements
must lie within 0.35 m of them. Those coordinates constrain the search; they never replace a measurement.
Tank walls above coupler height, narrow fittings and horizontal decks cannot qualify. Sliding depth
windows avoid splitting one face at a rounding-bin boundary. An explicit reviewed band remains binding.
No suitable face still produces a geometry-review block, and the build report records the selected band,
support count, mesh names and source-end difference. No vehicle-specific offsets or names are used.

Validation on 2026-09-27: a complete C-70 conversion using the failed run's saved pre-build choices and
no geometry override exported and passed the bundle audit. It measured +5.038 m front and −8.370 m rear,
24 supporting rays each, matching the earlier independent manual survey. Twelve real Unity assertions
cover both ends, central obstruction, a broad truck behind the beam, high tank walls, repeated measurement,
explicit override failure, missing/narrow geometry, source-end mismatch and depth-bin splitting. The
affected Python project/build/API suites ran 42 tests successfully, with one optional Mono-compiler test
skipped. Validation did not install a pack, and its temporary conversion workspace was permanently deleted.

Coupler overlap with decorative pipework and other small details is acceptable. Whole-assembly visual
clearance warnings are advisory, not build failures. The gameplay requirement is reachability of the
stopcock, hook and hanging hose end; that still needs checking in the game. Do not move the assembly
outward merely to eliminate harmless decorative overlap.

- Real Unity 2019.4.40f1: geared RPM/torque graph and saturated temperature reference survived prefab save/reload.
- Real Unity: support capsules and all four A18 running-board seats checked on disposable generated geometry.
- Real Unity C-70 diagnostic: both main-rod big-end nub tops were measured and a disposable prefab retained two
  rod-parented providers with matching cup count. The left nub had clear top access while an eccentric rod crossed its
  outward approach at the sampled pose. A separate regression exercised rod priority, board fallback and pair omission.
- Real Unity C-70 end-beam survey: the reviewed 0.35–0.55 m band found broad faces at z +5.038 and −8.370 m,
  24/65 rays at each end, aligned with the source car-end planes. The default coupler-height band had split hits
  (16/57 front). The fingerprint-bound geometry review cleared the beam gate. A later geared-graph gate exposed
  duplicate references to the same RPM and gear components; the app now moves those entries into execution order.
- A non-installing C-70 conversion exported and passed bundle audit with two rod-parented oil cups, two providers,
  and simulation count two. Four coupler hook/chain clearance warnings remain in the build report; reach, coupling,
  moving-gear clearance and physics still need in-game checks. No C-70 pack was installed.
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
