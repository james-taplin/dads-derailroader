using System;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static partial class CclLocoBuild
{
    // Tread radius controls rolling speed and rail supports; it is not necessarily the source spindle's height.
    // Keep standard CCL/DV wheel rotation, but centre its visual [axle] on the per-axle RR wheel nodes selected
    // during preparation. Preserve all children's world poses so the frame, bearings and resting wheels do not move.
    static void CentreRr2dvTruckWheelPivots()
    {
        if (Cfg.Trucks.Count == 0) return;
        string path = $"{carFolder}/{CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            CentreRr2dvTruckWheelPivots(root, Cfg.Trucks.Select(t => t.Wheelset).Distinct().ToArray());
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    public static void CentreRr2dvTruckWheelPivots(GameObject root, string[] prefixes)
    {
        if (prefixes == null || prefixes.Length == 0 || prefixes.Any(string.IsNullOrEmpty))
            throw new InvalidOperationException("Truck wheel pivots require explicit wheel-node prefixes");
        int count = 0;
        foreach (var axle in root.GetComponentsInChildren<Transform>(true).Where(t => t.name == "[axle]"))
        {
            var children = axle.Cast<Transform>().ToArray();
            var wheels = children.Where(t => prefixes.Any(p => t.name.StartsWith(p, StringComparison.Ordinal))).ToArray();
            if (wheels.Length == 0) continue; // powered/pony axles and empty donor axles are outside this correction
            var centres = wheels.Select(t => axle.parent.InverseTransformPoint(t.position)).ToArray();
            if (centres.Any(p => float.IsNaN(p.y) || float.IsInfinity(p.y) || float.IsNaN(p.z) || float.IsInfinity(p.z)))
                throw new InvalidOperationException("Truck wheel spindle is not finite");
            float y = centres.Average(p => p.y), z = centres.Average(p => p.z);
            if (centres.Any(p => Mathf.Abs(p.y - y) > .0005f || Mathf.Abs(p.z - z) > .0005f))
                throw new InvalidOperationException("Truck axle contains wheel nodes from different spindle centres");
            var old = axle.localPosition;
            if (Mathf.Abs(z - old.z) > .005f)
                throw new InvalidOperationException("Truck wheel spindle does not match its recorded axle position");
            var positions = children.Select(t => t.position).ToArray();
            axle.localPosition = new Vector3(old.x, y, z);
            for (int i = 0; i < children.Length; i++) children[i].position = positions[i];
            count++;
            Line($"rr2dv truck spin pivot: {axle.parent.parent.name} ({old.y:F6},{old.z:F6}) -> RR spindle ({y:F6},{z:F6}); resting geometry retained, rolling radius unchanged");
        }
        if (count == 0) throw new InvalidOperationException("No prepared truck wheels found for spindle correction");
    }
}
