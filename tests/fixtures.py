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

def guid(*parts):
    import hashlib
    return hashlib.md5("|".join(parts).encode()).hexdigest()

def prefab_yaml(root, mat):
    return ("%YAML 1.1\n--- !u!1 &100\nGameObject:\n  m_Name: " + root + "\n--- !u!4 &101\nTransform:\n"
            "  m_GameObject: {fileID: 100}\n  m_Father: {fileID: 0}\n--- !u!1 &200\nGameObject:\n  m_Name: Wheel\n"
            "--- !u!4 &201\nTransform:\n  m_GameObject: {fileID: 200}\n  m_Father: {fileID: 101}\n"
            "--- !u!23 &202\nMeshRenderer:\n  m_Materials:\n  - {fileID: 2100000, guid: " + mat + ", type: 2}\n")

def export_fake_project(bundle, project):
    """Shape of an AssetRipper export: prefabs per catalogue asset (Wheel child, material by GUID),
    placeholder clip paths for vehicle packs, 2022-era project settings."""
    import zlib
    assets = project / "Assets"
    assets.mkdir(parents=True)
    pack = bundle.parent
    seed = bundle.read_bytes().hex()
    cat = next((f for f in pack.iterdir() if f.name.lower() == "catalog.json"), None)
    names = [a["filename"] for a in json.loads(cat.read_text())["assets"].values()] if cat else [pack.name + ".prefab"]
    for name in names:
        stem = name.rsplit(".", 1)[0]
        mat = guid(seed, stem, "mat")
        (assets / "Material").mkdir(exist_ok=True)
        (assets / "Material" / (stem + "_paint.mat")).write_text("%YAML 1.1\nMaterial:\n  m_Name: paint\n")
        (assets / "Material" / (stem + "_paint.mat.meta")).write_text("guid: " + mat + "\n")
        (assets / "PrefabInstance").mkdir(exist_ok=True)
        (assets / "PrefabInstance" / name).write_text(prefab_yaml(stem, mat))
        (assets / "PrefabInstance" / (name + ".meta")).write_text("guid: " + guid(seed, stem, "prefab") + "\n")
    if any(f.name.lower() == "definitions.json" for f in pack.iterdir()):
        (assets / "AnimationClip").mkdir()
        (assets / "AnimationClip" / "Drivers.anim").write_text(
            "AnimationClip:\n  m_FloatCurves:\n  - path: path_0x%x_wheel\n" % zlib.crc32(b"Wheel"))
        (assets / "AnimationClip" / "Drivers.anim.meta").write_text("guid: " + guid(seed, "anim") + "\n")
    settings = project / "ProjectSettings"
    settings.mkdir()
    (settings / "ProjectVersion.txt").write_text("m_EditorVersion: 2022.3.0f1\n")
    (settings / "EditorSettings.asset").write_text("EditorSettings:\n  m_SerializationMode: 2\n  m_LineEndingsForNewScripts: 0\n")
    (project / "Packages").mkdir()
    (project / "Packages" / "manifest.json").write_text(json.dumps({"dependencies": {
        "com.unity.render-pipelines.universal": "14.0.8", "com.unity.shadergraph": "14.0.8", "com.unity.modules.physics": "1.0.0"}}))

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
            export_fake_project(Path(loaded["path"]), Path(form["Path"]) / "ExportedProject")
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


def fake_carcreator(path: Path) -> Path:
    """Minimal .unitypackage: tar.gz of <guid>/{pathname, asset, asset.meta}."""
    import io, tarfile
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = {"a1": ("Assets/CarCreator", None), "b2": ("Assets/CarCreator/CCL.Types.dll", b"dll"),
               "c3": ("Assets/CarCreator/Editor/Wizard.cs", b"class Wizard {}")}
    with tarfile.open(path, "w:gz") as tar:
        for g, (pathname, data) in entries.items():
            files = {"pathname": pathname.encode(), "asset.meta": f"guid: {g}0000000000000000000000000000"[:38].encode()}
            if data is not None:
                files["asset"] = data
            for leaf, blob in files.items():
                info = tarfile.TarInfo(f"{g}/{leaf}")
                info.size = len(blob)
                tar.addfile(info, io.BytesIO(blob))
    return path
