# When a conversion stops: how to resolve it

`rr2dv` never guesses. When something is missing, ambiguous or needs your decision, it stops and says why, or lists
the item for review. This page covers each case and what to do about it.

**The tool cannot ask you questions mid-conversion or resume a stopped run yet.** You give your answers when you
start a conversion (command-line options, or the app's Options row), and after fixing a block you convert again from
the start. That is safe: every run gets a fresh folder, the input mod is never changed, and AssetRipper exports are
cached, so a rerun skips the slowest step. Your answers are saved in the run, so the same answers give the same result.

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

Inside a run folder:

| File | Look here for |
|---|---|
| `run.log` | the readable diary of the run (above) |
| `run.json` | every stage's status and message, and your answers (machine-readable) |
| `inventory.json` | the `issues` list: every error, warning and note, with a code |
| `index_issues.json` | problems reading other mods while searching (usually harmless) |
| `import/clips-*.json`, `import/clips-*-bindings.json` | how each animation's paths were restored, and every decision (bound to a model, left out, kept with absent targets) |
| `import/clips-*-diagnosis.json` | written when an animation stops the import: which model names it, how many of its targets each model has, and where each missing target is found |
| `probe/unity-1.log`, `probe/result.json`, `probe/probe.json` | what Unity reported while measuring the model |
| `record/vehicle-record.json` | the draft record: `metadata.pending` (review items), `metadata.wheelCandidates`, `metadata.leftOut` |

Command-line exit codes: `0` finished, `1` stopped (a block, or an error), `3` stopped cleanly at a stage that is not
built yet (currently `build`).

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
| `code-mod-component` | the loco relies on a Railroader code mod (e.g. LegosBetterSteam) for its behaviour; its Derail Valley simulation must be set deliberately |
| `pack-folder-mismatch`, `model-not-in-catalog`, `tender-archetype`, `unreadable-definitions` | the mod is laid out unusually; the conversion continues, check the result |

## Later stages

| Stage | Message | What to do |
|---|---|---|
| `stage` | *… changed while it was being copied* | something (a mod manager, a sync tool) wrote to the mod during the copy; wait until nothing is writing, convert again |
| `extract` | *AssetRipper exited during startup / did not start / produced no ExportedProject* | check `assetRipper` in the settings and the log folder named in the message (a `.failed-…` folder in the cache keeps it); a newer AssetRipper may need testing first |
| `extract` | *cache entry … is inconsistent* | delete the named folder under `<workRoot>\_cache\assetripper` and convert again |
| `import` | *animation clips fit several prefabs and the source does not say which* | the mod's animations could belong to more than one model and nothing in the mod says which. `import/clips-*-bindings.json` lists each clip and every model that names or references it. Report it on the app board; this needs a decision in `rr2dv`, not a guess |
| `import` | *resolve_clip_paths: N clip(s) did not resolve … No prefab resolves every clip binding; …* | an animation targets objects that no single model in the pack has all of, and the rest of the message says why `rr2dv` will not keep it: *… name it* (several models' clip maps name the animation), *no prefab's clip map names it*, or *lacks targets that other prefabs have* (the missing targets live in another model file). Open the `import/clips-*-diagnosis.json` the message names: for each animation it lists which model's clip map names it, how many of its targets each model has, and each missing target's `found_in`. Report it on the app board with that file; the fix is decided in `rr2dv`, never guessed. (When exactly one model names the animation and its missing targets are in no model of the export, the conversion does not stop: see *animation …* under review items.) |
| `import` | *duplicate GUID* | two assets in the combined project claim the same identity; report it with the run folder |
| `probe` | *scripts did not compile* | Unity could not compile our probe; the log path is in the message. Check the Unity version is exactly 2019.4.40f1 |
| `probe` | *is open in another Unity editor* | close that Unity window, convert again |
| `probe` | (seems stuck on *Measure the model*) | normal on a fresh project: Unity's splash and import window can appear and importing takes minutes (S-16 about 2, C-21 about 4). It is not hung while `probe/unity-1.log` keeps growing |
| `probe` | *did not finish … within … s* / *wrote no result.json* | see `probe/unity-1.log`; a licence prompt or a crash is the usual cause. Open Unity once by hand to settle the licence, then convert again |
| `record` | *definition lacks maximumBoilerPressure / pistonDiameterInches / …* | the loco's definition is missing figures the simulation needs; report it to the mod's author |
| `record` | *livery … is not one of …* | choose one of the liveries listed in the message (`--livery`, or the app's Livery box) |
| `build` | *stopped before 'build' … not implemented yet* | expected for now: everything up to the draft record is done. Review the draft record (below) |

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
| `Bogies`, `CollisionBoxes`, `boiler …`, `tender: trucks layout …` | come from measured geometry in the build stage (not written yet) |

## Still stuck?

Post on the app board (`board/APP_BOARD.md`) with the run folder name, the stage, the exact message and the relevant
part of `run.log` (or `rr2dv.log` if no run was started). The run folder has everything needed to look into it;
nothing in it is shared unless you share it.
