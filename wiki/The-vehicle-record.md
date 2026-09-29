# The vehicle record

The B03 vehicle record is the contract between the Python app and the Unity builder. The app drafts it from source definitions and probe evidence, applies reviewed choices, then completes it for the build. Read the [schema and loader guide](https://github.com/james-taplin/derailroader/blob/main/tooling/builder/VEHICLE_RECORD.md) for the authoritative field list.

```json
{
  "schemaVersion": 1,
  "vehicleId": "example-steam-loco",
  "config": {
    "WeightEmptyKg": {
      "value": 12345,
      "unit": "kg",
      "basis": "derived",
      "evidence": ["mass-ledger.json#dry-mass"]
    }
  },
  "hooks": {},
  "metadata": {}
}
```

This illustrates an envelope, not a buildable record. Each numeric builder value needs a `value`, `unit`, `basis`, and `evidence`. A source fact, measurement, derivation, user choice, and analogue estimate have different bases. The loader checks shape and evidence presence; it cannot confirm that a measurement is physically correct.

`config` uses exact builder field names. `hooks` declares supported behavior such as simulation settings, collision boxes, oil points, brake release, lamps, and lever physics. `metadata` holds provenance, source specifications, review decisions, simulation assumptions, validation, limitations, and `pending` items; it is descriptive, not executed by the builder. A coupled tender has its own top-level record section.

The draft is in `record/vehicle-record.json`; the completed build record and automatic choices are in the build report. Unknown or ambiguous values stay pending or block the build. Review changes are tied to the source fingerprint and adapter version. See [The pre-build review](https://github.com/james-taplin/derailroader/wiki/The-pre-build-review) and [Simulation mapping](https://github.com/james-taplin/derailroader/wiki/Simulation-mapping).
