# When a conversion stops: how to resolve it

`rr2dv` records the stage, message, evidence, and any unresolved choice. Start with the run's `run.log` and `run.json`; the [README](../README.md) explains setup and the supported locomotive list.

## Restricted test edition

`0.4.7+fixed.1` on `dads-derailroader/fixed` supports only A-23, A-26, C-25, D-46, F-71, G-25, K-35, P-18, T-17 and T-22. An excluded stock locomotive is refused before extraction. Reading 6-Chime (`wh-6-reading`) is absent from the whistle choices; selecting it explicitly or naming it as a source default blocks conversion with `unsupported-whistle`. Choose another available whistle. Historical all-fleet measurements below describe the retained reference library, not this edition's supported list. Existing installed packs and settings are not removed.

## Measured cab instruments and numerical speed HUD

All 21 cabs now require their selected source gauges and measured supports to agree with the fitting library. Changed source counts, names/styles or transforms stop the build. Missing/ambiguous gauges or supports, an intersecting pad, fewer than seven rear pad contacts, or changed mounting data also stop it. Stud adapters require at least three non-collinear contacts meeting their named source geometry within 1 mm and lengths of 2–160 mm. Preserve the build report for fitting review; do not bypass the check with a generic offset. Every newly built loco also requires a numerical F4 speed box and a speed reader wired to absolute km/h. A missing HUD layout, speed indicator or matching traction reader stops the build/audit for investigation.

The complete DV housing is deeper than the original generated dial. Diagnostic reports therefore retain the original face-distance screen and separately report the rear mounting pad; a face more than 30 mm from the backhead is not itself proof that the complete housing floats. A supported pad remains a candidate requiring driver-view, glass, lighting and full control-sweep checks in game. See [the implementation handover](cab-gauge-implementation-2026-10-02.md).

Two-instrument cabs retain boiler and pipe/cylinder brakes; three add speed; four add steam-chest pressure. Numerical speed and main reservoir remain on F4. Known cabs no longer receive neighbour-generated extra faces. C-25's unsupported extra faces came from the former shared rule; rebuild instead of manually moving the dials. All 73 assemblies have complete cases and measured backing pads or studs. See [the all-21 fitting pass](cab-gauge-fleet-pass-2026-10-02.md) for layouts and remaining game checks.

## Running-gear oil cups

The testing branch requires a left/right oil-cup pair for every driven axle, a minimum of six cups, and a maximum of twelve. Additional main-rod or crosshead bearing pairs are used where the source geometry supports them. All 21 stock locos have measured fittings in `oil_fits.json`, mirrored in the master vehicle table. Each anchor is parented to its named travelling mesh; CCL's stock position sync moves the cup while keeping it upright.

Source-file hash differences are reported, then the measured fittings must pass checks against the current built model and animation before export. A byte difference alone does not prove that the geometry changed. Missing/invalid source hashes still stop preparation. Changed driver radius/axle count or axle positions, a missing/stationary moving parent, lost bearing contact, or lost clearance stops the build. The builder checks an upright 3.5 cm radius, 9 cm high cup envelope and 12 cm cup spacing at 64 phases through a revolution. It does not fill the quota with running-board cups or silently disable manual oiling. Keep the run's build report and vehicle identifier for fitting review. Rebuild older packs; visual seating, lid motion and oil-can access still need in-game acceptance. See [the fleet oil-cup report](oil-cup-fleet-pass-2026-10-02.md).

The original 0.4.5 download stops immediately with **game files changed; remeasure the oil-cup fitting before using it**. This is an overly strict compatibility check, not evidence of a failed bearing fit. It compares the bundle, catalogue and definition bytes with the developer's reference installation. A Railroader update can trigger it, but the error does not identify why the files differ. **Use proposed geometry** only reviews end-beam placement and cannot bypass this oil-fitting error. Download the updated 0.4.5 app from the 2 October prerelease rebuild, close the old app and extract into a fresh folder before trying again. Retain the `vanilla table` line and run log for diagnosis rather than editing the hash library or copying old geometry reviews.

## Tender truck wheel pivots

The builder centres each prepared truck's visual rotation pivot on the original Railroader wheel spindle, while retaining its resting geometry and rolling radius. This follows the earlier fix that separated the two wheelsets onto their own axle nodes. Rebuild older packs to apply the additional correction.

Messages including **Truck wheel pivots require explicit wheel-node prefixes**, **Truck wheel spindle is not finite**, **Truck axle contains wheel nodes from different spindle centres**, **Truck wheel spindle does not match its recorded axle position**, or **No prepared truck wheels found for spindle correction** stop the build rather than guessing a rotation centre. Keep the vehicle identifier, probe output and build report for investigation; do not force a generic offset. See [the A-23 investigation](tender-wheel-pivot-fix-2026-10-02.md).

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

Choose one of the ten supported stock steam locomotives listed by `rr2dv list`. Excluded engines stay unavailable even when installed. The application reads supported engines' files from the Railroader installation. If a supported engine is missing from the list, use Steam to verify the game installation, then run **Settings > Check** again.

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

If oil preparation reports **Driver radius … differs from the measured oil-cup fitting**, compare the displayed values with the source driving-wheel radius. A low-confidence probe candidate may not be the tyre tread. Sumrac's S-23 report from 3 October restored a previously accepted **0.682972 m** candidate, while the definition and fitting use **0.6477 m**. In the pre-build review, set S-23's **Driving tyre radius (m)** to **0.6477**, confirm and retry. This addresses that review mismatch; the actual model must still pass the native bearing and motion checks. **Use proposed geometry** only concerns car ends.

From 0.4.7, the app replaces an incompatible automatically restored stock radius with the current source suggestion only when that suggestion agrees with the measured oil fitting. It explains the change in the review, retains all other saved choices and requires confirmation. It does not alter the original saved file before confirmation, substitute reference values for changed source geometry, or relax the oil-fitting checks. The error now names both radii and points to the pre-build review. Low-confidence candidates remain labelled; confirm the driving tyre rather than a flange.

A broad settings/cache reset is not needed for that radius conflict. Sumrac's S-23 report shows fresh extraction with zero bundles reused from cache: the conflicting value came from a saved review. Confirming the corrected radius updates that review. Deleting only `reviews` may still let older choices return from `reports/*/prebuild-review.json`; keep settings and reports for diagnosis. Close the old app and restart the newly extracted 0.4.7 app before retrying.

**Content used** lists credits from the selected source definitions and models, including the chosen whistle's definition and mesh. Missing artist metadata does not block conversion: that content is attributed to **Giraffe Labs LLC**, and all models remain the property of their existing rights holders. Unrelated definitions in the same asset pack are excluded. The credits accompany the installation notice and installed provenance records.

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


Catalogue files are shipped unpacked with their Unity metadata. If release packaging reports "Nested archive cannot ship", expand the required contents and update the loader; do not bypass the check or drop the catalogue. Windows builds also unpack the Python standard library and run the packaged self-test. Rebuild into a fresh output directory to avoid carrying an old nested ZIP forward.
