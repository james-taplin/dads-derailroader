using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using UnityEditor;
using UnityEngine;

// Editor-only JSON -> LocoConfig adapter. Existing C# profiles keep their original entry points.
// Values are data, never executable C#; numeric values require B03 provenance. See VEHICLE_RECORD.md.
public static class LlwVehicleRecord
{
    static readonly HashSet<string> Bases = new HashSet<string> { "source", "measured", "derived", "analogue_estimate", "DV_choice" };
    static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

    public static void Build()
    {
        try
        {
            string path = Environment.GetEnvironmentVariable("CCL_VEHICLE_RECORD");
            if (string.IsNullOrWhiteSpace(path)) throw Fail("CCL_VEHICLE_RECORD", "must name the reviewed JSON record");
            var cfg = Load(path);
            string catalog = Environment.GetEnvironmentVariable("CCL_CATALOG_RECORD");
            if (!string.IsNullOrEmpty(catalog))
            {
                var root = Obj(Json.Parse(File.ReadAllText(path)), "$record");
                cfg = LlwCatalogConfig.Apply(cfg, (string)root["vehicleId"]);
            }
            PrepareSources(cfg);
            if (Environment.GetEnvironmentVariable("CCL_SHARE") == "1") ApplyShareAudio(cfg);
            Debug.Log("[LlwVehicleRecord] " + Path.GetFullPath(path));
            CclLocoBuild.Run(cfg);
        }
        catch (Exception e)
        {
            Debug.LogException(e);
            string output = Environment.GetEnvironmentVariable("CCL_BUILD_OUT");
            if (!string.IsNullOrEmpty(output))
            {
                Directory.CreateDirectory(output);
                File.WriteAllText(Path.Combine(output, "build_report.txt"), "Vehicle record validation failed\n" + e);
                File.WriteAllText(Path.Combine(output, "result.json"), "{\"exported\":false,\"warnings\":0,\"runtimeValidated\":false,\"recordValidationFailed\":true}");
            }
            EditorApplication.Exit(1);
        }
    }

    public static LocoConfig Load(string path) { return LoadJson(File.ReadAllText(path)); }

    static void ApplyShareAudio(LocoConfig c)
    {
        c.Sounds.Clear();
        c.RemoveVanillaSounds = new string[0];
        if (c.Tender != null) ApplyShareAudio(c.Tender);
    }

    // Optional Unity -executeMethod check. Imports no new assets and does not build/export a car.
    public static void ValidateRecord()
    {
        try
        {
            string path = Environment.GetEnvironmentVariable("CCL_VEHICLE_RECORD");
            if (string.IsNullOrWhiteSpace(path)) throw Fail("CCL_VEHICLE_RECORD", "required");
            var cfg = Load(path);
            if (AssetDatabase.LoadAssetAtPath<GameObject>(cfg.SrcPrefab) == null) throw Fail(cfg.SrcPrefab, "missing source prefab");
            PrepareSources(cfg);
            Debug.Log("[LlwVehicleRecord] record and component parents validated: " + cfg.CarId);
            string output = Environment.GetEnvironmentVariable("CCL_BUILD_OUT");
            if (!string.IsNullOrEmpty(output))
            {
                Directory.CreateDirectory(output);
                File.WriteAllText(Path.Combine(output, "record_validation.json"), "{\"schema\":1,\"validated\":true,\"components\":" + cfg.Components.Count + ",\"runtimeValidated\":false}");
            }
            EditorApplication.Exit(0);
        }
        catch (Exception e) { Debug.LogException(e); EditorApplication.Exit(1); }
    }

