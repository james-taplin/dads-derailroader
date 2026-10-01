# Handover to Codex (written 2026-10-01 by the cloud Claude session, which is nearly out of usage)

Read this first on branch `claude/unity-crash-message` of `james-taplin/dads-derailroader` (private). The app board lives in the OLD repo
`james-taplin/derailroader` (`board/APP_BOARD.md`, posts VF27 to VF29 hold the same findings); this repo has no board and James wants it kept that way.
Also read `CLAUDE.md` (workflow rules): implement on a branch, never straight to `main`; board posts and releases only when James says.

## What this session did (and what the test runs were for)
James's goal: the stock-locomotive edition of derailroader converts Railroader's 21 stock steam locos into Derail Valley packs (0.4.0 and 0.4.1 are
released). The test runs you did (oil map, build runs) served these purposes:
1. **Oil-cup map** (`tools/vanilla/VfOil.cs`, `run_oil.py`, `docs/oil-map-brief.md`): Railroader's modellers put small oiling nubs on top of the running
   gear; the old detection missed them. The map measured them on all 21 locos (mesh pieces and ray-sampled bumps, with pictures). Result: the builder now
   seats each main-rod-end cup pair on the best-clearance modelled nub (`src/rr2dv/unity/Rr2dvOilNubs.cs`, glue in `Rr2dvPlacement.cs`), falling back to
   the old highest-level-spot search; main-rod rules fixed (line limit 4.5 cm, crank throw at least 0.2 m: F-71 and C-55 had no main rod before).
2. **Unattended build** (`tools/vanilla/build_all.py`, `docs/build-all-brief.md`): build and audit every loco without installing, to get a baseline.
   `docs/baseline-0.4.2.md` is that baseline: all 21 BUILT and audited in one run.
3. **Clip fixes found by those builds:** trailing-space/quoted node names (AssetRipper writes `m_Name: 'Trailing '`; P-18 trailing wheel, P-43 reverser,
   T-22 window clips were silently dropped), and clips written relative to a child node (C-55's tender `Coal Load/Bone` for `Tender/Coal Load/Bone`; the
   numeric `path:` values in `m_ClipBindingConstant` are hashes, not paths). Also: a tender toggle whose clip cannot resolve is left out and listed instead
   of stopping the build; tenders get number plates from RoadNumber decals, else side lettering (all 20 tenders used lettering), else mid-side.
4. Housekeeping: portable `rr2dv_work` folder (settings, runs, logs beside the app), crash message decodes Unity exit codes, non-ASCII path warning,
   `CHANGELOG.md` shipped in packages, false "window not responding" dump fixed.

## State
- Branch head = latest `claude/unity-crash-message`; `main` was fast-forwarded to it when James asked (check `git log origin/main`). Version is still 0.4.1.
- Tests: `PYTHONPATH=src:tests xvfb-run -a python3.12 -m unittest discover -s tests` (about 3 min); only 2 known failures (test_csharp_api: stub gaps in
  Rr2dvAudit.cs). C# in `src/rr2dv/unity/` is compiled only by Unity (except standalone files like Rr2dvOilNubs.cs): a compile error stops the next build.
- Nothing from this session has been tried in game. Nub-seated cups, plates, clip fixes: build reports only.

## Do next, in James's priority order (stability, reliability, working DV prefabs, working controls, cabs/gauges/lights/water glasses, animations last)
1. Get James's in-game check of a few locos (cups on nubs where? tender plates? tender hatch/coal/water animations, trailing wheels, P-43 reverser).
2. Known issues to examine from the baseline reports: loco-tender coupling overlaps or gaps (worst ones: bodies overlapping by 20-60 cm on a few; some too far apart),
   tender brake release "no seat found" on several tenders (the app's final placement then reports success: verify in game), F-71 big-end pair has no travelling-part nub
   (falls back to a flat spot), P-43's source reverser is replaced by a generated lever ("part also carries parts other clips move"), T-21 blower/coal-dump lever sweep clash,
   generated labels "no surface below" on some, water animation built with 0 objects on C-55's tender.
3. 0.4.2: merge to main (already there if James pushed), bump `src/rr2dv/__init__.py` and `pyproject.toml` to 0.4.2, add a block to `CHANGELOG.md` in James's style
   (hyphen lines, lower case, commas only, no full stops or colons, [brackets] for extra info, known issues as "known issue, ..."), build packages with
   `scripts/package_release.py` (now ships changelog, readme, wiki, docs). A draft of the 0.4.2 lines is below. Releases and tags are James's or Codex's job on GitHub.
4. Parked: repairing tender/loco animation clips beyond the fixes above, whistle sound swap, diesels (0.3.x line).

## Draft 0.4.2 changelog lines (check against in-game results before using)
- cups are now placed on the modelled oiling nubs of the rods, whichever has the best clearance at each end [untested in game]
- F-71 and C-55 main rods are now found, F-71 gets oil cups
- fixed trailing wheels, reverser and window animations being dropped where the part name ended in a space [P-18, P-43, T-22]
- C-55 now builds, its tender coal, water, hatch, brake rig and cut lever animations are present
- tenders get number plates from the side lettering
- known issue, the 0.4.1 known issues still apply

## Rules that must not change
- Never skip or automate the personal-use notice (10 clicks); `build_all.py` refuses it. The experimental-physics tick-box is ticked only with `--acknowledge-experimental`
  and geometry proposals applied only with `--accept-proposed-geometry`, both only because James allowed them for test runs.
- `tooling/` is a read-only snapshot; app fixes live in `src/rr2dv/`. No real game assets, audio or full logs in git. Check `git remote get-url origin` is
  `https://github.com/james-taplin/dads-derailroader.git` before pushing.
- James's user-facing text style: lowercase, commas, no formatting, one entry per line.
