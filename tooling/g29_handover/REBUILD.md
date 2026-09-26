# Inspecting and rebuilding the G29 conversion

These instructions target the included historical toolchain and copied project. They are not a claim of compatibility with every newer Unity, AssetRipper, CCL or DV release. The preserved test4 pack was copied, not rebuilt for this handover. **For the new ancillary animations and Railroader sounds, follow the [test5 continuation instructions](updates/test5-ancillary-and-audio/README.md).** The sections below describe the preserved test4 baseline. The update uses a complete newer C# source set and four audio inputs prepared from the recipient's own Railroader installation.

## Dependencies

| Dependency | Recorded version / requirement | Supplied? |
|---|---|---|
| Unity Editor | 2019.4.40f1, Windows | No; use your own installed/licensed Editor. |
| CarCreator | 3.1.9 | Yes: imported in the project and original `.unitypackage` in `conversion/tooling`. |
| TextMeshPro / uGUI | 2.1.6 / 1.0.0 | Project package manifest/lock supplied; Unity may need package download access after cache regeneration. |
| Python | Original venv metadata records 3.12.10 | Interpreter/venv not supplied. Standard-library scripts work with an appropriate Python 3 installation. |
| PyYAML | Original environment records 6.0.3 | Needed by `analyze_export.py`, not the normal setup/build. |
| UnityPy | Original environment records 1.25.3 | Needed by bundle-dump helpers, not normal setup/build. |
| AssetRipper GUI Free | Local executable metadata reports 2.0.0 | Not supplied; only needed to re-extract bundles. Preserved exports let you skip it. |
| Derail Valley + Unity Mod Manager + DVCustomCarLoader | Test-era game install; CCL 3.1.9 workflow | Not bundled. `Info.json` records ManagerVersion 0.27.3 and requires DVCustomCarLoader. No full game-version compatibility claim is made. |
| `ilspycmd` | Version not established from the G29 records | Optional for further investigation; not needed to build. |
| .NET Framework C# compiler | The helpers use Windows Framework `csc.exe` and game reference assemblies | Only needed if recompiling the separate support mods. |

The original venv is machine-bound and was not copied. Its original Python executable could not be launched in the handover environment, so it is not presented as a portable dependency. The optional Python package versions above were read from its installed metadata, not freshly installed or tested here.

## A. Rebuild from the included conversion project

Extract the ZIP to a reasonably short local path such as `C:\G29Handover` and open PowerShell in the extracted pack's **conversion** directory. Close any Unity Editor already using this project. The launcher starts a separate Editor process and the editor methods close it when finished.

Set the two paths for your machine (examples below are placeholders):

```powershell
$env:G29_PYTHON = 'C:\Path\To\Python\python.exe'
$env:G29_UNITY = 'C:\Path\To\2019.4.40f1\Editor\Unity.exe'
```

Python is used by setup to refresh shared parts even when the Unity project already exists. No third-party Python packages are needed for that step.

Then run:

Before the first run, choose the source state. By default setup uses the tools version, including its additional, unverified cab-light fix. To use the **saved Unity project's script state** instead, run the following in a separate working copy **before setup overwrites `Assets/Editor`**:

```powershell
Copy-Item -LiteralPath '.\unity\G29_CCL\Assets\Editor\CclLocoBuild.cs' -Destination '.\tools\unity\CclLocoBuild.cs'
```

The exact historical difference is in `verification/SOURCE_CORE_DIVERGENCE.diff`. The other five editor scripts are identical between the two locations. This selects a source snapshot; it does not guarantee binary-identical output.

Build with:

```powershell
.\tools\run_unity.ps1 -Method G29Config.Build -Out builds\author-test1
```

The copied launcher checks the executable path, keeps output inside `conversion`, and requires a new output directory. Setup refreshes editor scripts from `tools/unity`. The builder regenerates its working and CCL car assets in the copied project. Results go to `builds/author-test1`, including the pack, report, Editor log and inspection renders.

Review `build_report.txt` for zero warnings and no `EXCEPTION`, confirm the pack files exist, and inspect the renders. The launcher treats exception strings in the Editor log as requiring review; a benign message can therefore stop the wrapper even when a bundle was produced. This deliberate review flag does not modify the original builder.

The historical notes used windowed execution because of licensing behaviour on that machine. The handover launcher retains normal Editor execution without `-batchmode`, but starts its window hidden. Resolve licence/activation problems in your own Editor before retrying with a fresh output directory; the historical notes' licensing observations are not a universal Unity rule.

You can open `unity/G29_CCL` directly in Unity 2019.4.40f1 to inspect the generated prefabs. Do not accept an accidental upgrade to a newer Editor as part of following this recipe.

