using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

// Generic Railroader -> Derail Valley CCL 3.1.9 steam loco builder. All loco-specific data comes from a LocoConfig
// (RlwConfig.cs: RLW RBBM-1t 2-4-4-2T Mallet tank; RgbConfig.cs: RLW RGB-2 0-10-0 + tender). A tender loco builds two cars
// (loco, then its tender) into one pack. Guide: Claudes Place\GUIDE_Railroader_to_DV_CCL.md.
// Source: AssetRipper export of the RR asset bundle, version-changed to 2019.4, clip paths restored from CRC32.
// Run windowed (Personal licence refuses -batchmode):
//   Unity.exe -projectPath <project> -executeMethod RgbConfig.Build     env CCL_BUILD_OUT (or RLW_BUILD_OUT) = output folder
public static class CclLocoBuild
{
    static LocoConfig Cfg;                      // the car being built (loco or tender)
    static LocoConfig Loco;                     // the pack's loco (owns the pack; Loco.Tender is built after it)
    static readonly Dictionary<LocoConfig, string> builtFolders = new Dictionary<LocoConfig, string>();
    static string CarId => Cfg.CarId;
    static string CarName => Cfg.CarName;
    static string Livery => Cfg.Livery;
    static float Mass => Cfg.WeightEmptyKg;
    static float WaterCapacity => Cfg.WaterCapacityL;
    static float CoalCapacity => Cfg.CoalCapacityKg;
    static float WheelRadius => Cfg.WheelRadius;
    static float PonyRadius => Cfg.PonyRadius;
    static string SrcPrefab => Cfg.SrcPrefab;
    static string Work => Cfg.Work;
    static List<Comp> Components => Cfg.Components;

    const BindingFlags BF = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.Instance;
    static readonly StringBuilder Report = new StringBuilder();
    static int warnings;
    static string outDir, carFolder;
    static Dictionary<Material, Material> matMap;
    static readonly Dictionary<string, Material> ownMats = new Dictionary<string, Material>();
    static Transform refBody; // unmodified RR model instance in the build scene, for measurements (the car wizard resets the scene)
    static Transform RefBody => refBody ? refBody : (refBody = ((GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(SrcPrefab))).transform);

