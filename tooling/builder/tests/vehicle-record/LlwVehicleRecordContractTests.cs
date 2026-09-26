using System;
using System.IO;
using UnityEngine;

// Standalone contract harness; NOT installed in Assets/Editor. Compile with the actual LocoConfig,
// loader and Unity 2019 assemblies. Stub only the two core build methods, which tests never call.
public static class CclLocoBuild
{
    public static void Run(LocoConfig c) { throw new NotSupportedException("Harness must not build assets"); }
    public static void Phys(Component c, float min, float max, int n, float s, float d, float m, float dr, float a, float sc, float ss) { }
}
public static class LlwVehicleRecordContractTests
{
    const string Template = @"{
      ""schemaVersion"":1,""vehicleId"":""test"",
      ""config"":{""value"":{
        ""CarId"":""TEST"",""CarName"":""Test"",""Version"":""0.0.1"",""Author"":""Test"",
        ""SrcPrefab"":""Assets/test.prefab"",""Work"":""Assets/Test/loco"",""BodyName"":""body"",""Livery"":""Default"",
        ""Components"":[{""kind"":""Chuff"",""name"":""Chuff"",""pos"":[1,2,3],""rot"":[0,0,0,1],""scale"":[1,1,1]}],
        ""MaterialMap"":{""body"":""Assets/mat.mat""},""AnimationMap"":{},
        ""Liveries"":[[""Default"",[[""body"",""#ffffff""]]]],""Wheelsets"":[[0,1,1.2,3,""Drivers""]],
        ""WeightEmptyKg"":12000,""WheelRadius"":0.6,""WaterCapacityL"":0,""CoalCapacityKg"":0,
        ""CabZ"":null,""CabTeleportVolume"":[[0,2,-3],[2,2,2]],
        ""Bogies"":[{""Bogie"":""BogieF"",""Axles"":[1,-1]}],
        ""ExteriorShots"":[{""Fov"":40,""Pos"":[4,5,6],""Look"":[0,1,0],""File"":""test.png""}],
        ""RrLevers"":[{""Path"":""lever"",""Port"":""throttle.EXT_IN""}]
      },""unit"":""mixed SI / DV identifiers (test fixture)"",""basis"":""DV_choice"",""evidence"":[""contract test fixture""]},
      ""hooks"":{""value"":{
        ""CollisionBoxes"":[[""frame"",[0,1,0],[2,2,5]]],
        ""SimSpec"":{""steamEngine"":{""numCylinders"":2,""cylinderBore"":0.4},""_notes"":{""mass"":""fixture""}},
        ""BrakeRelease"":{""pos"":[1,2,3],""euler"":[0,90,180]},""LampKey"":{},
        ""LeverPhysics"":[{""path"":""lever"",""mass"":10,""notches"":11,""scrollAngleFraction"":0.25}]
      },""unit"":""mixed SI / DV proxy values (test fixture)"",""basis"":""DV_choice"",""evidence"":""contract test fixture""}
    }";
    static int passed;
    static void Check(bool condition, string name) { if (!condition) throw new Exception(name); passed++; Console.WriteLine("PASS " + name); }
    static void Reject(string input, string expected, string name)
    {
        try { LlwVehicleRecord.LoadJson(input); throw new Exception("Accepted invalid input: " + name); }
        catch (InvalidDataException e) { Check(e.Message.Contains(expected), name + " [" + e.Message + "]"); }
    }
    public static int Main(string[] args)
    {
        try
        {
            var c = LlwVehicleRecord.LoadJson(Template);
            Check(c.CarId == "TEST" && c.WheelRadius == 0.6f && c.WaterCapacityL == 0, "identity, numeric fields, explicit zero");
            Check(c.CabZ == null && c.CabTeleportVolume.Value.size.y == 2, "nullable remains unknown, nested vector tuple");
            Check(c.Components[0].pos.z == 3 && c.Components[0].rot.w == 1 && c.MaterialMap["body"] == "Assets/mat.mat", "source vectors, quaternion and dictionary");
            Check(c.Liveries[0].colors[0].hex == "#ffffff" && c.Wheelsets[0].axles == 3, "nested tuple arrays");
            Check(c.ExteriorShots[0].Fov == 40 && c.CollisionBoxes(null)[0].name == "frame", "constructor-backed Shot and collision hook");
            Check(c.SimSpec(null)["steamEngine"]["numCylinders"] is int && c.SimSpec(null)["steamEngine"]["cylinderBore"] is float, "simulation values use core-supported int/float types");
            Check(c.BrakeRelease(null).euler.y == 90 && c.RrLevers[0].Phys != null, "pose and lever hooks");
            Reject(Template.Replace("\"WheelRadius\":0.6", "\"WheelRadius\":null"), "unknown/null", "null physical radius rejected");
            Reject(Template.Replace("\"WheelRadius\":0.6", "\"WheelRaduis\":0.6"), "unknown", "misspelled config field rejected");
            Reject(Template.Replace("\"WeightEmptyKg\":12000", "\"WeightEmptyKg\":-1"), "positive", "invalid mass rejected");
            Reject(Template.Replace("\"basis\":\"DV_choice\"", "\"basis\":\"guessed\""), "basis", "invalid basis rejected");
            Reject(Template.Replace("\"Work\":\"Assets/Test/loco\"", "\"Work\":\"Assets/Test\""), "dedicated", "unsafe generation folder rejected");
            Reject(Template.Replace("\"schemaVersion\":1", "\"schemaVersion\":1,\"schemaVersion\":1"), "duplicate", "duplicate JSON key rejected");
            Reject(Template.Replace("\"WheelRadius\":0.6", "\"WheelRadius\":1e999"), "nonfinite", "nonfinite number rejected");
            Reject(Template.Replace("\"Fov\":40", "\"Fov\":40,"), "expected string", "trailing comma rejected");
            Reject("{\"schemaVersion\":1,\"vehicleId\":\"test\",\"config\":{\"WheelRadius\":0.6}}", "requires value/unit/basis/evidence", "unprovenanced number rejected");
            Reject(Template.Replace("\"WaterCapacityL\":0,", ""), "WaterCapacityL", "missing resource capacity rejected");
            if (args.Length > 0) { var actual = LlwVehicleRecord.Load(args[0]); Check(actual.CarId != "TEST", "actual record validates: " + actual.CarId); }
            Console.WriteLine("RESULT " + passed + " passed"); return 0;
        }
        catch (Exception e) { Console.Error.WriteLine(e); return 1; }
    }
}
