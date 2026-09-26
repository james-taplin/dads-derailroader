"""Synthetic Railroader mods for tests. Shapes follow real Definitions.json/Catalog.json fields; contents are made up."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def write_pack(folder: Path, objects=None, assets=None, bundle: bytes | None = b"bundle-bytes",
               bundle_name: str = "bundle", trailing_commas: bool = False) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    if objects is not None:
        text = json.dumps({"objects": objects}, indent=2)
        if trailing_commas:  # Railroader tolerates these; so must we
            text = text.replace("\n  ]\n}", ",\n  ],\n}")
        (folder / "Definitions.json").write_text(text, encoding="utf-8")
    if assets is not None:
        (folder / "Catalog.json").write_text(json.dumps({"assets": assets}), encoding="utf-8")
    if bundle is not None:
        (folder / bundle_name).write_bytes(bundle + folder.name.encode())
    return folder


def part(pack_identifier: str, asset: str, name: str) -> dict:
    return {"kind": "PrefabModelComponent", "model": {"assetPackIdentifier": pack_identifier, "assetIdentifier": asset},
            "name": name, "transform": {"position": [0, 0, 0], "rotation": [0, 0, 0, 1], "scale": [1, 1, 1]},
            "parent": None, "enabled": True}


def loco(ident: str, tender: str = "", truck: str = "", parts=(), kind: str = "SteamLocomotive", whistle: str | None = "wh-test",
         heating_surface: float | None = 1200.0, extra_components=()) -> dict:
    components = [
        {"kind": "RadialControl", "purpose": "Throttle", "name": "Throttle", "animation": {"clipName": "Throttle"}},
        {"kind": "RadialControl", "purpose": "Reverser", "name": "Reverser", "animation": {"clipName": "Reverser"}},
        {"kind": "ToggleAnimation", "name": "Cab Door Left"},
        *parts,
    ]
    if whistle:
        components.append({"kind": "Whistle", "defaultWhistleIdentifier": whistle, "name": "Whistle"})
    components += list(extra_components)
    d = {"kind": kind, "archetype": "LocomotiveSteam", "modelIdentifier": ident,
         "tenderIdentifier": tender, "truckIdentifier": truck, "components": components}
    if heating_surface is not None:
        d["totalHeatingSurface"] = heating_surface
    return {"identifier": ident, "metadata": {"name": f"Test {ident}"}, "definition": d}


def tender(ident: str, truck: str = "") -> dict:
    return {"identifier": ident, "metadata": {"name": f"Test {ident}"},
            "definition": {"kind": "Car", "archetype": "Tender", "modelIdentifier": ident, "truckIdentifier": truck,
                           "components": [{"kind": "ToggleAnimation", "name": "Water Hatch"}]}}


def truck(ident: str) -> dict:
    return {"identifier": ident, "definition": {"kind": "Truck", "modelIdentifier": ident, "components": []}}


def standard_mod(base: Path) -> dict:
    """A tender loco with one part in a second pack, whose trucks live in a separate mod (search root)."""
    mod = base / "input" / "Test Loco Mod"
    mod.mkdir(parents=True)
    (mod / "info.json").write_text('{"id": "test-loco-mod"}', encoding="utf-8")
    write_pack(mod / "ts-260-a",
               objects=[loco("ts-260-a", tender="tt-260-a", parts=[part("Test Loco Mod\\parts", "bell", "bell1")]),
                        tender("tt-260-a", truck="test-truck-2s")],
               assets={"ts-260-a": {"filename": "ts-260-a.prefab"}, "tt-260-a": {"filename": "tt-260-a.prefab"}},
               trailing_commas=True)
    write_pack(mod / "parts", assets={"bell": {"filename": "bell.prefab"}})
    search = base / "rrmods"
    write_pack(search / "TruckMod" / "Trucks", objects=[truck("test-truck-2s")],
               assets={"test-truck-2s": {"filename": "Test-Truck-2s.prefab"}}, bundle_name="Bundle")
    return {"mod": mod, "search": search}


def tree_state(root: Path) -> dict:
    """Every file under root with its hash and modification time, to prove nothing was written."""
    state = {}
    for current, _, files in os.walk(root):
        for name in files:
            p = Path(current) / name
            state[p.relative_to(root).as_posix()] = (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
    return state


FAKE_ASSETRIPPER = r'''#!/usr/bin/env python3
"""Stand-in for AssetRipper's headless HTTP API, for tests. Records what it was asked in $FAKE_AR_STATE."""
import http.server, json, os, sys, urllib.parse
from pathlib import Path
port = int(sys.argv[sys.argv.index("--port") + 1])
state = Path(os.environ["FAKE_AR_STATE"])
state.mkdir(parents=True, exist_ok=True)
FORM = """<form><input name="TargetVersion" value="2022.3.0f1"><input type="checkbox" name="Skip" checked>
<input type="checkbox" name="Off"><input name="Locked" value="x" disabled><select name="Mode"><option value="a">
<option value="b" selected></select><input type="submit" value="Save"></form>"""
loaded = {}
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def reply(self, body="ok"):
        self.send_response(200); self.end_headers(); self.wfile.write(body.encode())
    def do_GET(self):
        self.reply(FORM if self.path == "/Settings/Edit" else "AssetRipper")
    def do_POST(self):
        form = dict(urllib.parse.parse_qsl(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode(), keep_blank_values=True))
        if self.path == "/Settings/Update":
            (state / "settings.json").write_text(json.dumps(form))
        elif self.path == "/LoadFile":
            loaded["path"] = form["Path"]
        elif self.path == "/Export/UnityProject":
            if os.environ.get("FAKE_AR_FAIL"):
                self.reply(); return
            assets = Path(form["Path"]) / "ExportedProject" / "Assets"
            assets.mkdir(parents=True)
            (assets / (Path(loaded["path"]).parent.name + ".prefab")).write_text("prefab")
            count = state / "exports.txt"
            count.write_text(str(int(count.read_text()) + 1 if count.exists() else 1))
            print("Finished post-export", flush=True)
        self.reply()
http.server.HTTPServer(("127.0.0.1", port), H).serve_forever()
'''


def fake_assetripper(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    exe = folder / "AssetRipper.GUI.Free"
    exe.write_text(FAKE_ASSETRIPPER.replace("#!/usr/bin/env python3", "#!" + os.environ.get("FAKE_AR_PYTHON", __import__("sys").executable), 1))
    exe.chmod(0o755)
    return exe
