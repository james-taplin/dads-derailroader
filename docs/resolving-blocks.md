# When a conversion stops: how to resolve it

`rr2dv` distinguishes source facts, measured candidates and labelled starting assumptions. Unresolved or ambiguous
items require review. This page covers each case and what to do about it.

**Engine specifications:** review cylinder bore/stroke (inches), boiler pressure (psi gauge), heating area (ft²),
simulation boiler dimensions (metres), capacity factor and coal-consumption adjustment. Each field shows its
origin and has a Restore button. Boiler basis values describe the inherited simulation, not the prototype.
When editing capacity, spawn water scales to preserve the existing fill fraction. Heating-area edits retain the
existing injector/firebed approximation. Coal adjustment changes coal required for the simulated firebed; it is
not a historical burn-rate measurement or an oil-firing model.

The live nominal TE estimate uses the existing 0.85-pressure convention, physical cylinder count, driving radius
and selected fixed gearing. Factor of adhesion uses **weight on driven wheels**, never total locomotive weight.
Published TE is an optional comparison; editing it does not retune the engine. The legacy equivalent-bore profile
shows its separate calibration target. These are simple-expansion estimates, not measured drawbar pull or a
validated compound-engine model. Bad numbers, non-finite values, and partial boiler dimensions are rejected before
building. Leave both optional dimensions blank to inherit the basis, or restore their suggested values.

**The app asks for vehicle choices after measuring the source.** In 0.1.3 it fills source facts, suitable tyre
candidates and labelled defaults, and restores previous choices for an unchanged vehicle/source automatically.
Confirm or change the fields directly; no JSON file or offline build folder is required. Measured tyre candidates
are available in the review window. Geared wheel roles use named groups rather than numerical indices. Unknown
ratios still require input. Advanced JSON import remains optional. After fixing another block, convert again from
the start. Every run gets a fresh temporary folder and the input mod is never changed. By default the temporary
inputs, ripped assets, Unity project and build intermediates are permanently deleted when the run stops or finishes.
Answers and a rebuild recipe survive in `<workRoot>/reports/<run-id>`. Reruns re-extract and re-import.
Remembered choices also survive in `<workRoot>/reviews`, keyed to vehicle, source, adapter and track catalogue.
Changing any of these identities requires a fresh review; confirmation is never carried over automatically.
Only explicit developer setting `"keepWorkFiles": true` enables retained workspaces and shared caches.
The recipe records source/code/tool hashes and choices; byte-identical Unity rebuilds have not been verified.

## First: where to look

Start with the logs:

