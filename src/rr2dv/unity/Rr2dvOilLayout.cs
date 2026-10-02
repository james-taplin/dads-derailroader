using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

public static partial class CclLocoBuild
{
    [Serializable] public class OilFit {
        public string tag,parentPath,role,evidence;
        public int axle;
        public float side,phase;
        public float[] local;
    }
    [Serializable] public class OilSelection {public int schema;public string carId,state;public float[] axleZ;public OilFit[] points;}
    [Serializable] class OilBuildInput {public OilSelection oiling;}

    static OilSelection ReadRrOilSelection() {
        string path=Path.Combine(Application.dataPath,"Rr2dv/BuildInput.json");
        if(!File.Exists(path))return null;
        var selection=JsonUtility.FromJson<OilBuildInput>(File.ReadAllText(path)).oiling;
        if(selection==null || selection.carId!=CarId)return null;
        if(selection.schema!=1 || selection.points==null || selection.axleZ==null)
            throw new InvalidDataException("Unsupported oil-cup fitting selection");
        return selection;
    }

    static List<RrOilSeat> RrOilApplyLayout(Transform body,float[] axles,OilSelection selection) {
        if(selection.axleZ.Length!=axles.Length || selection.axleZ.Where((z,i)=>Mathf.Abs(z-axles[i])>.001f).Any())
            throw new InvalidDataException("Oil-cup fitting axle positions differ from the built locomotive");
        if(selection.points.Length<Mathf.Max(6,2*axles.Length) || selection.points.Length>12 || selection.points.Length%2!=0)
            throw new InvalidDataException("Oil-cup fitting must have six to twelve cups and a pair per driven axle");
        RrOilBody=body;RrOilAxles=axles;RrOilSeats.Clear();Rr2dvCupSpacing.Clear();Rr2dvMotion=Rr2dvGearMotion(body);
        var animators=Rr2dvGearAnimators(body);
        using(new Rr2dvLodScope(body))using(var hits=new VisualHits(body))try {
            for(int i=0;i<selection.points.Length;i++) {
                var fit=selection.points[i];float side=i%2==0?-1:1;int axle=i<2*axles.Length?i/2:-1;
                if(fit.side!=side || fit.axle!=axle || fit.tag!="oil_"+(i/2+1)+(side<0?"L":"R") || fit.phase<0 || fit.phase>=1 || float.IsNaN(fit.phase))
                    throw new InvalidDataException("Invalid oil-cup pair identity or support pose");
                var host=body.Find(fit.parentPath);
                if(!host || !host.GetComponent<MeshFilter>() || !Rr2dvTravels(host))
                    throw new InvalidDataException("Oil-cup fitted moving mesh is missing or stationary: "+fit.parentPath);
                var seat=new RrOilSeat {host=host,local=GaugeVector(fit.local),axle=axle,side=side,phase=fit.phase,role=fit.role,evidence=fit.evidence};
                Rr2dvSampleGear(animators,fit.phase);
                var surface=seat.Position-Vector3.up*(CupPivotAboveBase-CupSeatSink);
                if(!hits.Ray(surface+Vector3.up*.03f,Vector3.down,.06f,out var contact,host) || contact.normal.y<.8f || Vector3.Distance(contact.point,surface)>.003f)
                    throw new InvalidDataException("Oil-cup measured bearing support no longer agrees: "+fit.tag+" / "+fit.parentPath);
                Rr2dvSampleGear(animators,0);
                if(Mathf.Sign(host.GetComponent<MeshRenderer>().bounds.center.x)!=side || axle>=0 && !RrOilAxleMatch(host,seat.Position,axle))
                    throw new InvalidDataException("Oil-cup fitting no longer follows its intended axle/side: "+fit.tag);
                RrOilSeats.Add(seat);
            }
            foreach(var seat in RrOilSeats)
                if(!Rr2dvCupClear(hits,body,seat.Position,seat.host,out var why))
                    throw new InvalidDataException("Measured oil-cup layout has lost full-turn clearance: "+seat.role+" / "+why);
        }finally{Rr2dvSampleGear(animators,0);}
        return RrOilSeats.ToList();
    }

