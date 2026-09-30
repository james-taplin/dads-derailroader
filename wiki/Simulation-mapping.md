# Simulation mapping

The vehicle record keeps **source specifications** separate from **Derail Valley simulation choices**. A source bore or cylinder count is not silently rewritten to make a convenient CCL value. Derived values keep their basis and evidence. See the [engine specification guide](https://github.com/james-taplin/dads-derailroader/blob/main/docs/engine-specification-review.md) and [current adapter limits](https://github.com/james-taplin/dads-derailroader/blob/main/docs/review-and-geometry.md).

| Source or choice | Current mapping | Limit |
| --- | --- | --- |
| Bore, stroke, pressure, wheel radius | Estimate nominal tractive effort using the stated simple-expansion convention. | An estimate, not measured drawbar pull. |
| Physical 3- or 4-cylinder engine | Keep the physical count in metadata; simulate two cylinders with adjusted bore for equal swept volume. | Sound compatibility workaround; gameplay calibration pending. |
| Heating area and boiler data | Choose S060 or S282 built-in audio and inherited boiler/firebox starting values. | Boiler defaults are simulation values, not prototype measurements. |
| Fixed geared steam | Apply reviewed ratio and efficiency to engine RPM and wheel torque. | Shaft animation, slip, and performance under load need game tests. |
| Oil firing | Map a tank locomotive's fuel oil and firing controls through available CCL slots. | Tender oil firing and mixed regimes remain pending. |

The **Engine specifications** review shows units and provenance. Published tractive effort is a comparison figure. Weight on driven wheels informs factor of adhesion; total locomotive weight is not substituted. The coal-consumption adjustment changes simulated firebed replenishment, not a measured historical burn rate.

Current profiles are starting points. Record actual starting pull, sustained pull at several speeds, adhesion, boiler recovery, water use, and fuel use before claiming calibration. See the [Roadmap](https://github.com/james-taplin/dads-derailroader/wiki/Roadmap) for the current validation status.
