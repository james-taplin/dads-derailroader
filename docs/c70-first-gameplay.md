# C-70 first gameplay follow-up — app 0.1.2 candidate

James reported a successful first drive: running gear, couplers, one oil cap per side,
info plates, dynamo and cylinder-cock jets worked. Cab controls were stiff and some
lacked a white outline. Doors, windows and hatches had no working interactions.
The supplied HUD screenshot shows the locomotive identity and header over an empty
instrument area. Acceleration was rapid, with rapid chuffs, reaching about 50–60 km/h.
Gearbox 1 was not tested because the key was not remembered.

## Changes

- Initialize the complete CCL steam HUD before applying the reviewed brake valve;
  explicitly enable the numerical speedometer and serialize CCL's runtime JSON.
  Audit the imported JSON, not just the editor fields.
- Give cab levers explicit same-prefab highlight renderers. Estimate their response
  mass from measured grip radius rather than carrying 5–30 kg donor settings into
  different handle geometry. Existing detents, limits, return springs and inputs
  remain intact. This is an experimental response target, not gameplay acceptance.
- Resolve ancillary controls from source ToggleAnimation declarations, exact target
  paths and complete clips. Preserve their source hierarchy and verify all bound
  transforms at five phases. Remove stationary visual/collision copies of moving
  parts. Put complete assemblies and highlight references in the same external prefab.
- Use a small physical grip and separate trigger-only interaction area. A simple
  linear hinge or slide can use a lever/puller. Eased or linked movement uses a
  native toggle button on the declared target and native smoothed simulation output;
  source clip length/speed sets its response time. This preserves motion without
  forcing a compound source mechanism into a single physical joint. Click interaction
  is the C-70 candidate's route; drag/scroll equivalence is not claimed.
- Fail builds on missing/ambiguous targets, unsupported curves, overlapping moving
  assemblies or mismatched source poses. Audit control count, saved control ports,
  transition nodes, complete highlight lists and same-prefab reference ownership.
- Explain the fixed reduction in the pre-build screen and report. Gearbox 1/2 do
  not change gears. Add wheel RPM, engine RPM and double-acting exhaust-event estimates
  at 10, 30, 50 and 60 km/h to support calibration.

The selected source declares nine ancillary groups: DoorL, DoorR, DE, DF, WFL, WFR,
WRR, WRL and WH. These represent four door groups, four window groups and the water
hatch. There is no separate roof-hatch clip in this source's animation map. Firebox
and cylinder-cock controls stay on their existing driving-control paths.

## Physics finding

The current reviewed reduction is 2:1, efficiency 0.9 and wheel radius 0.4572 m.
The game's fixed-transmission implementation multiplies engine torque by ratio and
efficiency, consistent with the app's graph; crank RPM is wheel RPM times ratio.
At 50–60 km/h this implies roughly 580–696 engine RPM and 39–46 exhaust events/sec
for two double-acting cylinders. It explains why rapid chuffs are possible under
these assumptions; it does not establish realistic acceleration or a speed limit.
No new speed cap, ratio or steam-flow tuning was invented from one drive report.

## Validation and remaining checks

The new audit rejects the installed first build for the two reported defects:
zero of nine ancillary controls and missing imported steam HUD/speedometer layout.
The new candidate passes the exported bundle audit with zero errors/warnings,
zero AudioClips, CCL.Types-only scripts and the existing two oil cups.
All nine moving assemblies pass source-pose checks. A real Unity synthetic regression
checks declared-target selection despite an earlier decoy binding, multipart poses,
a linear puller, saved highlight references and failure on a missing target.

Final fresh conversion: `20260928-004843-ls-04440-x30c-bdf7f3`, app 0.1.2. It completed
through bundle audit, deliberately declined installation and cleaned its temporary
workspace. Four existing coupler proximity warnings remain; their geometry was
not changed in response to the successful gameplay report. The installed first-build
bundle is unchanged (SHA-256 `3f3931ff929beea7692e4aaa663e7f3302f03084d0d0cdff1f8b052f6bd67177`).

The Python suite ran 204 tests successfully (seven opt-in skips). The new real Unity
regression ran separately and passed, including scaled target grips and eased motion.
The packaged executable's bundled-tooling/Tk self-test exited 0. An intermediate
test fixture exposed a missing `vehicleId` assumption in the audit; it now falls back
to the car ID and has regression coverage. The screenshot of that error came from
the test workspace, not the real C-70 conversion.

Next gameplay acceptance: populated HUD and numerical speed; cab highlight coverage,
control response/hold/return, fully closed regulator; all nine click interactions,
complete outlines and motion; fresh-spawn and save/reload state; measured acceleration,
cutoff/throttle settings, load/gradient and steam pressure. VR and actual persistence
remain unverified. No polling diagnostic helper is included.

The separate A-18 X52 branch remains outside this change. X53's same-prefab highlight
and full-source mapping findings informed this implementation; no M-2 coordinates
or model-specific selection branches were copied.
