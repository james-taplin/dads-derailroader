# Controls and the HUD

Railroader handles become Derail Valley controls through the reviewed vehicle record. Source levers use per-role starting joint physics. Functions without a source handle may receive a generated backhead control. These are recorded in `build/review.json` and need in-game validation.

Every newly built steam locomotive must show a numerical **km/h speed box in the F4 HUD**, including tank engines. Reviewed custom layouts enable the numerical speed slot; the vanilla fallback uses S282. The speed reading comes from the locomotive's km/h traction port and reports magnitude in either direction. This does not change the locomotive's boiler, sound or resource simulation basis. Rebuild older installed packs to obtain changes.

The testing branch has measured instrument fittings for all 21 steam cabs. Boiler and chest pressure use complete DV pressuremeter resources through CCL. Brake and speed dials use the same housing/glass with standalone faces and needles. The converter keeps each loco's placement, scale and backing contacts in the master tuning data. Boiler/chest printed 0–18 bar corresponds to 1–19 bar absolute; brake printed 0–10 corresponds to 1–11 absolute, so released brakes read zero. Speed and chest needles use DV damping.

Cabs fitted for two instruments receive **boiler and brake pipe/cylinder pressure** (C-25, K-35). Three-instrument layouts add speed; four add steam-chest pressure. Numerical speed and reservoir remain on F4. Complete cases use measured backing pads or mounting studs; no extra faces are placed beside neighbouring dials. Rebuild from the testing branch to apply the fleet pass; published 0.4.4 predates it. Visibility, glass appearance and control clearance still require per-locomotive game checks. See [the fleet fitting report](https://github.com/james-taplin/dads-derailroader/blob/claude/unity-crash-message/docs/cab-gauge-fleet-pass-2026-10-02.md) for the complete layout list.

## What must agree

For each control, trace **handle or input > reported value > simulation port > physical effect**. Grabbing the handle, using the F4 HUD, and keyboard or scroll input must reach the same control. Check the visible motion, full travel, detents, and small steps. A closed steam valve must command exactly zero flow under pressure (CTRL-02); fine input must respond without lag or overshoot (CTRL-01).

Momentary controls such as the whistle return to closed. Brake release placement follows BR-01: upright, red handle outward, hanger up. Generated cab light and other overridable controls must remain usable through their intended HUD and keyboard routes. See the [twelve acceptance gates](https://github.com/james-taplin/dads-derailroader#what-a-finished-pack-must-pass).

The exported-bundle audit checks that required HUD and driving controls have feeders. It cannot prove feel, collision ownership, exact steam closure, or save/reload behavior. Use [Testing a pack in Derail Valley](https://github.com/james-taplin/dads-derailroader/wiki/Testing-a-pack-in-Derail-Valley) to mark each input route pass, fail, or pending.
