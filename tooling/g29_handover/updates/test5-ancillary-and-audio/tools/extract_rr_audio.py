"""Extract the four test5 clips from the recipient's Railroader installation.
Handover adaptation: explicit paths and expected-sample checks.
The unchanged historical extractor is retained in ../source_tools.
"""
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--railroader-root', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    import UnityPy
    game_data = args.railroader_root / 'Railroader_Data'
    jobs = [
        (game_data / 'StreamingAssets/AssetPacks/audio.whistles01/Bundle', {'wh-3-cnj'}),
        (game_data / 'sharedassets3.assets', {'2024-07-07_CNR_Brass_Rope_Bell-Geordie-Cleaned',
          '2021-06-19-TVRM-Compressor', '2021-06-19-TVRM-Dynamo'}),
    ]
    for src, _ in jobs:
        if not src.is_file(): raise SystemExit(f'Missing input: {src}')
    wanted = set().union(*(names for _, names in jobs))
    args.out.mkdir(parents=True, exist_ok=True)
    for name in wanted:
        if (args.out / (name + '.wav')).exists():
            raise SystemExit('Use a fresh output folder; an expected output already exists.')
    found = {}
    for src, names in jobs:
        env = UnityPy.load(str(src))
        for obj in env.objects:
            if obj.type.name != 'AudioClip': continue
            clip = obj.read()
            if clip.m_Name not in names: continue
            samples = clip.samples
            if len(samples) != 1 or clip.m_Name in found:
                raise SystemExit(f'Ambiguous audio payload for {clip.m_Name}; inspect this game version.')
            data = next(iter(samples.values()))
            if not data.startswith(b'RIFF') or data[8:12] != b'WAVE':
                raise SystemExit(f'{clip.m_Name} was not decoded as WAV.')
            found[clip.m_Name] = data
    if set(found) != wanted:
        raise SystemExit('Missing clips: ' + ', '.join(sorted(wanted - set(found))))
    for name, data in sorted(found.items()):
        path = args.out / (name + '.wav')
        path.write_bytes(data)
        print(f'wrote {path} ({len(data)} bytes)')

if __name__ == '__main__':
    main()
