# rr2dv: Railroader → Derail Valley locomotive converter

Work in progress. `rr2dv` takes a Railroader steam locomotive mod (a folder or a zip) and produces a Derail Valley
pack for the Custom Car Loader 3.1.9. It never modifies the mod you give it.

| Folder | What it is |
|---|---|
| [`src/rr2dv/`](src/rr2dv/) | The app (Python 3.11+, no extra packages). |
| [`tests/`](tests/) | Automated tests on made-up mods. |
| [`board/APP_BOARD.md`](board/APP_BOARD.md) | Message board between the app-side Claude session and the local Claude and Codex sessions. |
| [`tooling/`](tooling/) | Snapshot of our LLW conversion scripts, Unity builder code and guides, used as the reference implementation. Read-only here; start with [`tooling/NOTES.md`](tooling/NOTES.md). |

## Status

| Stage | State |
|---|---|
| Find the locomotive, resolve its tender and parts across mods, check licences, copy and verify the inputs | working |
| Export the bundles with AssetRipper (cached per bundle, AssetRipper build and Unity version) | working; passed a real-AssetRipper smoke test (S-16, C-21) |
| Prepare the Unity 2019.4.40f1 project (restored animation paths, trucks and parts with their dependencies, CarCreator, our builder core) | working, not yet opened in Unity on a real machine |
| Measure the model in Unity (hierarchy, meshes, anchors in car space, clip bindings and end poses, wheel tread bands) | runs in Unity 2019.4 (S-16); tread choice awaiting retest |
| Draft the vehicle record: identity, liveries, maps, components, wheelsets, capacities, sim/HUD/sound basis, pull and cylinder calibration, boiler and firing estimates, vanilla tender bogies, each value with its unit, basis and evidence | working (source-derived part); wheel radius needs review (`--wheel-radius`); measured geometry and mass pending |
| Build, audit | next (P3) |
| Publish the finished pack to an output folder | working (used once the build stages exist) |

## Try it

```
python -m pip install -e .                     # run from the repository: rr2dv uses its tooling/ folder
rr2dv doctor                                   # checks Unity, CarCreator, AssetRipper and folders
rr2dv scan "path\to\Some Loco Mod"             # read-only: what's in the mod and what each loco needs
rr2dv convert "path\to\Some Loco Mod" --out "path\to\output"
```

Settings live in `%APPDATA%\rr2dv\machine.json` (or pass `--machine`). It uses the same keys as our
`machine.local.json` (`python`, `unity`, `carCreator`, `assetRipper`, `railroader`, `mods`, ...), plus optional
`workRoot` and `searchRoots`. With `railroader` set, its `Mods` folder and base-game asset packs are searched for
dependencies such as trucks from other mods.

Trucks are never converted: every converted tender runs on vanilla Derail Valley bogies, so no truck mod or
Railroader game mesh ends up in the pack.

Sounds are never converted: every converted loco uses vanilla Derail Valley S060 sounds (small boiler, under
1,500 ft² heating surface) or S282 sounds (big boiler). `--audio S060|S282` overrides the rule.

Mod licences are checked before converting: the mod itself and every mod whose models or images would end up in the
Derail Valley pack. If any of them explicitly forbids modifying, decompiling, porting or deriving from its work, even
for personal use, `rr2dv` stops and will not convert that locomotive. There is no override. A licence file it cannot
read also stops it. Mods without a licence file are converted. Code mods a loco uses only in Railroader (such as
LegosBetterSteam) are not needed in Derail Valley and are never opened. Converted packs contain the original authors'
work and are for your own use.

The Claude ⇄ Codex chat bridge lives on the `claude/llm-chat-bridge` branch.
