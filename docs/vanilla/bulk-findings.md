# Bulk measurement findings (Codex run, 2026-09-30, 21 steam packs, VfMeasure M1-M13)

Source: `vf_bulk.zip` (20 OK, 1 OK-with-problems: K-35's `Pilot ` clip, trailing space). Numbers per loco: `bulk-measured.json`.

## Wheel radius
Definition nominal = tread on all 21. Highest point of each driving wheel that touches the rail is 19-40 mm above nominal
(flange), and about 0 on blind (flangeless) drivers (D-46, C-25, T-17, P-18). The probe's wrong candidates on S-51, C-46, B-65,
T-22, P-43 came from merging every rotating node into one band list and are not needed: use nominal, with this as the evidence.
(The filter counted only rail-touching wheels, so per-loco wheel counts are incomplete; the 19-40 mm result is consistent.)

## Cab floor (from the second run, M14)
Every loco's `collision` MeshCollider (the walkable hull; Unity reports `isReadable` false but the editor reads it) has a large upward-facing flat
level over the cab zone, which the rays missed. `bulk-measured.json` has it per loco (`cabFloorFromCollisionHullM`: best level, its area, whether it
is confined to the cab, and any other levels). K-28T gives 1.66 m, which matches its visible `Floor.002` top (1.66). Where the best level spans the
whole body (a running board or catwalk at the same height, e.g. D-46, T-17, T-21) or a second level sits close (C-25 1.28/1.7, A-26 1.72/2.0, S-51,
P-48...) the value is a candidate, not a decision. Nothing in the build reads the floor yet (the cab position comes from the crew seat), so these are
evidence for the cab/bulb/teleport height checks and for James's in-game review, not build inputs.

## Oddities to handle per loco
Zero scale: C-25, B-65, T-21, G-25, P-18 (rods, links, valve gear, coal bones). Extreme scale: S-51 and F-71 cab meshes, D-46 collision, P-43 whistle,
T-22 doors. Name with trailing space: K-35 `Pilot ` and a brake hanger, B-65 `Dad `, P-18 `Trailing `, P-43 `Reverser `. P-48: 42 (its shared truck pack).
