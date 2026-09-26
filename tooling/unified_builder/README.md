# LLW Unified Builder

One shared editor builder for LLW Railroader -> Derail Valley / CCL 3.1.9. Built with Codex and Claude assistance from James's tested G29/C21 conversions and the reviewed unified guide. Original LLW assets: MarquetteCreations. This workspace is a private development workspace; only curated `share/` output is intended for handoff.

## Entry points

- `tools/unity/`: authoritative shared C# core; `profiles/{g29,c21}/`: measured Config/Defs/Source/Probe.
- `catalog/`: 25 generated, source-hashed records; `overrides/`: two measured profile registrations. Other 23 records are explicitly incomplete. `catalog.py` preserves full source objects/components and routes metadata; it does not invent geometry or produce 25 playable conversions.
- `unity/{G29,C21}_CCL`: prepared project copies. Refresh through prepare.py/run_build.ps1; do not hand-edit Editor copies.
- `builds/`: immutable runs and audits; `baseline/`: original source snapshots and SHA256 provenance; `analysis/`: tests, diff, validation report.
- `MIGRATION_PLAN.md`: C13 proposal for consolidating all LLW work; originals remain in place.

## Behavior

G29 general core + C21 explicit oil anchors, source-pin checks and firebox indicator scaling. Final poses are checked after auto/exact placement. Runtime-scaled release bracket .431255 m; G29 accepted locomotive seat pinned and geometry checked. Plate anchor local +x faces outward. End-beam probes exclude the high tank face, fail on insufficient/implausible geometry. Pony groups accept separate radii; measured G29 .345 m overrides catalogue .34 m. Source clips reject unresolved or duplicate hierarchy paths. Oil cups retain save-index order, use animated parents, and undergo four-phase motion/triangle-surface checks. C21 shallow caps also pass independent island discovery.

C21 working-order interpretation now subtracts 5632.78 L provisional spawn boiler water from its 41,730.50 kg source figure: base 36,097.72 kg, water restored by DV. Firebox/other contents remain additional. This is a labelled source interpretation, not a historical certification or full C21 steaming rebalance. G29 firebox HUD range now matches its configured 65 kg, ported from C21's capacity-aware method.

## Commands

Windows PowerShell; installed Unity 2019.4.40f1 (`B:/Games/Unity 2019.4.40f1/Editor/Unity.exe`) and private prepared source projects are required. Bundled Python path is configurable in run_build.ps1. Unity needs its normal user context to reach local licensing. No package installation required.

```powershell
$py = 'C:\Users\james\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py .\tools\catalog.py
& $py .\tools\test_workflow.py
.\tools\run_build.ps1 -Profile g29 -Run my_check -Tests
.\tools\run_build.ps1 -Profile g29 -Run my_build
.\tools\run_build.ps1 -Profile c21 -Run my_build
.\tools\run_build.ps1 -Profile g29 -Run my_share -Share
# Launch returns a PID. Wait for Unity to exit and result.json/exported=true before auditing.
& $py .\tools\audit_build.py g29 .\builds\g29\my_build
& $py .\tools\audit_build.py c21 .\builds\c21\my_build --share
& $py .\tools\audit_build.py g29 .\builds\g29\my_share --share
```

Audits require the existing UnityPy installation; the script uses its located private site-packages path. Paths to inputs/tooling are explicit in prepare.py/catalog.py/audit_build.py; set these for another machine. Original exports, CarCreator and Fox truck dependency must be acquired separately; no full source import/bootstrap of an arbitrary new locomotive is claimed.

`-Share` uses DV stock audio on G29, preserving its normal personal-use RR audio profile. C21 already uses stock DV audio. Bundle audits check zero embedded AudioClips for share outputs. `tools/share_project.py` only packages audited bundles plus allowlisted source/docs; it never includes Unity projects, extracted assets, decompilation, source game audio or CarCreator. Fox truck meshes remain in compiled locomotive bundles and are disclosed.

No automatic installation or save modifications. New merged packs need in-game checks for driving/steaming, cab plates, oil interaction, both coupling ends and save/reload; old user acceptance is not assigned to newly merged outputs. See `analysis/VALIDATION.md` for exact results.
