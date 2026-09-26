using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

// LLW G-29 Mogul (Railroader AssetPack 'LLW Generic Locomotive Catalog' v1.4.3, MarquetteCreations; asset ls-260-g29 + lt-260-g29):
// 2-6-0 with a swing-bolster Fox-truck tender. The per-car half of the build: CclLocoBuild does the work, this says what.
// Values come from the RR definition (G29Defs, generated), probe renders (analysis\probe) and the model itself.
//   tools\run_unity.ps1 -Method G29Config.Build -Out builds\testN
public static class G29Config
{
    public static void Build() { G29Source.EnsureFlat(); CclLocoBuild.Run(LlwCatalogConfig.Apply(Create(), "ls-260-g29")); }

    const float LbToKg = 0.45359237f, GalToL = 3.785411784f, LbfToN = 4.4482216f, InToM = 0.0254f, PsiToBar = 0.0689476f;
    static PlaceCfg P(string name, float x, float y, bool wheel, string port, int ctl, bool toggle, int notches, string label, float range = 0, System.Action<Component> phys = null)
        => new PlaceCfg { Name = name, X = x, Y = y, Wheel = wheel, Port = port, Ctl = ctl, Toggle = toggle, Notches = notches, Label = label, Range = range, Phys = phys };
    static IEnumerable<Comp> Comps(G29Defs.Comp[] a) => a.Select(d => new Comp { kind = d.kind, name = d.name, parentPath = d.parentPath, extra = d.extra, pos = d.pos, rot = d.rot, scale = d.scale });
    static IEnumerable<Comp> Comps(G29TenderDefs.Comp[] a) => a.Select(d => new Comp { kind = d.kind, name = d.name, parentPath = d.parentPath, extra = d.extra, pos = d.pos, rot = d.rot, scale = d.scale });

    // Driving wheels: RR wheelset 1.30 m (tread r 0.650, flanges 0.673; analysis\probe\wheels_report.txt), model rail height y = -0.006
    const float WheelR = 0.65f;
    static readonly Vector3 Sash = new Vector3(0.018f, 0.70f, 0.55f);   // cab window grab box (pane 0.024 x 0.784 x 0.595)

    // Starting pull: RR publishes none (publishedTractiveEffort 0), so the fallback 0.85 P d^2 S / D (RR counts 2 cylinders).
    static float TeLbf => 0.85f * G29Defs.MaxBoilerPsi * G29Defs.PistonDiameterIn * G29Defs.PistonDiameterIn * G29Defs.PistonStrokeIn / (1.30f / InToM);
    // DV mean pull = p_gauge * A * (2/pi) * (S/2) * N / r (no 0.85 factor): 2 cylinders sized to the RR pull
    const float Stroke = 26f * InToM;
    static float Bore
    {
        get
        {
            float area = TeLbf * LbfToN * WheelR / (G29Defs.MaxBoilerPsi * PsiToBar * 1e5f * (2f / Mathf.PI) * (Stroke / 2f) * 2f);
            return Mathf.Sqrt(4f * area / Mathf.PI);
        }
    }

    // ---- realism pass (0.9.0). The G-29 is a generic 'Atlantic Locomotive Works' design (catalog builder's photo); LLW class
    // numbers are starting TE in thousands of lbf (C-21: 20,994; G-29: 29,363). RR gives 20x26 in, 51.2 in drivers, 170 psi,
    // 1,735 sq ft heating surface, 137,000 lb (120,000 on drivers), tender 6,000 gal / 9 t. The rest from 1906 Moguls of the
    // same size (Locobase: ICC class 201, 138,400 / 120,500 lb, grate 27.6 sq ft, 1,560 sq ft; ICC class 601, 20x26 in,
    // grate 31 sq ft, 2,203 sq ft): saturated, grate ~29 sq ft (2.69 m2).
    // Max evaporation (saturated, hand fired): ~11.5 lb/sq ft/h x 1,735 = ~20,000 lb/h = 2.5 kg/s; coal at ~6.8 lb steam per
    // lb and ~115 lb/sq ft grate/h = ~3,300 lb/h = 0.42 kg/s. DV gives 32 MJ/kg x 0.5 (efficiency at max firing) = 16 MJ/kg of
    // heat, so 0.42 kg/s = 6.7 MW = ~2.5 kg/s of steam from 25 C feed: the real figure.
    const float GrateM2 = 2.69f, MaxFiringKgS = 0.42f;
    // fire bed: DV's S282 holds 150 kg on a 66.7 sq ft (USRA light Mikado) grate = 2.25 kg/sq ft -> 29 sq ft = 65 kg
    const float FireBedKg = 65f;

    // Boiler: the model's barrel is 1.7 m over the jacket, tube sheet z 3.0 to cab front z -2.0 plus half the firebox. Real
    // water+steam space of a 64 in, 13 ft-tube saturated boiler (~235 x 2 in tubes; barrel 8.0 m3 less 1.9 m3 of tubes, plus
    // 1.5 m3 of firebox legs and crown, plus dome) is ~8.0 m3, working water ~76% = ~6,100 L (1,600 gal, 13,400 lb).
    const float BoilerDia = 1.7f, BoilerLen = 5.0f + 0.6f, BoilerTotalL = 8000f;
    static float BoilerCapacityMultiplier => BoilerTotalL / (Mathf.PI * BoilerDia * BoilerDia / 4f * BoilerLen * 1000f);
    static float BoilerVolumeL => BoilerTotalL;
    static float SpawnWaterL => BoilerVolumeL * 0.76f;
    // safety valves 170 psig lift, 167 psig reseat (3 psi blowdown), absolute bar as DV's boiler
    const float SafetyOpenBar = 170f * PsiToBar + 1.01325f, SafetyCloseBar = 167f * PsiToBar + 1.01325f;
    // one large lifting injector (Sellers/Nathan No. 10 class, ~3,300 gal/h) = 3.5 L/s: 1.4x the max evaporation
    const float InjectorLs = 3.5f;

