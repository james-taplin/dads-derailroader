# Run an editor method in a windowed Unity 2019.4.40f1 (Personal licence refuses -batchmode).
#   powershell -File run_unity.ps1 -Method G29Probe.Run -Out analysis\probe
#   powershell -File run_unity.ps1 -Method G29Config.Build -Out builds\test1
param([string]$Method = 'G29Config.Build', [string]$Out = 'builds\test1', [int]$TimeoutMin = 40)
$root = Split-Path $PSScriptRoot -Parent
& (Join-Path $PSScriptRoot 'setup_build_project.ps1')
$outDir = Join-Path $root $Out
New-Item -ItemType Directory -Force $outDir | Out-Null
$env:RLW_PROBE_OUT = $outDir
$env:CCL_BUILD_OUT = $outDir
$log = Join-Path $outDir 'unity_editor.log'
$proj = Join-Path $root 'unity\G29_CCL'
$sw = [Diagnostics.Stopwatch]::StartNew()
$p = Start-Process 'B:\Games\Unity 2019.4.40f1\Editor\Unity.exe' -PassThru -ArgumentList @(
    '-projectPath', "`"$proj`"", '-executeMethod', $Method, '-logFile', "`"$log`"")
if (-not $p.WaitForExit($TimeoutMin * 60000)) { $p.Kill(); "TIMEOUT after $TimeoutMin min - Unity killed" }
"unity exit $($p.ExitCode) after $([int]$sw.Elapsed.TotalSeconds)s"
Select-String -Path $log -Pattern 'error CS\d+|Scripts have compiler errors|executeMethod class|Exception|Aborting|No valid Unity Editor license' |
    Select-Object -First 25 | ForEach-Object { $_.Line }

