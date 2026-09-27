using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using CCL.Types.Proxies.Ports;
using CCL.Types.Proxies.Simulation;
using CCL.Types.Components.Simulation;

// Editor-only adapters; exported runtime remains CCL-only.
public static partial class CclLocoBuild
{
    [Serializable] public class RrReview
    {
        public string trainBrake, spawnMode, physics, steamHeat;
        public float gearRatio, efficiency;
        public int[] spawnTracks;
        public int[] poweredWheelsets;
    }
    [Serializable] class RrReviewInput { public RrReview review; }
    static RrReview RrChoices;

    static void LoadRrReview()
    {
        var path = Path.Combine(Application.dataPath, "Rr2dv/BuildInput.json");
        RrChoices = File.Exists(path) ? JsonUtility.FromJson<RrReviewInput>(File.ReadAllText(path)).review : null;
    }

    static void ConfigureRrReview()
    {
        if (RrChoices == null) return;
        Cfg = Loco; carFolder = builtFolders[Loco]; refBody = null;
        var type = FindAsset("CustomCarType");
        bool self = RrChoices.trainBrake == "self-lapping";
        Set(type, "brakes.brakeValveType", self ? 1 : 2);
        var hud = AssetDatabase.LoadAssetAtPath<ScriptableObject>($"{carFolder}/{CarId}_hud.asset");
        Set(hud, "HUDType", 1000);
        var settings = hud.GetType().GetField("CustomHUDSettings").GetValue(hud);
        // Changing HUDType alone leaves the custom layout empty. CCL imports its
        // serialized JSON, so initialize the whole steam preset and refresh that JSON.
        settings.GetType().GetMethod("SetToS").Invoke(settings, null);
        settings.GetType().GetMethod(self ? "SelfLappingBrakeSetup" : "NonSelfLappingBrakeSetup").Invoke(settings, null);
        var basic = settings.GetType().GetField("BasicControls").GetValue(settings);
        var speed = basic.GetType().GetField("Speedometer");
        speed.SetValue(basic, Enum.ToObject(speed.FieldType, 1));
        hud.GetType().GetMethod("OnValidate").Invoke(hud, null);
        EditorUtility.SetDirty(hud);
        EditorUtility.SetDirty(type);
        var livery = FindAsset("CustomCarVariant");
        string tenderId = null;
        if (Loco.Tender != null)
        {
            carFolder = builtFolders[Loco.Tender];
            tenderId = Get<string>(FindAsset("CustomCarVariant"), "id");
            carFolder = builtFolders[Loco];
        }
        var tracks = RrChoices.spawnTracks ?? new int[0];
        SetArraySize(livery, "LocoSpawnGroups", tracks.Length);
        for (int i = 0; i < tracks.Length; i++)
        {
            Set(livery, $"LocoSpawnGroups.Array.data[{i}].Track", tracks[i]);
            Set(livery, $"LocoSpawnGroups.Array.data[{i}].AdditionalLiveries",
                tenderId == null ? new System.Collections.Generic.List<string>() : new System.Collections.Generic.List<string> { tenderId });
        }
        livery.GetType().GetMethod("ForceValidation", BF)?.Invoke(livery, null);
        EditorUtility.SetDirty(livery);
        string path = $"{carFolder}/{CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            ApplyRrSteamGraph(root.transform.Find("[sim]"), RrChoices);
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
        Line($"rr2dv review: actual brake valve + HUD {RrChoices.trainBrake}; {RrChoices.spawnMode}, {tracks.Length} tracks; profile {RrChoices.physics}; thermal regime {RrChoices.steamHeat}; runtime validation pending");
    }

    static void ApplyRrSteamGraph(Transform sim, RrReview choice)
    {
        var conn = sim.GetComponent<SimConnectionsDefinitionProxy>();
        conn.AfterImport();
        if (choice.steamHeat != "basis-approximation")
        {
            var heat = conn.portReferenceConnections.Single(p => p.portReferenceId == "steamEngine.INTAKE_TEMPERATURE");
            heat.portId = choice.steamHeat == "superheated" ? "firebox.TEMPERATURE" : "boiler.TEMPERATURE";
        }
        if (choice.physics == "geared")
        {
            if (choice.gearRatio <= 1 || choice.efficiency <= 0 || choice.efficiency > 1)
                throw new InvalidOperationException("Invalid reviewed gear ratio or efficiency");
            var direct = conn.connections.Single(p => p.fullPortIdOut == "steamEngine.TORQUE_OUT" && p.fullPortIdIn == "traction.TORQUE_IN");
            var crank = conn.portReferenceConnections.Single(p => p.portReferenceId == "steamEngine.CRANK_RPM");
            var rpm = Child(sim, "rr2dvEngineRPM", Vector3.zero).gameObject.AddComponent<ConstantMultiplierOffsetDefinition>();
            rpm.ID = "rr2dvEngineRPM"; rpm.Multiplier = choice.gearRatio;
            rpm.Input = new PortReferenceDefinition(DVPortValueType.RPM, "IN");
            rpm.Output = new PortDefinition(DVPortType.READONLY_OUT, DVPortValueType.RPM, "OUT");
            rpm.OnValidate();
            conn.portReferenceConnections.Add(new PortReferenceConnectionProxy { portReferenceId = rpm.ID + ".IN", portId = crank.portId });
            crank.portId = rpm.ID + ".OUT";
            var gear = Child(sim, "rr2dvGear", Vector3.zero).gameObject.AddComponent<TransmissionFixedGearDefinitionProxy>();
            gear.ID = "rr2dvGear"; gear.gearRatio = choice.gearRatio; gear.transmissionEfficiency = choice.efficiency;
            gear.OnValidate();
            direct.fullPortIdIn = gear.ID + ".TORQUE_IN";
            conn.connections.Add(new PortConnectionProxy { fullPortIdOut = gear.ID + ".TORQUE_OUT", fullPortIdIn = "traction.TORQUE_IN" });
            // The component's OnValidate registers it in executionOrder when it is added.
            // Move that entry into its required evaluation position rather than adding it twice.
            conn.executionOrder.RemoveAll(p => p == rpm || p == gear);
            var engine = conn.executionOrder.Single(p => p.ID == "steamEngine");
            var traction = conn.executionOrder.Single(p => p.ID == "traction");
            conn.executionOrder.Insert(conn.executionOrder.IndexOf(engine), rpm);
            conn.executionOrder.Insert(conn.executionOrder.IndexOf(traction), gear);
            // Steam demand continues to read engine.INTAKE_FLOW, now evaluated at geared crank RPM.
            if (!conn.portReferenceConnections.Any(p => p.portId == "steamEngine.INTAKE_FLOW"))
                throw new InvalidOperationException("Geared profile has no engine steam-demand consumer");
        }
        conn.OnValidate();
        EditorUtility.SetDirty(conn);
    }
}
