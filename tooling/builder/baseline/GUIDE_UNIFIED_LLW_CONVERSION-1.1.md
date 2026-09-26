# GUIDE_UNIFIED_LLW_CONVERSION

```yaml
baseline: LLW-DV-1.1
reviewed: 2026-09-26
scope: LLW Generic Locomotive Catalog 1.4.3 -> DV / CCL 3.1.9
target: Unity 2019.4.40f1; Built-in rendering
purpose: normative builder specification + implementation source map
review: Codex cross-source/code review; Claude C10-C11 review incorporated and technical corrections cross-checked
runtime_acceptance: user confirms all recent implemented methods working in game, 2026-09-26
artifact: documentation only; existing builder branches remain separate
units: metres, kilograms, seconds, litres; pressures explicitly gauge or absolute
coordinates: car-local x right, y up, z front; tender coordinates local unless stated
```

## 00 READ CONTRACT

- Read 00-03 once; load task-specific sections thereafter. Resolve source aliases in 01; consult older narratives only for evidence/detail. Rule IDs are stable references.
- MUST = baseline invariant. DEFAULT = working choice, overridable by measured vehicle profile. DESIGN = proposed extension, not implemented fleet capability. Per-model constants are examples, never universal settings.
- Current user acceptance supersedes older `pending`, `not tested`, `found not built` labels for recent implemented methods. Do not reopen accepted G29/C21 methods merely because copied notes lag. This does not turn unbuilt fleet layouts, missing assets or future features into completed conversions.
- Technical conflict order: explicit current requirement -> matching source/config + saved-build evidence + accepted runtime result -> this reconciliation -> dated general guides -> handover/archive/memory. Runtime success establishes the tested configuration; it does not make every source constant portable.
- Change inputs/config/core, then regenerate. Preserve source packages, prior builds and source evidence. No hand-edited generated prefabs as the durable implementation.
- This document unifies the rules, not the C# files. Adoption work is explicit in 02. No new Unity build, game test, source merge or installation was performed for this document.

## 01 SOURCE MAP

Aliases are absolute directories; `$A/file` means path join, not a required shell variable.

```text
C = C:/Users/james/Desktop/Derail Valley Mods/Claudes Place
L = C:/Users/james/Desktop/LLW CONVERT
G = C:/Users/james/Desktop/Derail Valley Mods/Claudes Place/LLW_G29_Conversion
P = C:/Users/james/Desktop/LLW CONVERT/LLW Pilot Workflows
H = C:/Users/james/Desktop/LLW CONVERT/LLW G29 CONVERSION
RR = B:/SteamLibrary/steamapps/common/Railroader
DV = B:/SteamLibrary/steamapps/common/Derail Valley
LOG = C:/Users/james/AppData/LocalLow/Altfuture/Derail Valley
```

| Ref | File / evidence | Role |
|---|---|---|
| S01 | `$C/GUIDE_Railroader_to_DV_CCL.md` | Claude general method + examples A-F |
| S02 | `$C/GUIDE_Railroader_to_DV_CCL_CODEX.md` | Codex method + C21 corrections |
| S03 | `$C/GUIDE_SHARED.md`, through C11 | joint, fittings, oiling and outer-coupler reconciliation; C10/C11 baseline review |
| S04 | `$G/builds/prerelease1/TEST_NOTES.md`, `build_report.txt`; `$G/builds/test7/TEST_NOTES.md`; `$G/builds/test8/TEST_NOTES.md`, `feedback/` | current G29 geometry, six cups, couplers, realism |
| S05 | `$P/C21_STATUS.md`; `$P/builds/c21/test17/TEST_NOTES.md`, `build_report.txt`, `result.json`, `bundle_audit.json`, `installation.json` | current C21 v0.1.3; eight cups; couplers |
| S06 | `$P/README.md`; `$P/FLEET_WORKFLOW_DESIGN.md`; `$P/DEPENDENCY_FINDINGS.md`; `$P/analysis/catalogue/` | extraction fixes, full inventory, dependency evidence, future family work |
| S07 | `$P/analysis/oil-cup-survey-20260926/REPORT.md`, per-model `anchor_manifest.json` | 238 source landmarks / 25 locos; detector limits |
| S08 | `$P/analysis/gameplay-oiling-design-20260926/FINDINGS_AND_METHOD.md`, `layout_evidence.json` | proposed 6/8/10 selection, reviewed with S03 C2 |
| S09 | `$P/analysis/c21/joint-pin-check-20260926/joint_check.txt`; `$P/analysis/c21/oil-anchors/`; `$P/builds/c21/oilvalidate01/oil_built_validation.txt` | joint geometry and moving anchors |
| S10 | `$P/analysis/c21/runtime-feedback-20260926/stock_fittings/stock_fittings_geometry.json`; `CONTROL_DECISION.md` in its parent | runtime fitting dimensions; retained lever physics |
| S11 | `$H/GUIDE_LLW_G29_Railroader_to_DV.md`, `STATUS.md`, `REBUILD.md`, `updates/test5-ancillary-and-audio/` | historical reproduction; source/core divergence; ancillary/audio detail |
| S12 | `$L/LLW_CATALOGUE_FEASIBILITY_AND_INITIAL_PLAN.md` | initial catalogue scope; superseded availability/status claims |
| S13 | `$C/DV-Oil-Burning.md`; `$C/ALCo_Mikado1610_Conversion/` | optional oil-fuel adapter; corrections in 13 |
| S14 | `$C/RLW_RGB2_Conversion/analysis/decomp/DV.ReciprocatingSteamEngine.cs` | saved decompilation: MeanEffectivePressureRatio, SimulateMeanTorque, Tick; E03 correction |

Other context consulted: Claude conversion memories under `C:/Users/james/.claude/projects/`, `$C/README.md`, `$C/notes/`; Codex chats `List LLW generic catalogue locos` and `Review modding document clarity`. Memories/logs locate evidence; they do not override newer builds. Archived guides, rollback docs and older test data remain historical records. No unrelated texture/UV pipeline is a prerequisite.

## 02 IMPLEMENTATION BASELINE / ADOPTION MAP

