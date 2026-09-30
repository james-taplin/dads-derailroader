# Unity project context

The app assembles a temporary Unity project from the configured project manifest and checked-in builder scripts. The supported Unity editor version and package dependencies are defined in the project files and validation scripts; keep those records in sync when the project setup changes.

`workspace.json` is the source of truth for workspace paths. The manifest identifies included tooling files, while generated `Assets/Editor` copies are created by the preparation scripts. Do not commit generated Unity caches or machine-specific paths.

Run the builder workflow tests after changing project preparation. Unity serialization, bundle audit, appearance, and in-game behavior require their own checks; a successful project setup alone does not establish acceptance.
