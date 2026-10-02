# Cab gauge inspection kit — 0.1

First-pass tools for all 21 rr2dv steam cabs: **do the actual dial faces point rearwards, and is there support behind them?** This is a diagnostic package, not a gauge repair, converter update or game mod.

## What you get

- `GaugeProbe.cs`: automated Unity inspection and native synthetic regression cases.
- `run.py`: discovers installed packs, decodes their geometry, creates a separate inspection project, runs Unity and writes reports.
- `test_kit.py`: tests the report/error handling and ZIP allowlist.
- `report.html`: generated fleet tables and top-view face-direction diagrams; opens in a normal browser without a server.
- `gauges.csv`: spreadsheet-friendly per-gauge measurements.
- `result.json`: complete centre/rim hits, supporting hierarchy paths, face normals and needle configuration.
- `summary.json`: completion status and counts. Completion means inspection succeeded, NOT that gauges passed.
- `gauge-results.zip`: only the four report files, never game geometry or the inspection project.

## Requirements

Windows; licensed Unity **2019.4.40f1**; Python 3.11 or later with UnityPy; an existing disposable Unity project with **Car Creator 3.1.9** imported at `Assets/CarCreator`; installed rr2dv packs. No game or Creator assets are distributed in this kit.

If UnityPy is not installed, install it in your preferred diagnostic Python environment. The kit does not install dependencies automatically. Use the same Python for its tests and runner.

## Run

Extract the kit, then run in PowerShell (replace paths as appropriate):

```powershell
py -3.14 -B .\test_kit.py
py -3.14 -B .\run.py `
  --mods 'B:\SteamLibrary\steamapps\common\Derail Valley\Mods' `
  --unity 'B:\Games\Unity 2019.4.40f1\Editor\Unity.exe' `
  --creator-project 'B:\path\to\a\CreatorProject' `
  --output 'B:\gauge-inspection-new-run' `
  --only k35,p18,t21,t22
