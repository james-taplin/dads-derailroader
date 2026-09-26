using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine;

// Call on the saved template, before Export, for new-locomotive builds only.
// This reads CCL's actual exposed-port schema instead of guessing port names.
public static class NewLocoBuildGate
{
    [Serializable] public class Entry { public string id, componentClass; public string[] ports, references; }
    [Serializable] public class Document { public int schema = 1; public string carId, prefab; public Entry[] components; }
    static object Read(object value, string member)
    {
        var flags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
        var field = value.GetType().GetField(member, flags);
        if (field != null) return field.GetValue(value);
        var property = value.GetType().GetProperty(member, flags);
        if (property != null) return property.GetValue(value, null);
        throw new InvalidOperationException(value.GetType().Name + " has no " + member);
    }
    static string[] Names(object value, string member)
    {
        var sequence = Read(value, member) as IEnumerable;
        if (sequence == null) throw new InvalidOperationException(member + " is not enumerable");
        return sequence.Cast<object>().Select(p => (string)Read(p, "ID")).ToArray();
    }
    public static void ValidateAndWrite(LocoConfig cfg, string output)
    {
        if (cfg.Tender != null) throw new InvalidOperationException("New-locomotive gate currently supports one tank locomotive only");
        string carId = cfg.CarId;
        var matches = AssetDatabase.FindAssets("t:Prefab", new[] { "Assets/_CCL_CARS" })
            .Select(AssetDatabase.GUIDToAssetPath).Where(p => Path.GetFileName(p) == carId + "_template.prefab").ToArray();
        if (matches.Length != 1) throw new InvalidOperationException("Expected one saved template for " + carId);
        string prefabPath = matches[0];
        var root = PrefabUtility.LoadPrefabContents(prefabPath);
        try
        {
            var sim = root.GetComponentsInChildren<MonoBehaviour>(true).Single(c => c && c.GetType().Name == "SimConnectionsDefinitionProxy");
            var entries = new List<Entry>();
            foreach (var component in ((IEnumerable)Read(sim, "executionOrder")).Cast<object>())
            {
                if (component == null) throw new InvalidOperationException("Null simulation entry");
                entries.Add(new Entry { id = (string)Read(component, "ID"), componentClass = component.GetType().Name,
                    ports = Names(component, "ExposedPorts"), references = Names(component, "ExposedPortReferences") });
            }
            if (entries.Any(e => string.IsNullOrEmpty(e.id)) || entries.Select(e => e.id).Distinct().Count() != entries.Count)
                throw new InvalidOperationException("Missing or duplicate simulation IDs");
            foreach (var e in entries)
                if (e.ports.Distinct().Count() != e.ports.Length || e.references.Distinct().Count() != e.references.Length)
                    throw new InvalidOperationException("Duplicate exposed ports/references on " + e.id);
            var ports = new HashSet<string>(entries.SelectMany(e => e.ports.Select(p => e.id + "." + p)));
            var refs = new HashSet<string>(entries.SelectMany(e => e.references.Select(p => e.id + "." + p)));
            foreach (var link in ((IEnumerable)Read(sim, "connections")).Cast<object>())
                foreach (var field in new[] { "fullPortIdOut", "fullPortIdIn" })
                    if (!ports.Contains((string)Read(link, field))) throw new InvalidOperationException("Missing connected port: " + Read(link, field));
            foreach (var link in ((IEnumerable)Read(sim, "portReferenceConnections")).Cast<object>())
            {
                string reference = (string)Read(link, "portReferenceId"), port = (string)Read(link, "portId");
                if (!refs.Contains(reference)) throw new InvalidOperationException("Missing port reference: " + reference);
                if (!string.IsNullOrEmpty(port) && !ports.Contains(port)) throw new InvalidOperationException("Missing referenced port: " + port);
            }
            File.WriteAllText(Path.Combine(output, "sim_ports.json"), JsonUtility.ToJson(new Document {
                carId = carId, prefab = prefabPath, components = entries.ToArray() }, true));
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }
}
