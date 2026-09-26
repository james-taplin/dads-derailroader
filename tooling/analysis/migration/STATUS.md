# LLW migration status — 2026-09-26

Canonical workspace: **B:/LLW CONVERT**. The Desktop folder is a compatibility junction.

Preparation, automated validation and Claude's independent review C17 passed. James approved final cutover: board and guides now at workspace root, eight stale source folders preserved in verified ZIPs; seven folders removed and the eighth empty root locked. See cutover-completion.json, cutover-archives.json and cutover-deletions.json.

## Evidence

- Complete move: 20,790 files, 8,218,577,231 bytes; destination SHA256 matched every source file, then source was rechecked before removing the C: copy. See move-result.json and move-*-sha256.json.
- Consolidation: 14,988 cache-excluded copied files, 8,185,134,824 bytes, hash-verified. See copy-sha256.json. Predecessor trees are now preserved in ZIPs; canonical private snapshots remain available.
- Nine Python workflow tests, eight actual Unity editor integration checks, eight temporary-target installer/rollback checks and two additional source-manifest coverage checks passed.
- Current G29 and C21 plus G29 share output match their preserved unified references by serialized semantics. Frozen G29/C21 match prerelease2/test17 respectively. Comparison resolves local IDs and external file indices by identity, checks object fields and warning lines, and rounds floats to six decimals. Bundle-byte identity is not claimed.
- No game installation occurred. Installed G29 0.9.1 and C21 0.1.3 still match their captured prerelease2/test17 bundle hashes. Complete rollback copies are in reference/private/installed-before-migration.

| Profile | Final run | Result | Exact reference warning count |
|---|---|---|---|
| g29 | migration_current01 | passed | 7 |
| c21 | migration_current01 | passed | 8 |
| g29 | migration_frozen02 | passed | 7 |
| c21 | migration_frozen01 | passed | 8 |
| g29 | migration_share01 | passed | 7 |

The first G29 frozen driver failure was a launcher mismatch with the legacy exporter, not a failed export. Its initial build-matrix.json and diagnostic evidence remain. migration_frozen02 passed the corrected launcher end to end. See VALIDATION_HISTORY.md for comparator fixes and deliberately invalid test fixtures.

## Limits and outstanding decisions

E04 is confirmed: current profiles subtract spawn-water litres as kilograms; actual serialized spawn pressure is 1 bar and DV uses 1.049301 L/kg. The ledger is about 285.666 kg light for G29 and 264.654 kg for C21 before other contents. Physics was preserved during relocation; a correction needs a separate profile change and acceptance.

No new driving, VR or save/reload test was performed. Existing acceptance is not automatically assigned to new bundle hashes. Full arbitrary-pilot import and future sharing publication are outside these relocation checks.

Claude reviewed the migration evidence in C17. James subsequently approved cutover, complete except for the locked empty G29 root. Shared board: B:/LLW CONVERT/GUIDE_SHARED.md. Claude memory and cloud relay coordination uses quiet-owl.

User update: James deleted the empty root LLW G29 CONVERSION.7z; no deletion action remains for it. See cutover-plan.json for the completed action record.


## Remaining empty-folder cleanup

Seven stale source folders removed. The eighth (original G29) has no remaining contents, but its empty root is locked by Unity Hub; James chose to close Hub himself. No process was stopped by Codex. Empty-root deletion remains pending.
