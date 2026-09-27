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
// The snapshot remains unchanged. No vehicle IDs or model-specific offsets belong here.
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
        matMap = BuildMaterials(Livery);
        CreateCar();
        SeatRr2dvFallbackOil();
        BuildExterior();
        AlignRr2dvBogieSupports();
        SeatRr2dvPlates();
        if (!c.IsTender) { BuildInterior(); SeatRr2dvControls(); BuildInteriorLOD(); }
        BuildInteractables();
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

    static void SeatRr2dvFallbackOil()
    {
        if (Cfg.IsTender || Cfg.OilPoints == null || Cfg.RodOilers != null || Cfg.OilAnchors != null) return;
        var points = Cfg.OilPoints(RefBody).ToArray();
        if (points.Length != Cfg.EngineUnits.Sum(u => u.DriverParts.Length) * 2)
            throw new InvalidOperationException("Fallback oil cups must cover every driving axle on both sides");
        using (var hits = new VisualHits(RefBody))
        for (int i = 0; i < points.Length; i++)
        {
            var point = points[i];
            float side = Mathf.Sign(point.Item2.x);
            bool found = false;
            // Search the outboard horizontal surface nearest the axle, requiring a full cup footprint.
            // Never leave a point at the old estimated height inside the vehicle.
            for (float x = 1.65f; x >= .8f && !found; x -= .025f)
            for (int dz = 0; dz < 9 && !found; dz++)
            {
                float z = point.Item2.z + (dz == 0 ? 0 : (dz % 2 == 0 ? -1 : 1) * ((dz + 1) / 2) * .05f);
                var origin = new Vector3(side * x, 2 * WheelRadius + 1.2f, z);
                if (!hits.Ray(origin, Vector3.down, 1.8f, out var hit, RefBody) || hit.normal.y < .97f) continue;
                bool footprint = true;
                foreach (var offset in new[] { new Vector3(.045f, 0, 0), new Vector3(-.045f, 0, 0), new Vector3(0, 0, .045f), new Vector3(0, 0, -.045f) })
                    if (!hits.Ray(origin + offset, Vector3.down, 1.8f, out var edge, RefBody) || edge.normal.y < .97f || Mathf.Abs(edge.point.y - hit.point.y) > .01f) footprint = false;
                if (!footprint) continue;
                var pos = hit.point + Vector3.up * (CupPivotAboveBase - CupSeatSink);
                // Space above the cup and a clear outward approach are necessary for access.
                if (hits.Ray(pos + Vector3.up * .08f, Vector3.up, .12f, out var overhead, RefBody)) continue;
                if (hits.Ray(pos + Vector3.up * .08f, Vector3.right * side, .6f, out var sideHit, RefBody)) continue;
                points[i] = (point.Item1, pos);
                Line($"rr2dv fallback oil {point.Item1}: {V(point.Item2)} -> {V(pos)} on {hit.collider.transform.parent.name}");
                found = true;
            }
            if (!found) throw new InvalidOperationException("No accessible running-board seat for oil cup " + point.Item1);
        }
        Cfg.OilPoints = root => points;
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
                var axles = bogie.Cast<Transform>().Where(t => t.name == "[axle]").Select(t => root.transform.InverseTransformPoint(t.position).z).ToArray();
                if (axles.Length == 0) throw new InvalidOperationException("No support axles");
                float z = front ? axles.Max() : axles.Min();
                float radius = WheelRadius;
                var ws = Cfg.Wheelsets.Where(w => w.axles > 0).OrderBy(w => Mathf.Abs(z - (w.offset + (front ? 1 : -1) * (w.axles > 1 ? w.length / 2 : 0)))).First();
                bool reviewedPowered = RrChoices != null && RrChoices.physics == "geared" &&
                    (RrChoices.poweredWheelsets ?? new int[0]).Contains(Array.IndexOf(Cfg.Wheelsets, ws));
                if (!Cfg.IsTender && !reviewedPowered && !Cfg.EngineUnits.Any(u => u.AnimKey == ws.clip))
                    radius = Cfg.PonyRadii.TryGetValue(ws.clip ?? "", out var measured) ? measured : ws.diameter / 2;
                if (radius <= 0) throw new InvalidOperationException("Invalid end-wheel support radius");
                var support = root.transform.Find("[colliders]/[bogies]/" + (front ? "front" : "rear"));
                var collider = support.GetComponent<CapsuleCollider>();
                if (!collider) throw new InvalidOperationException("Missing bogie support capsule");
                var oldCentre = collider.center;
                collider.center = Vector3.zero;
                collider.radius = radius;
                collider.height = Mathf.Max(collider.height, radius * 2);
                support.position = root.transform.TransformPoint(new Vector3(0, radius, z));
                Line($"rr2dv support {support.name}: donor centre {V(oldCentre)} cleared; car centre (0,{radius:F5},{z:F5}), radius {radius:F5}, rail contact y=0");
            }
            SaveRr2dvPrefab(root, path);
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
                var origin = new Vector3(side * 3f, source.pos.y, source.pos.z);
                if (!hits.Ray(origin, new Vector3(-side, 0, 0), 3f, out var hit, body))
                    throw new InvalidOperationException("No visible surface for plate " + pair.Item1);
                if (hit.normal.x * side < .5f)
                    throw new InvalidOperationException("Plate surface does not face outward: " + pair.Item1);
                var old = anchor.localPosition;
                anchor.localPosition = new Vector3(hit.point.x + side * .01f, source.pos.y, source.pos.z);
                Line($"rr2dv visible plate {pair.Item1}: {V(old)} -> {V(anchor.localPosition)} on {hit.collider.transform.parent.name}");
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
                if (!hits.Ray(labelOrigin, Vector3.forward, 1f, out var labelHit, RefBody) || labelHit.normal.z > -.5f)
                    throw new InvalidOperationException("No visible surface for generated label " + spec.Label);
                label.localPosition = new Vector3(labelOrigin.x, labelOrigin.y, labelHit.point.z - .016f);
            }
            Section("rr2dv control sweep after visible-surface placement");
            SweepCheck(root.transform.Find("Controls"));
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }
}
