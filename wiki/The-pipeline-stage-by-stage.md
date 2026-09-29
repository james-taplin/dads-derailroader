# The pipeline, stage by stage

Every conversion starts from installed source files and a fresh run identity. The app stops at the first unresolved block and records the reason. See [When a conversion stops](https://github.com/james-taplin/derailroader/wiki/When-a-conversion-stops) for user actions.

| Stage | Input and result | Typical stop |
| --- | --- | --- |
| `locate` | Find the selected steam locomotive in the Railroader mod. | No steam locomotive or ambiguous selection. |
| `link` | Resolve tender, trucks, parts, images, and source provenance. | Missing or duplicate dependency. |
| `stage` | Copy only needed inputs into a guarded run workspace and verify hashes. | Source changed during copying. |
| `extract` | Use AssetRipper to export bundles. | Tool startup or incomplete export. |
| `import` | Assemble a Unity project with restored animation paths, dependencies, Car Creator, and builder scripts. | Ambiguous clip ownership or invalid assets. |
| `probe` | Measure hierarchy, anchors, animation, and wheel-tread candidates in Unity. | Compilation, licence, timeout, or geometry failure. |
| `record` | Draft a B03 vehicle record with units, basis, evidence, and pending items. | Required source specification missing. |
| Review | Confirm brake, spawn, wheel, firing, and simulation choices. | Cancelled, stale, or unsupported choice. |
| `build` | Complete the record, prepare the model, and export a CCL pack. | Geometry, placement, material, control, or simulation block. |
| `audit` | Reload the exported bundle in Unity and check scripts, audio, HUD feeders, mass, wheel radius, and other invariants. | Bundle differs from the record or fails an invariant. |
| `publish` | Show the notice, then install into Derail Valley `Mods`. | Notice declined or unrelated folder collision. |

`run.log` is the readable timeline. The compact report retains `run.json`, review answers, the vehicle record, `build_report.txt` and audit results where produced. `rebuild.json` records source, code, tool, and answer fingerprints plus expected output hashes. It identifies a recipe; byte-identical Unity bundles are not verified.

The imported and probed project can be reused after a failed build, keyed to inputs that shape the probe. Successful cleanup removes temporary conversion data. A pack that passes `audit` is still a candidate until [Testing a pack in Derail Valley](https://github.com/james-taplin/derailroader/wiki/Testing-a-pack-in-Derail-Valley).
