"""Read Unity's exported C-21 YAML to inventory moving rod mesh islands without an Editor licence."""

from collections import defaultdict
from pathlib import Path
import re
import struct

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / "unity/C21_CCL/Assets"
PREFAB = ASSETS / "connor/ls-280-c21.prefab"
RODS = (
    "Main/Empty.004/Main Rod Left",
    "Main/Empty.006/Connecting Rod Left",
    "Main/Empty.028/Connecting Rod Left.001",
    "Main/Empty.030/Main Rod Left.001",
)
HEADER = re.compile(r"(?m)^--- !u!(\d+) &(-?\d+)\s*$")


def unity_documents(path):
    source = path.read_text(encoding="utf-8-sig")
    heads = list(HEADER.finditer(source))
    return {
        int(head.group(2)): (
            int(head.group(1)),
            yaml.safe_load(source[head.end() : heads[i + 1].start() if i + 1 < len(heads) else None]),
        )
        for i, head in enumerate(heads)
    }


def xyz(value):
    return np.array([value[k] for k in ("x", "y", "z")], dtype=float)


def matrix(transform):
    q = transform["m_LocalRotation"]
    x, y, z, w = (q[k] for k in ("x", "y", "z", "w"))
    rotation = np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )
    result = np.eye(4)
    result[:3, :3] = rotation @ np.diag(xyz(transform["m_LocalScale"]))
    result[:3, 3] = xyz(transform["m_LocalPosition"])
    return result


def source_parts():
    docs = unity_documents(PREFAB)
    game_objects = {fid: data["GameObject"] for fid, (kind, data) in docs.items() if kind == 1}
    transforms = {
        fid: data["Transform" if kind == 4 else "RectTransform"]
        for fid, (kind, data) in docs.items() if kind in (4, 224)
    }
    mesh_filters = {fid: data["MeshFilter"] for fid, (kind, data) in docs.items() if kind == 33}
    by_go = {t["m_GameObject"]["fileID"]: fid for fid, t in transforms.items()}
    go_by_transform = {fid: go for go, fid in by_go.items()}

    def path(fid):
        t = transforms[fid]
        parent = t["m_Father"]["fileID"]
        name = game_objects[go_by_transform[fid]]["m_Name"]
        return (path(parent) + "/" if parent else "") + name

    def world(fid):
        t = transforms[fid]
        parent = t["m_Father"]["fileID"]
        return (world(parent) if parent else np.eye(4)) @ matrix(t)

    result = {}
    for f in mesh_filters.values():
        go = f["m_GameObject"]["fileID"]
        tid = by_go[go]
        full_path = path(tid)
        for candidate in RODS:
            if full_path.endswith(candidate):
                result[candidate] = (f["m_Mesh"], world(tid), full_path)
    if set(result) != set(RODS):
        raise ValueError("Missing source rods: " + str(set(RODS) - set(result)))
    return result


def mesh_for_reference(reference):
    guid = reference["guid"]
    for meta in (ASSETS / "Mesh").glob("*.asset.meta"):
        if f"guid: {guid}" in meta.read_text(encoding="utf-8-sig"):
            return meta.with_suffix("")
    raise ValueError("No mesh asset for GUID " + guid)


def mesh_geometry(path):
    docs = unity_documents(path)
    mesh = next(data["Mesh"] for kind, data in docs.values() if kind == 43)
    data = mesh["m_VertexData"]
    count = data["m_VertexCount"]
    raw = bytes.fromhex(data["_typelessdata"])
    stride = len(raw) // count
    if len(raw) != stride * count or data["m_Channels"][0]["offset"] != 0:
        raise ValueError("Unexpected vertex layout: " + str(path))
    vertices = np.array([struct.unpack_from("<fff", raw, i * stride) for i in range(count)])
    index_format = mesh["m_IndexFormat"]
    fmt = "<" + ("H" if index_format == 0 else "I") * (len(bytes.fromhex(mesh["m_IndexBuffer"])) // (2 if index_format == 0 else 4))
    indices = np.array(struct.unpack(fmt, bytes.fromhex(mesh["m_IndexBuffer"]))).reshape(-1, 3)
    return vertices, indices


def islands(vertices, triangles):
    keys = [tuple(np.round(v, 7)) for v in vertices]
    welded = {}
    ids = []
    for key in keys:
        ids.append(welded.setdefault(key, len(welded)))
    parent = list(range(len(welded)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b, c in triangles:
        root = find(ids[a])
        parent[find(ids[b])] = root
        parent[find(ids[c])] = root
    grouped = defaultdict(list)
    for tri in triangles:
        grouped[find(ids[tri[0]])].append(tri)
    return list(grouped.values())


def main():
    lines = []
    for name, (reference, transform, full_path) in source_parts().items():
        mesh_path = mesh_for_reference(reference)
        vertices, triangles = mesh_geometry(mesh_path)
        world = (transform @ np.c_[vertices, np.ones(len(vertices))].T).T[:, :3]
        lines.append(f"PART {name} asset={mesh_path.name} path={full_path} triangles={len(triangles)}")
        lines.append("  transform=" + np.array2string(transform, precision=6, suppress_small=True))
        for group in sorted(islands(vertices, triangles), key=len, reverse=True):
            points = world[np.unique(np.array(group).flatten())]
            low, high = points.min(axis=0), points.max(axis=0)
            lines.append(
                f"  island triangles={len(group)} centre={np.round((low + high) / 2, 5)} "
                f"size={np.round(high - low, 5)} min={np.round(low, 5)} max={np.round(high, 5)}"
            )
    output = Path(__file__).with_name("rod_islands.txt")
    output.write_text("\n".join(lines) + "\n")
    print(output)


if __name__ == "__main__":
    main()