- **`run.log`** in the run folder (the app's **Open run folder**, or the path printed at the end of `convert`): the whole
  run in order, readable. It records the settings, tools and game installs used; your answers; every stage as it
  starts and ends; every issue found; what AssetRipper and Unity reported; the review items; and, if something
  unexpected went wrong, the full error traceback. **This is the file to send when asking for help.**
- **The app log**, `%LOCALAPPDATA%\rr2dv\logs\rr2dv.log` (**Settings… → Open app log**): what happens outside a
  run, from the app and the command line: commands, games found or not, mods listed, and every unexpected error with
  its traceback. It keeps the last five files of 1 MB.

Then:

| Where | What it tells you |
|---|---|
| The app's **Checks** list (or `rr2dv scan "Mod"`) | problems found before converting: red ✗ blocks, amber ! is a warning, i is information |
| The app's **Conversion** panel (or the `convert` output) | which stage stopped, and the reason in one line |
| `rr2dv doctor` (or **Settings… → Check**) | anything wrong with the tools or the game installs |
| The run folder (**Open run folder**, which also works after a conversion stops) | the full record, see below |

Normal report files include `run.json`, `run.log`, `rebuild.json`, `record/vehicle-record.json`, `review.json`,
`blocks.json`, `build_report.txt`, `prep.json`, `audit.json` and diagnostic log tails where available.
The finished pack is at `run.json`'s `output` path; **Open build folder** opens it. If cleanup is pending, the report
names the retained temporary path and error; close anything holding it and start another conversion to retry.
Original-source/game/tool folders and unmarked legacy workspaces are never part of this automatic deletion.

The following detailed intermediate paths exist during conversion or with developer retention enabled:

| File | Look here for |
|---|---|
| `run.log` | the readable diary of the run (above) |
| `run.json` | every stage's status and message, and your answers (machine-readable) |
| `inventory.json` | the `issues` list: every error, warning and note, with a code |
| `index_issues.json` | problems reading other mods while searching (usually harmless) |
| `import/clips-*.json`, `import/clips-*-bindings.json` | how each animation's paths were restored, and every decision (bound to a model, left out, kept with absent targets) |
| `import/clips-*-diagnosis.json` | written when an animation stops the import: which model names it, how many of its targets each model has, and where each missing target is found |
| `probe/unity-1.log`, `probe/result.json`, `probe/probe.json` | what Unity reported while measuring the model; `probe.json`, `result.json` and `probe-input.json` are kept in `reports/<run>/probe/` after cleanup (measurements only, no ripped assets) |
| `record/vehicle-record.json` | the draft record: `metadata.pending` (review items), `metadata.wheelCandidates`, `metadata.leftOut` |
| `build/blocks.json` | why the build stage stopped, one entry per thing to resolve (with the measured candidate for the wheel radius) |
| `build/vehicle-record.json`, `build/review.json` | the record the pack was built from, and every choice made automatically to complete it (`choices`), for review |
| `build/out/build_report.txt` | our builder's full report: every step, every `WARN`, and any `EXCEPTION` that stopped it |
| `build/out/*.png` | the builder's renders: outside, cab, lamps, markers (oil cups, plates, cab teleport, targets), couplers |
| `build/out/prep.json` | what was done to the project before building: animation bindings removed, AudioSources removed, parts placed |
| `build/out/<pack name>/` | the exported pack (`Info.json` and the bundle), before installing |
| `audit/summary.json`, `audit/audit.json` | the audit's findings: errors (stop the install), notes, and the builder's warnings |

Command-line exit codes: `0` installed, `1` stopped (a block, or an error), `3` stopped cleanly and waiting for you: an
answer is needed (the wheel radius), or the pack was built and audited but not installed (the notice was not agreed to).

## Before a conversion starts

| Message says | Why | What to do |
|---|---|---|
| Railroader / Derail Valley *was not found in any Steam library* | the game is not in a Steam library `rr2dv` can see | set `railroader` (or `game`) to the install folder in **Settings…** or the settings file |
| *is installed in several Steam libraries* | more than one copy was found | set `railroader` (or `game`) to the one to use |
| *not found at …* (*no Railroader_Data* / *no DerailValley_Data folder*) | the folder in the settings is not the game's install folder | point the setting at the folder that contains `Railroader_Data` / `DerailValley_Data` |
| *Derail Valley has no Mods folder* | Unity Mod Manager is not installed in Derail Valley | install Unity Mod Manager, then Custom Car Loader |
| *Railroader has no Mods folder* | Railroader's own `Mods` folder is missing | restore it (it is where Railroader mods are installed); Derail Valley tools do not fix this |
| *Custom Car Loader … is not installed* | CCL is missing from Derail Valley's `Mods` folder | install Custom Car Loader 3.1.9 |
| *… is not set up: add `unity` / `carCreator` / `assetRipper`* | a tool path is missing | set it in **Settings…**; `rr2dv doctor` checks them |
| *is not a mod folder in the Railroader Mods folder* / *not an archive* | the mod was given as a zip or from another folder | install the mod into Railroader's `Mods` folder and choose it there; zips are not accepted |
| *the work folder path is N characters* | Unity 2019.4 fails on long paths | set `workRoot` to a short folder, at most 74 characters, e.g. `C:\rr2dv` |
| *refusing to write inside …* | the work folder is inside the mod or a game folder | choose a work folder outside them |

## Stage `locate`: choosing the locomotive

| Message | What to do |
|---|---|
| *the input has several steam locomotives; choose one with --loco* | pick one: in the app, select it in the list; on the command line add `--loco <id>` (the ids are listed in the message and by `rr2dv scan`) |
| *no steam locomotive found in the input* | the mod has no steam locomotive (diesels and other cars are not converted) |
| *not a steam locomotive in the input* | the `--loco` id is misspelt or belongs to another mod |

## Stage `link`: what the loco needs (codes from `inventory.json`)

Blocking (red ✗ in the app):

| Code | Why | What to do |
|---|---|---|
| `missing-tender`, `missing-truck`, `missing-part-pack` | the loco uses a tender, truck or part pack from another mod that is not installed | install that mod into Railroader's `Mods` folder (the message names what is missing), then convert again |
| `ambiguous` | two installed mods provide the same thing at the same level, and `rr2dv` will not pick one | move the duplicate copy (often an old version of the same mod) out of the Railroader `Mods` folder, then convert again. Disabling it in a mod manager may not be enough: `rr2dv` reads every folder in `Mods` |
| `pack-unreadable`, `missing-bundle` | a pack the loco needs has a broken `Catalog.json`/`Definitions.json` or no `bundle` file | reinstall or update that mod; if it is broken at the source, report it to its author |
| `no-model`, `bad-part` | the loco's definition is incomplete | this needs a fix in the mod itself; report it to its author |
| `needs-answer` (sounds) | the definition has no heating surface, so the S060/S282 sound rule cannot decide | choose the sounds yourself: command line `--audio S060` (small engines) or `--audio S282` (big engines). **Known issue:** the app's Sounds dropdown does not clear this block yet (Convert stays greyed out); use the command line for these locos for now |
| `not-found`, `not-steam` | the chosen id is not a steam locomotive here | choose another locomotive |

Not blocking, but worth reading (amber ! in the app):

| Code | Meaning |
|---|---|
| `left-out` | a part the mod references but does not contain (Railroader cannot load it either) is left out; anything attached inside it goes too, and is named |
| `missing-texture`, `ambiguous-texture` | an image (logo, decal) was not found, or found twice; it is left out |
| `code-mod-component` | the loco relies on a Railroader code mod (e.g. LegosBetterSteam) for its behaviour; its Derail Valley simulation must be set deliberately. Vehicle choices shows what the mod's settings in the definition mean (never its code): for LegosBetterSteam's articulated engine, "Pull to build to" offers the mod's compound and simple pull (the mod's own mode first) and the published or plain Railroader figure; with the legacy-equivalent profile the equivalent bore is sized to the chosen pull. Other code-mod components have their settings listed, with multipliers, ratios and gearing flagged |
| `pack-folder-mismatch`, `model-not-in-catalog`, `tender-archetype`, `unreadable-definitions` | the mod is laid out unusually; the conversion continues, check the result |

