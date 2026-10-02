# Workflow, branches and releases

Before editing, check the current branch and working tree. Keep each change focused and use a working branch when the change needs review. Update the README, affected wiki pages, and `docs/resolving-blocks.md` when user-visible behavior changes.

Run the focused checks for the change and record what they do not cover. A successful automated build or bundle audit does not establish in-game acceptance.

Prepare a release from a reviewed `main` commit. Confirm the version, packaged files, and release notes, then create the tag and publish the release when authorized by the repository owner.


Catalogue files are shipped unpacked with their Unity metadata. If release packaging reports "Nested archive cannot ship", expand the required contents and update the loader; do not bypass the check or drop the catalogue. Windows builds also unpack the Python standard library and run the packaged self-test. Rebuild into a fresh output directory to avoid carrying an old nested ZIP forward.
