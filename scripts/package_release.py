"""Package the portable Windows build and the Python source launcher for GitHub Releases."""
from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, is_zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
SOURCE_ROOT = f"Derailroader-{VERSION}-Source"
# Every release carries the changelog, readme, wiki and docs (James, 2026-10-01: 0.4.1's source zip left them out).
READING_FILES = {"CHANGELOG.md", "README.md", "LICENSE"}
READING_FOLDERS = ("wiki/", "docs/")
SOURCE_FILES = {"Derailroader.pyw", "Launch Derailroader.bat", "pyproject.toml"} | READING_FILES
SOURCE_FOLDERS = ("src/", "tooling/") + READING_FOLDERS


def reject_nested_archives(files: list[Path]) -> None:
    """Fail rather than silently omit assets when a nested archive would ship."""
    extensions = {'.zip', '.7z', '.rar', '.gz', '.tgz', '.tar', '.bz2', '.xz', '.whl', '.unitypackage'}
    for file in files:
        if file.suffix.lower() in extensions or is_zipfile(file):
            raise ValueError(f'Nested archive cannot ship in release: {file}; store its required contents as loose files')


def source_files() -> list[Path]:
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    return [ROOT / path for raw in tracked if raw
            if (path := raw.decode("utf-8")) in SOURCE_FILES or path.startswith(SOURCE_FOLDERS)]


def reading_files() -> list[Path]:
    """The documents that travel with every package: the changelog, readme, wiki and docs."""
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    return [ROOT / path for raw in tracked if raw
            if (path := raw.decode("utf-8")) in READING_FILES or path.startswith(READING_FOLDERS)]


def package(dist: Path, output: Path) -> None:
    app = dist / "Derailroader"
    if not (app / "Derailroader.exe").is_file():
        raise SystemExit(f"Missing Windows build: {app / 'Derailroader.exe'}")
    app_files = sorted(p for p in app.rglob('*') if p.is_file())
    sources = source_files()
    reading = reading_files()
    reject_nested_archives(app_files + sources + reading)
    output.mkdir(parents=True, exist_ok=True)
    windows = output / f"Derailroader-{VERSION}-Windows.zip"
    with ZipFile(windows, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for file in app_files:
            archive.write(file, f"Derailroader/{file.relative_to(app).as_posix()}")
        archive.write(ROOT / "LICENSE", "Derailroader/LICENSE.txt")
        for file in reading:
            if file.name != "LICENSE":
                archive.write(file, f"Derailroader/{file.relative_to(ROOT).as_posix()}")
        python_license = Path(sys.base_prefix) / "LICENSE.txt"
        if python_license.is_file():
            archive.write(python_license, "Derailroader/PYTHON-LICENSE.txt")
        archive.writestr("Derailroader/START-HERE.txt", (
            f"Derailroader {VERSION} for Windows\n\n"
            "Extract this entire folder, then double-click Derailroader.exe.\n"
            "Keep the _internal folder beside the executable. Python is included.\n"
            "Set your game and tool paths in the app's Settings window.\n"
            "Unity 2019.4.40f1, AssetRipper, CarCreator 3.1.9, and the game mods are separate.\n"
            "Converted packs still require in-game review and calibration.\n"
        ))

    source = output / f"Derailroader-{VERSION}-Source.zip"
    with ZipFile(source, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for file in sources:
            archive.write(file, f"{SOURCE_ROOT}/{file.relative_to(ROOT).as_posix()}")
    print(windows)
    print(source)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, required=True, help="PyInstaller dist directory")
    parser.add_argument("--output", type=Path, required=True, help="directory for release ZIPs")
    args = parser.parse_args()
    package(args.dist, args.output)
