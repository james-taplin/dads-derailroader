param(
    [string]$Python = "python",
    [string]$BuildRoot = (Join-Path $env:TEMP "derailroader-release")
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:PYTHONPATH = "$repo\src;$env:PYTHONPATH"

& $Python -m PyInstaller --noconfirm --clean --onedir --windowed `
    --name Derailroader `
    --paths "$repo\src" `
    --add-data "$repo\src\rr2dv;rr2dv" `
    --add-data "$repo\tooling;tooling" `
    --distpath "$BuildRoot\dist" `
    --workpath "$BuildRoot\work" `
    --specpath "$BuildRoot" `
    "$repo\scripts\derailroader_launcher.py"

if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
Write-Output "Windows app: $BuildRoot\dist\Derailroader\Derailroader.exe"