```

Omit `--only` to inspect **all 21**. Codes accept hyphens, e.g. `K-35`. Use a **new output directory every time**. The runner refuses to reuse a project or silently omit a requested loco. Duplicate installed copies of a loco are an error. Expected IDs: A-23, A-26, B-65, C-25, C-40, C-46, C-55, D-46, F-71, G-16, G-25, K-28T, K-35, P-18, P-43, P-48, S-23, S-51, T-17, T-21, T-22.

The runner copies only Creator assets and the project's Packages/ProjectSettings, not the converter's Editor scripts or source models. Use a trusted Creator project with its normal dependencies. Unity runs hidden, windowed (not batchmode), with a 15-minute default timeout. `--timeout` changes that limit. It may take several minutes to decode bundles and import the new project. Errors are preserved in `failure.txt` and/or `unity.log`; a failed measurement is never a gauge pass.

Open `report.html` when finished. The return code is 0 for complete inspection, 1 for an incomplete run. A successfully measured sideways/floating gauge is still a finding even though the tool exits 0. Do not run conversions into the inspected Mods folder concurrently: input hashes are checked before/after to reject a moving baseline.

For the C-25 pressuremeter pilot, also supply `--dv-resources 'B:\SteamLibrary\steamapps\common\Derail Valley\DerailValley_Data\resources.assets'` (adjust to your own install). The probe resolves MeshGrabberFilter references on temporary diagnostic clones. Missing or ambiguous donor resources fail explicitly. Only the four allowlisted pressuremeter meshes are reconstructed, into private diagnostic buffers excluded from both report and kit ZIPs. Original bundles remain unchanged.

A complete pressuremeter has depth, so its face can legitimately be over 30 mm ahead of its support. Instruments with a `mount datum` also receive a separate nine-point housing-pad screen: at least seven contacts within 4 mm, with no intersection over 1 mm. `supported-pad-candidate` still requires full housing clearance and in-game acceptance. The original face thresholds and labels remain unchanged for comparison with the baseline.

## Measurements and screening rules

Coordinates are the exported car frame: +Z front, -Z rear/crew, +Y up. The probe checks root position/rotation and derives the face normal from transformed **mesh triangles**, so a 90-degree or mirrored face is not hidden by misleading transform labels. It records position, face normal, rear angle, face-up angle and measured diameter.

- Rear-facing: within 15 degrees of -Z.
- Sideways: 60–120 degrees from rear.
- Front-facing: 165–180 degrees from rear.
- Other angles: explicit review; not an automatic pass.

Mounting uses nine rays: centre and eight points at 80% of the face radius. They run behind the dial along its actual normal, starting 50 mm in front, and search to 500 mm behind. The gauge assemblies themselves, collision-only objects and lower LOD meshes are excluded from support geometry. Positive gap is behind the face; negative is in front. Each sample records distance, hit normal and part path. A missing hit is `found=false` (numeric sentinel -999 is not a measured gap).

- `supported-candidate`: at least 7/9 hits are within 30 mm behind the face, with no intersection exceeding 2 mm.
- `partial-support-review`: some nearby support but insufficient rim coverage.
- `unsupported-within-30mm`: no samples establish nearby support; includes large floating gaps.
- `intersects-surface`: a sampled surface is more than 2 mm in front of the dial plane.

These are **initial screening thresholds**, not universal mounting dimensions. A thick housing or proper narrow bracket may need manual acceptance. A close pipe or moving panel is not automatically a valid mount: inspect the recorded paths. Skinned support geometry is not ray-tested; unknown/missing support must stay under review. Eight rim samples cannot prove the whole face is free from clipping. Gauges should not be repositioned from these measurements alone.

The probe inspects the exported `_interior` and `_template`, using temporary readable meshes reconstructed from original vertex/index buffers; it never changes their source bundles. Missing/ambiguous mesh matches and missing scripts fail explicitly. Measurements are for the installed bundle hash, which may predate the latest app release.

## Testing package

Every Unity run first tests the same measuring function with known geometry: rear/side/front faces, nine-point support, a 250 mm floating gap, an intersecting panel, centre-only support and a mirrored face. Failure prevents a normal completed receipt. Python tests exercise fleet cardinality, failed-result reporting and the report ZIP's no-geometry allowlist.

The kit inventories each visible gauge needle's range, angles, reader type, port strings and needle reference. It **does not yet drive the simulation, test needle calibration/damping, render cab screenshots, assess printed units, or certify glass/lighting/HUD readings**. Its diagrams are asset-free measurement schematics. Water glasses and HUD-only indicators are outside this dial-first scan. Absent boiler-water geometry must not be reported as a failed dial.

## Fix and retest workflow

1. Preserve a baseline report and bundle hash; inspect sideways/front-facing gauges first.
2. Verify a real panel/backhead/bracket for each unsupported candidate. Use side and driver-view evidence; do not rotate every gauge by 90 degrees indiscriminately.
3. Apply any correction in app-owned source on the testing branch. Do not edit pinned tooling, the offline builder or installed prefabs by hand.
4. Rebuild the affected pack, rerun this kit into a fresh output folder, compare gauge path, angle and support samples.
5. Confirm the entire face/needles/glass/housing assembly, readability and control clearance in game. Only then move to needle calibration and cosmetic polish.

Keep full meshes/projects/logs locally; the output folder contains reconstructed game geometry for diagnostics and is not a distributable pack. Share the small results ZIP privately for review; failed-run stack traces may contain local paths. The kit ZIP itself contains only source, instructions and optional asset-free test receipts.


## Included baseline — 2026-10-02

The supplied `baseline/` reports measure 101 exported dial assemblies across all 21 installed steam locomotives. Unity inspection completed with exit 0; native geometric regressions and four Python tests passed. Every installed bundle hash was unchanged after inspection. 50 faces met the 15-degree rear-facing screen and 48 mounts met the 7/9 nearby-support screen; these are independent counts. Other results require individual review, not blanket rotation or relocation. Each loco's exact inspected bundle hash is in result.json; this historical installed fleet is not claimed to be rebuilt 0.4.3 or validated in game.
