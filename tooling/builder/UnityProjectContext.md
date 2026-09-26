# Migration amendment, 2026-09-26

Confirmed canonical root is B:/LLW CONVERT. Projects: locos/g29/unity and locos/c21/unity; profiles: locos/<id>/profile; core: builder/tools/unity. Paths are manifest-owned. Unity version rechecked as 2019.4.40f1 (ffc62b691db5), TMP 2.1.6/uGUI 1.0.0, empty player scene list. Nine Python workflow checks and eight actual editor integration checks passed after relocation. Frozen replay projects live under reference/private/frozen-projects. No Unity MCP is required or configured. Historical notes below describe the predecessor layout; use the manifest for active paths. See analysis/migration for exact validation outcomes and E04's pre-existing mass discrepancy. No source-control commit exists; SHA256 copy/source manifests supply provenance.

# Unified LLW builder context
date: 2026-09-26; repository: local non-Git workspace; baseline/sources.json pins inputs.

Confirmed roots: `unity/G29_CCL`, `unity/C21_CCL`, cloned by tools/prepare.py from the frozen G29 and C21 projects; reference paths are in that script. Sources stay in tools/unity; per-vehicle profiles in profiles/{g29,c21}. Assets/Editor copies are generated deployment copies.

Environment: Unity 2019.4.40f1 (ffc62b691db5), Windows x64 CCL asset bundles, CarCreator 3.1.9. Built-in renderer; TMP 2.1.6, uGUI 1.0.0; legacy input settings. No game/player build scenes (EditorBuildSettings m_Scenes=[]). This is an editor-driven mod exporter; game input/simulation belongs to DV/CCL. No networking or MCP integration found in manifests. No package changes required. Unity editor is callable directly; connected editor/MCP unverified and unnecessary for this pipeline.

Architecture: static CclLocoBuild consumes a LocoConfig; reflection creates CCL.Types proxies in generated prefabs; tender is a second config. Config delegates supply vehicle-specific measurements and simulation values. Unity executes G29Config.Build/C21Config.Build, renders inspections, exports CCL packs. First-party scripts are editor-only in Assets/Editor, using System/UnityEditor/UnityEngine; runtime bundle scripts must belong only to CCL.Types. Preserve CarCreator and imported source GUIDs. No new runtime assembly.

Validation: baseline G29 prerelease2 (7 accepted coupler-envelope warnings); C21 test17 (8). Both previous implementations were user-confirmed in game; merged outputs need fresh runtime checks. Compile/export logs, final-pose placement gates, bundle semantic audits and regression comparisons are required. New runs have unique output directories. Source profiles and shared scripts are SHA256 recorded per run. No Unity Test Framework suite configured; Python workflow tests and editor integration gates cover automation. Existing imported caches/logs are not source.

Constraints: no editing reference cores or source bundles; no blanket warning suppression; no inference of in-game acceptance from export; installed packs and saves remain outside the build workflow. Exact fitting overrides still pass final-pose geometry validation. Fleet records may be generated from definitions, but a record without measured overrides is not a playable conversion.

Evidence: both ProjectVersion.txt/Packages manifests/EditorBuildSettings; G29 tools/setup_build_project.ps1 and run_unity.ps1; C21 tools/run_c21.ps1, audit_c21.py, README.md; CclLocoBuild.cs/LocoConfig.cs and configs/sources; GUIDE_UNIFIED_LLW_CONVERSION.md 1.1 + GUIDE_SHARED.md C12. No source-control commit is available; snapshots provide provenance.
