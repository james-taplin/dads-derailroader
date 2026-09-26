using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

// Read-only probe of the G-29 export (loco, tender, Fox truck): parts with world bounds,
// anchors, what every clip moves, wheel revolutions per clip, and renders with a quick Standard preview of the RR materials.
//   tools\run_unity.ps1 -Method C21Probe.Run -Out analysis\probe        (env RLW_PROBE_OUT = output folder)
public static class C21Probe
{
    static readonly string[] Prefabs = { C21Source.Loco, C21Source.Tender, C21Source.Truck };
    static readonly StringBuilder R = new StringBuilder();
    static string outDir;
    static bool chain;
    public static void RunAll() { chain = true; Wheels(); R.Clear(); Backhead(); R.Clear(); Floor(); R.Clear(); Faces(); EditorApplication.Exit(0); }

    public static void Run()
    {
        outDir = Environment.GetEnvironmentVariable("RLW_PROBE_OUT") ?? Path.GetFullPath("ProbeOut");
        Directory.CreateDirectory(outDir);
        try
        {
            C21Source.EnsureFlat();
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            Clips();
            foreach (var p in Prefabs) Parts(p);
            Renders();
        }
        catch (Exception e) { L("EXCEPTION " + e); }
        File.WriteAllText(Path.Combine(outDir, "probe_report.txt"), R.ToString());
        if (!chain) EditorApplication.Exit(0);
    }

