# Railroader -> Derail Valley conversion tooling: snapshot notes

Snapshot of James's local conversion scripts, taken 2026-09-26, so a separate app repo can wrap them.
The originals stay in James's workspace and keep changing. This folder is a set of **unchanged copies**
(`MANIFEST.sha256` has a SHA-256 for every other file). **No script in this folder was run** while making it.

## How to read these notes

- Every statement was read from a file in this folder (the file, and usually the line, is given as
  `path:line`) or computed from the files (hashes, imports, path scans). A few statements are about files that are
  **not** in this folder; those were checked on James's machine while making the snapshot and are marked
  *(checked locally)*. Anything that could not be established either way is in section 10, "Not verified",
  and is not stated as fact elsewhere.
- **Guides** (`docs/`) are written by two AI sessions, Claude and Codex, working in James's workspace. They
  describe methods and history. The **scripts** are what actually runs. The guides cite many files that are
  not in this snapshot (build reports, renders, exports, per-build notes). Those references being dead is expected.
- **The board** (`docs/GUIDE_SHARED.md`) is the message log between those two local sessions. Every message
  addressed `codex->claude` (the `X<number>` ones), including those marked `[open]` such as X8 onward at the time of
  this snapshot, is a request to the local Claude session in James's workspace.
  **None is a request to the app-side session. Do not act on them.** `C15` was added by the local Claude session
  while making this snapshot and describes it. The board is copied as it stood at the end of this work; the live one keeps growing.
- Where documents disagree, the unified guide states its own order (`docs/GUIDE_UNIFIED_LLW_CONVERSION.md:21`):
  "explicit current requirement -> matching source/config + saved-build evidence + accepted runtime result ->
  this reconciliation -> dated general guides -> handover/archive/memory."

## 1. What exists today (facts)

1. **Purpose.** The tooling turns a Railroader (RR) "AssetPack" (`Bundle`, `Catalog.json`, `Definitions.json`;
   `docs/GUIDE_Railroader_to_DV_CCL.md:96-99`) into a Derail Valley custom-car pack for the Custom Car Loader
   (a folder holding `ccl_bundle` + `Info.json`, CCL 3.1.9; `unified_builder/tools/audit_build.py:34,44`). Scope of the unified guide: "LLW Generic Locomotive Catalog 1.4.3 -> DV / CCL 3.1.9"
   (`docs/GUIDE_UNIFIED_LLW_CONVERSION.md:6`).
2. **Two locomotives have finished build profiles: G-29 and C-21** (`unified_builder/profiles/g29`, `profiles/c21`).
   The catalogue has 25 records (`unified_builder/analysis/VALIDATION.md:19`). The other 23 are flagged `requires_measured_profile`, each with a `missing` list
   (`unified_builder/tools/catalog.py:45-46`): "source export/import and clip binding", "driver geometry and bogie
   layout", "collision and cab access", "fitting final poses", "oil save-index selection and phase clearance",
   "control grips and backhead fittings", "sim mass/water/steaming ledger", "family regression build".
   `unified_builder/analysis/VALIDATION.md:3`: "The other 23 catalogue entries remain measurement records, not playable conversions."
3. **Not built.** `docs/GUIDE_UNIFIED_LLW_CONVERSION.md:334`: "DESIGN: automatic measured-profile generation/family
   pilots/full-fleet batch; no 25-engine completion claim." Same file, line 101: the vehicle-record schema "is not an existing importer API."
   The unified README says "no full source import/bootstrap of an arbitrary new locomotive is claimed" (`unified_builder/README.md:37`).
   No script in this folder converts a new locomotive without a profile for it.
4. **Test status.** G-29 0.9.2 and C-21 0.1.4 were exported and audited; the merged outputs were **not** game-tested
   (`unified_builder/analysis/VALIDATION.md:3,22`; guide front matter, line 10: "user-confirmed predecessor methods; new unified outputs pending game test").
5. **How a build is launched.** By starting Unity 2019.4.40f1 with `-projectPath ... -executeMethod <Profile>Config.Build`.
   `unified_builder/tools/run_build.ps1:30-32` starts `Unity.exe` with `-WindowStyle Hidden` and no `-batchmode`.
   The guide (`docs/GUIDE_Railroader_to_DV_CCL.md:70`): "The Personal licence refuses `-batchmode`. Run windowed ...
   A 'No valid Unity Editor license' exit after ~10 s is a flake: rerun." Whether it can run any other way is in section 10.

## 2. How measurement works (the earlier notes got this wrong)

**Measuring is done by scripts, not by hand.** The authors' own rule (`docs/GUIDE_Railroader_to_DV_CCL.md:62`):
"Placement must be deterministic. Fittings, coupling spacing and control positions come from measured geometry and
Railroader's own rules, checked in the build report, never from a hand-tuned number."

Where each kind of number comes from:

| Kind of number | Produced by | Evidence |
|---|---|---|
| Wheel sizes, mass, pressure, cylinders, component positions, liveries from the RR definition | `gen_defs.py` writes `*Defs.cs`; `catalog.py` writes records | `pilot_workflows/tools/gen_defs.py:53-100`; `unified_builder/tools/catalog.py:22-59` |
| Model geometry: wheel radius and rail height, cab floor, coupling faces, backhead depth, rod oilers, what each clip moves | Read-only Unity probe classes | `unified_builder/profiles/g29/G29Probe.cs:11-13` (read-only), `:39-42` Backhead, `:160-162` Wheels, `:193-194` Floor, `:219-221` Faces, `:274-277` Details, `:378-380` Rods; C-21: `C21Probe.cs`, `C21OilProbe.cs`, `C21PlacementProbe.cs`; pilot source inspection (C-21, S-16): `pilot_workflows/tools/unity/PilotProbe.cs` |
| Oil-cup mount candidates for every catalogue loco | `oil_cup_survey.py` (opens each bundle, samples the animation clips at four phases, finds small mesh islands on the rods); `oil_cup_survey_report.py` classifies them and writes `anchor_manifest.json` | `pilot_workflows/tools/oil_cup_survey.py:126,133-161`; `oil_cup_survey_report.py:8-52,110-121`; `VALIDATION.md:19`: 238 linked source candidates |
| Dimensions of DV's stock parts (handwheel, brake release, oil cup) | Scripts that read DV's `resources.assets` and dump the parts' meshes and colliders | `pilot_workflows/analysis/.../extract_stock.py`, `find_stock.py`, `inspect_stock_cup.py`. The core's comments say its constants were "measured from the mesh vertices" / "measured from resources.assets" (`CclLocoBuild.cs:39,1045-1046`); board message `X1` names `extract_stock.py` as the source of the 0.431255 m brake-release figure (`docs/GUIDE_SHARED.md:27`). Which script produced which other constant was not traced. |
| Final positions of parts, measured while the pack is being built | The build core | list below |

