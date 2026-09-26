param(
    [Parameter(Mandatory=$true)][ValidateSet('c21','s16')][string]$Pilot,
    [Parameter(Mandatory=$true)][string]$Run,
    [string]$Unity = 'B:\Games\Unity 2019.4.40f1\Editor\Unity.exe',
    [int]$TimeoutMin = 15
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
if ($Run -notmatch '^[A-Za-z0-9_-]+$') { throw 'Run must be a single folder name.' }
if (!(Test-Path -LiteralPath $Unity -PathType Leaf)) { throw "Missing Unity: $Unity" }
if ((Get-Item -LiteralPath $Unity).VersionInfo.ProductVersion -notlike '2019.4.40*') { throw 'Use Unity 2019.4.40f1.' }
$project = Join-Path $root ('unity\' + $Pilot.ToUpperInvariant() + '_CCL')
if (!(Test-Path -LiteralPath "$project\Assets\PilotProbeInput.json")) { throw 'Prepare the pilot first.' }
if (Test-Path -LiteralPath "$project\Temp\UnityLockfile") { throw 'Project may be open; close its Editor before running a probe.' }
$outDir = [IO.Path]::GetFullPath((Join-Path $root "analysis\$Pilot\$Run"))
if (!$outDir.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Output escaped workspace.' }
if (Test-Path -LiteralPath $outDir) { throw 'Use a new Run name to preserve previous evidence.' }
New-Item -ItemType Directory -Path $outDir | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'unity\PilotProbe.cs') -Destination "$project\Assets\Editor\PilotProbe.cs" -Force
$previous = $env:LLW_PROBE_OUT
try {
    $env:LLW_PROBE_OUT = $outDir
    $process = Start-Process -FilePath $Unity -WindowStyle Hidden -WorkingDirectory $root -PassThru -ArgumentList @(
        '-projectPath', "`"$project`"", '-executeMethod', 'PilotProbe.Run', '-logFile', "`"$outDir\unity_editor.log`"")
    $process.Id | Set-Content -LiteralPath "$outDir\unity.pid"
    if (!$process.WaitForExit($TimeoutMin * 60000)) { $process.Kill(); throw 'Unity probe timed out.' }
    if ($process.ExitCode -ne 0) { throw "Unity exited $($process.ExitCode); inspect $outDir\unity_editor.log" }
    $resultPath = Join-Path $outDir 'result.json'
    if (!(Test-Path -LiteralPath $resultPath)) { throw 'Probe did not produce its completion result.' }
    $result = Get-Content -Raw -LiteralPath $resultPath | ConvertFrom-Json
    if ($result.status -ne 'passed') { throw 'Source validation failed; inspect probe_report.txt.' }
    $errors = Select-String -LiteralPath "$outDir\unity_editor.log" -Pattern 'error CS\d+|Scripts have compiler errors|executeMethod class|No valid Unity Editor license'
    if ($errors) { throw 'Unity log contains compilation or launch errors.' }
    Write-Output "Source inspection passed: $outDir"
} finally { $env:LLW_PROBE_OUT = $previous }
