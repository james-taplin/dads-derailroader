using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using DV.CabControls;
using DV.KeyboardInput;
using DV.Simulation.Cars;
using DV.Simulation.Ports;
using HarmonyLib;
using LocoSim.Implementations;
using UnityEngine;
using UnityModManagerNet;

[assembly: AssemblyVersion("0.2.0.0")]
[assembly: AssemblyFileVersion("0.2.0.0")]

namespace RR2DVControlLogger
{
    // rr2dv control logger: a passive, low-impact diagnostic for tuning converted controls (James, 2026-09-29).
    // Writes <Derail Valley>/rr2dv-controls.log. For the loco whose cab is loaded it records every change of a cab control's
    // value (0..1) and of the sim port it feeds, which input most likely caused it (keyboard, scroll, grab, F4 HUD, or no
    // player input: the sim or another mod), and a snapshot of watched sim ports at the change, +1 s and +3 s.
    // It never writes to the game. C# 5 (csc /langversion:5, as DVCCLControlFix): no ?., no $"", no nameof.
    public static class Main
    {
        internal static UnityModManager.ModEntry Mod;
        private static Harmony _harmony;
        private static GameObject _runner;

        public static bool Load(UnityModManager.ModEntry modEntry)
        {
            Mod = modEntry;
            try
            {
                Log.Open(modEntry.Path);
                _harmony = new Harmony(modEntry.Info.Id);
                _harmony.PatchAll(Assembly.GetExecutingAssembly());
                KeyboardTicks.PatchAll(_harmony);
                _runner = new GameObject("rr2dv control logger");
                UnityEngine.Object.DontDestroyOnLoad(_runner);
                _runner.AddComponent<Watcher>();
            }
            catch (Exception ex)
            {
                modEntry.Logger.Error("rr2dv control logger failed to start: " + ex);
                return false;
            }
            modEntry.OnToggle = OnToggle;
            return true;
        }

        private static bool OnToggle(UnityModManager.ModEntry modEntry, bool value)
        {
            if (_runner != null) _runner.SetActive(value);
            Log.Write(value ? "logger on" : "logger off");
            return true;
        }
    }

    // Buffered file writer, flushed once a second by the Watcher.
    internal static class Log
    {
        private static StreamWriter _w;
        internal static string[] WatchPorts = new string[0];

        internal static void Open(string modPath)
        {
            string root = Path.GetDirectoryName(Application.dataPath);
            _w = new StreamWriter(Path.Combine(root, "rr2dv-controls.log"), true, Encoding.UTF8);
            _w.WriteLine();
            _w.WriteLine("==== rr2dv control logger 0.2.0, session " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
            _w.WriteLine("columns: time | car | control | port | source | control value old -> new (delta) | port value");
            string watch = Path.Combine(modPath, "watch.txt");
            if (!File.Exists(watch)) File.WriteAllText(watch, DefaultWatch);
            var ports = new List<string>();
            foreach (var line in File.ReadAllLines(watch))
            {
                string t = line.Trim();
                if (t.Length > 0 && !t.StartsWith("#")) ports.Add(t);
            }
            WatchPorts = ports.ToArray();
            _w.WriteLine("watched ports (" + watch + "): " + string.Join(", ", WatchPorts));
            _w.Flush();
        }

        internal static void Write(string line)
        {
            if (_w != null) _w.WriteLine(Time.realtimeSinceStartup.ToString("F2").PadLeft(9) + " | " + line);
        }

        internal static void Flush()
        {
            if (_w != null) _w.Flush();
        }

        // Port ids seen in rr2dv builds (build_report sim components); a port the car lacks is skipped.
        private const string DefaultWatch =
            "# one full port id per line; edit and restart the game\n" +
            "boiler.PRESSURE\nsteamEngine.STEAM_CHEST_PRESSURE\ntraction.WHEEL_SPEED_KMH_EXT_IN\n" +
            "exhaust.WHISTLE_CONTROL\nbell.BELL_NORMALIZED\ncompressor.PRODUCTION_RATE_NORMALIZED\n" +
            "sander.SAND_FLOW\nsand.NORMALIZED\nlubricator.LUBRICATION_NORMALIZED\noil.NORMALIZED\n" +
            "firebox.TEMPERATURE\nfirebox.COAL_LEVEL\nboiler.WATER_LEVEL_NORMALIZED\n" +
            "headlightDecoder.FRONT_HEADLIGHTS_EXT_IN\nheadlightDecoder.REAR_HEADLIGHTS_EXT_IN\n";
    }

