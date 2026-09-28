using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

// rr2dv generic source probe (Unity 2019.4, editor only). Read-only: it instantiates temporary copies in an empty
// scene and never saves a scene, prefab or asset. What to measure comes from Assets/Rr2dv/ProbeInput.json, written by
// rr2dv's probeinput.py. Results are data (probe.json) for the record stage; nothing here decides a conversion value.
// Coordinates: car space = the instantiated prefab at the origin; x right, y up, z front (guide 00).
public static class Rr2dvProbe
{
    [Serializable] public class MapEntry { public string key, asset, guid; }
    [Serializable] public class Wheelset { public string clip, clipAsset; public float diameter, offset, length; public int axles; }
    [Serializable] public class Comp { public string kind, name, purpose, parentPath, clip, clipAsset; public float[] position, rotation, scale; }
    // Cab rays: a grid of rays along +z (towards the front) from startZ, at each (x, y); the first visible surface each meets.
    [Serializable] public class CabSpec { public float startZ, length; public float[] xs, ys; }
    [Serializable] public class Vehicle { public string id, role, prefab; public Wheelset[] wheelsets; public Comp[] components; public MapEntry[] animationMap, materialMap; public CabSpec cab; }
    [Serializable] public class Input { public int schema; public Vehicle[] vehicles; public string[] missing; }

    [Serializable] public class Node { public string path; public float[] position, rotation, lossyScale; }
    [Serializable] public class MeshOut { public string path; public int triangles; public float[] boundsMin, boundsMax; public string[] materials; }
    [Serializable] public class AnchorOut { public string kind, name, purpose, parentPath; public bool resolved; public float[] position, rotation, scale; }
    [Serializable] public class Pose { public string path; public float[] start, end, startEuler, endEuler; }
    [Serializable] public class ClipOut { public string key, asset; public float duration; public int curves; public string[] missingPaths; public Pose[] poses; }
    // One 1 mm radius band of the wheel's outer surface: mean radius and the lateral extent it covers, measured from the
    // rotating node's pivot (axle-centric; both sides folded). A tyre tread is a wide band; the flange tip is narrow.
    // modeRadius: the most common exact radius in the band (0.01 mm steps): a cylindrical tread's vertices share one.
    [Serializable] public class RadiusBand { public float radius, modeRadius, radiusMin, radiusMax, lateralMin, lateralMax; public int vertices, modeVertices; }
    [Serializable] public class WheelMesh { public string path; public int vertices; public float centreOffset, maxRadius; public bool used; public string reason; }
    [Serializable] public class WheelOut
    {
        public string clip; public float sourceRadius; public string[] rotatingPaths; public WheelMesh[] meshes; public RadiusBand[] bands;
    }
    [Serializable] public class RayHit { public float x, y, z, distance, normalZ; public bool hit; public string part; }
    // A wheel mesh of a truck prefab (a transform whose name contains "wheel" or starts with "whl", or under one): its centre and radius bands about it.
    [Serializable] public class TruckWheel { public string path, wheelNode; public float[] centre; public float maxRadius; public int vertices; public RadiusBand[] bands; }
    [Serializable] public class VehicleOut
    {
        public string id, role, prefab; public float[] boundsMin, boundsMax;
        public Node[] nodes; public MeshOut[] meshes; public AnchorOut[] anchors; public WheelOut[] wheels; public ClipOut[] clips;
        public RayHit[] cabRays; public TruckWheel[] truckWheels; public int audioSources;
    }
    [Serializable] public class Output { public int schema = 1; public string unity; public VehicleOut[] vehicles; public string[] problems; }
    [Serializable] public class Result { public string status; public int exitCode, problems; public bool runtimeValidated; public string error; }

    const string InputAsset = "Assets/Rr2dv/ProbeInput.json";
    const float BandWindow = 0.15f;      // radius bands kept within +/-15% of the source radius
    const float WheelCentreMax = 0.1f;   // a wheel-like mesh is centred on its pivot within 10% of the source radius
    static readonly List<string> Problems = new List<string>();

