"""Install a finished pack into the Derail Valley Mods folder, only after the personal-use notice (W25).

Nothing is written until the user has clicked "I agree" the required number of times (consent.py). The pack is
assembled in a hidden staging folder beside the destination, every file is hash-checked, NOTICE.txt,
SOURCE_PROVENANCE.txt (notice version, when it was acknowledged, the source content detected) and an rr2dv.json
marker are added, and only then is it renamed into place. An existing folder of the same name is replaced
only if rr2dv made it (it carries our marker); any other mod's folder is never touched. Saves are never touched.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Callable, Sequence

from . import __version__, consent as consent_mod
from .installs import Install
from .jsonio import read_json, sha256_file
from .safety import UnsafePath, is_link

MARKER = "rr2dv.json"
NOTICE_FILE = "NOTICE.txt"
PROVENANCE_FILE = "SOURCE_PROVENANCE.txt"
RESERVED = (MARKER, NOTICE_FILE, PROVENANCE_FILE)
GENERATOR = "rr2dv"


class InstallRefused(RuntimeError):
    """The pack was not installed: the notice was declined, or the destination belongs to another mod."""


def made_by_rr2dv(folder: Path) -> bool:
    marker = folder / MARKER
    if not marker.is_file() or is_link(marker):
        return False
    try:
        data = read_json(marker)
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get("generator") == GENERATOR


def source_label(source: dict) -> str:
    """One line of "Source content detected": the mod id, and the authors its definitions credit."""
    credits = source.get("credits") or []
    return source["id"] + (f" (credited: {', '.join(credits)})" if credits else "")


def provenance_text(name: str, sources: Sequence[dict], details: dict, acknowledged: str) -> str:
    lines = ["rr2dv source provenance", "",
             f"Pack: {name}",
             f"Notice version: {consent_mod.NOTICE_VERSION}",
             f"Acknowledged: {acknowledged} ({consent_mod.REQUIRED_CLICKS} clicks on \"I agree\")",
             f"Converted from: {details.get('input', '?')} (locomotive {details.get('locomotive', '?')})",
             f"Input fingerprint: {details.get('input_fingerprint') or '?'}", "",
             consent_mod.SOURCES_HEADING]
    for s in sources:
        where = f" [{s['root']}{':' + s['path'] if s.get('path') else ''}]" if s.get("root") else ""
        lines.append(f"  - {source_label(s)}{where}")
        lines += [f"      {p}" for p in s.get("packs", [])]
    lines += ["", "Copyright and other rights in the source assets remain with their respective rights holders.", ""]
    return "\n".join(lines)


def install(pack_dir: Path, dv: Install, expected: dict[str, str], sources: Sequence[dict], details: dict,
            ask: Callable[[str, Sequence[str]], bool] = consent_mod.ask) -> tuple[Path, dict]:
    """Copy exactly the `expected` files (name -> sha256) from pack_dir to <DV Mods>/<pack name>, after consent.
    Returns the destination and the acknowledgement record (for the run log)."""
    name = pack_dir.name
    if Path(name).name != name or name in (".", "..") or name.startswith("."):
        raise UnsafePath(f"unsafe pack folder name {name!r}")
    if not dv.mods.is_dir() or is_link(dv.mods):
        raise UnsafePath(f"Derail Valley Mods folder missing or a link: {dv.mods}")
    if not expected:
        raise ValueError("nothing to install")
    for f in expected:
        if Path(f).name != f or f in (".", "..") or f in RESERVED:
            raise UnsafePath(f"install expects plain file names other than {', '.join(RESERVED)}, got {f!r}")
    dest = dv.mods / name
    replacing = dest.exists() or is_link(dest)
    if replacing and (is_link(dest) or not made_by_rr2dv(dest)):
        raise InstallRefused(f"{dest} already exists and was not made by rr2dv; it was left untouched. Rename or remove "
                             "it yourself if you want to install this conversion")

    labels = [source_label(s) for s in sources]
    text = consent_mod.notice_text(name, labels)
    if not ask(name, labels):
        raise InstallRefused("the personal-use notice was not agreed to; nothing was installed")
    acknowledged = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    record = {"notice_version": consent_mod.NOTICE_VERSION, "notice_sha256": consent_mod.notice_sha256(text),
              "acknowledged": acknowledged, "clicks": consent_mod.REQUIRED_CLICKS, "sources": list(sources)}

    stage = dv.mods / f".rr2dv-stage-{uuid.uuid4().hex[:12]}"
    stage.mkdir()
    old = None
    try:
        for f, digest in sorted(expected.items()):
            src = pack_dir / f
            if not src.is_file() or is_link(src):
                raise FileNotFoundError(f"{src} is missing or not a regular file")
            shutil.copyfile(src, stage / f)
            actual = sha256_file(stage / f)
            if actual != digest:
                raise ValueError(f"{f}: copied hash {actual[:12]} does not match the audited {digest[:12]}")
        (stage / NOTICE_FILE).write_text(text + "\n", encoding="utf-8")
        (stage / PROVENANCE_FILE).write_text(provenance_text(name, sources, details, acknowledged), encoding="utf-8")
        marker = {"generator": GENERATOR, "version": __version__, **details, **record, "files": expected}
        (stage / MARKER).write_text(json.dumps(marker, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if replacing:
            if not made_by_rr2dv(dest):
                raise InstallRefused(f"{dest} changed while installing; nothing was replaced")
            old = dv.mods / f".rr2dv-old-{uuid.uuid4().hex[:12]}"
            os.rename(dest, old)
        elif dest.exists() or is_link(dest):
            raise FileExistsError(f"{dest} appeared while installing; nothing was replaced")
        os.rename(stage, dest)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)  # only ever our own fresh staging folder
        if old is not None and not dest.exists():
            os.rename(old, dest)  # put the previous conversion back
            old = None
        raise
    if old is not None:
        shutil.rmtree(old, ignore_errors=True)  # our own previous conversion, already moved aside
    return dest, record
