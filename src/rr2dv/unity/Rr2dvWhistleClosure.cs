// Whistle closure (CTRL-02): a closed whistle must command exactly 0 to the steam exhaust.
// Game test 2026-09-28 (every converted loco, every input route: drag and release, scroll, Enter, HUD): after one use the
// whistle lever settles a fraction short of zero, and Derail Valley's steam sim turns that residue into a constant low
// chime. A joint spring cannot promise an exact zero, so the exhaust reads the whistle through a deadzone instead:
//   whistleDeadzone = whistle.EXT_IN / (1 - d) - d / (1 - d)     (CCL Constant Multiplier + Offset)
//   whistleClosure  = MAX(whistleDeadzone, 0)                     (DV Configurable Function, with a constant 0 port)
// Below d of the lever's travel the valve is exactly 0; above it the whole range 0..1 is kept. The whistle control,
// its HUD and keyboard routes, and its linkage animation are unchanged (they read whistle.EXT_IN).
using System;
using System.Linq;
using UnityEditor;
using UnityEngine;
using CCL.Types.Components.Simulation;
using CCL.Types.Proxies.Ports;

public static partial class CclLocoBuild
{
    const float Rr2dvWhistleDeadzone = .05f;

    static void CloseRr2dvWhistle()
    {
        string path = $"{carFolder}/{CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            var sim = root.transform.Find("[sim]");
            var connections = sim ? sim.GetComponent<SimConnectionsDefinitionProxy>() : null;
            if (!connections) throw new InvalidOperationException("Missing [sim] connections for the whistle closure");
            connections.AfterImport();
            var link = connections.portReferenceConnections.Where(c => c.portReferenceId == "exhaust.WHISTLE_CONTROL").ToArray();
            if (link.Length != 1 || link[0].portId != "whistle.EXT_IN")
            {
                Warn("rr2dv whistle closure not added: expected exhaust.WHISTLE_CONTROL <- whistle.EXT_IN, found " +
                     (link.Length == 0 ? "none" : string.Join(", ", link.Select(c => c.portReferenceId + " <- " + c.portId))) +
                     " (a closed whistle may not command exactly 0; CTRL-02 check in game)");
                return;
            }

            float d = Rr2dvWhistleDeadzone;
            var dead = Child(sim, "whistleDeadzone", Vector3.zero).gameObject.AddComponent<ConstantMultiplierOffsetDefinition>();
            dead.ID = "whistleDeadzone";
            dead.Multiplier = 1f / (1f - d);
            dead.Offset = -d / (1f - d);
            dead.Input = new PortReferenceDefinition(DVPortValueType.CONTROL, "IN");
            dead.Output = new PortDefinition(DVPortType.READONLY_OUT, DVPortValueType.CONTROL, "OUT");
            dead.OnValidate();

            var zero = Child(sim, "whistleZero", Vector3.zero).gameObject.AddComponent<ConfigurablePortDefinitionProxy>();
            zero.ID = "whistleZero";
            zero.value = 0f;
            zero.port = new PortDefinition(DVPortType.READONLY_OUT, DVPortValueType.CONTROL, "VALUE");
            zero.OnValidate();

            var closure = Child(sim, "whistleClosure", Vector3.zero).gameObject.AddComponent<ConfigurableFunctionDefinitionProxy>();
            closure.ID = "whistleClosure";
            closure.type = ConfigurableFunctionDefinitionProxy.FunctionType.MAX;
            closure.readers = new[] { new PortReferenceDefinition(DVPortValueType.CONTROL, "OPEN"), new PortReferenceDefinition(DVPortValueType.CONTROL, "ZERO") };
            closure.outReadOut = new PortDefinition(DVPortType.READONLY_OUT, DVPortValueType.CONTROL, "OUT");
            closure.OnValidate();

            connections.portReferenceConnections.Add(new PortReferenceConnectionProxy { portReferenceId = "whistleDeadzone.IN", portId = "whistle.EXT_IN" });
            connections.portReferenceConnections.Add(new PortReferenceConnectionProxy { portReferenceId = "whistleClosure.OPEN", portId = "whistleDeadzone.OUT" });
            connections.portReferenceConnections.Add(new PortReferenceConnectionProxy { portReferenceId = "whistleClosure.ZERO", portId = "whistleZero.VALUE" });
            link[0].portId = "whistleClosure.OUT";

            // Evaluated before the exhaust reads it, in this order. CCL's Reset() already appended each new component to
            // the execution order when it was added; take them out first or they are listed twice (camelback audit).
            connections.executionOrder.RemoveAll(c => c == zero || c == dead || c == closure);
            var exhaust = connections.executionOrder.FindIndex(c => c && c.ID == "exhaust");
            if (exhaust < 0) throw new InvalidOperationException("Missing exhaust in the simulation execution order");
            connections.executionOrder.InsertRange(exhaust, new SimComponentDefinitionProxy[] { zero, dead, closure });
            connections.OnValidate();
            Line($"rr2dv whistle closure: exhaust.WHISTLE_CONTROL reads MAX(0, (whistle - {d:F2}) / {1 - d:F2}); " +
                 $"below {d * 100:F0}% of travel the valve is exactly 0 (CTRL-02), full travel still 1");
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }
}
