using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using CCL.Types.Components;
using CCL.Types.Proxies.Controls;
using CCL.Types.Proxies.Indicators;
using CCL.Types.HUD;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

[InitializeOnLoad]
static class PressuremeterPlayBootstrap
{
    static PressuremeterPlayBootstrap()
    {
        if (SessionState.GetBool("rr2dv pressure play armed", false))
            EditorApplication.delayCall += () => CclLocoBuild.PressuremeterRuntimeRegression();
    }
}

public static partial class CclLocoBuild
{
    static void PressureAssert(bool pass, string message) { if (!pass) throw new Exception(message); }
    static string PressureOutput => Environment.GetEnvironmentVariable("CCL_BUILD_OUT");
    static readonly string[] PressureResources = { "s060_gauge_pressuremeter", "s060_gauge_label_pressuremeter",
        "s060_gauge_glass_pressuremeter", "s060_needle_pressuremeter" };

    public static void PressuremeterRegression()
    {
        try
        {
            Directory.CreateDirectory(PressureOutput);
            Cfg = new LocoConfig { CarId = "RR2DV_LS_280_C25", Work = "Assets/PressuremeterRegression", MainPressureGauge = "Boiler Gauge" };
            carFolder = Cfg.Work; Folder(carFolder); BuildOwnAssets();
            var root = new GameObject(CarId + "_interior"); var hudReader = root.AddComponent<LocoIndicatorReaderProxy>();
            var speedHost = Child(root.transform, "HUD speed", Vector3.zero);
            hudReader.speed = speedHost.gameObject.AddComponent<IndicatorGaugeProxy>();
            speedHost.gameObject.AddComponent<IndicatorPortReaderProxy>().portId = "traction.WHEEL_SPEED_KMH_EXT_IN";
            var old = Child(root.transform, "gauge Boiler Gauge", Vector3.zero);
            Child(old, "old generated dial", Vector3.zero);
            Child(root.transform, "gauge Brake Gauge", Vector3.zero);
            Child(root.transform, "gauge preserved reservoir", new Vector3(.4f, 3.5f, -2.4f));
            SaveRr2dvPrefab(root, $"{carFolder}/{CarId}_interior.prefab"); Object.DestroyImmediate(root);
            root = new GameObject(CarId + "_template");
            SaveRr2dvPrefab(root, $"{carFolder}/{CarId}_template.prefab"); Object.DestroyImmediate(root);
            var hudLayout = ScriptableObject.CreateInstance<VanillaHUDLayout>();
            hudLayout.HUDType = VanillaHUDLayout.BaseHUD.S060;
            string hudPath = $"{carFolder}/{CarId}_hud.asset";
            if (AssetDatabase.LoadAssetAtPath<VanillaHUDLayout>(hudPath)) AssetDatabase.DeleteAsset(hudPath);
            AssetDatabase.CreateAsset(hudLayout, hudPath);
            RequireRr2dvSpeedHud();
            PressureAssert(hudLayout.HUDType == VanillaHUDLayout.BaseHUD.S282, "Tank HUD fallback did not use S282 speed box");
            hudLayout.HUDType = VanillaHUDLayout.BaseHUD.Custom;
            hudLayout.CustomHUDSettings.SetToS();
            hudLayout.CustomHUDSettings.BasicControls.Speedometer = CustomHUDLayout.ShouldDisplay.None;
            RequireRr2dvSpeedHud();
            hudLayout.AfterImport();
            PressureAssert(hudLayout.HUDType == VanillaHUDLayout.BaseHUD.Custom &&
                hudLayout.CustomHUDSettings.BasicControls.Speedometer == CustomHUDLayout.ShouldDisplay.Display,
                "Custom steam HUD lost its numerical speed box after serialization");
            var source = new GameObject("source"); var engine = Child(source.transform, "engine", Vector3.zero);
            var panel = GameObject.CreatePrimitive(PrimitiveType.Cube); panel.name = "Interior.007_LOD0.003";
            panel.transform.SetParent(engine, false); panel.transform.position = new Vector3(0, 3.5f, -2.4241722f);
            panel.transform.localScale = new Vector3(.6f, .8f, .02f); Object.DestroyImmediate(panel.GetComponent<Collider>());
            refBody = source.transform;
            BuildRr2dvGauges(); BuildRr2dvGauges(); BuildInteriorLOD(); RestoreRr2dvGaugeLodGrabbers(); RestoreRr2dvGaugeLodGrabbers();
            var interior = AssetDatabase.LoadAssetAtPath<GameObject>($"{carFolder}/{CarId}_interior.prefab");
            var readings = interior.GetComponent<LocoIndicatorReaderProxy>();
            PressureAssert(readings.mainReservoir && readings.mainReservoir.GetComponentsInChildren<Renderer>(true).Length == 0,
                "Missing physical reservoir must retain an invisible HUD reading");
            PressureAssert(readings.mainReservoir.GetComponent(T("CCL.Types.Proxies.Indicators.IndicatorBrakeReservoirReaderProxy")),
                "HUD-only reservoir has no standard brake reservoir reader");
            PressureAssert(interior.GetComponentsInChildren<Transform>(true).Count(t => t.name == "HUD-only mainReservoir") == 1,
                "Repeated HUD finishing duplicated the reservoir reader");
            CheckPressureProxy(interior.transform.Find("gauge Boiler Gauge"), true);
            PressureAssert(interior.transform.Find("gauge preserved reservoir"), "Unrelated reservoir instrument was removed");
            var template = AssetDatabase.LoadAssetAtPath<GameObject>($"{carFolder}/{CarId}_template.prefab");
            CheckPressureProxy(template.transform.Find("[interior LOD]/gauge Boiler Gauge"), false);
            // Resource failure is explicit. Never substitute copied game data or a generated face.
            bool missingRejected = false;
            try { S060GaugePart(source.transform, "missing", "not-a-vanilla-mesh", "LocoS060_Gauges", Vector3.zero); }
            catch (InvalidDataException) { missingRejected = true; }
            PressureAssert(missingRejected, "Missing donor mesh was silently accepted");
            var fit = ReadRr2dvGaugeSelection().instruments[0]; fit.position[2] += .1f;
            bool intersectionRejected = false;
            try { ValidateRr2dvGaugeSupport(fit); } catch (InvalidDataException) { intersectionRejected = true; }
            PressureAssert(intersectionRejected, "Bad pilot support was silently accepted");
            Object.DestroyImmediate(source); refBody = null;
            var paths = new[] { $"{carFolder}/{CarId}_interior.prefab", $"{carFolder}/{CarId}_template.prefab", hudPath };
            AssetDatabase.SaveAssets();
            var dependencies = AssetDatabase.GetDependencies(paths, true);
            PressureAssert(!dependencies.Any(p => PressureResources.Any(r => Path.GetFileNameWithoutExtension(p) == r)),
                "Donor mesh bytes were embedded in the exported assets");
            string bundles = Path.Combine(PressureOutput, "bundles"); Directory.CreateDirectory(bundles);
            BuildPipeline.BuildAssetBundles(bundles, new[] { new AssetBundleBuild {
                assetBundleName = "pressuremeter", assetNames = paths } },
                BuildAssetBundleOptions.ForceRebuildAssetBundle, BuildTarget.StandaloneWindows64);
            var bundle = AssetBundle.LoadFromFile(Path.Combine(bundles, "pressuremeter"));
            PressureAssert(bundle, "Pressuremeter bundle could not reload");
            CheckPressureProxy(bundle.LoadAsset<GameObject>(paths[0]).transform.Find("gauge Boiler Gauge"), true);
            CheckPressureProxy(bundle.LoadAsset<GameObject>(paths[1]).transform.Find("[interior LOD]/gauge Boiler Gauge"), false);
            var exportedHud = bundle.LoadAsset<VanillaHUDLayout>(hudPath); exportedHud.AfterImport();
            PressureAssert(exportedHud.CustomHUDSettings.BasicControls.Speedometer == CustomHUDLayout.ShouldDisplay.Display,
                "Exported HUD lacks the numerical speed box");
            var exportedSpeed = bundle.LoadAsset<GameObject>(paths[0]).GetComponent<LocoIndicatorReaderProxy>().speed;
            PressureAssert(exportedSpeed.GetComponent<IndicatorPortReaderProxy>().useAbsoluteValue,
                "Reverse speed is not configured as numerical km/h magnitude");
            PressureAssert(!bundle.LoadAllAssets<Mesh>().Any(m => PressureResources.Contains(m.name)), "Bundle includes donor meshes");
            bundle.Unload(true);
            SessionState.SetBool("rr2dv pressure play armed", true);
            EditorApplication.isPlaying = true;
        }
        catch (Exception e) { PressureFailure(e); }
    }

