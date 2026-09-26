"""Check the configured C-21 cup points against the exported source rod vertices."""

from pathlib import Path
import re

import numpy as np

from offline_oil_probe import ROOT, mesh_for_reference, mesh_geometry, source_parts


CONFIG = ROOT / "unity/C21_CCL/Assets/Editor/C21Config.cs"
ANCHOR = re.compile(
    r'new OilAnchor \{Tag="([^"]+)",SourcePath="([^"]+)",'
    r'CarPosition=new Vector3\((-?[\d.]+)f,(-?[\d.]+)f,\s*(-?[\d.]+)f\),SourceTriangles=(\d+)\}'
)


def main():
    entries = ANCHOR.findall(CONFIG.read_text(encoding="utf-8-sig"))
    expected = [f"MOP {side} {i}" for side in (-1, 1) for i in range(4)]
    assert [entry[0] for entry in entries] == expected, "Oil point count/order/tags changed"
    parts = source_parts()
    max_error = 0.0
    for tag, path, x, y, z, triangles_expected in entries:
        position = np.array([float(x), float(y), float(z)])
        reference, transform, _ = parts[path]
        vertices, triangles = mesh_geometry(mesh_for_reference(reference))
        assert len(triangles) == int(triangles_expected), (tag, "source mesh changed")
        world = (transform @ np.c_[vertices, np.ones(len(vertices))].T).T[:, :3]
        nearby = world[np.linalg.norm(world[:, [0, 2]] - position[[0, 2]], axis=1) < 0.04]
        assert len(nearby), (tag, "cap missing")
        error = abs(nearby[:, 1].max() - position[1])
        max_error = max(max_error, error)
        assert error < 0.003, (tag, "source cap height changed", error)
        print(f"{tag}: {path} car={position} cap-top-error={error*1000:.2f} mm")
    print(f"Validated {len(entries)} source cap anchors; worst vertical error {max_error*1000:.2f} mm")


if __name__ == "__main__":
    main()
