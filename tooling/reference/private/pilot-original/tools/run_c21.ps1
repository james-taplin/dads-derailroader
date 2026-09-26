param(
    [Parameter(Mandatory=$true)][string]$Run,
    [string]$Method = 'C21Config.Build'
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
if ($Run -notmatch '^[A-Za-z0-9_-]+$') { throw 'Run must be one directory name.' }
if ($Method -notmatch '^C21(Config|Probe|OilProbe)\.[A-Za-z]+$') { throw 'Only C21 entry points are allowed.' }
$project = Join-Path $root 'unity\C21_CCL'
$outDir = Join-Path $root "builds\c21\$Run"
if (Test-Path -LiteralPath $outDir) { throw 'Choose a fresh run name to preserve evidence.' }
if (Test-Path -LiteralPath "$project\Temp\UnityLockfile") { throw 'Close the C21 editor before running.' }
New-Item -ItemType Directory -Path $outDir | Out-Null
$oldBuild = $env:CCL_BUILD_OUT
$oldProbe = $env:RLW_PROBE_OUT
try {
    $env:CCL_BUILD_OUT = $outDir
    $env:RLW_PROBE_OUT = $outDir
    $proc = Start-Process -FilePath 'B:\Games\Unity 2019.4.40f1\Editor\Unity.exe' -WindowStyle Hidden -WorkingDirectory $root -ArgumentList @(
        '-projectPath', ('"' + $project + '"'), '-executeMethod', $Method, '-logFile', ('"' + "$outDir\unity_editor.log" + '"')) -PassThru
    $proc.Id | Set-Content -LiteralPath "$outDir\unity.pid"
    @{ project=$project; method=$Method; output=$outDir; pid=$proc.Id; started=(Get-Date -Format o) } | ConvertTo-Json | Set-Content -LiteralPath "$outDir\launch.json"
    Write-Output "Started $Method (PID $($proc.Id)): $outDir"
} finally { $env:CCL_BUILD_OUT=$oldBuild; $env:RLW_PROBE_OUT=$oldProbe }
