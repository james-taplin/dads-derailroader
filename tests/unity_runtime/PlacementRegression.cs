using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

// Run in a disposable assembled builder project (contains the pinned core + app extension).
// Synthetic geometry only: no dependency on any particular vehicle or its dimensions.
public static partial class CclLocoBuild
{
    public static void PlacementRegression()
    {
        int code = 0;
        const string folder = "Assets/Rr2dvPlacementRegression";
        bool created = false;
        try
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            if (AssetDatabase.IsValidFolder(folder)) throw new Exception("Regression folder already exists");
            Folder(folder);
            created = true;
            Cfg = new LocoConfig { CarId = "test", BodyName = "body", BackheadRayStartZ = -1,
                Components = new List<Comp>() };
            carFolder = folder;
            Cfg.Components.Add(new Comp { name = "number", pos = new Vector3(1, 1, 0) });
            Cfg.PlateDecals = new[] { ("plate", "number") };
            var exterior = new GameObject("exterior");
            var model = Child(exterior.transform, "Model", Vector3.zero);
            var body = Child(model, "body", Vector3.zero);
            var wall = PlacementCube(body, "visible wall", new Vector3(.5f, 1, 0), new Vector3(1, 2, 2));
            var hidden = PlacementCube(body, "hidden collision mesh", new Vector3(.75f, 1, 0), new Vector3(1.5f, 2, 2));
            hidden.GetComponent<MeshRenderer>().enabled = false;
            // Reproduce the builder's collision transfer: no original colliders remain on the model.
            Object.DestroyImmediate(wall.GetComponent<Collider>());
            Object.DestroyImmediate(hidden.GetComponent<Collider>());
            Child(exterior.transform, "plate", new Vector3(1.51f, 1, 0));
            SaveRr2dvPrefab(exterior, folder + "/test_template.prefab");
            Object.DestroyImmediate(exterior);
            SeatRr2dvPlates();
            var saved = AssetDatabase.LoadAssetAtPath<GameObject>(folder + "/test_template.prefab");
            PlacementNear(saved.transform.Find("plate").localPosition.x, 1.01f, "plate ignored hidden mesh");

            var source = new GameObject("source");
            refBody = source.transform;
            PlacementCube(refBody, "backhead", new Vector3(0, 1, .05f), new Vector3(2, 2, .1f));
            var proxy = new GameObject("invisible collision");
            proxy.transform.SetParent(refBody, false);
            proxy.transform.localPosition = new Vector3(0, 1, -.3f);
            proxy.AddComponent<BoxCollider>().size = new Vector3(2, 2, .1f);
            Cfg.Placed.Add(new PlaceCfg { Name = "test lever", X = 0, Y = 1, Label = "testlabel" });
            var interior = new GameObject("interior");
            var controls = Child(interior.transform, "Controls", Vector3.zero);
            var lever = Child(controls, "C_test lever", new Vector3(0, 1, -.37f));
            var grip = Child(lever, "collider", new Vector3(0, .07f, -.01f));
            grip.gameObject.AddComponent<BoxCollider>();
            Child(controls, "label label", new Vector3(0, .965f, -.366f));
            SaveRr2dvPrefab(interior, folder + "/test_interior.prefab");
            Object.DestroyImmediate(interior);
            SeatRr2dvControls();
            saved = AssetDatabase.LoadAssetAtPath<GameObject>(folder + "/test_interior.prefab");
            PlacementNear(saved.transform.Find("Controls/C_test lever").localPosition.z, -.02f, "lever on visible backhead");
            PlacementNear(saved.transform.Find("Controls/label label").localPosition.z, -.016f, "label on visible backhead");
            PlacementNear(saved.transform.Find("Controls/C_test lever/collider").localPosition.z, -.01f, "grip still attached");
            if (!proxy.GetComponent<BoxCollider>().enabled) throw new Exception("source collider was not restored");
            Object.DestroyImmediate(source);
            refBody = null;
            File.WriteAllText("placement-regression-passed.json", "{\"hiddenMeshIgnored\":true,\"collisionIgnored\":true,\"reloadVerified\":true}");
        }
        catch (Exception e) { Debug.LogException(e); code = 1; }
        finally { if (created) AssetDatabase.DeleteAsset(folder); }
        EditorApplication.Exit(code);
    }

    static GameObject PlacementCube(Transform parent, string name, Vector3 position, Vector3 size)
    {
        var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
        cube.name = name;
        cube.transform.SetParent(parent, false);
        cube.transform.localPosition = position;
        cube.transform.localScale = size;
        return cube;
    }
    static void PlacementNear(float actual, float expected, string description)
    {
        if (Mathf.Abs(actual - expected) > .001f) throw new Exception(description + ": " + actual + " != " + expected);
    }
}
