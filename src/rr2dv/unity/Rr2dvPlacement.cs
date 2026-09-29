using System;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

// App-owned orchestration around the pinned builder snapshot. Keep its build, validation and export order;
// seat generated fittings before rendering/export, and before making the interior LOD copy.
// The core's app-maintained changes are documented in tooling/NOTES.md. No vehicle IDs or model-specific offsets belong here.
public static partial class CclLocoBuild
{
    public static void RunRr2dvRecord()
    {
        try
        {
            var cfg = LlwVehicleRecord.Load(Environment.GetEnvironmentVariable("CCL_VEHICLE_RECORD"));
            LoadRrReview();
            LlwVehicleRecord.PrepareSources(cfg);
            // rr2dv always exports stock DV audio; custom source audio is never shipped.
            foreach (var car in Cars(cfg)) { car.Sounds.Clear(); car.RemoveVanillaSounds = new string[0]; }
            RunRr2dv(cfg);
        }
        catch (Exception e)
        {
            Debug.LogException(e);
            var output = Environment.GetEnvironmentVariable("CCL_BUILD_OUT");
            Directory.CreateDirectory(output);
            File.WriteAllText(Path.Combine(output, "build_report.txt"), "Vehicle record validation failed\n" + e);
            File.WriteAllText(Path.Combine(output, "result.json"), "{\"exported\":false,\"runtimeValidated\":false,\"recordValidationFailed\":true}");
            EditorApplication.Exit(1);
        }
    }
    static void RunRr2dv(LocoConfig cfg)
    {
        int exitCode = 0;
        Loco = Cfg = cfg;
        Report.Clear(); warnings = 0; ownMats.Clear(); refBody = null; builtFolders.Clear(); meshIslandSources.Clear();
        Line($"CclLocoBuild: {CarName} ({CarId}) v{Cfg.Version}{(cfg.Tender != null ? $" + tender {cfg.Tender.CarName} ({cfg.Tender.CarId})" : "")}");
        outDir = Environment.GetEnvironmentVariable("CCL_BUILD_OUT") ?? Environment.GetEnvironmentVariable("RLW_BUILD_OUT") ?? Path.GetFullPath("BuildOut");
        Directory.CreateDirectory(outDir);
        try
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            foreach (var c in Cars(cfg)) if (AssetDatabase.IsValidFolder(c.Work)) AssetDatabase.DeleteAsset(c.Work);
            foreach (var c in Cars(cfg)) { Folder(c.Work); Folder(c.Work + "/Generated"); }
            Section("Source placement validation");
            foreach (var line in RRPlacementValidation.Validate(cfg)) Line(line);
            BuildOwnAssets();
            foreach (var c in Cars(cfg)) BuildRr2dvCar(c);
            if (cfg.Tender != null) LinkTender(cfg, cfg.Tender);
            ConfigureRrReview();
            Cfg = cfg; refBody = null; carFolder = builtFolders[cfg];
            EditorSceneManager.SaveOpenScenes();
            AssetDatabase.SaveAssets();
            RenderCheck();
            if (Environment.GetEnvironmentVariable("CCL_NEW_LOCO") == "1")
                NewLocoBuildGate.ValidateAndWrite(cfg, outDir);
            Export();
        }
        catch (Exception e)
        {
            exitCode = 1;
            Line("EXCEPTION " + (e is TargetInvocationException tie && tie.InnerException != null ? tie.InnerException : e));
        }
        Line($"\nwarnings: {warnings}");
        File.WriteAllText(Path.Combine(outDir, "build_report.txt"), Report.ToString());
        File.WriteAllText(Path.Combine(outDir, "result.json"), "{\"exported\":" + (exitCode == 0 ? "true" : "false") + ",\"warnings\":" + warnings + ",\"runtimeValidated\":false}");
        EditorApplication.Exit(exitCode);
    }

    static void BuildRr2dvCar(LocoConfig c)
    {
        Cfg = c; refBody = null; carFolder = null;
        validatedClips.Clear();
        Section($"######## CAR {c.CarName} ({c.CarId}){(c.IsTender ? " - tender" : "")}");
        if (c.RodOilers != null && c.OilAnchors != null) throw new InvalidOperationException("Select RodOilers OR OilAnchors, not both");
        if (c.OilAnchors != null && c.OilPoints == null) c.OilPoints = root => c.OilAnchors.Select(a => (a.Tag, a.CarPosition));
        if (c.RodOilers != null) c.OilPoints = root => RodOilerPoints(root, c.RodOilers).Select(p => (p.tag, root.InverseTransformPoint(p.world)));
        PrepareClips();
        PrepareRr2dvInteractions();
        matMap = BuildMaterials(Livery);
        FinishRr2dvMaterials();
        PrepareRr2dvGrips();
        FitRr2dvCoalLoad();
        CreateCar();
        try { BuildExterior(); }
        catch (InvalidOperationException e)
        {
            if (e.Message.Contains("end beam")) SurveyRr2dvEndBeams();
            throw;
        }
        if (c.IsTender) ShapeRr2dvCoalLoad();
        FinishRr2dvMaterialSlots();
        if (!c.IsTender) AimRr2dvJets();
        StripRr2dvModelLights();
        PassRr2dvGrabRays();
        if (!c.IsTender && Rr2dvNoDynamo) StripRr2dvDynamoHud();
        if (!c.IsTender) CloseRr2dvWhistle();
        SeatRr2dvOilCups();
        AlignRr2dvBogieSupports();
        SeatRr2dvPlates();
        AlignRr2dvDefaultPlates();
        if (!c.IsTender)
        {
            StripRr2dvSourceColliders();
            BuildInterior(); SeatRr2dvControls(); FinishRr2dvInteriorControls(); BuildInteriorLOD();
            FreshRr2dvSource();
        }
        Rr2dvReleaseSeat();
        BuildInteractables();
        BuildRr2dvAncillaries();
        var sound = c.IsTender ? null : BuildSound();
        ConfigureAssets(sound);
        builtFolders[c] = carFolder;
    }


    // The core finds the backhead with temporary colliders on the visible meshes, but skips a mesh that already has a
    // collider and then hits that one instead: a single-mesh model whose own RR collider has no backhead face (Reading
    // B8a camelback, 2026-09-28: all 20 generated controls "no backhead found"). The cab is measured on the visible model
    // only; the walkable colliders were already taken in BuildExterior, and later stages get a fresh source copy.
    // No dynamo (pre-build review): the lamps, cab light and their backhead controls are not built (record), and the HUD
    // loses its dynamo and headlight controls here; the dynamo sim stays unpowered at 0, so it makes no steam jet.
    static bool Rr2dvNoDynamo => Environment.GetEnvironmentVariable("RR2DV_NO_DYNAMO") == "1";

    static void StripRr2dvDynamoHud()
    {
        string path = $"{carFolder}/{CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            int removed = 0;
            foreach (var name in new[] { "dynamoControl", "headlightDecoder" })
            {
                var sim = root.transform.Find("[sim]/" + name);
                if (!sim) continue;
                foreach (var control in sim.GetComponents<Component>().Where(k => k && k.GetType().Name == "OverridableControlProxy").ToArray())
                {
                    Object.DestroyImmediate(control); removed++;
                }
            }
            Line($"rr2dv no dynamo: {removed} HUD control(s) removed (dynamo, headlights); no lamps, cab light or their controls built");
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    // The core's release fitter searches down to 0.30 m, but its final check needs the valve (position - 0.0806 m) at
    // 0.30 m or more: a low frame at the hint (Reading B8a camelback: rod at y 0.370, 2026-09-28) passes the fitter and
    // stops the build. Try the fitter at the hint, then along the frame in 0.4 m steps, and hand the core the first hint
    // whose seat clears the floor; the core then fits it again, with the same result.
    const float Rr2dvReleaseFloor = .3f + .080590f;

    // The fitter also accepts a valve body 0.08 m behind the face (its pMax), but the final check needs 0.10 m from the
    // outermost skin along the rod line (RRPlacementValidation.CheckReleaseClearance): a seat at the fitter's limit stops
    // the build (C&O T1 tender, 2026-09-29: 0.080 m). Such a seat moves inward along the rod to 0.105 m and goes to the core
    // as an exact pose; the core's final checks (handle exposed, bracket, floor) still judge it.
    const float Rr2dvReleaseDepth = .105f;

    static float Rr2dvReleaseSkinDepth(Vector3 pos, Vector3 dir)
    {
        using (var vh = new VisualHits(RefBody))
            return vh.Ray(pos + dir * 1.5f, -dir, 3f, out var hit) ? Vector3.Dot(hit.point - pos, dir) : float.NaN;
    }

    // A generated tender coal load comes from a layout rule ending 0.25 m behind Railroader's car end, but the car end can
    // sit well ahead of the tender's front: the R48's coal showed as a block across the gap into the cab, and the RXM-1's
    // stood on the front deck ahead of its coal doors (James's game tests, 2026-09-29). Two measurements, at 30 % and 60 %
    // of the coal height:
    //  - the front wall: rays from ahead of the tender back along -z (five across the middle of the box); the median first
    //    hit is the coal space's front (sheet, coal board or doors); the coal ends 5 cm behind it;
    //  - failing that, the sides: from the front, the first 0.15 m run of slices with a side sheet within 0.6 m of the box
    //    on both sides (a lone handrail is thinner).
    // A front wall that leaves less than 0.5 m moves the box back behind it, keeping its length.
    static void FitRr2dvCoalLoad()
    {
        var cl = Cfg.CoalLoad;
        if (cl == null || !cl.Pivot.HasValue) return;
        var p = cl.Pivot.Value;
        float half = cl.Footprint.x / 2, length = cl.Footprint.y, rear = p.z - length / 2, front = p.z + length / 2;
        float reach = half + .6f, start = half + 2f;
        float edge = float.NaN, wall = float.NaN;
        var heights = new[] { .3f, .6f }.Select(f => p.y + cl.FullHeight * f).ToArray();
        using (var vh = new VisualHits(RefBody))
        {
            var walls = new System.Collections.Generic.List<float>();
            foreach (float y in heights)
                foreach (float u in new[] { -.5f, -.25f, 0f, .25f, .5f })
                    if (vh.Ray(new Vector3(u * half, y, front + 3f), Vector3.back, 3f + length, out var h) && h.point.z > rear + .3f)
                        walls.Add(h.point.z);
            if (walls.Count >= 5) wall = walls.OrderBy(z => z).ElementAt(walls.Count / 2);
            bool Side(float s, float y, float z) =>
                vh.Ray(new Vector3(s * start, y, z), new Vector3(-s, 0, 0), start, out var h) && Mathf.Abs(h.point.x) <= reach;
            bool Enclosed(float z) => heights.Any(y => Side(1, y, z) && Side(-1, y, z));
            int run = 0;
            for (float z = front; z >= rear + .5f; z -= .05f)
            {
                run = Enclosed(z) ? run + 1 : 0;
                if (run == 3) { edge = z + .1f; break; }
            }
        }
        string how;
        if (!float.IsNaN(wall) && (float.IsNaN(edge) || wall - .05f < edge)) { edge = wall - .05f; how = $"the coal space's front wall at z {wall:F3}"; }
        else how = "the tender sides end there at coal height";
        if (float.IsNaN(edge))
        {
            Warn("rr2dv coal load: no front wall or enclosing sides found at coal height; left as placed (check it in game)");
            return;
        }
        if (edge >= front - .02f) return;
        if (edge - rear < .5f) rear = edge - length;
        cl.Pivot = new Vector3(p.x, p.y, (rear + edge) / 2);
        cl.Footprint = new Vector2(cl.Footprint.x, edge - rear);
        Line($"rr2dv coal load: front {front:F3} -> {edge:F3} ({how}); box {rear:F3}..{edge:F3}, length {edge - rear:F3} m");
    }

    // The generated coal load as a heap, not a block (James, 2026-09-29): the same unit footprint and height as the core's
    // bottom-pivot box (so the coal-amount scaling is unchanged), highest at the back and centre, falling to 20 % at the
    // front wall and 45 % at the sides, with walls down to the floor so no gap shows.
    static void ShapeRr2dvCoalLoad()
    {
        if (Cfg.CoalLoad == null) return;
        string path = $"{carFolder}/{CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            var load = root.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == "[coal load]");
            var mf = load ? load.Find("scaler/coal")?.GetComponent<MeshFilter>() : null;
            if (!mf) return;
            string file = System.Text.RegularExpressions.Regex.Replace($"{CarId}_coal_heap", "[^A-Za-z0-9_.-]", "_");
            var mesh = Rr2dvCoalHeap();
            AssetDatabase.CreateAsset(mesh, AssetDatabase.GenerateUniqueAssetPath($"{carFolder}/{file}.asset"));
            mf.sharedMesh = mesh;
            Line("rr2dv coal load: heap shape (full at the back and centre, 20 % at the front wall, 45 % at the sides)");
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    static Mesh Rr2dvCoalHeap()
    {
        const int n = 12;
        float H(float u, float w) => (1f - .55f * (2 * u - 1) * (2 * u - 1)) * (w < .35f ? 1f : Mathf.Lerp(1f, .2f, (w - .35f) / .65f));
        var v = new System.Collections.Generic.List<Vector3>(); var uv = new System.Collections.Generic.List<Vector2>();
        var t = new System.Collections.Generic.List<int>();
        for (int j = 0; j <= n; j++)
            for (int i = 0; i <= n; i++)
            {
                float u = (float)i / n, w = (float)j / n;   // u across (x), w rear (-z) to front (+z)
                v.Add(new Vector3(u - .5f, H(u, w), w - .5f)); uv.Add(new Vector2(u * 2, w * 2));
            }
        for (int j = 0; j < n; j++)
            for (int i = 0; i < n; i++)
            {
                int a = j * (n + 1) + i, b = a + n + 1;
                t.AddRange(new[] { a, b, b + 1, a, b + 1, a + 1 });
            }
        // skirt: each perimeter segment of the top down to the floor, both faces
        var ring = new System.Collections.Generic.List<Vector3>();
        for (int i = 0; i < n; i++) ring.Add(v[i]);
        for (int j = 0; j < n; j++) ring.Add(v[j * (n + 1) + n]);
        for (int i = n; i > 0; i--) ring.Add(v[n * (n + 1) + i]);
        for (int j = n; j > 0; j--) ring.Add(v[j * (n + 1)]);
        for (int k = 0; k < ring.Count; k++)
        {
            var top0 = ring[k]; var top1 = ring[(k + 1) % ring.Count];
            var bot0 = new Vector3(top0.x, 0, top0.z); var bot1 = new Vector3(top1.x, 0, top1.z);
            foreach (bool outer in new[] { true, false })
            {
                int s = v.Count;
                v.AddRange(new[] { top0, top1, bot1, bot0 });
                uv.AddRange(new[] { new Vector2(0, top0.y), new Vector2(1, top1.y), new Vector2(1, 0), new Vector2(0, 0) });
                t.AddRange(outer ? new[] { s, s + 1, s + 2, s, s + 2, s + 3 } : new[] { s, s + 2, s + 1, s, s + 3, s + 2 });
            }
        }
        var m = new Mesh { name = "rr2dv_coal_heap" };
        m.SetVertices(v); m.SetUVs(0, uv); m.SetTriangles(t, 0);
        m.RecalculateNormals(); m.RecalculateTangents(); m.RecalculateBounds();
        return m;
    }

    // Whistle and dynamo steam jets. CCL's steam template makes 'Whistle' and 'DynamoSteam' unrotated, and its importer
    // puts the vanilla steam system under each with identity rotation (ObjectInstancerProcessor), so it blows along the
    // emitter's +z: forward along the boiler on every converted loco (James's game test, 2026-09-29). The whistle jet goes
    // straight up. The dynamo jet follows its exhaust pipe where the tip can be measured (swept back, to the side or
    // otherwise angled), else straight up (James: always up as the fallback).
    static void AimRr2dvJets()
    {
        string path = $"{carFolder}/{CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            var particles = root.transform.Find("[particles]");
            if (!particles) return;
            foreach (Transform t in particles)
            {
                bool whistle = t.name == "Whistle", dynamo = t.name.Contains("Dynamo");
                if (!whistle && !dynamo) continue;
                var tip = dynamo ? Rr2dvExhaustTip(t.position) : null;
                var dir = tip ?? Vector3.up;
                var now = t.rotation * Vector3.forward;
                t.rotation = Quaternion.FromToRotation(now, dir) * t.rotation;
                Line($"rr2dv steam jet {t.name}: {V(now)} -> {V(dir)} " +
                     (tip.HasValue ? "(along the measured exhaust pipe tip)" : dynamo ? "(straight up: no measurable exhaust pipe tip)" : "(straight up)"));
            }
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    // The exhaust pipe's direction at a jet point: the long axis of the model's vertices within 0.25 m. It counts only when
    // the cloud is pipe-like (long axis variance >= 2.5x the next), the point sits at its end (the tip: at least 3 cm along
    // the axis from the cloud's centre, nothing more than 8 cm beyond it) and the axis does not point down.
    static Vector3? Rr2dvExhaustTip(Vector3 p)
    {
        const float r = .25f;
        var pts = new System.Collections.Generic.List<Vector3>();
        foreach (var mf in RefBody.GetComponentsInChildren<MeshFilter>(false))
        {
            var mr = mf.GetComponent<MeshRenderer>();
            if (!mf.sharedMesh || !mr || !mr.enabled) continue;
            var b = mr.bounds; b.Expand(2 * r);
            if (!b.Contains(p)) continue;
            foreach (var v in mf.sharedMesh.vertices)
            {
                var w = mf.transform.TransformPoint(v);
                if ((w - p).sqrMagnitude <= r * r) pts.Add(w);
            }
        }
        if (pts.Count < 12) return null;
        var c = pts.Aggregate(Vector3.zero, (s, v) => s + v) / pts.Count;
        float xx = 0, xy = 0, xz = 0, yy = 0, yz = 0, zz = 0;
        foreach (var v in pts) { var d = v - c; xx += d.x * d.x; xy += d.x * d.y; xz += d.x * d.z; yy += d.y * d.y; yz += d.y * d.z; zz += d.z * d.z; }
        Vector3 Mul(Vector3 v) => new Vector3(xx * v.x + xy * v.y + xz * v.z, xy * v.x + yy * v.y + yz * v.z, xz * v.x + yz * v.y + zz * v.z);
        Vector3 Power(Vector3 v, Vector3 skip)
        {
            for (int i = 0; i < 50; i++) { v = Mul(v); v -= Vector3.Dot(v, skip) * skip; if (v.sqrMagnitude < 1e-12f) return Vector3.zero; v.Normalize(); }
            return v;
        }
        var a = Power(new Vector3(.3f, .9f, .3f).normalized, Vector3.zero);
        if (a == Vector3.zero) return null;
        var seed = Mathf.Abs(a.y) < .9f ? Vector3.up : Vector3.right;
        var a2 = Power((seed - Vector3.Dot(seed, a) * a).normalized, a);
        float l1 = Vector3.Dot(a, Mul(a)), l2 = a2 == Vector3.zero ? 0f : Vector3.Dot(a2, Mul(a2));
        if (l1 < 2.5f * l2) return null;
        if (Vector3.Dot(p - c, a) < 0) a = -a;
        if (Vector3.Dot(p - c, a) < .03f || pts.Max(v => Vector3.Dot(v - p, a)) > .08f || a.y <= 0f) return null;
        return a;
    }

    // When the core stops on an end beam (ambiguous / insufficient rays / no broad face), the reviewed EndBeamProbeHeight
    // band must come from a measurement, never from what merely passes (resolving-blocks.md; RLW RXM-1B front,
    // 2026-09-29). This survey is that measurement, written to the build report before the error: every upright transverse
    // face seen along the car axis across x -1.0..1.0 m and y 0.20..2.00 m, per 0.2 m band, outermost first, with its depth,
    // ray count, support either side of +-0.3 m (the core wants both), distance from the source car end (the core allows
    // 0.35 m) and part names. It changes nothing; the build still stops.
    static void SurveyRr2dvEndBeams()
    {
        var ci = System.Globalization.CultureInfo.InvariantCulture;
        string N(float v) => v.ToString("0.###", ci);
        string Q(string t) => "\"" + (t ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
        var json = new System.Text.StringBuilder();
        json.Append("{\"schema\":1,\"car\":").Append(Q(CarId)).Append(",\"isTender\":").Append(Cfg.IsTender ? "true" : "false")
            .Append(",\"couplerHeight\":").Append(N(Cfg.CouplerHeight)).Append(",\"ends\":[");
        bool firstEnd = true;
        foreach (int dir in new[] { 1, -1 })
        {
            float? end = dir > 0 ? Cfg.RrEndFront : Cfg.RrEndRear;
            // the ends the core rigs on a measured beam: not a drawbar end (tender front, loco rear with a tender), no buffer
            // or explicit coupling face (CclLocoBuild.BuildExterior couplers)
            bool drawbar = dir > 0 ? Cfg.IsTender && Cfg.RrEndFront.HasValue : Cfg.Tender != null && Cfg.RrEndRear.HasValue;
            bool rigged = !drawbar && (dir > 0 ? Cfg.CouplingFaceFront : Cfg.CouplingFaceRear) == null &&
                          (dir > 0 ? Cfg.BufferFront : Cfg.BufferRear) == null;
            var hits = new System.Collections.Generic.List<(Vector3 p, string part)>();
            var core = new System.Collections.Generic.List<string>();
            using (var vh = new VisualHits(RefBody))
            {
                for (int ix = -10; ix <= 10; ix++)
                    for (int iy = 0; iy <= 36; iy++)
                        if (vh.Ray(new Vector3(ix * .1f, .2f + iy * .05f, dir * 30f), new Vector3(0, 0, -dir), 30f, out var h) &&
                            dir * h.normal.z >= .95f && dir * h.point.z > .5f)
                            hits.Add((h.point, h.collider.transform.parent.name));
                // the core's own default check (CclLocoBuild.EndBeam) per 0.2 m band: x -0.6..0.6 by 0.1, five rows, every hit,
                // the largest 1 cm depth bin within 0.5 m of the outermost hit; it passes with 20 hits and a 20-ray bin
                for (float low = .2f; low <= 1.801f; low += .1f)
                {
                    var ray = new System.Collections.Generic.List<(float x, float z, string part)>();
                    for (int ix = -6; ix <= 6; ix++)
                        for (float y = low; y <= low + .201f; y += .05f)
                            if (vh.Ray(new Vector3(ix * .1f, y, dir * 30f), new Vector3(0, 0, -dir), 30f, out var h))
                                ray.Add((ix * .1f, h.point.z, h.collider.transform.parent.name));
                    if (ray.Count == 0) continue;
                    float outer = ray.Max(r => dir * r.z);
                    var bin = ray.Where(r => outer - dir * r.z <= .5f).GroupBy(r => Mathf.RoundToInt(dir * r.z * 100f))
                        .OrderByDescending(g => g.Count()).First().ToList();
                    core.Add("{\"low\":" + N(low) + ",\"high\":" + N(low + .2f) + ",\"hits\":" + ray.Count + ",\"bin\":" + bin.Count +
                             ",\"beam\":" + N(bin.Average(r => r.z)) + ",\"binLeft\":" + bin.Count(r => r.x <= -.299f) +
                             ",\"binRight\":" + bin.Count(r => r.x >= .299f) + ",\"parts\":[" +
                             string.Join(",", bin.Select(r => Q(r.part)).Distinct().Take(4)) + "]}");
                }
            }
            Line($"rr2dv end-beam survey {(dir > 0 ? "front" : "rear")}: source car end {(end.HasValue ? end.Value.ToString("F3") : "unknown")}, " +
                 $"{hits.Count} upright transverse hits (x -1.0..1.0 m, y 0.20..2.00 m){(rigged ? "" : "; this end is not rigged on a beam")}");
            var faces = new System.Collections.Generic.List<string>();
            for (float low = .2f; low <= 1.801f; low += .1f)
            {
                var band = hits.Where(h => h.p.y >= low - .001f && h.p.y <= low + .201f).OrderByDescending(h => dir * h.p.z).ToList();
                var shown = new System.Collections.Generic.List<string>();
                for (int i = 0; i < band.Count;)
                {
                    float z0 = band[i].p.z;
                    var face = band.Skip(i).TakeWhile(h => Mathf.Abs(h.p.z - z0) <= .015f).ToList();
                    i += face.Count;
                    if (face.Count < 6) continue;
                    float z = face.Average(h => h.p.z);
                    int left = face.Count(h => h.p.x <= -.299f), right = face.Count(h => h.p.x >= .299f);
                    var parts = face.Select(h => h.part).Distinct().Take(3).ToList();
                    faces.Add("{\"low\":" + N(low) + ",\"high\":" + N(low + .2f) + ",\"z\":" + N(z) + ",\"rays\":" + face.Count +
                              ",\"left\":" + left + ",\"right\":" + right + ",\"parts\":[" + string.Join(",", parts.Select(Q)) + "]}");
                    if (shown.Count < 3)
                        shown.Add($"z {z:F3} ({face.Count} rays, {left} left / {right} right of 0.3 m" +
                                  (end.HasValue ? $", {z - end.Value:+0.000;-0.000} m from the source end" : "") + $"; {string.Join(", ", parts)})");
                }
                if (shown.Count > 0) Line($"  band {low:F2}..{low + .2f:F2} m: {string.Join(" | ", shown)}");
            }
            json.Append(firstEnd ? "" : ",").Append("{\"end\":").Append(Q(dir > 0 ? "front" : "rear")).Append(",\"dir\":").Append(dir)
                .Append(",\"rigged\":").Append(rigged ? "true" : "false").Append(",\"sourceEnd\":").Append(end.HasValue ? N(end.Value) : "null")
                .Append(",\"faces\":[").Append(string.Join(",", faces)).Append("],\"core\":[").Append(string.Join(",", core)).Append("]}");
            firstEnd = false;
        }
        json.Append("]}");
        File.WriteAllText(Path.Combine(outDir, "endbeam-survey.json"), json.ToString());
    }

    static void Rr2dvReleaseSeat()
    {
        if (Cfg.BrakeRelease == null || Cfg.BrakeReleaseExact) return;
        var (hint, euler) = Cfg.BrakeRelease(RefBody);
        var probe = new GameObject("rr2dv release probe").transform;
        try
        {
            foreach (int step in new[] { 0, 1, 2, 3, 4, 5, 6, -1, -2 })  // forward first: the hint is at the loco's rear
            {
                var candidate = hint + new Vector3(0, 0, step * .4f);
                int before = warnings;
                PlaceBrakeRelease(probe, candidate);
                bool seated = warnings == before;  // the fitter warns when it finds no seat
                warnings = before;
                if (seated && probe.localPosition.y >= Rr2dvReleaseFloor)
                {
                    var dir = probe.localRotation * Vector3.forward;
                    float depth = Rr2dvReleaseSkinDepth(probe.localPosition, dir);
                    if (!float.IsNaN(depth) && depth < Rr2dvReleaseDepth)
                    {
                        var pos = probe.localPosition - dir * (Rr2dvReleaseDepth - depth);
                        var rot = probe.localEulerAngles;
                        Cfg.BrakeRelease = _ => (pos, rot);
                        Cfg.BrakeReleaseExact = true;
                        Line($"rr2dv brake release: valve body {depth:F3} m behind the skin at z {candidate.z:F3} (the core's check needs 0.10 m); " +
                             $"moved {Rr2dvReleaseDepth - depth:F3} m inward along the rod to {V(pos)}, handed to the core as an exact pose");
                        return;
                    }
                    if (step != 0)
                    {
                        Cfg.BrakeRelease = _ => (candidate, euler);
                        Line($"rr2dv brake release: hint z {hint.z:F3} seats below the clearance floor; moved {step * .4f:+0.0;-0.0} m to z {candidate.z:F3} " +
                             $"(rod y {probe.localPosition.y:F3})");
                    }
                    return;
                }
            }
            Warn("rr2dv brake release: no seat along the frame clears the 0.30 m floor; the core's own check decides");
        }
        finally { Object.DestroyImmediate(probe.gameObject); }
    }

    // The control-grab ray stops at the first collider it meets. The walkable/items copies of the mod's own cab
    // collision meshes are blockier than the model and cover handles you can see (H9: brake cutout, lubricator, cab
    // light, headlights, coal dump, throttle grabbed only at some angles, 2026-09-28). They let the ray pass (CCL's
    // GrabberRaycastPassThrough, as on the cab teleport box); you still stand on and walk into them. Every conversion.
    static void PassRr2dvGrabRays()
    {
        string path = $"{carFolder}/{CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            int n = 0;
            foreach (var group in new[] { "[colliders]/[walkable]", "[colliders]/[items]" })
            {
                var g = root.transform.Find(group);
                if (!g) continue;
                foreach (var col in g.GetComponentsInChildren<Collider>(true))
                    if (!col.GetComponent(T("CCL.Types.Proxies.GrabberRaycastPassThroughProxy")))
                    { Add(col.gameObject, "CCL.Types.Proxies.GrabberRaycastPassThroughProxy"); n++; }
            }
            Line($"rr2dv grab rays pass through {n} walkable/items collider(s) copied from the mod's collision meshes");
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    // Railroader switches its cab and lamp lights from its own scripts, which are not converted, so a Unity Light left in
    // the model is on for good: a bright roof light, sometimes with no bulb (James's game test, 2026-09-29). Every source
    // light goes; the car keeps the builder's own switchable cab light (under the roof centre, on the dynamo fuse) and lamps.
    static int StripRr2dvLights(Transform t)
    {
        var lights = t.GetComponentsInChildren<Light>(true);
        foreach (var light in lights) Object.DestroyImmediate(light);
        return lights.Length;
    }

    static void StripRr2dvModelLights()
    {
        string path = $"{carFolder}/{CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            var model = root.transform.Find("Model");
            int n = model ? StripRr2dvLights(model) : 0;
            if (n > 0) { Line($"rr2dv source lights: {n} Railroader light(s) removed from the model (always on without RR's scripts)"); SaveRr2dvPrefab(root, path); }
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    static void StripRr2dvSourceColliders()
    {
        StripRr2dvLights(RefBody);
        var colliders = RefBody.GetComponentsInChildren<Collider>(true);
        foreach (var collider in colliders) Object.DestroyImmediate(collider);
        if (colliders.Length > 0) Line($"rr2dv cab measured on the visible model: {colliders.Length} source collider(s) set aside");
    }

    static void FreshRr2dvSource()
    {
        if (refBody) Object.DestroyImmediate(refBody.gameObject);
        refBody = null;
    }

    static void SaveRr2dvPrefab(GameObject root, string path)
    {
        bool success;
        var saved = PrefabUtility.SaveAsPrefabAsset(root, path, out success);
        if (!success || !saved) throw new InvalidOperationException("Could not save measured placement: " + path);
    }

    // The record's axle pairs are provisional. Modelled big-end nubs define the oiling
    // layout when present; a board is only a fallback for a missing nub or a model
    // without detectable nubs. A pair with no seat on either surface is omitted.
    static void SeatRr2dvOilCups()
    {
        if (Cfg.IsTender || Cfg.OilPoints == null || Cfg.RodOilers != null || Cfg.OilAnchors != null) return;
        var hints = Cfg.OilPoints(RefBody).ToArray();
        if (hints.Length % 2 != 0 || hints.Length != Cfg.EngineUnits.Sum(u => u.DriverParts.Length) * 2)
            throw new InvalidOperationException("Oil-cup hints must contain a left/right pair for every driving axle");
        string path = $"{carFolder}/{CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            var body = root.transform.Find("Model/" + Cfg.BodyName);
            if (!body) throw new InvalidOperationException("Missing built body for oil-cup placement");
            var placed = new System.Collections.Generic.List<(string tag, Vector3 pos, Transform rod, string seat)>();
            Rr2dvMotion = Rr2dvGearMotion(body);
            var nubs = Rr2dvRodNubs(body);
            using (var hits = new VisualHits(body))
            {
                var remaining = nubs.Where(n => n.pos.x > 0).ToList();
                var pairs = new System.Collections.Generic.List<((Transform rod, Vector3 pos) l, (Transform rod, Vector3 pos) r, float z)>();
                foreach (var left in nubs.Where(n => n.pos.x < 0))
                {
                    var right = remaining.OrderBy(n => Mathf.Abs(n.pos.z - left.pos.z)).FirstOrDefault();
                    if (right.rod && Mathf.Abs(right.pos.z - left.pos.z) <= .45f) remaining.Remove(right);
                    else right = (null, Vector3.zero);
                    pairs.Add(((left.rod, left.pos), (right.rod, right.pos), (left.pos.z + (right.rod ? right.pos.z : left.pos.z)) / 2));
                }
                foreach (var right in remaining) pairs.Add(((null, Vector3.zero), (right.rod, right.pos), right.pos.z));
                pairs = Rr2dvOilBudget(pairs, hints);
                int pair = 0;
                foreach (var p in pairs) Rr2dvAddOilPair(placed, hits, body, ++pair, p.l, p.r, p.z);
                if (nubs.Count == 0)
                {
                    for (int i = 0; i < hints.Length; i += 2)
                        Rr2dvAddOilPair(placed, hits, body, i / 2 + 1,
                            (null, Vector3.zero), (null, Vector3.zero),
                            (hints[i].Item2.z + hints[i + 1].Item2.z) / 2);
                }
            }
            var old = body.Find("[oiling points]");
            if (old) Object.DestroyImmediate(old.gameObject);
            var holder = new GameObject("[oiling points]").transform;
            holder.SetParent(body, false);
            var points = new (string tag, Vector3 pos)[placed.Count];
            for (int i = 0; i < placed.Count; i++)
            {
                var p = placed[i];
                var provider = new GameObject(p.tag).transform;
                provider.SetParent(p.rod ? p.rod : holder, false);
                provider.position = p.pos;
                Set(Add(provider.gameObject, "CCL.Types.Proxies.Util.PositionSyncProviderProxy"), "syncTag", p.tag);
                points[i] = (p.tag, root.transform.InverseTransformPoint(p.pos));
                Line($"rr2dv oil {p.tag}: {p.seat} at {V(points[i].pos)}; provider parent {provider.parent.name}");
            }
            Cfg.OilPoints = _ => points;
            var oilDefinition = root.transform.Find("[sim]/oilingPoints")?.GetComponents<Component>()
                .FirstOrDefault(c => c.GetType().Name == "ManualOilingPointsDefinitionProxy");
            if (!oilDefinition) throw new InvalidOperationException("Missing simulation oiling-point definition");
            Set(oilDefinition, "OilingPointCount", points.Length);
            oilDefinition.GetType().GetMethod("OnValidate", BF)?.Invoke(oilDefinition, null);
            Line($"rr2dv oil layout: {placed.Count} cups ({nubs.Count} rod-nub candidates, {hints.Length} provisional axle hints)");
            Line($"rr2dv oil simulation count: {points.Length}");
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    // Oil-cup budget (James, 2026-09-29): one left/right pair per driving axle, 10 cups at most on a large loco. Every
    // rod nub became a pair before, so a model rich in nubs got cups on every surface (C&O T1: 28 cups, 8 pairs bunched
    // around the cylinders and crossheads). Over budget, each driving axle (the provisional axle hints) keeps the nub
    // pair nearest its z within 0.6 m (a crank throw and margin); the rest are dropped and listed.
    const int Rr2dvOilPairsMax = 5;

    static System.Collections.Generic.List<((Transform rod, Vector3 pos) l, (Transform rod, Vector3 pos) r, float z)> Rr2dvOilBudget(
        System.Collections.Generic.List<((Transform rod, Vector3 pos) l, (Transform rod, Vector3 pos) r, float z)> pairs,
        (string, Vector3)[] hints)
    {
        int budget = Mathf.Min(hints.Length / 2, Rr2dvOilPairsMax);
        if (pairs.Count <= budget) return pairs;
        var axles = Enumerable.Range(0, hints.Length / 2).Select(i => (hints[2 * i].Item2.z + hints[2 * i + 1].Item2.z) / 2).ToArray();
        var free = pairs.ToList();
        var chosen = new System.Collections.Generic.List<(((Transform rod, Vector3 pos) l, (Transform rod, Vector3 pos) r, float z) pair, float dz)>();
        foreach (float az in axles)
        {
            if (free.Count == 0) break;
            var best = free.OrderBy(p => Mathf.Abs(p.z - az)).First();
            if (Mathf.Abs(best.z - az) > .6f) { Line($"rr2dv oil budget: driving axle z {az:F3} has no rod nub pair within 0.6 m; no cup there"); continue; }
            free.Remove(best);
            chosen.Add((best, Mathf.Abs(best.z - az)));
        }
        var keep = chosen.OrderBy(c => c.dz).Take(budget).Select(c => c.pair).ToList();
        var kept = pairs.Where(p => keep.Contains(p)).ToList();  // source order kept (O01: stable tags and indices)
        foreach (var p in pairs.Where(p => !kept.Contains(p)))
            Line($"rr2dv oil budget: nub pair at z {p.z:F3} dropped (one pair per driving axle, at most {Rr2dvOilPairsMax * 2} cups)");
        Line($"rr2dv oil budget: {pairs.Count} nub pairs -> {kept.Count} ({axles.Length} driving axle(s), at most {Rr2dvOilPairsMax * 2} cups)");
        return kept;
    }

    static void Rr2dvAddOilPair(System.Collections.Generic.List<(string tag, Vector3 pos, Transform rod, string seat)> placed,
        VisualHits hits, Transform body, int pair, (Transform rod, Vector3 pos) left, (Transform rod, Vector3 pos) right, float z)
    {
        var a = left.rod && Rr2dvRodSeatAccessible(hits, body, left.pos)
            ? (true, left.pos, left.rod, "rod big end") : Rr2dvGearTopSeat(hits, body, -1, z);
        if (!a.Item1) a = Rr2dvBoardSeat(hits, body, -1, z);
        var b = right.rod && Rr2dvRodSeatAccessible(hits, body, right.pos)
            ? (true, right.pos, right.rod, "rod big end") : Rr2dvGearTopSeat(hits, body, 1, z);
        if (!b.Item1) b = Rr2dvBoardSeat(hits, body, 1, z);
        if (!a.Item1 || !b.Item1)
        {
            Line($"rr2dv oil pair {pair} omitted: no accessible {(a.Item1 ? "right" : b.Item1 ? "left" : "left or right")} rod, running-gear or board seat");
            return;
        }
        placed.Add(($"oil_{pair}L", a.Item2, a.Item3, a.Item4));
        placed.Add(($"oil_{pair}R", b.Item2, b.Item3, b.Item4));
    }

    static bool Rr2dvRodSeatAccessible(VisualHits hits, Transform body, Vector3 pos)
    {
        float side = Mathf.Sign(pos.x);
        // A rod can have a moving eccentric outside the big end. The cup remains
        // usable when it has a clear approach from above even if that side ray
        // meets the linkage at one sampled wheel phase.
        return !hits.Ray(pos + Vector3.up * .08f, Vector3.up, .12f, out var overhead, body) ||
            !hits.Ray(pos + Vector3.up * .08f, Vector3.right * side, .6f, out var sideHit, body);
    }

    static (bool found, Vector3 pos, Transform rod, string seat) Rr2dvBoardSeat(VisualHits hits, Transform body, float side, float zHint)
    {
        // Search outboard horizontal surfaces near the axle. This is intentionally a
        // secondary route; moving rods and wheels cannot masquerade as a board.
        for (float x = 1.65f; x >= .8f; x -= .025f)
        for (int dz = 0; dz < 9; dz++)
        {
            float z = zHint + (dz == 0 ? 0 : (dz % 2 == 0 ? -1 : 1) * ((dz + 1) / 2) * .05f);
            var origin = new Vector3(side * x, 2 * WheelRadius + 1.2f, z);
            if (!hits.Ray(origin, Vector3.down, 1.8f, out var hit, body) || hit.normal.y < .97f ||
                hit.point.y < 2 * WheelRadius + .08f || Rr2dvIsRod(hit.collider.transform.parent.name)) continue;
            bool footprint = true;
            foreach (var offset in new[] { new Vector3(.045f, 0, 0), new Vector3(-.045f, 0, 0), new Vector3(0, 0, .045f), new Vector3(0, 0, -.045f) })
                if (!hits.Ray(origin + offset, Vector3.down, 1.8f, out var edge, body) || edge.normal.y < .97f ||
                    Mathf.Abs(edge.point.y - hit.point.y) > .01f) footprint = false;
            if (!footprint) continue;
            var pos = hit.point + Vector3.up * (CupPivotAboveBase - CupSeatSink);
            if (hits.Ray(pos + Vector3.up * .08f, Vector3.up, .12f, out var overhead, body)) continue;
            if (hits.Ray(pos + Vector3.up * .08f, Vector3.right * side, .6f, out var sideHit, body)) continue;
            return (true, pos, null, "running board on " + hit.collider.transform.parent.name);
        }
        return (false, Vector3.zero, null, null);
    }

    // A big-end nub can be a small island (L-27's were rejected at under 35 triangles; James, 2026-09-28: slightly lower).
    const int Rr2dvMinNubTriangles = 20;

    // Flat tops on the running gear itself, before falling back to the running boards (James, 2026-09-28: the H9's
    // big ends, crossheads and axlebox tops look better than the boards). Searched down from above the wheels, in the
    // rod plane outside the frames, near the axle: a level spot at least 5 cm across, clear above and to the outside, on
    // any part but a wheel. A cup on a moving part (rod, crosshead) rides with it.
    static (bool found, Vector3 pos, Transform rod, string seat) Rr2dvGearTopSeat(VisualHits hits, Transform body, float side, float zHint)
    {
        float top = 2 * WheelRadius + .1f, low = WheelRadius * .6f;
        for (int dz = 0; dz < 17; dz++)
        for (float x = .7f; x <= 1.45f; x += .025f)
        {
            float z = zHint + (dz == 0 ? 0 : (dz % 2 == 0 ? -1 : 1) * ((dz + 1) / 2) * .05f);
            var origin = new Vector3(side * x, top + .5f, z);
            if (!hits.Ray(origin, Vector3.down, 2f, out var hit, body) || hit.normal.y < .95f ||
                hit.point.y > top || hit.point.y < low) continue;
            var part = hit.collider.transform.parent;
            if (part.name.ToLowerInvariant().Contains("wheel") || Rr2dvSpins(part)) continue;
            bool footprint = true;
            foreach (var offset in new[] { new Vector3(.025f, 0, 0), new Vector3(-.025f, 0, 0), new Vector3(0, 0, .025f), new Vector3(0, 0, -.025f) })
                if (!hits.Ray(origin + offset, Vector3.down, 2f, out var edge, body) || edge.normal.y < .95f ||
                    edge.collider != hit.collider || Mathf.Abs(edge.point.y - hit.point.y) > .006f) footprint = false;
            if (!footprint) continue;
            var pos = hit.point + Vector3.up * (CupPivotAboveBase - CupSeatSink);
            if (hits.Ray(pos + Vector3.up * .08f, Vector3.up, .12f, out var overhead, body)) continue;
            if (hits.Ray(pos + Vector3.up * .08f, Vector3.right * side, .6f, out var sideHit, body)) continue;
            bool moving = Rr2dvIsRod(part.name) || part.name.ToLowerInvariant().Contains("crosshead") || Rr2dvTravels(part);
            return (true, pos, moving ? part : null, "running gear top on " + part.name);
        }
        return (false, Vector3.zero, null, null);
    }

    // Running gear by what it does, not what it is called (DM&IR M-3: wheels and rods are all 'Cylinder.nnn', so cups
    // sat on wheel tops and rod cups stayed behind while the rods moved, 2026-09-29). Each driving group's own clip is
    // sampled over a revolution: a part whose middle travels is a rod (the cup rides on it); a part that turns about a
    // fixed middle is a wheel, axle or crank (no cup on it).
    static System.Collections.Generic.Dictionary<Transform, bool> Rr2dvMotion = new System.Collections.Generic.Dictionary<Transform, bool>();
    static bool Rr2dvTravels(Transform t) => Rr2dvMotion.TryGetValue(t, out var travels) && travels;
    static bool Rr2dvSpins(Transform t) => Rr2dvMotion.TryGetValue(t, out var travels) && !travels;

    static System.Collections.Generic.Dictionary<Transform, bool> Rr2dvGearMotion(Transform body)
    {
        var result = new System.Collections.Generic.Dictionary<Transform, bool>();
        foreach (var u in Cfg.EngineUnits)
        foreach (var animator in body.GetComponentsInChildren<Animator>(true)
                     .Where(a => a.name == $"[anim] {u.GroupName}" || a.name.StartsWith($"[anim] {u.GroupName} ")))
        {
            var clip = animator.runtimeAnimatorController ? animator.runtimeAnimatorController.animationClips.FirstOrDefault() : null;
            if (!clip) continue;
            var renderers = animator.GetComponentsInChildren<Renderer>(true);
            var samples = renderers.ToDictionary(r => r, r => new System.Collections.Generic.List<(Vector3 centre, Quaternion rot)>());
            try
            {
                foreach (var phase in new[] { 0f, .25f, .5f, .75f })
                {
                    clip.SampleAnimation(animator.gameObject, phase * clip.length);
                    foreach (var r in renderers) samples[r].Add((r.bounds.center, r.transform.rotation));
                }
            }
            finally { clip.SampleAnimation(animator.gameObject, 0); }
            foreach (var kv in samples)
            {
                float travel = kv.Value.Max(a => kv.Value.Max(b => Vector3.Distance(a.centre, b.centre)));
                float turn = kv.Value.Max(a => kv.Value.Max(b => Quaternion.Angle(a.rot, b.rot)));
                if (travel > .02f) result[kv.Key.transform] = true;
                else if (turn > 5f) result[kv.Key.transform] = false;
            }
        }
        Line($"rr2dv oil running gear by motion: {result.Count(kv => kv.Value)} travelling parts (rods), {result.Count(kv => !kv.Value)} turning in place (wheels, axles, cranks)");
        return result;
    }

    static bool Rr2dvIsRod(string name)
    {
        // Spaces and underscores ignored: 'DriverDriveRod' (GN L-27) is a drive rod as much as 'Drive Rod'.
        string n = name.ToLowerInvariant().Replace(" ", "").Replace("_", "");
        return n.Contains("mainrod") || n.Contains("siderod") || n.Contains("connectingrod") ||
            n.Contains("couplingrod") || n.Contains("driverod") || n.Contains("conrod");
    }

    static System.Collections.Generic.List<(Transform rod, Vector3 pos)> Rr2dvRodNubs(Transform body)
    {
        var result = new System.Collections.Generic.List<(Transform rod, Vector3 pos)>();
        foreach (var mf in body.GetComponentsInChildren<MeshFilter>(true).Where(m => Rr2dvIsRod(m.name) || Rr2dvTravels(m.transform)))
        {
            var mesh = mf.sharedMesh;
            var renderer = mf.GetComponent<MeshRenderer>();
            if (!mesh || !renderer || !renderer.enabled || !mf.gameObject.activeInHierarchy) continue;
            var world = mesh.vertices.Select(mf.transform.TransformPoint).ToArray();
            if (world.Length == 0) continue;
            var whole = new Bounds(world[0], Vector3.zero);
            foreach (var v in world) whole.Encapsulate(v);
            if (Mathf.Max(whole.size.y, whole.size.z) < .5f) { Line($"rr2dv oil rod {mf.name}: shorter than 0.5 m, no nub search"); continue; }
            int small = 0, wrongSize = 0, notEnd = 0, noTop = 0, found = 0;
            var groups = Islands(mesh);
            for (int sub = 0; sub < mesh.subMeshCount; sub++)
            {
                var triangles = mesh.GetTriangles(sub);
                groups.Add(Enumerable.Range(0, triangles.Length / 3).Select(i =>
                    (sub, triangles[3 * i], triangles[3 * i + 1], triangles[3 * i + 2])).ToList());
            }
            foreach (var group in groups)
            {
                if (group.Count < Rr2dvMinNubTriangles) { small++; continue; }
                var box = new Bounds(world[group[0].a], Vector3.zero);
                foreach (var t in group) { box.Encapsulate(world[t.a]); box.Encapsulate(world[t.b]); box.Encapsulate(world[t.c]); }
                var size = box.size;
                if (size.x < .035f || size.z < .035f || size.y < .035f ||
                    size.x > .3f || size.z > .3f || size.y > .3f) { wrongSize++; continue; }
                int axis = whole.size.z >= whole.size.y ? 2 : 1;
                if (Mathf.Min(Mathf.Abs(box.center[axis] - whole.min[axis]),
                    Mathf.Abs(box.center[axis] - whole.max[axis])) > .35f) { notEnd++; continue; }
                Vector3 top = Vector3.zero; float area = 0;
                foreach (var t in group)
                {
                    var a = world[t.a]; var b = world[t.b]; var c = world[t.c];
                    var normal = Vector3.Cross(b - a, c - a);
                    if (normal.magnitude < 1e-8f || normal.normalized.y < .75f ||
                        Mathf.Min(a.y, b.y, c.y) < box.max.y - .03f) continue;
                    float weight = normal.magnitude / 2;
                    top += (a + b + c) / 3 * weight;
                    area += weight;
                }
                if (area < .0003f) { noTop++; continue; }
                var pos = top / area + Vector3.up * (CupPivotAboveBase - CupSeatSink);
                if (Mathf.Abs(pos.x) < .3f || result.Any(p => p.rod == mf.transform && Vector3.Distance(p.pos, pos) < .08f)) continue;
                result.Add((mf.transform, pos));
                found++;
            }
            // Why a rod gave no nub is otherwise invisible (L-27: 0 candidates on rods with visible big-end bosses).
            Line($"rr2dv oil rod {mf.name}: {found} nub(s); islands rejected: {small} under {Rr2dvMinNubTriangles} triangles, {wrongSize} outside 3.5-30 cm, " +
                 $"{notEnd} not within 0.35 m of a rod end, {noTop} without an upward face");
        }
        return result.OrderByDescending(p => p.pos.z).ThenBy(p => p.pos.x).ToList();
    }

    static void AlignRr2dvBogieSupports()
    {
        string path = $"{carFolder}/{CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            foreach (var front in new[] { true, false })
            {
                var bogie = root.transform.Find((front ? "BogieF" : "BogieR") + "/bogie_car");
                var axleNodes = bogie.Cast<Transform>().Where(t => t.name == "[axle]").ToArray();
                var axles = axleNodes.Select(t => root.transform.InverseTransformPoint(t.position).z).ToArray();
                if (axles.Length == 0) throw new InvalidOperationException("No support axles");
                // The body rests at the bogie pivot, which can be a driver behind an articulated pilot or the centre of
                // a leading truck: not the outermost axle (Codex X52, A-18; RLW RPP-1's front sank through its leading
                // truck, 2026-09-28). Each axle sits at its own wheel's radius, not the driver's.
                float z = root.transform.InverseTransformPoint(bogie.position).z;
                float pivotAxleZ = axles.OrderBy(a => Mathf.Abs(a - z)).First();
                float radius = Rr2dvAxleRadius(pivotAxleZ);
                if (radius <= 0) throw new InvalidOperationException("Invalid end-wheel support radius");
                for (int i = 0; i < axleNodes.Length; i++)
                {
                    float axleRadius = Rr2dvAxleRadius(axles[i]);
                    var oldAxle = axleNodes[i].localPosition;
                    axleNodes[i].localPosition = new Vector3(oldAxle.x, axleRadius, oldAxle.z);
                    Line($"rr2dv axle z {axles[i]:F5}: y {oldAxle.y:F5} -> {axleRadius:F5}");
                }
                var support = root.transform.Find("[colliders]/[bogies]/" + (front ? "front" : "rear"));
                var collider = support.GetComponent<CapsuleCollider>();
                if (!collider) throw new InvalidOperationException("Missing bogie support capsule");
                var oldCentre = collider.center;
                collider.center = Vector3.zero;
                collider.radius = radius;
                collider.height = Mathf.Max(collider.height, radius * 2);
                support.position = root.transform.TransformPoint(new Vector3(0, radius, z));
                Line($"rr2dv support {support.name}: donor centre {V(oldCentre)} cleared; pivot z {z:F5}, nearest axle z {pivotAxleZ:F5}, car centre (0,{radius:F5},{z:F5}), radius {radius:F5}, rail contact y=0");
            }
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    static float Rr2dvAxleRadius(float axleZ)
    {
        if (Cfg.IsTender) return WheelRadius;
        var ws = Cfg.Wheelsets.Where(w => w.axles > 0).OrderBy(w =>
            Enumerable.Range(0, w.axles).Min(i => Mathf.Abs(axleZ -
                (w.offset + (w.axles > 1 ? w.length / 2 - i * w.length / (w.axles - 1) : 0))))).First();
        bool reviewedPowered = RrChoices != null && RrChoices.physics == "geared" &&
            (RrChoices.poweredWheelsets ?? new int[0]).Contains(Array.IndexOf(Cfg.Wheelsets, ws));
        if (reviewedPowered || Cfg.EngineUnits.Any(u => u.AnimKey == ws.clip)) return WheelRadius;
        return Cfg.PonyRadii.TryGetValue(ws.clip ?? "", out var radius) ? radius : ws.diameter / 2;
    }

    // A tender with no Railroader number decals keeps the template's plate anchors, which CCL places diagonally (one toward
    // each end on opposite sides, as DV wagons): read as misplaced in the L-27 game test (2026-09-28). James's rule, tenders
    // only: both plates at the midpoint of the two, lowered to just above the bottom edge of the tender body's side sheet
    // (measured by rays at that point, top down), keeping CCL's depth. Locomotives keep the template positions.
    static void AlignRr2dvDefaultPlates()
    {
        if (!Cfg.IsTender || (Cfg.PlateDecals != null && Cfg.PlateDecals.Length > 0)) return;
        string path = $"{carFolder}/{CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            var a = root.transform.Find("[car plate anchor1]");
            var b = root.transform.Find("[car plate anchor2]");
            var body = root.transform.Find("Model/" + Cfg.BodyName);
            if (!a || !b || !body || Mathf.Sign(a.localPosition.x) == Mathf.Sign(b.localPosition.x)) return;
            float z = (a.localPosition.z + b.localPosition.z) / 2;
            var renderers = body.GetComponentsInChildren<Renderer>().Where(r => r.enabled).ToArray();
            if (renderers.Length == 0) return;
            var extent = renderers[0].bounds; foreach (var r in renderers) extent.Encapsulate(r.bounds);
            using (var hits = new VisualHits(body))
            foreach (var anchor in new[] { a, b })
            {
                float side = Mathf.Sign(anchor.localPosition.x), outside = Mathf.Max(Mathf.Abs(extent.min.x), Mathf.Abs(extent.max.x)) + 1;
                var dummy = anchor.GetComponentInChildren<Renderer>(true);
                float half = dummy ? dummy.bounds.extents.y : .16f;
                var row = new System.Collections.Generic.List<(float y, float x)>();
                for (float y = extent.max.y; y >= extent.min.y; y -= .02f)
                    if (hits.Ray(new Vector3(side * outside, y, z), Vector3.left * side, outside, out var hit, body) && hit.normal.x * side > .9f)
                        row.Add((y, Mathf.Abs(hit.point.x)));
                if (row.Count == 0) { Line($"rr2dv tender plate {anchor.name}: no side sheet found at z {z:F3}; template height kept"); anchor.localPosition = new Vector3(anchor.localPosition.x, anchor.localPosition.y, z); continue; }
                // The side sheet: the most common outward face depth; its bottom edge is the lowest hit at that depth
                // (beading or lining bands break a top-down run early: RPP-1 plates landed under the top rail).
                float sheet = row.GroupBy(h => Mathf.Round(h.x * 100)).OrderByDescending(g => g.Count()).First().Key / 100f;
                int i = row.FindLastIndex(h => Mathf.Abs(h.x - sheet) <= .02f);
                float y0 = row[i].y + half + .03f;
                Line($"rr2dv tender plate {anchor.name}: z {anchor.localPosition.z:F3} -> {z:F3} (midpoint), y {anchor.localPosition.y:F3} -> {y0:F3} " +
                     $"(side sheet at |x| {sheet:F3}, bottom edge y {row[i].y:F3})");
                anchor.localPosition = new Vector3(anchor.localPosition.x, y0, z);
            }
            PrefabUtility.SaveAsPrefabAsset(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    static void SeatRr2dvPlates()
    {
        string path = $"{carFolder}/{CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            var body = root.transform.Find("Model/" + Cfg.BodyName);
            if (!body) throw new InvalidOperationException("Missing built body for plate measurement");
            using (var hits = new VisualHits(body))
            foreach (var pair in Cfg.PlateDecals)
            {
                var source = Comp(pair.Item2);
                float side = Mathf.Sign(source.pos.x);
                var anchor = root.transform.Find(pair.Item1);
                if (!anchor || side == 0) throw new InvalidOperationException("Invalid plate anchor " + pair.Item1);
                var dummy = anchor.GetComponentInChildren<Renderer>(true);
                if (!dummy) throw new InvalidOperationException("No plate footprint supplied by template: " + pair.Item1);
                var footprint = dummy.bounds;
                var bodyBounds = body.GetComponentsInChildren<Renderer>().Where(r => r.enabled).Select(r => r.bounds).ToArray();
                if (bodyBounds.Length == 0) throw new InvalidOperationException("No visible body for plates");
                var extent = bodyBounds[0]; foreach (var b in bodyBounds) extent.Encapsulate(b);
                float outside = Mathf.Max(Mathf.Abs(extent.min.x), Mathf.Abs(extent.max.x)) + 1;
                bool found = false; RaycastHit hit = new RaycastHit();
                string fit = null; float scale = 1f;
                // Full size first; where it would overhang, the plate may shrink to 90 then 80 % (James, 2026-09-29: no smaller,
                // so it stays readable). Derail Valley spawns its plate at the anchor, so the anchor's scale sizes it.
                foreach (var s in new[] { 1f, .9f, .8f })
                {
                if (found) break;
                scale = s;
                var fe = footprint.extents * s; var fs = footprint.size * s;
                // Search nearest to the source label, then verify the entire plate footprint.
                var candidates = new System.Collections.Generic.List<Vector3>();
                for (float z = extent.min.z + fe.z; z <= extent.max.z - fe.z; z += .05f)
                for (int y = -10; y <= 10; y++) candidates.Add(new Vector3(side * outside, source.pos.y + y * .05f, z));
                candidates.Insert(0, new Vector3(side * outside, source.pos.y, source.pos.z));
                // Flat to 5.7 degrees within 8 mm first; then a curved or panelled side (PLW Trojan saddle tank, 2026-09-28)
                // to 18 degrees within 25 mm; then the plate stays at the source decal with a WARN rather than stopping.
                foreach (var (flat, relief, rule) in new[] { (.995f, .008f, "flat"), (.95f, .025f, "curved side") })
                {
                if (found) break;
                foreach (var origin in candidates.OrderBy(p => Mathf.Pow(p.y-source.pos.y,2) + Mathf.Pow(p.z-source.pos.z,2)))
                {
                    if (!hits.Ray(origin, Vector3.left * side, outside, out hit, body) || hit.normal.x * side < flat) continue;
                    bool supported = true;
                    int ny = Mathf.CeilToInt(fs.y / .1f), nz = Mathf.CeilToInt(fs.z / .1f);
                    for (int iy = 0; iy <= ny && supported; iy++)
                    for (int iz = 0; iz <= nz; iz++)
                    {
                        var sample = origin + new Vector3(0, Mathf.Lerp(-fe.y, fe.y, (float)iy/ny), Mathf.Lerp(-fe.z, fe.z, (float)iz/nz));
                        if (!hits.Ray(sample, Vector3.left * side, outside, out var edge, body) || edge.collider != hit.collider ||
                            edge.normal.x * side < flat || Mathf.Abs(edge.point.x-hit.point.x) > relief) { supported = false; break; }
                    }
                    if (supported) { found = true; fit = rule; break; }
                }
                }
                }
                if (!found)
                {
                    Warn($"plate {pair.Item1}: no fully supported visible surface; left at the source decal {V(anchor.localPosition)} (check it in game)");
                    continue;
                }
                var old = anchor.localPosition;
                anchor.position = hit.point + Vector3.right * side * .01f;
                anchor.localRotation = Quaternion.Euler(0, side > 0 ? 0 : 180, 0);
                if (scale < 1f) anchor.localScale = Vector3.one * scale;
                Line($"rr2dv visible plate {pair.Item1}: {V(old)} -> {V(anchor.localPosition)} on {hit.collider.transform.parent.name}; " +
                     (scale < 1f ? $"scaled to {scale * 100:F0} %: {footprint.size.y * scale:F3} x {footprint.size.z * scale:F3} m footprint supported ({fit}; the full size overhangs)"
                                 : $"full {footprint.size.y:F3} x {footprint.size.z:F3} m footprint supported ({fit})"));
            }
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    static void SeatRr2dvControls()
    {
        string path = $"{carFolder}/{CarId}_interior.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            using (var hits = new VisualHits(RefBody))
            foreach (var spec in Cfg.Placed)
            {
                var control = root.transform.Find("Controls/C_" + spec.Name);
                if (!control) throw new InvalidOperationException("Missing generated control " + spec.Name);
                var origin = new Vector3(spec.X, spec.Y, Cfg.BackheadRayStartZ);
                if (!hits.Ray(origin, Vector3.forward, 1f, out var hit, RefBody) || hit.normal.z > -.5f)
                    throw new InvalidOperationException("No visible cab-facing surface for generated control " + spec.Name);
                var old = control.localPosition;
                control.localPosition = new Vector3(spec.X, spec.Y, hit.point.z - (spec.Wheel ? .035f : .02f));
                Line($"rr2dv visible control {control.name}: {V(old)} -> {V(control.localPosition)} on {hit.collider.transform.parent.name}");
                if (spec.Label == null) continue;
                var label = root.transform.Find("Controls/label " + spec.Label.Substring(4));
                if (!label) throw new InvalidOperationException("Missing generated control label " + spec.Label);
                var labelOrigin = new Vector3(spec.X, spec.Y - (spec.Wheel ? .075f : .035f), Cfg.BackheadRayStartZ);
                if (!hits.Ray(labelOrigin, Vector3.forward, 1f, out var labelHit, RefBody) || labelHit.normal.z > -.5f ||
                    Mathf.Abs(labelHit.point.z - hit.point.z) > .1f)
                {
                    // No surface just below the control (the H9's injector sits on a pipe 0.32 m proud of the plate, with
                    // nothing under it): a name plate is no reason to stop the build. It hangs just in front of its control.
                    label.localPosition = new Vector3(labelOrigin.x, labelOrigin.y, hit.point.z - .016f);
                    Warn($"generated label {spec.Label}: no surface below its control; placed at the control's depth");
                    continue;
                }
                label.localPosition = new Vector3(labelOrigin.x, labelOrigin.y, labelHit.point.z - .016f);
            }
            Section("rr2dv control sweep after visible-surface placement");
            SweepCheck(root.transform.Find("Controls"));
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }
}
