"""Synthetic Railroader mods for tests. Shapes follow real Definitions.json/Catalog.json fields; contents are made up."""
from __future__ import annotations

import os as _os
import tempfile as _tempfile

# Tests never write to the user's real app log (%LOCALAPPDATA%\rr2dv\logs): every test module imports this file.
_os.environ.setdefault("RR2DV_LOG_DIR", _tempfile.mkdtemp(prefix="rr2dv-test-logs-"))

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


def anchor(kind: str, name: str, position, **extra) -> dict:
    return {"kind": kind, "name": name, "transform": {"position": position, "rotation": [0, 0, 0, 1], "scale": [1, 1, 1]},
            "parent": None, "enabled": True, **extra}


def loco(ident: str, tender: str = "", truck: str = "", parts=(), kind: str = "SteamLocomotive", whistle: str | None = "wh-test",
         heating_surface: float | None = 1200.0, extra_components=()) -> dict:
    components = [
        {"kind": "RadialControl", "purpose": "Throttle", "name": "Throttle", "animation": {"clipName": "Throttle"}},
        {"kind": "RadialControl", "purpose": "Reverser", "name": "Reverser", "animation": {"clipName": "Reverser"}},
        {"kind": "ToggleAnimation", "name": "Cab Door Left"},
        *parts,
    ]
    if whistle:
        components.append({"kind": "Whistle", "defaultWhistleIdentifier": whistle, "name": "Whistle",
                           "transform": {"position": [0.4, 3.1, -0.3]}})
    components += [anchor("Chuff", "Chuff", [0, 3.6, 2.3]), anchor("CylinderCock", "CylinderCock 1", [0, 0.5, 2.5], radius=1.1),
                   anchor("Seat", "Engineer Seat", [1.0, 2.0, -2.3]), anchor("Seat", "Fireman Seat", [-1.0, 2.0, -2.3]),
                   anchor("FireboxEffect", "FireboxEffect 1", [0, 1.4, -2.0]), anchor("Headlight", "hl1", [0, 2.9, 3.2], forward=True),
                   anchor("Decal", "Decal 1", [-1.35, 1.7, -1.7], content="RoadNumber"),
                   anchor("Decal", "Decal 2", [1.35, 1.7, -1.7], content="RoadNumber")]
    components += list(extra_components)
    d = {"kind": kind, "archetype": "LocomotiveSteam", "modelIdentifier": ident, "mainDriverIndex": 0,
         "maximumBoilerPressure": 180.0, "pistonDiameterInches": 16.0, "pistonStrokeInches": 24.0, "publishedTractiveEffort": 0,
         "weightEmpty": 90000, "positionHead": 5.2, "positionTail": -4.1,
         "wheelsets": [{"offset": 0.0, "length": 2.4, "diameter": 1.2, "numberOfAxles": 3, "animation": {"clipName": "Drivers"}}],
         "tenderIdentifier": tender, "truckIdentifier": truck, "components": components}
    if heating_surface is not None:
        d["totalHeatingSurface"] = heating_surface
    return {"identifier": ident, "metadata": {"name": f"Test {ident}"}, "definition": d}


def tender(ident: str, truck: str = "") -> dict:
    return {"identifier": ident, "metadata": {"name": f"Test {ident}"},
            "definition": {"kind": "Car", "archetype": "Tender", "modelIdentifier": ident, "truckIdentifier": truck, "length": 7.0,
                           "truckSeparation": 4.0,
                           "weightEmpty": 40000,
                           "loadSlots": [{"requiredLoadIdentifier": "coal", "maximumCapacity": 20000},
                                         {"requiredLoadIdentifier": "water", "maximumCapacity": 6000}],
                           "components": [{"kind": "ToggleAnimation", "name": "Water Hatch"},
                                          {"kind": "DefaultLivelryComponent", "name": "Black", "idColors": [{"id": "Body", "value": "#191919"}]}]}}


def truck(ident: str) -> dict:
    return {"identifier": ident, "definition": {"kind": "Truck", "modelIdentifier": ident, "components": []}}


