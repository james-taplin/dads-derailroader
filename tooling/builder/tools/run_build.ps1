param(
    [Parameter(Mandatory=$true)][ValidateSet('g29','c21')][string]$Profile,
    [Parameter(Mandatory=$true)][string]$Run,
    [switch]$Frozen,
    [switch]$Tests,
    [switch]$Share
)
$ErrorActionPreference='Stop'
$workspaceRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$machine=Get-Content -LiteralPath (Join-Path $workspaceRoot 'machine.local.json') -Raw | ConvertFrom-Json
$buildArgs=@((Join-Path $PSScriptRoot 'build.py'),$Profile,$Run)
if($Frozen){$buildArgs+='--frozen'}
if($Tests){$buildArgs+='--tests'}
if($Share){$buildArgs+='--share'}
& $machine.python @buildArgs
if($LASTEXITCODE -ne 0){throw "Build/validation failed with exit code $LASTEXITCODE"}
