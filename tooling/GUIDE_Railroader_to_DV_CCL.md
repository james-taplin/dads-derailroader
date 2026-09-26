> **Canonical location (2026-09-26):** `B:/LLW CONVERT/GUIDE_Railroader_to_DV_CCL.md`. Shared board: [GUIDE_SHARED.md](GUIDE_SHARED.md). Current tools: `builder/tools`; profiles: `locos/<profile>/profile`. Historical example paths below are preserved for provenance; use [path mapping](docs/MIGRATION_PATHS.md).

# Railroader → Derail Valley (CCL 3.1.9) conversion guide

Learned converting Railroader (Unity 2022.3 URP) steam locos into working DV CCL locos.
- **Part 1** holds what applies to any conversion.
- **Part 2** keeps each loco's own numbers, quirks and history as a worked example. Each example project also has probes, per-build `TEST_NOTES.md` and a data sheet.

**How to use this:** these are findings and techniques, not a fixed recipe. Check claims against the current DV, CCL and Railroader versions: decompile, probe and render before relying on memory. Every "gotcha" below cost at least one failed in-game test.

**Scope and provenance:** Claude maintains this guide. It covers the non-LLW conversions in `Claudes Place\` and the LLW work, which since 2026-09-26 lives in `B:/LLW CONVERT` (G-29 and C-21 are `locos/g29`, `locos/c21`; the old `Claudes Place\LLW_G29_Conversion` and `LLW Pilot Workflows` are archived). Codex keeps its own copy, `GUIDE_Railroader_to_DV_CCL_CODEX.md`, alongside this one. Each reads the other's but edits only its own. Findings taken from Codex's work are marked *(C-21)*; check them against the source before building on them. Messages between the two go in `B:/LLW CONVERT/GUIDE_SHARED.md`. The old `Claudes Place` copy is a redirect, and the board is due to move to the converter app's GitHub repo later.

Oil firing has its own write-up: `Claudes Place\DV-Oil-Burning.md`. Example E only covers how the ALCo used it.

## Contents
**Part 1: General**
1. Principles
2. Tools and paths
3. Builder and pipeline
4. Source model quirks
5. Materials and liveries
6. Running gear and animation
7. Couplers and the loco-tender joint
8. Colliders and the cab
9. Controls and HUD
10. Simulation
11. Lights
12. Audio
13. Particles
14. Stock fittings and servicing
15. Oil cups
16. Tender locos
17. Debugging in game
18. Checklist per test build

**Part 2: Worked examples**
- A. RLW RBBM-1t: tank Mallet
- B. RLW RGB-2: first tender loco
- C. GN M-2: nested model, Mallet, third-party mods
- D. LLW G-29: catalog pack, one-mesh model (current reference core)
- E. ALCo 1610: oil burner, saddle tank
- F. LLW C-21: separate project; joint check

**Open items**

---

# Part 1: General

## 1. Principles
1. **Script everything.** One Unity editor class rebuilds the whole pack from the pristine export every time (~45-75 s). Never hand-edit prefabs, so every fix is reproducible and diffable.
2. **Verify before you ship:**
   - a build report listing every placement and value, plus warnings
   - renders from fixed cameras
   - targeted probes (gridded orthographic views, mesh-island lists)
   - a build-time check of the saved prefab
3. **Decompile to confirm behaviour.** Use `ilspycmd` on DV `Assembly-CSharp.dll`, `DV.Simulation.dll` and `DV.LayeredAudio.dll`, CCL `CCL.Types.dll` and `CCL.Creator.dll`, and Railroader `Assembly-CSharp.dll`. Most root causes were found in minutes this way.
4. **Borrow from a working CCL loco.** Dump its MonoBehaviours (`tools\dump_ccl_bundle.py`, UnityPy) and copy port ids, joint physics and structure. References used: `Mods\4-6-2T` (steam tank, CCL3) and Emeralds LMS 8F (tender loco).
5. **Test loop with the user.**
   - Each build goes into `builds\testN\` with a TEST_NOTES.md checklist.
   - Install to Mods backs up the previous build into `rollback\`.
   - The user plays; read `Player.log` from the **first exception**.
6. **Keep a data sheet** for stats: every number carries its source (Railroader stated / measured from the model / derived / DV balance).
7. **Placement must be deterministic.** Fittings, coupling spacing and control positions come from measured geometry and Railroader's own rules, checked in the build report, never from a hand-tuned number.

## 2. Tools and paths
Paths on this machine: Railroader `B:\SteamLibrary\steamapps\common\Railroader`, DV `B:\SteamLibrary\steamapps\common\Derail Valley`. DV logs: `%USERPROFILE%\AppData\LocalLow\Altfuture\Derail Valley\Player.log` (`Player-prev.log` = previous run).

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

## 3. Builder and pipeline
**The reusable builder** is in each project's `tools\unity\`. The newest is **`LLW_G29_Conversion\tools\unity\`**: start new conversions from it. When another project's core is newer, diff the two (python difflib; there is no git here) and adopt it if it is a superset.
- `CclLocoBuild.cs`: the generic pipeline, with no loco names in it.
- `LocoConfig.cs`: every per-car setting. An empty section skips that step. A tender is a second config hung off the loco's.
- `<X>Config.cs`: one loco filled in. `<X>Source.cs`: source fix-ups (flattening, component transforms). `<X>Probe.cs`: measurements.
- Scripts: `run_unity.ps1 -Method <X>Config.Build -Out builds\testN`, `export_assetripper.ps1 -Bundle/-OutName/-Port`, `copy_deps.py`, `install_build.ps1`.

**Starting a new loco:**
1. Run `gen_defs.py` on the new Definitions.json (one C# class per Railroader object: loco, tender).
2. Copy the closest existing config (tank or tender loco).
3. Probe the model (Run for parts/clips/renders, Backhead for control placement, Faces/Floor for coupling faces and floors) and fill in part names, positions, clips, stats and control layout.
4. Build, read the report and renders, repeat.
5. Add to the core only what the config can't express, as a new optional config field.

**Pipeline:**
1. **Unpack the Railroader mod zip.** An AssetPack has three parts:
   - `Bundle` (Unity 2022.3, URP)
   - `Catalog.json`
   - `Definitions.json`
2. **Harvest `Definitions.json`** into generated C# constants (`gen_defs.py`, one class per object; a tender loco has loco, tender and truck objects):
   - `pistonDiameterInches`, `pistonStrokeInches`, `maximumBoilerPressure`
   - `totalHeatingSurface`, `weightOnDrivers`, `weightEmpty`
   - `positionHead/Tail`, `couplerHeight`, wheelsets
   - load slots (water gal, coal lb)
   - liveries (tints per colour id; see section 5)
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
   11. render check (including the loco-tender coupling check, section 7)
   12. `ExportPackWizard.Export`, then patch Info.json `Requirements`

   Call CCL wizards and proxies by reflection (`T("CCL...")`) and set fields through `SerializedObject` (a `Set(obj, "path", value)` helper).
7. **Install** to `Mods\<Name>` with a timestamped rollback copy.

## 4. Source model quirks
**Hierarchy and clips**
- **Clips bound to a wrapper child, not the prefab root** (`Master`, `Engine`). No clip path resolves until `resolve_clip_paths.py` also hashes paths relative to the root's children. Build from prefab copies with that child's children lifted to the root, world pose kept (`<X>Source.EnsureFlat`). Component parent paths then drop the wrapper prefix.
- **Deep hierarchies.** When many clips share the same top-level objects, the flat-model rule (move each clip's top-level objects under one node at the body root) breaks. With `NestedClipGroups`:
  - each clip is split by region (its first two path segments)
  - each region's Animator goes on an identity node under the deepest common parent of its objects
  - that Animator plays a copy of the clip re-rooted to the node
- **Split regions lose children.** A clip may bind an object at depth 2 and also its children. The two-segment region key put them in different regions, and the parent's region moved the object first. `AnimGroups` now keys a path by its shortest bound ancestor.
- **Clips that nest** (a hatch, and its prop rod in a second clip): list the child's clip first in `LoadAnimations`. Its animator then goes inside the hatch, which the hatch's own group moves afterwards. In the other order, the hatch has already moved and the rod's host path is gone.
- **`Main` = Blender import** (scale 100, rot -90 X): every animated part sits under it and every clip shares it, so use `NestedClipGroups`. A wheel clip then splits into many regions: **all** of them must go on the wheel proxy's `animatorSetups`, or only the first region (the wheels, no rods) is driven. The same goes for port-driven clips (`LoadAnimations` drives every region).
- **Wheel clip length.** Check it: some are one revolution over 2.5 s, so the animator state speed is `clip.length` × SpeedMultiplier.
- **AnimationMap keys are not the clip names.** The key is what RR code calls the clip (`FBDoor` -> FireboxDoor.anim, `Indy` -> LocoBrake, `TB` -> TrainBrake, `Pump` -> AirPump). Configs use the key; check `<X>Defs.AnimationMap`.

**Components and parts**
- **Component transforms can be parent-relative** (`parent.path`). Convert them to car space before the core uses them (`<X>Source.ResolveComps`). Check the anchors themselves too (GN M-2's cylinder-cock anchors sat on the centreline).
- **One-mesh bodies** (a Blender export with the whole loco in one mesh and one hull collider). There are no part bounds for the firebox, safety valve or lamp glass, so give explicit values (`BackheadZ`, `FireDoorCentre`, `SafetyPos`). Valve wheels are mesh islands of that mesh (`Fittings`, with the island centre from the backhead probe). A lamp modelled as housing + glass in one mesh gets its lens from the triangles of the glass material only (`GlassLamps` entry `path#material`).
- **Mesh islands** (union-find over welded vertex positions) are the tool for anything merged into a big mesh: fittings, pins, oil cups, valve wheels.
- **Empty glass meshes.** Glass can export with 0 triangles (and the core deletes empty meshes); take lenses from `LampLenses` at the RR Headlight component's position.

