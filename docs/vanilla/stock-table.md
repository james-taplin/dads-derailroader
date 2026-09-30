# The stock-locomotive table (`src/rr2dv/stock_locos.json`)

James, 2026-09-30: every locomotive must have every fact the conversion needs written down, so nothing is inferred at conversion time
and there is as little room for bugs as possible. The table has one entry per stock steam locomotive (21) and is checked by
`stock.validate_table()` (a test fails if any entry lacks a field, a basis, a hash or an evidence line).

| Field | What it holds | Used by |
|---|---|---|
| `displayName`, `whyte`, `tank`, `tender` | name, wheel arrangement, whether it is a tank engine, the tender's id, truck pack and length (definitions) | documentation, checks |
| `source` | bore, stroke, pressure, heating surface, weights, brake valve (definitions) | documentation |
| `driver` | main driver clip, axles, radius (definition diameter / 2), basis, evidence, flange tip above tread (measured) | review prefill |
| `answers` | 2 cylinders, hand-fired, dynamo yes, physics, brake, spawn mode, each with its basis (James) | review prefill |
| `whistle` | the definition's whistle id (may be empty), the whistle built (`wh-3-std` when empty), its mesh | whistle option |
| `gauges` | styles in the model, styles generated (`Quadruplex` is built as the DV main-reservoir/equalizing gauge) | gauge rule (`buildrecord._ensure_gauges`) |
| `cab` | backhead z, floor from the collision hull (candidate), other levels | evidence only, not read by the build |
| `endBeam` | a measured sampling band (with evidence and who accepted it) per tender that needs one, else a note | pipeline (applied only when the installed files match) |
| `lodMeshes`, `knownOddities` | uses LOD0-3 meshes; zero/extreme scales, names with spaces | LOD scope, per-loco notes |
| `hide` | meshes left out of this loco's pack, each with a reason (K-35's three bell-cord planes, which ran out to infinity in game); `Rr2dvBuild` removes their renderers from the source prefab and stops the build if one is not found | build input (`hide`) |
| `conversion` | `untested` or `converted`, audit result, what the build reported | history |
| `sourceSha256` | hashes of the pack's `Bundle`, `Catalog.json`, `Definitions.json` for Railroader build 20238526 | unknown-build report, band guard |

**What the pipeline does with it.** After the inventory it compares the installed pack's hashes with the table. A match is logged
("vanilla table: matches ... build 20238526") and lets a stored end-beam band be applied exactly like a reviewed-geometry file
(same validation, same fingerprint check; a file the user passes wins). A difference is logged as "unknown game build" and never
refuses the conversion; table values are then used only where the definition agrees. The review dialog is prefilled from the table
(`reviewchoices._stock_answers`); a definition that disagrees with the table's radius wins and says so.

**Regenerating.** `python tools/vanilla/make_table.py --railroader <folder> --hashes game-hashes.json --bulk <unzipped vf_bulk.zip>`.
Observations (`OBSERVED`) and accepted bands (`END_BEAM`) are written in that script; edit them there and regenerate.
