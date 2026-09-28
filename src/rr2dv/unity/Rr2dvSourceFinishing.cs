using System;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static partial class CclLocoBuild
{
    [Serializable] class RrColour { public string colorID, materialName; public bool enabled = true, matchNameExact; }
    [Serializable] class RrGripShape { public float[] center; public float radius, height; public string kind; }
    [Serializable] class RrRadial { public RrToggleAnimation animation; public RrGripShape collider; public bool enabled = true; }

    static void FinishRr2dvMaterials()
    {
        var colours = Cfg.Liveries.First(l => l.name == Livery).colors.ToDictionary(c => c.id, c => ParseHex(c.hex), StringComparer.OrdinalIgnoreCase);
        foreach (var pair in matMap.Where(p => !p.Key.shader.name.StartsWith("Railroader")))
        {
            var source = pair.Key; var output = pair.Value;
            string texture = source.HasProperty("_BaseMap") && source.GetTexture("_BaseMap") ? "_BaseMap" : "_MainTex";
            if (source.HasProperty(texture) && source.GetTexture(texture))
            {
                output.SetTexture("_MainTex", source.GetTexture(texture));
                output.SetTextureScale("_MainTex", source.GetTextureScale(texture));
                output.SetTextureOffset("_MainTex", source.GetTextureOffset(texture));
            }
            foreach (var component in Components.Where(c => c.kind == "MaterialColorizerComponent" || c.kind == "Colorizer"))
            {
                var data = JsonUtility.FromJson<RrColour>(component.extra);
                if (!data.enabled || string.IsNullOrEmpty(data.materialName)) continue;
                bool match = data.matchNameExact ? source.name == data.materialName : source.name.StartsWith(data.materialName, StringComparison.Ordinal);
                if (!component.extra.Contains("\"material\":null"))
                    match = Cfg.MaterialMap.TryGetValue(data.materialName, out var materialPath) && AssetDatabase.GetAssetPath(source) == materialPath;
                if (!match || !colours.TryGetValue(component.kind == "Colorizer" ? "base" : data.colorID ?? "", out var colour)) continue;
                colour.a = output.color.a;
                output.color = colour;
                Line($"rr2dv material {source.name}: source colourizer {component.name}, tint #{ColorUtility.ToHtmlStringRGB(colour)} applied across shader types");
            }
            EditorUtility.SetDirty(output);
        }
    }

    static void PrepareRr2dvGrips()
    {
        foreach (var lever in Cfg.RrLevers.Where(l => !l.Grip.HasValue && l.AnimKey != null))
        {
            var matches = Cfg.Components.Where(c => c.kind == "RadialControl")
                .Select(c => new { component = c, data = JsonUtility.FromJson<RrRadial>(c.extra) })
                .Where(x => x.data.enabled && x.data.animation?.clipName == lever.AnimKey && x.data.collider?.center?.Length == 3).ToArray();
            if (matches.Length != 1) continue;
            var item = matches[0]; var component = item.component; var shape = item.data.collider;
            var center = new Vector3(shape.center[0], shape.center[1], shape.center[2]);
            // PrepareSources has already baked the component's parent-local pose to car space.
            lever.Grip = RefBody.TransformPoint(component.pos + component.rot * Vector3.Scale(center, component.scale));
            lever.GripSize = Vector3.one * Mathf.Clamp(shape.radius * 2, .05f, .12f);
            Line($"rr2dv source grip {lever.Path}: {V(lever.Grip.Value)} from {component.name} collider centre; no farthest-linkage heuristic");
        }
    }
}
