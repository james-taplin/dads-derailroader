"""The locomotives this edition converts: Railroader's own 21 stock steam locomotives, by asset-pack name.

vanilla-flavoured (James, 2026-09-30): no modded locomotives. The only input is one of these packs in Railroader's
Railroader_Data/StreamingAssets/AssetPacks folder. The three stock diesels are known but not converted in this
release (diesel integration continues on the 0.3.x branch). Nothing here reads a file; the names are the packs'
folder names, which are also their locomotive identifiers.
"""
from __future__ import annotations

# pack folder name -> display name (the Definitions.json metadata name)
STEAM: dict[str, str] = {
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

DIESEL: dict[str, str] = {
    "ld-gp9": "EMD GP9",
    "ld-sd7": "EMD SD7",
    "ld-sw1": "EMD SW1",
}


# Railroader's optional whistle meshes live in one pack; a whistle is a model plus a clip (VF9). The default is what a
# locomotive gets when its definition names none (James, 2026-09-30).
WHISTLE_PACK = "audio.whistles01"
DEFAULT_WHISTLE = "wh-3-std"


def refusal(pack_name: str) -> str | None:
    """Why a pack folder name is not converted here, or None when it is one of the 21 stock steam locomotives."""
    if pack_name in STEAM:
        return None
    if pack_name in DIESEL:
        return (f"{pack_name} ({DIESEL[pack_name]}) is a stock diesel; diesel locomotives are not supported in this release "
                "(diesel integration is on the 0.3.x branch)")
    return (f"{pack_name} is not one of Railroader's 21 stock steam locomotives; this edition converts only those "
            f"({', '.join(sorted(STEAM))})")
