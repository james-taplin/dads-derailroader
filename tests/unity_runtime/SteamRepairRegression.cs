using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

public static partial class CclLocoBuild
{
    static void SteamAssert(bool ok, string message)
    {
        if (!ok) throw new Exception(message);
    }

    public static void SteamRepairRegression()
    {
        int code = 0;
        string output = Environment.GetEnvironmentVariable("CCL_BUILD_OUT");
        try
        {
            Directory.CreateDirectory(output);
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            const string folder = "Assets/SteamRepairRegression";
            Folder(folder);
            SafetyFallbackRegression();
            var assets = new List<string>();
            foreach (bool hasGlass in new[] { true, false })
            {
                Cfg = new LocoConfig { CarId = hasGlass ? "glass" : "noglass", Work = folder };
                carFolder = folder;
                var root = new GameObject(CarId + "_interior");
                var reader = Add(root, "CCL.Types.Proxies.Controls.LocoIndicatorReaderProxy");
                if (hasGlass)
                {
                    var glass = Child(root.transform, "sight glass test", new Vector3(0, 2, 0));
                    var scaler = Child(glass, "scaler", Vector3.zero);
                    var water = GameObject.CreatePrimitive(PrimitiveType.Cube).transform;
                    water.name = "water"; water.SetParent(scaler, false);
                    water.localScale = new Vector3(.022f, .24f, .022f);
                    var indicator = Add(scaler.gameObject, "CCL.Types.Proxies.Indicators.IndicatorScalerProxy");
                    Set(indicator, "indicatorToScale", scaler);
                    Set(indicator, "minValue", 0f); Set(indicator, "maxValue", 1f);
                    Set(indicator, "startScale", new Vector3(1, 0, 1)); Set(indicator, "endScale", Vector3.one);
                    PortReader(scaler.gameObject, "boiler.WATER_LEVEL_NORMALIZED");
                    Set(reader, "locoWaterLevel", indicator);
                    SteamAssert(water.GetComponent<Renderer>().bounds.min.y < glass.position.y,
                        "baseline must reproduce water extending below bottom");
                }
                string path = folder + "/" + CarId + "_interior.prefab";
                SaveRr2dvPrefab(root, path); Object.DestroyImmediate(root);
                RepairRr2dvWaterIndicators();
                RepairRr2dvWaterIndicators(); // repeat-safe, no duplicate fallback
                assets.Add(path);
            }
            foreach (bool waterFirst in new[] { false, true })
            {
                string name = waterFirst ? "waterfirst" : "coalfirst";
                Cfg = new LocoConfig { CarId = name, Work = folder + "/" + name,
                    NestedClipGroups = true, CabControlObjects = new string[0] };
                var body = new GameObject(name);
                var tender = Child(body.transform, "tender", Vector3.zero);
                foreach (string part in new[] { "Coal", "Water" })
                    Child(Child(tender, part, Vector3.zero), "Bone", Vector3.zero);
                foreach (string part in waterFirst ? new[] { "Water", "Coal" } : new[] { "Coal", "Water" })
                {
                    var clip = new AnimationClip { name = part, frameRate = 30 };
                    AnimationUtility.SetEditorCurve(clip,
                        EditorCurveBinding.FloatCurve("tender/" + part + "/Bone", typeof(Transform), "m_LocalPosition.y"),
                        AnimationCurve.Linear(0, 0, 1, 1));
                    var groups = PortAnimGroups(body, part.ToLowerInvariant(), clip,
                        part.ToLowerInvariant() + ".NORMALIZED", .999f, 0);
                    SteamAssert(groups.Count == 1 && groups[0].transform.childCount == 1, "load target lost: " + part);
                    Object.DestroyImmediate(clip);
                }
                string path = folder + "/" + name + ".prefab";
                SaveRr2dvPrefab(body, path); Object.DestroyImmediate(body); assets.Add(path);
            }
            AssetDatabase.SaveAssets();
            string bundles = Path.Combine(output, "bundles"); Directory.CreateDirectory(bundles);
            BuildPipeline.BuildAssetBundles(bundles, new[] { new AssetBundleBuild {
                assetBundleName = "steam-repairs", assetNames = assets.ToArray() } },
                BuildAssetBundleOptions.ForceRebuildAssetBundle, BuildTarget.StandaloneWindows64);
            var bundle = AssetBundle.LoadFromFile(Path.Combine(bundles, "steam-repairs"));
            SteamAssert(bundle, "bundle reload failed");
            foreach (string path in assets)
            {
                var root = Object.Instantiate(bundle.LoadAsset<GameObject>(path));
                if (path.EndsWith("_interior.prefab"))
                {
                    var reader = root.GetComponentsInChildren<Component>(true).Single(c => c && c.GetType().Name == "LocoIndicatorReaderProxy");
                    var level = new SerializedObject(reader).FindProperty("locoWaterLevel").objectReferenceValue as Component;
                    SteamAssert(level, "missing boiler water HUD reader after export");
                    SteamAssert(root.GetComponentsInChildren<Renderer>().Length == (path.EndsWith("/glass_interior.prefab") ? 1 : 0), "fallback added visible geometry");
                    var glass = root.transform.Find("sight glass test");
                    if (glass)
                    {
                        var scaler = glass.Find("scaler"); var water = scaler.Find("water");
                        foreach (float f in new[] { 0f, .5f, 1f })
                        {
                            scaler.localScale = new Vector3(1, f, 1);
                            float bottom = glass.position.y;
                            SteamAssert(Mathf.Abs(water.TransformPoint(new Vector3(0, -.5f, 0)).y - bottom) < .0001f, "glass bottom moved");
                            SteamAssert(Mathf.Abs(water.TransformPoint(new Vector3(0, .5f, 0)).y - bottom - .24f * f) < .0001f, "glass top incorrect");
                        }
                    }
                    else SteamAssert(root.transform.Cast<Transform>().Count(t => t.name == "HUD-only boiler water") == 1, "duplicate HUD fallback");
                }
                else
                {
                    var groups = root.GetComponentsInChildren<Animator>();
                    SteamAssert(groups.Length == 2, "missing load animator after export");
                    foreach (var group in groups)
                    {
                        var other = groups.Single(g => g != group).transform.GetChild(0);
                        var before = other.localPosition;
                        foreach (float f in new[] { 0f, .5f, 1f })
                        {
                            group.runtimeAnimatorController.animationClips[0].SampleAnimation(group.gameObject, f);
                            SteamAssert(Mathf.Abs(group.transform.GetChild(0).localPosition.y - f) < .0001f, "load did not follow its clip");
                            SteamAssert(other.localPosition == before, "one load moved the other");
                        }
                    }
                }
                Object.DestroyImmediate(root);
            }
            bundle.Unload(true);
            File.WriteAllText(Path.Combine(output, "result.json"), "{\"passed\":true,\"prefabs\":4,\"bundleReload\":true}");
        }
        catch (Exception e) { Debug.LogException(e); code = 1; }
        EditorApplication.Exit(code);
    }

