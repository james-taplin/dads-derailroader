"""Measure the stock S282A CupOnly visual/collider in root-local metres."""

from pathlib import Path
import numpy as np
import UnityPy
from UnityPy.helpers.MeshHelper import MeshHandler


ASSETS = Path(r"B:/SteamLibrary/steamapps/common/Derail Valley/DerailValley_Data/resources.assets")
environment = UnityPy.load(str(ASSETS))
objects = {object_.path_id: object_ for object_ in environment.objects}


def tree(path_id):
    return objects[path_id].read_typetree()


def xyz(value):
    return np.array([value[key] for key in ("x", "y", "z")], dtype=float)


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


def components(game_object_id):
    return [objects[c["component"]["m_PathID"]] for c in tree(game_object_id)["m_Component"]]


def transform_id(game_object_id):
    return next(component.path_id for component in components(game_object_id) if component.type.name == "Transform")


def parent_id(game_object_id):
    parent = tree(transform_id(game_object_id))["m_Father"]["m_PathID"]
    return tree(parent)["m_GameObject"]["m_PathID"] if parent else None


def path(game_object_id):
    parts = []
    while game_object_id:
        parts.append(tree(game_object_id)["m_Name"])
        game_object_id = parent_id(game_object_id)
    return "/".join(reversed(parts))


def walk(game_object_id, pose, name, root=False):
    game_object = tree(game_object_id)
    transform = tree(transform_id(game_object_id))
    pose = pose if root else pose @ matrix(transform)
    name += "/" + game_object["m_Name"]
    for component in components(game_object_id):
        if component.type.name == "MeshFilter":
            reference = tree(component.path_id)["m_Mesh"]
            mesh = objects[reference["m_PathID"]].read()
            handler = MeshHandler(mesh)
            handler.process()
            vertices = np.asarray(handler.m_Vertices)
            vertices = (pose @ np.c_[vertices, np.ones(len(vertices))].T).T[:, :3]
            print("MESH", name, "id", reference["m_PathID"], "min", vertices.min(axis=0), "max", vertices.max(axis=0))
        if "Collider" in component.type.name:
            print("COLLIDER", name, component.type.name, "pose", pose.round(4), "data", tree(component.path_id))
    for child in transform["m_Children"]:
        walk(tree(child["m_PathID"])["m_GameObject"]["m_PathID"], pose, name)


if __name__ == "__main__":
    matches = [o.path_id for o in environment.objects if o.type.name == "GameObject" and tree(o.path_id)["m_Name"] == "OilingPoint0"]
    for match in matches:
        print("CANDIDATE", match, path(match))
    # The S282A CupOnly is the first of its external-interactables oiling points.
    selected = next(match for match in matches if path(match).startswith("LocoS282A_ExternalInteractables/"))
    print("SELECTED", selected, path(selected))
    walk(selected, np.eye(4), "", True)
