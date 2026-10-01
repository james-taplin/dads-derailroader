"""Run one editor method in Unity 2019.4 and wait for its explicit result, as our build.py does.

Unity's Personal licence refuses -batchmode, so the editor runs windowed but hidden (guide: "Run windowed").
The method must write result.json into the output folder; a process exit alone proves nothing (guide B05).
A "No valid Unity Editor license" exit shortly after launch is a known flake: retried once, never more.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

from . import procs
from .jsonio import read_json, write_json

LICENCE_FLAKE = "No valid Unity Editor license"
# A windowed editor with compiler errors waits forever instead of running the method (board X29): stop it at once.
COMPILER_ERROR = re.compile(r"\): error CS\d+:.*|Scripts have compiler errors")
POLL_SECONDS = 2.0


class UnityError(RuntimeError):
    pass


def _launch(unity: Path, project: Path, method: str, log: Path, env: dict, timeout: float) -> int:
    cmd = [str(unity), "-projectPath", str(project), "-executeMethod", method, "-logFile", str(log)]
    kwargs = {}
    if sys.platform == "win32":
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        info.wShowWindow = 0  # hidden window, not batch mode
        kwargs["startupinfo"] = info
    try:
        proc = subprocess.Popen(cmd, cwd=project, env=env, **kwargs)
    except OSError as e:
        raise UnityError(f"Unity at {unity} could not be started ({e}); check `unity` in the settings file") from e
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                return proc.wait(timeout=POLL_SECONDS)
            except subprocess.TimeoutExpired:
                pass
            text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
            errors = sorted({m.group(0).strip() for m in COMPILER_ERROR.finditer(text)})
            if errors or time.monotonic() > deadline:
                procs.stop(proc, grace=60)
                if errors:
                    raise UnityError(f"scripts did not compile, so {method} could not run: " + "; ".join(errors[:5]) + f" (see {log})")
                raise UnityError(f"Unity did not finish {method} within {timeout:.0f} s; see {log}")
    finally:
        if proc.poll() is None:
            procs.stop(proc)  # interruption must stop the editor before workspace cleanup


# Windows exit codes a crashed Unity editor leaves (the code is unsigned in Python): what they usually mean for the user.
CRASH_CODES = {
    0xC000041D: "Unity crashed with a fatal exception in a callback: typically the graphics driver, low memory or an RDP/locked desktop session",
    0xC0000005: "Unity crashed with an access violation",
    0xC0000409: "Unity crashed (stack buffer overrun)",
    0xC00000FD: "Unity crashed (stack overflow)",
}


def _crash_meaning(code) -> str:
    if isinstance(code, int) and code != 0:
        text = CRASH_CODES.get(code & 0xFFFFFFFF)
        return f" = 0x{code & 0xFFFFFFFF:08X}" + (f": {text}" if text else "")
    return ""


NON_ASCII_ADVICE = ("Unity 2019.4 is known to be unreliable when a path it uses has non-English (e.g. Cyrillic) characters, "
                    "and on Windows set to \"Beta: Use Unicode UTF-8 for worldwide language support\". Use a plain-English "
                    "Unity install folder and work folder (e.g. C:\\rr2dv), and if your user profile name is not plain English, "
                    "set the TEMP and TMP environment variables to a plain folder such as C:\\Temp")


def non_ascii_paths(named: dict) -> list[str]:
    """`label: path` for every given path (empty ones skipped) containing a non-ASCII character."""
    return [f"{label}: {value}" for label, value in named.items() if value and not str(value).isascii()]


def environment_paths(env=None) -> dict:
    env = os.environ if env is None else env
    return {key: env.get(key) for key in ("USERPROFILE", "LOCALAPPDATA", "TEMP", "TMP")}


def _non_ascii_hint(paths: dict) -> str:
    found = non_ascii_paths(paths)
    return ("\n  non-English characters in paths Unity uses: " + "; ".join(found) + "\n  " + NON_ASCII_ADVICE) if found else ""


def _log_tail(log: Path, lines: int = 12) -> str:
    """The last lines of Unity's own log (where a crash names itself), for the error message."""
    try:
        tail = [l.rstrip() for l in log.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()][-lines:]
    except OSError:
        return ""
    return "\n  last lines of the Unity log:\n    " + "\n    ".join(tail) if tail else ""


RETRY_PAUSE_S = 10  # lets a just-closed editor release the project before the retry


def run_method(unity: Path, project: Path, method: str, out: Path, extra_env: dict | None = None,
               timeout: float = 3600) -> dict:
    if not unity or not Path(unity).is_file():
        raise FileNotFoundError("Unity 2019.4.40f1 is not set up: add `unity` to the settings file (see `rr2dv doctor`)")
    if (project / "Temp" / "UnityLockfile").exists():
        raise UnityError(f"{project} is open in another Unity editor (Temp/UnityLockfile); close it and rerun")
    out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, **(extra_env or {}))
    attempts = []
    for attempt in (1, 2):
        log = out / f"unity-{attempt}.log"
        started = time.time()
        code = _launch(Path(unity), project, method, log, env, timeout)
        text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
        attempts.append({"attempt": attempt, "exit_code": code, "seconds": round(time.time() - started, 1)})
        if attempt == 1 and code != 0 and LICENCE_FLAKE in text and not (out / "result.json").exists():
            continue
        # Unity sometimes quits right after opening the project without running the method (exit 0, no result):
        # seen straight after another editor closed on the same project (RLW RPP-1 audit, 2026-09-28). Once more.
        # (the method name is always in the log's command line, so test that no scripts were ever loaded)
        if attempt == 1 and not (out / "result.json").exists() and "ReloadAssembly" not in text \
                and "error CS" not in text:
            time.sleep(RETRY_PAUSE_S)
            continue
        break
    write_json(out / "launch.json", {"method": method, "project": str(project), "attempts": attempts})
    result_file = out / "result.json"
    if not result_file.exists():
        code = attempts[-1]["exit_code"]
        last = attempts[-1]["attempt"]
        raise UnityError(f"{method} wrote no result.json (exit code {code}{_crash_meaning(code)}, after {len(attempts)} attempt(s)); "
                         f"see {out / f'unity-{last}.log'}{_log_tail(out / f'unity-{last}.log')}"
                         f"{_non_ascii_hint({'Unity': unity, 'project': project, **environment_paths(env)})}")
    result = read_json(result_file)
    result["exit_code"] = attempts[-1]["exit_code"]
    return result
