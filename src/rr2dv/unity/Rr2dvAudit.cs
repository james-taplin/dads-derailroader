using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

// rr2dv audit stage (Unity 2019.4, editor only): read-only checks of the pack the build stage exported, in the same
// project. Input Assets/Rr2dv/AuditInput.json (rr2dv's audit.py), output audit.json + result.json in RR2DV_AUDIT_OUT.
// Q05 in our guide audits the bundle itself; here Unity's own loader reads it (no third-party parser):
//  - no AudioClip anywhere: in the bundle, or among the built car assets' dependencies (James, W5: no Railroader audio);
//  - behaviours only from CCL.Types, none missing;
//  - the HUD/keyboard controls and indicators the LocoControlsReader/LocoIndicatorReader need, the driving controls'
//    port feeders, unique simulation IDs, one cab teleport, and the car types' mass and wheel radius as recorded.
// Passing is not acceptance: runtime checks (CTRL-01/CTRL-02) stay pending.
public static class Rr2dvAudit
{
    [Serializable] public class Car { public string id; public float mass, wheelRadius; public bool locomotive; public int drivenAxles; }
    [Serializable] public class Review { public string trainBrake, physics; public int[] spawnTracks; }
    [Serializable] public class EngineMetric { public string component, field; public float value; }
    [Serializable] public class CataloguePage { public string sourceId, carId, assetName, consist; }
    [Serializable] public class CatalogueTerm { public string Term; }
    [Serializable] public class CatalogueTerms { public CatalogueTerm[] terms; }
    [Serializable] public class Input { public int schema, openingCount; public string[] bundles; public string[] carFolders; public Car[] cars; public string[] controls, ports, indicators; public Review review; public EngineMetric[] engineMetrics; public CataloguePage[] cataloguePages; public string[] catalogueTermKeys; }
    [Serializable] public class Output
    {
        public int schema = 1; public string status; public string[] errors, warnings, bundleAssets, scriptAssemblies, dependencies;
        public int audioClips; public string[] audioClipNames; public string[] portFeeders;
        public int oilCupCount;
        public string[] coalLoadMeshes;
        public string[] cataloguePages, catalogueLiveries;
    }
    [Serializable] public class Result { public string status; public int errors, warnings; public bool runtimeValidated; public string error; }

    const string InputAsset = "Assets/Rr2dv/AuditInput.json";