## B. Reconstruct the project from the preserved exports

Work in a **second extracted copy** of the handover. In that copy, rename `conversion/unity/G29_CCL` to `G29_CCL_saved` before running:

```powershell
.\tools\setup_build_project.ps1
```

Setup only creates the project when `unity/G29_CCL` is absent; when it already exists, it refreshes shared G29 parts and editor scripts. The new project is copied from `assetripper/export_2019/ExportedProject`, repaired and augmented with FoxTrucks, G29 parts and CarCreator. Run the build command from section A after setup.

Do not use the original scripts in `reference/original-tools` as launchers: they contain historical machine paths and some overwrite existing outputs.

## C. Re-extract from the included packaged bundles

This is optional. Use a disposable second copy if you want to replace the standard export folders. The portable exporter deliberately refuses an existing output, so the examples below create new side-by-side folders:

```powershell
$env:G29_ASSETRIPPER = 'C:\Path\To\AssetRipper.GUI.Free.exe'
.\tools\export_assetripper.ps1 -Target 2019.4.40f1 -OutName author_g29
.\tools\export_assetripper.ps1 -Target 2019.4.40f1 -OutName author_fox -Bundle (Join-Path $PWD 'source\FoxTrucks\Bundle')
.\tools\export_assetripper.ps1 -Target 2019.4.40f1 -OutName author_parts -Bundle (Join-Path $PWD 'source\extracted\LLW Generic Locomotive Catalog\g29parts\bundle')
```

Run these sequentially; they share a local port and log filenames. Change `-Port` if 47831 is already in use. The script drives the AssetRipper 2.0 settings form/API recorded in the original workflow; a different release may require adapting those endpoints or fields.

To build from the fresh exports in that disposable copy, rename the old export directories to preserve them, then rename `author_g29`, `author_fox` and `author_parts` to `export_2019`, `export_fox` and `export_g29parts`. Follow section B to create a new project. All of these operations should stay in your working copy.

## D. Regenerate or inspect intermediate data

The definition generator command, run from `conversion`, is:

```powershell
& $env:G29_PYTHON .\tools\gen_defs.py `
  '.\source\extracted\LLW Generic Locomotive Catalog\ls-260-g29\Definitions.json' `
  '.\assetripper\export_2019\ExportedProject\Assets' `
  '.\tools\unity\G29Defs.cs' `
  'G29Defs=ls-260-g29=Assets/mslmike/ls-260-g29.prefab' `
  'G29TenderDefs=lt-260-g29=Assets/squam/lt-260-g29.prefab'
```

This overwrites the generated definition file in your working copy. Setup will synchronize it to `Assets/Editor` at the next run. Use the existing generated file if you are only inspecting or rebuilding the unchanged handover.

For a read-only binding analysis (no `--apply`):

```powershell
& $env:G29_PYTHON .\tools\resolve_clip_paths.py `
  '.\assetripper\export_2019\ExportedProject\Assets' '.\analysis\author_clip_paths.txt'
```

Probe commands use the same launcher and each needs a fresh output folder:

```powershell
.\tools\run_unity.ps1 -Method G29Probe.RunAll -Out analysis\author-probe
.\tools\run_unity.ps1 -Method G29Probe.Floor -Out analysis\author-floor
.\tools\run_unity.ps1 -Method G29Probe.Faces -Out analysis\author-faces
```

The retained `analysis` folder and test4 renders let you study the existing findings without running anything.

## E. Optional installation and support mods

Close DV. Install your CCL runtime separately. You may manually copy `builds/author-test1/LLW G-29` to your game's Mods directory, or use the copied install helper with an explicit destination:

```powershell
.\tools\install_build.ps1 -Name author-test1 -ModsPath 'D:\YourGame\Derail Valley\Mods'
```

It validates the new build before backing up any existing `LLW G-29` folder into this working copy's `rollback`. `-Remove` backs up an installed G29 without copying a replacement. Nothing in setup or the Unity build invokes installation.

The historical test environment also contained the two helpers in `support`. Their READMEs explain their wider use across CCL locomotives. To recompile one, open its folder and run `Build.ps1 -GameRoot 'D:\YourGame\Derail Valley'`; this requires the referenced DLLs from your own game/UMM installation. Add `-Install` only when deliberately installing it. These support launchers now require an explicit game root; historical versions are under `reference`.

The support helpers are retained as personal experimental tools. Their presence in this handover does not establish that they are required by every G29 environment or that their effect is confined to G29. Inspect their code and [test status](STATUS.md) when evaluating the conversion.
