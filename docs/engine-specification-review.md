# Engine specification review

The pre-build review lets users inspect and adjust the source and simulation values used to build a locomotive. It preserves source facts and records the basis and units for each value.

## Editable values

| Value | Unit | Build effect |
|---|---|---|
| Cylinder bore / piston stroke | in | Physical dimensions; equivalent-bore fitting remains explicit |
| Working pressure | psi gauge | Safety-valve opening in absolute bar; closing pressure 3 psi lower |
| Total heating area | ft² | Existing injector, firebed and firing-rate approximations |
| Simulation boiler diameter / length | m | Boiler geometry and capacity; not outside cladding measurements |
| Boiler capacity multiplier | dimensionless | Simulation capacity adjustment |
| Coal consumption adjustment | dimensionless | Coal mass required to replenish the simulated firebed |
| Weight on driven wheels | lb | Reference for factor of adhesion; no mass/axle-loading override |
| Published tractive effort | lbf | Comparison only; does not silently retune the engine |

Values show their source, units, and whether they were edited. Restore returns a field to its suggested value. Optional notes record the basis for corrected figures. Original source specifications remain intact in the report.

Inherited boiler dimensions, capacity, and water quantity are simulation defaults from the configured Custom Car Loader profile, not prototype measurements. Capacity edits preserve the original water-fill fraction.

## Estimates

Nominal tractive effort uses the existing pressure convention, extended to physical cylinder count and selected fixed gearing:

`lbf = .85 × gauge psi × bore_in² × stroke_in / driving_diameter_in × cylinders/2 × ratio × efficiency`

Factor of adhesion is driven-wheel weight in pounds divided by nominal tractive effort in lbf. Unknown driven-wheel weight stays unknown. Published tractive effort and any equivalent-bore calibration target are shown separately. These are estimates, not validated compound-engine performance or measured drawbar pull.

## Validation

Automated checks cover unchanged-default numerical parity, physical edits and units, boiler fill scaling, gearing and adhesion calculations, invalid values, review migration, provenance, and the edit/restore flow.

Gameplay calibration and the accuracy of user-supplied figures require in-game testing.