    public static void Run()
    {
        string output = Environment.GetEnvironmentVariable("RR2DV_AUDIT_OUT");
        var errors = new List<string>();
        var warnings = new List<string>();
        var result = new Result { status = "failed" };
        int exit = 1;
        var loaded = new List<AssetBundle>();
        try
        {
            if (string.IsNullOrEmpty(output)) throw new InvalidOperationException("RR2DV_AUDIT_OUT is required");
            Directory.CreateDirectory(output);
            var project = Directory.GetParent(Application.dataPath).FullName;
            var input = JsonUtility.FromJson<Input>(File.ReadAllText(Path.Combine(project, InputAsset)));
            if (input == null || input.schema != 1) throw new InvalidDataException("unsupported audit input");
            var outp = new Output();

            // built car assets and everything they depend on: what the export packed
            var assets = (input.carFolders ?? new string[0]).Where(AssetDatabase.IsValidFolder)
                .SelectMany(f => AssetDatabase.FindAssets("", new[] { f })).Select(AssetDatabase.GUIDToAssetPath).Distinct().ToArray();
            if (assets.Length == 0) errors.Add("no built car assets found in " + string.Join(", ", input.carFolders ?? new string[0]));
            var deps = AssetDatabase.GetDependencies(assets, true).Distinct().OrderBy(p => p, StringComparer.Ordinal).ToArray();
            foreach (var d in deps)
            {
                if (AssetDatabase.GetMainAssetTypeAtPath(d) == typeof(AudioClip)) errors.Add("audio in the built car's dependencies: " + d);
                string ext = Path.GetExtension(d).ToLowerInvariant();
                if ((ext == ".cs" || ext == ".dll") && Path.GetFileName(d) != "CCL.Types.dll") errors.Add("script outside CCL.Types in the built car's dependencies: " + d);
            }
            outp.dependencies = deps;

            // the exported bundle(s), read by Unity's own loader
            var names = new List<string>();
            var scripts = new SortedSet<string>(StringComparer.Ordinal);
            var clips = new List<string>();
            var feeders = new SortedSet<string>(StringComparer.Ordinal);
            var objects = new List<Object>();
            foreach (var path in input.bundles ?? new string[0])
            {
                var b = AssetBundle.LoadFromFile(path);
                if (!b) { errors.Add("the exported bundle could not be loaded: " + path); continue; }
                loaded.Add(b);
                names.AddRange(b.GetAllAssetNames());
                objects.AddRange(b.LoadAllAssets());
            }
            if ((input.bundles ?? new string[0]).Length == 0) errors.Add("no exported bundle to audit");
            var all = CollectObjects(objects, errors);
            foreach (var o in all)
            {
                if (o is AudioClip) clips.Add(o.name);
                if (o is AudioSource && ((AudioSource)o).clip) clips.Add(((AudioSource)o).clip.name);
                if (o is MonoBehaviour || o is ScriptableObject)
                {
                    var asm = o.GetType().Assembly.GetName().Name;
                    scripts.Add(asm);
                    if (asm != "CCL.Types") errors.Add("behaviour outside CCL.Types in the bundle: " + o.GetType().FullName + " (" + asm + ")");
                }
                if (o.GetType().Name == "InteractablePortFeederProxy") feeders.Add(Str(o, "portId"));
            }
            outp.audioClips = clips.Count;
            outp.audioClipNames = clips.ToArray();
            if (clips.Count > 0) errors.Add(clips.Count + " AudioClip(s) in the bundle: " + string.Join(", ", clips.Take(10)));
            outp.bundleAssets = names.OrderBy(n => n, StringComparer.Ordinal).ToArray();
            outp.scriptAssemblies = scripts.ToArray();
            outp.portFeeders = feeders.ToArray();
            CheckCatalogue(input, all, outp, errors);

            Func<string, string, Object> One = (type, what) =>
            {
                var hits = all.Where(o => o.GetType().Name == type).ToList();
                if (hits.Count != 1) { errors.Add("expected one " + type + " (" + what + "), found " + hits.Count); return null; }
                return hits[0];
            };
            var controls = One("LocoControlsReaderProxy", "HUD and keyboard controls");
            foreach (var metric in input.engineMetrics ?? new EngineMetric[0])
            {
                var targets = all.Where(o => Str(o, "ID") == metric.component).ToArray();
                // ApplySpec can set a controller beside the definition on the same sim object
                // (e.g. firebox.coalConsumptionMultiplier lives on FireboxSimControllerProxy).
                var owner = targets.Length == 1 ? targets[0] as Component : null;
                var fields = owner ? owner.GetComponents<Component>().Where(c => c is MonoBehaviour)
                    .Select(c => new SerializedObject(c).FindProperty(metric.field)).Where(p => p != null).ToArray() : new SerializedProperty[0];
                var field = fields.Length == 1 ? fields[0] : null;
                if (field == null) { errors.Add("Reviewed engine field missing: " + metric.component + "." + metric.field); continue; }
                float actual = field.propertyType == SerializedPropertyType.Integer ? field.intValue : field.floatValue;
                if (float.IsNaN(actual) || float.IsInfinity(actual) || Mathf.Abs(actual - metric.value) > Mathf.Max(.0001f, Mathf.Abs(metric.value) * .00001f))
                    errors.Add("Reviewed engine field differs in bundle: " + metric.component + "." + metric.field + " expected " + metric.value + ", got " + actual);
            }
            if (controls) foreach (var f in input.controls ?? new string[0]) if (!Ref(controls, f)) errors.Add("no control for the HUD's " + f);
            var indicators = One("LocoIndicatorReaderProxy", "HUD readings");
            if (indicators && !Ref(indicators, "speed")) errors.Add("Numerical speed HUD has no speed indicator");
            var speedIndicator = indicators ? new SerializedObject(indicators).FindProperty("speed")?.objectReferenceValue as Component : null;
            var speedPort = speedIndicator ? speedIndicator.GetComponents<Component>().FirstOrDefault(c => c && c.GetType().Name == "IndicatorPortReaderProxy") : null;
            if (!speedPort || Str(speedPort, "portId") != "traction.WHEEL_SPEED_KMH_EXT_IN" ||
                !new SerializedObject(speedPort).FindProperty("useAbsoluteValue").boolValue)
                errors.Add("Numerical speed HUD must read absolute km/h from its own traction port reader");
            var speedHud = all.FirstOrDefault(o => o.GetType().Name == "VanillaHUDLayout");
            if (!speedHud) errors.Add("Locomotive has no HUD layout");
            else
            {
                speedHud.GetType().GetMethod("AfterImport")?.Invoke(speedHud, null);
                var layout = new SerializedObject(speedHud); int basis = layout.FindProperty("HUDType").intValue;
                if (basis != 20 && (basis != 1000 || layout.FindProperty("CustomHUDSettings.BasicControls.Speedometer").intValue != 1))
                    errors.Add("Locomotive HUD must use the S282 speed box or enable the numerical speed slot in its custom layout");
            }
            if (indicators) foreach (var f in input.indicators ?? new string[0]) if (!Ref(indicators, f)) warnings.Add("the HUD has no reading for " + f + " (no instrument for it in the model)");
            foreach (var p in input.ports ?? new string[0]) if (!feeders.Contains(p)) errors.Add("no control feeds " + p);
            One("CabTeleportDestinationProxy", "cab teleport");
            var openings = all.OfType<Component>().Where(c => c.name.StartsWith("C_rr2dvOpening", StringComparison.Ordinal) &&
                (c.GetType().Name == "LeverProxy" || c.GetType().Name == "PullerProxy" || c.GetType().Name == "ButtonProxy")).ToArray();
            if (openings.Length != input.openingCount) errors.Add("Expected " + input.openingCount + " ancillary controls, exported " + openings.Length);
            foreach (var control in openings)
            {
                string id = control.name.Substring(2);
                if (!feeders.Contains(id + ".EXT_IN")) errors.Add("Opening has no saved control feeder: " + control.name);
                if (!all.Any(o => o.GetType().Name == "ExternalControlDefinitionProxy" && Str(o, "ID") == id && new SerializedObject(o).FindProperty("saveState").boolValue))
                    errors.Add("Opening has no persistent simulation control: " + control.name);
                if (control.GetType().Name == "ButtonProxy")
                {
                    if (!all.Any(o => o.GetType().Name == "SmoothedOutputDefinitionProxy" && Str(o, "ID") == id + "Motion" && new SerializedObject(o).FindProperty("smoothTime").floatValue > 0))
                        errors.Add("Click opening has no native animated transition: " + control.name);
                    if (!all.Any(o => o.GetType().Name == "AnimatorPortReaderProxy" && Str(o, "portId") == id + "Motion.OUTPUT"))
                        errors.Add("Click opening animation is not connected to its transition: " + control.name);
                }
                var highlight = control.GetComponents<Component>().FirstOrDefault(c => c && c.GetType().Name == "HighlightTagProxy");
                var renderers = highlight ? new SerializedObject(highlight).FindProperty("renderers") : null;
                if (renderers == null || renderers.arraySize == 0) { errors.Add("Opening has no explicit highlight: " + control.name); continue; }
                var root = control.transform;
                while (root.parent) root = root.parent;
                for (int i = 0; i < renderers.arraySize; i++)
                {
                    var renderer = renderers.GetArrayElementAtIndex(i).objectReferenceValue as Renderer;
                    if (!renderer || !renderer.transform.IsChildOf(root)) errors.Add("Opening highlight is missing or outside its prefab: " + control.name);
                }
            }

            // what the exported tender coal load draws (RLW RXM-1B, 2026-09-29: a box in game though the build made a heap)
            var coalMeshes = new List<string>();
            foreach (var mf in all.OfType<MeshFilter>())
                for (var t = mf.transform; t; t = t.parent)
                    if (t.name == "[coal load]") { coalMeshes.Add(mf.name + ": " + (mf.sharedMesh ? mf.sharedMesh.name : "(no mesh)")); break; }
            outp.coalLoadMeshes = coalMeshes.ToArray();
            if (coalMeshes.Any(m => m.EndsWith(": unit_box_bottom_pivot", StringComparison.Ordinal)))
                warnings.Add("the tender coal load is drawn as the builder's plain box, not a measured heap: " + string.Join(", ", coalMeshes));

            var oilCups = all.Where(o => o.GetType().Name == "ManualOilingPoint").ToArray();
            var oilProviders = all.Where(o => o.GetType().Name == "PositionSyncProviderProxy").ToArray();
            var cupTags = oilCups.Select(o => Str(o, "SyncTag")).ToArray();
            var providerTags = oilProviders.Select(o => Str(o, "syncTag")).ToArray();
            outp.oilCupCount = oilCups.Length;
            int drivenAxles=(input.cars??new Car[0]).Where(c=>c.locomotive).Sum(c=>c.drivenAxles);
            if(drivenAxles>0) {
                if(oilCups.Length<Math.Max(6,drivenAxles*2) || oilCups.Length>12 || oilCups.Length%2!=0)
                    errors.Add("oil cups must cover every driven axle and total six to twelve in complete pairs");
                for(int i=1;i<=drivenAxles;i++)foreach(string side in new[]{"L","R"})
                    if(!cupTags.Contains("oil_"+i+side))errors.Add("missing driven-axle oil cup oil_"+i+side);
                foreach(var provider in oilProviders.OfType<Component>()) {
                    // AssetBundle prefab roots are inactive; GetComponentInParent's default lookup skips them.
                    bool animated=false;
                    for(var parent=provider.transform.parent;parent;parent=parent.parent)
                        if(parent.GetComponent<Animator>()) {animated=true;break;}
                    if(!provider.transform.parent || !provider.transform.parent.GetComponent<MeshFilter>() || !animated)
                        errors.Add("oil provider is not parented to animated running-gear geometry: "+provider.name);
                }
            }
            if (cupTags.Any(string.IsNullOrEmpty) || cupTags.Distinct().Count() != cupTags.Length ||
                !cupTags.OrderBy(t => t, StringComparer.Ordinal).SequenceEqual(providerTags.OrderBy(t => t, StringComparer.Ordinal)))
                errors.Add("oil-cup and moving-provider tags do not match the placed layout");
            var oilDefinition = One("ManualOilingPointsDefinitionProxy", "placed oil-cup count");
            if (oilDefinition != null)
            {
                var so = new SerializedObject(oilDefinition);
                var count = so.FindProperty("OilingPointCount");
                var perRev = so.FindProperty("consumptionPerRev");
                // the no-manual-oiling failsafe (Rr2dvPlacement): one internal point that never drains, no cup
                bool noManualOiling = oilCups.Length == 0 && count != null && count.intValue == 1 && perRev != null && perRev.floatValue == 0f;
                if (noManualOiling) warnings.Add("no manual oiling: no accessible seat at any driving axle, so the oiling system never drains (failsafe)");
                else if (count == null || count.intValue != oilCups.Length)
                    errors.Add("oil simulation count differs from the placed cups");
            }
            if (oilCups.Length == 0 && oilDefinition == null) warnings.Add("no accessible manual oil-cup pair was placed");

            // BR-01 (board X41): the stock brake-release fitting stands upright with its red handle pointing outward: in the
            // car's space its +z (handle) points to the side it is on and its +y (hanger) points up. Never rolled over.
            foreach (var go in all.OfType<GameObject>().Where(g => !g.transform.parent))
                foreach (var t in go.GetComponentsInChildren<Transform>(true).Where(x => x.name == "[brake release]"))
                {
                    var q = Quaternion.Inverse(go.transform.rotation) * t.rotation;
                    var local = go.transform.InverseTransformPoint(t.position);
                    Vector3 handle = q * Vector3.forward, hanger = q * Vector3.up;
                    // the side is where the handle end is (the rod runs 1.07 m along +z): on a narrow frame the valve end
                    // can sit just past the centreline while the handle is outboard (DM&IR M-3: valve x -0.23, handle
                    // 0.63..0.84, 2026-09-29), and judging by the valve end called a correct fitting reversed
                    float side = (local + handle * 1.067645f).x < 0 ? -1f : 1f;
                    if (handle.x * side < 0.999f || hanger.y < 0.999f)
                        errors.Add("BR-01: brake release in " + go.name + " is not upright with its handle outward (handle " + handle + ", hanger " + hanger + ")");
                }

            foreach (var sim in all.Where(o => o.GetType().Name == "SimConnectionsDefinitionProxy"))
            {
                var order = new SerializedObject(sim).FindProperty("executionOrder");
                var ids = new List<string>();
                for (int i = 0; order != null && i < order.arraySize; i++)
                {
                    var entry = order.GetArrayElementAtIndex(i).objectReferenceValue;
                    if (!entry) { errors.Add("empty simulation entry"); continue; }
                    ids.Add(Str(entry, "ID"));
                }
                var dup = ids.GroupBy(i => i).Where(g => g.Count() > 1).Select(g => g.Key).ToArray();
                if (dup.Length > 0) errors.Add("duplicate simulation IDs: " + string.Join(", ", dup));
            }
            var types = all.Where(o => o.GetType().Name == "CustomCarType").ToList();
            foreach (var car in input.cars ?? new Car[0])
            {
                var t = types.FirstOrDefault(o => Str(o, "id") == car.id);
                if (!t) { errors.Add("car type " + car.id + " not in the bundle"); continue; }
                var so = new SerializedObject(t);
                float mass = so.FindProperty("mass").floatValue, radius = so.FindProperty("wheelRadius").floatValue;
                if (Mathf.Abs(mass - car.mass) > 0.5f) errors.Add(car.id + " mass " + mass + " kg, record " + car.mass);
                if (Mathf.Abs(radius - car.wheelRadius) > 0.0005f) errors.Add(car.id + " wheel radius " + radius + " m, record " + car.wheelRadius);
                if (car.locomotive && input.review != null)
                {
                    int brake = input.review.trainBrake == "self-lapping" ? 1 : 2;
                    if (so.FindProperty("brakes.brakeValveType").intValue != brake) errors.Add("Actual brake valve differs from reviewed choice");
                    var variant = all.FirstOrDefault(o => o.GetType().Name == "CustomCarVariant" && new SerializedObject(o).FindProperty("parentType").objectReferenceValue == t);
                    if (!variant) errors.Add("No locomotive variant for reviewed spawning");
                    else
                    {
                        var groups = new SerializedObject(variant).FindProperty("LocoSpawnGroups");
                        var actual = Enumerable.Range(0, groups.arraySize).Select(i => groups.GetArrayElementAtIndex(i).FindPropertyRelative("Track").intValue).OrderBy(i => i).ToArray();
                        if (!actual.SequenceEqual((input.review.spawnTracks ?? new int[0]).OrderBy(i => i))) errors.Add("Exported spawn pool differs from review");
                    }
                    var hud = all.FirstOrDefault(o => o.GetType().Name == "VanillaHUDLayout");
                    if (hud)
                    {
                        if (string.IsNullOrEmpty(Str(hud, "_json"))) errors.Add("Custom HUD has no serialized runtime layout");
                        hud.GetType().GetMethod("AfterImport")?.Invoke(hud, null);
                        var imported = new SerializedObject(hud);
                        foreach (var binding in new[] { new[] { "CabLightStyle", "cabLight" }, new[] { "Headlights1", "headlightsFront" } })
                            if (controls && (imported.FindProperty("CustomHUDSettings.Cab." + binding[0]).intValue != 0) != (bool)Ref(controls, binding[1]))
                                errors.Add("HUD lighting slot differs from its control wiring: " + binding[0]);
                        // slot 22 lower half: rear headlights when wired, else the bell slider (Slot24B 3) when a bell is wired
                        int rearSlot = imported.FindProperty("CustomHUDSettings.Cab.Headlights2").intValue;
                        if (controls && (rearSlot == 3 ? !(bool)Ref(controls, "bell") || (bool)Ref(controls, "headlightsRear")
                                                       : (rearSlot != 0) != (bool)Ref(controls, "headlightsRear")))
                            errors.Add("HUD lighting slot differs from its control wiring: Headlights2");
                        if (imported.FindProperty("HUDType").intValue != 1000 || Str(hud, "CustomHUDSettings.Powertrain") != "S" ||
                            imported.FindProperty("CustomHUDSettings.BasicControls.Speedometer").intValue != 1 ||
                            imported.FindProperty("CustomHUDSettings.BasicControls.Throttle").intValue == 0 ||
                            imported.FindProperty("CustomHUDSettings.BasicControls.Reverser").intValue == 0 ||
                            imported.FindProperty("CustomHUDSettings.Cab.HornStyle").intValue != 2)
                            errors.Add("Imported HUD is missing its steam driving layout or numerical speedometer");
                    }
                    if (!hud || new SerializedObject(hud).FindProperty("CustomHUDSettings.Braking.BrakeType").intValue != brake) errors.Add("HUD brake behaviour differs from reviewed valve");
                }
            }
            if (types.Count != (input.cars ?? new Car[0]).Length) errors.Add("expected " + (input.cars ?? new Car[0]).Length + " car type(s), found " + types.Count);

            outp.errors = errors.ToArray();
            outp.warnings = warnings.ToArray();
            outp.status = errors.Count == 0 ? "passed" : "failed";
            File.WriteAllText(Path.Combine(output, "audit.json"), JsonUtility.ToJson(outp, true));
            result = new Result { status = outp.status, errors = errors.Count, warnings = warnings.Count };
            exit = errors.Count == 0 ? 0 : 2;
        }
        catch (Exception e)
        {
            Debug.LogException(e);
            result = new Result { status = "failed", errors = errors.Count + 1, warnings = warnings.Count, error = e.ToString() };
            exit = 1;
        }
        finally
        {
            foreach (var b in loaded) if (b) b.Unload(true);
            if (!string.IsNullOrEmpty(output) && Directory.Exists(output))
                File.WriteAllText(Path.Combine(output, "result.json"), JsonUtility.ToJson(result, true));
            EditorApplication.Exit(exit);
        }
    }

