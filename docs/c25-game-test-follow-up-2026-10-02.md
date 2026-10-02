# C-25 game-test follow-up — 2026-10-02

James's screenshots show two unsupported generated gauge faces, a forward-leaning dynamo jet against a rearward spout, and a slight body tilt while coupled. He confirmed the locomotive returns level when uncoupled on straight, level track. The first two causes are confirmed and corrected locally on `claude/unity-crash-message`. The live coupling tilt remains unresolved.

## Instruments

C-25's source definition contains only `Brake Gauge` (`DualBrakeCylinderLine`) and `Boiler Gauge` (`BoilerPressure`). The earlier shared rule added a physical reservoir gauge and speedometer beside the brake gauge without establishing their backing surfaces. Those are the unsupported faces visible in the game screenshot.

The shared rule in `buildrecord._Builder._ensure_gauges` now limits a cab with two source gauges to boiler pressure and brake pipe/cylinder pressure at those source positions, without physical reservoir, chest or speed additions. It does not classify engines by size or date: the available source instrument count determines the policy. In the current fleet this affects C-25 and K-35. C-25 retains its original pair; K-35's second boiler-gauge mount becomes the brake instrument and still needs its own game acceptance.

The existing C-25 donor boiler pilot is retained. The normal core already supplies invisible speed/chest readers when physical dials are absent. The app's HUD finishing preserves absolute numerical km/h and now supplies a standard invisible brake-reservoir reader when no physical reservoir gauge exists. The normal steam HUD therefore keeps its reservoir reading. No new runtime script is exported.

## Dynamo jet

The tested C-25 report explicitly includes the prior 180-degree yaw correction, so this is not attributed to a stale app. Readable diagnostic copies of its exported meshes reproduce the outward pipe direction `(-0.003986, 0.871570, -0.490254)`, while the exported jet points `(0.003986, 0.871571, 0.490254)`: the blanket horizontal reversal sends a correctly measured rearward direction forward.

`AimRr2dvJets` now uses the measured outward direction directly. Position and upward tilt are retained; unmeasurable pipes keep the straight-up fallback, and whistle/safety remain upright. The first 0.4.4 changelog line has been rewritten accordingly. The previous synthetic regression proved the requested reversal occurred, but used the wrong acceptance target for this game geometry. The revised regression checks alignment with the pipe itself and fails against the old code before passing with the correction.

## Coupling tilt: investigation still open

The uncoupling observation ties the symptom to live coupling behavior. Read-only cloned template inspection shows both exported coupler centres at y = 1.05 m, zero height difference, and no body/bogie collider penetration when the exported coupling points are aligned. Front/rear locomotive support radii are 0.65 m; tender supports are 0.3794 m. These authored poses do not reproduce the running game's track constraints, suspension or loaded body heights.

The source CCL `RigidCouplerInternal` waits for DV joint adaptation, then locks all three linear axes and enables automatic connected-anchor configuration. Inspection of the installed game's `Coupler.CreateRigidJoint` confirms the standard configurable-joint path and limited/free angular axes. This identifies the next runtime path to inspect; it does not prove which constraint causes C-25 to tilt. No coupling, mass, support or spacing change is claimed. The existing visual draw-gear gap warning also remains open; a mesh gap alone does not explain pitching.

Next evidence: settled uncoupled versus coupled root pitch and bogie heights, both live coupling-anchor world heights, joint state before/after adaptation and tightening, and comparison with the vanilla S282 tender connection. Capture both sides at the same track position and resource loads. Do not disable rigid coupling or invent a vertical offset from the screenshot alone.

## Validation and candidate

- Source/instrument and adjacent steam/API checks: 19 tests, 3 optional skips, no failures. The source test inspected all 21 real definitions, including the two-cab policy and retained positions.
- Build/record regressions: 55 tests passed. The sandboxed attempt could not exercise local fake-tool servers; the supported unsandboxed run passed.
- Native dynamo baseline failed on the revised outlet-alignment expectation. With the fix, eight pipe directions/fallback cases passed, including rotated parents, repeated application, untouched other jets and bundle export/reload. Receipts: `rr2dv_work/dynamo-jet-validation/outlet-baseline` and `outlet-corrected`.
- Native gauge unittest: four tests passed without skips in 29.902 seconds, including invisible reservoir-reader existence/no visible geometry/no duplication, real pressure/speed calibration, CCL resource binding and export/reload.
- Normal final C-25 conversion and bundle audit passed with zero audit errors/warnings. Existing 20 builder warnings and 22 automatic choices are retained in its review.
- Fresh final exported-bundle inspection passed: exactly two physical gauges, invisible absolute-speed and reservoir HUD readers, and jet direction matching the rearward source spout. Receipts: `rr2dv_work/c25-inspection/baseline-4` and `corrected`. Its private readable diagnostic buffers stay under ignored work files.

Final candidate: `rr2dv_work/c25fix/20261002-102720-ls-280-c25-793f4a/build/out/C-25 Consolidation`. It also contains the earlier tender-wheel spindle correction. Both normal conversions used `ask=False`; neither candidate was installed. Restart the development app and rebuild C-25 through the normal flow to apply. Confirm both instruments, live HUD readings, jet off/on and save/reload in game. Coupling tilt and complete gauge-pilot acceptance remain open. No installed pack, stable checkout, pinned tooling, offline builder, commit, push or release was changed by this follow-up.
