# llw-conversions: app-side notes for Claude sessions

Goal: `rr2dv`, a Windows app that takes **any** Railroader steam locomotive mod (folder or zip) in and puts a working,
mostly finished Derail Valley (CCL 3.1.9) pack out, deterministically, with only minor input from the user.
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
| `src/rr2dv/` | The app. Standard library only, Python 3.11+. `rrmod.py` scans mods and resolves a loco's dependency closure; `licences.py` is the licence policy; `assetripper.py` drives AssetRipper's HTTP API (exports cached in `<workRoot>/_cache/assetripper`); `probeinput.py` + `unity/Rr2dvProbe.cs` + `unityrun.py` measure the model in Unity (input from the prefab YAML maps and definitions, output `probe/probe.json`); `record.py` drafts the B03 vehicle record (`record/vehicle-record.json`; unknowns null and listed in `metadata.pending`); `unityproject.py` assembles the per-run Unity project with our canonical `resolve_clip_paths.py` and `copy_deps.py` from `tooling/` (run, never copied); `pipeline.py` runs the stages; `runs.py` owns run folders; `publish.py` and `safety.py` guard every write; `machine.py` holds tool paths and `doctor`; `cli.py` is the entry point. |
| `tests/` | `unittest` suite on synthetic mods built by `tests/fixtures.py`, with a fake AssetRipper HTTP server (POSIX only). Never commit real mod files. |
| `board/APP_BOARD.md` | Message board with the local sessions. We post as `W<n>`; read it at session start (`git pull`). |
| `tooling/` | Read-only snapshot of our local tooling (see below). |

Run the tests: `PYTHONPATH=src:tests python3 -m unittest discover -s tests`. Run the app: `PYTHONPATH=src python3 -m rr2dv --help`.

## Pipeline

Stages follow the guide's acceptance states (Q01): locate -> link -> stage -> extract -> import -> probe -> record -> build ->
audit -> publish. `runs.STAGES` marks which are implemented; the pipeline stops cleanly (exit 3) at the first one that isn't.
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
- Building does not need a Derail Valley install; installing and testing do.
- Duplicate identifiers or pack names at the same search priority are errors, never a first match (D03). The input mod
  outranks search roots.
- **No audio conversion (James, W5).** Every sound (whistle, bell, chuff, pumps, dynamo) aliases to vanilla Derail Valley
  S060 or S282 audio by boiler size: `totalHeatingSurface` < 1,500 ft2 = S060, otherwise S282 (`rrmod.audio_basis`).
  `--audio` overrides; a definition without heating surface needs that answer. Never extract Railroader audio.
- `modelIdentifier` may name a catalogue key or a prefab file (GN M-2: model `gn-m2t`, key `gn-m2t-2680`).
- Optional component-group files (`identifier` + `bulkAdds`, from the mod being converted) are choices for the user;
  their images are named `<mod id>.<file>` and are looked up inside that mod.

## Licences

- **Strict policy, no override (James, W7/W8).** `licences.py` + `rrmod.inventory`: if any mod whose content ends up
  in the DV pack (the converted mod, mods whose bundles or images we copy) explicitly forbids modification even for
  personal use, reverse engineering, porting/conversion or derivative works, the conversion stops. An unreadable
  licence file also stops it. No licence file = no restriction (explicit restrictions only). Code mods used only in
  Railroader (LegosBetterSteam, LegosLibraryOfStuff) are not needed in DV, never opened, never blocking; they are
  listed as `railroader_only`. Never add a flag, setting or "permission" path around a block; fix wrong matches in
  the patterns instead.
- Never open, decompile or inspect code mods (DLLs) or bundles of mods we only depend on. Learn formats from the data
  files of the mod being converted and from our guides. Uploaded test mods stay in the session container, never in git.
- Converted packs contain the original authors' work: personal use unless the author agrees otherwise.

## Safety rules for the app

- Never write to the input folder or zip. Build in a fresh per-run folder; publish output only when every stage passes.
- Refuse output or work folders inside the input, the work root, the Railroader install or Derail Valley.
- Never install into the game or touch saves unless explicitly asked.
- Share outputs exclude Railroader game audio, the CarCreator package, decompiled code and third-party exports.
