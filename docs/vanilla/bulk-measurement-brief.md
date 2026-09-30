# Brief for Codex: bulk measurement run (vanilla-flavoured, Phase 2 rerun)

Branch `vanilla-flavoured` only. Read-only towards Railroader and Derail Valley: nothing is installed, no save is touched,
no file in either game folder is written. The run is long (about 1-2 hours), so it is built to be safe to interrupt and rerun.

## What is new since the last Phase 2 run
- `VfMeasure.cs` now also records `colliderYs` in every cab/body column ray (floors that have no visible mesh, ~10 locos) and
  measures every wheel band per rotating node.
- One command does everything (`tools/vanilla/run_bulk.py`): project preparation, measurement, checks, zip. It replaces
  `run_phase2.py measure` and `run_regime.py`; you do not run those.
- Fingerprints changed (commit `4cb8d12`), so each loco re-imports once: about 2-4 minutes per loco the first time.
- The Windows `WinError 32` on the AssetRipper cache rename has a retry (`bf8fcfa`). If it still appears, see "If something fails".

## Before you start (once)
1. `git pull` on `vanilla-flavoured`; `git log -1` must show `bf8fcfa` or later.
2. Close every Unity editor and AssetRipper. Do not open Unity while the run works.
3. The settings file (the app's default, or the one you pass with `--machine`) needs a short `"workRoot"` (for example
   `C:\rr2dv`) and valid `unity` (2019.4.40f1) and `assetRipper` paths. `doctor` shows them:
   `set PYTHONPATH=src` then `python -m rr2dv doctor`. Leave `keepWorkFiles` as it is: the runner switches it on in
   memory for its own run only and never edits the settings file.
4. Run in a normal, unrestricted terminal (the first Unity launch failed inside a sandbox before: Licensing Client IPC).
5. At least 25 GB free on the work drive and on the output drive (the script checks).

## Commands (from the repo root)
```
set PYTHONPATH=src
python tools\vanilla\run_bulk.py --dry-run
python tools\vanilla\run_bulk.py --pilot
python tools\vanilla\run_bulk.py
```
- `--dry-run` checks everything and launches nothing. It must print `preflight ok. 21 pack(s)`. If it prints `PROBLEM:` lines, fix
  those and rerun; nothing else has happened.
- `--pilot` runs K-28T and T-17 only (about 10 minutes). Look at its `[n/n] pack: OK` lines before starting the full run.
- The full run measures all 21 steam packs. The 3 diesels are not part of this run (the pipeline is steam only).
- Results go to `vf_bulk_out\` (change with `--out-dir`). `vf_bulk_out\vf_bulk.zip` is rewritten after every pack.
- Add `--machine <settings.json>` if you do not use the app's default settings.

## Reading the progress lines
`[7/21] ls-260-g25: OK in 210 s` is a pass. `OK-with-problems` means Unity measured it and logged problems (normal for some
locos; they are in the zip). `FAILED (why)` is a real failure for that pack; the run continues with the next pack.
The final line says `all packs measured` (exit 0) or `FAILED packs (n): ...` (exit 1). Exit 2 = preflight failed, nothing ran.

## If something fails
- Do not edit any script or setting to make it pass, and do not skip a pack. Rerun the same command: passed packs are
  skipped, failed packs are retried. A pack that fails twice: leave it, finish the rest, report it.
- If the window closes, the machine sleeps, or you press Ctrl+C: rerun the same command; it resumes.
- `open in another Unity editor`: close Unity, rerun.
- `WinError 32` at the AssetRipper stage on every pack: rerun `python -m unittest tests.test_assetripper` in the same terminal
  and report whether it passes. Do not work around it.
- Any other error: leave `vf_bulk_out` as it is and send it (the zip contains the reason per pack).

## What to send back
1. `vf_bulk_out\vf_bulk.zip` (small; never add bundles, exports, textures, or the Unity project).
2. `vf_bulk_out\state.json` is inside the summary already; not needed separately.
3. A short `notes.md` in your own words: anything odd, run time, whether any pack needed a rerun, Unity/Windows version.
Do not attach anything else, and do not analyse the results: that is done offline.

## What the zip contains
`summary.json` (per pack: verdict, seconds, counts of axles, columns with `colliderYs`, sweeps, renderers), `game-hashes.json`
(Bundle/Definitions/Catalog hashes; results count only for these), `MANIFEST.sha256`, and per pack under `results/<pack>/`:
`vf-measure.json`, `result.json`, `launch.json`, Unity log tails, `review-questions.json`, `probe__probe.json`,
`record__vehicle-record.json`, `run.log`, `inventory.json`.
