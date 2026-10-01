# Oil-cup map run: brief for Codex (offline)

Goal: for every stock steam loco, record every place an oil cup could go on the running gear under our requirements, and why
each candidate passes or fails, **and every modelled oiling nub** (Railroader's modellers put small nubs on top of the running
gear: big ends, crossheads, valve gear, axleboxes; they imply the real-world oiling points), so we can read the results and add defined positions to the loco table
(`src/rr2dv/stock_locos.json`). Nothing is built, installed or changed: this only measures.

The old nub search (islands of 20+ triangles near a rod end, in 0.3.x before 2026-09-30) was replaced by the highest level spot within
0.3 m of a rod end, which finds a flat but not a small domed nub. This run measures nubs directly so we can see where they are.

Our requirements (James, 2026-09-30, as coded in `Rr2dvPlacement.SeatRr2dvOilCups`): cups only at the ends of the main rods, as a
left/right pair on the same end or not at all; running boards only when no main-rod pair fits, then on both sides; at most 6 pairs.
A seat is a level spot (normal.y at least 0.9) with a 4 x 3 cm level footprint within 0.3 m of the rod end, measured on the rod in
its own level pose, LOD0 meshes only. The cup's own space (3.5 cm radius, 9 cm tall) must stay clear through a whole turn of the
drivers, and cups must be 12 cm apart.

## Run it

    cd <your clone of dads-derailroader, on branch claude/unity-crash-message>
    git pull
    set PYTHONPATH=src
    python tools\vanilla\run_oil.py --dry-run
    python tools\vanilla\run_oil.py --pilot
    python tools\vanilla\run_oil.py

- `--dry-run` checks everything and launches nothing. If it prints PROBLEM lines, fix those and stop; do not edit the tool.
- `--pilot` runs K-28T and T-17 first (a few minutes). Check `vf_oil_out\vf_oil.zip` has both with verdict OK, then run all 21.
- The run is resumable: if it stops, rerun the same command. `--force` redoes packs that already passed.
- It reuses a kept project from an earlier bulk run when the inputs match, so it is much faster after `run_bulk.py`.
- Do not edit settings, the app, `tooling/` or the tool scripts. Close other Unity editors first.

## Send back

`vf_oil_out\vf_oil.zip` (small: JSON only), whatever the exit code. If a pack FAILED, send the zip anyway and name the pack.
Exit 0 = all passed, 1 = some failed (zip still written), 2 = preflight failed (nothing ran), 130 = interrupted.

## What is in each pack's `vf-oil.json` (for the analysis)

- `movingParts`: every part the driving clips move (travel and turn), so rods, valve gear and wheels can be told apart.
- `rods`: every long moving part with a verdict (`main rod`, `candidate`, `rejected`) and the reason, per side and cylinder.
- `endSeats`: for each main rod and each end (`crank`, `cross`): the best seat (world and rod-local position), a grid of every cell
  tested (level, footprint), the clearance result and what clashed.
- `pairs`: left/right main-rod pairs with which end passes on both sides.
- `axles` and `boardSeats`: running-board fallback seats per driving axle and side, with counts of why cells failed.
- `nubParts` (new in the second version): for every travelling part and every static part of the running gear outside the frames:
  `islands` (pieces of the mesh that are 2-30 cm across, 12 or more triangles, not the part's largest piece: nubs modelled as their
  own piece, with size, top face area, top centre in world and part-local coordinates and the distance along the part from each end)
  and `bumps` (places where the part's own top surface, sampled by rays on a 1 cm grid, stands at least 6 mm above its surroundings:
  nubs welded into the part, with rise, plateau area, size, peak position in world and part-local coordinates, distance from each
  end, and whether a cup on the peak has clear space through a whole turn).
- `nubParts` entries with motion `static-window` are axlebox windows: the low frame meshes are far too big to scan whole, so a window
  0.8 m long round each driving axle, on each side, 0.5-2.0 m out, up to the top of the wheels, is scanned for bumps (not mesh pieces).
- `renders` and the `oil-renders` folder (third version): tilted orthographic pictures of the running gear, left and right, in tiles 4.5 m long
  (about 4 pictures per loco), with a small marker on every candidate: magenta = small island, cyan = larger island, yellow = bump of
  1 cm or more, orange = bump of 6-10 mm, green = a main-rod end seat that passed. They are what we look at to say which candidates are the
  real modelled oiling nubs. The zip is about 10-15 MB because of them.
- `spec`: the numbers used, so the analysis matches the requirements above.
