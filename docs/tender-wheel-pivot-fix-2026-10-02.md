# Tender wheel pivot correction — 2026-10-02

The A-23 report says its tender wheels rotate around the axle instead of on it. This was reproduced on the installed exported pack and corrected in the app-owned builder on `claude/unity-crash-message`. In-game acceptance remains pending.

## Earlier repair and remaining cause

Claude's `5f76f88` repair already selects a separate source node for each axle. It prevents one DV axle rotating both wheelsets through the source truck's shared `Wheels Animation` parent. That repair is present in the A-23 pack inspected here.

The remaining fault is the position of the rotation pivot. For `truck.archbar.tatum`, the original wheel spindle is at 0.422442 m while the measured tread radius is 0.379400 m. The core places `[axle]` at the rolling radius and attaches the source wheel nodes while preserving world position. This leaves the wheel spindle approximately 43.042 mm above its rotation pivot. A full turn therefore moves the wheel centre through an orbit about 86.085 mm across. C-25 uses the same truck; its earlier gauge-pilot candidate predates this correction.

## Builder change

`src/rr2dv/unity/Rr2dvTruckWheels.cs` centres the visual `[axle]` on the prepared Railroader spindle nodes. It runs immediately after `AlignRr2dvBogieSupports` in the existing finishing pipeline, because support alignment otherwise resets the axle height to the rolling radius. Moving the pivot preserves all child world positions, including the resting wheels and any static children. Standard CCL/DV wheel rotation is retained.

The correction uses the source spindle transforms, not mesh bounds: asymmetric wheel meshes and LODs can have bounds centres away from their true spindle. Nodes on an axle must agree within 0.5 mm, remain within 5 mm of its recorded longitudinal position and have finite coordinates. Invalid or missing prepared nodes stop the build. Applying the correction twice is safe. Rolling radius, wheel-speed calibration, mass, collider/contact geometry and original source meshes are unchanged. Powered and pony axles without prepared truck nodes are outside this correction. No pinned tooling or offline-builder edit is required.

## Validation

| Check | Result |
|---|---|
| Installed A-23, four wheelsets, full turn sampled at 0/90/180/270/360 degrees | Reproduced 86.0846 mm wheel-centre travel |
| Same A-23 geometry after correction | 0.000382 mm residual travel; resting mesh centres and other transforms retained; repeated application passed |
| All 20 installed tenders, corrected on diagnostic clones | 164 prepared spindle nodes including LOD copies; 19 tenders initially exceeded 0.5 mm travel; maximum 86.0849 mm before, zero measured source-spindle travel after |
| Synthetic native export/reload regression | Four wheelsets, rotated parents and reversed source wheels; resting geometry and serialized rolling radius preserved; mismatched spindle rejected; 1 native unittest passed |
| Normal A-23 conversion and bundle audit | Build passed; audit had zero errors/warnings; no installation |
| Actual rebuilt A-23 bundle, loaded afresh | Four wheelsets; 0.000382 mm residual wheel-centre travel; passed |
| Adjacent steam/gauge/API regressions | 18 tests, 4 optional skips, no failures |

The fleet count is source nodes including render LODs, not 164 physical wheelsets. Fleet checks use spindle positions; A-23 also verifies actual mesh-bounds centres. These Unity checks do not establish in-game suspension, wheel contact, braking or visual acceptance.

Local receipts are under `rr2dv_work/truck-orbit-validation/{baseline,corrected,fleet-corrected,rebuilt}`. The normal A-23 run is `rr2dv_work/tp/20261002-095503-ls-440-a23-f84843`, with its candidate at `build/out/A-23 American`. The existing 22 builder warnings and 25 automatic choices remain in the review; they are separate from the successful bundle audit. Permanent regression sources are `tests/test_truck_wheels.py` and `tests/unity_runtime/TruckWheelOrbitRegression.cs`.

## Next game check

Restart the development app and rebuild A-23 and any C-25 built before this correction. The C-25 gauge test can continue independently. Check a fresh spawn through a complete wheel turn, forward/reverse, curves, braking/sliding, and save/reload. Record any wheel-centre wobble, frame movement or rail-contact regression. No installed game pack, game setting, stable checkout, commit, push or release was changed by this investigation.

The final read-only hash check found 20 installed bundles unchanged against the earlier gauge-survey baseline. C-25 differs while James is rebuilding/testing it; its current installed bundle also differs from the earlier gauge-pilot candidate. This investigation did not install either candidate or restore the baseline.
