# derailroader

**Convert the Railroader steam locomotives you already have installed into Derail Valley locomotives.**

`derailroader` (command line: `rr2dv`) takes a steam locomotive mod from your own Railroader `Mods` folder,
rebuilds it for Derail Valley's Custom Car Loader (CCL 3.1.9), checks the result, and installs it into your own
Derail Valley `Mods` folder. It works the same way for any locomotive, with no per-locomotive scripts, and it never
changes the Railroader mod it reads.

![The derailroader app](docs/app-window.png)

> **Status: working, in active testing.** Every stage runs end to end, from finding the mod to installing the pack.
> Locomotives built and driven in game so far include the H9, RPP-1, L-27, Trojan, Reading camelback, ALCo K-66,
> R48 and DM&IR M-3 Yellowstone. An installed pack is still a **candidate**: controls and handling are checked in game
> (see [What a finished pack must pass](#what-a-finished-pack-must-pass)). The latest published build is
> [0.1.2](https://github.com/james-taplin/derailroader/releases/tag/v0.1.2); `main` is 0.1.3 in development.

## Contents

- [What it does](#what-it-does)
- [Personal use only](#personal-use-only)
- [Installation](#installation)
- [Using the app](#using-the-app)
- [Command line](#command-line)
- [How a conversion runs](#how-a-conversion-runs)
- [If a conversion stops](#if-a-conversion-stops)
- [Rules the tool follows](#rules-the-tool-follows)
- [What a finished pack must pass](#what-a-finished-pack-must-pass)
- [Settings](#settings)
- [For developers](#for-developers)
- [Licence](#licence)

## What it does

- **Finds everything the locomotive uses** in your Railroader install: its tender, trucks and parts, from any
  installed mod or Railroader's own asset packs.
- **Measures the model in Unity**: cab, backhead, wheels, rods, lamps, doors and windows.
- **Builds a working Derail Valley locomotive**, which includes:
  - Railroader's cab handles become Derail Valley levers;
  - functions with no handle get generated backhead controls;
  - the F4 HUD, keyboard and cab controls all drive the same simulation;
  - doors, windows and hatches open;
  - oil cups sit on the moving rods;
  - lamps work;
  - the brake release is fitted under the cab.
- **Asks you only what the source cannot answer**, in a pre-build review (below), and remembers your answers.
- **Audits the finished pack** before installing it: no audio, Custom Car Loader scripts only, every HUD control
  wired, mass and wheel radius as recorded.
- **Uses vanilla Derail Valley sounds.** Railroader audio is never extracted.

## Personal use only

A converted pack contains third-party work. Before anything is written to your Derail Valley `Mods` folder, `rr2dv`
shows a large notice. It says that:
- copyright in the source assets stays with their rights holders;
- rr2dv grants no permission to redistribute;
- you should not share the conversion unless the applicable licences already permit it, or you have any required
  permission from the relevant rights holders.

The notice also lists the source content it detected. You click **I agree** ten times to continue, and there is no
setting that skips it.

The installed pack carries three records:
- `NOTICE.txt`: the same text;
- `SOURCE_PROVENANCE.txt`: the notice version, when it was acknowledged, and which mods and authors the content came
  from;
- `rr2dv.json`: the same information as a machine-readable record.

![The personal-use notice](docs/personal-use-notice.png)

## Installation

These steps are for Windows. Install Railroader and Derail Valley through Steam first, or set their install folders in
**Settings…**. Download from the publisher or project pages linked below, check the version and file name before
opening an archive, and avoid third-party mirrors.

### 1. Set up Derail Valley mods

1. Download [Unity Mod Manager from its Nexus Mods page](https://www.nexusmods.com/site/mods/21). Extract it, run
   UnityModManager, select **Derail Valley**, and install it using **Doorstop Proxy** as that page directs.
2. Download **Custom Car Loader v3.1.9** from the **Main files** on the
   [CCL Nexus Mods page](https://www.nexusmods.com/derailvalley/mods/324?tab=files). Also install the dependencies
   listed there, including Language Helper.

   In Unity Mod Manager's **Mods** tab, add the CCL archive without extracting it, and confirm CCL shows **OK**. This is
   the game mod, separate from the Car Creator Package below.

### 2. Install the three build tools

1. **Unity Editor 2019.4.40f1**, exactly this version: a newer Unity is not a substitute. Get it from
   [Unity's release page](https://unity.com/releases/editor/whats-new/2019.4.40f1). In **Settings…**, point `unity` at
   its `Editor\Unity.exe`, for example `C:\Program Files\Unity\Hub\Editor\2019.4.40f1\Editor\Unity.exe`.
2. **CCL Car Creator Package v3.1.9**: under **Optional files** on the
   [CCL Nexus Mods page](https://www.nexusmods.com/derailvalley/mods/324?tab=files). Unzip it somewhere you choose, such
   as Documents. Point `carCreator` at the extracted `CarCreator_3.1.9.unitypackage`, not the ZIP. The app imports it
   itself; you never open it in Unity.
3. **AssetRipper**: the stable **Windows x64** release from
   [AssetRipper's downloads page](https://assetripper.github.io/AssetRipper/articles/Downloads.html). Extract the whole
   archive and point `assetRipper` at `AssetRipper.GUI.Free.exe`, or at the `AssetRipper.GUI.exe` your release supplies.

### 3. Install derailroader

- **Portable app:** from the [0.1.2 release](https://github.com/james-taplin/derailroader/releases/tag/v0.1.2), download
  `Derailroader-0.1.2-Windows.zip`. Extract the **whole** folder and run `Derailroader.exe`, keeping its `_internal`
  folder beside it.
- **From source:** download `Derailroader-0.1.2-Source.zip`, extract it, and run `Launch Derailroader.bat`. This needs
  Python 3.11+ with Tk.

Neither download includes Unity, AssetRipper or the Car Creator Package.

Then open **Settings… → Check**, and **Save** the detected tool paths. If a tool is not found, browse to the exact file
described above and check again. From the command line, use `rr2dv doctor`.

## Using the app

1. **Pick a locomotive.** The left side lists the steam locomotives in your Railroader `Mods` folder; type to filter.
   The coloured chips at the top show whether Railroader, Derail Valley, Custom Car Loader and the tools were found.
2. **Check what it uses.** You see its tender, trucks, parts, controls and sounds, whose work it contains, and any
   problems. Choose the livery and sounds.
3. **Convert.** The stages tick off as they run. The first run of a locomotive imports and measures it in Unity. This
   can take a while for a big model. The measured project is then kept until that locomotive builds and passes its
   audit, so a failed build does not repeat the import.
4. **Review.** After measuring, the **Pre-build review** asks what the source cannot answer (next section).
5. **Agree to the notice**, and the pack is installed. Open the run report, vehicle record or finished pack from the
   buttons afterwards.

### The pre-build review

Every value shows where it came from: a source fact, a measurement or a labelled assumption. Confirm or change it in
the window. Your answers are saved per vehicle in the work folder's `reviews` directory and restored on the next run
of the same unchanged source.

| Choice | What it sets |
|---|---|
| Train brake valve | self-lapping or manual-lap, from the source when it says |
| Spawning | radio only, chosen tracks, or every track long enough for the whole engine and tender |
| Steam profile | legacy-equivalent pull, physical bore, or fixed-geared (experimental) |
| Steam heat | saturated or superheated, from the source's flag when it has one |
| Physical cylinders | 2, 3 or 4. This sets the physics only: the simulation always runs 2 cylinders of the same total volume, which is what Derail Valley's chuff sounds support |
| Driving-wheel radius | pre-filled from the source's driver size, with measured candidates to choose from |
| Dynamo | yes or no. With no dynamo, the pack has no electric lamps, cab light, or controls for them |
| Firing | hand-fired, or oil burner (tank locomotives for now). A mechanical stoker is listed but not built yet |
| Pull to build to | shown when the Railroader mod relies on a code mod, such as LegosBetterSteam's articulated engine, that Derail Valley cannot run. You choose which figure to match |

The **Engine specifications** tab shows bore, stroke, pressure, heating area, boiler dimensions and a coal adjustment,
with units, sources and **Restore** buttons. Nominal tractive effort and factor of adhesion update as you edit.
Inherited boiler values are labelled as simulation defaults, not measurements of the real engine.

## Command line

```
rr2dv doctor                      # find both games and check Unity, Car Creator, AssetRipper and CCL
rr2dv list                        # steam locomotive mods in your Railroader Mods folder
rr2dv scan "Some Loco Mod"        # read-only: what the mod contains and what each loco needs
rr2dv convert "Some Loco Mod"     # convert, with the pre-build review in the terminal
rr2dv convert "Some Loco Mod" --review-file prebuild-review.json  # replay reviewed choices
```

Name a mod by its folder in the Railroader `Mods` folder, or give that folder's path. Zip files and folders elsewhere
are refused.

| `convert` option | Meaning |
|---|---|
| `--loco ID` | which locomotive, when the mod has more than one |
| `--livery NAME` | livery to use (default: the mod's first) |
| `--audio S060\|S282` | vanilla sound set instead of the boiler-size rule |
| `--wheel-radius M` | the driving-wheel radius, once you have reviewed the measured candidate |
| `--search DIR` | an extra folder to look in for dependencies |
| `--geometry-review FILE` | reviewed end-beam heights, when automatic measurement is inconclusive |

## How a conversion runs

Each conversion gets a fresh run folder under the work folder, and stops at the first stage that cannot finish:

| Stage | What it does |
|---|---|
| locate | find the locomotive in the mod |
| link | resolve its tender, trucks and parts, from any installed mod or Railroader's asset packs |
| stage | copy the needed files into the run folder, hash-checked |
| extract | export the bundles with AssetRipper |
| import | assemble a Unity 2019.4 project with the Car Creator Package and our builder |
| probe | measure the model: hierarchy, anchors, animations, cab, wheels |
| record | draft the vehicle record; every value has a unit, basis and evidence |
| build | apply the pre-build review, complete the record from the measurements, and build the CCL pack in Unity |
| audit | load the exported pack and check it |
| publish | show the notice, then install into Derail Valley's `Mods` folder |

Both game installs are checked before a conversion starts, again before the build, and again just before installing.

### Temporary storage

By default, copied inputs, ripped assets, Unity projects, renders and build intermediates are deleted when a
conversion ends, including when it fails. They do not go to the Recycle Bin. The one exception is the imported and
measured project, which is kept until that locomotive builds and passes its audit.

Small reports stay in `<workRoot>/reports/<run-id>`: status, your choices, the vehicle record, the audit and short log
tails. `rebuild.json` records everything needed to rebuild:
- source file hashes;
- tool fingerprints and versions;
- your answers;
- the expected output hashes.

Byte-identical Unity bundles are **not** guaranteed.

For deliberate diagnosis only, the setting `"keepWorkFiles": true` keeps everything.

## If a conversion stops

It stops rather than guess, and always says why: in the app, in the terminal, and in the run folder.
**[docs/resolving-blocks.md](docs/resolving-blocks.md) lists every block and review item and how to resolve each.**
Reruns are safe and start from the source files again.

For diagnosis, every run writes a readable **`run.log`** in its run folder. It covers the settings and installs used,
every stage and issue, tool output, review items, and the full traceback of any unexpected error. The app also keeps
**`%LOCALAPPDATA%\rr2dv\logs\rr2dv.log`**. The builder's `build/out/build_report.txt` and renders show every placement
decision.

## Rules the tool follows

- **Generic.** One pipeline for every locomotive; no per-locomotive scripts. What one model does differently becomes a
  general rule.
- **Nothing is guessed silently.** Values that need a person stay empty and are listed. Every automatic choice is
  written to `build/review.json`. Two equally good matches are an error, never a first pick.
- **Sounds are never converted.** Every locomotive uses vanilla Derail Valley sounds: S060 below 1,500 ft² of heating
  surface, S282 above. `--audio` overrides this.
- **Dependencies.** Everything a locomotive uses from your own Railroader install is used, whichever mod it comes
  from. A part the source mod references but does not contain is left out and listed.
- **Code mods are never run or opened.** Railroader-only code mods, such as LegosBetterSteam, are detected from the
  locomotive's settings. Their effect becomes a review choice instead.
- **Deterministic.** The same input files, answers and tool versions give the same result.
- **Where it writes:** the run folder, and your Derail Valley `Mods` folder after you agree to the notice. It never
  writes to the Railroader install or touches saves. It replaces a folder in Derail Valley's `Mods` only if `rr2dv`
  made it.

## What a finished pack must pass

A pack that builds and passes the audit is a **candidate**. These gates are checked in game, and anything not yet
checked stays pending. Earlier accepted conversions (G-29, C-21) are evidence of what works, not templates.

1. **Proven fixes are kept.** Geometry, travel and tuning are worked out for each locomotive, never a blanket preset.
2. **Every control is there and does its job**; anything missing or replaced is listed.
3. **Right pivot, axis, direction and travel**; handle, joint and reported value agree at both ends.
4. **Grips you can reach**, each collider belonging to its own control.
5. **No interference through full travel.**
6. **Fine, prompt response (CTRL-01)**: no sticking, lag or overshoot.
7. **Holding, return and detents**: set controls stay set, the whistle returns.
8. **Closed means exactly zero (CTRL-02)**: a closed throttle, whistle or valve passes no steam.
9. **Every input route agrees**: grab, F4 HUD, keyboard and scroll move the same control the same way.
10. **Repeated use and save/reload.**
11. **External fittings placed right (BR-01)**: the brake release is upright, red handle outward, hanger up.
12. **Evidence before acceptance**: untested means pending.

The audit already enforces the automatic parts. It refuses a pack with audio, with non-CCL scripts, with a HUD or
driving control lacking its feeder, with duplicate simulation IDs, or with a brake release that fails BR-01.

## Settings

Settings live in `%APPDATA%\rr2dv\machine.json`, or pass `--machine FILE`. The app's **Settings…** dialog edits the
same file. Everything is optional except the three tools.

| Key | What |
|---|---|
| `unity` | `Unity.exe` of Unity 2019.4.40f1 |
| `carCreator` | `CarCreator_3.1.9.unitypackage` |
| `assetRipper` | the AssetRipper executable |
| `python` | Python for the builder's own scripts |
| `railroader` | Railroader install folder (default: found through Steam) |
| `game`, `mods` | Derail Valley install and `Mods` folder (default: found through Steam) |
| `steamRoots` | Steam folders to search instead of the registry and default locations |
| `workRoot` | where run folders go; at most 74 characters, e.g. `C:\rr2dv` (Unity 2019.4 needs short paths) |
| `searchRoots` | extra folders to look in for dependencies |

## For developers

```
python -m pip install -e .        # from a checkout: rr2dv uses its tooling/ folder
derailroader                      # opens the app (or: rr2dv gui)
PYTHONPATH=src:tests python -m unittest discover -s tests   # on Windows: src;tests
```

The window tests run where Tk and a display are available (Windows, or Linux under Xvfb). For the real Unity
prefab-save regression, set `RR2DV_TEST_UNITY` to Unity 2019.4.40f1 and run
`python -m unittest discover -s tests -p test_unity_runtime.py -v`.

| Path | What |
|---|---|
| [`src/rr2dv/`](src/rr2dv/) | the app: Python standard library only (Tk for the window); Unity editor scripts in [`src/rr2dv/unity/`](src/rr2dv/unity/) |
| [`tests/`](tests/) | automated tests on made-up mods, with stand-ins for AssetRipper and Unity |
| [`tooling/`](tooling/) | read-only snapshot of our conversion tooling and guides, the reference builder (start with [`tooling/NOTES.md`](tooling/NOTES.md)) |
| [`docs/`](docs/) | [resolving blocks](docs/resolving-blocks.md), [feature roadmap](docs/feature-roadmap.md), [wiki plan](docs/wiki-plan.md), design notes |
| [`board/APP_BOARD.md`](board/APP_BOARD.md) | message board between the app's and the local Claude and Codex sessions |
| [`CLAUDE.md`](CLAUDE.md) | working notes for Claude sessions on the app |

Changes go on a branch, and test builds are GitHub pre-releases; `main` gets a change after it has been tested.

## Licence

The code in this repository is released under the Unlicense (see [`LICENSE`](LICENSE)). It covers this tool only,
not the content it converts: copyright and other rights in the source assets remain with their respective rights
holders.
