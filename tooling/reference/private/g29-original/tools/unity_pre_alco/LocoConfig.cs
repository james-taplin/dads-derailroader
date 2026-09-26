using System;
using System.Collections.Generic;
using UnityEngine;

// Everything that is specific to one Railroader car. CclLocoBuild reads only this; a new conversion copies an existing
// config (RlwConfig.cs = RBBM-1t tank loco, RgbConfig.cs = RGB-2 tender loco), fills these in (probe renders + build report
// make it quick) and adds anything the core can't express as a hook.
// Optional sections: leave null / empty and that step is skipped (e.g. no pony trucks, no fire-door leaves, no lamps).
// A tender is a second LocoConfig with IsTender = true, hung off the loco's Tender field: it is built into the same pack.
public class LocoConfig
{
    // ---- identity / source
    public string CarId, CarName, Author, Version;
    public string Livery;                       // RR livery name (from the generated defs) baked into the materials
    public string SrcPrefab;                    // AssetRipper export prefab of the body
    public string[] ExtraPrefabs = new string[0];   // e.g. RR headcode lamp prefabs, instantiated under ExtraPrefabsGroup
    public string[] ExtraParts = new string[0];      // prefabs modelled in car space (pack parts), instantiated at their own root pose under ExtraPrefabsGroup
    public string ExtraPrefabsGroup = "[extra prefabs]";
    public string Work;                         // generated asset folder (deleted and rebuilt every run)
    public string BodyName;                     // name of the RR body under Model
    public int BaseCarType = 6;                 // CarWizard base (6 = LocoS060, 8 = S282Tender)
    public string ReportTitle;

    // ---- tender (RR 'tenderIdentifier'): a separate DV car of kind Tender, coupled rigidly behind the loco
    public bool IsTender;                       // this config is a tender (CarWizard kind Tender, TenderSimCreator, no cab)
    public LocoConfig Tender;                   // loco only: its tender, built into the same pack
    public int[] SpawnTracks = new int[0];      // loco only: CCL SpawnTrack ids where loco + tender spawn together

    // ---- generated RR definition data (gen_defs.py output)
    public List<Comp> Components;
    public Dictionary<string, string> MaterialMap, AnimationMap;
    public (string name, (string id, string hex)[] colors)[] Liveries;
    public (float offset, float length, float diameter, int axles, string clip)[] Wheelsets;
    public float WeightEmptyKg, WaterCapacityL, CoalCapacityKg;

    // ---- physics / DV assets
    public float WheelRadius, CouplerHeight = 1.05f, CouplerInset = 0.30f;
    public string License = "SH282";            // DV GeneralLicenseType id (null for a tender)
    public int HudType = 20;                    // CCL BaseHUD: S060 25, S282 20, Custom 1000
    public float WheelslipFriction = 0.2f;      // x (weight on drivers / total) - DV counts all weight as adhesive
    public float WheelsHP = 2000f, MechanicalPowertrainHP = 2000f;
    public int SimBasis = 0;                    // SteamerSimCreator basis (0 S060, 1 S282 = tender ports); every value is then overridden
    public Func<Transform, Dictionary<string, Dictionary<string, object>>> SimSpec;   // RefBody -> sim component -> field -> value
    public Dictionary<string, string> PortRefOverrides = new Dictionary<string, string>();  // sim port reference -> port ("" = unconnected)
    public string[] Requirements = { "DVCustomCarLoader" };

    // ---- body clean-up and fixed parts
    public string[] RemoveObjects = new string[0];      // stray RR objects
    public string[] ExtraWalkableParts = new string[0]; // visible meshes that need walkable colliders (RR climbs via Ladder)
    public string[] NoWalkParts = new string[0];        // RR MeshColliders on moving parts (rods): no static walkable copy
    public Func<Transform, List<(string name, Vector3 centre, Vector3 size)>> CollisionBoxes;  // body -> [collision] boxes
    public string BufferFront, BufferRear;               // renderers whose bounds give the buffer faces
    public float? CouplingFaceFront, CouplingFaceRear;   // explicit coupling planes (z) where there are no buffers (drawbar end)
    public bool HideFrontCoupler, HideBackCoupler;       // DV screw-link coupler visuals (hidden on the loco-tender drawbar)
    public (string anchor, string decalComp)[] PlateDecals = new (string, string)[0];
    public string CabSeatComp; public float CabSeatOffsetZ = 0.3f;
    public float? CabZ;                                  // [cab] teleport z when the RR seats are not in the cab
    public (Vector3 centre, Vector3 size)? CabTeleportVolume;   // car-space box the teleport pointer hits (default 2.6 x 2.2 x 1.8 m above [cab])
    public Vector3 ExplosionAnchor;
    public Action<GameObject, string> BodyExtras;          // (body, generated asset folder): add static parts, e.g. RR decal images

