# Workflow, branches and releases

Before editing, check the current branch and working tree. Keep each change focused and use a working branch when the change needs review. Update the README, affected wiki pages, and `docs/resolving-blocks.md` when user-visible behavior changes.

Run the focused checks for the change and record what they do not cover. A successful automated build or bundle audit does not establish in-game acceptance.

Prepare a release from a reviewed `main` commit. Confirm the version, packaged files, and release notes, then create the tag and publish the release when authorized by the repository owner.


Catalogue files are shipped unpacked with their Unity metadata. If release packaging reports "Nested archive cannot ship", expand the required contents and update the loader; do not bypass the check or drop the catalogue. Windows builds also unpack the Python standard library and run the packaged self-test. Rebuild into a fresh output directory to avoid carrying an old nested ZIP forward.


## Current source scope — 3 October 2026

The ten-locomotive restriction from commit `5cf87ecf18706989e451ddc780ea79ccdf6208fc` is promoted to main and the testing branch (`claude/unity-crash-message`). Source version remains `0.4.7+fixed.1`. Supported: A-23, A-26, C-25, D-46, F-71, G-25, K-35, P-18, T-17 and T-22. Reading 6-Chime is excluded. The complete stock tuning/catalogue reference is retained; its presence does not enable excluded conversions.

GitHub 0.4.7 is rebuilt from main on 4 October 2026 with ten supported locomotives (A-23, A-26, C-25, D-46, F-71, G-25, K-35, P-18, T-17, T-22), Reading 6-Chime excluded, and the Unity licence-startup correction. The tag and both attached release packages are replaced together. Redownload if you obtained the earlier unrestricted GitHub 0.4.7 packages. James confirms the existing Nexus 0.4.7 upload was already restricted, built from the earlier fixed branch; the Nexus upload is not changed by this GitHub rebuild. Historical all-fleet reports remain reference evidence, not conversion support.
