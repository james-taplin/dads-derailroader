# C-70 gameplay follow-up

This note records a gameplay follow-up for the C-70 candidate. Reported issues included a pale left cab-window frame, missing grab highlights, sliding or notching behavior, a floating information plate, and absent HUD lighting controls. Sampled video frames showed window movement and cab interaction, but did not establish input or detent values.

## Changes made

- The left moving window used a non-Railroader `Windows` material while the other windows used `Windows_0`. Colorizers now apply across shader types, retaining available base textures and UV transforms without inventing textures or copying another window's material.
- Driving grip placement now uses source control collider centers. Explicit renderer highlight bindings remain, and scroll increments match one detent of the measured lever sweep.
- Monotonic single-axis source clips are reparameterized by displacement while preserving the complete hierarchy and linked poses. Compound motion retains the previous click and smoothing route.
- Plate seating checks the full template footprint against the visible surface and blocks when no supported seat exists.
- Steam HUD lighting slots follow the actual headlight and cab-light reader references, and the exported-bundle audit checks slot visibility against those references.

## Validation and remaining checks

A Unity diagnostic export compiled and passed the bundle audit with no errors or warnings, CCL.Types scripts only, and no audio clips. Four coupler-proximity build warnings remain. Automated regressions cover declared targets, multipart clips, saved highlights, pullers, grip scale, missing targets, plate edges, hidden collision meshes, and material tint/texture preservation.

Gameplay reach, outline appearance, detent feel, HUD lighting operation, VR, and save/reload still require in-game acceptance.