| Capability | Reuse source | Integration boundary |
|---|---|---|
| General builder/config | `$G/tools/unity/CclLocoBuild.cs`, `LocoConfig.cs` | starting core: `CouplingCheck`, `PinPairs`, `RigOnEndBeam`, `RodOilers`, stock-fitting placement, saved ancillary controls, audio, `ReleaseLabel` |
| Explicit moving cap anchors | `$P/tools/unity/CclLocoBuild.cs`, `LocoConfig.cs` (`OilAnchor`, `OilAnchors`) | port as an alternative to `RodOilers`; preserve tags/index order; create providers before regrouping |
| Source geometry gate | `$P/tools/unity/RRPlacementValidation.cs` | port required config fields too; adapt to final fitted poses, not original hints; verify actual built output |
| Preparation/import checks | `$P/tools/resolve_clip_paths.py`, `gen_defs.py`, `pilots.py`, `test_workflow.py`, `unity/PilotProbe.cs` | recursive clip search; full component metadata; source fingerprints; actual Unity target checks |
| G29 reference | `$G/tools/unity/G29Config.cs`, `G29Source.cs`, `G29Probe.cs` | vehicle choices, not generic constants |
| C21 reference | `$P/unity/C21_CCL/Assets/Editor/C21Config.cs`, `C21OilProbe.cs` | vehicle choices, cap anchor manifest; compare tools/project copies |
| Build/audit/install pattern | `$P/tools/run_c21.ps1`, `audit_c21.py`, `install_c21.ps1`; `$G/tools/run_unity.ps1`, `install_build.ps1` | C21 helpers contain C21-specific values and warning allowance; parameterize for another car |

B01 MUST diff capabilities, not timestamps. G29 is not a strict superset of C21; do not overwrite one branch wholesale. Keep one authoritative shared core when implementing a future merge; sync generated `Assets/Editor` copies from it. Record input hashes and new build evidence.

B02 Reviewed code deltas to handle during adoption:
- G29 still declares `ReleaseBracketH=0.332f` and uses it in fitting/stand-in logic. Runtime root-local extent is **0.431255 m**; C21's validator uses this corrected value. New fitting checks/stand-ins MUST use transformed stock geometry. Extending the upward probe from .302 to .401255 m may change automatic placement: compare final poses, never silently move the accepted G29 release. If the original pose passes actual scaled-geometry clearance, preserve it with `BrakeReleaseExact`; an override does not waive validation. This is a reuse correction, not evidence of an observed game failure (S03 C11).
- G29 `RodOilers` detects tall oilers only. C21 shallow plugs require explicit `OilAnchors` or the reviewed family detector (07). Never replace C21's eight-point manifest with tall-only rediscovery.
- Both configs still expose a single `PonyRadius`. `WheelClips` supports explicit per-clip radii but is not proof that all pony-wheel construction is generalized. Unequal wheel groups need a measured adapter (13).
- Pilot resolver logs duplicate paths but selects first matches/ties. MUST independently reject unresolved or ambiguous bindings; a zero-unresolved counter alone does not certify the chosen hierarchy.
- `EndBeam` returns 0 on no hits. MUST treat `no hits`/an implausible beam as failed measurement, not a valid z=0 installation. Inspect modal support and surface identity (06).
- C21 pre-export checks and bundle audit complement G29 coupling checks. Neither automatically proves the other's branches or future merged output.

Snapshot fingerprints, SHA-256 first 16 hex; exact on-disk state reviewed, not a merged revision. Board snapshot ends at C11; subsequent review messages naturally change its live hash.

```text
6ba4fd0cc8945488 $C/GUIDE_Railroader_to_DV_CCL.md
8dfb8f0b7720c799 $C/GUIDE_Railroader_to_DV_CCL_CODEX.md
22137f2ca3013735 $C/GUIDE_SHARED.md
71055e7f46374067 $G/tools/unity/CclLocoBuild.cs
a8acc718e8ecb5a0 $G/tools/unity/LocoConfig.cs
402b13b66abecb52 $G/tools/unity/G29Config.cs
42944097d21832ed $P/tools/unity/CclLocoBuild.cs
feb0c3bcc42113cb $P/tools/unity/LocoConfig.cs
208625685633597c $P/tools/unity/RRPlacementValidation.cs
28da9f9ce3db1be6 $P/tools/resolve_clip_paths.py
30e49464ebf6b22a $P/tools/gen_defs.py
9cc00f34ff66734f $C/RLW_RGB2_Conversion/analysis/decomp/DV.ReciprocatingSteamEngine.cs
```

## 03 VEHICLE RECORD / PIPELINE

B03 Record schema below is a documentation/data contract; it is not an existing importer API. Keep unknowns `null`, not guessed zeros. Every numeric setting needs `value, unit, basis, evidence`; basis = source | measured | derived | analogue_estimate | DV_choice.

```yaml
vehicle:
  identity: [source_id, car_id, livery_id, version, release_label]
  inputs: [bundle_sha256, definition_sha256, catalogue_sha256, extractor_version, target_unity]
  dependencies: [{id, provider, hash, selected_asset, state, repair_or_substitution}]
  appearance: [livery_key_exact, selected_options, excluded_options, decals]
  mechanics: [{role, axle_count, tread_radius_m, pivot, clip_key, regions, engine_unit, phase}]
  geometry: [body_transform, bounds, cab_floor, teleport_volume, collision, walkable, coupler_end_modes]
  controls: [{source_path, clip_or_axis, grip, port, control_type, physics, keyboard_mode}]
  simulation: [basis, mass_ledger, TE_target, cylinder_equivalence, resources, boiler, firebox, adhesion]
  oiling: [{stable_id, source_hash, mesh_fingerprint, parent, landmark_space, landmark, seat_method, tag, sim_index}]
  acceptance: [build_id, exported, warnings_with_disposition, audit, installed_hash, runtime_feedback, fidelity_gaps]
```

