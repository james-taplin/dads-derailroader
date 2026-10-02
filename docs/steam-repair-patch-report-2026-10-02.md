# Steam test-batch patch report — 2026-10-02

Local app changes on `claude/unity-crash-message` in `dads-derailroader-exp`. James authorised implementation after the documentation-only investigation. Existing catalogue work and other local changes were preserved. No commit, push, release, game installation or offline-builder modification was made.

Six evidence-backed defects have corrections in source. They are candidates for rebuilt packs and gameplay checks, not a declaration that the fleet is finished. The two supplied rebuilds already proved catalogue references for K-28T, C-25 and its tender; that success is separate from this patch.

## Changes and evidence

| Correction | Cause and change | Validation and remaining limit |
|---|---|---|
| Whistle mesh attached to its lever | `_part_specs` used a name-only dictionary. Ten stock definitions call both the steam fitting and cab control `Whistle`. It now requires the uniquely named component of kind `Whistle`, preserves its full source transform and parent, and rejects missing/ambiguous fittings. | Three regression cases failed before the fix and pass after it. Read-only checks against all 21 installed Railroader definitions match the fitting's parent, position, rotation and scale; all correct parents are root. Rebuilt mesh movement in game remains pending. |
| Empty tender coal/water animations | Flat grouping gave the shared tender root to the first resource clip. Tender records now enable the existing nested grouping implementation. No pinned core edit. | Pipeline regression verifies the tender flag. Native Unity tests export/reload coal-first and water-first synthetic tenders, sample each clip at 0/.5/1 and verify its target moves independently. C-25's previously empty coal group and the 17 empty water groups still need rebuilt-fleet checks. |
| Boiler glass grows below its frame | The core's centred water mesh was at zero under a bottom-anchored scaler. An app-owned finishing step raises the water child by half its height before the interior LOD is copied. | Native Unity reproduces the old below-bottom geometry, then verifies corrected bottom/top at 0/.5/1 after bundle reload. Repeat application is safe. This changes the indicator, not boiler physics or explosion behaviour. |
| P-18 missing boiler-water HUD reading | The core only assigns `locoWaterLevel` when it creates a physical sight glass. The app now adds an invisible boiler-water scaler/port reader only when that reference is absent. | Native export/reload test verifies the reference survives, creates no visible renderer and does not duplicate the fallback. Existing glass readers are preserved. In-game HUD values still need comparison against the boiler port. |
| K-28T invalid licence | `SH060` is not the game's tank-engine licence ID. Corrected to `S060`, preserving the intended vanilla-licence policy. | Read-only inspection of DV build 99 `resources.assets`: GeneralLicenseType_S060, path ID 296942, contains length-prefixed `S060` at byte 56; SH282 asset 296943 contains `SH282`. Regression preserves both exact IDs. Career/sandbox behaviour still needs gameplay testing; no broader licence-policy decision made. |
| Optional control logger generates missing-port errors | It watched nonexistent `exhaust.WHISTLE_CONTROL` and called DV's noisy lookup for absent optional ports. Default now uses `whistle.EXT_IN`; old watch entries migrate in memory, preserving the file. Optional reads use the existing read-only port dictionary. | Compiled against installed DV assemblies. Standalone regression checks 330 absent reads, a valid .75 whistle value and null simulation without Unity logging. Revised helper has not been installed. Private-field compatibility is checked, with one explicit message if the dictionary is unavailable. |

The ten duplicate-name whistle cases are A-23, C-40, C-46, F-71, G-16, K-28T, K-35, P-48, S-23 and T-22. The correction is based on component identity and applies to every source, with no per-locomotive offsets.

## Validation receipts

