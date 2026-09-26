# S16 conversion build status

The first personal S16 pre-release is built and passes the automated build and bundle gates. The authoritative deliverable is `locos/s16/builds/prerelease2`, version 0.1.0; `packages/LLW_S16_0.1.0_personal.zip` is the installable package. Its package and bundle hashes are recorded in `delivery.json` and the ZIP's `.sha256` file.

The generic `LlwVehicleRecord` JSON loader, S16 record, launcher integration and first-build auditor are implemented. G29/C21 keep their existing profile entry points and physics. Original S16 source assets and the source inspection project remain preserved.

## Validation evidence

| Check | Result | Evidence |
|---|---|---|
| Python workflow/resolver checks | 9 passed | canonical `builder/tools/test_workflow.py` |
| JSON record contract | 18 passed | `builder/tests/vehicle-record`, final record exercised before test05 |
| Actual Unity geometry regressions | 28 passed | `locos/s16/analysis/mesh-weld-tests04` |
| Auditor negative/mutation tests | 16 passed | `locos/s16/analysis/audit-tests-final.txt` |
| Source closure | passed | final run `source_closure.json` |
| CCL ports, simulation, controls, wheel/axle/resources and serialized data | passed | final run `sim_ports.json` and `bundle_audit.json` |
| Animated tank-hatch grip alignment | 5 phases per hatch, maximum error 0.2 micrometres | final run `build_report.txt` |
| Six oil cups and real 90-degree lids | no sampled surface crossings across 576 point/phase/reverser combinations | `locos/s16/analysis/oil-screen-test05-six` |
| Final oil geometry/animation fidelity | identical to screened export | final run `oil_geometry_fingerprint.json` comparison |
| Coupling interaction exposure | all ten stock grab targets have clear centres from all six sampled approaches | `locos/s16/analysis/coupler-review/stock_grab_access.json` |

Three coupling mesh-box warnings remain and have exact written dispositions in `profile/warning_dispositions.json`. James explicitly accepted mesh overlaps when grabbable colliders are available and not buried. No warning was suppressed in the builder, and no unnecessary coupling or hose offset was introduced.

## Acceptance boundary

There are no remaining build/toolchain blockers. This is a pre-release ready for an in-game smoke test, not an accepted runtime reference. Driving, heat/fuel calibration, dynamic hose behavior, servicing, save/reload and VR interaction remain unverified. Some oil points are obscured at a few crank positions; the measured body/lid geometry is clear, and changing wheel position provides access in the screen.

Installed on 2026-09-26 into `Mods/LLW S16` at James's request, after a fresh audit; the installed bundle hash matches prerelease2. The installation receipt is linked in `delivery.json`. Other mods and saves were not changed. No accepted S16 baseline is declared until game acceptance. Detailed assumptions and the suggested first test are in the delivered `BUILD_NOTES.md`; measurements are in `locos/s16/profile/S16_MEASUREMENTS.md`.

Failed exploratory runs and the superseded prerelease1 are preserved for diagnosis. Prerelease2 corrects two evidence links in the record; it uses the same tested geometry and simulation settings.
