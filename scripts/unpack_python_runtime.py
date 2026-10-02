"""Expand PyInstaller's standard-library ZIP into its already searched runtime directory."""
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
import sys


def unpack(app: Path) -> None:
    runtime = app / '_internal'
    archive = runtime / 'base_library.zip'
    if not archive.is_file():
        raise RuntimeError('Expected fresh PyInstaller base_library.zip is missing')
    with ZipFile(archive) as z:
        files = []
        for item in z.infolist():
            name = PurePosixPath(item.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in item.filename or ':' in item.filename:
                raise ValueError('Unsafe Python runtime archive path')
            if item.is_dir():
                continue
            target = runtime / item.filename
            if not target.resolve().is_relative_to(runtime.resolve()) or target.exists():
                raise ValueError(f'Python runtime extraction collision: {item.filename}')
            files.append((target, z.read(item)))
    for target, data in files:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    # The bootloader also searches _internal; Python finds these .pyc modules there.
    archive.unlink()
    print(f'Expanded {len(files)} Python runtime files; no base_library.zip retained')


if __name__ == '__main__':
    unpack(Path(sys.argv[1]))
