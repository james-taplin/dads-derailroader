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
        CreateCar();
        BuildExterior();
        FinishRr2dvMaterialSlots();
        SeatRr2dvOilCups();
        AlignRr2dvBogieSupports();
        SeatRr2dvPlates();
        AlignRr2dvDefaultPlates();
        if (!c.IsTender) { BuildInterior(); SeatRr2dvControls(); FinishRr2dvInteriorControls(); BuildInteriorLOD(); }
        BuildInteractables();
        BuildRr2dvAncillaries();
        var sound = c.IsTender ? null : BuildSound();
        ConfigureAssets(sound);
        builtFolders[c] = carFolder;
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
            var nubs = Rr2dvRodNubs(body);
            using (var hits = new VisualHits(body))
            {
                var remaining = nubs.Where(n => n.pos.x > 0).ToList();
                int pair = 0;
                foreach (var left in nubs.Where(n => n.pos.x < 0))
                {
                    var right = remaining.OrderBy(n => Mathf.Abs(n.pos.z - left.pos.z)).FirstOrDefault();
                    if (right.rod && Mathf.Abs(right.pos.z - left.pos.z) <= .45f) remaining.Remove(right);
                    else right = (null, Vector3.zero);
                    pair++;
                    Rr2dvAddOilPair(placed, hits, body, pair,
                        (left.rod, left.pos), (right.rod, right.pos), (left.pos.z + (right.rod ? right.pos.z : left.pos.z)) / 2);
                }
                foreach (var right in remaining)
                {
                    pair++;
                    Rr2dvAddOilPair(placed, hits, body, pair, (null, Vector3.zero),
                        (right.rod, right.pos), right.pos.z);
                }
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

    static void Rr2dvAddOilPair(System.Collections.Generic.List<(string tag, Vector3 pos, Transform rod, string seat)> placed,
        VisualHits hits, Transform body, int pair, (Transform rod, Vector3 pos) left, (Transform rod, Vector3 pos) right, float z)
    {
        var a = left.rod && Rr2dvRodSeatAccessible(hits, body, left.pos)
            ? (true, left.pos, left.rod, "rod big end") : Rr2dvBoardSeat(hits, body, -1, z);
        var b = right.rod && Rr2dvRodSeatAccessible(hits, body, right.pos)
            ? (true, right.pos, right.rod, "rod big end") : Rr2dvBoardSeat(hits, body, 1, z);
        if (!a.Item1 || !b.Item1)
        {
            Line($"rr2dv oil pair {pair} omitted: no accessible {(a.Item1 ? "right" : b.Item1 ? "left" : "left or right")} rod/board seat");
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
        foreach (var mf in body.GetComponentsInChildren<MeshFilter>(true).Where(m => Rr2dvIsRod(m.name)))
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
                if (group.Count < 35) { small++; continue; }
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
            Line($"rr2dv oil rod {mf.name}: {found} nub(s); islands rejected: {small} under 35 triangles, {wrongSize} outside 3.5-30 cm, " +
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
                // Search nearest to the source label, then verify the entire native plate footprint.
                var candidates = new System.Collections.Generic.List<Vector3>();
                for (float z = extent.min.z + footprint.extents.z; z <= extent.max.z - footprint.extents.z; z += .05f)
                for (int y = -10; y <= 10; y++) candidates.Add(new Vector3(side * outside, source.pos.y + y * .05f, z));
                candidates.Insert(0, new Vector3(side * outside, source.pos.y, source.pos.z));
                bool found = false; RaycastHit hit = new RaycastHit();
                foreach (var origin in candidates.OrderBy(p => Mathf.Pow(p.y-source.pos.y,2) + Mathf.Pow(p.z-source.pos.z,2)))
                {
                    if (!hits.Ray(origin, Vector3.left * side, outside, out hit, body) || hit.normal.x * side < .995f) continue;
                    bool supported = true;
                    int ny = Mathf.CeilToInt(footprint.size.y / .1f), nz = Mathf.CeilToInt(footprint.size.z / .1f);
                    for (int iy = 0; iy <= ny && supported; iy++)
                    for (int iz = 0; iz <= nz; iz++)
                    {
                        var sample = origin + new Vector3(0, Mathf.Lerp(-footprint.extents.y, footprint.extents.y, (float)iy/ny), Mathf.Lerp(-footprint.extents.z, footprint.extents.z, (float)iz/nz));
                        if (!hits.Ray(sample, Vector3.left * side, outside, out var edge, body) || edge.collider != hit.collider ||
                            edge.normal.x * side < .995f || Mathf.Abs(edge.point.x-hit.point.x) > .008f) { supported = false; break; }
                    }
                    if (supported) { found = true; break; }
                }
                if (!found) throw new InvalidOperationException("No fully supported visible surface for plate " + pair.Item1);
                var old = anchor.localPosition;
                anchor.position = hit.point + Vector3.right * side * .01f;
                anchor.localRotation = Quaternion.Euler(0, side > 0 ? 0 : 180, 0);
                Line($"rr2dv visible plate {pair.Item1}: {V(old)} -> {V(anchor.localPosition)} on {hit.collider.transform.parent.name}; full {footprint.size.y:F3} x {footprint.size.z:F3} m footprint supported");
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
