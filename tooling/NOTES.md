# Fresh tooling snapshot for W — 2026-09-26_201436

Live workspace: B:/LLW CONVERT. This tooling/ folder preserves the new workspace-relative layout. Copied source bytes are unchanged; SNAPSHOT_SOURCES.json maps every original to its SHA256. MANIFEST.sha256 covers every other tooling file, including generated delivery notes.

## Current entry points

- GUIDE_SHARED.md and the three GUIDE_ method/unified documents are at the root. This is a snapshot of the live board, including W1/W2/C18; messages addressed to local Claude/Codex remain historical coordination context. The future GitHub-board move has not occurred.
- builder/tools/run_build.ps1 and build.py launch current builds; workspace.py reads workspace.json and machine.local.json.
- builder/tools/unity is the current shared C# core. locos/g29/profile and locos/c21/profile contain current locomotive sources; locos/s16/profile holds existing pilot configuration.
- builder/tools/prepare.py prepares projects; builder/tools/pilot/pilots.py is the active pilot import entry, using the canonical strict resolver. Other predecessor scripts retain their historical behavior.
- builder/tools/audit_build.py, parity.py, install_build.py and share_project.py handle audit, semantic comparison, explicit-target installation and curated sharing.
- builder/baseline and reference/private/*-original/tools are frozen/historical evidence. They are not alternative current cores.

## Path mapping from C15

| C15 snapshot | Current tooling snapshot / workspace |
|---|---|
| unified_builder/tools | builder/tools |
| unified_builder/profiles/<id> | locos/<id>/profile |
| unified_builder/overrides | builder/overrides |
| docs/GUIDE_*.md | root GUIDE_*.md |
| pilot_workflows/tools | builder/tools/pilot (active importer); reference/private/pilot-original/tools (history) |
| g29_live_tools | reference/private/g29-original/tools (history) |
| old named workspace folders | ARCHIVE/PRIVATE-retired-projects/2026-09-26 in full snapshot |

## Inputs and machine configuration

This small ZIP contains tooling, configuration, guides and selected validation reports. The separate full snapshot contains every workspace file, including source/catalog-1.4.3, generated builder/catalog records, prepared projects, bundles, source assets, frozen references, caches, private archives and the original machine.local.json. Nothing was excluded from the full snapshot.

For a different machine, copy machine.local.example.json to machine.local.json and fill in local tool/dependency paths. workspace.json is an unchanged copy, including the live absolute board path; the app adapter should resolve its own snapshot location. Full snapshot copies of machine.local.json still name James's external tool paths; tools installed outside B:/LLW CONVERT are not included.

Unity 2019.4.40f1 and the separately acquired CarCreator 3.1.9 package remain dependencies. This packaging task does not build, install or publish packs. Original scripts in the tooling ZIP are for inspection/adaptation; the small ZIP alone lacks the asset and reference inputs required to run builds/audits. requirements.txt records local environment versions without installing them.

## Status

Migration evidence is under analysis/migration. Current/frozen/share semantic checks and nine workflow tests passed during migration. New game/VR acceptance remains separate. E04 mass correction is still pending. The empty original desktop G29 folder's lock status is recorded in cutover-completion.json; it is outside this B: snapshot and does not affect these deliverables.

The complete workspace content inventory is also supplied as LLW-CONVERT-CONTENTS.txt and LLW-CONVERT-MANIFEST.json alongside the ZIPs. Full snapshot includes local/private preservation material; it is distinct from the author's curated share packages under share/.

Snapshot timing: this captures every file in the initial inventory at 2026-09-26T19:14:42.009308+00:00. Later S16 work added paths and subsequently changed workspace.json; see CHANGES-AFTER-SNAPSHOT.json. The delivery preserves the captured versions, all ZIP file checksums passed, and the tooling copies match the full snapshot.

The complete workspace listing is also included here as WORKSPACE_CONTENTS.txt, so W can inspect every path using this small ZIP.
