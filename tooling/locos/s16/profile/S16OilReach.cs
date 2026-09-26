using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Text;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

// Offline geometry screening. This deliberately makes NO game/VR reach claim.
// Reads the already-built prefab; never saves or modifies project assets.
public static class S16OilReach
{
    [Serializable] public class MeshData { public string name; public Vector3[] vertices; public int[] triangles; }
    [Serializable] public class Stock { public string source, sourceSha256, prefab, notes; public MeshData cup, lid; public Vector3 hinge, triggerCentre; public float triggerRadius; }
    [Serializable] public class Sample { public string tag; public float phase, reverser; public Vector3 position; public int standingClear, crouchedClear; public float minimumClearEyeDistance; public string[] rayBlockers, cupCrossings, lidSweepCrossings, triggerOverlaps; }
    [Serializable] public class Summary { public string tag; public int samples, standingVisible, crouchedVisible, eitherVisible, cupCrossingSamples, lidCrossingSamples; }
    [Serializable] public class Result { public int schema=1, phases=32; public string status, carId, stockSourceSha256, assumptions; public bool runtimeValidated=false; public Sample[] samples; public Summary[] summary; }
    class Cup { public Transform provider; public GameObject body, lid, trigger; public Collider bodyCollider, lidCollider, triggerCollider; }
    class Solid { public Transform source; public Mesh original, baked, world; public MeshCollider collider; public SkinnedMeshRenderer skinned; }
    static readonly int[] Postures = { 0, 1 };

