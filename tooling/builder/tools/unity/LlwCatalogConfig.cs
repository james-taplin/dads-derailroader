using System;
using System.IO;
using System.Linq;
using UnityEngine;

// Source-derived wheel metadata + independently measured LocoConfig. Never constructs guessed grips/colliders.
public static class LlwCatalogConfig
{
    [Serializable] public class Pony { public string key; public float radius_m; }
    [Serializable] public class Record { public int schema; public string id, profile; public Pony[] ponies; }
    public static LocoConfig Apply(LocoConfig measured, string id)
    {
        string path = Environment.GetEnvironmentVariable("CCL_CATALOG_RECORD");
        if (string.IsNullOrEmpty(path)) throw new InvalidOperationException("Use unified run_build.ps1: CCL_CATALOG_RECORD is required");
        var record = JsonUtility.FromJson<Record>(File.ReadAllText(path));
        if (record == null || record.schema != 1 || record.id != id || string.IsNullOrEmpty(record.profile))
            throw new InvalidOperationException("Wrong or incomplete catalogue record: " + id);
        foreach (var pony in record.ponies ?? new Pony[0])
        {
            if (!measured.PonyTrucks.Any(p => p.animKey == pony.key))
                throw new InvalidOperationException(id + " missing measured pony animation: " + pony.key);
            if (pony.radius_m <= 0 || float.IsNaN(pony.radius_m) || float.IsInfinity(pony.radius_m))
                throw new InvalidOperationException(id + " invalid source radius");
            // A reviewed measured override wins; otherwise use the source's diameter/2 (never diameter).
            if (!measured.PonyRadii.ContainsKey(pony.key)) measured.PonyRadii.Add(pony.key, pony.radius_m);
        }
        Debug.Log("[LlwCatalogConfig] " + id + " source record + measured profile " + record.profile);
        return measured;
    }
}
