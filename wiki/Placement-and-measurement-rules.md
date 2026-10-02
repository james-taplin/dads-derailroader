# Placement and measurement rules

The app measures each source model and applies general rules. A prior locomotive is regression evidence, not a set of offsets to copy. The [visible-surface guide](https://github.com/james-taplin/dads-derailroader/blob/main/docs/visible-surface-placement.md) and [block guide](https://github.com/james-taplin/dads-derailroader/blob/main/docs/resolving-blocks.md) hold the detailed rules and failures.

| Feature | General rule | Example that exposed it |
| --- | --- | --- |
| Backhead controls | Seat generated controls and labels on visible source meshes, not hidden collision shapes. | Camelback backhead. |
| Brake release (BR-01) | Place the stock fitting upright, red handle outward, hanger up into the mount. | External fitting regression. |
| Oil cups | A supported travelling left/right pair per driven axle; additional main-rod/crosshead bearing pairs where clear. Six to twelve total. Measured per-loco parents/local anchors, with 64-phase upright clearance and 12 cm spacing; reject missing support or quota failures. | Fleet of 21 steam locos; C-40 rear-right bearing needs the finer seat search. |
| Number plates | Seat against the visible body at the source road-number height and length; report unsupported seating. | A-18 cab and curved tank sides. |
| Lamps and glass | Match visible source surfaces and record missing lenses or materials for review. | Exported material warnings. |
| Doors and windows | Treat a part as moving only when source animation or component evidence supports movement. | Source models with static panels. |
| Coal load | Use source dimensions and record the simulation approximation. | Tender and tank capacity reviews. |
| End beams and couplers | Measure a qualifying exterior beam; permit a central drawgear opening and reject truck crossmembers behind it. | C-70 end-beam survey. |

A reviewed end-beam geometry correction must match the exact source fingerprint and include measurement evidence. Oil-fitting compatibility instead requires the measured seats to pass axle, parent, bearing, motion and full-turn clearance checks on the current built model, with source-byte differences reported. Published 0.4.5 stops before these tests if any reference hash differs; the development correction removes that premature stop. Accepting proposed end-beam geometry cannot fix the 0.4.5 oil hash error. The builder still applies its placement guards. `build_report.txt` records measured seats and warnings; final reach, moving clearance, appearance, and wheel contact require [Testing a pack in Derail Valley](https://github.com/james-taplin/dads-derailroader/wiki/Testing-a-pack-in-Derail-Valley).
