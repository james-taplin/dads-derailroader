# When a conversion stops

`rr2dv` stops when a required fact is missing or a choice would be ambiguous. Start with the **Conversion** panel's stage and message. Then use **Open run folder** and read `run.log`. If no run began, use **Settings > Check** or `rr2dv doctor`.

| Where it stopped | First thing to check |
| --- | --- |
| Before conversion | Game installs, CCL, tool paths, a short work folder, and that the locomotive is one of the 21 stock steam locomotives in Railroader's asset packs. |
| `locate` / `link` | Which locomotive was selected; missing or duplicate tenders, trucks, part packs, or sounds evidence. |
| `stage` / `extract` | Whether a source file changed while copied; AssetRipper path and export diagnostics. |
| `import` / `probe` | Animation ownership, Unity version, an open Editor, licence prompt, and Unity logs. |
| `record` / review | Missing source specifications, livery, wheel radius, or a changed review fingerprint. |
| `build` | `build/blocks.json`, `build/review.json`, and `build_report.txt` for geometry, controls, materials, and simulation decisions. |
| `audit` | `audit.json`: exported audio, missing controls, forbidden scripts, or values that differ from the record. |
| `publish` | The notice, or an existing pack folder that `rr2dv` did not create. |

The [complete block and review-item guide](https://github.com/james-taplin/dads-derailroader/blob/main/docs/resolving-blocks.md) is the maintained source for exact messages, codes, and fixes. After a fix, run the conversion again. Your Railroader install is read only; saved review answers and compact reports survive a stopped run.

<details>
<summary><strong>What to include when asking for help</strong></summary>

Give the stage, exact message, `run.log` excerpt, and relevant `build_report.txt` or `audit.json` finding. The app-wide log for problems outside a run is `%LOCALAPPDATA%\rr2dv\logs\rr2dv.log`. Remove private paths or personal details before posting. Do not upload source assets.
</details>
