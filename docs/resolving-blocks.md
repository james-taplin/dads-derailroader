# When a conversion stops: how to resolve it

`rr2dv` records the stage, message, evidence, and any unresolved choice. Start with the run's `run.log` and `run.json`; the [README](../README.md) explains setup and the supported locomotive list.

## Before starting

| Message | What to check |
|---|---|
| A game was not found | In **Settings**, point `railroader` or `game` at the installation folder, or run `rr2dv doctor`. |
| Several installations were found | Select the intended installation in **Settings**. |
| A game folder is invalid | Choose the folder containing `Railroader_Data` or `DerailValley_Data`. |
| Derail Valley has no `Mods` folder | Install Unity Mod Manager, then install Custom Car Loader. |
| Custom Car Loader is not installed | Install the version required by the README and check that Unity Mod Manager reports it as ready. |
| A tool path is missing | Configure Unity, Car Creator, and AssetRipper in **Settings**; `rr2dv doctor` checks them. |
| The work folder path is too long | Set `workRoot` to a short path such as `C:\rr2dv`. |
| The app refuses to write inside a game folder | Choose a work folder outside both game installations. |

## Windows Security blocks the launcher or a tool

If `Launch Derailroader.bat`, `Derailroader.exe`, or a build tool is blocked or disappears, open **Windows Security > Virus & threat protection > Protection history**. Check the event at the time of the failure and record the detection name, affected file, and action taken. A Unity crash or a locked log file alone does not prove Defender caused it.

Update Defender's security intelligence and check that the download came from the project's linked release page. If the detection remains, report the app version, detection name, and affected filename to the maintainer so the exact file can be investigated and, if appropriate, submitted to Microsoft as a false positive. Do not upload game assets or converted packs.

Only restore or allow the specific detected item after verifying it is safe; do not disable Defender or exclude entire app, work, or game folders. Microsoft's [Protection history guide](https://support.microsoft.com/en-us/windows/security/windows-security/protection-history-in-the-windows-security-app) explains the available actions. If the warning instead says **Windows protected your PC**, include that exact wording in the report; a SmartScreen reputation warning is different from an antivirus detection.

## Locomotive selection and source files

Choose one of the 21 supported stock steam locomotives listed by `rr2dv list`. The application reads its files from the Railroader installation. If it is missing from the list, use Steam to verify the game installation, then run **Settings > Check** again.

| Stage or message | What to check |
|---|---|
| No supported steam locomotive was found | Verify Railroader's installation and run `rr2dv list` to see the names the app recognizes. |
| A required tender, truck, or part is missing | Verify the Railroader installation through Steam. The run report names the missing item. |
| A source pack cannot be read | Verify the game installation and inspect the named `Catalog.json`, `Definitions.json`, or bundle path. |
| A source definition is incomplete | Keep the run report and the named locomotive identifier with your issue report. |
| A duplicate source identifier is ambiguous | Verify the installed game files and rerun the scan. The app does not choose an arbitrary match. |
| A source file changed while being copied | Wait for Steam or file synchronization to finish, then start a fresh run. |

## Tools and Unity stages

| Stage or message | What to check |
|---|---|
| AssetRipper did not start or produced no export | Check its configured path and inspect the extraction details in `run.log`. |
| An AssetRipper cache entry is inconsistent | Close the app and remove the specifically named cache entry under `<workRoot>/_cache/assetripper`, then rerun. |
| Unity scripts did not compile | Confirm the configured editor version and inspect the Unity log path in the run report. |
| A Unity project is already open | Close the other Unity editor using that project, then rerun. |
| Unity appears to pause during a fresh import | A fresh import can take several minutes. Check whether `probe/unity-1.log` is still growing. |
| Unity did not produce a result | Inspect `probe/unity-1.log` for a licensing prompt or error, open Unity once to resolve licensing, then rerun. |

## Review and build

Review questions identify values the source cannot determine reliably. Use the displayed source facts and measurements; keep uncertain values unresolved until you can verify them. The driving-wheel value is a radius in metres. A measured candidate is evidence to inspect, not a confirmed measurement.

A build or bundle-audit block names the failed check in the app and report. Keep `build_report.txt`, `build/review.json`, and `audit/audit.json` when reporting the issue. A successful build and audit still needs in-game checks for controls, fit, handling, and save/reload.

Catalogue pages are selected by the source locomotive and tender identifiers, then attached to every exported livery. A missing mapping, damaged library asset, wrong page reference, missing icon/diagram, or unrelated page in the exported pack stops the build or audit. Restore the complete app download for a missing or damaged library; keep the run identifier and audit report for a reference or selection failure. Do not install the whole authoring ZIP as a mod. See [vehicle catalogue integration](vehicle-catalogue.md).

A whistle mesh requires exactly one steam fitting with its source name and component type. If the build reports that the Whistle fitting cannot resolve uniquely, keep the report and source locomotive identifier. The converter will not substitute a similarly named cab control or invent a location.

The testing builder turns measured dynamo jets' horizontal facing by 180 degrees while preserving their upward pipe tilt and outlet position. An unmeasurable pipe still uses the straight-up fallback. Rebuild older packs to receive the correction; the build report identifies which direction was used. Compare the rebuilt jet with the physical outlet in game, including switching the dynamo off and on, and report the locomotive and a clear side view if it is still wrong.

## Installation and reports

The app installs only after the personal-use notice is accepted. If a folder already exists in Derail Valley's `Mods` directory and was not created by `rr2dv`, the app leaves it untouched; choose another output name or resolve the conflict yourself.

For help, include the run identifier, stage, exact message, and a short relevant log excerpt. Do not post game assets, converted packs, or full private logs publicly.


## Safety jet probe cannot find a supported forward surface

The fallback could not find a broad boiler/dome candidate clear of the cab, chimney and other fittings. Keep the run report and locomotive identifier for model review. Do not substitute the cab roof or whistle position. A reported candidate still needs visual checking after rebuilding and installing the pack.
