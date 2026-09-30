using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

// vanilla-flavoured Phase 2 measurements (docs/vanilla/measurement-regime.md, M1-M13). Unity 2019.4, editor only.
// Read-only like Rr2dvProbe: temporary copies in an empty scene, temporary colliders removed again, nothing saved.
// Input: Assets/Rr2dv/ProbeInput.json (the probe's own input, so the same vehicles, prefabs, wheelsets, anchors and
// clip maps). Output: <VF_OUT>/vf-measure.json and result.json. Every value is a measurement or a copy of a
// definition value; nothing here decides a conversion value.
// Coordinates: car space = the instantiated prefab at the origin; x right, y up, z front. Angles in degrees.
public static class VfMeasure
{
    [Serializable] public class MapEntry { public string key, asset, guid; }
    [Serializable] public class Wheelset { public string clip, clipAsset; public float diameter, offset, length; public int axles; }
    [Serializable] public class Comp { public string kind, name, purpose, parentPath, clip, clipAsset; public float[] position, rotation, scale; }
    [Serializable] public class Vehicle { public string id, role, prefab; public Wheelset[] wheelsets; public Comp[] components; public MapEntry[] animationMap; }
    [Serializable] public class Input { public int schema; public Vehicle[] vehicles; }

    // M1: one rotating wheel node of a wheelset clip, measured about its own pivot.
    [Serializable] public class Band { public float radius, lateralMin, lateralMax; public int vertices; }
    [Serializable] public class Axle
    {
        public string clip, path; public float sourceRadius; public float[] pivot;
        public int meshes, vertices; public float maxRadius, lateralMin, lateralMax, lowestY, pivotAboveLowest;
        public Band[] bands;
    }
    // M2: every transform a wheelset clip moves, in world space at four phases of the clip.
    [Serializable] public class PhasePose { public string path; public float[] position, rotation; }
    [Serializable] public class Phase { public float fraction; public PhasePose[] poses; }
    [Serializable] public class PhaseSet { public string clip; public float duration; public string[] missingPaths; public Phase[] phases; }
    // M3 / M4: rays. z is the first visible surface met; hits lists every surface met (y for downward rays).
    [Serializable] public class RayOut { public float x, y, z; public bool hit; public float distance, normalZ; public string part; }
    [Serializable] public class ColumnRay { public float x, z; public float[] ys, colliderYs; }
    // M4 / M5 / M13: what each clip does to each transform it moves.
    [Serializable] public class Sweep
    {
        public string clip, path; public float duration;
        public float worldAngle, localAngle; public float[] worldAxis, localAxis, worldMove, localMove, scaleEnd;
    }
    // M8 / M9 / M12 / M13 / M10.
    [Serializable] public class Slot { public int index; public string material, shader, mainTexture; public bool isNull, emission; public float[] colour; }
    [Serializable] public class RendererOut
    {
        public string path, kind; public bool enabled, active; public int triangles, lodGroups; public float[] boundsMin, boundsMax; public Slot[] slots;
    }
    [Serializable] public class SkinnedOut { public string path, mesh, rootBone; public int bones, vertices; public float[] boundsMin, boundsMax; }
    [Serializable] public class ColliderOut
    {
        public string path, type; public bool enabled, trigger, convex, moving; public string mesh; public float[] centre, size, lossyScale; public float radius, height;
    }
    [Serializable] public class Near { public string path; public float distance; public string[] emissiveMaterials; }
    [Serializable] public class LampOut { public string kind, name, purpose; public float[] position; public Near[] near; }
    [Serializable] public class LightOut { public string path, type; public float range, intensity; public bool enabled; }
    [Serializable] public class Odd { public string path, what; public float[] value; }
    [Serializable] public class Named { public string path; public float[] position; }
    [Serializable] public class VehicleOut
    {
        public string id, role, prefab; public float originY; public float[] boundsMin, boundsMax;
        public Axle[] axles; public PhaseSet[] phases; public RayOut[] beamFront, beamRear; public ColumnRay[] columns;
        public Sweep[] sweeps; public RendererOut[] renderers; public SkinnedOut[] skinned; public ColliderOut[] colliders;
        public LampOut[] lamps; public LightOut[] lights; public Odd[] oddities; public Named[] named; public int skippedSkinnedForRays;
    }
    [Serializable] public class Output { public int schema = 1; public string unity; public VehicleOut[] vehicles; public string[] problems; }
    [Serializable] public class Result { public string status; public int exitCode, problems; public string error; }