    // ---- running gear: one DV custom bogie per engine unit (Mallet: two units), or an explicit Bogies layout (rigid frames)
    public List<EngineUnit> EngineUnits = new List<EngineUnit>();
    public List<BogieCfg> Bogies = new List<BogieCfg>();   // if set: bogies from these, EngineUnits only animate
    public List<(string animKey, string groupName)> PonyTrucks = new List<(string, string)>();
    public float PonyRadius;
    public string ReverserHandle, ReverserClip;         // RR cab handle inside the reverser clip (becomes an interior control)
    public float SparksX = 0.72f;
    public List<TruckCfg> Trucks = new List<TruckCfg>();  // RR truck prefabs (tender wheelsets): wheel meshes go under the bogie axles

    // ---- cab and load animations
    // Nested RR models (GN M-2): clip objects sit deep in the hierarchy and clips share top-level masters. Each clip is split
    // by region, its Animator goes on a node under the objects' deepest common parent and a re-rooted copy of the clip is
    // played there. Wheel clips then run at clip.length x revs/s (RR wheel clips are one revolution over their length).
    public bool NestedClipGroups;
    public string[] CabControlObjects = new string[0];  // RR objects that become interior controls (removed from exterior)
    public string WhistleLinkageClip;                   // rest of the whistle clip, port-driven on the exterior
    public string[] FireDoorLeaves = new string[0];     // swing +-80 deg with fireboxDoor.EXT_IN
    public (string animKey, string objectPath, string port, bool perWaterCapacity)[] LoadAnimations = new (string, string, string, bool)[0];
    public (string part, string animKey) Handbrake;     // RR handbrake object animated by the DV handbrake
    public (string animKey, string port, float cyclesPerSecond)[] LoopAnimations = new (string, string, float)[0];   // looped RR clips whose speed follows a port (bell swing)
    public Vector3? BellSound;                          // steam bell audio anchor (sim bell = SteamerSimCreator 'bell'); null: no bell sound
    public List<(string path, string bogie)> ArticulatedParts = new List<(string, string)>();   // car-root paths hung on a DV bogie (Mallet front engine swings with it)
    public string[] BrakeHangers = new string[0]; public string BrakeHangerClip; public float BrakeHangerMaxBar = 3.5f;
    public Func<Transform, IEnumerable<(string tag, Vector3 pos)>> OilPoints;   // RefBody -> oil cup anchors
    public CoalLoadCfg CoalLoad;

    // ---- interior
    public string MainPressureGauge = "PSI";            // RR BoilerPressure gauge that reads boiler pressure (others: steam chest)
    public string FireboxBackheadPart, FireDoorPart;
    public float? BackheadZ; public Vector3? FireDoorCentre;   // explicit backhead plane z and fire door centre (one-mesh bodies)
    public List<RrLeverCfg> RrLevers = new List<RrLeverCfg>();
    public List<FittingCfg> Fittings = new List<FittingCfg>();   // RR mesh islands turned into controls
    public List<PlaceCfg> Placed = new List<PlaceCfg>();         // generated controls raycast onto the backhead
    public float BackheadRayStartZ = -3.55f;
    public string LeverMaterial = "Handles";

    // ---- lights (RR lamp models): key lookup from each 'Lamp Inside' renderer, then which keys light per setting
    public Func<Transform, Bounds, string> LampKey;     // (renderer transform, reflector bounds) -> key or null
    public (string key, string glassPart, bool front)[] GlassLamps = new (string, string, bool)[0];   // lamps without a 'Lamp Inside' reflector: lens on this glass part
    public string[] FrontLow = new string[0], FrontHigh = new string[0], FrontRed = new string[0];
    public string[] RearLow = new string[0], RearHigh = new string[0], RearRed = new string[0];
    public Vector3? CabLightProbe;                      // point under the cab roof (raycast up for the ceiling)
    public string LightsFrontPort = "headlightDecoder.FRONT_HEADLIGHTS_EXT_IN", LightsRearPort = "headlightDecoder.REAR_HEADLIGHTS_EXT_IN";
    public string LightsFuse = "fuseboxDummy.ELECTRONICS_MAIN";   // tender: fusebox.ELECTRONICS_MAIN (fed by the loco dynamo)

