# Create unity\G29_CCL from the AssetRipper export (version-changed to 2019.4.40f1) + CarCreator 3.1.9.
# Clip paths are restored from their CRC32 hashes against every prefab (resolve_clip_paths.py).
# Safe to re-run: it only creates the project if missing, then refreshes the Editor scripts.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$src = Join-Path $root 'assetripper\export_2019\ExportedProject'
$dst = Join-Path $root 'unity\G29_CCL'
. (Join-Path $PSScriptRoot 'handover_config.ps1')
$py = $G29Python
if (-not (Test-Path -LiteralPath $py -PathType Leaf)) { throw 'Set G29_PYTHON to a Python executable (see REBUILD.md).' }
$carCreator = Join-Path $root 'tooling\CarCreator_3.1.9.unitypackage'

if (-not (Test-Path $dst)) {
    robocopy $src $dst /E /NFL /NDL /NJH /NJS /NP /XD (Join-Path $src 'Temp') (Join-Path $src 'Logs') (Join-Path $src 'Library') | Out-Null
    if ($LASTEXITCODE -ge 8) { throw 'Project copy failed.' }

    @"
m_EditorVersion: 2019.4.40f1
m_EditorVersionWithRevision: 2019.4.40f1 (ffc62b691db5)
"@ | Set-Content (Join-Path $dst 'ProjectSettings\ProjectVersion.txt') -Encoding ascii

    # Asset Database v2 (as 2019.4 creates it): avoids the modal 'Asset Database Version Upgrade' prompt
    $es = Join-Path $dst 'ProjectSettings\EditorSettings.asset'
    $t = Get-Content $es -Raw
    if ($t -notmatch 'm_AssetPipelineMode') {
        $t = $t -replace '(  m_SerializationMode: 2\r?\n)', "`$1  m_AssetPipelineMode: 1`n"
    }
    Set-Content $es $t -Encoding ascii -NoNewline

    # TextMeshPro + uGUI (CCL.Types references Unity.TextMeshPro); drop URP/2022-only packages if AssetRipper listed any
    $manifestPath = Join-Path $dst 'Packages\manifest.json'
    $m = Get-Content $manifestPath -Raw | ConvertFrom-Json
    foreach ($n in @($m.dependencies.PSObject.Properties.Name)) {
        if ($n -match 'render-pipelines|shadergraph|visualeffectgraph') { $m.dependencies.PSObject.Properties.Remove($n) }
    }
    $m.dependencies | Add-Member -NotePropertyName 'com.unity.textmeshpro' -NotePropertyValue '2.1.6' -Force
    $m.dependencies | Add-Member -NotePropertyName 'com.unity.ugui' -NotePropertyValue '1.0.0' -Force
    ($m | ConvertTo-Json -Depth 5) | Set-Content $manifestPath -Encoding utf8

    # real clip paths (the export only has path_0x<crc> placeholders)
    & $py (Join-Path $root 'tools\resolve_clip_paths.py') (Join-Path $src 'Assets') (Join-Path $root 'analysis\clip_paths.txt') --apply (Join-Path $dst 'Assets')
    if ($LASTEXITCODE -ne 0) { throw 'Clip restoration failed.' }

    # tender trucks (RR FoxTrucks mod, fox-truck-2s): prefab + meshes/materials/textures/shaders, no scripts
    & $py (Join-Path $root 'tools\copy_deps.py') (Join-Path $root 'assetripper\export_fox\ExportedProject\Assets') 'fox trucks\Fox-Truck-2s.prefab' (Join-Path $dst 'Assets') 'FoxTrucks'
    if ($LASTEXITCODE -ne 0) { throw 'Fox truck dependency copy failed.' }
    # CarCreator unitypackage -> Assets (asset + .meta, original GUIDs)
    & $py -c @"
import tarfile, os
t = tarfile.open(r'$carCreator', 'r:gz')
entries = {}
for m in t.getmembers():
    g, _, leaf = m.name.partition('/')
    if leaf: entries.setdefault(g, {})[leaf] = m
n = 0
for g, e in entries.items():
    path = t.extractfile(e['pathname']).read().decode().splitlines()[0]
    full = os.path.join(r'$dst', *path.split('/'))
    if 'asset' in e:
        os.makedirs(os.path.dirname(full), exist_ok=True)
        open(full, 'wb').write(t.extractfile(e['asset']).read()); n += 1
    else:
        os.makedirs(full, exist_ok=True)
    if 'asset.meta' in e:
        open(full + '.meta', 'wb').write(t.extractfile(e['asset.meta']).read())
print('CarCreator files:', n)
"@
    if ($LASTEXITCODE -ne 0) { throw 'CarCreator extraction failed.' }
}

# pack parts the loco uses by default (RR PrefabModelComponent: headlight, handrail, markers); idempotent
foreach ($part in 'headlight2', 'handrail', 'markers') {
    & $py (Join-Path $root 'tools\copy_deps.py') (Join-Path $root 'assetripper\export_g29parts\ExportedProject\Assets') "prairie\$part.prefab" (Join-Path $dst 'Assets') 'G29Parts' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'G29 part dependency copy failed.' }
}
$ed = Join-Path $dst 'Assets\Editor'
New-Item -ItemType Directory -Force $ed | Out-Null
Get-ChildItem (Join-Path $root 'tools\unity') -Filter *.cs | Copy-Item -Destination $ed -Force
"project ready: $dst"




