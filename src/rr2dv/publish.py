"""Put a finished pack into the output folder without ever overwriting or half-writing anything."""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Iterable

from .jsonio import sha256_file
from .safety import UnsafePath, check_write_target, is_link


def publish(pack_dir: Path, out_dir: Path, expected: dict[str, str], protected: Iterable[tuple[str, Path]]) -> Path:
    """Copy exactly the `expected` files (name -> sha256) from pack_dir to out_dir/<pack name>.

    The copy is assembled in a hidden staging folder beside the destination, every file is hash-checked,
    and only then is the folder renamed into place (atomic on one volume). An existing destination is an
    error, never overwritten."""
    protected = list(protected)
    check_write_target(out_dir, protected)
    if out_dir.exists() and is_link(out_dir):
        raise UnsafePath(f"output folder is a link or junction: {out_dir}")
    if not expected:
        raise ValueError("nothing to publish")
    for name in expected:
        if Path(name).name != name or name in (".", ".."):
            raise UnsafePath(f"publish expects plain file names, got {name!r}")
    dest = out_dir / pack_dir.name
    if dest.exists() or is_link(dest):
        raise FileExistsError(f"{dest} already exists; choose another output folder or remove it yourself")

    out_dir.mkdir(parents=True, exist_ok=True)
    stage = out_dir / f".rr2dv-stage-{uuid.uuid4().hex[:12]}"
    stage.mkdir()
    try:
        for name, digest in sorted(expected.items()):
            src = pack_dir / name
            if not src.is_file() or is_link(src):
                raise FileNotFoundError(f"{src} is missing or not a regular file")
            shutil.copyfile(src, stage / name)
            actual = sha256_file(stage / name)
            if actual != digest:
                raise ValueError(f"{name}: copied hash {actual[:12]} does not match the audited {digest[:12]}")
        if dest.exists() or is_link(dest):
            raise FileExistsError(f"{dest} appeared while publishing; nothing was replaced")
        os.rename(stage, dest)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)  # only ever our own fresh staging folder
        raise
    return dest
