# Initial cab instrument implementation — 0.4.4 testing branch

## Delivered

The app-owned gauge construction path and separate measured fitting library are implemented. C-25's main boiler gauge is the first pilot. Its complete S060 pressuremeter housing, face, glass and needle use CCL MeshGrabberFilter/MaterialGrabberRenderer references; no extracted DV meshes, textures or materials are shipped in the app or pilot gauge assembly. The existing converter, CCL pipeline and pinned tooling remain in use.

Every steam locomotive's new build also requires a numerical **km/h F4 speed box**, independently of the physical speedometer work. Reviewed custom HUDs retain their controls and enable the numerical speed slot; a vanilla fallback is S282, including tank locomotives. The reader reports absolute traction speed, including reverse travel. This changes neither the simulation basis nor the sounds of tank engines. Previously installed packs need rebuilding.

The implementation brief requires a boiler pilot to be accepted before copying fits across the fleet. James's first C-25 game test shows the donor boiler housing in place, but reports two unsupported extra faces. The updated two-source-gauge rule below removes those additions; complete pilot acceptance and fleet replacement remain pending.

## Architecture and verified calibration

- `src/rr2dv/gauges.py` validates the selected gauge role and fitting input. `gauge_fits.json` holds the C-25 position, rotation, scale, support point and support path separately from common assembly construction.
- `src/rr2dv/unity/Rr2dvGauges.cs` builds the donor assembly after the normal interior stage and before seating controls and making the interior LOD. It preserves the donor-relative needle pivot and reader transform. It restores only resource grabbers on the render-only LOD, with references to that LOD's own filters/renderers. Repeated application does not duplicate the assembly or grabbers.
- CCL resources: `s060_gauge_pressuremeter`, `s060_gauge_label_pressuremeter`, `s060_gauge_glass_pressuremeter`, `s060_needle_pressuremeter`; materials `LocoS060_Interior`, `LocoS060_Gauges`, `GlassIndoors`. These names are checked against CCL's allowlists. Missing geometry in diagnostic resource resolution fails explicitly.
- DV's printed pressure face is **0–18 bar**. The installed vanilla gauge reads **1–19 bar absolute**, with angles −135° to +135°, around local −Z, clamped. At 1 bar absolute the printed indication is zero; at 10 it is 9; at 19 it is 18. The reader uses `boiler.PRESSURE`, multiplier 1, offset 0. The simulation is unchanged.
- Donor face diameter is about 152 mm; complete housing is about 169 × 184 × 75 mm. C-25 retains scale 1. Its assembly root is `(-0.007416681, 3.47949219, -2.4512896)` with identity rotation. The measured support is `engine/Interior.007_LOD0.003`, plane z = −2.4341722. A 2 mm pad bridges the housing rear to that plane.

The native build checks nine rear support samples and the measured datum, rejecting missing/ambiguous support, intersections or insufficient contact. This establishes rear attachment geometry, not whole housing clearance. The gauge kit keeps its old face-distance screen and now separately measures complete housing pad support. The new C-25 face is correctly rear-facing but over 30 mm ahead of the backhead because of housing depth; its pad has **9/9 contacts**. Treat `supported-pad-candidate` as a screening result.

## Validation receipts, kept locally

1. Focused Python build/gauge/API checks: 50 tests ran with two optional skips before the final HUD extension; the final focused gauge/API run had 13 tests with two optional skips. The six source gauge tests include real definitions for all 21 locomotives. Eight gauge-kit/analysis tests passed. The final native unittest entry ran all four pilot tests successfully in 29 seconds, with no skips, from an owned temporary app work folder.
2. Native Unity 2019.4.40f1 / Car Creator 3.1.9 pilot regression (`rr2dv_work/gauge-pressure-validation/native-6`): export/reload, live and LOD resource references, repeated application, invalid resource/support rejection, actual CCL importer resource binding on both live and LOD assemblies and actual DV pressure indicator code all passed. Three pressure samples matched the printed dial.
3. The same native regression serializes/reloads both the S060-to-S282 vanilla HUD fallback and the reviewed custom numerical speed slot. Actual DV reader code preserved km/h magnitude at 0, +32, −32 and 140; it did not normalize or cap HUD readings to a physical dial range.
4. The normal converter built C-25 in `rr2dv_work/gp/20261002-024645-ls-280-c25-7c90c9`. Its build and exported-bundle audit passed. The final stricter HUD audit (`rr2dv_work/gauge-c25-final-audit`) also passed with zero errors/warnings. The builder reports 20 existing warnings and 23 automatic choices; those remain in its normal review report.
5. Candidate geometry inspection (`rr2dv_work/gauge-c25-inspection`) completed: four rear-facing instrument assemblies, valid needle references, pressuremeter rear pad 9/9 contacts. Candidate bundle hashes stayed unchanged. All 21 installed baseline bundle hashes also remained unchanged.

The runtime harness uses private readable donor mesh buffers and synthetic named materials to exercise CCL's binding methods. It seeds the resource caches and invokes DV reader/indicator code without initializing a whole game locomotive. It therefore does **not** prove actual material appearance, shader/glass behavior, live simulation attachment, HUD rendering, saved-state persistence or in-game acceptance. Diagnostic game buffers, projects, reports and converted packs stay in ignored local work folders.