**Packs and libraries**
- **Catalog packs hold many cars.** One zip has a folder per loco, tender and parts bundle. A loco's `Catalog.json` may list its tender's prefab in the same bundle. Trucks can come from a **different mod** (`truckIdentifier`, e.g. Railroader `Mods\FoxTrucks`): export that bundle separately (`export_assetripper.ps1 -Bundle ... -OutName export_fox -Port N`) and copy just the prefab and what it references with `tools\copy_deps.py` (GUID walk, scripts skipped, meta kept).
- **Options are separate prefabs.** Headlamps, handrails and pilots may be RR `PrefabModelComponent`s pointing at a parts bundle, switched by `ComponentGroup`s. They are modelled in car space (their own root pose is already right), so the core instantiates them as-is (`ExtraParts`) and only the chosen option is built. Component `enabled` flags don't say which option RR shows by default.
- **LegosLibraryOfStuff** keeps option groups in `LegosLibraryOfStuff\Definitions\*.json` (`bulkAdds`: PrefabModelComponents, decals, CustomImages), outside the pack's `Definitions.json`. The option prefabs are in the pack's own bundle, in car space (`ExtraParts`). Decal groups (heralds, tender text) and CustomImage logos are baked as textured or alpha-cutout quads (`BodyExtras`); a Unity quad faces −z, as Railroader's decal rotation assumes.
- **Third-party mods change physics** (e.g. LegosBetterSteam). See section 10 before matching pull.

**Measuring**
- **RR walkable hull = floor.** The `[cab]` floor comes from the RR MeshCollider hull, not the visual meshes; a downward `RaycastAll` probe (`<X>Probe.Floor`) lists both. The hull is also what the core's backhead raycast hits.
- **Measure faces and cups against the visual meshes only,** RR hull colliders disabled (`<X>Probe.Faces`: rays along z for buffer beams, drawbars and coupler heads; down for the running-board edge).