    sealed class RrOilSeat
    {
        public Transform host;
        public Vector3 local;
        public int axle;
        public float side, phase;
        public string role, evidence;
        public Vector3 Position=>host.TransformPoint(local);
    }
    static readonly List<RrOilSeat> RrOilSeats=new List<RrOilSeat>();
    static float[] RrOilAxles;

    static bool RrOilAxleMatch(Transform host,Vector3 point,int axle)
    {
        var local=host.InverseTransformPoint(point);float z=0;
        var animators=Rr2dvGearAnimators(RrOilBody);
        try {
            for(int i=0;i<16;i++){Rr2dvSampleGear(animators,i/16f);z+=host.TransformPoint(local).z/16;}
        }finally{Rr2dvSampleGear(animators,0);}
        int nearest=Enumerable.Range(0,RrOilAxles.Length).OrderBy(i=>Mathf.Abs(RrOilAxles[i]-z)).First();
        return nearest==axle && Mathf.Abs(z-RrOilAxles[axle])<=.4f;
    }
    static Transform RrOilBody;

    static RrOilSeat RrOilFindSeat(VisualHits hits,Transform body,Rr2dvMainRod rod,Vector3 localSeed,
                                  int axle,string role,float phase)
    {
        var animators=Rr2dvGearAnimators(body);
        RrOilSeat seat=null;
        try {
            Rr2dvSampleGear(animators,phase);
            var seed=rod.rod.TransformPoint(localSeed);
            if(axle>=0) {
                float mean=0;
                for(int i=0;i<16;i++){Rr2dvSampleGear(animators,i/16f);mean+=rod.rod.TransformPoint(localSeed).z/16;}
                Rr2dvSampleGear(animators,phase);seed=rod.rod.TransformPoint(localSeed)+Vector3.forward*(RrOilAxles[axle]-mean);
            }
            string summary;
            var nubs=Rr2dvOilNubs.Find(
                (Vector3 o,Vector3 d,float distance,out RaycastHit h)=>hits.Ray(o,d,distance,out h),
                seed,.3f,CupPivotAboveBase-CupSeatSink,
                t=>Rr2dvTravels(t) && Mathf.Sign(t.GetComponent<MeshRenderer>().bounds.center.x)==rod.side,
                (p,t,r)=>{
                    Rr2dvSampleGear(animators,phase);
                    bool clear=Rr2dvCupClear(hits,body,p,t,out var why,r);
                    Rr2dvSampleGear(animators,phase);return clear?null:why;
                },
                p=>true,out summary); // spacing is checked through the full turn, in the same pose
            // Clearance sampling resets the gear to rest. Candidate.local belongs to its search pose.
            Rr2dvSampleGear(animators,0);
            foreach(var candidate in nubs) {
                var rest=candidate.host.TransformPoint(candidate.local);
                if(axle>=0 && !RrOilAxleMatch(candidate.host,rest,axle))continue;
                seat=new RrOilSeat {host=candidate.host,local=candidate.local,axle=axle,side=rod.side,phase=phase,role=role,evidence="modelled travelling nub; "+summary};
                return seat;
            }
            Rr2dvSampleGear(animators,phase);
            var surfaces=Rr2dvMotion.Where(k=>k.Value && k.Key.GetComponent<MeshFilter>() &&
                k.Key.GetComponent<MeshRenderer>().enabled && k.Key.gameObject.activeInHierarchy &&
                Mathf.Sign(k.Key.GetComponent<MeshRenderer>().bounds.center.x)==rod.side).Select(k=>k.Key).ToArray();
            var candidates=new List<RrOilSeat>();
            foreach(var host in surfaces) {
                var bounds=host.GetComponent<MeshRenderer>().bounds;
                if(seed.z<bounds.min.z-.3f || seed.z>bounds.max.z+.3f || Mathf.Abs(bounds.center.x-seed.x)>.4f)continue;
                for(float dx=-.32f;dx<=.321f;dx+=.01f)for(float dz=-.30f;dz<=.301f;dz+=.01f) {
                    if(dx*dx+dz*dz>.4f*.4f)continue;
                    var origin=seed+new Vector3(dx,.4f,dz);
                    if(!hits.Ray(origin,Vector3.down,.85f,out var hit,host) || hit.normal.y<.9f)continue;
                    bool footprint=true;
                    foreach(var offset in new[]{Vector3.right*.015f,Vector3.left*.015f,Vector3.forward*.02f,Vector3.back*.02f})
                        if(!hits.Ray(origin+offset,Vector3.down,.85f,out var edge,host) || edge.normal.y<.9f || Mathf.Abs(edge.point.y-hit.point.y)>.006f)footprint=false;
                    if(!footprint)continue;
                    var pivot=hit.point+Vector3.up*(CupPivotAboveBase-CupSeatSink);
                    if(candidates.Any(c=>c.host==host && Vector3.Distance(c.Position,pivot)<.009f))continue;
                    candidates.Add(new RrOilSeat {host=host,local=host.InverseTransformPoint(pivot),axle=axle,side=rod.side,phase=phase,role=role,evidence="measured 4 x 3 cm level bearing seat on travelling gear"});
                }
            }
            // Evaluate each retained local seat at rest, then check the entire revolution.
            Rr2dvSampleGear(animators,0);
            int rejected=0;string lastClash=null;
            foreach(var c in candidates.OrderByDescending(c=>c.Position.y).ThenBy(c=>Vector3.Distance(c.Position,seed))) {
                if(!Rr2dvCupSpaced(c.Position) || axle>=0 && !RrOilAxleMatch(c.host,c.Position,axle))continue;
                if(!Rr2dvCupClear(hits,body,c.Position,c.host,out lastClash)){
                    if(Environment.GetEnvironmentVariable("FLEET_OIL_TRACE")=="1" && rejected<3)
                        Line("rr2dv oil rejected flat "+role+" "+c.host.name+" local "+V(c.local)+" world "+V(c.Position)+": "+lastClash);
                    rejected++;continue;
                }
                return c;
            }
            Line("rr2dv oil search "+role+" side "+rod.side+" phase "+phase+": "+summary+"; "+candidates.Count+" flat candidates, "+rejected+" clearance rejects, last "+lastClash);
            return null;
        }finally{Rr2dvSampleGear(animators,0);}
    }

