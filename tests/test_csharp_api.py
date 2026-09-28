"""Guard for C# we cannot compile here (board X29): every Unity editor API member our app's editor scripts call must
already appear in C# that has compiled in Unity 2019.4 (our tooling's builder core and probes), or be reviewed below.
Where the Mono C# compiler is installed, the scripts are also type-checked against compile-only Unity stand-ins
(tests/unity_stubs), which catches syntax and type slips; it proves nothing about the real API beyond the list above."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP_CS = sorted((REPO / "src/rr2dv/unity").glob("*.cs"))
KNOWN_GOOD = sorted((REPO / "tooling").rglob("*.cs"))
CLASSES = ("AnimationUtility", "AssetDatabase", "EditorApplication", "EditorSceneManager", "PrefabUtility",
           "JsonUtility", "Application", "Physics", "Mathf", "Shader", "Debug", "AssetBundle", "EditorUtility",
           "SerializedPropertyType", "GameObjectUtility")
# Members checked by hand against the Unity 2019.4 scripting reference, with a reason.
REVIEWED = {
    "SerializedPropertyType.Integer": "Compiled by engine-metrics diagnostic in Unity 2019.4.40f1; distinguishes integer cylinder count from float simulation fields",
    "AnimationUtility.SetKeyLeftTangentMode": "Compiled and exercised by InteractionRegression in Unity 2019.4.40f1 (displacement-resampled source clips)",
    "AnimationUtility.SetKeyRightTangentMode": "Compiled and exercised by InteractionRegression in Unity 2019.4.40f1",
    "AnimationUtility.TangentMode": "Linear enum used by the passing Unity 2019.4.40f1 interaction regression",
    "Mathf.Clamp": "Compiled and exercised with Rr2dvInteractions in Unity 2019.4.40f1; float Clamp(float, float, float)",
    "GameObjectUtility.RemoveMonoBehavioursWithMissingScript": "https://docs.unity3d.com/2019.4/Documentation/ScriptReference/GameObjectUtility.RemoveMonoBehavioursWithMissingScript.html (returns removed count)",
    "JsonUtility.ToJson": "UnityEngine.JsonUtility.ToJson(object, bool), Unity 2019.4 scripting reference",
    "AssetDatabase.GetDependencies": "UnityEditor.AssetDatabase.GetDependencies(string[] pathNames, bool recursive), 2019.4",
    "AssetDatabase.GetMainAssetTypeAtPath": "UnityEditor.AssetDatabase.GetMainAssetTypeAtPath(string assetPath) -> Type, 2019.4",
    "AssetBundle.LoadFromFile": "UnityEngine.AssetBundle.LoadFromFile(string path) -> AssetBundle (null on failure), 2019.4",
    "SerializedPropertyType.ObjectReference": "UnityEditor.SerializedPropertyType.ObjectReference, 2019.4",
}


def members(files):
    rx = re.compile(r"\b(" + "|".join(CLASSES) + r")\.([A-Z]\w*)")
    found = set()
    for f in files:
        found |= {f"{a}.{b}" for a, b in rx.findall(f.read_text(encoding="utf-8-sig", errors="replace"))}
    return found


class UnityApi(unittest.TestCase):
    def test_every_editor_api_member_has_compiled_before(self):
        self.assertTrue(APP_CS, "no app C# found")
        self.assertTrue(KNOWN_GOOD, "tooling C# missing")
        used = members(APP_CS)
        unknown = sorted(used - members(KNOWN_GOOD) - set(REVIEWED))
        self.assertEqual(unknown, [], "not seen in compiled tooling C#; check the Unity 2019.4 API and add to REVIEWED")

    @unittest.skipUnless(shutil.which("mcs"), "needs the Mono C# compiler (mcs)")
    def test_scripts_compile_against_unity_stand_ins(self):
        stubs = REPO / "tests/unity_stubs/UnityStubs.cs"
        with tempfile.TemporaryDirectory() as tmp:
            # The placement extension shares private members with the actual pinned builder;
            # compile and exercise it with PlacementRegression in Unity, not fake core internals.
            standalone = [p for p in APP_CS if p.name not in ("Rr2dvPlacement.cs", "Rr2dvFeatures.cs", "Rr2dvInteractions.cs", "Rr2dvOpeningMotion.cs", "Rr2dvSourceFinishing.cs")]
            proc = subprocess.run(["mcs", "-target:library", "-langversion:7", f"-out:{tmp}/app.dll", str(stubs), *map(str, standalone)],
                                  capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_no_helper_hides_a_framework_type(self):
        for f in APP_CS:
            names = re.findall(r"static \w+(?:\[\])? (Path|File|Directory|Object|Debug|Input|Application)\(", f.read_text())
            self.assertEqual(names, [], f"{f.name}: a method named like a framework type hides it")


if __name__ == "__main__":
    unittest.main()
