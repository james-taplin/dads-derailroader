"""Stopping the external tools we launch (Unity, AssetRipper) together with the processes they started.

On Windows, killing a process leaves its children running: Unity's helper processes, or the real program behind a
.cmd launcher (our test stand-ins). Those keep files and folders in the run open, so a stop there ends the whole tree.
"""
from __future__ import annotations

import subprocess
import sys


def stop(proc: subprocess.Popen, grace: float = 15.0) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        done = subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        if done.returncode not in (0, 128):  # 128: already gone; anything else: at least stop the launcher itself
            proc.kill()
    else:
        proc.terminate()
        try:
            proc.wait(timeout=grace)
            return
        except subprocess.TimeoutExpired:
            proc.kill()
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=grace)