    public static void Run()
    {
        int exit = 0;
        string output = Environment.GetEnvironmentVariable("RR2DV_PROBE_OUT");
        var result = new Result { status = "failed", exitCode = 1 };
        try
        {
            if (string.IsNullOrEmpty(output)) throw new InvalidOperationException("RR2DV_PROBE_OUT is required");
            Directory.CreateDirectory(output);
            Problems.Clear();
            var project = Directory.GetParent(Application.dataPath).FullName;
            var input = JsonUtility.FromJson<Input>(File.ReadAllText(Path.Combine(project, InputAsset)));
            if (input == null || input.schema != 1 || input.vehicles == null) throw new InvalidDataException("unsupported probe input");
            if (input.missing != null) Problems.AddRange(input.missing.Select(m => "input: " + m));
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var outp = new Output { unity = Application.unityVersion, vehicles = input.vehicles.Select(Measure).ToArray() };
            outp.problems = Problems.ToArray();
            File.WriteAllText(Path.Combine(output, "probe.json"), JsonUtility.ToJson(outp, true));
            exit = Problems.Count > 0 ? 2 : 0;
            result = new Result { status = exit == 0 ? "passed" : "problems", exitCode = exit, problems = Problems.Count };
        }
        catch (Exception e)
        {
            Debug.LogException(e);
            exit = 1;
            result = new Result { status = "failed", exitCode = 1, problems = Problems.Count, error = e.ToString() };
        }
        finally
        {
            if (!string.IsNullOrEmpty(output) && Directory.Exists(output))
                File.WriteAllText(Path.Combine(output, "result.json"), JsonUtility.ToJson(result, true));
            EditorApplication.Exit(exit);
        }
    }

    static VehicleOut Measure(Vehicle v)
    {
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(v.prefab);
        if (!prefab) { Problems.Add(v.id + ": prefab not found " + v.prefab); return new VehicleOut { id = v.id, role = v.role, prefab = v.prefab }; }
        var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
        try
        {
            var root = go.transform;
            var outv = new VehicleOut { id = v.id, role = v.role, prefab = v.prefab };
            outv.nodes = root.GetComponentsInChildren<Transform>(true)
                .Select(t => new Node { path = TPath(t, root), position = V(t.position), rotation = Q(t.rotation), lossyScale = V(t.lossyScale) }).ToArray();
            outv.meshes = Meshes(v, root, out var bounds);
            if (bounds.HasValue) { outv.boundsMin = V(bounds.Value.min); outv.boundsMax = V(bounds.Value.max); }
            else Problems.Add(v.id + ": no visible geometry");
            outv.anchors = (v.components ?? new Comp[0]).Select(c => Anchor(v, root, c)).ToArray();
            outv.audioSources = root.GetComponentsInChildren<AudioSource>(true).Length;
            // Python cannot turn parented RR seat/firebox coordinates into car space before import.
            // Once the prefab is loaded, their measured anchors can supply the same cab grid.
            var cab = v.cab ?? CabFromAnchors(outv.anchors);
            outv.cabRays = cab != null && cab.xs != null && cab.xs.Length > 0 && cab.ys != null ? CabRays(root, cab) : new RayHit[0];
            outv.truckWheels = v.role == "truck" ? TruckWheels(root) : new TruckWheel[0];
            // Static-pose measurements are finished before any clip is sampled.
            outv.wheels = (v.wheelsets ?? new Wheelset[0]).Select(w => Wheel(v, root, w)).ToArray();
            outv.clips = (v.animationMap ?? new MapEntry[0]).Select(e => Clip(v, go, e)).ToArray();
            return outv;
        }
        finally { Object.DestroyImmediate(go); }
    }

