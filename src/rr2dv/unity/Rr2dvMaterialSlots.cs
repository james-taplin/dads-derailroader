// rr2dv material slot finishing, after the builder has converted the source materials (partial of the builder core).
//  - A slot left empty, or holding Unity's white 'Default-Material' (how the export fills an unresolved reference:
//    Railroader base-game truck rims), gets rr2dv's dark matte gunmetal (Assets/Rr2dv/Materials/rr2dv_gunmetal.mat).
//  - A slot whose converted material is named '...glass...' gets rr2dv's own clear glass (rr2dv_glass.mat, Standard
//    transparent). DV's S282 window glass was tried first: its smudge texture showed as a dark circle pattern on other
//    models' window UVs (L-27 game test, 2026-09-28).
//  - An unresolved slot on a renderer named '...coal...' gets rr2dv_coal (bump-mapped lumps) instead of gunmetal (H9 tender
//    coal load, 2026-09-28: gunmetal "looked very meh").
//  - Glass on a lamp ('lamp', 'light', 'lantern' in its path) gets rr2dv_lens, a pale opaque lens: clear glass let you
//    look into the lamp's hollow interior (2026-09-28).
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
    const string Rr2dvCoal = "Assets/Rr2dv/Materials/rr2dv_coal.mat";
    const string Rr2dvLens = "Assets/Rr2dv/Materials/rr2dv_lens.mat";

    static bool Rr2dvPathHas(string path, params string[] words)
    {
        return words.Any(w => path.IndexOf(w, StringComparison.OrdinalIgnoreCase) >= 0);
    }

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
            var coal = AssetDatabase.LoadAssetAtPath<Material>(Rr2dvCoal);
            var lens = AssetDatabase.LoadAssetAtPath<Material>(Rr2dvLens);
            if (!gunmetal || !clear || !coal || !lens) throw new InvalidOperationException("rr2dv fallback materials missing under Assets/Rr2dv/Materials");
            int filled = 0, glazed = 0;
            foreach (var r in model.GetComponentsInChildren<Renderer>(true))
            {
                var mats = r.sharedMaterials;
                bool changed = false;
                for (int i = 0; i < mats.Length; i++)
                {
                    string at = TPathOf(r.transform, root.transform);
                    if (Rr2dvUnresolvedMaterial(mats[i]))
                    {
                        var fill = Rr2dvPathHas(at, "coal") ? coal : gunmetal;
                        Line($"rr2dv material fallback: {at} slot {i} " +
                             $"{(mats[i] ? "had " + mats[i].name : "was empty")} -> {fill.name}");
                        mats[i] = fill; changed = true; filled++;
                    }
                    else if (mats[i].name.IndexOf("glass", StringComparison.OrdinalIgnoreCase) >= 0 && mats[i] != clear && mats[i] != lens)
                    {
                        var pane = Rr2dvPathHas(at, "lamp", "light", "lantern") ? lens : clear;
                        Line($"rr2dv glass: {at} slot {i} {mats[i].name} -> {pane.name}");
                        mats[i] = pane; changed = true; glazed++;
                    }
                }
                if (changed) r.sharedMaterials = mats;
            }
            if (filled > 0) Warn($"rr2dv material fallback: {filled} unresolved material slot(s) given rr2dv_gunmetal or rr2dv_coal (check them in the renders)");
            if (glazed > 0) Line($"rr2dv glass: {glazed} slot(s) given rr2dv_glass or rr2dv_lens");
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
