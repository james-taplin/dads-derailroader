# derailroader

A local interoperability tool which converts supported locomotive assets already installed in the user's Railroader
Mods directory into a structure usable by Derail Valley.

The tool is called `rr2dv` on the command line. It takes a steam locomotive mod from your own Railroader `Mods`
folder, rebuilds it for the Derail Valley Custom Car Loader (CCL 3.1.9), and installs the result into your own Derail
Valley `Mods` folder. It never changes the Railroader mod it reads.

> **Work in progress.** Everything up to a draft vehicle record works, from the desktop app or the command line,
> and has been run with real Unity and AssetRipper on Windows. The Unity build and audit stages are next, so no pack
> is installed yet.

## Personal use only

A converted pack contains third-party work. Before anything is written to your Derail Valley `Mods` folder, `rr2dv`
shows a large notice. It says that copyright in the source assets stays with their rights holders, that rr2dv grants
no permission to redistribute, and that you should not share the conversion unless the applicable licences already
permit it or you have any required permission from the relevant rights holders. It also lists the source content it
detected. You click **I agree** ten times to continue, and there is no setting that skips it.

The installed pack carries `NOTICE.txt` (the same text), `SOURCE_PROVENANCE.txt` (notice version, when it was
acknowledged, which mods and authors the content came from) and an `rr2dv.json` record of the same.

![The personal-use notice](docs/personal-use-notice.png)

## What you need