    // Each car's simulation, captured where DV sets up its controls.
    [HarmonyPatch(typeof(BaseControlsOverrider), "Init", new[] { typeof(TrainCar), typeof(SimulationFlow) })]
    internal static class BaseControlsOverrider_Init_Patch
    {
        internal static readonly Dictionary<TrainCar, SimulationFlow> Flows = new Dictionary<TrainCar, SimulationFlow>();

        // positional arguments (__0, __1): Harmony matches names, and only the first one's name is known
        private static void Postfix(TrainCar __0, SimulationFlow __1)
        {
            if (__0 != null && __1 != null) Flows[__0] = __1;
        }
    }

    // Marks controls whose keyboard input changed them during its own Tick. Every concrete AKeyboardInput type that
    // declares Tick(float) is patched, since overrides do not pass through the base method.
    internal static class KeyboardTicks
    {
        internal static readonly Dictionary<int, float> LastKeyChange = new Dictionary<int, float>();

        internal static void PatchAll(Harmony harmony)
        {
            var pre = new HarmonyMethod(typeof(KeyboardTicks).GetMethod("Prefix", BindingFlags.Static | BindingFlags.NonPublic));
            var post = new HarmonyMethod(typeof(KeyboardTicks).GetMethod("Postfix", BindingFlags.Static | BindingFlags.NonPublic));
            foreach (var t in typeof(AKeyboardInput).Assembly.GetTypes())
            {
                if (t.IsAbstract || !typeof(AKeyboardInput).IsAssignableFrom(t)) continue;
                var m = AccessTools.DeclaredMethod(t, "Tick", new[] { typeof(float) });
                if (m != null) harmony.Patch(m, pre, post);
            }
        }

        private static void Prefix(AKeyboardInput __instance, out float __state)
        {
            var c = __instance.GetComponent<ControlImplBase>();
            __state = c != null ? c.Value : float.NaN;
        }

        private static void Postfix(AKeyboardInput __instance, float __state)
        {
            var c = __instance.GetComponent<ControlImplBase>();
            if (c != null && !float.IsNaN(__state) && Math.Abs(c.Value - __state) > 1e-4f)
                LastKeyChange[c.GetInstanceID()] = Time.realtimeSinceStartup;
        }
    }

    // The car's air-brake pressures (brake pipe, main reservoir, cylinder...), which the HUD reads from the car's brake system
    // rather than a sim port. Found by reflection by name (a 'brakeSystem' member, then its float members named '*pressure*'),
    // so the logger needs no compile-time reference to them and simply logs nothing if DV names them differently.
    internal static class Brakes
    {
        private const BindingFlags Any = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
        private static readonly Dictionary<Type, MemberInfo> SystemMember = new Dictionary<Type, MemberInfo>();
        private static readonly Dictionary<Type, List<MemberInfo>> PressureMembers = new Dictionary<Type, List<MemberInfo>>();

        internal static void Append(TrainCar car, StringBuilder sb)
        {
            try
            {
                object system = Value(Find(car.GetType()), car);
                if (system == null) return;
                foreach (var m in Pressures(system.GetType()))
                {
                    object v = Value(m, system);
                    if (v is float) sb.Append(sb.Length > 0 ? ", " : "").Append("brakes.").Append(m.Name).Append('=').Append(((float)v).ToString("0.000"));
                }
            }
            catch (Exception) { }
        }

