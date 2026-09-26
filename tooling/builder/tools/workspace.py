"""Paths are owned by the local workspace and machine manifests."""
from pathlib import Path
import json, sys
WORKSPACE=Path(__file__).resolve().parents[2]
CONFIG=json.loads((WORKSPACE/'workspace.json').read_text(encoding='utf-8-sig'))
MACHINE=json.loads((WORKSPACE/'machine.local.json').read_text(encoding='utf-8-sig'))
ROOT=WORKSPACE/CONFIG['builder']
def location(value):
    p=Path(value)
    return p if p.is_absolute() else WORKSPACE/p
def profile_path(profile,key):return location(CONFIG['profiles'][profile][key])
def enable_unitypy():
    site=MACHINE.get('unityPySitePackages')
    if site:sys.path.append(site)
