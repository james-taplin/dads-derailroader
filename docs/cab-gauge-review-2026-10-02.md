# Cab gauge review — 0.4.4 work, 2026-10-02

Every locomotive must have a physical main-brake instrument showing **brake pipe and brake-cylinder/application pressure**, a boiler-pressure instrument and a speedometer. Add a steam-chest instrument where a readable, supported mount can be demonstrated. Main-reservoir pressure is useful additional information, but does not replace brake-cylinder/application pressure. Existing reservoir instruments need not be removed simply to meet this minimum.

Implementation follow-up: [initial C-25 pilot and fleet numerical HUD requirement](cab-gauge-implementation-2026-10-02.md). The donor calibration uncertainty below was subsequently resolved using the installed DV component serialization and code. The original slot table remains a historical baseline; it is not a fleet replacement approval.

## Tests and inspected baseline

The supplied Cab-Gauge-Kit-0.1.zip's five source files match the existing `tools/cab-gauge-kit` files byte for byte. Its four Python tests passed. All six converter gauge tests passed, including the real Railroader definitions for all 21 locos. Four additional analysis tests cover reading identity, pipe/cylinder versus reservoir, missing needle references and incomplete/duplicate fleet receipts.

A fresh read-only native inspection in **Unity 2019.4.40f1 / Car Creator 3.1.9** completed on all 21 installed packs with exit 0. The kit's native regressions passed: rear/side/front faces, nine-point support, floating/intersecting/partial support and mirrored winding. All 21 input bundle hashes were unchanged after inspection.

Measured 101 dial assemblies: 50 rear-facing, 33 angled, 18 sideways; 48 supported candidates, 44 unsupported within 30 mm, five intersecting and four partially supported. Only **21 dials satisfy both the rear-facing and nearby-support screens**. These are screening results, not proof of readability, actual mounting, donor fit or runtime calibration. An angled dial may be correctly aimed at the driver: it requires review, not an automatic rotation to -Z.

Receipts remain local under `rr2dv_work/gauge-review-20261002-fleet-2`: `summary.json`, `result.json`, `gauges.csv`, `report.html`, `gauge-results.zip`, `unity.log` and the disposable inspection project. Derived per-loco readings and inspected bundle hashes are in `rr2dv_work/gauge-review-20261002-analysis/fleet.csv`. `tools/cab-gauge-kit/analyse.py` reproduces that table from a complete receipt. Full meshes, game textures and private inputs are not included in this document.

This measures the **currently installed bundles**, including packs predating recent converter work; it does not certify a fresh 0.4.4 build. It does not drive the simulation or inspect driver sight lines and full control sweeps.

## What DV can supply

The present builder does not copy complete vanilla gauge prefabs. `BuildInterior` in the pinned core constructs a disc, generated dial texture, glass disc and needles, then attaches CCL indicator readers. Where the RR model supplies a housing, that housing is separate from these generated parts. Reusing genuine DV instruments therefore requires a new app-owned assembly step rather than renaming these dials.

Read-only inspection of the installed DV `resources.assets` confirms both stock steam interiors and their actual mesh/material hierarchies. CCL 3.1.9 exposes **MeshGrabberFilter and MaterialGrabberRenderer**, but its object-instancer handles particles/audio, not a general complete-gauge-prefab copy. Use the established CCL grabbers to resolve vanilla resources at game load; do not ship vanilla asset bytes in the app.

