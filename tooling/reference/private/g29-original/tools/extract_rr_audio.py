import UnityPy, os, sys
out = sys.argv[1]
jobs = [
    (r'B:\SteamLibrary\steamapps\common\Railroader\Railroader_Data\StreamingAssets\AssetPacks\audio.whistles01\Bundle', {'wh-3-cnj'}),
    (r'B:\SteamLibrary\steamapps\common\Railroader\Railroader_Data\sharedassets3.assets', {'2024-07-07_CNR_Brass_Rope_Bell-Geordie-Cleaned', '2021-06-19-TVRM-Compressor', '2021-06-19-TVRM-Dynamo'}),
]
for src, names in jobs:
    env = UnityPy.load(src)
    for o in env.objects:
        if o.type.name != 'AudioClip': continue
        d = o.read()
        if d.m_Name not in names: continue
        for fn, data in d.samples.items():
            path = os.path.join(out, d.m_Name + '.wav')
            open(path, 'wb').write(data)
            print('wrote', path, len(data))
