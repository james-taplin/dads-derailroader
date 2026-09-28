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
            // The whole car, not only Model: Railroader trucks hang under BogieF/BogieR (L-27 tender rims stayed white,
            // 2026-09-28, because only Model was searched).
            var model = root.transform;
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
                    if (at.Contains("[coal load]") && mats[i] != coal)
                    {
                        // the core's generated coal heap (a tender with no modelled coal) looks like coal too
                        Line($"rr2dv coal: {at} slot {i} {(mats[i] ? mats[i].name : "empty")} -> rr2dv_coal");
                        mats[i] = coal; changed = true;
                    }
                    else if (Rr2dvUnresolvedMaterial(mats[i]))
                    {
                        var fill = Rr2dvPathHas(at, "coal") ? coal : gunmetal;
                        Line($"rr2dv material fallback: {at} slot {i} " +
                             $"{(mats[i] ? "had " + mats[i].name : "was empty")} -> {fill.name}");
                        mats[i] = fill; changed = true; filled++;
                    }
                    else if (mats[i].name.IndexOf("glass", StringComparison.OrdinalIgnoreCase) >= 0 && mats[i] != clear && mats[i] != lens)
                    {
                        bool onLamp = Rr2dvPathHas(at, "lamp", "light", "lantern");
                        if (onLamp && mats[i].HasProperty("_Color") && mats[i].color.a <= .01f)
                        {
                            // Railroader draws this lamp glass fully transparent (PLW Trojan: a disc over each lamp that
                            // our glass or lens turned into a pale blob, 2026-09-29): keep it invisible.
                            Line($"rr2dv glass: {at} slot {i} {mats[i].name} kept invisible (alpha 0 in the source)");
                            continue;
                        }
                        var pane = onLamp ? lens : clear;
                        Line($"rr2dv glass: {at} slot {i} {mats[i].name} -> {pane.name}");
                        mats[i] = pane; changed = true; glazed++;
                        if (!onLamp && Rr2dvSplitLampGlass(r, i, root.transform, lens, ref mats))
                            Line($"rr2dv glass: {at} slot {i}: the glass in front of the lamp(s) split off -> {lens.name}");
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

    // A lamp's glass sharing the window material on one big mesh (ALCo K-66: 'RRR Window Glass' on the body, so the
    // headlight got clear glass and you saw through it, 2026-09-29): the triangles of that slot within a lamp lens's
    // radius of a lamp (LampLenses) move to a new slot with the opaque lens. The mesh is copied, never edited in place.
    static bool Rr2dvSplitLampGlass(Renderer r, int slot, Transform root, Material lens, ref Material[] mats)
    {
        var mf = r.GetComponent<MeshFilter>();
        if (!mf || !mf.sharedMesh || !(r is MeshRenderer) || Cfg.LampLenses.Length == 0 || slot >= mf.sharedMesh.subMeshCount) return false;
        var mesh = mf.sharedMesh;
        var verts = mesh.vertices;
        var tris = mesh.GetTriangles(slot);
        var keep = new List<int>(); var lamp = new List<int>();
        for (int t = 0; t < tris.Length; t += 3)
        {
            var centre = root.InverseTransformPoint(mf.transform.TransformPoint((verts[tris[t]] + verts[tris[t + 1]] + verts[tris[t + 2]]) / 3));
            bool near = Cfg.LampLenses.Any(l => Vector3.Distance(centre, l.centre) <= Mathf.Max(l.dia, .2f) * .75f);
            (near ? lamp : keep).AddRange(new[] { tris[t], tris[t + 1], tris[t + 2] });
        }
        if (lamp.Count == 0) return false;
        var copy = Object.Instantiate(mesh);
        copy.name = mesh.name + "_lamps";
        copy.subMeshCount = mesh.subMeshCount + 1;
        copy.SetTriangles(keep.ToArray(), slot);
        copy.SetTriangles(lamp.ToArray(), mesh.subMeshCount);
        AssetDatabase.CreateAsset(copy, $"{carFolder}/{CarId}_{mf.name}_{slot}_lamps.asset".Replace(" ", "_"));
        mf.sharedMesh = copy;
        mats = mats.Concat(new[] { lens }).ToArray();
        return true;
    }

    static string TPathOf(Transform t, Transform root)
    {
        var parts = new List<string>();
        for (; t && t != root; t = t.parent) parts.Insert(0, t.name);
        return string.Join("/", parts);
    }
}
