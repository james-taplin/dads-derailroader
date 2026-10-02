using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

// Measured candidates only. The fitting search never changes an installed pack.
public static class FleetGaugeFit
{
    [Serializable] public class Slot { public string sourceGauge, reading; public int sourceIndex; public float[] position, rotation; public float scale; }
    [Serializable] public class Case { public string id, pack, carId, bundle, meshData, donorMeshData, sha256; public float backheadZ; public Slot[] slots; }
    [Serializable] public class Input { public Case[] cases; }
    [Serializable] public class Fit {
        public string sourceGauge, reading, supportPath, evidence, error; public int sourceIndex, contacts;
        public float[] position, rotation, supportPoint; public float scale, displacement;
        public Contact[] supports;
    }
    [Serializable] public class Contact { public float[] point, radial; public string supportPath; }
    [Serializable] public class Finding { public string id, pack, sha256, error; public Fit[] instruments; }
    [Serializable] public class Output { public bool completed; public Finding[] findings; }
    static float[] A(Vector3 v) => new[] {v.x,v.y,v.z};
    static float[] A(Quaternion q) => new[] {q.x,q.y,q.z,q.w};
    static Vector3 V(float[] a) => new Vector3(a[0],a[1],a[2]);
    static Quaternion Q(float[] a) => new Quaternion(a[0],a[1],a[2],a[3]);

    static Fit Search(Case c, Slot slot, Transform body, HashSet<Collider> surfaces, List<Fit> placed)
    {
        var original=V(slot.position); var authored=Q(slot.rotation)*Quaternion.Euler(0,180,0);
        Fit best=null; float bestScore=float.MaxValue;
        // Preserve a working source angle; rear-facing relocation is a separate measured candidate.
        foreach(var rotation in new[]{authored,Quaternion.identity}) {
            var normal=rotation*Vector3.back;
            foreach(float dx in new[]{0f,-.12f,.12f,-.24f,.24f,-.36f,.36f,-.48f,.48f,-.60f,.60f})
            foreach(float dy in new[]{0f,-.10f,.10f,-.20f,.20f,-.30f,.30f}) {
                var seed=original+rotation*new Vector3(dx,dy,0);
                // Search from the crew side, covering the original housing and the measured backhead band.
                if(rotation==Quaternion.identity) seed.z=Mathf.Min(seed.z,c.backheadZ)-.60f;
                else seed+=normal*.40f;
                var hits=Physics.RaycastAll(seed,-normal,1.30f).Where(h=>surfaces.Contains(h.collider)).OrderBy(h=>h.distance).ToArray();
                if(hits.Length==0) continue;
                var centreHit=hits[0];
                if(Vector3.Dot(centreHit.normal,normal)<.92f) continue; // curved/oblique surfaces need a bespoke bracket
                float scale=slot.scale;
                var point=centreHit.point;
                var position=point-rotation*new Vector3(0,0,.017117139f)*scale;
                if(Vector3.Distance(position,original)>.85f) continue;
                // Full housing footprint plus stem; do not overlap another new instrument.
                var size=new Vector3(.169f,.184f,.075f)*scale;
                bool crowded=placed.Any(p=> {
                    var delta=Quaternion.Inverse(rotation)*(V(p.position)-position);
                    return Quaternion.Angle(rotation,Q(p.rotation))<45f && Mathf.Abs(delta.z)<.10f &&
                        Mathf.Abs(delta.x)<(.169f*(p.scale+scale)/2+.012f) && Mathf.Abs(delta.y)<(.184f*(p.scale+scale)/2+.012f);
                });
                if(crowded) continue;
                int contacts=0; bool buried=false;
                for(int i=0;i<9;i++) {
                    float angle=(i-1)*Mathf.PI/4;
                    var radial=i==0?Vector3.zero:new Vector3(Mathf.Cos(angle),Mathf.Sin(angle),0)*.06f;
                    var rear=position+rotation*(new Vector3(0,0,.015117139f)+radial)*scale;
                    var sample=Physics.RaycastAll(rear+normal*.05f,-normal,.10f).Where(h=>surfaces.Contains(h.collider)).OrderBy(h=>h.distance).ToArray();
                    if(sample.Length==0 || sample[0].collider!=centreHit.collider) continue;
                    float gap=sample[0].distance-.05f;
                    if(gap<-.001f) buried=true;
                    if(gap>=-.001f && gap<=.004f) contacts++;
                }
                if(buried || contacts<7) continue;
                // Sample the housing envelope, not only the attachment pad. A mesh within the case is rejected.
                bool clipped=false;
                foreach(float x in new[]{-.0845f,0f,.0845f}) foreach(float y in new[]{-.092f,0f,.092f}) {
                    var front=position+rotation*new Vector3(x,y,-.060f)*scale;
                    var envelope=Physics.RaycastAll(front,-normal,.075117139f*scale-.001f).Where(h=>surfaces.Contains(h.collider)).ToArray();
                    if(envelope.Length>0) clipped=true;
                }
                if(clipped) continue;
                float distance=Vector3.Distance(position,original);
                float score=distance+(Quaternion.Angle(rotation,authored)>15f?.18f:0f);
                if(score>=bestScore) continue;
                bestScore=score;
                best=new Fit {sourceGauge=slot.sourceGauge,sourceIndex=slot.sourceIndex,reading=slot.reading,
                    position=A(position),rotation=A(rotation),supportPoint=A(point),scale=scale,contacts=contacts,
                    displacement=distance,supportPath=AnimationUtility.CalculateTransformPath(centreHit.collider.transform.parent,body),
                    evidence="Native fleet fitting 2026-10-02: "+contacts+"/9 pad contacts on one static source mesh; housing envelope sampled; game sight lines and full control sweep pending"};
            }
        }
        var adapter=SearchAdapter(slot,body,surfaces,placed);
        if(adapter!=null && (best==null || adapter.displacement<best.displacement)) best=adapter;
        return best??new Fit {sourceGauge=slot.sourceGauge,sourceIndex=slot.sourceIndex,reading=slot.reading,
            error="No supported, non-overlapping housing candidate within the bounded source/backhead search"};
    }

