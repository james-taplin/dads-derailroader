using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

// C21 first playable test configuration. Measurements: analysis/c21/integration-measurements-02.
// Original definitions and asset exports are retained. DV balance values are listed in DATA_SHEET.md.
public static class C21Config
{
    const float Lb = 0.45359237f, Gal = 3.785411784f, Inch = 0.0254f;
    const float Radius = 0.545f, Stroke = 23f * Inch;
    const float BoilerDiameter = 1.50f, BoilerLength = 5.0f;
    static float Volume => Mathf.PI * BoilerDiameter * BoilerDiameter / 4 * BoilerLength * 0.85f * 1000;
    static float Pull => 0.85f * 180f * 16f * 16f * 23f / (1.09f / Inch);
    static float Bore => Mathf.Sqrt(4 * (Pull * 4.4482216f * Radius / (180f * 0.0689476f * 1e5f * (2 / Mathf.PI) * (Stroke / 2) * 2)) / Mathf.PI);
    public static void Build() { C21Source.EnsureFlat(); CclLocoBuild.Run(LlwCatalogConfig.Apply(Create(), "ls-280-c21")); }
    static IEnumerable<Comp> Comps(C21Defs.Comp[] a) => a.Select(d => new Comp {kind=d.kind, name=d.name, parentPath=d.parentPath, extra=d.extra, pos=d.pos, rot=d.rot, scale=d.scale});
    static IEnumerable<Comp> Comps(C21TenderDefs.Comp[] a) => a.Select(d => new Comp {kind=d.kind, name=d.name, parentPath=d.parentPath, extra=d.extra, pos=d.pos, rot=d.rot, scale=d.scale});
    static PlaceCfg P(string name, float x, float y, bool wheel, string port, int ctl, string label, int notches=2, bool toggle=true)
        => new PlaceCfg { Name=name, X=x, Y=y, Wheel=wheel, Port=port, Ctl=ctl, Label="car/"+label, Notches=notches, Toggle=toggle };
    static RrLeverCfg Lever(string path, string clip, string port, int ctl, int notches, Vector3? grip=null, bool toggle=false,
        float spring=85f, float damper=15f, float mass=10f, float drag=15f, float scrollSpring=0f)
        => new RrLeverCfg {Path=path, AnimKey=clip, Port=port, Ctl=ctl, Grip=grip, GripSize=new Vector3(0.085f,0.085f,0.085f), Toggle=toggle,
            Phys=(s,a)=>CclLocoBuild.Phys(s,0,a,notches,spring,damper,mass,drag,0,1,scrollSpring)};