    public static LocoConfig Create()
    {
        var c = new LocoConfig
        {
            // ---- identity / source
            CarId = "LLW_G29", CarName = "LLW G-29", Version = "0.9.2", ReleaseLabel = "pre-release",
            Author = "MarquetteCreations (Railroader model), CCL port",
            Livery = "Lined",                                            // RR liveries: Black, Lined, Subpar Southern, Black (Russian Iron)
            SrcPrefab = G29Source.Loco,
            ExtraParts = new[] { "Assets/G29Parts/prairie/headlight2.prefab", "Assets/G29Parts/prairie/handrail.prefab", "Assets/G29Parts/prairie/markers.prefab" },
            Work = "Assets/G29_DV/loco", BodyName = "G29_body", BaseCarType = 6,
            SpawnTracks = new[] { 300, 400, 1100, 1400, 1700 },   // CoalMineSouth, CoalPowerPlant, IronMineEast, OilRefinery, Sawmill

            // ---- generated RR definition data
            Components = G29Source.ResolveComps(G29Source.Loco, Comps(G29Defs.Components)),
            MaterialMap = G29Defs.MaterialMap, AnimationMap = G29Defs.AnimationMap, Liveries = G29Defs.Liveries, Wheelsets = G29Defs.Wheelsets,
            WeightEmptyKg = G29Defs.WeightEmptyLb * LbToKg - SpawnWaterL,  // RR 137,000 lb in working order, boiler water added by DV
            WaterCapacityL = 0, CoalCapacityKg = 0,                      // on the tender
            NestedClipGroups = true,                                     // 'Main' is shared by every clip

            // ---- physics / DV assets
            WheelRadius = WheelR,
            CouplerHeight = 1.05f, CouplerInset = 0.30f,
            License = "SH282", HudType = 20,
            // DV grip = coef x W/axles x powered axles (3 of 4 here); RR adhesive weight 120,000 of 137,000 lb
            WheelslipFriction = 0.25f * (120000f / 137000f) / (3f / 4f),
            SimBasis = 1,                                                // S282: tender ports (tenderWater/tenderCoal), superheater
            PortRefOverrides = new Dictionary<string, string> { { "boiler.FEEDWATER_TEMPERATURE", "" } },   // no feedwater heater
            Requirements = new[] { "DVCustomCarLoader" },

            // ---- body clean-up and fixed parts
            // front coupler rig: from the measured pilot beam (core RigOnEndBeam); test1-7 had CouplingFaceFront 5.4 - 0.3 (buried)
            RrEndRear = G29Defs.PositionTail,                            // RR car end -3.319: drawbar plane -3.819, tender origin z -8.194 as in RR
                                                                         // (test1-5 used -4.15 / -7.894: 0.3 m too close, the draw castings overlapped)
            HideBackCoupler = true,
            PlateDecals = new[] { ("[car plate anchor1]", "Decal 1"), ("[car plate anchor2]", "Decal 2") },   // cab sides
            CabZ = -3.6f,                                                // cab floor y 1.496, backhead plane z -3.15
            CabTeleportVolume = (new Vector3(0, 2.8f, -3.05f), new Vector3(2.8f, 2.5f, 1.9f)),   // the cab: sides x +-1.45, floor 1.5 to roof 4.1, z -4.0..-2.1
            ExplosionAnchor = new Vector3(0, 3.3f, -1.0f),

            // ---- running gear: rigid 2-6-0. One RR clip (Drivers) turns all three drivers and the whole valve gear. The DV bogies
            //      pivot on the end drivers (the rigid wheelbase), so the frame follows the chord between drivers 1 and 3; the pilot
            //      axle belongs to the front bogie and the pilot truck hangs on it (ArticulatedParts), swinging to the track.
            //      test1 pivoted on the pilot: drivers ~5 cm off the rails on a 100 m curve.
            EngineUnits = new List<EngineUnit> {
                new EngineUnit { DriverParts = new[] { "Main/Driver1", "Main/Driver2", "Main/Driver3" }, AnimKey = "Drivers", GroupName = "drivers", StartOffset = 0f },
            },
            Bogies = new List<BogieCfg> {
                new BogieCfg { Bogie = "BogieF", BogieCollider = "front", AxleParts = new[] { "PilotTruck/Pilot", "Main/Driver1" }, PivotAxle = 1 },
                new BogieCfg { Bogie = "BogieR", BogieCollider = "rear", AxleParts = new[] { "Main/Driver2", "Main/Driver3" }, PivotAxle = 1 },
            },
            PonyTrucks = new List<(string, string)> { ("Pilot", "pony front") },
            ArticulatedParts = new List<(string, string)> { ("Model/G29_body/PilotTruck", "BogieF") },
            PonyRadius = 0.345f,                                         // model pilot wheel tread (flange 0.366)
            PonyRadii = new Dictionary<string, float> { { "Pilot", .345f } }, // measured override of source diameter .68 / 2
            ReverserHandle = "Main/Empty.044/Reverser.001", ReverserClip = "Reverser",   // clip: yoke, reach rod and the cab Johnson bar
            SparksX = 0.72f,
            BrakeHangers = new[] { "Main/Brakes", "Main/Empty.017", "Main/Empty.038", "Main/Empty.039" }, BrakeHangerClip = "Brakes",

            // ---- cab and load animations: RR handles become DV levers; the rest of their clips follow the ports on the exterior
            CabControlObjects = new[] { "Main/Throttle", "Main/Whistle", "Main/TrainBrake", "Main/LocoBrake", "Main/Cocks", "Main/Armature.014/Bone/Peddle.002" },
            // moving parts with RR colliders: pedal, roof vent, cab doors, the four sliding windows (no static walkable copies)
            NoWalkParts = new[] { "Main/Armature.014", "Main/RoofVent.001", "Main/DoorEngineer", "Main/DoorFireman",
                                  "Main/Empty.003", "Main/Empty", "Main/Empty.053", "Main/Empty.001" },
            WhistleLinkageClip = "Whistle",
            // cab doors, windows and roof vent: hidden DV controls feed these saved ports; the RR parts follow on the exterior
            SimControls = new[] { "doorR", "doorL", "windowLF", "windowLR", "windowRF", "windowRR", "roofVent" },
            LoadAnimations = new[] {
                ("Throttle", "", "throttle.EXT_IN", false),               // throttle rod (Empty.128) follows the regulator
                ("Cocks", "", "cylinderCock.EXT_IN", false),              // cock pipes under the cylinders
                ("FBDoor", "", "fireboxDoor.EXT_IN", false),              // both door leaves (the pedal is the DV control)
                ("DE", "", "doorR.EXT_IN", false), ("DF", "", "doorL.EXT_IN", false),   // cab doors (to the running boards) + their check straps
                ("WLF", "", "windowLF.EXT_IN", false), ("WLR", "", "windowLR.EXT_IN", false),
                ("WRF", "", "windowRF.EXT_IN", false), ("WRR", "", "windowRR.EXT_IN", false),
                ("RH", "", "roofVent.EXT_IN", false) },
            // RR 'Wrench' wheelset (3 m, no wheel): the mechanical lubricator's ratchet arm, turned by the valve gear
            WheelClips = new List<(string, string, float)> { ("Wrench", "lubricator ratchet", 1.5f) },
            LoopAnimations = new[] { ("Bell", "bell.BELL_NORMALIZED", 0.8f), ("Pump", "compressor.PRODUCTION_RATE_NORMALIZED", 1.5f) },
            BellSound = new Vector3(0f, 3.9f, 1.23f),                    // bell on the boiler (br.bell z 1.234)

            // ---- interior
            MainPressureGauge = "BPG",
            BackheadZ = -3.15f, FireDoorCentre = new Vector3(0, 2.0f, -3.18f),   // backhead plane and fire hole centre (probe depth table)
            BackheadRayStartZ = -3.85f, LeverMaterial = "black",

            // ---- lights: an electric headlight on the pack's headlight part (housing + glass in one mesh); the tender has none
            LampKey = (t, b) => null,
            GlassLamps = new[] { ("Head", "[extra prefabs]/headlight2#RRR Window Glass", true) },
            FrontLow = new[] { "Head" }, FrontHigh = new[] { "Head" },
            CabLightProbe = new Vector3(0, 3.4f, -3.6f),

            // ---- particles / sound anchors (RR anchors: Chuff chimney, Whistle, Dynamo, CylinderCock)
            ChimneyComp = "Chuff", WhistleComp = "Whistle", SafetyPos = new Vector3(0, 4.4f, 0f),
            BlowdownPos = new Vector3(1.4f, 1.0f, -2.6f), DynamoPos = new Vector3(0.03f, 4.07f, -0.71f), CrackPos = new Vector3(0, 0.5f, 3.3f),
            FourCylinderCocks = false, CylinderLength = 1.1f,            // 2 sim cylinders; cock pipes end at x +-1.524, y 0.26, z 3.8
            ChuffType = 0,                                               // S060 chuffs (2 equivalent cylinders = 4 beats, stock slots)
            WhistleSystem = 3050,                                        // S060 whistle
            SndCab = new Vector3(0, 3.0f, -3.5f), SndCylinders = new Vector3(0, 0.9f, 3.3f), SndWheels = new Vector3(0, 0.6f, 0f),
            SndFire = new Vector3(0, 2.0f, -3.4f), SndAirPump = new Vector3(-1.2f, 2.4f, 0f), SndCoalDump = new Vector3(0, 1.0f, -3.0f),
            SndCrownSheet = new Vector3(0, 3.0f, -2.5f), SndSafety = new Vector3(0, 4.4f, 0f), SndSand = new Vector3(0, 0.6f, 1.2f),

            // ---- external interactables: no handbrake on the loco (the tender's); brake release on the right side under the cab
            BrakeReleaseExact = true,
            BrakeRelease = body => (new Vector3(0.551f, 1.240f, -3.850f), new Vector3(0, 90, 0)),   // hint: right side under the cab (core points it out sideways, under the edge)

            // ---- render check
            RenderCabLight = new Vector3(0, 3.5f, -3.4f),
            ExteriorShots = new List<Shot> {
                new Shot(35, new Vector3(-24, 2.2f, 1f), new Vector3(0, 2.0f, 1f), "built_left.png"),
                new Shot(35, new Vector3(10, 4.5f, 16), new Vector3(0, 1.9f, 2f), "built_front34.png"),
                new Shot(35, new Vector3(-10, 5f, -16), new Vector3(0, 1.9f, -1f), "built_rear34.png"),
                new Shot(35, new Vector3(-8, 1.0f, 2.0f), new Vector3(0, 0.8f, 2.0f), "built_gear_front_left.png"),
                new Shot(35, new Vector3(-8, 1.0f, -1.5f), new Vector3(0, 0.8f, -1.5f), "built_gear_rear_left.png") },
            CabShots = new List<Shot> {
                new Shot(60, new Vector3(0, 3.0f, -4.6f), new Vector3(0, 2.8f, -2.5f), "built_cab_backhead.png"),
                new Shot(40, new Vector3(-0.35f, 3.0f, -4.2f), new Vector3(-0.5f, 2.8f, -3.2f), "built_backhead_left.png"),
                new Shot(40, new Vector3(0.35f, 3.0f, -4.2f), new Vector3(0.5f, 2.8f, -3.2f), "built_backhead_right.png"),
                new Shot(40, new Vector3(0.0f, 2.6f, -4.2f), new Vector3(0.0f, 2.3f, -3.2f), "built_backhead_centre.png"),
                new Shot(45, new Vector3(0.3f, 3.3f, -4.2f), new Vector3(1.15f, 2.8f, -2.9f), "built_cab_driver.png"),
                new Shot(35, new Vector3(0.0f, 3.3f, -4.3f), new Vector3(0.0f, 3.2f, -3.2f), "built_gauges.png") },
            LampShots = new List<Shot> {
                new Shot(35, new Vector3(4f, 3.5f, 12f), new Vector3(0, 3.2f, 4.9f), "built_lamps_front_lit.png") },
            MarkerShots = new List<Shot> {
                new Shot(35, new Vector3(-24, 2.2f, 1f), new Vector3(0, 2.0f, 1f), "markers_left.png"),
                new Shot(35, new Vector3(24, 2.2f, 1f), new Vector3(0, 2.0f, 1f), "markers_right.png"),
                new Shot(35, new Vector3(-8, 12f, 0f), new Vector3(0, 2.0f, 0.001f), "markers_top.png"),
                new Shot(35, new Vector3(4.2f, 1.3f, -2.6f), new Vector3(1.2f, 1.2f, -3.85f), "markers_release.png") },
            ConsistShots = new List<Shot> {
                new Shot(35, new Vector3(-32, 2.6f, -3f), new Vector3(0, 2.0f, -3f), "consist_left.png"),
                new Shot(40, new Vector3(-4f, 5f, -9f), new Vector3(0, 2.0f, -4.5f), "consist_drawbar.png"),
                new Shot(30, new Vector3(-4.5f, 0.9f, -4.1f), new Vector3(0, 0.8f, -4.1f), "consist_drawgear_side.png"),
                new Shot(30, new Vector3(-2.2f, 1.6f, -2.6f), new Vector3(0, 0.7f, -4.1f), "consist_drawgear_34.png"),
                new Shot(55, new Vector3(-0.9f, 0.25f, -3.2f), new Vector3(0, 0.75f, -4.6f), "consist_drawgear_below.png"),
                new Shot(45, new Vector3(-0.5f, 3.1f, -3.5f), new Vector3(-1.18f, 2.35f, -4.55f), "consist_handbrake_from_cab.png"),
                new Shot(35, new Vector3(-8, 5f, -22f), new Vector3(0, 2f, -8f), "consist_rear34.png") },
        };

        // RR CylinderCock anchor sits on the centreline (RR spawns jets at +-radius); the cock pipes end at the cylinder sides
        foreach (var cc in c.Components.Where(x => x.kind == "CylinderCock")) cc.pos = new Vector3(1.524f, 0.26f, cc.pos.z);

        // [collision] boxes from the model's own extents (analysis\probe\faces_report.txt): pilot beam z 5.175 (coupler head
        // 5.43), rear beam -3.943 (drawbar pin -4.105); the cab roof overhangs to z -4.95 over the tender's front
        c.CollisionBoxes = body => new List<(string, Vector3, Vector3)>
        {
            ("frame", new Vector3(0, 1.0f, 0.68f), new Vector3(2.9f, 1.3f, 9.24f)),       // z -3.94..5.30
            ("boiler", new Vector3(0, 2.5f, 1.3f), new Vector3(1.9f, 1.8f, 6.6f)),
            ("cab", new Vector3(0, 3.05f, -3.0f), new Vector3(3.0f, 2.8f, 2.3f)),
            ("chimney", new Vector3(0, 3.75f, 3.4f), new Vector3(0.5f, 0.95f, 0.5f)),
            ("dome1", new Vector3(0, 3.85f, 2.3f), new Vector3(0.8f, 1.0f, 0.8f)),
            ("dome2", new Vector3(0, 3.85f, 0.05f), new Vector3(0.8f, 1.0f, 0.8f)),
        };

        // oil cups on the modelled rod oilers (analysis\rods): each side rod has one at every crank pin, each main rod one on
        // its big end. Gameplay layout (LLW gameplay-oiling-design-20260926): the front side-rod oilers stay modelled (behind
        // the main rod/crosshead at some wheel positions), so 6 cups: per side rear pin, main pin (side rod) and main big end.
        // test1-6 had them on the running-board edge.
        c.RodOilers = new List<(string, bool)>
        {
            ("Connecting Rod Left", true), ("Main Rod Left", false),            // left (x -)
            ("Connecting Rod Left.001", true), ("Main Rod Left.001", false),    // right (x +)
        };

        c.SimSpec = body => new Dictionary<string, Dictionary<string, object>>
        {
            ["steamEngine"] = new Dictionary<string, object> {
                { "numCylinders", 2 }, { "cylinderBore", Bore }, { "pistonStroke", Stroke },
                { "minCutoff", 0.10f }, { "maxCutoff", 0.85f }, { "throttleMaxFlow", 4f }, { "steamChestVolume", 600f },
                { "maxCondensationRate", 0.008f } },
            // feedwater 25 C: DV's injector draws no steam, so cold tender water is the energy-correct feed for a live-steam injector
            ["boiler"] = new Dictionary<string, object> {
                { "diameter", BoilerDia }, { "length", BoilerLen }, { "capacityMultiplier", BoilerCapacityMultiplier },
                { "maxInjectorRate", InjectorLs }, { "defaultFeedwaterTemperature", 25f }, { "waterConsumptionMultiplier", 1f },
                { "maxBlowdownRate", 20f }, { "safetyValveOpeningPressure", SafetyOpenBar }, { "safetyValveClosingPressure", SafetyCloseBar },
                { "maxSafetyValveVentRate", 3f }, { "spawnWaterLevel", SpawnWaterL } },
            // real coal use (consumption multiplier 1: a shovelful from the tender is what the fire gets)
            ["firebox"] = new Dictionary<string, object> {
                { "maxCoalCapacity", FireBedKg }, { "burnTime", FireBedKg / MaxFiringKgS }, { "coalDumpRate", 10f }, { "coalConsumptionMultiplier", 1f } },
            ["exhaust"] = new Dictionary<string, object> { { "passiveExhaust", 0.4f } },
            ["poweredAxles"] = new Dictionary<string, object> { { "value", 3f } },
            ["_notes"] = new Dictionary<string, object> {
                { "pull", $"RR start {TeLbf:F0} lbf (0.85 P d2 S / D; LLW class G-29 = 29,000 lbf); DV 2 x {Bore:F4} m bore x {Stroke:F4} m at r {WheelR} (bore sized so DV's pull, which has no 0.85 factor, equals it); factor of adhesion {G29Defs.WeightOnDriversLb / TeLbf:F2}" },
                { "boiler", $"dia {BoilerDia} m, length {BoilerLen:F3} m (barrel + half firebox), DV volume {BoilerVolumeL:F0} L (capacityMultiplier {BoilerCapacityMultiplier:F3}), spawn water {SpawnWaterL:F0} L; safety {SafetyOpenBar:F2}/{SafetyCloseBar:F2} bar abs (170/167 psig); injector {InjectorLs} L/s" },
                { "firing", $"grate {GrateM2} m2 (~29 sq ft), fire bed {FireBedKg} kg, max {MaxFiringKgS} kg/s = {MaxFiringKgS * 3600f / LbToKg:F0} lb/h ({MaxFiringKgS * 3600f / LbToKg / 29f:F0} lb/sq ft/h) -> {MaxFiringKgS * 32e6f * 0.5f / 1e6f:F1} MW -> ~{MaxFiringKgS * 32e6f * 0.5f / 2.68e6f:F2} kg/s steam (~{MaxFiringKgS * 32e6f * 0.5f / 2.68e6f * 3600f / LbToKg:F0} lb/h); real saturated max ~20,000 lb/h" },
                { "mass", $"car {G29Defs.WeightEmptyLb * LbToKg - SpawnWaterL:F0} kg + boiler water = RR {G29Defs.WeightEmptyLb * LbToKg:F0} kg" } },
        };

        // RR cab handles -> DV levers (axis/range from the RR clips); joint physics as the working RBBM-1t / RGB-2 / CCL 4-6-2T.
        // The driver sits on the right (throttle, Johnson bar, brake valves); the fire door is the RR pedal.
        // One key tap / scroll = one notch (DV LeverBase: SingleNotchAngle x scrollWheelHoverScroll), then the joint snaps to the
        // nearest notch 0.3 s after release. test3: angular drag 2e5 (from the 4-6-2T, which hides it with 4 notches per tap)
        // left the lever short of the next notch, so taps crawled or snapped back. Now no angular drag, damper 15, and notches for
        // 5 % per tap: throttle 21 (0..100 %), Johnson bar 41 (HUD -100..100 %, notch 20 = mid gear; ~4.3 % real cut-off per tap).
        c.RrLevers = new List<RrLeverCfg> {
            new RrLeverCfg { Path = "Main/Throttle", AnimKey = "Throttle", Port = "throttle.EXT_IN", Ctl = 0, Phys = (s, a) => CclLocoBuild.Phys(s, 0, a, 21, 50, 15, 15, 10, 0, 1, 400) },
            new RrLeverCfg { Path = "Main/Empty.044/Reverser.001", AnimKey = "Reverser", Port = "reverser.CONTROL_EXT_IN", Ctl = 1, Phys = (s, a) => CclLocoBuild.Phys(s, 0, a, 41, 85, 15, 30, 15, 0, 1, 200) },
            new RrLeverCfg { Path = "Main/TrainBrake", AnimKey = "TB", Port = "brake.EXT_IN", Ctl = 2, Phys = (s, a) => CclLocoBuild.Phys(s, 0, a, 11, 85, 15, 30, 16, 0, 1, 100) },
            new RrLeverCfg { Path = "Main/LocoBrake", AnimKey = "Indy", Port = "indBrake.EXT_IN", Ctl = 3, Phys = (s, a) => CclLocoBuild.Phys(s, 0, a, 11, 65, 0, 30, 16, 0, 1, 100) },
            // whistle: the pull bar spans the cab - grip on the hanging handle at the driver's side (Cylinder.326)
            new RrLeverCfg { Path = "Main/Whistle", AnimKey = "Whistle", Port = "whistle.EXT_IN", Ctl = 14, Phys = (s, a) => CclLocoBuild.Phys(s, 0, a, 0, 50, 5, 5, 5, 0, a / 4, 100),
                Grip = new Vector3(0.987f, 3.51f, -2.577f), GripSize = new Vector3(0.12f, 0.25f, 0.12f) },  // spring return
            new RrLeverCfg { Path = "Main/Cocks", AnimKey = "Cocks", Port = "cylinderCock.EXT_IN", Ctl = 22, Toggle = true, Phys = (s, a) => CclLocoBuild.Phys(s, 0, a, 2, 85, 15, 10, 15, 0, 1, 0), Label = "car/cyl_cock" },
            // the RR foot pedal opens both fire door leaves (FireboxDoor clip, driven by the same port)
            new RrLeverCfg { Path = "Main/Armature.014/Bone/Peddle.002", AnimKey = "FBDoor", Port = "fireboxDoor.EXT_IN", Ctl = 21, Toggle = true, Phys = (s, a) => CclLocoBuild.Phys(s, 0, a, 10, 100, 0, 50, 15, 0, 1, 0), Label = "car/fire_door" },
            // cab doors (hinged on the outer edge, open 90 deg onto the running boards) and the roof vent: hidden levers, the RR
            // parts follow on the exterior; door physics as the RBBM-1t's (5 notches, holding spring)
            new RrLeverCfg { Path = "Main/DoorEngineer", AnimKey = "DE", Port = "doorR.EXT_IN", Hidden = true, Phys = (s, a) => CclLocoBuild.Phys(s, 0, a, 5, 40, 5, 10, 10, 0, 1, 0),
                Grip = new Vector3(1.05f, 2.70f, -2.13f), GripSize = new Vector3(0.10f, 0.60f, 0.12f) },   // free edge of the leaf
            new RrLeverCfg { Path = "Main/DoorFireman", AnimKey = "DF", Port = "doorL.EXT_IN", Hidden = true, Phys = (s, a) => CclLocoBuild.Phys(s, 0, a, 5, 40, 5, 10, 10, 0, 1, 0),
                Grip = new Vector3(-1.05f, 2.70f, -2.13f), GripSize = new Vector3(0.10f, 0.60f, 0.12f) },
            new RrLeverCfg { Path = "Main/RoofVent.001/Bone", AnimKey = "RH", Port = "roofVent.EXT_IN", Hidden = true, Phys = (s, a) => CclLocoBuild.Phys(s, 0, a, 5, 40, 5, 10, 10, 0, 1, 0),
                Grip = new Vector3(0f, 3.92f, -3.19f), GripSize = new Vector3(0.08f, 0.20f, 0.10f) },       // the hanging vent handle (Cylinder.045)
        };

        // cab side windows: sashes sliding forward (front pair 0.58 m, rear pair 1.20 m, clips WLF/WLR/WRF/WRR) as hidden Pullers
        c.Pullers = new List<PullerCfg> {
            // grab boxes 1.8 cm thick on each sash (front x 1.430, rear 1.407): the rear sash slides past the front one, and control
            // rigidbodies collide, so the boxes must not overlap in x
            new PullerCfg { Path = "Main/Empty.003", AnimKey = "WLF", Port = "windowLF.EXT_IN", Name = "Window left front", Grip = new Vector3(-1.430f, 2.829f, -3.084f), GripSize = Sash },
            new PullerCfg { Path = "Main/Empty", AnimKey = "WLR", Port = "windowLR.EXT_IN", Name = "Window left rear", Grip = new Vector3(-1.407f, 2.829f, -3.673f), GripSize = Sash },
            new PullerCfg { Path = "Main/Empty.053", AnimKey = "WRF", Port = "windowRF.EXT_IN", Name = "Window right front", Grip = new Vector3(1.430f, 2.829f, -3.084f), GripSize = Sash },
            new PullerCfg { Path = "Main/Empty.001", AnimKey = "WRR", Port = "windowRR.EXT_IN", Name = "Window right rear", Grip = new Vector3(1.407f, 2.829f, -3.673f), GripSize = Sash },
        };

        // Railroader's own sounds (analysis: RR plays these; its chuffs are synthesised, so DV's S060 chuffs stay).
        // Whistle: the pack's default wh-3-cnj (CNJ 3-chime, base-game audio.whistles01), loopified as RR does at runtime
        // (RR WhistlePlayer: pitch ramps 0.9 -> 1 with the valve). Bell: RR's steam rope bell. Air pump and turbo-generator: RR's
        // TVRM recordings. Clips extracted by tools\extract_rr_audio.py + loopify_wav.py (personal use only - game assets).
        c.RemoveVanillaSounds = new[] { "Whistle", "Airpump", "Dynamo", "BellRing", "BellPump" };
        c.Sounds = new List<SoundCfg> {
            new SoundCfg { Name = "RR Whistle", Clip = "Assets/G29_audio/g29_whistle_cnj3.wav", Port = "exhaust.WHISTLE_FLOW_NORMALIZED", Mixer = 12,
                Pos = new Vector3(-0.578f, 4.05f, 0.031f), MinDistance = 20f, MaxDistance = 1200f, Inertia = 0.08f,
                VolumeCurve = new[] { new Vector2(0, 0), new Vector2(0.05f, 0.3f), new Vector2(0.5f, 0.85f), new Vector2(1, 1) },
                PitchCurve = new[] { new Vector2(0, 0.9f), new Vector2(1, 1f) } },
            new SoundCfg { Name = "RR Bell", Clip = "Assets/G29_audio/g29_bell_rope.wav", Port = "bell.BELL_NORMALIZED", Mixer = 12,
                Pos = new Vector3(0f, 3.9f, 1.23f), MinDistance = 8f, MaxDistance = 600f },
            new SoundCfg { Name = "RR Air pump", Clip = "Assets/G29_audio/g29_airpump.wav", Port = "compressor.PRODUCTION_RATE_NORMALIZED", Mixer = 21,
                Pos = new Vector3(-1.2f, 2.4f, 0f), MinDistance = 3f, MaxDistance = 250f,
                VolumeCurve = new[] { new Vector2(0, 0), new Vector2(0.05f, 0.6f), new Vector2(1, 1) },
                PitchCurve = new[] { new Vector2(0, 0.85f), new Vector2(1, 1.05f) } },
            new SoundCfg { Name = "RR Dynamo", Clip = "Assets/G29_audio/g29_dynamo.wav", Port = "dynamo.DYNAMO_FLOW_NORMALIZED", Mixer = 7,
                Pos = new Vector3(0.03f, 4.07f, -0.71f), MinDistance = 3f, MaxDistance = 150f,
                VolumeCurve = new[] { new Vector2(0, 0), new Vector2(0.1f, 0.7f), new Vector2(1, 1) },
                PitchCurve = new[] { new Vector2(0, 0.9f), new Vector2(1, 1f) } },
        };

        // C14: share packs retain DV stock audio and contain no Railroader-extracted AudioClips.
        if (System.Environment.GetEnvironmentVariable("G29_SHARE") == "1") { c.Sounds.Clear(); c.RemoveVanillaSounds = new string[0]; }

        // RR red valve wheels: a row of five on the manifold above the backhead plate (mesh islands of the body mesh) and one
        // on the right (analysis\probe\backhead_report.txt); each is cut out of the exterior mesh and turns as a DV control
        const string Body = "Cylinder.002";
        c.Fittings = new List<FittingCfg> {
            new FittingCfg { Part = Body, Centre = new Vector3(-0.314f, 3.379f, -3.329f), Name = "Injector", Port = "injector.EXT_IN", Ctl = 17, Toggle = true, Notches = 18, Label = "car/injector" },
            new FittingCfg { Part = Body, Centre = new Vector3(-0.182f, 3.378f, -3.332f), Name = "Blowdown", Port = "blowdown.EXT_IN", Ctl = 18, Toggle = true, Notches = 10, Label = "car/water_dump" },
            new FittingCfg { Part = Body, Centre = new Vector3(-0.051f, 3.378f, -3.333f), Name = "Blower", Port = "blower.EXT_IN", Ctl = 19, Toggle = true, Notches = 18, Label = "car/blower" },
            new FittingCfg { Part = Body, Centre = new Vector3(0.182f, 3.378f, -3.332f), Name = "Air pump", Port = "compressorControl.EXT_IN", Ctl = 23, Toggle = true, Notches = 2, Label = "car/air_pump" },
            new FittingCfg { Part = Body, Centre = new Vector3(0.314f, 3.379f, -3.329f), Name = "Dynamo", Port = "dynamoControl.EXT_IN", Ctl = 24, Toggle = true, Notches = 2, Label = "car/dynamo" },
            new FittingCfg { Part = Body, Centre = new Vector3(0.660f, 2.839f, -3.225f), Name = "Sander", Port = "sander.CONTROL_EXT_IN", Ctl = 13, Toggle = true, Notches = 2, Label = "car/sander" },
        };

        // generated levers on the bare backhead plate: lower left and lower right of the disc (x -0.78..-0.5, 0.46..0.56)
        c.Placed = new List<PlaceCfg> {
            P("Damper", -0.78f, 2.35f, false, "damper.EXT_IN", 20, true, 8, "car/damper"),
            P("Coal dump", -0.68f, 2.35f, false, "coalDumpControl.EXT_IN", -1, false, 3, "car/ash_pan"),
            P("Cab light", -0.58f, 2.35f, false, "cabLight.EXT_IN", 12, true, 2, "car/cab_lights", 45f),
            P("Headlights", -0.70f, 2.05f, false, "headlightDecoder.HEADLIGHTS_EXT_IN", 10, false, 7, "car/headlights", 90f,
                s => CclLocoBuild.Phys(s, 0, 90, 7, 100, 5, 2, 0.5f, 0, 1, 0)),
            P("Lubricator", -0.60f, 2.05f, false, "lubricatorControl.EXT_IN", 25, false, 2, "car/lubricator", 35f,
                s => CclLocoBuild.Phys(s, 0, 35, 2, 1, 0, 1, 20, 1150, 0.85f, 200)),   // 4-6-2T priming handle
            P("Brake cutout", 0.46f, 2.35f, false, "brakeCutout.EXT_IN", 5, true, 2, "car/brake_cutout"),
            P("Bell", 0.56f, 2.35f, false, "bellControl.EXT_IN", 15, true, 2, "car/bell"),
        };

        c.Tender = CreateTender();
        return c;
    }