B04 Pipeline:
1. Index **all** Definitions/Catalog files globally; follow loco -> actual tender -> trucks/parts/images/audio. Retain full source JSON including mod-defined components and option deactivation rules. Repair syntax only in recorded overlays; preserve originals.
2. Resolve selected appearance explicitly. `enabled` alone is not an option selection. Shared parts are usually in car space; use their original pose unless a component specifies placement. Preserve exact keys (e.g. tender `Lined ` with trailing space).
3. Export AssetRipper with `TargetVersion=2019.4.40f1`; retain native reference where available. Cache by bundle hash + extractor version + target, not pack ID. Copy dependency GUID closure + `.meta`; skip RR scripts; reject GUID collisions and ambiguous asset names. No FBX round trip required.
4. Repair **every** `.anim` recursively, including `Assets/box`; preserve relative directories/duplicate filenames. CRC32 against all relevant prefab paths and child-relative paths; rewrite to the actual target root. C21 tender: `Main/...` -> `Tender/Main/...`. G29 retains `Main`; flatten a wrapper only when needed, keeping world pose and adjusting component paths.
5. Unity project: 2019.4.40f1, asset pipeline v1, remove URP, uGUI 1.0.0 + TMP 2.1.6, CarCreator 3.1.9 with GUIDs preserved. Verify instantiated clip targets, source component parents, meshes/material slots and options.
6. Generate definitions; configure per-car profile; probe wheels, backhead, visual faces, hull floor, islands and selected parts. Convert parent-relative source components to car space. Reject degenerate transforms (C21 source Reverser has zero Y scale).
7. Build: clips/materials/generated assets -> car wizard -> exterior/gear/sim -> interior -> interior LOD -> interactables -> sound -> types/liveries/pack -> geometry/serialized checks + renders -> `ExportPackWizard.Export` -> Info.json requirements -> independent bundle audit.
8. Fresh `builds/<run>/`; preserve previous run. Install only when requested within the conversion task, after audit, with game closed, timestamped rollback and installed hash. Fully restart DV for changed bundles; radio respawn can preserve old state.

B05 Tool context (machine-specific): Unity `B:/Games/Unity 2019.4.40f1/Editor/Unity.exe`; AssetRipper `C:/Users/james/Desktop/Derail Valley Mods/AssetRipper FREE/AssetRipper.GUI.Free.exe`; Python `$C/.venv312` or bundled Python; ilspycmd `C:/Users/james/.dotnet/tools/ilspycmd.exe`; CarCreator `$C/GWR_1366_CCL_Migration/tooling/CarCreator_3.1.9.unitypackage`. Use existing launchers. Local licensing failures occurred under restricted/batch launches; normal user-context launch worked. Wait for exit + explicit result/export, not process creation. No licence workarounds or toolchain upgrade needed.

B06 AssetRipper API: read `/Settings/Edit`; POST `/Reset` before settings changes; POST `/Settings/Update` with complete form and target version; POST `/LoadFile` Path; POST `/Export/UnityProject` Path. Probe the actual installed API when changing versions.

## 04 MATERIALS / SOURCE GEOMETRY

M01 RR Standard Car Shader -> DV `Standard (Specular setup)`: preserve `_MainTex`, `_SpecGlossMap`, normal/occlusion, `_GlossMapScale=_Smoothness`; resolve `_BaseColor`/livery tint through source colorizer mappings into `_Color`. Colour ID is not necessarily material name; material-null colorizers match renderer material names. Four-digit colours are Unity `#RGBA`.
M02 Unique converted material filenames across packages; duplicate names (`black`, `metal`, `white`) must not overwrite assets. URP Lit fallback is colour-only unless deliberately adapted; glass premultiplied alpha. Multi-livery automation/`PaintSubstitutions` is not established by the single-livery builds.
M03 Combined bodies need welded-position mesh-island analysis for valve wheels/oilers/pins. Select by source identity + geometry; cut only the reviewed island. For merged lamp glass, use material triangles (`GlassLamps: path#material`); zero-triangle glass -> explicit `LampLenses` at measured/source anchor.
M04 Measurements: visual meshes with original hull colliders disabled for coupling/fittings; hull for walkable floor. Backhead rays start inside the cab; distinguish hull vs visible backhead hit. Preserve import transforms (LLW `Main`: scale 100, -90 X); do not compensate twice.

## 05 MOTION / COLLISION

A01 `AnimationMap` key != filename (`FBDoor`, `Indy`, `TB`, `Pump`). Use map keys. `NestedClipGroups`: identity animator nodes at appropriate common parents, copied/re-rooted bindings, shortest bound ancestor defines a region. Register **every** region with its wheel/port proxy. Region count is build-derived, not fixed at 14; G29 test4/test5 reports had eight driver and two reverser regions.
A02 One-revolution source clip of length L seconds: state speed L times wheel-revs/sec parameter, loop enabled. Powered/pony/auxiliary wheel proxies need correct tread radius. Port sampling `SET_NORMALIZED_TIME` wraps via FloorMod; use endpoint factor 0.999. For nested clips, create child animation before parent regrouping. Retain configured `LoopAnimations`, `BrakeHangers` and `FireDoorLeaves`; inventory those mechanisms rather than dropping them when copying the main wheel clip.
A03 Physical axles != source wheelset records. `Wrench`, `Shovel`, `Speedo`, `Conduit` can drive auxiliary motion. G29 Wrench source diameter 3 m -> `WheelClips` radius **1.5 m**, no added axle.
A04 Rigid coupled frame: split real axles across DV's two bogies; pivots at outermost **drivers**, not pilot/trailing axle. Hang pilot truck on its bogie via `ArticulatedParts`. Tender trucks at +/-separation/2; honour per-end truck overrides; wheel mesh pivots on axles under nearest DV `[axle]`. Measure treads, not flange bounds; correct ride height once.
A05 Articulated front engine: parent its gear, pilot and mounted fittings/lights to corresponding `BogieF/bogie_car`; preserve engine phase. Bogie-centre pivot is an approximation to a real Mallet hinge. Visual articulation does not establish compound sim or independent slip.
A06 `[collision]`: boxes or convex shapes on car rigidbody. `[walkable]`/`[items]`: source non-convex hulls allowed. Remove original model colliders; exclude moving rods/doors/windows from static walkable copies. Add steps/ladder support. Coupler-band collision/camera trimming: 06.
A07 `[cab]` at measured floor plus child `teleport_indicator`: trigger BoxCollider + `GrabberRaycastPassThroughProxy`, correctly sized. HUD/input follow the walkable floor under the player; tender deck means tender control context. A source `Seat` alone does not prove cab position.

## 06 COUPLING (S03-S05, S09)

