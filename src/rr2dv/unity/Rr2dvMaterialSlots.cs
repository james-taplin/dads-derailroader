// rr2dv material slot finishing, after the builder has converted the source materials (partial of the builder core).
//  - A slot left empty, or holding Unity's white 'Default-Material' (how the export fills an unresolved reference:
//    Railroader base-game truck rims), gets rr2dv's dark matte gunmetal (Assets/Rr2dv/Materials/rr2dv_gunmetal.mat).
//  - A slot whose converted material is named '...glass...' gets rr2dv's own clear glass (rr2dv_glass.mat, Standard
//    transparent). DV's S282 window glass was tried first: its smudge texture showed as a dark circle pattern on other
//    models' window UVs (L-27 game test, 2026-09-28).
// Every fallback is written to the build report.
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

public static partial class CclLocoBuild
{
    const string Rr2dvGunmetal = "Assets/Rr2dv/Materials/rr2dv_gunmetal.mat";
    const string Rr2dvGlass = "Assets/Rr2dv/Materials/rr2dv_glass.mat";

    static bool Rr2dvUnresolvedMaterial(Material m)
    {
        return !m || m.name == "Default-Material" || m.name == "Default-Diffuse";
    }

    static void FinishRr2dvMaterialSlots()
    {
        string path = $"{carFolder}/{CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            var model = root.transform.Find("Model");
            if (!model) return;
            var gunmetal = AssetDatabase.LoadAssetAtPath<Material>(Rr2dvGunmetal);
            var clear = AssetDatabase.LoadAssetAtPath<Material>(Rr2dvGlass);
            if (!gunmetal || !clear) throw new InvalidOperationException("rr2dv fallback materials missing under Assets/Rr2dv/Materials");
            int filled = 0, glazed = 0;
            foreach (var r in model.GetComponentsInChildren<Renderer>(true))
            {
                var mats = r.sharedMaterials;
                bool changed = false;
                for (int i = 0; i < mats.Length; i++)
                {
                    if (Rr2dvUnresolvedMaterial(mats[i]))
                    {
                        Line($"rr2dv material fallback: {TPathOf(r.transform, root.transform)} slot {i} " +
                             $"{(mats[i] ? "had " + mats[i].name : "was empty")} -> rr2dv_gunmetal");
                        mats[i] = gunmetal; changed = true; filled++;
                    }
                    else if (mats[i].name.IndexOf("glass", StringComparison.OrdinalIgnoreCase) >= 0 && mats[i] != clear)
                    {
                        Line($"rr2dv glass: {TPathOf(r.transform, root.transform)} slot {i} {mats[i].name} -> rr2dv_glass");
                        mats[i] = clear; changed = true; glazed++;
                    }
                }
                if (changed) r.sharedMaterials = mats;
            }
            if (filled > 0) Warn($"rr2dv material fallback: {filled} unresolved material slot(s) given rr2dv_gunmetal (check them in the renders)");
            if (glazed > 0) Line($"rr2dv glass: {glazed} slot(s) given rr2dv_glass");
            PrefabUtility.SaveAsPrefabAsset(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    static string TPathOf(Transform t, Transform root)
    {
        var parts = new List<string>();
        for (; t && t != root; t = t.parent) parts.Insert(0, t.name);
        return string.Join("/", parts);
    }
}