**What the build core measures for itself** (all `unified_builder/tools/unity/CclLocoBuild.cs`):

- Handbrake wheel: samples the face around a hint and seats the wheel on its crest (`PlaceHandbrakeWheel`, `:3366-3407`).
- Brake release: finds the outermost side structure and a rod height that clears it (`PlaceBrakeRelease`, `:3413`).
- Outer couplers: fires rays along z at the coupler height, takes the most common stop position in 1 cm bins as the end beam,
  and **throws** if fewer than 20 hits, if the modal bin is under 20, or if the result is implausible
  (`EndBeam`, `:1295-1313`; tested by `UnifiedBuilderTests.cs`). `RigOnEndBeam` (`:1315-1356`) places the coupler rig
  0.309 m beyond it, hides DV's buffer and hook-plate meshes, warns where the model intrudes on DV's coupler hardware, and trims collision boxes.
- Loco-to-tender joint at the coupled position: joint parts, solid overlap, and the same check with the tender 0.1 and 0.3 m
  either way (`CouplingCheck`, comment at `:3542-3550`).
- Lever range and axis come from the RR animation clip (`RrLever`, `:2091-2114`); the grip box is computed from the mesh
  unless the profile supplies one (see below).
- Every animation-clip binding must resolve to exactly one object, otherwise the build throws (`Clip`, `:140-157`).
- Oil cups: two strategies, chosen by the profile (`:96`, `:940-989`).
  **G-29 `RodOilers`**: the profile names rod meshes; the core finds the oiler islands on them by shape rules, cuts them out, seats a
  DV cup on what the oiler stood on, and puts the sync provider under the rod (`:1044-1117`).
  **C-21 `OilAnchors`**: the profile holds 8 explicit ordered anchors; the core does **not** find them, it checks each against the
  source mesh (triangle count, cap height within 3 mm, tag order) and throws on any mismatch (`:946-976`). An optional detector
  (`ValidateShallowOilAnchors`, `DiscoverShallowOilAnchors`, `:993-1042`) cross-checks them.
- `RRPlacementValidation.cs` has two entry points. `Validate` runs first in `Run` (`CclLocoBuild.cs:66-67`): loco-to-tender spacing and
  mating pins (`:12-42`). `ValidateFinalFittings` runs in `BuildInteractables` **after** the handbrake wheel and brake release are placed, whether by the
  core or by an `*Exact` pose from the profile (`CclLocoBuild.cs:2417-2434`; comment at `RRPlacementValidation.cs:44`): handbrake mount and rim
  clearance (`:136-175`), brake release (`:68-110`, `:184-236`). An exact pose is therefore still checked. The end beam is checked in `EndBeam`
  and the car-plate direction in `audit_build.py`, not here.

**What a session still writes, per locomotive: the profile (`*Config.cs`).** `unified_builder/tools/unity/LocoConfig.cs:5-9`:
a new conversion "copies an existing config ..., fills these in (probe renders + build report make it quick) and adds anything the
core can't express as a hook." Concretely:

- Which mesh is which cab control, with its port, notches and physics: `G29Config.cs:253` (`RrLevers`), `:312` (`Fittings`), `:322` (`Placed`).
  Where a `Grip` box is given it is used as given (`CclLocoBuild.cs:2139`); the log marks it "(config)" (`:2158`).
  Fitting centres cite the probe output: `G29Config.cs:309-310` ("analysis\probe\backhead_report.txt").
- Oil cups: G-29 lists rod names (`G29Config.cs:213-221`). C-21 lists 8 literal anchors described as "Reviewed cap-top islands ...
  (analysis/c21/oil-anchors/rod_islands.txt)" (`C21Config.cs:90-103`); that file is written by `offline_oil_probe.py`.
  `validate_oil_anchors.py` re-checks them from Python.
- Hints for the handbrake wheel and brake release (`LocoConfig.cs:150-157`). The core refines them unless the `*Exact` flag is set.
- Simulation numbers (bore, boiler size, firing rate, injector) are **engineering and balance choices**, not measurements.
  G-29's cite real locomotive classes (`G29Config.cs:37-59`); C-21's point to a `DATA_SHEET.md` that is not included (`C21Config.cs:7`).
  The unified guide's vocabulary for this: `basis = source | measured | derived | analogue_estimate | DV_choice` (`:101`).
- The catalogue record feeds **only pony-truck radii** into the build; measured profile values win (`LlwCatalogConfig.cs:6-27`).

For the 23 unfinished locos, the `missing` list (section 1, point 2) names what has not been produced yet, and `VALIDATION.md:3` calls them "measurement records".
The oil-cup survey scripts have run over all 25 (`VALIDATION.md:19`: 238 linked source candidates). In this snapshot, per-loco probe and profile code exists only for G-29 and C-21
(`unified_builder/profiles/`), plus a source-inspection pilot for S-16 (`pilots.py`, `config/s16.json`).

## 3. The process, as the authors document it