C01 Each end has exactly one mode, ordered: **RR drawbar -> measured buffers -> unbuffered outer beam**. Do not mix end beam, visual knuckle face, RR car end, rig origin and live coupler anchor.

C02 RR loco/tender drawbar:
```text
T = loco.positionTail - 1.000 - tender.head
loco_rear_plane = loco.positionTail - 0.500
tender_front_plane = tender.head + 0.500
T = loco_rear_plane - tender_front_plane
config: loco.RrEndRear; tender.RrEndFront
```
Tender/head for non-loco cars usually length/2; use resolved definition. RR planes override `CouplingFace*` at drawbar ends. Auto/rigid coupling and hidden internal DV hardware: 10. Never move the tender to force non-mating features together.

C03 Outer unbuffered end, `dir=+1 front,-1 rear`:
```text
rig.z = beam.z + dir*0.309
live_coupler.z = rig.z + dir*0.249 = beam.z + dir*0.558
rig.y = CouplerHeight; default 1.050
```
Measure visual beam: rays from outboard along z, x=-0.6..0.6 step .1, y=height-.20..height+.05 step .05; group hits within .5 m of outermost hit in .01 m bins; select modal bin, average z. Log support count and hit part. Narrow knuckle/lift bar is not the beam. Current `CouplingFace*` is ignored in this mode. Buffer-equipped ends keep measured buffer-face handling; the .309 rule does not replace it.

C04 Verify beam identity when adjacent bins/tank faces compete. C21 rear uses -2.917, not earlier -2.936 estimate; .5 m window leaves little margin against tank face. Narrowing Y band or merging neighbouring bins is a future measured adjustment, not an already applied universal change. Fail no-hit results. Live placement comes from CCL `BufferProcessor` + `CouplerProcessor` offsets, not prefab child-marker appearance.

C05 Stock rig front: hook z=-.324..+.012, y=-.233..-.006; chain down to y=-.59; hose anchor=(-.383,-.087,-.173); snap trigger r=.17 centred=(0,-.125,-.017). Rear mirrors x/z. Hook plate offset=(0,-.0784,-dir*.332); buffer pad z=dir*.2145. Inspect hook/chain/cock/hose envelopes. Trim `[collision]` and `[camera dampening]` boxes beyond beam in x +/-0.6, y=height-.70..height+.25. Source visual overlap >20 mm proud of beam is a review warning, not proof of blocked interaction.

C06 G29/C21 visual knuckle overlaps are accepted in game. Preserve per-build warning evidence; no global suppression and no automatic knuckle deletion. New models require their own geometry/interaction disposition.

C07 `CouplingCheck`: joint-crossing bars/castings/hoses/fall plates; draw-gear reach; compact-solid overlap; sensitivity T +/-0.1 and +/-0.3 m. `PinPairs`: pair only geometrically credible mating pin-shaped islands within .5 m in plan, flag >.03 m misalignment. C21's former loco "pin" was a draw casting. Its tender pins are rear bar ends, not loco mating pins; no pair is valid there.

| Accepted reference | Tender origin | Loco front beam / rig / live | Tender rear beam / rig / live |
|---|---:|---|---|
| G29 0.9.0, geometry from test8 | -8.194 | 5.175 / 5.484 / 5.733 | -3.738 / -4.047 / -4.296 |
| C21 0.1.3 test17 | -7.445 | 5.189 / 5.498 / 5.747 | -2.917 / -3.226 / -3.475 |

Rejected history: G29 -7.894 (0.3 m too close); C21 -7.057 (385 mm casting intrusion, 98 overlap cells). Correct RR spacing gave ~6/4 mm casting gaps and zero solid overlap respectively. Test17's copied `DATA_SHEET.md` still says test12 and old coupling planes; use current config/report above.

## 07 STOCK FITTINGS / OILING (S03, S07-S10)

F01 Stock handbrake `[brake small]`: local +z **outward**; rim r=.208, z=.040.. .086; shaft back to -.062, r=.030. Hint-based fitting: raycast mounting face/crest over +/- .3 m, shaft insertion ~.022, rim clearance >=.012. Verify entire rotating rim (C21: 24 samples), not placeholder bounds. `HandbrakeWheelExact` skips automatic fitting only; it does not skip validation.
F02 Stock `[brake release]`: local +z along rod toward exposed red end; grey body at root; body to z=.875, red z=.857..1.068, knob r=.080. Bracket root-local +y=.431255 after stock child scale 1.3 (raw .332). Sideways yaw +/-90; optional 180 roll puts bracket down. Placeholder scale is not copied into runtime part. Hide root inside measured skin; red tip ~.15 beyond side edge; rod >=.1 below edge, bracket outside cab/clear of overhead structure. G29 hint search +/- .4 m in z is a starting method; validate actual side/underside at fitted height and correct scaled bracket, including rotated pose.

O01 One finalized ordered list controls cup placeholders, consumers, providers, `OilingPointCount`, tags and saved sim indices. Matching `PositionSyncProviderProxy.syncTag` is mandatory. Decorative skipped oilers have no hidden demand. Preserve IDs/index order across updates; changing count/order requires a save-state migration decision.
O02 Providers attach to the actual moving rigid rod/engine unit. Cache source->built transform identity before regrouping. C21 resolves source path and creates provider **before** animation regrouping; G29 rediscovers named rod meshes later. Either timing works only if identity/local position is preserved. MUST NOT copy car-space coordinates directly into rod-local position. Do not animate the provider separately.
O03 `PositionSyncConsumer.Sync` copies **position only**: cup remains upright. A rod-local offset rocks with a pitching rod; rotating the provider does not rotate the cup. Inspect upright cup base/seat and lid throughout motion. Existing upright G29 main-rod fit is accepted; new follow-rotation/world-up-offset mechanisms are separate work.

| Mount mode | Implementation / default |
|---|---|
| Keep shallow cap | C21 `OilAnchors`: pivot at measured cap top; original cap retained; visual cup base 17.5 mm inside cap; eight side-rod cups, no main-rod cups |
| Replace tall oiler | G29 `RodOilers`: cut selected oiler island, retain washer/boss; pivot=seat+17.5 mm-3 mm; six cups: rear+main side-rod pins and main big end on each side; front side oilers decorative |
| New guide support | DESIGN for K50/K56/L29; measure real support and feed route first. L29 `Main` is front/articulating unit, so provider follows that unit, not boiler body |