    static GameObject SafetyShape(Transform parent, string name, Vector3 at, Vector3 size, PrimitiveType kind = PrimitiveType.Cube)
    {
        var g = GameObject.CreatePrimitive(kind);
        g.name = name; g.transform.SetParent(parent, false);
        g.transform.localPosition = at; g.transform.localScale = size;
        return g;
    }

    static void SafetyFallbackRegression()
    {
        var body = new GameObject("source");
        try
        {
            SafetyShape(body.transform, "anonymous frame", Vector3.zero, new Vector3(2, .2f, 12));
            SafetyShape(body.transform, "anonymous boiler", new Vector3(0, 2.5f, 1.5f), new Vector3(1.4f, 1, 6));
            var dome = SafetyShape(body.transform, "dome", new Vector3(0, 3.4f, 2), new Vector3(.8f, .8f, .8f), PrimitiveType.Sphere);
            SafetyShape(body.transform, "anonymous rear cab", new Vector3(0, 8, -3), new Vector3(2, 1, 2));
            SafetyShape(body.transform, "anonymous stack", new Vector3(0, 6, 4.5f), new Vector3(.6f, 2, .6f));
            var bell = Child(body.transform, "Bell Anim", Vector3.zero);
            var namedWrong = SafetyShape(bell, "Boiler_001", new Vector3(0, 7, 1), new Vector3(.6f, .8f, .6f));
            SafetyShape(body.transform, "anonymous thin fitting", new Vector3(0, 9, .5f), new Vector3(.04f, 1, .04f));
            SafetyShape(body.transform, "anonymous dynamo", new Vector3(0, 5, 3), new Vector3(.3f, .3f, .3f));
            var hidden = SafetyShape(body.transform, "hidden", new Vector3(0, 20, 2), Vector3.one);
            hidden.GetComponent<Renderer>().enabled = false;
            var lod = SafetyShape(body.transform, "boiler_LOD1", new Vector3(0, 12, 2), Vector3.one);
            var chimney = new Vector3(0, 7, 4.5f);
            var measured = ProbeRr2dvBoilerTop(body.transform, -2, chimney, new[] { new Vector3(0, 5, 3) });
            SteamAssert(measured.part.EndsWith("/dome") && measured.point.y > 3.78f && measured.point.y <= 3.801f,
                "safety fallback selected a cab/fitting or ignored dome: " + measured.part + " " + measured.point);
            SteamAssert(measured.point.z > 0 && measured.point.z < 4, "safety probe escaped forward boiler window");
            // S-23 combines boiler geometry into a mesh named Cab. Spatial
            // limits must exclude the cab without discarding that boiler.
            dome.name = "Cab_1_LOD0";
            var combined = ProbeRr2dvBoilerTop(body.transform, -2, chimney, new[] { new Vector3(0, 5, 3) });
            SteamAssert((combined.point - measured.point).sqrMagnitude < .000001f,
                "Cab-named boiler geometry was discarded");
            SteamAssert(namedWrong.GetComponent<Renderer>().enabled && lod.GetComponent<Renderer>().enabled &&
                !hidden.GetComponent<Renderer>().enabled, "probe changed source renderer visibility");
            Cfg = new LocoConfig { BackheadZ = -2, ChimneyComp = "stack", Components = new List<Comp> {
                new Comp { kind = "Chuff", name = "stack", pos = chimney },
                new Comp { kind = "Dynamo", name = "generator", pos = new Vector3(0, 5, 3) } } };
            refBody = body.transform;
            ProbeRr2dvSafetyJet();
            SteamAssert(Cfg.SafetyPos.HasValue && Mathf.Abs(Cfg.SafetyPos.Value.y - 3.82f) < .02f &&
                Cfg.SndSafety == Cfg.SafetyPos.Value, "jet clearance and sound anchor differ");
            var prior = Cfg.SafetyPos.Value;
            ProbeRr2dvSafetyJet();
            SteamAssert(Cfg.SafetyPos.Value == prior, "explicit measured safety position overwritten");
            bool rejected = false;
            try { ProbeRr2dvBoilerTop(body.transform, 4.4f, chimney, new Vector3[0]); }
            catch (InvalidOperationException) { rejected = true; }
            SteamAssert(rejected, "invalid forward region must not fall back onto cab");
            Line("safety fallback regression passed: dome, rear cab, chimney, named/misnamed and thin fittings, LOD, hidden mesh, sound, explicit position, invalid region");
        }
        finally { refBody = null; Object.DestroyImmediate(body); }
    }
}
