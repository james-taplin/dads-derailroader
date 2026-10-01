# Unattended test build of all stock steam locos: brief for Codex

Goal: build and audit all 21 stock steam locos with the current commit, never install anything, and send back the compact reports so the
owner can read the build reports when back. The owner allowed, for this run only: confirming the app's suggested vehicle choices as they are,
ticking "I acknowledge experimental physics and pending in-game calibration", and using the app's own measured end-beam proposals when a
build stops for geometry review (up to 3 rounds per loco). Nothing is installed: the personal-use notice needs a person and is refused.

    cd <the dads-derailroader clone, branch claude/unity-crash-message>
    git pull
    git log --oneline -1
    set PYTHONPATH=src
    python tools\\vanilla\\build_all.py --dry-run
    python tools\\vanilla\\build_all.py --pilot --acknowledge-experimental --accept-proposed-geometry
    python tools\\vanilla\\build_all.py --acknowledge-experimental --accept-proposed-geometry

- Check the dry run's line says: geometry proposals ACCEPTED, experimental-physics box TICKED, installing: never.
- Close any open Unity editors first. Leave `keepWorkFiles` off (the tool warns if it is on): run folders are deleted after each pack.
- A pack that builds and passes its audit is BUILT ("not installed"). Resume by rerunning the same command; `--force` rebuilds built packs.
- Send `vf_build_out\\vf_build.zip` (small, reports only) and the console text whatever the exit code. A FAILED pack: name it and do not retry it more than once.
- Do not edit settings, the app, `tooling/` or the scripts. Do not push. Read-only towards Railroader and Derail Valley, never install.