    static List<Object> CollectObjects(IEnumerable<Object> objects, List<string> errors)
    {
        // CCL exports the pack as its sole named asset; cars/prefabs are referenced dependencies,
        // not separate LoadAllAssets entries. Follow the serialized graph, deduplicating cycles.
        var all = new List<Object>();
        var seen = new HashSet<Object>();
        var pending = new Queue<Object>(objects);
        while (pending.Count > 0)
        {
            var o = pending.Dequeue();
            if (!o || !seen.Add(o)) continue;
            all.Add(o);
            var go = o as GameObject;
            if (go) foreach (var c in go.GetComponentsInChildren<Component>(true))
            {
                if (c == null) { errors.Add("missing behaviour script in " + go.name); continue; }
                pending.Enqueue(c);
            }
            // Mesh/texture buffers are leaves for these checks; avoid walking their large numeric arrays.
            if (o is GameObject || o is Component || o is ScriptableObject || o is AnimationClip || o is Material)
            {
                var property = new SerializedObject(o).GetIterator();
                while (property.Next(true))
                    if (property.propertyType == SerializedPropertyType.ObjectReference && property.objectReferenceValue)
                        pending.Enqueue(property.objectReferenceValue);
            }
        }
        return all;
    }

    // Read the exported reference graph, not the authoring library. Every livery
    // must reference its own car's page; unrelated page/text keys cannot ship.
    public static void CheckCatalogue(Input input, List<Object> all, Output output, List<string> errors)
    {
        if (input.cataloguePages == null) return; // older/synthetic builds
        var expected = input.cataloguePages;
        var pages = all.Where(o => o.GetType().Name == "CatalogPage").ToArray();
        output.cataloguePages = pages.Select(p => p.name).OrderBy(n => n, StringComparer.Ordinal).ToArray();
        if (pages.Length != expected.Length || !new HashSet<string>(pages.Select(p => p.name)).SetEquals(expected.Select(p => p.assetName)))
            errors.Add("catalogue: exported pages differ from the selected engine/tender pages");
        var liveries = new List<string>();
        foreach (var selected in expected)
        {
            var matches = pages.Where(p => p.name == selected.assetName).ToArray();
            if (matches.Length != 1) { errors.Add("catalogue: expected one page " + selected.assetName); continue; }
            var page = matches[0];
            if (!Ref(page, "DiagramLayout") || Str(page, "ConsistUnits") != selected.consist)
                errors.Add("catalogue: missing diagram or wrong engine/tender numbering on " + page.name);
            var cars = all.Where(o => o.GetType().Name == "CustomCarType" && Str(o, "id") == selected.carId).ToArray();
            if (cars.Length != 1) { errors.Add("catalogue: expected one car type " + selected.carId); continue; }
            var variants = new SerializedObject(cars[0]).FindProperty("liveries");
            if (variants == null || variants.arraySize == 0) { errors.Add("catalogue: no liveries for " + selected.carId); continue; }
            for (int i = 0; i < variants.arraySize; i++)
            {
                var variant = variants.GetArrayElementAtIndex(i).objectReferenceValue;
                if (!variant) { errors.Add("catalogue: missing livery on " + selected.carId); continue; }
                string id = Str(variant, "id");
                if (Reference(variant, "CatalogPage") != page || !Ref(variant, "icon"))
                    errors.Add("catalogue: wrong page or missing silhouette for " + id);
                liveries.Add(id + " -> " + page.name);
            }
        }
        output.catalogueLiveries = liveries.OrderBy(n => n, StringComparer.Ordinal).ToArray();
        var packs = all.Where(o => o.GetType().Name == "CustomCarPack").ToArray();
        if (packs.Length != 1) { errors.Add("catalogue: expected one car pack"); return; }
        var extras = Reference(packs[0], "ExtraTranslations");
        if (!extras) { errors.Add("catalogue: missing pack translations"); return; }
        var terms = JsonUtility.FromJson<CatalogueTerms>("{\"terms\":" + Str(extras, "_termsJson") + "}");
        var keys = (terms == null || terms.terms == null ? new CatalogueTerm[0] : terms.terms)
            .Select(t => t.Term).Where(k => k != null && k.StartsWith("rrstock/catalogue/", StringComparison.Ordinal)).ToArray();
        if (keys.Distinct().Count() != keys.Length || !new HashSet<string>(keys).SetEquals(input.catalogueTermKeys ?? new string[0]))
            errors.Add("catalogue: missing, duplicated or unrelated catalogue text keys");
    }

    static Object Reference(Object o, string field)
    {
        var p = new SerializedObject(o).FindProperty(field);
        return p != null && p.propertyType == SerializedPropertyType.ObjectReference ? p.objectReferenceValue : null;
    }

    static string Str(Object o, string field)
    {
        var p = new SerializedObject(o).FindProperty(field);
        return p != null && p.propertyType == SerializedPropertyType.String ? p.stringValue : null;
    }

    static bool Ref(Object o, string field)
    {
        var p = new SerializedObject(o).FindProperty(field);
        return p != null && p.propertyType == SerializedPropertyType.ObjectReference && p.objectReferenceValue;
    }
}
