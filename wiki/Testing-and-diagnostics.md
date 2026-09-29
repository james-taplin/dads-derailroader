# Testing and diagnostics

Use synthetic mods and controlled Unity projects for development tests. Do not commit real locomotive assets or full private logs. The [repository README](https://github.com/james-taplin/derailroader#for-developers) and [contributor notes](https://github.com/james-taplin/derailroader/blob/main/CLAUDE.md) hold current commands and environment requirements.

## Test layers

| Layer | What it checks | What it cannot prove |
| --- | --- | --- |
| Python `unittest` suite | Scan, review, records, pipeline, safety, and report behavior with made-up mods and fake external tools. | Real Unity imports or game behavior. |
| C# API/stub compilation | Editor script types against available stubs or Mono, when installed. | Complete pinned-builder behavior or rendered placement. |
| Real Unity runtime regressions | Prefab save/reload, measured placement, and selected synthetic build paths. | Driving and control feel in Derail Valley. |
| Exported-bundle audit | Serialized mass, radius, scripts, audio, HUD feeders, and other pack invariants. | Physics calibration, input response, and visual fit in game. |
| Game acceptance | The checklist in [Testing a pack in Derail Valley](https://github.com/james-taplin/derailroader/wiki/Testing-a-pack-in-Derail-Valley) and locomotive-specific driving checks. | Untested locomotives or conditions. |

On Windows, set `PYTHONPATH=src;tests` and run `python -m unittest discover -s tests` from the repository root. The optional Unity regression needs `RR2DV_TEST_UNITY` set to Unity 2019.4.40f1 and a disposable project when that test specifies one. Inspect the individual test instructions before running it against a project.

## Read a failed run

`run.log` gives stage order, decisions, tool output, and an unexpected-error traceback. `build_report.txt` gives builder placement and sweep findings. `build/review.json` lists automatic choices even when completion is blocked. `audit.json` describes exported-bundle failures. The [maintained block guide](https://github.com/james-taplin/derailroader/blob/main/docs/resolving-blocks.md) maps exact messages to fixes.

Keep **built**, **audited**, **installed**, **driven**, and **accepted** as separate states in reports and release notes.
