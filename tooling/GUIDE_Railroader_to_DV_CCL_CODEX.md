> **Canonical location (2026-09-26):** `B:/LLW CONVERT/GUIDE_Railroader_to_DV_CCL_CODEX.md`. Shared board: [GUIDE_SHARED.md](GUIDE_SHARED.md). Current tools: `builder/tools`; profiles: `locos/<profile>/profile`. Historical example paths below are preserved for provenance; use [path mapping](docs/MIGRATION_PATHS.md).

# Railroader → Derail Valley (CCL 3.1.9) conversion guide

> Current route: the shared core is merged under `builder/tools`; S16 uses the generic JSON loader. Historical examples below are superseded where section 11 says otherwise. S16 installation is complete; runtime acceptance is pending.

> **Codex working copy (2026-09-26).** Maintain Codex edits here; read `GUIDE_Railroader_to_DV_CCL.md` and `GUIDE_SHARED.md` for Claude findings, but edit only this guide. C-21: Railroader tender origin -7.445 m is supported by the joint probe; the old -7.057 m setting overlaps the draw gear. See section 9 and `LLW Pilot Workflows/analysis/c21/joint-pin-check-20260926/joint_check.txt` *(claude)*.

Learned converting Railroader (Unity 2022.3 URP) steam locos into working DV CCL locos. Worked examples, each with probes, per-build test notes and a data sheet:
- `Claudes Place\RLW_RBBM1t_Conversion\`: tank loco (2-4-4-2T Mallet).
- `Claudes Place\RLW_RGB2_Conversion\`: tender loco (0-10-0 + separate tender car).
- `Claudes Place\ALCo_Mikado1610_Conversion\`: oil-fired saddle-tank 2-8-2T (section 10); its `tools\` remain the latest oil-burning example.
- `Desktop\LLW CONVERT\LLW Pilot Workflows\`: C-21 tender locomotive. Its `tools\unity\RRPlacementValidation.cs` adds focused source-geometry checks for stock fittings, verified nearby drawbar pins and moving oil-cup anchors (section 9). G-29 remains the general coupling-check reference; these project branches are not yet one merged conversion core.

The reusable builder (in `tools\unity\`):
- `CclLocoBuild.cs`: the generic pipeline, with no loco names in it.
- `LocoConfig.cs`: every per-car setting. An empty section skips that step. A tender is a second config hung off the loco's.
- `<X>Config.cs`: one loco filled in (`RlwConfig.cs`, `RgbConfig.cs`). Run with `tools\run_unity.ps1 -Method <X>Config.Build -Out builds\testN`.

**Starting a new loco:**
1. Run `gen_defs.py` on the new Definitions.json (one C# class per Railroader object: loco, tender).
2. Copy the closest existing config (tank or tender loco).
3. Probe the model (the project's `*Probe.cs`: Run for parts/clips/renders, Backhead for control placement) and fill in part names, positions, clips, stats and control layout.
4. Build, read the report and renders, repeat.
5. Add to the core only what the config can't express, as a new optional config field.

**How to use this:** these are findings and techniques, not a fixed recipe. Check claims against the current DV, CCL and Railroader versions: decompile, probe and render before relying on memory. Every "gotcha" below cost at least one failed in-game test.

---

## 0. Principles that worked
1. **Script everything.** One Unity editor class rebuilds the whole pack from the pristine export every time (~45 s). Never hand-edit prefabs, so every fix is reproducible and diffable.
2. **Verify before you ship:**
   - a build report listing every placement and value, plus warnings
   - renders from fixed cameras
   - targeted probes (gridded orthographic views, mesh-island lists)
   - a build-time check of the saved prefab
3. **Decompile to confirm behaviour.** Use `ilspycmd` on DV `Assembly-CSharp.dll`, `DV.Simulation.dll` and `DV.LayeredAudio.dll`, CCL `CCL.Types.dll` and `CCL.Creator.dll`, and Railroader `Assembly-CSharp.dll`. Most root causes were found in minutes this way.
4. **Borrow from a working CCL loco.** Dump its MonoBehaviours (`tools\dump_ccl_bundle.py`, UnityPy) and copy port ids, joint physics and structure. The reference used was `Mods\4-6-2T` (steam tank, CCL3).
5. **Test loop with the user.**
   - Each build goes into `builds\testN\` with a TEST_NOTES.md checklist.
   - Install to Mods backs up the previous build into `rollback\`.
   - The user plays and sends `Player.log`; read it from the **first exception**.
6. **Keep a data sheet** for stats: every number carries its source (Railroader stated / measured from the model / derived / DV balance).

## 1. Tools and paths (this machine)
| Tool | Use | Notes |
|---|---|---|
| AssetRipper 2.0 (`Desktop\Derail Valley Mods\AssetRipper FREE\AssetRipper.GUI.Free.exe`) | Railroader bundle → Unity project | Headless: `--headless --port N`. HTTP API (below). |
| Unity **2019.4.40f1** (`B:\Games\Unity 2019.4.40f1\Editor\Unity.exe`) | CCL build project | The Personal licence refuses `-batchmode`. Run windowed with `-projectPath P -executeMethod Class.Method -logFile L` and call `EditorApplication.Exit(0)`. A "No valid Unity Editor license" exit after ~10 s is a flake: rerun. |
| CCL CarCreator 3.1.9 (`GWR_1366_CCL_Migration\tooling\CarCreator_3.1.9.unitypackage`) | Proxies and wizards | Extract the tar.gz straight into Assets (keeps GUIDs) instead of importing through the GUI. |
| ilspycmd (`%USERPROFILE%\.dotnet\tools\ilspycmd.exe`) | Decompiling | `-t Type -r <managed dir> <dll>`, `-l c` to list classes, `-p -o dir` for a whole project. |
| Python venv `Claudes Place\.venv312` | PyYAML, UnityPy, opencv-headless | For YAML analysis, CRC32 clip paths, bundle dumps and video frames. |
| csc.exe (.NET Framework 4, `/noconfig /nostdlib+ /langversion:5`) | Small UMM/Harmony helper mods | Template: `DVCCLControlFix\Build.ps1`. langversion 5 has no `?.`, `$""` or `nameof`. The x64 dotnet SDK is at `C:\Program Files\dotnet\dotnet.exe` (PATH points to a broken 32-bit one). |

**AssetRipper API.**
- To read the settings, GET `/Settings/Edit` and read the form.
- To change them, POST `/Reset` first; settings are locked while a file is loaded. Then POST `/Settings/Update` with all the form fields.
- Load with POST `/LoadFile` (field `Path`). Export with POST `/Export/UnityProject` (field `Path`).

## 2. Pipeline
1. **Unpack the Railroader mod zip.** An AssetPack has three parts:
   - `Bundle` (Unity 2022.3, URP)
   - `Catalog.json`
   - `Definitions.json`
2. **Harvest `Definitions.json`** into generated C# constants (`gen_defs.py`, one class per object; a tender loco has loco, tender and truck objects):
   - `pistonDiameterInches`, `pistonStrokeInches`, `maximumBoilerPressure`
   - `totalHeatingSurface`, `weightOnDrivers`, `weightEmpty`
   - `positionHead/Tail`, `couplerHeight`, wheelsets
   - load slots (water gal, coal lb)
   - liveries (tints per colour id; see Materials)
   - the components list: Gauge, SightGlass, Headlight, CylinderCock, Chuff, Whistle, Seat, LoadTarget, RoadNumber decals, coal load and more. These give the positions for the DV substitutes.
3. **AssetRipper export twice:**
   - native, for reference
   - with **`TargetVersion=2019.4.40f1`**, which rewrites the YAML to 2019 format. This is the key trick; no FBX round trip (it broke scale on MAV 475).
4. **Restore animation clip paths.** The export gives `path_0x<crc32>` bindings. Compute zlib CRC32 of every transform path and map them back (`resolve_clip_paths.py`). Clips can belong to different prefabs (loco, tender, trucks), so match each clip against every prefab in the export. Railroader has no Animator; it samples clips by name via its AnimationMap MonoBehaviour.
5. **Set up the build project** (`setup_build_project.ps1`):
   - copy the 2019 export
   - `ProjectVersion` 2019.4.40f1, asset pipeline v1
   - manifest: remove URP, add ugui and textmeshpro
   - extract CarCreator
   - copy the editor scripts
6. **Build in stages** (`CclLocoBuild.Run(config)`):
   1. clips (loopTime on wheel clips)
   2. materials
   3. generated assets (dials, meshes)
   4. `CarWizard.CreateNewCar` (base S060)
   5. exterior (body, colliders, running gear, cab animations, sim, particles)
   6. interior (gauges, controls)
   7. `[interior LOD]` copy
   8. interactables
   9. sound
   10. car type, livery and pack assets
   11. render check
   12. `ExportPackWizard.Export`, then patch Info.json `Requirements`

   Call CCL wizards and proxies by reflection (`T("CCL...")`) and set fields through `SerializedObject` (a `Set(obj, "path", value)` helper).
7. **Install** to `Mods\<Name>` with a timestamped rollback copy.

## 3. Findings by area

### Materials
- **Railroader standard shader** ("Railroader/Standard Car Shader (Shared)") = `_MainTex × _BaseColor`, `_SpecGlossMap`, `_Smoothness`, normal, occlusion. In DV use **Standard (Specular setup)** with the same maps, `_GlossMapScale = _Smoothness`, and the livery tint in `_Color`.
- **URP Lit** → colour only. Transparent glass → premultiplied alpha.
- **Liveries** in Railroader are just tints. The colorizer components say which colour id paints which material: `MaterialColorizerComponent` maps `colorID` → `material.materialName`, `Colorizer` is "base", and one with `material: null` matches renderer materials by name. Colour ids need not equal material names, so build the tint map from the colorizers. Only one livery per loco built so far; the others need separate CCL liveries or `PaintSubstitutions` (not yet tried).

### Animations
- **Driving wheels:** one Animator node per clip ("[anim] name"), holding the clip's top-level objects. `PoweredWheelRotationViaAnimationProxy` sets the float `SpeedMultiplier` = wheel revs per second, so the clip must be exactly one revolution per second and looped.
- **Mallet engines:** each engine unit gets its own animator setup with a `startTimeOffset` (the Railroader phase, here 0.78).
- **Pony trucks:** `WheelRotationViaAnimationProxy` with their own radius.
- **DV bogies on a rigid frame:** DV sees any car as a body on two bogies. For a rigid coupled wheelbase, split the axles over the two bogies and pivot each bogie on its **outermost axle**, so the body follows the chord between the end axles like the real frame. DV's `Bogie` uses `bogie_car/[axle]` only for wheel spin and joint audio, so any axle count (including 1) works; clone `[axle]`s when needed.
- **Railroader trucks** (tenders, carriages) are separate prefabs placed at runtime at ±`truckSeparation`/2, with `CustomTruckComponent` swapping one end for a different truck. Place them yourself and parent each wheelset (pivot on its axle) under the nearest DV `[axle]`: DV spins it using the car type's `wheelRadius`.
- **Port-driven clips** (reverser/valve gear, water level): `AnimatorPortReaderProxy` in `SET_NORMALIZED_TIME` mode does `Play(FloorMod(v·mult + offset, 1))`, so keep the value below 1 (×0.999).
- **`IndicatorGauge` sets an absolute `localRotation`,** so wrap the moving part in an identity pivot. Get the angle and axis by sampling the clip at t=0 and t=end.

### DV substitutes for Railroader runtime features
Railroader spawns these at runtime; DV/CCL needs them built:
- **Gauges:** generated dials and needles plus port readers.
- **Sight glass:** an `IndicatorScaler` on `boiler.WATER_LEVEL_NORMALIZED`.
- **Couplers:** For outer ends without modelled buffers, place the CCL rig **0.309 m outboard of the measured end beam** at coupler height; the CCL importer places the live coupler another 0.249 m outboard. The former `coupling face − 0.30 m` rule buried C-21's front and tender-rear DV hook/chain inside the pilot and end sill. Find the modal beam surface using rays across x ±0.6 m and y `CouplerHeight − 0.20..+0.05 m`, excluding narrow modelled coupler heads; log the beam ray count and check stock hook/chain/cock/hose envelopes. Trim collision and camera boxes past the beam in the coupler band. C-21 0.1.3/test17 builds with beams +5.189/−2.917 m, rigs +5.498/−3.226 m, live anchors +5.747/−3.475 m. Eight source-mesh visual-overlap warnings remain; in-game hook/hose access is pending. The loco–tender drawbar ends still use Railroader car ends and spacing. Evidence: `LLW Pilot Workflows/builds/c21/test17/build_report.txt`, `TEST_NOTES.md` and Claude's C5/C6 in `GUIDE_SHARED.md`.
- **Loco-tender spacing: take it from Railroader, don't guess it.** Railroader keeps coupled car ends exactly `carLength + 1 m` apart (`Car.CouplerSeparation = 1`, `TrainController` adds `carLength + 1f` per car). A car's ends (`LocationF/R`) are the steam loco's `positionHead/Tail`, or ±`length`/2 for other cars and tenders. So the tender origin = loco `positionTail` − 1 m − tender head, and the drawbar plane sits 0.5 m beyond each end. Core: `RrEndRear` (loco) and `RrEndFront` (tender) set the plane and override `CouplingFaceRear/Front`. The model's draw gear then meets as its author drew it; the G-29's castings came out 6 mm apart. A guessed 0.7 m left the G-29 tender 0.3 m too close up to test5.
- **Coupling check** (`CouplingCheck`, "Loco-tender coupling check" in the build report):
  - It lists every mesh part that crosses the joint (drawbars, castings, hoses, fall plates), classified by shape as solid, bar, hose, plate or fitting, and says whether each free end meets the other car.
  - It WARNs if no draw-gear part meets, meaning the cars are too far apart.
  - It WARNs if compact solids overlap, meaning the cars are too close.
  - It repeats the test with the tender ±0.1 and ±0.3 m. On the G-29 only the Railroader spacing passes.
- **Number plates:** at the Railroader RoadNumber decals (on a tender, its RoadName lettering).
- **Cab teleport:** `[cab]` on the floor, found by raycast. Railroader `Seat` positions are not always in the cab; check them against the backhead. `[cab]` also needs a **`teleport_indicator` child: a trigger `BoxCollider` scaled to the cab, with `GrabberRaycastPassThroughProxy`** (as the CCL 4-6-2T and LMS 8F). DV's non-VR teleport pointer ray (`NonVRPointerLogic.ScanForCab`) looks for a collider under the destination; without one the cab never highlights. All conversions up to G-29 test2 lacked it (config `CabTeleportVolume`).
- **Which car is the player in?** DV takes it from the walkable floor under the player's feet (`CharacterReparenting` in `DV.CharacterController.dll`, lowest floor hit first), and the HUD and keyboard follow that car. Behind a short cab floor the tender's deck counts as the tender, so stand at the backhead.
- **Coal load** (Railroader AggregateLoadModel): a box scaled by `coal.AMOUNT`.
- **Particles:** placed at the Railroader anchors.
- **Oil cups:** need **`PositionSyncProvider`s on the body with the same SyncTag.** Without them DV throws `PositionSyncConsumer` NullReferenceExceptions every frame (66k in one log).
- **Modelled moving-bearing cups (C-21 0.1.2 onward).** A reviewed eight-anchor manifest selects the raised cap tops on the two connecting-rod meshes (four each), preserving the original oil-port order and tags. `OilAnchor` records each source path, car-space cap-top position and mesh triangle count. The builder creates each `PositionSyncProviderProxy` below its moving source rod *before* animation-group reparenting; the interactable cups retain the same order and start positions. Offline source-mesh checks matched all eight cap tops within 0.01 mm; Unity post-build sampling confirmed each provider remains on its rod cap and travels about 0.506 m through one wheel revolution. `PositionSyncConsumer.Sync` copies position only, so the stock cup stays upright. The user reports the C-21 cups successful in game; no per-cup access or save/reload record has been supplied. Evidence: `Desktop\LLW CONVERT\LLW Pilot Workflows\analysis\c21\oil-anchors\` and `builds\c21\oilvalidate01\oil_built_validation.txt`; current installed candidate `builds\c21\test17\`.

- **Fleet oiling budgets remain provisional.** The proposed 6/8/10-point LLW layout tiers in `analysis/gameplay-oiling-design-20260926` are a design survey, not a validated build rule. Before reusing them, test actual cup collider access, account for body obstructions, sample more animation phases, and define deterministic selection when the candidate count misses a tier. C-21's eight-point implementation has source-anchor/build checks and user-reported in-game success, but does not validate the fleet-wide selection method.

### Colliders
- `[collision]` must be boxes, or convex colliders on the car rigidbody.
- `[walkable]` and `[items]` can reuse Railroader's non-convex MeshColliders.
- Remove Railroader's colliders from the model itself. Skip any on moving parts (connecting rods can have them); a static copy leaves an invisible platform.
- Add missing steps and ladders; Railroader climbs with "Ladder" components instead.

### Interior, controls and HUD
- **The F4 HUD only mirrors real interior controls and indicators.** It needs a `LocoControlsReaderProxy` and a `LocoIndicatorReaderProxy` (a reference holder: every indicator needs its own port reader), plus `InteractablePortFeederProxy`s. Add keyboard input with `ControlControlsWizard.AddInput`. The ControlType enum: 0 throttle, 1 reverser, 2 train brake, 3 independent, 5 brake cutout, 10/11 headlights front/rear, 12 cab lights, 13 sander, 14 horn, 17 injector, 18 blowdown, 19 blower, 20 damper, 21 fire door, 22 cylinder cocks, 23 compressor, 24 dynamo, 25 lubricator.
- **Port ids** (from the 4-6-2T):
  - `throttle.EXT_IN`, `reverser.CONTROL_EXT_IN`, `brake.EXT_IN`, `indBrake.EXT_IN`, `whistle.EXT_IN`
  - `cylinderCock.EXT_IN`, `injector.EXT_IN`, `blower.EXT_IN`, `damper.EXT_IN`, `blowdown.EXT_IN`, `fireboxDoor.EXT_IN`
  - `coalDumpControl.EXT_IN`, `lubricatorControl.EXT_IN`, `compressorControl.EXT_IN`, `dynamoControl.EXT_IN`
  - `sander.CONTROL_EXT_IN`, `brakeCutout.EXT_IN`, `headlightDecoder.HEADLIGHTS_EXT_IN`
  - indicators: `boiler.PRESSURE`, `steamEngine.STEAM_CHEST_PRESSURE`, `traction.WHEEL_SPEED_KMH_EXT_IN`, `boiler.WATER_LEVEL_NORMALIZED`, `firebox.COAL_LEVEL`, `water/coal/sand/oil.NORMALIZED` (range port `.CAPACITY`)
- **`LeverProxy` physics — critical.** Use `useSteppedJoint=true` with notches plus a holding spring. With the stepped joint off and the default spring on, DV's `LeverBase` resets the spring target to 0 on release, which makes a **spring-return control**: levers snap back, wheels "won't turn", HUD toggles won't stay lit. Only the whistle should be non-stepped. Joint limits are clamped to ±177°.
- **Key/scroll step size.** One tap or scroll moves the lever's target by `notches`-step x `scrollWheelHoverScroll` (DV `LeverBase.ScrollWheelRotate`); 0.3 s after release the stepped joint snaps to the nearest notch. So the per-tap step = 1/(notches-1) of the travel. For 5 %: throttle 21 notches, reverser 41 (the HUD shows it as -100..100 %). **Don't copy the 4-6-2T's angular drag 2e5 on throttle/reverser:** it makes the lever crawl, and a 1-notch tap snaps back before it arrives (the 4-6-2T hides it with 4 notches per tap). Use angular drag 0 with damper ~15 (G-29 test4).
- **Use the tested lever values, including scroll spring.** RGB-2/G-29 throttle: `Phys(0,angle,21,50,15,15,10,0,1,400)`; reverser: `Phys(0,angle,41,85,15,30,15,0,1,200)`; train brake: `Phys(0,angle,11,85,15,30,16,0,1,100)`; independent brake: `Phys(0,angle,11,65,0,30,16,0,1,100)`. For larger 10% key steps, use 11 throttle / 21 reverser detents while keeping these tested physics values. Check the 0.3 s snap in game for each new handle; lever length affects inertia. Keep the whistle spring-return.
- **Collider size.** Put control colliders on the grip only. Control rigidbodies collide with each other, so a long arm's bounding box jammed the regulator at 25%.
- **Railroader's own handles become controls:** axis and range from the clip (t=0 → value 0), hinge pivot projected onto the axis. Remove the exterior copy and let `[interior LOD]` show a static copy.
- **Railroader fittings merged into big meshes** (valve wheels): split out the **mesh island** by union-find over welded vertex positions, nearest to a probe coordinate. Cut it from the exterior mesh and use it as a control.
- **Placing new controls:** raycast onto the backhead with temporary MeshColliders; use a gridded orthographic probe render plus a depth table to find free plate. Users want controls on the backhead (firewall), not the cab sides.
- **Name plates:** `LabelLocalizer` with `ModelType=2` (Offset), key `car/...`, placed as a **sibling** of the control (not a child, or it would rotate with it), with +z into the surface.
- **Doors:** a `LeverProxy` with no port, hinge from the Railroader clip. Remove their static walkable colliders.

### Simulation
- **Starting point:** `SteamerSimCreator.CreateSimForBasis(0)` (S060, tank loco) or `(1)` (S282, tender loco: see Tender locos), then override **every** value from the data sheet. Check `poweredAxles` (S060 gives 3, S282 gives 4). To unhook a basis feature, rewrite its port reference in `SimConnectionsDefinitionProxy.portReferenceConnections`; `portId = ""` is how the S060 basis leaves `boiler.FEEDWATER_TEMPERATURE` unconnected.
- **DV engine maths** (decompiled `ReciprocatingSteamEngine`):
  - mean torque = (p_abs−1)·1e5·A·(2/π)·(S/2)·N, and pulling force = torque / wheel radius
  - there is **no 0.85 factor**, and pressures are **absolute** bar (safety valve 220 psig ≈ 16.2)
  - chuffs per cycle = 2 × numCylinders
  - each cylinder leads by 0.25 turn (1/3 for 3 cylinders)
- **Railroader maths** (`Model.Physics.TrainMath`, `SteamEngine`):
  - **if `publishedTractiveEffort` is set, it *is* the starting pull** (`StartingTractiveEffort` returns it); the formula below is only the fallback. Check the definition first.
  - **`numberOfCylinders` is hard-coded to 2 for every loco, Mallets included**
  - fallback starting pull = 0.85·d²·2·S·P/(2D)
  - speed fall-off follows the TE-to-heating-surface curves
  - grate ≈ 2.3 + 0.000236·TE + 1.427e-8·TE²
  - water use is ~2× real, so don't copy it
  - **Runtime mods change the pull. Check the mod's `info.json` requirements and the definition's `components` for mod-defined kinds.** Lego's Better Steam (`Mods\LegosBetterSteam`, decompiled in RLW `analysis\legos_better_steam`) reads `ArticulatedSteamEngineComponent` (second engine `diamater`/`stroke`, `cylinderType` 0 simple / 1 compound / 2 both = compound with a simpling valve, `baseIsLP`) and replaces the starting pull:
    - base engine: 0.85·P·d²·S/D (simple formula)
    - plus the second engine: simple uses 0.85·P·d²·S/D; compound uses 0.923·(0.85·P·(d·0.2055/D_m·39.37))/2 (its formula, stroke unused)
    - RLW RBBM-1t: 32.4k vanilla → 39.4k compound / 50.8k simple
    - The falloff uses the same heating-surface curves, so pull at speed barely changes; only the low-speed pull rises.
    - `Car.TractiveForceMultiplier` 1.1 is vanilla RR's global balance factor; leave it out.
- **Matching Railroader's pull in DV:** size "equivalent cylinders" so DV's formula gives Railroader's figure. Choose the cylinder count for the exhaust beat you want (beats per turn = 2 × cylinders): a Mallet with 4 cylinders produces 8 beats (verify compatibility with the selected native chuff system before accepting that mapping); a 4-cylinder engine with paired cranks (4 beats) becomes 2 cylinders of the same swept volume, which fits DV's stock chuff slots.
- **Other DV sim facts:**
  - firebox max burn rate = capacity / burnTime; heat = coal × 32 MJ × efficiency
  - boiler volume = πr²·L·capacityMultiplier
  - `waterConsumptionMultiplier` is a DV gameplay fudge (S060 2, S282 4)
- **Mass: use dry mass.** DV adds the mass of all resource containers (water, coal, sand, oil) plus boiler water and firebox coal at runtime (`ResourceContainerController.GetResourcesMass`). Set `CustomCarType.mass` to Railroader's `weightEmpty`, never to its loaded weight.
- **Grip in DV** = wheelslipFrictionCoef × (total weight / axles) × powered axles. Scale the coefficient by Railroader's weight-on-drivers ratio.
- **Licence ids** are DV `GeneralLicenseType` names: `S060`, **`SH282`** (not "S282").
- **HUD `BaseHUD`:** S060=25, S282=20 (numeric speedometer), Custom=1000.

### Lights
- **Structure:** follow CCL's `HeadlightWizard` layout (6 setups per end, index = round(port × 5)). Use the decoder ports `headlightDecoder.FRONT_/REAR_HEADLIGHTS_EXT_IN` and power fuse `fuseboxDummy.ELECTRONICS_MAIN`, which is powered by the dynamo.
- **Setup index 0 must be the main-off setup (no sub-controllers).** `HeadlightsMainController.Init` applies the port value (0) *before* the sub-controllers are initialised. Anything there throws a NullReferenceException that **aborts the whole sim init**.
- **An end with no lamps still needs its 6 setups** (all off). DV indexes them with round(port × (count − 1)), so an empty array throws in `Init`. Likewise never leave a `Light` that no sub-controller switches: it stays on.
- **Lamps with no `Lamp Inside` reflector** (a housing plus glass): put the lens on the glass part.
- **`multipleUnityDependent` = None** on locos without an MU cable.
- **Lamp lenses:** generated discs at the front of each lamp's "Lamp Inside" submesh, with lit/unlit materials. Glare and beam come from the proxy's `CreateDefaultGlare`/`CreateDefaultBeam`, then call `OnValidate`.
- **New sim control** (e.g. `cabLight`, an `ExternalControlDefinitionProxy`): **don't add it to `executionOrder` by hand.** CCL adds it automatically, and a duplicate makes DV's `SimulationFlow` throw "same key" on spawn. Check the saved prefab for duplicate IDs after saving.
- **Firebox lights:** the 3 m point light plus fill and bounce lights lit the whole cab through the backhead. Keep the fire light at ≤0.6 m range inside the firebox, and set the fill and bounce multipliers to 0.

### Audio: native DV S060/S282 aliases

**Required policy, James 2026-09-26 (app board W5/W9):** all conversions use native DV/CCL S060 or S282 audio aliases. Finished packs must load and operate without Railroader installed or any RR runtime libraries, code mods, source bundles or external audio files. Source geometry dependencies are conversion inputs; DV/CCL are the target runtime requirements.

Use the selected family for whistle, bell, chuffs, air pump, dynamo and cylinder cocks. Select **S060 below 1,500 ft2** `totalHeatingSurface`, **S282 at or above 1,500 ft2**. Record the source value and chosen basis. Missing heating surface requires a recorded user choice; an explicit recorded S060/S282 override is allowed. Examples: S16 876 and C21 1,300 => S060; G29 1,735 => S282. Read each loco's definition independently.

Preserve native audio systems and their control/simulation bindings. Check that each required sound responds to its port and plays once. Audio-family selection must not silently change locomotive physics or controls. Every deliverable must contain **zero serialized AudioClips**; audit alias selection and bindings as well as clip count. Validate sound operation, load/spawn and save/reload with RR unavailable before declaring runtime independence. Source-model distribution permissions remain separate.

Current build command: select `-Share`/`--share`, then verify the required family and zero-AudioClip audit explicitly. The flag alone does not establish compliance. Enforcement in code and per-profile compliance still need verification; installed-pack acceptance is tracked in each loco's delivery/status record.

- **Vanilla systems:** `CopyVanillaAudioSystem` ids 3000–3018 (steam systems), 3050 S060 whistle, 3100 S282 whistle. `CopyChuffSystem.LocomotiveType` 0=S060, 1=S282.
- **Chuff slots:** DV's `ChuffClipsSimReader` has one clip slot per beat (S060/S282 = 4). Any other cylinder count throws `IndexOutOfRange` in `OnChuff`, so half the beats go silent.

### Particles
- **Cylinder cocks:** `CylinderCockParticlePortReaderProxy.cylinderSetups` = one entry per sim cylinder (front and rear jets), each gated by that cylinder's inlet-valve bit.
- The CCL template only covers 2 cylinders. For more, clone the jet groups and use CCL's `Curve0/90/180/270`, stepped 90° per cylinder (S282: cylinder 0 = 270/90, cylinder 1 = 0/180). Call `OnValidate`.

### Interactables (freight template)
- `[brake small]` stock handbrake wheel: local **+z faces out of the wall**. Its visible rim and spokes extend in +z, while only its short shaft (to -0.061 m) enters the mount. The prior instruction to point +z into the wall was reversed. Check a 0.208 m rotating radius around the entire rim against the model, not the CCL placeholder.
- `[brake release]` stock rod runs 1.068 m along its local +z to the red puller. Rotate +z toward the side (±90° yaw), place the grey cube/root inside the body, and expose just the red end. Its support extends 0.431 m along local +y; a 180° roll can turn it downward under a low running board. Raycast the *actual* source side at the cube height and the board underside at the red tip, then check both clearances. The placeholder scale is not copied to the runtime fitting.
  - The G-29 bracket height **0.332 m** is the raw mesh extent. The stock `StaticPart` child has y scale **1.3**, yielding **0.431 m** in root-local space; these are the same fitting, not two variants. Check transformed geometry when placing it. Evidence: `LLW Pilot Workflows/analysis/c21/runtime-feedback-20260926/stock_fittings/stock_fittings_geometry.json`.
  - `HandWheel_01` ×2: rim r 0.208 at z +0.04..+0.086, shaft r 0.03 back to −0.062.
- **The core places both from a config hint** (`HandbrakeWheel` / `BrakeRelease` pose, G-29 test6; `*Exact` opts out):
  - **Handbrake wheel:** raycast which way the face looks, sample it ±0.3 m sideways, put the hub on the most protruding point (the crest of a rounded tank end, ignoring thin rails), shaft 22 mm into the mount, rim ≥ 12 mm clear.
  - **Release:** at the hint z (±0.4 m), find the outermost side structure (running board, cab or tank side) and its bottom edge. Take the highest rod height ≥ 0.1 m below it where the valve body is hidden behind a face (frame, sill, ash pan) and the rod runs clear under the car, not over a cab floor. The bracket must fit under what is above it or end outside the cab (the `CabTeleportVolume`). The handle ends 0.15 m out past the edge.
  - The build renders stand-ins of both (`markers_release.png`, `tender_handbrake*.png`, `tender_release.png`).
- Coal: `ShovelCoalPileProxy` trigger; `LocoResourceReceiverProxy` (coal 21, water 20).
- DV has **no water-hatch mechanic**; only the receiver collider matters.

## 4. Debugging in game
- **The rule:** any exception inside `SimController.Initialize` (TrainCar.Awake) silently breaks the whole car: no colliders, no interior, no teleport, no steam, no oil cups. The follow-on errors are `DrivingForce.FixedUpdate` and `SimController.Update` NullReferenceExceptions by the thousand. Find the **first** stack trace after the spawn line (`<CarId>(Clone)`).
- **Harmless noise** here:
  - "Attempted to externally feed port that isn't EXTERNAL_IN" (another mod)
  - "Can't find ControlImplBase on Coal Collider / ignition collider"
  - DVStateProbe, SkinManager and TurboTurbo lines
  - "ItemLight needs light assigned!" then a NullReferenceException in `ItemLightOptimizer.RemoveLight`, from `CabLightsController.Init`. DV adds the `ItemLight` before assigning its light; Unity swallows the error and init continues, but that ItemLight stays disabled. The core now pre-adds CCL's `ItemLightProxy` (light assigned) on the cab light, so DV finds one and logs "Found existing ItemLight" instead (built into RGB-2 test3; not yet confirmed in game).
- **Useful confirmations:** `[DVPositionSyncFix] … real providers N`; `[FiremanAssistant] Water management ready …` means the sim started.
- **Unknown behaviour:** decompile the DV class named in the stack, read it, then fix the build script. Don't hand-patch the output.

## 5. Checklist per test build
- 0 warnings.
- Saved-prefab sim IDs are unique.
- Renders reviewed: exterior, backhead, lamps lit, markers.
- Bundle references only CCL.Types scripts.
- Info.json `Requirements` correct.
- Installed with rollback.
- TEST_NOTES.md lists what changed, what to check, and what's known.

## 6. Tender locos
A Railroader tender (`tenderIdentifier` on the loco; a `kind: Car`, `archetype: Tender` object with the load slots) becomes a **second DV car** in the same pack. Worked example: `RLW_RGB2_Conversion` (`RgbConfig.cs`, in-game tested). Reference CCL loco with a tender: Emeralds LMS 8F (`Mods\Emeralds_LMS_8F`; dump with `dump_ccl_bundle.py` and `dump_ccl_transforms.py`).
- **Creating the cars:** `CarWizard.CreateNewCar` for the loco (Kind Loco, with pack settings) and the tender (Kind `Tender`, `BaseCarType` `S282Tender`, pack settings `null`), then set `pack.Cars` to both. `AssetDatabase.FindAssets` folder filters match by prefix, so check an asset's folder exactly when two car folders share a name start.
- **Sims (CCL creators wire the link):** the loco uses `SteamerSimCreator` basis 1 (S282), which has no coal or water of its own. It reads `tenderWater`/`tenderCoal` ports fed over the coupling by broadcast consumers (`TENDER_*` tags), and broadcasts dynamo flow and headlight settings to the rear. The tender uses `TenderSimCreator` (coal and water containers, coal pile, broadcast providers, headlight consumers, a fuse powered by the loco's dynamo). The S282 basis also adds a superheater and feedwater heater; unhook what the prototype lacked.
- **Coupling:** on the loco root `CarAutoCoupler` (Rear → the other car's Front) and `RigidCoupler` (Rear), both for car kind "Tender"; on the loco `[sim]` a `VirtualHandbrakeOverrider` (Rear, "Tender") with the loco type's `brakes.hasHandbrake = false`; on the tender `KeepCoupledInteriorLoaded` (front). Hide the DV coupler visuals on the drawbar ends (`HideBackCoupler` / `HideFrontCoupler`).
- **Spawning as a pair:** loco livery `TrainsetLiveries` = [loco, tender] and `LocoSpawnGroups` with the tender in `AdditionalLiveries`; call the variant's `ForceValidation()` so the JSON copy is written.
- **HUD:** the loco's tender indicators read `tenderWater`/`tenderCoal` `.NORMALIZED` (range `.CAPACITY`), not `water`/`coal`.
- **Tender interactables:** coal and water receivers at the Railroader `LoadTarget`s, the coal-pile trigger where the fireman shovels, and the handbrake. A Railroader handbrake lever works as a `LeverProxy` with a `HandbrakeFeederProxy` on the same object (DV adds the controller); CCL's `[brake small]` is only a placeholder for DV's stock wheel.

## 7. Open items per project
See each project's latest `builds\testN\TEST_NOTES.md` (and `AUDIT.md` where present) rather than this guide.

## 8. Nested models and third-party Railroader mods
Worked example: `GN_M2_Conversion` (Eilelwen GN M-2 2-6-8-0 Mallet + 8-wheel tender; `GnConfig.cs`, `GnSource.cs`). Its core adds optional `NestedClipGroups`, `MainPressureGauge` and `BodyExtras` fields. It also copies Railroader box and capsule colliders, and matches `CabControlObjects`/`NoWalkParts` by path as well as by name.
- **Clips bound to a child, not the prefab root.** On this pack the `AnimationMap` sits on `Master`, and no clip path resolved (0 of 277) until `resolve_clip_paths.py` also hashed paths relative to the root's children. The build uses prefab copies with Master's children lifted to the root, world pose kept (`GnSource.EnsureFlat`).
- **Deep hierarchies.** Many clips share the same top-level objects, which breaks the flat-model rule of moving each clip's top-level objects under one node at the body root. With `NestedClipGroups`:
  - each clip is split by region (its first two path segments)
  - each region's Animator goes on an identity node under the deepest common parent of its objects
  - that Animator plays a copy of the clip re-rooted to the node

  A reverser clip that moves both engines plus the cab rod becomes three port-driven animators.
- **Wheel clip length.** Check it: these were one revolution over 2.5 s, so the animator state speed is `clip.length` × SpeedMultiplier.
- **Component transforms can be parent-relative** (`parent.path`). Convert them to car space before the core uses them (`GnSource.ResolveComps`). Check the anchors themselves too: the cylinder-cock anchors sat on the centreline.
- **Handle bones may carry long linkages** (a throttle rod to the dome). Group only the handle meshes under a new child node and make that the DV lever. Drive the rest of the clip from the port (`LoadAnimations`, `WhistleLinkageClip`). Clips bind bones only, so the extra node changes no path.
- **Third-party Railroader mods change physics.** `ArticulatedSteamEngineComponent` comes from LegosBetterSteam (`Railroader\Mods\LegosBetterSteam`), not the base game. Its patch on `SteamEngine.CalculateTractiveEffort` adds the second engine's 0.85·P·d²·S/D × simpleMultiplier (Simple mode) to the base figure; for the GN M-2 that doubles the pull to 107,635 lbf. Find which mods define a pack's component kinds before matching pull. The RBBM-1t carries the same component; its pull used the base figure only.
- **LegosLibraryOfStuff** decal groups (heralds, tender text) live outside `Definitions.json`. They can be baked as textured quads (`BodyExtras`); a Unity quad faces −z, as Railroader's decal rotation assumes.
- **Every control the HUD shows must be registered with `LocoControlsReader`,** Railroader-handle levers included; an unwired slot shows a full bar. The S282 basis includes a steam bell (`bellControl`, `bell`), so its HUD has a BELL slot. Wire a bell control (ControlType 15) and audio 3015/3016 (`bell.BELL_NORMALIZED`), or the slot reads full.
- **Two-state controls need a toggle keyboard input** (`RrLeverCfg.Toggle`); otherwise the key does nothing useful. The cylinders blew on the first run because the cocks couldn't be opened.
- **Grab boxes on long parts.** The grip heuristic (points farthest from the axis) takes the whole part when a rod turns about its own length or a bar about its long axis. Set `Grip` explicitly (Railroader `*Control` anchor objects mark the handle). The core now sweeps every lever through its travel against the other controls and warns on a clash. It also reports clashes with cab colliders without warning: DV evidently doesn't collide controls with those, since the throttle passed through the backhead collider in game. Check the `grab_*.png` renders.
- **Ride height:** measure the tread, not the mesh bounds. Railroader wheels are coned, and the lowest point is the flange (M-2: tread r 0.680, flange 0.700). Lower the model so the treads sit at y 0, and use the tread radius as the wheel radius.
- **Mallet articulation:** hang the front engine (and anything on it: pilot truck, headlight setup) under `BogieF/bogie_car` (`ArticulatedParts`). DV turns the bogie to the track, so the unit swings under the boiler. The pivot is mid-unit, not at the real hinge: the wheels stay on the rails and the hinge end swings slightly the other way. `articulation_*.png` shows it with the bogie turned 4°. The RBBM-1t's physics bogies already turn, but its engine meshes are fixed to the body. The same treatment would fix it; it needs a list of the RLW front-unit parts.
- **American locos:**
  - the driver sits on the right
  - there are no buffers: couple at the pilot coupler face and at the drawbar ends (the cab overhangs the drawbar)
  - Railroader may put two gauge faces back to back in one fitting

## 9. One-mesh Blender models, catalog packs and shared parts
Worked example: `LLW_G29_Conversion` (LLW Generic Locomotive Catalog v1.4.3 asset `ls-260-g29` + its tender `lt-260-g29`; `G29Config.cs`). First build: 0 warnings, no exception. Core additions: `ExtraParts`, `SafetyPos`, `BackheadZ`/`FireDoorCentre`, glass-submesh lamps (`path#material`), HUD-only gauges, multi-region wheel clips.
- **A catalog pack holds many cars.** One zip has a folder per loco/tender/parts bundle (`ls-260-g29`, `lt-...`, `g29parts`). The loco's `Catalog.json` lists both `ls-260-g29` and `lt-260-g29` prefabs in one bundle, so the tender comes free; the tender's trucks (`truckIdentifier: fox-truck-2s`) are in a **different mod** (Railroader `Mods\FoxTrucks`). Export that bundle separately (`export_assetripper.ps1 -Bundle ... -OutName export_fox -Port N`) and copy just the prefab and what it references with `tools\copy_deps.py` (GUID walk, scripts skipped, meta kept).
- **Options are separate prefabs.** The loco body has no headlamp or handrail: RR `PrefabModelComponent`s point at `g29parts` prefabs, switched by `ComponentGroup`s. The parts are modelled in car space (their own root pose is already right), so the core instantiates them as-is (`ExtraParts`) and only the chosen option is built (headlight2, handrail, markers). Component `enabled` flags don't say which option RR shows by default.
- **The body is one mesh.** `Cylinder.002` is a single 204k-triangle mesh with 25 materials (boiler, cab, boards, backhead) and one RR MeshCollider hull. Consequences: no part bounds for the firebox, safety valve, or lamp glass, so give explicit values (`BackheadZ`, `FireDoorCentre`, `SafetyPos`); valve wheels are mesh islands of that mesh (`Fittings` with the island centre from the backhead probe); the lens for a lamp modelled as housing + glass in one mesh is the bounds of the triangles of the glass material only (`GlassLamps` entry `path#material`).
- **`Main` = Blender import.** Every animated part sits under `Main` (scale 100, rot -90 X), and every clip shares it. Use `NestedClipGroups`. The Drivers clip splits into 14 regions (one per `Armature.NNN` plus the loose parts under `Main`): **all** of them must go on the wheel proxy's `animatorSetups`, or only the first region (the wheels, no rods) is driven. Same for port-driven clips (`LoadAnimations` now drives every region).
- **AnimationMap keys are not the clip names.** RR's `AnimationMap` key is what RR code calls the clip (`FBDoor` -> FireboxDoor.anim, `Indy` -> LocoBrake, `TB` -> TrainBrake, `Pump` -> AirPump). Configs use the key; check `G29Defs.AnimationMap`.
- **Two source materials can share a name** (the body and the parts pack both have `black`, `metal`, `white`). `AssetDatabase.CreateAsset` at an existing path replaces the file and the first material's renderers go **pink**. The core now gives each converted material a unique file name.
- **Livery colours are `#RGBA`.** `0000` = black, `FFFF` = white (Unity's 4-digit HTML colour), so RR's "Black" livery is a fully black loco and "Lined" (white stripes, maroon roof) is the one that looks like a loco. Colorizers map colour id -> material name; the tint applies to the RR "Standard Car Shader" only.
- **A model with no instrument for a HUD slot.** The Mogul has no speedometer or steam-chest gauge; the core adds invisible `IndicatorGauge`s on `traction.WHEEL_SPEED_KMH_EXT_IN` and `steamEngine.STEAM_CHEST_PRESSURE`, so the HUD slots read something.
- **The RR fire door can be a foot pedal.** Its clip has pedal + two leaves: make the pedal the DV lever (`fireboxDoor.EXT_IN`, toggle) and drive the rest of the clip from the same port.
- **Tender coupling from Railroader's spacing** (section 3; test6). The origin is −3.319 − 1 − 3.875 = −8.194. Up to test5 a guessed 0.7 m gap put it at −7.894: 0.3 m too close, with the draw castings overlapping (seen in game).
  - The tender carries the drawbar: three bars 0.8 m forward from its pins at z 3.786, ending in the loco's pocket.
  - The loco has the rear draw casting, a fall plate onto the tender deck, and feed hoses that run 0.8 m under the tender.
- **Oil cups on the rods (found, not built yet).** The cups you see are separate small upright mesh islands on top of each rod end: 136–176 tris, about 8 × 10 × 8 cm.
  - The side rods have one at each crank pin; the main rod has one on the big end. That makes 8 in all.
  - DV's oil-cup consumers follow their `PositionSyncProvider` every frame, so providers parented to the animated rods can carry the cups.
  - The plan is in G-29 `builds\test6\TEST_NOTES.md` (next steps).
- **Modelled pin/joint alignment.** Identify actual mating geometry before pairing pin-shaped islands. C-21 has no loco pin island: the alleged loco pin was a rear draw casting. At Railroader spacing, tender origin -7.445 m (loco tail -3.395 m, 1 m joint gap, tender head 3.050 m), the castings meet within 4 mm with no solid-overlap cells; the tender pins sit at the rear ends of its drawbars, 314 mm from the loco. At the old -7.057 m offset, the front tender casting lies 385 mm inside the loco casting with 98 solid-overlap cells. C-21 0.1.2 now derives its drawbar planes from `RrEndRear/Front`, and `RRPlacementValidation` only aligns verified nearby pin pairs. Future conversions should also inspect source mesh islands and check draw-gear contact and volume overlap at Railroader spacing. Evidence: `LLW Pilot Workflows/analysis/c21/joint-pin-check-20260926/joint_check.txt` *(claude)* and `builds/c21/test13/build_report.txt`.
- **RR walkable hull = floor.** The `[cab]` floor comes from the RR MeshCollider hull (aisle y 1.496, benches 1.72), not the visual meshes; a downward `RaycastAll` probe (`G29Probe.Floor`) lists both.
- **Pony trucks and the rigid wheelbase.** Pivot the DV bogies on the end *drivers*, not on the pilot wheel: pivoting on the pilot puts the rigid drivers ~5 cm off the rails on a 100 m curve. Give the pilot axle to the front bogie and hang the pilot truck on it (ArticulatedParts) so it swings to the track (G-29 test2).
- **Measure, don't guess, the faces and cup positions.** G29Probe.Faces casts rays along z (buffer beams, drawbars, coupler heads) and down (running-board edge) against the visual meshes only, with the RR hull colliders disabled. The RR hull is what Raycast in the core hits for backhead placement.

## 10. Oil burners, saddle tanks and LegosLibraryOfStuff packs
Worked example: `ALCo_Mikado1610_Conversion` (Greenninja2404's Large ALCo Logging Mikado 2-8-2T, oil fired; `AlcoConfig.cs`, `AlcoSource.cs`). Its `tools\unity\` is the oil-burning example, not the general conversion core. test1: 0 warnings, installed 2026-09-25, not yet tested.
- **Oil firing on a tank loco** (method: `Claudes Place\DV-Oil-Burning.md`, from the 2901). Config `OilFiring`:
  - the car's own `coal` ResourceContainer becomes type Fuel (litres)
  - a CCL `SteamMechanicalStokerDefinition` (`oilBurner`) reads `coal.AMOUNT`/`CONSUME_EXT_IN` and feeds `firebox.COAL_CONTROL_EXT_IN`
  - the valve `oilValve` is an ExternalControl with an OverridableControl of type DynamicBrake (14), so the HUD's dynamic-brake slot and keys drive it; a neutral-state setter closes it
  - no tender bridge ports are needed
- **The stoker idles below 2 bar** (`MIN_WORKING_PRESSURE`) on its STEAM_PRESSURE reference, and the firebox needs fuel before it can be lit. A cold oil burner could therefore never start. The core wires that reference to a constant `atomizer.PRESSURE` port (ConfigurablePort, 10 bar), so the valve feeds from cold. `FromBoiler` gives the steam-driven behaviour instead.
- **Diesel-pump refuelling needs a fuel cap.** DV's service-station `LocoResourceModule` fills either through a raycast onto a `LocoResourceReceiver` (water and coal towers) or through a hose plugged into a socket (the fuel pump). A Fuel container alone is not enough. CCL's importer replaces every car-root child named `[fuel de2]` with the DE2's FuelTankCap, which carries the socket (config `FuelCaps`). DV's own cap poses come from `resources.assets` via UnityPy: DM1U side-wall caps are at x ±1.58 with rot R (-0.5,-0.5,-0.5,0.5), L (-0.5,0.5,0.5,0.5).
- **Atomizer valve** (`OilFiringCfg.AtomizerValveId`): a second ExternalControl drives CCL's `ConstantMultiplierOffsetDefinition` (valve x 10 bar), which is the stoker's STEAM_PRESSURE. With the stoker's `MaxWorkingPressure` 5, the burner is gated by the atomizer: closed = nothing, 1/4 = about 17 %, from 1/2 = full. Its cab wheel is registered as `LocoControlsReader.gearboxA` (`ControlsReaderExtra`): DV's `InteriorControlsManager` maps reader fields to ControlTypes by name, and the HUD's Gearbox A buttons call `MoveScrollable(GearboxA, ±1)`. The HUD slot needs `BasicControls.GearboxA` = Display.
- **DV does not type-check port references** (`SimulationFlow` only warns on port-to-port connections), so COAL-typed stoker references can read a FUEL container.
- **Keep MagicShovelling on an oil burner.** DV's HUD shovel button and `FireboxKeyboardInput` (which also lights the fire) look it up and log errors without it; with the coal pile on the fuel tank, the shovel just primes a chunk of oil. Drop the physical shovel pile and coal receivers instead.
- **Custom HUD** (`HudCustom`): `VanillaHUDLayout.CustomHUDSettings.SetToS()` plus `NonSelfLappingBrakeSetup()`, then "Section.Field" overrides (DynamicBrake for the valve, TenderCoal for the fuel, Shovel/FuelDump off); call `OnValidate` to write its JSON.
- **Clips bound to a wrapper child again** (`Engine`, as the GN M-2's `Master`): flatten it (`AlcoSource.EnsureFlat`). Component parent paths then drop the `Engine/` prefix.
- **Split regions lose children.** A clip may bind an object at depth 2 (`b.r.main/Empty.005`, a driver) and its children (the return cranks). The two-segment region key put them in different regions, and the parent's region moved the object first. `AnimGroups` now keys a path by its shortest bound ancestor.
- **RR parts with no clip become controls** (`RrLeverCfg.Axis/Angle/Pivot`): valve handles, whole handwheel objects. A bone-only path (skinned whistle cord) plus `Grip` gives an invisible control, and the clip moves the cord from the port.
- **Empty glass meshes.** The pack's headlight glass exported with 0 triangles (and the core deletes empty meshes), so lenses come from `LampLenses` at the RR Headlight component's position.
- **LegosLibraryOfStuff packs** keep option groups in `LegosLibraryOfStuff\Definitions\*.json` (`bulkAdds`: PrefabModelComponents, decals, CustomImages). The option prefabs are in the pack's own bundle and are modelled in car space (`ExtraParts`). CustomImage logos are baked as alpha-cutout quads (`BodyExtras`).
- **Saddle tank:** the backhead sits inside the cab (z -4.05) with crew space behind it and beside the boiler. Probe the backhead from a ray start inside the cab (`RayZ`), not from the bunker.
- **Clips that nest, grouped for SimControls** (the roof hatch `Empty.048` and its prop rod `Empty.048/Empty.049` in a second clip): list the child's clip first in `LoadAnimations`. Its animator then goes inside the hatch, which the hatch's own group moves afterwards. In the other order, the hatch has already moved and the rod's host path is gone.

### Cab parts with no DV function (G-29 test5)
Core control fields: `SimControls`, `RrLeverCfg.Hidden`, `Pullers`, `WheelClips`.
- **Doors, windows, vents, hatches:** give each a saved sim control (`SimControls`: an `ExternalControlDefinitionProxy` with `saveState`). A *hidden* DV control (grab box only, no mesh copy) feeds `ID.EXT_IN`, and the RR part **stays on the exterior** and follows the port through its own clip (`LoadAnimations`). It then looks right from outside and with the interior unloaded, and keeps its state across saves. Take the parts off the static walkable colliders (`NoWalkParts`).
- **Sliding parts are DV Pullers.** DV `PullerBase`: a ConfigurableJoint limited along the control's local y, value = |localPosition.y| / (2 x `linearLimit`), pulled towards -y, local pose (0, identity) at value 0 (CCL's validation checks this). So: a slot node at the closed position with its -y along the clip's travel, the control at its origin, `useCustomConnectionAnchor` with the anchor mid-travel. Travel and direction come from the clip (t=0 closed).
- **Control rigidbodies collide with each other**, sliding ones too: two sashes that pass each other need grab boxes that don't overlap across their gap (G-29: 1.8 cm boxes, sashes 2.3 cm apart).
- **RR wheelsets without wheels** (the G-29's 3 m 'Wrench' = lubricator ratchet) are clips that turn with the car: `WheelRotationViaAnimationProxy` at that radius.

## 11. S16: JSON records and scaled source geometry (2026-09-26)

These findings come from editor probes, geometry regression tests and serialized bundle audits. S16 prerelease2 is installed for testing; driving, servicing, save/reload and VR acceptance remain pending. It is not an accepted baseline. Evidence: [build status](locos/s16/analysis/BUILD_STATUS.md), [measurements](locos/s16/profile/S16_MEASUREMENTS.md), [delivery receipt](locos/s16/analysis/delivery.json).

### Current build route

The shared core is now `builder/tools/unity`. S16 is the first authoritative JSON profile, `locos/s16/profile/vehicle-record.json`, loaded by `LlwVehicleRecord.Build`. G29/C21 retain their existing C# entry points; JSON parity for those profiles has not been demonstrated. The older starting recipe above is historical. New records should follow [the schema contract](builder/VEHICLE_RECORD.md), retain reviewed geometry overrides and use the canonical launcher with a fresh run name.

Numeric record values require value/unit/basis/evidence envelopes. Evidence presence is validated; its scientific correctness still needs review. Units are documentation, not automatic conversion. Unknown fields, duplicate keys and invalid values fail rather than being silently ignored. Source-parent positions are baked into car coordinates once. The loader has 18 contract tests; it is not an automatic arbitrary-locomotive measurement system.

### Geometry and interaction lessons

- **Weld tolerance is mesh-local.** S16's Cylinder.018 has scale 100: a 0.0001 local tolerance welds across 10 mm in car space and merges valves into pipes. Its reviewed 0.0000001 override gives 10 micrometres and separates six 592-triangle valve wheels. Cache by source mesh plus tolerance, and retain original mesh identity across SaveMesh/CreateAsset renaming. Test sequential saved cuts, not only temporary meshes. Evidence: `builder/tools/unity/ReviewedMeshIslandRemoval.cs`, `locos/s16/analysis/mesh-weld-tests04` (28 tests).
- **Animated controls must follow the complete source transform.** The tank hatches translate as well as rotate. A transform-only animation rig follows the same saved port and 0.999 normalization as the exterior. Native CCL toggles use no joints, rigidbody or push offset. Five sampled phases per hatch aligned within 0.2 micrometres; runtime save/reload still needs testing. Full-turn bell animation also needs an explicit control angle because quaternion endpoints can be identical. Evidence: `builder/tools/unity/CclLocoBuild.AnimatedToggles.cs`, final `build_report.txt`.
- **Translation is not zero travel.** Source brake links with no endpoint rotation can still slide. Use the slider and brake-cylinder reader on the same node, with measured local start/end positions. Evidence: S16 record and `S16_MEASUREMENTS.md`.
- **Probe height can select the wrong surface.** The default floor ray hit the roof at 3.43 m; a reviewed 2.2 m start inside the cab finds the floor at 1.039 m. Keep missing-hit failures strict. A separate end-beam probe range measures low wooden beams without lowering DV's coupling height. These are profile overrides, not new global heuristics. Evidence: `locos/s16/analysis/measure01/measure_report.txt`, S16 record.
- **Remove source islands only by reviewed identity.** Match centroid, bounds and triangle count within tolerance; never delete merely the nearest island. S16 removed 28 coupling-hardware islands while retaining beams and footboards. Evidence: `locos/s16/analysis/coupler-review`.
- **Judge couplings by usable grab volumes.** James accepts cosmetic coupling-mesh overlap when interaction colliders remain available and not buried. Keep the three exact warnings and their written dispositions. All ten stock grab-target centres were exposed from six sampled approaches. Inspect actual parked chain/hose poses, not only editor placeholders; dynamic hoses and VR reach still require playtesting. Evidence: `profile/warning_dispositions.json`, `analysis/coupler-review/stock_grab_access.json` under S16.
- **Scaled collider probes can produce false intersections.** Tiny local meshes under the source's 100x transform made MeshCollider ray tests report spurious oil-cup collisions. Bake sampled animated geometry into car coordinates on identity probe colliders and cross-check triangles. The actual stock lid opens 90 degrees, not the assumed 180. Six selected cups passed 32 phases x 3 reverser settings = 576 samples with no sampled cup/lid surface crossing. Visibility is not proof of nozzle or VR reach. Evidence: `locos/s16/analysis/oil-screen-test05-six`; final `oil_geometry_fingerprint.json` proves the delivered geometry/animation matches the screen.

### Audit and provenance lessons

For a new loco, use source closure and serialized build gates without inventing a parity baseline. Check actual CCL ports, unique simulation IDs, animation registration, axles/resources, oil tags/order, controls, identity and scripts; each warning needs an exact disposition. A configured simulation field may belong to a sibling controller on the same GameObject as its execution definition. Resolve it uniquely on that exact node; reject missing, ambiguous or unrelated-node matches. Evidence: `builder/tools/unity/NewLocoBuildGate.cs`, `builder/tools/audit_new_loco.py`, `locos/s16/analysis/audit-tests-final.txt` (16 mutation/negative tests).

Do not equate a litre of boiler water to a kilogram. The verified DV 1-bar specific volume is 1.049301 L/kg: S16's 3,040 L contributes 2,897.16678 kg. Its 80,000 lb source mass is explicitly interpreted as operating locomotive mass including boiler water but excluding load slots, giving 33,390.222819 kg dry. This is a documented assumption; heat/fuel calibration still needs driving. Evidence: S16 measurements and `analysis/migration/E04-mass-ledger.md`.

Completed build manifests are immutable. Correct evidence links in a new run, retain prior runs, and verify the installed bundle hash. Prerelease2 was installed on 2026-09-26 using `install_build.py --allow-game`, with a fresh audit and matching hash; see delivery.json for the private receipt. No game acceptance has been inferred from installation.

### App-board decisions and remaining work

James requires complete native S060/S282 audio aliases using the 1,500 ft2 threshold and RR-independent finished packs. See the Audio section for the build and acceptance requirements.

The app now has an AssetRipper extraction stage, but its requested real-machine smoke test (W10) remains outstanding. Our local S16 success does not validate the app pipeline. The published tooling snapshot predates the final S16 changes; a fresh reviewed snapshot is still needed before the app can consume them. Keep game assets, audio, private reports and catalogue records out of the public repository.
