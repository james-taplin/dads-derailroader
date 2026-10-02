using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

// Diagnostic only. Instantiates exported prefabs in an empty disposable scene.
public static class GaugeProbe
{
    [Serializable] public class Case { public string id, carId, bundle, meshData, donorMeshData, sha256; }
    [Serializable] public class Input { public Case[] cases; }
    [Serializable] public class Sample { public Vector3 origin, hit, normal; public bool found; public float gap; public string part; }
    [Serializable] public class Needle { public string name, reader, port; public float min, max, minAngle, maxAngle; public bool referenceValid; }
    [Serializable] public class Gauge {
        public string path, orientation, mounting, error; public Vector3 position, faceNormal;
        public float rearAngle, uprightAngle, diameter; public int nearSupport, intersections;
        public int housingSupport; public string housingMounting;
        public Sample[] samples; public Needle[] needles;
    }
    [Serializable] public class Finding { public string id, sha256, error; public Gauge[] gauges; }
    [Serializable] public class Output { public int schema = 1; public bool completed; public string regression; public Finding[] findings; }
    static string PathOf(Transform t) { return t.parent ? PathOf(t.parent) + "/" + t.name : t.name; }
    static bool IsGauge(Transform t) { return t.name.StartsWith("gauge ", StringComparison.Ordinal); }
    static bool GaugeAncestor(Transform t) { while (t) { if (IsGauge(t)) return true; t = t.parent; } return false; }
    public static List<Object> Collect(Object[] roots) {
        var all = new List<Object>(); var seen = new HashSet<Object>(); var q = new Queue<Object>(roots);
        while (q.Count > 0) {
            var o = q.Dequeue(); if (!o || !seen.Add(o)) continue; all.Add(o);
            var go = o as GameObject;
            if (go) foreach (var c in go.GetComponentsInChildren<Component>(true)) {
                if (!c) throw new Exception("Missing script in " + go.name + "; check Creator version"); q.Enqueue(c);
            }
            if (o is GameObject || o is Component || o is ScriptableObject || o is Material) {
                var p = new SerializedObject(o).GetIterator();
                while (p.Next(true)) if (p.propertyType == SerializedPropertyType.ObjectReference && p.objectReferenceValue) q.Enqueue(p.objectReferenceValue);
            }
        }
        return all;
    }
    public static List<Mesh> ReadMeshes(string path) {
        var list = new List<Mesh>();
        using (var r = new BinaryReader(File.OpenRead(path))) {
            int count = r.ReadInt32();
            for (int i = 0; i < count; i++) {
                string name = System.Text.Encoding.UTF8.GetString(r.ReadBytes(r.ReadInt32()));
                var vertices = new Vector3[r.ReadInt32()];
                for (int j = 0; j < vertices.Length; j++) vertices[j] = new Vector3(r.ReadSingle(), r.ReadSingle(), r.ReadSingle());
                var indices = new int[r.ReadInt32()]; for (int j = 0; j < indices.Length; j++) indices[j] = r.ReadInt32();
                var m = new Mesh { name = name, indexFormat = UnityEngine.Rendering.IndexFormat.UInt32 };
                m.vertices = vertices; m.triangles = indices; m.RecalculateBounds(); list.Add(m);
            }
        }
        return list;
    }
    public static void ReplaceMeshes(GameObject root, List<Mesh> meshes) {
        foreach (var f in root.GetComponentsInChildren<MeshFilter>(true)) {
            var old = f.sharedMesh; if (!old) continue;
            // Unity built-in primitives are external bundle references but already
            // CPU-readable. They need no reconstructed buffer or mutation.
            if (old.isReadable) continue;
            var hits = meshes.Where(m => m.name == old.name && m.vertexCount == old.vertexCount &&
                (m.bounds.center-old.bounds.center).sqrMagnitude < .00001f && (m.bounds.size-old.bounds.size).sqrMagnitude < .00001f).ToArray();
            if (hits.Length == 0 || hits.Skip(1).Any(m => !m.vertices.SequenceEqual(hits[0].vertices) || !m.triangles.SequenceEqual(hits[0].triangles)))
                throw new Exception("Missing or ambiguous readable mesh: " + old.name);
            f.sharedMesh = hits[0];
        }
    }
    static void ResolveDonorMeshes(GameObject root, List<Mesh> meshes) {
        foreach (var component in root.GetComponentsInChildren<Component>(true).Where(c => c && c.GetType().Name == "MeshGrabberFilter")) {
            var data = new SerializedObject(component);
            string name = data.FindProperty("ReplacementName").stringValue;
            var matches = meshes.Where(m => m.name == name).ToArray();
            var filter = data.FindProperty("Filter").objectReferenceValue as MeshFilter;
            if (matches.Length != 1 || !filter) throw new Exception("Missing or ambiguous runtime donor mesh: " + name + "; supply --dv-resources");
            filter.sharedMesh = matches[0]; // diagnostic clone only; the input bundle stays unchanged
        }
    }
    static float Num(SerializedObject s, string key) { var p=s.FindProperty(key); return p == null ? float.NaN : p.floatValue; }
    static Needle[] Needles(Transform gauge) {
        var list = new List<Needle>();
        foreach (var c in gauge.GetComponentsInChildren<Component>(true).Where(c => c && c.GetType().Name == "IndicatorGaugeProxy")) {
            var s = new SerializedObject(c); var n = new Needle { name=c.name, min=Num(s,"minValue"), max=Num(s,"maxValue"),
                minAngle=Num(s,"minAngle"), maxAngle=Num(s,"maxAngle") };
            var reference=s.FindProperty("needle"); n.referenceValid=reference != null && reference.objectReferenceValue;
            var readers=c.GetComponents<Component>().Where(x=>x && x.GetType().Name.Contains("Reader")).ToArray();
            n.reader=string.Join(",", readers.Select(x=>x.GetType().Name));
            var ports=new List<string>();
            foreach(var reader in readers) { var p=new SerializedObject(reader).GetIterator();
                while(p.Next(true)) if(p.propertyType==SerializedPropertyType.String && p.propertyPath.ToLowerInvariant().Contains("port")) ports.Add(p.propertyPath+"="+p.stringValue);
            }
            n.port=string.Join(";",ports); list.Add(n);
        }
        return list.ToArray();
    }
    public static Gauge Measure(Transform gauge, HashSet<Collider> support) {
        var result = new Gauge { path=PathOf(gauge), needles=Needles(gauge) };
        try {
            var face=gauge.Find("face"); var filter=face ? face.GetComponent<MeshFilter>() : null;
            if (!filter || !filter.sharedMesh) throw new Exception("Missing face mesh");
            var vertices=filter.sharedMesh.vertices; var tri=filter.sharedMesh.triangles; var sum=Vector3.zero;
            for(int i=0;i<tri.Length;i+=3) sum+=Vector3.Cross(face.TransformPoint(vertices[tri[i+1]])-face.TransformPoint(vertices[tri[i]]), face.TransformPoint(vertices[tri[i+2]])-face.TransformPoint(vertices[tri[i]]));
            if(sum.sqrMagnitude<1e-12f) throw new Exception("No unambiguous face normal");
            var normal=sum.normalized; var centre=face.TransformPoint(filter.sharedMesh.bounds.center);
            // Exported rr2dv prefab coordinates: +Z locomotive front, -Z crew/rear.
            result.position=centre; result.faceNormal=normal; result.rearAngle=Vector3.Angle(normal,Vector3.back);
            result.uprightAngle=Vector3.Angle(face.TransformVector(Vector3.up),Vector3.up);
            result.orientation=result.rearAngle<=15 ? "rear-facing" : result.rearAngle>=165 ? "front-facing" : result.rearAngle>=60 && result.rearAngle<=120 ? "sideways" : "angled-review";
            float radius=vertices.Max(v=>Vector3.Distance(centre,face.TransformPoint(v)));
            result.diameter=2*radius;
            var x=face.TransformVector(Vector3.right).normalized; var y=Vector3.Cross(normal,x).normalized;
            var samples=new List<Sample>();
            for(int i=0;i<9;i++) {
                float angle=(i-1)*Mathf.PI/4;
                var point=centre+(i==0 ? Vector3.zero : .8f*radius*(x*Mathf.Cos(angle)+y*Mathf.Sin(angle)));
                var sample=new Sample { origin=point, gap=-999, part="" };
                var hits=Physics.RaycastAll(point+normal*.05f,-normal,.55f).Where(h=>support.Contains(h.collider)).OrderBy(h=>h.distance).ToArray();
                if(hits.Length>0) {
                    var h=hits[0]; sample.found=true; sample.gap=h.distance-.05f; sample.hit=h.point; sample.normal=h.normal;
                    sample.part=PathOf(h.collider.transform.parent ? h.collider.transform.parent : h.collider.transform);
                    if(sample.gap<-.002f) result.intersections++;
                    if(sample.gap>=-.002f && sample.gap<=.03f) result.nearSupport++;
                }
                samples.Add(sample);
            }
            result.samples=samples.ToArray();
            result.mounting=result.intersections>0 ? "intersects-surface" : result.nearSupport>=7 ? "supported-candidate" : result.nearSupport>0 ? "partial-support-review" : "unsupported-within-30mm";
            var datum = gauge.Find("mount datum");
            if (datum) {
                // A complete housing has depth: retain the face screen and report its rear pad separately.
                var back = gauge.TransformDirection(Vector3.forward); int contacts=0, buried=0;
                for(int i=0;i<9;i++) {
                    float angle=(i-1)*Mathf.PI/4;
                    var point=datum.position+(i==0 ? Vector3.zero : gauge.TransformVector(new Vector3(Mathf.Cos(angle),Mathf.Sin(angle),0)*.06f));
                    var hits=Physics.RaycastAll(point-back*.05f,back,.10f).Where(h=>support.Contains(h.collider)).OrderBy(h=>h.distance).ToArray();
                    if(hits.Length==0) continue;
                    float gap=hits[0].distance-.05f;
                    if(gap<-.001f) buried++;
                    if(gap>=-.001f && gap<=.004f) contacts++;
                }
                result.housingSupport=contacts;
                result.housingMounting=buried>0 ? "intersects-surface" : contacts>=7 ? "supported-pad-candidate" : "pad-support-review";
            }
            var studs=gauge.Cast<Transform>().Where(t=>t.name=="mounting stud").ToArray();
            if(studs.Length>0) {
                var endpoints=studs.Select(s=>s.TransformPoint(Vector3.up)).ToArray(); int contacts=0;
                foreach(var point in endpoints) {
                    var hits=Physics.RaycastAll(point+normal*.02f,-normal,.04f).Where(h=>support.Contains(h.collider)).OrderBy(h=>h.distance).ToArray();
                    if(hits.Length>0 && Vector3.Distance(hits[0].point,point)<=.001f) contacts++;
                }
                bool triangle=false;
                for(int i=0;i<endpoints.Length;i++) for(int j=i+1;j<endpoints.Length;j++) for(int k=j+1;k<endpoints.Length;k++)
                    if(Vector3.Cross(endpoints[j]-endpoints[i],endpoints[k]-endpoints[i]).magnitude>.00025f) triangle=true;
                result.housingSupport=contacts;
                result.housingMounting=contacts==studs.Length && contacts>=3 && triangle ? "supported-adapter-candidate" : "adapter-support-review";
            }
        } catch(Exception e) { result.error=e.Message; result.orientation="unmeasured"; result.mounting="unmeasured"; }
        return result;
    }
    static Finding Inspect(Case c) {
        var finding=new Finding { id=c.id, sha256=c.sha256 }; AssetBundle bundle=null;
        var clones=new List<GameObject>(); var meshes=new List<Mesh>();
        try {
            bundle=AssetBundle.LoadFromFile(c.bundle); if(!bundle) throw new Exception("Bundle failed to load");
            var all=Collect(bundle.LoadAllAssets());
            foreach(string suffix in new[]{"_template","_interior"}) {
                var prefab=all.OfType<GameObject>().Single(g=>g.name==c.carId+suffix);
                var clone=Object.Instantiate(prefab); clones.Add(clone);
                if(clone.transform.position.sqrMagnitude>.000001f || Quaternion.Angle(clone.transform.rotation,Quaternion.identity)>.01f)
                    throw new Exception("Unexpected prefab root transform; cannot assume car coordinate frame");
                foreach(var a in clone.GetComponentsInChildren<Animator>(true)) a.enabled=false;
                foreach(var co in clone.GetComponentsInChildren<Collider>(true)) co.enabled=false;
                foreach(var lod in clone.GetComponentsInChildren<LODGroup>(true)) {
                    var levels=lod.GetLODs();
                    for(int i=levels.Length-1;i>=0;i--) foreach(var renderer in levels[i].renderers) if(renderer) renderer.enabled=i==0;
                }
            }
            meshes=ReadMeshes(c.meshData); foreach(var clone in clones) ReplaceMeshes(clone,meshes);
            if(!string.IsNullOrEmpty(c.donorMeshData)) meshes.AddRange(ReadMeshes(c.donorMeshData));
            foreach(var clone in clones) ResolveDonorMeshes(clone,meshes);
            var support=new HashSet<Collider>();
            foreach(var clone in clones) foreach(var f in clone.GetComponentsInChildren<MeshFilter>(false)) {
                var renderer=f.GetComponent<MeshRenderer>();
                if(!renderer || !renderer.enabled || !f.sharedMesh || GaugeAncestor(f.transform) || System.Text.RegularExpressions.Regex.IsMatch(PathOf(f.transform),@"(?i)lod[_ ]?[1-9]|collision|collider")) continue;
                var go=new GameObject("[gauge-probe-surface]"); go.transform.SetParent(f.transform,false);
                var collider=go.AddComponent<MeshCollider>(); collider.sharedMesh=f.sharedMesh; support.Add(collider);
            }
            Physics.SyncTransforms();
            var gauges=clones[1].GetComponentsInChildren<Transform>(true).Where(IsGauge).ToArray();
            if(gauges.Length==0) throw new Exception("No gauges found in exported interior");
            finding.gauges=gauges.Select(g=>Measure(g,support)).ToArray();
        } catch(Exception e) { finding.error=e.ToString(); }
        finally { foreach(var root in clones) Object.DestroyImmediate(root); foreach(var m in meshes) Object.DestroyImmediate(m); if(bundle) bundle.Unload(true); }
        return finding;
    }
    static void Assert(bool pass,string message) { if(!pass) throw new Exception("Regression: "+message); }
    public static void Regression() {
        var gauge=new GameObject("gauge fixture"); var face=new GameObject("face"); face.transform.SetParent(gauge.transform,false);
        var mesh=new Mesh(); mesh.vertices=new[]{new Vector3(-.1f,-.1f,0),new Vector3(.1f,-.1f,0),new Vector3(.1f,.1f,0),new Vector3(-.1f,.1f,0)};
        mesh.triangles=new[]{0,1,2,0,2,3}; mesh.RecalculateBounds(); face.AddComponent<MeshFilter>().sharedMesh=mesh;
        var panel=GameObject.CreatePrimitive(PrimitiveType.Cube); panel.transform.position=new Vector3(0,0,.03f); panel.transform.localScale=new Vector3(1,1,.02f);
        var support=new HashSet<Collider>{panel.GetComponent<Collider>()};
        try {
            gauge.transform.rotation=Quaternion.Euler(0,180,0); Physics.SyncTransforms(); var r=Measure(gauge.transform,support);
            Assert(r.orientation=="rear-facing" && r.nearSupport==9,"rear face / nine-point support: "+JsonUtility.ToJson(r));
            gauge.transform.rotation=Quaternion.Euler(0,90,0); Assert(Measure(gauge.transform,support).orientation=="sideways","90 degree face");
            gauge.transform.rotation=Quaternion.identity; Assert(Measure(gauge.transform,support).orientation=="front-facing","backwards face");
            gauge.transform.rotation=Quaternion.Euler(0,180,0); panel.transform.position=new Vector3(0,0,.25f); Physics.SyncTransforms();
            Assert(Measure(gauge.transform,support).mounting=="unsupported-within-30mm","floating face");
            panel.transform.position=new Vector3(0,0,0); Physics.SyncTransforms(); Assert(Measure(gauge.transform,support).intersections==9,"buried face");
            panel.transform.position=new Vector3(0,0,.03f); panel.transform.localScale=new Vector3(.04f,.04f,.02f); Physics.SyncTransforms();
            Assert(Measure(gauge.transform,support).mounting=="partial-support-review","centre-only support is not full panel");
            face.transform.localScale=new Vector3(-1,1,1); Assert(Measure(gauge.transform,support).orientation=="front-facing","mirrored winding");
        } finally { Object.DestroyImmediate(gauge); Object.DestroyImmediate(panel); Object.DestroyImmediate(mesh); }
    }
    public static void Run() {
        var output=new Output(); bool old=Physics.queriesHitBackfaces; int exit=1;
        try {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single); Physics.queriesHitBackfaces=true;
            Regression(); output.regression="passed: rear/side/front, rim support, floating, intersection, partial support, mirrored face";
            var input=JsonUtility.FromJson<Input>(File.ReadAllText(Environment.GetEnvironmentVariable("GAUGE_INPUT")));
            output.findings=input.cases.Select(Inspect).ToArray();
            output.completed=output.findings.Length>0 && output.findings.All(f=>string.IsNullOrEmpty(f.error) && f.gauges.All(g=>string.IsNullOrEmpty(g.error)));
            exit=output.completed ? 0 : 1;
        } catch(Exception e) { output.regression=e.ToString(); Debug.LogException(e); }
        finally { Physics.queriesHitBackfaces=old; File.WriteAllText(Path.Combine(Environment.GetEnvironmentVariable("GAUGE_OUTPUT"),"result.json"),JsonUtility.ToJson(output,true)); }
        EditorApplication.Exit(exit);
    }
}
