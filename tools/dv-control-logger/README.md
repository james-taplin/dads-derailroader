# rr2dv control logger

A small Unity Mod Manager helper for tuning converted controls. It only reads; it never changes the game.

It writes `rr2dv-controls.log` in the Derail Valley folder. For the loco whose cab is loaded, every 0.1 s it compares
each cab control's value (0..1) and the sim port that control feeds, and logs:

- each control change: old -> new value, the change, the port value, and the most likely source: `keyboard` (the
  control's own key input moved it), `scroll`, `grab (mouse)`, `F4 HUD (mouse, cursor shown)`, or
  `no player input (sim or another mod)`;
- a port that changes while its control does not (`port changed without the control`): something else writes it;
- the watched sim ports at each change, then 1 s and 3 s later, to see what the simulation did.

The source is a best guess from what the player did in the last second (mouse, cursor, scroll, keys), except
`keyboard`, which is certain when the control's own keyboard input moved it.

Watched ports are listed in `watch.txt` in the mod folder (made on first start; one full port id per line, e.g.
`boiler.PRESSURE`). A port a loco does not have is skipped.

## Build and install

On Windows, with Derail Valley and Unity Mod Manager installed:

    powershell -ExecutionPolicy Bypass -File Build.ps1 -Dv "B:\SteamLibrary\steamapps\common\Derail Valley"

This compiles `Main.cs` with the .NET Framework 4 `csc` (C# 5, as our DVCCLControlFix helper) against the game's
`Managed` folder and copies the DLL and `Info.json` to `Mods\RR2DVControlLogger`. If the compile fails on references,
use DVCCLControlFix's own `Build.ps1` with this `Main.cs` and the output name `RR2DVControlLogger.dll`.

Untested: written in the cloud without the game's assemblies; the first build on Windows is its compile check.