        private static MemberInfo Find(Type t)
        {
            MemberInfo m;
            if (SystemMember.TryGetValue(t, out m)) return m;
            m = null;
            foreach (var f in t.GetFields(Any)) if (string.Equals(f.Name, "brakeSystem", StringComparison.OrdinalIgnoreCase)) { m = f; break; }
            if (m == null)
                foreach (var p in t.GetProperties(Any)) if (string.Equals(p.Name, "brakeSystem", StringComparison.OrdinalIgnoreCase)) { m = p; break; }
            SystemMember[t] = m;
            return m;
        }

        private static List<MemberInfo> Pressures(Type t)
        {
            List<MemberInfo> list;
            if (PressureMembers.TryGetValue(t, out list)) return list;
            list = new List<MemberInfo>();
            foreach (var f in t.GetFields(Any))
                if (f.FieldType == typeof(float) && f.Name.IndexOf("pressure", StringComparison.OrdinalIgnoreCase) >= 0) list.Add(f);
            foreach (var p in t.GetProperties(Any))
                if (p.PropertyType == typeof(float) && p.CanRead && p.GetIndexParameters().Length == 0 &&
                    p.Name.IndexOf("pressure", StringComparison.OrdinalIgnoreCase) >= 0) list.Add(p);
            PressureMembers[t] = list;
            return list;
        }

        private static object Value(MemberInfo m, object o)
        {
            var f = m as FieldInfo;
            if (f != null) return f.GetValue(o);
            var p = m as PropertyInfo;
            return p != null ? p.GetValue(o, null) : null;
        }
    }

    internal class Watcher : MonoBehaviour
    {
        private class Entry
        {
            public InteractablePortFeeder Feeder;
            public ControlImplBase Control;
            public float LastValue = float.NaN, LastPort = float.NaN;
        }

        private const float Period = 0.1f;
        private float _poll, _flush;
        private float _lastKey = -99f, _lastScroll = -99f, _lastGrab = -99f, _lastHud = -99f;
        private GameObject _interior;
        private readonly List<Entry> _entries = new List<Entry>();
        private readonly List<KeyValuePair<float, string>> _followUps = new List<KeyValuePair<float, string>>();

        private void Update()
        {
            float now = Time.realtimeSinceStartup;
            // what the player is doing this frame (cheap Unity input reads; DV's own input is untouched)
            bool mouse = Input.GetMouseButton(0) || Input.GetMouseButton(1);
            if (mouse && Cursor.visible) _lastHud = now;
            else if (mouse) _lastGrab = now;
            if (Input.mouseScrollDelta.y != 0f) _lastScroll = now;
            if (Input.anyKey && !mouse) _lastKey = now;

            _flush += Time.unscaledDeltaTime;
            if (_flush >= 1f) { _flush = 0f; Log.Flush(); }
            _poll += Time.unscaledDeltaTime;
            if (_poll < Period) return;
            _poll = 0f;
            try { Poll(now); }
            catch (Exception ex) { Log.Write("logger error: " + ex.Message); }
        }

