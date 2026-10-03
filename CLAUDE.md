# derailroader contributor notes

The current source contains the Windows app restricted to A-23, A-26, C-25, D-46, F-71, G-25, K-35, P-18, T-17 and T-22. Reading 6-Chime is excluded. Historical tuning records for the full stock fleet remain reference data, not conversion support. The app reads game files from the local installation, builds and audits a pack, then installs it after the user accepts the personal-use notice. Keep this scope accurate in user-facing documentation.

## Working practices

- Check the current branch and working tree before editing. Keep changes focused on the requested task.
- Do not commit game assets, converted packs, private logs, or machine-specific settings.
- Preserve source provenance and the personal-use notice. Never imply that this project grants permission to distribute game assets.
- Update `docs/resolving-blocks.md` and the relevant wiki page when a user-visible block, review item, or message changes.
- Keep the README and wiki aligned with the behavior currently implemented in `src/`.
- Run the focused checks requested for a change. For the full Python suite, use `PYTHONPATH=src:tests python -m unittest discover -s tests`.

## Repository map

- `src/rr2dv/`: Python app, command line, desktop interface, conversion pipeline, safety checks, and Unity editor scripts.
- `tests/`: automated checks using synthetic inputs and stand-in tools.
- `tooling/`: builder scripts and reference material used by the app.
- `tools/`: supporting utilities, including the control logger.
- `docs/`: maintained user guidance and engineering notes.
- `wiki/`: pages intended for the GitHub wiki.
- `README.md`: project overview, installation, and usage.

## Releases

Prepare releases from a reviewed `main` commit. Check the version in `src/rr2dv/__init__.py` and `pyproject.toml`, confirm the packaged files and release notes, and publish only when the repository owner requests it.
