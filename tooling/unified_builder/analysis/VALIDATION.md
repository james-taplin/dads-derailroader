# Unified builder validation — 2026-09-26

Status: **Ready with limitations for author review and game testing.** Shared builder implemented; G29 and C21 compile/export/audit successfully. No merged-output game session, installation, save migration or VR test was performed. The other 23 catalogue entries remain measurement records, not playable conversions.

| Acceptance criterion | Result | Evidence |
|---|---|---|
| One shared core, separate measured profiles | Passed | tools/unity, profiles; per-run source_hashes.json |
| G29 normal 0.9.2 | Passed | builds/g29/unified02/result.json + bundle_audit.json; 7 exact reference warnings |
| G29 share 0.9.2, stock DV audio | Passed | builds/g29/share01/result.json + bundle_audit.json; 7 exact reference warnings, zero AudioClips |
| C21 0.1.4 | Passed | builds/c21/unified01/result.json + bundle_audit.json; 8 exact reference warnings, zero AudioClips |
| Four plate anchors per pack point outward | Passed | bundle audit quaternions/side signs; C21 cab yaw corrected |
| Coupler beams/live anchors and RR tender gap retained | Passed | exact normalized report comparison; G29 gap -8.194, C21 -7.445 m; zero solid-overlap cells |
| Final stock-fitting poses validated | Passed | scaled bracket .431255 m, G29 locomotive exact seat + tender automatic placement; C21 measured exact poses |
| Oil identity/attachment preserved | Passed | G29 6, C21 8; original cup tag/index order; moving mesh parents; four-phase motion + triangle-surface proximity |
| Shallow-cap detector | Passed for C21 | 8 independent island candidates match explicit manifest; optional detector, no automatic save-layout rewrite |
| Unequal pony radii | Passed in editor test | actual CCL proxies .42/.47 with distinct animator references; invalid radius rejected; no six-family fleet-build claim |
| Empty geometry/tank-face checks | Passed | editor synthetic raycast checks; accepted G29/C21 beam faces unchanged with 65-ray band |
| Clip resolver safeguards | Passed | 9 Python tests, including unresolved/ambiguous rejection and no partial writes |
| Catalogue generation | Passed | 25 source-hashed records; 238 linked source candidates; 6 unequal-radius entries; 2 measured profiles |
| C21 mass correction | Applied and audited | source working-order interpretation: 41,730.50 kg - 5,632.78 L spawn boiler water = 36,097.72 kg base; auxiliary contents additional |
| Visual inspection | Limited, completed | inspected G29 overview/right oil stand-ins and C21 low/standing oil views; close-up lighting/occlusion limits judgement; runtime stock replacements not shown by editor |
| In-game driving, plates, oil interaction, save/reload, VR | Not run | required next validation for these newly merged outputs |
| C13 whole-workspace migration | Plan delivered | MIGRATION_PLAN.md; original paths retained pending coordinated migration review |

Tests: `tools/test_workflow.py` **9/9 passed**, recorded in workflow_tests.txt/json. Unity `UnifiedBuilderTests.Run` **8/8 passed**, builds/g29/checks02/editor_tests.txt/json. The Unity tests exercise triangle seating, edge/degenerate cases, no-hit rejection, tank-face exclusion, collider restoration, actual unequal-radius CCL proxies, and zero-radius rejection.

Environment: Unity 2019.4.40f1, CCL/CarCreator 3.1.9, Built-in renderer, Windows CCL bundles. Normal user-context editor launch is required for local licensing; no license/toolchain/package changes. No compile errors in final runs. Original G/P sources were snapshotted before merge. The sole later observed predecessor change was Claude's documented C14 G29_SHARE conditional, incorporated into the new profile; snapshots remain unchanged.

Preserved failed/intermediate evidence: g29/merge01 could not reach licensing under the restricted process; g29/merge03 rejected a valid seating location because the newly written validator compared nearest vertices instead of triangle surfaces. The validator was corrected, covered by numerical editor tests, and final exports pass. Intermediate merge runs do not represent current delivery.

Intentional differences from predecessors: C21 cab plate yaw; C21 base mass -5632.78 kg; G29 firebox HUD capacity 65 rather than hardcoded150 kg; corrected bracket stand-ins/checks; stricter geometry/binding/result gates; generated catalogue application preserving measured radii. No silent cup-count, control-port, driver/tender radius, outer-anchor or drawbar-gap change. Share G29 intentionally uses stock DV audio.

Runtime checklist: spawn each loco/tender, inspect both cab plates, exercise all eight/six cups through wheel motion, couple and operate both outer hardware sets, drive/brake/steam under load (especially C21 mass), save/reload and confirm control/oil state. Existing installed packs remain untouched by this workflow.
