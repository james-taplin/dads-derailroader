"""Clip bindings to nodes whose names end in a space (P-18 'Trailing ', P-43 'Reverser ', T-22 'Right Door Window ')."""
import json
import tempfile
import unittest
import zlib
from pathlib import Path

import fixtures  # noqa: F401
from rr2dv import unityproject


def prefab(names):
    """A chain root -> names[0] -> names[1] ... as Unity YAML (GameObject = class 1, Transform = class 4)."""
    docs = []
    for i, name in enumerate(names):
        go, tr = 100 + i, 200 + i
        father = 200 + i - 1 if i else 0
        docs.append(f"--- !u!1 &{go}\nGameObject:\n  m_Name: {name}\n")
        docs.append(f"--- !u!4 &{tr}\nTransform:\n  m_GameObject: {{fileID: {go}}}\n  m_Father: {{fileID: {father}}}\n")
    return "".join(docs)


def clip(path_hash):
    return f"AnimationClip:\n  m_Name: c\n  curve:\n    path: path_0x{path_hash:X}_abc\n"


class SpacedNames(unittest.TestCase):
    def resolve(self, names, relative_path):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "m.prefab").write_text(prefab(names), encoding="utf-8")
            (src / "c.anim").write_text(clip(zlib.crc32(relative_path.encode())), encoding="utf-8")
            dest = Path(tmp) / "dest"
            result = unityproject._resolve(src, dest, Path(tmp) / "report.json")
            return result, ((dest / "c.anim").read_text(encoding="utf-8") if (dest / "c.anim").is_file() else "")

    def test_a_name_with_a_trailing_space_resolves(self):
        result, text = self.resolve(["body", "engine", "Trailing ", "Bone"], "Trailing /Bone")
        self.assertEqual(result["errors"], [])
        self.assertIn("path: engine/Trailing /Bone", text)

    def test_a_binding_that_ends_on_the_spaced_node_is_quoted(self):
        result, text = self.resolve(["body", "engine", "Trailing "], "Trailing ")
        self.assertEqual(result["errors"], [])
        self.assertIn("path: 'engine/Trailing '", text)

    def test_plain_names_still_resolve_as_before(self):
        result, text = self.resolve(["body", "engine", "Drivers", "Bone"], "Drivers/Bone")
        self.assertEqual(result["errors"], [])
        self.assertIn("path: engine/Drivers/Bone", text)


if __name__ == "__main__":
    unittest.main()