| Reading | Reusable DV parts | Work still needed |
|---|---|---|
| Boiler pressure | S060's separate `Swivelables/Pressuremeter`: `s060_gauge_pressuremeter`, `s060_gauge_label_pressuremeter`, `s060_gauge_glass_pressuremeter`, `s060_needle_pressuremeter`; their `LocoS060_Interior`, `LocoS060_Gauges`, `GlassIndoors` materials are all in the Creator allowlists. S282 also has a separate pressuremeter. | Build an app-owned CCL assembly preserving the donor's transforms, pivot and complete housing/face/glass/needle. Rewire to `boiler.PRESSURE`. Match printed scale to needle calibration and choose a supported mount per cab. No new boiler-gauge artwork is required if that donor scale is suitable. |
| Steam-chest pressure, optional | The same separate DV pressuremeter can be reused with a chest-pressure reader and a clearly distinct label. Stock chest needles are also reusable. | Wire to `steamEngine.STEAM_CHEST_PRESSURE`; verify donor scale, label and a spare mount after required instruments and controls fit. The stock chest face itself is part of the larger cab panel, so it is not a separate ready-to-copy prefab. |
| Main brake: pipe + application | DV has separate movable needles and proper readers. The stock S060/S282 brake-pipe and brake-cylinder indicators share a pivot, with the red cylinder needle offset 1.5 mm from the black pipe needle; `NeedleRed` is available. A DV pressuremeter housing can also be adapted. | Make a standalone two-needle brake assembly. Stock brake faces/housings are not exposed as a complete isolated prefab. Provide a new or isolated correctly marked brake face, preserve separate pivots/depths, and attach pipe and cylinder readers. A reservoir/pipe gauge is not a substitute. |
| Speed | DV speed needles and lagging indicator behaviour are reusable. A donor housing can be adapted. | Make a standalone speed assembly with an appropriate km/h dial and matched range, direction and damping. Stock speed faces are in the combined cab mesh, not separate gauge prefabs. Attach `traction.WHEEL_SPEED_KMH_EXT_IN` and the HUD speed reference. |
| Mounts and brackets | Existing RR backhead plates or instrument supports may be retained where verified. | Create brackets, small panels or pedestals where current slots float, intersect, face away, or cannot hold the donor housing without clipping. These must be fitted per cab; a generic offset is not acceptance. |

The S060 boiler dial face/glass is about **152 mm across**; its housing bounds are **169 mm wide, 184 mm high and 75 mm deep** at donor scale. Current generated faces range from about 68 to 219 mm. Matching face diameter alone does not establish that the extra housing depth, lower stem and rim fit. Preserve readability when scaling. The combined S060 gauge-label mesh spans roughly **712 × 582 × 1136 mm** and the S282 gauge mesh **1129 × 659 × 612 mm**: copying either whole group would transplant multiple instruments in the original cab arrangement.

Conclusion: **no required reading needs a new simulation system or a whole gauge built from zero**. Boiler and optional chest can use the separate DV pressuremeter. Brake and speed need newly assembled standalone instruments, with custom/adapted faces and housing as required. Per-cab mounting is the largest unresolved task. Stripped vanilla MonoBehaviour fields could not be fully decoded by the installed UnityPy environment; exact donor ranges, needle angles and damping remain to be verified rather than inferred from names.

## Per-locomotive findings

Columns describe the **existing installed slot**, not an approved replacement. Boiler/chest use the DV donor route above; main brake/speed use the standalone assembly route. “Supported candidate” means the kit's centre/rim ray screen passed and still requires model/driver review. Where more than one instrument has the same reading, this table shows the best current candidate, not permission to discard the others.

