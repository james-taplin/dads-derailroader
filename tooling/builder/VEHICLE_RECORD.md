# Vehicle record schema 1

The record loader reads the file named by `CCL_VEHICLE_RECORD`, creates the
existing `LocoConfig`, resolves source component parent transforms, and calls
`CclLocoBuild.Run`. If `CCL_CATALOG_RECORD` is set, the existing catalogue bridge
also checks the source identifier and source wheel radii.

The loader is editor-only: copy the record-loader source into the project's
`Assets/Editor` through the shared builder sync. No package is required. The
strict JSON parser preserves missing/null distinctions, dictionaries and tuple
arrays that Unity JsonUtility alone cannot represent.

## Structure

```json
{
  "schemaVersion": 1,
  "vehicleId": "ls-060-s16",
  "config": {
    "CarId": "RR2DV_SAMPLE",
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

This is a shape example, not a complete buildable record. Required identity,
source, physics and collision/simulation settings must also be present.

`config` uses the exact public fields of `LocoConfig` and its data classes.
Unknown fields reject the record; delegate fields cannot be assigned as data.
`metadata` is descriptive provenance/acceptance data and is not executed or
applied to the car. The loader validates evidence **presence**, not whether a
measurement or historical interpretation is correct. Review and downstream
source/build gates remain required.

Every submitted numeric setting in `config` or `hooks` needs an ancestor
envelope with `value`, nonempty `unit`, `basis`, and nonempty `evidence` string
or string array. Basis is one of `source`, `measured`, `derived`,
`analogue_estimate`, or `DV_choice`. Optional `notes` is permitted. An envelope
may contain a vector or collection sharing one evidence basis; mixed-unit
collections must identify their constituent units explicitly. A plain object
whose only key is `value` is a normal dictionary, not an envelope; this matters
for simulation components such as `poweredAxles.value`.

Unknown numbers remain null. Null cannot populate a nonnullable numeric field;
nullable fields such as `CabZ` retain null. Missing mandatory data rejects the
record. Optional omitted LocoConfig fields retain the existing shared builder
defaults; these are code defaults, not new historical claims. Explicitly record
vehicle-specific physics and geometry rather than relying on these defaults.

## Value mapping

- Strings and booleans are ordinary JSON values.
- Vector2/Vector3 use `[x,y]` / `[x,y,z]` or objects with those keys.
- Quaternion uses `[x,y,z,w]`; Color uses `[r,g,b,a]`.
- Dictionaries use JSON objects and preserve case-sensitive keys.
- Arrays and lists use JSON arrays.
- Value tuples use positional arrays, or objects with `Item1`, `Item2`, etc.
  A livery is `[name, [[colorId,hex],...]]`; a wheelset is
  `[offset,length,diameter,axles,clip]`.
- Nested `config` data uses exact fields such as `Bogies`, `RrLevers`,
  `OilAnchors`, `LampLenses`, and `ExteriorShots`.
- SimSpec integer tokens become int, decimal/exponent tokens become float, so
  the core's serialized-property setter receives types it supports.

Units describe already-converted values; the loader does not convert pounds,
inches or gallons automatically. Supply the units expected by LocoConfig/the
named DV field and retain the conversion arithmetic in evidence.

Components with nonempty `parentPath` are source-parent-local. Before building,
`PrepareSources` reads that exact Transform from `SrcPrefab`, bakes position and
rotation into car space, combines scale, and clears the parent path. A missing
parent is an error. Components already measured in car space use an empty path.

## Declarative hooks

All numeric hook payloads follow the same provenance rule.

| Hook | Value |
|---|---|
| `SimSpec` | `{componentId: {field: value}}`; `_notes` retains explanatory strings |
| `CollisionBoxes` | `[[name, centreVector, sizeVector], ...]` |
| `OilPoints` | `[[tag, positionVector], ...]`, in stable simulation index order |
| `BrakeRelease` | `{pos: vector, euler: vector}` |
| `HandbrakeWheel` | `{pos: vector, euler: vector}` |
| `CoalPile` | `{centre: vector, size: vector}` |
| `LampKey` | `{rendererNameOrFullTransformPath: lampKey}`; `{}` enables explicit configured lenses |
| `LeverPhysics` | List of physics entries selecting exactly one `RrLevers.Path` each |

Lever physics fields are `path`, `min`, `notches`, `spring`, `damper`, `mass`,
`drag`, `angularDrag`, `scroll`, and `scrollSpring`. Optional
`scrollAngleFraction` replaces `scroll` with the measured animation sweep times
the fraction. Maximum angle is always the core's measured animation sweep.
The hook calls the existing `CclLocoBuild.Phys`; no C# expressions or arbitrary
method names can be executed from the record.

When explicit lamps are configured, include `"LampKey": {}` to activate the
core's lighting build. Use `OilAnchors` or `RodOilers` in config for the existing
source-validated strategies. Record order is preserved.

Additional delegate behaviors (`BodyExtras`, per-placed-control `Phys`, and
arbitrary lamp predicates) are intentionally not inferred. Any new declarative
behavior requires review and validation before use.

A coupled tender is a top-level `tender` object containing its own `config`,
`hooks`, optional `metadata`, and `config.IsTender=true`. Do not put a nested
`Tender` directly inside config.

## Validation and execution

The loader requires identity/source/material/livery/wheelset data, positive dry
mass and wheel radius, explicit nonnegative water/coal capacities, a measured
running-gear layout, collision boxes, and a simulation hook for a locomotive.
Generation `Work` must name a dedicated `Assets/<conversion>/<car>` subtree.
It rejects duplicate JSON keys, unknown fields, nonfinite values, malformed
numbers, fractional integers, and missing provenance.

The share-build setting clears custom sound references so built-in DV audio remains available. The serialized-bundle audit must still confirm zero embedded AudioClips.

`ValidateRecord` is an optional Unity executeMethod that loads
the record, checks its source prefab, resolves its source component parents,
writes `record_validation.json` beneath `CCL_BUILD_OUT`, and exits. It does not
build/export a car or prove runtime behavior.

The standalone `test_record_loader.ps1` compiles the actual loader and canonical
LocoConfig against Unity 2019.4.40f1 assemblies, then runs 17 contract cases. Pass
`-Record <path>` to validate a real record as an additional case. Its harness has
a **stub CclLocoBuild** and must never be copied into Assets/Editor. These tests
exercise parsing/conversion and failure semantics; actual prefab resolution,
export, bundle audits, rendered appearance, and in-game checks are separate.

Contract tests exercise parsing and failure semantics. Unity editor build and runtime acceptance are separate checks.
