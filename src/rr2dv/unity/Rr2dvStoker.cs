using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;
using CCL.Types.Components.Simulation;
using CCL.Types.Proxies.Controls;
using CCL.Types.Proxies.Ports;
using Object = UnityEngine.Object;

// Mechanical stoker (pre-build review firing 'mechanical-stoker'), app-side on CCL's own SteamMechanicalStoker, the
// component the core's oil burner already uses (W57/X60 design; the core request for it is still open):
//  - control 'stokerControl' (saved), fed by the generated backhead 'Stoker' valve wheel, which the HUD's Gearbox A slot
//    and keys drive (record ControlsReaderExtra gearboxA, as the oil burner's atomizer; James, 2026-09-29);
//  - 'stoker' moves coal from the bunker into the firebox at up to MaxTransferRate, scaled by boiler pressure from 2 bar
//    to MaxWorkingPressure, and its steam use joins the boiler's steam consumption sum;
//  - on a tender loco the tender's coal amount and consumption cross the coupling as the tender's water already does
//    (CCL TenderSimCreator/SteamerSimCreator): tender coal.AMOUNT -> loco tenderCoal.AMOUNT, loco tenderCoal.CONSUME_EXT_IN
//    -> tender coal.CONSUME_EXT_IN;
//  - the shovel and coal pile stay as a backup (X60: the stoker's firebox feed does not erase shovelled coal).
// Numbers come from this loco's own firebox and boiler, not a preset: see Rr2dvStokerSpec. Runtime-pending (CTRL-01/02).
public static partial class CclLocoBuild
{
    const string StokerControl = "stokerControl", Stoker = "stoker", StokingTag = "RR2DV_STOKING_NORMALIZED";

    // Parts the source animates as stoker/auger toggles (PrepareRr2dvInteractions): car, toggle name, path under the body,
    // local turning axis from the toggle's own clip.
    static readonly List<(string car, string name, string path, Vector3 axis)> Rr2dvStokerParts = new List<(string, string, string, Vector3)>();
    static readonly System.Text.RegularExpressions.Regex Rr2dvStokerToggle =
        new System.Text.RegularExpressions.Regex("auger|stoker", System.Text.RegularExpressions.RegexOptions.IgnoreCase);

    // The local axis a clip turns a transform about: its rotation at the first of the quarter points that has turned it
    // (a full-turn clip is back where it started at its end), relative to its start. Null if it only slides or barely turns.
    static Vector3? Rr2dvClipAxis(AnimationClip clip, string path)
    {
        var part = RefBody.Find(path);
        if (!part) return null;
        clip.SampleAnimation(RefBody.gameObject, 0f);
        var start = part.localRotation;
        Vector3? axis = null;
        foreach (float f in new[] { .25f, .5f, .75f, 1f })
        {
            clip.SampleAnimation(RefBody.gameObject, clip.length * f);
            (Quaternion.Inverse(start) * part.localRotation).ToAngleAxis(out float angle, out Vector3 a);
            if (angle > 5f && angle < 355f) { axis = a.normalized; break; }
        }
        clip.SampleAnimation(RefBody.gameObject, 0f);
        return axis;
    }

