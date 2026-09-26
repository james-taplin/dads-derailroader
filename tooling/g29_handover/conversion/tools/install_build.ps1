# Optional manual installation only. No game path is assumed. Close DV first.
# Historical version is retained in reference/original-tools.
param([Parameter(Mandatory=$true)][string]$ModsPath, [string]$Name = 'handover-test', [switch]$Remove)
$ErrorActionPreference = 'Stop'
if ($Name -notmatch '^[A-Za-z0-9_-]+$') { throw 'Name must be a single build folder name.' }
$root = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$mods = (Resolve-Path -LiteralPath $ModsPath).Path.TrimEnd('\')
if (-not (Test-Path -LiteralPath (Join-Path (Split-Path $mods -Parent) 'DerailValley_Data') -PathType Container)) { throw 'ModsPath must be inside your Derail Valley installation.' }
$target = [IO.Path]::GetFullPath((Join-Path $mods 'LLW G-29'))
if ((Split-Path $target -Parent) -ne $mods) { throw 'Target containment check failed.' }
$src = Join-Path $root "builds\$Name\LLW G-29"
if (-not $Remove) {
    foreach ($file in 'ccl_bundle','Info.json') { if (-not (Test-Path -LiteralPath (Join-Path $src $file) -PathType Leaf)) { throw "Missing build file: $file" } }
}
if (Test-Path -LiteralPath $target) {
    $rollback = Join-Path $root 'rollback'
    New-Item -ItemType Directory -Force -Path $rollback | Out-Null
    $backup = [IO.Path]::GetFullPath((Join-Path $rollback ('LLW G-29 ' + (Get-Date -Format 'yyyy-MM-dd_HHmmss_fff'))))
    if (-not $backup.StartsWith($root + '\rollback\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Backup containment check failed.' }
    Move-Item -LiteralPath $target -Destination $backup
    Write-Host "Previous pack backed up to $backup"
}
if (-not $Remove) { Copy-Item -LiteralPath $src -Destination $target -Recurse; Write-Host "Installed $Name to $target" }
