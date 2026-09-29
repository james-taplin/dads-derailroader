# Architecture

`rr2dv` is a Python 3.11+ desktop and command-line app. It orchestrates AssetRipper and Unity 2019.4.40f1, then installs a CCL 3.1.9 pack after the user's notice acknowledgement. The [repository layout](https://github.com/james-taplin/derailroader#repository) is the code map.

| Piece | Responsibility |
| --- | --- |
| `src/rr2dv/` | Scan source mods, resolve dependencies, collect review choices, run the pipeline, keep reports, audit, and install. `appmodel.py` holds window-independent app logic; `gui.py` is the Tk window; `cli.py` is the command line. |
| `src/rr2dv/unity/` | App-owned Unity probe, build, audit, placement, and interaction scripts. |
| `tooling/` | Read-only snapshot of the shared builder core and guides. Refresh it only through the agreed snapshot workflow. |
| `tests/` | Synthetic mod fixtures, fake external tools, C# compile checks, and optional real Unity regressions. |
| `docs/` | Maintained block guide and design/validation notes. |

Each conversion has a fresh run workspace. Compact reports live under `<workRoot>/reports/<run-id>`; saved choices live under `<workRoot>/reviews`. Temporary inputs, extracted assets, and build intermediates are normally removed. The imported and measured project cache can remain until a locomotive builds and passes its audit. The app-wide log is `%LOCALAPPDATA%\rr2dv\logs\rr2dv.log`.

Start with [The pipeline, stage by stage](https://github.com/james-taplin/derailroader/wiki/The-pipeline-stage-by-stage), [The vehicle record](https://github.com/james-taplin/derailroader/wiki/The-vehicle-record), and [`tooling/NOTES.md`](https://github.com/james-taplin/derailroader/blob/main/tooling/NOTES.md). The [contributor notes](https://github.com/james-taplin/derailroader/blob/main/CLAUDE.md) define the current branch and snapshot workflow.
