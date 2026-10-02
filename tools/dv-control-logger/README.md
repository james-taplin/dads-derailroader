# rr2dv control logger

A small Unity Mod Manager helper for tuning converted controls. It only reads; it never changes the game.

It writes `rr2dv-controls.log` in the Derail Valley folder. For the loco whose cab is loaded, every 0.1 s it compares
each cab control's value (0..1) and the sim port that control feeds, and logs:

- each control change: old -> new value, the change, the port value, and the most likely source: `keyboard` (the
  control's own key input moved it), `scroll`, `grab (mouse)`, `F4 HUD (mouse, cursor shown)`, or
  `no player input (sim or another mod)`;
- a port that changes while its control does not (`port changed without the control`): something else writes it;
- the watched sim ports at each change, then 1 s and 3 s later, to see what the simulation did, with the car's brake
  pressures (brake pipe, main reservoir, cylinder) where DV exposes them;
- each call that reaches one of DV's overridable controls (the route the F4 HUD, keyboard and remote use), with its
  value, when it changes (`overrider ...`), and whether the cursor was shown (F4 HUD or a menu).

The source is a best guess from what the player did in the last second (mouse, cursor, scroll, keys), except
`keyboard`, which is certain when the control's own keyboard input moved it.

Watched ports are listed in `watch.txt` in the mod folder (made on first start; one full port id per line, e.g.
`boiler.PRESSURE`). A port a loco does not have is skipped without calling the game's error-logging lookup. The old generated `exhaust.WHISTLE_CONTROL` entry is mapped to `whistle.EXT_IN` in memory; the user's watch file is preserved.

This is a separate, optional developer diagnostic mod. The converter does not install it in a converted pack. Its source lives under `tools/`, outside the app's `src/` and the release source-package selection. The app's own conversion logs are a different logging system.

## Build and install

On Windows, with Derail Valley and Unity Mod Manager installed:

    powershell -ExecutionPolicy Bypass -File Build.ps1 -Dv "B:\SteamLibrary\steamapps\common\Derail Valley"

This compiles `Main.cs` with the .NET Framework 4 `csc` (C# 5, as our DVCCLControlFix helper) against the game's
`Managed` folder and copies the DLL and `Info.json` to `Mods\RR2DVControlLogger`. If the compile fails on references,
use DVCCLControlFix's own `Build.ps1` with this `Main.cs` and the output name `RR2DVControlLogger.dll`.

2026-10-02 validation: compiled against DV build 99's installed assemblies. `tests/unity_runtime/LoggerPortRegression.cs` checks 330 absent-port reads, a valid whistle value and a null simulation without invoking Unity logging. The implementation reads the game's private read-only port dictionary; if a future game version changes that field, it records one compatibility message and omits optional snapshots. New in-game validation and installation of this revised helper are still pending.