## 5. Materials and liveries
- **Railroader standard shader** ("Railroader/Standard Car Shader (Shared)") = `_MainTex × _BaseColor`, `_SpecGlossMap`, `_Smoothness`, normal, occlusion. In DV use **Standard (Specular setup)** with the same maps, `_GlossMapScale = _Smoothness`, and the livery tint in `_Color`.
- **URP Lit** → colour only. Transparent glass → premultiplied alpha.
- **Liveries** in Railroader are just tints. The colorizer components say which colour id paints which material: `MaterialColorizerComponent` maps `colorID` → `material.materialName`, `Colorizer` is "base", and one with `material: null` matches renderer materials by name. Colour ids need not equal material names, so build the tint map from the colorizers. The tint applies to the RR "Standard Car Shader" only.
- **Livery colours are `#RGBA`** (Unity's 4-digit HTML colour): `0000` = black, `FFFF` = white. A livery named "Black" can be a fully black loco; look at the colours before choosing.
- **Two source materials can share a name** (a body and its parts pack both have `black`). `AssetDatabase.CreateAsset` at an existing path replaces the file, and the first material's renderers go **pink**. The core gives each converted material a unique file name.
- Only one livery per loco built so far; the others need separate CCL liveries or `PaintSubstitutions` (not yet tried).

## 6. Running gear and animation
- **Driving wheels:** one Animator node per clip ("[anim] name"), holding the clip's top-level objects. `PoweredWheelRotationViaAnimationProxy` sets the float `SpeedMultiplier` = wheel revs per second, so the clip must be exactly one revolution per second and looped.
- **Mallet engines:** each engine unit gets its own animator setup with a `startTimeOffset` (the Railroader phase).
- **Mallet articulation:** hang the front engine (and anything on it: pilot truck, headlight setup) under `BogieF/bogie_car` (`ArticulatedParts`). DV turns the bogie to the track, so the unit swings under the boiler. The pivot is mid-unit, not at the real hinge: the wheels stay on the rails and the hinge end swings slightly the other way. Check it with the bogie turned 4° (`articulation_*.png`).
- **DV bogies on a rigid frame:** DV sees any car as a body on two bogies. For a rigid coupled wheelbase, split the axles over the two bogies and pivot each bogie on its **outermost driver**, so the body follows the chord between the end drivers like the real frame. DV's `Bogie` uses `bogie_car/[axle]` only for wheel spin and joint audio, so any axle count (including 1) works; clone `[axle]`s when needed.
- **Pony trucks:** `WheelRotationViaAnimationProxy` with their own radius. Don't pivot a bogie on the pilot wheel (the rigid drivers end up ~5 cm off the rails on a 100 m curve): give the pilot axle to the front bogie and hang the pilot truck on it (`ArticulatedParts`) so it swings to the track.
- **Railroader trucks** (tenders, carriages) are separate prefabs placed at runtime at ±`truckSeparation`/2, with `CustomTruckComponent` swapping one end for a different truck. Place them yourself and parent each wheelset (pivot on its axle) under the nearest DV `[axle]`: DV spins it using the car type's `wheelRadius`.
- **RR wheelsets without wheels** (e.g. a lubricator ratchet) are clips that turn with the car: `WheelRotationViaAnimationProxy` at that wheelset's radius.
- **Ride height:** measure the tread, not the mesh bounds. Railroader wheels are coned, and the lowest point is the flange. Lower the model so the treads sit at y 0, and use the tread radius as the wheel radius.
- **Port-driven clips** (reverser/valve gear, water level): `AnimatorPortReaderProxy` in `SET_NORMALIZED_TIME` mode does `Play(FloorMod(v·mult + offset, 1))`, so keep the value below 1 (×0.999).
- **`IndicatorGauge` sets an absolute `localRotation`,** so wrap the moving part in an identity pivot. Get the angle and axis by sampling the clip at t=0 and t=end.

## 7. Couplers and the loco-tender joint
- **DV couplers** rig at height 1.05; hide DV buffers and hook plates when the model has its own.
- **Outer ends with no modelled buffers (US knuckle couplers): rig = measured end beam + 0.309 m** (core `RigOnEndBeam`, G-29 test8). The old rule, "0.30 m inboard of the coupling face", buries DV's hook, screw chain, air hose and cut-out cock inside the pilot or end sill, because they all hang 0.13–0.36 m **inboard** of the rig. The C-21 couldn't use any of them in game.
  - DV's own geometry (CarFlatcar, whose rig CCL builds for custom buffers; `resources.assets`): end beam 8.467, hook plate 8.514, rig 8.776. So the beam is 0.309 m inboard of the rig.
  - CCL `CarPartOffset`: live coupler at the rig ±0.249; hook plate at the rig (0, −0.078, ∓0.332); buffer pads at the rig ±0.2145.
  - Hardware in rig space (front): hook z −0.324..+0.012, y −0.233..−0.006; chain and screw hang to y −0.59; cock valve x −0.47..−0.33, z −0.31..−0.12; hose rig at (−0.383, −0.087, −0.173). Rear rigs are mirrored in x and z.
  - Finding the beam: rays along z at x −0.6..0.6, y 0.85..1.10. Take the z that most rays stop at (1 cm bins), so a narrow modelled coupler head doesn't count as the beam.
  - Checks: the build warns about any model part more than 20 mm out from the beam inside the hook, chain, cock or hose boxes. It also trims collision boxes that run past the beam across the coupler area.
  - The result lands close to Railroader's own coupled spacing (end ± 0.5 m). G-29: live coupler 5.733 vs 5.85 at the front, −4.296 vs −4.375 at the tender rear.
  - Models with buffers keep the buffer-face rule. Drawbar ends keep Railroader's spacing.
- **Don't use Railroader's `positionHead/Tail`** (or ±length/2 for cars) **as the coupling face:** they sit ~0.5 m inside the car ends because Railroader draws knuckle couplers beyond them. Use a physical face: buffer faces, or on American locos (no buffers) the pilot coupler face.
- **Loco-tender spacing: take it from Railroader, don't guess it.** Railroader keeps coupled car ends exactly `carLength + 1 m` apart (`Car.CouplerSeparation = 1`, `TrainController` adds `carLength + 1f` per car). A car's ends (`LocationF/R`) are the steam loco's `positionHead/Tail`, or ±`length`/2 for other cars and tenders. So:
  - tender origin = loco `positionTail` − 1 m − tender head
  - the drawbar plane sits 0.5 m beyond each end
  - core: `RrEndRear` (loco) and `RrEndFront` (tender) set the plane and override `CouplingFaceRear/Front`

  The model's draw gear then meets as its author drew it (Examples D and F).
- **Coupling check** (`CouplingCheck`, "Loco-tender coupling check" in the build report), at the coupled position, against the visual meshes:
  - **Joint parts:** every mesh part that crosses the joint (drawbars, castings, hoses, fall plates), classified by shape as solid, bar, hose, plate or fitting, and whether each free end meets the other car. It WARNs if no draw-gear part meets, meaning the cars are too far apart.
  - **Solid overlap:** it WARNs if compact solids overlap, meaning the cars are too close.
  - **Drawbar pins:** it finds vertical pin-shaped islands near the joint on both cars and gives each one's distance to the other car. A loco pin and a tender pin within 0.5 m of each other are taken as one pin modelled on both cars; if such a pair is more than 30 mm out of line, it WARNs and says how far to move the tender. Pins further apart are different pins (the two ends of a drawbar).
  - **Sensitivity:** it repeats the test with the tender ±0.1 and ±0.3 m.
- **Don't line up pins that aren't the same pin.** On the LLW catalog tenders (G-29, C-21) the tender carries the drawbar. Its three pins are at the bar's rear end, on the tender. The bars run about 0.8 m forward under or into the loco's draw casting, and the loco has no pin of its own there. Pinning the tender's pins onto the loco's casting put the C-21 tender 0.39 m too close, with the two castings overlapping (Example F). Railroader's spacing is the rule; the pin check only confirms it where both cars really model the same pin.

## 8. Colliders and the cab
- `[collision]` must be boxes, or convex colliders on the car rigidbody.
- `[walkable]` and `[items]` can reuse Railroader's non-convex MeshColliders.
- Remove Railroader's colliders from the model itself. Skip any on moving parts (connecting rods can have them); a static copy leaves an invisible platform.
- Add missing steps and ladders; Railroader climbs with "Ladder" components instead.
- **Cab teleport:** `[cab]` on the floor, found by raycast. Railroader `Seat` positions are not always in the cab; check them against the backhead. `[cab]` also needs a **`teleport_indicator` child: a trigger `BoxCollider` scaled to the cab, with `GrabberRaycastPassThroughProxy`** (as the CCL 4-6-2T and LMS 8F; config `CabTeleportVolume`). DV's non-VR teleport pointer ray (`NonVRPointerLogic.ScanForCab`) looks for a collider under the destination; without one the cab never highlights.
- **Which car is the player in?** DV takes it from the walkable floor under the player's feet (`CharacterReparenting` in `DV.CharacterController.dll`, lowest floor hit first), and the HUD and keyboard follow that car. Behind a short cab floor the tender's deck counts as the tender, so stand at the backhead.
- **Backhead probing:** start the ray inside the cab (`RayZ`/`BackheadRayStartZ`), not from behind it. On a saddle tank the backhead sits inside the cab with crew space behind it and beside the boiler.

## 9. Controls and HUD
**HUD wiring**
- **The F4 HUD only mirrors real interior controls and indicators.** It needs a `LocoControlsReaderProxy` and a `LocoIndicatorReaderProxy` (a reference holder: every indicator needs its own port reader), plus `InteractablePortFeederProxy`s. Add keyboard input with `ControlControlsWizard.AddInput`. The ControlType enum: 0 throttle, 1 reverser, 2 train brake, 3 independent, 5 brake cutout, 10/11 headlights front/rear, 12 cab lights, 13 sander, 14 horn, 15 bell, 17 injector, 18 blowdown, 19 blower, 20 damper, 21 fire door, 22 cylinder cocks, 23 compressor, 24 dynamo, 25 lubricator.
- **Every control the HUD shows must be registered with `LocoControlsReader`,** Railroader-handle levers included; an unwired slot shows a full bar. The S282 basis includes a steam bell (`bellControl`, `bell`), so its HUD has a BELL slot: wire a bell control (ControlType 15) and audio 3015/3016 (`bell.BELL_NORMALIZED`), or the slot reads full.
- **DV maps reader fields to ControlTypes by name** (`InteriorControlsManager`). An extra control can take a spare HUD slot by being registered under that field (`ControlsReaderExtra`, e.g. `gearboxA`); the slot also needs showing in the HUD settings.
- **Custom HUD** (`HudCustom`): `VanillaHUDLayout.CustomHUDSettings.SetToS()` plus `NonSelfLappingBrakeSetup()`, then "Section.Field" overrides; call `OnValidate` to write its JSON.
- **A model with no instrument for a HUD slot** (no speedometer or steam-chest gauge): add invisible `IndicatorGauge`s on `traction.WHEEL_SPEED_KMH_EXT_IN` and `steamEngine.STEAM_CHEST_PRESSURE` so the HUD slots read something.
- **Port ids** (from the 4-6-2T):
  - `throttle.EXT_IN`, `reverser.CONTROL_EXT_IN`, `brake.EXT_IN`, `indBrake.EXT_IN`, `whistle.EXT_IN`
  - `cylinderCock.EXT_IN`, `injector.EXT_IN`, `blower.EXT_IN`, `damper.EXT_IN`, `blowdown.EXT_IN`, `fireboxDoor.EXT_IN`
  - `coalDumpControl.EXT_IN`, `lubricatorControl.EXT_IN`, `compressorControl.EXT_IN`, `dynamoControl.EXT_IN`
  - `sander.CONTROL_EXT_IN`, `brakeCutout.EXT_IN`, `headlightDecoder.HEADLIGHTS_EXT_IN`
  - indicators: `boiler.PRESSURE`, `steamEngine.STEAM_CHEST_PRESSURE`, `traction.WHEEL_SPEED_KMH_EXT_IN`, `boiler.WATER_LEVEL_NORMALIZED`, `firebox.COAL_LEVEL`, `water/coal/sand/oil.NORMALIZED` (range port `.CAPACITY`)

**Lever physics and feel**
- **`LeverProxy` physics: critical.** Use `useSteppedJoint=true` with notches plus a holding spring. With the stepped joint off and the default spring on, DV's `LeverBase` resets the spring target to 0 on release, which makes a **spring-return control**: levers snap back, wheels "won't turn", HUD toggles won't stay lit. Only the whistle should be non-stepped. Joint limits are clamped to ±177°.
- **Key/scroll step size.** One tap or scroll moves the lever's target by `notches`-step x `scrollWheelHoverScroll` (DV `LeverBase.ScrollWheelRotate`); 0.3 s after release the stepped joint snaps to the nearest notch. So the per-tap step = 1/(notches-1) of the travel. The user wants about 4-5 % per tap: throttle 21 notches, reverser 41 (the HUD shows it as -100..100 %). **Don't copy the 4-6-2T's angular drag 2e5 on throttle/reverser:** it makes the lever crawl, and a 1-notch tap snaps back before it arrives (the 4-6-2T hides it with 4 notches per tap). Use angular drag 0 with damper ~15.
- **Tested lever values, including scroll spring** (RGB-2/G-29). Throttle: `Phys(0,angle,21,50,15,15,10,0,1,400)`; reverser: `Phys(0,angle,41,85,15,30,15,0,1,200)`; train brake: `Phys(0,angle,11,85,15,30,16,0,1,100)`; independent brake: `Phys(0,angle,11,65,0,30,16,0,1,100)`. For 10 % key steps use 11 throttle / 21 reverser detents with the same physics. Check the 0.3 s snap in game for each new handle; lever length affects inertia. Keep the whistle spring-return.
- **Two-state controls need a toggle keyboard input** (`RrLeverCfg.Toggle`); otherwise the key does nothing useful (GN M-2's cylinders blew on the first run because the cocks couldn't be opened).

**Grab boxes and collisions**
- **Put control colliders on the grip only.** Control rigidbodies collide with each other (sliding ones too), so a long arm's bounding box jammed a regulator at 25 %, and two sashes that pass each other need grab boxes that don't overlap across their gap.
- **Grab boxes on long parts.** The grip heuristic (points farthest from the axis) takes the whole part when a rod turns about its own length or a bar about its long axis. Set `Grip` explicitly (Railroader `*Control` anchor objects mark the handle). The core sweeps every lever through its travel against the other controls and warns on a clash. It also reports clashes with cab colliders without warning: DV evidently doesn't collide controls with those. Check the `grab_*.png` renders.

**Making controls from Railroader parts**
- **Railroader's own handles become controls:** axis and range from the clip (t=0 → value 0), hinge pivot projected onto the axis. Remove the exterior copy and let `[interior LOD]` show a static copy.
- **Handle bones may carry long linkages** (a throttle rod to the dome). Group only the handle meshes under a new child node and make that the DV lever. Drive the rest of the clip from the port (`LoadAnimations`, `WhistleLinkageClip`). Clips bind bones only, so the extra node changes no path.
- **RR parts with no clip** (valve handles, whole handwheel objects) become controls with `RrLeverCfg.Axis/Angle/Pivot`. A bone-only path (a skinned whistle cord) plus `Grip` gives an invisible control, and the clip moves the cord from the port.
- **Fittings merged into big meshes** (valve wheels): split out the **mesh island** nearest to a probe coordinate, cut it from the exterior mesh and use it as a control.
- **A fire door worked by a foot pedal:** make the pedal the DV lever (`fireboxDoor.EXT_IN`, toggle) and drive the rest of the clip (the leaves) from the same port.

**Doors, windows, vents, hatches** (core fields `SimControls`, `RrLeverCfg.Hidden`, `Pullers`)
- Give each a saved sim control (`SimControls`: an `ExternalControlDefinitionProxy` with `saveState`). A *hidden* DV control (grab box only, no mesh copy) feeds `ID.EXT_IN`, and the RR part **stays on the exterior** and follows the port through its own clip (`LoadAnimations`). It then looks right from outside and with the interior unloaded, and keeps its state across saves. Take the parts off the static walkable colliders (`NoWalkParts`).
- **Sliding parts are DV Pullers.** DV `PullerBase`: a ConfigurableJoint limited along the control's local y, value = |localPosition.y| / (2 x `linearLimit`), pulled towards -y, local pose (0, identity) at value 0 (CCL's validation checks this). So: a slot node at the closed position with its -y along the clip's travel, the control at its origin, `useCustomConnectionAnchor` with the anchor mid-travel. Travel and direction come from the clip (t=0 closed).

