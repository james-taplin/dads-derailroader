"""Supported conversion scope and retained stock tuning reference, by asset-pack name.

vanilla-flavoured (James, 2026-09-30): no modded locomotives. The only input is one of the ten supported packs in Railroader's
Railroader_Data/StreamingAssets/AssetPacks folder. The three stock diesels are known but not converted in this
release (diesel integration continues on the 0.3.x branch). Nothing here reads a file; the names are the packs'
folder names, which are also their locomotive identifiers.
"""
from __future__ import annotations

# pack folder name -> display name (the Definitions.json metadata name)
KNOWN_STEAM: dict[str, str] = {
    "ls-060-s23": "S-23 Switcher",
    "ls-080-s51": "S-51 Switcher",
    "ls-2100-d46": "D-46 Decapod",
    "ls-2102-f71": "F-71 Santa Fe",
    "ls-260-g16": "G-16 Mogul",
    "ls-260-g25": "G-25 Mogul",
    "ls-280-c25": "C-25 Consolidation",
    "ls-280-c46": "C-46 Consolidation",
    "ls-280-c55": "C-55 Consolidation",
    "ls-282-k28t": "K-28T Logging Tank Mikado",
    "ls-282-k35": "K-35 Logging Mikado",
    "ls-284-b65": "B-65 Berkshire",
    "ls-440-a23": "A-23 American",
    "ls-442-a26": "A-26 Atlantic",
    "ls-460-t17": "T-17 Ten Wheeler",
    "ls-460-t21": "T-21 Ten Wheeler",
    "ls-460-t22": "T-22 Ten Wheeler",
    "ls-462-p18": "P-18 Pacific",
    "ls-462-p43": "P-43 Pacific",
    "ls-462-p48": "P-48 Pacific",
    "ls-480-c40": "C-40 Mastodon",
}

# Keep the complete measurement table as reference; it does not grant conversion support.
REAL_STEAM = frozenset(KNOWN_STEAM)
SUPPORTED_STEAM = frozenset({
    'ls-440-a23', 'ls-442-a26', 'ls-280-c25', 'ls-2100-d46', 'ls-2102-f71',
    'ls-260-g25', 'ls-282-k35', 'ls-462-p18', 'ls-460-t17', 'ls-460-t22',
})
STEAM: dict[str, str] = {key: name for key, name in KNOWN_STEAM.items() if key in SUPPORTED_STEAM}
EXCLUDED_STEAM = REAL_STEAM - SUPPORTED_STEAM

DIESEL: dict[str, str] = {
    "ld-gp9": "EMD GP9",
    "ld-sd7": "EMD SD7",
    "ld-sw1": "EMD SW1",
}


# Railroader's optional whistle meshes live in one pack; a whistle is a model plus a clip (VF9). The default is what a
# locomotive gets when its definition names none (James, 2026-09-30).
WHISTLE_PACK = "audio.whistles01"
DEFAULT_WHISTLE = "wh-3-std"
EXCLUDED_WHISTLES = frozenset({'wh-6-reading'})


def refusal(pack_name: str) -> str | None:
    """Why a pack folder name is not converted in this test edition."""
    if pack_name in STEAM:
        return None
    if pack_name in EXCLUDED_STEAM:
        return f"{pack_name} ({KNOWN_STEAM[pack_name]}) is not supported in this ten-locomotive test edition"
    if pack_name in DIESEL:
        return (f"{pack_name} ({DIESEL[pack_name]}) is a stock diesel; diesel locomotives are not supported in this release "
                "(diesel integration is on the 0.3.x branch)")
    return (f"{pack_name} is not one of this edition's ten supported stock steam locomotives; this edition converts only those "
            f"({', '.join(sorted(STEAM))})")


# ---------------------------------------------------------------------------------------------------------------------
# The per-locomotive table (stock_locos.json, built by tools/vanilla/make_table.py): every fact the conversion relies on
# for each of the 21 locomotives, with its basis, so nothing is left to inference at conversion time (James, 2026-09-30).
import json  # noqa: E402
from functools import lru_cache  # noqa: E402
from pathlib import Path  # noqa: E402