    static MeshOut[] Meshes(Vehicle v, Transform root, out Bounds? bounds)
    {
        var list = new List<MeshOut>();
        Bounds? all = null;
        foreach (var r in root.GetComponentsInChildren<Renderer>(true))
        {
            Mesh mesh = null;
            var filter = r.GetComponent<MeshFilter>();
            if (filter) mesh = filter.sharedMesh;
            var skinned = r as SkinnedMeshRenderer;
            if (skinned) mesh = skinned.sharedMesh;
            if (!(r is MeshRenderer) && !skinned) continue;
            if (!mesh) { Problems.Add(v.id + ": missing mesh " + TPath(r.transform, root)); continue; }
            long tris = 0;
            for (int s = 0; s < mesh.subMeshCount; s++) tris += (long)mesh.GetIndexCount(s) / 3;
            int nullMaterials = r.sharedMaterials.Count(m => !m);
            if (nullMaterials > 0) Problems.Add(v.id + ": " + nullMaterials + " missing material(s) on " + TPath(r.transform, root));
            list.Add(new MeshOut { path = TPath(r.transform, root), triangles = (int)tris, boundsMin = V(r.bounds.min), boundsMax = V(r.bounds.max),
                                   materials = r.sharedMaterials.Select(m => m ? m.name : "").ToArray() });
            if (r.enabled && r.gameObject.activeInHierarchy)
            {
                if (all.HasValue) { var b = all.Value; b.Encapsulate(r.bounds); all = b; } else all = r.bounds;
            }
        }
        bounds = all;
        return list.ToArray();
    }

    static AnchorOut Anchor(Vehicle v, Transform root, Comp c)
    {
        var parent = string.IsNullOrEmpty(c.parentPath) ? root : root.Find(c.parentPath);
        var a = new AnchorOut { kind = c.kind, name = c.name, purpose = c.purpose, parentPath = c.parentPath, resolved = parent != null };
        if (!parent) { Problems.Add(v.id + ": component " + c.name + " parent not found: " + c.parentPath); return a; }
        var local = ToV(c.position, Vector3.zero);
        var rot = ToQ(c.rotation);
        a.position = V(parent.TransformPoint(local));
        a.rotation = Q(parent.rotation * rot);
        a.scale = V(Vector3.Scale(parent.lossyScale, ToV(c.scale, Vector3.one)));
        return a;
    }