    // Source Comp parentPath explicitly means parent-local coordinates. The core expects car space.
    // Bake each once and clear parentPath. Missing source parents are errors, never zero/local fallbacks.
    public static void PrepareSources(LocoConfig cfg)
    {
        if (cfg.Components.Any(c => !string.IsNullOrEmpty(c.parentPath)))
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(cfg.SrcPrefab);
            if (prefab == null) throw Fail(cfg.SrcPrefab, "missing source prefab");
            var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
            try
            {
                foreach (var c in cfg.Components)
                {
                    if (string.IsNullOrEmpty(c.parentPath)) continue;
                    Transform parent = go.transform.Find(c.parentPath);
                    if (parent == null) throw Fail(c.name, "source component parent does not exist: " + c.parentPath);
                    c.pos = go.transform.InverseTransformPoint(parent.TransformPoint(c.pos));
                    c.rot = Quaternion.Inverse(go.transform.rotation) * parent.rotation * c.rot;
                    c.scale = Vector3.Scale(parent.lossyScale, c.scale);
                    c.parentPath = "";
                }
            }
            finally { UnityEngine.Object.DestroyImmediate(go); }
        }
        if (cfg.Tender != null) PrepareSources(cfg.Tender);
    }

    // Kept independent of AssetDatabase so the data contract can be tested without opening a project.
    public static LocoConfig LoadJson(string json)
    {
        var record = Obj(Json.Parse(json), "$record");
        Only(record, "$record", "schemaVersion", "vehicleId", "config", "hooks", "metadata", "tender");
        if (!record.ContainsKey("schemaVersion") || Convert.ToInt32(record["schemaVersion"], Inv) != 1)
            throw Fail("schemaVersion", "expected 1");
        if (!record.ContainsKey("vehicleId") || !(record["vehicleId"] is string) || string.IsNullOrWhiteSpace((string)record["vehicleId"]))
            throw Fail("vehicleId", "required source identifier");
        return ReadCar(record, "$record");
    }

    static LocoConfig ReadCar(Dictionary<string, object> record, string path)
    {
        object raw;
        if (!record.TryGetValue("config", out raw)) throw Fail(path, "missing config");
        CheckEvidence(raw, path + ".config", false);
        var plain = Obj(Unwrap(raw), path + ".config");
        if (plain.ContainsKey("Tender")) throw Fail(path + ".config.Tender", "use the tender record with its own config/hooks");
        var cfg = (LocoConfig)Read(plain, typeof(LocoConfig), path + ".config");
        if (record.TryGetValue("hooks", out raw))
        {
            CheckEvidence(raw, path + ".hooks", false);
            ApplyHooks(cfg, Obj(Unwrap(raw), path + ".hooks"), path + ".hooks");
        }
        if (record.TryGetValue("tender", out raw) && raw != null)
        {
            var tender = Obj(raw, path + ".tender");
            Only(tender, path + ".tender", "config", "hooks", "metadata");
            cfg.Tender = ReadCar(tender, path + ".tender");
            if (!cfg.Tender.IsTender) throw Fail(path + ".tender", "IsTender must be true");
        }
        Validate(cfg, plain, path);
        return cfg;
    }

    static void Validate(LocoConfig c, Dictionary<string, object> raw, string p)
    {
        foreach (string k in new[] { "CarId", "CarName", "Version", "Author", "SrcPrefab", "Work", "BodyName", "Livery", "Components", "MaterialMap", "AnimationMap", "Liveries", "Wheelsets", "WeightEmptyKg", "WheelRadius", "WaterCapacityL", "CoalCapacityKg" })
            if (!raw.ContainsKey(k) || raw[k] == null || (raw[k] is string && string.IsNullOrWhiteSpace((string)raw[k])))
                throw Fail(p + ".config." + k, "required and must be known");
        // Run deletes Work before creating generated assets. Restrict it to one dedicated subtree.
        if (!c.Work.StartsWith("Assets/", StringComparison.Ordinal) || c.Work.Split('/').Length < 3 || c.Work.Contains("..") || c.Work.Contains('\\'))
            throw Fail(p + ".config.Work", "must be a dedicated Assets/<conversion>/<car> subtree");
        if (!c.SrcPrefab.StartsWith("Assets/", StringComparison.Ordinal) || c.SrcPrefab.Contains(".."))
            throw Fail(p + ".config.SrcPrefab", "must be an Assets path");
        if (c.WeightEmptyKg <= 0 || c.WheelRadius <= 0 || c.WaterCapacityL < 0 || c.CoalCapacityKg < 0)
            throw Fail(p, "mass/radius must be positive; resource capacities cannot be negative");
        if (c.Components.Count == 0 || c.MaterialMap.Count == 0 || c.Liveries.Length == 0 || c.Wheelsets.Length == 0)
            throw Fail(p, "source components, materials, liveries and wheelsets cannot be empty");
        if (!c.Liveries.Any(l => l.name == c.Livery)) throw Fail(p + ".config.Livery", "does not exactly match a source livery");
        if (c.Bogies.Count == 0 && c.EngineUnits.Count == 0) throw Fail(p, "requires a measured bogie or engine layout");
        if (c.CollisionBoxes == null) throw Fail(p + ".hooks.CollisionBoxes", "required measured collision layout");
        if (!c.IsTender && c.SimSpec == null) throw Fail(p + ".hooks.SimSpec", "required explicit simulation specification");
        if (c.OilAnchors != null && c.RodOilers != null) throw Fail(p, "select OilAnchors OR RodOilers");
        if (c.Tender != null && c.IsTender) throw Fail(p, "nested tenders are unsupported");
    }

    // Metadata may wrap a single number, a vector, or a collection whose values share provenance.
    // A null remains unknown; Read rejects it for nonnullable numeric fields instead of making zero.
    static void CheckEvidence(object node, string path, bool covered)
    {
        var map = node as Dictionary<string, object>;
        if (IsEnvelope(map))
        {
            Only(map, path, "value", "unit", "basis", "evidence", "notes");
            object unit, basis, evidence;
            if (!map.TryGetValue("unit", out unit) || !(unit is string) || string.IsNullOrWhiteSpace((string)unit)) throw Fail(path, "unit is required");
            if (!map.TryGetValue("basis", out basis) || !(basis is string) || !Bases.Contains((string)basis)) throw Fail(path, "invalid or missing basis");
            if (!map.TryGetValue("evidence", out evidence) || !Evidence(evidence)) throw Fail(path, "nonempty evidence string or string array is required");
            CheckEvidence(map["value"], path + ".value", true);
        }
        else if (map != null) { foreach (var kv in map) CheckEvidence(kv.Value, path + "." + kv.Key, covered); }
        else if (node is List<object>) { var a = (List<object>)node; for (int i = 0; i < a.Count; i++) CheckEvidence(a[i], path + "[" + i + "]", covered); }
        else if (node is long || node is double) { if (!covered) throw Fail(path, "numeric setting requires value/unit/basis/evidence"); }
    }
    static bool Evidence(object e) { return e is string ? !string.IsNullOrWhiteSpace((string)e) : e is List<object> && ((List<object>)e).Count > 0 && ((List<object>)e).All(x => x is string && !string.IsNullOrWhiteSpace((string)x)); }
    static bool IsEnvelope(Dictionary<string, object> m) { return m != null && m.ContainsKey("value") && (m.ContainsKey("unit") || m.ContainsKey("basis") || m.ContainsKey("evidence")); }
    static object Unwrap(object n)
    {
        var m = n as Dictionary<string, object>;
        if (IsEnvelope(m)) return Unwrap(m["value"]);
        if (m != null) return m.ToDictionary(k => k.Key, k => Unwrap(k.Value));
        var a = n as List<object>; return a != null ? a.Select(Unwrap).ToList() : n;
    }

    static object Read(object n, Type t, string p)
    {
        Type nullable = Nullable.GetUnderlyingType(t);
        if (n == null)
        {
            if (t.IsValueType && nullable == null) throw Fail(p, "unknown/null cannot populate " + t.Name);
            return null;
        }
        if (nullable != null) return Read(n, nullable, p);
        if (typeof(Delegate).IsAssignableFrom(t)) throw Fail(p, "delegate fields require a supported declarative hook");
        if (t == typeof(object))
        {
            if (n is long) return checked((int)(long)n);
            if (n is double) return FiniteFloat(n, p);
            if (n is List<object>) return ((List<object>)n).Select((v, i) => Read(v, typeof(object), p + "[" + i + "]")).ToList();
            if (n is Dictionary<string, object>) return ((Dictionary<string, object>)n).ToDictionary(k => k.Key, k => Read(k.Value, typeof(object), p + "." + k.Key));
            return n;
        }
        if (t == typeof(string)) { if (!(n is string)) throw Fail(p, "expected string"); return n; }
        if (t == typeof(bool)) { if (!(n is bool)) throw Fail(p, "expected boolean"); return n; }
        if (t == typeof(float)) return FiniteFloat(n, p);
        if (t == typeof(double)) { Number(n, p); return Convert.ToDouble(n, Inv); }
        if (t == typeof(int)) { Number(n, p); double d = Convert.ToDouble(n, Inv); if (d != Math.Truncate(d)) throw Fail(p, "expected whole number"); return checked((int)d); }
        if (t.IsEnum) return n is string ? Enum.Parse(t, (string)n, false) : Enum.ToObject(t, (int)Read(n, typeof(int), p));
        if (t == typeof(Vector2) || t == typeof(Vector3) || t == typeof(Quaternion) || t == typeof(Color))
        {
            string[] names = t == typeof(Color) ? new[] { "r", "g", "b", "a" } : t == typeof(Vector2) ? new[] { "x", "y" } : t == typeof(Vector3) ? new[] { "x", "y", "z" } : new[] { "x", "y", "z", "w" };
            var values = n as List<object>;
            if (values == null) { var map = Obj(n, p); Only(map, p, names); values = names.Select(k => { if (!map.ContainsKey(k)) throw Fail(p, "missing " + k); return map[k]; }).ToList(); }
            if (values.Count != names.Length) throw Fail(p, "expected " + names.Length + " coordinates");
            return Activator.CreateInstance(t, values.Select((v, i) => (object)FiniteFloat(v, p + "." + names[i])).ToArray());
        }
        if (t.IsArray)
        {
            var list = Arr(n, p); Type et = t.GetElementType(); Array a = Array.CreateInstance(et, list.Count);
            for (int i = 0; i < list.Count; i++) a.SetValue(Read(list[i], et, p + "[" + i + "]"), i); return a;
        }
        if (t.IsGenericType && t.GetGenericTypeDefinition() == typeof(List<>))
        {
            var result = (IList)Activator.CreateInstance(t); var list = Arr(n, p); Type et = t.GetGenericArguments()[0];
            for (int i = 0; i < list.Count; i++) result.Add(Read(list[i], et, p + "[" + i + "]")); return result;
        }
        if (t.IsGenericType && t.GetGenericTypeDefinition() == typeof(Dictionary<,>))
        {
            var args = t.GetGenericArguments(); if (args[0] != typeof(string)) throw Fail(p, "dictionary keys must be strings");
            var result = (IDictionary)Activator.CreateInstance(t);
            foreach (var kv in Obj(n, p)) result.Add(kv.Key, Read(kv.Value, args[1], p + "." + kv.Key)); return result;
        }
        if (t.IsGenericType && t.FullName.StartsWith("System.ValueTuple`", StringComparison.Ordinal))
        {
            Type[] args = t.GetGenericArguments(); var values = n as List<object>;
            if (values == null) { var m = Obj(n, p); var keys = Enumerable.Range(1, args.Length).Select(i => "Item" + i).ToArray(); Only(m, p, keys); values = keys.Select(k => { if (!m.ContainsKey(k)) throw Fail(p, "missing " + k); return m[k]; }).ToList(); }
            if (values.Count != args.Length) throw Fail(p, "wrong tuple length");
            return Activator.CreateInstance(t, values.Select((v, i) => Read(v, args[i], p + ".Item" + (i + 1))).ToArray());
        }
        object instance = t == typeof(Shot) ? (object)new Shot(35, Vector3.zero, Vector3.zero, null) : Activator.CreateInstance(t);
        foreach (var kv in Obj(n, p))
        {
            FieldInfo f = t.GetField(kv.Key, BindingFlags.Public | BindingFlags.Instance);
            if (f == null || f.IsInitOnly) throw Fail(p + "." + kv.Key, "unknown or readonly " + t.Name + " field");
            f.SetValue(instance, Read(kv.Value, f.FieldType, p + "." + kv.Key));
        }
        return instance;
    }

    public class Pose { public Vector3 pos, euler; }
    public class Box { public Vector3 centre, size; }
    public class LeverPhysics
    {
        public string path; public float min, spring, damper, mass, drag, angularDrag, scroll, scrollSpring;
        public int notches; public float? scrollAngleFraction;
    }
    static void ApplyHooks(LocoConfig c, Dictionary<string, object> h, string p)
    {
        Only(h, p, "SimSpec", "CollisionBoxes", "OilPoints", "BrakeRelease", "HandbrakeWheel", "CoalPile", "LampKey", "LeverPhysics");
        foreach (var kv in h)
        {
            string at = p + "." + kv.Key;
            switch (kv.Key)
            {
                case "SimSpec": { var v = (Dictionary<string, Dictionary<string, object>>)Read(kv.Value, typeof(Dictionary<string, Dictionary<string, object>>), at); c.SimSpec = b => v; break; }
                case "CollisionBoxes": { var v = (List<(string, Vector3, Vector3)>)Read(kv.Value, typeof(List<(string, Vector3, Vector3)>), at); c.CollisionBoxes = b => v; break; }
                case "OilPoints": { var v = (List<(string, Vector3)>)Read(kv.Value, typeof(List<(string, Vector3)>), at); c.OilPoints = b => v; break; }
                case "BrakeRelease": { var v = (Pose)Read(kv.Value, typeof(Pose), at); c.BrakeRelease = b => (v.pos, v.euler); break; }
                case "HandbrakeWheel": { var v = (Pose)Read(kv.Value, typeof(Pose), at); c.HandbrakeWheel = b => (v.pos, v.euler); break; }
                case "CoalPile": { var v = (Box)Read(kv.Value, typeof(Box), at); c.CoalPile = b => (v.centre, v.size); break; }
                case "LampKey":
                {
                    var v = (Dictionary<string, string>)Read(kv.Value, typeof(Dictionary<string, string>), at);
                    c.LampKey = (t, b) => { string key; return v.TryGetValue(t.name, out key) ? key : v.TryGetValue(TransformPath(t), out key) ? key : null; }; break;
                }
                case "LeverPhysics":
                {
                    var v = (List<LeverPhysics>)Read(kv.Value, typeof(List<LeverPhysics>), at);
                    var seen = new HashSet<string>();
                    foreach (var phys in v)
                    {
                        var matches = c.RrLevers.Where(l => l.Path == phys.path).ToArray();
                        if (matches.Length != 1 || !seen.Add(phys.path)) throw Fail(at, "physics path must select exactly one lever once: " + phys.path);
                        if (phys.mass <= 0 || phys.notches < 0) throw Fail(at, "positive mass/nonnegative notch count required");
                        matches[0].Phys = (s, angle) => CclLocoBuild.Phys(s, phys.min, angle, phys.notches, phys.spring, phys.damper, phys.mass, phys.drag, phys.angularDrag, phys.scrollAngleFraction.HasValue ? angle * phys.scrollAngleFraction.Value : phys.scroll, phys.scrollSpring);
                    }
                    break;
                }
            }
        }
    }
    static string TransformPath(Transform t) { return t.parent == null ? t.name : TransformPath(t.parent) + "/" + t.name; }
    static float FiniteFloat(object n, string p) { Number(n, p); float f = Convert.ToSingle(n, Inv); if (float.IsNaN(f) || float.IsInfinity(f)) throw Fail(p, "must be finite"); return f; }
    static void Number(object n, string p) { if (!(n is long) && !(n is double)) throw Fail(p, "expected number"); }
    static Dictionary<string, object> Obj(object n, string p) { var v = n as Dictionary<string, object>; if (v == null) throw Fail(p, "expected object"); return v; }
    static List<object> Arr(object n, string p) { var v = n as List<object>; if (v == null) throw Fail(p, "expected array"); return v; }
    static void Only(Dictionary<string, object> m, string p, params string[] allowed) { foreach (string k in m.Keys) if (!allowed.Contains(k)) throw Fail(p + "." + k, "unknown field"); }
    static InvalidDataException Fail(string p, string why) { return new InvalidDataException(p + ": " + why); }

    // Small strict JSON parser: preserves null/missing, rejects duplicate keys and nonfinite values.
    // No package dependency, expression evaluator, reflection type names, or arbitrary method hooks.
    sealed class Json
    {
        readonly string s; int i;
        Json(string text) { s = text; }
        public static object Parse(string text) { var p = new Json(text); object n = p.Value(); p.White(); if (p.i != text.Length) throw p.Error("trailing content"); return n; }
        Exception Error(string message) { return Fail("JSON offset " + i, message); }
        void White() { while (i < s.Length && (s[i] == ' ' || s[i] == '\t' || s[i] == '\r' || s[i] == '\n' || (i == 0 && s[i] == '\uFEFF'))) i++; }
        bool Take(char c) { White(); if (i < s.Length && s[i] == c) { i++; return true; } return false; }
        void Need(char c) { if (!Take(c)) throw Error("expected '" + c + "'"); }
        object Value()
        {
            White(); if (i >= s.Length) throw Error("unexpected end"); char c = s[i];
            if (c == '"') return String();
            if (c == '{')
            {
                i++; var m = new Dictionary<string, object>(); if (Take('}')) return m;
                do { White(); string k = String(); Need(':'); if (m.ContainsKey(k)) throw Error("duplicate key " + k); m.Add(k, Value()); } while (Take(','));
                Need('}'); return m;
            }
            if (c == '[') { i++; var a = new List<object>(); if (Take(']')) return a; do { a.Add(Value()); } while (Take(',')); Need(']'); return a; }
            foreach (string literal in new[] { "true", "false", "null" })
                if (i + literal.Length <= s.Length && string.CompareOrdinal(s, i, literal, 0, literal.Length) == 0) { i += literal.Length; return literal == "null" ? null : (object)(literal == "true"); }
            int start = i; if (s[i] == '-') i++;
            if (i >= s.Length) throw Error("incomplete number");
            if (s[i] == '0') i++; else { if (s[i] < '1' || s[i] > '9') throw Error("expected value"); while (i < s.Length && s[i] >= '0' && s[i] <= '9') i++; }
            bool real = false;
            if (i < s.Length && s[i] == '.') { real = true; i++; int first = i; while (i < s.Length && s[i] >= '0' && s[i] <= '9') i++; if (i == first) throw Error("missing fraction digits"); }
            if (i < s.Length && (s[i] == 'e' || s[i] == 'E')) { real = true; i++; if (i < s.Length && (s[i] == '+' || s[i] == '-')) i++; int first = i; while (i < s.Length && s[i] >= '0' && s[i] <= '9') i++; if (i == first) throw Error("missing exponent digits"); }
            string token = s.Substring(start, i - start);
            if (!real) { long l; if (long.TryParse(token, NumberStyles.Integer, Inv, out l)) return l; throw Error("integer overflow"); }
            double d; if (!double.TryParse(token, NumberStyles.Float, Inv, out d) || double.IsNaN(d) || double.IsInfinity(d)) throw Error("invalid/nonfinite number"); return d;
        }
        string String()
        {
            if (i >= s.Length || s[i++] != '"') throw Error("expected string"); var b = new StringBuilder();
            while (i < s.Length)
            {
                char c = s[i++]; if (c == '"') return b.ToString(); if (c < 32) throw Error("unescaped control character");
                if (c != '\\') { b.Append(c); continue; } if (i >= s.Length) throw Error("incomplete escape");
                c = s[i++]; switch (c)
                {
                    case '"': case '\\': case '/': b.Append(c); break;
                    case 'b': b.Append('\b'); break; case 'f': b.Append('\f'); break; case 'n': b.Append('\n'); break; case 'r': b.Append('\r'); break; case 't': b.Append('\t'); break;
                    case 'u': int v; if (i + 4 > s.Length || !int.TryParse(s.Substring(i, 4), NumberStyles.HexNumber, Inv, out v)) throw Error("invalid unicode escape"); b.Append((char)v); i += 4; break;
                    default: throw Error("invalid escape");
                }
            }
            throw Error("unterminated string");
        }
    }
}
