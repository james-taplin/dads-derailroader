# Oil-fitting source compatibility investigation, 2 October 2026

Sumrac reported published 0.4.5 stopping at build preparation for S-23 with `game files changed; remeasure the oil-cup fitting before using it`. He says all locomotives fail at the same stage, while 0.4.4 works. His changed-file list and Railroader build number are not yet available. This establishes a compatibility regression, not a confirmed game update or changed mesh.

## Cause and correction

The oil preparation added in 0.4.5 compared the exact SHA256 hashes of the locomotive bundle, catalogue and definitions with the developer's measured installation. Any byte difference stopped before the native builder examined the actual model. A controlled S-23 definitions-hash difference reproduces the exact published error. This new guard explains the version difference and can affect the whole fleet after a common source update.

The development correction treats complete, valid but differing source hashes as a diagnostic requiring native fit validation. It names the changed files in BuildInput and the build report, without rewriting the actual input fingerprint, reference measurements or master-table hashes. A successful native validation is also logged.

Every selected fitting must still pass the existing checks against current built geometry and animation: actual axle positions and side, a named travelling mesh parent, bearing contact, and 64-phase upright clearance and spacing. Driver radius/count changes, missing or stationary parents, lost support, intersections, quota failures and invalid manifests still stop. Internal disagreement between the fitting library and its master-table reference also remains an error. This revalidates stored local coordinates against current geometry; it does not automatically invent replacement coordinates when a bearing actually moved.

The proposed-geometry button reviews end-beam placement only. It cannot address the published oil hash error, and old source-mismatched geometry reviews remain refused. The app's existing source staging, fingerprint and cache invalidation are unchanged.

## Reproduction and evidence

Private receipts are in ignored `rr2dv_work/oil-source-compatibility-20261002`, with suite logs alongside that directory. Published-code comparison uses the unchanged `v0.4.5` tag. The original report is reproduced with only the S-23 definitions hash changed; the corrected preparation retains all ten cups and identifies `Definitions.json` as differing.

Python regressions cover separate bundle, catalogue and definition changes for every supported locomotive, unchanged-source selection, malformed/missing hash manifests, and radius/count changes despite differing hashes. Geometry and motion checks run separately in native Unity; Python preparation alone is not acceptance of a fit.

The native test uses actual source hierarchy and private readable mesh buffers. Negative cases alter axle coordinates, replace a bearing's real mesh with geometry displaced by five world metres, and remove the named parent. The initial negative fixture instead altered a local coordinate by 0.25, which was too small after K-35's mesh scaling; its failed assertion was retained and the fixture corrected to change actual geometry in world units. Production clearance thresholds were not weakened.

Real Unity 2019.4.40f1 / Creator 3.1.9 validation then passed all 21 locomotives and 218 exported/reloaded cups, including actual CCL port binding and 55,808 DV position-sync checks. All 63 deliberate axle/bearing/parent mismatches were rejected despite changed-source flags. Receipt: `native-2/result.json`. The permanent optional `test_oil_fleet.NativeOilFleet` now simulates source-byte differences on every case and includes those rejection checks. Its geometry, visual-substitute and live-game limitations are the same as the fleet report.

The full Python suite passed 387 tests with no failures/errors and 21 optional skips. The eight focused oil-policy tests also passed. The separate native run above exercised the optional fleet scenario explicitly. Whitespace checks passed; no pinned-tooling changes or installed-pack modifications were made.

## Support and release state

The correction is development work on the testing branch. Published 0.4.5 is unchanged, and no replacement release or tag was made during investigation. Sumrac can temporarily keep using 0.4.4, which he reports working. Do not tell him to edit source hashes, accept an unrelated geometry proposal or reinstall the game solely on this evidence.

His exact changed-file list and build number are still needed to attribute the mismatch. Successful local regression tests do not establish compatibility with his actual game files or whole-locomotive game appearance. See [the fleet oil pass](oil-cup-fleet-pass-2026-10-02.md) for runtime-fixture and in-game limitations.
