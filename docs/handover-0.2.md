# Handover: 0.2.X-exp

Branch `0.2.X-exp` starts from `main` at 9206bfb (0.1.3 plus board W61). Work here; follow CLAUDE.md (W36 workflow:
branch, pre-release for James to test, merge only when he says, board post after every change, `tooling/` read-only).

## Read first
1. `CLAUDE.md`, then `board/APP_BOARD.md` from W50 on (W57-W61 are the latest).
2. `docs/resolving-blocks.md` (every rule the app applies), `README.md`, `docs/wiki-plan.md`.

## State
- 0.1.3 converts steam locos end to end; built and driven: H9, RPP-1, L-27, Trojan, Reading camelback, ALCo K-66,
  R48, DM&IR M-3. Packs are candidates until James checks them in game.
- **Untested in Unity/game (first thing James will test):** firing choice (oil burner, tank locos only), cylinders
  simulated as 2 of equal swept volume, brake cutout and cab light as handwheels (F4 HUD), Railroader Unity lights
  stripped, oil cups placed by running-gear motion, lamp glass split/invisible flare discs, M-3 door toggles (only
  moved parts count), brakes/lights one notch per key press, generated whistle physics.
- The Unity partials `Rr2dvPlacement/Interactions/MaterialSlots.cs` are outside the C# stub compile: review edits by
  eye; `test_csharp_api` fails for known stub gaps only.
- v0.1.3 is not tagged or released yet (the cloud session could not push tags); James makes the pre-release.

## Open work, in James's priority order
1. Act on James's next game test of the list above; fix each failure on this branch.
2. Mechanical stoker: needs the builder-core change requested in W57 (local tooling first, then a snapshot). Then the
   app side: K-66 "Stoker"/"auger" toggles driven from `STOKING_NORMALIZED` via `LoadAnimations`, audit exclusion.
3. Oil firing for tender locos (the tender's coal container must become fuel too).
4. Control feel: evidence-based only (build reports + James's notes), never a blanket preset (CTRL-01).
5. Wiki: write it from `docs/wiki-plan.md` once James enables the wiki and grants access.
6. Unknown code-mod detection needs a list of Railroader's base-game component kinds (`codemods.py`).

## How James tests
He runs the Windows app, uploads `run.log`, `build_report.txt`, `Player.log`
(`%USERPROFILE%\AppData\LocalLow\Altfuture\Derail Valley\`) and screenshots. Read the reports before changing code;
the project cache means a rerun after a build fix skips the long import.