## Later stages

| Stage | Message | What to do |
|---|---|---|
| `stage` | *… changed while it was being copied* | something (a mod manager, a sync tool) wrote to the mod during the copy; wait until nothing is writing, convert again |
| `extract` | *AssetRipper exited during startup / did not start / produced no ExportedProject* | check `assetRipper` in settings and the retained report; full export/cache diagnostics require an explicit developer-retention rerun; a newer AssetRipper may need testing first |
| `extract` | *cache entry … is inconsistent* | delete the named folder under `<workRoot>\_cache\assetripper` and convert again |
| `import` | *animation clips fit several prefabs and the source does not say which* | the mod's animations could belong to more than one model and nothing in the mod says which. `import/clips-*-bindings.json` lists each clip and every model that names or references it. Report it on the app board; this needs a decision in `rr2dv`, not a guess |
| `import` | *resolve_clip_paths: N clip(s) did not resolve … No prefab resolves every clip binding; …* | an animation targets objects that no single model in the pack has all of, and the rest of the message says why `rr2dv` will not keep it: *… name it* (several models' clip maps name the animation), *no prefab's clip map names it*, or *lacks targets that other prefabs have* (the missing targets live in another model file). Open the `import/clips-*-diagnosis.json` the message names: for each animation it lists which model's clip map names it, how many of its targets each model has, and each missing target's `found_in`. Report it on the app board with that file; the fix is decided in `rr2dv`, never guessed. (When exactly one model names the animation and its missing targets are in no model of the export, the conversion does not stop: see *animation …* under review items.) |
| `import` | *the model … is not in the exported pack …: the pack's Catalog.json names it, but the export holds these prefabs: …* | the pack's catalogue names a model file the ripped bundle does not contain under that name. The message lists the prefabs it does contain. Check the dependency mod is installed and up to date (Railroader could not load it either); if it is and the list shows the model under another name, report it on the app board with the message |
| `import` | *duplicate GUID* | two assets in the combined project claim the same identity; report it with the run folder |
| `probe` | *scripts did not compile* | Unity could not compile our probe; the log path is in the message. Check the Unity version is exactly 2019.4.40f1 |
| `probe` | *is open in another Unity editor* | close that Unity window, convert again |
| `probe` | (seems stuck on *Measure the model*) | normal on a fresh project: Unity's splash and import window can appear and importing takes minutes (S-16 about 2, C-21 about 4; texture-heavy mods such as the PLW Trojan took 10 before rr2dv stopped importing textures no converted model uses; `unity/project.json` `unused_textures` lists what was left out). It is not hung while `probe/unity-1.log` keeps growing |
| `probe` | *did not finish … within … s* / *wrote no result.json* | see `probe/unity-1.log`; a licence prompt or a crash is the usual cause. Open Unity once by hand to settle the licence, then convert again |
| `record` | *definition lacks maximumBoilerPressure / pistonDiameterInches / …* | the loco's definition is missing figures the simulation needs; report it to the mod's author |
| `record` | *livery … is not one of …* | choose one of the liveries listed in the message (`--livery`, or the app's Livery box) |

## Stage `build`

X43 preparation fixes: unsupported missing-script components are removed only from this run's copied prefabs,
with each hierarchy path and count in `prep.json` (`audioStripped[].missingScripts`). Valid components remain.
Every changed prefab and composite must save successfully and reload before the builder runs; a failure is reported
as preparation failure. Railroader code DLLs are never imported to satisfy missing scripts.

`build/review.json` is also written when record completion is blocked, with `status: blocked`, the choices reached
so far and the blocks. It is diagnostic evidence, not a completed build record. The wheel-radius question offers
only a powered wheelset's candidate, preferring `mainDriverIndex`; it does not substitute a pilot wheel when the
driving candidate is unavailable. Suggested CLI reruns preserve a custom global `--machine` argument.

Models without a named material map can use explicit renderer material references when no livery colours need
mapping. Their `renderer:<guid>` keys are asset identities, not tint names. The builder leaves them untinted;
its exact `no colour` warnings remain in the report for review. Source colourizer choices and appearance remain
pending. A model with livery colours but no named tint map stops with `untinted-livery`; supply a reviewed mapping
through a future supported adapter rather than guessing colour IDs. Missing renderer slots still remain pending.

For car-space control anchors with no parent path, a handle is matched only when its clip has one animated hierarchy
within the source control radius. The choice is recorded; it does not validate grip ownership, travel or response.
Ambiguous hierarchies, distant pivots and absent bindings retain the disclosed generated-control fallback.
Nested load animations are created child-first so moving a parent into an animator group does not lose the child's
source path. `animation-order` means two clips have conflicting parent/child ownership and need binding review.

The build first completes the draft record from the definitions and the measurements (every choice it makes is listed
in `build/review.json`), then builds the pack with our builder in Unity. It stops with a block when something cannot
be worked out; `build/blocks.json` lists them all at once.

If the source has no `CylinderCock` (PLW Trojan), the vehicle record adds an estimated drain-jet and sound anchor 1.0 m
ahead of the leading driver at axle height, 80% of the model's half-width (at most 1.1 m) each side. `build/review.json` lists its position; check the placement in the build renders and in game.

| Code / message | Why | What to do |
|---|---|---|
| `needs-wheel-radius` (*the driving wheel tread radius needs your review*) | no driving tyre radius was confirmed; legacy callers may reach this block directly | normally confirm the populated radius or select a measured candidate in **Vehicle choices** during the same conversion. If the run already stopped, use the candidate shown in the report and convert again. `--wheel-radius` remains available for scripts. Normal reruns use fresh temporary workspaces |
| `missing-anchor` (*no Chuff (chimney) / Whistle component*) | the builder places chimney and whistle effects and sounds from these Railroader components | the mod's definition lacks one; report it on the app board with the loco id |
| `drivers-not-found`, `drivers-no-clip`, `no-drivers`, `one-axle` | the driving wheels could not be matched to turning wheels in the model | when the definition gives one driving axle over a long wheelset (the Western Maryland H9 gives 1 over 5.5 m) and the model shows several wheels at axle height there, the model's count is used and listed in `review.json`, so that case no longer stops. Likewise when the model's driving wheels sit as a whole set away from the definition's positions at the definition's spacing (RLW ROF-1: 0.875 m), or a single driving wheel within 1 m of the definition's axle (RLW RPP-1: 0.5 m). A wheel's pivot must be within 2 m of the centreline. Otherwise the message says what the wheel clip turns and why each mesh under it was not used; report it with `probe/probe.json` (its `wheels`), kept in the run's reports folder |
| `no-backhead` | no flat backhead plate was found from the cab, and the definition has no firebox glow to fall back on | report it with `probe/probe.json` (`cabRays`) |
| `no-room-for-controls` | too little flat backhead plate for the generated controls, (a leaning backhead counts as one plate: hits within 3 cm of a fitted sloped plane), even after trying the upper plate (to 1.7 m above the fire door) and then 0.15 x 0.2 m spacing | report it with `probe/probe.json` (`cabRays`) |
| `tender-trucks`, `truck-wheels`, `tender-data`, `tender-empty` | the tender's trucks, their wheels, or its weight and load slots could not be found | report it with the tender and truck ids; the message says which. A truck whose wheels are modelled into its frame (no separate wheel objects) is built as a fixed truck on Derail Valley's default layout (axles ±1.0 m, radius 0.459 m; the wheels do not turn) and listed in `review.json`. Truck wheels are found by name: objects whose name contains `wheel` or starts with `whl`; each axle's own node is then renamed `rr2dvWheel_N` in the run's truck copy, so a container holding both axles is never turned as one |
| `no-materials`, `no-weight`, `no-geometry`, `probe-missing` | the model or definition lacks something every build needs | report it; the message names it |
| *the builder did not export a pack: EXCEPTION …* | our builder stopped while building (the most common: *insufficient end-beam rays* when no buffer beam is found at coupler height, or a placement check for the handbrake wheel or brake release) | send `build/out/build_report.txt` and `run.log`; the renders in `build/out` often show the cause |
| *Vehicle record validation failed* | the loader rejected the record (a `rr2dv` bug: the record is checked before Unity starts) | send `build/out/build_report.txt` and `build/vehicle-record.json` |
| *preparing the Unity project failed* | removing the listed animation bindings, removing AudioSources, or placing a part failed | send `build/out/prep.json` |
| *scripts did not compile* | as for the probe | check the Unity version is exactly 2019.4.40f1 and that CarCreator 3.1.9 is the package set in the settings |

### Reviewed end-beam geometry

If the default sampling heights miss the actual frame, the builder now automatically searches lower heights
for a broad, upright end face supported on both sides of the drawgear. The build report records its measured
height band and depth. If that also fails, an *ambiguous end beam* or *insufficient end-beam rays* error still
requires review. Measure the current model first, including the broad beam face and nearby coupler/lift hardware.
Do not choose a band merely because it passes. The height band changes where the existing rays sample; it does
not change coupler height, the minimum ray count, clearance checks or any acceptance requirement.

For a reviewed correction, choose **Reviewed geometry** in the app, or pass `--geometry-review FILE` to `convert`.
The JSON has this shape (replace the fingerprint, car id, heights and evidence with the current measurements):

```json
{
  "schema": 1,
  "inputFingerprint": "copy input_fingerprint from the measured run.json",
  "vehicles": {
    "source-car-id": {
      "EndBeamProbeHeight": {
        "value": [1.0, 1.2],
        "unit": "m",
        "basis": "derived",
        "evidence": ["measurement report, beam bounds, ray counts and review reasoning"]
      }
    }
  }
}
```

Only the selected locomotive and its tender may be named. Each band must lie in 0..2 m, span 0.1..0.4 m, and have
`measured` or `derived` provenance with nonempty evidence. No other config fields are accepted. A changed source
fingerprint stops before extraction: remeasure it. The file's contents are copied into the run's
`geometry-review.json`, answers and build record so later edits to the input file cannot change that run.
An explicit override remains a manual geometry review and will not be silently replaced by an automatic band.
Automatic beam placement is a build-time measurement, not in-game acceptance: check that the stopcock, hook
and hanging hose end are reachable. Cosmetic overlap with decorative pipework is acceptable.

Material slots: a slot the export left empty or filled with Unity's white `Default-Material` (Railroader base-game
truck rims, the `…deadbeef…` references) is given rr2dv's own dark matte gunmetal
(`src/rr2dv/unity/materials/rr2dv_gunmetal.mat`), and a slot whose material is named `…glass…` gets rr2dv's own clear
glass (`rr2dv_glass.mat`). An empty slot on a part named `…coal…` gets a bump-mapped coal (`rr2dv_coal.mat`), and
glass on a lamp gets a pale opaque lens (`rr2dv_lens.mat`) so the lamp's hollow inside does not show. The whole car
is searched, trucks included (tender truck rims). A tender whose model has no coal of its own (Railroader draws it at
runtime) gets a generated coal heap in its coal space, rising and falling with the coal amount. All
are listed in `build_report.txt` (`rr2dv material fallback`, `rr2dv glass`).

Main driver with nothing behind it: when the definition's `mainDriverIndex` names a wheelset with no animation and no
model part (ALCo 3-cylinder Mikado), and exactly one animated wheelset has the same axle count over the same span, that
one is the main driver and the empty one is left out (listed as a choice). This used to stop the build with
`drivers-not-found` / `drivers-no-clip`.

Cab controls: the walkable/items copies of the mod's own collision meshes let the control-grab ray pass through
(`rr2dv grab rays pass through` in `build_report.txt`), so a handle you can see is never hidden behind an invisible,
blockier collision shell. You still stand on and walk into them.

Brake release: hinted 0.5 m inside the loco's rear end, under the cab, where the rod stays clear of pipes and valve
gear; when the fitted seat at the hint is below the 0.30 m clearance floor (a low frame, Reading B8a
camelback), the hint moves along the frame in 0.4 m steps to the first seat that clears it (`rr2dv brake release: … moved`).

Oil cups are seated, per side and axle, on a rod big-end nub (islands of 20+ triangles), else on a flat top of the
running gear (big ends, crossheads, axlebox tops; a cup on a moving part rides with it), else on the running board. A
pair with no seat on either side is left out (`rr2dv oil pair … omitted`).

Dynamo (Vehicle choices): suggested from the Railroader definition (a `Dynamo` component or not). With "no", the pack
has no electric lamps, cab light, or Dynamo/Cab light/Headlights backhead controls, and the HUD has no dynamo or
headlight controls; the dynamo stays off, so no dynamo steam jet.

Whistle closed (0) is always the whistle handle's resting end. When a Railroader whistle handle is modelled at the end of
its clip rather than the start, the lever uses the clip reversed (`RR control …: its handle rests at the end of …`).
Generated whistle levers rest at 0 already.
The steam exhaust reads the whistle through a 5% deadzone (`rr2dv whistle closure` in `build_report.txt`): a lever that
settles a fraction short of closed after use still commands exactly 0, so there is no constant low chime (CTRL-02).

A Railroader cab handle that does not swing in its own animation (the GN L-27's throttle slides 50 mm) cannot become a
Derail Valley lever: a generated backhead lever works that function, the modelled handle follows the same setting, and
`review.json` says so.

A door, window or hatch animation (Railroader `ToggleAnimation`) that cannot be resolved (no clip, no or ambiguous
target, a clip that does not move its declared target, overlap with another moving assembly) no longer stops the build:
that one animation is left out, its model stays as modelled, and a `WARN rr2dv ancillary toggle '…' left out` line in
`build_report.txt` names it and says why (L-27: a second roof-hatch toggle). Driving controls keep their hard checks.
A rigged opening, whose clip moves the bones inside its declared target (the H9's windows, deflectors and roof hatch),
is kept: the whole declared assembly, mesh and bones, becomes the opening, and it opens with a click.

Generated backhead controls are placed against the visible model only: a model whose own collision shape has no
backhead face (Reading B8a camelback) no longer loses every control with `no backhead found`.

Number plates are seated on a flat side first, then on a curved or panelled side (a saddle tank); if neither fits,
the plate stays at the source decal with `WARN plate …: no fully supported visible surface` instead of stopping the build.

## Stage `audit`

The audit loads binary bundles, excluding text `.manifest` sidecars, then follows the pack's serialized references
to cars, prefabs and their components. Dependencies need not appear as separately named bundle assets. Reference
cycles are deduplicated; missing components, forbidden scripts and referenced audio still fail the audit.

The audit reads the exported pack with Unity's own loader, in a second Unity run, before anything is installed.

| Message | Why | What to do |
|---|---|---|
| *AudioClip(s) in the bundle* / *audio in the built car's dependencies* | Railroader audio must never reach a pack; every sound is a stock Derail Valley sound | report it: it means a model carried audio that was not removed |
| *behaviour outside CCL.Types* / *missing behaviour script* | only Custom Car Loader's own components may be in a pack | report it with `audit/audit.json` |
| *no control for the HUD's …* / *no control feeds …* | a control the HUD and keyboard need was not built (usually a generated backhead control that found no plate) | check `build/out/build_report.txt` for the control's `WARN`, report it |
| *car type … mass / wheel radius* | the pack does not carry the recorded values | report it |
| *BR-01: brake release … is not upright with its handle outward* | the stock brake-release fitting was placed rolled or turned (board X41) | report it with `build/out/build_report.txt` and the `markers_*` renders |
| *the HUD has no reading for …* (a note, not an error) | the model has no instrument for that reading (for example no brake-pipe gauge) | nothing to do; the HUD shows no value there |

A passed audit is **not** acceptance: the pack is a candidate until it has been checked in game (below).

## Stage `publish`

| Message | What to do |
|---|---|
| *the personal-use notice was not agreed to; nothing was installed* | the pack was built and audited; convert again when you want to install it (the rerun reuses the imported project) |
| *already exists and was not made by rr2dv* | a folder of that name in Derail Valley's `Mods` belongs to another mod; `rr2dv` never touches it. Rename or remove it yourself if you want this conversion there |
| *cannot show the personal-use notice* | the notice needs a window (Tk); run from a desktop session |

## After installing: checking the candidate in Derail Valley

Every installed pack is a candidate. Before calling it done, go through the twelve gates in the README's *What a
finished pack must pass* (board X42) for each control and each input route (grabbing, HUD, keyboard; VR if you use it):
every control moves in fine steps across its full range, holds where it is left, and momentary controls (the whistle)
return; nothing sticks, lags or overshoots (CTRL-01). A closed throttle and a closed whistle give no steam flow at all
under pressure, also after saving and loading (CTRL-02). The brake release stands upright with its handle outward
(BR-01). Then the brakes, lamps, the cab teleport, coupling (and the tender), oiling and firing. `build/review.json`
lists what was chosen automatically and is worth reading first; post what you find on the app board.

## Review items: `metadata.pending` in the draft record

These do not stop a conversion. They are values `rr2dv` will not make up, so a person has to confirm them before a
pack can be accepted. Each item says what is missing and where its evidence is.

| Item | How to resolve it |
|---|---|
| `WheelRadius` (and `steamEngine.cylinderBore`, which follows from it) | `metadata.wheelCandidates` gives the probe's tread candidate for each wheelset: the lateral band it came from, the flange radius, the meshes it used, a confidence and notes. **The candidate is evidence, not a measurement, and "high" is only the selector's confidence.** Before entering a value, check the tyre itself: in Unity, measure the tread across the tyre width (not the flange, not an inner rim) around the axle, and confirm the meshes used are the wheels (a rod or link among them, as on the C-21, means the candidate needs a closer look). Our reviewed S-16 tread is 0.488783 m, the mean of the tyre rings; the probe gave 0.48889 m. Then convert again with the reviewed value: app **Wheel radius (m)**, or `--wheel-radius 0.488783` on the command line. Until then it stays pending |
| `poweredAxles` | the powered axles were inferred from equal wheel diameters; check the model's coupling rods drive them all |
| `WeightEmptyKg` | confirm what the mod's weight means (working order, empty, with water); the mass ledger follows from it |
| `simulation: draft engine, boiler, firebox and exhaust choices` | starting values from our reviewed S-16 record; they need tuning per engine during the build and in-game tests |
| `simulation: nonstandard running gear (…)` | an articulated or otherwise unusual engine: its pull and cylinders need setting deliberately |
| `simulation: carries …, not coal` | an oil burner or similar: Derail Valley simulates a coal-fired boiler, review firing |
| `animation …: N of its M bindings target objects that are in no model of the export` (or *animates nothing in the exported model*) | the mod's animation points at objects that are not in its exported model (GN A-18: 3 of the 40 `Drivers` targets, and the only `Whistle` target). The targets it does have are restored; the others are listed in `metadata.absentBindings` and are removed during the build, before our builder, which rejects them. We only know they are absent from AssetRipper's export, not how Railroader treats them, so check in Railroader and in the converted pack that nothing that should move is missing. For an animation with no target at all (*animates nothing*), also check the control it belongs to (for example the whistle) still works without it |
| `left out: N part(s)` | see `metadata.leftOut` for each part, why, and what it takes with it; check the loco still looks and works right |
| `materials: N renderer(s) have an empty material slot` | the export already has an unresolved material in that slot (GN A-18's base-game truck); `rr2dv` neither guesses a replacement nor drops the slot. Check that part in the renders (`build/out`) and in game |
| `Bogies`, `CollisionBoxes`, `boiler …`, `tender: trucks layout …` | the build stage completes these from the measurements by fixed rules and lists each in `build/review.json` (bogies pivot on the end drivers; one collision box from the model's bounds within the car ends; the boiler keeps Derail Valley's basis boiler until measured); check them in the renders and in game |

## Still stuck?

Post on the app board (`board/APP_BOARD.md`) with the run folder name, the stage, the exact message and the relevant
part of `run.log` (or `rr2dv.log` if no run was started). The report includes a rebuild recipe and bounded diagnostics;
nothing in it is shared unless you share it.
