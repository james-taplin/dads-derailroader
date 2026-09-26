# E04: verified pre-existing boiler mass discrepancy

WaterSpecificVolume(p) = 1.04 + p*(0.00943 - 0.000129*p); spawn water mass = spawnWaterLevel / v(p)

Evidence: installed DV.Simulation.dll, private decompilation of SteamTables/BoilerDefinition, and serialized BoilerDefinitionProxy from the preserved unified bundles. Both proxies set spawnPressure to 1 bar. The local Boiler constructor confirms division by specific volume.

- g29: 6080.000 L becomes 5794.334 kg at spawn; subtracting litres as kilograms makes the ledger 285.666 kg light, before separate firebox/other contents.
- c21: 5632.777 L becomes 5368.123 kg at spawn; subtracting litres as kilograms makes the ledger 264.654 kg light, before separate firebox/other contents.

Disposition: confirmed pre-existing issue. Migration preserves profile physics to keep parity comparisons meaningful. A correction must be a separate profile change with its own audit expectations and game acceptance; no approximate 250 kg adjustment has been applied.