    static void RrOilAddPair(RrOilSeat left,RrOilSeat right)
    {
        RrOilSeats.Add(left);RrOilSeats.Add(right);
        Rr2dvCupSpacing.Add(left.Position);Rr2dvCupSpacing.Add(right.Position);
    }

    static List<RrOilSeat> RrOilMeasureLayout(Transform body,float[] axles)
    {
        RrOilBody=body;RrOilAxles=axles;RrOilSeats.Clear();Rr2dvCupSpacing.Clear();
        if(axles.Length>6)throw new InvalidOperationException("More than six driven axles cannot meet two cups per axle within the twelve-cup maximum");
        Rr2dvMotion=Rr2dvGearMotion(body);
        using(new Rr2dvLodScope(body))using(var hits=new VisualHits(body)) {
            var rods=Rr2dvMainRods(body);
            var pair=Rr2dvPairRods(rods).OrderByDescending(p=>p.l.throwM+p.r.throwM).FirstOrDefault();
            if(pair.l==null || pair.r==null)throw new InvalidOperationException("No paired main rods for axle oiling layout");
            for(int axle=0;axle<axles.Length;axle++) {
                RrOilSeat left=null,right=null;
                foreach(float phase in new[]{pair.l.levelPhase,0f,.25f,.5f,.75f}.Distinct()) {
                    left=RrOilFindSeat(hits,body,pair.l,pair.l.crankEnd,axle,"driven axle "+(axle+1),phase);
                    if(left!=null)break;
                }
                foreach(float phase in new[]{pair.r.levelPhase,0f,.25f,.5f,.75f}.Distinct()) {
                    right=RrOilFindSeat(hits,body,pair.r,pair.r.crankEnd,axle,"driven axle "+(axle+1),phase);
                    if(right!=null)break;
                }
                if(left==null || right==null)throw new InvalidOperationException("No supported, clear travelling oil-cup pair at driven axle "+(axle+1)+"; left "+(left!=null)+", right "+(right!=null));
                RrOilAddPair(left,right);
            }
            foreach(bool crank in new[]{false,true}) {
                if(RrOilSeats.Count>=12)break;
                var left=RrOilFindSeat(hits,body,pair.l,crank?pair.l.crankEnd:pair.l.crossEnd,-1,crank?"main-rod big end":"crosshead/small end",pair.l.levelPhase);
                var right=RrOilFindSeat(hits,body,pair.r,crank?pair.r.crankEnd:pair.r.crossEnd,-1,crank?"main-rod big end":"crosshead/small end",pair.r.levelPhase);
                if(left!=null && right!=null)RrOilAddPair(left,right);
            }
        }
        if(RrOilSeats.Count<Mathf.Max(6,axles.Length*2))throw new InvalidOperationException("Supported running-gear seats do not meet the six-cup minimum");
        using(new Rr2dvLodScope(body))using(var hits=new VisualHits(body))
            foreach(var s in RrOilSeats)
                if(!Rr2dvCupClear(hits,body,s.Position,s.host,out var why))
                    throw new InvalidOperationException("Final oil-cup layout lost clearance: "+s.role+" / "+why);
        return RrOilSeats.ToList();
    }

