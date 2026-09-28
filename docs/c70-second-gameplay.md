# C-70 second gameplay follow-up — local 0.1.3 candidate

James confirmed the 0.1.2 C-70 ran well and the main HUD worked. Remaining reports:
white left cab window frame, missing grab highlights, sliding/notching trouble
(especially cutoff/windows), floating info plate, and absent HUD lighting controls.
The 22.5-second recording was inspected through sampled frames. It shows window
movement and cab interaction, but does not independently prove input or detent values.

## Evidence and changes

- The installed baseline identifies 0.1.2, run
  `20260928-010754-ls-04440-x30c-3cc654`, bundle SHA-256
  `02b05b5a07152e4c8e0fe6bb49c212eb27cb6fac64b5d15b477f512c2ea44315`.
- Left moving window used a non-Railroader `Windows` material, pale grey and
  untextured. The other three used `Windows_0` with the source livery tint.
  The converter applied colourizers only in its Railroader shader branch.
  App finishing now applies declared source colourizers across shader types and
  retains available base textures and UV transforms. It does not invent a texture
  or copy the opposite window material.
- The cutoff grab box was selected on distant linkage, at approximately
  `(0.7, 1.7, 0.7)` in car coordinates. Source RadialControl collider centres now
  place all five driving grips; cutoff becomes `(1.042, 2.743, -1.773)`.
  Explicit renderer highlight bindings remain. The experimental mass-only
  reduction and drag removal are withdrawn; role spring/mass/damping stay together.
  Scroll increments now equal one detent of the measured lever sweep.
- Monotonic single-axis source clips are reparameterized by displacement, preserving
  the complete hierarchy and linked poses. Source easing no longer forces a click
  button. C-70 exports four stepped window pullers, four door levers, and one
  click-operated water hatch. Genuinely compound motion retains the previous native
  click/smoothing route. No runtime helper is shipped.
- Plate seating formerly checked only the anchor point. It now measures the template
  plate footprint and checks a grid across the whole footprint against the same
  visible surface. It searches nearest to the source label and blocks if no supported
  seat exists. C-70 plates move from z=-8.179 to z=-7.225, x=+/-1.447: the full
  0.320 by 1.300 m plate fits the tank side. No locomotive-specific coordinates
  are used by the algorithm.
- Steam HUD lighting slots now follow actual front/rear headlight and cab-light
  reader references. Runtime JSON is refreshed and the exported bundle audit
  checks slot visibility against those references.

## Validation and limits

Unity 2019.4 compiled and exported a C-70 diagnostic candidate. Bundle audit passed
with zero errors/warnings, CCL.Types scripts only and no audio clips. Four existing
coupler-proximity build warnings remain. Candidate folder:
`B:/LLW CONVERT/c70-second-diagnostic/C-70 Climax`.

Real Unity regressions cover declared targets, multipart clips, saved highlights,
eased direct pullers, compound fallback, grip scale, missing targets, plate edges,
hidden collision meshes, and non-Railroader material tint/texture preservation.
The Python suite passed 214 tests with seven opt-in/environment skips. The portable
Windows app passed its bundled-tooling/Tk startup self-test.

The local 0.1.3 app also includes automatic vehicle-choice suggestions and restoration
from matching previous reports. Gameplay reach, outline appearance, detent feel,
HUD lighting operation, VR and save/reload remain acceptance checks. The diagnostic
pack has not replaced the installed C-70 and 0.1.3 has not been published to GitHub.
