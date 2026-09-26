using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

// Source-inspection only. Instantiates temporary copies and never saves a scene
// or modifies source prefabs. Neutral-material renders are not finished DV art.
public static class PilotProbe
{
    [Serializable] public class Entry { public string id, prefab; }
    [Serializable] public class Input { public string pilot, truck; public Entry[] vehicles, parts; }
    static readonly StringBuilder Report = new StringBuilder();
    static string output;
    static int missingBindings, missingMeshes, missingMaterials;
    static int missingAnchors;
    static bool outputValidated;

    public static void Run()
    {
        int exit = 0;
        outputValidated = false;
        output = Environment.GetEnvironmentVariable("LLW_PROBE_OUT");
        try
        {
            if (string.IsNullOrEmpty(output)) throw new InvalidOperationException("LLW_PROBE_OUT is required.");
            var project = Directory.GetParent(Application.dataPath).FullName;
            var workspace = Directory.GetParent(Directory.GetParent(project).FullName).FullName;
            output = Path.GetFullPath(output);
            if (!output.StartsWith(workspace + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Probe output must remain inside the pilot workspace.");
            outputValidated = true;
            Directory.CreateDirectory(output);
            var input = JsonUtility.FromJson<Input>(File.ReadAllText("Assets/PilotProbeInput.json"));
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            Report.Clear(); missingBindings = missingMeshes = missingMaterials = missingAnchors = 0;
            Line("SOURCE INSPECTION: " + input.pilot + "; Unity " + Application.unityVersion);
            Line("Neutral source renders; optional parts are inspected separately, not selected for a DV build.");
            foreach (var entry in input.vehicles)
            {
                var body = Instantiate(entry);
                Inspect(entry, body);
                var prefix = input.pilot.ToUpperInvariant();
                InspectClips(body, prefix + (entry.id.StartsWith("lt-") ? "TenderDefs" : "Defs"));
                Render(body, entry.id);
                Object.DestroyImmediate(body);
            }
            foreach (var entry in input.parts)
            {
                var part = Instantiate(entry); Inspect(entry, part); Object.DestroyImmediate(part);
            }
            if (!string.IsNullOrEmpty(input.truck))
            {
                var e = new Entry { id = "fox-truck-2s", prefab = input.truck };
                var truck = Instantiate(e); Inspect(e, truck); Object.DestroyImmediate(truck);
            }
            Line($"CHECKS missingBindings={missingBindings} missingMeshes={missingMeshes} missingMaterials={missingMaterials} missingAnchors={missingAnchors}");
            if (missingBindings + missingMeshes + missingMaterials + missingAnchors > 0) exit = 2;
        }
        catch (Exception e) { Report.AppendLine("EXCEPTION " + e); Debug.LogException(e); exit = 1; }
        finally
        {
            if (outputValidated && Directory.Exists(output))
            {
                File.WriteAllText(Path.Combine(output, "probe_report.txt"), Report.ToString());
                File.WriteAllText(Path.Combine(output, "result.json"),
                    "{\"status\":\"" + (exit == 0 ? "passed" : "failed") + "\",\"exitCode\":" + exit +
                    ",\"missingBindings\":" + missingBindings + ",\"missingMeshes\":" + missingMeshes +
                    ",\"missingMaterials\":" + missingMaterials + ",\"missingAnchors\":" + missingAnchors + ",\"runtimeValidated\":false}");
            }
            EditorApplication.Exit(exit);
        }
    }

    static GameObject Instantiate(Entry entry)
    {
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(entry.prefab);
        if (!prefab) throw new FileNotFoundException(entry.prefab);
        return (GameObject)PrefabUtility.InstantiatePrefab(prefab);
    }

    static void Inspect(Entry entry, GameObject go)
    {
        Line("\nASSET " + entry.id + " " + entry.prefab);
        long triangles = 0;
        foreach (var t in go.GetComponentsInChildren<Transform>(true))
            Line("TRANSFORM " + Rel(t, go.transform) + " pos=" + V(t.position) + " scale=" + V(t.lossyScale));
        foreach (var f in go.GetComponentsInChildren<MeshFilter>(true))
        {
            if (!f.sharedMesh) { missingMeshes++; Line("MISSING MESH " + Rel(f.transform, go.transform)); continue; }
            var mesh = f.sharedMesh;
            long count = 0;
            for (int s = 0; s < mesh.subMeshCount; s++) count += (long)mesh.GetIndexCount(s) / 3;
            triangles += count;
            var renderer = f.GetComponent<Renderer>();
            if (!renderer) continue;
            missingMaterials += renderer.sharedMaterials.Count(m => !m);
            Line("MESH " + Rel(f.transform, go.transform) + " center=" + V(renderer.bounds.center) +
                " size=" + V(renderer.bounds.size) + " min=" + V(renderer.bounds.min) +
                " max=" + V(renderer.bounds.max) + " tris=" + count +
                " materials=" + string.Join("|", renderer.sharedMaterials.Select(m => m ? m.name : "NULL")));
        }
        Line("TOTAL triangles=" + triangles + " renderers=" + go.GetComponentsInChildren<Renderer>(true).Length);
    }

    static void InspectClips(GameObject go, string className)
    {
        var type = typeof(PilotProbe).Assembly.GetType(className, true);
        foreach (var component in (Array)type.GetField("Components").GetValue(null))
        {
            var t = component.GetType();
            string name = (string)t.GetField("name").GetValue(component);
            string kind = (string)t.GetField("kind").GetValue(component);
            string path = (string)t.GetField("parentPath").GetValue(component);
            var parent = string.IsNullOrEmpty(path) ? go.transform : go.transform.Find(path);
            if (!parent) { missingAnchors++; Line("MISSING ANCHOR " + name + " parent=" + path); continue; }
            var local = (Vector3)t.GetField("pos").GetValue(component);
            var scale = (Vector3)t.GetField("scale").GetValue(component);
            var rotation = (Quaternion)t.GetField("rot").GetValue(component);
            Line("ANCHOR " + kind + " / " + name + " parent=" + path + " world=" + V(parent.TransformPoint(local)) +
                " euler=" + V((parent.rotation * rotation).eulerAngles) + " sourceScale=" + V(scale));
            if (scale.x == 0 || scale.y == 0 || scale.z == 0)
                Line("REVIEW zero source scale: " + name + "; do not apply this scale blindly to a DV control.");
        }
        var map = (Dictionary<string, string>)type.GetField("AnimationMap").GetValue(null);
        foreach (var item in map)
        {
            var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(item.Value);
            if (!clip) { missingBindings++; Line("MISSING CLIP " + item.Key + " " + item.Value); continue; }
            var bindings = AnimationUtility.GetCurveBindings(clip);
            Line($"CLIP {item.Key} file={item.Value} duration={clip.length:F3} curves={bindings.Length}");
            foreach (var path in bindings.Select(b => b.path).Distinct())
            {
                var target = string.IsNullOrEmpty(path) ? go.transform : go.transform.Find(path);
                if (!target) missingBindings++;
                Line("  " + (target ? "OK " : "MISSING ") + path);
            }
            // Summarize actual animated travel for subsequent control configuration.
            foreach (var binding in bindings.Where(b => b.propertyName.Contains("Euler") || b.propertyName.Contains("Rotation")))
            {
                var curve = AnimationUtility.GetEditorCurve(clip, binding);
                if (curve == null || curve.keys.Length == 0) continue;
                Line($"  CURVE {binding.path} {binding.propertyName} first={curve.keys[0].value:F5} last={curve.keys[curve.keys.Length - 1].value:F5}");
            }
        }
    }

    static Material Preview(Material source)
    {
        var material = new Material(Shader.Find("Standard (Specular setup)"));
        material.color = new Color(0.32f, 0.35f, 0.38f);
        if (!source) return material;
        foreach (var key in new[] { "_MainTex", "_SpecGlossMap", "_BumpMap", "_OcclusionMap" })
            if (source.HasProperty(key) && source.GetTexture(key)) material.SetTexture(key, source.GetTexture(key));
        if (source.HasProperty("_BaseColor")) material.color = source.GetColor("_BaseColor");
        else if (source.HasProperty("_Color")) material.color = source.GetColor("_Color");
        if (source.HasProperty("_Smoothness")) material.SetFloat("_GlossMapScale", source.GetFloat("_Smoothness"));
        if (material.GetTexture("_SpecGlossMap")) material.EnableKeyword("_SPECGLOSSMAP");
        if (material.GetTexture("_BumpMap")) material.EnableKeyword("_NORMALMAP");
        return material;
    }

    static void Render(GameObject go, string name)
    {
        var renderers = go.GetComponentsInChildren<Renderer>(true);
        var materials = new Dictionary<Material, Material>();
        foreach (var renderer in renderers)
            renderer.sharedMaterials = renderer.sharedMaterials.Select(m =>
            {
                if (!m) return Preview(null);
                if (!materials.ContainsKey(m)) materials[m] = Preview(m);
                return materials[m];
            }).ToArray();
        var visible = renderers.Where(r => r.enabled && r.gameObject.activeInHierarchy).ToArray();
        if (visible.Length == 0) throw new InvalidOperationException("No visible geometry: " + name);
        var bounds = visible[0].bounds;
        foreach (var r in visible) bounds.Encapsulate(r.bounds);
        var light = new GameObject("ProbeLight").AddComponent<Light>();
        light.type = LightType.Directional; light.intensity = 1.2f;
        light.transform.rotation = Quaternion.Euler(35, 25, 0);
        RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
        RenderSettings.ambientLight = new Color(0.55f, 0.55f, 0.55f);
        var camera = new GameObject("ProbeCamera").AddComponent<Camera>();
        camera.backgroundColor = new Color(0.12f, 0.15f, 0.19f);
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.fieldOfView = 35;
        float d = Mathf.Max(bounds.size.z, bounds.size.y, bounds.size.x) * 1.7f;
        Shot(camera, bounds.center + new Vector3(-d, d * 0.15f, 0), bounds.center, name + "_left.png");
        Shot(camera, bounds.center + new Vector3(d, d * 0.4f, d), bounds.center, name + "_front.png");
        Shot(camera, bounds.center + new Vector3(-d, d * 0.35f, -d), bounds.center, name + "_rear.png");
        Object.DestroyImmediate(camera.gameObject); Object.DestroyImmediate(light.gameObject);
        foreach (var m in materials.Values) Object.DestroyImmediate(m);
    }

    static void Shot(Camera camera, Vector3 position, Vector3 target, string filename)
    {
        camera.transform.position = position; camera.transform.LookAt(target);
        var rt = new RenderTexture(1600, 900, 24);
        var old = RenderTexture.active;
        var image = new Texture2D(1600, 900, TextureFormat.RGB24, false);
        try
        {
            camera.targetTexture = rt; camera.Render(); RenderTexture.active = rt;
            image.ReadPixels(new Rect(0, 0, 1600, 900), 0, 0); image.Apply();
            File.WriteAllBytes(Path.Combine(output, filename), image.EncodeToPNG());
        }
        finally
        {
            RenderTexture.active = old; camera.targetTexture = null;
            Object.DestroyImmediate(rt); Object.DestroyImmediate(image);
        }
    }

    static string Rel(Transform t, Transform root) => t == root ? "" : (t.parent == root ? t.name : Rel(t.parent, root) + "/" + t.name);
    static string V(Vector3 value) => $"({value.x:F4},{value.y:F4},{value.z:F4})";
    static void Line(string text) { Report.AppendLine(text); }
}
