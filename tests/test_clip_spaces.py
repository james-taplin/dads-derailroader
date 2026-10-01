"""Clip bindings to nodes whose names end in a space (P-18 'Trailing ', P-43 'Reverser ', T-22 'Right Door Window ')."""
import json
import tempfile
import unittest
import zlib
from pathlib import Path

import fixtures  # noqa: F401
from rr2dv import unityproject


def prefab(names, quote=False):
    """A chain root -> names[0] -> names[1] ... as Unity YAML (GameObject = class 1, Transform = class 4). With `quote`, a name with a space
    at its end is written the way AssetRipper does, as a quoted string."""
    docs = []
    for i, name in enumerate(names):
        go, tr = 100 + i, 200 + i
        father = 200 + i - 1 if i else 0
        shown = "'" + name.replace("'", "''") + "'" if quote and name != name.strip() else name
        docs.append(f"--- !u!1 &{go}\nGameObject:\n  m_Name: {shown}\n")
        docs.append(f"--- !u!4 &{tr}\nTransform:\n  m_GameObject: {{fileID: {go}}}\n  m_Father: {{fileID: {father}}}\n")
    return "".join(docs)


def clip(path_hash):
    return f"AnimationClip:\n  m_Name: c\n  curve:\n    path: path_0x{path_hash:X}_abc\n"


class SpacedNames(unittest.TestCase):
    def resolve(self, names, relative_path, quote=False):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "m.prefab").write_text(prefab(names, quote), encoding="utf-8")
            (src / "c.anim").write_text(clip(zlib.crc32(relative_path.encode())), encoding="utf-8")
            dest = Path(tmp) / "dest"
            result = unityproject._resolve(src, dest, Path(tmp) / "report.json")
            return result, ((dest / "c.anim").read_text(encoding="utf-8") if (dest / "c.anim").is_file() else "")

    def test_a_name_with_a_trailing_space_resolves(self):
        result, text = self.resolve(["body", "engine", "Trailing ", "Bone"], "Trailing /Bone")
        self.assertEqual(result["errors"], [])
        self.assertIn("path: engine/Trailing /Bone", text)

    def test_a_quoted_name_is_the_name_without_its_quotes(self):
        # AssetRipper writes m_Name: 'Trailing ' (P-18, P-43, T-22 in the 0.4.1 build, 2026-10-01)
        result, text = self.resolve(["body", "engine", "Trailing ", "Bone"], "Trailing /Bone", quote=True)
        self.assertEqual(result["errors"], [])
        self.assertIn("path: engine/Trailing /Bone", text)
        self.assertEqual(unityproject._yaml_name("'It''s '"), "It's ")
        self.assertEqual(unityproject._yaml_name('"A b "'), "A b ")
        self.assertEqual(unityproject._yaml_name("Plain name\r"), "Plain name")

    def test_a_binding_that_ends_on_the_spaced_node_is_quoted(self):
        result, text = self.resolve(["body", "engine", "Trailing "], "Trailing ")
        self.assertEqual(result["errors"], [])
        self.assertIn("path: 'engine/Trailing '", text)

    def test_plain_names_still_resolve_as_before(self):
        result, text = self.resolve(["body", "engine", "Drivers", "Bone"], "Drivers/Bone")
        self.assertEqual(result["errors"], [])
        self.assertIn("path: engine/Drivers/Bone", text)


class RootlessClips(unittest.TestCase):
    """C-55's tender clips are written relative to the 'Tender' child ('Coal Load/Bone'): the builder looks from the prefab root."""

    NODES = {"", "Tender", "Tender/Coal Load", "Tender/Coal Load/Bone", "Tender/Water Hatch", "Tender/Water Hatch/Bone"}

    def clip(self, *paths):
        return "AnimationClip:\n" + "".join(f"  curve:\n    path: {p}\n" for p in paths)

    def test_paths_that_fit_under_one_child_get_its_name(self):
        text, prefix = unityproject.prefix_missing_paths(self.clip("Coal Load/Bone", "Coal Load"), self.NODES)
        self.assertEqual(prefix, "Tender")
        self.assertIn("path: Tender/Coal Load/Bone", text)
        self.assertIn("path: Tender/Coal Load\n", text)

    def test_a_clip_that_already_resolves_is_left_alone(self):
        original = self.clip("Tender/Coal Load/Bone")
        self.assertEqual(unityproject.prefix_missing_paths(original, self.NODES), (original, None))

    def test_a_path_that_fits_nowhere_is_left_alone(self):
        original = self.clip("Coal Load/Bone", "No Such Part/Bone")
        self.assertEqual(unityproject.prefix_missing_paths(original, self.NODES), (original, None))

    def test_two_children_that_both_fit_are_not_guessed(self):
        nodes = self.NODES | {"Other", "Other/Coal Load", "Other/Coal Load/Bone"}
        original = self.clip("Coal Load/Bone")
        self.assertEqual(unityproject.prefix_missing_paths(original, nodes), (original, None))

    def test_unresolved_hashes_are_not_touched(self):
        original = self.clip("path_0x1234ABCD_xyz", "Coal Load/Bone")
        text, prefix = unityproject.prefix_missing_paths(original, self.NODES)
        self.assertIn("path: path_0x1234ABCD_xyz", text)
        self.assertEqual(prefix, "Tender")

    def test_node_paths_of_a_prefab_leave_out_the_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "m.prefab"
            f.write_text(prefab(["root", "Tender", "Coal Load", "Bone"]), encoding="utf-8")
            self.assertEqual(unityproject._node_paths(f), {"", "Tender", "Tender/Coal Load", "Tender/Coal Load/Bone"})


if __name__ == "__main__":
    unittest.main()
