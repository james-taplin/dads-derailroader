"""Scope tripwires: the app reads Railroader's 21 supported stock steam locomotives.

These read the source files, not the runtime lists, because other tests add synthetic pack names to stock.STEAM for the
test process (fixtures.register_stock). If one of these fails, modded-locomotive support has crept back in."""
import ast
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from fixtures import game_installs, standard_mod, tool_machine

SRC = Path(__file__).resolve().parents[1] / "src" / "rr2dv"

STEAM = {"ls-060-s23", "ls-080-s51", "ls-2100-d46", "ls-2102-f71", "ls-260-g16", "ls-260-g25", "ls-280-c25", "ls-280-c46",
         "ls-280-c55", "ls-282-k28t", "ls-282-k35", "ls-284-b65", "ls-440-a23", "ls-442-a26", "ls-460-t17", "ls-460-t21",
         "ls-460-t22", "ls-462-p18", "ls-462-p43", "ls-462-p48", "ls-480-c40"}
DIESEL = {"ld-gp9", "ld-sd7", "ld-sw1"}


def literal_dict_keys(source: str, name: str) -> set[str]:
    for node in ast.parse(source).body:
        target = getattr(node, "target", None) or (node.targets[0] if isinstance(node, ast.Assign) else None)
        if isinstance(target, ast.Name) and target.id == name and isinstance(node.value, ast.Dict):
            return {k.value for k in node.value.keys}
    raise AssertionError(f"{name} not found in stock.py")


class StockList(unittest.TestCase):
    def test_the_source_lists_exactly_the_24_stock_locomotives(self):
        source = (SRC / "stock.py").read_text(encoding="utf-8")
        self.assertEqual(literal_dict_keys(source, "STEAM"), STEAM)
        self.assertEqual(literal_dict_keys(source, "DIESEL"), DIESEL)
        self.assertEqual(len(STEAM) + len(DIESEL), 24)

    def test_refusal_messages(self):
        from rr2dv import stock
        self.assertIsNone(stock.refusal("ls-282-k28t"))
        self.assertIn("not supported in this release", stock.refusal("ld-gp9"))
        self.assertIn("not one of Railroader's 21 stock steam locomotives", stock.refusal("Some Loco Mod"))


class NoModdedLocomotiveSupport(unittest.TestCase):
    FORBIDDEN = {
        r"\bmod_in_railroader\b": "the Mods-folder input function",
        r"searchRoots": "the searchRoots setting",
        r"--search\b|no-default-search": "the --search options",
        r"\brr\.mods\b|\brailroader\.mods\b": "Railroader's Mods folder",
        r"\blist_mods\b": "the mod list",
        r"\bsearch_roots\(\s*rr\s*,": "extra search roots",
        r"\bcodemods\b|\bcode_mods\b|\bcodeMods\b|LegosBetterSteam": "code-mod handling",
        r"\brailroader_only\b|\boptional_groups\b|\bbulkAdds\b|\bGroupFile\b": "mod component groups",
        r"\bfind_mod\b|\bfind_texture\b|\bextra_files\b": "mod lookups",
    }

    def test_source_has_none_of_the_removed_entry_points(self):
        found = []
        for path in sorted(SRC.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for pattern, what in self.FORBIDDEN.items():
                for match in re.finditer(pattern, text):
                    found.append(f"{path.name}: {what} ({match.group(0)})")
        self.assertEqual(found, [])

    def test_settings_and_command_line_have_no_search_roots(self):
        from rr2dv import cli
        from rr2dv.machine import Machine
        self.assertFalse(hasattr(Machine, "search_roots"))
        text = cli.build_parser().format_help()
        for sub in ("scan", "convert"):
            with self.assertRaises(SystemExit):
                cli.build_parser().parse_args([sub, "ls-282-k28t", "--search", "x"])
        self.assertNotIn("search", text.replace("research", ""))


class RefusedBeforeAnythingIsRead(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.m = standard_mod(self.tmp)
        from rr2dv.machine import Machine
        self.machine = Machine(None, tool_machine(self.tmp))

    def test_mods_folder_or_unknown_or_diesel_or_link_inputs_create_nothing(self):
        from rr2dv import installs
        from rr2dv.pipeline import convert
        rr = self.tmp / "Railroader"
        (rr / "Mods" / "Some Loco Mod" / "pack").mkdir(parents=True)
        (rr / "Mods" / "ls-282-k28t").mkdir(parents=True)
        packs = self.m["search"]
        (packs / "ld-gp9").mkdir()
        (packs / "SomeMod").mkdir()
        for bad in ("Some Loco Mod", rr / "Mods" / "Some Loco Mod", rr / "Mods" / "ls-282-k28t", "ls-282-k28t", "ld-gp9",
                    "SomeMod", packs / "SomeMod", packs / ".." / "SomeMod", self.tmp):
            with self.assertRaises(installs.InstallError, msg=str(bad)):
                convert(bad, self.machine)
        self.assertFalse((self.tmp / "work").exists(), "no run folder may be created for a refused input")


if __name__ == "__main__":
    unittest.main()