TABLE_FILE = Path(__file__).with_name("stock_locos.json")
REQUIRED = ("displayName", "whyte", "tank", "tender", "source", "driver", "answers", "whistle", "gauges", "cab", "endBeam",
            "lodMeshes", "knownOddities", "hide", "conversion", "sourceSha256")
HASHED_FILES = ("Bundle", "Catalog.json", "Definitions.json")


@lru_cache(maxsize=1)
def table() -> dict:
    return json.loads(TABLE_FILE.read_text(encoding="utf-8"))


def entry(pack_name: str) -> dict | None:
    """The table's entry for a stock steam pack, or None for a name the table does not know (only test packs)."""
    return table()["locos"].get(pack_name)


def validate_table(data: dict | None = None) -> list[str]:
    """Every problem that would leave a conversion fact ambiguous: a missing pack, field, basis or hash."""
    data = table() if data is None else data
    problems = []
    if not isinstance(data.get("gameBuild"), str) or not data["gameBuild"]:
        problems.append("the table does not say which game build it describes")
    locos = data.get("locos", {})
    if set(locos) != set(REAL_STEAM):
        problems.append(f"the table's locomotives differ from the stock list: {sorted(set(locos) ^ set(REAL_STEAM))}")
    for name, e in sorted(locos.items()):
        for key in REQUIRED:
            if key not in e or e[key] is None and key != "tender":
                problems.append(f"{name}: '{key}' is missing")
        if e.get("tender") is None and not e.get("tank"):
            problems.append(f"{name}: no tender but not marked as a tank locomotive")
        drv = e.get("driver", {})
        if not (isinstance(drv.get("radiusM"), (int, float)) and .1 <= drv["radiusM"] <= 1.5 and drv.get("basis") and drv.get("evidence")):
            problems.append(f"{name}: the driver radius needs a value in 0.1..1.5 m, a basis and evidence")
        ans = e.get("answers", {})
        if ans.get("cylinders") != 2 or ans.get("firing") != "hand-fired" or ans.get("dynamo") != "yes" or not ans.get("basis"):
            problems.append(f"{name}: answers must be 2 cylinders, hand-fired, dynamo yes, with a basis")
        if set(e.get("sourceSha256", {})) != set(HASHED_FILES) or any(len(str(v)) != 64 for v in e.get("sourceSha256", {}).values()):
            problems.append(f"{name}: sourceSha256 must hold a 64-digit hash for {HASHED_FILES}")
        eb = e.get("endBeam", {})
        if not eb:
            problems.append(f"{name}: endBeam must be a band per tender or a note saying none is needed")
        for vid, band in eb.items():
            if vid == "none":
                continue
            if not band.get("evidence") or len(band.get("band", [])) != 2:
                problems.append(f"{name}: end-beam band for {vid} needs two heights and evidence")
        for h in e.get("hide", []):
            if not h.get("path") or not h.get("why"):
                problems.append(f"{name}: every hidden mesh needs a path and a reason")
        if e.get("conversion", {}).get("status") not in ("untested", "converted"):
            problems.append(f"{name}: conversion status must be 'untested' or 'converted'")
    return problems


def build_status(pack_name: str, inventory_packs: list[dict]) -> tuple[bool, str]:
    """(matches, text): does the installed pack carry the exact files the table describes? An unknown build is reported,
    never refused (James, 2026-09-30: Railroader is splitting legacy and beta on Steam)."""
    e = entry(pack_name)
    if e is None:
        return False, f"{pack_name} is not in the vanilla table"
    pack = next((p for p in inventory_packs if p.get("name") == pack_name), None)
    if pack is None:
        return False, "the pack's files were not inventoried"
    have = {f["name"]: f["sha256"] for f in pack.get("files", [])}
    differ = [n for n in HASHED_FILES if have.get(n) != e["sourceSha256"][n]]
    if differ:
        return False, (f"unknown game build: {', '.join(differ)} differ from the vanilla table (recorded for Railroader build "
                       f"{table()['gameBuild']}); table values are used only where the definition agrees")
    return True, f"matches the vanilla table (Railroader build {table()['gameBuild']})"
