# Approved cutover: empty-folder cleanup pending — 2026-09-26

Board and all three guides are directly at B:/LLW CONVERT. Original guide locations redirect here; full pre-cutover text is preserved in Guides-before-cutover.zip.

Each archive was read back file by file with SHA256, then the complete source inventory was rechecked before deletion. Empty directories are preserved too.

| Removed stale source | Preserved ZIP | Files |
|---|---|---|
| B:\LLW CONVERT\LLW Unified Builder | ARCHIVE\PRIVATE-retired-projects\2026-09-26\LLW Unified Builder.zip | 9055 |
| B:\LLW CONVERT\LLW Pilot Workflows | ARCHIVE\PRIVATE-retired-projects\2026-09-26\LLW Pilot Workflows.zip | 9289 |
| B:\LLW CONVERT\LLW Generic Locomotive Catalog | ARCHIVE\PRIVATE-retired-projects\2026-09-26\LLW Generic Locomotive Catalog.zip | 102 |
| B:\LLW CONVERT\LLW G29 CONVERSION | ARCHIVE\PRIVATE-retired-projects\2026-09-26\LLW G29 CONVERSION.zip | 2315 |
| B:\LLW CONVERT\_G29_Update_Work | ARCHIVE\PRIVATE-retired-projects\2026-09-26\_G29_Update_Work.zip | 20 |
| B:\LLW CONVERT\FoxTrucks | ARCHIVE\PRIVATE-retired-projects\2026-09-26\FoxTrucks.zip | 4 |
| C:\Users\james\Desktop\Derail Valley Mods\Claudes Place\LLW_G29_Conversion | ARCHIVE\PRIVATE-retired-projects\2026-09-26\G29-original-from-Claudes-Place.zip | 6025 |
| B:\LLW CONVERT\to_send_2026-09-26 | share\sent\2026-09-26\ARCHIVE\to_send_2026-09-26.zip | 2 |

Sent-package flat ZIP copies remain unchanged in share/sent/2026-09-26. James already deleted the empty .7z; no action was taken on it.

Evidence: cutover-archives.json, cutover-deletions.json, cutover-completion.json. Game bundle hashes unchanged. E04 and new game acceptance remain separate.


## Remaining empty-folder cleanup

Seven stale source folders removed. The eighth (original G29) has no remaining contents, but its empty root is locked by Unity Hub; James chose to close Hub himself. No process was stopped by Codex. Empty-root deletion remains pending.
