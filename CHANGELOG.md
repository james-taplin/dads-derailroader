Version 0.4.5

- 2 october rebuild, fixed the oil cup build stop when Railroader source file hashes differ, byte differences are reported and every fitting is checked against the current model and motion before export [download the updated app, changed bearings, axles, parents or clearance still stop for fitting review]

- fitted moving oil cups across all 21 steam locos, with a supported left and right pair at every driven axle and extra cups on clear running gear bearings, six to twelve cups required [rebuild packs, appearance and oil can access still need checking in game]
- corrected oil cup anchor coordinates and checked support, clearance and spacing through a complete wheel turn so cups ride their parent parts
- fitted complete cab instruments across all 21 steam locos, with bespoke two, three or four gauge layouts, boiler and pipe and application brakes first, then speed and steam chest pressure where mounts allow [rebuild packs, cab visibility and control clearance still need checking in game]
- added housed standalone brake and speed dials, corrected brake atmospheric-zero calibration, and retained numerical km/h on every F4 HUD
- updated the master vehicle table with measured gauge and oil cup supports, fitting coordinates and current repair status
- retained C-40's accepted tender beam band for ordinary rebuilds
- included the nested zip packaging repair from main, all catalogue pages and the bundled Python library are loose files, future nested archives stop packaging [pages still selected per loco and matching tender]
- known issue, C-25 coupling tilt and the outstanding 0.4.4 issues remain open
- automated and native Unity checks passed, the latest rebuilt packs still need in game acceptance

Version 0.4.4

- repackaged catalogue pages and the bundled Python standard library as loose files, removing nested ZIPs from both downloads; catalogue pages are retained and future nested archives stop release packaging

