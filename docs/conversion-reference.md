# Conversion reference

This page documents the basis for default values written to a vehicle record. A default is a starting point for review, not an accepted calibration. Keep source facts, derived values, measurements, and user choices distinct.

## U02 — Simulation choices

The draft record uses explicit Derail Valley simulation choices for cutoff limits, feedwater temperature, water-consumption multiplier, blowdown, coal-dump rate, and exhaust behavior. Review these against the target locomotive and record any changes in the vehicle record.

## E02 / E03 — Tractive effort and equivalent bore

When the source does not publish tractive effort, the estimate uses the documented pressure convention and the source cylinder dimensions and driving-wheel diameter. Equivalent bore is calculated only for a clearly identified comparison target. Keep the original bore, stroke, cylinder count, and published figure unchanged in source provenance.

## E05 — Mass and load basis

Record whether a source weight is empty, working order, or otherwise defined. Convert units explicitly and list the water, coal, sand, and oil included or excluded. Do not use an ambiguous source weight as a measured value.

## E06 — Boiler and firebox starting values

Boiler, injector, firebed, and firing-rate values without source evidence are labelled estimates or simulation defaults. The current draft uses an explicit heating-area basis for the estimates; it does not claim measured performance. Replace estimates only with reviewed source evidence or recorded in-game measurements.

## DV integration choice — Spawn pressure

The starting spawn-pressure value is a Derail Valley integration choice. It is not a Railroader prototype specification and remains reviewable.
