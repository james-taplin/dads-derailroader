# Visible surfaces for generated fittings

Generated control roots and their labels seat against visible source meshes. Number plates seat against visible
built-body meshes at the source RoadNumber anchor's height and longitudinal position. Source collision shapes and
disabled renderers must not determine these surfaces. The existing fitting stand-offs and plate orientation remain.
Missing surfaces or surfaces facing the wrong direction stop the build instead of exporting an unseated fitting.

`Rr2dvPlacement.cs` is an app-owned partial extension of the pinned builder. It uses the core's `VisualHits`, which
temporarily disables source colliders and restores them after measuring enabled mesh renderers. It corrects the
saved exterior after `BuildExterior`, and generated controls after `BuildInterior`, before `BuildInteriorLOD` copies
the corrected interior. Preserved source handles, joint settings, input wiring, couplers and brake-release placement
are unchanged. Every measured placement is recorded in `build_report.txt`.

The extension retains the core entry/car orchestration because the pinned snapshot exposes no post-placement hook.
When refreshing the snapshot, review `RunRr2dv` and `BuildRr2dvCar` against core `Run` and `BuildCar`, including validation,
state resets, tender linking, export and failure handling. The app entry deliberately always strips custom audio and
uses its generated vehicle record, without the optional legacy catalogue-profile route.

## Regression evidence

On 2026-09-27, Unity 2019.4 measurements reproduced two failures in the A18 candidate:

- Transferring source colliders exposed a disabled collision mesh to the old side probe. Cab plates were placed at
  x ±1.463 m instead of ±1.344 m against the visible cab. The new rule leaves tender plates at ±1.331 m.
- The old control ray hit a collision shape at z -2.184 m. The visible boiler was at -1.904 m; the generated whistle
  lever root now seats at -1.924 m instead of -2.204 m. Other generated controls use their own measured hits.

These are regression observations, not converter constants or per-vehicle exceptions. Both A18 and S16 exported with
the new placement rule. The A18 exported-bundle audit passed; runtime acceptance remains pending.

`tests/unity_runtime/PlacementRegression.cs` uses synthetic geometry unrelated to either locomotive. It checks a
hidden collision mesh outside a visible side wall, a collision-only box in front of a visible backhead, saved/reloaded
plate/control/label positions, attached grip placement, and restoration of source colliders. It passed in real Unity.

To run it through unittest, set `RR2DV_TEST_UNITY` to Unity 2019.4.40f1 and `RR2DV_TEST_BUILDER_PROJECT` to a disposable
assembled rr2dv project, then run `python -m unittest discover -s tests -p test_unity_runtime.py -v`. This writes editor
test scripts and temporary synthetic assets into that explicitly selected project. Stand-in C# compilation does not
cover the partial extension because it requires the real pinned builder's private members.

## Remaining runtime findings

The A18 user's successful steam raising is positive simulation evidence. Driving remains for their manual test.
The photographed tilt and wheel clipping are not claimed fixed by this change. Export inspection found identity
bogie rotations, mixed pilot/driver geometry, tender visual wheel centres 24–26 mm below their rotation pivots, and
missing source tender-wheel materials. Those observations do not establish a single cause of the runtime tilt and
must not be converted into a guessed model-specific height offset. No AI-driver investigation is required.
