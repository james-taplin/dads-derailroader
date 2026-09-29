# Builds RR2DVControlLogger.dll and installs it into Derail Valley's Mods folder.
# Same toolchain as our DVCCLControlFix helper: .NET Framework 4 csc, /noconfig /nostdlib+ /langversion:5.
# Usage: powershell -ExecutionPolicy Bypass -File Build.ps1 [-Dv "B:\SteamLibrary\steamapps\common\Derail Valley"]
param([string]$Dv = "B:\SteamLibrary\steamapps\common\Derail Valley")
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$managed = Join-Path $Dv "DerailValley_Data\Managed"
$umm = Join-Path $managed "UnityModManager"
$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$refs = @(Get-ChildItem $managed -Filter *.dll | ForEach-Object { "/reference:" + $_.FullName })
$refs += "/reference:" + (Join-Path $umm "0Harmony.dll")
$refs += "/reference:" + (Join-Path $umm "UnityModManager.dll")
$out = Join-Path $here "RR2DVControlLogger.dll"
& $csc /noconfig /nostdlib+ /langversion:5 /target:library /optimize+ /nologo "/out:$out" $refs (Join-Path $here "Main.cs")
if ($LASTEXITCODE -ne 0) { throw "csc failed" }
$dest = Join-Path $Dv "Mods\RR2DVControlLogger"
New-Item -ItemType Directory -Force $dest | Out-Null
Copy-Item $out, (Join-Path $here "Info.json") $dest -Force
Write-Host "Installed to $dest; the log is $(Join-Path $Dv 'rr2dv-controls.log')"
