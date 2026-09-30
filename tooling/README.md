# Builder tooling

This directory contains the Unity builder scripts and configuration used by the application. `workspace.json` defines the workspace layout; local machine settings belong in an untracked `machine.local.json` created from `machine.local.example.json`.

Start with [`builder/README.md`](builder/README.md), [`builder/VEHICLE_RECORD.md`](builder/VEHICLE_RECORD.md), and the build scripts under `builder/tools/`. The pilot tools inspect source data and are not alternate build entry points.

The repository does not include game assets, exported packs, private logs, Unity caches, or machine-specific settings. Run the included checks from their source files when changing builder behavior. A passing automated check does not establish in-game acceptance.
