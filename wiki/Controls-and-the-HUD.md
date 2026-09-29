# Controls and the HUD

Railroader handles become Derail Valley controls through the reviewed vehicle record. Source levers use per-role starting joint physics. Functions without a source handle may receive a generated backhead control. These are recorded in `build/review.json` and need in-game validation.

## What must agree

For each control, trace **handle or input > reported value > simulation port > physical effect**. Grabbing the handle, using the F4 HUD, and keyboard or scroll input must reach the same control. Check the visible motion, full travel, detents, and small steps. A closed steam valve must command exactly zero flow under pressure (CTRL-02); fine input must respond without lag or overshoot (CTRL-01).

Momentary controls such as the whistle return to closed. Brake release placement follows BR-01: upright, red handle outward, hanger up. Generated cab light and other overridable controls must remain usable through their intended HUD and keyboard routes. See the [twelve acceptance gates](https://github.com/james-taplin/derailroader#what-a-finished-pack-must-pass).

The exported-bundle audit checks that required HUD and driving controls have feeders. It cannot prove feel, collision ownership, exact steam closure, or save/reload behavior. Use [Testing a pack in Derail Valley](https://github.com/james-taplin/derailroader/wiki/Testing-a-pack-in-Derail-Valley) to mark each input route pass, fail, or pending.
