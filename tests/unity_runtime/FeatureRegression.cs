using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using CCL.Types.Proxies.Ports;
using CCL.Types.Proxies.Simulation;
using CCL.Types.Components.Simulation;

public static partial class CclLocoBuild
{
    public static void FeatureRegression()
    {
        int code = 0;
        const string folder = "Assets/Rr2dvFeatureRegression";
        try
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            Folder(folder);
            // Inspect existing generated geometry without rewriting it.
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/_CCL_CARS/A-18 American/RR2DV_LS_440_A18_template.prefab");
            if (!prefab) throw new Exception("Diagnostic generated A18 prefab missing");
            Cfg = LlwVehicleRecord.Load(Environment.GetEnvironmentVariable("CCL_VEHICLE_RECORD"));
            carFolder = folder; refBody = null;
            AssetDatabase.CopyAsset(AssetDatabase.GetAssetPath(prefab), folder + "/" + CarId + "_template.prefab");
            var damaged = PrefabUtility.LoadPrefabContents(folder + "/" + CarId + "_template.prefab");
            foreach (var c in damaged.GetComponentsInChildren<CapsuleCollider>(true).Where(c => c.transform.parent.name == "[bogies]"))
                c.center = new Vector3(0, .47f, c.name == "front" ? 7.3f : -7.3f);
            SaveRr2dvPrefab(damaged, folder + "/" + CarId + "_template.prefab");
            PrefabUtility.UnloadPrefabContents(damaged);
            AlignRr2dvBogieSupports();
            var aligned = AssetDatabase.LoadAssetAtPath<GameObject>(folder + "/" + CarId + "_template.prefab");
            foreach (var c in aligned.GetComponentsInChildren<CapsuleCollider>(true).Where(c => c.transform.parent.name == "[bogies]"))
            {
                if (c.center != Vector3.zero || Mathf.Abs(c.transform.position.y - c.radius) > .0001f)
                    throw new Exception("Support capsule offset or ground plane incorrect after reload");
                Debug.Log("RR_SUPPORT_FIXED " + c.name + " " + c.transform.position.ToString("F5") + " radius=" + c.radius);
            }
            SeatRr2dvOilCups();
            var oil = Cfg.OilPoints(RefBody).ToArray();
            if (oil.Length % 2 != 0 || oil.Length > 4) throw new Exception("A18 oil placement did not retain complete pairs");
            foreach (var p in oil) Debug.Log("RR_OIL_FIXED " + p.Item1 + " " + p.Item2.ToString("F5"));
            var root = UnityEngine.Object.Instantiate(prefab);
            foreach (var c in root.GetComponentsInChildren<CapsuleCollider>(true))
                Debug.Log("RR_GEOMETRY " + AnimationUtility.CalculateTransformPath(c.transform,root.transform) + " position=" + c.transform.position.ToString("F5") + " center=" + c.center + " radius=" + c.radius);
            foreach (var b in new[] {"BogieF", "BogieR"})
            foreach (Transform a in root.transform.Find(b + "/bogie_car"))
                if (a.name == "[axle]") Debug.Log("RR_AXLE " + b + " " + a.position.ToString("F5"));
            var sim = root.transform.Find("[sim]");
            ApplyRrSteamGraph(sim, new RrReview { physics="geared", steamHeat="saturated", gearRatio=2.5f, efficiency=.9f });
            SaveRr2dvPrefab(root, folder + "/gear.prefab");
            UnityEngine.Object.DestroyImmediate(root);
            root = PrefabUtility.LoadPrefabContents(folder + "/gear.prefab");
            var conn = root.transform.Find("[sim]").GetComponent<SimConnectionsDefinitionProxy>();
            conn.AfterImport();
            var rpm = root.GetComponentInChildren<ConstantMultiplierOffsetDefinition>();
            rpm.AfterImport();
            if (rpm.Multiplier != 2.5f || rpm.Input.valueType != DVPortValueType.RPM) throw new Exception("RPM serialization failed");
            var gear = root.GetComponentInChildren<TransmissionFixedGearDefinitionProxy>();
            if (gear.gearRatio != 2.5f || gear.transmissionEfficiency != .9f) throw new Exception("Torque gearing serialization failed");
            if (conn.portReferenceConnections.Single(p => p.portReferenceId == "steamEngine.CRANK_RPM").portId != "rr2dvEngineRPM.OUT") throw new Exception("Crank reference failed");
            if (conn.portReferenceConnections.Single(p => p.portReferenceId == "steamEngine.INTAKE_TEMPERATURE").portId != "boiler.TEMPERATURE") throw new Exception("Heat reference failed");
            if (!conn.connections.Any(p => p.fullPortIdOut == "rr2dvGear.TORQUE_OUT" && p.fullPortIdIn == "traction.TORQUE_IN")) throw new Exception("Torque output failed");
            if (conn.executionOrder.IndexOf(rpm) >= conn.executionOrder.FindIndex(p => p.ID == "steamEngine")) throw new Exception("RPM order failed");
            if (conn.executionOrder.Select(p => p.ID).Distinct().Count() != conn.executionOrder.Count) throw new Exception("Geared simulation component was inserted twice");
            PrefabUtility.UnloadPrefabContents(root);
            File.WriteAllText("feature-regression-passed.json", "{\"serializedGearGraph\":true,\"runtimeValidated\":false}");
        }
        catch (Exception e) { Debug.LogException(e); code = 1; }
        finally { if (AssetDatabase.IsValidFolder(folder)) AssetDatabase.DeleteAsset(folder); }
        EditorApplication.Exit(code);
    }
}
