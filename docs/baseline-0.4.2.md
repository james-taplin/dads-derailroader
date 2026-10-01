# Baseline for 0.4.2: all 21 stock steam locos built and audited in one unattended run

Source: Codex's `tools/vanilla/build_all.py --force --acknowledge-experimental --accept-proposed-geometry` over all 21 packs (zip `vf_build.zip`
sent 2026-10-01; the app commit was the branch head after 5dcc6d6, clip fixes included). Nothing was installed (the personal-use notice is
refused by the tool). Audit = the app's bundle audit; in-game checks are still pending for every loco.

| loco | geometry rounds | oil cups | nub picks | build warnings | audit | seconds |
|---|---|---|---|---|---|---|
| S-23 | 0 | 2 | 2 | 32 | passed | 156 |
| S-51 | 1 | 4 | 4 | 23 | passed | 180 |
| D-46 | 0 | 2 | 3 | 19 | passed | 140 |
| F-71 | 0 | 4 | 2 | 34 | passed | 148 |
| G-16 | 0 | 2 | 3 | 22 | passed | 148 |
| G-25 | 1 | 4 | 4 | 29 | passed | 174 |
| C-25 | 0 | 2 | 1 | 21 | passed | 140 |
| C-46 | 1 | 2 | 1 | 27 | passed | 180 |
| C-55 | 0 | 4 | 4 | 29 | passed | 140 |
| K-28T | 0 | 2 | 3 | 16 | passed | 118 |
| K-35 | 0 | 2 | 3 | 21 | passed | 147 |
| B-65 | 0 | 4 | 4 | 20 | passed | 144 |
| A-23 | 0 | 4 | 4 | 23 | passed | 138 |
| A-26 | 0 | 2 | 3 | 25 | passed | 144 |
| T-17 | 0 | 2 | 2 | 22 | passed | 143 |
| T-21 | 0 | 2 | 1 | 37 | passed | 136 |
| T-22 | 2 | 2 | 2 | 24 | passed | 199 |
| P-18 | 0 | 2 | 2 | 21 | passed (1 warning: the HUD has no reading for loco water level) | 141 |
| P-43 | 1 | 2 | 3 | 44 | passed | 184 |
| P-48 | 0 | 4 | 4 | 40 | passed | 166 |
| C-40 | 1 | 2 | 2 | 34 | passed | 208 |

Geometry rounds = how many times the build stopped for "geometry review required" and the app's own measured end-beam proposal was used.
Nub picks = `rr2dv oil nub on ...` lines in the build report (a cup seated on a modelled nub, best clearance).

Used as the comparison point for later changes: rebuild and compare cups, warning counts and audit results against this table.
Untested in game, all of it: nub-seated cups, tender plates, the clip fixes (quoted names, the tender's child prefix, trailing-space names).
