using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Reflection;
using UnityEditor;
using UnityEngine;
using Object=UnityEngine.Object;

[InitializeOnLoad] static class FleetOilPlayBootstrap {
    static FleetOilPlayBootstrap() {
        if(SessionState.GetBool("rr2dv fleet oil armed",false))EditorApplication.delayCall+=()=>CclLocoBuild.FleetOilRuntime();
    }
}

public static partial class CclLocoBuild
{
    [Serializable] public class OilCase {public string id,pack,carId,bundle,meshData;public float radius;public float[] axleZ;public OilSelection oiling;}
    [Serializable] public class OilInput {public OilCase[] cases;}
    [Serializable] public class OilPart {public string path;public bool travels;public float[] centre,size,pivot;}
    [Serializable] public class OilRod {public string path;public float side,phase;public float[] crank,cross;}
    [Serializable] public class OilSeatOut {public string parentPath,role,evidence;public int axle;public float side,phase;public float[] local,position;}
    [Serializable] public class OilFinding {public string id,error;public OilPart[] parts;public OilRod[] rods;public OilSeatOut[] seats;}
    [Serializable] public class OilScanResult {public bool passed;public OilFinding[] findings;}
    static float[] OilVector(Vector3 v)=>new[]{v.x,v.y,v.z};
    static OilInput OilCases()=>JsonUtility.FromJson<OilInput>(File.ReadAllText(Environment.GetEnvironmentVariable("FLEET_OIL_INPUT")));
    static void OilAssert(bool condition,string why){if(!condition)throw new Exception(why);}
    static void OilFail(Exception e){
        string output=Environment.GetEnvironmentVariable("CCL_BUILD_OUT");Directory.CreateDirectory(output);
        File.WriteAllText(Path.Combine(output,"failure.txt"),e.ToString());
        File.WriteAllText(Path.Combine(output,"result.json"),"{\"passed\":false}");Debug.LogException(e);EditorApplication.Exit(1);
    }
    // Test-only copies of hierarchy/curves. No game code or source assets are shipped by this harness.
    static AnimationClip OilCopyClip(Animator source) {
        // A loaded player-bundle clip has stripped editor curves. Saving an Instantiate of it loses motion.
        // Bake observed transforms at the same 64 validation phases into a test-only editor clip.
        var original=source.runtimeAnimatorController.animationClips[0];
        var transforms=source.GetComponentsInChildren<Transform>(true);
        var values=transforms.ToDictionary(t=>t,t=>Enumerable.Range(0,10).Select(i=>new List<Keyframe>()).ToArray());
        for(int step=0;step<=64;step++) {
            float time=step/64f*original.length;original.SampleAnimation(source.gameObject,time);
            foreach(var t in transforms) {
                var p=t.localPosition;var r=t.localRotation;var s=t.localScale;
                var row=new[]{p.x,p.y,p.z,r.x,r.y,r.z,r.w,s.x,s.y,s.z};
                for(int i=0;i<10;i++)values[t][i].Add(new Keyframe(time,row[i]));
            }
        }
        original.SampleAnimation(source.gameObject,0);
        var clip=new AnimationClip {name="observed driver motion",wrapMode=WrapMode.Loop};
        var names=new[]{"m_LocalPosition.x","m_LocalPosition.y","m_LocalPosition.z","m_LocalRotation.x","m_LocalRotation.y","m_LocalRotation.z","m_LocalRotation.w","m_LocalScale.x","m_LocalScale.y","m_LocalScale.z"};
        foreach(var t in transforms)for(int i=0;i<10;i++) {
            var keys=values[t][i];if(keys.Max(k=>k.value)-keys.Min(k=>k.value)<.0000001f)continue;
            var curve=new AnimationCurve(keys.ToArray());
            for(int k=0;k<curve.length;k++){AnimationUtility.SetKeyLeftTangentMode(curve,k,AnimationUtility.TangentMode.Linear);AnimationUtility.SetKeyRightTangentMode(curve,k,AnimationUtility.TangentMode.Linear);}
            AnimationUtility.SetEditorCurve(clip,EditorCurveBinding.FloatCurve(AnimationUtility.CalculateTransformPath(t,source.transform),typeof(Transform),names[i]),curve);
        }
        clip.EnsureQuaternionContinuity();return clip;
    }
    static Transform OilCopyTree(Transform source,Transform parent,string folder,ref int asset) {
        var target=new GameObject(source.name).transform;target.SetParent(parent,false);
        target.localPosition=source.localPosition;target.localRotation=source.localRotation;target.localScale=source.localScale;
        foreach(Transform child in source)OilCopyTree(child,target,folder,ref asset);
        var animator=source.GetComponent<Animator>();
        if(animator && animator.name.StartsWith("[anim] drivers") && animator.runtimeAnimatorController && animator.runtimeAnimatorController.animationClips.Length>0) {
            var clip=OilCopyClip(animator);
            AssetDatabase.CreateAsset(clip,folder+"/clip"+asset+".anim");
            var controller=UnityEditor.Animations.AnimatorController.CreateAnimatorControllerAtPath(folder+"/controller"+(asset++)+".controller");
            controller.AddMotion(clip);var copy=target.gameObject.AddComponent<Animator>();copy.runtimeAnimatorController=controller;
        }
        if(source.GetComponent<MeshFilter>())target.gameObject.AddComponent<MeshFilter>();
        return target;
    }
    public static void FleetOilRegression() {
        try {
            OilAssert(OilCases().cases.Length==21,"Oil regression must cover all 21 locomotives");
            var builds=new List<AssetBundleBuild>();
            foreach(var c in OilCases().cases) {
                AssetBundle bundle=null;GameObject source=null,fixture=null;List<Mesh> meshes=null;
                try {
                    bundle=AssetBundle.LoadFromFile(c.bundle);
                    source=Object.Instantiate(GaugeProbe.Collect(bundle.LoadAllAssets()).OfType<GameObject>().Single(g=>g.name==c.carId+"_template"));
                    meshes=GaugeProbe.ReadMeshes(c.meshData);GaugeProbe.ReplaceMeshes(source,meshes);
                    refBody=source.transform.Find("Model/"+c.pack+"_body");
                    Cfg=new LocoConfig {CarId=c.carId,BodyName=c.pack+"_body",WheelRadius=c.radius,
                        EngineUnits=new List<EngineUnit>{new EngineUnit {GroupName="drivers",DriverParts=c.axleZ.Select(z=>"measured axle").ToArray()}}};
                    var seats=RrOilApplyLayout(refBody,c.axleZ,c.oiling);
                    string folder="Assets/FleetOil/"+c.id;if(AssetDatabase.IsValidFolder(folder))AssetDatabase.DeleteAsset(folder);Folder(folder);int asset=0;
                    fixture=new GameObject(c.carId+"_oil");
                    var body=OilCopyTree(refBody,fixture.transform,folder,ref asset);
                    var cups=new GameObject("ManualOilingPoints").transform;cups.SetParent(fixture.transform,false);
                    for(int i=0;i<seats.Count;i++) {
                        var fit=c.oiling.points[i];var host=body.Find(fit.parentPath);
                        var provider=new GameObject(fit.tag).transform;provider.SetParent(host,false);provider.localPosition=seats[i].local;
                        provider.gameObject.AddComponent<CCL.Types.Proxies.Util.PositionSyncProviderProxy>().syncTag=fit.tag;
                        var cup=new GameObject(fit.tag).transform;cup.SetParent(cups,false);cup.position=provider.position;
                        cup.gameObject.AddComponent<CCL.Types.Components.ManualOilingPoint>().SyncTag=fit.tag;
                    }
                    string prefab=folder+"/"+c.carId+"_oil.prefab";SaveRr2dvPrefab(fixture,prefab);
                    builds.Add(new AssetBundleBuild {assetBundleName=c.id,assetNames=new[]{prefab}});
                }finally{refBody=null;if(source)Object.DestroyImmediate(source);if(fixture)Object.DestroyImmediate(fixture);
                    if(meshes!=null)foreach(var m in meshes)Object.DestroyImmediate(m);if(bundle)bundle.Unload(true);}
            }
            AssetDatabase.SaveAssets();string outDir=Path.Combine(Environment.GetEnvironmentVariable("CCL_BUILD_OUT"),"bundles");Directory.CreateDirectory(outDir);
            OilAssert(BuildPipeline.BuildAssetBundles(outDir,builds.ToArray(),BuildAssetBundleOptions.ForceRebuildAssetBundle,BuildTarget.StandaloneWindows64),"Oil fixture bundle export failed");
            SessionState.SetBool("rr2dv fleet oil armed",true);EditorApplication.isPlaying=true;
        }catch(Exception e){OilFail(e);}
    }

