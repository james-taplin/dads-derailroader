using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Reflection;
using CCL.Types.Components;
using CCL.Types.Proxies.Controls;
using CCL.Types.Proxies.Indicators;
using CCL.Types.HUD;
using UnityEditor;
using UnityEngine;
using Object=UnityEngine.Object;

[InitializeOnLoad] static class FleetGaugePlayBootstrap {
    static FleetGaugePlayBootstrap() {
        if(SessionState.GetBool("rr2dv fleet gauges armed",false)) EditorApplication.delayCall+=()=>CclLocoBuild.FleetGaugeRuntime();
    }
}
public static partial class CclLocoBuild
{
    [Serializable] public class FleetCase {public string id,pack,carId,bundle,meshData;public GaugeSelection gauges;}
    [Serializable] public class FleetInput {public FleetCase[] cases;}
    static string FleetOut=>Environment.GetEnvironmentVariable("CCL_BUILD_OUT");
    static FleetInput FleetData()=>JsonUtility.FromJson<FleetInput>(File.ReadAllText(Environment.GetEnvironmentVariable("FLEET_ASSEMBLY_INPUT")));
    static void FleetAssert(bool value,string message) {if(!value) throw new Exception(message);}
    static void FleetFail(Exception e) {
        File.WriteAllText(Path.Combine(FleetOut,"failure.txt"),e.ToString());
        File.WriteAllText(Path.Combine(FleetOut,"result.json"),"{\"passed\":false}");Debug.LogException(e);EditorApplication.Exit(1);
    }
    static void CheckFleetReaders(GameObject root, GaugeSelection selection) {
        var hud=root.GetComponent<LocoIndicatorReaderProxy>();
        FleetAssert(hud.steam && hud.brakePipe && hud.brakeCylinder && hud.speed && hud.mainReservoir,"Missing essential/HUD readings: "+root.name);
        FleetAssert(root.GetComponentsInChildren<Transform>(true).Count(t=>t.name.StartsWith("gauge "))==selection.instruments.Length,"Wrong physical gauge count");
        foreach(var fit in selection.instruments) {
            var gauge=root.transform.Find("gauge "+fit.sourceGauge);FleetAssert(gauge,"Missing fitted assembly");
            var proxies=gauge.GetComponentsInChildren<IndicatorGaugeProxy>(true);
            FleetAssert(proxies.Length==(fit.reading=="brake"?2:1),"Wrong needle count: "+fit.reading);
            FleetAssert(proxies.All(p=>p.needle && p.needle.IsChildOf(gauge)),"Needle reference escaped fitted assembly");
            FleetAssert(gauge.Find("housing") && gauge.Find("glass") && gauge.Find("face"),"Incomplete gauge housing/face/glass");
            if(fit.reading=="brake") {
                FleetAssert(proxies.All(p=>p.minValue==1 && p.maxValue==11),"Brake zero must represent released atmospheric pressure");
                FleetAssert(proxies.Any(p=>p.GetComponent(T("CCL.Types.Proxies.Indicators.IndicatorBrakePipeReaderProxy"))),"Missing brake pipe reader");
                FleetAssert(proxies.Any(p=>p.GetComponent(T("CCL.Types.Proxies.Indicators.IndicatorBrakeCylinderReaderProxy"))),"Missing application pressure reader");
            }
            if(fit.reading=="speed" || fit.reading=="chest") {
                var lag=proxies.Single() as IndicatorGaugeLaggingProxy;
                FleetAssert(lag && lag.smoothTime==.5f && lag.updateThreshold==.001f,"Missing stock speed/chest damping");
            }
        }
        FleetAssert(hud.speed.GetComponent<IndicatorPortReaderProxy>().useAbsoluteValue,"Numerical speed must read magnitude");
    }
    public static void FleetGaugeRegression() {
        try {
            var input=FleetData();FleetAssert(input.cases.Length==21,"Fleet must cover all 21 cabs");
            var builds=new List<AssetBundleBuild>();
            foreach(var c in input.cases) {
                AssetBundle bundle=null;GameObject source=null;var meshes=new List<Mesh>();
                try {
                    bundle=AssetBundle.LoadFromFile(c.bundle);
                    var prefab=GaugeProbe.Collect(bundle.LoadAllAssets()).OfType<GameObject>().Single(g=>g.name==c.carId+"_template");
                    source=Object.Instantiate(prefab);meshes=GaugeProbe.ReadMeshes(c.meshData);GaugeProbe.ReplaceMeshes(source,meshes);
                    refBody=source.transform.Find("Model/"+c.pack+"_body");FleetAssert(refBody,"Missing source body");
                    Cfg=new LocoConfig {CarId=c.carId,Work="Assets/FleetGauges/"+c.id,MainPressureGauge=c.gauges.instruments.Single(f=>f.reading=="boiler").sourceGauge};
                    ownMats.Clear();carFolder=Cfg.Work;Folder(carFolder);BuildOwnAssets();
                    var root=new GameObject(CarId+"_interior");var hud=root.AddComponent<LocoIndicatorReaderProxy>();
                    var speed=Child(root.transform,"HUD-only speed",Vector3.zero);hud.speed=speed.gameObject.AddComponent<IndicatorGaugeProxy>();
                    speed.gameObject.AddComponent<IndicatorPortReaderProxy>().portId="traction.WHEEL_SPEED_KMH_EXT_IN";
                    foreach(var fit in c.gauges.instruments) Child(root.transform,"gauge "+fit.sourceGauge,Vector3.zero);
                    SaveRr2dvPrefab(root,$"{carFolder}/{CarId}_interior.prefab");Object.DestroyImmediate(root);
                    root=new GameObject(CarId+"_template");SaveRr2dvPrefab(root,$"{carFolder}/{CarId}_template.prefab");Object.DestroyImmediate(root);
                    var layout=ScriptableObject.CreateInstance<VanillaHUDLayout>();layout.HUDType=VanillaHUDLayout.BaseHUD.S060;
                    string hudPath=$"{carFolder}/{CarId}_hud.asset";
                    if(AssetDatabase.LoadAssetAtPath<VanillaHUDLayout>(hudPath)) AssetDatabase.DeleteAsset(hudPath);
                    AssetDatabase.CreateAsset(layout,hudPath);
                    string buildInput=Path.Combine(Application.dataPath,"Rr2dv/BuildInput.json");Directory.CreateDirectory(Path.GetDirectoryName(buildInput));
                    File.WriteAllText(buildInput,JsonUtility.ToJson(new GaugeBuildInput {gauges=c.gauges}));
                    BuildRr2dvGauges();BuildRr2dvGauges();BuildInteriorLOD();RestoreRr2dvGaugeLodGrabbers();RestoreRr2dvGaugeLodGrabbers();
                    RequireRr2dvSpeedHud();
                    var interior=AssetDatabase.LoadAssetAtPath<GameObject>($"{carFolder}/{CarId}_interior.prefab");CheckFleetReaders(interior,c.gauges);
                    var paths=new[] {$"{carFolder}/{CarId}_interior.prefab",$"{carFolder}/{CarId}_template.prefab"};
                    builds.Add(new AssetBundleBuild {assetBundleName=c.id,assetNames=paths});
                } finally {refBody=null;if(source) Object.DestroyImmediate(source);foreach(var mesh in meshes) Object.DestroyImmediate(mesh);if(bundle) bundle.Unload(true);}
            }
            string output=Path.Combine(FleetOut,"bundles");Directory.CreateDirectory(output);AssetDatabase.SaveAssets();
            BuildPipeline.BuildAssetBundles(output,builds.ToArray(),BuildAssetBundleOptions.ForceRebuildAssetBundle,BuildTarget.StandaloneWindows64);
            foreach(var c in input.cases) {
                var bundle=AssetBundle.LoadFromFile(Path.Combine(output,c.id));
                try {
                    var interior=bundle.LoadAllAssets<GameObject>().Single(g=>g.name==c.carId+"_interior");CheckFleetReaders(interior,c.gauges);
                    FleetAssert(!bundle.LoadAllAssets<Mesh>().Any(m=>m.name.StartsWith("s060_")),"Donor game mesh bytes embedded in export");
                    var lod=bundle.LoadAllAssets<GameObject>().Single(g=>g.name==c.carId+"_template").transform.Find("[interior LOD]");
                    foreach(var grabber in lod.GetComponentsInChildren<MeshGrabberFilter>(true))
                        FleetAssert(grabber.Filter && grabber.Filter.transform.IsChildOf(lod),"LOD grabber escaped its assembly");
                } finally {bundle.Unload(true);}
            }
            File.WriteAllText(Path.Combine(FleetOut,"proxy-fields.txt"),string.Join("\n",typeof(IndicatorGaugeProxy).Assembly.GetTypes().Where(t=>t.Name.Contains("IndicatorGauge"))
                .Select(t=>t.FullName+": "+string.Join(", ",t.GetFields().Select(f=>f.Name+"="+f.FieldType.Name)))));
            SessionState.SetBool("rr2dv fleet gauges armed",true);EditorApplication.isPlaying=true;
        } catch(Exception e) {FleetFail(e);}
    }
    public static void FleetGaugeRuntime() {
        if(!SessionState.GetBool("rr2dv fleet gauges armed",false)) return;SessionState.SetBool("rr2dv fleet gauges armed",false);
        ResolveEventHandler resolver=(sender,args)=>{
            string file=new AssemblyName(args.Name).Name+".dll";
            foreach(var folder in new[]{Environment.GetEnvironmentVariable("RR2DV_GAME_MANAGED"),Path.Combine(Environment.GetEnvironmentVariable("RR2DV_GAME_MANAGED"),"UnityModManager"),
                Path.Combine(Path.GetDirectoryName(Environment.GetEnvironmentVariable("RR2DV_CCL_RUNTIME")),"DVLangHelper"),Environment.GetEnvironmentVariable("RR2DV_CCL_RUNTIME")})
                if(File.Exists(Path.Combine(folder,file))) return Assembly.LoadFrom(Path.Combine(folder,file));
            return null;
        };
        try {
            AppDomain.CurrentDomain.AssemblyResolve+=resolver;
            var game=Assembly.LoadFrom(Path.Combine(Environment.GetEnvironmentVariable("RR2DV_GAME_MANAGED"),"Assembly-CSharp.dll"));
            var importer=Assembly.LoadFrom(Path.Combine(Environment.GetEnvironmentVariable("RR2DV_CCL_RUNTIME"),"CCL.Importer.dll"));
            var processor=importer.GetType("CCL.Importer.Processing.GrabberProcessor",true);
            var meshes=GaugeProbe.ReadMeshes(Environment.GetEnvironmentVariable("RR2DV_PRESSURE_MESHES")).ToDictionary(m=>m.name,m=>m);
            var materials=new[]{"LocoS060_Interior","LocoS060_Gauges","GlassIndoors"}.ToDictionary(n=>n,n=>new Material(Shader.Find("Standard")){name=n});
            foreach(var entry in new[]{new object[]{"s_meshCache",meshes},new object[]{"s_materialCache",materials}}) {
                var cache=processor.GetField((string)entry[0],BindingFlags.Static|BindingFlags.NonPublic).GetValue(null);
                cache.GetType().GetField("_cachedResources",BindingFlags.Instance|BindingFlags.NonPublic).SetValue(cache,entry[1]);
            }
            int instruments=0,samples=0;
            foreach(var c in FleetData().cases) {
                var bundle=AssetBundle.LoadFromFile(Path.Combine(FleetOut,"bundles",c.id));GameObject root=null,lod=null;
                try {
                    root=Object.Instantiate(bundle.LoadAllAssets<GameObject>().Single(g=>g.name==c.carId+"_interior"));root.SetActive(false);
                    lod=Object.Instantiate(bundle.LoadAllAssets<GameObject>().Single(g=>g.name==c.carId+"_template"));lod.SetActive(false);
                    foreach(var host in new[]{root,lod}) foreach(string method in new[]{"ProcessMeshGrabberFilter","ProcessMaterialGrabberRenderer"})
                        processor.GetMethod(method,BindingFlags.Static|BindingFlags.NonPublic).Invoke(null,new object[]{host});
                    foreach(var fit in c.gauges.instruments) {
                        var gauge=root.transform.Find("gauge "+fit.sourceGauge);instruments++;
                        foreach(var grabber in gauge.GetComponentsInChildren<MeshGrabberFilter>(true)) FleetAssert(grabber.Filter.sharedMesh,"Actual CCL resource binding failed");
                        var face=gauge.Find("face");var mesh=face.GetComponent<MeshFilter>().sharedMesh;var tri=mesh.triangles;var vertices=mesh.vertices;var normal=Vector3.zero;
                        for(int i=0;i<tri.Length;i+=3) normal+=Vector3.Cross(face.TransformPoint(vertices[tri[i+1]])-face.TransformPoint(vertices[tri[i]]),face.TransformPoint(vertices[tri[i+2]])-face.TransformPoint(vertices[tri[i]]));
                        FleetAssert(Vector3.Angle(normal,new Quaternion(fit.rotation[0],fit.rotation[1],fit.rotation[2],fit.rotation[3])*Vector3.back)<.1f,"Gauge face points away from fitted direction");
                        foreach(var proxy in gauge.GetComponentsInChildren<IndicatorGaugeProxy>(true)) {
                            var runtime=proxy.gameObject.AddComponent(game.GetType("IndicatorGauge",true));
                            foreach(string field in new[]{"needle","minValue","maxValue","minAngle","maxAngle","rotationAxis","unclamped"}) SetPressureField(runtime,field,proxy.GetType().GetField(field).GetValue(proxy));
                            foreach(float value in new[]{proxy.minValue,(proxy.minValue+proxy.maxValue)/2,proxy.maxValue}) {
                                runtime.GetType().GetProperty("Value").SetValue(runtime,value,null);
                                float angle=Mathf.Lerp(proxy.minAngle,proxy.maxAngle,(value-proxy.minValue)/(proxy.maxValue-proxy.minValue));
                                FleetAssert(Quaternion.Angle(proxy.needle.localRotation,Quaternion.AngleAxis(angle,proxy.rotationAxis))<.01f,"Runtime needle/calibration differs from face range");samples++;
                            }
                        }
                    }
                } finally {if(root) Object.DestroyImmediate(root);if(lod) Object.DestroyImmediate(lod);bundle.Unload(true);}
            }
            File.WriteAllText(Path.Combine(FleetOut,"result.json"),"{\"passed\":true,\"locomotives\":21,\"instruments\":"+instruments+",\"needleSamples\":"+samples+",\"bundleReload\":true,\"actualCclBinding\":true,\"gameTested\":false}");EditorApplication.Exit(0);
        } catch(Exception e) {FleetFail(e);}
        finally {AppDomain.CurrentDomain.AssemblyResolve-=resolver;}
    }
}