    static Fit SearchAdapter(Slot slot, Transform body, HashSet<Collider> surfaces, List<Fit> placed)
    {
        Fit best=null;var rotation=Q(slot.rotation)*Quaternion.Euler(0,180,0);var original=V(slot.position);
        foreach(float radius in new[]{.052f,.074f}) {
            var candidate=SearchAdapterAt(slot,body,surfaces,placed,radius);
            if(candidate!=null && (best==null || candidate.displacement<best.displacement)) best=candidate;
        }
        if(best!=null) return best;
        foreach(float x in new[]{-.06f,.06f,-.12f,.12f}) foreach(float y in new[]{0f,-.06f,.06f}) {
            var shifted=new Slot {sourceGauge=slot.sourceGauge,reading=slot.reading,sourceIndex=slot.sourceIndex,
                position=A(original+rotation*new Vector3(x,y,0)),rotation=slot.rotation,scale=slot.scale};
            var candidate=SearchAdapterAt(shifted,body,surfaces,placed,.074f);
            if(candidate==null) continue;
            candidate.displacement=Vector3.Distance(V(candidate.position),original);
            if(best==null || candidate.displacement<best.displacement) best=candidate;
        }
        return best;
    }

    static Fit SearchAdapterAt(Slot slot, Transform body, HashSet<Collider> surfaces, List<Fit> placed, float radius)
    {
        var original=V(slot.position); var rotation=Q(slot.rotation)*Quaternion.Euler(0,180,0); var normal=rotation*Vector3.back;
        float scale=slot.scale;
        var contacts=new List<Contact>(); var depths=new List<float>();
        for(int i=0;i<8;i++) {
            float angle=i*Mathf.PI/4; var radial=new Vector3(Mathf.Cos(angle),Mathf.Sin(angle),0)*radius*scale;
            var origin=original+rotation*radial+normal*.25f;
            var hits=Physics.RaycastAll(origin,-normal,.50f).Where(h=>surfaces.Contains(h.collider)).OrderBy(h=>h.distance).ToArray();
            if(hits.Length==0 || Vector3.Dot(hits[0].normal,normal)<.55f) continue;
            var hit=hits[0];
            contacts.Add(new Contact {point=A(hit.point),radial=A(radial),supportPath=AnimationUtility.CalculateTransformPath(hit.collider.transform.parent,body)});
            depths.Add(Vector3.Dot(hit.point-original,normal));
        }
        if(contacts.Count<3) return null;
        bool triangle=false;
        for(int i=0;i<contacts.Count;i++) for(int j=i+1;j<contacts.Count;j++) for(int k=j+1;k<contacts.Count;k++)
            if(Vector3.Cross(V(contacts[j].radial)-V(contacts[i].radial),V(contacts[k].radial)-V(contacts[i].radial)).magnitude>.001f*scale*scale) triangle=true;
        if(!triangle || depths.Max()-depths.Min()>.10f) return null;
        // The entire rear of the casing is beyond the nearest sampled source surface.
        float foremost=depths.Max();
        foreach(float x in new[]{-.0845f,0f,.0845f}) foreach(float y in new[]{-.092f,0f,.092f}) {
            var origin=original+rotation*new Vector3(x,y,0)*scale+normal*.25f;
            var hits=Physics.RaycastAll(origin,-normal,.50f).Where(h=>surfaces.Contains(h.collider)).OrderBy(h=>h.distance).ToArray();
            if(hits.Length>0) foremost=Mathf.Max(foremost,Vector3.Dot(hits[0].point-original,normal));
        }
        float offset=foremost+.015117139f*scale+.006f;
        var position=original+normal*offset;
        if(Vector3.Distance(position,original)>.20f) return null;
        contacts=contacts.Where(contact=> {
            var rear=position+rotation*(V(contact.radial)+new Vector3(0,0,.015117139f*scale));
            float length=Vector3.Distance(rear,V(contact.point));return length>=.002f && length<=.16f;
        }).ToList();
        if(contacts.Count<3) return null;
        triangle=false;
        for(int i=0;i<contacts.Count;i++) for(int j=i+1;j<contacts.Count;j++) for(int k=j+1;k<contacts.Count;k++)
            if(Vector3.Cross(V(contacts[j].radial)-V(contacts[i].radial),V(contacts[k].radial)-V(contacts[i].radial)).magnitude>.001f*scale*scale) triangle=true;
        if(!triangle) return null;
        if(placed.Any(p=> {var d=Quaternion.Inverse(rotation)*(V(p.position)-position);
            return Quaternion.Angle(rotation,Q(p.rotation))<45f && Mathf.Abs(d.z)<.10f &&
                Mathf.Abs(d.x)<.169f*(p.scale+scale)/2+.012f && Mathf.Abs(d.y)<.184f*(p.scale+scale)/2+.012f;})) return null;
        foreach(float x in new[]{-.0845f,0f,.0845f}) foreach(float y in new[]{-.092f,0f,.092f}) {
            var front=position+rotation*new Vector3(x,y,-.060f)*scale;
            if(Physics.RaycastAll(front,-normal,.075117139f*scale-.001f).Any(h=>surfaces.Contains(h.collider))) return null;
        }
        return new Fit {sourceGauge=slot.sourceGauge,sourceIndex=slot.sourceIndex,reading=slot.reading,
            position=A(position),rotation=A(rotation),scale=scale,supports=contacts.ToArray(),contacts=contacts.Count,
            supportPath=contacts[0].supportPath,supportPoint=contacts[0].point,displacement=Mathf.Abs(offset),
            evidence="Native fleet fitting 2026-10-02: "+contacts.Count+" measured non-collinear adapter contacts on static source meshes; original gauge facing retained; housing envelope sampled; game sight lines and control sweeps pending"};
    }

