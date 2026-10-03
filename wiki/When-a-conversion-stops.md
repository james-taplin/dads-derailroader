# When a conversion stops

`rr2dv` stops when a required fact is missing or a choice would be ambiguous. Start with the **Conversion** panel's stage and message. Then use **Open run folder** and read `run.log`. If no run began, use **Settings > Check** or `rr2dv doctor`.

| Where it stopped | First thing to check |
| --- | --- |
| Before conversion | Game installs, CCL, tool paths, a short work folder, and that the locomotive is one of the ten supported stock steam locomotives in Railroader's asset packs. |
| Windows Security blocks or removes a file | Protection history: record the detection name, affected file, and action. See the [Windows Security guide](https://github.com/james-taplin/dads-derailroader/blob/main/docs/resolving-blocks.md#windows-security-blocks-the-launcher-or-a-tool). A Unity crash alone does not establish an antivirus block. |
| `unsupported-whistle` | Reading 6-Chime is excluded in this test edition. Choose another available whistle. |
| No active Unity Editor licence | Sign in to Unity Hub and activate or refresh the appropriate licence. Open the configured Unity 2019.4.40f1 once to confirm startup, close it, then retry. After a failed run, send the compact report's `probe.log`; see [Installation](https://github.com/james-taplin/dads-derailroader/wiki/Installation). |
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

Give the stage, exact message, `run.log` excerpt, and relevant `build_report.txt` or `audit.json` finding. The app-wide log for problems outside a run is `rr2dv_work\logs\rr2dv.log` beside the app. Remove private paths or personal details before posting. Do not upload source assets.
</details>

## whistle fitting cannot resolve uniquely

the source whistle fitting is missing or ambiguous, keep the run report and locomotive name, the app will not attach its mesh to a similarly named cab lever


## Safety jet probe cannot find a supported forward surface

The fallback could not find a broad boiler/dome candidate clear of the cab, chimney and other fittings. Keep the run report and locomotive identifier for model review. Do not substitute the cab roof or whistle position. A reported candidate still needs visual checking after rebuilding and installing the pack.