Changed implementation files: `src/rr2dv/build.py` (whistle identity), `buildrecord.py` (tender groups), `record.py` (licence), `unity/Rr2dvPlacement.cs` (glass and HUD), and `tools/dv-control-logger/Main.cs` (optional diagnostics). Regression coverage: `tests/test_build.py`, `tests/test_steam_repairs.py`, `tests/unity_runtime/SteamRepairRegression.cs` and `LoggerPortRegression.cs`. Guidance, ledger and both local boards were updated. Pre-existing catalogue changes are not claimed as new fixes from this pass.

- Focused Python tests: whistle missing/ambiguous fitting, parent/transform preservation and tender pipeline flag passed using the normal Windows Python runtime. The sandbox's stand-in extractor run encountered a file-lock restriction; that was not treated as an application regression.
- Native Unity 2019.4.40f1 / Car Creator 3.1.9: all app scripts compile; four synthetic prefabs export and reload successfully. Receipt: `rr2dv_work/steam-repair-validation/native-out-2/result.json`, `passed=true`, `prefabs=4`, `bundleReload=true`, exit 0. The first native invocation had a missing test-output environment setting; it was corrected before the successful run. The initial sandbox invocation could not access the desktop licence.
- All 21 real source whistle definitions checked without changing game assets. Receipt: `rr2dv_work/steam-repair-validation/fleet-whistle-source-check.json`.
- Logger compiled to the isolated validation folder, not `Mods`. `LoggerPortRegression.exe` passed against the installed game assemblies.
- Full final Python suite: **360 tests run in 312.089 seconds, no failures or errors, 15 optional checks skipped**. Receipt: `rr2dv_work/steam-repair-validation/python-suite-final.log`. Native export/reload validation and logger regression were run separately as described above. The suite includes expected negative CLI argument tests; their usage messages are not failures.
- Pinned app `tooling/` remains unchanged. The offline builder remains separate. The app correction uses the existing core's supported configuration and an app finishing step, not an offline core replacement.

Repeatable native tests are in `tests/test_steam_repairs.py` and `tests/unity_runtime/SteamRepairRegression.cs`. Set `RR2DV_TEST_UNITY` and `RR2DV_TEST_CAR_CREATOR` to opt into the native test. The normal suite skips native tests unless explicitly enabled. No full 21-locomotive conversion or game session was run for this patch.

## Every ledger item accounted for

| Ledger | Disposition after this patch |
|---|---|
| 1 cups on nubs | Open: need full wheel-turn and manual-oiling observations; rest-pose seats do not prove runtime motion/access. |
| 2 clips and tender resource animations | Empty resource groups corrected in source and tested synthetically. All affected exports and the earlier trailing-wheel/window/hatch fixes still need per-loco checks. |
| 3 tender plates | Open: no gameplay mounting/number/orientation evidence yet. |
| 4 coupling | Open: overlap/gap samples identify candidates but not a safe offset. G-25/K-35 require visible mating-point, collider and curve/compression checks; C-25's 88 mm warning remains recorded. |
| 5 tender brake release | Open: six failed seat searches remain unresolved. Clearance alone does not establish bracket support; inspect the real frame before choosing a mount. |
| 6 cup count | Open coverage review; no evidence justifying a fixed cup quota. |
| 7 P-43 reverser | Open: generated control avoids shared-assembly ownership conflict. Need source clip separation and input tests before replacing it. |
| 8 T-21 lever collision | Confirmed sweep warning, still open. Need a measured alternative placement/sweep; no arbitrary relocation made. |
| 9 labels and floating dials | Unsupported labels are evidenced; dial cause remains unresolved. Existing fallback places labels at control depth without support. Need suitable mounting geometry or an explicitly designed bracket, not an invented offset or silent removal. |
| 10 lights/lenses | Open: supplied trace has no off-state test. Need input-to-decoder-to-intensity/emission observation and lens inspection. |
| 11 skinned cords | Open: no animated deformation evidence; K-35 stopgap retained. |
| 12 omitted clips | Open: shared ownership/target mismatches require isolated source clip tests; resource grouping does not automatically fix them. |
| 13 whistle sound swap | Remains parked feature work. This patch only corrects mesh placement. |
| 14 diesels | Remains separate parked 0.3.x work, outside this steam repair. |
| 15 licences | Invalid tank ID corrected and verified against assets. Policy and runtime acceptance remain open. |
| 16 catalogue | Three car types have verified exported pages/icons in the supplied rebuilds; fleet/game appearance still pending. James identified pulling during conversion as a likely cause of stale loaded Python. No release restart guard added. |
| 17 logger errors | Helper source patched and tested; installation and a new game log remain pending. |
| 18 T-22 control behaviour | Retain positive limited evidence. No tuning change justified without timed inputs, mouse/VR and persistence tests. |
| 19 P-18 boiler-water HUD | Fallback added and export-tested; compare actual HUD against the port in game. |
| 20 fitting/material warnings | Open: C-40/P-43 handbrake support and fallback material appearance need model/visual checks. Warning count alone is not a rendering defect. |
| 21 performance/save/external mods | No attributable app cause established. No speculative performance, save or third-party-mod patch. Need an isolated runtime/profile comparison. |
| 22 water-glass offset | Corrected and geometry/export-tested; fleet rebuild, slopes and in-game readings remain pending. |
| 23 moving whistle mesh | Identity lookup corrected; all 21 source definitions checked. In-game lever motion remains pending. |
| 24 all steam fittings/jets | Open fleet acceptance. Correct whistle mesh identity is only part of this requirement. See the specific blocker below. |

