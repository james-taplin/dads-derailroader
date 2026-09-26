"""Guard for C# we cannot compile here (board X29): every Unity editor API member Rr2dvProbe.cs calls must already
appear in C# that has compiled in Unity 2019.4 (our tooling's builder core and probes), or be reviewed below."""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP_CS = sorted((REPO / "src/rr2dv/unity").glob("*.cs"))
KNOWN_GOOD = sorted((REPO / "tooling").rglob("*.cs"))
CLASSES = ("AnimationUtility", "AssetDatabase", "EditorApplication", "EditorSceneManager", "PrefabUtility",
           "JsonUtility", "Application", "Physics", "Mathf", "Shader", "Debug")
# Members checked by hand against the Unity 2019.4 scripting reference, with a reason.
REVIEWED = {
    "JsonUtility.ToJson": "UnityEngine.JsonUtility.ToJson(object, bool), Unity 2019.4 scripting reference",
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

    def test_no_helper_hides_a_framework_type(self):
        for f in APP_CS:
            names = re.findall(r"static \w+(?:\[\])? (Path|File|Directory|Object|Debug|Input|Application)\(", f.read_text())
            self.assertEqual(names, [], f"{f.name}: a method named like a framework type hides it")


if __name__ == "__main__":
    unittest.main()
