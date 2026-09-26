# LLW conversion workspace

Canonical location: **B:/LLW CONVERT**. The Desktop LLW CONVERT entry is a junction here.

## Start here

- [Shared Claude/Codex board](GUIDE_SHARED.md)
- [Claude method guide](GUIDE_Railroader_to_DV_CCL.md)
- [Codex method guide](GUIDE_Railroader_to_DV_CCL_CODEX.md)
- [Unified conversion guide](GUIDE_UNIFIED_LLW_CONVERSION.md)
- [Builder commands](builder/README.md)
- [Current path mapping](docs/MIGRATION_PATHS.md)

Current tools: builder/tools. Locomotive profiles: locos/{g29,c21}/profile. Paths are in workspace.json; private machine tool settings are in machine.local.json.

The root-path cutover and archive preservation are complete. Seven stale project folders were preserved as individually verified ZIPs in [ARCHIVE](ARCHIVE/README.md); all contents are removed, with one empty locked root awaiting deletion. Sent-package records are in share/sent/2026-09-26, with the former to_send folder preserved as a ZIP in its ARCHIVE subfolder. File manifests, checksums and deletion evidence are in analysis/migration.

Use builder/tools/run_build.ps1 with -Profile g29 or c21 and a fresh -Run name. -Frozen replays preserved prerelease2/test17 source; -Tests runs editor integration checks; -Share selects stock audio for G29. The launcher waits and audits. Output goes to locos/<profile>/builds/<run>.

Only explicitly audited allowlisted packages are shareable. Project archives, audio-bearing packs, Unity projects, rollbacks and machine settings remain private. Installed game packs were unchanged. E04 mass correction and new in-game acceptance remain separate work.


## Remaining empty-folder cleanup

Seven stale source folders removed. The eighth (original G29) has no remaining contents, but its empty root is locked by Unity Hub; James chose to close Hub himself. No process was stopped by Codex. Empty-root deletion remains pending.
