# Handover launcher. Historical version: ../../reference/original-tools/run_unity.ps1
param([string]$Method = 'G29Config.Build', [string]$Out = 'builds\handover-test', [int]$TimeoutMin = 40)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
. (Join-Path $PSScriptRoot 'handover_config.ps1')
if (-not (Test-Path -LiteralPath $G29Unity -PathType Leaf)) { throw 'Set G29_UNITY to the Unity 2019.4.40f1 Editor executable.' }
if ([IO.Path]::IsPathRooted($Out)) { throw 'Out must be relative to conversion.' }
$outDir = [IO.Path]::GetFullPath((Join-Path $root $Out))
if (-not $outDir.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Output must stay inside conversion.' }
if (Test-Path -LiteralPath $outDir) { throw 'Use a fresh Out folder to preserve earlier results.' }
& (Join-Path $PSScriptRoot 'setup_build_project.ps1')
New-Item -ItemType Directory -Path $outDir | Out-Null
$log = Join-Path $outDir 'unity_editor.log'
$proj = Join-Path $root 'unity\G29_CCL'
$oldProbe = $env:RLW_PROBE_OUT
$oldBuild = $env:CCL_BUILD_OUT
try {
    $env:RLW_PROBE_OUT = $outDir
    $env:CCL_BUILD_OUT = $outDir
    $p = Start-Process -FilePath $G29Unity -WindowStyle Hidden -PassThru -ArgumentList @(
        '-projectPath', "`"$proj`"", '-executeMethod', $Method, '-logFile', "`"$log`"")
    if (-not $p.WaitForExit($TimeoutMin * 60000)) { $p.Kill(); throw "Unity timed out after $TimeoutMin minutes." }
    if ($p.ExitCode -ne 0) { throw "Unity exited with code $($p.ExitCode). Inspect $log" }
    $errors = Select-String -LiteralPath $log -Pattern 'error CS\d+|Scripts have compiler errors|executeMethod class|Exception|Aborting|No valid Unity Editor license' -ErrorAction SilentlyContinue
    if ($errors) { $errors | Select-Object -First 15 | ForEach-Object { Write-Warning $_.Line }; throw 'Unity log contains errors; inspect it before treating this run as successful.' }
    if ($Method -eq 'G29Config.Build') {
        $report = Join-Path $outDir 'build_report.txt'
        if (-not (Test-Path -LiteralPath $report)) { throw 'Build report missing.' }
        $contents = Get-Content -LiteralPath $report -Raw
        if ($contents -match 'EXCEPTION' -or $contents -notmatch '(?m)^warnings: 0\s*$') { throw 'Build report did not pass; inspect exceptions and warnings.' }
        if (-not (Test-Path -LiteralPath (Join-Path $outDir 'LLW G-29\ccl_bundle'))) { throw 'Exported bundle missing.' }
    }
    Write-Host "Finished $Method. Review the reports and renders in $outDir"
} finally {
    $env:RLW_PROBE_OUT = $oldProbe
    $env:CCL_BUILD_OUT = $oldBuild
}
