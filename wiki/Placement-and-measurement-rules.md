# Placement and measurement rules

The app measures each source model and applies general rules. A prior locomotive is regression evidence, not a set of offsets to copy. The [visible-surface guide](https://github.com/james-taplin/derailroader/blob/main/docs/visible-surface-placement.md) and [block guide](https://github.com/james-taplin/derailroader/blob/main/docs/resolving-blocks.md) hold the detailed rules and failures.

| Feature | General rule | Example that exposed it |
| --- | --- | --- |
| Backhead controls | Seat generated controls and labels on visible source meshes, not hidden collision shapes. | Camelback backhead. |
| Brake release (BR-01) | Place the stock fitting upright, red handle outward, hanger up into the mount. | External fitting regression. |
| Oil cups | Prefer modelled big-end nubs on moving rods; use accessible running-board seats when needed. Omit a pair if neither seat is valid. | A-18 and C-70. |
| Number plates | Seat against the visible body at the source road-number height and length; report unsupported seating. | A-18 cab and curved tank sides. |
| Lamps and glass | Match visible source surfaces and record missing lenses or materials for review. | Exported material warnings. |
| Doors and windows | Treat a part as moving only when source animation or component evidence supports movement. | Source models with static panels. |
| Coal load | Use source dimensions and record the simulation approximation. | Tender and tank capacity reviews. |
| End beams and couplers | Measure a qualifying exterior beam; permit a central drawgear opening and reject truck crossmembers behind it. | C-70 end-beam survey. |

A reviewed geometry correction must match the exact source fingerprint and include measurement evidence. The builder still applies its placement guards. `build_report.txt` records measured seats and warnings; final reach, moving clearance, appearance, and wheel contact require [Testing a pack in Derail Valley](https://github.com/james-taplin/derailroader/wiki/Testing-a-pack-in-Derail-Valley).
