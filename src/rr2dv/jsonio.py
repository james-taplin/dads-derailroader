"""JSON reading/writing and hashing shared by every stage."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

# Railroader definition files can carry trailing commas. Strip them outside quoted strings only
# (same rule as tooling/builder/tools/catalog.py read_def).
_TRAILING_COMMA = re.compile(r'"(?:\\.|[^"\\])*"|,(?=\s*[}\]])')


class SourceError(ValueError):
    """A source file could not be read or parsed."""

    def __init__(self, path: Path, message: str):
        super().__init__(f"{path}: {message}")
        self.path = path


def read_json_lenient(path: Path):
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        raise SourceError(path, f"cannot read ({e})") from e
    cleaned = _TRAILING_COMMA.sub(lambda m: m[0] if m[0].startswith('"') else "", text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise SourceError(path, f"invalid JSON at line {e.lineno} column {e.colno}: {e.msg}") from e


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dumps(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_json(path: Path, data) -> None:
    """Write atomically: a crash never leaves a half-written file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(dumps(data))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