    static void CheckPressureProxy(Transform gauge, bool live)
    {
        PressureAssert(gauge, "Pressuremeter is missing");
        var mesh = gauge.GetComponentsInChildren<MeshGrabberFilter>(true);
        PressureAssert(mesh.Length == 4 && mesh.All(g => g.Filter && !g.Filter.sharedMesh), "Donor mesh references are missing or baked");
        PressureAssert(PressureResources.All(n => mesh.Count(g => g.ReplacementName == n) == 1), "Donor part selection differs");
        foreach (var material in gauge.GetComponentsInChildren<MaterialGrabberRenderer>(true))
        {
            material.AfterImport(); string error;
            PressureAssert(material.IsValid(out error), "Invalid material grabber: " + error);
            PressureAssert(material.RenderersToAffect.Length == 1 && material.RenderersToAffect[0].transform.IsChildOf(gauge), "LOD material reference escaped its assembly");
        }
        var proxy = gauge.GetComponentInChildren<IndicatorGaugeProxy>();
        PressureAssert(live ? proxy && proxy.needle && proxy.needle.parent == gauge : !proxy, "Needle/pivot or render-only LOD wiring differs");
        if (live)
        {
            PressureAssert(proxy.minValue == 1 && proxy.maxValue == 19 && proxy.minAngle == -135 && proxy.maxAngle == 135 && proxy.rotationAxis == Vector3.back,
                "Donor absolute-pressure calibration changed");
            var reader = proxy.GetComponent<IndicatorPortReaderProxy>();
            PressureAssert(reader && reader.portId == "boiler.PRESSURE" && reader.valueMultiplier == 1 && reader.valueOffset == 0,
                "Boiler port wiring changed");
        }
    }

