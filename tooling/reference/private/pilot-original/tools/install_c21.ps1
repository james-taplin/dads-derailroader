param([Parameter(Mandatory=$true)][string]$Run)
$ErrorActionPreference = 'Stop'
if ($Run -notmatch '^[A-Za-z0-9_-]+$') { throw 'Run must be one directory name.' }
$root = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$build = Join-Path $root "builds\c21\$Run"
$source = Join-Path $build 'LLW C-21'
$target = 'B:\SteamLibrary\steamapps\common\Derail Valley\Mods\LLW C-21'
if (Get-Process -Name DerailValley -ErrorAction SilentlyContinue) { throw 'Close Derail Valley before installing.' }
$audit = Get-Content -Raw -LiteralPath "$build\bundle_audit.json" | ConvertFrom-Json
if ($audit.status -ne 'passed') { throw 'Bundle audit must pass before installation.' }
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath "$source\ccl_bundle").Hash
if ($hash -ne $audit.bundle_sha256) { throw 'Bundle changed after its audit.' }
$info = Get-Content -Raw -LiteralPath "$source\Info.json" | ConvertFrom-Json
if ($info.Id -ne 'LLW_C21') { throw 'Not a C21 pack.' }
$backup = $null
if (Test-Path -LiteralPath $target) {
    $backup = Join-Path $root ('rollback\C21_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
    New-Item -ItemType Directory -Path (Split-Path $backup -Parent) -Force | Out-Null
    Copy-Item -LiteralPath $target -Destination $backup -Recurse
}
New-Item -ItemType Directory -Path $target -Force | Out-Null
foreach ($file in Get-ChildItem -LiteralPath $source -File) { Copy-Item -LiteralPath $file.FullName -Destination $target -Force }
foreach ($name in @('TEST_NOTES.md','DATA_SHEET.md')) { Copy-Item -LiteralPath "$build\$name" -Destination $target -Force }
if ((Get-FileHash -Algorithm SHA256 -LiteralPath "$target\ccl_bundle").Hash -ne $hash) { throw 'Installed bundle hash mismatch.' }
@{ installed=(Get-Date -Format o); target=$target; source=$source; backup=$backup; sha256=$hash; runtimeValidated=$false } | ConvertTo-Json | Set-Content -LiteralPath "$build\installation.json"
Write-Output "Installed $($info.DisplayName) $($info.Version) at $target"