    // Measures only; the tread is chosen from the bands by rr2dv (wheels.py), which keeps it for review (board X30).
    // A mesh counts when the wheelset clip rotates it through its nearest animated ancestor (so rods and linkage with
    // their own curves are left out), it is centred on that pivot and it reaches the source radius.
    static WheelOut Wheel(Vehicle v, Transform root, Wheelset w)
    {
        var o = new WheelOut { clip = w.clip, sourceRadius = w.diameter / 2f, rotatingPaths = new string[0], meshes = new WheelMesh[0], bands = new RadiusBand[0] };
        var clip = string.IsNullOrEmpty(w.clipAsset) ? null : AssetDatabase.LoadAssetAtPath<AnimationClip>(w.clipAsset);
        if (!clip) { Problems.Add(v.id + ": wheelset clip not loadable: " + w.clip); return o; }
        if (o.sourceRadius <= 0) { Problems.Add(v.id + ": wheelset " + w.clip + " has no source diameter"); return o; }
        var bindings = AnimationUtility.GetCurveBindings(clip);
        var animated = new HashSet<Transform>();
        foreach (var b in bindings) { var t = Find(root, b.path); if (t) animated.Add(t); }
        var rotating = bindings
            .Where(b => b.propertyName.IndexOf("Rotation", StringComparison.OrdinalIgnoreCase) >= 0 || b.propertyName.IndexOf("Euler", StringComparison.OrdinalIgnoreCase) >= 0)
            .Select(b => b.path).Distinct().OrderBy(p => p, StringComparer.Ordinal).ToArray();
        o.rotatingPaths = rotating;
        var seen = new HashSet<MeshFilter>();
        var meshes = new List<WheelMesh>();
        var bands = new SortedDictionary<int, RadiusBand>();
        var sums = new Dictionary<int, double>();
        var fine = new Dictionary<int, Dictionary<int, int>>();
        foreach (var path in rotating)
        {
            var t = Find(root, path);
            if (!t) continue;
            var pivot = t.position;
            foreach (var f in t.GetComponentsInChildren<MeshFilter>(true))
            {
                if (!f.sharedMesh) continue;
                var owner = f.transform;
                while (owner != t && !animated.Contains(owner)) owner = owner.parent;
                // A mesh under a nested rotating node is measured around that node's own pivot, on its turn.
                if (owner != t && rotating.Contains(TPath(owner, root))) continue;
                if (!seen.Add(f)) continue;
                var m = new WheelMesh { path = TPath(f.transform, root) };
                meshes.Add(m);
                if (owner != t) { m.reason = "moved by its own curves (" + TPath(owner, root) + ")"; continue; }
                var points = f.sharedMesh.vertices.Select(local => f.transform.TransformPoint(local) - pivot).ToArray();
                m.vertices = points.Length;
                if (points.Length == 0) { m.reason = "no vertices"; continue; }
                // Axle along car-local x: radius in the y-z plane around the pivot.
                var centre = new Vector2(points.Average(p => p.y), points.Average(p => p.z));
                m.centreOffset = centre.magnitude;
                m.maxRadius = points.Max(p => new Vector2(p.y, p.z).magnitude);
                if (m.centreOffset > WheelCentreMax * o.sourceRadius) { m.reason = "not centred on the axle"; continue; }
                if (m.maxRadius < (1f - BandWindow) * o.sourceRadius) { m.reason = "smaller than the wheel"; continue; }
                m.used = true;
                foreach (var p in points)
                {
                    float r = new Vector2(p.y, p.z).magnitude;
                    if (Mathf.Abs(r - o.sourceRadius) > BandWindow * o.sourceRadius) continue;
                    float lateral = Mathf.Abs(p.x);
                    int key = Mathf.RoundToInt(r * 1000f);
                    RadiusBand band;
                    if (!bands.TryGetValue(key, out band))
                    {
                        band = new RadiusBand { lateralMin = lateral, lateralMax = lateral, radiusMin = r, radiusMax = r };
                        bands[key] = band; sums[key] = 0; fine[key] = new Dictionary<int, int>();
                    }
                    band.vertices++;
                    sums[key] += r;
                    if (r < band.radiusMin) band.radiusMin = r;
                    if (r > band.radiusMax) band.radiusMax = r;
                    int step = Mathf.RoundToInt(r * 100000f);
                    int seenAt;
                    fine[key][step] = fine[key].TryGetValue(step, out seenAt) ? seenAt + 1 : 1;
                    if (lateral < band.lateralMin) band.lateralMin = lateral;
                    if (lateral > band.lateralMax) band.lateralMax = lateral;
                }
            }
        }
        foreach (var kv in bands)
        {
            kv.Value.radius = (float)(sums[kv.Key] / kv.Value.vertices);
            var mode = fine[kv.Key].OrderByDescending(f => f.Value).ThenBy(f => f.Key).First();
            kv.Value.modeRadius = mode.Key / 100000f;
            kv.Value.modeVertices = mode.Value;
        }
        o.meshes = meshes.ToArray();
        o.bands = bands.Values.ToArray();
        if (o.bands.Length == 0) Problems.Add(v.id + ": no wheel surface near the source radius for wheelset " + w.clip);
        return o;
    }

