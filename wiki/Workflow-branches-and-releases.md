# Workflow, branches and releases

Before editing, check the current branch and working tree. Keep each change focused and use a working branch when the change needs review. Update the README, affected wiki pages, and `docs/resolving-blocks.md` when user-visible behavior changes.

Run the focused checks for the change and record what they do not cover. A successful automated build or bundle audit does not establish in-game acceptance.

Prepare a release from a reviewed `main` commit. Confirm the version, packaged files, and release notes, then create the tag and publish the release when authorized by the repository owner.


Catalogue files are shipped unpacked with their Unity metadata. If release packaging reports "Nested archive cannot ship", expand the required contents and update the loader; do not bypass the check or drop the catalogue. Windows builds also unpack the Python standard library and run the packaged self-test. Rebuild into a fresh output directory to avoid carrying an old nested ZIP forward.


## Current source scope — 3 October 2026

The ten-locomotive restriction from commit `5cf87ecf18706989e451ddc780ea79ccdf6208fc` is promoted to main and the testing branch (`claude/unity-crash-message`). Source version remains `0.4.7+fixed.1`. Supported: A-23, A-26, C-25, D-46, F-71, G-25, K-35, P-18, T-17 and T-22. Reading 6-Chime is excluded. The complete stock tuning/catalogue reference is retained; its presence does not enable excluded conversions.

The published `v0.4.7` tag remains at `b5e7dfc`, before this restriction. Its existing downloads still represent the 21-locomotive edition. This integration does not rebuild or retag any release. Do not describe the restriction as shipped in v0.4.7. Earlier dated all-fleet reports below are historical evidence, not the current support list.
