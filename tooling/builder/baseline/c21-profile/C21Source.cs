using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

// C21 source transforms. Tender animation paths were already normalized to the Tender wrapper by pilot preparation.
public static class C21Source
{
    public const string Loco = "Assets/connor/ls-280-c21.prefab", Tender = "Assets/box/lt-280-c21.prefab";
    public const string Truck = "Assets/FoxTrucks/fox trucks/Fox-Truck-2s.prefab";

    // Height of the model above the rail: measured by the wheels probe (treads bottom at y = DropY)
    public const float DropY = 0f;

    public const string Pilot = "Assets/C21_SourceParts/pilot.prefab";
    public static void EnsureFlat()
    {
        // Shared G19 pilot: use the C21 PrefabModelComponent's position while preserving the imported basis/scale.
        if (!AssetDatabase.IsValidFolder("Assets/C21_SourceParts")) AssetDatabase.CreateFolder("Assets", "C21_SourceParts");
        var go = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>("Assets/LLWParts/g19parts/parts/pilot1.prefab"));
        PrefabUtility.UnpackPrefabInstance(go, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
        go.transform.position = C21Defs.Components.First(c => c.name == "pt2").pos;
        PrefabUtility.SaveAsPrefabAsset(go, Pilot);
        Object.DestroyImmediate(go);
        AssetDatabase.SaveAssets();
    }

    // RR component transforms may be relative to a parent object (path from the car root); the core reads car space.
    public static List<Comp> ResolveComps(string prefab, IEnumerable<Comp> comps)
    {
        var go = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(prefab));
        var list = new List<Comp>();
        foreach (var c in comps)
        {
            if (string.IsNullOrEmpty(c.parentPath)) { list.Add(c); continue; }
            var p = go.transform.Find(c.parentPath);
            if (!p) { Debug.LogWarning($"[C21Source] component {c.name}: parent {c.parentPath} not found, kept local"); list.Add(c); continue; }
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