    static CabSpec CabFromAnchors(AnchorOut[] anchors)
    {
        var seats = anchors.Where(a => a.resolved && a.kind == "Seat" && a.position != null).ToArray();
        var fire = anchors.Where(a => a.resolved && a.kind == "FireboxEffect" && a.position != null)
            .OrderBy(a => a.position[2]).FirstOrDefault();
        if (seats.Length == 0 && fire == null) return null;
        float start = seats.Length > 0 ? seats.Min(a => a.position[2]) : fire.position[2] - 1f;
        float refY = fire != null ? fire.position[1] : seats.Min(a => a.position[1]) - 0.5f;
        return new CabSpec {
            startZ = start, length = 3f,
            xs = Enumerable.Range(0, 21).Select(i => -1f + i * 0.1f).ToArray(),
            ys = Enumerable.Range(0, 21).Select(i => refY - 0.4f + i * 0.1f).ToArray()
        };
    }

    // As the builder core's VisualHits: temporary MeshColliders on every visible mesh, the model's own colliders off.
    static RayHit[] CabRays(Transform root, CabSpec spec)
    {
        var temp = new List<GameObject>();
        var off = new List<Collider>();
        foreach (var c in root.GetComponentsInChildren<Collider>(true)) if (c.enabled) { c.enabled = false; off.Add(c); }
        foreach (var mf in root.GetComponentsInChildren<MeshFilter>(false))
        {
            var r = mf.GetComponent<MeshRenderer>();
            if (!mf.sharedMesh || mf.sharedMesh.vertexCount == 0 || !r || !r.enabled) continue;
            var g = new GameObject("[vis]"); g.transform.SetParent(mf.transform, false);
            g.AddComponent<MeshCollider>().sharedMesh = mf.sharedMesh;
            temp.Add(g);
        }
        Physics.SyncTransforms();
        var scene = root.gameObject.scene.GetPhysicsScene();
        var buf = new RaycastHit[256];
        var list = new List<RayHit>();
        try
        {
            foreach (float y in spec.ys)
                foreach (float x in spec.xs)
                {
                    var o = new RayHit { x = x, y = y };
                    int n = scene.Raycast(new Vector3(x, y, spec.startZ), Vector3.forward, buf, spec.length, ~0, QueryTriggerInteraction.Ignore);
                    for (int i = 0; i < n; i++)
                    {
                        if (buf[i].collider.name != "[vis]") continue;
                        if (o.hit && buf[i].distance >= o.distance) continue;
                        o.hit = true; o.distance = buf[i].distance; o.z = buf[i].point.z; o.normalZ = buf[i].normal.z;
                        o.part = TPath(buf[i].collider.transform.parent, root);
                    }
                    list.Add(o);
                }
        }
        finally
        {
            foreach (var g in temp) if (g) Object.DestroyImmediate(g);
            foreach (var c in off) if (c) c.enabled = true;
        }
        return list.ToArray();
    }

    // Truck prefabs: RR places them at runtime; their wheels are measured about each mesh's own centre (axle along x),
    // radius bands within 20% below the mesh's largest radius. rr2dv picks the tread from them (wheels.py).
    // A name containing "wheel" ('Standard 33" Wheels.001') or starting with "whl" (whl1_LOD0). Must match buildrecord.is_wheel_name.
    static bool IsWheelName(string name)
    {
        return name.IndexOf("wheel", StringComparison.OrdinalIgnoreCase) >= 0 || name.StartsWith("whl", StringComparison.OrdinalIgnoreCase);
    }

