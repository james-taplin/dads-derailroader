using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

// Run using Unity -executeMethod MeshIslandWeldTests.Run. Tests the core itself by reflection.
// Optional CCL_VEHICLE_RECORD adds source-specific sequential fitting extraction checks.
public static class MeshIslandWeldTests
{
    public static void Run()
    {
        var output = Environment.GetEnvironmentVariable("CCL_BUILD_OUT");
        Directory.CreateDirectory(output);
        var lines = new List<string>(); int failed = 0;
        Action<bool, string> check = (ok, text) => { lines.Add((ok ? "PASS " : "FAIL ") + text); if (!ok) failed++; };
        const BindingFlags flags = BindingFlags.Static | BindingFlags.NonPublic;
        var core = typeof(CclLocoBuild); var cfgField = core.GetField("Cfg", flags);
        var prior = cfgField.GetValue(null);
        var created = new List<Object>();
        string assetFolder = null;
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        try
        {
            var mesh = new Mesh { name = "scaled-fittings-test" };
            created.Add(mesh);
            mesh.vertices = new[] {
                Vector3.zero, new Vector3(.001f,0,0), new Vector3(0,.001f,0),
                new Vector3(0,0,.00002f), new Vector3(.001f,0,.00002f), new Vector3(0,.001f,.00002f) };
            mesh.triangles = new[] { 0, 1, 2, 3, 4, 5 };
            var islands = core.GetMethod("Islands", flags);
            var index = core.GetMethod("IslandIndex", flags);
            Func<int> count = () => ((IList)islands.Invoke(null, new object[] { mesh })).Count;
            Func<int> indexCount = () => ((ValueTuple<int[], Bounds[]>)index.Invoke(null, new object[] { mesh })).Item2.Length;
            var cfg = new LocoConfig(); cfgField.SetValue(null, cfg);
            check(count() == 1, "legacy default retains 1e-4 local connectivity (2mm gap at x100 merges)");
            check(indexCount() == 1, "default cached index matches island extraction");
            cfg.MeshIslandWeldTolerances[mesh.name] = .0000001f;
            check(count() == 2, "reviewed 1e-7 local grid separates two 2mm-apart faces at x100");
            check(indexCount() == 2, "cached index changes when tolerance changes for the same mesh");
            mesh.name = "unrelated-rod";
            check(count() == 1, "mesh-name override does not change unrelated source meshes");
            mesh.name = "scaled-fittings-test";
            cfg.MeshIslandWeldTolerances[mesh.name] = 0;
            bool rejected = false;
            try { count(); } catch (TargetInvocationException e) { rejected = e.InnerException is InvalidOperationException; }
            check(rejected, "zero weld tolerance rejects instead of merging or dividing silently");

            var beamBody = new GameObject("low-beam-body"); created.Add(beamBody);
            var beam = GameObject.CreatePrimitive(PrimitiveType.Cube); beam.transform.SetParent(beamBody.transform, false);
            beam.transform.localPosition = new Vector3(0,.775f,3f); beam.transform.localScale = new Vector3(1.5f,.15f,.2f);
            var tank = GameObject.CreatePrimitive(PrimitiveType.Cube); tank.transform.SetParent(beamBody.transform, false);
            tank.transform.localPosition = new Vector3(0,1.2f,3.35f); tank.transform.localScale = new Vector3(2f,.5f,.2f);
            var endBeam = core.GetMethod("EndBeam", flags);
            cfg.EndBeamProbeHeight = new Vector2(.70f,.85f);
            var beamArgs = new object[] { beamBody, 1, null };
            float sampled = (float)endBeam.Invoke(null, beamArgs);
            check(Mathf.Abs(sampled-3.1f)<.002f, "reviewed low beam band selects actual beam below high tank face");
            cfg.EndBeamProbeHeight = null;
            check(Mathf.Abs((float)endBeam.Invoke(null,new object[] {beamBody,1,null})-3.45f)<.002f, "null beam override retains existing coupler-height sampling band");
            cfg.EndBeamProbeHeight = new Vector2(.70f,.70f); rejected = false;
            try { endBeam.Invoke(null,new object[] {beamBody,1,null}); } catch(TargetInvocationException e) { rejected=e.InnerException is InvalidOperationException; }
            check(rejected, "beam probe span below 0.1m rejects");
            cfg.EndBeamProbeHeight = new Vector2(0,2); rejected = false;
            try { endBeam.Invoke(null,new object[] {beamBody,1,null}); } catch(TargetInvocationException e) { rejected=e.InnerException is InvalidOperationException; }
            check(rejected, "beam probe span above 0.4m rejects");

            var cabBody = new GameObject("low-cab"); created.Add(cabBody);
            var cabFloor = GameObject.CreatePrimitive(PrimitiveType.Cube); cabFloor.transform.SetParent(cabBody.transform,false);
            cabFloor.transform.localPosition = new Vector3(0,1f,0); cabFloor.transform.localScale = new Vector3(2f,.1f,2f);
            Object.DestroyImmediate(cabFloor.GetComponent<Collider>());
            var cabRoof = GameObject.CreatePrimitive(PrimitiveType.Cube); cabRoof.transform.SetParent(cabBody.transform,false);
            cabRoof.transform.localPosition = new Vector3(0,3.4f,0); cabRoof.transform.localScale = new Vector3(2f,.1f,2f);
            Object.DestroyImmediate(cabRoof.GetComponent<Collider>());
            var floorProbe = core.GetMethod("FloorY",flags);
            check(Mathf.Abs((float)floorProbe.Invoke(null,new object[]{cabBody,0f,0f})-3.45f)<.002f,"null cab origin preserves legacy roof-height sampling");
            cfg.CabFloorProbeHeight=2.2f;
            check(Mathf.Abs((float)floorProbe.Invoke(null,new object[]{cabBody,0f,0f})-1.05f)<.002f,"below-roof cab probe measures actual floor");
            rejected=false;
            try { floorProbe.Invoke(null,new object[]{cabBody,4f,0f}); } catch(TargetInvocationException e) { rejected=e.InnerException is InvalidOperationException; }
            check(rejected,"configured cab probe fails if no floor exists, without a fallback teleport height");

            string record = Environment.GetEnvironmentVariable("CCL_VEHICLE_RECORD");
            if (!string.IsNullOrEmpty(record))
            {
                cfg = LlwVehicleRecord.Load(record); cfgField.SetValue(null, cfg);
                string folderName = "__LLW_MeshWeldTests_" + Guid.NewGuid().ToString("N");
                AssetDatabase.CreateFolder("Assets", folderName); assetFolder = "Assets/" + folderName;
                AssetDatabase.CreateFolder(assetFolder, "Generated"); cfg.Work = assetFolder;
                var source = AssetDatabase.LoadAssetAtPath<GameObject>(cfg.SrcPrefab);
                var body = (GameObject)PrefabUtility.InstantiatePrefab(source); created.Add(body);
                var split = core.GetMethod("SplitIsland", flags);
                var save = core.GetMethod("SaveMesh", flags);
                var getScale = core.GetMethod("MeshIslandWeldScale", flags);
                if (cfg.RemovedMeshIslands.Length > 0)
                {
                    var removal = cfg.RemovedMeshIslands[0];
                    var edited = body.transform.Find(removal.Part).GetComponent<MeshFilter>();
                    var original = edited.sharedMesh; int originalTriangles = original.triangles.Length/3;
                    Func<Mesh,List<List<(int sub,int a,int b,int c)>>> groups = m => (List<List<(int sub,int a,int b,int c)>>)islands.Invoke(null,new object[]{m});
                    var sub = core.GetMethod("SubMesh",flags);
                    ReviewedMeshIslandRemoval.Apply(body,cfg.RemovedMeshIslands,groups,
                        (m,t) => (Mesh)sub.Invoke(null,new object[]{m,t}),
                        (m,n) => (Mesh)save.Invoke(null,new object[]{m,n}),s=>{});
                    check(original.triangles.Length/3==originalTriangles,"reviewed hardware removal leaves imported source mesh intact");
                    check(originalTriangles-edited.sharedMesh.triangles.Length/3==2744,"S16 removes exactly the independently reviewed 2744 coupling-hardware triangles");
                    bool duplicateRejected=false;
                    try { ReviewedMeshIslandRemoval.Apply(body,new[]{removal},groups,
                        (m,t) => (Mesh)sub.Invoke(null,new object[]{m,t}),
                        (m,n) => (Mesh)save.Invoke(null,new object[]{m,n}),s=>{}); }
                    catch(InvalidOperationException){duplicateRejected=true;}
                    check(duplicateRejected,"already-removed hardware cannot match a neighbouring structural island");
                }
                foreach (var fitting in cfg.Fittings)
                {
                    var part = body.transform.Find(fitting.Part);
                    if (!part) throw new InvalidOperationException("Missing fitting mesh " + fitting.Part);
                    var result = (ValueTuple<Mesh, Mesh, Bounds>)split.Invoke(null, new object[] { part, fitting.Centre });
                    created.Add(result.Item1); created.Add(result.Item2);
                    float error = (result.Item3.center - fitting.Centre).magnitude;
                    check(error < .002f, fitting.Name + " sequential source extraction matches measured island centre (error " + error.ToString("F6") + " m, " + (result.Item1.triangles.Length / 3) + " triangles)");
                    var remainder = (Mesh)save.Invoke(null, new object[] { result.Item2, "test_cut_" + fitting.Name.Replace(' ','_') });
                    float expectedScale = 1f/cfg.MeshIslandWeldTolerances["Cylinder.018"];
                    check((float)getScale.Invoke(null,new object[] {remainder}) == expectedScale, fitting.Name + " saved remainder retains original source weld tolerance (asset name " + remainder.name + ")");
                    part.GetComponent<MeshFilter>().sharedMesh = remainder;
                }
            }
        }
        catch (Exception e) { failed++; lines.Add("EXCEPTION " + e); }
        finally
        {
            cfgField.SetValue(null, prior);
            if (assetFolder != null) AssetDatabase.DeleteAsset(assetFolder);
            foreach (var o in created.AsEnumerable().Reverse()) if (o && !AssetDatabase.Contains(o)) Object.DestroyImmediate(o);
        }
        File.WriteAllLines(Path.Combine(output, "mesh_weld_tests.txt"), lines);
        File.WriteAllText(Path.Combine(output, "mesh_weld_tests.json"), "{\"passed\":" + lines.Count(l => l.StartsWith("PASS ")) + ",\"failed\":" + failed + "}");
        EditorApplication.Exit(failed == 0 ? 0 : 1);
    }
}