    // The tender (RR lt-260-g29): a DV car of kind Tender with the coal and water, on two RR Fox swing-bolster trucks
    // (fox-truck-2s, 0.8 m wheels, axles +-0.84 m) at +-truckSeparation/2 = 1.95 m.
    static LocoConfig CreateTender()
    {
        const float TruckZ = G29TenderDefs.TruckSeparation / 2f, AxleOff = 0.838f;
        var t = new LocoConfig
        {
            IsTender = true,
            CarId = "LLW_G29_Tender", CarName = "LLW G-29 Tender", Version = "0.9.2",
            Author = "MarquetteCreations (Railroader model), CCL port",
            Livery = "Lined ",                                            // RR liveries: Black, 'Lined ' (sic)
            SrcPrefab = G29Source.Tender,
            Work = "Assets/G29_DV/tender", BodyName = "G29_tender_body", BaseCarType = 8,   // S282Tender

            Components = G29Source.ResolveComps(G29Source.Tender, Comps(G29TenderDefs.Components)),
            MaterialMap = G29TenderDefs.MaterialMap, AnimationMap = G29TenderDefs.AnimationMap, Liveries = G29TenderDefs.Liveries,
            Wheelsets = G29TenderDefs.Wheelsets,
            WeightEmptyKg = G29TenderDefs.WeightEmptyLb * LbToKg,          // 25,401 kg; DV adds the coal and water containers
            WaterCapacityL = G29TenderDefs.WaterCapacityGal * GalToL,      // 22,712 L
            CoalCapacityKg = G29TenderDefs.CoalCapacityLb * LbToKg,        // 8,165 kg
            NestedClipGroups = true,

            WheelRadius = 0.418f,                                         // Fox truck tread r 0.420 about a 0.4176 axle (flange 0.445; RR says 0.8 m)
            CouplerHeight = 1.05f, CouplerInset = 0.30f,
            License = null, WheelslipFriction = 0.2f,

            RrEndFront = G29TenderDefs.PositionHead,                      // RR car end 3.875 (length/2): drawbar plane 4.375, 1 m from the loco end
            // rear coupler rig: from the measured end sill (core RigOnEndBeam); test1-7 had CouplingFaceRear -4.0 + 0.3 (buried)
            HideFrontCoupler = true,
            PlateDecals = new[] { ("[car plate anchor1]", "lettering2"), ("[car plate anchor2]", "lettering1") },

            Bogies = new List<BogieCfg> {
                new BogieCfg { Bogie = "BogieF", BogieCollider = "front", Axles = new[] { TruckZ + AxleOff, TruckZ - AxleOff } },
                new BogieCfg { Bogie = "BogieR", BogieCollider = "rear", Axles = new[] { -TruckZ + AxleOff, -TruckZ - AxleOff } },
            },
            Trucks = new List<TruckCfg> {
                new TruckCfg { Prefab = G29Source.Truck, Wheelset = "Wheel", Z = TruckZ },
                new TruckCfg { Prefab = G29Source.Truck, Wheelset = "Wheel", Z = -TruckZ },
            },

            // RR LoadAnimations: water surface and coal pile follow the tender's containers
            // + the water hatch lid (RR clip WaterHatch, 131 deg), opened by a hidden external lever on the lid handle
            LoadAnimations = new[] { ("Water", "", "water.NORMALIZED", false), ("Coal", "", "coal.NORMALIZED", false),
                                     ("WaterHatch", "", "waterHatch.EXT_IN", false) },
            SimControls = new[] { "waterHatch" },
            NoWalkParts = new[] { "Main/WaterHatch" },
            RrLevers = new List<RrLeverCfg> {
                new RrLeverCfg { Path = "Main/WaterHatch", AnimKey = "WaterHatch", Port = "waterHatch.EXT_IN", External = true, Hidden = true,
                    Phys = (s, a) => CclLocoBuild.Phys(s, 0, a, 5, 40, 5, 10, 10, 0, 1, 0),
                    Grip = new Vector3(0f, 2.72f, -2.48f), GripSize = new Vector3(0.35f, 0.12f, 0.15f) } },   // lid handle (BezierCurve.042)

            // coal is shovelled over the front bulkhead; coal and water fill at the RR LoadTargets
            CoalPile = body => (new Vector3(0, 2.3f, 2.75f), new Vector3(2.2f, 0.9f, 1.7f)),
            CoalTargetComp = "LoadTarget Coal", WaterTargetComps = new[] { "LoadTarget Water 1" },
            // hints (the core fits them to the model): wheel on the front face of the fireman's-side tank leg, facing the loco
            // (the leg's rounded end peaks at x -1.18, z 3.544); release out of the right frame sill between the trucks
            HandbrakeWheel = body => (new Vector3(-1.05f, 2.35f, 3.62f), new Vector3(0, 180, 0)),
            BrakeRelease = body => (new Vector3(1.55f, 1.1f, -0.3f), new Vector3(0, 180, 0)),

            ExteriorShots = new List<Shot> {
                new Shot(35, new Vector3(-16, 2.2f, 0f), new Vector3(0, 1.6f, 0f), "tender_left.png"),
                new Shot(35, new Vector3(8, 4.5f, 12f), new Vector3(0, 1.6f, 0.5f), "tender_front34.png"),
                new Shot(35, new Vector3(-7, 4.5f, -12f), new Vector3(0, 1.6f, -0.5f), "tender_rear34.png"),
                new Shot(35, new Vector3(-6, 0.8f, 0f), new Vector3(0, 0.5f, 0f), "tender_wheels_left.png"),
                new Shot(45, new Vector3(0.3f, 3.6f, 7f), new Vector3(0, 2.3f, 3.6f), "tender_front_face.png"),
                new Shot(35, new Vector3(-0.2f, 3.2f, 5.6f), new Vector3(-1.18f, 2.35f, 3.6f), "tender_handbrake.png"),
                new Shot(35, new Vector3(-2.2f, 2.9f, 3.9f), new Vector3(-1.18f, 2.35f, 3.6f), "tender_handbrake_side.png"),
                new Shot(35, new Vector3(4.0f, 1.0f, 0.9f), new Vector3(1.2f, 0.9f, -0.3f), "tender_release.png") },
        };

        t.CollisionBoxes = body => new List<(string, Vector3, Vector3)>
        {
            // front beam z 3.908 (drawbar 4.08), rear beam -3.738, tank body 3.473..-3.433
            ("frame", new Vector3(0, 0.85f, 0.06f), new Vector3(2.6f, 0.5f, 7.58f)),   // z -3.73..3.85
            ("tank", new Vector3(0, 1.95f, 0.02f), new Vector3(3.0f, 1.8f, 6.9f)),
        };
        return t;
    }
}