    const string InputAsset = "Assets/Rr2dv/ProbeInput.json";
    const float BandWindow = 0.15f;
    static readonly float[] Fractions = { 0f, 0.25f, 0.5f, 0.75f };
    static readonly float[] BeamXs = { -1.0f, -0.5f, 0f, 0.5f, 1.0f };
    static readonly float[] BeamYs = { 0.4f, 0.6f, 0.8f, 1.0f, 1.2f, 1.4f, 1.7f, 2.0f };
    static readonly float[] ColumnXs = { -0.8f, -0.4f, 0f, 0.4f, 0.8f };
    static readonly string[] NameKeys = { "coupler", "knuckle", "pilot", "buffer", "beam", "bolster", "pivot", "kingpin", "center plate", "headlight", "coal", "hatch" };
    static readonly List<string> Problems = new List<string>();

    public static void Run()
    {
        int exit = 0;
        string output = Environment.GetEnvironmentVariable("VF_OUT");
        var result = new Result { status = "failed", exitCode = 1 };
        try
        {
            if (string.IsNullOrEmpty(output)) throw new InvalidOperationException("VF_OUT is required");
            Directory.CreateDirectory(output);
            Problems.Clear();
            var project = Directory.GetParent(Application.dataPath).FullName;
            var input = JsonUtility.FromJson<Input>(File.ReadAllText(Path.Combine(project, InputAsset)));
            if (input == null || input.schema != 1 || input.vehicles == null) throw new InvalidDataException("unsupported probe input");
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var outp = new Output { unity = Application.unityVersion, vehicles = input.vehicles.Select(Measure).ToArray() };
            outp.problems = Problems.ToArray();
            File.WriteAllText(Path.Combine(output, "vf-measure.json"), JsonUtility.ToJson(outp, true));
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
        var o = new VehicleOut { id = v.id, role = v.role, prefab = v.prefab };
        if (!prefab) { Problems.Add(v.id + ": prefab not found " + v.prefab); return o; }
        var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
        try
        {
            var root = go.transform;
            o.originY = root.position.y;
            Bounds? bounds = null;
            foreach (var r in root.GetComponentsInChildren<Renderer>(true))
            {
                if (!(r is MeshRenderer) && !(r is SkinnedMeshRenderer)) continue;
                if (!r.enabled || !r.gameObject.activeInHierarchy) continue;
                if (bounds.HasValue) { var b = bounds.Value; b.Encapsulate(r.bounds); bounds = b; } else bounds = r.bounds;
            }
            if (bounds.HasValue) { o.boundsMin = V(bounds.Value.min); o.boundsMax = V(bounds.Value.max); }
            else Problems.Add(v.id + ": no visible geometry");
            var animated = AnimatedTransforms(v, root);
            // Static pose first: everything below that samples a clip is done after these.
            o.renderers = Renderers(v, root);
            o.skinned = root.GetComponentsInChildren<SkinnedMeshRenderer>(true).Select(s => Skinned(root, s)).ToArray();
            o.colliders = root.GetComponentsInChildren<Collider>(true).Select(c => ColliderInfo(root, c, animated)).ToArray();
            o.lights = root.GetComponentsInChildren<Light>(true).Select(l => new LightOut { path = TPath(l.transform, root), type = l.type.ToString(), range = l.range, intensity = l.intensity, enabled = l.enabled }).ToArray();
            o.lamps = (v.components ?? new Comp[0]).Where(c => IsLampKind(c.kind)).Select(c => Lamp(v, root, c)).ToArray();
            o.oddities = Oddities(root);
            o.named = root.GetComponentsInChildren<Transform>(true)
                .Where(t => NameKeys.Any(k => t.name.IndexOf(k, StringComparison.OrdinalIgnoreCase) >= 0))
                .Select(t => new Named { path = TPath(t, root), position = V(t.position) }).ToArray();
            if (bounds.HasValue && v.role != "truck") { BeamAndColumns(v, root, bounds.Value, o); }
            o.axles = v.role == "truck" ? TruckAxles(root) : (v.wheelsets ?? new Wheelset[0]).SelectMany(w => Axles(v, root, w)).ToArray();
            // Clips move things: sweeps and phases run last, each starting and ending on the start pose.
            o.sweeps = (v.animationMap ?? new MapEntry[0]).SelectMany(e => Sweeps(v, go, e)).ToArray();
            o.phases = (v.wheelsets ?? new Wheelset[0]).Where(w => !string.IsNullOrEmpty(w.clipAsset)).GroupBy(w => w.clipAsset).Select(g => Phases(v, go, g.First())).ToArray();
            return o;
        }
        finally { Object.DestroyImmediate(go); }
    }

    // ---- M1: wheel nodes, one by one ---------------------------------------------------------------------------------
    static Axle[] Axles(Vehicle v, Transform root, Wheelset w)
    {
        var list = new List<Axle>();
        var clip = string.IsNullOrEmpty(w.clipAsset) ? null : AssetDatabase.LoadAssetAtPath<AnimationClip>(w.clipAsset);
        if (!clip) { Problems.Add(v.id + ": wheelset clip not loadable: " + w.clip); return list.ToArray(); }
        float source = w.diameter / 2f;
        var bindings = AnimationUtility.GetCurveBindings(clip);
        var animated = new HashSet<Transform>();
        foreach (var b in bindings) { var t = Find(root, b.path); if (t) animated.Add(t); }
        var rotating = bindings
            .Where(b => b.propertyName.IndexOf("Rotation", StringComparison.OrdinalIgnoreCase) >= 0 || b.propertyName.IndexOf("Euler", StringComparison.OrdinalIgnoreCase) >= 0)
            .Select(b => b.path).Distinct().OrderBy(p => p, StringComparer.Ordinal).ToArray();
        foreach (var path in rotating)
        {
            var t = Find(root, path);
            if (!t) continue;
            var pivot = t.position;
            var a = new Axle { clip = w.clip, path = path, sourceRadius = source, pivot = V(pivot), lowestY = float.MaxValue, lateralMin = float.MaxValue, lateralMax = float.MinValue };
            var bands = new SortedDictionary<int, Band>();
            foreach (var f in t.GetComponentsInChildren<MeshFilter>(true))
            {
                if (!f.sharedMesh) continue;
                var owner = f.transform;
                while (owner != t && !animated.Contains(owner)) owner = owner.parent;
                if (owner != t) continue;   // rods and linkage with their own curves are not the wheel
                a.meshes++;
                foreach (var local in f.sharedMesh.vertices)
                {
                    var p = f.transform.TransformPoint(local);
                    var d = p - pivot;
                    float r = new Vector2(d.y, d.z).magnitude;
                    a.vertices++;
                    if (r > a.maxRadius) a.maxRadius = r;
                    if (p.y < a.lowestY) a.lowestY = p.y;
                    if (source > 0f && Mathf.Abs(r - source) > BandWindow * source) continue;
                    float lateral = Mathf.Abs(d.x);
                    if (lateral < a.lateralMin) a.lateralMin = lateral;
                    if (lateral > a.lateralMax) a.lateralMax = lateral;
                    int key = Mathf.RoundToInt(r * 1000f);
                    Band band;
                    if (!bands.TryGetValue(key, out band)) { band = new Band { lateralMin = lateral, lateralMax = lateral }; bands[key] = band; }
                    band.vertices++;
                    band.radius += r;   // sum for now, divided below
                    if (lateral < band.lateralMin) band.lateralMin = lateral;
                    if (lateral > band.lateralMax) band.lateralMax = lateral;
                }
            }
            if (a.vertices == 0) continue;   // rods, valve gear and links that the wheelset clip also turns: not wheels, not a problem
            foreach (var kv in bands) kv.Value.radius /= kv.Value.vertices;
            // Every 1 mm band in the window, largest radius first (Phase 2 kept only the six widest, which hid the tread; capped at 60).
            a.bands = bands.Values.OrderByDescending(b => b.radius).Take(60).ToArray();
            a.pivotAboveLowest = pivot.y - a.lowestY;
            if (a.lateralMin == float.MaxValue) { a.lateralMin = 0f; a.lateralMax = 0f; }
            list.Add(a);
        }
        return list.ToArray();
    }

    // M7: truck prefabs have no wheelset clip here; each wheel-named mesh is measured about its own bounds centre (axle along x),
    // as the probe's truckWheels do, plus its lowest point and lateral width.
    static Axle[] TruckAxles(Transform root)
    {
        var list = new List<Axle>();
        foreach (var f in root.GetComponentsInChildren<MeshFilter>(true))
        {
            if (!f.sharedMesh || f.sharedMesh.vertexCount == 0) continue;
            Transform node = null;
            for (var t = f.transform; t && t != root; t = t.parent)
                if (t.name.IndexOf("wheel", StringComparison.OrdinalIgnoreCase) >= 0 || t.name.StartsWith("whl", StringComparison.OrdinalIgnoreCase)) node = t;
            if (!node) continue;
            var points = f.sharedMesh.vertices.Select(local => f.transform.TransformPoint(local)).ToArray();
            var bb = new Bounds(points[0], Vector3.zero);
            foreach (var p in points) bb.Encapsulate(p);
            var c = bb.center;
            var a = new Axle { clip = "", path = TPath(f.transform, root), pivot = V(c), meshes = 1, vertices = points.Length, lowestY = points.Min(p => p.y), lateralMin = float.MaxValue, lateralMax = float.MinValue };
            a.maxRadius = points.Max(p => new Vector2(p.y - c.y, p.z - c.z).magnitude);
            a.pivotAboveLowest = c.y - a.lowestY;
            var bands = new SortedDictionary<int, Band>();
            foreach (var p in points)
            {
                float r = new Vector2(p.y - c.y, p.z - c.z).magnitude;
                float lateral = Mathf.Abs(p.x - c.x);
                if (lateral < a.lateralMin) a.lateralMin = lateral;
                if (lateral > a.lateralMax) a.lateralMax = lateral;
                if (r < 0.8f * a.maxRadius) continue;
                int key = Mathf.RoundToInt(r * 1000f);
                Band band;
                if (!bands.TryGetValue(key, out band)) { band = new Band { lateralMin = lateral, lateralMax = lateral }; bands[key] = band; }
                band.vertices++; band.radius += r;
                if (lateral < band.lateralMin) band.lateralMin = lateral;
                if (lateral > band.lateralMax) band.lateralMax = lateral;
            }
            foreach (var kv in bands) kv.Value.radius /= kv.Value.vertices;
            a.bands = bands.Values.OrderByDescending(b => b.radius).Take(60).ToArray();
            list.Add(a);
        }
        return list.ToArray();
    }

    // ---- M2: wheelset clip at four phases -----------------------------------------------------------------------------
    static PhaseSet Phases(Vehicle v, GameObject go, Wheelset w)
    {
        var ps = new PhaseSet { clip = w.clip, missingPaths = new string[0], phases = new Phase[0] };
        var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(w.clipAsset);
        if (!clip) return ps;
        var root = go.transform;
        ps.duration = clip.length;
        var paths = AnimationUtility.GetCurveBindings(clip).Select(b => b.path).Distinct().OrderBy(p => p, StringComparer.Ordinal).ToArray();
        ps.missingPaths = paths.Where(p => !Find(root, p)).ToArray();
        var found = paths.Where(p => Find(root, p)).ToArray();
        var phases = new List<Phase>();
        foreach (float f in Fractions)
        {
            clip.SampleAnimation(go, f * clip.length);
            phases.Add(new Phase { fraction = f, poses = found.Select(p => { var t = Find(root, p); return new PhasePose { path = p, position = V(t.position), rotation = Q(t.rotation) }; }).ToArray() });
        }
        clip.SampleAnimation(go, 0f);
        ps.phases = phases.ToArray();
        return ps;
    }

    // ---- M4 / M5 / M13: what each clip does to each transform it moves -------------------------------------------------
    static Sweep[] Sweeps(Vehicle v, GameObject go, MapEntry e)
    {
        var list = new List<Sweep>();
        var clip = string.IsNullOrEmpty(e.asset) ? null : AssetDatabase.LoadAssetAtPath<AnimationClip>(e.asset);
        if (!clip) return list.ToArray();
        var root = go.transform;
        var paths = AnimationUtility.GetCurveBindings(clip).Select(b => b.path).Distinct().OrderBy(p => p, StringComparer.Ordinal).Where(p => Find(root, p)).ToArray();
        var ts = paths.Select(p => Find(root, p)).ToArray();
        clip.SampleAnimation(go, 0f);
        var p0 = ts.Select(t => t.position).ToArray(); var q0 = ts.Select(t => t.rotation).ToArray();
        var lp0 = ts.Select(t => t.localPosition).ToArray(); var lq0 = ts.Select(t => t.localRotation).ToArray();
        clip.SampleAnimation(go, 0.999f * clip.length);
        for (int i = 0; i < ts.Length; i++)
        {
            float wa, la; Vector3 wx, lx;
            var dq = ts[i].rotation * Quaternion.Inverse(q0[i]); dq.ToAngleAxis(out wa, out wx);
            var dl = ts[i].localRotation * Quaternion.Inverse(lq0[i]); dl.ToAngleAxis(out la, out lx);
            if (wa > 180f) { wa = 360f - wa; wx = -wx; }
            if (la > 180f) { la = 360f - la; lx = -lx; }
            list.Add(new Sweep { clip = e.key, path = paths[i], duration = clip.length, worldAngle = wa, localAngle = la, worldAxis = V(wx), localAxis = V(lx),
                                 worldMove = V(ts[i].position - p0[i]), localMove = V(ts[i].localPosition - lp0[i]), scaleEnd = V(ts[i].lossyScale) });
        }
        clip.SampleAnimation(go, 0f);
        return list.ToArray();
    }

    // ---- M3 / M4: rays against every visible mesh ------------------------------------------------------------------------
    static void BeamAndColumns(Vehicle v, Transform root, Bounds b, VehicleOut o)
    {
        var temp = new List<GameObject>();
        var off = new List<Collider>();
        // First the model's own solid colliders (the walkable hull: a cab floor is often collision only, with no visible floor mesh).
        Physics.SyncTransforms();
        var scene0 = root.gameObject.scene.GetPhysicsScene();
        var buf0 = new RaycastHit[256];
        var own = new Dictionary<string, float[]>();
        for (float z = b.min.z; z <= b.max.z; z += 0.25f)
            foreach (float x in ColumnXs)
            {
                int n0 = scene0.Raycast(new Vector3(x, b.max.y + 0.5f, z), Vector3.down, buf0, b.size.y + 1f, ~0, QueryTriggerInteraction.Ignore);
                var oy = new List<float>();
                for (int i = 0; i < n0; i++) oy.Add(buf0[i].point.y);
                oy.Sort(); oy.Reverse();
                own[x + "|" + z] = oy.Take(40).ToArray();
            }
        foreach (var c in root.GetComponentsInChildren<Collider>(true)) if (c.enabled) { c.enabled = false; off.Add(c); }
        foreach (var mf in root.GetComponentsInChildren<MeshFilter>(false))
        {
            var r = mf.GetComponent<MeshRenderer>();
            if (!mf.sharedMesh || mf.sharedMesh.vertexCount == 0 || !r || !r.enabled) continue;
            var g = new GameObject("[vf]"); g.transform.SetParent(mf.transform, false);
            g.AddComponent<MeshCollider>().sharedMesh = mf.sharedMesh;
            temp.Add(g);
        }
        // Skinned meshes are not baked here (BakeMesh scale handling is unverified): counted, and their bounds are in renderers[].
        o.skippedSkinnedForRays = root.GetComponentsInChildren<SkinnedMeshRenderer>(false).Length;
        Physics.SyncTransforms();
        var scene = root.gameObject.scene.GetPhysicsScene();
        var buf = new RaycastHit[256];
        try
        {
            float len = b.size.z + 2f;
            var front = new List<RayOut>(); var rear = new List<RayOut>();
            foreach (float y in BeamYs)
                foreach (float x in BeamXs)
                {
                    front.Add(Cast(scene, buf, root, new Vector3(x, y, b.max.z + 1f), Vector3.back, len));
                    rear.Add(Cast(scene, buf, root, new Vector3(x, y, b.min.z - 1f), Vector3.forward, len));
                }
            o.beamFront = front.ToArray(); o.beamRear = rear.ToArray();
            // Downward columns over the whole length in 0.25 m steps: every surface met, top to bottom (roof, ceiling, floor, frame).
            var cols = new List<ColumnRay>();
            for (float z = b.min.z; z <= b.max.z; z += 0.25f)
                foreach (float x in ColumnXs)
                {
                    int n = scene.Raycast(new Vector3(x, b.max.y + 0.5f, z), Vector3.down, buf, b.size.y + 1f, ~0, QueryTriggerInteraction.Ignore);
                    var ys = new List<float>();
                    for (int i = 0; i < n; i++) if (buf[i].collider.name == "[vf]") ys.Add(buf[i].point.y);
                    ys.Sort(); ys.Reverse();
                    cols.Add(new ColumnRay { x = x, z = z, ys = ys.Take(40).ToArray(), colliderYs = own[x + "|" + z] });
                }
            o.columns = cols.ToArray();
        }
        finally
        {
            foreach (var g in temp) if (g) Object.DestroyImmediate(g);
            foreach (var c in off) if (c) c.enabled = true;
        }
    }

    static RayOut Cast(PhysicsScene scene, RaycastHit[] buf, Transform root, Vector3 origin, Vector3 dir, float len)
    {
        var o = new RayOut { x = origin.x, y = origin.y };
        int n = scene.Raycast(origin, dir, buf, len, ~0, QueryTriggerInteraction.Ignore);
        for (int i = 0; i < n; i++)
        {
            if (buf[i].collider.name != "[vf]") continue;
            if (o.hit && buf[i].distance >= o.distance) continue;
            o.hit = true; o.distance = buf[i].distance; o.z = buf[i].point.z; o.normalZ = buf[i].normal.z;
            o.part = TPath(buf[i].collider.transform.parent, root);
        }
        return o;
    }

    // ---- M8 / M9 / M12 / M13 / M10 ----------------------------------------------------------------------------------------
    static RendererOut[] Renderers(Vehicle v, Transform root)
    {
        var groups = root.GetComponentsInChildren<LODGroup>(true);
        var list = new List<RendererOut>();
        foreach (var r in root.GetComponentsInChildren<Renderer>(true))
        {
            Mesh mesh = null;
            var filter = r.GetComponent<MeshFilter>();
            if (filter) mesh = filter.sharedMesh;
            var skinned = r as SkinnedMeshRenderer;
            if (skinned) mesh = skinned.sharedMesh;
            long tris = 0;
            if (mesh) for (int s = 0; s < mesh.subMeshCount; s++) tris += (long)mesh.GetIndexCount(s) / 3;
            var slots = r.sharedMaterials.Select((m, i) => MakeSlot(m, i)).ToArray();
            list.Add(new RendererOut { path = TPath(r.transform, root), kind = skinned ? "skinned" : (r is MeshRenderer ? "mesh" : r.GetType().Name), enabled = r.enabled,
                                        active = r.gameObject.activeInHierarchy, triangles = (int)tris, lodGroups = groups.Count(g => r.transform.IsChildOf(g.transform)),
                                        boundsMin = V(r.bounds.min), boundsMax = V(r.bounds.max), slots = slots });
        }
        return list.ToArray();
    }

    static Slot MakeSlot(Material m, int i)
    {
        if (!m) return new Slot { index = i, isNull = true, material = "", shader = "", mainTexture = "" };
        var s = new Slot { index = i, material = m.name, shader = m.shader ? m.shader.name : "" };
        var tex = m.HasProperty("_MainTex") ? m.GetTexture("_MainTex") : null;
        s.mainTexture = tex ? tex.name : "";
        s.emission = m.HasProperty("_EmissionColor") && m.IsKeywordEnabled("_EMISSION");
        Color c = m.HasProperty("_BaseColor") ? m.GetColor("_BaseColor") : (m.HasProperty("_Color") ? m.GetColor("_Color") : Color.white);
        s.colour = new[] { c.r, c.g, c.b, c.a };
        return s;
    }

    static SkinnedOut Skinned(Transform root, SkinnedMeshRenderer s)
    {
        return new SkinnedOut { path = TPath(s.transform, root), mesh = s.sharedMesh ? s.sharedMesh.name : "", vertices = s.sharedMesh ? s.sharedMesh.vertexCount : 0,
                                rootBone = s.rootBone ? TPath(s.rootBone, root) : "", bones = s.bones == null ? 0 : s.bones.Length,
                                boundsMin = V(s.bounds.min), boundsMax = V(s.bounds.max) };
    }

    static HashSet<Transform> AnimatedTransforms(Vehicle v, Transform root)
    {
        var set = new HashSet<Transform>();
        foreach (var e in v.animationMap ?? new MapEntry[0])
        {
            var clip = string.IsNullOrEmpty(e.asset) ? null : AssetDatabase.LoadAssetAtPath<AnimationClip>(e.asset);
            if (!clip) continue;
            foreach (var b in AnimationUtility.GetCurveBindings(clip)) { var t = Find(root, b.path); if (t) set.Add(t); }
        }
        return set;
    }

    static ColliderOut ColliderInfo(Transform root, Collider c, HashSet<Transform> animated)
    {
        var o = new ColliderOut { path = TPath(c.transform, root), type = c.GetType().Name, enabled = c.enabled, trigger = c.isTrigger, lossyScale = V(c.transform.lossyScale) };
        for (var t = c.transform; t && t != root.parent; t = t.parent) if (animated.Contains(t)) { o.moving = true; break; }
        var box = c as BoxCollider; var cap = c as CapsuleCollider; var sph = c as SphereCollider; var mc = c as MeshCollider;
        if (box) { o.centre = V(box.center); o.size = V(box.size); }
        if (cap) { o.centre = V(cap.center); o.radius = cap.radius; o.height = cap.height; }
        if (sph) { o.centre = V(sph.center); o.radius = sph.radius; }
        if (mc) { o.convex = mc.convex; o.mesh = mc.sharedMesh ? mc.sharedMesh.name : ""; }
        return o;
    }

    static bool IsLampKind(string kind)
    {
        return kind == "Headlight" || kind == "ClassLight" || kind == "LightFixture" || kind == "MarkerLight" || kind == "Lantern";
    }

    // M10: the definition places a lamp; the mesh that looks like the lens is whatever visible mesh is nearest.
    static LampOut Lamp(Vehicle v, Transform root, Comp c)
    {
        var parent = string.IsNullOrEmpty(c.parentPath) ? root : root.Find(c.parentPath);
        var o = new LampOut { kind = c.kind, name = c.name, purpose = c.purpose, near = new Near[0] };
        if (!parent) { Problems.Add(v.id + ": lamp " + c.name + " parent not found: " + c.parentPath); return o; }
        var point = parent.TransformPoint(c.position != null && c.position.Length == 3 ? new Vector3(c.position[0], c.position[1], c.position[2]) : Vector3.zero);
        o.position = V(point);
        o.near = root.GetComponentsInChildren<Renderer>(false)
            .Where(r => r.enabled && (r is MeshRenderer || r is SkinnedMeshRenderer))
            .Select(r => new { r, d = Mathf.Sqrt(r.bounds.SqrDistance(point)) })
            .Where(x => x.d <= 0.35f).OrderBy(x => x.d).Take(3)
            .Select(x => new Near { path = TPath(x.r.transform, root), distance = x.d,
                                    emissiveMaterials = x.r.sharedMaterials.Where(m => m && m.HasProperty("_EmissionColor") && m.IsKeywordEnabled("_EMISSION")).Select(m => m.name).ToArray() })
            .ToArray();
        return o;
    }

    // M13: source data that is odd at world pose. Reported, never corrected.
    static Odd[] Oddities(Transform root)
    {
        var list = new List<Odd>();
        foreach (var t in root.GetComponentsInChildren<Transform>(true))
        {
            var s = t.lossyScale;
            string path = TPath(t, root);
            if (Mathf.Abs(s.x) < 1e-4f || Mathf.Abs(s.y) < 1e-4f || Mathf.Abs(s.z) < 1e-4f) list.Add(new Odd { path = path, what = "zero scale", value = V(s) });
            else if (Mathf.Max(Mathf.Abs(s.x), Mathf.Max(Mathf.Abs(s.y), Mathf.Abs(s.z))) > 5f || Mathf.Min(Mathf.Abs(s.x), Mathf.Min(Mathf.Abs(s.y), Mathf.Abs(s.z))) < 0.05f)
                list.Add(new Odd { path = path, what = "extreme scale", value = V(s) });
            if (t != root && (t.name != t.name.Trim())) list.Add(new Odd { path = path, what = "name has leading or trailing space" });
            if (t.parent)
            {
                int same = 0;
                foreach (Transform sib in t.parent) if (sib != t && sib.name == t.name) same++;
                if (same > 0 && t.GetSiblingIndex() == t.parent.Cast<Transform>().ToList().FindIndex(x => x.name == t.name))
                    list.Add(new Odd { path = path, what = "duplicate sibling name (x" + (same + 1) + ")" });
            }
        }
        return list.ToArray();
    }

    static Transform Find(Transform root, string path) => string.IsNullOrEmpty(path) ? root : root.Find(path);
    static string TPath(Transform t, Transform root) => AnimationUtility.CalculateTransformPath(t, root);
    static float[] V(Vector3 v) => new[] { v.x, v.y, v.z };
    static float[] Q(Quaternion q) => new[] { q.x, q.y, q.z, q.w };
}