def game_installs(base: Path) -> dict:
    """Fake Railroader and Derail Valley installs under base (W25: both are required), DV with Custom Car Loader."""
    rr, dv = base / "Railroader", base / "Derail Valley"
    (rr / "Railroader_Data" / "StreamingAssets" / "AssetPacks").mkdir(parents=True, exist_ok=True)
    (rr / "Mods").mkdir(exist_ok=True)
    (dv / "DerailValley_Data").mkdir(parents=True, exist_ok=True)
    (dv / "Mods" / "DVCustomCarLoader").mkdir(parents=True, exist_ok=True)
    (dv / "Mods" / "DVCustomCarLoader" / "Info.json").write_text('{"Id": "DVCustomCarLoader", "Version": "3.1.9"}')
    return {"railroader": str(rr), "game": str(dv)}


def standard_mod(base: Path) -> dict:
    """A tender loco with one part in a second pack, in a fake Railroader install's Mods folder. The tender's trucks
    live in a separate mod there (search root)."""
    games = game_installs(base)
    mods = Path(games["railroader"]) / "Mods"
    mod = mods / "Test Loco Mod"
    mod.mkdir(parents=True)
    (mod / "info.json").write_text('{"id": "test-loco-mod"}', encoding="utf-8")
    write_pack(mod / "ts-260-a",
               objects=[loco("ts-260-a", tender="tt-260-a", parts=[part("Test Loco Mod\\parts", "bell", "bell1")]),
                        tender("tt-260-a", truck="test-truck-2s")],
               assets={"ts-260-a": {"filename": "ts-260-a.prefab"}, "tt-260-a": {"filename": "tt-260-a.prefab"}},
               trailing_commas=True)
    write_pack(mod / "parts", assets={"bell": {"filename": "bell.prefab"}})
    write_pack(mods / "TruckMod" / "Trucks", objects=[truck("test-truck-2s")],
               assets={"test-truck-2s": {"filename": "Test-Truck-2s.prefab"}}, bundle_name="Bundle")
    return {"mod": mod, "search": mods, "games": games, "dv_mods": Path(games["game"]) / "Mods"}


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

def prefab_yaml(root, mat, dll, anim):
    return ("%YAML 1.1\n--- !u!1 &100\nGameObject:\n  m_Name: " + root + "\n--- !u!4 &101\nTransform:\n"
            "  m_GameObject: {fileID: 100}\n  m_Father: {fileID: 0}\n--- !u!1 &200\nGameObject:\n  m_Name: Wheel\n"
            "--- !u!4 &201\nTransform:\n  m_GameObject: {fileID: 200}\n  m_Father: {fileID: 101}\n"
            "--- !u!23 &202\nMeshRenderer:\n  m_Materials:\n  - {fileID: 2100000, guid: " + mat + ", type: 2}\n"
            "--- !u!114 &203\nMonoBehaviour:\n  m_Script: {fileID: 11500000, guid: " + dll + ", type: 3}\n"
            "  clips:\n  - name: Drivers\n    clip: {fileID: 7400000, guid: " + anim + ", type: 2}\n"
            "  materials:\n  - name: paint\n    material: {fileID: 2100000, guid: " + mat + ", type: 2}\n")

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
    dll = guid(seed, "dll")
    for rel, body, g in (("Plugins/RR.Runtime.dll", "MZ", dll), ("Scripts/Assembly-CSharp/AnimationMap.cs", "class AnimationMap {}", guid(seed, "cs")),
                         ("Scripts/Assembly-CSharp/Assembly-CSharp.asmdef", "{}", guid(seed, "asmdef"))):
        (assets / rel).parent.mkdir(parents=True, exist_ok=True)
        (assets / rel).write_text(body)
        (assets / (rel + ".meta")).write_text("guid: " + g + "\n")
    for name in names:
        stem = name.rsplit(".", 1)[0]
        mat = guid(seed, stem, "mat")
        (assets / "Material").mkdir(exist_ok=True)
        (assets / "Material" / (stem + "_paint.mat")).write_text("%YAML 1.1\nMaterial:\n  m_Name: paint\n")
        (assets / "Material" / (stem + "_paint.mat.meta")).write_text("guid: " + mat + "\n")
        (assets / "PrefabInstance").mkdir(exist_ok=True)
        (assets / "PrefabInstance" / name).write_text(prefab_yaml(stem, mat, dll, guid(seed, "anim")))
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


def fake_tool(folder: Path, name: str, script: str, python: str | None = None) -> Path:
    """A stand-in executable running `script` with Python: a shebang script on POSIX; on Windows the script plus a
    .cmd launcher, which Windows starts like an .exe (X33: extensionless scripts fail there with WinError 193)."""
    import sys
    python = python or sys.executable
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        body = folder / (name + ".py")
        body.write_text(script)
        exe = folder / (name + ".cmd")
        exe.write_text(f'@echo off\n"{python}" "%~dp0{name}.py" %*\n')
        return exe
    exe = folder / name
    exe.write_text(script.replace("#!/usr/bin/env python3", "#!" + python, 1))
    exe.chmod(0o755)
    return exe


