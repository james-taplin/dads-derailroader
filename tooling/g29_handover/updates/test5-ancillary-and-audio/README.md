# G29 test5 — ancillary animations and Railroader sounds

This update contains the later G29 source snapshot, original test5 notes/report/renders, and a recipient-facing audio extraction helper. The existing `conversion` project and test4 built pack remain the historical baseline. No new archive was created and no game was modified.

**Latest documented development:** test5 / 0.5.0, built and installed according to the project log, with zero build warnings and **in-game testing still pending**. The sources implement cab doors, four sliding sashes, roof vent, tender water hatch, lubricator animation and four Railroader audio loops. The shared core incorporates ALCo 1610 work, including the bound-ancestor animation-region fix. Oil-burner features in that core are background capability, not a change to the G29's coal firing.

## Files

| Location | Contents |
|---|---|
| `source_tools` | Exact current G29 tools copied from Claudes Place, including six editor C# sources and original audio helpers. Historical PowerShell machine paths remain in this evidence snapshot. |
| `tools/extract_rr_audio.py` | Adapted extractor with explicit Railroader root/output arguments and checks for four expected WAV payloads. |
| `tools/loopify_wav.py` | Unchanged historical offline loop processor. Requires NumPy. |
| `evidence` | Original test5 notes, data sheet, build report, Editor log and renders. |
| `G29_PROJECT_LOG_EXCERPT.md` | Updated original G29 project-log entry. |
| `previous-handover-docs` | Previous root documents and verification manifest/report. Their old relative links are historical, not the current navigation. |

Raw Railroader recordings and the compiled test5 bundle containing them are not added to this author-method handover. The recipe obtains those inputs from the recipient's installation. The extraction method is included without treating game recordings as original LLW assets. The original notes' personal-use description is retained as source context.

## Continue from the test4 project with test5 sources

Make a **separate working copy of the whole handover folder** first. Commands below assume PowerShell is open at that working copy's root. Keep using the portable launchers in `conversion/tools`; do not overwrite them with the historical PowerShell scripts in `source_tools`.

Set your tool paths and prepare the project:

```powershell
$env:G29_PYTHON = 'C:\Path\To\Python\python.exe'
$env:G29_UNITY = 'C:\Path\To\2019.4.40f1\Editor\Unity.exe'
& .\conversion\tools\setup_build_project.ps1
Copy-Item -Path '.\updates\test5-ancillary-and-audio\source_tools\unity\*.cs' -Destination '.\conversion\tools\unity' -Force
```

Copy the complete matching set of six C# files. Do not mix a new `G29Config.cs` with the older core or configuration types. Setup refreshes `Assets/Editor` from this directory at the next build. This supersedes the earlier four-line cab-light source-selection caveat for the test5 route: its recorded build report contains an `ItemLightProxy`, though it is not yet in-game verified.

Audio preparation needs UnityPy and NumPy in the selected Python environment. The historical environment recorded UnityPy 1.25.3 and NumPy 2.5.3; these are recorded versions, not a claim of compatibility with arbitrary future installs. No virtual environment is bundled.

```powershell
$audioTools = '.\updates\test5-ancillary-and-audio\tools'
$raw = '.\conversion\source\audio\raw'
$ready = '.\conversion\source\audio\dv'
& $env:G29_PYTHON "$audioTools\extract_rr_audio.py" --railroader-root 'D:\YourGame\Railroader' --out $raw
if ($LASTEXITCODE -ne 0) { throw 'Audio extraction failed.' }
New-Item -ItemType Directory -Force -Path $ready | Out-Null
& $env:G29_PYTHON "$audioTools\loopify_wav.py" "$raw\wh-3-cnj.wav" "$ready\g29_whistle_cnj3.wav"
if ($LASTEXITCODE -ne 0) { throw 'Whistle processing failed.' }
& $env:G29_PYTHON "$audioTools\loopify_wav.py" "$raw\2024-07-07_CNR_Brass_Rope_Bell-Geordie-Cleaned.wav" "$ready\g29_bell_rope.wav" --asis
if ($LASTEXITCODE -ne 0) { throw 'Bell processing failed.' }
& $env:G29_PYTHON "$audioTools\loopify_wav.py" "$raw\2021-06-19-TVRM-Compressor.wav" "$ready\g29_airpump.wav"
if ($LASTEXITCODE -ne 0) { throw 'Compressor processing failed.' }
& $env:G29_PYTHON "$audioTools\loopify_wav.py" "$raw\2021-06-19-TVRM-Dynamo.wav" "$ready\g29_dynamo.wav"
if ($LASTEXITCODE -ne 0) { throw 'Dynamo processing failed.' }
$audioAssets = '.\conversion\unity\G29_CCL\Assets\G29_audio'
New-Item -ItemType Directory -Force -Path $audioAssets | Out-Null
Copy-Item -Path "$ready\*.wav" -Destination $audioAssets -Force
& .\conversion\tools\run_unity.ps1 -Method G29Config.Build -Out builds\author-test5
```

The baseline setup does not copy audio automatically, so the explicit `Assets/G29_audio` step is required. The newer snapshot setup shows how Claude automated that copy. WAV assets receive Unity metadata on import; the config references their filenames. A fresh-project reconstruction must perform setup before copying the audio. Use a new build output name each time.

The unchanged loop processor expects integer PCM WAV input with 16- or 32-bit sample width. Its 4096-frame crossfade assumes a clip longer than 8192 frames; it is specialized to these recordings, not a general audio converter. `--asis` skips the crossfade but still rewrites to 16-bit PCM, so the bell output need not be byte-identical to the raw input.

To investigate the animations while retaining DV sounds, in a separate working copy replace `c.RemoveVanillaSounds` with an empty string array and the four-entry `c.Sounds` list with an empty `List<SoundCfg>`. Do not remove vanilla systems while omitting their replacements. This is an optional adaptation, not the historical test5 build.

## Test before treating this as complete

Use `evidence/TEST_NOTES.md`: whistle sustain/release/clicks/loudness; bell fade; compressor and dynamo gating; all doors/sashes/vent/hatch travel and collisions; saved positions and outside/interior-unloaded appearance; lubricator motion. Save-state wiring and exterior rendering are implemented intentions, not yet demonstrated by an in-game test in the supplied record.
