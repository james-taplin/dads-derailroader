# Controls and the HUD

Railroader handles become Derail Valley controls through the reviewed vehicle record. Source levers use per-role starting joint physics. Functions without a source handle may receive a generated backhead control. These are recorded in `build/review.json` and need in-game validation.

Every newly built steam locomotive must show a numerical **km/h speed box in the F4 HUD**, including tank engines. Reviewed custom layouts enable the numerical speed slot; the vanilla fallback uses S282. The speed reading comes from the locomotive's km/h traction port and reports magnitude in either direction. This does not change the locomotive's boiler, sound or resource simulation basis. Rebuild older installed packs to obtain changes.

Cab instrument replacement starts with the C-25 boiler-pressure pilot. Its housing, dial, glass and needle resolve from local DV resources through CCL; the converter keeps the measured fitting separately. The donor's printed scale is 0–18 bar and its input is 1–19 bar absolute, so atmospheric pressure reads zero. Other physical instruments retain their existing build path until their bespoke fittings are implemented and tested. The F4 speed box remains required throughout that work.

Cabs with two source gauges now receive only **boiler pressure and brake pipe/cylinder pressure** at those source mounts. C-25 keeps its existing boiler/brake positions; K-35 uses its second boiler-gauge position for the brake instrument. Neither receives extra reservoir, chest or speed faces. Speed and reservoir readings remain available through invisible HUD readers. This replaces the earlier rule that added four physical instrument types to every cab; rebuild older packs to apply it. Mount visibility and control clearance still require per-locomotive checks.

## What must agree

For each control, trace **handle or input > reported value > simulation port > physical effect**. Grabbing the handle, using the F4 HUD, and keyboard or scroll input must reach the same control. Check the visible motion, full travel, detents, and small steps. A closed steam valve must command exactly zero flow under pressure (CTRL-02); fine input must respond without lag or overshoot (CTRL-01).

Momentary controls such as the whistle return to closed. Brake release placement follows BR-01: upright, red handle outward, hanger up. Generated cab light and other overridable controls must remain usable through their intended HUD and keyboard routes. See the [twelve acceptance gates](https://github.com/james-taplin/dads-derailroader#what-a-finished-pack-must-pass).

The exported-bundle audit checks that required HUD and driving controls have feeders. It cannot prove feel, collision ownership, exact steam closure, or save/reload behavior. Use [Testing a pack in Derail Valley](https://github.com/james-taplin/dads-derailroader/wiki/Testing-a-pack-in-Derail-Valley) to mark each input route pass, fail, or pending.