| Loco | Boiler | Main brake: pipe + cylinder | Speed | Optional chest |
|---|---|---|---|---|
| A-23 | rear; unsupported | angled 27 deg; supported candidate | angled 27 deg; unsupported | No physical dial |
| A-26 | rear; supported candidate | angled 20 deg; supported candidate | angled 20 deg; unsupported | rear; supported candidate |
| B-65 | sideways; unsupported | rear; unsupported | angled 15 deg; unsupported | sideways; unsupported |
| C-25 | rear; supported candidate | rear; supported candidate | rear; unsupported | No physical dial |
| C-40 | rear; supported candidate | sideways; supported candidate | rear; unsupported | No physical dial |
| C-46 | sideways; supported candidate | rear; unsupported | rear; unsupported | sideways; supported candidate |
| C-55 | angled 32 deg; unsupported | angled 31 deg; supported candidate | angled 31 deg; unsupported | rear; unsupported |
| D-46 | sideways; unsupported | rear; supported candidate | rear; partial support | sideways; unsupported |
| F-71 | rear; supported candidate | angled 27 deg; supported candidate | angled 27 deg; unsupported | rear; supported candidate |
| G-16 | rear; supported candidate | rear; unsupported | rear; unsupported | No physical dial |
| G-25 | sideways; unsupported | rear; supported candidate | rear; supported candidate | sideways; unsupported |
| K-28T | sideways; supported candidate | rear; supported candidate | rear; supported candidate | sideways; supported candidate |
| K-35 | sideways; supported candidate | rear; unsupported | rear; unsupported | sideways; supported candidate |
| P-18 | rear; unsupported | angled 27 deg; supported candidate | angled 27 deg; unsupported | No physical dial |
| P-43 | rear; intersects surface | angled 35 deg; unsupported | angled 21 deg; supported candidate | No physical dial |
| P-48 | sideways; partial support | rear; intersects surface | angled 21 deg; supported candidate | sideways; partial support |
| S-23 | sideways; unsupported | angled 42 deg; supported candidate | angled 42 deg; unsupported | sideways; unsupported |
| S-51 | rear; supported candidate | angled 27 deg; supported candidate | angled 27 deg; unsupported | rear; supported candidate |
| T-17 | rear; unsupported | rear; supported candidate | rear; unsupported | No physical dial |
| T-21 | rear; unsupported | rear; unsupported | rear; unsupported | rear; unsupported |
| T-22 | rear; supported candidate | angled 27 deg; supported candidate | angled 27 deg; unsupported | rear; supported candidate |

Seven boiler slots meet both screens: A-26, C-25, C-40, F-71, G-16, S-51, T-22. Four existing chest slots meet both: A-26, F-71, S-51, T-22. This is enough to nominate pilots, not to certify the larger donor housing fits. G-25 and K-28T are the two speed slots meeting both screens; P-43/P-48 also have fully supported but angled speed slots. The other 17 speed slots need mounting work or additional support review.

All 21 contain visible boiler, pipe/cylinder and speed readers in this installed baseline. Fourteen have a visible chest reader; the other seven have no physical chest dial in this scan. Missing physical chest is not failure of the required instrument set. HUD-only indicators are outside this dial scan.

## Implementation order and acceptance

1. Prove the separate S060 pressuremeter assembly on C-25 or A-26, preserving donor geometry, complete transforms and CCL references through export/reload. Verify printed scale and needles at minimum, intermediate and maximum values. Add the app extension around the existing interior build; do not modify pinned tooling or the offline builder.
2. Build common standalone main-brake and speed assemblies. Give every loco all required readings; do not reuse an MR/pipe reading as application pressure. Preserve HUD references and keep optional reservoir instruments functional.
3. Fit assemblies to actual backhead/panel/bracket geometry. Start the relocation review with B-65 and T-21 (no dial met the support screen), P-43/P-48 (intersections), and the nine locos with sideways boiler pairs. Do not apply a fleet-wide 90-degree correction: side-facing sources and combined model housings need individual review.
4. Add optional chest only after required instrument visibility, housing clearance and control sweeps are established. A-26/F-71/S-51/T-22 are the first existing-slot candidates. Defer the seven absent physical slots until a spare mount is demonstrated.
5. Rebuild each affected pack and rerun the kit against its new bundle hash, extending the probe to recognise genuine donor face meshes as well as today's child named `face`. Check seated/standing driver views, full control travel, gauge lighting/glass, units, demand/pressure behaviour, and save/reload in game.

The inspection and report are complete. Production gauge replacements, revised mounts and game-side acceptance are **not implemented or claimed by this investigation**. No installed pack, game asset, pinned tooling, offline builder or release version changed; no commit/push/release performed.
