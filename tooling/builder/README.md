# Builder

The Unity builder turns a validated vehicle record into a Custom Car Loader pack and audits the exported bundle. It is invoked by the application pipeline; use `tools/run_build.ps1` or the app's normal workflow rather than copying editor scripts by hand.

## Layout

- `tools/`: preparation, build, audit, and validation scripts.
- `tools/unity/`: Unity editor implementation.
- `overrides/`: reviewed geometry and configuration overrides.
- `tests/`: contract and workflow checks.
- `VEHICLE_RECORD.md`: record schema and validation rules.

The builder expects a dedicated generated Unity project and the configured game/tool installations. Keep source assets read-only. Run contract tests after changing record handling, then perform Unity and in-game checks appropriate to the change.
