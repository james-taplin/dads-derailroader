using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using CCL.Types.Proxies.Wheels;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

public static class TruckWheelOrbitRegression
{
    [Serializable] public class Result { public bool passed, reproduced, bundleReload; public int wheelsets; public float beforeTravel, afterTravel; }
    static void Check(bool pass, string message) { if (!pass) throw new Exception(message); }
    static GameObject Template(AssetBundle bundle, string carId = "RR2DV_LS_440_A23_TENDER")
    {
        var queue = new Queue<Object>(bundle.LoadAllAssets()); var seen = new HashSet<Object>();
        while (queue.Count > 0)
        {
            var obj = queue.Dequeue(); if (!obj || !seen.Add(obj)) continue;
            var go = obj as GameObject;
            if (go && go.name == carId + "_template") return go;
            if (go) foreach (var component in go.GetComponentsInChildren<Component>(true)) if (component) queue.Enqueue(component);
            if (!(obj is GameObject || obj is Component || obj is ScriptableObject || obj is Material)) continue;
            var fields = new SerializedObject(obj).GetIterator();
            while (fields.Next(true)) if (fields.propertyType == SerializedPropertyType.ObjectReference && fields.objectReferenceValue)
                queue.Enqueue(fields.objectReferenceValue);
        }
        throw new Exception("Tender template not found: " + carId);
    }
    static Transform[] Wheels(GameObject root) => root.GetComponentsInChildren<Transform>(true)
        .Where(t => t.name.StartsWith("rr2dvWheel_", StringComparison.Ordinal)).ToArray();
    static float Travel(GameObject root)
    {
        float maximum = 0;
        foreach (var wheel in Wheels(root))
        {
            var axle = wheel.parent;
            Check(axle && axle.name == "[axle]", "Truck wheel lost its standard DV axle parent");
            var meshes = wheel.GetComponentsInChildren<MeshFilter>(true).Where(f => f.sharedMesh).ToArray();
            var centres = meshes.Select(f => f.transform.TransformPoint(f.sharedMesh.bounds.center)).ToArray();
            var rest = axle.localRotation;
            try
            {
                foreach (float angle in new[] { 0f, 90f, 180f, 270f, 360f })
                {
                    axle.localRotation = rest * Quaternion.AngleAxis(angle, Vector3.right);
                    for (int i = 0; i < meshes.Length; i++) maximum = Mathf.Max(maximum,
                        Vector3.Distance(centres[i], meshes[i].transform.TransformPoint(meshes[i].sharedMesh.bounds.center)));
                }
            }
            finally { axle.localRotation = rest; }
        }
        return maximum;
    }
    static float SpindleTravel(GameObject root)
    {
        float maximum = 0;
        foreach (var wheel in Wheels(root))
        {
            var axle = wheel.parent; Check(axle && axle.name == "[axle]", "Invalid tender wheel parent");
            var position = wheel.position; var rotation = axle.localRotation;
            try { foreach (float angle in new[] { 0f, 90f, 180f, 270f, 360f }) {
                axle.localRotation = rotation * Quaternion.AngleAxis(angle, Vector3.right);
                maximum = Mathf.Max(maximum, Vector3.Distance(position, wheel.position));
            } }
            finally { axle.localRotation = rotation; }
        }
        return maximum;
    }
    [Serializable] public class FleetCase { public string id, carId, bundle; }
    [Serializable] public class FleetInput { public FleetCase[] cases; }
    [Serializable] public class FleetResult { public bool passed; public int tenders, wheelsets, affected; public float maximumBefore, maximumAfter; }
    public static void RunSynthetic()
    {
        string output = Environment.GetEnvironmentVariable("CCL_BUILD_OUT"); Directory.CreateDirectory(output);
        var result = new Result(); GameObject root = null; int exit = 1;
        try
        {
            root = new GameObject("truck spindle regression"); root.transform.position = new Vector3(2, 1, -5);
            root.transform.rotation = Quaternion.Euler(11, 27, 3);
            var proxy = root.AddComponent<WheelRotationViaCodeProxy>(); proxy.wheelRadius = .3794f;
            var axes = new List<Transform>();
            for (int bogie = 0; bogie < 2; bogie++)
            {
                var frame = new GameObject(bogie == 0 ? "BogieF" : "BogieR"); frame.transform.SetParent(root.transform, false);
                frame.transform.localPosition = new Vector3(0, 0, bogie == 0 ? 2 : -2);
                frame.transform.localRotation = Quaternion.Euler(0, bogie == 0 ? 6 : -6, 0);
                frame.AddComponent<BoxCollider>().size = new Vector3(1.8f, .2f, 2.2f);
                for (int i = 0; i < 2; i++)
                {
                    var axle = new GameObject("[axle]").transform; axle.SetParent(frame.transform, false);
                    axle.localPosition = new Vector3(0, .3794f, i == 0 ? .85f : -.85f); axes.Add(axle);
                    var wheel = new GameObject("rr2dvWheel_" + i).transform; wheel.SetParent(axle, false);
                    wheel.localPosition = new Vector3(0, .0430423f, .000047f);
                    wheel.localRotation = Quaternion.Euler(0, bogie == 0 ? 0 : 180, 0);
                    var mesh = GameObject.CreatePrimitive(PrimitiveType.Cylinder); mesh.transform.SetParent(wheel, false);
                    mesh.transform.localRotation = Quaternion.Euler(0, 0, 90); mesh.transform.localScale = new Vector3(.76f, .08f, .76f);
                    Object.DestroyImmediate(mesh.GetComponent<Collider>());
                }
            }
            proxy.transformsToRotate = axes.ToArray();
            result.wheelsets = Wheels(root).Length; result.beforeTravel = Travel(root);
            result.reproduced = result.beforeTravel > .08f; Check(result.reproduced, "Synthetic off-centre spindle did not orbit");
            var positions = Wheels(root).Select(t => t.position).ToArray();
            var colliders = root.GetComponentsInChildren<BoxCollider>();
            var supports = colliders.Select(c => c.transform.position).ToArray();
            CclLocoBuild.CentreRr2dvTruckWheelPivots(root, new[] { "rr2dvWheel_" });
            for (int i = 0; i < positions.Length; i++) Check(Vector3.Distance(positions[i], Wheels(root)[i].position) < .00001f, "Synthetic resting wheel moved");
            for (int i = 0; i < colliders.Length; i++) Check(Vector3.Distance(supports[i], colliders[i].transform.position) < .00001f, "Physics support moved");
            Check(proxy.wheelRadius == .3794f, "Rolling radius changed");
            result.afterTravel = Travel(root); Check(result.afterTravel < .0005f, "Synthetic spindle still orbits");
            CclLocoBuild.CentreRr2dvTruckWheelPivots(root, new[] { "rr2dvWheel_" });
            Check(Travel(root) < .0005f, "Synthetic correction was not repeatable");
            var extra = new GameObject("rr2dvWheel_bad").transform; extra.SetParent(axes[0], false);
            extra.localPosition = new Vector3(0, .01f, 0); bool rejected = false;
            try { CclLocoBuild.CentreRr2dvTruckWheelPivots(root, new[] { "rr2dvWheel_" }); }
            catch (InvalidOperationException) { rejected = true; }
            Check(rejected, "Mismatched source spindle was accepted"); Object.DestroyImmediate(extra.gameObject);
            string path = "Assets/TruckSpindleRegression.prefab"; PrefabUtility.SaveAsPrefabAsset(root, path); AssetDatabase.SaveAssets();
            string folder = Path.Combine(output, "bundles"); Directory.CreateDirectory(folder);
            BuildPipeline.BuildAssetBundles(folder, new[] { new AssetBundleBuild { assetBundleName = "truck-regression", assetNames = new[] { path } } },
                BuildAssetBundleOptions.ForceRebuildAssetBundle, BuildTarget.StandaloneWindows64);
            var bundle = AssetBundle.LoadFromFile(Path.Combine(folder, "truck-regression")); Check(bundle, "Synthetic bundle failed to reload");
            var copy = Object.Instantiate(bundle.LoadAsset<GameObject>(path));
            try { Check(Travel(copy) < .0005f, "Orbit returned after export/reload");
                Check(copy.GetComponent<WheelRotationViaCodeProxy>().wheelRadius == .3794f, "Export changed rolling radius"); result.bundleReload = true; }
            finally { Object.DestroyImmediate(copy); bundle.Unload(true); }
            result.passed = true; exit = 0;
        }
        catch (Exception e) { Debug.LogException(e); }
        finally { if (root) Object.DestroyImmediate(root); }
        File.WriteAllText(Path.Combine(output, "result.json"), JsonUtility.ToJson(result, true)); EditorApplication.Exit(exit);
    }
    public static void RunFleet()
    {
        string output = Environment.GetEnvironmentVariable("CCL_BUILD_OUT"); Directory.CreateDirectory(output);
        var result = new FleetResult(); int exit = 1;
        try
        {
            var input = JsonUtility.FromJson<FleetInput>(File.ReadAllText(Environment.GetEnvironmentVariable("RR2DV_TRUCK_FLEET_INPUT")));
            foreach (var entry in input.cases)
            {
                AssetBundle bundle = null; GameObject root = null;
                try
                {
                    bundle = AssetBundle.LoadFromFile(entry.bundle); Check(bundle, "Fleet bundle failed: " + entry.id);
                    root = Object.Instantiate(Template(bundle, entry.carId));
                    float before = SpindleTravel(root); if (before > .0005f) result.affected++;
                    var meshes = root.GetComponentsInChildren<MeshFilter>(true).Where(f => f.sharedMesh).ToArray();
                    var centres = meshes.Select(f => f.transform.TransformPoint(f.sharedMesh.bounds.center)).ToArray();
                    CclLocoBuild.CentreRr2dvTruckWheelPivots(root, new[] { "rr2dvWheel_" });
                    for (int i = 0; i < meshes.Length; i++) Check(Vector3.Distance(centres[i], meshes[i].transform.TransformPoint(meshes[i].sharedMesh.bounds.center)) < .00001f,
                        "Resting fleet geometry moved: " + entry.id);
                    float after = SpindleTravel(root); Check(after < .0005f, "Source wheel spindle still orbits: " + entry.id);
                    CclLocoBuild.CentreRr2dvTruckWheelPivots(root, new[] { "rr2dvWheel_" });
                    Check(SpindleTravel(root) < .0005f, "Repeated fleet correction differs: " + entry.id);
                    result.tenders++; result.wheelsets += Wheels(root).Length;
                    result.maximumBefore = Mathf.Max(result.maximumBefore, before); result.maximumAfter = Mathf.Max(result.maximumAfter, after);
                }
                finally { if (root) Object.DestroyImmediate(root); if (bundle) bundle.Unload(true); }
            }
            Check(result.tenders == 20, "Expected all 20 tender engines"); result.passed = true; exit = 0;
        }
        catch (Exception e) { Debug.LogException(e); }
        File.WriteAllText(Path.Combine(output, "result.json"), JsonUtility.ToJson(result, true)); EditorApplication.Exit(exit);
    }
    public static void Run()
    {
        var output = Environment.GetEnvironmentVariable("CCL_BUILD_OUT"); Directory.CreateDirectory(output);
        AssetBundle bundle = null; GameObject root = null; int exit = 1;
        var result = new Result();
        try
        {
            bundle = AssetBundle.LoadFromFile(Environment.GetEnvironmentVariable("RR2DV_TRUCK_BUNDLE"));
            Check(bundle, "A-23 bundle failed to load"); root = Object.Instantiate(Template(bundle));
            result.wheelsets = Wheels(root).Length; Check(result.wheelsets == 4, "Expected four A-23 tender wheelsets");
            result.beforeTravel = Travel(root); result.reproduced = result.beforeTravel > .04f;
            bool expectedFixed = Environment.GetEnvironmentVariable("RR2DV_TRUCK_EXPECT_FIXED") == "1";
            if (!expectedFixed) Check(result.reproduced, "Reported orbital wheel motion was not reproduced");
            else { result.afterTravel = result.beforeTravel; Check(result.afterTravel < .0005f, "Rebuilt wheel centres still orbit"); result.bundleReload = true; }
            if (Environment.GetEnvironmentVariable("RR2DV_TRUCK_FIX") == "1")
            {
                var transforms = root.GetComponentsInChildren<Transform>(true);
                var positions = transforms.Select(t => t.position).ToArray();
                var rotations = transforms.Select(t => t.rotation).ToArray();
                var bounds = root.GetComponentsInChildren<MeshFilter>(true).Where(f => f.sharedMesh).ToArray();
                var centres = bounds.Select(f => f.transform.TransformPoint(f.sharedMesh.bounds.center)).ToArray();
                typeof(CclLocoBuild).GetMethod("CentreRr2dvTruckWheelPivots", BindingFlags.Static | BindingFlags.Public).Invoke(null, new object[] { root, new[] { "rr2dvWheel_" } });
                for (int i = 0; i < bounds.Length; i++) Check(Vector3.Distance(centres[i], bounds[i].transform.TransformPoint(bounds[i].sharedMesh.bounds.center)) < .00001f,
                    "Pivot correction moved resting truck geometry");
                for (int i = 0; i < transforms.Length; i++) if (transforms[i].name != "[axle]")
                    Check(Vector3.Distance(positions[i], transforms[i].position) < .00001f && Quaternion.Angle(rotations[i], transforms[i].rotation) < .001f,
                        "Pivot correction moved a frame, brake, contact point or wheel at rest");
                result.afterTravel = Travel(root); Check(result.afterTravel < .0005f, "Corrected wheel centres still orbit");
                typeof(CclLocoBuild).GetMethod("CentreRr2dvTruckWheelPivots", BindingFlags.Static | BindingFlags.Public).Invoke(null, new object[] { root, new[] { "rr2dvWheel_" } });
                Check(Travel(root) < .0005f, "Repeated pivot correction changed wheel motion");
            }
            result.passed = true; exit = 0;
        }
        catch (Exception e) { Debug.LogException(e); }
        finally { if (root) Object.DestroyImmediate(root); if (bundle) bundle.Unload(true); }
        File.WriteAllText(Path.Combine(output, "result.json"), JsonUtility.ToJson(result, true));
        EditorApplication.Exit(exit);
    }
}
