# Bulk measurement findings (Codex run, 2026-09-30, 21 steam packs, VfMeasure M1-M13)

Source: `vf_bulk.zip` (20 OK, 1 OK-with-problems: K-35's `Pilot ` clip, trailing space). Numbers per loco: `bulk-measured.json`.

## Wheel radius
Definition nominal = tread on all 21. Highest point of each driving wheel that touches the rail is 19-40 mm above nominal
(flange), and about 0 on blind (flangeless) drivers (D-46, C-25, T-17, P-18). The probe's wrong candidates on S-51, C-46, B-65,
T-22, P-43 came from merging every rotating node into one band list and are not needed: use nominal, with this as the evidence.
(The filter counted only rail-touching wheels, so per-loco wheel counts are incomplete; the 19-40 mm result is consistent.)

## Cab floor (partly solved)
Rays found a consistent floor level for 11 locos (`cabFloorCandidatesM`, 0.1 m resolution, in the 1.3 m ahead of the backhead toward the cab end); ten
(S-23, G-16, G-25, C-55, A-23, A-26, T-22, P-43, P-48, C-40) gave none. Every loco has a `collision` MeshCollider, but the downward rays found no floor
in it. Seats in the definitions are unusable (y 2.15-2.9; C-40's are all zero). M14 (added after this run) reads the real
triangles: flat-surface areas per 2 cm height for each MeshCollider (`hulls`) and for all visible meshes (`visibleLevels`). It needs one more run.

## Oddities to handle per loco
Zero scale: C-25, B-65, T-21, G-25, P-18 (rods, links, valve gear, coal bones). Extreme scale: S-51 and F-71 cab meshes, D-46 collision, P-43 whistle,
T-22 doors. Name with trailing space: K-35 `Pilot ` and a brake hanger, B-65 `Dad `, P-18 `Trailing `, P-43 `Reverser `. P-48: 42 (its shared truck pack).
