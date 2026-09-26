param(
    [Parameter(Mandatory=$true)][ValidateSet('g29','c21')][string]$Profile,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9_-]+$')][string]$Run,
    [switch]$Tests,
    [switch]$Share,
    [string]$Python = 'C:\Users\james\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
)
$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$taskProject = Join-Path $taskRoot ('unity\' + $Profile.ToUpper() + '_CCL')
$taskOutput = Join-Path $taskRoot ('builds\' + $Profile + '\' + $Run)
if (Test-Path -LiteralPath $taskOutput) { throw 'Choose a fresh run name; evidence is never overwritten.' }
& $Python (Join-Path $PSScriptRoot 'prepare.py') $Profile
if ($LASTEXITCODE -ne 0) { throw 'Project preparation failed.' }
New-Item -ItemType Directory -Path $taskOutput | Out-Null
Copy-Item -LiteralPath (Join-Path $taskProject 'unified-scripts.json') -Destination (Join-Path $taskOutput 'source_hashes.json')
$taskMethod = $Profile.ToUpper() + 'Config.Build'
if ($Tests) { $taskMethod = 'UnifiedBuilderTests.Run' }
$taskOldOutput = $env:CCL_BUILD_OUT
$taskOldProbe = $env:RLW_PROBE_OUT
$taskOldCatalog = $env:CCL_CATALOG_RECORD
$taskOldShare = $env:G29_SHARE
try {
    $env:CCL_BUILD_OUT = $taskOutput
    $env:RLW_PROBE_OUT = $taskOutput
    $env:G29_SHARE = if ($Share) { '1' } else { '0' }
    $taskId = if ($Profile -eq 'g29') { 'ls-260-g29' } else { 'ls-280-c21' }
    $env:CCL_CATALOG_RECORD = Join-Path $taskRoot ('catalog\' + $taskId + '.json')
    Copy-Item -LiteralPath $env:CCL_CATALOG_RECORD -Destination (Join-Path $taskOutput 'catalog_record.json')
    $taskProcess = Start-Process -FilePath 'B:\Games\Unity 2019.4.40f1\Editor\Unity.exe' -WindowStyle Hidden -WorkingDirectory $taskRoot -ArgumentList @(
        '-projectPath', ('"' + $taskProject + '"'), '-executeMethod', $taskMethod,
        '-logFile', ('"' + (Join-Path $taskOutput 'unity_editor.log') + '"')) -PassThru
    @{project=$taskProject;method=$taskMethod;pid=$taskProcess.Id;started=(Get-Date -Format o);output=$taskOutput;share=[bool]$Share} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskOutput 'launch.json')
    Write-Output "Started $taskMethod (PID $($taskProcess.Id)): $taskOutput"
} finally { $env:CCL_BUILD_OUT=$taskOldOutput; $env:RLW_PROBE_OUT=$taskOldProbe; $env:CCL_CATALOG_RECORD=$taskOldCatalog; $env:G29_SHARE=$taskOldShare }
