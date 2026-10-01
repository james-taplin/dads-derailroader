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
