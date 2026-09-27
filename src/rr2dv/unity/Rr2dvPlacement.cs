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
        BuildExterior();
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
