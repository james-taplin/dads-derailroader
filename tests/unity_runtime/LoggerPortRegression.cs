// Standalone .NET Framework check against installed game assemblies; never starts
// the game or installs a mod. Arguments: Managed directory, compiled logger DLL.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.IO;
using System.Reflection;
using System.Runtime.Serialization;

class LoggerPortRegression
{
    static int Main(string[] args)
    {
        AppDomain.CurrentDomain.AssemblyResolve += (sender, e) => {
            string name = new AssemblyName(e.Name).Name + ".dll";
            foreach (string dir in new[] { args[0], Path.Combine(args[0], "UnityModManager") })
            {
                string path = Path.Combine(dir, name);
                if (File.Exists(path)) return Assembly.LoadFrom(path);
            }
            return null;
        };
        try
        {
            var sim = Assembly.LoadFrom(Path.Combine(args[0], "DV.Simulation.dll"));
            var flowType = sim.GetType("LocoSim.Implementations.SimulationFlow", true);
            var portType = sim.GetType("LocoSim.Implementations.Port", true);
            var flow = FormatterServices.GetUninitializedObject(flowType);
            var port = FormatterServices.GetUninitializedObject(portType);
            portType.GetField("value", BindingFlags.NonPublic | BindingFlags.Instance).SetValue(port, .75f);
            var mapType = typeof(Dictionary<,>).MakeGenericType(typeof(string), portType);
            var map = (IDictionary)Activator.CreateInstance(mapType);
            map.Add("whistle.EXT_IN", port);
            var readOnly = Activator.CreateInstance(typeof(ReadOnlyDictionary<,>).MakeGenericType(typeof(string), portType), map);
            flowType.GetField("fullPortIdToPort", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(flow, readOnly);
            var logger = Assembly.LoadFrom(Path.GetFullPath(args[1]));
            MethodInfo lookup = null;
            foreach (var type in logger.GetTypes())
            {
                var method = type.GetMethod("PortValue", BindingFlags.NonPublic | BindingFlags.Static);
                if (method != null) { lookup = method; break; }
            }
            if (lookup == null) throw new Exception("logger lookup not found");
            for (int i = 0; i < 330; i++)
                if (!float.IsNaN((float)lookup.Invoke(null, new object[] { flow, "missing.OPTIONAL" })))
                    throw new Exception("missing optional port returned a value");
            if ((float)lookup.Invoke(null, new object[] { flow, "whistle.EXT_IN" }) != .75f)
                throw new Exception("valid port value lost");
            if (!float.IsNaN((float)lookup.Invoke(null, new object[] { null, "whistle.EXT_IN" })))
                throw new Exception("null simulation returned a value");
            Console.WriteLine("PASS: 330 absent-port reads, valid whistle value, null simulation; no Unity logging invoked");
            return 0;
        }
        catch (Exception e) { Console.Error.WriteLine(e); return 1; }
    }
}
