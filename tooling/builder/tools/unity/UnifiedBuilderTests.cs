using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

// Negative geometry cases and numerical checks, run in an isolated disposable editor scene.
public static class UnifiedBuilderTests
{
    public static void Run()
    {
        var output=Environment.GetEnvironmentVariable("CCL_BUILD_OUT");var lines=new List<string>();int failures=0;
        Action<bool,string> check=(ok,label)=> { lines.Add((ok?"PASS ":"FAIL ")+label);if(!ok)failures++; };
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
        var root=new GameObject("test body");
        try
        {
            check(Mathf.Abs(CclLocoBuild.PointTriangleDistance(new Vector3(.5f,.0145f,.5f),Vector3.zero,new Vector3(2,0,0),new Vector3(0,0,2))-.0145f)<1e-5f,"seat inside triangle measures surface, not distant vertices");
            check(Mathf.Abs(CclLocoBuild.PointTriangleDistance(new Vector3(2,0,0),Vector3.zero,Vector3.right,Vector3.forward)-1)<1e-5f,"outside triangle clamps to edge");
            check(Mathf.Abs(CclLocoBuild.PointTriangleDistance(Vector3.up,Vector3.zero,Vector3.zero,Vector3.zero)-1)<1e-5f,"degenerate triangle distance finite");
            var type=typeof(CclLocoBuild);const BindingFlags flags=BindingFlags.Static|BindingFlags.NonPublic;
            type.GetField("Cfg",flags).SetValue(null,new LocoConfig {CarId="test"});
            var method=type.GetMethod("EndBeam",flags);
            bool rejected=false;
            try { method.Invoke(null,new object[] {root,1,null}); }
            catch(TargetInvocationException e) { rejected=e.InnerException is InvalidOperationException; }
            check(rejected,"empty end-beam geometry rejects instead of returning z=0");
            var beam=GameObject.CreatePrimitive(PrimitiveType.Cube);beam.transform.SetParent(root.transform,false);
            beam.transform.localPosition=new Vector3(0,.95f,3f);beam.transform.localScale=new Vector3(1.5f,.25f,.2f);
            // Broad tank face begins at y=1.1: the legacy high sample could see it; the narrowed band cannot.
            var tank=GameObject.CreatePrimitive(PrimitiveType.Cube);tank.transform.SetParent(root.transform,false);
            tank.transform.localPosition=new Vector3(0,1.6f,3.35f);tank.transform.localScale=new Vector3(2f,1f,.2f);
            var args=new object[] {root,1,null};float z=(float)method.Invoke(null,args);
            check(Mathf.Abs(z-3.1f)<.002f,"tank face excluded; actual lower beam selected");
            check(root.GetComponentsInChildren<Collider>().All(c=>c.enabled),"temporary raycast colliders removed and original colliders restored");
            var front=new GameObject("front animator");front.transform.SetParent(root.transform,false);
            var rear=new GameObject("rear animator");rear.transform.SetParent(root.transform,false);
            var fa=front.AddComponent<Animator>();var ra=rear.AddComponent<Animator>();
            var proxies=CclLocoBuild.BuildPonyAnimations(root.transform,new List<(Animator,float)> {(fa,.42f),(ra,.47f)});
            var serialized=proxies.Select(p=>new SerializedObject(p)).ToArray();
            check(serialized.Length==2 && Mathf.Abs(serialized[0].FindProperty("wheelRadius").floatValue-.42f)<1e-5f &&
                Mathf.Abs(serialized[1].FindProperty("wheelRadius").floatValue-.47f)<1e-5f &&
                serialized[0].FindProperty("_animators").GetArrayElementAtIndex(0).objectReferenceValue==fa &&
                serialized[1].FindProperty("_animators").GetArrayElementAtIndex(0).objectReferenceValue==ra,
                "unequal radii export distinct CCL proxies with their own animator references");
            bool badRadius=false;
            try { CclLocoBuild.BuildPonyAnimations(root.transform,new List<(Animator,float)> {(fa,0f)}); }
            catch(InvalidOperationException) { badRadius=true; }
            check(badRadius,"zero pony radius rejected");
        }
        catch(Exception e) { failures++;lines.Add("EXCEPTION "+e); }
        finally { Object.DestroyImmediate(root); }
        File.WriteAllLines(Path.Combine(output,"editor_tests.txt"),lines);
        File.WriteAllText(Path.Combine(output,"editor_tests.json"),"{\"passed\":"+(lines.Count-failures)+",\"failed\":"+failures+"}");
        EditorApplication.Exit(failures==0?0:1);
    }
}
