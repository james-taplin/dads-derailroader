# Fleet oil-cup pass — 2026-10-02

The testing branch now has measured oil-cup fittings for all 21 stock steam locomotives. Every driven axle receives a left/right pair, with additional main-rod or crosshead bearing pairs where clear. Required total: `max(6, 2 × driven axles)` through twelve cups, in complete pairs. Current layouts contain **218 cups: 154 on detected modelled travelling nubs and 64 on measured level bearing seats**. Rebuild existing packs; published 0.4.4 predates this work.

| Loco | Driven axles | Required minimum | Fitted cups |
|---|---|---|---|
| A-23 | 2 | 6 | 8 |
| A-26 | 2 | 6 | 8 |
| B-65 | 4 | 8 | 12 |
| C-25 | 4 | 8 | 10 |
| C-40 | 4 | 8 | 12 |
| C-46 | 4 | 8 | 10 |
| C-55 | 4 | 8 | 12 |
| D-46 | 5 | 10 | 12 |
| F-71 | 5 | 10 | 12 |
| G-16 | 3 | 6 | 10 |
| G-25 | 3 | 6 | 10 |
| K-28T | 4 | 8 | 12 |
| K-35 | 4 | 8 | 12 |
| P-18 | 3 | 6 | 8 |
| P-43 | 3 | 6 | 10 |
| P-48 | 3 | 6 | 10 |
| S-23 | 3 | 6 | 10 |
| S-51 | 4 | 8 | 12 |
| T-17 | 3 | 6 | 10 |
| T-21 | 3 | 6 | 10 |
| T-22 | 3 | 6 | 8 |

## Construction and placement

The former finder stopped after finding main-rod end pairs, so most locos received only two cups. The new fitter covers every measured driver spindle before considering additional main-rod/crosshead bearings. It searches actual travelling gear, prefers raised modelled nubs and accepts a level bearing surface only with four footprint contacts over a 4 × 3 cm area. A finer 1 cm search found C-40's rear-right seat without reducing clearance requirements. F-71 uses supported flat seats where its big-end geometry has no usable travelling nub. Running boards and stationary wheel tops cannot fill the quota.

Source wheelsets sometimes describe evenly spaced axles while the models are unevenly spaced. Profiles use actual rotating-wheel spindle positions, including T-17's offset middle driver. Each axle fitting's mean position through a turn must agree with that axle and be nearer to it than any other driver.

Clearance sampling previously reset animation to rest before the nub finder finished calculating local coordinates. The search now restores its measurement pose around each clearance callback, then converts the retained local anchor back to rest consistently. Every provider is a child of its named travelling mesh, with a fixed local coordinate. Stock CCL creates the cup and assigns its tag; DV position sync follows the provider's position while retaining upright orientation. No custom runtime script is added.

`oil_fits.json` contains numerical fittings and evidence: source hashes, wheel radius, measured axle positions, parent paths, local anchors, search phases, side/axle identities and bearing roles. `stock_locos.json` remains the master table and records the same fittings and acceptance status. Refresh/regeneration preserves fitting and game evidence. C-40's earlier source-matched tender beam review (0.90–1.10 m) is also now in the table so an ordinary rebuild uses that verified band.

The builder validates actual source fingerprints, radius, axle count/positions, moving parent, side and bearing contact. Complete layouts are checked at 64 phases for a 3.5 cm radius, 9 cm high upright envelope, at least 12 cm cup spacing, and cup-base contact with the moving bearing within 6 mm. Lost support or a required pair stops the build; manual oiling is not silently disabled. Simulation point count equals external cup count. Export audit checks quota, paired tags, animated parents and simulation count, including inactive prefab ancestors.

## Validation and limits

Private receipts stay in ignored `rr2dv_work/oil-fleet-pass-20261002`:

- `scan-3`: all 21 source spindle measurements, read-only.
- `fit-6`: all 21 layouts pass measured axle identity, full-turn bearing contact, clearance and spacing.
- `runtime-6`: Unity 2019.4.40f1 / Creator 3.1.9 exported/reloaded every layout. Actual CCL import assigns door, refill and oil-level ports; actual DV provider/consumer methods pass **55,808 position checks**, using 64 forward and 64 reverse phases at two car transforms. Every cup travels, retains its parent/local anchor and stays upright.
- `production-runtime-1`: fresh **C-25, A-23, C-40 and F-71 production packs** pass another **10,752 checks** using original exported animations.
- Those four normal converter builds pass exported-pack audits with zero audit errors/warnings. Existing builder review warnings remain (20/22/33/33); these are not whole-locomotive game acceptance. Local runs under `rr2dv_work/of`: `20261002-130840-ls-280-c25-1d178d`, `20261002-130957-ls-440-a23-57937b`, `20261002-131458-ls-480-c40-1b485e`, `20261002-131639-ls-2102-f71-2abb39`. All decline installation.
- C-40 also passes an ordinary rebuild without an explicit geometry-review argument after carrying its accepted beam band into the table: `20261002-132500-ls-480-c40-bd8bfb`.
- Final Python suite: 380 tests, 21 optional skips, no failures. Focused oil/gauge/build/API/table checks: 65 tests, five optional skips, no failures. Master-table validation and whitespace checks pass. All 21 installed bundle hashes remain unchanged.

The fleet runtime fixture uses visual substitutes with actual DV components. A player-bundle clip cannot simply be copied into an editor asset: its editor curves are stripped. The fixture bakes observed transforms at validation phases; direct production-pack checks separately exercise original exported curves. Tests do not spawn a complete DV locomotive or initialise live oil-can interaction. Stock cup/lid appearance, visibility, oil-can access, live consumption/refilling and save/reload remain game checks.

Permanent optional entry: `test_oil_fleet.NativeOilFleet`, requiring `RR2DV_TEST_UNITY`, `RR2DV_TEST_CAR_CREATOR`, `RR2DV_TEST_DV_GAME` and `RR2DV_FLEET_OIL_INPUT`. Private input contains all 21 bundle/readable-mesh paths, measured driver radius/positions and `oiling` selections. Game geometry and machine paths are never committed.

Restart the development app and rebuild. Inspect both sides stopped and moving forwards/backwards, check all cups remain seated through a turn, open every lid, refill with the oil can, verify oil-level response, then save/reload. Record adjustments against that loco's fitting. No installed packs, game settings, stable checkout, main branch or release were changed.
