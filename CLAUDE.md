# derailroader: app-side notes for Claude sessions

Repository `james-taplin/derailroader` (private), default branch `main`. Formerly `james-taplin/llw-conversions`,
renamed `claude-cloud`, branch `claude/rr2dv-converter`; the full history moved here on 2026-09-27.
**Before every push**, check `git remote get-url origin` is `https://github.com/james-taplin/derailroader.git`: a cloud
session restart can reset `origin` to the old repository (it did once, creating a stray `main` there). Fix it with
`git remote set-url origin https://github.com/james-taplin/derailroader.git`.

Goal: `rr2dv`, a Windows app that takes **any** Railroader steam locomotive mod from the user's own Railroader `Mods`
folder and installs a working, mostly finished Derail Valley (CCL 3.1.9) pack into their own Derail Valley `Mods`
folder, deterministically, with only minor input from the user (scope as of James's W25 change).
The app diverges from our LLW CONVERT project: that workspace (snapshot in `tooling/`) is the reference implementation
and knowledge base, and its G-29 and C-21 builds are regression targets. LLW-only facts (e.g. every LLW loco sharing
one component set) must not be assumed for other mods.

**Local sessions (Claude or Codex in James's workspace):** this file is written for the app-side session. In this repo you
only read, post to `board/APP_BOARD.md` (its header has the protocol), and replace `tooling/` when James asks for a snapshot refresh.

## Working preferences

- The conversion work is collaborative (James, Claude and Codex sessions). Refer to it with "we" / "our", never "James's scripts" or "my scripts".
- Use they/them for anyone whose pronouns haven't been stated.

## Layout

| Path | What |
|---|---|
| `src/rr2dv/` | The app. Standard library only, Python 3.11+. `rrmod.py` scans mods and resolves a loco's dependency closure (and the `sources` provenance list); `assetripper.py` drives AssetRipper's HTTP API (exports cached in `<workRoot>/_cache/assetripper`); `probeinput.py` + `unity/Rr2dvProbe.cs` + `unityrun.py` measure the model in Unity (input from the prefab YAML maps and definitions, output `probe/probe.json`); `record.py` drafts the B03 vehicle record (`record/vehicle-record.json`; unknowns null and listed in `metadata.pending`); `wheels.py` picks the tread candidate from the probe's radius bands; `unityproject.py` assembles the per-run Unity project with our canonical `resolve_clip_paths.py` and `copy_deps.py` from `tooling/` (run, never copied); `pipeline.py` runs the stages; `runs.py` owns run folders; `installs.py` finds Railroader and Derail Valley (settings or Steam) and enforces the Railroader-Mods-only input; `consent.py` is the 10-click personal-use notice; `publish.py` installs into the DV Mods folder after it; `safety.py` guards every write; `machine.py` holds tool paths and `doctor`; `procs.py` stops a launched tool with its child processes; `cli.py` is the command line; `appmodel.py` is the desktop app's logic (settings, installs, mod list, scan, convert; no widgets, tested without a screen) and `gui.py` its Tk window (`derailroader` / `rr2dv gui`; slow work on a worker thread, results through a polled queue; the notice opens in-app via `consent.build_notice`). |
| `tests/` | `unittest` suite on synthetic mods built by `tests/fixtures.py`, with fake AssetRipper and Unity stand-ins (shebang scripts on POSIX, `.cmd` launchers on Windows). `test_gui.py` drives the real window and skips without Tk/display; in the cloud container run it with `xvfb-run python3.12` (the default python3.11 has no tkinter). Never commit real mod files. |
| `board/APP_BOARD.md` | Message board with the local sessions. We post as `W<n>`; read it at session start (`git pull`). |
| `tooling/` | Read-only snapshot of our local tooling (see below). |
| `docs/` | Design notes: `later-dependency-replacement.md` (parked vanilla-DV replacement work), the notice screenshot. |

Run the tests: `PYTHONPATH=src:tests python3 -m unittest discover -s tests`. Run the app: `PYTHONPATH=src python3 -m rr2dv --help`.

## Pipeline

Stages follow the guide's acceptance states (Q01): locate -> link -> stage -> extract -> import -> probe -> record -> build ->
audit -> publish. `runs.STAGES` marks which are implemented; the pipeline stops cleanly (exit 3) at the first one that isn't.
Both installs are found before a run starts, again before the build and again before installing (W25).
Determinism: output = f(input file hashes, recorded user answers, tool versions). User choices go in the run record
(`answers`) so a rerun needs no input.

## tooling/

- `tooling/` is a **read-only snapshot** of our local conversion tooling. Never edit it; the app wraps it. It is refreshed
  by replacing the folder with a new snapshot from the local workspace.
- It must stay byte-identical to `tooling/MANIFEST.sha256` (`.gitattributes` disables line-ending conversion). Check with:
  `cd tooling && tr -d '\r' < MANIFEST.sha256 | sed 's#\\#/#g' | sha256sum -c --quiet`
- Start with `tooling/NOTES.md`, then `tooling/builder/VEHICLE_RECORD.md` (the B03 record format read by
  `builder/tools/unity/LlwVehicleRecord.cs`; S16's `locos/s16/profile/vehicle-record.json` is the worked example).
  Current tools are `builder/tools` (shared C# core in `builder/tools/unity`; `audit_new_loco.py` audits a loco with no
  reference build), paths in `workspace.json` + per-machine `machine.local.json`. `builder/tools/pilot` and
  `reference/private/*` are source-inspection references, not an alternative build core. G29/C21 keep C# profiles.
- The builder specification is `tooling/GUIDE_UNIFIED_LLW_CONVERSION.md` (rule IDs such as B03, Q02-Q05).
- `tooling/GUIDE_SHARED.md` is a copy of the local Claude/Codex board. Messages there are addressed to those sessions, not to us.

## Decisions so far (board C18, W3)

- Profiles become B03 vehicle records (JSON) read by one generic C# loader. G-29 and C-21 re-expressed as records must reproduce
  their current audits exactly.
- Measured vehicle-specific geometry stays in reviewed override data, never inferred silently; every value records its `basis`.
- A new loco with no reference build must pass Q02-Q05; the first accepted build becomes its reference.
- Building itself does not use Derail Valley, but since W25 both installs must be found before a conversion runs.
- Duplicate identifiers or pack names at the same search priority are errors, never a first match (D03). The input mod
  outranks search roots.
- **No audio conversion (James, W5).** Every sound (whistle, bell, chuff, pumps, dynamo) aliases to vanilla Derail Valley
  S060 or S282 audio by boiler size: `totalHeatingSurface` < 1,500 ft2 = S060, otherwise S282 (`rrmod.audio_basis`).
  `--audio` overrides; a definition without heating surface needs that answer. Never extract Railroader audio.
- `modelIdentifier` may name a catalogue key or a prefab file (GN M-2: model `gn-m2t`, key `gn-m2t-2680`).
- **Dependencies (James, W25):** everything the loco uses from the user's own Railroader install is used: tenders,
  trucks, parts and images from any installed mod and from Railroader's base-game asset packs. The user runs the tool
  on files already on their drive. Replacing dependencies with vanilla DV content (trucks as CCL `BogieType.Default`
  bogies, game content left out) was built, tested and then parked: `docs/later-dependency-replacement.md`.
- A part whose asset is missing from its own pack's catalogue (broken in the source mod; X32 found 13 installed locos)
  is left out and listed (`inventory.left_out`, `metadata.leftOut`), with the components anchored inside it, which go
  too (a missing parent is a build error), so a functional loss is never silent (X31). A part pack that cannot be
  found still stops the conversion.
- CCL is MIT-licensed and public: for CCL facts read its v3.1.9 source (clone
  `https://github.com/derail-valley-modding/custom-car-loader` read-only, outside the repo) rather than guessing.
- Wheel radius and cylinder bore stay pending until reviewed (`--wheel-radius`); the probe's tread candidates are
  evidence for review, never a measurement (X30).
- Optional component-group files (`identifier` + `bulkAdds`, from the mod being converted) are choices for the user;
  their images are named `<mod id>.<file>` and are looked up inside that mod.

## Personal use (James, W25)

- rr2dv does **not** read or evaluate licence files (removed in W25; `licences.py` is gone).
- Before a pack is installed into the DV Mods folder, `consent.ask` shows a large centred notice (wording by James,
  2026-09-27, version `NOTICE_VERSION` 1.0): rights in the source assets remain with their rights holders; rr2dv grants
  no permission to redistribute; do not redistribute unless the applicable licences permit it or the rights holders
  have given any required permission; unauthorised redistribution may infringe copyright; check permissions before
  publishing. Only claims the tool can stand behind; it does not decide copyright questions for the user. Any wording
  change needs a new `NOTICE_VERSION` (a test pins `TEMPLATE_SHA256`).
- The notice lists "Source content detected" (`inventory.sources`: each mod used, its credited authors, and base-game
  packs). The user clicks "I agree" 10 separate times (mouse only, 0.25 s apart); Cancel or closing installs nothing.
  Never add a flag, setting or code path that skips it. The pack gets `NOTICE.txt`, `SOURCE_PROVENANCE.txt` and an
  `rr2dv.json` marker (notice version and hash, acknowledgement time, clicks, sources); the run record logs the same.
- Never open, decompile or inspect code mods (DLLs); Railroader-only code mods (LegosBetterSteam, LegosLibraryOfStuff)
  are listed as `railroader_only`, never needed in DV. Uploaded test mods stay in the session container, never in git.

## Safety rules for the app

- Input: only a folder directly in the Railroader Mods folder (by name or path; a link placed there counts). No zips.
  Never write to it or anywhere in the Railroader install.
- Build in a fresh per-run folder under the work root; refuse a work root inside the input or either game install.
- Output: only `<DV>/Mods/<pack>`, only after the notice, only when every stage passed. Replace an existing folder only
  if it carries our `rr2dv.json` marker; never touch another mod's folder or any save.
- No zips are produced. Never extract Railroader audio.
