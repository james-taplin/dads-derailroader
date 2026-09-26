using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object=UnityEngine.Object;
public static class S16Measure {
 static StringBuilder text=new StringBuilder(); static string output;
 static string V(Vector3 v)=>$"({v.x:F5},{v.y:F5},{v.z:F5})";
 static string P(Transform t,Transform root)=>AnimationUtility.CalculateTransformPath(t,root);
 static void L(string s){text.AppendLine(s);}
 public static void Wheels(){
 output=Environment.GetEnvironmentVariable("RLW_PROBE_OUT")??Path.GetFullPath("S16Measure");Directory.CreateDirectory(output);
 var go=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>("Assets/shrimpy/ls-060-s16.prefab"));var t=go.transform.Find("Main/Driver1/Cylinder.002");var mesh=t.GetComponent<MeshFilter>().sharedMesh;var rr=t.GetComponent<Renderer>();var v=mesh.vertices.Select(p=>t.TransformPoint(p)).ToArray();var pivot=t.parent.position;
 for(int sub=0;sub<mesh.subMeshCount;sub++){var ids=mesh.GetTriangles(sub).Distinct();foreach(var g in ids.GroupBy(i=>Mathf.RoundToInt(Mathf.Abs(v[i].x)*1000)).OrderBy(g=>g.Key)){var radii=g.Select(i=>new Vector2(v[i].y-pivot.y,v[i].z-pivot.z).magnitude).Where(r=>r>.45).ToArray();if(radii.Length>0)L($"RING {rr.sharedMaterials[sub].name} x={g.Key/1000f:F3} count={radii.Length} min={radii.Min():F6} max={radii.Max():F6} mean={radii.Average():F6}");}}
 File.WriteAllText(Path.Combine(output,"wheel_details.txt"),text.ToString());EditorApplication.Exit(0);
 }
 public static void Run(){
 output=Environment.GetEnvironmentVariable("RLW_PROBE_OUT")??Path.GetFullPath("S16Measure");Directory.CreateDirectory(output);
 try {
 EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
 var go=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>("Assets/shrimpy/ls-060-s16.prefab"));
 foreach(var c in go.GetComponentsInChildren<Collider>(true)) Object.DestroyImmediate(c);
 foreach(var mf in go.GetComponentsInChildren<MeshFilter>(true)) {
  if(!mf.sharedMesh)continue;var rr=mf.GetComponent<Renderer>();if(!rr)continue;var m=mf.sharedMesh;var vv=m.vertices.Select(v=>mf.transform.TransformPoint(v)).ToArray();var path=P(mf.transform,go.transform);
  var collider=mf.gameObject.AddComponent<MeshCollider>();collider.sharedMesh=m;
  L($"MESH {path} tris={m.triangles.Length/3} bounds={V(rr.bounds.center)} size={V(rr.bounds.size)}");
  for(int sub=0;sub<m.subMeshCount;sub++) {var tt=m.GetTriangles(sub);if(tt.Length==0)continue;var bb=new Bounds(vv[tt[0]],Vector3.zero);foreach(var t in tt)bb.Encapsulate(vv[t]);L($"MAT {path} {rr.sharedMaterials[sub].name} c={V(bb.center)} size={V(bb.size)} min={V(bb.min)} max={V(bb.max)}");}
  if(path.Contains("Driver")){var pivot=mf.transform.parent.position;var hist=vv.Select(v=>Mathf.RoundToInt(new Vector2(v.y-pivot.y,v.z-pivot.z).magnitude*10000)).GroupBy(n=>n).Where(g=>g.Key>4500).OrderByDescending(g=>g.Count()).Take(15);L($"WHEEL {path} pivot={V(pivot)} radii="+string.Join(";",hist.Select(g=>$"{g.Key/10000f:F4}:{g.Count()}")));}
  var ids=new Dictionary<Vector3Int,int>();var vi=new int[vv.Length];for(int i=0;i<vv.Length;i++){var key=Vector3Int.RoundToInt(vv[i]*100000f);if(!ids.TryGetValue(key,out vi[i])){vi[i]=ids.Count;ids[key]=vi[i];}}
  var parents=Enumerable.Range(0,ids.Count).ToArray();int Find(int i){while(parents[i]!=i)i=parents[i]=parents[parents[i]];return i;}
  var triangles=m.triangles;for(int i=0;i<triangles.Length;i+=3){int a=Find(vi[triangles[i]]);parents[Find(vi[triangles[i+1]])]=a;parents[Find(vi[triangles[i+2]])]=Find(a);}
  var groups=new Dictionary<int,List<int>>();for(int i=0;i<triangles.Length;i+=3){int id=Find(vi[triangles[i]]);if(!groups.ContainsKey(id))groups[id]=new List<int>();groups[id].AddRange(new[]{triangles[i],triangles[i+1],triangles[i+2]});}
  foreach(var kv in groups){var bb=new Bounds(vv[kv.Value[0]],Vector3.zero);foreach(int t in kv.Value)bb.Encapsulate(vv[t]);if(kv.Value.Count/3<12)continue;
   if(path=="Cylinder.018"||path.Contains("Rod"))L($"ISLAND {path} id={kv.Key} tris={kv.Value.Count/3} c={V(bb.center)} size={V(bb.size)} min={V(bb.min)} max={V(bb.max)}");}
 }
 Physics.SyncTransforms();
 foreach(float z in new[]{-2.35f,-2.55f,-2.75f,-2.95f})foreach(float x in new[]{-1f,-0.65f,0f,0.65f,1f}){var hits=Physics.RaycastAll(new Vector3(x,1.85f,z),Vector3.down,1.8f);if(hits.Length>0){var h=hits.OrderBy(hh=>hh.distance).First();L($"FLOOR x={x:F2} z={z:F2} y={h.point.y:F5} {P(h.transform,go.transform)}");}}
 for(float y=1.25f;y<=3.15f;y+=0.1f)for(float x=-1.1f;x<=1.101f;x+=0.1f){var hits=Physics.RaycastAll(new Vector3(x,y,-2.55f),Vector3.forward,1.6f);if(hits.Length>0){var h=hits.OrderBy(hh=>hh.distance).First();L($"BACKHEAD x={x:F2} y={y:F2} z={h.point.z:F5} {P(h.transform,go.transform)}");}}
 foreach(var comp in S16Defs.Components.Where(c=>!string.IsNullOrEmpty(c.parentPath))){var p=go.transform.Find(comp.parentPath);if(!p)throw new Exception("missing parent "+comp.parentPath);L($"RESOLVED {comp.name} pos={V(p.TransformPoint(comp.pos))} rotation=({(p.rotation*comp.rot).x:R},{(p.rotation*comp.rot).y:R},{(p.rotation*comp.rot).z:R},{(p.rotation*comp.rot).w:R}) scale={V(Vector3.Scale(p.lossyScale,comp.scale))}");}
 foreach(var an in S16Defs.AnimationMap.Where(k=>new[]{"Throttle","Reverser","Indy","TB","Whistle","Cocks","Bell2","FBD","FBD2","RW","LW","WBR","WBL","RV","HatchLeft","HatchRight"}.Contains(k.Key))){var clip=AssetDatabase.LoadAssetAtPath<AnimationClip>(an.Value);foreach(float f in new[]{0f,0.999f}){clip.SampleAnimation(go,f*clip.length);foreach(var path in AnimationUtility.GetCurveBindings(clip).Select(b=>b.path).Distinct()){var t=go.transform.Find(path);L($"SAMPLE {an.Key} f={f} path={path} pos={V(t.position)} euler={V(t.eulerAngles)}");}}clip.SampleAnimation(go,0);}
 foreach(var r in go.GetComponentsInChildren<Renderer>()){r.sharedMaterials=r.sharedMaterials.Select(m=>{var n=new Material(Shader.Find("Standard"));if(m&&m.HasProperty("_MainTex"))n.mainTexture=m.GetTexture("_MainTex");n.color=m&&m.HasProperty("_Color")?m.color:Color.gray;return n;}).ToArray();}
 var light=new GameObject("light").AddComponent<Light>();light.type=LightType.Directional;light.intensity=1.2f;light.transform.rotation=Quaternion.Euler(35,20,0);RenderSettings.ambientMode=UnityEngine.Rendering.AmbientMode.Flat;RenderSettings.ambientLight=Color.gray;
 var cam=new GameObject("cam").AddComponent<Camera>();cam.clearFlags=CameraClearFlags.SolidColor;cam.backgroundColor=new Color(.11f,.11f,.11f);cam.orthographic=true;cam.orthographicSize=1.25f;cam.transform.position=new Vector3(0,2.2f,-5f);cam.transform.rotation=Quaternion.identity;cam.nearClipPlane=2.47f;cam.farClipPlane=4.1f;var rt=new RenderTexture(1400,1250,24);cam.targetTexture=rt;cam.Render();RenderTexture.active=rt;var tex=new Texture2D(1400,1250,TextureFormat.RGB24,false);tex.ReadPixels(new Rect(0,0,1400,1250),0,0);tex.Apply();File.WriteAllBytes(Path.Combine(output,"backhead.png"),tex.EncodeToPNG());RenderTexture.active=null;
 File.WriteAllText(Path.Combine(output,"measure_report.txt"),text.ToString());EditorApplication.Exit(0);
 }catch(Exception ex){L("ERROR "+ex);File.WriteAllText(Path.Combine(output,"measure_report.txt"),text.ToString());Debug.LogException(ex);EditorApplication.Exit(1);}
 }
}
