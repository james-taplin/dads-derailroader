"""Package kit source and optional asset-free receipts using explicit allowlists."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

HERE = Path(__file__).resolve().parent
SOURCE = ('README.md', 'GaugeProbe.cs', 'FleetGaugeFit.cs', 'run.py', 'test_kit.py', 'package.py', 'LICENSE')
RESULTS = ('report.html', 'gauges.csv', 'summary.json', 'result.json')


def package(output, results=None):
    files = {name: HERE/name for name in SOURCE}
    # In checkout the project licence lives two levels above tools/.
    if not files['LICENSE'].is_file():
        files['LICENSE'] = HERE.parents[1]/'LICENSE'
    if results:
        files.update({'baseline/'+name: results/name for name in RESULTS})
    missing = [str(p) for p in files.values() if not p.is_file()]
    if missing:
        raise ValueError('Missing files: '+', '.join(missing))
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError('Refusing to overwrite an existing kit ZIP')
    manifest = {name: hashlib.sha256(p.read_bytes()).hexdigest() for name, p in files.items()}
    with ZipFile(output, 'w', ZIP_DEFLATED) as z:
        for name, path in files.items():
            z.write(path, 'Cab-Gauge-Kit/'+name)
        z.writestr('Cab-Gauge-Kit/SHA256.json', json.dumps(manifest, indent=2))
    with ZipFile(output) as z:
        assert z.testzip() is None
        for name, digest in manifest.items():
            assert hashlib.sha256(z.read('Cab-Gauge-Kit/'+name)).hexdigest() == digest
    print(output.resolve())


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--results', type=Path)
    a=p.parse_args()
    package(a.output, a.results)
