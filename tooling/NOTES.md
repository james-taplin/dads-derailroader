# Tooling notes

The builder scripts in this directory support the app's import, measurement, build, and audit stages. Their inputs and generated workspace locations are described by `workspace.json` and the relevant builder documentation.

`MANIFEST.sha256` covers the current checked-in tooling tree. Do not use paths from a developer's machine as canonical user setup instructions.

The repository omits source game assets, exported packs, audio, images, Unity caches, private logs, and machine-specific settings. Build tests from the included sources. A tooling snapshot or automated pass does not certify a pack's runtime behavior.