    static void BuildRr2dvStoker()
    {
        Section("Mechanical stoker (pre-build review)");
        var loco = Loco; var tender = Loco.Tender;
        string locoPath = $"{builtFolders[loco]}/{loco.CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(locoPath);
        try
        {
            var sim = root.transform.Find("[sim]");
            var conn = sim.GetComponent<SimConnectionsDefinitionProxy>();
            conn.AfterImport();
            string amount, consume;
            if (tender != null)
            {
                var bridge = sim.Find("tenderCoal")?.GetComponent<ConfigurablePortsDefinitionProxy>();
                if (!bridge) throw new InvalidOperationException("mechanical stoker: the loco has no tenderCoal bridge to its tender's coal");
                bridge.AfterImport();
                var ports = bridge.Ports.ToList();
                ports.Add(new ConfigurablePortsDefinitionProxy.PortStartValue(new PortDefinition(DVPortType.READONLY_OUT, DVPortValueType.COAL, "AMOUNT"), 0));
                ports.Add(new ConfigurablePortsDefinitionProxy.PortStartValue(new PortDefinition(DVPortType.EXTERNAL_IN, DVPortValueType.COAL, "CONSUME_EXT_IN"), 0));
                bridge.Ports = ports.ToArray();
                bridge.OnValidate();
                Consumer(bridge.gameObject, "tenderCoal.AMOUNT", DVPortForwardConnectionType.COUPLED_REAR, "TENDER_COAL_AMOUNT", 0, false);
                Provider(bridge.gameObject, "tenderCoal.CONSUME_EXT_IN", DVPortForwardConnectionType.COUPLED_REAR, "TENDER_COAL_CONSUME");
                amount = "tenderCoal.AMOUNT"; consume = "tenderCoal.CONSUME_EXT_IN";
            }
            else
            {
                if (!sim.Find("coal")) throw new InvalidOperationException("mechanical stoker: the tank loco has no 'coal' container");
                amount = "coal.AMOUNT"; consume = "coal.CONSUME_EXT_IN";
            }
            var spec = Rr2dvStokerSpec(sim);

            var control = Child(sim, StokerControl, Vector3.zero).gameObject.AddComponent<ExternalControlDefinitionProxy>();
            control.ID = StokerControl; control.defaultValue = 0; control.saveState = true;
            var stoker = Child(sim, Stoker, Vector3.zero).gameObject.AddComponent<SteamMechanicalStokerDefinition>();
            stoker.ID = Stoker;
            stoker.MaxTransferRate = spec.rate; stoker.MaxSteamConsumption = spec.steam; stoker.MaxWorkingPressure = spec.pressure;
            stoker.SmoothTime = 5f; stoker.FireboxCoalConsumptionMultiplier = spec.multiplier;
            foreach (var (reference, port) in new[] {
                ("CONTROL", StokerControl + ".EXT_IN"), ("STEAM_PRESSURE", "boiler.PRESSURE"),
                ("FIREBOX_COAL_LEVEL", "firebox.COAL_LEVEL"), ("FIREBOX_COAL_CAPACITY", "firebox.COAL_CAPACITY"),
                ("FIREBOX_COAL_CONTROL", "firebox.COAL_CONTROL_EXT_IN"), ("COAL_AMOUNT", amount), ("COAL_CONSUMPTION", consume) })
                conn.portReferenceConnections.Add(new PortReferenceConnectionProxy { portReferenceId = $"{Stoker}.{reference}", portId = port });

            // its steam joins the boiler's consumption (CCL SteamerSimCreator: steamConsumptionCalculator -> boiler.STEAM_CONSUMPTION)
            var sum = sim.Find("steamConsumptionCalculator")?.GetComponent<MultiplePortSumDefinitionProxy>();
            if (!sum) throw new InvalidOperationException("mechanical stoker: no steamConsumptionCalculator for its steam use");
            sum.AfterImport();
            sum.inputs = sum.inputs.Concat(new[] { new PortReferenceDefinition(DVPortValueType.MASS_RATE, "STOKER") }).ToArray();
            sum.OnValidate();
            conn.portReferenceConnections.Add(new PortReferenceConnectionProxy { portReferenceId = "steamConsumptionCalculator.STOKER", portId = Stoker + ".STEAM_CONSUMPTION" });

            // the control before the stoker, the stoker before the steam sum reads it
            conn.executionOrder.RemoveAll(p => p == control || p == stoker);
            int at = conn.executionOrder.IndexOf(sum);
            conn.executionOrder.Insert(at < 0 ? conn.executionOrder.Count : at, stoker);
            conn.executionOrder.Insert(conn.executionOrder.IndexOf(stoker), control);

            // MU / remote neutral closes it, like the other steam valves (the core's oil valve does the same)
            var overrider = root.GetComponentInChildren<BaseControlsOverriderProxy>(true);
            if (overrider)
            {
                var so = new SerializedObject(overrider);
                var ns = so.FindProperty("neutralStateSetters");
                ns.InsertArrayElementAtIndex(ns.arraySize);
                var e = ns.GetArrayElementAtIndex(ns.arraySize - 1);
                e.FindPropertyRelative("portId").stringValue = StokerControl + ".EXT_IN";
                e.FindPropertyRelative("value").floatValue = 0f;
                so.ApplyModifiedPropertiesWithoutUndo();
            }
            // the tender's auger (if one can be found) turns with the stoking rate
            if (tender != null) Provider(stoker.gameObject, Stoker + ".STOKING_NORMALIZED", DVPortForwardConnectionType.COUPLED_REAR, StokingTag);
            // and the loco's own stoker parts (the K-66's stoker drive shaft), from the stoker directly
            var locoParts = Rr2dvDeclaredStokerParts(root.transform, loco);
            if (locoParts.Count > 0)
            {
                var rotator = stoker.gameObject.AddComponent<RotatorPortReaderProxy>();
                rotator.portId = Stoker + ".STOKING_NORMALIZED";
                rotator.transformsToRotate = locoParts.Select(d => new RotatorPortReaderProxy.RotationData { transformToRotate = d.part, rotationAxis = d.axis, maxRps = AugerMaxRps }).ToArray();
                rotator.OnValidate();
                Line($"rr2dv stoker: loco part(s) {string.Join(", ", locoParts.Select(d => d.name))} turn with the stoking rate");
            }
            conn.OnValidate();
            EditorUtility.SetDirty(conn);
            SaveRr2dvPrefab(root, locoPath);
            Line($"rr2dv stoker: {StokerControl} (backhead 'Stoker' wheel, HUD Gearbox A slot and keys) -> {Stoker}: max {spec.rate:F3} kg/s " +
                 $"({spec.rateWhy}), steam up to {spec.steam:F3} kg/s ({spec.steamWhy}), full rate from {spec.pressure:F1} bar ({spec.pressureWhy}), " +
                 $"firebox multiplier {spec.multiplier:F2}; coal from {amount}; shovel and coal pile kept as a backup");
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
        if (tender != null) BuildRr2dvTenderStoker(tender);
    }

    static void BuildRr2dvTenderStoker(LocoConfig tender)
    {
        string path = $"{builtFolders[tender]}/{tender.CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            var sim = root.transform.Find("[sim]");
            var coal = sim.Find("coal");
            if (!coal) throw new InvalidOperationException("mechanical stoker: the tender has no 'coal' container");
            Provider(coal.gameObject, "coal.AMOUNT", DVPortForwardConnectionType.COUPLED_FRONT, "TENDER_COAL_AMOUNT");
            Consumer(coal.gameObject, "coal.CONSUME_EXT_IN", DVPortForwardConnectionType.COUPLED_FRONT, "TENDER_COAL_CONSUME", 0, true);
            var declared = Rr2dvDeclaredStokerParts(root.transform, tender);
            var auger = declared.Count > 0 ? (pivot: (Transform)null, why: "the source's own " + string.Join(", ", declared.Select(d => d.name)))
                                           : Rr2dvAuger(root.transform.Find("Model"));
            var turning = declared.Select(d => new RotatorPortReaderProxy.RotationData { transformToRotate = d.part, rotationAxis = d.axis, maxRps = AugerMaxRps }).ToList();
            if (auger.pivot) turning.Add(new RotatorPortReaderProxy.RotationData { transformToRotate = auger.pivot, rotationAxis = Vector3.forward, maxRps = AugerMaxRps });
            if (turning.Count > 0)
            {
                var conn = sim.GetComponent<SimConnectionsDefinitionProxy>();
                conn.AfterImport();
                var drive = Child(sim, "stokerDrive", Vector3.zero).gameObject.AddComponent<ConfigurablePortsDefinitionProxy>();
                drive.ID = "stokerDrive";
                drive.Ports = new[] { new ConfigurablePortsDefinitionProxy.PortStartValue(new PortDefinition(DVPortType.READONLY_OUT, DVPortValueType.STATE, "NORMALIZED"), 0) };
                drive.OnValidate();
                Consumer(drive.gameObject, "stokerDrive.NORMALIZED", DVPortForwardConnectionType.COUPLED_FRONT, StokingTag, 0, false);
                conn.executionOrder.RemoveAll(p => p == drive);
                conn.executionOrder.Add(drive);
                conn.OnValidate();
                var rotator = drive.gameObject.AddComponent<RotatorPortReaderProxy>();
                rotator.portId = "stokerDrive.NORMALIZED";
                rotator.transformsToRotate = turning.ToArray();
                rotator.OnValidate();
            }
            SaveRr2dvPrefab(root, path);
            Line($"rr2dv stoker: tender coal.AMOUNT and CONSUME_EXT_IN cross the coupling (tags TENDER_COAL_AMOUNT / TENDER_COAL_CONSUME, as the water); auger: {auger.why}");
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    // The source's declared stoker/auger parts on this car, found in the built template's body.
    static List<(string name, Transform part, Vector3 axis)> Rr2dvDeclaredStokerParts(Transform root, LocoConfig car)
    {
        var body = root.Find("Model/" + car.BodyName);
        var found = new List<(string, Transform, Vector3)>();
        foreach (var p in Rr2dvStokerParts.Where(p => p.car == car.CarId))
        {
            var part = body ? body.Find(p.path) : null;
            if (!part && body)
            {
                // the builder may have regrouped animated objects (e.g. under '[anim] water'): match the path's segments in order
                var segs = p.path.Split('/');
                var hits = body.GetComponentsInChildren<Transform>(true).Where(t =>
                {
                    var cur = t;
                    for (int k = segs.Length - 1; k >= 0; k--)
                    {
                        while (cur && cur != body && cur.name != segs[k]) { if (k == segs.Length - 1) return false; cur = cur.parent; }
                        if (!cur || cur == body) return false;
                        cur = cur.parent;
                    }
                    return true;
                }).ToList();
                if (hits.Count == 1) part = hits[0];
            }
            if (part) found.Add((p.name, part, p.axis));
            else Warn($"rr2dv stoker part {p.name}: '{p.path}' not found in the built model; not animated");
        }
        return found;
    }

    // Visual only: a stoker screw at full stoking turns about once every two seconds (DV_choice, not a measurement).
    const float AugerMaxRps = .5f;
    static readonly System.Text.RegularExpressions.Regex AugerName =
        new System.Text.RegularExpressions.Regex(@"auger|stoker|(^|[^a-z])(screw|conveyor|worm)([^a-z]|$)", System.Text.RegularExpressions.RegexOptions.IgnoreCase);

    // When the source has no stoker/auger toggle of its own (those come first: Rr2dvStokerParts), the tender's stoker
    // screw, found by its name and its shape, never guessed ('AugerScrew' counts; a bolt named 'Screw.001' fails the shape): exactly one visible mesh named auger, stoker,
    // screw, conveyor or worm (the name or its parent's) that is long and round (length >= 4x each other extent, the other
    // two within 1.5x of each other) and lies within 30 deg of level. It turns about its own long axis through its middle
    // (a new pivot there; the mesh keeps its place). None, several, or a shape that is not a screw: no animation, and the
    // report says why (James: fall back to no animation where ambiguous).
    static (Transform pivot, string why) Rr2dvAuger(Transform model)
    {
        if (!model) return (null, "no model");
        var named = model.GetComponentsInChildren<MeshFilter>(true)
            .Where(f => f.sharedMesh && f.GetComponent<MeshRenderer>() && (AugerName.IsMatch(f.name) || (f.transform.parent && AugerName.IsMatch(f.transform.parent.name))))
            .ToList();
        if (named.Count == 0) return (null, "none (no mesh named auger, stoker, screw, conveyor or worm): no animation");
        if (named.Count > 1) return (null, $"ambiguous ({named.Count} candidates: {string.Join(", ", named.Take(5).Select(f => f.name))}): no animation");
        var mf = named[0];
        var pts = mf.sharedMesh.vertices.Select(v => model.InverseTransformPoint(mf.transform.TransformPoint(v))).ToArray();
        if (pts.Length < 12) return (null, $"'{mf.name}' has too few vertices to measure: no animation");
        var c = pts.Aggregate(Vector3.zero, (a, p) => a + p) / pts.Length;
        var (axes, ext) = Rr2dvPrincipal(pts, c);
        if (ext[0] < 4 * ext[1] || ext[1] > 1.5f * ext[2] || Mathf.Abs(axes[0].y) > .5f)
            return (null, $"'{mf.name}' is not a level screw shape (extents {ext[0]:F2}/{ext[1]:F2}/{ext[2]:F2} m, axis {V(axes[0])}): no animation");
        var pivot = new GameObject("rr2dv auger pivot").transform;
        pivot.SetParent(mf.transform.parent, false);
        pivot.position = model.TransformPoint(c);
        pivot.rotation = Quaternion.LookRotation(model.TransformDirection(axes[0]), model.up);
        try { mf.transform.SetParent(pivot, true); }
        catch (Exception e)  // e.g. a part of a prefab instance that cannot be restructured
        {
            Object.DestroyImmediate(pivot.gameObject);
            return (null, $"'{mf.name}' could not be given a pivot on its axis ({e.Message}): no animation");
        }
        return (pivot, $"'{mf.name}' turns about its long axis {V(axes[0])} through {V(c)} (length {ext[0]:F2} m), up to {AugerMaxRps} rev/s with the stoking rate");
    }

    // Principal axes of a point cloud (power iteration on the covariance) and the cloud's extent along each.
    static (Vector3[] axes, float[] ext) Rr2dvPrincipal(Vector3[] pts, Vector3 c)
    {
        float xx = 0, xy = 0, xz = 0, yy = 0, yz = 0, zz = 0;
        foreach (var p in pts) { var d = p - c; xx += d.x * d.x; xy += d.x * d.y; xz += d.x * d.z; yy += d.y * d.y; yz += d.y * d.z; zz += d.z * d.z; }
        Vector3 Mul(Vector3 v) => new Vector3(xx * v.x + xy * v.y + xz * v.z, xy * v.x + yy * v.y + yz * v.z, xz * v.x + yz * v.y + zz * v.z);
        Vector3 Dominant(Vector3 start, Func<Vector3, Vector3> project)
        {
            var v = project(start).normalized;
            for (int i = 0; i < 64; i++) { var n = project(Mul(v)); if (n.sqrMagnitude < 1e-12f) break; v = n.normalized; }
            return v;
        }
        var a0 = Dominant(new Vector3(.3f, .2f, .9f), v => v);
        var a1 = Dominant(Vector3.Cross(a0, Math.Abs(a0.y) < .9f ? Vector3.up : Vector3.right), v => v - Vector3.Dot(v, a0) * a0);
        var a2 = Vector3.Cross(a0, a1).normalized;
        var axes = new[] { a0, a1, a2 };
        var ext = axes.Select(a => pts.Max(p => Vector3.Dot(p - c, a)) - pts.Min(p => Vector3.Dot(p - c, a))).ToArray();
        return (axes, ext);
    }

    // Transfer rate: enough to keep a full firebox at the loco's own burn rate (capacity / burn time, times the firebox's coal
    // multiplier), with half again to build the fire back up. Steam: the loco's own steam air pump's full use (a stoker engine
    // is a small reciprocating steam engine of that class; analogue_estimate). Full rate from half the safety-valve pressure.
    static (float rate, string rateWhy, float steam, string steamWhy, float pressure, string pressureWhy, float multiplier) Rr2dvStokerSpec(Transform sim)
    {
        float Field(string component, string field)
        {
            var t = sim.Find(component);
            if (!t) return float.NaN;
            foreach (var c in t.GetComponents<Component>())
            {
                var p = c ? new SerializedObject(c).FindProperty(field) : null;
                if (p != null && p.propertyType == SerializedPropertyType.Float) return p.floatValue;
            }
            return float.NaN;
        }
        float capacity = Field("firebox", "maxCoalCapacity"), burn = Field("firebox", "burnTime"), multiplier = Field("firebox", "coalConsumptionMultiplier");
        if (float.IsNaN(multiplier) || multiplier <= 0) multiplier = 1f;
        if (float.IsNaN(capacity) || float.IsNaN(burn) || capacity <= 0 || burn <= 0)
            throw new InvalidOperationException("mechanical stoker: the firebox's maxCoalCapacity and burnTime could not be read");
        float rate = 1.5f * capacity / burn * multiplier;
        string rateWhy = $"1.5 x firebox {capacity:F0} kg / {burn:F1} s x {multiplier:F2}";
        float steam = Field("compressor", "maxSteamConsumption");
        string steamWhy = "the steam air pump's full use (analogue)";
        if (float.IsNaN(steam) || steam <= 0)
        {
            steam = 0f;
            steamWhy = "none: no steam air pump figure to take it from";
            Warn("rr2dv stoker: no compressor maxSteamConsumption found; the stoker uses no steam (check boiler draw in game)");
        }
        float safety = Field("boiler", "safetyValveOpeningPressure");
        float pressure = float.IsNaN(safety) || safety <= 4 ? 6f : safety / 2;
        string pressureWhy = float.IsNaN(safety) || safety <= 4 ? "CCL's default: no safety-valve pressure read" : $"half the {safety:F1} bar safety-valve pressure";
        return (rate, rateWhy, steam, steamWhy, pressure, pressureWhy, multiplier);
    }

    static void Provider(GameObject go, string port, DVPortForwardConnectionType connection, string tag)
    {
        var p = go.AddComponent<BroadcastPortValueProviderProxy>();
        p.providerPortId = port; p.connection = connection; p.connectionTag = tag;
    }

    static void Consumer(GameObject go, string port, DVPortForwardConnectionType connection, string tag, float disconnected, bool propagate)
    {
        var c = go.AddComponent<BroadcastPortValueConsumerProxy>();
        c.consumerPortId = port; c.connection = connection; c.connectionTag = tag;
        c.disconnectedValue = disconnected; c.propagateConsumerValueChangeBackToProvider = propagate;
    }
}