- Windows, with Python 3.11 or later (its standard installer includes Tk, which the app's window uses)
- Railroader and Derail Valley installed through Steam (or in folders you name in the settings file)
- Unity Mod Manager and Custom Car Loader 3.1.9 installed in Derail Valley
- Unity 2019.4.40f1, the CCL 3.1.9 CarCreator package (`CarCreator_3.1.9.unitypackage`) and AssetRipper

## The app

```
python -m pip install -e .        # run from this repository: rr2dv uses its tooling/ folder
derailroader                      # opens the app (or: rr2dv gui)
```

![The derailroader app](docs/app-window.png)

- The coloured chips at the top show whether Railroader, Derail Valley, Custom Car Loader and the tools were found
  (hover for where). **Settings…** sets the tool paths and runs the same checks as `rr2dv doctor`.
- The left side lists the steam locomotive mods in your Railroader `Mods` folder; type to filter.
- Pick a locomotive to see its tender, trucks, parts, controls, sounds, whose work it uses and any problems. Choose
  the livery and sounds, then **Convert**. The stages tick off below as they run; afterwards you can open the run
  folder and the draft record. The personal-use notice opens inside the app before anything is installed.

## Command line

```
rr2dv doctor                      # finds both games and checks Unity, CarCreator, AssetRipper and CCL
rr2dv list                        # steam locomotive mods in your Railroader Mods folder
rr2dv scan "Some Loco Mod"        # read-only: what the mod contains and what each loco needs
rr2dv convert "Some Loco Mod"     # convert it (add --loco <id> when the mod has several)
```

You name a mod by its folder in the Railroader `Mods` folder, or give that folder's path. Zip files and folders
elsewhere are refused.

`convert` options:

| Option | Meaning |
|---|---|
| `--loco ID` | which locomotive, when the mod has more than one |
| `--livery NAME` | livery to use (default: the mod's first) |
| `--audio S060\|S282` | vanilla sound set instead of the boiler-size rule |
| `--wheel-radius M` | the driving wheel tread radius, once you have reviewed the measured candidates |
| `--search DIR` | an extra folder to look in for dependencies |

## What happens

Each conversion gets a fresh run folder under the work folder. The pipeline runs these stages and stops at the first
one that fails or is not built yet:

| Stage | What it does | State |
|---|---|---|
| locate | find the locomotive in the mod | working |
| link | resolve its tender, trucks and parts, including those from other installed mods and Railroader's own asset packs | working |
| stage | copy the needed files into the run folder, hash-checked | working |
| extract | export the bundles with AssetRipper (cached per bundle) | working |
| import | assemble a Unity 2019.4 project: restored animation paths, dependencies, CarCreator, our builder | working |
| probe | measure the model in Unity: hierarchy, anchors, animations, wheel tread candidates | working |
| record | draft the vehicle record: every value with its unit, basis and evidence; unknowns listed for review | working |
| build | build the CCL pack in Unity | next |
| audit | check the built pack | next |
| publish | show the notice, then install into Derail Valley's `Mods` folder | ready, waits for build |

Both game installs are found before a conversion starts, again before the Unity build, and again just before
installing.

## If a conversion stops

It stops rather than guess, and always says why: in the app's Checks list and Conversion panel, in the command
line's output, and in the run folder. **[docs/resolving-blocks.md](docs/resolving-blocks.md) lists every block and
review item and how to resolve each one.** The tool cannot yet ask you questions mid-run or resume a stopped run:
give your answers when you start (the app's Options, or `--loco`, `--livery`, `--audio`, `--wheel-radius`) and
convert again after fixing a block. Reruns are safe and reuse the cached AssetRipper exports.

## Rules the tool follows

- **Sounds are never converted.** Every loco uses vanilla Derail Valley sounds: S060 for a small boiler (under
  1,500 ft² heating surface), S282 otherwise. `--audio` overrides this.
- **Dependencies:** everything a loco uses from your own Railroader install is used, whichever mod it comes from.
  A part the source mod references but does not contain is left out and listed, because Railroader cannot load it
  either.
- **Nothing is guessed.** Values that need measuring or a person's review stay empty and are listed in the draft
  record's `metadata.pending`. Two equally good matches are an error, never a first pick.
- **Deterministic:** the same input files, answers and tool versions give the same result. Your answers are saved
  in the run record, so a rerun needs no input.
- **Where it writes:** the run folder, and your Derail Valley `Mods` folder after you agree to the notice. It never
  writes to the Railroader install or touches saves. It replaces a folder in Derail Valley's `Mods` folder only if
  `rr2dv` made that folder earlier; any other mod's folder is left alone.

## What a finished pack must pass

The build and audit stages still to come will only accept a pack that passes our builder's gates (`tooling/`, guide
rules Q02–Q05), plus two control gates we have learned the hard way (board X36):

- **Responsive controls (CTRL-01).** Driving controls and valves must behave like our last accepted G-29/C-21
  builds: they respond to fine inputs, cover their full range, keep their settings and release momentary controls
  reliably, with no sticking, lag, overshoot or drift. Intended detents stay.
- **Closed means zero (CTRL-02).** A closed throttle, whistle or other steam valve must command exactly zero in the
  simulation, not just look closed or round to 0% on the HUD, with no steam flow attributable to it.

A successful build is not enough on its own: these need checking in game, and a pack that has not been checked yet is
marked as pending, not accepted.

## Settings

Settings live in `%APPDATA%\rr2dv\machine.json` (or pass `--machine FILE`). The app's **Settings…** dialog edits the same
file. All keys are optional except the tools:

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

## Repository

| Path | What |
|---|---|
| [`src/rr2dv/`](src/rr2dv/) | the app: Python standard library only (the window uses Tk, included with Python on Windows), plus a Unity editor probe in [`src/rr2dv/unity/`](src/rr2dv/unity/) |
| [`tests/`](tests/) | automated tests on made-up mods, with stand-ins for AssetRipper and Unity |
| [`tooling/`](tooling/) | read-only snapshot of our conversion tooling and guides, used as the reference implementation (start with [`tooling/NOTES.md`](tooling/NOTES.md)) |
| [`board/APP_BOARD.md`](board/APP_BOARD.md) | message board between this app's Claude session and the local Claude and Codex sessions |
| [`docs/`](docs/) | [resolving blocks](docs/resolving-blocks.md), design notes ([replacing dependencies with vanilla DV content](docs/later-dependency-replacement.md), parked) and the screenshots on this page |
| [`CLAUDE.md`](CLAUDE.md) | notes for Claude sessions working on the app |

Run the tests with `PYTHONPATH=src:tests python -m unittest discover -s tests` (on Windows use `src;tests`). The
window tests run where Tk and a display are available (Windows, or Linux under Xvfb) and are skipped otherwise.

## Licence

The code in this repository is released under the Unlicense (see [`LICENSE`](LICENSE)). It covers this tool only,
not the content it converts: copyright and other rights in the source assets remain with their respective rights
holders.
