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
            Cfg.Components.Add(new Comp { name = "number", pos = new Vector3(1, 1, .95f) });
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
            var plate = Child(exterior.transform, "plate", new Vector3(1.51f, 1, .95f));
            PlacementCube(plate, "DummyPlate", Vector3.zero, new Vector3(.02f, .3f, .5f));
            SaveRr2dvPrefab(exterior, folder + "/test_template.prefab");
            Object.DestroyImmediate(exterior);
            SeatRr2dvPlates();
            var saved = AssetDatabase.LoadAssetAtPath<GameObject>(folder + "/test_template.prefab");
            PlacementNear(saved.transform.Find("plate").localPosition.x, 1.01f, "plate ignored hidden mesh");
            if (saved.transform.Find("plate").position.z > .7501f) throw new Exception("Plate edge extends beyond supporting wall");

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

            Cfg.WheelRadius = .4f;
            var oilBody = new GameObject("oil regression body").transform;
            var leftRod = PlacementRod(oilBody, "Main Rod Left", -1f);
            var rightRod = PlacementRod(oilBody, "Main Rod Right", 1f);
            var nubs = Rr2dvRodNubs(oilBody);
            if (nubs.Count != 2 || nubs[0].pos.x * nubs[1].pos.x >= 0)
                throw new Exception("two modelled big-end nub seats were not found");
            using (var oilHits = new VisualHits(oilBody))
            {
                var cups = new List<(string tag, Vector3 pos, Transform rod, string seat)>();
                Rr2dvAddOilPair(cups, oilHits, oilBody, 1,
                    (leftRod, nubs.Find(n => n.pos.x < 0).pos),
                    (rightRod, nubs.Find(n => n.pos.x > 0).pos), -.5f);
                if (cups.Count != 2 || cups[0].rod != leftRod || cups[1].rod != rightRod)
                    throw new Exception("rod-nub pair did not take priority");
                cups.Clear();
                Rr2dvAddOilPair(cups, oilHits, oilBody, 2,
                    (leftRod, nubs.Find(n => n.pos.x < 0).pos), (null, Vector3.zero), -.5f);
                if (cups.Count != 0) throw new Exception("unplaceable pair was not omitted together");
            }
            PlacementCube(oilBody, "left running board", new Vector3(-1.25f, 1.2f, 1), new Vector3(.3f, .05f, .3f));
            PlacementCube(oilBody, "right running board", new Vector3(1.25f, 1.2f, 1), new Vector3(.3f, .05f, .3f));
            using (var oilHits = new VisualHits(oilBody))
            {
                var cups = new List<(string tag, Vector3 pos, Transform rod, string seat)>();
                Rr2dvAddOilPair(cups, oilHits, oilBody, 3,
                    (null, Vector3.zero), (null, Vector3.zero), 1f);
                if (cups.Count != 2 || cups.Exists(c => c.rod))
                    throw new Exception("running boards did not seat a fallback pair");
            }
            Object.DestroyImmediate(oilBody.gameObject);
            Cfg.Livery = "test";
            Cfg.Liveries = new[] { ("test", new[] { ("frame", "#112233") }) };
            Cfg.Components.Add(new Comp { kind = "MaterialColorizerComponent", name = "frame tint", extra = "{\"material\":null,\"colorID\":\"frame\",\"materialName\":\"frame\",\"enabled\":true}" });
            var sourceMaterial = new Material(Shader.Find("Standard")) { name = "frame", color = Color.white };
            var targetMaterial = new Material(Shader.Find("Standard")) { color = Color.white };
            var texture = new Texture2D(2,2);
            sourceMaterial.mainTexture = texture;
            matMap = new Dictionary<Material,Material> { { sourceMaterial, targetMaterial } };
            FinishRr2dvMaterials();
            if (ColorUtility.ToHtmlStringRGB(targetMaterial.color) != "112233" || targetMaterial.mainTexture != texture)
                throw new Exception("Non-Railroader shader lost source tint or texture");
            File.WriteAllText("placement-regression-passed.json", "{\"hiddenMeshIgnored\":true,\"collisionIgnored\":true,\"reloadVerified\":true,\"rodNubsFirst\":true,\"boardFallback\":true,\"pairOmission\":true}");
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

    static Transform PlacementRod(Transform parent, string name, float x)
    {
        var cylinder = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        var bar = GameObject.CreatePrimitive(PrimitiveType.Cube);
        var mesh = new Mesh { name = name + " test mesh" };
        mesh.CombineMeshes(new[] {
            new CombineInstance { mesh = cylinder.GetComponent<MeshFilter>().sharedMesh,
                transform = Matrix4x4.TRS(new Vector3(0, 0, -.5f), Quaternion.identity, new Vector3(.1f, .08f, .1f)) },
            new CombineInstance { mesh = bar.GetComponent<MeshFilter>().sharedMesh,
                transform = Matrix4x4.TRS(Vector3.zero, Quaternion.identity, new Vector3(.07f, .08f, 1.2f)) }
        }, false, true);
        Object.DestroyImmediate(cylinder);
        Object.DestroyImmediate(bar);
        var rod = new GameObject(name).transform;
        rod.SetParent(parent, false);
        rod.localPosition = new Vector3(x, .8f, 0);
        rod.gameObject.AddComponent<MeshFilter>().sharedMesh = mesh;
        rod.gameObject.AddComponent<MeshRenderer>();
        return rod;
    }
}
