using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

// Read-only geometry inventory for selecting C-21 running-gear oil-cup anchors.
public static class C21OilProbe
{
    static readonly string[] Paths = {
        "Main/Empty.004/Main Rod Left", "Main/Empty.006/Connecting Rod Left",
        "Main/Empty.028/Connecting Rod Left.001", "Main/Empty.030/Main Rod Left.001"
    };

    public static void Run()
    {
        string output = Environment.GetEnvironmentVariable("RLW_PROBE_OUT") ?? Path.GetFullPath("OilProbeOut");
        Directory.CreateDirectory(output);
        var log = new StringBuilder();
        try
        {
            C21Source.EnsureFlat();
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(C21Source.Loco);
            if (!prefab) throw new InvalidOperationException("C-21 source prefab missing");
            var root = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
            foreach (string path in Paths)
            {
                var t = root.transform.Find(path);
                if (!t) throw new InvalidOperationException("Missing source oil candidate " + path);
                var mf = t.GetComponent<MeshFilter>();
                if (!mf || !mf.sharedMesh) throw new InvalidOperationException("No mesh at " + path);
                log.AppendLine("PART " + path + " mesh=" + mf.sharedMesh.name + " vertices=" + mf.sharedMesh.vertexCount);
                var islands = Islands(mf);
                log.AppendLine("  islands=" + islands.Count);
                foreach (var island in islands.OrderByDescending(x => x.triangles))
                    log.AppendLine(string.Format("  triangles={0} centre={1} size={2} min={3} max={4}",
                        island.triangles, V(island.bounds.center), V(island.bounds.size), V(island.bounds.min), V(island.bounds.max)));
            }
            Object.DestroyImmediate(root);
        }
        catch (Exception e) { log.AppendLine("EXCEPTION " + e); }
        File.WriteAllText(Path.Combine(output, "oil_probe.txt"), log.ToString());
        EditorApplication.Exit(log.ToString().Contains("EXCEPTION ") ? 1 : 0);
    }

    public static void ValidateBuilt()
    {
        string output = Environment.GetEnvironmentVariable("RLW_PROBE_OUT") ?? Path.GetFullPath("OilProbeOut");
        Directory.CreateDirectory(output);
        var log = new StringBuilder();
        try
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            const string carPath = "Assets/_CCL_CARS/LLW C-21/LLW_C21_template.prefab";
            const string cupPath = "Assets/_CCL_CARS/LLW C-21/LLW_C21_interactables.prefab";
            var carAsset = AssetDatabase.LoadAssetAtPath<GameObject>(carPath);
            var cupAsset = AssetDatabase.LoadAssetAtPath<GameObject>(cupPath);
            if (!carAsset || !cupAsset) throw new InvalidOperationException("Built C-21 prefabs missing");
            var car = (GameObject)PrefabUtility.InstantiatePrefab(carAsset);
            var providers = car.GetComponentsInChildren<Transform>(true).Where(t => t.name.StartsWith("MOP ")).ToArray();
            var cupRoot = cupAsset.transform.Find("ManualOilingPoints");
            if (!cupRoot || providers.Length != 8 || cupRoot.childCount != 8)
                throw new InvalidOperationException("Expected eight oil providers and eight cups");
            var byTag = providers.ToDictionary(p => p.name);
            for (int i = 0; i < cupRoot.childCount; i++)
            {
                string tag = "MOP " + (i < 4 ? "-1" : "1") + " " + (i % 4);
                if (cupRoot.GetChild(i).name != tag || !byTag.TryGetValue(tag, out var p))
                    throw new InvalidOperationException("Oil cup/provider order differs at " + i);
                var animator = p.GetComponentInParent<Animator>();
                if (!animator || !animator.runtimeAnimatorController)
                    throw new InvalidOperationException("Oil provider is not under a driven rod: " + p.name);
                var clips = animator.runtimeAnimatorController.animationClips;
                if (clips.Length != 1) throw new InvalidOperationException("Unexpected rod animation count for " + p.name);
                var clip = clips[0];
                var mesh = p.parent.GetComponent<MeshFilter>()?.sharedMesh;
                if (!mesh) throw new InvalidOperationException("Oil provider parent lacks rod mesh: " + p.name);
                var samples = new List<Vector3>();
                foreach (float phase in new[] { 0f, .25f, .5f, .75f })
                {
                    clip.SampleAnimation(animator.gameObject, phase * clip.length);
                    samples.Add(p.position);
                    float nearest = mesh.vertices.Min(v => Vector3.Distance(p.position, p.parent.TransformPoint(v)));
                    if (nearest > .045f)
                        throw new InvalidOperationException($"{p.name} left the modelled cap at phase {phase}: {nearest:F3} m");
                }
                float travel = samples.Max(v => Vector3.Distance(v, samples[0]));
                if (travel < .04f) throw new InvalidOperationException(p.name + " stayed body-fixed across the driving cycle");
                log.AppendLine($"{i} {p.name}: parent {p.parent.name}; animator {animator.name}; travel {travel:F3} m; positions {string.Join(" | ", samples.Select(V))}");
            }
            Object.DestroyImmediate(car);
            log.AppendLine("PASS eight ordered cups follow their moving rod caps");
        }
        catch (Exception e) { log.AppendLine("EXCEPTION " + e); }
        File.WriteAllText(Path.Combine(output, "oil_built_validation.txt"), log.ToString());
        EditorApplication.Exit(log.ToString().Contains("EXCEPTION ") ? 1 : 0);
    }

    static List<(Bounds bounds, int triangles)> Islands(MeshFilter mf)
    {
        var vertices = mf.sharedMesh.vertices;
        var triangles = mf.sharedMesh.triangles;
        var ids = new int[vertices.Length];
        var welded = new Dictionary<Vector3Int, int>();
        for (int i = 0; i < vertices.Length; i++)
        {
            var key = Vector3Int.RoundToInt(vertices[i] * 10000f);
            if (!welded.TryGetValue(key, out ids[i])) { ids[i] = welded.Count; welded.Add(key, ids[i]); }
        }
        var parent = Enumerable.Range(0, welded.Count).ToArray();
        int Find(int a) { while (parent[a] != a) a = parent[a] = parent[parent[a]]; return a; }
        for (int i = 0; i < triangles.Length; i += 3)
        {
            int a = Find(ids[triangles[i]]);
            parent[Find(ids[triangles[i + 1]])] = a;
            parent[Find(ids[triangles[i + 2]])] = a;
        }
        var result = new Dictionary<int, (Bounds bounds, int triangles)>();
        for (int i = 0; i < triangles.Length; i += 3)
        {
            int id = Find(ids[triangles[i]]);
            var point = mf.transform.TransformPoint(vertices[triangles[i]]);
            if (!result.TryGetValue(id, out var entry)) entry = (new Bounds(point, Vector3.zero), 0);
            entry.bounds.Encapsulate(mf.transform.TransformPoint(vertices[triangles[i + 1]]));
            entry.bounds.Encapsulate(mf.transform.TransformPoint(vertices[triangles[i + 2]]));
            entry.triangles++;
            result[id] = entry;
        }
        return result.Values.ToList();
    }

    static string V(Vector3 p) => string.Format("({0:F4},{1:F4},{2:F4})", p.x, p.y, p.z);
}
