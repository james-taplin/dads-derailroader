using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

// LLW G-29 Mogul (Railroader AssetPack 'LLW Generic Locomotive Catalog' v1.4.3, MarquetteCreations): 2-6-0 with a 6-wheel-class
// tender on two Fox swing-bolster trucks. The prefabs have no 'Master' wrapper: 'Main' (scale 100, rot -90 X, the Blender import)
// holds the animated parts, so clip paths resolve from the prefab root as in the RLW packs.
public static class G29Source
{
    public const string Loco = "Assets/mslmike/ls-260-g29.prefab", Tender = "Assets/squam/lt-260-g29.prefab";
    public const string Truck = "Assets/FoxTrucks/fox trucks/Fox-Truck-2s.prefab";

    // Height of the model above the rail: measured by the wheels probe (treads bottom at y = DropY)
    public const float DropY = 0f;

    public static void EnsureFlat() { }

    // RR component transforms may be relative to a parent object (path from the car root); the core reads car space.
    public static List<Comp> ResolveComps(string prefab, IEnumerable<Comp> comps)
    {
        var go = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(prefab));
        var list = new List<Comp>();
        foreach (var c in comps)
        {
            if (string.IsNullOrEmpty(c.parentPath)) { list.Add(c); continue; }
            var p = go.transform.Find(c.parentPath);
            if (!p) { Debug.LogWarning($"[G29Source] component {c.name}: parent {c.parentPath} not found, kept local"); list.Add(c); continue; }
            list.Add(new Comp
            {
                kind = c.kind, name = c.name, extra = c.extra, parentPath = "",
                pos = p.TransformPoint(c.pos), rot = p.rotation * c.rot, scale = Vector3.Scale(p.lossyScale, c.scale),
            });
        }
        Object.DestroyImmediate(go);
        return list;
    }
}