    public static void FleetOilResume() {SessionState.SetBool("rr2dv fleet oil armed",true);EditorApplication.isPlaying=true;}
    public static void FleetOilRuntime() {
        if(!SessionState.GetBool("rr2dv fleet oil armed",false))return;SessionState.SetBool("rr2dv fleet oil armed",false);
        ResolveEventHandler resolver=(sender,args)=>{
            string file=new AssemblyName(args.Name).Name+".dll";
            foreach(var folder in new[]{Environment.GetEnvironmentVariable("RR2DV_GAME_MANAGED"),Path.Combine(Environment.GetEnvironmentVariable("RR2DV_GAME_MANAGED"),"UnityModManager"),
                Path.Combine(Path.GetDirectoryName(Environment.GetEnvironmentVariable("RR2DV_CCL_RUNTIME")),"DVLangHelper"),Environment.GetEnvironmentVariable("RR2DV_CCL_RUNTIME")})
                if(File.Exists(Path.Combine(folder,file)))return Assembly.LoadFrom(Path.Combine(folder,file));return null;
        };
        try {
            AppDomain.CurrentDomain.AssemblyResolve+=resolver;
            var game=Assembly.LoadFrom(Path.Combine(Environment.GetEnvironmentVariable("RR2DV_GAME_MANAGED"),"Assembly-CSharp.dll"));
            var importer=Assembly.LoadFrom(Path.Combine(Environment.GetEnvironmentVariable("RR2DV_CCL_RUNTIME"),"CCL.Importer.dll"));
            var providerType=game.GetType("DV.Util.PositionSyncProvider",true);var consumerType=game.GetType("DV.Util.PositionSyncConsumer",true);
            var processType=importer.GetType("CCL.Importer.Processing.OilingPointsProcessor",true);
            // Stand-in visual prefab with real DV components; exercises the actual CCL tag/port import.
            var cupPrefab=new GameObject("test cup");cupPrefab.SetActive(false);
            foreach(string name in new[]{"DV.Util.PositionSyncConsumer","DV.Simulation.Ports.InteractablePortFeeder","DV.Simulation.Ports.OilingPointPortFeederReader",
                "DV.Simulation.Ports.IndicatorPortReader","DV.Simulation.Ports.LayeredAudioPortReader"})cupPrefab.AddComponent(game.GetType(name,true));
            processType.GetField("s_oilingPointCupOnly",BindingFlags.Static|BindingFlags.NonPublic).SetValue(null,cupPrefab);
            int samples=0,total=0;var receipts=new List<string>();
            bool production=Environment.GetEnvironmentVariable("FLEET_OIL_PRODUCTION")=="1";
            foreach(var c in OilCases().cases) {
                var bundle=AssetBundle.LoadFromFile(production?c.bundle:Path.Combine(Environment.GetEnvironmentVariable("FLEET_OIL_BUNDLES")??Path.Combine(Environment.GetEnvironmentVariable("CCL_BUILD_OUT"),"bundles"),c.id));
                var assets=GaugeProbe.Collect(bundle.LoadAllAssets()).OfType<GameObject>().ToArray();
                var root=Object.Instantiate(production?assets.Single(g=>g.name==c.carId+"_template"):bundle.LoadAllAssets<GameObject>().Single());
                try {
                    var body=root.transform.Find((production?"Model/":"")+c.pack+"_body");
                    Transform cups;
                    if(production) {
                        var interactables=Object.Instantiate(assets.Single(g=>g.name==c.carId+"_interactables"),root.transform);
                        interactables.transform.localPosition=Vector3.zero;interactables.transform.localRotation=Quaternion.identity;
                        cups=interactables.transform.Find("ManualOilingPoints");
                    }else cups=root.transform.Find("ManualOilingPoints");
                    var providers=body.GetComponentsInChildren<CCL.Types.Proxies.Util.PositionSyncProviderProxy>(true);
                    OilAssert(providers.Length==c.oiling.points.Length,"Export changed provider count: "+c.id);
                    var actual=new Dictionary<string,Component>();
                    foreach(var proxy in providers) {
                        var fit=c.oiling.points.Single(p=>p.tag==proxy.syncTag);
                        OilAssert(AnimationUtility.CalculateTransformPath(proxy.transform.parent,body)==fit.parentPath,"Export changed moving parent");
                        OilAssert(Vector3.Distance(proxy.transform.localPosition,GaugeVector(fit.local))<.000001f,"Export changed local oil-cup anchor");
                        var runtimeProvider=proxy.gameObject.AddComponent(providerType);providerType.GetField("syncTag").SetValue(runtimeProvider,proxy.syncTag);actual.Add(proxy.syncTag,runtimeProvider);
                    }
                    var simObject=new GameObject("oil definition");simObject.SetActive(false);
                    var sim=Assembly.LoadFrom(Path.Combine(Environment.GetEnvironmentVariable("RR2DV_GAME_MANAGED"),"DV.Simulation.dll"));
                    var definition=simObject.AddComponent(sim.GetType("LocoSim.Definitions.ManualOilingPointsDefinition",true));
                    definition.GetType().GetField("ID").SetValue(definition,"oilingPoints");
                    processType.GetMethod("ProcessPrefab",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(Activator.CreateInstance(processType),new object[]{cups.gameObject,definition});
                    var consumers=cups.GetComponentsInChildren(consumerType,true).Cast<Component>().ToArray();
                    OilAssert(consumers.Length==providers.Length,"CCL did not create every oil cup: "+c.id);
                    foreach(var consumer in consumers) {
                        string tag=(string)consumerType.GetField("syncTag").GetValue(consumer);
                        int index=Array.FindIndex(c.oiling.points,p=>p.tag==tag);
                        OilAssert(index>=0,"CCL created an unknown oil-cup tag");
                        foreach(var field in new[]{new[]{"DV.Simulation.Ports.InteractablePortFeeder","portId","POINT_DOOR_EXT_IN"},
                            new[]{"DV.Simulation.Ports.OilingPointPortFeederReader","refillPortId","REFILL_EXT_IN"},
                            new[]{"DV.Simulation.Ports.IndicatorPortReader","portId","OIL_LEVEL_NORMALIZED"}}) {
                            var type=game.GetType(field[0],true);var component=consumer.GetComponent(type);
                            OilAssert((string)type.GetField(field[1]).GetValue(component)=="oilingPoints."+field[2]+"_"+index,"CCL assigned the wrong oil simulation port");
                        }
                        consumerType.GetMethod("SetProviderTransform").Invoke(consumer,new object[]{actual[tag]});
                    }
                    var animators=body.GetComponentsInChildren<Animator>(true).Where(a=>a.name.StartsWith("[anim] drivers")).ToList();
                    OilAssert(animators.Count>0,"Export lost driver animation");
                    foreach(var a in animators)a.enabled=false;
                    var origins=new Dictionary<string,Vector3>();var travel=actual.Keys.ToDictionary(k=>k,k=>0f);
                    foreach(int pose in new[]{0,1}) {
                        root.transform.position=pose==0?Vector3.zero:new Vector3(123,7,-456);
                        root.transform.rotation=pose==0?Quaternion.identity:Quaternion.Euler(3,71,-4);
                        foreach(int direction in new[]{1,-1})for(int step=0;step<64;step++) {
                            float phase=direction>0?step/64f:(63-step)/64f;Rr2dvSampleGear(animators,phase);
                            foreach(var consumer in consumers) {
                                string tag=(string)consumerType.GetField("syncTag").GetValue(consumer);
                                consumerType.GetMethod("Sync").Invoke(consumer,null);
                                OilAssert(Vector3.Distance(consumer.transform.position,actual[tag].transform.position)<.0001f,"Oil cup detached while travelling: "+c.id+" / "+tag);
                                OilAssert(Quaternion.Angle(consumer.transform.localRotation,Quaternion.identity)<.001f,"Oil cup inherited rod rotation; stock cups must stay upright");samples++;
                                if(pose==0) {
                                    if(!origins.ContainsKey(tag))origins.Add(tag,consumer.transform.position);
                                    travel[tag]=Mathf.Max(travel[tag],Vector3.Distance(origins[tag],consumer.transform.position));
                                }
                            }
                        }
                    }
                    OilAssert(travel.Values.All(v=>v>.02f),"Export lost oil-cup travel: "+c.id+" / "+string.Join(", ",travel.Select(k=>k.Key+"="+k.Value.ToString("F5")))+
                        " / "+string.Join(", ",animators.Select(a=>a.name+" clip "+a.runtimeAnimatorController.animationClips[0].name+" curves "+AnimationUtility.GetCurveBindings(a.runtimeAnimatorController.animationClips[0]).Length)));
                    total+=providers.Length;receipts.Add(c.id+": "+providers.Length+" cups, 64 forward + 64 reverse phases at two car poses, exported CCL tags + actual DV position sync");
                    Object.DestroyImmediate(simObject);
                }finally{Object.DestroyImmediate(root);bundle.Unload(true);}
            }
            Object.DestroyImmediate(cupPrefab);
            string output=Environment.GetEnvironmentVariable("CCL_BUILD_OUT");
            File.WriteAllText(Path.Combine(output,"runtime.txt"),string.Join("\n",receipts));
            File.WriteAllText(Path.Combine(output,"result.json"),"{\"passed\":true,\"locos\":"+OilCases().cases.Length+",\"cups\":"+total+",\"motionSamples\":"+samples+"}");EditorApplication.Exit(0);
        }catch(Exception e){OilFail(e);}finally{AppDomain.CurrentDomain.AssemblyResolve-=resolver;}
    }
    public static void FleetOilScan()
    {
        var findings=new List<OilFinding>();
        foreach(var c in OilCases().cases) {
            var f=new OilFinding {id=c.id};AssetBundle bundle=null;GameObject root=null;List<Mesh> meshes=null;
            try {
                bundle=AssetBundle.LoadFromFile(c.bundle);
                root=Object.Instantiate(GaugeProbe.Collect(bundle.LoadAllAssets()).OfType<GameObject>().Single(g=>g.name==c.carId+"_template"));
                meshes=GaugeProbe.ReadMeshes(c.meshData);GaugeProbe.ReplaceMeshes(root,meshes);
                refBody=root.transform.Find("Model/"+c.pack+"_body");
                Cfg=new LocoConfig {CarId=c.carId,BodyName=c.pack+"_body",WheelRadius=c.radius,
                    EngineUnits=new List<EngineUnit>{new EngineUnit {GroupName="drivers",DriverParts=c.axleZ.Select(z=>"measured axle").ToArray()}}};
                using(new Rr2dvLodScope(refBody)) {
                    Rr2dvMotion=Rr2dvGearMotion(refBody);
                    f.parts=Rr2dvMotion.Where(k=>k.Key.GetComponent<MeshRenderer>().enabled).Select(k=> {
                        var bounds=k.Key.GetComponent<MeshRenderer>().bounds;
                        return new OilPart {path=AnimationUtility.CalculateTransformPath(k.Key,refBody),travels=k.Value,centre=OilVector(bounds.center),size=OilVector(bounds.size),pivot=OilVector(k.Key.parent.position)};
                    }).ToArray();
                    f.rods=Rr2dvMainRods(refBody).Select(r=>new OilRod {path=AnimationUtility.CalculateTransformPath(r.rod,refBody),side=r.side,phase=r.levelPhase,
                        crank=OilVector(r.rod.TransformPoint(r.crankEnd)),cross=OilVector(r.rod.TransformPoint(r.crossEnd))}).ToArray();
                    if(Environment.GetEnvironmentVariable("FLEET_OIL_FIT")=="1") {
                        var seats=RrOilMeasureLayout(refBody,c.axleZ);
                        f.seats=seats.Select(s=>new OilSeatOut {parentPath=AnimationUtility.CalculateTransformPath(s.host,refBody),
                            role=s.role,evidence=s.evidence,axle=s.axle,side=s.side,phase=s.phase,local=OilVector(s.local),position=OilVector(s.Position)}).ToArray();
                    }
                }
            }catch(Exception e){f.error=e.ToString();}
            finally {refBody=null;if(root)Object.DestroyImmediate(root);if(meshes!=null)foreach(var m in meshes)Object.DestroyImmediate(m);if(bundle)bundle.Unload(true);}
            findings.Add(f);
        }
        var result=new OilScanResult {passed=findings.All(f=>string.IsNullOrEmpty(f.error)),findings=findings.ToArray()};
        string output=Environment.GetEnvironmentVariable("CCL_BUILD_OUT");Directory.CreateDirectory(output);
        File.WriteAllText(Path.Combine(output,"result.json"),JsonUtility.ToJson(result,true));EditorApplication.Exit(result.passed?0:1);
    }
}
