# Headless AssetRipper export of the RR bundle to a Unity 2019.4.40f1 project (the TargetVersion trick in the guide).
#   powershell -File export_assetripper.ps1 [-Target 2019.4.40f1] [-OutName export_2019]
param([string]$Target = '2019.4.40f1', [string]$OutName = 'export_2019', [int]$Port = 47831, [string]$Bundle = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot 'handover_config.ps1')
$exe = $G29AssetRipper
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Set G29_ASSETRIPPER to AssetRipper.GUI.Free.exe.' }
if ($OutName -notmatch '^[A-Za-z0-9_-]+$') { throw 'OutName must be a single folder name.' }
$bundle = if ($Bundle) { $Bundle } else { Join-Path $root 'source\extracted\LLW Generic Locomotive Catalog\ls-260-g29\bundle' }
$outDir = Join-Path $root "assetripper\$OutName"
$logDir = Join-Path $root "analysis\exports\$OutName"
$base = "http://127.0.0.1:$Port"
if (-not (Test-Path -LiteralPath $bundle -PathType Leaf)) { throw "Missing bundle: $bundle" }
if (Test-Path -LiteralPath $outDir) { throw 'Output already exists. Use a new OutName; preserved exports are never deleted.' }
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$p = Start-Process $exe -ArgumentList '--headless', '--port', $Port -PassThru -WindowStyle Hidden -WorkingDirectory $root `
    -RedirectStandardOutput (Join-Path $logDir 'assetripper.log') -RedirectStandardError (Join-Path $logDir 'assetripper.err.log')
$p.Id | Set-Content (Join-Path $logDir 'pid.txt')
try {
    for ($i = 0; $i -lt 60; $i++) {
        try { Invoke-WebRequest "$base/" -UseBasicParsing -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep 1 }
    }
    Invoke-WebRequest "$base/Reset" -Method Post -UseBasicParsing | Out-Null

    # Re-post the settings form as a browser would: current select values, checked boxes, TargetVersion overridden
    $html = (Invoke-WebRequest "$base/Settings/Edit" -UseBasicParsing).Content
    $html | Set-Content (Join-Path $logDir 'settings_form.html') -Encoding utf8
    $form = @{}
    foreach ($m in [regex]::Matches($html, '<input[^>]*>')) {
        $t = $m.Value
        $name = [regex]::Match($t, 'name="([^"]+)"').Groups[1].Value
        if (-not $name -or $t -match 'disabled') { continue }
        if ($t -match 'type="checkbox"') { if ($t -match 'checked') { $form[$name] = '' } }
        else { $form[$name] = [regex]::Match($t, 'value="([^"]*)"').Groups[1].Value }
    }
    foreach ($m in [regex]::Matches($html, '(?s)<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>')) {
        $sel = [regex]::Match($m.Groups[2].Value, '<option[^>]*value="([^"]*)"[^>]*selected')
        if ($sel.Success) { $form[$m.Groups[1].Value] = $sel.Groups[1].Value }
    }
    $form['TargetVersion'] = $Target
    Invoke-WebRequest "$base/Settings/Update" -Method Post -Body $form -UseBasicParsing | Out-Null

    Invoke-WebRequest "$base/LoadFile" -Method Post -Body @{ Path = $bundle } -UseBasicParsing -TimeoutSec 600 | Out-Null
    Invoke-WebRequest "$base/Export/UnityProject" -Method Post -Body @{ Path = $outDir } -UseBasicParsing -TimeoutSec 1800 | Out-Null
} finally {
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
}
if (-not (Test-Path -LiteralPath (Join-Path $outDir 'ExportedProject\Assets'))) { throw 'Export did not produce an Assets directory.' }
if (-not (Select-String -LiteralPath (Join-Path $logDir 'assetripper.log') -SimpleMatch 'Finished post-export' -Quiet)) { throw 'AssetRipper did not report a completed export.' }
Select-String -Path (Join-Path $logDir 'assetripper.log') -Pattern 'TargetVersion|Exporting to Unity version|Finished|error' | Select-Object -Last 10 | ForEach-Object Line
"prefabs: " + (Get-ChildItem (Join-Path $outDir 'ExportedProject\Assets') -Recurse -Filter *.prefab | ForEach-Object { $_.FullName.Substring($outDir.Length) }) -join "`n  "