- made dynamo steam jets follow the measured exhaust spout direction, correcting the blanket 180-degree turn that sent C-25's steam forwards [rebuild existing packs; still needs checking in game]
- started the cab instrument replacements with C-25's boiler gauge, using the vanilla pressuremeter housing, face, glass and needle with matched pressure calibration [pilot only; appearance and control clearance still need checking in game]
- made the numerical km/h box a required F4 HUD feature for every steam loco, including tank engines, with the S282 layout as the vanilla fallback [rebuild existing packs; still needs checking in game]
- corrected tender truck wheel pivots so the wheels spin around their source axle centres instead of orbiting around them [rebuild existing packs; still needs checking in game]
- limited two-gauge cabs, currently C-25 and K-35, to boiler pressure and brake pipe/cylinder instruments, removing the extra unsupported reservoir and speed faces; numerical speed and reservoir readings remain on F4 [rebuild existing packs; K-35's reused brake mount still needs checking in game]
- known issue, C-25 can tilt slightly when coupled to its tender and return level when uncoupled; coupling physics investigation remains open
- known issue, the outstanding 0.4.3 issues still apply, including cab controls, labels, lights, tender brake release placement and other coupling or animation problems
- automated and native Unity checks passed; the latest rebuilt packs still need in-game acceptance

Version 0.4.3

- added vehicle catalogue pages, icons and diagrams for all 21 steam locos and their tenders [rebuild existing packs to include them; appearance still needs checking in game]
- fixed whistle meshes being attached to a similarly named cab control, which could make the whistle move when pulling the lever
- corrected tender coal and water animation grouping so the two loads can animate independently
- corrected water sight glasses so the water column fills upwards from the bottom
- added the missing boiler-water HUD reading on locos without a suitable sight-glass reader, including P-18
- corrected the tank locomotive licence identifier to S060 [licence behaviour still needs checking in game]
- safety steam now uses a measured fallback on the front boiler or dome surface, with the jet pointing upwards and its sound at the same position [placement still needs checking in game, especially K-28T]
- fixed missing-port error spam in the separate optional control logger [developer tool; not included in the app download]
- known issue, the outstanding 0.4.2 issues still apply, including coupling gaps or overlaps, tender brake release placement, cab controls, floating labels or dials, lights and bell cords
- this is a test release: automated checks passed, but these repairs have not yet been fully tested in game

Version 0.4.2

- oil cups are now placed on the modelled oiling nubs on the rods, whichever nub has the best clearance at each end [untested in game, falls back to the old flat spot where there is no clear nub]
- F-71 and C-55 main rods are now found, F-71 now gets oil cups
- fixed trailing wheel, reverser and door window animations being dropped where the part name ended in a space [P-18, P-43, T-22]
- C-55 now builds, its tender hatch, coal, water, brake rig and cut lever animations are in
- every tender now gets number plates, taken from the side lettering [first guess at the position, check them in game]
- a tender door or hatch animation that cannot be resolved is left out and listed instead of stopping the build
- settings, runs and logs now live in an rr2dv_work folder beside the app [old AppData settings are not read]
- a crashed Unity now says so, with the exit code explained and the last lines of its log
- warns when the Unity, work folder, user profile or temp paths contain non-english characters
- the release packages now include the changelog, readme, wiki and docs
- known issue, the 0.4.1 known issues still apply
- known issue, couplings between loco and tender may overlap or sit too far apart on some locos
- known issue, the tender brake release may point sideways on several tenders
- known issue, P-43 gets a generated reverser lever in place of the original one
- known issue, T-21 blower and coal dump levers may collide

Version 0.4.1

- settings, runs and logs now live in an rr2dv_work folder beside the app instead of hidden system folders, a workRoot you already set still wins [your old settings in AppData are not read, copy machine.json across or set the paths again]
- a crashed Unity now says so, with the exit code explained and the last lines of the Unity log in the error
- warns when the Unity, work folder, user profile or temp paths contain non-english characters, these can make Unity 2019.4 crash on some systems
- trailing wheel animations now work on locos where the node name ended in a space [P-18 trailing wheels]
- fixed reverser and reverser latch animations being dropped on P-43, and a cab window animation on T-22
- tenders now get number plates, from the road number decals, else the side lettering, else the middle of each side [placement is a first guess, check them in game]
- a tender door or hatch animation that cannot be resolved is left out and listed in the build report instead of stopping the whole build [C-55 now builds, its tender water hatch will not open yet]
- the finished box no longer triggers a false window not responding log entry
- known issue, F-71 gets no oil cups because no main rod end seat is found
- known issue, couplings between loco and tender may overlap or sit too far apart, worst on G-25 and K-35, which may show humping
- known issue, the tender brake release may point sideways on C-40, F-71, G-25, P-43, P-48, S-23 and T-21
- known issue, T-21 blower and coal dump levers may collide
- known issue, other tender animations that point at missing parts may be left out, such as coal, brake rig and cut lever
- known issue, the 0.4.0 known issues still apply

Version 0.4.0

- first public test version of the stock locomotive edition, converts Railroader's own 21 steam locomotives into Derail Valley packs
- stock steam only, mod support has been removed and diesels are not included yet
- needs Railroader, Derail Valley with Custom Car Loader, AssetRipper and Unity 2019.4.40f1 set up in settings, windows only
- one click personal use notice before anything is installed, the assets belong to the Railroader developers and rights holders, no sharing without their permission
- every loco comes with sensible answers already filled in, you just confirm them before it builds
- an unknown game build is reported and never refused
- vehicle option to pick the whistle mesh from Railroader's 23 whistles, the default is the standard 3 chime
- normal Derail Valley gauges on every loco, including boiler pressure, brake and speed
- oil cups on the main rod ends as matched left and right pairs
- throttle and cut-off have fewer notches and move more freely, the whistle springs back to zero when released
- known issue, drive via keyboard or the F4 hud for now, cab controls are at your own risk
- known issue, controls may be stiff or twitchy, and the whistle may take over a second to reach full when you hold the key
- known issue, some controls only work via the cab or the keyboard
- known issue, lights may not turn off and headlight lenses might be broken
- known issue, dials can float in the air
- known issue, only one pair of oil cups per loco
- known issue, the tender brake release on S-23 and P-48 may point sideways instead of sitting on the tender
- known issue, B-65 loco and tender may overlap slightly at the coupling, P-48 couplings may not quite meet
- known issue, P-48 front doors are missing
- known issue, bell cords are left out on K-35 because they stretched in game, other locos with bell cords may show the same stretched line
- known issue, some parts get a plain gunmetal or coal colour where the original material could not be used, so coal piles and some details may look off
- known issue, whistle sound is still the Derail Valley one, only the mesh changes with your choice
- known issue, the latest control feel, safety valve and bell cord changes were not tested in game before this release