    static Finding Inspect(Case c) {
        var result=new Finding {id=c.id,pack=c.pack,sha256=c.sha256}; AssetBundle bundle=null;
        GameObject root=null; var meshes=new List<Mesh>();
        try {
            bundle=AssetBundle.LoadFromFile(c.bundle); if(!bundle) throw new Exception("Cannot load bundle");
            var asset=GaugeProbe.Collect(bundle.LoadAllAssets()).OfType<GameObject>().Single(g=>g.name==c.carId+"_template");
            root=Object.Instantiate(asset);
            foreach(var co in root.GetComponentsInChildren<Collider>(true)) co.enabled=false;
            foreach(var a in root.GetComponentsInChildren<Animator>(true)) a.enabled=false;
            meshes=GaugeProbe.ReadMeshes(c.meshData); GaugeProbe.ReplaceMeshes(root,meshes);
            var body=root.transform.Find("Model/"+c.pack+"_body"); if(!body) throw new Exception("Missing source model body");
            var surfaces=new HashSet<Collider>();
            foreach(var f in body.GetComponentsInChildren<MeshFilter>(false)) {
                var path=AnimationUtility.CalculateTransformPath(f.transform,body);
                var renderer=f.GetComponent<MeshRenderer>();
                if(!f.sharedMesh || !renderer || System.Text.RegularExpressions.Regex.IsMatch(path,@"(?i)lod[_ ]?[1-9]|collision|collider|handle|lever|valve|wheel|rod|bell|cord")) continue;
                var go=new GameObject("[fit surface]"); go.transform.SetParent(f.transform,false);
                var co=go.AddComponent<MeshCollider>(); co.sharedMesh=f.sharedMesh; surfaces.Add(co);
            }
            Physics.SyncTransforms();
            var fits=new List<Fit>(); foreach(var slot in c.slots) fits.Add(Search(c,slot,body,surfaces,fits.Where(f=>string.IsNullOrEmpty(f.error)).ToList()));
            result.instruments=fits.ToArray();
        } catch(Exception e) {result.error=e.ToString();}
        finally {if(root) Object.DestroyImmediate(root); foreach(var m in meshes) Object.DestroyImmediate(m); if(bundle) bundle.Unload(true);}
        return result;
    }
    public static void Run() {
        string output=Environment.GetEnvironmentVariable("FLEET_GAUGE_OUTPUT");
        try {
            var input=JsonUtility.FromJson<Input>(File.ReadAllText(Environment.GetEnvironmentVariable("FLEET_GAUGE_INPUT")));
            var result=new Output {findings=input.cases.Select(Inspect).ToArray()};
            result.completed=result.findings.All(f=>string.IsNullOrEmpty(f.error) && f.instruments!=null &&
                f.instruments.All(i=>string.IsNullOrEmpty(i.error)));
            File.WriteAllText(output,JsonUtility.ToJson(result,true)); EditorApplication.Exit(result.completed?0:1);
        } catch(Exception e) {File.WriteAllText(output,e.ToString());EditorApplication.Exit(1);}
    }
}