**Placing new controls and labels**
- Raycast onto the backhead with temporary MeshColliders; use a gridded orthographic probe render plus a depth table to find free plate. Users want controls on the backhead (firewall), not the cab sides.
- American locos: the driver sits on the right. Railroader may put two gauge faces back to back in one fitting.
- **Name plates:** `LabelLocalizer` with `ModelType=2` (Offset), key `car/...`, placed as a **sibling** of the control (not a child, or it would rotate with it), with +z into the surface.

## 10. Simulation
- **Starting point:** `SteamerSimCreator.CreateSimForBasis(0)` (S060, tank loco) or `(1)` (S282, tender loco: see section 16), then override **every** value from the data sheet. Check `poweredAxles` (S060 gives 3, S282 gives 4). To unhook a basis feature, rewrite its port reference in `SimConnectionsDefinitionProxy.portReferenceConnections`; `portId = ""` is how the S060 basis leaves `boiler.FEEDWATER_TEMPERATURE` unconnected.
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
  - `Car.TractiveForceMultiplier` 1.1 is vanilla RR's global balance factor; leave it out.
- **Runtime mods change the pull.** Check the mod's `info.json` requirements and the definition's `components` for mod-defined kinds. `ArticulatedSteamEngineComponent` comes from LegosBetterSteam (`Railroader\Mods\LegosBetterSteam`, decompiled in RLW `analysis\legos_better_steam`), not the base game. It reads the second engine's `diamater`/`stroke`, `cylinderType` (0 simple / 1 compound / 2 both = compound with a simpling valve) and `baseIsLP`, and replaces the starting pull (patch on `SteamEngine.CalculateTractiveEffort`):
  - base engine: 0.85·P·d²·S/D (simple formula)
  - plus the second engine: simple uses 0.85·P·d²·S/D × simpleMultiplier; compound uses 0.923·(0.85·P·(d·0.2055/D_m·39.37))/2 (its formula, stroke unused)
  - the falloff uses the same heating-surface curves, so pull at speed barely changes; only the low-speed pull rises.
- **Matching Railroader's pull in DV:** size "equivalent cylinders" so DV's formula gives Railroader's figure. Choose the cylinder count for the exhaust beat you want (beats per turn = 2 × cylinders): a Mallet keeps 4 cylinders (8 beats, needs the audio mod in section 12); a 4-cylinder engine with paired cranks (4 beats) becomes 2 cylinders of the same swept volume, which fits DV's stock chuff slots.
- **Other DV sim facts:**
  - firebox max burn rate = capacity / burnTime; heat = coal × 32 MJ × efficiency
  - boiler volume = πr²·L·capacityMultiplier
  - `waterConsumptionMultiplier` is a DV gameplay fudge (S060 2, S282 4)
  - DV does not type-check port references (`SimulationFlow` only warns on port-to-port connections)
