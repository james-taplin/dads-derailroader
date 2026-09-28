using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

// rr2dv build stage (Unity 2019.4, editor only). Prepares this run's own project, then runs our builder core through its
// app placement entry (env CCL_VEHICLE_RECORD / CCL_BUILD_OUT), which writes result.json and exits.
// What to prepare comes from Assets/Rr2dv/BuildInput.json (rr2dv's build.py); every change is written to prep.json:
//  1. absent bindings: exactly the listed placeholder bindings (targets in no model of the export, board X39/X40) are
//     removed through AnimationUtility, never by editing curve YAML; then no placeholder may remain in those clips
//     (CclLocoBuild.Clip rejects them);
//  2. AudioSource components come off every prefab the build uses: no Railroader audio reaches a pack (James, W5);
//  3. a model with parts: the vehicle prefab with each part prefab placed as Railroader places it (component transform,
//     under its parent path), each instance named after its component so parent paths into parts resolve.
public static class Rr2dvBuild
{
    [Serializable] public class Absent { public string clip; public string[] hashes; }
    [Serializable] public class Part { public string name, parentPath, prefab; public float[] position, rotation, scale; }
    [Serializable] public class Composite { public string vehicle, source, target; public Part[] parts; }
    [Serializable] public class TruckWheels { public string prefab, prefix; public string[] nodes; }
    [Serializable] public class Input { public int schema; public Absent[] absentBindings; public string[] audioStrip; public Composite[] composites; public TruckWheels[] truckWheels; }

    [Serializable] public class Removed { public string clip, hash; public int bindings; }
    [Serializable] public class MissingScript { public string path; public int count; }
    [Serializable] public class Stripped { public string prefab; public int audioSources; public MissingScript[] missingScripts; }
    [Serializable] public class Placed { public string vehicle, target, part, parent; }
    [Serializable] public class Prep { public int schema = 1; public Removed[] removedBindings; public Stripped[] audioStripped; public Placed[] parts; public string error; }

    const string InputAsset = "Assets/Rr2dv/BuildInput.json";

    public static void Build()
    {
        string output = Environment.GetEnvironmentVariable("CCL_BUILD_OUT");
        var prep = new Prep { removedBindings = new Removed[0], audioStripped = new Stripped[0], parts = new Placed[0] };
        try
        {
            if (string.IsNullOrEmpty(output)) throw new InvalidOperationException("CCL_BUILD_OUT is required");
            Directory.CreateDirectory(output);
            var project = Directory.GetParent(Application.dataPath).FullName;
            var input = JsonUtility.FromJson<Input>(File.ReadAllText(Path.Combine(project, InputAsset)));
            if (input == null || input.schema != 1) throw new InvalidDataException("unsupported build input");
            prep.removedBindings = (input.absentBindings ?? new Absent[0]).SelectMany(RemoveAbsent).ToArray();
            var stripped = new List<Stripped>();
            foreach (var path in input.audioStrip ?? new string[0])
            {
                var entry = StripAudio(path);
                if (entry.audioSources > 0 || entry.missingScripts.Length > 0) stripped.Add(entry);
                prep.audioStripped = stripped.ToArray();
            }
            foreach (var truck in input.truckWheels ?? new TruckWheels[0]) RenameTruckWheels(truck);
            var placed = new List<Placed>();
            foreach (var composite in input.composites ?? new Composite[0])
            {
                placed.AddRange(MakeComposite(composite));
                prep.parts = placed.ToArray();
            }
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            File.WriteAllText(Path.Combine(output, "prep.json"), JsonUtility.ToJson(prep, true));
        }
        catch (Exception e)
        {
            Debug.LogException(e);
            if (!string.IsNullOrEmpty(output))
            {
                Directory.CreateDirectory(output);
                prep.error = e.ToString();
                File.WriteAllText(Path.Combine(output, "prep.json"), JsonUtility.ToJson(prep, true));
                File.WriteAllText(Path.Combine(output, "build_report.txt"), "rr2dv build preparation failed\n" + e);
                File.WriteAllText(Path.Combine(output, "result.json"), "{\"exported\":false,\"warnings\":0,\"runtimeValidated\":false,\"prepFailed\":true}");
            }
            EditorApplication.Exit(1);
            return;
        }
        CclLocoBuild.RunRr2dvRecord();   // measured app placement, then the pinned core export
    }

