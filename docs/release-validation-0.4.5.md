# 0.4.5 promotion, 2 October 2026

## 2 October oil compatibility rebuild

James requested replacement of the existing 0.4.5 prerelease after Sumrac's source-hash regression. The corrected source includes geometric revalidation for differing game-file bytes, documented in [the investigation](oil-source-compatibility-2026-10-02.md). The full correction suite passed 387 tests with 21 optional skips. Native validation passed all 21 locomotives, 218 cups, 55,808 movement checks and 63 incompatible-geometry rejection cases. The replacement Windows build uses a fresh output directory and its executable self-test now exercises changed-source oil preparation for every locomotive in addition to all catalogue selections, Tk and tooling. Release-focused checks passed 24 tests with two optional skips.

The existing `v0.4.5` tag and prerelease are updated at the owner's explicit request, replacing the original downloads and checksums. The original source commit remains `21ecd86c469084cde95b238698374e7be251de4a`. Users must download the rebuilt app rather than accepting proposed end-beam geometry or editing hashes. New private release receipts are under `rr2dv_work/release-0.4.5-oil-hotfix`; previous receipts remain intact. Gameplay limitations below still apply.

The testing branch combines the measured cab-gauge and travelling oil-cup fleet passes with the complete nested-archive repair from `ca01c37b8b20d1a6cdc9965ad6558a74ded061b5` on main. App-board handover X73 was read before integration. The only merge conflict was package data, resolved by retaining the new oil fitting library and all loose catalogue assets.

Both app version declarations are 0.4.5. The changelog describes the complete combined change. The pinned tooling snapshot is unchanged. No private game meshes, converted packs, local logs or machine settings were added to Git.

## Validation

- The combined Python suite passed all 384 tests with no failures or errors, with 21 optional environment-dependent checks skipped. The separate native catalogue check below was explicitly enabled and passed.
- Real Unity 2019.4.40f1 and Car Creator 3.1.9 compiled all merged editor scripts. The native catalogue regression passed F-71, K-28T and C-40 root-only exports and reloads, including every test livery, translation preservation and rejection of unrelated or missing pages.
- A fresh Windows PyInstaller build passed the packaged executable self-test after expanding and removing `base_library.zip`. That self-test stages every one of the 21 catalogue selections and checks Tk and bundled tooling.
- Both final ZIPs and a wheel passed CRC checks, byte-for-byte comparisons of all 287 catalogue files against their indexed SHA256 hashes, nested-archive extension and disguised-ZIP scans, fitting-data and Unity-adapter inclusion, and version checks. Both ZIPs carry the current changelog and exclude the private work folder and SCRATCH ledger.
- The verification wheel was rebuilt using a fresh build directory after an initial wheel retained the obsolete catalogue ZIP from a pre-existing `build/lib` cache. The fresh wheel passed the same archive and hash checks. The Windows and source ZIPs did not contain that stale file.
- Existing native fleet evidence remains applicable, since the packaging merge changes no gauge or oil placement code. The gauge pass covered all 21 locomotives and 73 instruments, including actual importer binding and 282 needle calibration checks. The oil pass covered all 21 locomotives and 218 cups, with 55,808 position checks, plus 10,752 checks on four fresh production packs using their original exported animations. See the linked fleet reports for exact fixtures and limitations.

Private receipts are under ignored `rr2dv_work/release-0.4.5`, with build, Python-suite and native-catalogue logs alongside it. The executable was built using the existing packaging environment, without installing or updating dependencies.

## Gameplay acceptance

This is ready for the requested test-version promotion with gameplay limitations. There was no Nexus upload or new game installation. Rebuild from the restarted app before checking physical gauge visibility and control clearance, cup artwork and lids, oil-can access and refilling, live readings and save/reload. Coupling tilt, lights and the outstanding 0.4.4 issues remain open.

See [cab gauge fleet pass](cab-gauge-fleet-pass-2026-10-02.md) and [oil cup fleet pass](oil-cup-fleet-pass-2026-10-02.md).
