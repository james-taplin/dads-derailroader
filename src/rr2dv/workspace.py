"""Owned temporary workspaces: permanent deletion, with small receipts and audited output retained."""
from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

from .jsonio import read_json, sha256_file, write_json
from .safety import UnsafePath, is_link

MARKER = '.rr2dv-temporary'
LOCK = '.rr2dv-active'


def keep_files(machine) -> bool:
    # Deliberately opt-in; strings such as "false" must not enable retention.
    return machine.values.get('keepWorkFiles') is True


def checked(path: Path, root: Path) -> Path:
    root = root.absolute()
    path = path.absolute()
    if path == root or not path.is_relative_to(root) or not path.resolve().is_relative_to(root.resolve()):
        raise UnsafePath(f'workspace path outside its owner: {path}')
    for p in (path, *path.parents):
        if is_link(p):
            raise UnsafePath(f'workspace cleanup refuses linked paths: {p}')
        if p == root:
            break
    return path


def remove_tree(path: Path, root: Path) -> None:
    """Never follow a symlink/junction or delete a computed path without checking its boundary."""
    checked(path, root)
    if not path.exists():
        return
    for current, dirs, files in os.walk(path, followlinks=False):
        for name in dirs + files:
            if is_link(Path(current) / name):
                raise UnsafePath(f'workspace cleanup refuses a link: {Path(current) / name}')
    def retry_readonly(func, failed, error):
        target = checked(Path(failed), root)
        if not isinstance(error[1], PermissionError):
            raise error[1]
        target.chmod(target.stat().st_mode | stat.S_IWRITE)
        func(failed)
    shutil.rmtree(path, onerror=retry_readonly)  # direct deletion; never the Recycle Bin


class Lease:
    def __init__(self, path: Path):
        self.file = open(path / LOCK, 'a+b')
        try:
            self.file.seek(0)
            if self.file.read(1) == b'':
                self.file.write(b'0')
                self.file.flush()
            self.file.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise

    def close(self):
        self.file.close()


def begin(run):
    lease = Lease(run.path)
    write_json(run.path / MARKER, {'generator': 'rr2dv', 'run_id': run.path.name})
    return lease


def _copy_small(src: Path, dest: Path, root: Path):
    if not src.is_file():
        return
    checked(src, root)
    checked(dest, root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix == '.json':
        shutil.copyfile(src, dest)  # JSON receipts must remain complete and parseable.
        return
    # A bounded diagnostic tail, never a copy of ripped data or the Unity Library.
    with src.open('rb') as f:
        f.seek(max(0, src.stat().st_size - 2 * 1024 * 1024))
        dest.write_bytes(f.read())


def finish(run, lease: Lease) -> None:
    original = run.path
    root = original.parent
    report = root / 'reports' / original.name
    deleting = False
    try:
        checked(original, root)
        marker = read_json(original / MARKER)
        if marker != {'generator': 'rr2dv', 'run_id': original.name}:
            raise UnsafePath('temporary workspace ownership does not match')
        checked(report, root)
        report.mkdir(parents=True, exist_ok=True)
        installed = run.record.get('installed')
        if installed:
            run.record['output'] = installed
        elif not run.record.get('output') and run.record['stages']['audit']['status'] == 'done':
            built = read_json(original / 'build' / 'built.json')
            source = checked(Path(built['pack']), original)
            output = checked(root / 'output' / original.name / source.name, root)
            output.mkdir(parents=True, exist_ok=True)
            for name, digest in built['files'].items():
                if Path(name).name != name or name in ('.', '..'):
                    raise UnsafePath('invalid output filename')
                src = checked(source / name, original)
                dest = checked(output / name, root)
                shutil.copyfile(src, dest)
                if sha256_file(dest) != digest:
                    raise ValueError(f'finished pack hash mismatch: {name}')
            run.record['output'] = str(output)
        # Keep a small amount of extractor failure evidence without retaining its exported assets.
        for i, log in enumerate(sorted((original / 'extracted').glob('*/logs/assetripper.log'))[:4]):
            _copy_small(log, report / f'extractor-{i + 1}.log', root)
        for rel, dest in (
            ('run.log', 'run.log'), ('record/vehicle-record.json', 'record/vehicle-record.json'),
            ('build/vehicle-record.json', 'record/vehicle-record.json'), ('build/review.json', 'review.json'),
            ('build/blocks.json', 'blocks.json'), ('build/out/build_report.txt', 'build_report.txt'),
            ('build/out/prep.json', 'prep.json'), ('audit/summary.json', 'audit.json'),
            ('geometry-review.json', 'geometry-review.json'),
            ('geometry-review-proposed.json', 'geometry-review-proposed.json'), ('build/out/endbeam-survey.json', 'endbeam-survey.json'),
            ('review-questions.json', 'review-questions.json'), ('prebuild-review.json', 'prebuild-review.json'),
            ('rebuild.json', 'rebuild.json'),
            # Measurements only (transform paths, radii, ray hits), no ripped assets: blocks point the user at them.
            ('probe/probe.json', 'probe/probe.json'), ('probe/result.json', 'probe/result.json'),
            ('unity/project/Assets/Rr2dv/ProbeInput.json', 'probe/probe-input.json'),
            ('probe/unity-1.log', 'probe.log'), ('build/out/unity-1.log', 'build.log'),
            ('audit/unity-1.log', 'audit.log'),
        ):
            _copy_small(original / rel, report / dest, root)
        run.path, run.file = report, report / 'run.json'
        run.record['cleanup'] = {'status': 'pending', 'temporary_path': str(original)}
        run.save()  # Preserve the output location and receipt BEFORE deleting any intermediate files.
        lease.close()
        deleting = True
        remove_tree(original, root)
        run.record['cleanup']['status'] = 'done'
        run.log('Temporary ripped assets, Unity project and build workspace permanently deleted.')
        run.save()
    except (OSError, ValueError) as e:
        lease.close()
        run.record['cleanup'] = {'status': 'pending', 'temporary_path': str(original), 'error': str(e)}
        if deleting and original.exists():
            # rmtree can remove ownership/metadata before hitting a locked child. Restore the retry receipt.
            checked(original, root)
            write_json(original / MARKER, {'generator': 'rr2dv', 'run_id': original.name})
            write_json(original / 'run.json', run.record)
        run.log(f'Temporary cleanup pending: {e}')
        run.save()
        run._notify('cleanup', 'warning', f'Temporary cleanup pending: {e}')


def recover(root: Path) -> list[str]:
    """Retry only our marked, unlocked workspaces; never sweep legacy runs or shared caches."""
    from .runs import Run
    warnings = []
    if not root.is_dir():
        return warnings
    for path in root.iterdir():
        if is_link(path) or not path.is_dir() or not (path / MARKER).is_file():
            continue
        lease = None
        try:
            checked(path, root)
            if (path / 'unity/project/Temp/UnityLockfile').exists():
                warnings.append(f'Temporary workspace still locked by Unity: {path}')
                continue
            lease = Lease(path)
            run = Run(path)
            if run.record.get('status') == 'running':
                run.close('interrupted', 'Previous conversion was interrupted; temporary workspace reclaimed.')
            finish(run, lease)
            if run.record.get('cleanup', {}).get('status') != 'done':
                warnings.append(f'Temporary cleanup pending: {path}')
        except (OSError, ValueError, KeyError):
            if lease:
                lease.close()
            # Locked by another process or unrecognised: do not touch its files.
    return warnings
