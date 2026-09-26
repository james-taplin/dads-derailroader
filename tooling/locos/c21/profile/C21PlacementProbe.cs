using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object=UnityEngine.Object;

// Narrow source geometry probe; does not modify source assets or save the inspection scene.
public static class C21PlacementProbe
{
    static StringBuilder report=new StringBuilder();
    static string output;
    public static void Run()
    {
        output=Environment.GetEnvironmentVariable("CCL_BUILD_OUT");
        int code=0;
        try {
            foreach(var e in new[]{new Vector3(0,90,0),new Vector3(0,90,180),new Vector3(0,-90,180),new Vector3(180,90,0),new Vector3(180,-90,0)})
                report.AppendLine("ROT "+V(e)+" forward "+V(Quaternion.Euler(e)*Vector3.forward)+" up "+V(Quaternion.Euler(e)*Vector3.up));
            Directory.CreateDirectory(output);
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            foreach(var entry in new[] {(C21Source.Loco,"loco"),(C21Source.Tender,"tender")}) {
                var go=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(entry.Item1));
                var cache=new Dictionary<Material,Material>();
                foreach(var r in go.GetComponentsInChildren<Renderer>(true)) r.sharedMaterials=r.sharedMaterials.Select(m=>{
                    if(!m)return null;
                    if(!cache.ContainsKey(m))cache[m]=new Material(Shader.Find("Standard")){color=new Color(0.55f,0.58f,0.6f)};
                    return cache[m];}).ToArray();
                float minZ=entry.Item2=="loco"?-5.5f:2.4f, maxZ=entry.Item2=="loco"?-3.7f:3.7f;
                report.AppendLine("VEHICLE "+entry.Item2);
                foreach(var mf in go.GetComponentsInChildren<MeshFilter>(true)) {
                    if(!mf.sharedMesh)continue;
                    Islands(mf,minZ,maxZ);
                }
                // Dedicated views remove the boiler/tank with camera clipping so pins and sockets remain visible.
                SetupLight();
                Shot(new Vector3(0,8,(minZ+maxZ)/2),new Vector3(0,0,(minZ+maxZ)/2+0.0001f),1.2f,7.02f,7.6f,entry.Item2+"_drawbar_top.png");
                Shot(new Vector3(-8,0.78f,(minZ+maxZ)/2),new Vector3(0,0.78f,(minZ+maxZ)/2),1.15f,0.1f,20,entry.Item2+"_drawbar_side.png");
                if(entry.Item2=="tender") {
                    Shot(new Vector3(-6,2.1f,6),new Vector3(-1,2.1f,2.6f),0.8f,0.1f,20,"tender_handbrake_surface.png");
                }
                Surface(go,entry.Item2);
                Object.DestroyImmediate(go);
            }
        }catch(Exception e){code=1;report.AppendLine(e.ToString());Debug.LogException(e);}
        File.WriteAllText(Path.Combine(output,"placement_probe.txt"),report.ToString());
        EditorApplication.Exit(code);
    }
    static void Islands(MeshFilter mf,float minZ,float maxZ)
    {
        var mesh=mf.sharedMesh;var vv=mesh.vertices;var tri=mesh.triangles;
        var dict=new Dictionary<Vector3Int,int>();var ids=new int[vv.Length];
        for(int i=0;i<vv.Length;i++) {var key=Vector3Int.RoundToInt(vv[i]*10000f);if(!dict.TryGetValue(key,out ids[i])){ids[i]=dict.Count;dict[key]=ids[i];}}
        var p=Enumerable.Range(0,dict.Count).ToArray();
        int Find(int a){while(p[a]!=a)a=p[a]=p[p[a]];return a;}
        for(int i=0;i<tri.Length;i+=3){int a=Find(ids[tri[i]]);p[Find(ids[tri[i+1]])]=a;p[Find(ids[tri[i+2]])]=Find(a);}
        var bounds=new Dictionary<int,Bounds>();var counts=new Dictionary<int,int>();
        foreach(int i in tri) {int key=Find(ids[i]);var pt=mf.transform.TransformPoint(vv[i]);if(bounds.TryGetValue(key,out var b)){b.Encapsulate(pt);bounds[key]=b;counts[key]++;}else{bounds[key]=new Bounds(pt,Vector3.zero);counts[key]=1;}}
        foreach(var kv in bounds.OrderBy(x=>x.Value.center.z)) {
            var b=kv.Value;
            if(b.max.z<minZ || b.min.z>maxZ || b.min.y>1.1f || b.max.y<0.35f || b.size.z>2 || b.size.x>0.8f || Mathf.Abs(b.center.x)>0.45f)continue;
            report.AppendLine($"ISLAND {AnimationUtility.CalculateTransformPath(mf.transform,mf.transform.root)} c={V(b.center)} min={V(b.min)} max={V(b.max)} size={V(b.size)} triangles={counts[kv.Key]/3}");
        }
    }
    static void Surface(GameObject go,string vehicle)
    {
        foreach(var c in go.GetComponentsInChildren<Collider>(true))c.enabled=false;
        foreach(var mf in go.GetComponentsInChildren<MeshFilter>(true)) {
            if(!mf.sharedMesh)continue;var child=new GameObject("measure collider");child.transform.SetParent(mf.transform,false);child.AddComponent<MeshCollider>().sharedMesh=mf.sharedMesh;
        }
        Physics.SyncTransforms();
        if(vehicle=="tender") {
            report.AppendLine("TENDER FRONT SURFACE (ray from +z), y=2.2");
            for(float x=-1.45f;x<=-0.4f;x+=0.05f){var hs=Physics.RaycastAll(new Vector3(x,2.2f,5),Vector3.back,4).OrderBy(h=>h.distance).ToArray();if(hs.Length>0)report.AppendLine($"SURFACE x={x:F3} z={hs[0].point.z:F4} normal={V(hs[0].normal)}");}
        }
        foreach(float site in vehicle=="tender"?new[]{-2.5f,-1.5f,-0.3f,0.5f,1.5f,2.3f}:new[]{-3.9f,-3.5f,-3.0f,-2.5f,-2.0f}) {
            report.AppendLine(vehicle+" BRAKE RELEASE SIDE, z="+site);
            foreach(float y in new[]{0.65f,0.85f,1.08f}) {
                var side=Physics.RaycastAll(new Vector3(3,y,site),Vector3.left,3).OrderBy(h=>h.distance).Take(2).ToArray();
                report.AppendLine("side y="+y+" "+string.Join(" ",side.Select(h=>V(h.point)+"/n"+V(h.normal))));
            }
            foreach(float x in new[]{1.2f,1.3f,1.4f}) {
                var above=Physics.RaycastAll(new Vector3(x,0.2f,site),Vector3.up,1.5f).OrderBy(h=>h.distance).Take(2).ToArray();
                report.AppendLine("board x="+x+" "+string.Join(" ",above.Select(h=>V(h.point)+"/n"+V(h.normal))));
            }
            if(vehicle=="loco" && Mathf.Abs(site+3.5f)<.01f) {
                foreach(float x in new[]{-0.85f,-1.0f,-1.2f,-1.4f}) {
                    var above=Physics.RaycastAll(new Vector3(x,0.2f,site),Vector3.up,1.8f).OrderBy(h=>h.distance).Take(4).ToArray();
                    report.AppendLine("LEFT board x="+x+" "+string.Join(" ",above.Select(h=>V(h.point)+"/n"+V(h.normal))));
                }
            }
        }
    }
    static void SetupLight()
    {
        RenderSettings.ambientMode=UnityEngine.Rendering.AmbientMode.Flat;RenderSettings.ambientLight=Color.gray;
        var light=new GameObject("probe light").AddComponent<Light>();light.type=LightType.Directional;light.intensity=1.2f;light.transform.rotation=Quaternion.Euler(40,-40,0);
    }
    static void Shot(Vector3 pos,Vector3 look,float size,float near,float far,string file)
    {
        var cam=new GameObject("probe camera").AddComponent<Camera>();cam.orthographic=true;cam.orthographicSize=size;cam.nearClipPlane=near;cam.farClipPlane=far;
        cam.clearFlags=CameraClearFlags.SolidColor;cam.backgroundColor=new Color(0.08f,0.10f,0.13f);cam.transform.position=pos;cam.transform.LookAt(look);
        var rt=new RenderTexture(1400,1000,24);cam.targetTexture=rt;cam.Render();RenderTexture.active=rt;
        var tex=new Texture2D(1400,1000,TextureFormat.RGB24,false);tex.ReadPixels(new Rect(0,0,1400,1000),0,0);tex.Apply();
        File.WriteAllBytes(Path.Combine(output,file),tex.EncodeToPNG());RenderTexture.active=null;cam.targetTexture=null;Object.DestroyImmediate(rt);Object.DestroyImmediate(tex);Object.DestroyImmediate(cam.gameObject);
    }
    static string V(Vector3 v)=>$"({v.x:F5},{v.y:F5},{v.z:F5})";
}