def fake_assetripper(folder: Path) -> Path:
    return fake_tool(folder, "AssetRipper.GUI.Free", FAKE_ASSETRIPPER, os.environ.get("FAKE_AR_PYTHON"))


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


FAKE_UNITY = r'''#!/usr/bin/env python3
"""Stand-in for Unity 2019.4 running our editor methods, for tests. $FAKE_UNITY_MODE: flake-once | no-result | problems |
compile-error | build-fails | build-audio | install-cancel (not used here)."""
import hashlib, json, os, sys
from pathlib import Path
args = sys.argv[1:]
project = Path(args[args.index("-projectPath") + 1]); log = Path(args[args.index("-logFile") + 1])
method = args[args.index("-executeMethod") + 1]
out = Path(os.environ.get({"Rr2dvProbe.Run": "RR2DV_PROBE_OUT", "Rr2dvBuild.Build": "CCL_BUILD_OUT",
                           "Rr2dvAudit.Run": "RR2DV_AUDIT_OUT"}[method]))
mode = os.environ.get("FAKE_UNITY_MODE", "")
state = Path(os.environ.get("FAKE_UNITY_STATE", str(out) + ".state"))
calls = int(state.read_text()) + 1 if state.exists() else 1
state.write_text(str(calls))
if mode == "compile-error":
    import time
    log.write_text("Assets/Editor/Rr2dvProbe.cs(203,74): error CS0117: 'AnimationUtility' does not contain a definition\\n")
    time.sleep(300)  # a windowed editor with compiler errors just waits
if mode == "flake-once" and calls == 1:
    log.write_text("No valid Unity Editor license found\n"); sys.exit(1)
log.write_text("fake unity " + method + "\n")
if mode == "no-result":
    sys.exit(0)

def axles(w):
    n, off, length = w["axles"], w["offset"], w["length"]
    return [off] * n if n <= 1 else [off + length / 2 - i * length / (n - 1) for i in range(n)]

def probe():
    data = json.loads((project / "Assets/Rr2dv/ProbeInput.json").read_text())
    problems = ["fake problem"] if mode == "problems" else []
    vehicles = []
    for v in data["vehicles"]:
        nodes = [{"path": "", "position": [0, 0, 0], "rotation": [0, 0, 0, 1], "lossyScale": [1, 1, 1]}]
        wheels, clips = [], []
        for w in v["wheelsets"]:
            r = w["diameter"] / 2
            paths = []
            for i, z in enumerate(axles(w)):
                p = f"Main/{w['clip']}{i + 1}"
                paths.append(p)
                nodes.append({"path": p, "position": [0, r, z], "rotation": [0, 0, 0, 1], "lossyScale": [1, 1, 1]})
            wheels.append({"clip": w["clip"], "sourceRadius": r, "rotatingPaths": paths,
                           "meshes": [{"path": p + "/wheel", "used": True} for p in paths],
                           "bands": [{"radius": r * 0.998, "vertices": 40, "lateralMin": 0.72, "lateralMax": 0.8},
                                     {"radius": r * 1.07, "vertices": 20, "lateralMin": 0.7, "lateralMax": 0.72}]})
            clips.append({"key": w["clip"], "poses": [{"path": p} for p in paths]})
        anchors = [{"kind": c["kind"], "name": c["name"], "resolved": True, "position": c["position"]} for c in v["components"]]
        out_v = {"id": v["id"], "role": v["role"], "prefab": v["prefab"], "nodes": nodes, "wheels": wheels, "clips": clips,
                 "anchors": anchors, "boundsMin": [-1.5, 0.0, -4.4], "boundsMax": [1.5, 4.0, 5.5], "audioSources": 0}
        cab = v.get("cab")
        if cab:  # a flat backhead 0.5 m ahead of the rays' start, 1.4 m wide
            out_v["cabRays"] = [{"x": x, "y": y, "hit": abs(x) <= 0.7, "z": cab["startZ"] + 0.5, "distance": 0.5,
                                 "normalZ": -1.0, "part": "Main/Backhead"} for y in cab["ys"] for x in cab["xs"]]
        if v["role"] == "truck":
            out_v["truckWheels"] = [{"path": f"truck/Wheel{i}_LOD0", "wheelNode": f"truck/Wheel{i}_LOD0", "centre": [0, 0.42, z],
                                     "maxRadius": 0.45, "vertices": 60,
                                     "bands": [{"radius": 0.42, "vertices": 40, "lateralMin": 0.72, "lateralMax": 0.8},
                                               {"radius": 0.445, "vertices": 20, "lateralMin": 0.7, "lateralMax": 0.72}]}
                                    for i, z in ((1, 0.84), (2, -0.84))]
            out_v["nodes"] += [{"path": "truck", "position": [0, 0, 0]}] + [{"path": w["path"], "position": w["centre"]} for w in out_v["truckWheels"]]
        vehicles.append(out_v)
    (out / "probe.json").write_text(json.dumps({"schema": 1, "vehicles": vehicles, "problems": problems}))
    (out / "result.json").write_text(json.dumps({"status": "problems" if problems else "passed", "exitCode": 2 if problems else 0,
                                                "problems": len(problems), "runtimeValidated": False}))
    return 2 if problems else 0

def build():
    rec = json.loads(Path(os.environ["CCL_VEHICLE_RECORD"]).read_text())
    inp = json.loads((project / "Assets/Rr2dv/BuildInput.json").read_text())
    (out / "prep.json").write_text(json.dumps({"schema": 1, "removedBindings": [{"clip": a["clip"], "hash": h, "bindings": 1}
        for a in inp["absentBindings"] for h in a["hashes"]], "audioStripped": [], "parts": [
        {"vehicle": c["vehicle"], "part": p["name"]} for c in inp["composites"] for p in c["parts"]]}))
    if mode == "build-fails":
        (out / "build_report.txt").write_text("CclLocoBuild\nEXCEPTION System.InvalidOperationException: insufficient end-beam rays: 3\n")
        (out / "result.json").write_text('{"exported":false,"warnings":0,"runtimeValidated":false}')
        return 1
    name = rec["config"]["CarName"]
    pack = out / name
    pack.mkdir(parents=True)
    (pack / "Info.json").write_text(json.dumps({"Id": rec["config"]["CarId"], "DisplayName": name, "Requirements": ["DVCustomCarLoader"]}))
    (pack / "ccl_bundle").write_bytes(hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).digest())
    (out / "build_report.txt").write_text("CclLocoBuild\nWARN control sweep: C_Throttle meets C_Reverser at 30 deg\n\nwarnings: 1\n")
    (out / "record_seen.json").write_text(json.dumps({"env": {k: os.environ.get(k) for k in ("CCL_SHARE", "CCL_NEW_LOCO", "CCL_CATALOG_RECORD")}}))
    (out / "result.json").write_text('{"exported":true,"warnings":1,"runtimeValidated":false}')
    return 0

def audit():
    inp = json.loads((project / "Assets/Rr2dv/AuditInput.json").read_text())
    errors = ["1 AudioClip(s) in the bundle: whistle"] if mode == "build-audio" else []
    (out / "audit.json").write_text(json.dumps({"schema": 1, "status": "failed" if errors else "passed", "errors": errors,
        "warnings": ["the HUD has no reading for brakePipe (no instrument for it in the model)"], "audioClips": len(errors),
        "scriptAssemblies": ["CCL.Types"], "portFeeders": inp["ports"], "input": inp}))
    (out / "result.json").write_text(json.dumps({"status": "failed" if errors else "passed", "errors": len(errors), "warnings": 1,
                                                "runtimeValidated": False}))
    return 2 if errors else 0

sys.exit({"Rr2dvProbe.Run": probe, "Rr2dvBuild.Build": build, "Rr2dvAudit.Run": audit}[method]())
'''


def fake_unity(folder: Path) -> Path:
    return fake_tool(folder, "Unity", FAKE_UNITY)


def tool_machine(tmp: Path) -> dict:
    """Settings for a machine with fake AssetRipper, Unity and CarCreator (POSIX tests)."""
    os.environ["FAKE_AR_STATE"] = str(tmp / "ar-state")
    # Most stage tests inspect intermediate artifacts; production defaults to deleting them.
    return {"keepWorkFiles": True, "workRoot": str(tmp / "work"), "assetRipper": str(fake_assetripper(tmp / "tools")),
            "unity": str(fake_unity(tmp / "tools")), "carCreator": str(fake_carcreator(tmp / "tools" / "CarCreator_3.1.9.unitypackage")),
            **game_installs(tmp)}
