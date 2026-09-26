# Install or remove a LLW G-29 test build in the game's Mods folder (the pack holds both the loco and its tender).
#   powershell -File install_build.ps1 -Name test1     (install; backs up any existing Mods\LLW G-29 first)
#   powershell -File install_build.ps1 -Remove          (remove; backs it up first)
param([string]$Name = 'test1', [switch]$Remove, [string]$Pack = 'LLW G-29')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$mods = 'B:\SteamLibrary\steamapps\common\Derail Valley\Mods'
$target = Join-Path $mods $Pack
$rollback = Join-Path $root 'rollback'

if (Test-Path $target) {
    New-Item -ItemType Directory -Force $rollback | Out-Null
    $bak = Join-Path $rollback ("$Pack " + (Get-Date -Format 'yyyy-MM-dd_HHmmss'))
    Move-Item $target $bak
    "backed up $target -> $bak"
}
if ($Remove) { "removed $Pack from Mods"; return }

$src = Join-Path $root "builds\$Name\$Pack"
if (-not (Test-Path (Join-Path $src 'ccl_bundle'))) { throw "no ccl_bundle in $src" }
Copy-Item $src $target -Recurse
Get-ChildItem $target | ForEach-Object { "{0,-24} {1,12:N0}  {2}" -f $_.Name, $_.Length, (Get-FileHash $_.FullName -Algorithm SHA256).Hash.Substring(0, 16) }
"installed $Name -> $target"