    static Mesh BuildMesh(MeshData data)
    {
        var mesh = new Mesh { name = data.name + "_screen_only" };
        mesh.vertices = data.vertices; mesh.triangles = data.triangles; mesh.RecalculateBounds();
        return mesh;
    }
    static string PathOf(Transform t)
    {
        var names = new List<string>(); while (t) { names.Add(t.name); t=t.parent; }
        names.Reverse();return string.Join("/",names);
    }
    static void SampleAnimator(Animator animator,float normalized)
    {
        var controller=animator.runtimeAnimatorController as AnimatorController;
        if (!controller || controller.layers.Length==0)throw new InvalidOperationException("Missing sampled controller "+animator.name);
        var clip=controller.layers[0].stateMachine.defaultState.motion as AnimationClip;
        if(!clip)throw new InvalidOperationException("Expected clip motion "+animator.name);
        clip.SampleAnimation(animator.gameObject,Mathf.Clamp01(normalized)*clip.length);
    }
    static List<(int a,int b)> Edges(int[] triangles)
    {
        var seen=new HashSet<string>();var result=new List<(int,int)>();
        for(int i=0;i<triangles.Length;i+=3)for(int j=0;j<3;j++)
        {
            int a=triangles[i+j],b=triangles[i+(j+1)%3];if(a>b){int c=a;a=b;b=c;}
            if(seen.Add(a+":"+b))result.Add((a,b));
        }
        return result;
    }
    static bool SegmentHits(Collider collider,Vector3 a,Vector3 b)
    {
        Vector3 delta=b-a;float length=delta.magnitude;if(length<.00001f)return false;
        RaycastHit hit;
        return collider.Raycast(new Ray(a,delta/length),out hit,length) || collider.Raycast(new Ray(b,-delta/length),out hit,length);
    }
    static HashSet<string> Crossings(Vector3[] vertices,List<(int a,int b)> edges,HashSet<Collider> candidates,HashSet<Collider> ignored)
    {
        var bounds=new Bounds(vertices[0],Vector3.zero);foreach(var v in vertices)bounds.Encapsulate(v);
        bounds.Expand(.0005f);var hits=new HashSet<string>();
        foreach(var collider in candidates)
        {
            if(!collider || !collider.enabled || collider.isTrigger || ignored.Contains(collider) || !bounds.Intersects(collider.bounds))continue;
            if(edges.Any(e=>SegmentHits(collider,vertices[e.a],vertices[e.b])))hits.Add(PathOf(collider.transform));
        }
        return hits;
    }
    static GameObject MeshColliderObject(string name,Mesh mesh,Vector3 position)
    {
        var go=new GameObject(name);go.transform.position=position;
        var collider=go.AddComponent<MeshCollider>();collider.sharedMesh=mesh;return go;
    }
    public static void Run()
    {
        string output=Environment.GetEnvironmentVariable("RLW_PROBE_OUT")??Path.GetFullPath("S16OilReach");
        Directory.CreateDirectory(output);var log=new StringBuilder();bool oldBackfaces=Physics.queriesHitBackfaces;
        try
        {
            string record=Environment.GetEnvironmentVariable("CCL_VEHICLE_RECORD");
            string stockFile=Environment.GetEnvironmentVariable("CCL_OIL_STOCK_JSON");
            if(string.IsNullOrEmpty(record)||string.IsNullOrEmpty(stockFile))throw new InvalidOperationException("Set CCL_VEHICLE_RECORD and CCL_OIL_STOCK_JSON");
            LocoConfig cfg=LlwVehicleRecord.Load(record);Stock stock=JsonUtility.FromJson<Stock>(File.ReadAllText(stockFile));
            if(stock.cup.vertices.Length==0||stock.lid.vertices.Length==0)throw new InvalidOperationException("Missing measured stock cup/lid geometry");
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var prefabPath=AssetDatabase.FindAssets("t:Prefab",new[]{"Assets/_CCL_CARS"}).Select(AssetDatabase.GUIDToAssetPath)
                .Single(p=>System.IO.Path.GetFileName(p)==cfg.CarId+"_template.prefab");
            var go=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath));
            foreach(var collider in go.GetComponentsInChildren<Collider>(true))collider.enabled=false;
            var geometry=new HashSet<Collider>();var solids=new List<Solid>();
            foreach(var filter in go.GetComponentsInChildren<MeshFilter>(false))
            {
                var renderer=filter.GetComponent<Renderer>();if(!filter.sharedMesh||!renderer||!renderer.enabled)continue;
                var collisionObject=new GameObject(PathOf(filter.transform));var collider=collisionObject.AddComponent<MeshCollider>();
                solids.Add(new Solid{source=filter.transform,original=filter.sharedMesh,world=new Mesh(),collider=collider});geometry.Add(collider);
            }
            foreach(var renderer in go.GetComponentsInChildren<SkinnedMeshRenderer>(false))
            {
                if(!renderer.enabled)continue;var collisionObject=new GameObject(PathOf(renderer.transform));var collider=collisionObject.AddComponent<MeshCollider>();
                solids.Add(new Solid{source=renderer.transform,skinned=renderer,baked=new Mesh(),world=new Mesh(),collider=collider});geometry.Add(collider);
            }
            var providers=go.GetComponentsInChildren<Component>(true).Where(c=>c&&c.GetType().Name=="PositionSyncProviderProxy")
                .Select(c=>c.transform).OrderBy(t=>t.name,StringComparer.Ordinal).ToArray();
            if(providers.Length==0)throw new InvalidOperationException("No built oil providers");
            var driverAnimators=go.GetComponentsInChildren<Animator>(true).Where(a=>cfg.EngineUnits.Any(u=>a.name=="[anim] "+u.GroupName||a.name.StartsWith("[anim] "+u.GroupName+" "))).ToArray();
            var reverserAnimators=go.GetComponentsInChildren<Animator>(true).Where(a=>a.name=="[anim] reverser"||a.name.StartsWith("[anim] reverser ")).ToArray();
            if(driverAnimators.Length==0)throw new InvalidOperationException("No driver animator regions");
            Mesh cupMesh=BuildMesh(stock.cup),lidMesh=BuildMesh(stock.lid);
            var cupEdges=Edges(stock.cup.triangles);var lidEdges=Edges(stock.lid.triangles);
            var cups=new List<Cup>();
            foreach(var provider in providers)
            {
                var cup=new Cup{provider=provider};cup.body=MeshColliderObject("screen "+provider.name+" cup",cupMesh,provider.position);
                cup.lid=MeshColliderObject("screen "+provider.name+" lid",lidMesh,provider.position);
                cup.bodyCollider=cup.body.GetComponent<Collider>();cup.lidCollider=cup.lid.GetComponent<Collider>();
                cup.trigger=new GameObject("screen "+provider.name+" interactable sphere");var trigger=cup.trigger.AddComponent<SphereCollider>();
                trigger.radius=stock.triggerRadius;trigger.isTrigger=true;cup.triggerCollider=trigger;cups.Add(cup);
            }
            var allSolids=new HashSet<Collider>(geometry);foreach(var cup in cups){allSolids.Add(cup.bodyCollider);allSolids.Add(cup.lidCollider);}
            var queryable=new HashSet<Collider>(allSolids);foreach(var cup in cups)queryable.Add(cup.triggerCollider);
            var samples=new List<Sample>();Physics.queriesHitBackfaces=true;
            foreach(float reverser in new[]{0f,.5f,1f})for(int phase=0;phase<32;phase++)
            {
                foreach(var animator in reverserAnimators)SampleAnimator(animator,reverser);
                foreach(var animator in driverAnimators)
                {
                    var unit=cfg.EngineUnits.First(u=>animator.name=="[anim] "+u.GroupName||animator.name.StartsWith("[anim] "+u.GroupName+" "));
                    SampleAnimator(animator,(phase/32f+unit.StartOffset)%1f);
                }
                // Cook geometry at car/world scale with identity transforms.
                // The source hierarchy combines tiny mesh coordinates, 100x
                // scale, rotations and nonuniform scaling; directly attaching
                // MeshColliders produced false surface hits at every wheel.
                foreach(var solid in solids)
                {
                    var local=solid.original;if(solid.skinned){solid.skinned.BakeMesh(solid.baked);local=solid.baked;}
                    solid.collider.sharedMesh=null;solid.world.Clear();solid.world.indexFormat=local.indexFormat;
                    solid.world.vertices=local.vertices.Select(v=>solid.source.TransformPoint(v)).ToArray();
                    solid.world.triangles=local.triangles;solid.world.RecalculateBounds();solid.collider.sharedMesh=solid.world;
                }
                foreach(var cup in cups){cup.body.transform.position=cup.provider.position;cup.lid.transform.position=cup.provider.position;cup.trigger.transform.position=cup.provider.position+stock.triggerCentre;}
                Physics.SyncTransforms();
                foreach(var cup in cups)
                {
                    var ignored=new HashSet<Collider>{cup.bodyCollider,cup.lidCollider,cup.triggerCollider};
                    Vector3 pos=cup.provider.position,target=pos+stock.triggerCentre;float side=Mathf.Sign(pos.x);
                    var clear=new int[2];float minDistance=float.PositiveInfinity;var blockers=new HashSet<string>();
                    foreach(int posture in Postures)foreach(float x in new[]{2.1f,2.6f})foreach(float z in new[]{-.45f,0f,.45f})
                    {
                        var eye=new Vector3(side*x,posture==0?1.65f:.8f,target.z+z);var delta=target-eye;
                        var hits=Physics.RaycastAll(eye,delta.normalized,Mathf.Max(0,delta.magnitude-stock.triggerRadius),~0,QueryTriggerInteraction.Collide)
                            .Where(h=>queryable.Contains(h.collider)&&!ignored.Contains(h.collider)).OrderBy(h=>h.distance).ToArray();
                        if(hits.Length==0){clear[posture]++;minDistance=Mathf.Min(minDistance,delta.magnitude);}else blockers.Add(PathOf(hits[0].transform));
                    }
                    // The deliberately embedded support seam is omitted from cup body collision checks only.
                    var bodyIgnored=new HashSet<Collider>(ignored);foreach(var solid in solids.Where(s=>s.source==cup.provider.parent))bodyIgnored.Add(solid.collider);
                    var cupHits=Crossings(stock.cup.vertices.Select(v=>pos+v).ToArray(),cupEdges,allSolids,bodyIgnored);
                    var lidHits=new HashSet<string>();
                    for(int angle=0;angle<=90;angle+=15)
                    {
                        Quaternion turn=Quaternion.AngleAxis(-angle,Vector3.right);
                        var vertices=stock.lid.vertices.Select(v=>pos+stock.hinge+turn*(v-stock.hinge)).ToArray();
                        lidHits.UnionWith(Crossings(vertices,lidEdges,allSolids,ignored));
                    }
                    var overlaps=Physics.OverlapSphere(target,stock.triggerRadius,~0,QueryTriggerInteraction.Collide)
                        .Where(c=>queryable.Contains(c)&&!ignored.Contains(c)).Select(c=>PathOf(c.transform)).Distinct().OrderBy(x=>x).ToArray();
                    samples.Add(new Sample{tag=cup.provider.name,phase=phase/32f,reverser=reverser*2-1,position=pos,
                        standingClear=clear[0],crouchedClear=clear[1],minimumClearEyeDistance=float.IsInfinity(minDistance)?-1:minDistance,
                        rayBlockers=blockers.OrderBy(x=>x).ToArray(),cupCrossings=cupHits.OrderBy(x=>x).ToArray(),lidSweepCrossings=lidHits.OrderBy(x=>x).ToArray(),triggerOverlaps=overlaps});
                }
            }
            var summaries=samples.GroupBy(s=>s.tag).Select(g=>new Summary{tag=g.Key,samples=g.Count(),standingVisible=g.Count(s=>s.standingClear>0),
                crouchedVisible=g.Count(s=>s.crouchedClear>0),eitherVisible=g.Count(s=>s.standingClear+s.crouchedClear>0),
                cupCrossingSamples=g.Count(s=>s.cupCrossings.Length>0),lidCrossingSamples=g.Count(s=>s.lidSweepCrossings.Length>0)}).ToArray();
            var result=new Result{status=summaries.Any(s=>s.eitherVisible<s.samples||s.cupCrossingSamples>0||s.lidCrossingSamples>0)?"review_required":"screen_passed",
                carId=cfg.CarId,stockSourceSha256=stock.sourceSha256,samples=samples.ToArray(),summary=summaries,
                assumptions="Actual installed stock cup/cap mesh, hinge and 40mm trigger. Upright position-only sync. 32 wheel phases x reverser -1/0/+1. All enabled source mesh/skinned geometry, including body/tanks/cylinders, plus neighbouring cups/lids/triggers. 6 standing + 6 crouched rays per sample. Installed OilingPointReactionOnControlChange opens cap -90deg X and closes0; screen samples0..90deg at15deg including both runtime endpoint poses. Surface-edge crossing checks omit own rod mounting seam for cup body only. No continuous collision/solid containment proof; no runtime reach, selection-mask or VR proof. Geometric body occlusion can be stricter than DV oiler Interactable selection."};
            File.WriteAllText(System.IO.Path.Combine(output,"oil_reach_screen.json"),JsonUtility.ToJson(result,true));
            log.AppendLine(result.assumptions);log.AppendLine("STATUS "+result.status);
            foreach(var item in summaries)log.AppendLine($"{item.tag}: standing {item.standingVisible}/{item.samples}; crouched {item.crouchedVisible}/{item.samples}; either {item.eitherVisible}/{item.samples}; cup surface crossings {item.cupCrossingSamples}; lid sweep crossings {item.lidCrossingSamples}");
            File.WriteAllText(System.IO.Path.Combine(output,"oil_reach_screen.txt"),log.ToString());EditorApplication.Exit(0);
        }
        catch(Exception e){log.AppendLine("ERROR "+e);File.WriteAllText(System.IO.Path.Combine(output,"oil_reach_screen.txt"),log.ToString());Debug.LogException(e);EditorApplication.Exit(1);}
        finally{Physics.queriesHitBackfaces=oldBackfaces;}
    }
}