        private void Poll(float now)
        {
            TrainCar car = null; SimulationFlow flow = null;
            foreach (var kv in BaseControlsOverrider_Init_Patch.Flows)
                if (kv.Key != null && kv.Key.loadedInterior != null) { car = kv.Key; flow = kv.Value; break; }
            if (car == null) { _interior = null; _entries.Clear(); return; }
            if (car.loadedInterior != _interior)
            {
                _interior = car.loadedInterior;
                _entries.Clear();
                foreach (var f in _interior.GetComponentsInChildren<InteractablePortFeeder>(true))
                    if (f != null && !string.IsNullOrEmpty(f.portId))
                        _entries.Add(new Entry { Feeder = f, Control = f.GetComponent<ControlImplBase>() });
                Log.Write(Id(car) + " | cab loaded: " + _entries.Count + " controls");
                Snapshot(car, flow, "cab loaded");
            }
            // several controls jumping in one poll is the comms-radio startup, a HUD preset or another mod, not a hand
            int moving = 0;
            foreach (var e in _entries)
                if (e.Feeder != null && e.Control != null && !float.IsNaN(e.LastValue) && !Same(e.Control.Value, e.LastValue)) moving++;
            foreach (var e in _entries)
            {
                if (e.Feeder == null) continue;
                float value = e.Control != null ? e.Control.Value : float.NaN;
                float port = PortValue(flow, e.Feeder.portId);
                bool controlMoved = !float.IsNaN(value) && !Same(value, e.LastValue);
                bool portMoved = !float.IsNaN(port) && !Same(port, e.LastPort);
                if (controlMoved && !float.IsNaN(e.LastValue))
                {
                    string source = moving >= 3 && !KeyboardFlag(e, now) ? moving + " controls at once (radio startup, HUD preset or another mod)" : Source(e, now);
                    Log.Write(Id(car) + " | " + e.Feeder.name + " | " + e.Feeder.portId + " | " + source + " | " +
                              F(e.LastValue) + " -> " + F(value) + " (" + (value - e.LastValue).ToString("+0.000;-0.000") + ") | port " + F(port));
                    string tag = e.Feeder.name;
                    Snapshot(car, flow, "at " + tag);
                    _followUps.Add(new KeyValuePair<float, string>(now + 1f, "+1 s after " + tag));
                    _followUps.Add(new KeyValuePair<float, string>(now + 3f, "+3 s after " + tag));
                }
                else if (portMoved && !float.IsNaN(e.LastPort))
                {
                    // the port moved but its control did not: something else writes it (the sim, another mod, the HUD)
                    Log.Write(Id(car) + " | " + e.Feeder.name + " | " + e.Feeder.portId + " | port changed without the control | " +
                              "control " + F(value) + " | port " + F(e.LastPort) + " -> " + F(port));
                }
                e.LastValue = value; e.LastPort = port;
            }
            for (int i = _followUps.Count - 1; i >= 0; i--)
                if (_followUps[i].Key <= now) { Snapshot(car, flow, _followUps[i].Value); _followUps.RemoveAt(i); }
        }

        private static bool KeyboardFlag(Entry e, float now)
        {
            float key;
            return e.Control != null && KeyboardTicks.LastKeyChange.TryGetValue(e.Control.GetInstanceID(), out key) && now - key < 1f;
        }

        private string Source(Entry e, float now)
        {
            if (KeyboardFlag(e, now)) return "keyboard";
            float best = Math.Max(Math.Max(_lastKey, _lastScroll), Math.Max(_lastGrab, _lastHud));
            if (now - best > 1f) return "no player input (sim or another mod)";
            if (best == _lastHud) return "F4 HUD (mouse, cursor shown)";
            if (best == _lastGrab) return "grab (mouse)";
            if (best == _lastScroll) return "scroll";
            return "keyboard";
        }

        private static void Snapshot(TrainCar car, SimulationFlow flow, string why)
        {
            var sb = new StringBuilder();
            foreach (var id in Log.WatchPorts)
            {
                float v = PortValue(flow, id);
                if (!float.IsNaN(v)) sb.Append(sb.Length > 0 ? ", " : "").Append(id).Append('=').Append(F(v));
            }
            Brakes.Append(car, sb);
            if (sb.Length > 0) Log.Write(Id(car) + " |   sim " + why + ": " + sb);
        }

        private static float PortValue(SimulationFlow flow, string id)
        {
            Port p;
            return flow != null && flow.TryGetPort(id, out p) && p != null ? p.Value : float.NaN;
        }

        private static bool Same(float a, float b)
        {
            return !float.IsNaN(b) && Math.Abs(a - b) <= 1e-3f;
        }

        private static string F(float v)
        {
            return float.IsNaN(v) ? "-" : v.ToString("0.000");
        }

        private static string Id(TrainCar car)
        {
            return car.carLivery != null ? car.carLivery.id : car.name;
        }
    }
}
