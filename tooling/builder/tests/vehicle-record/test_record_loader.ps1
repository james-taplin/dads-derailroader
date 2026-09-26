param([string]$Record)
$ErrorActionPreference='Stop'
$workspaceRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$machine=Get-Content -LiteralPath (Join-Path $workspaceRoot 'machine.local.json') -Raw | ConvertFrom-Json
$sourceRoot=Join-Path $workspaceRoot 'builder\tools\unity'
$unityData=Join-Path (Split-Path -Parent $machine.unity) 'Data'
$compiler=Join-Path $unityData 'Tools\Roslyn\csc.exe'
$mono=Join-Path $unityData 'MonoBleedingEdge\bin\mono.exe'
$managed=Join-Path $unityData 'Managed'
$engine=Join-Path $managed 'UnityEngine'
$framework=Join-Path $unityData 'MonoBleedingEdge\lib\mono\4.7.1-api'
$argsList=@('/nologo','/langversion:7.3','/target:exe',('/out:'+(Join-Path $PSScriptRoot 'RecordContractTests.exe')),('/reference:'+(Join-Path $engine 'UnityEngine.CoreModule.dll')),('/reference:'+(Join-Path $engine 'UnityEditor.dll')),('/reference:'+(Join-Path $unityData 'MonoBleedingEdge\lib\mono\4.7.1-api\Facades\netstandard.dll')),(Join-Path $sourceRoot 'LlwVehicleRecord.cs'),(Join-Path $PSScriptRoot 'LlwVehicleRecordContractTests.cs'),(Join-Path $sourceRoot 'LocoConfig.cs'),(Join-Path $sourceRoot 'LlwCatalogConfig.cs'))
$argsList += @('mscorlib.dll','System.dll','System.Core.dll') | ForEach-Object { '/reference:'+(Join-Path $framework $_) }
$argsList += '/reference:'+(Join-Path $engine 'UnityEngine.JSONSerializeModule.dll')
$argsList += '/reference:'+(Join-Path $engine 'UnityEngine.dll')
& $compiler @argsList
if($LASTEXITCODE -ne 0){throw 'Compilation failed'}
$priorMonoPath=$env:MONO_PATH
try {
    $env:MONO_PATH=$engine+';'+$managed
    $runArgs=@((Join-Path $PSScriptRoot 'RecordContractTests.exe'))
    if($Record){$runArgs += $Record}
    & $mono @runArgs
    if($LASTEXITCODE -ne 0){throw 'Contract tests failed'}
} finally { $env:MONO_PATH=$priorMonoPath }