    // Backhead layout for placing DV controls: orthographic front view (from the cab, looking +z) with a 0.1 m grid
    // (x -1.2..1.2, y 1.7..3.9, 500 px/m), mesh islands of every part near the backhead, and a depth table of the first surface.
    const float BhZMin = -3.75f, BhZMax = -2.6f, BhY0 = 1.6f, CamZ = -6.5f;
    public static void Backhead()
    {
        outDir = Environment.GetEnvironmentVariable("RLW_PROBE_OUT") ?? Path.GetFullPath("ProbeOut");
        Directory.CreateDirectory(outDir);
        try
        {
            C21Source.EnsureFlat();
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var go = Inst(Prefabs[0]);
            var cache = new Dictionary<Material, Material>();
            foreach (var r in go.GetComponentsInChildren<Renderer>(true))
                r.sharedMaterials = r.sharedMaterials.Select(m => m == null ? null : cache.TryGetValue(m, out var s) ? s : (cache[m] = Preview(m))).ToArray();

            S($"Mesh islands near the backhead (z {BhZMin}..{BhZMax})");
            var boxes = new List<(Bounds b, Color c)>();
            int n = 0;
            foreach (var mf in go.GetComponentsInChildren<MeshFilter>(true))
            {
                var r = mf.GetComponent<Renderer>();
                if (!r || !mf.sharedMesh) continue;
                var rb = r.bounds;
                if (rb.max.z < BhZMin || rb.min.z > BhZMax || rb.max.y < BhY0 || rb.min.y > 3.9f || Mathf.Abs(rb.center.x) > 1.25f) continue;
                var verts = mf.sharedMesh.vertices; var tris = mf.sharedMesh.triangles;
                var key = new Dictionary<Vector3Int, int>(); var id = new int[verts.Length];
                for (int i = 0; i < verts.Length; i++)
                {
                    var k = Vector3Int.RoundToInt(verts[i] * 10000f);
                    if (!key.TryGetValue(k, out id[i])) { id[i] = key.Count; key[k] = id[i]; }
                }
                var parent = Enumerable.Range(0, key.Count).ToArray();
                int Find(int a) { while (parent[a] != a) a = parent[a] = parent[parent[a]]; return a; }
                for (int t = 0; t < tris.Length; t += 3) { int a = Find(id[tris[t]]); parent[Find(id[tris[t + 1]])] = a; parent[Find(id[tris[t + 2]])] = Find(a); }
                var groups = new Dictionary<int, (Bounds b, int tris)>();
                var l2w = mf.transform.localToWorldMatrix;
                for (int t = 0; t < tris.Length; t += 3)
                {
                    int g = Find(id[tris[t]]);
                    var bb = new Bounds(l2w.MultiplyPoint3x4(verts[tris[t]]), Vector3.zero);
                    bb.Encapsulate(l2w.MultiplyPoint3x4(verts[tris[t + 1]])); bb.Encapsulate(l2w.MultiplyPoint3x4(verts[tris[t + 2]]));
                    if (groups.TryGetValue(g, out var e)) { e.b.Encapsulate(bb); groups[g] = (e.b, e.tris + 1); } else groups[g] = (bb, 1);
                }
                L($"{TPath(mf.transform, go.transform)}  whole c {V(rb.center)} s {V(rb.size)}  islands {groups.Count}  mats {string.Join("|", r.sharedMaterials.Select(m => m ? m.name : "null"))}");
                foreach (var kv in groups.OrderBy(k => k.Value.b.center.x))
                {
                    var b = kv.Value.b;
                    if (kv.Value.tris < 12 || b.size.magnitude > 0.8f || b.center.z < BhZMin || b.center.z > BhZMax) continue;
                    var col = Color.HSVToRGB((n * 0.61803f) % 1f, 0.95f, 1f);
                    L($"   #{n,-3} {ColorUtility.ToHtmlStringRGB(col)} island c {V(b.center)} s {V(b.size)} tris {kv.Value.tris}");
                    boxes.Add((b, col));
                    n++;
                }
            }

            var sun = new GameObject("sun").AddComponent<Light>(); sun.type = LightType.Directional; sun.intensity = 1.0f; sun.transform.rotation = Quaternion.Euler(20, 10, 0);
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat; RenderSettings.ambientLight = new Color(0.55f, 0.55f, 0.55f);
            var cam = new GameObject("cam").AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = Color.black;
            cam.orthographic = true; cam.orthographicSize = 1.1f;
            cam.transform.SetPositionAndRotation(new Vector3(0, BhY0 + 1.1f, CamZ), Quaternion.identity);
            cam.nearClipPlane = (BhZMin - 0.02f) - CamZ; cam.farClipPlane = (BhZMax + 0.4f) - CamZ;   // only the backhead slab
            const int W = 1200, H = 1100; const float ppm = 500f;
            var rt = new RenderTexture(W, H, 24);
            cam.targetTexture = rt; cam.Render(); RenderTexture.active = rt;
            var tex = new Texture2D(W, H, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, W, H), 0, 0);
            RenderTexture.active = null; cam.targetTexture = null;
            int PX(float x) => Mathf.RoundToInt((x + 1.2f) * ppm);
            int PY(float y) => Mathf.RoundToInt((y - BhY0) * ppm);
            File.WriteAllBytes(Path.Combine(outDir, "backhead_front_plain.png"), tex.EncodeToPNG());
            for (int k = -12; k <= 12; k++)
            {
                var c = k == 0 ? Color.magenta : k % 5 == 0 ? Color.yellow : new Color(0, 0.8f, 0.8f);
                int px = PX(k * 0.1f);
                for (int y = 0; y < H; y += (k % 5 == 0 ? 1 : 2)) if (px >= 0 && px < W) tex.SetPixel(px, y, c);
            }
            for (int k = 16; k <= 38; k++)
            {
                var c = k % 5 == 0 ? Color.yellow : new Color(0, 0.8f, 0.8f);
                int py = PY(k * 0.1f);
                for (int x = 0; x < W; x += (k % 5 == 0 ? 1 : 2)) if (py >= 0 && py < H) tex.SetPixel(x, py, c);
            }
            tex.Apply();
            File.WriteAllBytes(Path.Combine(outDir, "backhead_front_grid.png"), tex.EncodeToPNG());
            foreach (var (b, c) in boxes)
            {
                int x0 = PX(b.min.x), x1 = PX(b.max.x), y0 = PY(b.min.y), y1 = PY(b.max.y);
                for (int x = x0; x <= x1; x++) { tex.SetPixel(x, y0, c); tex.SetPixel(x, y1, c); }
                for (int y = y0; y <= y1; y++) { tex.SetPixel(x0, y, c); tex.SetPixel(x1, y, c); }
            }
            tex.Apply();
            File.WriteAllBytes(Path.Combine(outDir, "backhead_front_islands.png"), tex.EncodeToPNG());
            L($"render backhead_front_*.png: x -1.2..1.2, y {BhY0}..{BhY0 + 2.2f}, 500 px/m, grid 0.1 m (yellow every 0.5 m, magenta x=0)");

            S("Backhead depth (first hit z along +z from z=-5.5, 5 cm grid; '.' = no hit within 2.8 m)");
            var tmp = new List<MeshCollider>();
            foreach (var mf in go.GetComponentsInChildren<MeshFilter>(true))
                if (mf.sharedMesh && mf.GetComponent<Renderer>() && !mf.GetComponent<Collider>()) tmp.Add(mf.gameObject.AddComponent<MeshCollider>());
            Physics.SyncTransforms();
            var sb = new StringBuilder("   y\\x ");
            for (float x = -1.15f; x <= 1.151f; x += 0.05f) sb.Append($"{x,6:F2}");
            L(sb.ToString());
            for (float y = 3.75f; y >= BhY0; y -= 0.05f)
            {
                sb.Clear().Append($"{y,6:F2} ");
                for (float x = -1.15f; x <= 1.151f; x += 0.05f)
                {
                    var hits = Physics.RaycastAll(new Vector3(x, y, -5.5f), Vector3.forward, 2.8f);
                    sb.Append(hits.Length == 0 ? "     ." : $"{hits.Min(h => h.point.z),6:F2}");
                }
                L(sb.ToString());
            }
            foreach (var c in tmp) Object.DestroyImmediate(c);
        }
        catch (Exception e) { L("EXCEPTION " + e); }
        File.WriteAllText(Path.Combine(outDir, "backhead_report.txt"), R.ToString());
        if (!chain) EditorApplication.Exit(0);
    }

    // Wheel profile: radius of every vertex about the axle (world x through the wheelset pivot) for the driver/pilot meshes,
    // as a histogram near the rim, to find tread vs flange radius and the model's rail height (pivot y - tread radius).
    public static void Wheels()
    {
        outDir = Environment.GetEnvironmentVariable("RLW_PROBE_OUT") ?? Path.GetFullPath("ProbeOut");
        Directory.CreateDirectory(outDir);
        try
        {
            C21Source.EnsureFlat();
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var go = Inst(Prefabs[0]);
            foreach (var (pivot, mesh) in new[] {
                ("Main/Driver1", "Main/Driver1/Cube.002"),
                ("Main/Driver2", "Main/Driver2/Cube.001"),
                ("Main/Driver3", "Main/Driver3/Cube.016"),
                ("PilotTruck/Pilot", "PilotTruck/Pilot/Cylinder.005") })
            {
                var p = go.transform.Find(pivot).position;
                var mf = go.transform.Find(mesh).GetComponent<MeshFilter>();
                var l2w = mf.transform.localToWorldMatrix;
                var rs = mf.sharedMesh.vertices.Select(v => l2w.MultiplyPoint3x4(v)).Select(w => (r: new Vector2(w.y - p.y, w.z - p.z).magnitude, x: Mathf.Abs(w.x))).ToList();
                float max = rs.Max(v => v.r);
                S($"{mesh}: pivot y {p.y:F4}, max radius {max:F4} (lowest point y {p.y - max:F4})");
                foreach (var g in rs.Where(v => v.r > max - 0.06f).GroupBy(v => Mathf.Round(v.r * 200f) / 200f).OrderByDescending(g => g.Key))
                    L($"   r {g.Key:F3}: {g.Count(),5} verts, |x| {g.Min(v => v.x):F3}..{g.Max(v => v.x):F3}");
            }
        }
        catch (Exception e) { L("EXCEPTION " + e); }
        File.WriteAllText(Path.Combine(outDir, "wheels_report.txt"), R.ToString());
        if (!chain) EditorApplication.Exit(0);
    }


    // Cab floor: every surface a vertical ray meets at a few x positions (RR walkable collider hull and the visual meshes)
    public static void Floor()
    {
        outDir = Environment.GetEnvironmentVariable("RLW_PROBE_OUT") ?? Path.GetFullPath("ProbeOut");
        Directory.CreateDirectory(outDir);
        try
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var go = Inst(Prefabs[0]);
            var tmp = new List<MeshCollider>();
            foreach (var mf in go.GetComponentsInChildren<MeshFilter>(true))
                if (mf.sharedMesh && mf.GetComponent<Renderer>() && !mf.GetComponent<Collider>()) tmp.Add(mf.gameObject.AddComponent<MeshCollider>());
            Physics.SyncTransforms();
            S("Floor: downward rays from y 3.5 (hits listed top to bottom; H = RR collider hull, V = visual mesh)");
            foreach (float z in new[] { -2.6f, -3.0f, -3.4f, -3.6f, -3.8f, -3.95f, -4.3f })
                foreach (float x in new[] { -1.0f, -0.5f, 0f, 0.5f, 1.0f })
                {
                    var hits = Physics.RaycastAll(new Vector3(x, 3.5f, z), Vector3.down, 4f).OrderBy(h => -h.point.y).ToList();
                    L($"  x {x,5:F2} z {z,5:F2}: " + string.Join("  ", hits.Select(h => $"{h.point.y:F3}{(tmp.Contains(h.collider as MeshCollider) ? "V" : "H")}:{h.collider.name}")));
                }
        }
        catch (Exception e) { L("EXCEPTION " + e); }
        File.WriteAllText(Path.Combine(outDir, "floor_report.txt"), R.ToString());
        if (!chain) EditorApplication.Exit(0);
    }

    // Review probe: coupling faces (rays along z), running-board edge (rays down), tender wheel profile. Visual meshes only
    // (each renderer gets a child MeshCollider of its own mesh; the RR hull colliders are disabled).
    public static void Faces()
    {
        outDir = Environment.GetEnvironmentVariable("RLW_PROBE_OUT") ?? Path.GetFullPath("ProbeOut");
        Directory.CreateDirectory(outDir);
        try
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            foreach (var pf in new[] { Prefabs[0], Prefabs[1] })
            {
                var go = Inst(pf);
                if (pf == Prefabs[0])
                    foreach (var part in new[] { "Assets/LLWParts/c21parts/parts 1/headlight1.prefab", "Assets/LLWParts/c21parts/parts 1/handrail1.prefab" })
                    { var p = Inst(part); p.transform.SetParent(go.transform, true); }
                foreach (var c in go.GetComponentsInChildren<Collider>(true)) c.enabled = false;
                foreach (var mf in go.GetComponentsInChildren<MeshFilter>(true))
                {
                    if (!mf.sharedMesh || !mf.GetComponent<Renderer>()) continue;
                    var g = new GameObject("vc"); g.transform.SetParent(mf.transform, false);
                    g.AddComponent<MeshCollider>().sharedMesh = mf.sharedMesh;
                }
                Physics.SyncTransforms();
                string Hit(Vector3 o, Vector3 d, float dist)
                {
                    var hs = Physics.RaycastAll(o, d, dist).Where(h => h.collider.enabled).OrderBy(h => h.distance).ToList();
                    return hs.Count == 0 ? "   .  " : $"{(Mathf.Abs(d.z) > 0.5f ? hs[0].point.z : hs[0].point.y),6:F3}:{hs[0].collider.transform.parent.name}";
                }
                S($"{pf}: first surface from the front (ray -z from z 9) and from the rear (ray +z from z -9)");
                foreach (float y in new[] { 0.5f, 0.7f, 0.9f, 1.0f, 1.1f, 1.2f, 1.4f, 1.7f, 2.0f, 2.5f, 3.0f })
                    L($"  y {y:F2}  front: " + string.Join(" ", new[] { -1.0f, -0.5f, 0f, 0.5f, 1.0f }.Select(x => $"x{x:+0.0;-0.0} " + Hit(new Vector3(x, y, 9f), Vector3.back, 18f)))
                      + "  | rear: " + string.Join(" ", new[] { -1.0f, 0f, 1.0f }.Select(x => $"x{x:+0.0;-0.0} " + Hit(new Vector3(x, y, -9f), Vector3.forward, 18f))));
                if (pf == Prefabs[0])
                {
                    S("running board: first surface down from y 4 at the driver axles");
                    foreach (float z in new[] { 2.051f, 0.6f, 0.45f, 0.3f, 0f, -1.0f, -1.6f, -1.8f, -1.95f, -2.064f })
                        L($"  z {z,6:F3}: " + string.Join(" ", new[] { -1.6f, -1.5f, -1.4f, -1.3f, -1.2f, 1.2f, 1.3f, 1.4f, 1.5f, 1.6f }.Select(x => $"x{x:+0.0;-0.0} " + Hit(new Vector3(x, 4f, z), Vector3.down, 4.2f))));
                }
                Object.DestroyImmediate(go);
            }
            // Fox truck wheel: radius histogram about the axle
            var tr = Inst(Prefabs[2]);
            var w = tr.transform.Find("V2-s/Wheel1");
            var wm = w.GetComponentInChildren<MeshFilter>();
            var l2w = wm.transform.localToWorldMatrix; var pv = w.position;
            var rs = wm.sharedMesh.vertices.Select(v => l2w.MultiplyPoint3x4(v)).Select(q => (r: new Vector2(q.y - pv.y, q.z - pv.z).magnitude, x: Mathf.Abs(q.x))).ToList();
            float max = rs.Max(v => v.r);
            S($"Fox truck Wheel1: pivot y {pv.y:F4}, max radius {max:F4}");
            foreach (var g in rs.Where(v => v.r > max - 0.06f).GroupBy(v => Mathf.Round(v.r * 200f) / 200f).OrderByDescending(g => g.Key))
                L($"   r {g.Key:F3}: {g.Count(),5} verts, |x| {g.Min(v => v.x):F3}..{g.Max(v => v.x):F3}");
        }
        catch (Exception e) { L("EXCEPTION " + e); }
        File.WriteAllText(Path.Combine(outDir, "faces_report.txt"), R.ToString());
        if (!chain) EditorApplication.Exit(0);
    }
    static GameObject Inst(string path) => (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(path));

    // every renderer (world bounds, materials) and collider, sorted front to rear; top-level children marked
    static void Parts(string prefab)
    {
        S("Parts of " + prefab);
        var go = Inst(prefab);
        var rs = go.GetComponentsInChildren<Renderer>(true);
        var all = Bounds(rs);
        L($"renderers {rs.Length}, bounds c {V(all.center)} s {V(all.size)} min {V(all.min)} max {V(all.max)}");
        var sb = new StringBuilder();
        foreach (var r in rs.OrderByDescending(r => r.bounds.center.z))
        {
            var b = r.bounds;
            var mf = r.GetComponent<MeshFilter>();
            sb.AppendLine($"{TPath(r.transform, go.transform),-44} c {V(b.center)} s {V(b.size)} tris {(mf && mf.sharedMesh ? mf.sharedMesh.triangles.Length / 3 : 0),6} mats {string.Join("|", r.sharedMaterials.Select(m => m ? m.name : "null"))}{(r.enabled ? "" : " [OFF]")}{(r.gameObject.activeInHierarchy ? "" : " [INACTIVE]")}");
        }
        string pn = Path.GetFileNameWithoutExtension(prefab);
        File.WriteAllText(Path.Combine(outDir, $"parts_{pn}.txt"), sb.ToString());
        L($"  -> parts_{pn}.txt");
        foreach (var c in go.GetComponentsInChildren<Collider>(true))
            L($"  collider {c.GetType().Name,-14} {TPath(c.transform, go.transform),-36} c {V(c.bounds.center)} s {V(c.bounds.size)}{(c is MeshCollider mc && mc.sharedMesh ? $" tris {mc.sharedMesh.triangles.Length / 3}" : "")}");
        // anchors: every childless transform without a renderer (RR component parents), plus the unit masters
        foreach (var t in go.GetComponentsInChildren<Transform>(true))
        {
            var r = t.GetComponent<Renderer>();
            bool anchor = t.childCount == 0 && (!r || !r.enabled || (t.GetComponent<MeshFilter>() is MeshFilter mf0 && mf0 && mf0.sharedMesh && mf0.sharedMesh.name == "Cube"));
            if (anchor && !t.name.StartsWith("Bone") && !t.name.EndsWith("_end")) L($"  anchor {TPath(t, go.transform),-60} pos {V(t.position)} fwd {V(t.forward)} up {V(t.up)}");
            else if (t.parent == go.transform) L($"  top-level {t.name,-30} pos {V(t.position)} rot {V(t.eulerAngles)} scale {V(t.lossyScale)} children {t.childCount}");
        }
        Object.DestroyImmediate(go);
    }

    // For each clip: the prefab it binds to, top-level objects moved, and each animated transform's t=0 -> t=end motion.
    static void Clips()
    {
        S("Clips");
        var clips = AssetDatabase.FindAssets("t:AnimationClip", new[] { "Assets/AnimationClip" })
            .Select(g => AssetDatabase.LoadAssetAtPath<AnimationClip>(AssetDatabase.GUIDToAssetPath(g))).OrderBy(c => c.name).ToList();
        foreach (var c in clips)
        {
            var paths = AnimationUtility.GetCurveBindings(c).Select(b => b.path).Distinct().ToList();
            GameObject go = null; string host = null;
            foreach (var p in Prefabs)
            {
                var g = Inst(p);
                if (paths.All(x => g.transform.Find(x))) { go = g; host = p; break; }
                Object.DestroyImmediate(g);
            }
            L($"\n-- clip '{c.name}' length {c.length:F3}s, {paths.Count} paths, host {host ?? "NONE (paths not all found)"}");
            if (!go) continue;
            var tops = paths.Select(p => p.Split('/')[0]).Distinct().ToList();
            L($"   top-level objects: {string.Join(", ", tops)}");
            foreach (var p in paths)
            {
                var t = go.transform.Find(p);
                c.SampleAnimation(go, 0f);
                Vector3 p0 = t.position; var q0 = t.rotation;
                c.SampleAnimation(go, c.length);
                Vector3 p1 = t.position; var q1 = t.rotation;
                (q1 * Quaternion.Inverse(q0)).ToAngleAxis(out float ang, out Vector3 axis);
                if (ang > 180) { ang = 360 - ang; axis = -axis; }
                // total signed turn about world x, unwrapped over 120 steps (wheels)
                float total = 0; var prev = q0;
                for (int i = 1; i <= 120; i++)
                {
                    c.SampleAnimation(go, c.length * i / 120f);
                    (Quaternion.Inverse(prev) * t.rotation).ToAngleAxis(out float a, out Vector3 ax);
                    if (a > 180) { a = 360 - a; ax = -ax; }
                    total += a * Vector3.Dot(prev * ax, Vector3.right);
                    prev = t.rotation;
                }
                var r = t.GetComponent<Renderer>();
                L($"   {p,-44} pos0 {V(p0)} d {V(p1 - p0)} rot {ang:F1} about {V(axis)} turnX {total:F0}{(r ? $" bounds c {V(r.bounds.center)} s {V(r.bounds.size)}" : "")}");
            }
            c.SampleAnimation(go, 0f);
            Object.DestroyImmediate(go);
        }
    }

    static void Renders()
    {
        S("Renders");
        var cache = new Dictionary<Material, Material>();
        void Prev(GameObject g) { foreach (var r in g.GetComponentsInChildren<Renderer>(true)) r.sharedMaterials = r.sharedMaterials.Select(m => m == null ? null : cache.TryGetValue(m, out var s) ? s : (cache[m] = Preview(m))).ToArray(); }
        var sun = new GameObject("sun").AddComponent<Light>();
        sun.type = LightType.Directional; sun.intensity = 1.1f; sun.transform.rotation = Quaternion.Euler(40, 120, 0);
        RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
        RenderSettings.ambientLight = new Color(0.5f, 0.5f, 0.55f);
        var cam = new GameObject("cam").AddComponent<Camera>();
        cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(0.72f, 0.78f, 0.85f); cam.fieldOfView = 35; cam.nearClipPlane = 0.03f;

        // loco: RR positionHead 5.35 / Tail -3.319, cab at the rear (seats z -3.55)
        var loco = Inst(Prefabs[0]); Prev(loco);
        var lb = Bounds(loco.GetComponentsInChildren<Renderer>());
        L($"loco bounds c {V(lb.center)} s {V(lb.size)} min {V(lb.min)} max {V(lb.max)}");
        Shot(cam, new Vector3(-24, 2.2f, 1f), new Vector3(0, 2.0f, 1f), "raw_loco_left.png");
        Shot(cam, new Vector3(24, 2.2f, 1f), new Vector3(0, 2.0f, 1f), "raw_loco_right.png");
        Shot(cam, new Vector3(10, 4.5f, 16), new Vector3(0, 1.9f, 2f), "raw_loco_front34.png");
        Shot(cam, new Vector3(-10, 5f, -16), new Vector3(0, 1.9f, -1f), "raw_loco_rear34.png");
        Shot(cam, new Vector3(-8, 1.0f, 2.0f), new Vector3(0, 0.8f, 2.0f), "raw_loco_gear_front_left.png");
        Shot(cam, new Vector3(-8, 1.0f, -1.5f), new Vector3(0, 0.8f, -1.5f), "raw_loco_gear_rear_left.png");
        var top = new GameObject("topcam").AddComponent<Camera>();
        top.CopyFrom(cam); top.orthographic = true; top.orthographicSize = 6.5f;
        Shot(top, new Vector3(0, 20, 1), new Vector3(0, 0, 1.001f), "raw_loco_top.png");
        top.transform.SetPositionAndRotation(new Vector3(-20, 2.2f, 1), Quaternion.Euler(0, 90, 0)); top.orthographicSize = 4.5f;
        ShotAs(top, "raw_loco_side_ortho.png");
        Object.DestroyImmediate(top.gameObject);
        var cabLight = new GameObject("cab light").AddComponent<Light>();
        cabLight.type = LightType.Point; cabLight.range = 6f; cabLight.intensity = 1.5f; cabLight.transform.position = new Vector3(0, 3.3f, -3.0f);
        cam.fieldOfView = 60;
        Shot(cam, new Vector3(0, 3.0f, -4.6f), new Vector3(0, 2.8f, -2.5f), "raw_cab_look_fwd.png");
        Shot(cam, new Vector3(0, 3.0f, -2.2f), new Vector3(0, 2.8f, -5.0f), "raw_cab_look_back.png");
        Shot(cam, new Vector3(0, 6.5f, -3.0f), new Vector3(0, 2.0f, -3.0f), "raw_cab_from_above.png");
        Shot(cam, new Vector3(-0.4f, 3.0f, -4.4f), new Vector3(1.3f, 2.8f, -3.0f), "raw_cab_right.png");
        Shot(cam, new Vector3(0.4f, 3.0f, -4.4f), new Vector3(-1.3f, 2.8f, -3.0f), "raw_cab_left.png");
        cam.fieldOfView = 35;
        Object.DestroyImmediate(cabLight.gameObject);

        // tender alone (Fox trucks at +-truckSeparation/2 = 1.95), then coupled behind the loco
        var tender = Inst(Prefabs[1]); Prev(tender);
        foreach (var z in new[] { 1.95f, -1.95f })
        {
            var tr = Inst(Prefabs[2]); Prev(tr);
            tr.transform.SetParent(tender.transform, false); tr.transform.localPosition = new Vector3(0, 0, z);
        }
        var tb = Bounds(tender.GetComponentsInChildren<Renderer>());
        L($"tender bounds c {V(tb.center)} s {V(tb.size)} min {V(tb.min)} max {V(tb.max)}");
        loco.SetActive(false);
        Shot(cam, new Vector3(-16, 2.2f, tb.center.z), new Vector3(0, 1.6f, tb.center.z), "raw_tender_left.png");
        Shot(cam, new Vector3(8, 4.5f, tb.max.z + 10), new Vector3(0, 1.6f, tb.center.z), "raw_tender_front34.png");
        Shot(cam, new Vector3(-7, 4.5f, tb.min.z - 10), new Vector3(0, 1.6f, tb.center.z), "raw_tender_rear34.png");
        Shot(cam, new Vector3(-6, 0.8f, tb.center.z), new Vector3(0, 0.5f, tb.center.z), "raw_tender_wheels_left.png");
        loco.SetActive(true);
        float tz = -3.319f - 0.7f - 3.875f;
        tender.transform.position = new Vector3(0, 0, tz);
        L($"coupled preview: tender origin at z {tz:F3}");
        Shot(cam, new Vector3(-30, 2.6f, -3f), new Vector3(0, 2.0f, -3f), "raw_coupled_left.png");
        Shot(cam, new Vector3(-4, 5f, -9f), new Vector3(0, 2.0f, -4.5f), "raw_coupled_drawbar.png");
        var ct = new GameObject("coupledtop").AddComponent<Camera>();
        ct.CopyFrom(cam); ct.orthographic = true; ct.orthographicSize = 3.5f;
        Shot(ct, new Vector3(0, 20, -4.5f), new Vector3(0, 0, -4.501f), "raw_coupled_top.png");
        ct.transform.SetPositionAndRotation(new Vector3(-20, 2.5f, -4.5f), Quaternion.Euler(0, 90, 0)); ct.orthographicSize = 3.5f;
        ShotAs(ct, "raw_coupled_side_ortho.png");
        Object.DestroyImmediate(ct.gameObject);        Object.DestroyImmediate(loco); Object.DestroyImmediate(tender);
    }

    static void ShotAs(Camera cam, string file)
    {
        var rt = new RenderTexture(1600, 900, 24);
        cam.targetTexture = rt; cam.Render(); RenderTexture.active = rt;
        var tex = new Texture2D(1600, 900, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, 1600, 900), 0, 0);
        File.WriteAllBytes(Path.Combine(outDir, file), tex.EncodeToPNG());
        RenderTexture.active = null; cam.targetTexture = null;
        Object.DestroyImmediate(rt); Object.DestroyImmediate(tex);
        L("render " + file);
    }

    static Material Preview(Material src)
    {
        bool rr = src.shader.name.StartsWith("Railroader");
        var m = new Material(Shader.Find("Standard (Specular setup)"));
        if (rr)
        {
            m.SetTexture("_MainTex", src.GetTexture("_MainTex"));
            m.SetTexture("_SpecGlossMap", src.GetTexture("_SpecGlossMap"));
            m.SetTexture("_BumpMap", src.GetTexture("_BumpMap"));
            m.SetTexture("_OcclusionMap", src.GetTexture("_OcclusionMap"));
            m.SetFloat("_GlossMapScale", src.GetFloat("_Smoothness"));
            m.EnableKeyword("_SPECGLOSSMAP"); m.EnableKeyword("_NORMALMAP");
        }
        else if (src.HasProperty("_BaseColor")) m.color = src.GetColor("_BaseColor");
        return m;
    }

    static void Shot(Camera cam, Vector3 pos, Vector3 look, string file)
    {
        cam.transform.position = pos; cam.transform.LookAt(look);
        var rt = new RenderTexture(1600, 900, 24);
        cam.targetTexture = rt; cam.Render(); RenderTexture.active = rt;
        var tex = new Texture2D(1600, 900, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, 1600, 900), 0, 0);
        File.WriteAllBytes(Path.Combine(outDir, file), tex.EncodeToPNG());
        RenderTexture.active = null; cam.targetTexture = null;
        Object.DestroyImmediate(rt); Object.DestroyImmediate(tex);
        L("render " + file);
    }

    static Bounds Bounds(IEnumerable<Renderer> rs)
    {
        var l = rs.Where(r => r.enabled).ToList();
        if (l.Count == 0) return new Bounds();
        var b = l[0].bounds;
        foreach (var r in l) b.Encapsulate(r.bounds);
        return b;
    }

    static string TPath(Transform t, Transform root) => t == root ? "" : (t.parent == root ? t.name : TPath(t.parent, root) + "/" + t.name);
    static string V(Vector3 v) => $"({v.x:F3}, {v.y:F3}, {v.z:F3})";
    static void S(string s) => L($"\n==== {s}");
    static void L(string s) { R.AppendLine(s); Debug.Log("[C21Probe] " + s); }
}







