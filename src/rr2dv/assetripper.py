"""Drive AssetRipper (free GUI build, 2.0) headless over its local HTTP API to export a Railroader bundle to a
Unity 2019.4.40f1 project. Same protocol as our tooling's export_assetripper.ps1 (guide B06):
GET / until up -> POST /Reset -> GET /Settings/Edit -> POST /Settings/Update (whole form, TargetVersion set)
-> POST /LoadFile Path -> POST /Export/UnityProject Path -> check ExportedProject/Assets and the log.

Exports are cached by (bundle SHA-256, AssetRipper SHA-256, target version) as guide B04 asks, written to a
temporary folder and renamed into place only once verified, so a cache entry is always complete. Cache entries are
read-only inputs for later stages.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from . import procs
from .jsonio import read_json, sha256_file, write_json

TARGET_VERSION = "2019.4.40f1"
FINISHED_MARKER = "Finished post-export"
HOST = "127.0.0.1"


class ExportError(RuntimeError):
    pass


class _SettingsForm(HTMLParser):
    """Collect the settings form as a browser would submit it: inputs with values, checked boxes, selected options."""

    def __init__(self):
        super().__init__()
        self.fields: dict[str, str] = {}
        self._select: str | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        name = a.get("name")
        if tag == "input" and name and "disabled" not in a:
            if a.get("type") == "checkbox":
                if "checked" in a:
                    self.fields[name] = a.get("value") or ""
            elif a.get("type") not in ("submit", "button", "reset"):
                self.fields[name] = a.get("value") or ""
        elif tag == "select" and name and "disabled" not in a:
            self._select = name
        elif tag == "option" and self._select and "selected" in a:
            self.fields[self._select] = a.get("value") or ""

    def handle_endtag(self, tag):
        if tag == "select":
            self._select = None


def settings_from_form(html: str, target: str = TARGET_VERSION) -> dict[str, str]:
    parser = _SettingsForm()
    parser.feed(html)
    if "TargetVersion" not in parser.fields:
        raise ExportError("AssetRipper settings page has no TargetVersion field; this AssetRipper version is not supported yet")
    parser.fields["TargetVersion"] = target
    return parser.fields


def _free_port() -> int:
    with socket.socket() as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def _request(base: str, path: str, data: dict | None = None, timeout: float = 30) -> str:
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(base + path, data=body, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def cache_key(bundle_sha256: str, extractor_sha256: str, target: str = TARGET_VERSION) -> str:
    return f"{bundle_sha256[:16]}-{extractor_sha256[:12]}-{target}"


def export(exe: Path, bundle: Path, bundle_sha256: str, cache_root: Path, target: str = TARGET_VERSION,
           startup_timeout: float = 60, load_timeout: float = 600, export_timeout: float = 1800) -> dict:
    """Return {"key", "path" (the folder holding ExportedProject), "cached"} for one bundle."""
    extractor_sha = sha256_file(exe)
    key = cache_key(bundle_sha256, extractor_sha, target)
    final = cache_root / key
    record = final / "export.json"
    if record.is_file():
        info = read_json(record)
        if info.get("bundle_sha256") == bundle_sha256 and (final / "ExportedProject" / "Assets").is_dir():
            return {"key": key, "path": str(final), "cached": True}
        raise ExportError(f"cache entry {final} is inconsistent; remove it and rerun")

    cache_root.mkdir(parents=True, exist_ok=True)
    temp = cache_root / f".partial-{key}-{os.getpid()}-{int(time.time())}"
    temp.mkdir()
    out = temp / "export"
    logs = temp / "logs"
    logs.mkdir()
    port = _free_port()
    base = f"http://{HOST}:{port}"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    try:
        with open(logs / "assetripper.log", "wb") as stdout, open(logs / "assetripper.err.log", "wb") as stderr:
            try:
                proc = subprocess.Popen([str(exe), "--headless", "--port", str(port)], stdout=stdout, stderr=stderr,
                                        cwd=temp, creationflags=flags)
            except OSError as e:
                raise ExportError(f"AssetRipper at {exe} could not be started ({e}); check `assetRipper` in the settings file") from e
            try:
                deadline = time.monotonic() + startup_timeout
                while True:
                    try:
                        _request(base, "/", timeout=2)
                        break
                    except (urllib.error.URLError, ConnectionError, OSError):
                        if proc.poll() is not None:
                            raise ExportError(f"AssetRipper exited during startup (code {proc.returncode}); see {logs}")
                        if time.monotonic() > deadline:
                            raise ExportError(f"AssetRipper did not start within {startup_timeout:.0f} s")
                        time.sleep(0.5)
                _request(base, "/Reset", {})
                html = _request(base, "/Settings/Edit")
                (logs / "settings_form.html").write_text(html, encoding="utf-8")
                _request(base, "/Settings/Update", settings_from_form(html, target))
                _request(base, "/LoadFile", {"Path": str(bundle)}, timeout=load_timeout)
                _request(base, "/Export/UnityProject", {"Path": str(out)}, timeout=export_timeout)
            finally:
                procs.stop(proc)
        log = (logs / "assetripper.log").read_text(encoding="utf-8", errors="replace")
        if not (out / "ExportedProject" / "Assets").is_dir():
            raise ExportError(f"AssetRipper produced no ExportedProject/Assets for {bundle.name}; see {logs}")
        if FINISHED_MARKER not in log:
            raise ExportError(f"AssetRipper did not report a completed export for {bundle.name}; see {logs}")
        for item in out.iterdir():
            item.rename(temp / item.name)
        out.rmdir()
        write_json(temp / "export.json", {"schema": 1, "bundle": bundle.name, "bundle_sha256": bundle_sha256,
                                          "extractor_sha256": extractor_sha, "target": target,
                                          "created": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
        try:
            temp.rename(final)
        except OSError:
            if (final / "export.json").is_file():  # another run finished the same export first
                shutil.rmtree(temp, ignore_errors=True)
                return {"key": key, "path": str(final), "cached": True}
            raise
    except BaseException:
        if temp.exists():
            try:
                # keep the logs for diagnosis; a .failed- folder is never reused as a cache entry
                temp.rename(cache_root / f".failed-{key}-{int(time.time())}-{os.getpid()}")
            except OSError:
                shutil.rmtree(temp, ignore_errors=True)
        raise
    return {"key": key, "path": str(final), "cached": False}