    // Placeholder path segments look like path_0x100F2BBC_QROHKiL: the CRC32 of the unresolved path, then a tag.
    static string PlaceholderHash(string path)
    {
        foreach (var segment in path.Split('/'))
        {
            if (!segment.StartsWith("path_0x", StringComparison.Ordinal)) continue;
            var hex = segment.Substring("path_".Length);
            int end = hex.IndexOf('_');
            return (end < 0 ? hex : hex.Substring(0, end)).ToLowerInvariant();
        }
        return null;
    }

    static IEnumerable<Removed> RemoveAbsent(Absent a)
    {
        var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(a.clip);
        if (!clip) throw new InvalidOperationException("clip with absent bindings not found: " + a.clip);
        var wanted = new HashSet<string>((a.hashes ?? new string[0]).Select(h => h.ToLowerInvariant()));
        var counts = wanted.ToDictionary(h => h, h => 0);
        foreach (var b in AnimationUtility.GetCurveBindings(clip))
        {
            var h = PlaceholderHash(b.path);
            if (h == null || !wanted.Contains(h)) continue;
            AnimationUtility.SetEditorCurve(clip, b, null);
            counts[h]++;
        }
        foreach (var b in AnimationUtility.GetObjectReferenceCurveBindings(clip))
        {
            var h = PlaceholderHash(b.path);
            if (h == null || !wanted.Contains(h)) continue;
            AnimationUtility.SetObjectReferenceCurve(clip, b, null);
            counts[h]++;
        }
        EditorUtility.SetDirty(clip);
        var left = AnimationUtility.GetCurveBindings(clip).Concat(AnimationUtility.GetObjectReferenceCurveBindings(clip))
            .Where(b => PlaceholderHash(b.path) != null).Select(b => b.path).Distinct().ToArray();
        if (left.Length > 0) throw new InvalidOperationException(a.clip + " still has unresolved bindings after removal: " + string.Join(", ", left));
        var missing = counts.Where(kv => kv.Value == 0).Select(kv => kv.Key).ToArray();
        if (missing.Length > 0) throw new InvalidOperationException(a.clip + ": listed absent bindings not found in the clip: " + string.Join(", ", missing));
        return counts.OrderBy(kv => kv.Key, StringComparer.Ordinal).Select(kv => new Removed { clip = a.clip, hash = kv.Key, bindings = kv.Value }).ToList();
    }

