using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

// Opt-in, read-only survey of already installed bundles. Writes only its receipt.
// This checks geometry selection, not a conversion or gameplay acceptance.
public static partial class CclLocoBuild
{
    [Serializable] class SafetyCase { public string id, bundle, carId, meshData; public float backhead; public Vector3 chimney; public Vector3[] fittings; }
    [Serializable] class SafetyCases { public SafetyCase[] cases; }
    [Serializable] class SafetyFinding { public string id, part, error; public Vector3 point; public float from, to; }
    [Serializable] class SafetySurvey { public SafetyFinding[] findings; public bool passed; }
    public static void SafetyFleetSurvey()
    {
        string output = Environment.GetEnvironmentVariable("CCL_BUILD_OUT");
        var findings = new List<SafetyFinding>();
        foreach (var c in JsonUtility.FromJson<SafetyCases>(File.ReadAllText(Environment.GetEnvironmentVariable("RR2DV_SAFETY_FLEET_INPUT"))).cases)
        {
            var finding = new SafetyFinding { id = c.id }; findings.Add(finding);
            AssetBundle bundle = null; GameObject root = null;
            var readable = new List<Mesh>();
            try
            {
                bundle = AssetBundle.LoadFromFile(c.bundle);
                var errors = new List<string>();
                var collect = typeof(Rr2dvAudit).GetMethod("CollectObjects", BindingFlags.Static | BindingFlags.NonPublic);
                var objects = (List<Object>)collect.Invoke(null, new object[] { bundle.LoadAllAssets(), errors });
                var prefab = objects.OfType<GameObject>().Single(g => g.name == c.carId + "_template");
                root = Object.Instantiate(prefab);
                foreach (var animator in root.GetComponentsInChildren<Animator>()) animator.enabled = false;
                var model = root.transform.Find("Model");
                var body = model.GetChild(0);
                if (!string.IsNullOrEmpty(c.meshData))
                {
                    using (var input = new BinaryReader(File.OpenRead(c.meshData)))
                    {
                        int count = input.ReadInt32();
                        for (int i = 0; i < count; i++)
                        {
                            string name = System.Text.Encoding.UTF8.GetString(input.ReadBytes(input.ReadInt32()));
                            var vertices = new Vector3[input.ReadInt32()];
                            for (int j = 0; j < vertices.Length; j++) vertices[j] = new Vector3(input.ReadSingle(), input.ReadSingle(), input.ReadSingle());
                            var indices = new int[input.ReadInt32()];
                            for (int j = 0; j < indices.Length; j++) indices[j] = input.ReadInt32();
                            var mesh = new Mesh { name = name, indexFormat = UnityEngine.Rendering.IndexFormat.UInt32 };
                            mesh.vertices = vertices; mesh.triangles = indices; mesh.RecalculateBounds(); readable.Add(mesh);
                        }
                    }
                    foreach (var filter in body.GetComponentsInChildren<MeshFilter>(true))
                    {
                        var old = filter.sharedMesh; if (!old) continue;
                        var matches = readable.Where(m => m.name == old.name && m.vertexCount == old.vertexCount &&
                            (m.bounds.center - old.bounds.center).sqrMagnitude < .00001f &&
                            (m.bounds.size - old.bounds.size).sqrMagnitude < .00001f).ToArray();
                        if (matches.Length == 0) throw new Exception("Cannot match readable test mesh: " + old.name);
                        if (matches.Skip(1).Any(m => !m.vertices.SequenceEqual(matches[0].vertices) || !m.triangles.SequenceEqual(matches[0].triangles)))
                            throw new Exception("Ambiguous test mesh: " + old.name);
                        filter.sharedMesh = matches[0];
                    }
                }
                var measured = ProbeRr2dvBoilerTop(body, c.backhead, c.chimney, c.fittings);
                finding.point = measured.point; finding.part = measured.part;
                finding.from = measured.from; finding.to = measured.to;
                Debug.Log(c.id + " safety fallback: " + finding.part + " " + finding.point);
            }
            catch (Exception e) { finding.error = e.ToString(); Debug.LogException(e); }
            finally { if (root) Object.DestroyImmediate(root); foreach (var m in readable) Object.DestroyImmediate(m); if (bundle) bundle.Unload(true); }
        }
        bool ok = findings.Count > 0 && findings.All(f => string.IsNullOrEmpty(f.error));
        Directory.CreateDirectory(output);
        File.WriteAllText(Path.Combine(output, "result.json"), JsonUtility.ToJson(new SafetySurvey { findings = findings.ToArray(), passed = ok }, true));
        EditorApplication.Exit(ok ? 0 : 1);
    }
}
