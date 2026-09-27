using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

public class AuditGraphNode : ScriptableObject { public Object next; public AuditGraphNode cycle; }
public static class AuditGraphRegression
{
    public static void Run()
    {
        try
        {
            var pack = ScriptableObject.CreateInstance<AuditGraphNode>();
            var car = ScriptableObject.CreateInstance<AuditGraphNode>();
            var go = new GameObject("referenced car");
            var source = go.AddComponent<AudioSource>();
            var clip = AudioClip.Create("referenced sound", 8, 1, 8000, false);
            source.clip = clip;
            pack.next = car; car.next = go; car.cycle = pack;
            var errors = new List<string>();
            var method = typeof(Rr2dvAudit).GetMethod("CollectObjects", BindingFlags.NonPublic | BindingFlags.Static);
            var all = (List<Object>)method.Invoke(null, new object[] { new Object[] { pack }, errors });
            foreach (var item in new Object[] { pack, car, go, go.transform, source, clip })
                if (all.Count(o => o == item) != 1) throw new Exception("referenced object missing or duplicated: " + item.GetType().Name);
            if (errors.Count > 0) throw new Exception(string.Join("; ", errors));
            File.WriteAllText("audit-graph-passed.json", "{\"referencedObjects\":true,\"cyclesDeduplicated\":true,\"audioFound\":true}");
            EditorApplication.Exit(0);
        }
        catch (Exception e) { Debug.LogException(e); EditorApplication.Exit(1); }
    }
}