    public static LocoConfig Create()
    {
        var c = new LocoConfig {
            CarId="LLW_C21", CarName="LLW C-21", Version="0.1.4", Author="MarquetteCreations (Railroader assets), personal CCL conversion",
            Livery="Lined", SrcPrefab=C21Source.Loco, Work="Assets/C21_DV/loco", BodyName="C21_body", BaseCarType=6,
            ExtraParts=new[] {C21Source.Pilot, "Assets/LLWParts/c21parts/parts 1/headlight1.prefab", "Assets/LLWParts/c21parts/parts 1/handrail1.prefab"},
            Components=C21Source.ResolveComps(C21Source.Loco,Comps(C21Defs.Components)),
            MaterialMap=new Dictionary<string,string>(C21Defs.MaterialMap.Where(k=>k.Key!="Pump" && k.Key!="Plate" && k.Key!="Plate1").ToDictionary(k=>k.Key,k=>k.Value)) {
                {"AirPump",C21Defs.MaterialMap["Pump"]},{"Numplate",C21Defs.MaterialMap["Plate"]},{"Numplate2",C21Defs.MaterialMap["Plate1"]}},
            AnimationMap=C21Defs.AnimationMap, Liveries=C21Defs.Liveries, Wheelsets=C21Defs.Wheelsets,
            WeightEmptyKg=C21Defs.WeightEmptyLb*Lb-Volume*0.75f, WheelRadius=Radius, PonyRadius=0.345f, NestedClipGroups=true,
            SimBasis=1, License="SH282", HudType=20, Requirements=new[] {"DVCustomCarLoader"},
            WheelslipFriction=0.25f*(82000f/92000f)/(4f/5f),
            PortRefOverrides=new Dictionary<string,string> {{"boiler.FEEDWATER_TEMPERATURE",""}},
            SpawnTracks=new[] {300,400,1100,1400,1700},
            RrEndRear=C21Defs.PositionTail, HideBackCoupler=true,
            PlateDecals=new[] {("[car plate anchor1]","Decal 1"),("[car plate anchor2]","Decal 2")},
            CabZ=-3.65f, CabTeleportVolume=(new Vector3(0,2.65f,-3.25f),new Vector3(2.8f,2.3f,1.8f)),
            ExplosionAnchor=new Vector3(0,2.5f,0),
            EngineUnits=new List<EngineUnit> { new EngineUnit { DriverParts=new[] {"Main/Driver1","Main/Driver2","Main/Driver3","Main/Driver4"}, AnimKey="Drivers", GroupName="drivers" } },
            Bogies=new List<BogieCfg> {
                new BogieCfg { Bogie="BogieF", BogieCollider="front", AxleParts=new[] {"PilotTruck/Pilot","Main/Driver1","Main/Driver2"}, PivotAxle=1 },
                new BogieCfg { Bogie="BogieR", BogieCollider="rear", AxleParts=new[] {"Main/Driver3","Main/Driver4"}, PivotAxle=1 } },
            PonyTrucks=new List<(string,string)> {("Pilot","pony front")},
            ArticulatedParts=new List<(string,string)> {("Model/C21_body/PilotTruck","BogieF")},
            ReverserHandle="Main/Empty.061/Reverser.001", ReverserClip="Reverser", SparksX=0.72f,
            BrakeHangers=new[] {"Main/Brakes","Main/Empty.053","Main/Empty.055","Main/Empty.056","Main/Empty.062","Main/Empty.063"}, BrakeHangerClip="Brakes",
            CabControlObjects=new[] {"Main/Throttle","Main/TrainBrake","Main/LocoBrake","Main/Whistle","Main/Cocks"},
            NoWalkParts=new[] {"Main/RoofVent.001","Main/DoorEngineer","Main/DoorFireman","Main/WFL","Main/WFR","Main/WRL","Main/WRR"},
            WhistleLinkageClip="Whistle",
            LoadAnimations=new[] {("Throttle","","throttle.EXT_IN",false),("Cocks","","cylinderCock.EXT_IN",false),("FBDoor","","fireboxDoor.EXT_IN",false)},
            LoopAnimations=new[] {("Bell","bell.BELL_NORMALIZED",0.8f),("AirPump","compressor.PRODUCTION_RATE_NORMALIZED",1.5f)},
            BellSound=new Vector3(0,3.26f,1.308f), MainPressureGauge="BPG",
            BackheadZ=-3.20f, FireDoorCentre=new Vector3(0,1.80f,-3.23f), BackheadRayStartZ=-3.75f, LeverMaterial="black",
            LampKey=(t,b)=>null,
            LampLenses=new[] {("Head",new Vector3(0,3.046f,4.755f),0.28f,true)}, FrontLow=new[] {"Head"}, FrontHigh=new[] {"Head"},
            CabLightProbe=new Vector3(0,3.4f,-3.6f),
            ChimneyComp="Chuff", WhistleComp="Whistle", SafetyPos=new Vector3(0,3.55f,0.4f),
            BlowdownPos=new Vector3(1.3f,1.0f,-2.6f), DynamoPos=new Vector3(-0.029f,3.821f,-1.864f), CrackPos=new Vector3(0,0.5f,3.3f),
            CylinderLength=0.76f, ChuffType=0, WhistleSystem=3050,
            SndCab=new Vector3(0,2.8f,-3.5f), SndCylinders=new Vector3(0,0.7f,3.3f), SndWheels=new Vector3(0,0.54f,0),
            SndFire=new Vector3(0,1.8f,-3.2f), SndAirPump=new Vector3(-0.98f,2f,2.3f), SndCoalDump=new Vector3(0,1,-2.8f),
            SndCrownSheet=new Vector3(0,2.5f,-2.5f), SndSafety=new Vector3(0,3.55f,0.4f), SndSand=new Vector3(0,0.6f,1.2f),
            BrakeReleaseExact=true,BrakeRelease=b=>(new Vector3(-0.034f,0.85f,-3.5f),new Vector3(0,90,180)),BrakeReleaseSideX=0.934f,BrakeReleaseBoardBottomY=1.054f,
            RenderCabLight=new Vector3(0,3.4f,-3.6f),
            ExteriorShots=new List<Shot> {
                new Shot(35,new Vector3(-24,2.2f,1),new Vector3(0,2,1),"built_left.png"),
                new Shot(35,new Vector3(10,4.5f,16),new Vector3(0,1.9f,2),"built_front34.png"),
                new Shot(35,new Vector3(-10,5,-16),new Vector3(0,1.9f,-1),"built_rear34.png") },
            CabShots=new List<Shot> {
                new Shot(60,new Vector3(0,2.9f,-4.6f),new Vector3(0,2.6f,-2.5f),"built_cab_backhead.png"),
                new Shot(50,new Vector3(-0.35f,2.9f,-4.2f),new Vector3(-0.5f,2.45f,-3.2f),"built_backhead_left.png"),
                new Shot(50,new Vector3(0.35f,2.9f,-4.2f),new Vector3(0.5f,2.45f,-3.2f),"built_backhead_right.png") },
            LampShots=new List<Shot> {new Shot(35,new Vector3(4,3.5f,12),new Vector3(0,3.05f,4.74f),"built_lamps_front_lit.png")},
            ConsistShots=new List<Shot> {
                new Shot(35,new Vector3(-30,2.6f,-3),new Vector3(0,2,-3),"consist_left.png"),
                new Shot(45,new Vector3(-4,5,-8),new Vector3(0,1.8f,-4.3f),"consist_drawbar.png"),
                new Shot(35,new Vector3(-8,5,-20),new Vector3(0,1.8f,-7),"consist_rear34.png") }
        };
        foreach (var cc in c.Components.Where(x=>x.kind=="CylinderCock")) cc.pos=new Vector3(1.11f,0.234f,cc.pos.z);
        c.CollisionBoxes=b=>new List<(string,Vector3,Vector3)> {
            ("frame",new Vector3(0,1,0.5f),new Vector3(2.9f,1.1f,9.2f)),
            ("boiler",new Vector3(0,2.3f,0.5f),new Vector3(1.65f,1.7f,6.8f)),
            ("cab",new Vector3(0,2.65f,-3.05f),new Vector3(2.95f,2.3f,2.1f)) };
        // Reviewed cap-top islands in each moving connecting-rod mesh (analysis/c21/oil-anchors/rod_islands.txt).
        // Preserve the original side/index order: CCL assigns oil simulation ports by enumeration index.
        c.ValidateShallowOilAnchors=true;
        c.OilAnchors=new[] {
            new OilAnchor {Tag="MOP -1 0",SourcePath="Main/Empty.006/Connecting Rod Left",CarPosition=new Vector3(-0.91610f,0.43621f, 2.31946f),SourceTriangles=984},
            new OilAnchor {Tag="MOP -1 1",SourcePath="Main/Empty.006/Connecting Rod Left",CarPosition=new Vector3(-0.91610f,0.43621f, 0.74751f),SourceTriangles=984},
            new OilAnchor {Tag="MOP -1 2",SourcePath="Main/Empty.006/Connecting Rod Left",CarPosition=new Vector3(-0.91610f,0.43621f,-0.82769f),SourceTriangles=984},
            new OilAnchor {Tag="MOP -1 3",SourcePath="Main/Empty.006/Connecting Rod Left",CarPosition=new Vector3(-0.91610f,0.43621f,-2.31742f),SourceTriangles=984},
            new OilAnchor {Tag="MOP 1 0",SourcePath="Main/Empty.028/Connecting Rod Left.001",CarPosition=new Vector3(0.91610f,0.68887f, 2.57229f),SourceTriangles=984},
            new OilAnchor {Tag="MOP 1 1",SourcePath="Main/Empty.028/Connecting Rod Left.001",CarPosition=new Vector3(0.91610f,0.68887f, 1.00035f),SourceTriangles=984},
            new OilAnchor {Tag="MOP 1 2",SourcePath="Main/Empty.028/Connecting Rod Left.001",CarPosition=new Vector3(0.91610f,0.68887f,-0.57485f),SourceTriangles=984},
            new OilAnchor {Tag="MOP 1 3",SourcePath="Main/Empty.028/Connecting Rod Left.001",CarPosition=new Vector3(0.91610f,0.68888f,-2.06458f),SourceTriangles=984}
        };
        c.OilPoints=b=>c.OilAnchors.Select(a=>(a.Tag,a.CarPosition));
        c.SimSpec=b=>new Dictionary<string,Dictionary<string,object>> {
            ["steamEngine"]=new Dictionary<string,object> {{"numCylinders",2},{"cylinderBore",Bore},{"pistonStroke",Stroke},{"minCutoff",0.10f},{"maxCutoff",0.85f},{"throttleMaxFlow",3f},{"steamChestVolume",450f},{"maxCondensationRate",0.008f}},
            ["boiler"]=new Dictionary<string,object> {{"diameter",BoilerDiameter},{"length",BoilerLength},{"capacityMultiplier",0.85f},{"maxInjectorRate",6f},{"defaultFeedwaterTemperature",25f},{"waterConsumptionMultiplier",1f},{"maxBlowdownRate",15f},{"safetyValveOpeningPressure",13.41f},{"safetyValveClosingPressure",13.2f},{"maxSafetyValveVentRate",3f},{"spawnWaterLevel",Volume*0.75f}},
            ["firebox"]=new Dictionary<string,object> {{"maxCoalCapacity",100f},{"burnTime",180f},{"coalDumpRate",10f},{"coalConsumptionMultiplier",2f}},
            ["exhaust"]=new Dictionary<string,object> {{"passiveExhaust",0.4f}},
            ["poweredAxles"]=new Dictionary<string,object> {{"value",4f}},
            ["_notes"]=new Dictionary<string,object> {{"pull",$"RR fallback {Pull:F0} lbf; equivalent DV bore {Bore:F4} m, stroke {Stroke:F4} m"},{"boiler",$"Provisional model-envelope volume {Volume:F0} L; 75% spawn water"},{"mass","Working-order interpretation (C11): base=92000 lb minus provisional spawn boiler water; water restored by DV. Firebox/auxiliary contents remain additional. Not a historical field certification."}} };
        c.RrLevers=new List<RrLeverCfg> {
            // Working RGB-2 / G-29 lever physics from the guide. The 11/21 detents give 10% HUD steps as requested.
            Lever("Main/Throttle","Throttle","throttle.EXT_IN",0,11,new Vector3(0.87f,2.65f,-2.73f),spring:50,damper:15,mass:15,drag:10,scrollSpring:400),
            Lever(c.ReverserHandle,"Reverser","reverser.CONTROL_EXT_IN",1,21,new Vector3(0.876f,2.43f,-3.05f),spring:85,damper:15,mass:30,drag:15,scrollSpring:200),
            Lever("Main/TrainBrake","TB","brake.EXT_IN",2,11,new Vector3(0.57f,2.2f,-3.33f),spring:85,damper:15,mass:30,drag:16,scrollSpring:100),
            Lever("Main/LocoBrake","Indy","indBrake.EXT_IN",3,11,new Vector3(0.44f,2.3f,-3.37f),spring:65,damper:0,mass:30,drag:16,scrollSpring:100),
            Lever("Main/Cocks","Cocks","cylinderCock.EXT_IN",22,2,new Vector3(0.677f,1.65f,-2.79f),true,spring:85,damper:15,mass:10,drag:15,scrollSpring:0),
            new RrLeverCfg {Path="Main/Whistle",AnimKey="Whistle",Port="whistle.EXT_IN",Ctl=14,Grip=new Vector3(1.05f,3.35f,-2.65f),GripSize=new Vector3(0.12f,0.10f,0.1f),Phys=(s,a)=>CclLocoBuild.Phys(s,0,a,0,50,5,5,5,0,a/4,100)} };
        c.Placed=new List<PlaceCfg> {
            P("Injector",-0.65f,2.35f,true,"injector.EXT_IN",17,"injector",11,false),
            P("Blower",-0.23f,2.45f,true,"blower.EXT_IN",19,"blower",11,false),
            P("Compressor",-0.23f,2.7f,true,"compressorControl.EXT_IN",23,"air_pump"),
            P("Dynamo",0.20f,2.7f,true,"dynamoControl.EXT_IN",24,"dynamo"),
            P("Sander",0.48f,2.50f,false,"sander.CONTROL_EXT_IN",13,"sander"),
            P("Blowdown",-0.64f,2.10f,false,"blowdown.EXT_IN",18,"blowdown"),
            P("Damper",-0.54f,1.88f,false,"damper.EXT_IN",20,"damper",8),
            P("Fire door",0.32f,1.88f,false,"fireboxDoor.EXT_IN",21,"firebox"),
            P("Coal dump",-0.55f,1.65f,false,"coalDumpControl.EXT_IN",-1,"ash_pan",3,false),
            P("Cab light",-0.23f,2.20f,false,"cabLight.EXT_IN",12,"cab_lights"),
            P("Headlights",-0.51f,2.60f,false,"headlightDecoder.HEADLIGHTS_EXT_IN",10,"headlights",7,false),
            P("Lubricator",0.12f,2.45f,false,"lubricatorControl.EXT_IN",25,"lubricator",2,false),
            P("Brake cutout",0.49f,1.88f,false,"brakeCutout.EXT_IN",5,"brake_cutout"),
            P("Bell",-0.09f,2.70f,false,"bellControl.EXT_IN",15,"bell") };
        c.Tender=CreateTender();
        return c;
    }