Reproducible native test entry: `tests/test_gauge_pilot.py`, with `RR2DV_TEST_UNITY`, `RR2DV_TEST_CAR_CREATOR`, `RR2DV_TEST_DV_GAME` and `RR2DV_PRESSURE_MESHES` set to local tool/install/private buffer paths. The test creates its own temporary project under ignored `rr2dv_work`, matching the production work-folder approach. Its first Windows Temp run stalled during bundle generation and was stopped; the workspace rerun passed. `tools/cab-gauge-kit/run.py --dv-resources ...` supports resource-backed geometry inspections. Result/kit ZIPs explicitly exclude reconstructed geometry.

## Per-locomotive handover

All 21 receive the numerical HUD requirement when rebuilt. Physical statuses below concern the new replacement system. Two-source-gauge cabs now keep only boiler and pipe/cylinder instruments at their source mounts: C-25 retains its original pair; K-35's second boiler mount becomes brakes. Physical reservoir/chest/speed additions are omitted in those cabs, with speed and reservoir HUD readings retained invisibly. Larger cabs keep the existing physical instrument policy pending bespoke fitting. Main reservoir is not application pressure.

| Loco | Boiler replacement | Pipe + cylinder brake replacement | Physical speed replacement | Optional chest |
|---|---|---|---|---|
| A-23 | Awaiting bespoke fit | Awaiting bespoke fit | Awaiting bespoke fit | Deferred; no current physical dial |
| A-26 | Next supported pilot candidate | Awaiting bespoke fit | Awaiting bespoke fit | Retain existing; replacement deferred |
| B-65 | Awaiting bespoke fit | Awaiting bespoke fit | Awaiting bespoke fit | Retain existing; replacement deferred |
| C-25 | Implemented/exported; complete game acceptance pending | Existing instrument retained; replacement pending | HUD only under two-gauge rule | HUD only under two-gauge rule |
| C-40 | Supported candidate; awaiting fit | Awaiting bespoke fit | Awaiting bespoke fit | Deferred; no current physical dial |
| C-46 | Awaiting bespoke fit | Awaiting bespoke fit | Awaiting bespoke fit | Retain existing; replacement deferred |
| C-55 | Awaiting bespoke fit | Awaiting bespoke fit | Awaiting bespoke fit | Retain existing; replacement deferred |
| D-46 | Awaiting bespoke fit | Awaiting bespoke fit | Awaiting bespoke fit | Retain existing; replacement deferred |
| F-71 | Supported candidate; awaiting fit | Awaiting bespoke fit | Awaiting bespoke fit | Retain existing; replacement deferred |
| G-16 | Supported candidate; awaiting fit | Awaiting bespoke fit | Awaiting bespoke fit | Deferred; no current physical dial |
| G-25 | Awaiting bespoke fit | Awaiting bespoke fit | Existing slot candidate; fit pending | Retain existing; replacement deferred |
| K-28T | Awaiting bespoke fit | Awaiting bespoke fit | Existing slot candidate; fit pending | Retain existing; replacement deferred |
| K-35 | Awaiting bespoke fit | Second source boiler mount reused; game check pending | HUD only under two-gauge rule | HUD only under two-gauge rule |
| P-18 | Awaiting bespoke fit | Awaiting bespoke fit | Awaiting bespoke fit | Retain existing; replacement deferred |
| P-43 | Awaiting bespoke fit | Awaiting bespoke fit | Angled slot candidate; fit pending | Retain existing; replacement deferred |
| P-48 | Awaiting bespoke fit | Awaiting bespoke fit | Angled slot candidate; fit pending | Retain existing; replacement deferred |
| S-23 | Awaiting bespoke fit | Awaiting bespoke fit | Awaiting bespoke fit | Retain existing; replacement deferred |
| S-51 | Supported candidate; awaiting fit | Awaiting bespoke fit | Awaiting bespoke fit | Retain existing; replacement deferred |
| T-17 | Awaiting bespoke fit | Awaiting bespoke fit | Awaiting bespoke fit | Deferred; no current physical dial |
| T-21 | Awaiting bespoke fit | Awaiting bespoke fit | Awaiting bespoke fit | Retain existing; replacement deferred |
| T-22 | Supported candidate; awaiting fit | Awaiting bespoke fit | Awaiting bespoke fit | Retain existing; replacement deferred |

Brake assembly follows the accepted boiler pilot: separate pipe/cylinder needles and an isolated correctly marked face, with verified absolute pressure/angle calibration. Speed follows with deliberate dial range and damping; do not reuse S060's 60 km/h physical dial as a fleet default. Chest remains optional until the essential instruments and full control sweeps fit. Driver-facing angles require per-cab evidence.

## Ready for the next game check

The updated local candidate is `rr2dv_work/c25fix/20261002-102720-ls-280-c25-793f4a/build/out/C-25 Consolidation`. It includes the two-gauge rule, geometry-following dynamo jet and tender spindle correction, and was built/audited without installation. It supersedes the earlier four-gauge candidate in `rr2dv_work/gp`. Use the usual conversion/install flow when ready.

Check C-25 from the driver's position: whole housing and pad attachment, legible printed scale, glass/illumination, needle direction and indication at cold and working pressures, brake/reverser/full control sweeps, and visibility of both physical instruments. Confirm there are no extra floating faces. Open F4 and confirm numerical km/h forward/reverse and reservoir pressure; save/reload and confirm readings still work. Record failures before allowing fleet physical replacements. The separate coupling-induced tilt remains open; see the [C-25 game-test follow-up](c25-game-test-follow-up-2026-10-02.md).
