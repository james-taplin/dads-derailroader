# LLW conversion workspace

Canonical location: **B:/LLW CONVERT**. The Desktop LLW CONVERT entry is a junction here.

## Start here

- [Shared Claude/Codex board](GUIDE_SHARED.md)
- [Claude method guide](GUIDE_Railroader_to_DV_CCL.md)
- [Codex method guide](GUIDE_Railroader_to_DV_CCL_CODEX.md)
- [Unified conversion guide](GUIDE_UNIFIED_LLW_CONVERSION.md)
- [Builder commands](builder/README.md)
- [Current path mapping](docs/MIGRATION_PATHS.md)

Current tools: builder/tools. Locomotive profiles: locos/{g29,c21,s16}/profile. S16 is the first generic JSON vehicle record; see [vehicle record documentation](builder/VEHICLE_RECORD.md). Paths are in workspace.json; private machine tool settings are in machine.local.json.

The root-path cutover and archive preservation are complete. Seven stale project folders were preserved as individually verified ZIPs in [ARCHIVE](ARCHIVE/README.md); all contents are removed, with one empty locked root awaiting deletion. Sent-package records are in share/sent/2026-09-26, with the former to_send folder preserved as a ZIP in its ARCHIVE subfolder. File manifests, checksums and deletion evidence are in analysis/migration.

Use builder/tools/run_build.ps1 with -Profile g29, c21 or s16 and a fresh -Run name. -Frozen replays preserved G29/C21 prerelease2/test17 source; -Tests runs editor integration checks; -Share selects stock audio. The launcher waits and audits. Output goes to locos/<profile>/builds/<run>.

Only explicitly audited allowlisted packages are shareable. Project archives, audio-bearing packs, Unity projects, rollbacks and machine settings remain private. Migration left installed game packs unchanged; S16 was subsequently installed at James's request (see below). E04 mass correction and new in-game acceptance remain separate work.


## Remaining empty-folder cleanup

Seven stale source folders removed. The eighth (original G29) has no remaining contents, but its empty root is locked by Unity Hub; James chose to close Hub himself. No process was stopped by Codex. Empty-root deletion remains pending.

## S16 first build

The S16 personal pre-release is built: [status and validation](locos/s16/analysis/BUILD_STATUS.md), [build notes](locos/s16/builds/prerelease2/BUILD_NOTES.md), [installable ZIP](locos/s16/packages/LLW_S16_0.1.0_personal.zip). The generic JSON loader is implemented; S16 uses it. Installed into `Mods/LLW S16` on 2026-09-26 after a fresh audit and matching bundle hash; receipt in `locos/s16/analysis/delivery.json`. Game/VR acceptance is pending.
