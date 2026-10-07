"""One runtime payload policy for the source and Windows release builders."""
from pathlib import Path
import ast
import json
import argparse

ROOT = Path(__file__).resolve().parents[1]
TOOLING = frozenset(json.loads(Path(__file__).with_name('release_tooling.json').read_text()))
TABLES = {'stock_locos.json': 'locos', 'gauge_fits.json': 'profiles', 'oil_fits.json': 'profiles'}


def supported():
    tree = ast.parse((ROOT / 'src/rr2dv/stock.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SUPPORTED_STEAM' for t in node.targets):
            return frozenset(ast.literal_eval(node.value.args[0]))
    raise ValueError('Missing supported locomotive list')


def included(path):
    return not path.startswith('tooling/') or path in TOOLING


def payload(file):
    raw = file.read_bytes()
    if file.parent == ROOT / 'src/rr2dv' and file.name in TABLES:
        data = json.loads(raw)
        key = TABLES[file.name]
        keep = supported()
        missing = keep - data[key].keys()
        if missing:
            raise ValueError(f'{file.name}: missing supported profiles: {sorted(missing)}')
        data[key] = {k: v for k, v in data[key].items() if k in keep}
        return (json.dumps(data, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
    return raw


def stage(destination):
    # A fresh folder avoids accidentally preserving legacy files from a previous build.
    destination.mkdir(parents=True, exist_ok=False)
    files = [p for p in (ROOT / 'src/rr2dv').rglob('*')
             if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
    files += [ROOT / name for name in sorted(TOOLING)]
    for file in files:
        relative = file.relative_to(ROOT)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload(file))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('destination', type=Path)
    stage(parser.parse_args().destination)
