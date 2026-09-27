# Later: replacing dependencies with vanilla Derail Valley content

Status: **parked** (James, W25). rr2dv now uses every dependency the loco has in the user's own Railroader
install, copied from their own drive into their own Derail Valley Mods folder. This note keeps what we learned about
replacing dependencies, so the work can be picked up again. It was implemented in commits ec11e5c, 06981e4 and
a9c1670 (git history) and taken out of the default path in the W25 scope change.

## What was built and tested

- Every Railroader truck object (tender and car trucks, never a loco's own driving gear) swapped for a vanilla DV
  bogie; the truck's bundle never staged or exported, its definition read only to list what the swap leaves out
  (brake animation, load animations such as the GN M-2 tender truck's coal).
- Parts and images that were Railroader game content (any path under `Railroader_Data`) or came from a restricted
  mod left out, never staged or opened, removed from the record's Components together with any component anchored
  inside them, listed in `inventory.left_out` / `metadata.leftOut` with a reason and an effect.
- X32 (140 installed mods): 66 truck replacements across 91 steam locos, 10 of them base-game trucks from
  `Railroader_Data/StreamingAssets/AssetPacks`, detected correctly. No installed loco used a base-game or restricted
  part or image, so that branch was only unit-tested.

(Left out by default today: only parts whose asset is missing from their own pack's catalogue, which Railroader
cannot load either.)

## CCL facts (custom-car-loader v3.1.9, MIT)

- `CCL.Types/BogieBufferTypes.cs`: `BogieType` Default = 200 (DV's freight bogie), DE2 = 10, S282 = 20, DM1U = 35,
  DE6 = 40, DH4 = 50, Microshunter = 70, UtilityFlatbed = 220, Handcar = 700, Custom = 10000. The others are
  locomotive bogies; there is no S282-tender type, so Default is the only fit for a tender.
- `CCL.Importer/Processing/BogieProcessor.cs`: a non-custom bogie is copied from the vanilla car
  (`(TrainCarType)bogie`), placed at our `BogieF`/`BogieR` position; its collider is copied from the base car.
- `CCL.Creator/Wizards/CarPrefabManipulators.cs` `GetBogieOffset`: Default 1.00 m, DE6 2.03 m, DH4 1.10 m
  (half wheelbase). `CarWizard.cs`: default car `wheelRadius` 0.459 m. Source-derived, not measured in game.
- `CCL.Types/Components/MeshGrabber.cs`: 2,645 vanilla meshes a custom car can borrow at runtime. No loose steam
  fittings: no stacks, pilots, plows, ladders, handrails, marker lamps or bell bodies; only S060/S282 headlight glass,
  bell clapper/hammer, lanterns (`OilLantern`, `EOTLantern`). So parts could only be left out, not swapped (X31: the
  oil lantern is at most a reviewed decorative marker candidate).

## Builder work it needs (X31, local tooling)

- A per-car field (e.g. `VanillaBogie`, BogieType int) with reviewed front/rear centres; CclLocoBuild sets
  `CustomCarVariant.FrontBogie/RearBogie` from it instead of 10000, keeps BogieF/BogieR anchors at the centres.
- Skip source-truck dependency collection (the material walk includes `Cfg.Trucks`) as well as mesh building.
- Branch BuildRunningGear: the tender and powered paths dereference `BogieF/BogieR/bogie_car/ContactPoints` for sparks.
- Separate passive/tender audit coverage in `audit_new_loco.py`; do not weaken the locomotive checks.
- In game: body fit on the bogie (bolster height unknown), wheel motion, brakes/sparks, coupling, save/reload.
