using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

public static partial class CclLocoBuild
{
    static void JetAssert(bool ok, string message) { if (!ok) throw new Exception(message); }
    static Vector3[] DynamoTestAxes = {
        new Vector3(0, 4, 3).normalized, new Vector3(0, 4, -3).normalized,
        new Vector3(3, 4, 0).normalized, new Vector3(-3, 4, 0).normalized,
        new Vector3(2, 4, 3).normalized, new Vector3(-2, 4, -3).normalized,
        Vector3.up, Vector3.zero
    };

    public static void DynamoJetRegression()
    {
        string output = Environment.GetEnvironmentVariable("CCL_BUILD_OUT");
        int exit = 0;
        try
        {
            Directory.CreateDirectory(output);
            const string folder = "Assets/DynamoJetRegression";
            Folder(folder);
            var paths = new List<string>();
            for (int i = 0; i < DynamoTestAxes.Length; i++)
            {
                Cfg = new LocoConfig { CarId = "jet" + i, Work = folder };
                carFolder = folder;
                var root = new GameObject(CarId + "_template");
                var particles = Child(root.transform, "[particles]", Vector3.zero);
                particles.localRotation = Quaternion.Euler(17, 38, 9);
                var dynamo = Child(particles, "DynamoSteam", new Vector3(.4f, 1.2f, -.3f));
                dynamo.localRotation = Quaternion.Euler(31, -52, 27);
                var small = Child(dynamo, "SteamExhaust Small", Vector3.zero);
                var copy = Add(small.gameObject, "CCL.Types.Components.CopyVanillaParticleSystem");
                Set(copy, "SystemToCopy", 150);
                Child(particles, "Whistle", Vector3.zero);
                Child(particles, "SteamSafetyRelease", Vector3.zero);
                var smoke = Child(particles, "SteamSmoke", Vector3.zero);
                smoke.localRotation = Quaternion.Euler(7, 23, -14);
                var source = new GameObject("pipe geometry");
                Vector3 position = dynamo.position, axis = DynamoTestAxes[i];
                if (axis != Vector3.zero)
                {
                    var pipe = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                    pipe.transform.SetParent(source.transform, false);
                    pipe.transform.position = position - axis * .10f;
                    pipe.transform.rotation = Quaternion.FromToRotation(Vector3.up, axis);
                    pipe.transform.localScale = new Vector3(.012f, .10f, .012f);
                }
                refBody = source.transform;
                var measured = Rr2dvExhaustTip(position);
                JetAssert(axis == Vector3.zero ? !measured.HasValue : measured.HasValue && Vector3.Dot(measured.Value, axis) > .9999f,
                    "Pipe fixture failed to reproduce measured axis " + i);
                string path = folder + "/" + CarId + "_template.prefab";
                SaveRr2dvPrefab(root, path); Object.DestroyImmediate(root);
                AimRr2dvJets();
                CheckDynamoTemplate(AssetDatabase.LoadAssetAtPath<GameObject>(path), i, position);
                AimRr2dvJets(); // must not keep turning by 180 degrees on repeat application
                CheckDynamoTemplate(AssetDatabase.LoadAssetAtPath<GameObject>(path), i, position);
                paths.Add(path);
                Object.DestroyImmediate(source); refBody = null;
            }
            string bundles = Path.Combine(output, "bundles"); Directory.CreateDirectory(bundles);
            BuildPipeline.BuildAssetBundles(bundles, new[] { new AssetBundleBuild {
                assetBundleName = "dynamo-jets", assetNames = paths.ToArray() } },
                BuildAssetBundleOptions.ForceRebuildAssetBundle, BuildTarget.StandaloneWindows64);
            var bundle = AssetBundle.LoadFromFile(Path.Combine(bundles, "dynamo-jets"));
            JetAssert(bundle, "Could not reload the dynamo jet bundle");
            try
            {
                for (int i = 0; i < paths.Count; i++)
                {
                    var prefab = bundle.LoadAsset<GameObject>(paths[i]);
                    var particles = prefab.transform.Find("[particles]");
                    Vector3 position = particles.TransformPoint(new Vector3(.4f, 1.2f, -.3f));
                    CheckDynamoTemplate(prefab, i, position);
                }
            }
            finally { bundle.Unload(true); }
            File.WriteAllText(Path.Combine(output, "result.json"), "{\"passed\":true,\"prefabs\":8,\"bundleReload\":true}");
        }
        catch (Exception e)
        {
            Debug.LogException(e); exit = 1;
            File.WriteAllText(Path.Combine(output, "result.json"), "{\"passed\":false}");
        }
        finally { refBody = null; }
        EditorApplication.Exit(exit);
    }

    static void CheckDynamoTemplate(GameObject prefab, int i, Vector3 position)
    {
        var root = Object.Instantiate(prefab);
        try
        {
            var particles = root.transform.Find("[particles]");
            var dynamo = particles.Find("DynamoSteam");
            var axis = DynamoTestAxes[i];
            var expected = axis == Vector3.zero ? Vector3.up : axis;
            var actual = dynamo.rotation * Vector3.forward;
            JetAssert(Vector3.Dot(actual, expected) > .9999f,
                "Dynamo does not follow its outlet in case " + i + ": expected " + expected + ", got " + actual);
            JetAssert(Mathf.Abs(actual.y - expected.y) < .0001f, "Dynamo upward tilt changed");
            JetAssert((dynamo.position - position).sqrMagnitude < .000001f, "Dynamo outlet moved");
            var child = dynamo.Find("SteamExhaust Small");
            JetAssert(Vector3.Dot(child.rotation * Vector3.forward, expected) > .9999f,
                "Particle copy child lost the corrected direction");
            foreach (string name in new[] { "Whistle", "SteamSafetyRelease" })
                JetAssert(Vector3.Dot(particles.Find(name).rotation * Vector3.forward, Vector3.up) > .9999f,
                    name + " no longer points up");
            JetAssert(Quaternion.Angle(particles.Find("SteamSmoke").localRotation, Quaternion.Euler(7, 23, -14)) < .001f,
                "Unrelated smoke rotation changed");
        }
        finally { Object.DestroyImmediate(root); }
    }
}