`docs/GUIDE_Railroader_to_DV_CCL.md:95-132` (same list in the Codex guide, `:57-94`) and the unified guide (`:117-125`, "B04"):

| Step (authors' words, shortened) | Script in this snapshot |
|---|---|
| 1. Unpack the Railroader mod zip (Bundle, Catalog.json, Definitions.json) | none; no script here does it |
| 2. Harvest `Definitions.json` into generated C# constants | `gen_defs.py` (called by `pilots.py:205`; for G-29 by a manual command, `g29_handover/REBUILD.md`, section D) |
| 3. AssetRipper export with `TargetVersion=2019.4.40f1` (the guide also says export a native copy for reference) | `export_assetripper.ps1` (3 versions, section 5); the script sets `TargetVersion` from `-Target`, default 2019.4.40f1 (pilot version `:3,42`) |
| 4. Restore animation clip paths (`path_0x<crc32>` -> real paths) | `resolve_clip_paths.py` (3 versions, section 5) |
| 5. Set up the Unity build project (2019.4.40f1, remove URP, add uGUI + TextMeshPro, extract CarCreator 3.1.9, copy editor scripts) | G-29: `setup_build_project.ps1`. C-21 and S-16: `pilots.py prepare` |
| 6. Build in stages (`CclLocoBuild.Run(config)`) | launcher: `run_build.ps1` (unified), `run_unity.ps1` (G-29, older), `run_c21.ps1` (C-21, older) |
| 7. Install to `Mods\<Name>` with a timestamped rollback copy | `install_build.ps1`, `install_c21.ps1`; the unified README says "No automatic installation or save modifications" (`unified_builder/README.md:41`) |

"Starting a new loco" (Codex guide `:16-21`; Claude guide `:88-93`): run `gen_defs.py`; copy the closest existing config; probe the model and
fill in part names, positions, clips, stats and control layout; build, read the report and renders, repeat; add to the core only what the config cannot express.

The build stages inside `CclLocoBuild.Run` are the 12 listed at guide `:117-129`; in code: `CclLocoBuild.cs:53-86`.

**Unified builder run (the newest path, G-29 and C-21):** `run_build.ps1` -> `prepare.py` -> Unity runs `<Profile>Config.Build` ->
you wait for `result.json` -> `audit_build.py` -> optionally `share_project.py` (`unified_builder/README.md:23-35`).

**Steps that are not scripted in this snapshot, or that need a person's judgement (from the documents):**
unpack the mod zip (no script); choose the appearance/livery options ("`enabled` alone is not an option selection", unified guide `:119`;
`pilots.py` field `appearance_policy`); write or edit the profile (section 2); prepare Railroader audio if wanted: extract, loop and place the WAVs under
`Assets/G29_audio` (commands in `g29_handover/updates/test5-ancillary-and-audio/README.md:37-58`; the live `setup_build_project.ps1:69-72` copies them in
from `source\audio\dv`); wait for Unity and read `result.json` (the unified launcher returns immediately, `run_build.ps1:35`); review build-report
warnings (`audit_build.py:39-42` compares them with the reference build's); install and test in the game (Claude guide `:57-60`: "Test loop with the
user ... read `Player.log` from the first exception"). AssetRipper itself is scripted (`export_assetripper.ps1`, one bundle per run); the guide says
to export each pack twice, a native copy and the 2019.4 copy.

## 4. What each script does

Line numbers refer to the file named. All descriptions come from reading the file.

### `unified_builder/` (copy of `LLW CONVERT\LLW Unified Builder`; the newest builder)

| File | What it does |
|---|---|
| `tools/run_build.ps1 -Profile g29\|c21 -Run NAME [-Tests] [-Share] [-Python EXE]` | `:13-36`. Runs `prepare.py`; creates `builds\<profile>\<run>` (throws if it exists); copies `unified-scripts.json` to `source_hashes.json` and the catalogue record to `catalog_record.json`; sets `CCL_BUILD_OUT` and `RLW_PROBE_OUT` (run folder), `CCL_CATALOG_RECORD`, `G29_SHARE` (`1` with `-Share`), restoring them afterwards; starts Unity hidden with `-executeMethod <PROFILE>Config.Build` (`UnifiedBuilderTests.Run` with `-Tests`) and a log file; writes `launch.json`; prints the process id and **returns without waiting**. |
| `tools/prepare.py <g29\|c21>` | `:12-38`. Checks the stored `catalog/<id>.json` equals a freshly generated record (else error). If `unity/<PROFILE>_CCL` does not exist, copies `Assets`, `Packages`, `ProjectSettings` from a source project (G-29: `Claudes Place\LLW_G29_Conversion\unity\G29_CCL`; C-21: `LLW Pilot Workflows/unity/C21_CCL`, `:7-10`); refuses if Unity's lock file exists or if the project has no `unified-project.json`. Then copies `tools/unity/*.cs` and `profiles/<profile>/*.cs` into `Assets/Editor` and records their SHA-256 in `unified-scripts.json`. |
| `tools/catalog.py` | `:22-70`. For each `ls-*` folder of the LLW catalogue reads `Definitions.json` (tolerates trailing commas) and writes `catalog/<id>.json` and `catalog/index.json`: wheels with role (driver / pony / auxiliary) and radius = diameter/2, physics figures, tractive effort (published, else `.85*p*d^2*s/D`), end positions, tender id, all source objects, components grouped by kind, status and `missing` list. Adds oil candidates from `oil-cup-survey-20260926/<id>/anchor_manifest.json` when present (error if its bundle hash is stale). If `overrides/<id>.json` exists (its bundle hash must match) the record gets that profile name and an empty `missing`. |
| `tools/resolve_clip_paths.py SRC REPORT.json [--apply DST] [--bindings FILE]` | Strict rewrite: resolves every clip first, treats an unresolved or ambiguous mapping as an error, writes nothing unless all clips resolve, refuses `DST == SRC`, writes a **JSON** report. In this snapshot only `tools/test_workflow.py` calls it. The unified guide calls it the "future import resolver" (`docs/GUIDE_UNIFIED_LLW_CONVERSION.md:68`). |
| `tools/audit_build.py PROFILE RUN_DIR [--share]` | `:33-120`. Opens the built `ccl_bundle` with UnityPy and checks it against a reference build: `result.json` says exported; the `WARN` lines equal the reference build's exactly; `Info.json` id and `DVCustomCarLoader` requirement; no missing scripts, only CCL assemblies; expected car types and paired spawn; one each of `CarAutoCoupler`, `RigidCoupler`, `KeepCoupledInteriorLoaded`, `CabTeleportDestinationProxy`; four car-plate anchors facing outward; oil cups (count 6 / 8, tags match providers, save order equals the reference, providers parented to a rod mesh); base mass (`:57-59`); wheel radii and counts; simulation ids; HUD fields; firebox range 65 / 100; control ports equal the reference; outer coupler lines equal the reference; tender spacing -8.194 / -7.445; the four-phase oil line; `solid overlap: 0 cells`; `source_hashes.json` matches current files; with `--share`, zero AudioClips. Writes `bundle_audit.json`; exit code 1 on any error. Needs the two reference builds (`:8-11`, not included). |
| `tools/share_project.py NAME G29_RUN C21_RUN` | Re-audits both runs with `--share`, then zips only the bundles, evidence and allow-listed builder files into `share/NAME.zip` with a manifest. Never zips a Unity project. |
| `tools/test_workflow.py` | 9 unit tests for `catalog.py` and `resolve_clip_paths.py`; needs the catalogue folder. |
| `tools/unity/CclLocoBuild.cs` | The shared build core (about 250 KB). `Run` (`:53-86`): placement validation, own assets, per car: clips, materials, car wizard, exterior, interior + LOD (loco only), interactables, sound, assets; link tender; renders; export through CCL's `ExportPackWizard` (reflection, `:2946-2966`), patches `Info.json`; writes `build_report.txt` and `result.json` (`exported`, `warnings`, `runtimeValidated:false`). |
| `tools/unity/LocoConfig.cs` | The data class one profile fills in. Optional sections left null/empty are skipped (`:5-9`). A tender is a second config. |
| `tools/unity/LlwCatalogConfig.cs` | Reads the catalogue record named in `CCL_CATALOG_RECORD`; checks id/profile; adds pony radii not already set by the profile. Nothing else. |
| `tools/unity/RRPlacementValidation.cs` | Loco-tender spacing and mating-pin checks; final handbrake and brake-release pose checks (section 2). |
| `tools/unity/UnifiedBuilderTests.cs` | 8 checks in a scratch scene: triangle distance (3), empty end-beam rejected, tank face excluded, colliders restored, unequal pony radii, zero radius rejected. |
| `profiles/g29/`, `profiles/c21/` | `*Config.cs`: `Create()` returns the profile; `Build()` = `CclLocoBuild.Run(LlwCatalogConfig.Apply(Create(), id))` (`G29Config.cs:12`, `C21Config.cs:16`). `*Defs.cs`: generated ("Do not edit", line 1). `*Source.cs`: prefab paths, `DropY`, and `ResolveComps`, which converts parent-relative component transforms to car space; `C21Source.EnsureFlat` builds a pilot part from shared G-19 parts (`:16-26`). Probes: `G29Probe` (Run, Backhead, Wheels, Floor, Faces, Details, Rods), `C21Probe` (Run, Backhead, Wheels, Floor, Faces; its header comment still says "G-29"), `C21OilProbe` (Run, ValidateBuilt), `C21PlacementProbe` (Run). `G29Config.cs:307`: `G29_SHARE=1` clears the RR-extracted sounds. |
| `overrides/*.json` | Per-loco registration: profile name, pinned SHA-256 of the source bundle, path of the profile, reference build, oil and mass policy text, `runtime_status: "merged output not game tested"`. |
| `README.md`, `UnityProjectContext.md`, `MIGRATION_PLAN.md`, `analysis/VALIDATION.md` | The builder's commands and behaviour; a context note for AI sessions (versions, architecture, constraints); a **proposal** for reorganising the workspace (status line: "proposed; no originals moved/deleted"); the test and acceptance results. |

### `pilot_workflows/` (copy of `LLW CONVERT\LLW Pilot Workflows`; the older C-21 / S-16 front end and the survey scripts)

| File | What it does |
|---|---|
| `tools/pilots.py inventory\|prepare\|verify c21\|s16` | `inventory`: lists the source objects, part references and hashes for a pilot. `prepare` (`:148-220`): copies the AssetRipper export into `unity/<C21\|S16>_CCL` (errors if it already exists, `:152-153`); copies `ProjectSettings`/`Packages` from the G-29 project; runs `resolve_clip_paths.py` and requires `unresolved: 0` in its text report (`:166-168`); copies referenced part prefabs with `copy_deps.py`; C-21 also copies the Fox truck; unpacks CarCreator; copies `tools/unity/*.cs` (`:195-196`); runs `gen_defs.py`; writes `PilotSource.json`, `PilotProbeInput.json`, `config/<pilot>.json`. `verify`: re-checks source hashes and prefab files. Needs the catalogue and `LLW G29 CONVERSION/conversion` beside it (`:16-18`) and `FoxTrucks` (`:131,185`); uses `hashlib.file_digest` (Python 3.11+, `:44`). |
| `tools/create_integration_specs.py` | Runs on import, for both pilots. Reads `config/<pilot>.json`; writes `config/<pilot>-integration.json` ("source-derived integration specification; not a finished LocoConfig"): wheel roles and nominal radii (measured radius left `null`), control-to-port table for throttle, reverser, brakes, whistle, load capacities converted to litres/kg, masses, and a `pending_measurements` list. |
| `config/*.json` | Written by `pilots.py prepare` (`<pilot>.json`) and `create_integration_specs.py` (`<pilot>-integration.json`). `pilots.py verify` reads `<pilot>.json` (`:224`). |
| `tools/gen_defs.py`, `copy_deps.py`, `analyze_export.py`, `export_assetripper.ps1`, `handover_config.ps1`, `resolve_clip_paths.py`, `test_workflow.py` | Pilot-folder versions; see section 5. `analyze_export.py` writes `hierarchy.txt`, `clips.txt`, `materials.txt` from an export. |
| `tools/run_probe.ps1 c21\|s16 RUN` | Copies `unity/PilotProbe.cs` into the project, runs `PilotProbe.Run` and **waits** (15 min default); requires `result.json` with `status: passed` and no compile errors; output `analysis\<pilot>\<run>` (`:19-31`). `PilotProbe.cs` header: "Source-inspection only ... never saves a scene or modifies source prefabs." |
| `tools/run_c21.ps1 RUN [-Method]` | Starts `C21Config.Build` (or a `C21Probe`/`C21OilProbe` method) in the C-21 project; returns after launch (`:8-23`). |
| `tools/install_c21.ps1 RUN` | Requires `bundle_audit.json` with `status: passed` and a matching bundle hash, backs up any installed pack, copies the build to a fixed Mods path, writes `installation.json` (`:9-25`). |
| `tools/audit_c21.py RUN_DIR` | The C-21 audit (`:1-97`); writes `bundle_audit.json` (the file `install_c21.ps1` reads). For the unified builder the auditor is `unified_builder/tools/audit_build.py`, which writes the same file name; guide `B01` calls the pilot and G-29 tools "predecessor evidence, not active authority for the new builder" (`docs/GUIDE_UNIFIED_LLW_CONVERSION.md:72`). |
| `tools/oil_cup_survey.py [ls-...]` | Section 2. Writes `survey.json` and `geometry.npz` per loco under `analysis/oil-cup-survey-20260926/`. Considers clips whose name contains "driver" only (`:109`). |
| `tools/oil_cup_survey_report.py` | Classifies candidates (tall oiler, shallow plug, others rejected), writes `anchor_manifest.json` (fields for cup model, insertion depth and save-index mapping are left `null`), `classified_survey.json`, PNG sheets, `anchors.csv`, `index.html`. Needs Pillow and `C:/Windows/Fonts/segoeui.ttf`. |
| `tools/validate_oil_cup_survey.py` | Asserts the survey output for all 25 locos is consistent (counts from the definition, hashes, four-phase transforms) and writes `validation.json` and review sheets. |
| `tools/catalogue_design.py` | Reads every `Definitions.json`/`Catalog.json` in the catalogue and in the installed Railroader `Mods` folder; writes `analysis/catalogue/fleet_inventory.json` and `dependency_registry.json` (families, waves, decal/whistle/truck dependencies, installed-vs-source hashes). "Design inventory only." |
| `analysis/c21/oil-anchors/` | `offline_oil_probe.py` reads the exported C-21 YAML and writes `rod_islands.txt` (mesh islands of four rods) without an Editor licence; `validate_oil_anchors.py` checks the anchors in `C21Config.cs` against it; `inspect_stock_cup.py` measures DV's stock S282A cup from `resources.assets`. |
| `analysis/c21/runtime-feedback-20260926/stock_fittings/` | `find_stock.py`, `extract_stock.py`, `analyse_parts.py`: locate DV's stock handwheel and brake-release objects in `resources.assets`, dump their meshes and colliders, and print extents and connected pieces. |
| `analysis/gameplay-oiling-design-20260926/measure_recommendations.py` | Reads the survey and writes a per-loco cup-count proposal with clearance checks. Its own status text: "design recommendation; not fitted or runtime validated". |

### `g29_handover/` (copy of `LLW CONVERT\LLW G29 CONVERSION`; the G-29 files made for the LLW author)

| File | What it does |
|---|---|
| `conversion/tools/handover_config.ps1` | Reads `G29_PYTHON`, `G29_UNITY`, `G29_ASSETRIPPER` from the environment. Dot-sourced by `export_assetripper.ps1`, `run_unity.ps1`, `setup_build_project.ps1` here. |
| `conversion/tools/setup_build_project.ps1` | Creates `unity\G29_CCL` from `assetripper\export_2019\ExportedProject` if missing: sets the Unity version, package manifest (adds TextMeshPro 2.1.6 and uGUI 1.0.0, removes render-pipeline packages), runs `resolve_clip_paths.py`, copies the Fox truck and three G-29 parts with `copy_deps.py`, unpacks `tooling\CarCreator_3.1.9.unitypackage`; then copies `tools\unity\*.cs` into `Assets\Editor` (`:8-11,41,45,73,78`). Does not copy audio. |
| `conversion/tools/run_unity.ps1 -Method M -Out DIR` | Runs `setup_build_project.ps1`, starts Unity hidden, **waits** (40 min), throws on log errors, and for `G29Config.Build` **throws unless `build_report.txt` contains `warnings: 0`** (`:11,20-31`). |
| `conversion/tools/install_build.ps1 -ModsPath P -Name RUN [-Remove]` | `-ModsPath` is mandatory and must sit in a Derail Valley install (`:3,8`); backs up any installed `LLW G-29` into `rollback`, copies `builds\<name>\LLW G-29`. |
| `conversion/tools/export_assetripper.ps1`, `gen_defs.py`, `copy_deps.py`, `resolve_clip_paths.py`, `analyze_export.py`, `summarize_defs.py`, `dump_ccl_bundle.py`, `dump_ccl_transforms.py` | See section 5. `summarize_defs.py` prints a compact view of `Definitions.json`; `dump_ccl_bundle.py` dumps every MonoBehaviour of a CCL bundle (used to copy port ids from working DV locos); `dump_ccl_transforms.py` prints matching transform trees. |
| `updates/test5-ancillary-and-audio/tools/extract_rr_audio.py --railroader-root DIR --out DIR` | Extracts four named clips (CNJ 3-chime whistle, rope bell, TVRM compressor, TVRM dynamo) from a Railroader install; refuses to overwrite. |
| `updates/test5-ancillary-and-audio/tools/loopify_wav.py IN OUT [--asis]` | Loop-joins a WAV with a 4096-sample crossfade; "specialized to these recordings, not a general audio converter" (`updates/test5-ancillary-and-audio/README.md:60`). Needs NumPy. |
| `REBUILD.md`, `updates/.../README.md` | The author-handover instructions for these scripts, including the AssetRipper, Unity and Python versions recorded there. |

### `g29_live_tools/` (copy of the script files in `Claudes Place\LLW_G29_Conversion\tools`; what the local sessions run)

Same script names as the handover folder, with machine paths written into the scripts. Differences that were read:
`setup_build_project.ps1` also copies `source\audio\dv\*.wav` into `Assets\G29_audio` every run (`:69-72`) and has hard-coded Python and CarCreator paths (`:8-9`);
`run_unity.ps1` does not hide the window, prints the exit code and error lines, and does not require `warnings: 0`;
`install_build.ps1` has a hard-coded Mods path; `export_assetripper.ps1` has a hard-coded AssetRipper path;
`extract_rr_audio.py` has the Railroader paths and the four clip names written in (`:4-5`). `loopify_wav.py` is identical to the handover copy.

## 5. Different versions of the same script

Computed from the copies (first 8 hex digits of SHA-256). Same value = same bytes.

| Script | Versions |
|---|---|
| `resolve_clip_paths.py` | `d4ba4649` `g29_live_tools`, `g29_handover/conversion/tools` (reads `AnimationClip/*.anim` only; text report). `28da9f9c` `pilot_workflows/tools` (recursive, keeps the folder tree, maps child-relative hashes to full paths; text report with an `unresolved: N` line; ties take the first match). `b8edf59b` `unified_builder/tools` (strict, JSON report, see section 4). **Callers:** `setup_build_project.ps1` (both) and `pilots.py` (and its `test_workflow.py`) call the first two. `pilots.py:168` requires `^unresolved: 0$` in the report, so the JSON version cannot replace it as-is. |
| `gen_defs.py` | `3453b78e` `g29_live_tools`, `g29_handover`. `30e49464` `pilot_workflows` (keeps every field of each component in the generated `extra` string; the older one copies a fixed list of keys). |
| `export_assetripper.ps1` | `b041b00b` `g29_live_tools` (hard-coded AssetRipper path). `7bf2d2ac` `g29_handover` (path from `G29_ASSETRIPPER`). `a23cb337` `pilot_workflows` (also sets the working directory, logs under `analysis\exports\<OutName>`, checks the export finished, `:6-8,50-51`). |
| `setup_build_project.ps1` | `179e3e48` live (audio copy, hard-coded paths). `337553ce` handover (env vars, error checks, no audio copy). |
| `run_unity.ps1` | `2a319a34` live. `89ea84a1` handover (section 4). |
| `install_build.ps1` | `6f037d19` live. `d886510b` handover. |
| `extract_rr_audio.py` | `3b26c4ba` live. `471dd71f` handover update (arguments, checks). |
| `test_workflow.py` | `e38182dd` `unified_builder` (9 tests, catalogue + resolver). `ccc8b5f6` `pilot_workflows` (tests `pilots.py`; calls the pilot resolver). |
| Identical everywhere present | `analyze_export.py`, `copy_deps.py` (live, handover, pilot); `dump_ccl_bundle.py`, `dump_ccl_transforms.py`, `summarize_defs.py` (live, handover); `handover_config.ps1` (handover, pilot); `loopify_wav.py` (live, handover update). |

Other copies of these scripts exist in James's workspace and were not repeated here *(checked locally, by hash)*: `_G29_Handover_Work\setup_check\tools` is byte-identical to `g29_handover/conversion/tools` (all 12 files);
`LLW G29 CONVERSION\updates\...\source_tools` is identical to `g29_live_tools` for every file present; `LLW G29 CONVERSION\reference\original-tools` is identical to
`g29_live_tools` except an older `setup_build_project.ps1`; `LLW Unified Builder\share\author_review_2026-09-26\builder\tools` is identical to `unified_builder/tools` (7 files).

## 6. What the scripts need

| Need | Where it comes from |
|---|---|
| Windows PowerShell | The launchers are `.ps1` files; their header comments show `powershell -File ...` (`g29_live_tools/run_unity.ps1:2-3`, `export_assetripper.ps1:2`) and the unified README runs `.\tools\run_build.ps1` (`unified_builder/README.md:23-35`). They use `robocopy` (`setup_build_project.ps1`: live `:12`, handover `:14`) and `Start-Process` on `Unity.exe`. |
| Unity Editor **2019.4.40f1** | `unified_builder/UnityProjectContext.md:6` ("2019.4.40f1 (ffc62b691db5)"; TextMeshPro 2.1.6, uGUI 1.0.0, Built-in renderer). Launch details: section 1, point 5. The scripts must run as the normal user for licensing (`unified_builder/README.md:21`). |
| **CarCreator 3.1.9** (`CarCreator_3.1.9.unitypackage`) | Named "CCL CarCreator 3.1.9 ... Proxies and wizards" (`docs/GUIDE_Railroader_to_DV_CCL.md:71`). Not included. Board `C13` (a proposal) lists it as "link, don't redistribute" and `unified_builder/MIGRATION_PLAN.md:41` says to keep "the CarCreator package" out of shared output. The build code calls CCL's `ExportPackWizard` and proxy types by reflection (`CclLocoBuild.cs:2953`). |
| AssetRipper (free GUI build, 2.0) | `export_assetripper.ps1`; `docs/GUIDE_Railroader_to_DV_CCL.md:69` and `g29_handover/REBUILD.md:15` give 2.0. The script drives its local HTTP form/API and warns that another release "may require adapting" (`REBUILD.md:82`). |
| Python + packages | `requirements.txt`. Computed with `ast` over all 43 `.py` files: **UnityPy** (12 files), **numpy** (9), **Pillow** (2), **PyYAML** (4); everything else is standard library. All 43 parse under Python 3.14. `pilots.py` and `catalogue_design.py` use `hashlib.file_digest` (3.11+). `run_build.ps1:6` defaults to a Codex-bundled `python.exe` (version 3.12.14 *(checked locally)*); `audit_build.py:4` and `oil_cup_survey.py:4` add the site-packages of a virtual environment recorded as Python 3.12.10 (`g29_handover/REBUILD.md:12`). |
| Source inputs | LLW Generic Locomotive Catalog 1.4.3 (`ls-*` folders with `Definitions.json`, `Catalog.json`, `Bundle`), the FoxTrucks mod folder (every file in `FoxTrucks/FoxTrucks` is hashed, `pilots.py:131-133`). Not included. |
| Railroader install | Only `extract_rr_audio.py` (both versions) and `catalogue_design.py` (`:14`). |
| Derail Valley install | Only the install scripts and the stock-part analysis scripts (`resources.assets`). A scan of every script and C# file found no DV path in `run_build.ps1`, `prepare.py`, or the C#. |
| Blender, AssetStudio, ilspycmd, .NET SDK | **None is invoked by any script here.** "Blender" appears only in comments about how the source models were exported (`G29Source.cs:7`; `docs/GUIDE_Railroader_to_DV_CCL.md:143,149`; the Codex guide's section heading at `:276`). `ilspycmd` is listed in the guide's tool table for decompiling by hand (`docs/GUIDE_Railroader_to_DV_CCL.md:72`). AssetStudio appears in neither the scripts nor the guides. |
| Environment variables | `G29_PYTHON`, `G29_UNITY`, `G29_ASSETRIPPER` (handover/pilot `.ps1`); `CCL_BUILD_OUT`, `RLW_BUILD_OUT`, `RLW_PROBE_OUT`, `LLW_PROBE_OUT`, `CCL_CATALOG_RECORD`, `G29_SHARE` (set by the launchers, read by the C#). |

## 7. What breaks when files move

- **Machine paths written into scripts** (James's PC): `B:\Games\Unity 2019.4.40f1\Editor\Unity.exe` (`run_build.ps1:30`, `run_c21.ps1:19`,
  `run_probe.ps1:4`, live `run_unity.ps1:14`); `B:\SteamLibrary\steamapps\common\Derail Valley\Mods` (live `install_build.ps1:7`, `install_c21.ps1:7`);
  Railroader paths (live `extract_rr_audio.py:4-5`, `catalogue_design.py:14`); DV `resources.assets` (three analysis scripts);
  `C:\Windows\Fonts\segoeui.ttf` (`oil_cup_survey_report.py:5`, `validate_oil_cup_survey.py:54`); the Codex Python (`run_build.ps1:6`);
  a virtual-environment site-packages and the workspace folders `Claudes Place` (`audit_build.py:4,9`, `prepare.py:8`, `oil_cup_survey.py:4`, live `setup_build_project.ps1:8-9`, live `export_assetripper.ps1:6`).
  The handover `.ps1` files and the pilot `export_assetripper.ps1` take paths from environment variables instead.
- **Sibling folders.** Scripts find each other with `Path(__file__).parents[1]` and folder names such as `LLW Generic Locomotive Catalog`,
  `LLW Pilot Workflows`, `LLW G29 CONVERSION/conversion`, `FoxTrucks` (`catalog.py:5-6`, `prepare.py:8-10`, `pilots.py:16-18`). This snapshot renames the folders
  (`unified_builder`, `pilot_workflows`, `g29_handover`, `g29_live_tools`); each folder keeps the internal layout of the folder it was copied from,
  but the sibling folders (catalogue, exports, Unity projects, builds) are absent.
- **Reference builds.** `audit_build.py:8-11` compares with G-29 `prerelease2` and C-21 `test17` build folders, which are not included.
- **Older C# cores are not included** (section 9). `pilots.py:195-196` copies `tools/unity/*.cs`; here that folder holds only `PilotProbe.cs`. The handover and live
  `setup_build_project.ps1` (`:78` and `:76`) copy `tools\unity\*.cs` with `$ErrorActionPreference = 'Stop'` (`:4`), and this snapshot has no such folder there; what they do was not tested.
- **Links inside copied files.** `unified_builder/README.md` links `docs/GUIDE_UNIFIED_LLW_CONVERSION.md`, which is at `docs/` in this snapshot.

## 8. The documents in `docs/`

Checksums for all of them are in `MANIFEST.sha256`.

| File | What it is |
|---|---|
| `GUIDE_Railroader_to_DV_CCL.md` | Claude's method guide: Part 1 general, Part 2 worked examples (RBBM-1t, RGB-2, GN M-2, G-29, ALCo 1610, C-21). "Findings and techniques, not a fixed recipe" (`:7`). |
| `GUIDE_Railroader_to_DV_CCL_CODEX.md` | Codex's own guide, "for the LLW C-21 project" (Claude guide `:9`). |
| `GUIDE_UNIFIED_LLW_CONVERSION.md` | Baseline LLW-DV-1.2: "normative builder specification + implementation source map" (`:8`). Rules are marked MUST, DEFAULT or DESIGN (`:19`); DESIGN means "proposed extension, not implemented". Its `$C/$L/$G/$P/$U/$H` aliases (`:29-38`) map to this snapshot as: `$U` = `unified_builder/`, `$P` = `pilot_workflows/`, `$H` = `g29_handover/`, `$G` = `g29_live_tools/` (scripts only), `$C` = `docs/` (four documents only). |
| `GUIDE_SHARED.md` | The Claude/Codex message board (protocol in its first 8 lines; message ids `C<n>` are from Claude, `X<n>` from Codex). Copied when this snapshot was made; the live board keeps growing. |

The two method guides describe older branches and cite paths such as `tools\unity\` in projects that are not part of this snapshot. The unified guide's `B01` (`:72`):
"Existing G/P tools are predecessor evidence, not active authority for the new builder."

## 9. Left out

- Game files, mod assets, meshes, textures, exports, `.unity3d`/asset bundles, built packs, Unity projects, audio, renders, build reports.
- `catalog/*.json` (26 files, 4,608,042 bytes in the original): generated, and each record embeds the catalogue authors' full source definitions (`source_objects`, `catalog.py:43`) *(size and count checked locally)*.
  `catalog.py` regenerates them from the catalogue.
- The CarCreator package and the two frozen reference builds.
- Older C# cores *(sizes checked locally)*: `pilot_workflows/tools/unity/{CclLocoBuild.cs, LocoConfig.cs, RRPlacementValidation.cs}` (196,558 / 18,211 / 11,347 bytes; only `PilotProbe.cs` was kept),
  `LLW G29 CONVERSION/conversion/tools/unity/` (6 files), and the G-29 `tools\unity` in `Claudes Place`. `B01` says to keep one shared core (`docs/GUIDE_UNIFIED_LLW_CONVERSION.md:72`)
  and board `X11` calls `unified_builder/tools/unity` the canonical new core (`docs/GUIDE_SHARED.md`, message `X11`).
- Per-build notes and data sheets (`TEST_NOTES.md`, `DATA_SHEET.md`) and analysis outputs cited by the guides.
- Not part of this pipeline going by what was read *(checked locally)*: `DV CCL AI Prep` (its README describes "a local Windows pipeline for turning very large Derail Valley CCL Unity bundles into
  compact, reusable AI working sets", built on AssetStudioModCLI; the guides do not mention it); the X4025 Big Boy UV-mapping tools and general bundle helpers in `Claudes Place\tools`
  (54 `.py`; only the first docstring line of each was read); `DVCCLControlFix` and `DVPositionSyncFix` (board `C14`: "helper mods not needed by either loco");
  `_G29_Update_Work` and `LLW G29 CONVERSION\verification\verify_pack.py` (file-copy and verification scripts for the author handover; only their first lines were read).
  Other locomotive conversions in `Claudes Place` (RBBM-1t, RGB-2, GN M-2, ALCo 1610, GWR 1366, MAV 475) were identified by folder name and were **not reviewed**.
- A pattern scan of every file in this folder (`docs/` included) for passwords, secrets, API keys, tokens, private keys, e-mail addresses and web addresses found no credentials.
  Its only matches were the local AssetRipper address `http://127.0.0.1:$Port` in the three `export_assetripper.ps1` copies and two Python matrix-multiply expressions (`m@np...`,
  `.T@np...`) that look like e-mail addresses to a pattern. The scripts and docs contain the Windows user name `james` in paths, and `C15` names the repo `james-taplin/llw-conversions`.

## 10. Not verified

- **No script was run** for this snapshot and no test was re-run. The 9 + 8 passing tests are what `VALIDATION.md` reports about the originals.
- Whether the launchers work without a Windows desktop session, on another OS, or with a licence that allows `-batchmode`. Only the facts in section 1 point 5 are known.
- Whether building needs a Derail Valley install. The build scripts (`run_build.ps1`, `prepare.py`) and the C# do not refer to one; the install scripts and the stock-part analysis scripts do. Nothing was built.
- Whether the older and newer copies of a script (section 5) give the same output on the same input. Only their bytes were compared.
- Which copy is "current" for G-29 import: live or handover. File times and contents are given; no session was asked.
- Whether `pilots.py prepare`, the setup scripts and the analysis scripts run end to end in this folder layout. They expect sibling folders that are absent.
- Python compatibility of UnityPy 1.25.3 / numpy / Pillow / PyYAML with anything other than the versions recorded in the original environment
  (`requirements.txt`). James's machine has Python 3.14.7 on its PATH *(checked locally)*; the recorded environments are 3.12.
- The documents were not read in full. The parts cited above were. The guides are long (445, 297, 288 lines) and were not checked line by line against the code.
  In-game results quoted in the guides and the board (for example board `C9`'s "IG = tested in game OK") are the sessions' own records and were not checked.
- Unity, CarCreator or AssetRipper versions other than those recorded.
- The contents of anything not in this snapshot (reference builds, catalogue records other than the counts in `catalog/index.json`, exports, `Claudes Place\tools`).

## 11. Corrections to the first version of these notes

The first zip had these errors, now fixed: it said measuring is done by hand (it is not, section 2); it called G-29 and C-21 "tested" (merged outputs are not game-tested);
it said the catalogue record supplies source data to profiles (only pony radii); it said `RRPlacementValidation.cs` checks plates and end beams (it checks drawbar spacing/pins and the final
handbrake and release poses; plates are checked by `audit_build.py`, the end beam by `EndBeam`); it said the unified `resolve_clip_paths.py` supersedes the older ones and that setup calls it (the older ones are what setup and
`pilots.py` call, and were missing from the zip); it left out `audit_c21.py`, `PilotProbe.cs` and the analysis scripts; it said the launchers cannot run headless or on Linux (not established);
it said `install_build.ps1 -ModsPath` was optional (mandatory in the handover copy); it described the pilot `config/*.json` as regenerable (`prepare` refuses to overwrite an existing project); it listed Unity as needing internet
(the handover `REBUILD.md` says it "may need package download access"); and it used looser wording that the files do not support: `*Config.cs` as "hand-tuned", `*Source.cs` as "source pins",
`UnityProjectContext.md` as "the Unity project layout", and a tidy step order that was my own arrangement rather than the authors' (section 3 now follows theirs).
