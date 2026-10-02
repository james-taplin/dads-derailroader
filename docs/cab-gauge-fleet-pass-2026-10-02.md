# Fleet cab gauge pass — 2026-10-02

The testing branch now has measured instrument fittings for all 21 steam locomotives. James authorised the fleet pass after the C-25 feedback and selected steam-chest pressure as the fourth instrument. This supersedes the pilot-only rollout status in the earlier implementation report. Existing installed packs need rebuilding; the published 0.4.4 package predates this pass.

| Physical instruments | Locomotives | Readings |
|---|---|---|
| 2 | C-25, K-35 | Boiler pressure; brake pipe and cylinder/application pressure |
| 3 | A-23, C-40, C-46, G-16, P-18, P-43, T-17 | Boiler; pipe/cylinder brakes; speedometer |
| 4 | A-26, B-65, C-55, D-46, F-71, G-25, K-28T, P-48, S-23, S-51, T-21, T-22 | Boiler; pipe/cylinder brakes; speedometer; steam-chest pressure |

That is **73 physical assemblies**, including 21 dual-needle brake instruments. Numerical km/h and main-reservoir pressure remain available on F4, including the two-instrument cabs. Main-reservoir pressure is distinct from cylinder/application pressure.

## Construction and bespoke tuning

Boiler and chest instruments use the complete S060 pressuremeter housing, face, glass and needle through existing CCL resource grabbers. Brake and speed instruments use that housing/glass with app-owned standalone artwork and needles. Brake needles are labelled black PIPE and red CYL. Speed and chest use the stock DV damping settings (0.5-second smooth time, 0.001 update threshold).

The pressuremeter's printed 0–18 bar scale receives 1–19 bar absolute. The brake face's printed 0–10 bar scale receives 1–11 bar absolute: DV's brake readers pass absolute pressure directly, and the brake system's released cylinder pressure is 1 bar. Physical speed is 0–100 km/h; its reader uses speed magnitude. The numerical HUD is not limited to the physical dial's scale.

`src/rr2dv/gauge_fits.json` contains each selected source index/name, reading, position, rotation, scale, source support path, contact points and evidence. `src/rr2dv/stock_locos.json` remains the master table and records the same numerical fittings plus the HUD, dynamo and tender-pivot repairs. The C-25 coupling tilt remains explicitly open. `tools/vanilla/update_tuning.py` reconciles the table; the source-table generator now carries these fittings forward and refuses changed source hashes until they are remeasured.

Known source cabs receive their explicit two-, three- or four-instrument layout. They no longer receive extra faces inferred from neighbouring dials. Changed source mount counts, identities or transforms stop the build for fitting review. T-21's two selected mounts with the same original name receive distinct brake/chest names.

Fittings use either a measured backing pad or compact mounting studs meeting static source geometry. Pad checks require at least seven of nine contacts within 4 mm and reject penetration beyond 1 mm. Stud adapters require at least three non-collinear contacts, each meeting its named source mesh within 1 mm; lengths must be 2–160 mm. The search excludes moving controls and wheels as supports and samples the housing envelope. These screens do not prove complete cab clearance.

Most centres moved roughly 1–5 cm from their selected source mounts. Larger measured relocations include K-28T boiler (12.1 cm), P-43 brakes (9.7 cm), P-48 brakes (15.7 cm) and P-48 chest (8.5 cm). D-46's boiler and P-48's brakes were scaled down to avoid crowding. Original angled fittings are retained where suitable. K-35's brake and C-46's speed instrument reuse fireman-facing mounts; their driver visibility particularly needs checking.

## Validation and limits

Local receipts are kept in ignored `rr2dv_work/gauge-fleet-pass-20261002`:

- `baseline-2`: fresh read-only inspection of all 21 installed cabs; installed hashes unchanged, native geometry regressions passed.
- `fit-7`: all 73 proposed assemblies have measured pad or adapter support. B-65 brakes use its source Air Brake Gauge cluster, avoiding overly long studs at the previous high mount.
- `assembly-6`: real Unity 2019.4.40f1 / Car Creator 3.1.9 exported and reloaded all 21 fitted interiors and LODs. Actual CCL importer methods bound the donor meshes/material slots, and actual DV indicator code passed 282 minimum/midpoint/maximum needle-position checks. Essential readers, dual brake readers, damping fields, face direction, repeated construction and local LOD references passed. No donor mesh bytes were embedded in those instrument exports.
- Full Python suite: 373 tests passed with 13 optional skips; final focused fitting/API checks: 26 tests with two optional skips. Kit/analysis checks: eight passed. Private rendered brake/speed samples have complete cases and readable, correctly oriented faces/captions; synthetic housing materials and disabled diagnostic glass do not establish game appearance.
- Normal converter builds passed for C-25 (two instruments), A-23 (three) and T-21 (four). Each final exported-pack audit has zero errors/warnings. Existing builder review warnings remain: 20, 22 and 36 respectively. Local run receipts are `rr2dv_work/gf/20261002-121309-ls-280-c25-ac3d4d`, `20261002-121559-ls-440-a23-84ad30` and `20261002-121821-ls-460-t21-a9967d`. Packs were built without installation. The first C-25 build caught a compact-JSON requirement in the pinned parser; app output was corrected and the regression now covers it.
- Final installed-bundle hash check: all 21 unchanged against the fresh baseline. The stable checkout, published release, game settings and installed packs were not changed by this pass.

The optional permanent native entry is `test_gauge_fleet.NativeFleet`. It requires `RR2DV_TEST_UNITY`, `RR2DV_TEST_CAR_CREATOR`, `RR2DV_TEST_DV_GAME`, `RR2DV_PRESSURE_MESHES` and `RR2DV_FLEET_ASSEMBLY_INPUT`. Fleet input contains `cases` with source bundle/readable mesh paths and the corresponding `gauges` selection from the fitting library. These machine paths and buffers stay local. The entry creates a separate Creator project and runs `CclLocoBuild.FleetGaugeRegression`.

The runtime harness seeds private donor mesh buffers and synthetic named materials. It checks construction, binding and calibration without spawning a complete game locomotive. It does not establish actual glass/shader appearance, driver sightlines, full control sweeps, live simulation attachment, F4 rendering or save/reload. All master-table fittings remain `fleet-candidate-awaiting-game-acceptance`.

Rebuild from the restarted testing-branch app. For each loco, check boiler and both brake needles, reverse-speed magnitude, chest response where fitted, all cases/backings, visibility from both cab sides, and control travel. Check numerical km/h on F4 even where no physical speedometer fits. Then save/reload and repeat. Record any adjustment against that loco's fitting, rather than applying an unmeasured fleet offset.
