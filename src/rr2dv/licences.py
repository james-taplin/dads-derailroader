"""Licence policy. rr2dv will not convert a locomotive when the author of any mod whose content would end up in the
Derail Valley pack (the mod itself, and any mod whose bundles or images are copied) explicitly forbids modifying their
work (even for personal use), reverse engineering it, porting or converting it, or derivative works. A licence file
that cannot be read also stops the conversion. There is deliberately no override: not a flag, not a setting, not a
claimed permission.

Only explicit restrictions count: a mod without a licence file is converted. Code mods the loco uses in Railroader
(e.g. LegosBetterSteam) are not needed in Derail Valley and are never opened, so their licences do not block.

Matching is by patterns over the licence text and errs towards stopping. A mod that is stopped wrongly is fixed by
correcting the patterns here, never by letting a user skip the check.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from .jsonio import sha256_file

LICENCE_NAME = re.compile(r"licen[cs]e|copying|copyright|eula|terms|permission|legal", re.I)
README_NAME = re.compile(r"read[ _-]?me", re.I)
TEXT_SUFFIXES = {"", ".txt", ".md", ".markdown", ".rtf", ".html", ".htm", ".text"}
UNREADABLE_SUFFIXES = {".pdf", ".doc", ".docx", ".odt", ".pages"}
MAX_DEPTH = 2
MAX_BYTES = 2_000_000

_NEG = r"\b(?:no|not|never|nor|cannot|can't|don't|do not|must not|may not|shall not|prohibit\w*|forbid\w*|disallow\w*)\b"
FORBIDDING = {
    "no-modification": re.compile(_NEG + r"[^.\n]{0,80}\b(?:modif\w*|edit(?:s|ed|ing)?|alter(?:s|ed|ing|ation|ations)?)\b", re.I),
    "no-reverse-engineering": re.compile(r"reverse[\s-]*engineer|decompil|disassembl", re.I),
    "no-porting": re.compile(_NEG + r"[^.\n]{0,80}\b(?:port(?:s|ed|ing)?|convert\w*|conversions?)\b|\bno\s+(?:ports?|conversions?)\b", re.I),
    "no-derivatives": re.compile(r"no[\s-]*derivative|noderivatives|\bby-(?:nc-)?nd\b|" + _NEG + r"[^.\n]{0,60}\bderivative", re.I),
}
NOTED = {
    "no-redistribution": re.compile(r"redistribut|re-?upload", re.I),
    "personal-use-only": re.compile(r"personal[\s,]+(?:non-commercial\s+)?(?:use|purposes)", re.I),
    "no-commercial-use": re.compile(r"no\s+commercial|non-commercial|\bby-nc\b", re.I),
}
# A readme mixes install notes ("do not edit the folder name") with terms; only its terms paragraphs count.
TERMS_PARAGRAPH = re.compile(r"licen[cs]|permission|copyright|terms|all rights|redistribut|re-?upload|personal use", re.I)

# Licences we have read of code mods locos use in Railroader; shown for information, never opened or copied.
KNOWN_LICENCES = {
    "legosbettersteam": {"id": "LegosBetterSteam", "author": "legotrainman",
                         "terms": ["no-modification", "no-reverse-engineering", "no-redistribution", "personal-use-only", "no-commercial-use"],
                         "evidence": "LICENSE shipped with LegosBetterSteam 1.0.0, read 2026-09-26"},
    "legoslibraryofstuff": {"id": "LegosLibraryOfStuff", "author": "legotrainman",
                            "terms": ["no-modification", "no-reverse-engineering", "no-redistribution", "personal-use-only", "no-commercial-use"],
                            "evidence": "LICENSE shipped with LegosLibraryOfStuff 1.4.6, read 2026-09-26"},
}


def terms_in(text: str, readme: bool = False) -> list[str]:
    if readme:
        text = "\n\n".join(p for p in re.split(r"\n\s*\n", text) if TERMS_PARAGRAPH.search(p))
    return [n for n, rx in FORBIDDING.items() if rx.search(text)] + [n for n, rx in NOTED.items() if rx.search(text)]


def scan_folder(folder: Path) -> list[dict]:
    """Licence and readme files in a mod folder (and up to MAX_DEPTH levels below), with the terms they contain."""
    found = []
    base = len(folder.parts)
    for current, dirs, files in os.walk(folder, followlinks=False):
        here = Path(current)
        if len(here.parts) - base >= MAX_DEPTH:
            dirs[:] = []
        dirs.sort()
        for name in sorted(files):
            path = here / name
            stem, suffix = path.stem, path.suffix.casefold()
            is_licence, is_readme = bool(LICENCE_NAME.search(stem)), bool(README_NAME.search(stem))
            if not (is_licence or is_readme) or path.is_symlink():
                continue
            rel = path.relative_to(folder).as_posix()
            if suffix in UNREADABLE_SUFFIXES:
                found.append({"file": rel, "sha256": sha256_file(path), "terms": [], "unreadable": True})
            elif suffix in TEXT_SUFFIXES:
                if path.stat().st_size > MAX_BYTES:
                    found.append({"file": rel, "sha256": sha256_file(path), "terms": [], "unreadable": True})
                    continue
                text = path.read_text(encoding="utf-8-sig", errors="replace")
                found.append({"file": rel, "sha256": sha256_file(path), "terms": terms_in(text, readme=is_readme and not is_licence)})
    return found


def forbidding(terms: list[str]) -> list[str]:
    return [t for t in terms if t in FORBIDDING]


def describe(terms: list[str]) -> str:
    words = {"no-modification": "modifying it", "no-reverse-engineering": "opening or decompiling it",
             "no-porting": "porting or converting it", "no-derivatives": "derivative works"}
    return " and ".join(words[t] for t in terms)