## Remaining block and next checks

At the end of the initial six-fix pass, the app's safety-valve position was estimated at the whistle plus 0.1 m. None of the 21 source definitions exposes a component named as a safety/relief/pop valve; T-22's probe hierarchy also has no clearly named safety-valve node. A real outlet must be identified geometrically before changing this estimate. Dynamo pipe direction measurement and upward fallbacks do not prove correct origins. Cylinder-drain anchors and directions also require comparison against physical outlets. No fleet-wide jet correctness is claimed.

The next useful evidence is outlet/model identification for those fittings; T-21's full blower/coal-dump sweep; G-25/K-35's coupling geometry on straight and curved track; and the six uncertain tender release mounts. These are specific unresolved measurements, not permission to guess a location. Lights need an actual off trial. Each resulting correction should get its own regression and in-game check.

For this patch, restart the development app after pulling changes, rebuild the affected packs, and test C-25 coal/water independence, T-22 whistle/body separation, K-28T whistle/licence and P-18 HUD first. Then repeat across the fleet. Existing installed packs have not acquired these changes automatically. James's current builds remain historical evidence, not post-patch results.

## Logger clarification

The logger discussed here is **RR2DVControlLogger, a separate optional Unity Mod Manager diagnostic mod**, whose source is in `tools/dv-control-logger`. It runs inside Derail Valley and produces `rr2dv-controls.log`; it is not embedded in the converter or generated locomotive packs. The converter's own `rr2dv.log` and per-run logs are different.

The helper asked the game's simulation for ports that some locos do not have. DV's `TryGetPort` prints an error on each failed lookup. Its third boolean is named `canBeNullOrEmpty`, not a quiet flag; the earlier investigation's suggested quiet flag was incorrect and is superseded by the verified implementation here. The patch changes optional diagnostic reads and the known mistyped whistle watch entry. It does not alter the simulation, whistle sound or control behaviour. It was compiled/tested in an isolated folder and has not been installed into the game.


## Safety fallback follow-up — 2026-10-02 (X71)

James requested a measured fallback on the highest forward boiler surface, explicitly including boiler domes and excluding other fittings. This supersedes the whistle-plus-0.1 m estimate and the earlier requirement to identify a real valve before offering a fallback. It does not identify a physical safety-valve outlet.