    static void SetPressureField(object obj, string name, object value)
    {
        var type = obj.GetType(); FieldInfo field = null;
        while (type != null && field == null) { field = type.GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly); type = type.BaseType; }
        if (field == null) throw new Exception("Missing runtime field " + name);
        field.SetValue(obj, value);
    }

    public static void PressuremeterRuntimeRegression()
    {
        if (!SessionState.GetBool("rr2dv pressure play armed", false)) return;
        SessionState.SetBool("rr2dv pressure play armed", false);
        AssetBundle bundle = null; GameObject root = null, lodRoot = null;
        ResolveEventHandler resolver = (sender, args) => {
            string name = new AssemblyName(args.Name).Name + ".dll";
            foreach (var folder in new[] { Environment.GetEnvironmentVariable("RR2DV_GAME_MANAGED"),
                Path.Combine(Environment.GetEnvironmentVariable("RR2DV_GAME_MANAGED"), "UnityModManager"),
                Path.Combine(Path.GetDirectoryName(Environment.GetEnvironmentVariable("RR2DV_CCL_RUNTIME")), "DVLangHelper"),
                Environment.GetEnvironmentVariable("RR2DV_CCL_RUNTIME") })
                if (File.Exists(Path.Combine(folder, name))) return Assembly.LoadFrom(Path.Combine(folder, name));
            return null;
        };
        try
        {
            PressureAssert(Application.isPlaying, "Real importer/indicator test must run in Play Mode");
            AppDomain.CurrentDomain.AssemblyResolve += resolver;
            var game = Assembly.LoadFrom(Path.Combine(Environment.GetEnvironmentVariable("RR2DV_GAME_MANAGED"), "Assembly-CSharp.dll"));
            var importer = Assembly.LoadFrom(Path.Combine(Environment.GetEnvironmentVariable("RR2DV_CCL_RUNTIME"), "CCL.Importer.dll"));
            var processor = importer.GetType("CCL.Importer.Processing.GrabberProcessor", true);
            var donorMeshes = GaugeProbe.ReadMeshes(Environment.GetEnvironmentVariable("RR2DV_PRESSURE_MESHES"));
            var meshes = donorMeshes.ToDictionary(m => m.name, m => m);
            var materials = new[] { "LocoS060_Interior", "LocoS060_Gauges", "GlassIndoors" }
                .ToDictionary(n => n, n => new Material(Shader.Find("Standard")) { name = n });
            foreach (var entry in new[] { new object[] { "s_meshCache", meshes }, new object[] { "s_materialCache", materials } })
            {
                var cache = processor.GetField((string)entry[0], BindingFlags.Static | BindingFlags.NonPublic).GetValue(null);
                cache.GetType().GetField("_cachedResources", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(cache, entry[1]);
            }
            bundle = AssetBundle.LoadFromFile(Path.Combine(PressureOutput, "bundles/pressuremeter"));
            var prefab = bundle.LoadAllAssets<GameObject>().Single(g => g.name.EndsWith("_interior"));
            root = Object.Instantiate(prefab); root.SetActive(false);
            lodRoot = Object.Instantiate(bundle.LoadAllAssets<GameObject>().Single(g => g.name.EndsWith("_template")));
            lodRoot.SetActive(false);
            foreach (var assemblyRoot in new[] { root, lodRoot })
                foreach (string method in new[] { "ProcessMeshGrabberFilter", "ProcessMaterialGrabberRenderer" })
                    processor.GetMethod(method, BindingFlags.Static | BindingFlags.NonPublic).Invoke(null, new object[] { assemblyRoot });
            var gauge = root.transform.Find("gauge Boiler Gauge");
            foreach (var assembly in new[] { gauge, lodRoot.transform.Find("[interior LOD]/gauge Boiler Gauge") })
            {
                foreach (var filter in assembly.GetComponentsInChildren<MeshFilter>(true).Where(f => f.name != "mounting pad"))
                    PressureAssert(filter.sharedMesh && meshes.ContainsKey(filter.sharedMesh.name), "Actual CCL importer failed to bind donor mesh");
                foreach (var renderer in assembly.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.name != "mounting pad"))
                    PressureAssert(materials.Values.Contains(renderer.sharedMaterial), "Actual CCL importer failed to bind donor material");
            }
            var proxy = gauge.GetComponentInChildren<IndicatorGaugeProxy>(true);
            var runtime = proxy.gameObject.AddComponent(game.GetType("IndicatorGauge", true));
            foreach (var name in new[] { "needle", "minValue", "maxValue", "minAngle", "maxAngle", "unclamped", "rotationAxis" })
                SetPressureField(runtime, name, proxy.GetType().GetField(name).GetValue(proxy));
            var portReader = runtime.gameObject.AddComponent(game.GetType("DV.Simulation.Ports.IndicatorPortReader", true));
            SetPressureField(portReader, "indicator", runtime);
            foreach (var pressure in new[] { 1f, 10f, 19f })
            {
                portReader.GetType().GetMethod("OnValueUpdate", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(portReader, new object[] { pressure });
                float expectedAngle = pressure == 1f ? -135f : pressure == 10f ? 0f : 135f;
                PressureAssert(Quaternion.Angle(proxy.needle.localRotation, Quaternion.AngleAxis(expectedAngle, Vector3.back)) < .001f,
                    "Runtime pressure needle did not indicate printed " + (pressure - 1) + " bar");
            }
            var speedProxy = root.GetComponent<LocoIndicatorReaderProxy>().speed;
            var speedRuntime = speedProxy.gameObject.AddComponent(game.GetType("IndicatorGauge", true));
            SetPressureField(speedRuntime, "needle", Child(speedProxy.transform, "runtime speed test needle", Vector3.zero));
            SetPressureField(speedRuntime, "maxValue", 100f);
            var speedPort = speedProxy.gameObject.AddComponent(game.GetType("DV.Simulation.Ports.IndicatorPortReader", true));
            SetPressureField(speedPort, "indicator", speedRuntime); SetPressureField(speedPort, "useAbsoluteValue", true);
            foreach (var speedValue in new[] { 0f, 32f, -32f, 140f })
            {
                speedPort.GetType().GetMethod("OnValueUpdate", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(speedPort, new object[] { speedValue });
                float value = (float)speedRuntime.GetType().GetProperty("Value").GetValue(speedRuntime, null);
                PressureAssert(value == Mathf.Abs(speedValue), "HUD speed is negative, normalized, or capped at the dial maximum");
            }
            File.WriteAllText(Path.Combine(PressureOutput, "result.json"), "{\"passed\":true,\"bundleReload\":true,\"lodGrabbers\":true,\"actualCclBinding\":true,\"actualDvIndicator\":true,\"numericalHud\":true,\"speedSamples\":4,\"pressureSamples\":3,\"gameTested\":false}");
            EditorApplication.Exit(0);
        }
        catch (Exception e) { PressureFailure(e); }
        finally
        {
            AppDomain.CurrentDomain.AssemblyResolve -= resolver;
            if (root) Object.DestroyImmediate(root);
            if (lodRoot) Object.DestroyImmediate(lodRoot);
            if (bundle) bundle.Unload(true);
        }
    }

    static void PressureFailure(Exception e)
    {
        Debug.LogException(e); refBody = null;
        File.WriteAllText(Path.Combine(PressureOutput, "result.json"), "{\"passed\":false}");
        EditorApplication.Exit(1);
    }
}