    static LocoConfig CreateTender()
    {
        const float z=C21TenderDefs.TruckSeparation/2f, a=0.838f;
        return new LocoConfig {
            IsTender=true,CarId="LLW_C21_Tender",CarName="LLW C-21 Tender",Version="0.1.4",Author="MarquetteCreations (Railroader assets), personal CCL conversion",Livery="Lined ",
            SrcPrefab=C21Source.Tender,Work="Assets/C21_DV/tender",BodyName="C21_tender_body",BaseCarType=8,
            Components=C21Source.ResolveComps(C21Source.Tender,Comps(C21TenderDefs.Components)),
            MaterialMap=C21TenderDefs.MaterialMap,AnimationMap=C21TenderDefs.AnimationMap,Liveries=C21TenderDefs.Liveries,Wheelsets=C21TenderDefs.Wheelsets,
            WeightEmptyKg=C21TenderDefs.WeightEmptyLb*Lb,WaterCapacityL=C21TenderDefs.WaterCapacityGal*Gal,CoalCapacityKg=C21TenderDefs.CoalCapacityLb*Lb,
            NestedClipGroups=true,WheelRadius=0.418f,License=null,WheelslipFriction=0.2f,
            RrEndFront=C21TenderDefs.PositionHead,HideFrontCoupler=true,
            PlateDecals=new[] {("[car plate anchor1]","lettering 2"),("[car plate anchor2]","lettering1")},
            Bogies=new List<BogieCfg> {
                new BogieCfg {Bogie="BogieF",BogieCollider="front",Axles=new[] {z+a,z-a}},
                new BogieCfg {Bogie="BogieR",BogieCollider="rear",Axles=new[] {-z+a,-z-a}} },
            Trucks=new List<TruckCfg> {new TruckCfg {Prefab=C21Source.Truck,Wheelset="Wheel",Z=z},new TruckCfg {Prefab=C21Source.Truck,Wheelset="Wheel",Z=-z}},
            LoadAnimations=new[] {("Water","","water.NORMALIZED",false),("Coal","","coal.NORMALIZED",false)},
            CoalPile=b=>(new Vector3(0,1.90f,2.35f),new Vector3(1.9f,0.9f,0.6f)),CoalTargetComp="LoadTarget Coal",WaterTargetComps=new[] {"LoadTarget Water 1"},
            HandbrakeWheelExact=true,HandbrakeWheel=b=>(new Vector3(-1.175f,2.2f,2.61f),Vector3.zero),BrakeReleaseExact=true,BrakeRelease=b=>(new Vector3(0.33f,0.91f,-0.3f),new Vector3(0,90,180)),
            BrakeReleaseSideX=1.30f,BrakeReleaseBoardBottomY=1.096f,
            LampKey=(t,b)=>null,LampLenses=new[] {("Rear",new Vector3(-0.858f,2.706f,-2.53f),0.28f,false)},RearLow=new[] {"Rear"},RearHigh=new[] {"Rear"},
            LightsFrontPort="headlightsControlFront.EXT_IN",LightsRearPort="headlightsControlRear.EXT_IN",LightsFuse="fusebox.ELECTRONICS_MAIN",
            CollisionBoxes=b=>new List<(string,Vector3,Vector3)> {("frame",new Vector3(0,0.85f,0),new Vector3(2.6f,0.5f,5.85f)),("tank",new Vector3(0,1.8f,-0.05f),new Vector3(2.85f,1.65f,5.0f))},
            ExteriorShots=new List<Shot> {
                new Shot(35,new Vector3(-16,2.2f,0),new Vector3(0,1.6f,0),"tender_left.png"),
                new Shot(35,new Vector3(8,4.5f,12),new Vector3(0,1.6f,0.5f),"tender_front34.png"),
                new Shot(35,new Vector3(-7,4.5f,-12),new Vector3(0,1.6f,-0.5f),"tender_rear34.png") }
        };
    }
}