    static void SeatRr2dvAxleOilCups()
    {
        var hints=Cfg.OilPoints(RefBody).ToArray();
        int drivers=Cfg.EngineUnits.Sum(u=>u.DriverParts.Length);
        if(hints.Length!=drivers*2)throw new InvalidOperationException("Oil-cup hints must contain a left/right pair for every driven axle");
        var axles=Enumerable.Range(0,drivers).Select(i=>(hints[i*2].Item2.z+hints[i*2+1].Item2.z)/2).ToArray();
        string path=$"{carFolder}/{CarId}_template.prefab";
        var root=PrefabUtility.LoadPrefabContents(path);
        try {
            var body=root.transform.Find("Model/"+Cfg.BodyName);
            if(!body)throw new InvalidOperationException("Missing built body for oil-cup placement");
            foreach(var provider in body.GetComponentsInChildren<CCL.Types.Proxies.Util.PositionSyncProviderProxy>(true)
                .Where(p=>p.syncTag!=null && p.syncTag.StartsWith("oil_",StringComparison.Ordinal)).ToArray())
                UnityEngine.Object.DestroyImmediate(provider.gameObject);
            var old=body.Find("[oiling points]");if(old)UnityEngine.Object.DestroyImmediate(old.gameObject);
            var selection=ReadRrOilSelection();
            var seats=selection!=null?RrOilApplyLayout(body,axles,selection):RrOilMeasureLayout(body,axles);
            var points=new List<(string tag,Vector3 pos)>();
            for(int i=0;i<seats.Count;i++) {
                var seat=seats[i];string tag="oil_"+(i/2+1)+(seat.side<0?"L":"R");
                var provider=new GameObject(tag).transform;provider.SetParent(seat.host,false);provider.localPosition=seat.local;
                provider.gameObject.AddComponent<CCL.Types.Proxies.Util.PositionSyncProviderProxy>().syncTag=tag;
                points.Add((tag,root.transform.InverseTransformPoint(provider.position)));
                Line("rr2dv oil "+tag+": "+seat.role+"; "+seat.evidence+"; provider parent "+AnimationUtility.CalculateTransformPath(seat.host,body)+"; local "+V(seat.local));
            }
            Cfg.OilPoints=_=>points;
            var definition=root.transform.Find("[sim]/oilingPoints")?.GetComponent<CCL.Types.Proxies.Simulation.Steam.ManualOilingPointsDefinitionProxy>();
            if(!definition)throw new InvalidOperationException("Missing simulation oiling-point definition");
            definition.OilingPointCount=points.Count;definition.OnValidate();
            Line("rr2dv oil layout: "+points.Count+" cups, a supported travelling pair at each of "+drivers+" driven axles; 64-phase clearance/spacing; additional bearings where clear");
            SaveRr2dvPrefab(root,path);
        }finally{PrefabUtility.UnloadPrefabContents(root);}
    }
}