    // ---- particles / sound anchors
    public string ChimneyComp = "Chuff 1", WhistleComp = "Whistle 2", SafetyValvePart;
    public Vector3? SafetyPos;                          // explicit safety valve steam anchor (one-mesh bodies)
    public Vector3 BlowdownPos, DynamoPos, CrackPos;
    public bool FourCylinderCocks;                      // Mallet: 4 cylinders x 2 drain jets (CCL template covers 2)
    public float CylinderLength = 0.8f;                 // single RR CylinderCock anchor: rear drain jets this far behind it
    public int ChuffType = 1;                           // CopyChuffSystem 0 S060, 1 S282
    public int WhistleSystem = 3050;                    // CopyVanillaAudioSystem 3050 S060 / 3100 S282
    public Vector3 SndCab, SndCylinders, SndWheels, SndFire, SndAirPump, SndCoalDump, SndCrownSheet, SndSafety, SndSand;

    // ---- external interactables
    public Func<Transform, (Vector3 pos, Vector3 euler)> HandbrakeWheel, BrakeRelease;   // null HandbrakeWheel: no DV [brake small]
    public string CoalPileWallPart, CoalTargetComp;     // null: no coal pile / no coal receiver on this car
    public Func<Transform, (Vector3 centre, Vector3 size)> CoalPile;   // explicit shovel trigger (tender coal doors)
    public string[] WaterFillerParts = new string[0];
    public string[] WaterTargetComps = new string[0];   // RR LoadTarget components that take water (tender filler)

    // ---- render check cameras (pos, look, fov, file); phases: exterior, cab (interior instantiated, LOD hidden), lamps lit
    public List<Shot> ExteriorShots = new List<Shot>(), CabShots = new List<Shot>(), LampShots = new List<Shot>(), MarkerShots = new List<Shot>();
    public List<Shot> ConsistShots = new List<Shot>();  // loco + tender coupled
    public Vector3 RenderCabLight;
}

public class Comp { public string kind, name, parentPath, extra; public Vector3 pos, scale; public Quaternion rot; }
public class EngineUnit { public string[] DriverParts; public string AnimKey, GroupName, Bogie, BogieCollider; public float StartOffset; }
// Bogie = the DV bogie object (BogieF/BogieR); its pivot (where the car body rests on it) is axle PivotAxle (0 = frontmost),
// or the axle average when -1. Axles = z of each [axle] (joint audio and wheel spin); AxleParts gives them from RR parts instead.
// Rigid frames: pivot on the end axles, so the body follows the chord between the outermost axles as the real frame does.
public class BogieCfg { public string Bogie, BogieCollider; public string[] AxleParts; public float[] Axles; public int PivotAxle = -1; }
// RR truck prefab placed at z (RR truck origin), optionally turned 180 deg; renderers named Wheelset* go under the nearest axle.
public class TruckCfg { public string Prefab, Wheelset; public float Z; public bool Reversed; public string[] Remove = new string[0]; }
public class CoalLoadCfg { public string Comp, BunkerPart; public float FullHeight = 1.4f, EmptyFraction = 0.07f; public Vector3? Pivot; public Vector2 Footprint; }
// Grip: world centre of the lever's collider box (default: the handle end found from the mesh); Toggle: keyboard toggles it
public class RrLeverCfg { public string Path, AnimKey, Port; public int Ctl = -1; public Action<Component, float> Phys; public bool External, Handbrake, Toggle; public string Label; public Vector3? Grip; public Vector3 GripSize = new Vector3(0.12f, 0.12f, 0.12f); }
public class FittingCfg { public string Part, Name, Port, Label; public Vector3 Centre; public int Ctl = -1, Notches = 2; public bool Toggle; }
public class PlaceCfg { public string Name, Port, Label; public float X, Y, Range; public bool Wheel, Toggle; public int Ctl = -1, Notches = 2; public Action<Component> Phys; }
public class Shot { public Vector3 Pos, Look; public float Fov = 35; public string File; public Shot(float fov, Vector3 pos, Vector3 look, string file) { Fov = fov; Pos = pos; Look = look; File = file; } }