- **Mass: use dry mass.** DV adds the mass of all resource containers (water, coal, sand, oil) plus boiler water and firebox coal at runtime (`ResourceContainerController.GetResourcesMass`). Set `CustomCarType.mass` to Railroader's `weightEmpty`, never to its loaded weight.
- **Grip in DV** = wheelslipFrictionCoef × (total weight / axles) × powered axles. Scale the coefficient by Railroader's weight-on-drivers ratio.
- **Licence ids** are DV `GeneralLicenseType` names: `S060`, **`SH282`** (not "S282").
- **HUD `BaseHUD`:** S060=25, S282=20 (numeric speedometer), Custom=1000.
- **Oil firing:** see `DV-Oil-Burning.md` and Example E.
- **Realism pass** (G-29 pre-release 1, Example D). Work from the loco's size and real prototypes, never DV's gameplay defaults:
  - **Prototype:** Railroader gives cylinders, pressure, drivers, heating surface and weights. LLW catalog class numbers are the starting TE in thousands of lbf (C-21 20,994, G-29 29,363 lbf). Its builder's photos (`llw-builderphotos` textures) show a fictional builder, so fill the gaps from real classes of the same size (Locobase, steamlocomotive.com: grate, evaporative surface, tender).
  - **Pull:** size the DV bore so DV's pull (no 0.85 factor) equals the rated 0.85·P·d²·S/D. The stroke stays real.
  - **Steaming:** the target is max evaporation (saturated ~11–12 lb/sq ft/h of heating surface; superheated less per sq ft but more work per lb). DV makes 32 MJ/kg × efficiencyAtMaxCombustion 0.5 = 16 MJ/kg of heat, so max burn (capacity / burnTime) = steam kg/s × ~2.68 MJ / 16 MJ. For hand firing, check it is ≤ ~120 lb/sq ft of grate/h. Fire bed capacity: DV's S282 has 2.25 kg per sq ft of grate.
  - **Boiler:** set `capacityMultiplier` so πr²L equals the real water + steam space (barrel less tubes, plus firebox legs); spawn water ≈ 76% of it. Take the car's dry mass as working-order weight minus that water.
  - **Other figures:** injector ~1.4× max evaporation, in L/s. Safety valves at P and P − 3 psi, converted to absolute bar. Consumption multipliers 1 (real coal and water use; DV's own 2–4× are gameplay).
  - Log the derivation in the SimSpec `_notes` so the build report shows where each figure came from.

## 11. Lights
- **Structure:** follow CCL's `HeadlightWizard` layout (6 setups per end, index = round(port × 5)). Use the decoder ports `headlightDecoder.FRONT_/REAR_HEADLIGHTS_EXT_IN` and power fuse `fuseboxDummy.ELECTRONICS_MAIN`, which is powered by the dynamo.
- **Setup index 0 must be the main-off setup (no sub-controllers).** `HeadlightsMainController.Init` applies the port value (0) *before* the sub-controllers are initialised. Anything there throws a NullReferenceException that **aborts the whole sim init**.
- **An end with no lamps still needs its 6 setups** (all off). DV indexes them with round(port × (count − 1)), so an empty array throws in `Init`. Likewise never leave a `Light` that no sub-controller switches: it stays on.
- **Lamp lenses:** generated discs at the front of each lamp's "Lamp Inside" submesh, with lit/unlit materials. Lamps with no reflector (a housing plus glass) get the lens on the glass part (section 4: glass-material lamps, empty glass). Glare and beam come from the proxy's `CreateDefaultGlare`/`CreateDefaultBeam`, then call `OnValidate`.
- **`multipleUnityDependent` = None** on locos without an MU cable.
- **New sim control** (e.g. `cabLight`, an `ExternalControlDefinitionProxy`): **don't add it to `executionOrder` by hand.** CCL adds it automatically, and a duplicate makes DV's `SimulationFlow` throw "same key" on spawn. Check the saved prefab for duplicate IDs after saving.
- **Cab light:** pre-add CCL's `ItemLightProxy` (light assigned) on it, or DV's `CabLightsController.Init` logs "ItemLight needs light assigned!" and leaves the light disabled (section 17).
- **Firebox lights:** a 3 m point light plus fill and bounce lights lit the whole cab through the backhead. Keep the fire light at ≤0.6 m range inside the firebox, and set the fill and bounce multipliers to 0.

## 12. Audio
**DV systems**
- **Vanilla systems:** `CopyVanillaAudioSystem` ids 3000–3018 (steam systems), 3050 S060 whistle, 3100 S282 whistle. `CopyChuffSystem.LocomotiveType` 0=S060, 1=S282.
- **Chuff slots:** DV's `ChuffClipsSimReader` has one clip slot per beat (S060/S282 = 4). Any other cylinder count throws `IndexOutOfRange` in `OnChuff`, so half the beats go silent.
- **No pitch control in CCL.** Use a tiny Harmony mod (`audio_mod\`):
  - prefix `ChuffClipsSimReader.Init`: extend the clip slots, multiply `*ChuffConfig.pitch`, and `chuffLoop.PitchMultiply`
  - postfix `LayeredAudioPortReader.Init`: `layeredAudio.PitchMultiply` for the whistle
  - filter on `car.carLivery.parentType.id`, apply once per instance, and list the mod in the pack's Info.json `Requirements`

**Railroader's own sounds** (core fields `Sounds`, `RemoveVanillaSounds`)
- RR *synthesises* its chuffs (`Audio.DynamicChuff`), so there is nothing to copy; keep DV's chuffs.
- The whistle is one clip per `defaultWhistleIdentifier` (base game `Railroader_Data\StreamingAssets\AssetPacks\audio.whistles01`, or a whistle mod such as Greenninja's Whistles), looped at runtime by `AudioUtilities.Loopify` (second half + start, 4096-sample crossfade) with pitch ramping 0.9 -> 1 (`WhistlePlayer`).
- **An empty `defaultWhistleIdentifier` is not silent.** RR's `WhistleCustomizationSettings` falls back to `wh-5-drg-st` (5-chime, `audio.whistles01`); it does the same for `a.w.default`.
- The bell, steam air pump and dynamo are single looped clips in `sharedassets3.assets` (CNR brass rope bell, TVRM compressor, TVRM dynamo).
- Extract with UnityPy (`tools\extract_rr_audio.py <out> [names]`), loopify offline (`tools\loopify_wav.py`).
- These are game assets: fine in your own install, don't publish a pack containing them.

**Custom looped sound in CCL:** `LayeredAudioProxy` (type Continuous, mixer group) + one child layer with an `AudioSource` (clip, loop) and `AudioLayerProxy` (volume/pitch curves over the port value, `source`), plus a `LayeredAudioPortReaderProxy` (portId) on the same object. DV plays a layer while its volume >= 0.01.
- Ports: whistle `exhaust.WHISTLE_FLOW_NORMALIZED`, bell `bell.BELL_NORMALIZED` (1 while ringing, then smooths to 0), air pump `compressor.PRODUCTION_RATE_NORMALIZED`, dynamo `dynamo.DYNAMO_FLOW_NORMALIZED`.
- Mixer groups (CCL `DVAudioMixerGroup`): Horn 12, Compressor 21, Engine 7, Cab 3.

## 13. Particles
- Placed at the Railroader anchors (check them: section 4).
- **Cylinder cocks:** `CylinderCockParticlePortReaderProxy.cylinderSetups` = one entry per sim cylinder (front and rear jets), each gated by that cylinder's inlet-valve bit.
- The CCL template only covers 2 cylinders. For more, clone the jet groups and use CCL's `Curve0/90/180/270`, stepped 90° per cylinder (S282: cylinder 0 = 270/90, cylinder 1 = 0/180). Call `OnValidate`.

## 14. Stock fittings and servicing
**DV's stock handbrake wheel** (`[brake small]`; DV `HandWheel_01`)
- Local **+z faces out of the wall**. The rim (r 0.208) sits at z +0.04..+0.086 and the spokes extend in +z; only the short shaft (r 0.03, back to −0.062) enters the mount.
- Check the 0.208 m rotating radius around the whole rim against the model, not the CCL placeholder.

**DV's stock brake release** (`[brake release]`; `BrakeCylinderRelease` mesh in resources.assets)
- The rod runs along local +z: grey valve body at the root (z 0..0.875), red handle at z 0.857..1.067 (knob r 0.08 at the end).
- The support bracket rises along local +y to **0.431 m** in the car. That is the raw mesh's y 0.332 (my G-29 read) times the stock `/BrakeCylinderRelease/StaticPart`'s y scale of 1.3 *(C-21)*: same fitting. Use the scaled 0.431 when checking clearance. A 180° roll turns the bracket downward under a low running board.
- Rotate +z out to the side (±90° yaw), hide the valve body inside the body and expose just the red end. The placeholder scale is not copied to the runtime fitting.

**The core places both from a config hint** (`HandbrakeWheel` / `BrakeRelease` pose; `*Exact` opts out):
- **Handbrake wheel:** raycast which way the face looks, sample it ±0.3 m sideways, put the hub on the most protruding point (the crest of a rounded tank end, ignoring thin rails), shaft 22 mm into the mount, rim ≥ 12 mm clear.
- **Release:** at the hint z (±0.4 m), find the outermost side structure (running board, cab or tank side) and its bottom edge. Take the highest rod height ≥ 0.1 m below it where the valve body is hidden behind a face (frame, sill, ash pan) and the rod runs clear under the car, not over a cab floor. The bracket must fit under what is above it or end outside the cab (the `CabTeleportVolume`). The handle ends 0.15 m out past the edge.
- The build renders stand-ins of both (`markers_release.png`, `tender_handbrake*.png`, `tender_release.png`).
- *(C-21)* A pre-export gate can recheck the placed fittings against source geometry: the rim's surface clearance around 24 samples, and the release's cube, red tip and bracket against a fresh raycast of the side skin and running-board underside (C-21 `tools\unity\RRPlacementValidation.cs`).

**Servicing**
- Coal: `ShovelCoalPileProxy` trigger; `LocoResourceReceiverProxy` (coal 21, water 20).
- DV has **no water-hatch mechanic**; only the receiver collider matters.
- **Diesel-pump refuelling needs a fuel cap.** DV's service-station `LocoResourceModule` fills either through a raycast onto a `LocoResourceReceiver` (water and coal towers) or through a hose plugged into a socket (the fuel pump). A Fuel container alone is not enough. CCL's importer replaces every car-root child named `[fuel de2]` with the DE2's FuelTankCap, which carries the socket (config `FuelCaps`). DV's own cap poses come from `resources.assets` via UnityPy: DM1U side-wall caps are at x ±1.58 with rot R (-0.5,-0.5,-0.5,0.5), L (-0.5,0.5,0.5,0.5).

## 15. Oil cups
- **Oil cups need `PositionSyncProvider`s on the body with the same SyncTag.** Without them DV throws `PositionSyncConsumer` NullReferenceExceptions every frame (66k in one log).
- **Cups on the moving rods (core `RodOilers`, first built in G-29 test7, not yet tested in game).** Models often have the cups as small upright mesh islands on the rod ends (G-29: Example D). DV's oil-cup consumers follow their `PositionSyncProvider` every frame, so providers parented to the animated rods carry the cups.
  - Config: rod renderer names, each with a flag to leave its frontmost oiler modelled.
  - The core finds the oiler islands on each rod (at least 60 tris, at least 6 cm tall, 1.15 times taller than wide, no more than 12 cm across, nothing of the rod above them). Don't test for "above the rod's bounds centre": a pitched main rod's big end lies below it.
  - It cuts each oiler out and seats the DV cup 3 mm into the washer or boss the oiler stood on.
  - It parents the provider to the rod and renders cup stand-ins at 4 wheel phases.
  - **DV stock cup (S282 `OilingPoint0`, `CupOnly`):** pivot 17.5 mm above the base, 53 mm wide, 65 mm to the lid top. Its lid hinge is at local -z. Its trigger sphere (r 40 mm) sits at (0, 19, 3) mm. A modelled oiler bigger than that has to be cut out, or the cup disappears inside it.
  - Selection per Codex's gameplay design *(C-21)*: 6/8/10 cups; skip oilers the gear hides at some wheel positions.
  - Open question (test7): two cups side by side at the main crank pin. DV's desktop oiler raycast stops at the first cup collider it hits, so the outer cup may block the inner one.
  - Earlier notes:
  - *(C-21)* Mesh-island detection can shortlist candidates, but it cannot reliably tell a cup cap from a bolt. Review each cup point once by hand and keep it in a manifest: its animated parent/bone, local pose and oil-port order.
  - *(C-21)* DV's `PositionSyncConsumer.Sync` copies **position only**, not rotation. Where the cup's tilt matters, that needs a separate solution.
  - Sample a full driving-wheel revolution and check cup/lid clearance.

## 16. Tender locos
A Railroader tender (`tenderIdentifier` on the loco; a `kind: Car`, `archetype: Tender` object with the load slots) becomes a **second DV car** in the same pack. Worked example: RGB-2 (Example B). Reference CCL loco with a tender: Emeralds LMS 8F (`Mods\Emeralds_LMS_8F`; dump with `dump_ccl_bundle.py` and `dump_ccl_transforms.py`).
- **Creating the cars:** `CarWizard.CreateNewCar` for the loco (Kind Loco, with pack settings) and the tender (Kind `Tender`, `BaseCarType` `S282Tender`, pack settings `null`), then set `pack.Cars` to both. `AssetDatabase.FindAssets` folder filters match by prefix, so check an asset's folder exactly when two car folders share a name start.
- **Sims (CCL creators wire the link):** the loco uses `SteamerSimCreator` basis 1 (S282), which has no coal or water of its own. It reads `tenderWater`/`tenderCoal` ports fed over the coupling by broadcast consumers (`TENDER_*` tags), and broadcasts dynamo flow and headlight settings to the rear. The tender uses `TenderSimCreator` (coal and water containers, coal pile, broadcast providers, headlight consumers, a fuse powered by the loco's dynamo). The S282 basis also adds a superheater and feedwater heater; unhook what the prototype lacked.
- **Coupling:** on the loco root `CarAutoCoupler` (Rear → the other car's Front) and `RigidCoupler` (Rear), both for car kind "Tender"; on the loco `[sim]` a `VirtualHandbrakeOverrider` (Rear, "Tender") with the loco type's `brakes.hasHandbrake = false`; on the tender `KeepCoupledInteriorLoaded` (front). Hide the DV coupler visuals on the drawbar ends (`HideBackCoupler` / `HideFrontCoupler`). Spacing: section 7.
- **Spawning as a pair:** loco livery `TrainsetLiveries` = [loco, tender] and `LocoSpawnGroups` with the tender in `AdditionalLiveries`; call the variant's `ForceValidation()` so the JSON copy is written.
- **HUD:** the loco's tender indicators read `tenderWater`/`tenderCoal` `.NORMALIZED` (range `.CAPACITY`), not `water`/`coal`.
- **Tender interactables:** coal and water receivers at the Railroader `LoadTarget`s, the coal-pile trigger where the fireman shovels, and the handbrake. A Railroader handbrake lever works as a `LeverProxy` with a `HandbrakeFeederProxy` on the same object (DV adds the controller); CCL's `[brake small]` is only a placeholder for DV's stock wheel.
- **Coal load** (Railroader AggregateLoadModel): a box scaled by `coal.AMOUNT`.
- **Number plates** go at the Railroader RoadNumber decals; on a tender, at its RoadName lettering.
- **Info plates face along the anchor's local +x.** DV spawns `TrainCarPlate` under `[car plate anchor1/2]` with the anchor's rotation. Every stock car uses yaw 0 on the +x side and 180 on the −x side, whichever anchor it is. So the yaw must follow the side the plate is placed on, never the template: G-29/C-21 kept the template yaw and both cab plates faced inward. Core (G-29 pre-release 2) sets the yaw from the side and logs "plate faces ±x, outward".

## 17. Debugging in game
- **The rule:** any exception inside `SimController.Initialize` (TrainCar.Awake) silently breaks the whole car: no colliders, no interior, no teleport, no steam, no oil cups. The follow-on errors are `DrivingForce.FixedUpdate` and `SimController.Update` NullReferenceExceptions by the thousand. Find the **first** stack trace after the spawn line (`<CarId>(Clone)`).
- **Harmless noise:**
  - "Attempted to externally feed port that isn't EXTERNAL_IN" (another mod)
  - "Can't find ControlImplBase on Coal Collider / ignition collider"
  - DVStateProbe, SkinManager and TurboTurbo lines
  - "ItemLight needs light assigned!" then a NullReferenceException in `ItemLightOptimizer.RemoveLight`, from `CabLightsController.Init`. DV adds the `ItemLight` before assigning its light; Unity swallows the error and init continues, but that ItemLight stays disabled. With `ItemLightProxy` pre-added (section 11), DV logs "Found existing ItemLight" instead.
- **Useful confirmations:** `[DVPositionSyncFix] … real providers N`; `[FiremanAssistant] Water management ready …` means the sim started.
- **Unknown behaviour:** decompile the DV class named in the stack, read it, then fix the build script. Don't hand-patch the output.

## 18. Checklist per test build
- 0 warnings.
- Saved-prefab sim IDs are unique.
- Renders reviewed: exterior, backhead, lamps lit, markers, coupled joint.
- Bundle references only CCL.Types scripts.
- Info.json `Requirements` correct.
- Installed with rollback.
- TEST_NOTES.md lists what changed, what to check, and what's known.

---

# Part 2: Worked examples

## A. RLW RBBM-1t: tank Mallet
`Claudes Place\RLW_RBBM1t_Conversion\` (`RlwConfig.cs`): RLW 2-4-4-2T Mallet tank, reached test10.
- Each engine unit's animator has `startTimeOffset` 0.78 (the Railroader phase).
- Keeps 4 cylinders (8 beats) with the pitch/chuff audio mod.
- It carries LegosBetterSteam's `ArticulatedSteamEngineComponent`: 32.4k lbf vanilla → 39.4k compound / 50.8k simple. The build matched the base figure only.
- Its physics bogies turn, but the engine meshes are fixed to the body. Mallet articulation (section 6) would fix it; that needs a list of the RLW front-unit parts.

## B. RLW RGB-2: first tender loco
`Claudes Place\RLW_RGB2_Conversion\` (`RgbConfig.cs`): RLW 0-10-0 + 6-wheel UK tender, in-game tested. The worked example for section 16.
- test3 rebuilt it on the G-29 core (teleport indicator), with the `ItemLightProxy` cab-light fix and 5 %/tap throttle/reverser.
- Source of the tested lever values in section 9 (shared with the G-29).

## C. GN M-2: nested model, Mallet, third-party mods
`Claudes Place\GN_M2_Conversion\` (`GnConfig.cs`, `GnSource.cs`): Eilelwen GN M-2 2-6-8-0 simple Mallet + 8-wheel tender. Its core added optional `NestedClipGroups`, `MainPressureGauge` and `BodyExtras`. It also copies Railroader box and capsule colliders, and matches `CabControlObjects`/`NoWalkParts` by path as well as by name.
- The `AnimationMap` sits on `Master`; 0 of 277 clip paths resolved until children-relative hashing was added (`GnSource.EnsureFlat` lifts Master's children).
- A reverser clip that moves both engines plus the cab rod became three port-driven animators (`NestedClipGroups`).
- Wheel clips are one revolution over 2.5 s.
- The cylinder-cock anchors sat on the centreline.
- The throttle handle bone carries the rod to the dome (handle meshes grouped under a new node).
- LegosBetterSteam (Simple mode) doubles the pull to **107,635 lbf**. Check which mods define a pack's component kinds before matching pull.
- Heralds and tender text come from LegosLibraryOfStuff decal groups (baked quads).
- test1 findings: HUD wiring, lever jams, cocks that couldn't be opened (no toggle input), and a throttle that passed through the backhead collider without a problem. Ride height was 4.6 cm off: tread r 0.680 vs flange 0.700.
- Front engine hung on `BogieF` (articulation).
- Still lacks the `[cab]/teleport_indicator` (built on the older core).

## D. LLW G-29: catalog pack, one-mesh model (current reference core)
`Claudes Place\LLW_G29_Conversion\` (`G29Config.cs`): MarquetteCreations' LLW Generic Locomotive Catalog v1.4.3, asset `ls-260-g29` (2-6-0 Mogul) + tender `lt-260-g29`. **Its `tools\unity\` is the newest core.** Core additions over GN M-2: `ExtraParts`, `SafetyPos`, `BackheadZ`/`FireDoorCentre`, glass-submesh lamps (`path#material`), HUD-only gauges, multi-region wheel clips; test5 added `SimControls`, `RrLeverCfg.Hidden`, `Pullers`, `WheelClips`, `Sounds`, `RemoveVanillaSounds`; test6 the stock-fitting placement, RR spacing and `CouplingCheck`; the pin check followed on 2026-09-26.

**Source**
- The catalog zip has `ls-260-g29`, `lt-260-g29` and `g29parts` folders. The loco's `Catalog.json` lists both loco and tender prefabs in one bundle. The tender's trucks (`truckIdentifier: fox-truck-2s`) are in Railroader `Mods\FoxTrucks`.
- The loco body has no headlamp or handrail: `PrefabModelComponent`s point at `g29parts` prefabs. Built options: headlight2, handrail, markers.
- `Cylinder.002` is a single 204k-triangle mesh with 25 materials (boiler, cab, boards, backhead) and one RR MeshCollider hull.
- Every animated part sits under `Main`. The Drivers clip splits into 14 regions (one per `Armature.NNN` plus the loose parts under `Main`).
- The body and the parts pack both have materials `black`, `metal` and `white` (the pink-material bug).
- Liveries: RR's "Black" is a fully black loco; "Lined" (white stripes, maroon roof) is the one that looks like a loco. Built: Lined.
- The Mogul has no speedometer or steam-chest gauge (HUD-only gauges). The fire door is a foot pedal with two leaves.

**Running gear and cab**
- test2: pivoting the front bogie on the pilot wheel put the drivers ~5 cm off the rails on a 100 m curve; now pivoted on the end drivers, the pilot truck hung on the front bogie.
- `[cab]` floor from the RR hull: aisle y 1.496, benches 1.72 (`G29Probe.Floor`).
- test2: no controls, because the player stood on the tender deck, and the cab never highlighted for teleport (no `teleport_indicator`). Both fixed in test3.
- Sliding sashes: 1.8 cm grab boxes, sashes 2.3 cm apart.
- The 3 m 'Wrench' wheelset is the lubricator ratchet.
- test5 brought RR's own whistle, bell, air pump and dynamo sounds.

**Loco-tender joint** (RR spacing, test6)
- Tender origin = −3.319 − 1 − 3.875 = **−8.194**. Up to test5 a guessed 0.7 m gap put it at −7.894: 0.3 m too close, with the draw castings overlapping (seen in game).
- The tender carries the drawbar: three bars 0.8 m forward from its pins at tender z 3.786, ending in the loco's pocket.
- The loco has the rear draw casting, a fall plate onto the tender deck, and feed hoses that run 0.8 m under the tender.
- At RR spacing the castings are 6 mm apart and the bars reach the loco (23-51 mm), with no solid overlap. Only the RR spacing passes the ±0.1/±0.3 m sensitivity. Pin check: three pins, all on the tender, 316 mm from the loco (the bars' rear ends); the loco has none at the joint, so there is no pair.

**Stock fittings** (test6): handbrake on the tender face's crest, brake release out sideways (section 14). The release bracket measures y 0.332 in the raw mesh, which is 0.431 once the stock y scale of 1.3 is applied (section 14).
**Status: PRE-RELEASE 2** (0.9.1, 2026-09-26, installed; the mod manager shows "LLW G-29 (pre-release)" via `ReleaseLabel`). It is pre-release 1 plus the cab info-plate yaw fix (section 16). test8 was tested OK in game: couplers, oil cups and driving. This is the last G-29-core change; from here Astra writes the unified builder.
**Realism** (section 10; the figures and sources are in `builds\prerelease1\TEST_NOTES.md`):
- A generic "Atlantic Locomotive Works" design; class G-29 = 29,363 lbf starting TE, factor of adhesion 4.09.
- Saturated, 170 psig (valves 12.73/12.53 bar abs). Grate ~29 sq ft, taken between the 1906 ICC classes 201 and 601.
- Max firing 0.42 kg/s (65 kg bed, 155 s). That gives ~2.5 kg/s (~20,000 lb/h) of steam, the real maximum for this boiler; test1–8 made about double.
- Boiler 8.0 m³, 6,080 L of water. Injector 3.5 L/s. Coal and water use are real (multipliers 1).
- Tender 6,000 gal, 9 t coal.
**Oil cups** (test7, 0.7.0; tested OK in test8): 6 cups on the rods' modelled oilers via `RodOilers`: per side, the rear pin and main pin on the side rod, plus the main-rod big end. The front side-rod oilers stay modelled. Each oiler is cut out and the DV cup seated on the washer or big-end top; providers ride with the rods (section 15, `builds\test7\TEST_NOTES.md`).

**Oil cups (found, not built yet).** The cups are separate small upright mesh islands on top of each rod end: 136–176 tris, about 8 × 10 × 8 cm. The side rods have one at each crank pin; the main rod has one on the big end: 8 in all. The plan is in `builds\test6\TEST_NOTES.md` (next steps) and section 15.

## E. ALCo 1610: oil burner, saddle tank
`Claudes Place\ALCo_Mikado1610_Conversion\` (`AlcoConfig.cs`, `AlcoSource.cs`): Greenninja2404's Large ALCo Logging Mikado 2-8-2T saddle tank, oil fired. test2 is built on the G-29 test5 core; the G-29 core has moved on since (test6 placement, coupling check). Its `tools\` remain the oil-burning example.

**Oil firing on a tank loco** (method: `DV-Oil-Burning.md`, from Gingies Loco Lab's A.T.&S.F. 2901). Config `OilFiring`:
- the car's own `coal` ResourceContainer becomes type Fuel (litres)
- a CCL `SteamMechanicalStokerDefinition` (`oilBurner`) reads `coal.AMOUNT`/`CONSUME_EXT_IN` and feeds `firebox.COAL_CONTROL_EXT_IN`
- the valve `oilValve` is an ExternalControl with an OverridableControl of type DynamicBrake (14), so the HUD's dynamic-brake slot and keys drive it; a neutral-state setter closes it
- no tender bridge ports are needed
- because DV doesn't type-check port references, COAL-typed stoker references can read a FUEL container

**Lighting from cold**
- The stoker idles below 2 bar (`MIN_WORKING_PRESSURE`) on its STEAM_PRESSURE reference, and the firebox needs fuel before it can be lit, so a cold oil burner could never start.
- The core wires that reference to a constant `atomizer.PRESSURE` port (ConfigurablePort, 10 bar), so the valve feeds from cold. `FromBoiler` gives the steam-driven behaviour instead.
- **Atomizer valve** (`OilFiringCfg.AtomizerValveId`): a second ExternalControl drives CCL's `ConstantMultiplierOffsetDefinition` (valve x 10 bar), which is the stoker's STEAM_PRESSURE. With the stoker's `MaxWorkingPressure` 5, the burner is gated by the atomizer: closed = nothing, 1/4 = about 17 %, from 1/2 = full.
- Its cab wheel is registered as `LocoControlsReader.gearboxA` (`ControlsReaderExtra`). The HUD's Gearbox A buttons call `MoveScrollable(GearboxA, ±1)`, and the slot needs `BasicControls.GearboxA` = Display.

**HUD and servicing**
- Custom HUD: DynamicBrake for the valve, TenderCoal for the fuel, Shovel/FuelDump off.
- **Keep MagicShovelling on an oil burner.** DV's HUD shovel button and `FireboxKeyboardInput` (which also lights the fire) look it up and log errors without it; with the coal pile on the fuel tank, the shovel just primes a chunk of oil. Drop the physical shovel pile and coal receivers instead.
- Two `[fuel de2]` fuel caps on the bunker sides for diesel-pump refuelling (section 14).

**Model**
- Clips are bound to the wrapper child `Engine` (flattened by `AlcoSource.EnsureFlat`); component parent paths drop the `Engine/` prefix.
- `b.r.main/Empty.005` (a driver) and its children (the return cranks) were split across regions until `AnimGroups` keyed paths by their shortest bound ancestor.
- The headlight glass exported with 0 triangles: lenses come from `LampLenses`.
- Option prefabs and logos come from LegosLibraryOfStuff (`ExtraParts`, `BodyExtras`).
- Saddle tank: the backhead sits inside the cab (z -4.05), probed with `RayZ`.
- The roof hatch `Empty.048` and its prop rod `Empty.048/Empty.049` are nested clips (the rod's clip goes first).
- Sounds: no `defaultWhistleIdentifier`, so RR's fallback wh-5-drg-st; bell, pump, dynamo.

## F. LLW C-21: separate project; joint check
`Desktop\LLW CONVERT\LLW Pilot Workflows\` (another session's project; its status is in `C21_STATUS.md`, its builds in `builds\c21\`). A 2-8-0 from the same LLW catalog as the G-29, built on an earlier copy of this core plus its own pre-export gate `RRPlacementValidation.cs` (section 14).

**Joint check, 2026-09-26** (G-29 core's coupling and pin checks, run on the C-21's built templates; evidence and probe source in `analysis\c21\joint-pin-check-20260926\`)
- RR spacing: tender origin = −3.395 − 1 − 3.05 = **−7.445**. The C-21's test12 has −7.057 (from lining up "pins" on both cars).
- The C-21 "loco pin" is the island `Cylinder.006` 0.646 × 0.281 × 0.175 m at z −4.234: the loco's rear **draw casting**, not a pin. The tender's three pins at tender z 2.823 are the rear ends of its drawbars, as on the G-29.
- **At −7.445 (RR):** the loco casting's face meets the tender's front casting at 4 mm, with no solid overlap. The tender pins are 314 mm from the loco. This matches the G-29 (6 mm).
- **At −7.057 (test12):** the tender's front casting sits **385 mm inside** the loco casting (98 overlap cells), with the tender pins buried in it. This fits the "compressed drawbar" the user saw in game.
- So Railroader's spacing is right for the C-21 too. *(C-21)* test13 (0.1.2) now uses −7.445 and has dropped the false pin pair.

**Oil cups** *(C-21)*: test13 has 8 cups on the rods, one per crank pin, all on the side (connecting) rods, with no main-rod cups. Their providers are parented to the moving rods, and the anchors match the source caps to within 0.01 mm. The cup pivot sits at the modelled cap top, so the cup's base is 17.5 mm into the cap and its lid top is 47.2 mm above it. The G-29 (test7) cuts the modelled oiler out instead (section 15). Neither has been oiled in game yet. Evidence: `analysis\c21\oil-anchors\`, `builds\c21\test13\`.

---

## Open items
See each project's latest `builds\testN\TEST_NOTES.md` (and `AUDIT.md` where present).
- GN M-2, RBBM-1t and GWR 1366 predate the teleport indicator, RR spacing, coupling check and stock-fitting placement: rebuild them on the G-29 core.
- Oil cups on the moving rods (section 15): the G-29 test7 and C-21 test13 are built but haven't been oiled in game yet; the main-crank double cup is the open question.
- Liveries beyond the first (section 5).