O04 Actual stock S282 `CupOnly` bounds relative to pivot: mesh x +/- .02629, y=-.01752..+.04351, z=-.03220..+.02629; lid top +.04720, hinge local -z; trigger sphere r=.040 at (0,.0193,.0032). Thus ~65 mm base-to-lid, not 65 mm above pivot. Fit imported stock mesh, trigger and lid joints; stand-in renders alone do not prove access.
O05 Discovery: authored anchor first; then welded islands + top support + bearing neighborhood/symmetry; review/freeze selection with parent and fingerprints. G29 tall detector: >=60 triangles, height>=.06, height>=1.15*width, width<=.12, on-top support (not above whole rod's bounds centre). It misses LLW shallow 28-triangle plugs. Survey adds shallow plugs and stacked-base deduplication; counts are revision-specific hints, not semantic IDs. D47 stacked oiler/base = one mount; adjacent side/main rods remain distinct. Use area-weighted actual top face + normal/triangle identity, not bounding-box top centre. Footprint support rays handle pitched main rods better than one centre ray.
O06 G29 side-by-side main-crank cups are accepted for that geometry; C21 uses one per crank pin. Neither establishes a fleet-wide double-cup rule. NonVR oiler raycast selects first **Interactable** hit; ordinary rods are not its occlusion mask. Geometric visibility screen != DV reach. VR uses nozzle trigger and `Dot(-cup.up,nozzle.forward)>.5`.
O07 For new layouts: include body/running boards/cylinders/tanks, actual cup colliders and open-lid sweep; check standing/crouched approaches, both sides, reverse/reverser states and articulation. Sample >=16 phases for screening plus worst-case/continuous-motion review; four phases are survey evidence only. If double-cup access fails, keep one per pin or choose another credible support. No forced service count at inaccessible points.
O08 DESIGN `gameplay_6_8_10` remains a per-loco proposal, not installed catalogue coverage. Source survey: 238 landmarks; gameplay proposal: 196 cups including six unmeasured guide positions. Existing confirmed layouts: G29=6, C21=8. Future selection must define deterministic pair ranking and trim/fill policy; preserve full candidate evidence for a realism profile. Do not silently activate all candidates or fabricate the six guide coordinates.
O09 Oil budget: vanilla CCL S060/S282 defaults each have six points; capacity/consumption-per-rev/refill-rate are per point. More points increase aggregate oil/workload, not automatically the per-point depletion interval. Keep accepted settings; choose explicit aggregate/per-point policy for a new layout and record it. Do not copy the proposal's blanket economy claim as measured behavior.

## 08 CAB CONTROLS / HUD (S01-S02, S10-S11)

U01 Required chain: real lever/puller -> `InteractablePortFeederProxy` -> sim input; `LocoControlsReaderProxy` registers control; `ControlControlsWizard.AddInput` supplies keyboard; each indicator has port reader and `LocoIndicatorReaderProxy` reference. An animated handle alone does none of this. Missing registered control can display a full HUD bar. S282 bell slot needs bell control + audio, or intentional HUD removal.

```text
ControlType: throttle=0 reverser=1 trainBrake=2 independent=3 brakeCutout=5
headlightsFront/Rear=10/11 cabLight=12 sander=13 horn=14 bell=15
injector=17 blowdown=18 blower=19 damper=20 fireDoor=21 cocks=22
compressor=23 dynamo=24 lubricator=25
Inputs:
throttle.EXT_IN; reverser.CONTROL_EXT_IN; brake.EXT_IN; indBrake.EXT_IN
whistle.EXT_IN; cylinderCock.EXT_IN; injector.EXT_IN; blower.EXT_IN
damper.EXT_IN; blowdown.EXT_IN; fireboxDoor.EXT_IN; coalDumpControl.EXT_IN
lubricatorControl.EXT_IN; compressorControl.EXT_IN; dynamoControl.EXT_IN
sander.CONTROL_EXT_IN; brakeCutout.EXT_IN; headlightDecoder.HEADLIGHTS_EXT_IN
Indicators:
boiler.PRESSURE; steamEngine.STEAM_CHEST_PRESSURE; traction.WHEEL_SPEED_KMH_EXT_IN
boiler.WATER_LEVEL_NORMALIZED; firebox.COAL_LEVEL
water/coal/sand/oil.NORMALIZED with .CAPACITY range
tender loco: tenderWater/tenderCoal, not local water/coal
```

U02 Holding controls: stepped joint + notches + holding spring; whistle spring-return. Joint limits +/-177 degrees. Set toggle keyboard input for two-state controls. Test single tap/scroll and hold after .3 s notch snap. `Phys(component,min,max,notches,spring,damper,mass,drag,angularDrag,scroll,scrollSpring)`:

```text
throttle:    (s,0,angle,21,50,15,15,10,0,1,400)
reverser:    (s,0,angle,41,85,15,30,15,0,1,200)
trainBrake:  (s,0,angle,11,85,15,30,16,0,1,100)
independent: (s,0,angle,11,65, 0,30,16,0,1,100)
```
These are G29/RGB2 reference physics, not universal handle inertia. Throttle21/reverser41 => ~5 HUD percentage points/tap; C21 accepted preference uses 11/21 => ~10. Do not resurrect discarded `RRControlProfiles` edit-mode experiment or reference angular drag 2e5. Preserve per-car preference.
U03 Axis/range from source clip; t=0 is value0. Grip-only collider; explicit `Grip` for long rods/bone-only parts. Split handle meshes from remote linkage, port-drive linkage separately. Sweep controls against each other through full travel; full-arm boxes can jam levers. `IndicatorGauge` sets absolute localRotation: use identity pivot. Labels sibling to control, `LabelLocalizer ModelType=2`, `car/...`, +z into mounting surface.
U04 Doors/sashes/vents/hatches: saved `SimControls` + hidden lever/Puller; visible original stays on exterior, driven through `LoadAnimations`; exclude from `NoWalkParts` static copy. Puller slot closed at local zero/identity; -y along travel; custom connection anchor mid-travel; value=abs(localY)/(2*linearLimit). G29 sash boxes .018 m vs .023 m separation are example dimensions. Children-first nested animation creation preserves hatch props.
U05 HUD-only gauges for absent speed/chest instruments. Custom HUD: `SetToS()`, `NonSelfLappingBrakeSetup()`, overrides, `OnValidate()` JSON. Reader-field names control extra-slot mapping. `BaseHUD`: S060=25, S282=20, Custom=1000. License tender steam=`SH282`, not `S282`.

## 09 SIMULATION / REALISM (S01, S03-S06, S11, S14)

E01 Wizard car base != simulation basis. `SteamerSimCreator.CreateSimForBasis(0)` tank/onboard; `(1)` separate tender; override physical axle count and every relevant default deliberately. Disconnect unsupported basis features by rewriting `portReferenceConnections` (empty portId is valid unconnected form); S282 adds superheater/feedwater heater unless adapted.
E02 TE target precedence: source `publishedTractiveEffort` when supplied -> actual mod-defined physics if reproducing RR operation -> documented fallback. RR fallback, 2 cylinders: `TE_lbf=.85*P_psig*d_in^2*S_in/D_in`. RR's base cylinder count is two even for Mallets; inspect LegosBetterSteam components (`diamater` spelling included), mode/multipliers/LP side before multi-engine claims. Exclude global RR 1.1 balance multiplier by default. LLW class numbers roughly match klbf in G29/C21; they are a sanity check, not an independent source specification.
E03 Actual mean-pull magnitude before health scaling/output smoothing (S14; cutoff 0<c<=1, pressures absolute bar):
```text
R = (intake_temperature_K/380)^3
MEP(c) = c*(1+ln(1/c))                          if 1/c <= R
       = c*(1+(1-c)*ln(R)+c*ln(1/c))            otherwise
F_mean_N = max(0,p_adm*MEP(c)-1)*1e5 * A*(2/pi)*(stroke_m/2)*cylinders/wheel_radius_m
A = pi*bore_m^2/4
DEFAULT equivalent-bore calibration (near-full-cutoff approximation):
A_required = target_F_N*radius / (p_gauge_Pa*(2/pi)*(stroke/2)*cylinders)
bore = sqrt(4*A_required/pi)
```
`p_adm` is admission pressure supplied to the torque function after valve-flow and cock/cracked-cylinder losses, not automatically boiler pressure; steam-chest/throttle flow limits it. Below45 rpm, DV uses crank-angle-dependent instantaneous cylinder torque;45..60 blends to mean; above60 uses mean. Starting pull therefore varies with crank position. Default bore calibration assumes near-full cutoff (~.85, MEP~.988 without condensation) and approximates mean pull, not exact instantaneous starting TE. G29 at170 psig has effective mean ~11.58 bar vs calibration gauge ~11.72 bar (~1.2% difference). Keep physical stroke; no RR .85 factor exists in DV's torque model. The approximate 2-cylinder mapping gives bore~sqrt(.85)*source bore. Safety conversion=psig*.0689476+1.01325; torque code subtracts1 bar. Four-beat exhaust can use two equivalent cylinders; four-cylinder/eight-beat needs compatible audio/particles.
E04 **Mass ledger**, not `mass=weightEmpty` by name. DV adds container contents, boiler water and firebox coal. Decide whether source figure is dry or working order; record included/excluded water, coal, sand and oil and avoid double counting. G29 interprets 137,000 lb as working order and subtracts 6,080 L boiler water for base ~56,062 kg; auxiliary additions remain explicit. C21 source 92,000 lb ->41,730.50 kg was provisionally treated as dry. Claude recommends treating C21 as working order too, based on analogous engine specifications/driver-weight share (S03 C11); this remains a proposed realism correction, not a verified source-field definition or an applied config change. Resolve its full mass ledger before changing it. Gameplay acceptance does not establish historical weight semantics.
E05 Adhesion approximation: `F_slip=mu*(total_weight/axles)*powered_axles`; choose mu using source weight-on-drivers fraction and actual axle counts. Measure tread radius; starting TE alone does not match a speed/power curve.
E06 Accepted G29 realism **method**: derive from source dimensions/pressure/heating surface and explicitly labelled comparable real prototypes where absent. Values below are engineering estimates/calibration starting points, not universal constants or historical certification:
```text
max_burn_kg_s = firebox_capacity_kg / burnTime_s
heat_MW = burn_kg_s * 32 * efficiencyAtMaxCombustion
steam_kg_s ~ heat_MW / 2.68             # stated cold-feed energy assumption
volume_m3 = pi*(diameter/2)^2*length*capacityMultiplier
saturated evaporation starting estimate ~11-12 lb/(ft2 heating surface*h)
hand-firing sanity estimate <=~120 lb/(ft2 grate*h)
bed starting estimate ~2.25 kg/ft2 grate; water fraction ~.76
injector starting estimate ~1.4*max_evaporation L/s
coal/water consumption multipliers=1 for this realism profile
```
Choose saturated/superheated behavior intentionally; analogue estimates stay labelled. Record derivations in SimSpec `_notes`; validate sustained pull/steam balance for each new profile. C21's older 100 kg/180 s, coal x2 settings and Claude's ~.32 kg/s suggestion are not a completed C21 realism pass.

| G29 0.9.0 reference | Value |
|---|---|
| Pull; source cylinders; equivalent DV bore/stroke | ~29,363 lbf; 20x26 in; ~.4684/.6604 m |
| Pressure; opening/closing valves | 170 psig; ~12.73/12.53 bar absolute |
| Grate; heating surface | ~29 ft2 analogue; 1,735 ft2 source |
| Fire; steam; boiler space/water | 65 kg / ~155 s =.42 kg/s; ~2.5 kg/s; 8 m3 /6,080 L |
| Injector; tender | 3.5 L/s; 6,000 US gal; 18,000 lb coal =9 **short** tons (~8.165 metric t) |

Unit conversions: lb->kg .45359237; US gal->L 3.785411784; inch->m .0254; lbf->N 4.4482216. Specify US vs Imperial gallons and short vs metric tons.

## 10 TENDER / SERVICING / LIGHT / AUDIO

T01 Tender is second car: `Kind=Tender`, `BaseCarType=S282Tender`, wizard pack settings null; final `pack.Cars=[loco,tender]`. Exact folder matching when AssetDatabase prefix filters overlap. Loco S282 sim consumes `tenderWater/tenderCoal`; tender `TenderSimCreator` supplies resource/broadcast ports. Front/rear `TENDER_*` directions must match; dynamo/headlight signals return to tender. Tank locos keep onboard resources.
T02 Loco root: `CarAutoCoupler` rear->tender front, `RigidCoupler` rear, kind Tender; loco sim `VirtualHandbrakeOverrider` rear/Tender and loco `hasHandbrake=false`; tender `KeepCoupledInteriorLoaded` front. Hide internal drawbar-end DV couplers. Livery `TrainsetLiveries=[loco,tender]`; spawn group's `AdditionalLiveries` tender; `ForceValidation()` writes JSON. Do not rename stable IDs to change release label.
T03 Water/coal receivers at resolved `LoadTarget` anchors (resource types20/21); coal pile `ShovelCoalPileProxy` where reachable; coal visual via `coal.AMOUNT`. Source handbrake lever can use `HandbrakeFeederProxy`; stock placeholder is an alternative. Water hatch animation is cosmetic; DV refills through receiver collider, not hatch state.
V01 Headlights: six setups per end, even no-lamp ends; index0 OFF with no subcontrollers. Port decoders `headlightDecoder.FRONT_/REAR_HEADLIGHTS_EXT_IN`; dynamo fuse `fuseboxDummy.ELECTRONICS_MAIN`; no MU cable -> `multipleUnityDependent=None`. No uncontrolled always-on Light. Create lens/glare/beam, call `OnValidate`.
V02 Pre-add `ItemLightProxy` with Light assigned for cab lights. Firebox light <=.6 m; fill/bounce multipliers0. Newly added ExternalControls are inserted by CCL; do not duplicate in `executionOrder`. Inspect saved IDs for uniqueness.
V03 Steam vanilla audio IDs3000-3018, whistles3050(S060)/3100(S282); chuff type0/1. Stock chuff slots=4: other beat count needs helper extending slots in `ChuffClipsSimReader.Init`. Pitch helper applies once per instance/type; declare dependency. Cylinder-cock particle setup count must match sim cylinders; clone jets/phase curves beyond2 and validate.
V04 RR chuffs are synthesized; retain DV chuffs. Whistle recording by `defaultWhistleIdentifier`; empty/`a.w.default` falls back to `wh-5-drg-st`. G29 uses `wh-3-cnj`. Bell/pump/dynamo recordings: RR `sharedassets3.assets`. Extract exact AudioClip; duplicate catalogue ID is insufficient. Use `extract_rr_audio.py`, `loopify_wav.py`; whistle/pump/dynamo loopify with 4096-sample-frame crossfade, G29 rope bell `--asis`. Source audio provenance stays separate from LLW model.
V05 Custom loop: Continuous `LayeredAudioProxy` + child `AudioSource(loop)` + `AudioLayerProxy` volume/pitch curves/source + `LayeredAudioPortReaderProxy`. Ports: whistle=`exhaust.WHISTLE_FLOW_NORMALIZED`, bell=`bell.BELL_NORMALIZED`, pump=`compressor.PRODUCTION_RATE_NORMALIZED`, dynamo=`dynamo.DYNAMO_FLOW_NORMALIZED`. Mixer Horn12, Compressor21, Engine7, Cab3. Replace matching vanilla sounds only when replacement clips exist; do not leave duplicates. Personal extracted game audio is not an automatically redistributable release asset.

## 11 ACCEPTANCE / REGRESSION CONTRACT

Q01 Record distinct states: located -> metadata linked -> extracted -> Unity inspected -> exported -> audited -> installed -> game accepted. Current user's acceptance closes recent implemented-method pending flags. It does not fabricate per-cup/VR/save tests or complete missing fidelity work. Existing accepted build is regression reference; new geometry/core changes need relevant new evidence.
Q02 Source gate: selected dependency closure, recorded repairs, hashes, unique GUID/asset resolution, complete source fields, no missing used animation targets/meshes/material slots/parents. Check unused clips separately; unresolved unused dependency clip is not a used-animation pass.
Q03 Build gate: compile; explicit successful result/export; actual saved sim IDs unique, referenced ports/components present; complete wheel/port animator regions; correct axle/radius/resource route; fitting/beam/joint/oil manifest checks; runtime scripts restricted to approved target assemblies (baseline CCL.Types + explicitly declared helper needs, no RR behaviors/editor scripts).
Q04 Review fixed views: complete exterior, backhead/grips, floor/teleport, lamps lit/off, both outer rigs, coupled joint, fitting stand-ins, oil motion. **Zero unexplained warnings**, not zero warnings at any cost. G29 reference has7 accepted hardware visual-overlap warnings; C21 test17 has8. Freeze exact warning disposition against that build/source fingerprint; new types/count/geometry trigger review. Do not globally whitelist a warning category.
Q05 Bundle independently inspect: identities, scripts/requirements, provider/consumer count+tags, sim settings, coupler positions, pack contents and output hash. Refresh data sheet/test notes from actual output; stale copied headings/numbers fail documentation review. Installed Info.json presently G29=0.9.0, C21=0.1.3, CCL=3.1.9; both LLW packs declare DVCustomCarLoader. Record support-mod environment; DVPositionSyncFix/DVCCLControlFix/FiremanAssistant presence does not prove universal dependency or helper-free operation.
Q06 For a new conversion/change, game checks relevant to change: spawn/despawn; cold start/steam/pull; forward/reverse curves/points; axle/rod phase; HUD+keyboard+mouse and control hold; brakes/cocks; teleport/walkability; coupling at both outer ends and tender supply; servicing/cups/lids; lights/audio; save/reload. VR only when in release scope. Retest representative affected families after shared-core changes; measure multi-engine performance before fleet claims.
Q07 Deliver reproducible config/core hashes, source registry, build result/report, renders, bundle audit, packaged metadata, install/rollback record if installed, runtime feedback and explicit remaining fidelity choices. Stable car/livery/save IDs; `ReleaseLabel` changes DisplayName only. This guide does not install or authorize release publishing by itself.

## 12 FAILURE LOOKUP

| Symptom | First check / action |
|---|---|
| Spawned car lacks sim/interior/collision; thousands of later NREs | first exception after `<CarId>(Clone)` inside `SimController.Initialize`; later DrivingForce/Update spam is secondary |
| Init NRE in headlights | setup0 must be OFF/no subcontrollers; six entries at both ends |
| `same key` during spawn | duplicate sim IDs/executionOrder; CCL auto-added ExternalControl |
| PositionSync NRE / missing providers | matching tags/count and provider registration on actual rod; inspect helper environment |
| Wheel motion but frozen rods | missing animator regions, wrong key/binding root, clip-speed/radius mismatch |
| Cab does not highlight | floor + `[cab]/teleport_indicator` trigger/pass-through proxy |
| HUD/input wrong while rear of cab | standing on tender's walkable deck; inspect current-car context |
| Controls return, crawl, jam, or show full bars | stepped/holding physics, drag/scroll spring, grip clashes, reader registration |
| Pink or all-black model | duplicate material asset path; actual RR tint/colorizer and selected livery |
| Invisible platform through opening/gear | static source collider copied from moving part |
| Coupler buried | correct end mode; measured beam+.309; importer live offset; collision-band trim |
| Tender joint compressed | RR T formula; no casting-to-pin false pairing |
| Oiler floats/buries/stays fixed | coordinate space, pivot/base, chosen seat, moving parent, position-only sync |
| Cab light disabled / ItemLight errors | preassigned ItemLightProxy; initialization can continue despite this local failure |
| CCL cannot load rewritten UnityFS | preserve node flags/compression/alignment; see `$C/notes/UNITYFS_RULES.md` only if patching bundles directly |
| Unity launch without output | licensing/user context, compiler log, process exit and explicit result; fresh output folder |

Read `$LOG/Player.log` and `Player-prev.log`. Decompile implicated installed DV/CCL type to resolve unknown behavior; repair builder, not output. Known unrelated mod messages must be attributed, not ignored by broad text blacklist.

## 13 BOUNDARIES / NEXT FAMILY WORK

D01 Catalogue=25 locomotive definitions:24 conventional + L29 articulated. Conventional scope:4 tanks+20 tender locos,14 distinct default tenders (38 car identities); all25 use14 default tenders (39 identities).20 tender definitions supplied in total. Inventory/photos/liveries are different counts. S16 0-6-0T source inspection passed; remaining catalogue entries are not made playable by this baseline.
D02 Suggested progression after accepted G29/C21: S16 0-6-0T tank pilot -> S32/Fox tender -> S16 siblings -> C35/RV + Archbar -> remaining families. One representative per family before siblings. Measure all changed geometry; same wheel arrangement is not same config.
DESIGN (S03 C10): catalogue-driven `LlwCatalogConfig` from definitions/probes plus measured per-loco overrides. Shared component kinds support reuse, not universal coordinates. A drivable first-pass tier and later fidelity tier are proposed scope choices, not an implemented generator or authorization to batch all25.
D03 Required dependencies/known exceptions (S06):
- Fox `fox-truck-2s` -> explicit `Fox-Truck-2s` asset mapping; already inspected for pilots. TSW Archbar/ASF/Andrews found; inspect actual exported assets. Extensionless TSW catalogue names are not exported filenames.
- MSL images located in `$RR/Mods/MSLDecalPack/LegosLogosFolder`; use dependency registry hashes, source crop/pose. Availability does not mean pilot integration complete.
- `k35parts`: trailing comma; `plate` unresolved. `k50parts`: missing quote on headlight5 + trailing comma; `stack1` unresolved. `p39parts/plate` vs `numplate`: inspect before aliasing. Metadata repair does not prove missing asset resolved.
- `wh-3-lunkenheimner` exact audio unresolved in scanned catalogues; C21 uses documented stock S060 substitution. Greenninja duplicate `audio.whistles03` pack IDs have different bundles; inspect clips, never first-match by pack name.
- K35/K50/K56/P39 need unequal front/rear wheel radii; P39 two-axle pilot; D47 five-driver curve/overhang review. Auxiliary wheelset entries remain non-physical unless measured otherwise.
- L29: compound/simple behavior and independent slip need separate adapter; source default tender=G29 despite supplied L29 tender. Preserve source default until deliberately changed. L29 tender truck metadata alias discrepancy (`betten`/`bettendorf`) needs inspection; extra tender `truck.2b-p4` unresolved. These do not block conventional14 tenders.
D04 C21 working baseline retains static doors/windows/roof vent/filler hatch, incomplete cosmetic decals/source whistle, provisional realism. G29 already demonstrates saved ancillary motion/RR sounds. Reuse the methods; do not falsely record C21 fidelity work as complete. Multiple liveries, automatic full-fleet fitting and multi-engine runtime performance remain separate deliverables.
D05 Optional oil-fuel conversion stays outside the coal LLW core recipe: use S13 + ALCo worked example, not old 2901 numbers. The current G29 core already implements `BuildOilFiring` behind `LocoConfig.OilFiring`; G29 config leaves it null. C9's claim that the capability was absent is corrected by C11 and code inspection. Corrections to the early oil-burning write-up: fuel-pump socket requires `[fuel de2]`; keep `MagicShovelling` for ignition/input integration while removing physical coal loading; cold feed needs atomizer pressure/control rather than boiler-only >=2 bar gate; broadcast `coal.AMOUNT`, not CAPACITY. Fuel-oil container is distinct from lubricating Oil. Register execution entries once and validate actual port IDs/case. These corrections do not convert every LLW engine to oil firing.

## 14 CHANGE DISCIPLINE

Update this baseline by rule ID with source/build evidence and affected scope. Keep one current rule per issue; replace obsolete prescriptions, retain their reason only where it prevents regression. Put vehicle coordinates/balance changes in vehicle records. If code and guide disagree, document the exact delta (as B02), then separately implement/validate when a code change is requested. Do not label a future merged core "tested" from the success of its separate parents.

Review resolution index: outer-coupler face inset -> C03; guessed/pin-aligned tender gap -> C02/C07; raw brake bracket -> B02/F02; fixed/static or tall-only oiling -> O01-O08; 3 m ratchet radius confusion -> A03; hard-coded region counts -> A01; blanket dry-mass copy -> E04; zero-warning dogma -> Q04; stale runtime pending flags -> 00/Q01; archived oil-burning removals -> D05.