    // ------------------------------------------------------------------ entry
    public static void Run(LocoConfig cfg)
    {
        Loco = Cfg = cfg;
        Report.Clear(); warnings = 0; ownMats.Clear(); refBody = null; builtFolders.Clear();
        Line($"CclLocoBuild: {CarName} ({CarId}) v{Cfg.Version}{(cfg.Tender != null ? $" + tender {cfg.Tender.CarName} ({cfg.Tender.CarId})" : "")}");
        outDir = Environment.GetEnvironmentVariable("CCL_BUILD_OUT") ?? Environment.GetEnvironmentVariable("RLW_BUILD_OUT") ?? Path.GetFullPath("BuildOut");
        Directory.CreateDirectory(outDir);
        try
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            foreach (var c in Cars(cfg)) if (AssetDatabase.IsValidFolder(c.Work)) AssetDatabase.DeleteAsset(c.Work);
            foreach (var c in Cars(cfg)) { Folder(c.Work); Folder(c.Work + "/Generated"); }
            BuildOwnAssets();
            foreach (var c in Cars(cfg)) BuildCar(c);
            if (cfg.Tender != null) LinkTender(cfg, cfg.Tender);
            Cfg = cfg; refBody = null; carFolder = builtFolders[cfg];
            EditorSceneManager.SaveOpenScenes();
            AssetDatabase.SaveAssets();
            RenderCheck();
            Export();
        }
        catch (Exception e)
        {
            Line("EXCEPTION " + (e is TargetInvocationException tie && tie.InnerException != null ? tie.InnerException : e));
        }
        Line($"\nwarnings: {warnings}");
        File.WriteAllText(Path.Combine(outDir, "build_report.txt"), Report.ToString());
        EditorApplication.Exit(0);
    }

    static IEnumerable<LocoConfig> Cars(LocoConfig c) { yield return c; if (c.Tender != null) yield return c.Tender; }

    // one DV car (loco or tender): its own car folder, materials, prefabs and assets
    static void BuildCar(LocoConfig c)
    {
        Cfg = c; refBody = null; carFolder = null;
        Section($"######## CAR {c.CarName} ({c.CarId}){(c.IsTender ? " - tender" : "")}");
        PrepareClips();
        matMap = BuildMaterials(Livery);
        CreateCar();
        BuildExterior();
        if (!c.IsTender) { BuildInterior(); BuildInteriorLOD(); }
        BuildInteractables();
        var sound = c.IsTender ? null : BuildSound();
        ConfigureAssets(sound);
        builtFolders[c] = carFolder;
    }

    // The tender joins the loco's pack; the loco spawns with it (trainset + spawn groups) and couples to it rigidly
    // (CarAutoCoupler / RigidCoupler / VirtualHandbrakeOverrider on the loco, added in BuildExterior).
    static void LinkTender(LocoConfig loco, LocoConfig tender)
    {
        Section("Loco + tender");
        carFolder = builtFolders[loco];
        var pack = FindAsset("CustomCarPack");
        var locoType = FindAsset("CustomCarType");
        var locoLivery = FindAsset("CustomCarVariant");
        carFolder = builtFolders[tender];
        var tenderType = FindAsset("CustomCarType");
        var tenderLivery = FindAsset("CustomCarVariant");
        carFolder = builtFolders[loco];
        Set(pack, "Cars", new List<Object> { locoType, tenderType });
        string lid = Get<string>(locoLivery, "id"), tid = Get<string>(tenderLivery, "id");
        Set(locoLivery, "TrainsetLiveries", new List<string> { lid, tid });
        SetArraySize(locoLivery, "LocoSpawnGroups", loco.SpawnTracks.Length);
        for (int i = 0; i < loco.SpawnTracks.Length; i++)
        {
            Set(locoLivery, $"LocoSpawnGroups.Array.data[{i}].Track", loco.SpawnTracks[i]);
            Set(locoLivery, $"LocoSpawnGroups.Array.data[{i}].AdditionalLiveries", new List<string> { tid });
        }
        locoLivery.GetType().GetMethod("ForceValidation", BF)?.Invoke(locoLivery, null);
        foreach (var o in new[] { pack, locoLivery }) EditorUtility.SetDirty(o);
        AssetDatabase.SaveAssets();
        Line($"pack cars: {lid} + {tid}; trainset [{lid}, {tid}]; spawn tracks [{string.Join(", ", loco.SpawnTracks)}] with the tender");
    }

    // ------------------------------------------------------------------ step 0: clips, materials, generated assets
    static AnimationClip Clip(string rrName) => AssetDatabase.LoadAssetAtPath<AnimationClip>(Cfg.AnimationMap[rrName]);

    static void PrepareClips()
    {
        Section("Clips");
        foreach (var n in Cfg.EngineUnits.Select(u => u.AnimKey).Concat(Cfg.PonyTrucks.Select(p => p.animKey)))
        {
            var c = Clip(n);
            var s = AnimationUtility.GetAnimationClipSettings(c);
            s.loopTime = true;
            AnimationUtility.SetAnimationClipSettings(c, s);
            EditorUtility.SetDirty(c);
            Line($"  {n} ({c.name}): loopTime on, length {c.length:F3}s = one wheel revolution");
        }
        AssetDatabase.SaveAssets();
    }

    // RR "Standard Car Shader (Shared)" = MainTex * _BaseColor (livery tint), SpecGloss (rgb spec), _Smoothness, Normal, Occlusion.
    // DV: Standard (Specular setup) with the same maps; livery tint -> _Color.
    static Dictionary<Material, Material> BuildMaterials(string livery)
    {
        Section("Materials (" + livery + ")");
        var colors = Cfg.Liveries.First(l => l.name == livery).colors
            .ToDictionary(c => c.id.ToLowerInvariant(), c => ParseHex(c.hex));
        // RR colorizers say which livery colour id paints which material-map entry (Colorizer = 'base'). The ids need not match
        // the material names (RGB-2: colour 'Wheels Trim' paints material 'Wheel Trim 1'). A colorizer with no material entry
        // matches renderer materials by name instead (RGB-2 tender wheels: '8', 'X' on the truck prefabs).
        var idByMat = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var idByName = new List<(string name, string id)>();
        foreach (var c in Components.Where(c => c.kind == "Colorizer" || c.kind == "MaterialColorizerComponent"))
        {
            string id = c.kind == "Colorizer" ? "base" : Extra(c, "colorID");
            string mat = Extra(c, "materialName");
            if (string.IsNullOrEmpty(id) || string.IsNullOrEmpty(mat)) continue;
            if (c.extra.Contains("\"material\":null")) idByName.Add((mat, id)); else idByMat[mat] = id;
        }
        var tintByPath = new Dictionary<string, Color>();
        foreach (var kv in Cfg.MaterialMap)
        {
            string id = idByMat.TryGetValue(kv.Key, out var i) ? i : kv.Key;
            if (colors.TryGetValue(id.ToLowerInvariant(), out var col)) tintByPath[kv.Value] = col;
            else Warn($"livery {livery} has no colour '{id}' for material map entry '{kv.Key}'");
        }

        string dir = $"{Work}/Materials";
        Folder(dir);
        var used = new HashSet<Material>();
        foreach (var p in new[] { SrcPrefab }.Concat(Cfg.ExtraPrefabs).Concat(Cfg.ExtraParts).Concat(Cfg.Trucks.Select(t => t.Prefab)).Distinct())
            foreach (var r in AssetDatabase.LoadAssetAtPath<GameObject>(p).GetComponentsInChildren<Renderer>(true))
                foreach (var m in r.sharedMaterials) if (m) used.Add(m);
        foreach (var m in used)
        {
            var hit = idByName.FirstOrDefault(n => System.Text.RegularExpressions.Regex.IsMatch(m.name, "^" + System.Text.RegularExpressions.Regex.Escape(n.name) + "(_\\d+)?$"));
            if (hit.id != null && !tintByPath.ContainsKey(AssetDatabase.GetAssetPath(m)) && colors.TryGetValue(hit.id.ToLowerInvariant(), out var col))
                tintByPath[AssetDatabase.GetAssetPath(m)] = col;
        }

        var spec = Shader.Find("Standard (Specular setup)");
        var map = new Dictionary<Material, Material>();
        foreach (var src in used.OrderBy(m => m.name))
        {
            var m = new Material(spec) { name = src.name };
            string srcPath = AssetDatabase.GetAssetPath(src);
            bool rr = src.shader.name.StartsWith("Railroader");
            string note;
            if (rr)
            {
                m.SetTexture("_MainTex", src.GetTexture("_MainTex"));
                m.SetTexture("_SpecGlossMap", src.GetTexture("_SpecGlossMap"));
                m.SetTexture("_BumpMap", src.GetTexture("_BumpMap"));
                m.SetTexture("_OcclusionMap", src.GetTexture("_OcclusionMap"));
                m.SetFloat("_GlossMapScale", src.GetFloat("_Smoothness"));
                m.SetFloat("_SmoothnessTextureChannel", 0);
                if (m.GetTexture("_SpecGlossMap")) m.EnableKeyword("_SPECGLOSSMAP");
                if (m.GetTexture("_BumpMap")) m.EnableKeyword("_NORMALMAP");
                var c = tintByPath.TryGetValue(srcPath, out var tint) ? tint : Color.white;
                c.a = 1;
                m.color = c;
                note = tintByPath.ContainsKey(srcPath) ? $"livery tint #{ColorUtility.ToHtmlStringRGB(c)}" : "untinted";
            }
            else
            {
                var c = src.HasProperty("_BaseColor") ? src.GetColor("_BaseColor") : Color.white;
                m.SetColor("_SpecColor", new Color(0.2f, 0.2f, 0.2f));
                m.SetFloat("_Glossiness", src.HasProperty("_Smoothness") ? src.GetFloat("_Smoothness") : 0.5f);
                bool transparent = src.HasProperty("_Surface") && src.GetFloat("_Surface") > 0.5f;
                if (transparent) MakeTransparent(m);
                m.color = c;
                note = $"URP Lit -> {(transparent ? "transparent " : "")}colour {c}";
            }
            // two source materials may share a name (the body and a parts pack both have 'black'): the second CreateAsset would
            // replace the first file and leave its renderers pink
            string fileBase = Safe(src.name); int dup = 1;
            while (AssetDatabase.LoadAssetAtPath<Material>($"{dir}/{fileBase}.mat") != null) fileBase = Safe(src.name) + "_" + (++dup);
            AssetDatabase.CreateAsset(m, $"{dir}/{fileBase}.mat");
            map[src] = m;
            Line($"  {src.name,-28} {note}");
        }
        Line($"{map.Count} materials converted");
        return map;
    }

    static void MakeTransparent(Material m)
    {
        m.SetFloat("_Mode", 3);
        m.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.One);
        m.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
        m.SetInt("_ZWrite", 0);
        m.DisableKeyword("_ALPHATEST_ON");
        m.DisableKeyword("_ALPHABLEND_ON");
        m.EnableKeyword("_ALPHAPREMULTIPLY_ON");
        m.renderQueue = 3000;
    }

    static Mesh discMesh, needleMesh, boxMesh, wheelMesh, leverMesh;

    // Replacements for RR runtime assets: gauge dials, needles, coal load, water column.
    static void BuildOwnAssets()
    {
        Section("Generated assets (DV substitutes for RR runtime defaults)");
        Folder($"{Work}/Generated");
        discMesh = SaveMesh(Disc(48), "gauge_disc");
        needleMesh = SaveMesh(Needle(), "gauge_needle");
        boxMesh = SaveMesh(Box(), "unit_box_bottom_pivot");
        wheelMesh = SaveMesh(ValveWheel(), "control_valve_wheel");
        leverMesh = SaveMesh(Lever(), "control_lever");

        ownMats["dial_pressure"] = TexMat("dial_pressure", Dial(0, 20, 5, 1, true));
        ownMats["dial_speed"] = TexMat("dial_speed", Dial(0, 100, 20, 5, false));
        ownMats["dial_brake"] = TexMat("dial_brake", Dial(0, 10, 2, 0.5f, false));
        ownMats["needle_black"] = ColMat("needle_black", new Color(0.05f, 0.05f, 0.05f), 0.4f);
        ownMats["needle_red"] = ColMat("needle_red", new Color(0.7f, 0.05f, 0.03f), 0.4f); ownMats["brass"] = ColMat("brass", new Color(0.80f, 0.62f, 0.32f), 0.75f); ownMats["brass"].SetFloat("_Metallic", 0.85f);
        ownMats["gauge_glass"] = ColMat("gauge_glass", new Color(0.9f, 0.9f, 0.9f, 0.08f), 0.95f, true);
        ownMats["water_column"] = ColMat("water_column", new Color(0.18f, 0.28f, 0.36f, 0.85f), 0.9f, true);
        ownMats["coal"] = TexMat("coal", CoalTexture(), 0.25f);
        Line("  dials (pressure 0-20 bar, speed 0-100 km/h, brake 0-10 bar), needle, glass, water column, coal load");
    }

    // ------------------------------------------------------------------ step 1: CCL car wizard
    static void CreateCar()
    {
        Section("Car Wizard");
        foreach (var old in new[] { "Assets/_CCL_CARS/" + CarName, "Assets/_CCL_CARS/" + CarId })
            if (AssetDatabase.IsValidFolder(old)) { AssetDatabase.DeleteAsset(old); Line("deleted previous build folder " + old); }
        var wiz = T("CCL.Creator.Wizards.CarWizard");
        var cs = Activator.CreateInstance(T("CCL.Creator.Wizards.CarWizard+CarSettings"));
        SetField(cs, "Kind", Cfg.IsTender ? 3 : 2);          // DVTrainCarKind: Loco 2, Tender 3
        SetField(cs, "ID", CarId);
        SetField(cs, "Name", CarName);
        SetField(cs, "BaseCarType", Cfg.BaseCarType);
        SetField(cs, "Role", 0);
        object ps = null;                                       // a tender joins the loco's pack (LinkTender)
        if (!Cfg.IsTender) { ps = Activator.CreateInstance(T("CCL.Creator.Wizards.CarWizard+PackSettings")); SetField(ps, "Author", Cfg.Author); }
        wiz.GetMethod("CreateNewCar", BF).Invoke(null, new[] { cs, ps });
        AssetDatabase.Refresh();
        string existing = "Assets/_CCL_CARS/" + CarName;
        carFolder = AssetDatabase.IsValidFolder(existing) ? existing
            : Path.GetDirectoryName(AssetDatabase.GetAssetPath(FindAsset("CustomCarType"))).Replace('\\', '/');
        Line("car folder " + carFolder);
        foreach (var guid in AssetDatabase.FindAssets("", new[] { carFolder }))
            Line("  created " + AssetDatabase.GUIDToAssetPath(guid));
    }

    // ------------------------------------------------------------------ step 2: exterior
    static void BuildExterior()
    {
        Section("Exterior prefab");
        string path = $"{carFolder}/{CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        var R = root.transform;
        var model = R.Find("Model");
        Kill(R.Find("[BufferStems]"));
        foreach (Transform c in model.Cast<Transform>().ToList()) Kill(c);

        var body = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(SrcPrefab), root.scene);
        PrefabUtility.UnpackPrefabInstance(body, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
        body.transform.SetParent(model, false);
        body.name = Cfg.BodyName;
        var B = body.transform;
        StripScripts(body);

        // RR ComponentGroups switch headcode lamps; all four lamp models are kept and lit electrically (BuildLights)
        var lamps = new GameObject(Cfg.ExtraPrefabsGroup).transform;
        lamps.SetParent(B, false);
        foreach (var lp in Cfg.ExtraPrefabs)
        {
            var l = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(lp), root.scene);
            PrefabUtility.UnpackPrefabInstance(l, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            l.transform.SetParent(lamps, false);
        }

        // parts prefabs modelled in car space (G-29 pack parts: headlight, handrail, markers): kept at their own root pose
        foreach (var lp in Cfg.ExtraParts)
        {
            var l = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(lp), root.scene);
            PrefabUtility.UnpackPrefabInstance(l, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            l.transform.SetParent(lamps, true);
            Line($"  extra part {Path.GetFileNameWithoutExtension(lp)} at {V(l.transform.position)}");
        }

        // empty placeholder meshes (RR light anchors with 'Lit' material)
        foreach (var mf in body.GetComponentsInChildren<MeshFilter>(true).ToList())
            if (!mf.sharedMesh || mf.sharedMesh.vertexCount == 0)
            {
                Line($"  removed empty mesh object {mf.name}");
                if (mf.transform.childCount == 0) Kill(mf.transform);
                else { Object.DestroyImmediate(mf.GetComponent<MeshRenderer>()); Object.DestroyImmediate(mf); }
            }
        foreach (var n in Cfg.RemoveObjects)
        {
            var stray = B.Find(n);
            if (stray) { Line($"  removed stray object {n} at {V(stray.GetComponent<Renderer>().bounds.center)}"); Kill(stray); }
        }
        ApplyMaterials(body);
        if (Cfg.BodyExtras != null) { Folder($"{Work}/Generated"); Cfg.BodyExtras(body, $"{Work}/Generated"); Line("  body extras added (config)"); }
        CutFittings(body);
        var bounds = RendererBounds(body);
        Line($"body renderer bounds centre {V(bounds.center)} size {V(bounds.size)}");

        var cols = R.Find("[colliders]");
        BuildColliders(body, cols);
        var ax = BuildRunningGear(R, model, body, cols);
        BuildCabAnimations(body);
        BuildBrakeShoes(body);

        // couplers: DV screw-link rigs at the RR buffer faces (the model keeps its own buffers and hooks), or at an explicit
        // coupling plane on a drawbar end (loco rear / tender front: RR positionTail / tender head)
        float faceF = Cfg.CouplingFaceFront ?? B.Find(Cfg.BufferFront).GetComponent<Renderer>().bounds.max.z;
        float faceR = Cfg.CouplingFaceRear ?? B.Find(Cfg.BufferRear).GetComponent<Renderer>().bounds.min.z;
        Rig(R.Find("[coupler_rig_front]"), faceF - Cfg.CouplerInset, faceF, Cfg.CouplingFaceFront.HasValue ? "coupling plane (config)" : "buffer face " + Cfg.BufferFront);
        Rig(R.Find("[coupler_rig_rear]"), faceR + Cfg.CouplerInset, faceR, Cfg.CouplingFaceRear.HasValue ? "coupling plane (config)" : "buffer face " + Cfg.BufferRear);

        // number plates at the RR RoadNumber decals
        foreach (var (anchor, decal) in Cfg.PlateDecals)
        {
            var d = Comp(decal);
            var a = R.Find(anchor);
            float side = Mathf.Sign(d.pos.x);
            float sx = SurfaceX(body, d.pos.y, d.pos.z, side);
            var p = new Vector3(side * ((sx > 0 ? sx : Mathf.Abs(d.pos.x)) + 0.01f), d.pos.y, d.pos.z);
            a.localPosition = p;
            Line($"{anchor} -> {V(p)} (RR decal {decal} {V(d.pos)}, surface x {sx:F3}); rotation kept {V(a.localEulerAngles)}");
        }

        // cab teleport on the cab floor between the two RR seats (or at CabZ when the RR seats are elsewhere)
        if (!Cfg.IsTender)
        {
            float cabZ = Cfg.CabZ ?? Comp(Cfg.CabSeatComp).pos.z + Cfg.CabSeatOffsetZ;
            var cab = new GameObject("[cab]").transform;
            cab.SetParent(R, false);
            float floorY = FloorY(body, 0f, cabZ);
            cab.localPosition = new Vector3(0, floorY, cabZ);
            var glow = Child(cab, "CabHighlightGlow", new Vector3(0, 1.0f, 0));
            var room = Child(cab, "RoomscalePosition", Vector3.zero);
            // the teleport pointer ray hits this trigger box (as the CCL 4-6-2T / LMS 8F 'teleport_indicator'); without it the cab
            // never highlights (G-29 test2: no teleport). GrabberRaycastPassThrough lets the control-grab ray pass through it.
            var vol = Cfg.CabTeleportVolume ?? (new Vector3(0, floorY + 1.1f, cabZ), new Vector3(2.6f, 2.2f, 1.8f));
            var ind = Child(cab, "teleport_indicator", cab.InverseTransformPoint(R.TransformPoint(vol.centre)));
            ind.localScale = vol.size;
            ind.gameObject.AddComponent<BoxCollider>().isTrigger = true;
            Add(ind.gameObject, "CCL.Types.Proxies.GrabberRaycastPassThroughProxy");
            Line($"  cab teleport volume: centre {V(vol.centre)} size {V(vol.size)} (trigger, grab pass-through)");
            var ctd = Add(cab.gameObject, "CCL.Types.Proxies.CabTeleportDestinationProxy");
            Set(ctd, "hoverGlow", Add(glow.gameObject, "CCL.Types.Proxies.TeleportHoverGlowProxy"));
            Set(ctd, "roomscaleTeleportPosition", room);
            Line($"[cab] at {V(cab.localPosition)} (floor raycast y {floorY:F3})");
            Add(root, "CCL.Types.Proxies.Controllers.MagicShovellingProxy");
        }
        if (Cfg.CoalLoad != null) BuildCoalLoad(body);

        // steam simulation: stock S060/S282 basis (S282 = tender ports) or CCL's tender basis (S282B), then RR values
        var creator = Activator.CreateInstance(T(Cfg.IsTender ? "CCL.Creator.Wizards.SimSetup.TenderSimCreator" : "CCL.Creator.Wizards.SimSetup.SteamerSimCreator"), BF, null, new object[] { root }, null);
        creator.GetType().GetMethod("CreateSimForBasis", BF).Invoke(creator, new object[] { Cfg.IsTender ? 0 : Cfg.SimBasis });
        var sim = R.Find("[sim]");
        Line("sim components: " + string.Join(", ", sim.Cast<Transform>().Select(t => t.name)));
        TuneSim(sim);
        if (!Cfg.IsTender)
        {
            if (Cfg.OilPoints != null) ConfigureOiling(sim);
            FixHeadlightDecoder(sim);
            OverridePortRefs(sim);
        }
        if (Cfg.LampKey != null) BuildLights(root, body);

        if (Cfg.Tender != null)
        {
            // loco side of the tender: couple automatically and rigidly to a Tender behind; the tender's handbrake is the loco's
            foreach (var (type, auto) in new[] { ("CCL.Types.Components.CarAutoCoupler", true), ("CCL.Types.Components.RigidCoupler", false) })
            {
                var cpl = Add(root, type);
                Set(cpl, "Direction", 1);                           // CouplerDirection.Rear
                if (auto) Set(cpl, "OtherDirection", 0);            // the tender's front
                Set(cpl, "CarKinds", new List<string> { "Tender" });
            }
            var vho = Add(sim.gameObject, "CCL.Types.Components.VirtualHandbrakeOverrider");
            Set(vho, "Direction", 1);
            Set(vho, "CarKinds", new List<string> { "Tender" });
            Line("tender coupling: CarAutoCoupler + RigidCoupler (rear, kind Tender), VirtualHandbrakeOverrider on [sim]");
        }
        if (Cfg.IsTender)
        {
            Set(Add(root, "CCL.Types.Components.KeepCoupledInteriorLoaded"), "KeepFrontCoupledLoaded", true);
            Line("tender: KeepCoupledInteriorLoaded (front)");
        }

        if (!Cfg.IsTender)
        {
            var anchor2 = Child(model, "[explosion anchor]", Cfg.ExplosionAnchor);
            foreach (var ex in root.GetComponentsInChildren(T("CCL.Types.Proxies.Controllers.ExplosionActivationOnSignalProxy"), true))
                Set(ex, "explosionAnchor", anchor2);

            T("CCL.Creator.Wizards.ParticleWizards").GetMethod("CreateSteamParticles", BF).Invoke(null, new object[] { new MenuCommand(root) });
            PlaceParticles(R.Find("[particles]"));
        }

        var aos = R.Find("AOShadow");
        if (aos)
        {
            float zF = R.Find("[coupler_rig_front]").localPosition.z, zR = R.Find("[coupler_rig_rear]").localPosition.z;
            aos.localPosition = new Vector3(0, aos.localPosition.y, (zF + zR) / 2f);
            aos.localScale = new Vector3(3.2f, aos.localScale.y, (zF - zR) + 1.0f);
            Line($"AOShadow -> pos {V(aos.localPosition)} scale {V(aos.localScale)}");
        }

        // TrainCar expects an [interior LOD] when an interior prefab is assigned; the cab meshes live in the exterior here
        if (!Cfg.IsTender && !R.Find("[interior LOD]")) new GameObject("[interior LOD]").transform.SetParent(R, false);

        // Mallet: the front engine (and anything on it) hangs on its DV bogie, which DV turns to the track, so it swings under
        // the boiler on curves. The bogie pivots mid-unit, not at the real hinge: the wheels stay on the rails, the hinge end
        // swings a little the other way.
        foreach (var (p, bogie) in Cfg.ArticulatedParts)
        {
            var t = R.Find(p); var car = R.Find(bogie + "/bogie_car");
            if (!t || !car) { Warn($"articulation: {p} or {bogie}/bogie_car not found"); continue; }
            t.SetParent(car, true);
            Line($"  articulated: {p} -> {bogie}/bogie_car (pivot z {car.position.z:F3})");
        }

        DedupeSim(R.Find("[sim]"));
        PrefabUtility.SaveAsPrefabAsset(root, path);
        DedupeSim(null, path);
        DumpHierarchy(root, "exterior", 2);
        PrefabUtility.UnloadPrefabContents(root);
    }

    // test5: a duplicate executionOrder entry (cabLight) made DV's SimulationFlow throw on spawn -> no sim, no interior at all.
    static void DedupeSim(Transform sim, string savedPrefab = null)
    {
        GameObject loaded = null;
        if (savedPrefab != null) { loaded = PrefabUtility.LoadPrefabContents(savedPrefab); sim = loaded.transform.Find("[sim]"); }
        var conn = sim.GetComponent(T("CCL.Types.Proxies.Ports.SimConnectionsDefinitionProxy"));
        var order = (IList)conn.GetType().GetField("executionOrder").GetValue(conn);
        var seen = new HashSet<string>(); int removed = 0;
        for (int i = 0; i < order.Count; i++)
        {
            var c = order[i] as Component;
            string id = c ? Get<string>(c, "ID") : null;
            if (c == null || !seen.Add(id)) { order.RemoveAt(i--); removed++; }
        }
        if (savedPrefab != null)
        {
            if (removed > 0) { PrefabUtility.SaveAsPrefabAsset(loaded, savedPrefab); Warn($"saved prefab had {removed} duplicate sim entries (fixed)"); }
            Line($"  sim check (saved prefab): {order.Count} components, all IDs unique");
            PrefabUtility.UnloadPrefabContents(loaded);
        }
        else if (removed > 0) Line($"  sim: removed {removed} duplicate executionOrder entries");
    }

    static void ApplyMaterials(GameObject go, bool quiet = false)
    {
        int n = 0;
        foreach (var r in go.GetComponentsInChildren<Renderer>(true))
        {
            r.sharedMaterials = r.sharedMaterials.Select(m => m && matMap.TryGetValue(m, out var d) ? d : m).ToArray();
            n++;
        }
        if (!quiet) Line($"materials applied to {n} renderers");
    }

    // RR: 33 non-convex MeshColliders on the visual meshes (its walkable/collision model).
    // DV: [collision] must be primitive/convex (car rigidbody); [walkable] and [items] may use the RR meshes.
    static void BuildColliders(GameObject body, Transform cols)
    {
        Section("Colliders");
        foreach (var n in new[] { "[collision]", "[walkable]", "[items]", "[camera dampening]" })
            foreach (Transform c in cols.Find(n).Cast<Transform>().ToList()) Kill(c);

        var walk = new GameObject("rlw_walkable").transform; walk.SetParent(cols.Find("[walkable]"), false);
        var items = new GameObject("rlw_items").transform; items.SetParent(cols.Find("[items]"), false);
        int n2 = 0;
        var sources = body.GetComponentsInChildren<MeshCollider>(true).Select(mc => (mc.transform, mc.sharedMesh)).ToList();
        // e.g. steps with no RR collider (RR 'Ladder' components do the climbing); DV needs them walkable
        foreach (var n in Cfg.ExtraWalkableParts)
        {
            var steps = body.transform.Find(n);
            if (steps) sources.Add((steps, steps.GetComponent<MeshFilter>().sharedMesh));
        }
        var seen = new HashSet<(Transform, Mesh)>();
        // entries are names (flat RLW models) or paths from the body (nested models); children of a listed object count too
        var cabCtl = Cfg.CabControlObjects.Select(n => body.transform.Find(n)).Where(x => x).ToList();
        var noWalk = Cfg.NoWalkParts.Select(n => body.transform.Find(n)).Where(x => x).ToList();
        foreach (var (t, mesh) in sources)
        {
            if (!mesh || !seen.Add((t, mesh))) continue; // Water Tank Part.001 carries the same collider twice
            if (Cfg.CabControlObjects.Contains(t.name) || cabCtl.Any(x => t.IsChildOf(x))) continue;  // cab doors are interior controls now (open doorway)
            if (Cfg.NoWalkParts.Contains(t.name) || noWalk.Any(x => t.IsChildOf(x))) { Line($"  no walkable copy of moving part {t.name}"); continue; }
            foreach (var parent in new[] { walk, items })
            {
                var g = new GameObject("mc_" + t.name).transform;
                g.SetParent(parent, false);
                g.SetPositionAndRotation(t.position, t.rotation);
                g.localScale = t.lossyScale;
                g.gameObject.AddComponent<MeshCollider>().sharedMesh = mesh;
            }
            n2++;
        }
        // RR box/capsule colliders (GN M-2 tender decks, loco cube colliders) that have no MeshCollider twin
        int n3 = 0;
        foreach (var src in body.GetComponentsInChildren<Collider>(true).Where(c => (c is BoxCollider || c is CapsuleCollider) && !c.GetComponent<MeshCollider>()).ToList())
        {
            var t = src.transform;
            if (cabCtl.Any(x => t.IsChildOf(x)) || noWalk.Any(x => t.IsChildOf(x))) continue;
            foreach (var parent in new[] { walk, items })
            {
                var g = new GameObject("rr_" + t.name).transform;
                g.SetParent(parent, false);
                g.SetPositionAndRotation(t.position, t.rotation);
                g.localScale = t.lossyScale;
                if (src is BoxCollider b) { var nb = g.gameObject.AddComponent<BoxCollider>(); nb.center = b.center; nb.size = b.size; }
                else { var c = (CapsuleCollider)src; var nc = g.gameObject.AddComponent<CapsuleCollider>(); nc.center = c.center; nc.radius = c.radius; nc.height = c.height; nc.direction = c.direction; }
            }
            n3++;
        }
        foreach (var col in body.GetComponentsInChildren<Collider>(true).ToList()) Object.DestroyImmediate(col);
        Line($"[walkable]/[items]: {n2} static MeshColliders from the RR collider meshes (+ rear steps), {n3} RR box/capsule colliders; all colliders removed from the model");

        // collision boxes from the model's own extents (config; keep the buffers out so coupled cars do not collide at the faces)
        var boxes = Cfg.CollisionBoxes(body.transform);
        var coll = new GameObject("rlw_collision").transform; coll.SetParent(cols.Find("[collision]"), false);
        var cam = new GameObject("rlw_camera").transform; cam.SetParent(cols.Find("[camera dampening]"), false);
        foreach (var (name, c, s) in boxes)
        {
            foreach (var parent in new[] { coll, cam })
            {
                var g = new GameObject(name).transform; g.SetParent(parent, false);
                var bc = g.gameObject.AddComponent<BoxCollider>(); bc.center = c; bc.size = s;
            }
            Line($"  collision box {name,-10} centre {V(c)} size {V(s)}");
        }
    }

    // Coupled axles in engine units; DV physics sees a rigid car on two custom bogies: one per engine unit (Mallet), or an
    // explicit layout (rigid 0-10-0: the axles split over two bogies pivoting on the end axles; tender: RR truck wheelsets).
    static List<Component> BuildRunningGear(Transform R, Transform model, GameObject body, Transform cols)
    {
        Section("Running gear");
        var B = body.transform;
        var bogies = Cfg.Bogies.Count > 0 ? Cfg.Bogies
            : Cfg.EngineUnits.Select(u => new BogieCfg { Bogie = u.Bogie, BogieCollider = u.BogieCollider, AxleParts = u.DriverParts }).ToList();
        foreach (var bc in bogies)
        {
            var zs = (bc.AxleParts != null ? bc.AxleParts.Select(n => B.Find(n).position.z) : bc.Axles).OrderByDescending(z => z).ToArray();
            float pivot = bc.PivotAxle >= 0 ? zs[bc.PivotAxle] : zs.Average();
            SetupBogie(R.Find(bc.Bogie), pivot, zs.Select(z => z - pivot).ToArray());
            if (bc.BogieCollider != null) cols.Find("[bogies]/" + bc.BogieCollider).localPosition = new Vector3(0, 0, pivot);
        }
        var unitZ = Cfg.EngineUnits.Select(u => u.DriverParts.Select(n => B.Find(n).position.z).OrderByDescending(z => z).ToArray()).ToList();
        BuildTrucks(R, body);
        Line($"RR wheelsets: {string.Join("; ", Cfg.Wheelsets.Select(w => $"{w.clip} off {w.offset} len {w.length} dia {w.diameter}"))}");
        if (Cfg.EngineUnits.Count == 0)
        {
            // unpowered (tender): sliding sparks at the bogie contact points only
            var ws = new GameObject("[wheelsparks]"); ws.transform.SetParent(R, false);
            var cps = new[] { "BogieF", "BogieR" }.SelectMany(b => R.Find(b + "/bogie_car/ContactPoints").Cast<Transform>()).ToList();
            Set(Add(ws, "CCL.Types.Components.CustomWheelSlideSparks"), "sparkAnchors", cps);
            return new List<Component>();
        }

        // animation groups: every clip gets its own Animator on a node at the body origin holding the clip's top-level objects
        // nested models split a wheel clip into one Animator per region (G-29: 14); every one is driven by the wheel proxy
        var unitAnims = new List<Animator>(); var unitOffsets = new List<float>();
        foreach (var u in Cfg.EngineUnits)
        {
            var list = Cfg.NestedClipGroups ? AnimGroups(body, u.GroupName, Clip(u.AnimKey), true) : new List<Animator> { AnimGroup(body, u.GroupName, Clip(u.AnimKey), true) };
            unitAnims.AddRange(list); unitOffsets.AddRange(list.Select(_ => u.StartOffset));
        }
        var ponyAnims = Cfg.PonyTrucks.Select(p => AnimGroup(body, p.groupName, Clip(p.animKey), true)).ToList();

        var powered = new List<Component>();
        var lefts = new List<Transform>();
        var rights = new List<Transform>();
        foreach (var z in unitZ.SelectMany(a => a))
        {
            var ax = new GameObject("[axle]").transform;
            ax.SetParent(model, false);
            ax.localPosition = new Vector3(0, WheelRadius, z);
            var pw = Add(ax.gameObject, "CCL.Types.Proxies.Wheels.PoweredWheelProxy");
            Set(pw, "wheelTransform", ax);
            Set(pw, "localRotationAxis", Vector3.right);
            powered.Add(pw);
            lefts.Add(Child(ax, "sparksL", new Vector3(-Cfg.SparksX, -WheelRadius, 0)));
            rights.Add(Child(ax, "sparksR", new Vector3(Cfg.SparksX, -WheelRadius, 0)));
        }
        var pwGo = new GameObject("[powered wheels]");
        pwGo.transform.SetParent(R, false);
        var mgr = Add(pwGo, "CCL.Types.Proxies.Wheels.PoweredWheelsManagerProxy");
        Set(mgr, "poweredWheels", powered);
        Set(mgr, "GetWheelsFromDefaultBogies", false);
        var via = Add(pwGo, "CCL.Types.Proxies.Wheels.PoweredWheelRotationViaAnimationProxy");
        Set(via, "wheelRadius", WheelRadius);
        Set(via, "affectedByWheelSlide", true);
        SetArraySize(via, "animatorSetups", unitAnims.Count);
        for (int i = 0; i < unitAnims.Count; i++)
        {
            Set(via, $"animatorSetups.Array.data[{i}].animator", unitAnims[i]);
            Set(via, $"animatorSetups.Array.data[{i}].startTimeOffset", unitOffsets[i]);
        }
        Set(via, "_animators", unitAnims.Cast<Object>().ToList());
        Set(via, "_offsets", unitOffsets);
        Line($"powered wheels: {powered.Count} axles z {string.Join(", ", unitZ.SelectMany(a => a).Select(z => z.ToString("F3")))}; engine unit offsets {string.Join(", ", Cfg.EngineUnits.Select(u => u.StartOffset))} (RR phase)");

        // pony trucks roll with the car (not powered, no slip), own radius
        if (ponyAnims.Count > 0)
        {
            var ponyGo = new GameObject("[pony wheels]");
            ponyGo.transform.SetParent(R, false);
            var pony = Add(ponyGo, "CCL.Types.Proxies.Wheels.WheelRotationViaAnimationProxy");
            Set(pony, "wheelRadius", PonyRadius);
            Set(pony, "affectedByWheelSlide", false);
            SetArraySize(pony, "animatorSetups", ponyAnims.Count);
            for (int i = 0; i < ponyAnims.Count; i++)
            {
                Set(pony, $"animatorSetups.Array.data[{i}].animator", ponyAnims[i]);
                Set(pony, $"animatorSetups.Array.data[{i}].startTimeOffset", 0f);
            }
            Set(pony, "_animators", ponyAnims.Cast<Object>().ToList());
            Set(pony, "_offsets", ponyAnims.Select(_ => 0f).ToList());
            Line($"pony wheels: WheelRotationViaAnimation radius {PonyRadius}");
        }

        // valve gear cut-off follows the reverser port (RR plays the Reverser clip from the reverser value);
        // the cab reverser handle inside that clip becomes an interior control, the rest of the clip is the valve gear
        if (Cfg.ReverserClip != null)
        {
            if (Cfg.ReverserHandle != null) Kill(body.transform.Find(Cfg.ReverserHandle));
            PortAnimGroups(body, "reverser", Clip(Cfg.ReverserClip), "reverser.REVERSER", 0.4995f, 0.4995f);
        }

        var wsGo = new GameObject("[wheelsparks]");
        wsGo.transform.SetParent(R, false);
        var contact = R.Find("BogieF/bogie_car/ContactPoints").Cast<Transform>().Concat(R.Find("BogieR/bogie_car/ContactPoints").Cast<Transform>()).ToList();
        Set(Add(wsGo, "CCL.Types.Components.CustomWheelSlideSparks"), "sparkAnchors", contact);
        var wsc = Add(wsGo, "CCL.Types.Proxies.Wheels.WheelslipSparksControllerProxy");
        SetArraySize(wsc, "wheelSparks", powered.Count);
        for (int i = 0; i < powered.Count; i++)
        {
            Set(wsc, $"wheelSparks.Array.data[{i}].poweredWheel", powered[i]);
            Set(wsc, $"wheelSparks.Array.data[{i}].sparksLeftAnchor", lefts[i]);
            Set(wsc, $"wheelSparks.Array.data[{i}].sparksRightAnchor", rights[i]);
        }
        return powered;
    }

    // RR trucks are separate prefabs placed at runtime (tender: a 2-axle truck at the front, a 1-axle truck at the rear).
    // Placed here at the RR truck origins; each wheelset (pivot on its axle) goes under the nearest DV [axle], which DV spins
    // with the car type's wheelRadius. Frames/brake gear stay on the body.
    static void BuildTrucks(Transform R, GameObject body)
    {
        if (Cfg.Trucks.Count == 0) return;
        var axles = new[] { "BogieF", "BogieR" }.SelectMany(b => R.Find(b + "/bogie_car").Cast<Transform>().Where(t => t.name == "[axle]")).ToList();
        foreach (var t in Cfg.Trucks)
        {
            var go = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(t.Prefab), body.scene);
            PrefabUtility.UnpackPrefabInstance(go, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            go.transform.SetParent(body.transform, false);
            go.transform.localPosition = new Vector3(0, 0, t.Z);
            go.transform.localRotation = t.Reversed ? Quaternion.Euler(0, 180, 0) : Quaternion.identity;
            StripScripts(go);
            foreach (var n in t.Remove) foreach (var x in go.GetComponentsInChildren<Transform>(true).Where(x => x.name == n).ToList()) Kill(x);
            ApplyMaterials(go, quiet: true);
            foreach (var w in go.GetComponentsInChildren<Transform>(true).Where(x => x.name.StartsWith(t.Wheelset)).ToList())
            {
                var ax = axles.OrderBy(a => Mathf.Abs(a.position.z - w.position.z)).First();
                w.SetParent(ax, true);
                Line($"  truck {Path.GetFileNameWithoutExtension(t.Prefab)} wheelset {w.name} at z {w.position.z:F3} (y {w.position.y:F3}) -> [axle] z {ax.position.z:F3} (off {w.position.z - ax.position.z:+0.000;-0.000})");
            }
            if (go.transform.childCount == 0) Kill(go.transform);
        }
    }

    // Cab controls are not interactable in this stage (non-VR, HUD/keyboard); their RR clips follow the sim ports.
    static void BuildCabAnimations(GameObject body)
    {
        Section("Cab and load animations");
        // regulator, brake handles and whistle lever are real DV controls in the interior (they drive the HUD);
        // the whistle clip's roof linkage stays here, following the whistle port
        foreach (var n in Cfg.CabControlObjects) Kill(body.transform.Find(n));
        if (Cfg.WhistleLinkageClip != null)
            PortAnimGroups(body, "whistle linkage", Clip(Cfg.WhistleLinkageClip), "whistle.EXT_IN", 0.999f, 0f);
        BuildFireDoors(body);
        if (Cfg.OilPoints != null) AddOilingPointProviders(body);
        // RR LoadAnimations (e.g. tank water surface, cab tea cup): clip normalized time follows a resource port
        foreach (var (key, objectPath, port, perWater) in Cfg.LoadAnimations)
        {
            string group = key.ToLowerInvariant();
            var gs = Cfg.NestedClipGroups ? AnimGroups(body, group, Clip(key), false) : new List<Animator> { AnimGroup(body, group, Clip(key), false) };
            foreach (var g in gs) PortAnim(g.gameObject, port, perWater ? 0.999f / WaterCapacity : 0.999f, 0f);
            var g0 = gs[0];
            var t = body.transform.Find($"[anim] {group}/{objectPath}");
            var c = Clip(key);
            foreach (var tm in new[] { 0f, 0.5f, 0.999f })
            {
                c.SampleAnimation(g0.gameObject, tm * c.length);
                var r = t ? t.GetComponent<Renderer>() : null;
                if (r) Line($"  {key} t={tm:F2}: pivot {V(t.position)} bounds c {V(r.bounds.center)} s {V(r.bounds.size)}");
            }
            c.SampleAnimation(g0.gameObject, 0f);
        }

        // looped RR clips whose play speed follows a port (bell swing: bell.BELL_NORMALIZED x cycles per second)
        foreach (var (key, port, cps) in Cfg.LoopAnimations)
        {
            var list = Cfg.NestedClipGroups ? AnimGroups(body, key.ToLowerInvariant(), Clip(key), true) : new List<Animator> { AnimGroup(body, key.ToLowerInvariant(), Clip(key), true) };
            foreach (var a in list)
            {
                var apr = Add(a.gameObject, "CCL.Types.Proxies.Ports.AnimatorPortReaderProxy");
                Set(apr, "updateType", 1); Set(apr, "portId", port); Set(apr, "parameterName", "SpeedMultiplier");
                Set(apr, "valueMultiplier", cps); Set(apr, "valueOffset", 0f);
            }
            Line($"  loop {key}: {list.Count} animator(s), SpeedMultiplier = {port} x {cps} cycles/s");
        }

        // handbrake lever: RR clip -> gauge rotation driven by the DV handbrake
        if (Cfg.Handbrake.part != null)
        {
            var hb = body.transform.Find(Cfg.Handbrake.part);
            var w = Pivot(hb, Clip(Cfg.Handbrake.animKey), body, out float ang, out Vector3 axis);
            var g2 = Add(w.gameObject, "CCL.Types.Proxies.Indicators.IndicatorGaugeProxy");
            Set(g2, "needle", w); Set(g2, "minValue", 0f); Set(g2, "maxValue", 1f);
            Set(g2, "minAngle", 0f); Set(g2, "maxAngle", ang); Set(g2, "rotationAxis", axis);
            Add(w.gameObject, "CCL.Types.Components.Indicators.IndicatorHandbrakeReader");
            Line($"  handbrake lever: {ang:F1} deg about {V(axis)} from the handbrake reader");
        }
    }

    // RR 'Brake' clip swings the brake hangers; DV has no brake port, so each hanger becomes a gauge needle
    // driven by the brake-cylinder pressure.
    static void BuildBrakeShoes(GameObject body)
    {
        if (Cfg.BrakeHangerClip == null) return;
        var clip = Clip(Cfg.BrakeHangerClip);
        foreach (var n in Cfg.BrakeHangers)
        {
            var t = body.transform.Find(n);
            var w = Pivot(t, clip, body, out float ang, out Vector3 axis);
            var g = Add(w.gameObject, "CCL.Types.Proxies.Indicators.IndicatorGaugeProxy");
            Set(g, "needle", w); Set(g, "minValue", 0f); Set(g, "maxValue", Cfg.BrakeHangerMaxBar);
            Set(g, "minAngle", 0f); Set(g, "maxAngle", ang); Set(g, "rotationAxis", axis);
            Add(w.gameObject, "CCL.Types.Proxies.Indicators.IndicatorBrakeCylinderReaderProxy");
            Line($"  brake hanger {n}: {ang:F1} deg about {V(axis)} over 0..{Cfg.BrakeHangerMaxBar} bar brake cylinder");
        }
    }

    // Wraps t in an identity pivot at its origin; returns the clip's t=0 -> t=end rotation of t as angle/axis in pivot-parent space.
    static Transform Pivot(Transform t, AnimationClip clip, GameObject body, out float angle, out Vector3 axis)
    {
        var parent = t.parent;
        var q0 = t.localRotation;
        clip.SampleAnimation(body, clip.length);
        var q1 = t.localRotation;
        clip.SampleAnimation(body, 0f);
        t.localRotation = q0;
        (q1 * Quaternion.Inverse(q0)).ToAngleAxis(out angle, out axis);
        if (angle > 180) { angle = 360 - angle; axis = -axis; }
        var w = new GameObject("[pivot] " + t.name).transform;
        w.SetParent(parent, false);
        w.localPosition = t.localPosition;
        t.SetParent(w, true);
        return w;
    }

    // RR mesh islands that become interior controls: cut out of the exterior mesh (the [interior LOD] shows a static copy)
    static void CutFittings(GameObject body)
    {
        foreach (var f in Cfg.Fittings)
        {
            var part = body.transform.Find(f.Part);
            if (!part) { Warn("backhead fitting part not found: " + f.Part); continue; }
            var (_, rest, wb) = SplitIsland(part, f.Centre);
            part.GetComponent<MeshFilter>().sharedMesh = SaveMesh(rest, $"cut_{Safe(f.Part)}_{Safe(f.Name)}");
            Line($"  {f.Name}: wheel island {V(wb.center)} cut out of {f.Part} (now an interior control)");
        }
    }

    // RR fire-hole doors (two leaves, no RR animation): each leaf swings open towards the cab, driven by the fire door port
    static void BuildFireDoors(GameObject body)
    {
        foreach (var n in Cfg.FireDoorLeaves)
        {
            var t = body.transform.Find(n);
            var b = t.GetComponent<Renderer>().bounds;
            float hingeX = b.center.x > 0 ? b.max.x : b.min.x;           // outer edge
            var hinge = new GameObject("[door hinge] " + n).transform;
            hinge.SetParent(t.parent, false);
            hinge.position = new Vector3(hingeX, b.center.y, b.center.z);
            t.SetParent(hinge, true);
            float dx = b.center.x - hingeX;                                // leaf centre relative to the hinge
            float open = 80f * Mathf.Sign(dx);                               // positive dx swings towards -z (the cab) for +angle about +y
            var g = Add(hinge.gameObject, "CCL.Types.Proxies.Indicators.IndicatorGaugeProxy");
            Set(g, "needle", hinge); Set(g, "minValue", 0f); Set(g, "maxValue", 1f);
            Set(g, "minAngle", 0f); Set(g, "maxAngle", open); Set(g, "rotationAxis", Vector3.up);
            PortReader(hinge.gameObject, "fireboxDoor.EXT_IN");
            Line($"  fire door leaf {n}: hinge x {hingeX:F3}, opens {open:F0} deg with fireboxDoor.EXT_IN");
        }
    }

    // Oil cups (interactables) follow PositionSyncProviders with the same tag; without them DV throws every frame.
    static void AddOilingPointProviders(GameObject body)
    {
        var holder = new GameObject("[oiling points]").transform;
        holder.SetParent(body.transform, false);
        foreach (var (tag, pos) in Cfg.OilPoints(RefBody))
        {
            var p = Child(holder, tag, pos);
            Set(Add(p.gameObject, "CCL.Types.Proxies.Util.PositionSyncProviderProxy"), "syncTag", tag);
        }
        Line($"  {Cfg.OilPoints(RefBody).Count()} oil-cup PositionSyncProviders on the body");
    }

    // Port-driven clips may span several regions (GN M-2 reverser: both engines' valve gear + the cab lever): all get the port.
    static List<Animator> PortAnimGroups(GameObject body, string name, AnimationClip clip, string port, float mult, float offset)
    {
        var list = Cfg.NestedClipGroups ? AnimGroups(body, name, clip, false) : new List<Animator> { AnimGroup(body, name, clip, false) };
        foreach (var a in list) PortAnim(a.gameObject, port, mult, offset);
        return list;
    }

    static Animator AnimGroup(GameObject body, string name, AnimationClip clip, bool wheel)
    {
        if (Cfg.NestedClipGroups)
        {
            var list = AnimGroups(body, name, clip, wheel);
            if (list.Count != 1) Warn($"{name}: clip '{clip.name}' split into {list.Count} regions; only the first is driven here");
            return list[0];
        }
        var tops = AnimationUtility.GetCurveBindings(clip).Select(b => b.path.Split('/')[0]).Distinct().ToList();
        var g = new GameObject("[anim] " + name).transform;
        g.SetParent(body.transform, false);
        int moved = 0;
        foreach (var n in tops)
        {
            var t = body.transform.Find(n);
            if (!t) { if (!Cfg.CabControlObjects.Contains(n) && n != Cfg.ReverserHandle) Warn($"{name}: clip object '{n}' not a direct child of the body (already grouped?)"); continue; }
            t.SetParent(g, true);
            moved++;
        }
        string dir = $"{Work}/Animators";
        Folder(dir);
        var ac = AnimatorController.CreateAnimatorControllerAtPath($"{dir}/{Safe(name)}.controller");
        if (wheel) ac.AddParameter("SpeedMultiplier", AnimatorControllerParameterType.Float);
        var sm = ac.layers[0].stateMachine;
        var st = sm.AddState(clip.name);
        st.motion = clip;
        st.speed = wheel ? 1f : 0f;
        if (wheel) { st.speedParameterActive = true; st.speedParameter = "SpeedMultiplier"; }
        sm.defaultState = st;
        var an = g.gameObject.AddComponent<Animator>();
        an.runtimeAnimatorController = ac;
        an.cullingMode = AnimatorCullingMode.AlwaysAnimate;
        an.applyRootMotion = false;
        Line($"  [anim] {name}: clip '{clip.name}' ({(wheel ? "SpeedMultiplier-driven loop" : "port-driven, speed 0")}), {moved} top-level objects");
        return an;
    }

    // NestedClipGroups: region = first two path segments (e.g. 'RE-Master/RE-CabControls'); the Animator node is inserted under
    // the deepest common parent of the region's objects (identity, so nothing moves) and plays a copy of the clip whose paths
    // are re-rooted to it. Clips that bind the same object from two regions are not supported (warned as 'not found').
    static List<Animator> AnimGroups(GameObject body, string name, AnimationClip clip, bool wheel)
    {
        var B = body.transform;
        var curves = AnimationUtility.GetCurveBindings(clip);
        var refs = AnimationUtility.GetObjectReferenceCurveBindings(clip);
        string Key(string p) { var s = p.Split('/'); return s.Length >= 3 ? s[0] + "/" + s[1] : s[0]; }
        string Parent(string p) => p.Contains("/") ? p.Substring(0, p.LastIndexOf('/')) : "";
        var regions = curves.Select(b => b.path).Concat(refs.Select(b => b.path)).Distinct().GroupBy(Key).OrderBy(g => g.Key).ToList();
        var result = new List<Animator>();
        for (int ri = 0; ri < regions.Count; ri++)
        {
            var paths = regions[ri].ToList();
            string D = Parent(paths[0]);
            foreach (var q in paths.Select(Parent))
                while (D != "" && q != D && !q.StartsWith(D + "/")) D = Parent(D);
            var host = D == "" ? B : B.Find(D);
            string gname = regions.Count > 1 ? $"{name} {ri + 1}" : name;
            if (!host) { Warn($"{gname}: clip parent '{D}' not found"); continue; }
            string pre = D == "" ? "" : D + "/";
            var g = new GameObject("[anim] " + gname).transform;
            g.SetParent(host, false);
            int moved = 0;
            foreach (var n in paths.Select(p => p.Substring(pre.Length).Split('/')[0]).Distinct())
            {
                var t = host.Find(n);
                if (!t) { if (!Cfg.CabControlObjects.Contains(pre + n) && pre + n != Cfg.ReverserHandle) Warn($"{gname}: clip object '{pre}{n}' not found (grouped by another clip, or removed)"); continue; }
                t.SetParent(g, true);
                moved++;
            }
            var c = new AnimationClip { name = clip.name + (regions.Count > 1 ? $"_{ri + 1}" : ""), frameRate = clip.frameRate };
            foreach (var b in curves.Where(b => Key(b.path) == regions[ri].Key))
            {
                var nb = b; nb.path = b.path.Substring(pre.Length);
                AnimationUtility.SetEditorCurve(c, nb, AnimationUtility.GetEditorCurve(clip, b));
            }
            foreach (var b in refs.Where(b => Key(b.path) == regions[ri].Key))
            {
                var nb = b; nb.path = b.path.Substring(pre.Length);
                AnimationUtility.SetObjectReferenceCurve(c, nb, AnimationUtility.GetObjectReferenceCurve(clip, b));
            }
            var cs = AnimationUtility.GetAnimationClipSettings(clip);
            if (wheel) cs.loopTime = true;                 // speed-driven clips loop (wheels, bell)
            AnimationUtility.SetAnimationClipSettings(c, cs);
            Folder($"{Work}/Clips");
            AssetDatabase.CreateAsset(c, $"{Work}/Clips/{Safe(gname)}.anim");

            Folder($"{Work}/Animators");
            var ac = AnimatorController.CreateAnimatorControllerAtPath($"{Work}/Animators/{Safe(gname)}.controller");
            if (wheel) ac.AddParameter("SpeedMultiplier", AnimatorControllerParameterType.Float);
            var sm = ac.layers[0].stateMachine;
            var st = sm.AddState(c.name);
            st.motion = c;
            st.speed = wheel ? clip.length : 0f;      // SpeedMultiplier = wheel revs/s; the clip is one revolution over its length
            if (wheel) { st.speedParameterActive = true; st.speedParameter = "SpeedMultiplier"; }
            sm.defaultState = st;
            var an = g.gameObject.AddComponent<Animator>();
            an.runtimeAnimatorController = ac;
            an.cullingMode = AnimatorCullingMode.AlwaysAnimate;
            an.applyRootMotion = false;
            result.Add(an);
            Line($"  [anim] {gname}: under '{(D == "" ? "body" : D)}', clip '{c.name}' re-rooted ({paths.Count} objects, {moved} top-level){(wheel ? $", state speed {clip.length:F3} x SpeedMultiplier" : ", port-driven, speed 0")}");
        }
        if (result.Count == 0) Warn($"{name}: no animator built for clip '{clip.name}'");
        return result;
    }

    // DV AnimatorPortReader SET_NORMALIZED_TIME plays the current state at FloorMod(v*mult+offset, 1): keep the range below 1.
    static void PortAnim(GameObject go, string port, float mult, float offset)
    {
        var apr = Add(go, "CCL.Types.Proxies.Ports.AnimatorPortReaderProxy");
        Set(apr, "updateType", 0);
        Set(apr, "portId", port);
        Set(apr, "valueMultiplier", mult);
        Set(apr, "valueOffset", offset);
        Line($"  {go.name}: {port} -> normalized time x{mult:G4} + {offset}");
    }

    static void SetupBogie(Transform bogie, float z, float[] axleZ)
    {
        bogie.localPosition = new Vector3(0, 0, z);
        var car = bogie.Find("bogie_car");
        Kill(car.Find("bogie2"));
        Kill(car.Find("bogie2brakes"));
        var axles = car.Cast<Transform>().Where(t => t.name == "[axle]").ToList();
        while (axles.Count < axleZ.Length) axles.Add(Object.Instantiate(axles[0].gameObject, car).transform);   // 3-axle units
        foreach (var a in axles) a.name = "[axle]";
        for (int i = 0; i < axles.Count; i++)
        {
            foreach (Transform c in axles[i].Cast<Transform>().ToList()) Kill(c);
            if (i >= axleZ.Length) { Kill(axles[i]); continue; }
            axles[i].localPosition = new Vector3(0, WheelRadius, axleZ[i]);
        }
        // sparks/contact points under the end axles of the unit
        foreach (Transform cp in car.Find("ContactPoints"))
        {
            var p = cp.localPosition;
            cp.localPosition = new Vector3(p.x, p.y, cp.name.StartsWith("F") ? axleZ.Max() : axleZ.Min());
        }
        Line($"{bogie.name} z {z:F3} axles {string.Join(",", axleZ.Select(a => a.ToString("F3")))}");
    }

    static void Rig(Transform rig, float z, float face, string what)
    {
        rig.localPosition = new Vector3(0, Cfg.CouplerHeight, z);
        foreach (var r in rig.GetComponentsInChildren<MeshRenderer>(true))
            if (r.name.StartsWith("Buffer_") || r.name.StartsWith("HookPlate")) r.enabled = false;
        Line($"{rig.name} at {V(rig.localPosition)}: {what} z {face:F3}, inset {Cfg.CouplerInset} (DV coupler height {Cfg.CouplerHeight}); DV buffer/hook meshes hidden, model buffers kept");
    }

    static void TuneSim(Transform sim)
    {
        // coal/water live on the car with the RR load slots (tank loco, or the tender); a tender loco reads them over the coupling
        foreach (var (n, cap) in new[] { ("water", WaterCapacity), ("coal", CoalCapacity) })
        {
            if (cap <= 0) continue;
            var rc = sim.Find(n)?.GetComponents<Component>().FirstOrDefault(c => c.GetType().Name == "ResourceContainerProxy");
            if (rc == null) { Warn("no resource container " + n); continue; }
            Set(rc, "capacity", cap); Set(rc, "defaultValue", cap);
            Line($"  {n}: capacity {cap:F0} (RR load slot)");
        }
        ApplySpec(sim);
    }

    // Data-sheet values from the config: sim component name -> serialized field -> value (every S060/S282 default replaced).
    // Keys starting with '_' are report notes, not sim components.
    static void ApplySpec(Transform sim)
    {
        if (Cfg.SimSpec == null) { if (!Cfg.IsTender) Warn("no SimSpec: the sim keeps the CCL basis defaults"); return; }
        var spec = Cfg.SimSpec(RefBody);
        foreach (var kv in spec)
        {
            if (kv.Key.StartsWith("_")) { foreach (var f in kv.Value) Line($"  {f.Key}: {f.Value}"); continue; }
            var t = sim.Find(kv.Key);
            if (!t) { Warn("spec: no sim component " + kv.Key); continue; }
            foreach (var f in kv.Value)
            {
                var c = t.GetComponents<Component>().FirstOrDefault(x => x is MonoBehaviour && new SerializedObject(x).FindProperty(f.Key) != null);
                if (c == null) { Warn($"spec: {kv.Key}.{f.Key} not found"); continue; }
                Set(c, f.Key, f.Value);
            }
            Line($"  spec {kv.Key}: {string.Join(", ", kv.Value.Select(f => $"{f.Key}={(f.Value is float fl ? fl.ToString("0.###") : f.Value)}"))}");
        }
    }


    // Rewire sim port references the basis connected (e.g. S282's feedwater heater: boiler.FEEDWATER_TEMPERATURE -> "" = none).
    static void OverridePortRefs(Transform sim)
    {
        if (Cfg.PortRefOverrides.Count == 0) return;
        var conn = sim.GetComponent(T("CCL.Types.Proxies.Ports.SimConnectionsDefinitionProxy"));
        var so = new SerializedObject(conn);
        var arr = so.FindProperty("portReferenceConnections");
        var done = new HashSet<string>();
        for (int i = 0; i < arr.arraySize; i++)
        {
            var e = arr.GetArrayElementAtIndex(i);
            string refId = e.FindPropertyRelative("portReferenceId").stringValue;
            if (!Cfg.PortRefOverrides.TryGetValue(refId, out var port)) continue;
            string old = e.FindPropertyRelative("portId").stringValue;
            e.FindPropertyRelative("portId").stringValue = port;
            done.Add(refId);
            Line($"  port ref {refId}: '{old}' -> '{port}'");
        }
        so.ApplyModifiedPropertiesWithoutUndo();
        conn.GetType().GetMethod("OnValidate", BF)?.Invoke(conn, null);
        foreach (var k in Cfg.PortRefOverrides.Keys.Where(k => !done.Contains(k))) Warn($"port ref override: {k} not found");
    }

    static void ConfigureOiling(Transform sim)
    {
        var op = sim.Find("oilingPoints")?.GetComponents<Component>().FirstOrDefault(c => c.GetType().Name == "ManualOilingPointsDefinitionProxy");
        if (op == null) { Warn("no oilingPoints definition"); return; }
        Set(op, "OilingPointCount", Cfg.OilPoints(RefBody).Count());
        op.GetType().GetMethod("OnValidate", BF)?.Invoke(op, null);
        Line($"oilingPoints: count {Get<int>(op, "OilingPointCount")}");
    }

    static void FixHeadlightDecoder(Transform sim)
    {
        var dec = sim.Find("headlightDecoder");
        if (!dec) return;
        foreach (var oc in dec.GetComponents<Component>().Where(c => c.GetType().Name == "OverridableControlProxy"))
        {
            int ct = Get<int>(oc, "ControlType");
            string port = ct == 8 ? "headlightDecoder.FRONT_HEADLIGHTS_EXT_IN" : ct == 9 ? "headlightDecoder.REAR_HEADLIGHTS_EXT_IN" : null;
            if (port != null && string.IsNullOrEmpty(Get<string>(oc, "portId"))) Set(oc, "portId", port);
        }
    }

    // Electric lamps on the RR headcode lamp models (4 front, 1 on the bunker), powered like the 4-6-2T through the dynamo fuse.
    // Setups follow CCL's HeadlightWizard: 6 per end, index = round(port * 5), so the decoder's front/rear values
    // 0 / 0.2 = red, 0.4 = off, 0.6 / 0.8 = white low, 1 = white high. The cab lever drives the decoder (7 notches:
    // rear lit + front red .. off .. front lit + rear red).
    static void BuildLights(GameObject root, GameObject body)
    {
        string Fuse = Cfg.LightsFuse;
        Section($"Lights (dynamo-powered via {Fuse}; ports {Cfg.LightsFrontPort} / {Cfg.LightsRearPort})");
        var R = root.transform;
        var lit = ColMat("lamp_lens_lit", new Color(1f, 0.95f, 0.85f), 0.9f);
        lit.EnableKeyword("_EMISSION"); lit.SetColor("_EmissionColor", new Color(1f, 0.9f, 0.7f) * 3f);
        var litRed = ColMat("lamp_lens_lit_red", new Color(1f, 0.2f, 0.15f), 0.9f);
        litRed.EnableKeyword("_EMISSION"); litRed.SetColor("_EmissionColor", new Color(1f, 0.08f, 0.04f) * 3f);
        var off = ColMat("lamp_lens_off", new Color(0.85f, 0.85f, 0.8f, 0.06f), 0.95f, true);
        foreach (var m in new[] { lit, litRed }) EditorUtility.SetDirty(m);

        // lens position of each lamp: the front face of its reflector ('Lamp Inside' material)
        var lamps = new Dictionary<string, (Vector3 c, float d, bool front)>();
        foreach (var r in body.GetComponentsInChildren<MeshRenderer>(true))
        {
            int k = Array.FindIndex(r.sharedMaterials, m => m && m.name.StartsWith("Lamp Inside"));
            if (k < 0) continue;
            var mesh = r.GetComponent<MeshFilter>().sharedMesh; var v = mesh.vertices; var tri = mesh.GetTriangles(k);
            var b = new Bounds(r.transform.TransformPoint(v[tri[0]]), Vector3.zero);
            foreach (var i in tri) b.Encapsulate(r.transform.TransformPoint(v[i]));
            string key = Cfg.LampKey(r.transform, b);
            if (key == null || lamps.ContainsKey(key)) { Line($"  lamp reflector {PathOf(r.transform, body.transform)} at {V(b.center)} not used"); continue; }
            bool front = Cfg.FrontLow.Concat(Cfg.FrontHigh).Concat(Cfg.FrontRed).Contains(key);
            lamps[key] = (new Vector3(b.center.x, b.center.y, front ? b.max.z + 0.003f : b.min.z - 0.003f), Mathf.Min(b.size.x, b.size.y) * 0.9f, front);
            Line($"  lamp {key,-4} {PathOf(r.transform, body.transform)}: reflector {V(b.center)} size {V(b.size)} -> lens {V(lamps[key].c)} dia {lamps[key].d:F3}");
        }
        // lamps modelled as a housing + glass (RGB-2 smokebox headlight): the lens sits just outside the glass
        foreach (var (key, glass, front) in Cfg.GlassLamps)
        {
            // 'path#material': only the triangles of that material (a lamp housing and lens modelled as one mesh)
            Bounds b;
            if (glass.Contains("#"))
            {
                var parts = glass.Split('#');
                var gr = body.transform.Find(parts[0]).GetComponent<MeshRenderer>();
                int gk = Array.FindIndex(gr.sharedMaterials, m => m && m.name == parts[1]);
                var gm = gr.GetComponent<MeshFilter>().sharedMesh; var gv = gm.vertices; var gt = gm.GetTriangles(gk);
                b = new Bounds(gr.transform.TransformPoint(gv[gt[0]]), Vector3.zero);
                foreach (var i in gt) b.Encapsulate(gr.transform.TransformPoint(gv[i]));
            }
            else b = BoundsOf(body.transform, glass);
            lamps[key] = (new Vector3(b.center.x, b.center.y, front ? b.max.z + 0.003f : b.min.z - 0.003f), Mathf.Min(b.size.x, b.size.y) * 0.95f, front);
            Line($"  lamp {key,-4} glass {glass}: {V(b.center)} size {V(b.size)} -> lens {V(lamps[key].c)} dia {lamps[key].d:F3}");
        }

        var hl = new GameObject("[headlights]").transform;
        hl.SetParent(R, false);
        var main = Add(hl.gameObject, "CCL.Types.Proxies.Headlights.HeadlightsMainControllerProxy");
        var opt = Add(hl.gameObject, "CCL.Types.Proxies.Headlights.CarLightsOptimizerProxy");
        var beams = Add(hl.gameObject, "CCL.Types.Proxies.Headlights.HeadlightBeamControllerProxy");
        Set(beams, "headlightsMainController", main);
        Set(opt, "beamController", beams);
        Set(main, "headlightControlFrontId", Cfg.LightsFrontPort);
        Set(main, "headlightControlRearId", Cfg.LightsRearPort);
        Set(main, "powerFuseId", Fuse);

        var lightType = T("CCL.Creator.Utility.VanillaLight");
        var applyLight = T("CCL.Creator.Utility.VanillaLightCopy").GetMethod("ApplyProperties", BF, null, new[] { typeof(Light), lightType }, null);
        Light VanillaLight(Transform parent, string name, Vector3 pos, Vector3 euler, int kind)
        {
            var l = Child(parent, name, pos);
            l.localEulerAngles = euler;
            var light = l.gameObject.AddComponent<Light>();
            applyLight.Invoke(null, new object[] { light, Enum.ToObject(lightType, kind) });
            return light;
        }
        int n = 0;
        Component Lamp(Transform side, string key, string kind)
        {
            var (c, d, front) = lamps[key];
            var h = new GameObject($"Headlights{key}{kind}").transform;
            h.SetParent(side, false);
            h.SetPositionAndRotation(c + (front ? Vector3.forward : Vector3.back) * (0.0005f * n++), Quaternion.LookRotation(front ? Vector3.forward : Vector3.back));
            var lens = Child(h, "lens", Vector3.zero);                  // disc front face is its +z = the lamp's outside
            lens.localScale = Vector3.one * d;
            lens.gameObject.AddComponent<MeshFilter>().sharedMesh = discMesh;
            var lr = lens.gameObject.AddComponent<MeshRenderer>();
            lr.sharedMaterial = off;
            lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            var hp = Add(h.gameObject, "CCL.Types.Proxies.Headlights.HeadlightProxy");
            Set(hp, "headlightRenderer", lr);
            Set(hp, "emissionMaterialLit", kind == "Red" ? litRed : lit);
            Set(hp, "emissionMaterialUnlit", off);
            hp.GetType().GetMethod("CreateDefaultGlare", BF).Invoke(hp, null);
            hp.GetType().GetMethod("CreateDefaultBeam", BF).Invoke(hp, null);
            hp.GetType().GetMethod("OnValidate", BF).Invoke(hp, null);   // copies beamData into the serialized fields
            return hp;
        }
        foreach (bool front in new[] { true, false })
        {
            var side = Child(hl, front ? "FrontSide" : "RearSide", Vector3.zero);
            var setups = Enumerable.Range(0, 6).Select(_ => side.gameObject.AddComponent(T("CCL.Types.Proxies.Headlights.HeadlightSetup"))).ToArray();
            var subs = Child(side, "SubControllers", Vector3.zero);
            string[] low = front ? Cfg.FrontLow : Cfg.RearLow;
            string[] high = front ? Cfg.FrontHigh : Cfg.RearHigh;
            string[] red = front ? Cfg.FrontRed : Cfg.RearRed;
            void Setup(int i, int setting, Component sub)
            {
                Set(setups[i], "setting", setting);
                Set(setups[i], "subControllers", sub ? new List<Object> { sub } : new List<Object>());
                Set(setups[i], "mainOffSetup", sub == null);
            }
            bool none = low.Length + high.Length + red.Length == 0;
            if (!none && low.Concat(high).Concat(red).Any(k => !lamps.ContainsKey(k))) { Warn("headlights: lamp lens missing for " + (front ? "front" : "rear")); none = true; }
            if (none)
            {
                // an end without lamps still needs its 6 setups: DV indexes them with round(port * (count - 1)), and an
                // empty array throws in HeadlightsMainController.Init (loco rear / tender front)
                for (int i = 0; i < 6; i++) { Setup(i, 0, null); Set(setups[i], "mainOffSetup", i == 0); }
                Set(main, front ? "headlightSetupsFront" : "headlightSetupsRear", setups.Cast<Object>().ToList());
                Line($"  {(front ? "front" : "rear")}: no lamps (6 off setups)");
                continue;
            }
            var first = lamps[high.Concat(low).Concat(red).First()].c;
            var anchor = new Vector3(0, first.y, first.z + (front ? 0.05f : -0.05f));
            var rot = front ? Vector3.zero : new Vector3(0, 180, 0);
            // light sources only where a sub-controller switches them (an unreferenced Light would stay on)
            var lightHigh = high.Length > 0 ? VanillaLight(side, "LightHigh", anchor, rot + new Vector3(1, 0, 0), 0) : null;
            var lightLow = low.Length > 0 ? VanillaLight(side, "LightLow", anchor, rot + new Vector3(8, 0, 0), 1) : null;
            Light redLight = null;
            if (red.Length > 0)
            {
                redLight = Child(side, "RedLight", anchor).gameObject.AddComponent<Light>();
                redLight.type = LightType.Point; redLight.range = 4f; redLight.intensity = 1f; redLight.color = new Color(1f, 0.1f, 0.05f); redLight.shadows = LightShadows.None;
            }
            Component Sub(string name, string[] keys, string kind, Light light)
            {
                var s = Add(Child(subs, name, Vector3.zero).gameObject, "CCL.Types.Proxies.Headlights.HeadlightsSubControllerStandardProxy");
                Set(s, "isFront", front);
                Set(s, "multipleUnityDependent", 0);   // None: this loco has no MU cable (Front/Rear -> NRE in HoseConnectionAllowsHeadlights, aborts sim init)
                Set(s, "headlights", keys.Select(k => (Object)Lamp(side, k, kind)).ToList());
                Set(s, "lightSources", new List<Object> { light });
                return s;
            }
            var sHigh = high.Length > 0 ? Sub("WhiteHigh", high, "High", lightHigh) : null;
            var sLow = low.Length > 0 ? Sub("WhiteLow", low, "Low", lightLow) : null;
            var sRed = red.Length > 0 ? Sub("Red", red, "Red", redLight) : null;
            // index 0 must be the main off setup: HeadlightsMainController.Init applies the port value (0) before the sub-controllers
            // are initialised, and any sub-controller there throws and aborts the whole sim init (test6/7)
            Setup(0, 0, null); Setup(1, 1, sRed); Setup(2, 0, null); Setup(3, 1, sLow); Setup(4, 2, sLow ?? sHigh); Setup(5, 3, sHigh ?? sLow);
            for (int i = 1; i < 6; i++) Set(setups[i], "mainOffSetup", false);   // only index 0 is the main off setup
            Set(main, front ? "headlightSetupsFront" : "headlightSetupsRear", setups.Cast<Object>().ToList());
            Line($"  {(front ? "front" : "rear")}: low [{string.Join(",", low)}], high [{string.Join(",", high)}], red [{string.Join(",", red)}], lights at {V(anchor)}");
        }

        // cab light: new sim control 'cabLight' (like the 4-6-2T's), bulb under the cab roof, same dynamo fuse
        if (Cfg.CabLightProbe == null) return;
        var probe = Cfg.CabLightProbe.Value;
        var sim = R.Find("[sim]");
        var clGo = new GameObject("cabLight");
        clGo.transform.SetParent(sim, false);
        var ecd = Add(clGo, "CCL.Types.Proxies.Controls.ExternalControlDefinitionProxy");
        Set(ecd, "ID", "cabLight"); Set(ecd, "defaultValue", 0f); Set(ecd, "saveState", true);
        var conn = sim.GetComponent(T("CCL.Types.Proxies.Ports.SimConnectionsDefinitionProxy"));
        var order = (IList)conn.GetType().GetField("executionOrder").GetValue(conn); if (!order.Contains(ecd)) order.Add(ecd);
        float ceiling = Probe(body, probe, Vector3.up, 2f, h => h.point.y, probe.y + 1f);
        var cab = new GameObject("[cab lights]").transform;
        cab.SetParent(R, false);
        var bulb = Child(cab, "bulb", new Vector3(probe.x, ceiling - 0.02f, probe.z));
        bulb.localRotation = Quaternion.Euler(90, 0, 0);    // disc front face (+z) downwards
        bulb.localScale = Vector3.one * 0.07f;
        bulb.gameObject.AddComponent<MeshFilter>().sharedMesh = discMesh;
        var bulbR = bulb.gameObject.AddComponent<MeshRenderer>();
        var bulbOff = ColMat("cab_bulb_off", new Color(0.75f, 0.72f, 0.65f), 0.8f);
        bulbR.sharedMaterial = bulbOff;
        var cabLight = VanillaLight(cab, "Point Light", bulb.localPosition + Vector3.down * 0.1f, Vector3.zero, 105);
        // DV's CabLightsController.Init adds an ItemLight and sets its light only after AddComponent, so ItemLight.Awake logs
        // "needs light assigned" and throws in ItemLightOptimizer.RemoveLight; with one already there DV uses it as is
        Set(Add(cabLight.gameObject, "CCL.Types.Proxies.VFX.ItemLightProxy"), "light", cabLight);
        if (cabLight.GetComponents<Component>().Any(c => c.GetType().Name == "LightShadowQualityProxy")) Warn("cab light has LightShadowQuality: incompatible with ItemLight");
        var clc = Add(cab.gameObject, "CCL.Types.Proxies.Controllers.CabLightsControllerProxy");
        Set(clc, "controlId", "cabLight.EXT_IN");
        Set(clc, "powerFuseId", Fuse);
        Set(clc, "lightsLit", lit); Set(clc, "lightsUnlit", bulbOff);
        Set(clc, "lights", new List<Object> { cabLight.gameObject });
        Set(clc, "lightRenderers", new List<Object> { bulbR });
        Set(clc, "lightsOnControlThreshold", 0.5f);
        Set(opt, "cabLights", new List<Object> { cab.gameObject });
        Line($"  cab light: sim control cabLight (execution order {((IList)conn.GetType().GetField("executionOrder").GetValue(conn)).Count} components), bulb at {V(bulb.localPosition)} (ceiling y {ceiling:F3})");
    }

    // RR AggregateLoadModel (procedural coal slab in the bunker) -> coal box scaled by the coal level
    static void BuildCoalLoad(GameObject body)
    {
        var cl = Cfg.CoalLoad;
        var pivot = new GameObject("[coal load]").transform;
        pivot.SetParent(body.transform, false);
        var scaler = Child(pivot, "scaler", Vector3.zero);
        var box = Child(scaler, "coal", Vector3.zero);
        if (cl.Pivot.HasValue)
        {
            // explicit box from the RR keyframes: bottom at the empty surface, full height = top surface when full
            pivot.localPosition = cl.Pivot.Value;
            box.localScale = new Vector3(cl.Footprint.x, cl.FullHeight, cl.Footprint.y);
        }
        else
        {
            var c = Comp(cl.Comp);
            var bunker = body.transform.Find(cl.BunkerPart).GetComponent<Renderer>().bounds;
            pivot.localPosition = new Vector3(0, c.pos.y, bunker.center.z);
            box.localScale = new Vector3(bunker.size.x - 0.08f, cl.FullHeight, bunker.size.z - 0.08f);
        }
        box.gameObject.AddComponent<MeshFilter>().sharedMesh = boxMesh;
        box.gameObject.AddComponent<MeshRenderer>().sharedMaterial = ownMats["coal"];
        var s = Add(scaler.gameObject, "CCL.Types.Proxies.Indicators.IndicatorScalerProxy");
        Set(s, "indicatorToScale", scaler);
        Set(s, "minValue", 0f); Set(s, "maxValue", CoalCapacity);
        Set(s, "startScale", new Vector3(1, Cfg.CoalLoad.EmptyFraction, 1)); Set(s, "endScale", Vector3.one);
        Set(s, "scaleFromModel", false);
        var rd = Add(scaler.gameObject, "CCL.Types.Proxies.Indicators.IndicatorPortReaderProxy");
        Set(rd, "portId", "coal.AMOUNT");
        Set(rd, "valueMultiplier", 1f);
        Line($"coal load at {V(pivot.localPosition)} box {V(box.localScale)} (scaled {cl.EmptyFraction}..1 with coal.AMOUNT 0..{CoalCapacity:F0} kg)");
    }

    static void PlaceParticles(Transform particles)
    {
        if (!particles) { Warn("no [particles] created"); return; }
        var chimney = Comp(Cfg.ChimneyComp).pos + new Vector3(0, 0.05f, 0);
        var cc = Components.Where(x => x.kind == "CylinderCock").OrderByDescending(x => x.pos.z).ToArray(); // front, rear (RR: right side)
        // Mallet: one RR anchor per engine; single engine: one anchor at the cylinder front, rear drains one cylinder length back
        Vector3 ccF = cc[0].pos, ccR = cc.Length > 1 ? cc[1].pos : cc[0].pos + new Vector3(0, 0, -Cfg.CylinderLength);
        var whistle = Comp(Cfg.WhistleComp).pos + new Vector3(0, 0.12f, 0);
        var safety = Cfg.SafetyPos ?? BoundsOf(RefBody, Cfg.SafetyValvePart).center + new Vector3(0, 0.3f, 0);
        foreach (var t in particles.GetComponentsInChildren<Transform>(true))
        {
            if (t == particles) continue;
            bool placeable = t.parent == particles || (t.parent.parent == particles && t.parent.name.StartsWith("CylCock"));
            if (!placeable) continue;
            string n = t.name;
            Vector3? p = null; Quaternion? rot = null;
            if (n.Contains("Smoke") || n.Contains("Ember") || n.StartsWith("SteamExhaust") || n.Contains("Blowback")) p = chimney;
            else if (n.Contains("CylCock"))
            {
                bool rearUnit = n.Contains("R") && (n.EndsWith("RL") || n.EndsWith("RR"));
                var src = rearUnit ? ccR : ccF;
                bool left = n.EndsWith("L");
                p = new Vector3(left ? -Mathf.Abs(src.x) : Mathf.Abs(src.x), src.y, src.z);
                rot = Quaternion.Euler(0, left ? -90 : 90, 0);
            }
            else if (n == "Whistle") p = whistle;
            else if (n.Contains("Safety")) p = safety;
            else if (n == "Blowdown") { p = Cfg.BlowdownPos; rot = Quaternion.Euler(90, 0, 0); }
            else if (n.Contains("Dynamo")) p = Cfg.DynamoPos;
            else if (n.Contains("Crack") || n.Contains("Leak")) p = Cfg.CrackPos;
            if (p.HasValue) { t.position = p.Value; if (rot.HasValue) t.rotation = rot.Value; }
            Line($"  particle {PathOf(t, particles)} -> {V(t.position)}");
        }
        if (Cfg.FourCylinderCocks) RebuildCylinderCocks(particles, ccF, ccR);
    }

    // The CCL steam template drives the drain jets for 2 cylinders; the sim runs 4 (cylinder i leads by i/4 of a turn).
    // One setup per cylinder (0/1 = front engine L/R, 2/3 = rear engine L/R), each with a front-end and rear-end jet,
    // using DV's own S282 activity curves stepped by 90 degrees per cylinder (S282: cyl0 270/90, cyl1 0/180).
    static void RebuildCylinderCocks(Transform particles, Vector3 ccF, Vector3 ccR)
    {
        var readerType = T("CCL.Types.Proxies.VFX.CylinderCockParticlePortReaderProxy");
        var reader = particles.GetComponentsInChildren(readerType, true).FirstOrDefault();
        var group = particles.Find("CylCockSteam");
        var template = group ? group.Find("CylCockSteam FL") : null;
        if (reader == null || !template) { Warn("cylinder cocks: CCL reader or CylCockSteam FL not found"); return; }
        var old = group.Cast<Transform>().ToList();
        AnimationCurve Curve(string n) => (AnimationCurve)readerType.GetProperty(n, BF).GetValue(null);
        string[] front = { "Curve270", "Curve0", "Curve90", "Curve180" }, rear = { "Curve90", "Curve180", "Curve270", "Curve0" };
        var setupType = readerType.GetNestedType("CylinderSetup");
        var setups = Array.CreateInstance(setupType, 4);
        for (int i = 0; i < 4; i++)
        {
            bool left = i % 2 == 0;
            var src = i < 2 ? ccF : ccR;
            var at = new Vector3(left ? -Mathf.Abs(src.x) : Mathf.Abs(src.x), src.y, src.z);
            GameObject Jet(string end, float dz)
            {
                var g = Object.Instantiate(template.gameObject, group);
                g.name = $"CylCockSteam C{i} {end}";
                g.transform.SetPositionAndRotation(at + new Vector3(0, 0, dz), Quaternion.Euler(0, left ? -90 : 90, 0));
                return g;
            }
            var s = Activator.CreateInstance(setupType);
            setupType.GetField("frontParticlesParent").SetValue(s, Jet("front", 0.35f));
            setupType.GetField("frontActivityCurve").SetValue(s, Curve(front[i]));
            setupType.GetField("rearParticlesParent").SetValue(s, Jet("rear", -0.35f));
            setupType.GetField("rearActivityCurve").SetValue(s, Curve(rear[i]));
            setups.SetValue(s, i);
        }
        readerType.GetField("cylinderSetups").SetValue(reader, setups);
        readerType.GetMethod("OnValidate", BF).Invoke(reader, null);
        foreach (var o in old) Object.DestroyImmediate(o.gameObject);
        Line($"  cylinder cocks: 4 cylinders x 2 drain jets (front engine z {ccF.z:F2}, rear engine z {ccR.z:F2}), DV S282 curves stepped 90 deg");
    }

    // ------------------------------------------------------------------ step 3: interior (gauges + firebox)
    // RR spawns its own gauge prefabs (Gauge / PrefabControl SightGlass) at runtime; DV substitutes built here.
    static void BuildInterior()
    {
        Section("Interior prefab (DV gauges, sight glasses, firebox)");
        var I = new GameObject(CarId + "_interior");
        var reader = Add(I, "CCL.Types.Proxies.Controls.LocoIndicatorReaderProxy");
        var body = RefBody.gameObject;

        bool haveSpeed = false, haveChest = false;
        foreach (var g in Components.Where(c => c.kind == "Gauge"))
        {
            string style = Extra(g, "style");
            float dia = 0.19f * g.scale.x;
            var gauge = new GameObject("gauge " + g.name).transform;
            gauge.SetParent(I.transform, false);
            gauge.SetPositionAndRotation(g.pos, g.rot);
            var face = Child(gauge, "face", new Vector3(0, 0, 0.002f));
            face.localScale = Vector3.one * dia;
            face.gameObject.AddComponent<MeshFilter>().sharedMesh = discMesh;
            string dial = style == "BoilerPressure" ? "dial_pressure" : style.StartsWith("Speedometer") ? "dial_speed" : "dial_brake";
            face.gameObject.AddComponent<MeshRenderer>().sharedMaterial = ownMats[dial];
            var glass = Child(gauge, "glass", new Vector3(0, 0, 0.012f));
            glass.localScale = Vector3.one * dia;
            glass.gameObject.AddComponent<MeshFilter>().sharedMesh = discMesh;
            glass.gameObject.AddComponent<MeshRenderer>().sharedMaterial = ownMats["gauge_glass"];

            // every indicator the HUD shows must be referenced by the LocoIndicatorReader (test1: HUD showed placeholders)
            Component G(Transform n) => n.GetComponent(T("CCL.Types.Proxies.Indicators.IndicatorGaugeProxy"));
            if (style == "BoilerPressure" && g.name == Cfg.MainPressureGauge)
            {
                var n = GaugeNeedle(gauge, "needle", dia, 0f, 20f, "needle_black", 0.006f);
                PortReader(n.gameObject, "boiler.PRESSURE");
                Set(reader, "steam", G(n));
            }
            else if (style == "BoilerPressure")
            {
                // RR's second boiler gauge (right side) becomes DV's steam-chest pressure gauge
                var n = GaugeNeedle(gauge, "needle", dia, 0f, 20f, "needle_black", 0.006f);
                PortReader(n.gameObject, "steamEngine.STEAM_CHEST_PRESSURE");
                Set(reader, "chestPressure", G(n)); haveChest = true;
            }
            else if (style.StartsWith("Speedometer"))
            {
                var n = GaugeNeedle(gauge, "needle", dia, 0f, 100f, "needle_black", 0.006f);
                PortReader(n.gameObject, "traction.WHEEL_SPEED_KMH_EXT_IN");
                Set(reader, "speed", G(n)); haveSpeed = true;
            }
            else if (style == "DualBrakeCylinderLine")
            {
                var red = GaugeNeedle(gauge, "needle cylinder", dia, 0f, 10f, "needle_red", 0.006f);
                Add(red.gameObject, "CCL.Types.Proxies.Indicators.IndicatorBrakeCylinderReaderProxy");
                Set(reader, "brakeCylinder", G(red));
                var blk = GaugeNeedle(gauge, "needle pipe", dia, 0f, 10f, "needle_black", 0.008f);
                Add(blk.gameObject, "CCL.Types.Proxies.Indicators.IndicatorBrakePipeReaderProxy");
                Set(reader, "brakePipe", G(blk));
            }
            else if (style == "DualReservoirMainEq")
            {
                var red = GaugeNeedle(gauge, "needle main res", dia, 0f, 10f, "needle_red", 0.006f);
                Add(red.gameObject, "CCL.Types.Proxies.Indicators.IndicatorBrakeReservoirReaderProxy");
                Set(reader, "mainReservoir", G(red));
                var blk = GaugeNeedle(gauge, "needle eq (pipe)", dia, 0f, 10f, "needle_black", 0.008f);
                Add(blk.gameObject, "CCL.Types.Proxies.Indicators.IndicatorBrakePipeReaderProxy");
            }
            else if (style == "Quadruplex")
            {
                // RR 4-needle driver's brake gauge: main reservoir (red) and brake pipe (black); the HUD reads the dual gauges
                var red = GaugeNeedle(gauge, "needle main res", dia, 0f, 10f, "needle_red", 0.006f);
                Add(red.gameObject, "CCL.Types.Proxies.Indicators.IndicatorBrakeReservoirReaderProxy");
                var blk = GaugeNeedle(gauge, "needle pipe", dia, 0f, 10f, "needle_black", 0.008f);
                Add(blk.gameObject, "CCL.Types.Proxies.Indicators.IndicatorBrakePipeReaderProxy");
            }
            else Warn("unknown RR gauge style " + style);
            var near = NearestRenderer(body, g.pos, 0.25f);
            Line($"  gauge {g.name,-6} {style,-22} at {V(g.pos)} dia {dia:F3} (RR scale {g.scale.x}); nearest model part {near}");
        }

        // HUD readers with no RR instrument (a Mogul has no speedometer or steam-chest gauge): invisible gauges on the same ports
        foreach (var (field, port, max, have) in new[] { ("speed", "traction.WHEEL_SPEED_KMH_EXT_IN", 100f, haveSpeed), ("chestPressure", "steamEngine.STEAM_CHEST_PRESSURE", 20f, haveChest) })
        {
            if (have) continue;
            var hg = Child(I.transform, "HUD-only " + field, Vector3.zero);
            var g2 = Add(hg.gameObject, "CCL.Types.Proxies.Indicators.IndicatorGaugeProxy");
            Set(g2, "needle", hg); Set(g2, "minValue", 0f); Set(g2, "maxValue", max);
            Set(g2, "minAngle", -135f); Set(g2, "maxAngle", 135f); Set(g2, "rotationAxis", Vector3.forward);
            PortReader(hg.gameObject, port);
            Set(reader, field, g2);
            Line($"  HUD-only gauge for {field} ({port}): the model has no instrument for it");
        }

        // RR SightGlass prefabs: water columns in the model's gauge-glass frames, scaled by the boiler water level
        bool firstGlass = true;
        foreach (var sg in Components.Where(c => c.kind == "PrefabControl" && Extra(c, "prefab") == "SightGlass"))
        {
            float h = 0.30f * sg.scale.y;
            var col = new GameObject("sight glass " + sg.name).transform;
            col.SetParent(I.transform, false);
            col.localPosition = sg.pos - new Vector3(0, h / 2, 0.01f);
            var scaler = Child(col, "scaler", Vector3.zero);
            var water = Child(scaler, "water", Vector3.zero);
            water.localScale = new Vector3(0.022f, h, 0.022f);
            water.gameObject.AddComponent<MeshFilter>().sharedMesh = boxMesh;
            water.gameObject.AddComponent<MeshRenderer>().sharedMaterial = ownMats["water_column"];
            var s = Add(scaler.gameObject, "CCL.Types.Proxies.Indicators.IndicatorScalerProxy");
            Set(s, "indicatorToScale", scaler);
            Set(s, "minValue", 0f); Set(s, "maxValue", 1f);
            Set(s, "startScale", new Vector3(1, 0, 1)); Set(s, "endScale", Vector3.one);
            Set(s, "scaleFromModel", false);
            PortReader(scaler.gameObject, "boiler.WATER_LEVEL_NORMALIZED");
            if (firstGlass) Set(reader, "locoWaterLevel", s);
            firstGlass = false;
            Line($"  sight glass {sg.name}: column {h:F3} m from y {col.localPosition.y:F3}; nearest model part {NearestRenderer(body, sg.pos, 0.2f)}");
        }

        var fireboxScaler = BuildFirebox(I, body);
        Set(reader, "locoCoalLevel", fireboxScaler);

        // HUD-only readings with no cab instrument (same ports as the working CCL 4-6-2T); a tender loco reads the tender's
        // coal/water through its tenderWater/tenderCoal ports (fed over the coupling, as the CCL LMS 8F)
        var hud = Child(I.transform, "Indicators (HUD only)", Vector3.zero);
        string w = Cfg.Tender != null ? "tenderWater" : "water", co = Cfg.Tender != null ? "tenderCoal" : "coal";
        foreach (var (field, port, range, max) in new[] {
            ("fireTemperature", "firebox.TEMPERATURE", "", 2000f),
            ("tenderWaterLevel", w + ".NORMALIZED", w + ".CAPACITY", 1f),
            ("tenderCoalLevel", co + ".NORMALIZED", co + ".CAPACITY", 1f),
            ("sand", "sand.NORMALIZED", "sand.CAPACITY", 1f),
            ("oil", "oil.NORMALIZED", "oil.CAPACITY", 1f),
            ("transmissionOil", "lubricator.LUBRICATION_NORMALIZED", "", 1f) })
        {
            var t = Child(hud, field, Vector3.zero);
            var dummy = Child(t, "dummy", Vector3.zero);
            var s = Add(t.gameObject, "CCL.Types.Proxies.Indicators.IndicatorScalerProxy");
            Set(s, "indicatorToScale", dummy);
            Set(s, "minValue", 0f); Set(s, "maxValue", max);
            Set(s, "startScale", Vector3.one); Set(s, "endScale", Vector3.one);
            Set(s, "scaleFromModel", false);
            PortReader(t.gameObject, port, range);
            Set(reader, field, s);
        }
        Line("  HUD indicators: steam, chest, speed, brake pipe/cylinder/main res, boiler water, firebox coal + HUD-only fire temp, tank water, bunker coal, sand, oil, lubrication");

        BuildControls(I);

        string path = $"{carFolder}/{CarId}_interior.prefab";
        PrefabUtility.SaveAsPrefabAsset(I, path);
        DumpHierarchy(I, "interior", 2);
        Object.DestroyImmediate(I);
    }

    // ------------------------------------------------------------------ interior controls
    // The HUD and keyboard only work through real interior controls (LocoControlsReader + InteractablePortFeeders).
    // RR's own cab handles become DV levers; DV-only controls get simple generated handwheels/levers on the cab walls.
    static void BuildControls(GameObject I)
    {
        Section("Interior controls");
        var root = Child(I.transform, "Controls", Vector3.zero);
        var lcr = Add(I, "CCL.Types.Proxies.Controls.LocoControlsReaderProxy");

        // ControlControlsWizard.ControlType: 0 throttle, 1 reverser, 2 train brake, 3 ind brake, 5 brake cutout, 10 headlights front,
        // 12 cab lights, 13 sander, 14 horn, 17 injector, 18 blowdown, 19 blower, 20 damper, 21 firebox door, 22 cyl cocks,
        // 23 compressor, 24 dynamo, 25 lubricator
        // Joint physics follow the working CCL 4-6-2T: stepped joint + holding spring. test2 had useSteppedJoint off, which in DV
        // makes a spring-return control (LeverBase resets the spring target to 0 on release), so everything snapped back.
        // RR cab handles (and port-less hinged parts like doors): axis/range from their RR clips, physics from the config
        var byPort = new Dictionary<string, GameObject>();
        void Keep(string port, GameObject go) { if (go && port != null) byPort[port] = go; }
        foreach (var l in Cfg.RrLevers.Where(l => !l.External)) Keep(l.Port, RrLever(root, l));   // test1: RR levers were missing from the HUD reader

        // RR mesh-island fittings and generated fittings on the backhead, each with a DV name plate
        foreach (var f in Cfg.Fittings) Keep(f.Port, RrWheel(root, f, f.Port, f.Ctl, f.Toggle, f.Notches, f.Label));
        foreach (var p in Cfg.Placed) Keep(p.Port, Place(root, p.Name, p.X, p.Y, p.Wheel, p.Port, p.Ctl, p.Toggle, p.Notches, p.Label, p.Range, p.Phys));

        foreach (var kv in new Dictionary<string, string> {
            { "cylCock", "cylinderCock.EXT_IN" }, { "injector", "injector.EXT_IN" }, { "firedoor", "fireboxDoor.EXT_IN" },
            { "blower", "blower.EXT_IN" }, { "damper", "damper.EXT_IN" }, { "blowdown", "blowdown.EXT_IN" },
            { "coalDump", "coalDumpControl.EXT_IN" }, { "lubricator", "lubricatorControl.EXT_IN" },
            { "headlightsFront", "headlightDecoder.HEADLIGHTS_EXT_IN" }, { "cabLight", "cabLight.EXT_IN" }, { "bell", "bellControl.EXT_IN" } })
            if (byPort.TryGetValue(kv.Value, out var g) && g) Set(lcr, kv.Key, g);
        Line("  LocoControlsReader: " + string.Join(", ", new[] { "cylinderCock.EXT_IN", "injector.EXT_IN", "fireboxDoor.EXT_IN", "blower.EXT_IN", "damper.EXT_IN", "blowdown.EXT_IN", "coalDumpControl.EXT_IN", "lubricatorControl.EXT_IN", "headlightDecoder.HEADLIGHTS_EXT_IN", "cabLight.EXT_IN", "bellControl.EXT_IN" }.Select(p => byPort.ContainsKey(p) ? p.Split('.')[0] : "(" + p.Split('.')[0] + " MISSING)")));
        SweepCheck(root);
        Line("  not built: bell / wipers (the model has neither)");
    }

    // Control rigidbodies collide with each other (test8 RBBM: regulator jammed at 25%; GN M-2 test1: throttle stopped at 60%,
    // Johnson bar short of full forward, whistle not returning). Sweep every lever's grip box through its joint range and
    // warn where it meets another control's box at rest.
    static void SweepCheck(Transform controls)
    {
        var cols = controls.GetComponentsInChildren<BoxCollider>(true).Where(b => b.name == "collider" && b.gameObject.activeInHierarchy).ToList();
        Physics.SyncTransforms();
        int hits = 0;
        foreach (var col in cols)
        {
            var c = col.transform.parent;
            var spec = c.GetComponents<Component>().FirstOrDefault(x => x.GetType().Name == "LeverProxy");
            if (spec == null) continue;
            var axis = c.rotation * Get<Vector3>(spec, "jointAxis");
            float min = Get<float>(spec, "jointLimitMin"), max = Get<float>(spec, "jointLimitMax");
            var blocked = new SortedDictionary<string, List<float>>();
            for (int i = 0; i <= 16; i++)
            {
                float a = Mathf.Lerp(min, max, i / 16f);
                var q = Quaternion.AngleAxis(a, axis);
                var pos = c.position + q * (col.transform.position - c.position);
                var rot = q * col.transform.rotation;
                foreach (var other in cols)
                {
                    if (other == col || other.transform.parent == c) continue;
                    if (Physics.ComputePenetration(col, pos, rot, other, other.transform.position, other.transform.rotation, out _, out float d) && d > 0.002f)
                    {
                        string key = other.transform.parent.name;
                        if (!blocked.ContainsKey(key)) blocked[key] = new List<float>();
                        blocked[key].Add(a);
                    }
                }
            }
            foreach (var kv in blocked)
            {
                hits++;
                Warn($"control sweep: {c.name} (0..{max:F0} deg) meets {kv.Key} at {string.Join(", ", kv.Value.Select(a => a.ToString("F0")))} deg");
            }
            // the cab's own RR colliders (they become [walkable]/[items]): reported, not warned - whether DV lets a control
            // hit them depends on its layer matrix
            var cab = new SortedDictionary<string, List<float>>();
            foreach (var rc in RefBody.GetComponentsInChildren<Collider>(true).Where(x => x.enabled && x.gameObject.activeInHierarchy))
                for (int i = 0; i <= 16; i++)
                {
                    float a = Mathf.Lerp(min, max, i / 16f);
                    var q = Quaternion.AngleAxis(a, axis);
                    if (Physics.ComputePenetration(col, c.position + q * (col.transform.position - c.position), q * col.transform.rotation,
                        rc, rc.transform.position, rc.transform.rotation, out _, out float d) && d > 0.002f)
                    { if (!cab.ContainsKey(rc.name)) cab[rc.name] = new List<float>(); cab[rc.name].Add(a); }
                }
            foreach (var kv in cab) Line($"  control sweep (cab collider): {c.name} (0..{max:F0} deg) meets RR {kv.Key} at {string.Join(", ", kv.Value.Select(a => a.ToString("F0")))} deg");
        }
        Line($"  control sweep: {cols.Count} control colliders, {hits} clashes");
    }

    // LeverProxy joint set-up. notches 0 = free joint whose spring returns it to 0 on release (whistle).
    public static void Phys(Component s, float min, float max, int notches, float spring, float damper, float mass, float drag, float angDrag, float scroll, float scrollSpring)
    {
        Set(s, "useLimits", true); Set(s, "jointLimitMin", min); Set(s, "jointLimitMax", Mathf.Min(max, 177f));
        Set(s, "useSteppedJoint", notches > 0); Set(s, "steppedValueUpdate", true);
        if (notches > 0) Set(s, "notches", notches);
        Set(s, "useSpring", true); Set(s, "jointSpring", spring); Set(s, "jointDamper", damper);
        Set(s, "rigidbodyMass", mass); Set(s, "rigidbodyDrag", drag); Set(s, "rigidbodyAngularDrag", angDrag);
        Set(s, "scrollWheelHoverScroll", scroll); Set(s, "scrollWheelSpring", scrollSpring);
    }

    // RR cab handle -> DV LeverProxy. The joint axis and range come from the RR clip (t=0 pose = value 0, clip end = value 1).
    // External levers (tender handbrake, filler lid) live in the external interactables prefab; Handbrake = HandbrakeFeeder.
    static GameObject RrLever(Transform parent, RrLeverCfg l)
    {
        string path = l.Path, port = l.Port; int ctl = l.Ctl; var phys = l.Phys; var clip = Clip(l.AnimKey);
        var src = RefBody.Find(path);
        if (!src) { Warn("cab handle not found: " + path); return null; }
        clip.SampleAnimation(RefBody.gameObject, 0f);
        var q0 = src.rotation;
        clip.SampleAnimation(RefBody.gameObject, clip.length);
        var q1 = src.rotation;
        clip.SampleAnimation(RefBody.gameObject, 0f);
        (q1 * Quaternion.Inverse(q0)).ToAngleAxis(out float ang, out Vector3 axis);
        if (ang > 180) { ang = 360 - ang; axis = -axis; }

        var rs = src.GetComponentsInChildren<Renderer>();
        var rb = rs[0].bounds; foreach (var r in rs) rb.Encapsulate(r.bounds);
        // hinge anchor on the rotation axis, moved along it next to the handle (Empty.046 sits 1.9 m off to the side)
        var pivot = src.position + axis * Vector3.Dot(rb.center - src.position, axis);
        var name = path == Cfg.ReverserHandle ? "Reverser" : src.name;
        var c = new GameObject("C_" + name).transform;
        c.SetParent(parent, false);
        c.position = pivot;
        var copy = Object.Instantiate(src.gameObject, c);
        copy.name = src.name;
        copy.transform.SetPositionAndRotation(src.position, q0);
        copy.transform.localScale = src.lossyScale;
        foreach (var col in copy.GetComponentsInChildren<Collider>(true)) Object.DestroyImmediate(col);
        foreach (var mb in copy.GetComponentsInChildren<MonoBehaviour>(true)) Object.DestroyImmediate(mb);
        ApplyMaterials(copy, quiet: true);

        // collider on the grip only: a whole-handle AABB (the regulator arm is 0.7 m long and diagonal) overlapped the valve
        // wheels, and the lever rigidbodies jammed against them (test8: regulator stopped at 25%)
        var gb = rb;
        if (l.Grip.HasValue) gb = new Bounds(l.Grip.Value, l.GripSize);   // explicit grip (long rods and cords: the heuristic takes the whole part)
        else if (port != null || l.Handbrake)
        {
            var pts = copy.GetComponentsInChildren<MeshFilter>().SelectMany(mf => mf.sharedMesh.vertices.Select(v => mf.transform.TransformPoint(v))).ToList();
            float Arm(Vector3 p) { var d = p - pivot; return (d - axis * Vector3.Dot(d, axis)).magnitude; }
            float far = pts.Max(Arm);
            var grip = pts.Where(p => Arm(p) > far - 0.10f).ToList();
            gb = new Bounds(grip[0], Vector3.zero); foreach (var p in grip) gb.Encapsulate(p);
        }
        var colGo = Child(c, "collider", c.InverseTransformPoint(gb.center));
        colGo.gameObject.AddComponent<BoxCollider>().size = Vector3.Max(gb.size, Vector3.one * 0.05f);
        var spec = Add(c.gameObject, "CCL.Types.Proxies.Controls.LeverProxy");
        Set(spec, "jointAxis", axis);
        phys(spec, ang);
        Interactable(c, colGo, spec, port, ctl, l.Toggle);
        if (l.Handbrake) Add(c.gameObject, "CCL.Types.Proxies.Controls.HandbrakeFeederProxy");   // DV adds the feeders controller
        if (l.Label != null) { var lb = Child(parent, "label " + l.Label.Substring(4), gb.center + new Vector3(0, -0.08f, 0)); var ll = Add(lb.gameObject, "CCL.Types.Proxies.Indicators.LabelLocalizer"); Set(ll, "key", l.Label); Set(ll, "ModelType", 2); }
        bool stepped = Get<bool>(spec, "useSteppedJoint");
        Line($"  lever {c.name,-24} {(l.Handbrake ? "(handbrake feeder)" : port ?? "(no port)"),-26} axis {V(axis)} 0..{ang:F1} deg, pivot {V(pivot)}, {(stepped ? Get<int>(spec, "notches") + " notches" : "spring return")}, grip box {V(gb.center)} size {V(gb.size)}{(l.Grip.HasValue ? " (config)" : "")}");
        return c.gameObject;
    }

    // RR backhead valve wheel (a mesh island cut out of a merged RR mesh; the exterior copy is removed in CutFittings) as a
    // DV handwheel turning 0..170 deg about the backhead normal (anticlockwise as seen from the cab = open).
    static GameObject RrWheel(Transform parent, FittingCfg f, string port, int ctl, bool toggle, int notches, string label)
    {
        var src = RefBody.Find(f.Part);
        if (!src) { Warn("backhead fitting part not found: " + f.Part); return null; }
        var (island, _, wb) = SplitIsland(src, f.Centre);
        var c = new GameObject("C_" + f.Name).transform;
        c.SetParent(parent, false);
        c.SetPositionAndRotation(wb.center, Quaternion.identity);
        var model = new GameObject($"{f.Part} ({f.Name})").transform;
        model.SetParent(c, false);
        model.SetPositionAndRotation(src.position, src.rotation);
        model.localScale = src.lossyScale;
        model.gameObject.AddComponent<MeshFilter>().sharedMesh = SaveMesh(island, "fitting_" + Safe(f.Name));
        model.gameObject.AddComponent<MeshRenderer>().sharedMaterials = src.GetComponent<MeshRenderer>().sharedMaterials;
        ApplyMaterials(model.gameObject, quiet: true);
        var colGo = Child(c, "collider", Vector3.zero);
        colGo.gameObject.AddComponent<BoxCollider>().size = wb.size + new Vector3(0.01f, 0.01f, 0.02f);
        var spec = Add(c.gameObject, "CCL.Types.Proxies.Controls.LeverProxy");
        Set(spec, "jointAxis", Vector3.forward);
        Phys(spec, 0, 170, notches, 60, 10, 20, 15, 0, 1, 0);
        Interactable(c, colGo, spec, port, ctl, toggle);
        Label(parent, label, wb.center.x, wb.min.y - 0.04f);
        Line($"  RR wheel {c.name,-19} {port,-28} at {V(wb.center)} size {V(wb.size)} ({f.Part} island, {island.triangles.Length / 3} tris), {notches} notches");
        return c.gameObject;
    }

    // Generated handwheel (0..170 deg about the backhead normal) or lever (tips 0..60 deg towards the cab) on the backhead at
    // (x, y): a ray along +z from inside the cab finds the plate; the control's +z points into it.
    static GameObject Place(Transform parent, string name, float x, float y, bool wheel, string port, int ctl, bool toggle, int notches, string label, float range = 0, Action<Component> phys = null)
    {
        var origin = new Vector3(x, y, Cfg.BackheadRayStartZ);   // in front of the plate, behind the cab stands
        if (!Raycast(RefBody.gameObject, origin, Vector3.forward, 1f, out var hit)) { Warn($"{name}: no backhead found from {V(origin)}"); return null; }
        var c = new GameObject("C_" + name).transform;
        c.SetParent(parent, false);
        c.SetPositionAndRotation(new Vector3(x, y, hit.point.z - (wheel ? 0.035f : 0.02f)), Quaternion.identity);
        var vis = Child(c, "model", Vector3.zero);
        vis.gameObject.AddComponent<MeshFilter>().sharedMesh = wheel ? wheelMesh : leverMesh;
        vis.gameObject.AddComponent<MeshRenderer>().sharedMaterial = wheel ? ownMats["brass"] : MatByName(Cfg.LeverMaterial);
        var colGo = Child(c, "collider", wheel ? Vector3.zero : new Vector3(0, 0.07f, -0.01f));
        colGo.gameObject.AddComponent<BoxCollider>().size = wheel ? new Vector3(0.11f, 0.11f, 0.03f) : new Vector3(0.04f, 0.16f, 0.04f);
        var spec = Add(c.gameObject, "CCL.Types.Proxies.Controls.LeverProxy");
        Set(spec, "jointAxis", wheel ? Vector3.forward : Vector3.left); // lever tips towards the cab (-z)
        if (phys != null) phys(spec);
        else if (wheel) Phys(spec, 0, range > 0 ? range : 170, notches, 60, 10, 20, 15, 0, 1, 0);
        else Phys(spec, 0, range > 0 ? range : 60, notches, 85, 15, 10, 15, 0, 1, 0);
        Interactable(c, colGo, spec, port, ctl, toggle);
        Label(parent, label, x, y - (wheel ? 0.075f : 0.035f));
        Line($"  {(wheel ? "wheel" : "lever")} {c.name,-22} {port,-34} at {V(c.position)} on {lastHitName}, {notches} notches");
        return c.gameObject;
    }

    // DV name plate (LabelLocalizer, 'Offset' model: plate on a 16 mm stalk along +z) fixed to the backhead below a control
    static void Label(Transform parent, string key, float x, float y)
    {
        if (key == null) return;
        float z = Raycast(RefBody.gameObject, new Vector3(x, y, Cfg.BackheadRayStartZ), Vector3.forward, 1f, out var hit) ? hit.point.z : Cfg.BackheadRayStartZ + 0.37f;
        var l = new GameObject("label " + key.Substring(4)).transform;
        l.SetParent(parent, false);
        l.SetPositionAndRotation(new Vector3(x, y, z - 0.016f), Quaternion.identity);
        var ll = Add(l.gameObject, "CCL.Types.Proxies.Indicators.LabelLocalizer");
        Set(ll, "key", key);
        Set(ll, "ModelType", 2);
    }

    static void Interactable(Transform c, Transform colGo, Component spec, string port, int ctl, bool toggle)
    {
        Set(spec, "colliderGameObjects", new List<Object> { colGo.gameObject });
        var ia = Object.Instantiate(colGo.gameObject, c);
        ia.name = "IA_" + c.name.Substring(2);
        ia.GetComponent<BoxCollider>().isTrigger = true;
        var sia = Add(ia, "CCL.Types.Proxies.Controls.StaticInteractionAreaProxy");
        ia.SetActive(false);
        Set(spec, "nonVrStaticInteractionArea", sia);
        if (spec.GetType().Name == "LeverProxy") Set(spec, "interactionPoint", ia.transform);
        if (port != null) Set(Add(c.gameObject, "CCL.Types.Proxies.Controls.InteractablePortFeederProxy"), "portId", port);
        if (ctl >= 0) AddInput(c.gameObject, ctl, 0, toggle);
    }

    static void AddInput(GameObject go, int controlType, int inputType, bool autoToggle)
    {
        var w = T("CCL.Creator.Wizards.ControlControlsWizard");
        var ct = Enum.ToObject(T("CCL.Creator.Wizards.ControlControlsWizard+ControlType"), controlType);
        var it = Enum.ToObject(T("CCL.Creator.Wizards.ControlControlsWizard+InputType"), inputType);
        try { w.GetMethod("AddInput", BF).Invoke(null, new object[] { go, ct, it, autoToggle, false }); }
        catch (Exception e) { Warn($"AddInput {go.name}: {(e.InnerException ?? e).Message}"); }
    }

    static Material MatByName(string n) => matMap.Values.FirstOrDefault(m => m.name == n) ?? ownMats["needle_black"];

    // [interior LOD]: render-only copy of the interior (gauges, handles, controls) shown while the interior is unloaded
    static void BuildInteriorLOD()
    {
        Section("Interior LOD");
        string path = $"{carFolder}/{CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        Kill(root.transform.Find("[interior LOD]"));
        var lod = Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>($"{carFolder}/{CarId}_interior.prefab"), root.transform);
        lod.name = "[interior LOD]";
        foreach (var t in lod.GetComponentsInChildren<Transform>(true).Where(t => t.name.StartsWith("IA_") || t.name == "I_Firebox" || t.name == "FIRE FEED").ToList())
            if (t) Object.DestroyImmediate(t.gameObject);
        int removed = 0;
        for (int pass = 0; pass < 3; pass++)
            foreach (var c in lod.GetComponentsInChildren<Component>(true).ToList())
            {
                if (c == null || c is Transform || c is MeshFilter || c is MeshRenderer) continue;
                if (pass == 0 && !(c is MonoBehaviour)) continue;
                if (pass == 1 && (c is Collider || c is Light)) continue;
                Object.DestroyImmediate(c, true); removed++;
            }
        var lodRenderers = lod.GetComponentsInChildren<Renderer>(true);
        foreach (var r in lodRenderers) r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        PrefabUtility.SaveAsPrefabAsset(root, path);
        PrefabUtility.UnloadPrefabContents(root);
        Line($"[interior LOD]: {lodRenderers.Length} renderers, {removed} components removed");
    }

    static Transform GaugeNeedle(Transform gauge, string name, float dia, float min, float max, string mat, float z)
    {
        var w = Child(gauge, name, new Vector3(0, 0, z));
        var m = Child(w, "mesh", Vector3.zero);
        m.localScale = Vector3.one * dia;
        m.gameObject.AddComponent<MeshFilter>().sharedMesh = needleMesh;
        m.gameObject.AddComponent<MeshRenderer>().sharedMaterial = ownMats[mat];
        var g = Add(w.gameObject, "CCL.Types.Proxies.Indicators.IndicatorGaugeProxy");
        Set(g, "needle", w);
        Set(g, "minValue", min); Set(g, "maxValue", max);
        Set(g, "minAngle", -135f); Set(g, "maxAngle", 135f);
        Set(g, "rotationAxis", Vector3.forward);
        w.localRotation = Quaternion.AngleAxis(-135f, Vector3.forward); // at rest until the sim sets a value
        return w;
    }

    static Component BuildFirebox(GameObject I, GameObject body)
    {
        // firebox sits inside the boiler barrel behind the backhead; fire door = RR 'Firebox Handle.001'
        // one-mesh bodies (G-29): explicit backhead plane and fire door centre instead of part bounds
        var backhead = Cfg.BackheadZ.HasValue ? new Bounds(new Vector3(0, 0, Cfg.BackheadZ.Value), Vector3.zero) : BoundsOf(body.transform, Cfg.FireboxBackheadPart);
        var door = Cfg.FireDoorCentre.HasValue ? new Bounds(Cfg.FireDoorCentre.Value, Vector3.zero) : BoundsOf(body.transform, Cfg.FireDoorPart);
        var floorZ = backhead.max.z;
        var fx = new GameObject("I_Firebox").transform;
        fx.SetParent(I.transform, false);
        float w = 1.0f, d = 1.4f;
        fx.localPosition = new Vector3(0, door.center.y - 0.45f, floorZ + d / 2 + 0.05f);
        Line($"firebox: backhead z {floorZ:F3}, door centre {V(door.center)} -> I_Firebox {V(fx.localPosition)}");

        var scaler = Child(fx, "scaler", Vector3.zero);
        var sc = Add(scaler.gameObject, "CCL.Types.Proxies.Indicators.IndicatorScalerProxy");
        Set(sc, "minValue", 0f); Set(sc, "maxValue", 150f);
        Set(sc, "indicatorToScale", scaler);
        Set(sc, "startScale", new Vector3(1, 0, 1)); Set(sc, "endScale", Vector3.one);
        Set(sc, "scaleFromModel", true);
        PortReader(scaler.gameObject, "firebox.COAL_LEVEL");
        var fire = Child(scaler, "fire", new Vector3(0, 0.1f, 0));
        var fcp = Add(fire.gameObject, "CCL.Types.Components.CopyVanillaParticleSystem");
        Set(fcp, "SystemToCopy", 200); Set(fcp, "AllowReplacing", true);
        var sparks = Child(fx, "sparks", new Vector3(0, 0.15f, 0));
        var sp = Add(sparks.gameObject, "CCL.Types.Components.CopyVanillaParticleSystem");
        Set(sp, "SystemToCopy", 201); Set(sp, "AllowReplacing", true);

        var coal = Child(fx, "Coal Collider", new Vector3(0, 0.2f, 0));
        var coalBox = coal.gameObject.AddComponent<BoxCollider>(); coalBox.isTrigger = true; coalBox.size = new Vector3(w, 0.4f, d);
        Layer(coal.gameObject, 12, false);
        Add(coal.gameObject, "CCL.Types.Proxies.Interaction.NonPhysicsCoalTargetProxy");
        Set(Add(coal.gameObject, "CCL.Types.Proxies.Controls.InteractablePortFeederProxy"), "portId", "firebox.COAL_CONTROL_EXT_IN");
        var vr = Child(fx, "Coal Collider VR Helper", new Vector3(0, 0.25f, -d / 2 + 0.2f));
        var vrBox = vr.gameObject.AddComponent<BoxCollider>(); vrBox.isTrigger = true; vrBox.size = new Vector3(w * 0.8f, 0.45f, 0.4f);
        Layer(vr.gameObject, 12, false);
        Add(vr.gameObject, "CCL.Types.Proxies.Interaction.NonPhysicsCoalTargetProxy");
        var ign = Child(fx, "ignition collider", new Vector3(0, 0.15f, 0));
        var sph = ign.gameObject.AddComponent<SphereCollider>(); sph.isTrigger = true; sph.radius = 0.3f;
        Layer(ign.gameObject, 26, false);
        Set(Add(ign.gameObject, "CCL.Types.Proxies.Controls.InteractablePortFeederProxy"), "portId", "firebox.IGNITION_EXT_IN");
        var lt = Child(fx, "light", new Vector3(0, 0.35f, 0));
        var fireLight = MakeLight(lt, 0.6f);   // stays inside the firebox: test8 lit the whole cab through the backhead
        var fill = MakeLight(Child(lt, "fill", new Vector3(0, 0, -d / 2)), 2.5f);
        var bounce = MakeLight(Child(lt, "bounce", new Vector3(0, -0.1f, -d / 2 - 0.3f)), 2f);
        var feed = Child(I.transform, "FIRE FEED", new Vector3(0, door.center.y, floorZ - 0.05f));
        var feedBox = feed.gameObject.AddComponent<BoxCollider>(); feedBox.isTrigger = true; feedBox.size = new Vector3(0.5f, 0.4f, 0.3f);
        var fp = Add(fx.gameObject, "CCL.Types.Proxies.FireProxy");
        Set(fp, "fireObj", fire.gameObject); Set(fp, "sparksObj", sparks.gameObject);
        Set(fp, "helperTriggerVR", vr.gameObject); Set(fp, "ignitionCollider", sph);
        Set(fp, "fireLight", fireLight); Set(fp, "minFireIntensity", 1f); Set(fp, "maxFireIntensity", 25f);
        Set(fp, "fillLight", fill); Set(fp, "fillLightMultiplier", 0f);
        Set(fp, "bounceLight", bounce); Set(fp, "bounceLightMultiplier", 0f);
        Layer(fx.gameObject, 13, true);
        var target = Add(fx.gameObject, "CCL.Types.Proxies.Interaction.ItemUseTargetProxy");
        Set(target, "targetColliders", new List<Object> { feedBox, sph, coalBox, vrBox });
        Set(Add(feed.gameObject, "CCL.Types.Proxies.Interaction.ItemUseRedirectProxy"), "target", target);
        return sc;
    }

    static Light MakeLight(Transform t, float range)
    {
        var l = t.gameObject.AddComponent<Light>();
        l.type = LightType.Point; l.range = range; l.intensity = 1f; l.color = new Color(1f, 0.55f, 0.2f); l.shadows = LightShadows.None;
        return l;
    }

    // ------------------------------------------------------------------ step 4: external interactables
    static void BuildInteractables()
    {
        Section("Interactables prefab");
        string path = $"{carFolder}/{CarId}_interactables.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        var body = RefBody;
        var smalls = root.transform.Cast<Transform>().Where(t => t.name == "[brake small]").ToList();
        for (int i = Cfg.HandbrakeWheel != null ? 1 : 0; i < smalls.Count; i++) Kill(smalls[i]);   // none: RR lever or no handbrake here
        if (Cfg.HandbrakeWheel == null) smalls.Clear();
        // DV handbrake wheel (freight template [brake small]): its axis is local z (hub towards +z) - point +z into the wall.
        if (smalls.Count > 0 && Cfg.HandbrakeWheel != null)
        {
            Line($"[brake small] template local rot {V(smalls[0].localEulerAngles)}");
            var (pos, euler) = Cfg.HandbrakeWheel(body);
            smalls[0].localRotation = Quaternion.Euler(euler);
            smalls[0].localPosition = pos;
        }
        // RR levers outside the cab (tender handbrake, filler lid)
        foreach (var l in Cfg.RrLevers.Where(l => l.External)) RrLever(root.transform, l);
        // brake-cylinder release: the template rod runs 1 m along its local +z (default orientation sticks out sideways)
        var release = root.transform.Find("[brake release]");
        if (release && Cfg.BrakeRelease != null)
        {
            Line($"[brake release] template local rot {V(release.localEulerAngles)}");
            var (pos, euler) = Cfg.BrakeRelease(body);
            release.localRotation = Quaternion.Euler(euler);
            release.localPosition = pos;
        }
        Line($"[brake small] {(smalls.Count > 0 ? V(smalls[0].localPosition) : "-")}, [brake release] {(release ? V(release.localPosition) : "-")}");

        // coal: shovel from the bunker opening in the cab back wall (RR Plane.015), or an explicit box (tender coal doors)
        if (Cfg.CoalPile != null || Cfg.CoalPileWallPart != null)
        {
            Vector3 centre, size;
            if (Cfg.CoalPile != null) (centre, size) = Cfg.CoalPile(body);
            else { var wall = BoundsOf(body, Cfg.CoalPileWallPart); centre = new Vector3(0, wall.min.y + 0.35f, wall.center.z - 0.1f); size = new Vector3(1.2f, 0.6f, 0.15f); }
            var coal = Child(root.transform, "Coal", centre);
            var trig = Child(coal, "pile_trigger", Vector3.zero);
            var tb = trig.gameObject.AddComponent<BoxCollider>(); tb.isTrigger = true; tb.size = size;
            Layer(trig.gameObject, 12, false);
            var shovel = Add(trig.gameObject, "CCL.Types.Proxies.Controls.ShovelCoalPileProxy");
            Set(shovel, "isInfinite", false); Set(shovel, "coalChunkMass", 48f);
            var player = Child(trig, "player", Vector3.zero);
            var pb = player.gameObject.AddComponent<BoxCollider>(); pb.isTrigger = true; pb.size = tb.size;
            Layer(player.gameObject, 22, false);
            Set(Add(trig.gameObject, "CCL.Types.Proxies.Interaction.ItemUseTargetProxy"), "targetColliders", new List<Object> { tb, pb });
            Line($"coal pile trigger at {V(coal.localPosition)} size {V(size)}");
        }

        // resource receivers at the RR LoadTarget components (coal over the bunker, water at the tank fillers)
        if (Cfg.CoalTargetComp != null)
        {
            var ct = Comp(Cfg.CoalTargetComp);
            var coalTarget = Child(root.transform, "Coal target", ct.pos + new Vector3(0, 0.15f, 0));
            coalTarget.gameObject.AddComponent<BoxCollider>().size = new Vector3(1.6f, 0.2f, 1.4f);
            Layer(coalTarget.gameObject, 15, false);
            Set(Add(coalTarget.gameObject, "CCL.Types.Proxies.Resources.LocoResourceReceiverProxy"), "resourceType", 21);
            Line($"coal target at {V(coalTarget.localPosition)} (RR LoadTarget {Cfg.CoalTargetComp})");
        }
        var water = Child(root.transform, "Water", Vector3.zero);
        foreach (var wc in Cfg.WaterTargetComps)
        {
            var t = Child(water, $"target ({wc})", Comp(wc).pos + new Vector3(0, 0.05f, 0));
            t.gameObject.AddComponent<BoxCollider>().size = new Vector3(0.7f, 0.15f, 0.7f);
            Layer(t.gameObject, 15, false);
            Set(Add(t.gameObject, "CCL.Types.Proxies.Resources.LocoResourceReceiverProxy"), "resourceType", 20);
            Line($"water target {wc} at {V(t.localPosition)} (RR LoadTarget)");
        }
        foreach (var lid in Cfg.WaterFillerParts)
        {
            var b = BoundsOf(body, lid);
            var t = Child(water, $"target ({lid})", b.center + new Vector3(0, 0.05f, 0));
            t.gameObject.AddComponent<BoxCollider>().size = new Vector3(0.6f, 0.12f, 0.6f);
            Layer(t.gameObject, 15, false);
            Set(Add(t.gameObject, "CCL.Types.Proxies.Resources.LocoResourceReceiverProxy"), "resourceType", 20);
            Line($"water target {lid} at {V(t.localPosition)}");
        }

        // oil cups: one per driving axlebox, under the side-tank edge (the axleboxes are inside the frames)
        var mops = Child(root.transform, "ManualOilingPoints", Vector3.zero);
        int idx = 0;
        foreach (var (tag, pos) in Cfg.OilPoints?.Invoke(RefBody) ?? Enumerable.Empty<(string, Vector3)>())
        {
            var cup = Child(mops, tag, pos);
            var mop = Add(cup.gameObject, "CCL.Types.Components.ManualOilingPoint");
            Set(mop, "SyncTag", tag);
            Set(mop, "CupModel", 0);
            idx++;
        }
        Line($"{idx} oil cups, synced to the body providers");
        PrefabUtility.SaveAsPrefabAsset(root, path);
        DumpHierarchy(root, "interactables", 2);
        PrefabUtility.UnloadPrefabContents(root);
    }

    // ------------------------------------------------------------------ step 5: sound (vanilla S060 systems at RR anchors)
    static GameObject BuildSound()
    {
        Section("Sound prefab");
        var root = new GameObject(CarId + "_Sound");
        var eng = Child(root.transform, "[sim] Engine", Vector3.zero);
        var chuffPos = Comp(Cfg.ChimneyComp).pos;
        var chuff = Add(Child(eng, "SteamChuffMain", chuffPos).gameObject, "CCL.Types.Components.CopyChuffSystem");
        Set(chuff, "LocomotiveType", Cfg.ChuffType);
        Set(chuff, "chuffEventPortId", "steamEngine.CHUFF_EVENT");
        Set(chuff, "exhaustPressurePortId", "steamEngine.EXHAUST_PRESSURE");
        Set(chuff, "chuffFrequencyPortId", "steamEngine.CHUFF_FREQUENCY");
        Set(chuff, "cylinderWaterNormalizedPortId", "steamEngine.WATER_IN_CYLINDERS_NORMALIZED");
        Set(chuff, "cylinderCockControlPortId", "cylinderCock.EXT_IN");
        Set(chuff, "ashesInPipesPortId", "steamEngine.ASHES_IN_PIPES");
        var cc = Components.Where(x => x.kind == "CylinderCock").OrderByDescending(x => x.pos.z).ToArray();
        Vector3 cab = Cfg.SndCab, cyl = Cfg.SndCylinders, wheels = Cfg.SndWheels, fire = Cfg.SndFire;
        var whistle = Comp(Cfg.WhistleComp).pos;
        var systems = new (string name, int sys, string p1, string p2, Vector3 pos)[]
        {
            ("Airpump", 3013, "compressor.PRODUCTION_RATE_NORMALIZED", "", Cfg.SndAirPump),
            ("Blowdown", 3004, "boiler.BLOWDOWN_FLOW_NORMALIZED", "", Cfg.BlowdownPos),
            ("CoalDump", 3000, "firebox.COAL_DUMP_FLOW_NORMALIZED", "", Cfg.SndCoalDump),
            ("CrownSheetBoiling", 3012, "boiler.CROWN_SHEET_TEMPERATURE_NORMALIZED", "boiler.IS_BROKEN", Cfg.SndCrownSheet),
            ("CylinderCock L", 3007, "steamEngine.CYLINDER_CRACK_FLOW_NORMALIZED", "", new Vector3(-cc[0].pos.x, cc[0].pos.y, cc[0].pos.z)),
            ("CylinderCock R", 3007, "steamEngine.CYLINDER_CRACK_FLOW_NORMALIZED", "", cc[0].pos),
            ("CylinderCrack", 3006, "steamEngine.CYLINDER_CRACK_FLOW_NORMALIZED", "", cyl),
            ("Dynamo", 3014, "dynamo.DYNAMO_FLOW_NORMALIZED", "", Cfg.DynamoPos),
            ("Fire", 3001, "firebox.COMBUSTION_RATE_NORMALIZED", "", fire),
            ("FireboxWind", 3002, "exhaust.AIR_FLOW", "", fire),
            ("Injector", 3008, "boiler.INJECTOR_FLOW_NORMALIZED", "", cab),
            ("Lubricator", 3017, "lubricator.LUBRICATION_RATE_NORMALIZED", "", cab),
            ("PrimingCrank", 3018, "lubricatorControlSmoothing.OUTPUT", "", cab),
            ("Sand", 0, "sander.SAND_FLOW", "", Cfg.SndSand),
            ("SteamChestAdmissionMain", 3005, "steamEngine.INTAKE_FLOW_NORMALIZED", "", cyl),
            ("SteamSafetyRelease", 3003, "boiler.SAFETY_VALVE_NORMALIZED", "", Cfg.SndSafety),
            ("ValveGearNoOil", 3011, "oilingPoints.LOWEST_OIL_LEVEL_AUDIO", "traction.WHEEL_RPM_EXT_IN", wheels),
            ("ValveGear", 3009, "steamEngine.CHUFF_FREQUENCY", "", wheels),
            ("ValveGearDamaged", 3010, "lubricator.LUBRICATION_AUDIO_NORMALIZED", "traction.WHEEL_RPM_EXT_IN", wheels),
            ("Whistle", Cfg.WhistleSystem,
            "exhaust.WHISTLE_FLOW_NORMALIZED", "", whistle),
        };
        var sysList = systems.ToList();
        if (Cfg.BellSound.HasValue)
        {
            sysList.Add(("BellRing", 3015, "bell.BELL_NORMALIZED", "", Cfg.BellSound.Value));
            sysList.Add(("BellPump", 3016, "bell.BELL_NORMALIZED", "", Cfg.BellSound.Value));
        }
        foreach (var s in sysList)
        {
            var c = Add(Child(eng, s.name, s.pos).gameObject, "CCL.Types.Components.CopyVanillaAudioSystem");
            Set(c, "AudioSystem", s.sys); Set(c, "PortId1", s.p1); Set(c, "PortId2", s.p2);
        }
        string path = $"{carFolder}/{CarId}_Sound.prefab";
        var prefab = PrefabUtility.SaveAsPrefabAsset(root, path);
        Object.DestroyImmediate(root);
        Line($"saved {path} ({sysList.Count + 1} vanilla audio systems{(Cfg.BellSound.HasValue ? " incl. steam bell" : "")}; RR whistle/chuff anchors)");
        return prefab;
    }

    // ------------------------------------------------------------------ step 6: car type / livery / pack / HUD
    static void ConfigureAssets(GameObject sound)
    {
        Section("Assets");
        var type = FindAsset("CustomCarType");
        var livery = FindAsset("CustomCarVariant");
        Set(type, "mass", Mass);
        Set(type, "wheelRadius", WheelRadius);
        Set(type, "IsSteamLocomotive", !Cfg.IsTender);
        // DV grip = coef * total weight / axles * powered axles; RR adhesive weight is 161,280 of 201,600 lb (0.80)
        Set(type, "wheelslipFrictionCoefficient", Cfg.WheelslipFriction);
        Set(type, "damage.wheelsHP", Cfg.WheelsHP);
        if (Cfg.Tender != null) Set(type, "brakes.hasHandbrake", false);   // the tender's handbrake (VirtualHandbrakeOverrider)
        Set(livery, "FrontBogie", 10000);
        Set(livery, "RearBogie", 10000);
        Set(livery, "BufferType", 10000);
        Set(livery, "UseCustomHosePositions", false);
        Set(livery, "HideHookPlates", true);
        Set(livery, "HasMUCable", false);
        Set(livery, "HideFrontCoupler", Cfg.HideFrontCoupler);
        Set(livery, "HideBackCoupler", Cfg.HideBackCoupler);
        var dirty = new List<Object> { type, livery };
        if (!Cfg.IsTender)
        {
            var pack = FindAsset("CustomCarPack");
            var hud = ScriptableObject.CreateInstance(T("CCL.Types.HUD.VanillaHUDLayout"));
            AssetDatabase.CreateAsset(hud, $"{carFolder}/{CarId}_hud.asset");
            Set(hud, "HUDType", Cfg.HudType);
            Set(type, "GeneralLicense", Cfg.License);   // DV GeneralLicenseType id ("SH282", not "S282")
            Set(type, "HUDLayout", hud);
            Set(type, "SimAudioPrefab", sound);
            Set(type, "damage.mechanicalPowertrainHP", Cfg.MechanicalPowertrainHP);
            Set(livery, "interiorPrefab", AssetDatabase.LoadAssetAtPath<GameObject>($"{carFolder}/{CarId}_interior.prefab"));
            Set(pack, "PackName", CarName);
            Set(pack, "Version", Cfg.Version);
            Set(pack, "Author", Cfg.Author);
            dirty.Add(pack); dirty.Add(hud);
            Line($"pack {Get<string>(pack, "PackId")}");
        }
        foreach (var o in dirty) EditorUtility.SetDirty(o);
        type.GetType().GetMethod("ForceValidation", BF)?.Invoke(type, null);
        livery.GetType().GetMethod("ForceValidation", BF)?.Invoke(livery, null);
        AssetDatabase.SaveAssets();
        Line($"mass {Mass:F0} kg, wheel radius {WheelRadius}, license {Cfg.License ?? "-"}, HUD {(Cfg.IsTender ? "-" : Cfg.HudType.ToString())}, wheelslip coef {Cfg.WheelslipFriction:0.###}{(Cfg.Tender != null ? ", no handbrake (tender's)" : "")}");
        Line($"type id {Get<string>(type, "id")}; livery {Get<string>(livery, "id")}; hide couplers front {Cfg.HideFrontCoupler} back {Cfg.HideBackCoupler}");
    }

    // ------------------------------------------------------------------ step 7: render + export
    static void RenderCheck()
    {
        Section("Render check");
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var car = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>($"{carFolder}/{CarId}_template.prefab"));
        var inter = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>($"{carFolder}/{CarId}_interior.prefab"));
        var b = RendererBounds(car);
        Line($"built exterior renderer bounds centre {V(b.center)} size {V(b.size)}");
        // pose the running gear mid-stroke, as it would be in motion
        foreach (var u in Cfg.EngineUnits)
        {
            foreach (var g in car.GetComponentsInChildren<Transform>(true).Where(t => t.name == $"[anim] {u.GroupName}" || System.Text.RegularExpressions.Regex.IsMatch(t.name, "^\\[anim\\] " + System.Text.RegularExpressions.Regex.Escape(u.GroupName) + " \\d+$")).ToList())
            {
                var an = g.GetComponent<Animator>();
                ((AnimationClip)((AnimatorController)an.runtimeAnimatorController).layers[0].stateMachine.defaultState.motion).SampleAnimation(g.gameObject, (0.1f + u.StartOffset) % 1f);
            }
        }
        var sun = new GameObject("sun").AddComponent<Light>();
        sun.type = LightType.Directional; sun.intensity = 1.1f; sun.transform.rotation = Quaternion.Euler(40, 120, 0);
        RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
        RenderSettings.ambientLight = new Color(0.5f, 0.5f, 0.55f);
        var cam = new GameObject("cam").AddComponent<Camera>();
        cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(0.72f, 0.78f, 0.85f); cam.fieldOfView = 35; cam.nearClipPlane = 0.03f;
        void Shots(IEnumerable<Shot> list) { foreach (var s in list) { cam.fieldOfView = s.Fov; Shot(cam, s.Pos, s.Look, s.File); } }
        Shots(Cfg.ExteriorShots);
        var cabLight = new GameObject("cab light").AddComponent<Light>();
        cabLight.type = LightType.Point; cabLight.range = 5f; cabLight.intensity = 1.5f; cabLight.transform.position = Cfg.RenderCabLight;
        var iaGo = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>($"{carFolder}/{CarId}_interactables.prefab"));
        car.transform.Find("[interior LOD]").gameObject.SetActive(false); // the real interior is instantiated
        Shots(Cfg.CabShots);
        // the same cab views with every control's grab box (green) - where the player can take hold of it
        {
            var grab = new List<GameObject>();
            var gm = new Material(Shader.Find("Standard")) { color = new Color(0.1f, 1f, 0.2f, 0.45f) }; MakeTransparent(gm); gm.SetFloat("_Mode", 3);
            foreach (var bc in inter.GetComponentsInChildren<BoxCollider>(true).Where(x => x.name == "collider"))
            {
                var m = GameObject.CreatePrimitive(PrimitiveType.Cube);
                Object.DestroyImmediate(m.GetComponent<Collider>());
                m.transform.SetPositionAndRotation(bc.transform.TransformPoint(bc.center), bc.transform.rotation);
                m.transform.localScale = Vector3.Scale(bc.transform.lossyScale, bc.size);
                m.GetComponent<Renderer>().sharedMaterial = gm;
                grab.Add(m);
            }
            foreach (var s in Cfg.CabShots) { cam.fieldOfView = s.Fov; Shot(cam, s.Pos, s.Look, "grab_" + s.File); }
            foreach (var m in grab) Object.DestroyImmediate(m);
        }
        // lamps as they look when lit (the headlight controller swaps these materials in game)
        var lensSwap = new List<(Renderer r, Material m)>();
        foreach (var hp in car.GetComponentsInChildren(T("CCL.Types.Proxies.Headlights.HeadlightProxy"), true))
        {
            if (!(hp.name.EndsWith("High") || (hp.transform.parent.name == "RearSide" && hp.name.EndsWith("Red")))) continue;
            var so = new SerializedObject(hp);
            var r = (Renderer)so.FindProperty("headlightRenderer").objectReferenceValue;
            lensSwap.Add((r, r.sharedMaterial));
            r.sharedMaterial = (Material)so.FindProperty("emissionMaterialLit").objectReferenceValue;
        }
        Shots(Cfg.LampShots);
        foreach (var (r, m) in lensSwap) r.sharedMaterial = m;
        Object.DestroyImmediate(iaGo);
        car.transform.Find("[interior LOD]").gameObject.SetActive(true);

        // markers for runtime-spawned things: oil cups (yellow), number plates (red), cab teleport (green), coal/water targets (blue)
        var markers = new List<GameObject>();
        void Marker(PrimitiveType pt, Vector3 pos, Quaternion rot, Vector3 scale, Color c)
        {
            var m = GameObject.CreatePrimitive(pt);
            Object.DestroyImmediate(m.GetComponent<Collider>());
            m.transform.SetPositionAndRotation(pos, rot); m.transform.localScale = scale;
            m.GetComponent<Renderer>().sharedMaterial = new Material(Shader.Find("Standard")) { color = c };
            markers.Add(m);
        }
        var ia = AssetDatabase.LoadAssetAtPath<GameObject>($"{carFolder}/{CarId}_interactables.prefab").transform;
        foreach (Transform m in ia.Find("ManualOilingPoints")) Marker(PrimitiveType.Sphere, m.position, Quaternion.identity, Vector3.one * 0.09f, Color.yellow);
        foreach (var (n, _) in Cfg.PlateDecals)
        {
            var a = car.transform.Find(n);
            Marker(PrimitiveType.Cube, a.position, a.rotation, new Vector3(0.02f, 0.3f, 1.0f), Color.red);
        }
        Marker(PrimitiveType.Capsule, car.transform.Find("[cab]").position + Vector3.up * 0.9f, Quaternion.identity, new Vector3(0.4f, 0.9f, 0.4f), Color.green);
        foreach (var t in ia.GetComponentsInChildren<BoxCollider>().Where(c => c.name.Contains("target")))
            Marker(PrimitiveType.Cube, t.transform.position, Quaternion.identity, t.size, Color.blue);
        Shots(Cfg.MarkerShots);
        foreach (var m in markers) Object.DestroyImmediate(m);

        // articulation preview: turn each bogie that carries parts by 4 deg, as on a ~100 m curve, and look from above
        if (Cfg.ArticulatedParts.Count > 0)
        {
            var turned = Cfg.ArticulatedParts.Select(a => car.transform.Find(a.bogie)).Distinct().ToList();
            foreach (var bg in turned) bg.localRotation = Quaternion.Euler(0, 4, 0);
            var top = new GameObject("topcam").AddComponent<Camera>();
            top.CopyFrom(cam); top.orthographic = true; top.orthographicSize = 5.5f;
            top.transform.SetPositionAndRotation(new Vector3(0, 20, 3.5f), Quaternion.Euler(90, 0, 0));
            var rt = new RenderTexture(1600, 900, 24); top.targetTexture = rt; top.Render(); RenderTexture.active = rt;
            var tex = new Texture2D(1600, 900, TextureFormat.RGB24, false); tex.ReadPixels(new Rect(0, 0, 1600, 900), 0, 0);
            File.WriteAllBytes(Path.Combine(outDir, "articulation_top.png"), tex.EncodeToPNG());
            RenderTexture.active = null; Object.DestroyImmediate(rt); Object.DestroyImmediate(tex);
            cam.fieldOfView = 35; Shot(cam, new Vector3(-9, 4f, 11f), new Vector3(0, 1.5f, 3.5f), "articulation_front34.png");
            Object.DestroyImmediate(top.gameObject);
            foreach (var bg in turned) bg.localRotation = Quaternion.identity;
            Line("render articulation_top.png / articulation_front34.png (articulated bogies turned 4 deg)");
        }

        // colliders preview: collision boxes (translucent red) over the model
        var col = car.transform.Find("[colliders]/[collision]");
        foreach (var bc in col.GetComponentsInChildren<BoxCollider>(true))
        {
            var m = GameObject.CreatePrimitive(PrimitiveType.Cube);
            Object.DestroyImmediate(m.GetComponent<Collider>());
            m.transform.position = bc.transform.TransformPoint(bc.center); m.transform.localScale = bc.size;
            var mat = new Material(Shader.Find("Standard")) { color = new Color(1, 0, 0, 0.35f) }; MakeTransparent(mat); mat.SetFloat("_Mode", 3);
            m.GetComponent<Renderer>().sharedMaterial = mat;
            markers.Add(m);
        }
        if (Cfg.ExteriorShots.Count > 0) { var s0 = Cfg.ExteriorShots[0]; cam.fieldOfView = s0.Fov; Shot(cam, s0.Pos, s0.Look, "collision_left.png"); }
        foreach (var m in markers) Object.DestroyImmediate(m);

        // tender: coupled behind the loco (rigs 2 x inset apart = coupling planes touching), then alone with its lamps lit
        if (Loco.Tender != null)
        {
            var tc = Loco.Tender; string tf = builtFolders[tc];
            var tender = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>($"{tf}/{tc.CarId}_template.prefab"));
            var tia = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>($"{tf}/{tc.CarId}_interactables.prefab"));
            float off = car.transform.Find("[coupler_rig_rear]").localPosition.z - 2 * Loco.CouplerInset - tender.transform.Find("[coupler_rig_front]").localPosition.z;
            tender.transform.position = tia.transform.position = new Vector3(0, 0, off);
            Line($"tender placed at z {off:F3} (loco rear rig {car.transform.Find("[coupler_rig_rear]").localPosition.z:F3}, tender front rig {tender.transform.Find("[coupler_rig_front]").localPosition.z:F3})");
            Shots(Cfg.ConsistShots);
            car.SetActive(false);
            tender.transform.position = tia.transform.position = Vector3.zero;
            Shots(tc.ExteriorShots);
            foreach (var hp in tender.GetComponentsInChildren(T("CCL.Types.Proxies.Headlights.HeadlightProxy"), true))
            {
                var so = new SerializedObject(hp);
                ((Renderer)so.FindProperty("headlightRenderer").objectReferenceValue).sharedMaterial = (Material)so.FindProperty("emissionMaterialLit").objectReferenceValue;
            }
            Shots(tc.LampShots);
            Object.DestroyImmediate(tender); Object.DestroyImmediate(tia);
        }
        Object.DestroyImmediate(car);
        Object.DestroyImmediate(inter);
    }

    static void Shot(Camera cam, Vector3 pos, Vector3 look, string file)
    {
        cam.transform.position = pos; cam.transform.LookAt(look);
        var rt = new RenderTexture(1600, 900, 24);
        cam.targetTexture = rt; cam.Render(); RenderTexture.active = rt;
        var tex = new Texture2D(1600, 900, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, 1600, 900), 0, 0);
        File.WriteAllBytes(Path.Combine(outDir, file), tex.EncodeToPNG());
        RenderTexture.active = null; cam.targetTexture = null;
        Object.DestroyImmediate(rt); Object.DestroyImmediate(tex);
        Line("render " + file);
    }

    static void Export()
    {
        Section("Export");
        var pack = FindAsset("CustomCarPack");
        string dir = Path.Combine(outDir, CarName);
        if (Directory.Exists(dir)) foreach (var f in Directory.GetFiles(dir)) File.Delete(f);
        Directory.CreateDirectory(dir);
        var wiz = T("CCL.Creator.Wizards.ExportPackWizard");
        var reqs = Array.CreateInstance(T("CCL.Creator.Wizards.ExportPackWizard+ModDependencyEntry"), 0);
        wiz.GetMethod("Export", BF).Invoke(null, new object[] { pack, dir, reqs });
        string info = Path.Combine(dir, "Info.json");
        File.WriteAllText(info, File.ReadAllText(info).Replace("\"Requirements\":[]", "\"Requirements\":[" + string.Join(",", Cfg.Requirements.Select(r => "\"" + r + "\"")) + "]"));
        foreach (var f in Directory.GetFiles(dir)) Line($"  {Path.GetFileName(f)} {new FileInfo(f).Length:N0} bytes");
    }

    // ------------------------------------------------------------------ generated meshes/textures
    static Mesh Disc(int seg)
    {
        var v = new List<Vector3> { Vector3.zero }; var uv = new List<Vector2> { new Vector2(0.5f, 0.5f) }; var tri = new List<int>();
        for (int i = 0; i <= seg; i++)
        {
            float a = i * Mathf.PI * 2 / seg;
            var p = new Vector3(Mathf.Cos(a) * 0.5f, Mathf.Sin(a) * 0.5f, 0);
            v.Add(p);
            uv.Add(new Vector2(0.5f - p.x, 0.5f + p.y)); // viewed from +z: viewer's right is -x
            if (i > 0) { tri.Add(0); tri.Add(i); tri.Add(i + 1); } // clockwise as seen from +z = front face
        }
        var m = new Mesh { name = "gauge_disc" };
        m.SetVertices(v); m.SetUVs(0, uv); m.SetTriangles(tri, 0); m.RecalculateNormals(); m.RecalculateBounds();
        return m;
    }

    static Mesh Needle()
    {
        // unit-diameter gauge: tip at y 0.40, tail at -0.08, visible from +z
        var v = new[] { new Vector3(-0.012f, -0.08f, 0), new Vector3(0.012f, -0.08f, 0), new Vector3(0.022f, 0f, 0), new Vector3(0, 0.40f, 0), new Vector3(-0.022f, 0f, 0) };
        var m = new Mesh { name = "gauge_needle", vertices = v, triangles = new[] { 0, 1, 2, 0, 2, 4, 4, 2, 3 } }; // clockwise as seen from +z
        m.uv = v.Select(p => new Vector2(p.x, p.y)).ToArray();
        m.RecalculateNormals(); m.RecalculateBounds();
        return m;
    }

    static Mesh Box()
    {
        // unit box, pivot at the bottom centre (scaling y grows it upwards)
        var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
        var src = go.GetComponent<MeshFilter>().sharedMesh;
        var m = new Mesh { name = "unit_box" };
        m.vertices = src.vertices.Select(p => p + new Vector3(0, 0.5f, 0)).ToArray();
        m.normals = src.normals; m.uv = src.uv; m.triangles = src.triangles; m.tangents = src.tangents;
        m.RecalculateBounds();
        Object.DestroyImmediate(go);
        return m;
    }

    // brass handwheel, 0.1 m across, in the local xy plane (turns about local z)
    static Mesh ValveWheel()
    {
        var parts = new List<CombineInstance>();
        const float R = 0.045f, r = 0.006f; const int seg = 24, tube = 8;
        var v = new List<Vector3>(); var n = new List<Vector3>(); var tri = new List<int>();
        for (int i = 0; i <= seg; i++)
            for (int j = 0; j <= tube; j++)
            {
                float a = i * Mathf.PI * 2 / seg, b = j * Mathf.PI * 2 / tube;
                var c = new Vector3(Mathf.Cos(a), Mathf.Sin(a), 0);
                var nn = c * Mathf.Cos(b) + Vector3.forward * Mathf.Sin(b);
                v.Add(c * R + nn * r); n.Add(nn);
                if (i < seg && j < tube)
                {
                    int k = i * (tube + 1) + j, k2 = k + tube + 1;
                    tri.AddRange(new[] { k, k + 1, k2, k2, k + 1, k2 + 1 });
                }
            }
        var ring = new Mesh(); ring.SetVertices(v); ring.SetNormals(n); ring.SetTriangles(tri, 0);
        parts.Add(new CombineInstance { mesh = ring, transform = Matrix4x4.identity });
        var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
        var cm = Object.Instantiate(cube.GetComponent<MeshFilter>().sharedMesh);
        Object.DestroyImmediate(cube);
        for (int s = 0; s < 3; s++)
            parts.Add(new CombineInstance { mesh = cm, transform = Matrix4x4.TRS(Quaternion.Euler(0, 0, s * 120) * new Vector3(0, R / 2, 0), Quaternion.Euler(0, 0, s * 120), new Vector3(0.008f, R, 0.006f)) });
        parts.Add(new CombineInstance { mesh = cm, transform = Matrix4x4.TRS(new Vector3(0, 0, 0.012f), Quaternion.identity, new Vector3(0.018f, 0.018f, 0.03f)) }); // hub + spindle
        var m = new Mesh { name = "control_valve_wheel" };
        m.CombineMeshes(parts.ToArray(), true, true);
        m.RecalculateBounds();
        return m;
    }

    // lever handle: pivot boss at the origin, arm up local +y, round-ish grip at the top
    static Mesh Lever()
    {
        var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
        var cm = Object.Instantiate(cube.GetComponent<MeshFilter>().sharedMesh);
        Object.DestroyImmediate(cube);
        var parts = new[]
        {
            new CombineInstance { mesh = cm, transform = Matrix4x4.TRS(new Vector3(0, 0, 0.005f), Quaternion.identity, new Vector3(0.035f, 0.035f, 0.02f)) },
            new CombineInstance { mesh = cm, transform = Matrix4x4.TRS(new Vector3(0, 0.07f, -0.005f), Quaternion.identity, new Vector3(0.016f, 0.14f, 0.012f)) },
            new CombineInstance { mesh = cm, transform = Matrix4x4.TRS(new Vector3(0, 0.145f, -0.012f), Quaternion.identity, new Vector3(0.024f, 0.03f, 0.03f)) },
        };
        var m = new Mesh { name = "control_lever" };
        m.CombineMeshes(parts, true, true);
        m.RecalculateBounds();
        return m;
    }

    static bool Raycast(GameObject body, Vector3 origin, Vector3 dir, float dist, out RaycastHit best)
    {
        var temp = new List<MeshCollider>();
        foreach (var mf in body.GetComponentsInChildren<MeshFilter>(false))
        {
            if (!mf.sharedMesh || mf.sharedMesh.vertexCount == 0 || !mf.GetComponent<MeshRenderer>() || mf.GetComponent<Collider>()) continue;
            var mc = mf.gameObject.AddComponent<MeshCollider>(); mc.sharedMesh = mf.sharedMesh; temp.Add(mc);
        }
        Physics.SyncTransforms();
        var hits = new RaycastHit[64];
        int n = body.scene.GetPhysicsScene().Raycast(origin, dir.normalized, hits, dist, ~0, QueryTriggerInteraction.Ignore);
        best = default(RaycastHit); bool found = false;
        for (int i = 0; i < n; i++)
            if (hits[i].collider.transform.IsChildOf(body.transform) && (!found || hits[i].distance < best.distance)) { best = hits[i]; found = true; }
        if (found) best = new RaycastHit { point = best.point, normal = best.normal, distance = best.distance }; // copy before the colliders go
        string hitName = found ? hits.Take(n).OrderBy(h => h.distance).First(h => h.collider.transform.IsChildOf(body.transform)).collider.name : null;
        foreach (var mc in temp) Object.DestroyImmediate(mc);
        lastHitName = hitName;
        return found;
    }
    static string lastHitName;

    // Mesh islands: triangles connected through shared vertex positions (welded at 1e-4 local units, as the backhead probe).
    static List<List<(int sub, int a, int b, int c)>> Islands(Mesh mesh)
    {
        var verts = mesh.vertices;
        var key = new Dictionary<Vector3Int, int>(); var id = new int[verts.Length];
        for (int i = 0; i < verts.Length; i++)
        {
            var k = Vector3Int.RoundToInt(verts[i] * 10000f);
            if (!key.TryGetValue(k, out id[i])) { id[i] = key.Count; key[k] = id[i]; }
        }
        var parent = Enumerable.Range(0, key.Count).ToArray();
        int Find(int x) { while (parent[x] != x) x = parent[x] = parent[parent[x]]; return x; }
        var tris = new List<(int, int, int, int)>();
        for (int s = 0; s < mesh.subMeshCount; s++)
        {
            var t = mesh.GetTriangles(s);
            for (int i = 0; i < t.Length; i += 3)
            {
                tris.Add((s, t[i], t[i + 1], t[i + 2]));
                int r = Find(id[t[i]]);
                parent[Find(id[t[i + 1]])] = r;
                parent[Find(id[t[i + 2]])] = Find(r);
            }
        }
        return tris.GroupBy(t => Find(id[t.Item2])).Select(g => g.ToList()).ToList();
    }

    // Splits the island whose world bounds centre is nearest 'centre' out of part's mesh: (island, rest, island world bounds).
    static (Mesh island, Mesh rest, Bounds wb) SplitIsland(Transform part, Vector3 centre)
    {
        var mesh = part.GetComponent<MeshFilter>().sharedMesh;
        var v = mesh.vertices;
        var l2w = part.localToWorldMatrix;
        Bounds WB(List<(int sub, int a, int b, int c)> g)
        {
            var b = new Bounds(l2w.MultiplyPoint3x4(v[g[0].a]), Vector3.zero);
            foreach (var t in g) { b.Encapsulate(l2w.MultiplyPoint3x4(v[t.a])); b.Encapsulate(l2w.MultiplyPoint3x4(v[t.b])); b.Encapsulate(l2w.MultiplyPoint3x4(v[t.c])); }
            return b;
        }
        var islands = Islands(mesh).Select(g => (g, b: WB(g))).OrderBy(x => (x.b.center - centre).sqrMagnitude).ToList();
        var best = islands[0];
        if ((best.b.center - centre).magnitude > 0.02f) Warn($"{part.name}: nearest island to {V(centre)} is at {V(best.b.center)}");
        return (SubMesh(mesh, best.g), SubMesh(mesh, islands.Skip(1).SelectMany(x => x.g).ToList()), best.b);
    }

    static Mesh SubMesh(Mesh src, List<(int sub, int a, int b, int c)> tris)
    {
        var map = new Dictionary<int, int>();
        var order = new List<int>();
        int Map(int i) { if (!map.TryGetValue(i, out var j)) { j = map[i] = order.Count; order.Add(i); } return j; }
        var subs = Enumerable.Range(0, src.subMeshCount).Select(_ => new List<int>()).ToArray();
        foreach (var t in tris) { subs[t.sub].Add(Map(t.a)); subs[t.sub].Add(Map(t.b)); subs[t.sub].Add(Map(t.c)); }
        var m = new Mesh { name = src.name, indexFormat = order.Count > 65000 ? UnityEngine.Rendering.IndexFormat.UInt32 : UnityEngine.Rendering.IndexFormat.UInt16 };
        var sv = src.vertices; m.SetVertices(order.Select(i => sv[i]).ToList());
        var sn = src.normals; if (sn.Length > 0) m.SetNormals(order.Select(i => sn[i]).ToList());
        var st = src.tangents; if (st.Length > 0) m.SetTangents(order.Select(i => st[i]).ToList());
        var sc = src.colors; if (sc.Length > 0) m.SetColors(order.Select(i => sc[i]).ToList());
        for (int ch = 0; ch < 4; ch++)
        {
            var uv = new List<Vector2>(); src.GetUVs(ch, uv);
            if (uv.Count > 0) m.SetUVs(ch, order.Select(i => uv[i]).ToList());
        }
        m.subMeshCount = src.subMeshCount;
        for (int s = 0; s < subs.Length; s++) m.SetTriangles(subs[s], s);
        m.RecalculateBounds();
        return m;
    }

    static Mesh SaveMesh(Mesh m, string name)
    {
        AssetDatabase.CreateAsset(m, $"{Work}/Generated/{name}.asset");
        return m;
    }

    static readonly string[] Digits =
    {
        "01110100011001110101110011000101110", "00100011000010000100001000010001110", "01110100010000100010001000100011111",
        "11110000010000101110000010000111110", "00010001100101010010111110001000010", "11111100001111000001000011000101110",
        "00110010001000011110100011000101110", "11111000010001000100010000100001000", "01110100011000101110100011000101110",
        "01110100011000101111000010001001100",
    };

    static Texture2D Dial(float min, float max, float major, float minor, bool redline)
    {
        const int S = 512;
        var t = new Texture2D(S, S, TextureFormat.RGBA32, false);
        var px = new Color[S * S];
        var face = new Color(0.93f, 0.91f, 0.84f); var ink = new Color(0.08f, 0.08f, 0.08f); var rim = new Color(0.12f, 0.11f, 0.1f);
        for (int y = 0; y < S; y++)
            for (int x = 0; x < S; x++)
            {
                float dx = (x + 0.5f) / S - 0.5f, dy = (y + 0.5f) / S - 0.5f, r = Mathf.Sqrt(dx * dx + dy * dy);
                px[y * S + x] = r > 0.5f ? rim : r > 0.47f ? rim : face;
            }
        void Plot(float u, float v, Color c) { int x = (int)(u * S), y = (int)(v * S); if (x >= 0 && y >= 0 && x < S && y < S) px[y * S + x] = c; }
        void Tick(float value, float r0, float r1, float w, Color c)
        {
            float a = Mathf.Lerp(-135, 135, (value - min) / (max - min)) * Mathf.Deg2Rad; // clockwise from top, as seen by the viewer
            for (float r = r0; r <= r1; r += 0.5f / S)
                for (float o = -w; o <= w; o += 0.5f / S)
                    Plot(0.5f + Mathf.Sin(a) * r + Mathf.Cos(a) * o, 0.5f + Mathf.Cos(a) * r - Mathf.Sin(a) * o, c);
        }
        if (redline) for (float v = max * 0.8f; v <= max; v += (max - min) / 400) Tick(v, 0.40f, 0.44f, 0.004f, new Color(0.75f, 0.1f, 0.08f));
        for (float v = min; v <= max + 1e-3f; v += minor) Tick(v, 0.40f, 0.45f, 0.003f, ink);
        for (float v = min; v <= max + 1e-3f; v += major)
        {
            Tick(v, 0.36f, 0.45f, 0.007f, ink);
            string s = Mathf.RoundToInt(v).ToString();
            float a = Mathf.Lerp(-135, 135, (v - min) / (max - min)) * Mathf.Deg2Rad;
            float cu = 0.5f + Mathf.Sin(a) * 0.28f, cv = 0.5f + Mathf.Cos(a) * 0.28f;
            const int P = 5; // pixels per font dot
            float w = (s.Length * 6 - 1) * P / (float)S, h = 7 * P / (float)S;
            for (int i = 0; i < s.Length; i++)
            {
                var g = Digits[s[i] - '0'];
                for (int row = 0; row < 7; row++)
                    for (int col = 0; col < 5; col++)
                        if (g[row * 5 + col] == '1')
                            for (int py = 0; py < P; py++)
                                for (int pxx = 0; pxx < P; pxx++)
                                    Plot(cu - w / 2 + ((i * 6 + col) * P + pxx) / (float)S, cv + h / 2 - (row * P + py) / (float)S, ink);
            }
        }
        for (int y = 0; y < S; y++) for (int x = 0; x < S; x++) { float dx = (x + 0.5f) / S - 0.5f, dy = (y + 0.5f) / S - 0.5f; if (dx * dx + dy * dy < 0.035f * 0.035f) px[y * S + x] = ink; }
        t.SetPixels(px); t.Apply();
        return t;
    }

    static Texture2D CoalTexture()
    {
        const int S = 256;
        var t = new Texture2D(S, S, TextureFormat.RGBA32, true);
        var px = new Color[S * S];
        var rnd = new System.Random(1279);
        for (int y = 0; y < S; y++)
            for (int x = 0; x < S; x++)
            {
                float n = Mathf.PerlinNoise(x * 0.09f, y * 0.09f) * 0.6f + Mathf.PerlinNoise(x * 0.31f + 50, y * 0.31f) * 0.4f;
                float v = 0.03f + n * 0.09f + (rnd.NextDouble() < 0.02 ? 0.08f : 0f);
                px[y * S + x] = new Color(v, v, v * 1.05f);
            }
        t.SetPixels(px); t.Apply();
        return t;
    }

    static Material TexMat(string name, Texture2D tex, float gloss = 0.35f)
    {
        string p = $"{Work}/Generated/{name}.png";
        File.WriteAllBytes(p, tex.EncodeToPNG());
        AssetDatabase.ImportAsset(p);
        var m = new Material(Shader.Find("Standard")) { name = name };
        m.SetTexture("_MainTex", AssetDatabase.LoadAssetAtPath<Texture2D>(p));
        m.SetFloat("_Glossiness", gloss);
        AssetDatabase.CreateAsset(m, $"{Work}/Generated/{name}.mat");
        return m;
    }

    static Material ColMat(string name, Color c, float gloss, bool transparent = false)
    {
        var m = new Material(Shader.Find("Standard")) { name = name, color = c };
        m.SetFloat("_Glossiness", gloss);
        if (transparent) MakeTransparent(m);
        AssetDatabase.CreateAsset(m, $"{Work}/Generated/{name}.mat");
        return m;
    }

    // ------------------------------------------------------------------ helpers
    static Comp Comp(string name) => Components.First(c => c.name == name);

    static string Extra(Comp c, string key)
    {
        var m = System.Text.RegularExpressions.Regex.Match(c.extra, "\"" + key + "\":\"([^\"]*)\"");
        return m.Success ? m.Groups[1].Value : null;
    }

    static Color ParseHex(string hex)
    {
        ColorUtility.TryParseHtmlString(hex.StartsWith("#") ? hex : "#" + hex, out var c);
        return c;
    }

    static Bounds BoundsOf(Transform root, string path)
    {
        var t = root.Find(path);
        if (!t) { Warn("bounds: not found " + path); return new Bounds(); }
        var r = t.GetComponent<Renderer>();
        return r ? r.bounds : new Bounds(t.position, Vector3.zero);
    }

    static string NearestRenderer(GameObject body, Vector3 p, float max)
    {
        Renderer best = null; float bd = max;
        foreach (var r in body.GetComponentsInChildren<Renderer>(true))
        {
            if (r.bounds.size.magnitude > 0.8f) continue;
            float d = (r.bounds.center - p).magnitude;
            if (d < bd) { bd = d; best = r; }
        }
        return best ? $"{best.name} c {V(best.bounds.center)} s {V(best.bounds.size)} (d {bd:F3})" : "none";
    }

    // cab floor height under (x, z): raycast down against temporary colliders on the visible meshes
    static float FloorY(GameObject body, float x, float z) => Probe(body, new Vector3(x, 3.5f, z), Vector3.down, 3.5f, h => h.point.y, 1.7f);

    static float SurfaceX(GameObject body, float y, float z, float side) => Probe(body, new Vector3(side * 3f, y, z), new Vector3(-side, 0, 0), 3f, h => h.point.x * side, 0f);

    static float Probe(GameObject body, Vector3 origin, Vector3 dir, float dist, Func<RaycastHit, float> pick, float fallback)
    {
        var temp = new List<MeshCollider>();
        foreach (var mf in body.GetComponentsInChildren<MeshFilter>(false))
        {
            if (!mf.sharedMesh || mf.sharedMesh.vertexCount == 0 || !mf.GetComponent<MeshRenderer>() || mf.GetComponent<Collider>()) continue;
            var mc = mf.gameObject.AddComponent<MeshCollider>(); mc.sharedMesh = mf.sharedMesh; temp.Add(mc);
        }
        Physics.SyncTransforms();
        var hits = new RaycastHit[64];
        int n = body.scene.GetPhysicsScene().Raycast(origin, dir, hits, dist, ~0, QueryTriggerInteraction.Ignore);
        float best = fallback; float bestDist = float.MaxValue;
        for (int i = 0; i < n; i++)
            if (hits[i].collider is MeshCollider mc && temp.Contains(mc) && hits[i].distance < bestDist) { bestDist = hits[i].distance; best = pick(hits[i]); }
        foreach (var mc in temp) Object.DestroyImmediate(mc);
        return best;
    }

    static Type T(string name)
    {
        foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
        {
            var t = asm.GetType(name);
            if (t != null) return t;
        }
        throw new Exception("type not found: " + name);
    }

    static Component Add(GameObject go, string typeName) => go.AddComponent(T(typeName));

    static void SetField(object o, string field, object value)
    {
        var f = o.GetType().GetField(field, BF);
        f.SetValue(o, f.FieldType.IsEnum ? Enum.ToObject(f.FieldType, value) : value);
    }

    static void Set(Object o, string prop, object value)
    {
        var so = new SerializedObject(o);
        var p = so.FindProperty(prop);
        if (p == null) { Warn($"no property '{prop}' on {o.GetType().Name}"); return; }
        if (value is IList list && !(value is string))
        {
            if (!p.isArray) { Warn($"'{prop}' is not an array"); return; }
            p.arraySize = list.Count;
            for (int i = 0; i < list.Count; i++) Assign(p.GetArrayElementAtIndex(i), list[i], prop);
        }
        else Assign(p, value, prop);
        so.ApplyModifiedPropertiesWithoutUndo();
    }

    static void SetArraySize(Object o, string prop, int n)
    {
        var so = new SerializedObject(o);
        var p = so.FindProperty(prop);
        if (p == null) { Warn($"no array '{prop}' on {o.GetType().Name}"); return; }
        p.arraySize = n;
        so.ApplyModifiedPropertiesWithoutUndo();
    }

    static void Assign(SerializedProperty p, object v, string prop)
    {
        switch (v)
        {
            case null: p.objectReferenceValue = null; break;
            case Object obj: p.objectReferenceValue = obj; break;
            case bool b: p.boolValue = b; break;
            case int i: if (p.propertyType == SerializedPropertyType.Float) p.floatValue = i; else p.intValue = i; break;
            case float f: p.floatValue = f; break;
            case string s: p.stringValue = s; break;
            case Vector3 vec: p.vector3Value = vec; break;
            case Color c: p.colorValue = c; break;
            default: Warn($"unsupported value {v.GetType().Name} for '{prop}'"); break;
        }
    }

    static TV Get<TV>(Object o, string prop)
    {
        var p = new SerializedObject(o).FindProperty(prop);
        if (p == null) { Warn($"no property '{prop}' on {o.GetType().Name}"); return default(TV); }
        object v;
        switch (p.propertyType)
        {
            case SerializedPropertyType.Float: v = p.floatValue; break;
            case SerializedPropertyType.Boolean: v = p.boolValue; break;
            case SerializedPropertyType.String: v = p.stringValue; break;
            case SerializedPropertyType.Vector3: return (TV)(object)p.vector3Value;
            default: v = p.intValue; break;
        }
        return (TV)Convert.ChangeType(v, typeof(TV));
    }

    static void PortReader(GameObject go, string port, string rangePort = "")
    {
        var rd = Add(go, "CCL.Types.Proxies.Indicators.IndicatorPortReaderProxy");
        Set(rd, "portId", port);
        if (rangePort != "") Set(rd, "indicatorRangeScalerPortId", rangePort);
        Set(rd, "valueMultiplier", 1f);
    }

    static void Layer(GameObject go, int layer, bool children)
    {
        var l = Add(go, "CCL.Types.Proxies.InteriorNonStandardLayerProxy");
        Set(l, "Layer", layer);
        Set(l, "includeChildren", children);
    }

    static Transform Child(Transform parent, string name, Vector3 localPos)
    {
        var t = new GameObject(name).transform;
        t.SetParent(parent, false);
        t.localPosition = localPos;
        return t;
    }

    static Bounds RendererBounds(GameObject go)
    {
        var rs = go.GetComponentsInChildren<Renderer>(false).Where(r => r.enabled && !(r is ParticleSystemRenderer)).ToList();
        if (rs.Count == 0) return new Bounds();
        var b = rs[0].bounds;
        foreach (var r in rs) b.Encapsulate(r.bounds);
        return b;
    }

    static Object FindAsset(string typeName)
    {
        foreach (var guid in AssetDatabase.FindAssets("t:" + typeName, new[] { carFolder ?? "Assets/_CCL_CARS" }))
        {
            string p = AssetDatabase.GUIDToAssetPath(guid);
            // exact folder: 'RLW RGB-2 Tender' must not match a search in 'RLW RGB-2'
            if (carFolder != null && Path.GetDirectoryName(p).Replace('\\', '/') != carFolder) continue;
            var a = AssetDatabase.LoadMainAssetAtPath(p);
            if (a != null && a.GetType().Name == typeName) return a;
        }
        throw new Exception("asset not found: " + typeName);
    }

    // RR AssetPack.Common AnimationMap/MaterialMap are dummy stubs after export; DV must not see them
    static void StripScripts(GameObject go)
    {
        int n = 0, missing = 0;
        foreach (var mb in go.GetComponentsInChildren<MonoBehaviour>(true)) { Object.DestroyImmediate(mb, true); n++; }
        foreach (var t in go.GetComponentsInChildren<Transform>(true)) missing += GameObjectUtility.RemoveMonoBehavioursWithMissingScript(t.gameObject);
        Line($"removed {n} RR components ({missing} missing-script) from {go.name}");
    }

    static void Folder(string path)
    {
        if (AssetDatabase.IsValidFolder(path)) return;
        var parent = Path.GetDirectoryName(path).Replace('\\', '/');
        Folder(parent);
        AssetDatabase.CreateFolder(parent, Path.GetFileName(path));
    }

    static string Safe(string s) => string.Concat(s.Select(ch => Path.GetInvalidFileNameChars().Contains(ch) ? '_' : ch));
    static void Kill(Transform t) { if (t) Object.DestroyImmediate(t.gameObject, true); }

    static void DumpHierarchy(GameObject go, string label, int depth)
    {
        Line($"--- {label} hierarchy (depth {depth})");
        void Walk(Transform t, int d)
        {
            var comps = t.GetComponents<Component>().Where(c => c != null && !(c is Transform)).Select(c => c.GetType().Name);
            Line($"{new string(' ', d * 2)}{t.name}{(t.gameObject.activeSelf ? "" : " [inactive]")}  {V(t.localPosition)}  {string.Join(",", comps)}");
            if (d < depth) foreach (Transform c in t) Walk(c, d + 1);
        }
        Walk(go.transform, 0);
    }

    static string PathOf(Transform t, Transform root) => t == root || t.parent == null ? t.name : PathOf(t.parent, root) + "/" + t.name;
    static string V(Vector3 v) => $"({v.x:F3}, {v.y:F3}, {v.z:F3})";
    static void Section(string s) => Line($"\n==== {s}");
    static void Line(string s) { Report.AppendLine(s); Debug.Log("[CclLocoBuild] " + s); }
    static void Warn(string s) { warnings++; Line("WARN " + s); }
}





