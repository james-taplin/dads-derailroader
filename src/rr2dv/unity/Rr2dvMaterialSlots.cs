// rr2dv material slot finishing, after the builder has converted the source materials (partial of the builder core).
//  - A slot left empty (the export could not resolve its material: Railroader base-game truck rims, the '...deadbeef...'
//    references) gets rr2dv's own dark matte gunmetal (Assets/Rr2dv/Materials/rr2dv_gunmetal.mat), never pink or white.
//  - A slot whose converted material is named '...glass...' is swapped at load time for Derail Valley's own S282 cab
//    window glass through CCL's MaterialGrabberRenderer (source glass converts opaque: L-27 game test, 2026-09-28).
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
    const string DvWindowGlass = "Glass (LocoS282A_Windows_01d)";

    static void FinishRr2dvMaterialSlots()
    {
        string path = $"{carFolder}/{CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            var model = root.transform.Find("Model");
            if (!model) return;
            var gunmetal = AssetDatabase.LoadAssetAtPath<Material>(Rr2dvGunmetal);
            if (!gunmetal) throw new InvalidOperationException("rr2dv fallback material missing: " + Rr2dvGunmetal);
            int filled = 0;
            var glass = new Dictionary<int, List<Renderer>>();   // material slot -> renderers whose slot is glass
            foreach (var r in model.GetComponentsInChildren<Renderer>(true))
            {
                var mats = r.sharedMaterials;
                bool changed = false;
                for (int i = 0; i < mats.Length; i++)
                {
                    if (!mats[i])
                    {
                        mats[i] = gunmetal; changed = true; filled++;
                        Line($"rr2dv material fallback: {TPathOf(r.transform, root.transform)} slot {i} was empty -> rr2dv_gunmetal");
                    }
                    else if (mats[i].name.IndexOf("glass", StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        if (!glass.TryGetValue(i, out var list)) glass[i] = list = new List<Renderer>();
                        list.Add(r);
                    }
                }
                if (changed) r.sharedMaterials = mats;
            }
            foreach (var kv in glass)
            {
                var host = new GameObject("[rr2dv glass slot " + kv.Key + "]").transform;
                host.SetParent(model, false);
                var grabber = Add(host.gameObject, "CCL.Types.Components.MaterialGrabberRenderer");
                var entryType = T("CCL.Types.Components.MaterialGrabberRenderer+IndexToName");
                var entry = Activator.CreateInstance(entryType);
                entryType.GetField("RendererIndex").SetValue(entry, kv.Key);
                entryType.GetField("ReplacementName").SetValue(entry, DvWindowGlass);
                var entries = Array.CreateInstance(entryType, 1); entries.SetValue(entry, 0);
                grabber.GetType().GetField("RenderersToAffect").SetValue(grabber, kv.Value.ToArray());
                grabber.GetType().GetField("Replacements").SetValue(grabber, entries);
                grabber.GetType().GetMethod("OnValidate").Invoke(grabber, null);
                Line($"rr2dv glass: {kv.Value.Count} renderer(s), slot {kv.Key} -> DV '{DvWindowGlass}' at load: " +
                     string.Join(", ", kv.Value.Select(r => r.name)));
            }
            if (filled > 0) Warn($"rr2dv material fallback: {filled} empty material slot(s) given rr2dv_gunmetal (check them in the renders)");
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
