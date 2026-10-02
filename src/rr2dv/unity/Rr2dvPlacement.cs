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
        Rr2dvStokerParts.Clear(); Report.Clear(); warnings = 0; ownMats.Clear(); refBody = null; builtFolders.Clear(); meshIslandSources.Clear();
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
            Cfg = cfg; carFolder = builtFolders[cfg]; RequireRr2dvSpeedHud();
            Cfg = cfg; refBody = null; carFolder = builtFolders[cfg];
            Rr2dvCatalogue.Attach((CCL.Types.CustomCarPack)FindAsset("CustomCarPack"), Rr2dvCatalogue.ReadInput(), Line);
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
        if (!c.IsTender) ProbeRr2dvSafetyJet();
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
        Rr2dvSkinCheck();
        PassRr2dvGrabRays();
        if (!c.IsTender && Rr2dvNoDynamo) StripRr2dvDynamoHud();
        if (!c.IsTender) CloseRr2dvWhistle();
        SeatRr2dvOilCups();
        AlignRr2dvBogieSupports();
        CentreRr2dvTruckWheelPivots();
        SeatRr2dvPlates();
        AlignRr2dvDefaultPlates();
        if (!c.IsTender)
        {
            StripRr2dvSourceColliders();
            BuildInterior(); BuildRr2dvGauges(); RepairRr2dvWaterIndicators(); SeatRr2dvControls(); FinishRr2dvInteriorControls(); BuildInteriorLOD(); RestoreRr2dvGaugeLodGrabbers();
            FreshRr2dvSource();
        }
        Rr2dvReleaseSeat();
        StripRr2dvHiddenMeshes();
        BuildInteractables();
        FreshRr2dvSource();
        BuildRr2dvAncillaries();
        var sound = c.IsTender ? null : BuildSound();
        ConfigureAssets(sound);
        builtFolders[c] = carFolder;
    }


    // App-owned correction applied before the interior LOD is copied. The core's box
    // mesh is centred, while its scaler is anchored at the bottom of the glass.
    static void RepairRr2dvWaterIndicators()
    {
        string path = $"{carFolder}/{CarId}_interior.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            foreach (Transform glass in root.transform)
            {
                if (!glass.name.StartsWith("sight glass ")) continue;
                var water = glass.Find("scaler/water");
                if (!water) throw new InvalidOperationException("Generated sight glass has no water column: " + glass.name);
                var p = water.localPosition;
                water.localPosition = new Vector3(p.x, water.localScale.y / 2f, p.z);
                Line($"rr2dv {glass.name}: water centre raised to half-height {water.localPosition.y:F3} m");
            }
            var reader = root.GetComponentsInChildren<Component>(true)
                .Single(c => c && c.GetType().Name == "LocoIndicatorReaderProxy");
            var serialized = new SerializedObject(reader);
            var level = serialized.FindProperty("locoWaterLevel");
            if (level == null) throw new InvalidOperationException("Loco indicator reader has no boiler water field");
            if (!level.objectReferenceValue)
            {
                // A source loco without a SightGlass still needs its boiler-water HUD
                // reading. This creates no invented visible cab instrument.
                var host = Child(root.transform, "HUD-only boiler water", Vector3.zero);
                var dummy = Child(host, "dummy", Vector3.zero);
                var scaler = Add(host.gameObject, "CCL.Types.Proxies.Indicators.IndicatorScalerProxy");
                Set(scaler, "indicatorToScale", dummy);
                Set(scaler, "minValue", 0f); Set(scaler, "maxValue", 1f);
                Set(scaler, "startScale", Vector3.one); Set(scaler, "endScale", Vector3.one);
                Set(scaler, "scaleFromModel", false);
                PortReader(host.gameObject, "boiler.WATER_LEVEL_NORMALIZED");
                Set(reader, "locoWaterLevel", scaler);
                Line("rr2dv HUD-only boiler water reader: source has no generated sight glass");
            }
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
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
        using (new Rr2dvLodScope(RefBody))
        using (var vh = new VisualHits(RefBody))
            return vh.Ray(pos + dir * 1.5f, -dir, 3f, out var hit) ? Vector3.Dot(hit.point - pos, dir) : float.NaN;
    }

    // A generated tender coal load comes from a layout rule (a box at the tender front), which fits no particular tender: the
    // R48's showed as a block across the gap into the cab, the RXM-1B's stood on the front deck ahead of its coal doors and
    // through the bulkhead, with its real coal space (a stoker hopper) left empty (James's game tests, 2026-09-29). So the
    // coal space is measured from above instead, starting at Railroader's coal loading target (the chute aims at the coal):
    //  - downward rays every 4 cm give the surface under each point (hopper floor, sheet tops, decks);
    //  - the rim is the lower of the two side sheets' tops across the target;
    //  - the space runs forward and back from the target along the middle, then across each row, until a wall (a rise of
    //    more than 0.2 m between neighbouring rays to above half the depth: doors, bulkheads, but not a stoker trough's
    //    edge), the rim height (up a sloped hopper side) or a flat deck above half the depth (a tank top behind the coal).
    // The load keeps the core's bottom-pivot box (so the coal amount still scales it), fitted to that space: from just
    // under its floor to the rim plus the heap. Where nothing can be measured the layout box stays, with a warning.
    static Rr2dvCoalSpace coalSpace;
    class Rr2dvCoalSpace { public float floor, rim, peak, zRear, zFront; public float[] zs, left, right; }

    const float CoalStep = .04f, CoalWallRise = .2f;

    static void FitRr2dvCoalLoad()
    {
        coalSpace = null;
        var cl = Cfg.CoalLoad;
        if (cl == null || !cl.Pivot.HasValue) return;
        var p = cl.Pivot.Value;
        float boxRear = p.z - cl.Footprint.y / 2, boxFront = p.z + cl.Footprint.y / 2;
        Vector3 anchor = p;
        string from = "the layout box";
        try
        {
            var target = Cfg.CoalTargetComp == null ? null : Components.FirstOrDefault(c => c.name == Cfg.CoalTargetComp);
            if (target != null) { anchor = target.pos; from = $"Railroader's coal target {Cfg.CoalTargetComp}"; }
        }
        catch (Exception) { }
        var rs = RefBody.GetComponentsInChildren<Renderer>(false).Where(r => r.enabled).ToArray();
        if (rs.Length == 0) return;
        var bounds = rs[0].bounds; foreach (var r in rs) bounds.Encapsulate(r.bounds);
        float top = bounds.max.y + 1f;
        using (new Rr2dvLodScope(RefBody))
        using (var vh = new VisualHits(RefBody))
        {
            float Surface(float x, float z) => vh.Ray(new Vector3(x, top, z), Vector3.down, top + 1f, out var h) ? h.point.y : float.NaN;
            float Middle(float z)
            {
                var hs = new[] { -.3f, 0f, .3f }.Select(x => Surface(anchor.x + x, z)).Where(h => !float.IsNaN(h)).OrderBy(h => h).ToArray();
                return hs.Length == 0 ? float.NaN : hs[hs.Length / 2];
            }
            // the highest surface from `start` out to `stop`: a side sheet's top
            float Highest(Func<float, float> surface, float start, float dir, float stop)
            {
                float best = float.NaN;
                for (float u = start; dir > 0 ? u <= stop : u >= stop; u += dir * CoalStep)
                {
                    float h = surface(u);
                    if (!float.IsNaN(h) && !(h <= best)) best = h;
                }
                return best;
            }
            // from `start` in steps along `dir`, the last open position before the coal space ends: a wall (a rise of more
            // than 0.2 m to above half the depth: doors, bulkheads; not a stoker trough's edge), the rim height (up a sloped
            // hopper side) or a flat deck above half the depth (a tank top behind the coal); with that wall's or deck's height
            (float open, float wall) Walk(Func<float, float> surface, float start, float dir, float stop, float half, float top1)
            {
                float prev = surface(start), last = start, flatFrom = float.NaN;
                int flat = 0;
                for (float u = start + dir * CoalStep; dir > 0 ? u <= stop : u >= stop; u += dir * CoalStep)
                {
                    float h = surface(u);
                    if (float.IsNaN(h)) continue;
                    if (!float.IsNaN(prev) && h - prev > CoalWallRise && h >= half || h >= top1) return (last, h);
                    if (!float.IsNaN(prev) && h >= half && Mathf.Abs(h - prev) < .01f)
                    {
                        if (flat++ == 0) flatFrom = last;
                        if (flat >= 3) return (flatFrom, h);
                    }
                    else flat = 0;
                    prev = h; last = u;
                }
                return (float.NaN, float.NaN);
            }
            float floor0 = Surface(anchor.x, anchor.z);
            float wallL = Highest(x => Surface(x, anchor.z), anchor.x, -1, bounds.min.x);
            float wallR = Highest(x => Surface(x, anchor.z), anchor.x, 1, bounds.max.x);
            if (float.IsNaN(floor0) || float.IsNaN(wallL) || float.IsNaN(wallR))
            {
                Warn($"rr2dv coal load: no coal space with side walls found under {from}; the layout box stays (check it in game)");
                return;
            }
            float rim = Mathf.Min(wallL, wallR), limit = rim - .1f, mid = (floor0 + rim) / 2;
            if (rim - floor0 < .3f)
            {
                Warn($"rr2dv coal load: the surface under {from} is only {rim - floor0:F2} m below the side walls; the layout box stays");
                return;
            }
            var front = Walk(Middle, anchor.z, 1, bounds.max.z, mid, limit);
            var rear = Walk(Middle, anchor.z, -1, bounds.min.z, mid, limit);
            if (float.IsNaN(front.open) || float.IsNaN(rear.open) || front.open - rear.open < .5f)
            {
                Warn($"rr2dv coal load: no front and rear wall found along the coal space under {from}; the layout box stays");
                return;
            }
            var space = new Rr2dvCoalSpace { rim = rim, zFront = front.open - .03f, zRear = rear.open + .03f };
            var zs = new System.Collections.Generic.List<float>(); var ls = new System.Collections.Generic.List<float>(); var rrs = new System.Collections.Generic.List<float>();
            float floor = float.PositiveInfinity;
            for (float z = space.zRear; z <= space.zFront + 1e-4f; z += CoalStep)
            {
                float zz = z;
                var l = Walk(x => Surface(x, zz), anchor.x, -1, bounds.min.x, mid, limit);
                var r = Walk(x => Surface(x, zz), anchor.x, 1, bounds.max.x, mid, limit);
                if (float.IsNaN(l.open) || float.IsNaN(r.open)) continue;
                zs.Add(z); ls.Add(l.open + .03f); rrs.Add(r.open - .03f);
                for (float x = l.open; x <= r.open; x += CoalStep) { float h = Surface(x, z); if (!float.IsNaN(h)) floor = Mathf.Min(floor, h); }
            }
            if (zs.Count < 5) { Warn($"rr2dv coal load: the coal space under {from} has too few measurable rows; the layout box stays"); return; }
            space.zs = zs.ToArray(); space.left = ls.ToArray(); space.right = rrs.ToArray();
            float width = space.right.Max() - space.left.Min();
            space.floor = floor - .02f;
            space.peak = Mathf.Clamp(.2f * width, .15f, .45f);
            float x0 = space.left.Min(), x1 = space.right.Max();
            cl.Pivot = new Vector3((x0 + x1) / 2, space.floor, (space.zRear + space.zFront) / 2);
            cl.Footprint = new Vector2(x1 - x0, space.zFront - space.zRear);
            cl.FullHeight = space.rim + space.peak - space.floor;
            coalSpace = space;
            Line($"rr2dv coal load: coal space measured from above under {from}: z {space.zRear:F3}..{space.zFront:F3} (front wall top y {front.wall:F3}, " +
                 $"rear {rear.wall:F3}), x {x0:F3}..{x1:F3}, floor {space.floor:F3}, rim {rim:F3}; heap up to {space.rim + space.peak:F3} " +
                 $"(the layout box was z {boxRear:F3}..{boxFront:F3})");
        }
    }

    // The generated coal load as a heap in the measured coal space (James, 2026-09-29: "a more hump like shape, tapering
    // towards the tender front wall ... tighter sizing"): each measured row's own width, the top at the rim at the walls,
    // rising to the heap's peak over the back half and falling to the rim at the front wall, with walls down to the floor.
    // Drawn by its own renderer under the core's scaler (the core's box renderer is removed), in the box's unit coordinates,
    // so the coal amount scales it as before.
    static void ShapeRr2dvCoalLoad()
    {
        if (Cfg.CoalLoad == null || coalSpace == null) return;
        string path = $"{carFolder}/{CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            var load = root.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == "[coal load]");
            var box = load ? load.Find("scaler/coal") : null;
            if (!box) { Warn("rr2dv coal load: the core's coal load was not found; its heap was not made"); return; }
            string file = System.Text.RegularExpressions.Regex.Replace($"{CarId}_coal_heap", "[^A-Za-z0-9_.-]", "_");
            var mesh = Rr2dvCoalHeap(coalSpace, Cfg.CoalLoad);
            AssetDatabase.CreateAsset(mesh, AssetDatabase.GenerateUniqueAssetPath($"{carFolder}/{file}.asset"));
            var material = box.GetComponent<MeshRenderer>().sharedMaterial;
            Object.DestroyImmediate(box.GetComponent<MeshRenderer>());
            Object.DestroyImmediate(box.GetComponent<MeshFilter>());
            var heap = new GameObject("rr2dv coal heap").transform;
            heap.SetParent(box, false);
            heap.gameObject.AddComponent<MeshFilter>().sharedMesh = mesh;
            heap.gameObject.AddComponent<MeshRenderer>().sharedMaterial = material;
            Line($"rr2dv coal load: heap mesh {mesh.name} ({mesh.vertexCount} vertices, {coalSpace.zs.Length} measured rows) replaces the core's box renderer");
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    static Mesh Rr2dvCoalHeap(Rr2dvCoalSpace s, CoalLoadCfg cl)
    {
        const int n = 16;
        var c = cl.Pivot.Value; float sx = cl.Footprint.x, sz = cl.Footprint.y, sy = cl.FullHeight;
        float Row(float[] a, float z)
        {
            int i = Mathf.Clamp(Mathf.RoundToInt((z - s.zs[0]) / CoalStep), 0, s.zs.Length - 1);
            return a[i];
        }
        // w 0 at the rear wall, 1 at the front wall; u 0 at the left wall, 1 at the right
        float Top(float u, float w)
        {
            float across = 1f - (2 * u - 1) * (2 * u - 1);
            float along = w < .5f ? 1f - (1 - 2 * w) * (1 - 2 * w) * .4f : 1f - (2 * w - 1) * (2 * w - 1);
            return s.rim - .05f + (s.peak + .05f) * across * along;
        }
        var v = new System.Collections.Generic.List<Vector3>(); var uv = new System.Collections.Generic.List<Vector2>();
        var t = new System.Collections.Generic.List<int>();
        Vector3 Unit(float x, float y, float z) => new Vector3((x - c.x) / sx, (y - c.y) / sy, (z - c.z) / sz);
        for (int j = 0; j <= n; j++)
        {
            float w = (float)j / n, z = Mathf.Lerp(s.zRear, s.zFront, w);
            float l = Row(s.left, z), r = Row(s.right, z);
            for (int i = 0; i <= n; i++)
            {
                float u = (float)i / n, x = Mathf.Lerp(l, r, u);
                v.Add(Unit(x, Top(u, w), z)); uv.Add(new Vector2(x, z));
            }
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
                int st = v.Count;
                v.AddRange(new[] { top0, top1, bot1, bot0 });
                uv.AddRange(new[] { new Vector2(0, top0.y * sy), new Vector2(1, top1.y * sy), new Vector2(1, 0), new Vector2(0, 0) });
                t.AddRange(outer ? new[] { st, st + 1, st + 2, st, st + 2, st + 3 } : new[] { st, st + 2, st + 1, st, st + 3, st + 2 });
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
    // straight up. Dynamo jets follow the measured outward pipe direction, else straight up. C-25's game test
    // showed that the previous blanket 180-degree yaw correction reversed an already correct outlet measurement.
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
                // the safety valves too (board X61: MarquetteCreations/Moon asked for upward safety, dynamo and whistle steam;
                // the local core now turns all three holders -90 deg X, as the stock S282)
                bool whistle = t.name == "Whistle" || t.name.Contains("Safety"), dynamo = t.name.Contains("Dynamo");
                if (!whistle && !dynamo) continue;
                var tip = dynamo ? Rr2dvExhaustTip(t.position) : null;
                var dir = tip ?? Vector3.up;
                var now = t.rotation * Vector3.forward;
                t.rotation = Quaternion.FromToRotation(now, dir) * t.rotation;
                Line($"rr2dv steam jet {t.name}: {V(now)} -> {V(dir)} " +
                     (tip.HasValue ? "(measured outward pipe direction)" : dynamo ? "(straight up: no measurable exhaust pipe tip)" : "(straight up)"));
            }
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    // A fallback surface, not a claim to have identified the model's actual valve.
    // Restrict the query spatially as well as excluding named fittings: several
    // stock models use generic mesh names or call bell parts "Boiler".
    static void ProbeRr2dvSafetyJet()
    {
        if (Cfg.SafetyPos.HasValue || !string.IsNullOrEmpty(Cfg.SafetyValvePart)) return;
        if (!Cfg.BackheadZ.HasValue) throw new InvalidOperationException("Safety jet probe needs the backhead boundary");
        var chimney = Components.Single(c => c.kind == "Chuff" && c.name == Cfg.ChimneyComp).pos;
        var fittings = Components.Where(c => c.kind == "Bell" || c.kind == "Whistle" ||
            c.kind == "Dynamo" || c.kind == "Compressor").Select(c => c.pos).ToArray();
        var measured = ProbeRr2dvBoilerTop(RefBody, Cfg.BackheadZ.Value, chimney, fittings);
        Cfg.SafetyPos = measured.point + Vector3.up * .02f;
        Cfg.SndSafety = Cfg.SafetyPos.Value;
        Line($"rr2dv safety fallback: highest supported forward boiler/dome surface {measured.part} at {V(measured.point)}; " +
             $"jet {V(Cfg.SafetyPos.Value)} (20 mm clear), direction up; search z {measured.from:F3}..{measured.to:F3}, " +
             "centre strip x +/-0.30 m, 25 mm sampling; cab/chimney/other fittings excluded; verify in game");
    }

    static (Vector3 point, string part, float from, float to) ProbeRr2dvBoilerTop(
        Transform body, float backhead, Vector3 chimney, Vector3[] fittings)
    {
        using (new Rr2dvLodScope(body))
        {
            var renderers = body.GetComponentsInChildren<MeshRenderer>(false).Where(r => r.enabled).ToArray();
            if (renderers.Length == 0) throw new InvalidOperationException("Safety jet probe: no visible boiler geometry");
            var bounds = renderers[0].bounds;
            foreach (var r in renderers) bounds.Encapsulate(r.bounds);
            // Forward half of the locomotive only, and always ahead of the
            // backhead. Stop behind the stack so its rim cannot win the height search.
            float from = Mathf.Max(bounds.center.z, backhead + .25f);
            float to = chimney.z - Mathf.Max(.5f, (chimney.z - backhead) * .1f);
            if (to - from < .25f) throw new InvalidOperationException("Safety jet probe: no forward boiler search region clear of cab and chimney");
            float top = bounds.max.y + 1f, floor = (bounds.min.y + chimney.y) * .5f;
            var disabled = new System.Collections.Generic.List<Renderer>();
            try
            {
                foreach (var r in renderers)
                {
                      string path = PathOf(r.transform, body).ToLowerInvariant();
                      // Cab exclusion is spatial: S-23's Cab mesh also contains
                      // the boiler, so rejecting that name loses valid surfaces.
                    if (System.Text.RegularExpressions.Regex.IsMatch(path,
                        @"roof|chimney|stack|bell|whistle|dynamo|generator|compressor|pump|pipe|handrail|railing|cord|wire|headlight|headlamp|water|coal"))
                    { r.enabled = false; disabled.Add(r); }
                }
                using (var hits = new VisualHits(body))
                {
                    bool found = false; Vector3 best = Vector3.zero; string part = null;
                    bool Sample(float x, float z, out RaycastHit h)
                    {
                        h = default(RaycastHit);
                        if (z < from || z > to || fittings.Any(p => new Vector2(x - p.x, z - p.z).sqrMagnitude < .45f * .45f)) return false;
                        return hits.Ray(new Vector3(x, top, z), Vector3.down, top - floor, out h, body) && h.normal.y > .45f;
                    }
                    for (int iz = 4; from + iz * .025f <= to - .1f; iz++)
                    for (int ix = -12; ix <= 12; ix++)
                    {
                        float x = ix * .025f, z = from + iz * .025f;
                        if (!Sample(x, z, out var h) || (found && h.point.y < best.y - .0001f)) continue;
                        // Broad top support rejects narrow rails, pipes and isolated
                        // spikes, even when they are merged into a generic mesh.
                        bool supported = true;
                        foreach (var d in new[] { new Vector2(-.1f, 0), new Vector2(.1f, 0), new Vector2(0, -.1f), new Vector2(0, .1f) })
                            if (!Sample(x + d.x, z + d.y, out var edge) || Mathf.Abs(edge.point.y - h.point.y) > .08f)
                            { supported = false; break; }
                        if (!supported) continue;
                        if (found && Mathf.Abs(h.point.y - best.y) <= .0001f && Mathf.Abs(x) >= Mathf.Abs(best.x)) continue;
                        found = true; best = h.point; part = PathOf(h.collider.transform.parent, body);
                    }
                    if (!found) throw new InvalidOperationException("Safety jet probe: no supported forward boiler/dome top clear of fittings, review the model");
                    return (best, part, from, to);
                }
            }
            finally { foreach (var r in disabled) if (r) r.enabled = true; }
        }
    }

    // The exhaust pipe's direction at a jet point: the long axis of vertices within 0.25 m.
    // Require a pipe-like cloud, its end near the jet, and a non-downward direction.
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

    // Diagnostic (S-23 and P-48 tenders found no seat, 2026-09-30): the outer skin x at each height near the hint, LOD0 only,
    // so the build report shows why the core's fitter finds no side edge with a rod under it.
    static void Rr2dvReleaseProfile(Vector3 hint)
    {
        float side = Mathf.Sign(hint.x);
        using (new Rr2dvLodScope(RefBody))
        using (var vh = new VisualHits(RefBody))
            foreach (float dz in new[] { -1f, 0f, 1f })
            {
                var sb = new System.Text.StringBuilder();
                for (float y = 0.2f; y <= 2.001f; y += 0.1f)
                    sb.Append(vh.Ray(new Vector3(side * 3.5f, y, hint.z + dz), new Vector3(-side, 0, 0), 3.5f, out var h)
                        ? $" y{y:F1}:{h.point.x * side:F2}" : $" y{y:F1}:-");
                Line($"rr2dv brake release skin profile z {hint.z + dz:F2} (outer x by height, LOD0 only):{sb}");
            }
    }

    static void Rr2dvReleaseSeat()
    {
        if (Cfg.BrakeRelease == null || Cfg.BrakeReleaseExact) return;
        var (hint, euler) = Cfg.BrakeRelease(RefBody);
        var probe = new GameObject("rr2dv release probe").transform;
        using (new Rr2dvLodScope(RefBody))   // the core's fitter reads every enabled mesh: only each part's LOD0 counts
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
            Rr2dvReleaseProfile(hint);
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

    // The core seats the handbrake wheel on the visible model (VisualHits: active meshes with an enabled renderer), then its
    // final check (RRPlacementValidation.CheckHandbrake) casts against every MeshFilter, hidden ones too, and can find a
    // surface nobody sees in front of the wheel: the base-game K-28T stopped with "handbrake mount misfit: stand-off
    // -0.092 m" (2026-09-29). On the measuring copy only, meshes that are never drawn (inactive, no renderer or a disabled
    // one) are removed for that step, so both see the same surfaces; a fresh source copy follows for everything after.
    static void StripRr2dvHiddenMeshes()
    {
        var hidden = RefBody.GetComponentsInChildren<MeshFilter>(true)
            .Where(f => { var r = f.GetComponent<MeshRenderer>(); return !f.gameObject.activeInHierarchy || !r || !r.enabled; }).ToList();
        var names = hidden.Select(f => f.name).ToList();
        foreach (var f in hidden) { var r = f.GetComponent<MeshRenderer>(); if (r) Object.DestroyImmediate(r); Object.DestroyImmediate(f); }
        if (names.Count > 0)
            Line($"rr2dv fittings measured on the visible model: {names.Count} hidden mesh(es) set aside ({string.Join(", ", names.Take(6))}{(names.Count > 6 ? ", ..." : "")})");
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

    // Stock models carry two to four detail levels of most parts (Cab_1_LOD0..LOD3), all enabled in the built car. The core's
    // VisualHits and our own queries read every enabled mesh, so a coarse LOD shell counted as geometry in a cup's space or
    // under a brake release, and a main rod could be the LOD2 copy (S-23, P-48, board 2026-09-30). Only each part's LOD0 counts:
    // the lower levels are switched off for the length of one query and restored afterwards (the saved prefab is untouched).
    static System.Collections.Generic.HashSet<Renderer> Rr2dvLowerLodRenderers(Transform root)
    {
        var lower = new System.Collections.Generic.HashSet<Renderer>();
        var top = new System.Collections.Generic.HashSet<Renderer>();
        foreach (var group in root.GetComponentsInChildren<LODGroup>(true))
        {
            var levels = group.GetLODs();
            for (int i = 0; i < levels.Length; i++)
                foreach (var r in levels[i].renderers)
                    if (r) (i == 0 ? top : lower).Add(r);
        }
        foreach (var r in root.GetComponentsInChildren<Renderer>(true))
            if (System.Text.RegularExpressions.Regex.IsMatch(r.gameObject.name, @"(?i)lod[1-9]\d*$")) lower.Add(r);
        lower.ExceptWith(top);
        return lower;
    }

    sealed class Rr2dvLodScope : IDisposable
    {
        readonly System.Collections.Generic.List<Renderer> off = new System.Collections.Generic.List<Renderer>();
        public Rr2dvLodScope(Transform root)
        {
            foreach (var r in Rr2dvLowerLodRenderers(root)) if (r.enabled) { r.enabled = false; off.Add(r); }
        }
        public void Dispose() { foreach (var r in off) if (r) r.enabled = true; }
    }

    // Diagnostic (K-35's bell cords ran out to infinity in game, 2026-09-30; 10 stock locos have skinned cords): every skinned mesh
    // baked with the loco's animator groups at their first frame, the baked size compared with the mesh's own bounds. A stretched
    // cord shows here in the build report without a game test. BakeMesh's scale handling is unverified, so it only reports.
    static void Rr2dvSkinCheck()
    {
        var skinned = RefBody.GetComponentsInChildren<SkinnedMeshRenderer>(true).Where(s => s.sharedMesh).ToArray();
        if (skinned.Length == 0) return;
        foreach (var a in RefBody.GetComponentsInChildren<Animator>(true))
        {
            var clip = a.runtimeAnimatorController ? a.runtimeAnimatorController.animationClips.FirstOrDefault() : null;
            if (clip) clip.SampleAnimation(a.gameObject, 0f);
        }
        foreach (var s in skinned)
        {
            var baked = new Mesh();
            s.BakeMesh(baked);
            var vs = baked.vertices;
            var lo = new Vector3(1e9f, 1e9f, 1e9f); var hi = new Vector3(-1e9f, -1e9f, -1e9f); bool finite = true;
            foreach (var v in vs)
            {
                if (float.IsNaN(v.x + v.y + v.z) || float.IsInfinity(v.x + v.y + v.z)) { finite = false; continue; }
                lo = Vector3.Min(lo, v); hi = Vector3.Max(hi, v);
            }
            var size = finite && vs.Length > 0 ? hi - lo : Vector3.zero;
            var own = s.sharedMesh.bounds.size;
            float bigOwn = Mathf.Max(own.x, Mathf.Max(own.y, own.z)), bigBaked = Mathf.Max(size.x, Mathf.Max(size.y, size.z));
            string path = AnimationUtility.CalculateTransformPath(s.transform, RefBody);
            Line($"rr2dv skinned {path}: {s.bones.Length} bones, root bone {(s.rootBone ? s.rootBone.name : "none")}, mesh bounds {V(own)}, baked bounds {V(size)}");
            if (!finite || bigBaked > bigOwn * 2f + 0.5f)
                Warn($"rr2dv skinned {path}: the baked mesh is {(finite ? $"{bigBaked:F2} m long against the mesh's own {bigOwn:F2} m" : "not finite")} at the animation's first frame (a stretched cord?)");
            Object.DestroyImmediate(baked);
        }
        foreach (var a in RefBody.GetComponentsInChildren<Animator>(true)) { }
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
            int mainRods = 0;
            using (new Rr2dvLodScope(body))
            using (var hits = new VisualHits(body))
            {
                Rr2dvCupSpacing.Clear();
                var rods = Rr2dvMainRods(body);
                mainRods = rods.Count;
                int pair = 0;
                // cups only at the ends of the main rods, the same end on both sides or neither (James, 2026-09-30)
                foreach (var (l, r) in Rr2dvPairRods(rods))
                    foreach (bool crankEnd in new[] { true, false })
                    {
                        if (pair >= Rr2dvOilPairsMax) break;
                        string end = crankEnd ? "big end" : "small end";
                        // a modelled nub on both sides first (best clearance), else the highest level spot on each rod
                        Transform lhost = l.rod, rhost = r.rod; string how = "main rod " + end;
                        bool nubs = Rr2dvEndNubSeat(hits, body, l, crankEnd, out var lp, out var lnub, out var lnubWhy) &
                                    Rr2dvEndNubSeat(hits, body, r, crankEnd, out var rp, out var rnub, out var rnubWhy);
                        if (nubs) { lhost = lnub; rhost = rnub; how += " (modelled nub)"; }
                        else
                        {
                            Line($"rr2dv oil main rod {end}: no modelled-nub pair ({lnubWhy ?? "left nub found"}; {rnubWhy ?? "right nub found"}); highest level spot instead");
                            if (!Rr2dvRodEndSeat(hits, body, l, crankEnd, out lp, out var lwhy) | !Rr2dvRodEndSeat(hits, body, r, crankEnd, out rp, out var rwhy))
                            {
                                Line($"rr2dv oil main rod {end} pair ({l.rod.name} / {r.rod.name}) omitted: left {lwhy ?? "seat found"}; right {rwhy ?? "seat found"}");
                                continue;
                            }
                        }
                        Rr2dvCupSpacing.Add(lp); Rr2dvCupSpacing.Add(rp);
                        pair++;
                        placed.Add(($"oil_{pair}L", lp, lhost, how));
                        placed.Add(($"oil_{pair}R", rp, rhost, how));
                    }
                if (placed.Count == 0)
                {
                    // no main-rod pair: the running boards, the same axle on both sides or neither (never mixed with rods)
                    Line($"rr2dv oil: no main-rod end pair ({mainRods} main rod(s) found); running-board pairs at the driving axles instead");
                    for (int i = 0; i < hints.Length / 2 && pair < Rr2dvOilPairsMax; i++)
                    {
                        float z = (hints[2 * i].Item2.z + hints[2 * i + 1].Item2.z) / 2;
                        var a = Rr2dvBoardSeat(hits, body, -1, z);
                        var b = a.found ? Rr2dvBoardSeat(hits, body, 1, a.pos.z) : a;
                        if (!a.found || !b.found || Mathf.Abs(a.pos.z - b.pos.z) > .1f)
                        {
                            Line($"rr2dv oil board pair at axle z {z:F3} omitted: no matching running-board seat on {(a.found ? "the right" : "the left")}");
                            continue;
                        }
                        Rr2dvCupSpacing.Add(a.pos); Rr2dvCupSpacing.Add(b.pos);
                        pair++;
                        placed.Add(($"oil_{pair}L", a.pos, null, a.seat));
                        placed.Add(($"oil_{pair}R", b.pos, null, b.seat));
                    }
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
            if (points.Length > 0) Set(oilDefinition, "OilingPointCount", points.Length);
            else
            {
                // No manual oiling (James, 2026-09-29): with no seat at any driving axle, the oiling system keeps one internal
                // point that never drains (no cup, the oil lamp never lights, no running-gear wear), rather than zero points,
                // whose "lowest oil level" Derail Valley may read as empty. Deliberate and reported; the audit accepts it.
                Set(oilDefinition, "OilingPointCount", 1);
                Set(oilDefinition, "consumptionPerRev", 0f);
                Warn("rr2dv oil: no accessible seat at any driving axle: no manual oiling (one internal oiling point that never drains, no cup)");
            }
            oilDefinition.GetType().GetMethod("OnValidate", BF)?.Invoke(oilDefinition, null);
            Line($"rr2dv oil layout: {placed.Count} cups ({mainRods} main rod(s), {hints.Length} provisional axle hints)");
            Line($"rr2dv oil simulation count: {points.Length}");
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    // Oil cups (James, 2026-09-30): only at the ends of the main rods, as a left/right pair on the same end or not at all;
    // the running boards only when no main-rod pair fits, and then on both sides. At most 6 pairs (12 cups: x-4-4-x).
    // The sides' cranks are quartered, so at rest one main rod lies level and the other is pitched: a seat found in the
    // rest pose differed side to side (a nub on one, the board on the other). Each rod is measured in its own level pose
    // (the wheel phase where it lies flattest), against its own mesh only; the seat is then fixed on the rod, and its
    // clearance checked through a whole turn (Rr2dvCupClear).
    const int Rr2dvOilPairsMax = 6;

    class Rr2dvMainRod { public Transform rod; public Vector3 crankEnd, crossEnd; public float side, throwM, crossZ, levelPhase; }

    static System.Collections.Generic.List<Animator> Rr2dvGearAnimators(Transform body) =>
        Cfg.EngineUnits.SelectMany(u => body.GetComponentsInChildren<Animator>(true)
            .Where(a => a.name == $"[anim] {u.GroupName}" || a.name.StartsWith($"[anim] {u.GroupName} "))).Distinct().ToList();

    static void Rr2dvSampleGear(System.Collections.Generic.List<Animator> animators, float phase)
    {
        foreach (var a in animators)
        {
            var clip = a.runtimeAnimatorController ? a.runtimeAnimatorController.animationClips.FirstOrDefault() : null;
            if (clip) clip.SampleAnimation(a.gameObject, phase * clip.length);
        }
        Physics.SyncTransforms();
    }

    // A main rod by how it moves, not what it is called: one end runs on a straight line (the crosshead), the other on a
    // circle (the crank pin). Coupling rods have two circling ends; valve-gear rods are kept out by taking, per side and
    // cylinder, the rod with the largest circle (the crank throw, not an eccentric's).
    static System.Collections.Generic.List<Rr2dvMainRod> Rr2dvMainRods(Transform body)
    {
        const int N = 16;
        var animators = Rr2dvGearAnimators(body);
        var found = new System.Collections.Generic.List<Rr2dvMainRod>();
        var lower = Rr2dvLowerLodRenderers(body);
        var candidates = body.GetComponentsInChildren<MeshFilter>(true).Where(m => m.sharedMesh && m.sharedMesh.vertexCount > 0 &&
            m.GetComponent<MeshRenderer>() && m.GetComponent<MeshRenderer>().enabled && m.gameObject.activeInHierarchy &&
            !lower.Contains(m.GetComponent<MeshRenderer>()) &&
            (Rr2dvIsRod(m.name) || Rr2dvTravels(m.transform))).ToList();
        try
        {
            foreach (var mf in candidates)
            {
                var v = mf.sharedMesh.vertices;
                var c = v.Aggregate(Vector3.zero, (a, b) => a + b) / v.Length;
                var (axes, ext) = Rr2dvPrincipal(v, c);
                if (ext[0] < .8f) continue;   // a main rod is longer than a crank throw and a crosshead
                var wx = v.Select(q => mf.transform.TransformPoint(q).x).ToArray();
                if (wx.Max() - wx.Min() > .4f || Mathf.Abs(wx.Average()) < .3f) continue;   // one side's rod, outside the frames
                var e0 = c + axes[0] * v.Min(p => Vector3.Dot(p - c, axes[0]));
                var e1 = c + axes[0] * v.Max(p => Vector3.Dot(p - c, axes[0]));
                var p0 = new Vector3[N]; var p1 = new Vector3[N]; var tilt = new float[N];
                for (int k = 0; k < N; k++)
                {
                    Rr2dvSampleGear(animators, k / (float)N);
                    p0[k] = mf.transform.TransformPoint(e0); p1[k] = mf.transform.TransformPoint(e1);
                    tilt[k] = Mathf.Abs((p1[k] - p0[k]).normalized.y);
                }
                float Ry(Vector3[] p) => p.Max(q => q.y) - p.Min(q => q.y);
                float Rz(Vector3[] p) => p.Max(q => q.z) - p.Min(q => q.z);
                bool Circle(Vector3[] p) => Ry(p) > .1f && Rz(p) > .1f;
                // The crosshead end of F-71's and C-55's main rod wanders 3.5-3.7 cm in height over a turn (the oil-cup map of all 21 locos,
                // 2026-10-01), so a line is up to 4.5 cm; and a crank throw is at least 0.2 m (every real main rod measured 0.27-0.43 m;
                // the 0.05-0.11 m "main rods" kept on A-26, P-18, P-43 and C-40 were eccentric and valve-gear rods).
                bool Line_(Vector3[] p) => Ry(p) < .045f && Rz(p) > .1f;
                bool crank0 = Circle(p0) && Line_(p1), crank1 = Circle(p1) && Line_(p0);
                if (!crank0 && !crank1) continue;
                if (Ry(crank0 ? p0 : p1) / 2 < .2f) continue;
                var cross = crank0 ? p1 : p0;
                int level = Enumerable.Range(0, N).OrderBy(k => tilt[k]).First();
                found.Add(new Rr2dvMainRod { rod = mf.transform, crankEnd = crank0 ? e0 : e1, crossEnd = crank0 ? e1 : e0,
                    side = Mathf.Sign(mf.transform.TransformPoint(c).x), throwM = Ry(crank0 ? p0 : p1) / 2,
                    crossZ = cross.Average(q => q.z), levelPhase = level / (float)N });
            }
        }
        finally { Rr2dvSampleGear(animators, 0); }
        // one per side and cylinder (crosshead within 0.5 m): the biggest circle is the crank, a smaller one an eccentric
        var kept = found.GroupBy(m => (m.side, Mathf.Round(m.crossZ / .5f))).Select(g => g.OrderByDescending(m => m.throwM).First()).ToList();
        foreach (var m in kept)
            Line($"rr2dv oil main rod {m.rod.name}: {(m.side < 0 ? "left" : "right")}, crank throw {m.throwM:F3} m, crosshead z {m.crossZ:F3}, level at phase {m.levelPhase:F3}");
        foreach (var m in found.Except(kept)) Line($"rr2dv oil rod {m.rod.name}: not a main rod (smaller circle {m.throwM:F3} m beside a main rod)");
        return kept;
    }

    // left/right main rods of the same cylinder (crossheads within 0.3 m along the car); a rod with no partner gets no cup
    static System.Collections.Generic.List<(Rr2dvMainRod l, Rr2dvMainRod r)> Rr2dvPairRods(System.Collections.Generic.List<Rr2dvMainRod> rods)
    {
        var pairs = new System.Collections.Generic.List<(Rr2dvMainRod, Rr2dvMainRod)>();
        var right = rods.Where(m => m.side > 0).ToList();
        foreach (var l in rods.Where(m => m.side < 0).OrderByDescending(m => m.crossZ))
        {
            var r = right.OrderBy(m => Mathf.Abs(m.crossZ - l.crossZ)).FirstOrDefault();
            if (r == null || Mathf.Abs(r.crossZ - l.crossZ) > .3f) { Line($"rr2dv oil main rod {l.rod.name}: no right-hand partner, no cup"); continue; }
            right.Remove(r);
            pairs.Add((l, r));
        }
        foreach (var r in right) Line($"rr2dv oil main rod {r.rod.name}: no left-hand partner, no cup");
        return pairs;
    }

    // The seat at one end of a main rod, in the rod's own level pose, on the rod's own surface: the highest level spot
    // within 0.3 m of the end (a boss, a nub or the flat of the rod: any space at all), with a 4 x 3 cm level footprint.
    // Returned where it is at rest (the cup is parented to the rod, so it rides with it), after the clearance check.
    static bool Rr2dvRodEndSeat(VisualHits hits, Transform body, Rr2dvMainRod m, bool crankEnd, out Vector3 pos, out string why)
    {
        pos = Vector3.zero; why = null;
        var animators = Rr2dvGearAnimators(body);
        Vector3 local = Vector3.zero; bool ok = false;
        try
        {
            Rr2dvSampleGear(animators, m.levelPhase);
            var e = m.rod.TransformPoint(crankEnd ? m.crankEnd : m.crossEnd);
            var o = m.rod.TransformPoint(crankEnd ? m.crossEnd : m.crankEnd);
            var inward = new Vector3(o.x - e.x, 0, o.z - e.z).normalized;
            var across = Vector3.Cross(Vector3.up, inward).normalized;
            float best = float.MinValue;
            for (float t = 0; t <= .3f; t += .01f)
                for (float u = -.06f; u <= .061f; u += .01f)
                {
                    var origin = e + inward * t + across * u + Vector3.up * .5f;
                    if (!hits.Ray(origin, Vector3.down, 1f, out var hit, m.rod) || hit.normal.y < .9f || hit.point.y <= best) continue;
                    bool footprint = true;
                    foreach (var d in new[] { inward * .02f, -inward * .02f, across * .015f, -across * .015f })
                        if (!hits.Ray(origin + d, Vector3.down, 1f, out var edge, m.rod) || edge.normal.y < .9f || Mathf.Abs(edge.point.y - hit.point.y) > .006f)
                            footprint = false;
                    if (!footprint) continue;
                    best = hit.point.y;
                    local = m.rod.InverseTransformPoint(hit.point + Vector3.up * (CupPivotAboveBase - CupSeatSink));
                    ok = true;
                }
        }
        finally { Rr2dvSampleGear(animators, 0); }
        if (!ok) { why = "no level spot on the rod within 0.3 m of the end"; return false; }
        pos = m.rod.TransformPoint(local);
        if (!Rr2dvCupSpaced(pos)) { why = "too close to another cup"; return false; }
        if (!Rr2dvCupClear(hits, body, pos, m.rod, out var clash)) { why = "something visible in the cup's space: " + clash; return false; }
        return true;
    }

    // A cup on the best-clearance modelled nub around a main-rod end (James, 2026-10-01), in the rod's own level pose with the whole gear at
    // that phase; the seat is kept in its host part's own space, so the cup rides that part (the side rod's pin cap as much as the rod).
    static bool Rr2dvEndNubSeat(VisualHits hits, Transform body, Rr2dvMainRod m, bool crankEnd, out Vector3 pos, out Transform host, out string why)
    {
        pos = Vector3.zero; host = null; why = null;
        var animators = Rr2dvGearAnimators(body);
        Vector3 local = Vector3.zero; string summary = null; Rr2dvOilNubs.Candidate best = null;
        try
        {
            Rr2dvSampleGear(animators, m.levelPhase);
            var end = m.rod.TransformPoint(crankEnd ? m.crankEnd : m.crossEnd);
            var found = Rr2dvOilNubs.Find(
                (Vector3 o, Vector3 d, float dist, out RaycastHit h) => hits.Ray(o, d, dist, out h, null),
                end, .3f, CupPivotAboveBase - CupSeatSink, t => Rr2dvTravels(t),
                (p, t, r) => Rr2dvCupClear(hits, body, p, t, out var w, r) ? null : w,
                Rr2dvCupSpaced, out summary);
            if (found.Count > 0) { best = found[0]; local = best.local; host = best.host; }
        }
        finally { Rr2dvSampleGear(animators, 0); }
        if (best == null) { why = "no modelled nub with clear space (" + summary + ")"; return false; }
        pos = host.TransformPoint(local);
        Line($"rr2dv oil nub on {host.name} for {m.rod.name} {(crankEnd ? "big" : "small")} end: rise {best.rise * 1000:F0} mm, clear to a {best.margin * 100:F1} cm radius ({summary})");
        return true;
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
            if (!Rr2dvCupSpaced(pos) || !Rr2dvCupClear(hits, body, pos, null, out _)) continue;
            return (true, pos, null, "running board on " + hit.collider.transform.parent.name);
        }
        return (false, Vector3.zero, null, null);
    }

    // The oil cup's own space, which nothing visible may enter except the surface it stands on (James, 2026-09-29: cups
    // clipped into rods and linkages, or had rods through them): a 3.5 cm radius, 9 cm tall above its base. Checked with
    // short rays across and up through that space, at four phases of the driving wheels' turn (a rod swinging through it
    // later counts); a cup riding a moving part moves with it.
    const float CupClearRadius = .035f, CupClearHeight = .09f, CupSpacing = .12f;
    static readonly System.Collections.Generic.List<Vector3> Rr2dvCupSpacing = new System.Collections.Generic.List<Vector3>();
    static bool Rr2dvCupSpaced(Vector3 pos) => Rr2dvCupSpacing.All(p => Vector3.Distance(p, pos) >= CupSpacing);

    static bool Rr2dvCupClear(VisualHits hits, Transform body, Vector3 pos, Transform rider, out string why, float radius = CupClearRadius)
    {
        why = null;
        var local = rider ? rider.InverseTransformPoint(pos) : pos;
        var animators = Cfg.EngineUnits.SelectMany(u => body.GetComponentsInChildren<Animator>(true)
            .Where(a => a.name == $"[anim] {u.GroupName}" || a.name.StartsWith($"[anim] {u.GroupName} "))).Distinct().ToList();
        try
        {
            foreach (var phase in new[] { 0f, .125f, .25f, .375f, .5f, .625f, .75f, .875f })
            {
                foreach (var a in animators)
                {
                    var clip = a.runtimeAnimatorController ? a.runtimeAnimatorController.animationClips.FirstOrDefault() : null;
                    if (clip) clip.SampleAnimation(a.gameObject, phase * clip.length);
                }
                Physics.SyncTransforms();
                var p = rider ? rider.TransformPoint(local) : pos;
                var baseY = p.y - CupPivotAboveBase + CupSeatSink;
                var centre = new Vector3(p.x, baseY, p.z);
                // up through the cup from just above its base, at the centre and around the rim
                foreach (var o in new[] { Vector3.zero, new Vector3(radius, 0, 0), new Vector3(-radius, 0, 0), new Vector3(0, 0, radius), new Vector3(0, 0, -radius) })
                    if (hits.Ray(centre + o + Vector3.up * .006f, Vector3.up, CupClearHeight, out var h, body))
                    { why = $"{h.collider.transform.parent.name} above it at phase {phase:F2}"; return false; }
                // down onto it from above its top (a ray that starts inside a part does not see that part)
                foreach (var o in new[] { Vector3.zero, new Vector3(radius, 0, 0), new Vector3(-radius, 0, 0), new Vector3(0, 0, radius), new Vector3(0, 0, -radius) })
                    if (hits.Ray(centre + o + Vector3.up * (CupClearHeight + .04f), Vector3.down, CupClearHeight + .04f - .006f, out var h, body))
                    { why = $"{h.collider.transform.parent.name} over it at phase {phase:F2}"; return false; }
                // across the cup at three heights, from well outside its rim inward, both ways
                foreach (float y in new[] { .02f, .045f, .075f })
                    foreach (var d in new[] { Vector3.right, Vector3.left, Vector3.forward, Vector3.back })
                        if (hits.Ray(centre + Vector3.up * y + d * 3 * radius, -d, 4 * radius, out var h, body) &&
                            Vector3.Distance(new Vector3(h.point.x, 0, h.point.z), new Vector3(centre.x, 0, centre.z)) <= radius)
                        { why = $"{h.collider.transform.parent.name} inside it at phase {phase:F2}"; return false; }
            }
            return true;
        }
        finally
        {
            foreach (var a in animators)
            {
                var clip = a.runtimeAnimatorController ? a.runtimeAnimatorController.animationClips.FirstOrDefault() : null;
                if (clip) clip.SampleAnimation(a.gameObject, 0);
            }
            Physics.SyncTransforms();
        }
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
            using (new Rr2dvLodScope(body))
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
            using (new Rr2dvLodScope(body))
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
            using (new Rr2dvLodScope(RefBody))
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
