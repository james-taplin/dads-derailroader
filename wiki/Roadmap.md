# Roadmap

This is a compact status map, not a release promise. The [feature roadmap](https://github.com/james-taplin/derailroader/blob/main/docs/feature-roadmap.md) and [current implementation notes](https://github.com/james-taplin/derailroader/blob/main/docs/review-and-geometry.md) carry the detailed design and evidence.

| Area | State | Next evidence needed |
| --- | --- | --- |
| Steam review, brakes, and spawning | Implemented as build candidates | Cab, HUD, keyboard, and spawn tests in game. |
| Conventional and fixed-geared steam | Implemented starting profiles | Per-engine pull, slip, consumption, and animation calibration. |
| Mechanical stoker | Pending builder-core change | Keep coal and model stoker steam use. |
| Oil firing for tender locomotives | Pending | Fuel storage and control mapping that survives build and game tests. |
| Compound/simple switching | Pending feasibility | Coupled steam-demand and torque behavior, including exact closure. |
| Articulated locomotives | Partial geometry and simulation support | Wheel, pivot, slip, and sustained-load validation. |
| Diesels | Pending separate adapters | Mechanical, hydraulic, then electric capability and representative tests. |
| Replacing source dependencies with vanilla DV parts | Parked | A new design decision and fit/rights review. |

A built or audited pack remains a candidate until [Testing a pack in Derail Valley](https://github.com/james-taplin/derailroader/wiki/Testing-a-pack-in-Derail-Valley) is complete. New adapters should preserve source facts, label approximations, and report unsupported behavior plainly.