    static Stripped StripAudio(string prefabPath)
    {
        if (!AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath)) throw new InvalidOperationException("prefab not found: " + prefabPath);
        var root = PrefabUtility.LoadPrefabContents(prefabPath);
        try
        {
            var sources = root.GetComponentsInChildren<AudioSource>(true);
            foreach (var s in sources) Object.DestroyImmediate(s);
            var missing = new List<MissingScript>();
            foreach (var t in root.GetComponentsInChildren<Transform>(true))
            {
                int count = GameObjectUtility.RemoveMonoBehavioursWithMissingScript(t.gameObject);
                if (count > 0) missing.Add(new MissingScript { path = AnimationUtility.CalculateTransformPath(t, root.transform), count = count });
            }
            if (sources.Length > 0 || missing.Count > 0) SaveChecked(root, prefabPath);
            return new Stripped { prefab = prefabPath, audioSources = sources.Length, missingScripts = missing.ToArray() };
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    static IEnumerable<Placed> MakeComposite(Composite c)
    {
        var source = AssetDatabase.LoadAssetAtPath<GameObject>(c.source);
        if (!source) throw new InvalidOperationException(c.vehicle + ": model prefab not found: " + c.source);
        var go = (GameObject)PrefabUtility.InstantiatePrefab(source);
        var placed = new List<Placed>();
        try
        {
            PrefabUtility.UnpackPrefabInstance(go, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            foreach (var p in c.parts ?? new Part[0])
            {
                var parent = string.IsNullOrEmpty(p.parentPath) ? go.transform : go.transform.Find(p.parentPath);
                if (!parent) throw new InvalidOperationException(c.vehicle + ": part " + p.name + " parent not found: " + p.parentPath);
                if (parent.Cast<Transform>().Any(t => t.name == p.name))
                    throw new InvalidOperationException(c.vehicle + ": part " + p.name + " would share its name with an object already under " + (p.parentPath ?? "the root"));
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(p.prefab);
                if (!prefab) throw new InvalidOperationException(c.vehicle + ": part prefab not found: " + p.prefab);
                var inst = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
                PrefabUtility.UnpackPrefabInstance(inst, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
                inst.name = p.name;
                inst.transform.SetParent(parent, false);
                inst.transform.localPosition = V(p.position, Vector3.zero);
                inst.transform.localRotation = Q(p.rotation);
                inst.transform.localScale = V(p.scale, Vector3.one);
                placed.Add(new Placed { vehicle = c.vehicle, target = c.target, part = p.name, parent = p.parentPath ?? "" });
            }
            foreach (var s in go.GetComponentsInChildren<AudioSource>(true)) Object.DestroyImmediate(s);
            Folder(Path.GetDirectoryName(c.target).Replace('\\', '/'));
            SaveChecked(go, c.target);
        }
        finally { Object.DestroyImmediate(go); }
        return placed;
    }

    // One node per axle gets a unique name the builder's wheel prefix matches, in the run's own copy of the truck prefab:
    // source names can be shared with brake gear or wrap both axles (truck.archbar.diamond 'Wheels Animation').
    static void RenameTruckWheels(TruckWheels truck)
    {
        var root = PrefabUtility.LoadPrefabContents(truck.prefab);
        try
        {
            if (root.GetComponentsInChildren<Transform>(true).Any(t => t.name.StartsWith(truck.prefix)))
                throw new InvalidOperationException("truck already has objects named " + truck.prefix + "*: " + truck.prefab);
            for (int i = 0; i < truck.nodes.Length; i++)
            {
                var path = truck.nodes[i];
                var node = root.transform.Find(path);   // probe paths are relative to the prefab root
                if (!node) throw new InvalidOperationException("truck wheel node not found: " + path + " in " + truck.prefab);
                Debug.Log($"rr2dv truck wheel node {path} -> {truck.prefix}{i}");
                node.name = truck.prefix + i;
            }
            SaveChecked(root, truck.prefab);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    // A failed save must stop preparation before the record loader can misreport a missing source prefab.
    static void SaveChecked(GameObject root, string path)
    {
        bool success;
        var saved = PrefabUtility.SaveAsPrefabAsset(root, path, out success);
        if (!success || !saved) throw new InvalidOperationException("prefab save failed: " + path);
        var reloaded = PrefabUtility.LoadPrefabContents(path);
        if (!reloaded) throw new InvalidOperationException("saved prefab cannot be reloaded: " + path);
        try
        {
            foreach (var t in reloaded.GetComponentsInChildren<Transform>(true))
                if (t.gameObject.GetComponents<Component>().Any(c => c == null))
                    throw new InvalidOperationException("saved prefab still has missing scripts: " + path);
        }
        finally { PrefabUtility.UnloadPrefabContents(reloaded); }
    }

    static void Folder(string path)
    {
        if (AssetDatabase.IsValidFolder(path)) return;
        var parent = Path.GetDirectoryName(path).Replace('\\', '/');
        Folder(parent);
        AssetDatabase.CreateFolder(parent, Path.GetFileName(path));
    }

    static Vector3 V(float[] a, Vector3 fallback) => a != null && a.Length == 3 ? new Vector3(a[0], a[1], a[2]) : fallback;
    static Quaternion Q(float[] a) => a != null && a.Length == 4 ? new Quaternion(a[0], a[1], a[2], a[3]) : Quaternion.identity;
}
