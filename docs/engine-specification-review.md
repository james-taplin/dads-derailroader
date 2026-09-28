# Engine specification review

Local 0.1.3 adds an Engine specifications tab to the existing pre-build review.
It preserves the successful default conversion and allows targeted corrections.

## Editable values

| Value | Unit | Build effect |
|---|---|---|
| Cylinder bore / piston stroke | in | Physical dimensions; legacy equivalent-bore fitting remains explicit |
| Working pressure | psi gauge | Safety-valve opening in absolute bar; closing pressure 3 psi lower |
| Total heating area | ft² | Existing injector, firebed and firing-rate approximations |
| Simulation boiler diameter / length | m | Boiler geometry and capacity; not outside cladding measurements |
| Boiler capacity multiplier | dimensionless | Simulation capacity adjustment |
| Coal consumption adjustment | dimensionless | Coal mass required to replenish the simulated firebed |
| Weight on driven wheels | lb | Reference for factor of adhesion; no mass/axle-loading override |
| Published tractive effort | lbf | Comparison only; does not silently retune the engine |

Numbers carry source/default/edited provenance and units. Restore returns each field
to the current source/basis suggestion, even after previous edited choices were
automatically restored. Optional notes record the source of better figures.
Original source specifications remain intact in the report. Older review profiles
gain the new defaults without losing existing brake, wheel or simulation choices.

The inherited boiler dimensions, capacity factor and water quantity are the pinned
CCL 3.1.9 S060/S282 defaults, confirmed against BoilerDefinitionProxy's default methods.
They are labelled simulation defaults, never prototype measurements. Capacity edits
preserve the original water-fill fraction. Accepting unchanged metrics does not
emit new simulation overrides.

## Estimates

Nominal TE uses the existing 0.85 pressure convention, extended explicitly to physical
cylinder count and selected fixed gearing:

`lbf = .85 × gauge psi × bore_in² × stroke_in / driving_diameter_in × cylinders/2 × ratio × efficiency`

Factor of adhesion is driven-wheel weight in pounds divided by this nominal TE in lbf.
Unknown driven-wheel weight stays unknown. Published TE and the legacy equivalent-bore
calibration target are shown separately. These are double-acting simple-expansion
estimates, not validated compound-engine performance or measured drawbar pull.

## Validation

Tests cover unchanged-default numerical parity, physical edits and units, boiler fill
scaling, gearing/adhesion calculations, non-finite/out-of-range values, old-review
migration, independent reference TE, provenance, and the actual Tk edit/restore flow.

A diagnostic C-70 export used bore 15 in, stroke 17 in, 190 psig, 1200 ft² heating area,
1.4 × 5 m boiler with .8 capacity factor, and 1.2 coal adjustment. The exported-bundle
audit checked the actual simulation fields and passed. A negative audit expecting three
cylinders in the two-cylinder export correctly failed. The fuel field lives on the
FireboxSimControllerProxy beside the firebox definition, so audit ownership mirrors the
builder's existing same-object field assignment.

Local evidence: `B:/LLW CONVERT/engine-metrics-diagnostic`. The diagnostic pack is not
installed. Gameplay calibration and accuracy of user-supplied figures remain unverified.