    static TruckWheel[] TruckWheels(Transform root)
    {
        var list = new List<TruckWheel>();
        foreach (var f in root.GetComponentsInChildren<MeshFilter>(true))
        {
            if (!f.sharedMesh || f.sharedMesh.vertexCount == 0) continue;
            Transform node = null;
            for (var t = f.transform; t && t != root; t = t.parent)
                if (IsWheelName(t.name)) node = t;
            if (!node) continue;
            var points = f.sharedMesh.vertices.Select(local => f.transform.TransformPoint(local)).ToArray();
            var b = new Bounds(points[0], Vector3.zero);
            foreach (var p in points) b.Encapsulate(p);
            var c = b.center;
            float max = points.Max(p => new Vector2(p.y - c.y, p.z - c.z).magnitude);
            var bands = new SortedDictionary<int, RadiusBand>();
            var sums = new Dictionary<int, double>();
            foreach (var p in points)
            {
                float r = new Vector2(p.y - c.y, p.z - c.z).magnitude;
                if (r < 0.8f * max) continue;
                float lateral = Mathf.Abs(p.x);
                int key = Mathf.RoundToInt(r * 1000f);
                RadiusBand band;
                if (!bands.TryGetValue(key, out band))
                {
                    band = new RadiusBand { lateralMin = lateral, lateralMax = lateral, radiusMin = r, radiusMax = r };
                    bands[key] = band; sums[key] = 0;
                }
                band.vertices++;
                sums[key] += r;
                if (r < band.radiusMin) band.radiusMin = r;
                if (r > band.radiusMax) band.radiusMax = r;
                if (lateral < band.lateralMin) band.lateralMin = lateral;
                if (lateral > band.lateralMax) band.lateralMax = lateral;
            }
            foreach (var kv in bands) { kv.Value.radius = (float)(sums[kv.Key] / kv.Value.vertices); kv.Value.modeRadius = kv.Value.radius; }
            list.Add(new TruckWheel { path = TPath(f.transform, root), wheelNode = TPath(node, root), centre = V(c), maxRadius = max,
                                      vertices = points.Length, bands = bands.Values.ToArray() });
        }
        return list.ToArray();
    }

    static ClipOut Clip(Vehicle v, GameObject go, MapEntry e)
    {
        var o = new ClipOut { key = e.key, asset = e.asset, missingPaths = new string[0], poses = new Pose[0] };
        var clip = string.IsNullOrEmpty(e.asset) ? null : AssetDatabase.LoadAssetAtPath<AnimationClip>(e.asset);
        if (!clip) { Problems.Add(v.id + ": clip not loadable: " + e.key); return o; }
        var root = go.transform;
        var bindings = AnimationUtility.GetCurveBindings(clip);
        o.duration = clip.length;
        o.curves = bindings.Length;
        var paths = bindings.Select(b => b.path).Distinct().OrderBy(p => p, StringComparer.Ordinal).ToArray();
        o.missingPaths = paths.Where(p => !(string.IsNullOrEmpty(p) ? root : root.Find(p))).ToArray();
        foreach (var p in o.missingPaths) Problems.Add(v.id + ": clip " + e.key + " binds missing path " + p);
        var found = paths.Where(p => !o.missingPaths.Contains(p)).ToArray();
        var poses = found.Select(p => new Pose { path = p }).ToArray();
        // Endpoint 0.999 as the guide's port sampling does (A02); then back to the start pose.
        clip.SampleAnimation(go, 0f);
        for (int i = 0; i < found.Length; i++) { var t = Find(root, found[i]); poses[i].start = V(t.position); poses[i].startEuler = V(t.eulerAngles); }
        clip.SampleAnimation(go, 0.999f * clip.length);
        for (int i = 0; i < found.Length; i++) { var t = Find(root, found[i]); poses[i].end = V(t.position); poses[i].endEuler = V(t.eulerAngles); }
        clip.SampleAnimation(go, 0f);
        o.poses = poses;
        return o;
    }

    static Transform Find(Transform root, string path) => string.IsNullOrEmpty(path) ? root : root.Find(path);
    static string TPath(Transform t, Transform root) => AnimationUtility.CalculateTransformPath(t, root);
    static float[] V(Vector3 v) => new[] { v.x, v.y, v.z };
    static float[] Q(Quaternion q) => new[] { q.x, q.y, q.z, q.w };
    static Vector3 ToV(float[] a, Vector3 fallback) => a != null && a.Length == 3 ? new Vector3(a[0], a[1], a[2]) : fallback;
    static Quaternion ToQ(float[] a) => a != null && a.Length == 4 ? new Quaternion(a[0], a[1], a[2], a[3]) : Quaternion.identity;
}