The app now leaves SafetyPos unset until its Unity finishing step probes source geometry. It searches the forward half of the body, at least 0.25 m ahead of the backhead, and stops behind the chimney. It samples a central strip (+/-0.30 m) every 25 mm, requires upward-facing broad support, excludes named fittings and areas around typed bell/whistle/dynamo/compressor anchors, and ignores hidden/lower-LOD meshes. Domes remain eligible. A misleading Cab mesh name is not grounds to discard combined boiler geometry: the cab exclusion is spatial. Explicit supplied safety positions/parts retain priority. The selected jet is 20 mm above the surface, points upwards, and its sound shares that position. The build report records the selected mesh, surface, jet and search range. No supported candidate produces a clear build failure requiring model review.

Validation: 79 relevant Python tests passed (2 optional skips); Unity 2019.4.40f1 native regression passed dome selection, rear-cab/chimney/fitting rejection, misleading Cab names, renderer-state restoration, sound alignment, explicit-position preservation and invalid-region rejection, alongside the existing four-prefab export/reload checks. A separate geometry survey found a candidate for all 21 steam locomotives. Runtime bundle meshes were unreadable, so the survey reconstructed temporary readable meshes from original vertices and triangle indices while preserving the prefab transforms; it did not rebuild or modify installed packs. Receipts: rr2dv_work/steam-repair-validation/safety-out-3 and safety-fleet-geometry-2. Initial unreadable-mesh runs are fixture failures, not evidence of a converter defect.

Limit: this is a geometric fallback with semantic exclusions, not proof that every merged surface is boiler/dome or a valve outlet. K-28T selects a mesh called Tank: inspect that candidate especially before accepting it as boiler/dome placement. Generic combined meshes and P-43's off-centre candidate also need visual inspection. All fleet jet/origin acceptance remains open. Existing packs need rebuilding; no game installation or offline/pinned-core changes were made.

### Survey candidates (surface positions, metres; jet adds 0.020 m vertically)

| Locomotive | Selected mesh | x | y | z |
|---|---|---:|---:|---:|
| ls-440-a23 | Frame_low | 0.000 | 3.876 | 1.787 |
| ls-442-a26 | Boiler_7_LOD0 | -0.000 | 4.463 | 1.160 |
| ls-284-b65 | Boiler_LOD0 | 0.000 | 4.851 | -0.975 |
| ls-280-c25 | Boiler.009_LOD0 | 0.000 | 4.090 | 2.166 |
| ls-480-c40 | Engine_LOD0 | 0.000 | 4.614 | 3.149 |
| ls-280-c46 | Boiler_04_LOD0 | -0.000 | 4.603 | 1.614 |
| ls-280-c55 | Engine_LOD0 | -0.000 | 4.592 | 1.761 |
| ls-2100-d46 | Steam Dome 1 | 0.000 | 4.419 | 2.802 |
| ls-2102-f71 | Boiler_10_LOD0 | -0.000 | 4.637 | -0.416 |
| ls-260-g16 | Boiler.008_LOD0 | 0.000 | 3.753 | 1.682 |
| ls-260-g25 | Boiler | -0.000 | 3.930 | 2.467 |
| ls-282-k28t | Tank | 0.000 | 4.081 | 2.360 |
| ls-282-k35 | Steam Dome.001 | -0.000 | 4.520 | 1.912 |
| ls-462-p18 | Circle.004 | -0.000 | 3.844 | 0.700 |
| ls-462-p43 | Engine_LOD0 | 0.275 | 4.445 | 2.339 |
| ls-462-p48 | Engine_LOD0 | 0.000 | 4.530 | 2.026 |
| ls-060-s23 | Cab_1_LOD0 | -0.000 | 4.192 | 2.018 |
| ls-080-s51 | Boiler.013 | 0.000 | 4.506 | -0.311 |
| ls-460-t17 | Cube.073 | 0.000 | 2.963 | 2.386 |
| ls-460-t21 | Smokebox.005 | 0.000 | 4.336 | 2.161 |
| ls-460-t22 | Engine_LOD0 | -0.000 | 4.112 | 2.468 |
