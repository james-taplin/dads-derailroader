"""Package the portable Windows build and the Python source launcher for GitHub Releases."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"
SOURCE_ROOT = f"Derailroader-{VERSION}-Source"


def source_files() -> list[Path]:
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    include = {"Derailroader.pyw", "Launch Derailroader.bat", "README.md", "LICENSE", "pyproject.toml"}
    return [ROOT / path for raw in tracked if raw
            if (path := raw.decode("utf-8")) in include or path.startswith(("src/", "tooling/"))]


def package(dist: Path, output: Path) -> None:
    app = dist / "Derailroader"
    if not (app / "Derailroader.exe").is_file():
        raise SystemExit(f"Missing Windows build: {app / 'Derailroader.exe'}")
    output.mkdir(parents=True, exist_ok=True)
    windows = output / f"Derailroader-{VERSION}-Windows.zip"
    with ZipFile(windows, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for file in sorted(app.rglob("*")):
            if file.is_file():
                archive.write(file, f"Derailroader/{file.relative_to(app).as_posix()}")
        archive.write(ROOT / "LICENSE", "Derailroader/LICENSE.txt")
        python_license = Path(sys.base_prefix) / "LICENSE.txt"
        if python_license.is_file():
            archive.write(python_license, "Derailroader/PYTHON-LICENSE.txt")
        archive.writestr("Derailroader/START-HERE.txt", (
            "Derailroader 0.1.0 for Windows\n\n"
            "Extract this entire folder, then double-click Derailroader.exe.\n"
            "Keep the _internal folder beside the executable. Python is included.\n"
            "Set your game and tool paths in the app's Settings window.\n"
            "Unity 2019.4.40f1, AssetRipper, CarCreator 3.1.9, and the game mods are separate.\n"
            "Converted packs still require in-game review and calibration.\n"
        ))

    source = output / f"Derailroader-{VERSION}-Source.zip"
    with ZipFile(source, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for file in source_files():
            archive.write(file, f"{SOURCE_ROOT}/{file.relative_to(ROOT).as_posix()}")
    print(windows)
    print(source)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, required=True, help="PyInstaller dist directory")
    parser.add_argument("--output", type=Path, required=True, help="directory for release ZIPs")
    args = parser.parse_args()
    package(args.dist, args.output)
